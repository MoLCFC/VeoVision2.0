"""
Collect FIFA-style soccer match stats from a video.

This script estimates:
- possession percentage
- completed passes
- turnovers / interceptions
- shots, shots on target, goals (estimated)

The implementation uses the same VeoVision detection + tracking stack and writes
results to JSON and CSV files for downstream dashboards.
"""

import csv
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import supervision as sv
from inference import get_model
from tqdm import tqdm

# Add parent directory to path to import custom modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from veovision.configs_soccer import SoccerPitchConfiguration
from veovision.teams import TeamClassifier
from veovision.view import ViewTransformer


BALL_ID = 0
GOALKEEPER_ID = 1
PLAYER_ID = 2
REFEREE_ID = 3


@dataclass
class StatsConfig:
    detection_confidence: float = 0.3
    nms_threshold: float = 0.5
    keypoint_confidence_threshold: float = 0.5
    crop_stride: int = 30
    possession_distance_cm: float = 220.0
    min_possession_frames_for_pass: int = 5
    min_new_owner_frames: int = 3
    shot_cooldown_frames: int = 20
    goal_line_zone_cm: float = 260.0
    attacking_third_ratio: float = 0.66
    min_ball_speed_toward_goal_cm: float = 35.0
    min_ball_speed_total_cm: float = 55.0
    min_shot_owner_frames: int = 4


def extract_crops(
    video_path: str,
    detection_model,
    player_id: int = PLAYER_ID,
    stride: int = 30,
    confidence: float = 0.3,
    nms_threshold: float = 0.5,
) -> List[np.ndarray]:
    frame_generator = sv.get_video_frames_generator(source_path=video_path, stride=stride)
    crops: List[np.ndarray] = []
    for frame in tqdm(frame_generator, desc="Collecting Crops"):
        result = detection_model.infer(frame, confidence=confidence)[0]
        detections = sv.Detections.from_inference(result)
        detections = detections.with_nms(threshold=nms_threshold, class_agnostic=True)
        detections = detections[detections.class_id == player_id]
        crops.extend([sv.crop_image(frame, xyxy) for xyxy in detections.xyxy])
    return crops


def resolve_goalkeepers_team_id(players: sv.Detections, goalkeepers: sv.Detections) -> np.ndarray:
    if len(goalkeepers) == 0:
        return np.array([], dtype=int)
    if len(players) == 0:
        return np.zeros(len(goalkeepers), dtype=int)

    goalkeepers_xy = goalkeepers.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
    players_xy = players.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)

    team_0_players = players_xy[players.class_id == 0]
    team_1_players = players_xy[players.class_id == 1]

    if len(team_0_players) == 0:
        return np.ones(len(goalkeepers), dtype=int)
    if len(team_1_players) == 0:
        return np.zeros(len(goalkeepers), dtype=int)

    team_0_centroid = team_0_players.mean(axis=0)
    team_1_centroid = team_1_players.mean(axis=0)

    goalkeepers_team_id = []
    for goalkeeper_xy in goalkeepers_xy:
        dist_0 = np.linalg.norm(goalkeeper_xy - team_0_centroid)
        dist_1 = np.linalg.norm(goalkeeper_xy - team_1_centroid)
        goalkeepers_team_id.append(0 if dist_0 < dist_1 else 1)

    return np.array(goalkeepers_team_id, dtype=int)


def _empty_team_stats() -> Dict[str, int]:
    return {
        "possession_frames": 0,
        "completed_passes": 0,
        "turnovers": 0,
        "interceptions": 0,
        "estimated_shots": 0,
        "estimated_shots_on_target": 0,
        "estimated_goals": 0,
    }


def _goal_target_y_bounds(config: SoccerPitchConfiguration) -> Tuple[float, float]:
    goal_mid = config.width / 2.0
    goal_half = config.goal_box_width / 2.0
    return goal_mid - goal_half, goal_mid + goal_half


