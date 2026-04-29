"""
Soccer 2D Pitch Visualization - Top-Down View
This script processes soccer videos to create a 2D top-down view of the pitch,
showing player positions, ball location, goalkeepers, and referees mapped onto
a tactical diagram.
"""

import os
import sys
import numpy as np
import cv2
from typing import Dict, Optional
from tqdm import tqdm
import supervision as sv
from inference import get_model

# Add parent directory to path to import custom modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from veovision.teams import TeamClassifier
from veovision.view import ViewTransformer
from veovision.configs_soccer import SoccerPitchConfiguration
from veovision.annotators_soccer import draw_pitch, draw_points_on_pitch


def extract_crops(video_path: str, player_detection_model, player_id: int = 2, 
                  stride: int = 30, confidence: float = 0.3):
    """
    Extract player crops from a video for team classification training.
    
    Args:
        video_path: Path to the video file
        player_detection_model: The player detection model
        player_id: Class ID for players (default: 2)
        stride: Frame stride for sampling (default: 30)
        confidence: Detection confidence threshold (default: 0.3)
    
    Returns:
        List of cropped player images
    """
    frame_generator = sv.get_video_frames_generator(source_path=video_path, stride=stride)
    crops = []
    
    for frame in tqdm(frame_generator, desc='Collecting Crops'):
        result = player_detection_model.infer(frame, confidence=confidence)[0]
        detections = sv.Detections.from_inference(result)
        detections = detections.with_nms(threshold=0.5, class_agnostic=True)
        detections = detections[detections.class_id == player_id]
        players_crops = [sv.crop_image(frame, xyxy) for xyxy in detections.xyxy]
        crops += players_crops
    
    return crops


def resolve_goalkeepers_team_id(players: sv.Detections, goalkeepers: sv.Detections) -> np.ndarray:
    """
    Assign goalkeepers to teams based on proximity to player centroids.
    
    Args:
        players: Detections of players with team class_id assigned
        goalkeepers: Detections of goalkeepers
    
    Returns:
        Array of team IDs for goalkeepers
    """
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


