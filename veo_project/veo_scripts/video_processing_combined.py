"""
Soccer Video Analysis with Player Detection, Team Classification, and Pitch Mapping
This script processes soccer videos to detect players, ball, goalkeepers, and referees,
classifies players into teams, and overlays pitch detection lines.
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


def extract_crops(video_path: str, player_detection_model, player_id: int = 2, 
                  stride: int = 30, confidence: float = 0.3):
    """
    Extract player crops from a video.
    
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


def process_video(source_video_path: str, target_video_path: str, 
                  roboflow_api_key: str = None):
    """
    Process a soccer video with complete analysis and annotations.
    
    Args:
        source_video_path: Path to input video
        target_video_path: Path to output video
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
    
    # Setup annotators for detections
    ellipse_annotator = sv.EllipseAnnotator(
        color=sv.ColorPalette.from_hex(['#00BFFF', '#FF1493', '#FFD700']),
        thickness=2
    )
    
    triangle_annotator = sv.TriangleAnnotator(
        color=sv.Color.from_hex('#FFD700'),
        base=25,
        height=21,
        outline_thickness=1
    )
    
    label_annotator = sv.LabelAnnotator(
        color=sv.ColorPalette.from_hex(['#00BFFF', '#FF1493', '#FFD700']),
        text_color=sv.Color.from_hex('#000000'),
        text_position=sv.Position.BOTTOM_CENTER
    )
    
    # Setup annotators for pitch lines
    edge_annotator = sv.EdgeAnnotator(
        color=sv.Color.from_hex('#00BFFF'),
        thickness=2, 
        edges=CONFIG.edges
    )
    
    vertex_annotator = sv.VertexAnnotator(
        color=sv.Color.from_hex('#FF1493'),
        radius=8
    )
    
    vertex_annotator_2 = sv.VertexAnnotator(
        color=sv.Color.from_hex('#00BFFF'),
        radius=8
    )
    
    # Video processing setup
    print("Processing video...")
    video_info = sv.VideoInfo.from_video_path(source_video_path)
    video_sink = sv.VideoSink(target_video_path, video_info=video_info)
    frame_generator = sv.get_video_frames_generator(source_video_path)
    
    tracker = sv.ByteTrack()
    BALL_ID = 0
    GOALKEEPER_ID = 1
    PLAYER_ID = 2
    REFEREE_ID = 3
    MAX_TRANSFORM_STALE_FRAMES = 12
    tracker_team_cache: Dict[int, int] = {}
    last_view_transformer: Optional[ViewTransformer] = None
    transform_stale_frames = 0
    
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

            referees_detections.class_id -= 1

            all_detections = sv.Detections.merge([
                players_detections, 
                goalkeepers_detections, 
                referees_detections
            ])

            labels = [
                f"{tracker_id}" if tracker_id is not None else ""
                for tracker_id in all_detections.tracker_id
            ]
            
            # Pitch detection and line transformation
            frame_all_key_points = None
            frame_reference_key_points = None
            pitch_result = PITCH_DETECTION_MODEL.infer(frame, confidence=0.3)[0]
            key_points = sv.KeyPoints.from_inference(pitch_result)

            if (
                key_points.confidence is not None
                and len(key_points.confidence) > 0
                and key_points.xy is not None
                and len(key_points.xy) > 0
            ):
                filter_mask = key_points.confidence[0] > 0.5
                if np.count_nonzero(filter_mask) >= 4:
                    frame_reference_points = key_points.xy[0][filter_mask]
                    frame_reference_key_points = sv.KeyPoints(
                        xy=frame_reference_points[np.newaxis, ...]
                    )

                    pitch_reference_points = np.array(CONFIG.vertices)[filter_mask]

                    transformer = ViewTransformer(
                        source=pitch_reference_points,
                        target=frame_reference_points
                    )
                    last_view_transformer = transformer
                    transform_stale_frames = 0

                    pitch_all_points = np.array(CONFIG.vertices)
                    frame_all_points = transformer.transform_points(points=pitch_all_points)
                    frame_all_key_points = sv.KeyPoints(xy=frame_all_points[np.newaxis, ...])
                elif last_view_transformer is not None and transform_stale_frames < MAX_TRANSFORM_STALE_FRAMES:
                    transform_stale_frames += 1
                    pitch_all_points = np.array(CONFIG.vertices)
                    frame_all_points = last_view_transformer.transform_points(points=pitch_all_points)
                    frame_all_key_points = sv.KeyPoints(xy=frame_all_points[np.newaxis, ...])
            elif last_view_transformer is not None and transform_stale_frames < MAX_TRANSFORM_STALE_FRAMES:
                transform_stale_frames += 1
                pitch_all_points = np.array(CONFIG.vertices)
                frame_all_points = last_view_transformer.transform_points(points=pitch_all_points)
                frame_all_key_points = sv.KeyPoints(xy=frame_all_points[np.newaxis, ...])
            
            # Annotate frame with everything
            annotated_frame = frame.copy()
            
            # Draw pitch lines first (background)
            if frame_all_key_points is not None:
                annotated_frame = edge_annotator.annotate(
                    scene=annotated_frame,
                    key_points=frame_all_key_points
                )
                annotated_frame = vertex_annotator_2.annotate(
                    scene=annotated_frame,
                    key_points=frame_all_key_points
                )
            if frame_reference_key_points is not None:
                annotated_frame = vertex_annotator.annotate(
                    scene=annotated_frame,
                    key_points=frame_reference_key_points
                )
            
            # Draw detections on top
            annotated_frame = ellipse_annotator.annotate(
                scene=annotated_frame, 
                detections=all_detections
            )
            annotated_frame = triangle_annotator.annotate(
                scene=annotated_frame, 
                detections=ball_detections
            )
            annotated_frame = label_annotator.annotate(
                scene=annotated_frame, 
                detections=all_detections, 
                labels=labels
            )
            
            video_sink.write_frame(annotated_frame)
    
    print(f"Video processing complete! Output saved to: {target_video_path}")


if __name__ == "__main__":
    # Configuration
    SOURCE_VIDEO_PATH = r"old_content\testvid.mp4"
    TARGET_VIDEO_PATH = r"old_content\testvid_combined_result.mp4"
    
    # Optional: Set your Roboflow API key here or use environment variable
    ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "urspUQutaAeYNtL3l5Nq")
    
    # Process the video
    process_video(SOURCE_VIDEO_PATH, TARGET_VIDEO_PATH, ROBOFLOW_API_KEY)