def _frame_to_time(frame_idx: int, fps: float) -> float:
    if fps <= 0:
        return 0.0
    return float(frame_idx) / float(fps)


def _time_label(seconds: float) -> str:
    whole = max(0, int(seconds))
    mins = whole // 60
    secs = whole % 60
    return f"{mins:02d}:{secs:02d}"


def _empty_player_stats(team_id: int, tracker_id: int) -> Dict[str, Any]:
    return {
        "team": int(team_id),
        "tracker_id": int(tracker_id),
        "touches": 0,
        "completed_passes": 0,
        "estimated_shots": 0,
    }


def _snapshot_timeline_frame(frame_idx: int, fps: float, team_stats: Dict[int, Dict[str, int]]) -> Dict[str, Any]:
    return {
        "frame": int(frame_idx),
        "time_sec": round(_frame_to_time(frame_idx, fps), 3),
        "team_0": {
            "possession_frames": int(team_stats[0]["possession_frames"]),
            "completed_passes": int(team_stats[0]["completed_passes"]),
            "turnovers": int(team_stats[0]["turnovers"]),
            "interceptions": int(team_stats[0]["interceptions"]),
            "estimated_shots": int(team_stats[0]["estimated_shots"]),
            "estimated_shots_on_target": int(team_stats[0]["estimated_shots_on_target"]),
            "estimated_goals": int(team_stats[0]["estimated_goals"]),
        },
        "team_1": {
            "possession_frames": int(team_stats[1]["possession_frames"]),
            "completed_passes": int(team_stats[1]["completed_passes"]),
            "turnovers": int(team_stats[1]["turnovers"]),
            "interceptions": int(team_stats[1]["interceptions"]),
            "estimated_shots": int(team_stats[1]["estimated_shots"]),
            "estimated_shots_on_target": int(team_stats[1]["estimated_shots_on_target"]),
            "estimated_goals": int(team_stats[1]["estimated_goals"]),
        },
    }


def _top_player(players: List[Dict[str, Any]], key: str, team_id: int) -> Optional[Dict[str, Any]]:
    team_players = [p for p in players if int(p.get("team", -1)) == team_id]
    if not team_players:
        return None
    team_players = sorted(team_players, key=lambda p: int(p.get(key, 0)), reverse=True)
    top = team_players[0]
    if int(top.get(key, 0)) <= 0:
        return None
    return top


def _select_ball_position(
    pitch_ball_xy: np.ndarray,
    previous_ball_xy: Optional[np.ndarray],
) -> Optional[np.ndarray]:
    if len(pitch_ball_xy) == 0:
        return None
    if len(pitch_ball_xy) == 1 or previous_ball_xy is None:
        return pitch_ball_xy[0]
    distances = np.linalg.norm(pitch_ball_xy - previous_ball_xy, axis=1)
    return pitch_ball_xy[int(np.argmin(distances))]