def process_video_2d_pitch(source_video_path: str, target_video_path: str, 
                            roboflow_api_key: str = None):
    """
    Process a soccer video and create a 2D top-down pitch visualization.
    
    Args:
        source_video_path: Path to input video
        target_video_path: Path to output video (2D pitch view)
        roboflow_api_key: Roboflow API key (optional, uses env var if not provided)
    """
    # Get API key
    if roboflow_api_key is None:
        roboflow_api_key = os.getenv("ROBOFLOW_API_KEY", "urspUQutaAeYNtL3l5Nq")
    
    # Load detection models
    print("Loading detection models...")
    PLAYER_DETECTION_MODEL_ID = "veovision-tnp3c/1"
    PLAYER_DETECTION_MODEL = get_model(
        model_id=PLAYER_DETECTION_MODEL_ID,
        api_key=roboflow_api_key
    )
    
    PITCH_DETECTION_MODEL_ID = "football-field-detection-f07vi/15"
    PITCH_DETECTION_MODEL = get_model(
        model_id=PITCH_DETECTION_MODEL_ID, 
        api_key=roboflow_api_key
    )
    
    # Load pitch configuration
    CONFIG = SoccerPitchConfiguration()
    
    # Extract crops and train team classifier
    print("Training team classifier...")
    crops = extract_crops(source_video_path, PLAYER_DETECTION_MODEL)
    team_classifier = None
    if len(crops) > 0:
        team_classifier = TeamClassifier()
        team_classifier.fit(crops)
    
    # Video processing setup
    print("Processing video and generating 2D pitch view...")
    video_info = sv.VideoInfo.from_video_path(source_video_path)
    video_sink = sv.VideoSink(target_video_path, video_info=video_info)
    frame_generator = sv.get_video_frames_generator(source_video_path)
    
    tracker = sv.ByteTrack()
    BALL_ID = 0
    GOALKEEPER_ID = 1
    PLAYER_ID = 2
    REFEREE_ID = 3
    
    # Track last known ball position for possession calculation
    last_known_ball_position = None
    tracker_team_cache: Dict[int, int] = {}
    last_view_transformer: Optional[ViewTransformer] = None
    transform_stale_frames = 0
    MAX_TRANSFORM_STALE_FRAMES = 12
    
    with video_sink:
        for frame in tqdm(frame_generator, total=video_info.total_frames, desc="Processing frames"):
            # Player/ball/referee detection
            result = PLAYER_DETECTION_MODEL.infer(frame, confidence=0.3)[0]
            detections = sv.Detections.from_inference(result)
            
            ball_detections = detections[detections.class_id == BALL_ID]
            ball_detections.xyxy = sv.pad_boxes(xyxy=ball_detections.xyxy, px=10)

            all_detections = detections[detections.class_id != BALL_ID]
            all_detections = all_detections.with_nms(threshold=0.5, class_agnostic=True)
            
            # Track detections
            all_detections = tracker.update_with_detections(all_detections)

            # Classify teams
            players_detections = all_detections[all_detections.class_id == PLAYER_ID]
            goalkeepers_detections = all_detections[all_detections.class_id == GOALKEEPER_ID]
            referees_detections = all_detections[all_detections.class_id == REFEREE_ID]
            
            if len(players_detections) > 0:
                if team_classifier is None:
                    players_detections.class_id = np.zeros(len(players_detections), dtype=int)
                else:
                    assigned_team_ids = np.full(len(players_detections), -1, dtype=int)
                    unknown_indices = []
                    unknown_crops = []
                    for idx, (tracker_id, xyxy) in enumerate(zip(players_detections.tracker_id, players_detections.xyxy)):
                        if tracker_id is not None and int(tracker_id) in tracker_team_cache:
                            assigned_team_ids[idx] = tracker_team_cache[int(tracker_id)]
                        else:
                            unknown_indices.append(idx)
                            unknown_crops.append(sv.crop_image(frame, xyxy))

                    if len(unknown_crops) > 0:
                        predicted_unknown = team_classifier.predict(unknown_crops).astype(int)
                        for local_idx, predicted_team in zip(unknown_indices, predicted_unknown):
                            assigned_team_ids[local_idx] = int(predicted_team)
                            tracker_id = players_detections.tracker_id[local_idx]
                            if tracker_id is not None:
                                tracker_team_cache[int(tracker_id)] = int(predicted_team)

                    assigned_team_ids[assigned_team_ids < 0] = 0
                    players_detections.class_id = assigned_team_ids.astype(int)

            goalkeepers_detections.class_id = resolve_goalkeepers_team_id(
                players_detections, goalkeepers_detections
            ).astype(int)

            # Pitch detection and transformation
            result = PITCH_DETECTION_MODEL.infer(frame, confidence=0.3)[0]
            key_points = sv.KeyPoints.from_inference(result)
            view_transformer = None
            if (
                key_points.confidence is not None
                and len(key_points.confidence) > 0
                and key_points.xy is not None
                and len(key_points.xy) > 0
            ):
                filter_mask = key_points.confidence[0] > 0.5
                if np.count_nonzero(filter_mask) >= 4:
                    frame_reference_points = key_points.xy[0][filter_mask]
                    pitch_reference_points = np.array(CONFIG.vertices)[filter_mask]
                    view_transformer = ViewTransformer(
                        source=frame_reference_points,
                        target=pitch_reference_points
                    )
                    last_view_transformer = view_transformer
                    transform_stale_frames = 0
            if view_transformer is None and last_view_transformer is not None and transform_stale_frames < MAX_TRANSFORM_STALE_FRAMES:
                transform_stale_frames += 1
                view_transformer = last_view_transformer
            if view_transformer is None:
                continue

            # Transform ball coordinates
            frame_ball_xy = ball_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
            pitch_ball_xy = view_transformer.transform_points(frame_ball_xy)

            # Transform player coordinates
            frame_players_xy = players_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
            pitch_players_xy = view_transformer.transform_points(frame_players_xy)

            # Transform goalkeeper coordinates
            frame_goalkeepers_xy = goalkeepers_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
            pitch_goalkeepers_xy = view_transformer.transform_points(frame_goalkeepers_xy)

            # Transform referee coordinates
            frame_referees_xy = referees_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
            pitch_referees_xy = view_transformer.transform_points(frame_referees_xy)

            # Update last known ball position if ball is detected
            if len(pitch_ball_xy) > 0:
                last_known_ball_position = pitch_ball_xy[0]

            # Find player with ball possession (closest to last known ball position)
            player_with_ball_tracker_id = None
            if last_known_ball_position is not None:
                # Combine all players and goalkeepers with their tracker IDs
                all_player_positions = []
                all_tracker_ids = []
                
                # Add players
                if len(pitch_players_xy) > 0:
                    all_player_positions.extend(pitch_players_xy)
                    all_tracker_ids.extend(players_detections.tracker_id)
                
                # Add goalkeepers
                if len(pitch_goalkeepers_xy) > 0:
                    all_player_positions.extend(pitch_goalkeepers_xy)
                    all_tracker_ids.extend(goalkeepers_detections.tracker_id)
                
                if len(all_player_positions) > 0:
                    all_player_positions = np.array(all_player_positions)
                    all_tracker_ids = np.array(all_tracker_ids, dtype=object)
                    
                    # Calculate distances from last known ball position to all players
                    distances = np.linalg.norm(all_player_positions - last_known_ball_position, axis=1)
                    closest_player_idx = np.argmin(distances)
                    player_with_ball_tracker_id = all_tracker_ids[closest_player_idx]

            # Draw pitch
            pitch = draw_pitch(config=CONFIG)

            # Draw ball (white with black edge)
            pitch = draw_points_on_pitch(
                config=CONFIG, 
                xy=pitch_ball_xy, 
                face_color=sv.Color.WHITE, 
                edge_color=sv.Color.BLACK, 
                radius=10, 
                pitch=pitch
            )
           
            # Draw team 0 players (cyan/blue)
            team_0_mask = players_detections.class_id == 0
            team_0_tracker_ids = players_detections.tracker_id[team_0_mask]
            for i, (xy, tracker_id) in enumerate(zip(pitch_players_xy[team_0_mask], team_0_tracker_ids)):
                # Check if this player has possession
                if player_with_ball_tracker_id is not None and tracker_id == player_with_ball_tracker_id:
                    # Draw outer neon green aura ring first (larger)
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("00FF00"),  # Neon green
                        edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                        radius=16, 
                        pitch=pitch
                    )
                    # Draw player with neon green edge on top
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("00BFFF"), 
                        edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                        radius=10, 
                        pitch=pitch
                    )
                else:
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("00BFFF"), 
                        edge_color=sv.Color.BLACK, 
                        radius=10, 
                        pitch=pitch
                    )

            # Draw team 1 players (pink/magenta)
            team_1_mask = players_detections.class_id == 1
            team_1_tracker_ids = players_detections.tracker_id[team_1_mask]
            for i, (xy, tracker_id) in enumerate(zip(pitch_players_xy[team_1_mask], team_1_tracker_ids)):
                # Check if this player has possession
                if player_with_ball_tracker_id is not None and tracker_id == player_with_ball_tracker_id:
                    # Draw outer neon green aura ring first (larger)
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("00FF00"),  # Neon green
                        edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                        radius=16, 
                        pitch=pitch
                    )
                    # Draw player with neon green edge on top
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("FF1493"), 
                        edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                        radius=10, 
                        pitch=pitch
                    )
                else:
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("FF1493"), 
                        edge_color=sv.Color.BLACK, 
                        radius=10, 
                        pitch=pitch
                    )

            # Draw team 0 goalkeeper (cyan/blue)
            gk_team_0_mask = goalkeepers_detections.class_id == 0
            gk_team_0_tracker_ids = goalkeepers_detections.tracker_id[gk_team_0_mask]
            for i, (xy, tracker_id) in enumerate(zip(pitch_goalkeepers_xy[gk_team_0_mask], gk_team_0_tracker_ids)):
                # Check if this goalkeeper has possession
                if player_with_ball_tracker_id is not None and tracker_id == player_with_ball_tracker_id:
                    # Draw outer neon green aura ring first (larger)
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("00FF00"),  # Neon green
                        edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                        radius=16, 
                        pitch=pitch
                    )
                    # Draw goalkeeper with neon green edge on top
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("00BFFF"), 
                        edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                        radius=10, 
                        pitch=pitch
                    )
                else:
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("00BFFF"), 
                        edge_color=sv.Color.BLACK, 
                        radius=10, 
                        pitch=pitch
                    )

            # Draw team 1 goalkeeper (pink/magenta)
            gk_team_1_mask = goalkeepers_detections.class_id == 1
            gk_team_1_tracker_ids = goalkeepers_detections.tracker_id[gk_team_1_mask]
            for i, (xy, tracker_id) in enumerate(zip(pitch_goalkeepers_xy[gk_team_1_mask], gk_team_1_tracker_ids)):
                # Check if this goalkeeper has possession
                if player_with_ball_tracker_id is not None and tracker_id == player_with_ball_tracker_id:
                    # Draw outer neon green aura ring first (larger)
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("00FF00"),  # Neon green
                        edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                        radius=16, 
                        pitch=pitch
                    )
                    # Draw goalkeeper with neon green edge on top
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("FF1493"), 
                        edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                        radius=10, 
                        pitch=pitch
                    )
                else:
                    pitch = draw_points_on_pitch(
                        config=CONFIG, 
                        xy=np.array([xy]), 
                        face_color=sv.Color.from_hex("FF1493"), 
                        edge_color=sv.Color.BLACK, 
                        radius=10, 
                        pitch=pitch
                    )

            # Draw referees (yellow/gold)
            pitch = draw_points_on_pitch(
                config=CONFIG, 
                xy=pitch_referees_xy, 
                face_color=sv.Color.from_hex("FFD700"), 
                edge_color=sv.Color.BLACK, 
                radius=10, 
                pitch=pitch
            )

            # Resize pitch to match video dimensions
            pitch_resized = cv2.resize(pitch, (video_info.width, video_info.height))
            video_sink.write_frame(pitch_resized)
    
    print(f"2D pitch visualization complete! Output saved to: {target_video_path}")


if __name__ == "__main__":
    # Configuration
    SOURCE_VIDEO_PATH = r"content\testvid.mp4"
    TARGET_VIDEO_PATH = r"content\testvid_2d_pitch.mp4"
    
    # Optional: Set your Roboflow API key here or use environment variable
    ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "urspUQutaAeYNtL3l5Nq")
    
    # Process the video
    process_video_2d_pitch(SOURCE_VIDEO_PATH, TARGET_VIDEO_PATH, ROBOFLOW_API_KEY)