def collect_match_stats(
    source_video_path: str,
    output_json_path: str,
    output_csv_path: str,
    roboflow_api_key: Optional[str] = None,
    settings: Optional[StatsConfig] = None,
) -> Dict:
    settings = settings or StatsConfig()
    if roboflow_api_key is None:
        roboflow_api_key = os.getenv("ROBOFLOW_API_KEY", "urspUQutaAeYNtL3l5Nq")

    print("Loading detection models...")
    player_model = get_model(model_id="veovision-tnp3c/1", api_key=roboflow_api_key)
    pitch_model = get_model(model_id="football-field-detection-f07vi/15", api_key=roboflow_api_key)

    config = SoccerPitchConfiguration()
    video_info = sv.VideoInfo.from_video_path(source_video_path)
    tracker = sv.ByteTrack()

    print("Training team classifier...")
    crops = extract_crops(
        video_path=source_video_path,
        detection_model=player_model,
        stride=settings.crop_stride,
        confidence=settings.detection_confidence,
        nms_threshold=settings.nms_threshold,
    )

    team_classifier: Optional[TeamClassifier]
    if len(crops) == 0:
        print("WARNING: No player crops found. Defaulting all players to team_0.")
        team_classifier = None
    else:
        team_classifier = TeamClassifier()
        team_classifier.fit(crops)

    team_stats: Dict[int, Dict[str, int]] = {0: _empty_team_stats(), 1: _empty_team_stats()}

    active_owner_player: Optional[int] = None
    active_owner_team: Optional[int] = None
    active_owner_frames = 0
    pending_transition: Optional[Dict[str, Any]] = None
    last_ball_xy: Optional[np.ndarray] = None
    shot_cooldown = 0
    tracker_team_cache: Dict[int, int] = {}
    player_stats: Dict[int, Dict[str, Any]] = {}
    events: List[Dict[str, Any]] = []
    timeline: List[Dict[str, Any]] = []

    goal_y_min, goal_y_max = _goal_target_y_bounds(config)
    final_third_start = config.length * settings.attacking_third_ratio
    final_third_end = config.length * (1.0 - settings.attacking_third_ratio)

    frame_generator = sv.get_video_frames_generator(source_video_path)
    print("Collecting match stats...")
    for frame_idx, frame in enumerate(
        tqdm(frame_generator, total=video_info.total_frames, desc="Analyzing frames")
    ):
        detection_result = player_model.infer(frame, confidence=settings.detection_confidence)[0]
        detections = sv.Detections.from_inference(detection_result)

        ball_detections = detections[detections.class_id == BALL_ID]
        ball_detections.xyxy = sv.pad_boxes(ball_detections.xyxy, px=10)

        others = detections[detections.class_id != BALL_ID]
        others = others.with_nms(threshold=settings.nms_threshold, class_agnostic=True)
        others = tracker.update_with_detections(others)

        players = others[others.class_id == PLAYER_ID]
        goalkeepers = others[others.class_id == GOALKEEPER_ID]
        _referees = others[others.class_id == REFEREE_ID]

        if len(players) > 0:
            if team_classifier is None:
                players.class_id = np.zeros(len(players), dtype=int)
            else:
                assigned_team_ids = np.full(len(players), -1, dtype=int)
                unknown_indices: List[int] = []
                unknown_crops: List[np.ndarray] = []

                for idx, (tracker_id, xyxy) in enumerate(zip(players.tracker_id, players.xyxy)):
                    if tracker_id is not None and int(tracker_id) in tracker_team_cache:
                        assigned_team_ids[idx] = tracker_team_cache[int(tracker_id)]
                    else:
                        unknown_indices.append(idx)
                        unknown_crops.append(sv.crop_image(frame, xyxy))

                if len(unknown_crops) > 0:
                    predicted_unknown = team_classifier.predict(unknown_crops).astype(int)
                    for local_idx, predicted_team in zip(unknown_indices, predicted_unknown):
                        assigned_team_ids[local_idx] = int(predicted_team)
                        tracker_id = players.tracker_id[local_idx]
                        if tracker_id is not None:
                            tracker_team_cache[int(tracker_id)] = int(predicted_team)

                assigned_team_ids[assigned_team_ids < 0] = 0
                players.class_id = assigned_team_ids.astype(int)

        if len(goalkeepers) > 0:
            if team_classifier is None:
                goalkeepers.class_id = np.zeros(len(goalkeepers), dtype=int)
            else:
                goalkeepers.class_id = resolve_goalkeepers_team_id(players, goalkeepers)

        pitch_result = pitch_model.infer(frame, confidence=settings.detection_confidence)[0]
        key_points = sv.KeyPoints.from_inference(pitch_result)
        keypoint_mask = key_points.confidence[0] > settings.keypoint_confidence_threshold

        if np.count_nonzero(keypoint_mask) < 4:
            continue

        frame_reference_points = key_points.xy[0][keypoint_mask]
        pitch_reference_points = np.array(config.vertices)[keypoint_mask]

        try:
            view_transformer = ViewTransformer(
                source=frame_reference_points, target=pitch_reference_points
            )
        except ValueError:
            continue

        frame_ball_xy = ball_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
        pitch_ball_xy = view_transformer.transform_points(frame_ball_xy)

        frame_players_xy = players.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
        pitch_players_xy = view_transformer.transform_points(frame_players_xy)
        frame_goalkeepers_xy = goalkeepers.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
        pitch_goalkeepers_xy = view_transformer.transform_points(frame_goalkeepers_xy)

        owner_player: Optional[int] = None
        owner_team: Optional[int] = None

        previous_ball_xy = last_ball_xy.copy() if last_ball_xy is not None else None

        selected_ball_xy = _select_ball_position(pitch_ball_xy=pitch_ball_xy, previous_ball_xy=previous_ball_xy)
        if selected_ball_xy is not None:
            ball_xy = selected_ball_xy
            last_ball_xy = ball_xy
        elif last_ball_xy is not None:
            ball_xy = last_ball_xy
        else:
            ball_xy = None

        if ball_xy is not None:
            all_positions: List[np.ndarray] = []
            all_tracker_ids: List[int] = []
            all_team_ids: List[int] = []

            if len(pitch_players_xy) > 0:
                for position, tracker_id, team_id in zip(
                    pitch_players_xy, players.tracker_id, players.class_id
                ):
                    if tracker_id is None:
                        continue
                    all_positions.append(position)
                    all_tracker_ids.append(int(tracker_id))
                    all_team_ids.append(int(team_id))

            if len(pitch_goalkeepers_xy) > 0:
                for position, tracker_id, team_id in zip(
                    pitch_goalkeepers_xy, goalkeepers.tracker_id, goalkeepers.class_id
                ):
                    if tracker_id is None:
                        continue
                    all_positions.append(position)
                    all_tracker_ids.append(int(tracker_id))
                    all_team_ids.append(int(team_id))

            if len(all_positions) > 0:
                all_positions_np = np.array(all_positions)
                distances = np.linalg.norm(all_positions_np - ball_xy, axis=1)
                idx = int(np.argmin(distances))
                if float(distances[idx]) <= settings.possession_distance_cm:
                    owner_player = all_tracker_ids[idx]
                    owner_team = all_team_ids[idx]
                    if owner_player not in player_stats:
                        player_stats[owner_player] = _empty_player_stats(owner_team, owner_player)

        if active_owner_team is None and owner_team is not None:
            active_owner_team = owner_team
            active_owner_player = owner_player
            active_owner_frames = 1
            pending_transition = None
        elif active_owner_team is not None:
            if owner_team == active_owner_team and owner_player == active_owner_player:
                active_owner_frames += 1
                pending_transition = None
            elif owner_team is not None:
                if (
                    pending_transition is not None
                    and pending_transition["to_team"] == owner_team
                    and pending_transition["to_player"] == owner_player
                ):
                    pending_transition["frames"] += 1
                else:
                    pending_transition = {
                        "from_team": active_owner_team,
                        "from_player": active_owner_player,
                        "from_frames": active_owner_frames,
                        "to_team": owner_team,
                        "to_player": owner_player,
                        "frames": 1,
                    }

                if pending_transition["frames"] >= settings.min_new_owner_frames:
                    from_team = int(pending_transition["from_team"])
                    from_player = pending_transition["from_player"]
                    from_frames = int(pending_transition["from_frames"])
                    to_team = int(pending_transition["to_team"])
                    to_player = pending_transition["to_player"]

                    if (
                        to_team == from_team
                        and to_player != from_player
                        and from_frames >= settings.min_possession_frames_for_pass
                    ):
                        team_stats[from_team]["completed_passes"] += 1
                        if from_player is not None and from_player in player_stats:
                            player_stats[from_player]["completed_passes"] += 1
                        events.append(
                            {
                                "frame": int(frame_idx),
                                "time_sec": round(_frame_to_time(frame_idx, video_info.fps), 3),
                                "time_label": _time_label(_frame_to_time(frame_idx, video_info.fps)),
                                "event": "pass",
                                "team": from_team,
                                "from_tracker": int(from_player) if from_player is not None else None,
                                "to_tracker": int(to_player) if to_player is not None else None,
                            }
                        )
                    elif to_team != from_team and from_frames >= settings.min_possession_frames_for_pass:
                        team_stats[from_team]["turnovers"] += 1
                        team_stats[to_team]["interceptions"] += 1
                        events.append(
                            {
                                "frame": int(frame_idx),
                                "time_sec": round(_frame_to_time(frame_idx, video_info.fps), 3),
                                "time_label": _time_label(_frame_to_time(frame_idx, video_info.fps)),
                                "event": "turnover",
                                "team": from_team,
                                "next_team": to_team,
                                "from_tracker": int(from_player) if from_player is not None else None,
                                "to_tracker": int(to_player) if to_player is not None else None,
                            }
                        )

                    active_owner_team = to_team
                    active_owner_player = to_player
                    active_owner_frames = int(pending_transition["frames"])
                    pending_transition = None

        if active_owner_team is not None:
            team_stats[active_owner_team]["possession_frames"] += 1
            if active_owner_player is not None and active_owner_player in player_stats:
                player_stats[active_owner_player]["touches"] += 1

        if shot_cooldown > 0:
            shot_cooldown -= 1

        if (
            ball_xy is not None
            and active_owner_team is not None
            and shot_cooldown == 0
            and pending_transition is None
            and active_owner_frames >= settings.min_shot_owner_frames
        ):
            if previous_ball_xy is not None:
                toward_goal = 0.0
                in_attacking_zone = False
                near_goal_line = False
                movement_vector = ball_xy - previous_ball_xy
                total_speed = float(np.linalg.norm(movement_vector))

                if active_owner_team == 0:
                    toward_goal = ball_xy[0] - previous_ball_xy[0]
                    in_attacking_zone = ball_xy[0] >= final_third_start
                    near_goal_line = ball_xy[0] >= (config.length - settings.goal_line_zone_cm)
                else:
                    toward_goal = previous_ball_xy[0] - ball_xy[0]
                    in_attacking_zone = ball_xy[0] <= final_third_end
                    near_goal_line = ball_xy[0] <= settings.goal_line_zone_cm

                if (
                    toward_goal >= settings.min_ball_speed_toward_goal_cm
                    and total_speed >= settings.min_ball_speed_total_cm
                    and in_attacking_zone
                ):
                    team_stats[active_owner_team]["estimated_shots"] += 1
                    if active_owner_player is not None and active_owner_player in player_stats:
                        player_stats[active_owner_player]["estimated_shots"] += 1

                    shot_event: Dict[str, Any] = {
                        "frame": int(frame_idx),
                        "time_sec": round(_frame_to_time(frame_idx, video_info.fps), 3),
                        "time_label": _time_label(_frame_to_time(frame_idx, video_info.fps)),
                        "event": "shot",
                        "team": int(active_owner_team),
                        "tracker_id": int(active_owner_player) if active_owner_player is not None else None,
                    }
                    if goal_y_min <= ball_xy[1] <= goal_y_max and near_goal_line:
                        team_stats[active_owner_team]["estimated_shots_on_target"] += 1
                        shot_event["on_target"] = True
                    else:
                        shot_event["on_target"] = False

                    if (
                        (active_owner_team == 0 and ball_xy[0] >= config.length)
                        or (active_owner_team == 1 and ball_xy[0] <= 0)
                    ) and (goal_y_min <= ball_xy[1] <= goal_y_max):
                        team_stats[active_owner_team]["estimated_goals"] += 1
                        shot_event["is_goal"] = True
                    else:
                        shot_event["is_goal"] = False

                    events.append(shot_event)
                    shot_cooldown = settings.shot_cooldown_frames

        timeline.append(_snapshot_timeline_frame(frame_idx=frame_idx, fps=video_info.fps, team_stats=team_stats))

    total_possession_frames = team_stats[0]["possession_frames"] + team_stats[1]["possession_frames"]
    possession_team_0 = (
        (team_stats[0]["possession_frames"] / total_possession_frames) * 100.0
        if total_possession_frames > 0
        else 0.0
    )
    possession_team_1 = (
        (team_stats[1]["possession_frames"] / total_possession_frames) * 100.0
        if total_possession_frames > 0
        else 0.0
    )

    players_list = sorted(player_stats.values(), key=lambda entry: int(entry["touches"]), reverse=True)

    team_0_top_passer = _top_player(players_list, "completed_passes", team_id=0)
    team_1_top_passer = _top_player(players_list, "completed_passes", team_id=1)
    team_0_top_shooter = _top_player(players_list, "estimated_shots", team_id=0)
    team_1_top_shooter = _top_player(players_list, "estimated_shots", team_id=1)
    team_0_most_touches = _top_player(players_list, "touches", team_id=0)
    team_1_most_touches = _top_player(players_list, "touches", team_id=1)

    results = {
        "source_video": source_video_path,
        "total_frames": int(video_info.total_frames),
        "fps": float(video_info.fps),
        "heuristics_note": (
            "These are estimated event stats derived from detections/tracking and homography. "
            "Shot-related metrics are heuristic, not referee-grade labels."
        ),
        "events": events,
        "timeline": timeline,
        "player_stats": players_list,
        "player_insights": {
            "team_0": {
                "top_passer": team_0_top_passer,
                "top_shooter": team_0_top_shooter,
                "most_touches": team_0_most_touches,
            },
            "team_1": {
                "top_passer": team_1_top_passer,
                "top_shooter": team_1_top_shooter,
                "most_touches": team_1_most_touches,
            },
        },
        "team_0": {
            **team_stats[0],
            "possession_percent": round(possession_team_0, 2),
        },
        "team_1": {
            **team_stats[1],
            "possession_percent": round(possession_team_1, 2),
        },
    }

    json_dir = os.path.dirname(output_json_path)
    csv_dir = os.path.dirname(output_csv_path)
    if json_dir:
        os.makedirs(json_dir, exist_ok=True)
    if csv_dir:
        os.makedirs(csv_dir, exist_ok=True)

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "team",
                "possession_percent",
                "completed_passes",
                "turnovers",
                "interceptions",
                "estimated_shots",
                "estimated_shots_on_target",
                "estimated_goals",
            ]
        )
        for team_key in ("team_0", "team_1"):
            team_data = results[team_key]
            writer.writerow(
                [
                    team_key,
                    team_data["possession_percent"],
                    team_data["completed_passes"],
                    team_data["turnovers"],
                    team_data["interceptions"],
                    team_data["estimated_shots"],
                    team_data["estimated_shots_on_target"],
                    team_data["estimated_goals"],
                ]
            )

    print(f"Stats saved to JSON: {output_json_path}")
    print(f"Stats saved to CSV: {output_csv_path}")
    return results


if __name__ == "__main__":
    SOURCE_VIDEO_PATH = r"content\testvid.mp4"
    OUTPUT_JSON_PATH = r"content\testvid_match_stats.json"
    OUTPUT_CSV_PATH = r"content\testvid_match_stats.csv"
    ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "urspUQutaAeYNtL3l5Nq")

    collect_match_stats(
        source_video_path=SOURCE_VIDEO_PATH,
        output_json_path=OUTPUT_JSON_PATH,
        output_csv_path=OUTPUT_CSV_PATH,
        roboflow_api_key=ROBOFLOW_API_KEY,
    )
