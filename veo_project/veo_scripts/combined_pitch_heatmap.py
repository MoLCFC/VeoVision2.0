"""
Combined 2D Pitch and Heatmap Visualization
============================================
This script processes soccer match videos to create a combined visualization showing:
- 2D tactical pitch with player positions, ball, goalkeepers, and referees
- Voronoi diagram heatmap overlay showing territorial control by each team

The output displays both visualizations side-by-side or overlaid in a single video.

Features:
- Player and ball detection using YOLOv8
- Team classification using SigLIP embeddings
- Goalkeeper team assignment
- Pitch keypoint detection
- Homography transformation to map players to 2D pitch
- Combined visualization with player markers AND Voronoi heatmap

Author: VeoVision
"""

from tqdm import tqdm
import supervision as sv
import cv2
import os
import sys
import torch
import numpy as np

# Add parent directory to path to import custom modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from veovision.teams import TeamClassifier
from veovision.view import ViewTransformer
from veovision.annotators_soccer import (
    draw_pitch,
    draw_points_on_pitch,
    draw_pitch_voronoi_diagram,
)
from veovision.configs_soccer import SoccerPitchConfiguration
from inference import get_model

# ============================================================================
# Configuration
# ============================================================================

# API Configuration
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "urspUQutaAeYNtL3l5Nq")
PLAYER_DETECTION_MODEL_ID = "veovision-tnp3c/1"
PITCH_DETECTION_MODEL_ID = "football-field-detection-f07vi/15"

# Video Paths
SOURCE_VIDEO_PATH = r"content\testvid.mp4"
TARGET_VIDEO_PATH = r"content\testvid_combined_heatmap.mp4"

# Detection Parameters
CONFIDENCE_THRESHOLD = 0.3
NMS_THRESHOLD = 0.5
KEYPOINT_CONFIDENCE_THRESHOLD = 0.5

# Class IDs
BALL_ID = 0
GOALKEEPER_ID = 1
PLAYER_ID = 2
REFEREE_ID = 3

# Team Colors
TEAM_0_COLOR = sv.Color.from_hex("00BFFF")  # Cyan
TEAM_1_COLOR = sv.Color.from_hex("FF1493")  # Pink
REFEREE_COLOR = sv.Color.from_hex("FFD700")  # Gold
BALL_COLOR = sv.Color.WHITE

# Training Parameters
CROP_STRIDE = 30  # Sample every 30th frame for training data

# Visualization Options
HEATMAP_OPACITY = 0.8  # Opacity of Voronoi heatmap (0.0 to 1.0)
SHOW_SIDE_BY_SIDE = False  # True: side-by-side, False: overlay

# ============================================================================
# Helper Functions
# ============================================================================

def extract_crops(video_path: str, detection_model, player_id: int = PLAYER_ID, 
                  stride: int = CROP_STRIDE, confidence: float = CONFIDENCE_THRESHOLD):
    """
    Extract player crops from a video for training the team classifier.
    
    Args:
        video_path: Path to the video file
        detection_model: The player detection model to use
        player_id: Class ID for players (default: 2)
        stride: Frame stride for sampling (default: 30)
        confidence: Detection confidence threshold (default: 0.3)
    
    Returns:
        List of cropped player images
    """
    frame_generator = sv.get_video_frames_generator(source_path=video_path, stride=stride)
    crops = []
    
    print("Extracting player crops for team classification training...")
    for frame in tqdm(frame_generator, desc='Collecting Crops'):
        result = detection_model.infer(frame, confidence=confidence)[0]
        detections = sv.Detections.from_inference(result)
        detections = detections.with_nms(threshold=NMS_THRESHOLD, class_agnostic=True)
        detections = detections[detections.class_id == player_id]
        players_crops = [sv.crop_image(frame, xyxy) for xyxy in detections.xyxy]
        crops += players_crops
    
    print(f"Collected {len(crops)} player crops")
    return crops


def resolve_goalkeepers_team_id(
    players: sv.Detections,
    goalkeepers: sv.Detections
) -> np.ndarray:
    """
    Assign goalkeepers to teams based on proximity to team centroids.
    
    Args:
        players: Detections of field players with team assignments
        goalkeepers: Detections of goalkeepers
    
    Returns:
        Array of team IDs for goalkeepers
    """
    if len(goalkeepers) == 0:
        return np.array([])
    
    if len(players) == 0:
        return np.zeros(len(goalkeepers), dtype=int)
    
    goalkeepers_xy = goalkeepers.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
    players_xy = players.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
    
    # Calculate team centroids
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

    return np.array(goalkeepers_team_id)


def process_video_combined(source_video_path: str, target_video_path: str, 
                           roboflow_api_key: str = None):
    """
    Main video processing function that creates combined 2D pitch + heatmap visualization.
    
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
    
    # Determine device
    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {DEVICE}")
    
    # Train team classifier
    print("Training team classifier...")
    crops = extract_crops(source_video_path, PLAYER_DETECTION_MODEL)
    
    if len(crops) == 0:
        print("WARNING: No player crops collected. Cannot train team classifier.")
        print("The video will be processed without team classification.")
        team_classifier = None
    else:
        team_classifier = TeamClassifier(device=DEVICE)
        team_classifier.fit(crops)
        print("Team classifier training complete!")

    # Setup video processing
    print("Processing video...")
    video_info = sv.VideoInfo.from_video_path(source_video_path)
    video_sink = sv.VideoSink(target_video_path, video_info=video_info)
    frame_generator = sv.get_video_frames_generator(source_video_path)

    # Initialize tracker
    tracker = sv.ByteTrack()

    # Track last known ball position for possession calculation
    last_known_ball_position = None

    # Process video frames
    with video_sink:
        for frame in tqdm(frame_generator, total=video_info.total_frames, desc='Processing frames'):
            # Detect players, ball, goalkeepers, referees
            result = PLAYER_DETECTION_MODEL.infer(frame, confidence=CONFIDENCE_THRESHOLD)[0]
            detections = sv.Detections.from_inference(result)
            
            # Process ball detections
            ball_detections = detections[detections.class_id == BALL_ID]
            ball_detections.xyxy = sv.pad_boxes(xyxy=ball_detections.xyxy, px=10)

            # Process non-ball detections
            all_detections = detections[detections.class_id != BALL_ID]
            all_detections = all_detections.with_nms(threshold=NMS_THRESHOLD, class_agnostic=True)
            
            # Track detections
            all_detections = tracker.update_with_detections(all_detections)

            # Separate by class
            players_detections = all_detections[all_detections.class_id == PLAYER_ID]
            goalkeepers_detections = all_detections[all_detections.class_id == GOALKEEPER_ID]
            referees_detections = all_detections[all_detections.class_id == REFEREE_ID]
            
            # Classify players into teams
            if len(players_detections) > 0 and team_classifier is not None:
                players_crops = [sv.crop_image(frame, xyxy) for xyxy in players_detections.xyxy]
                players_detections.class_id = team_classifier.predict(players_crops).astype(int)
            elif len(players_detections) > 0:
                # Assign all to team 0 if no classifier
                players_detections.class_id = np.zeros(len(players_detections), dtype=int)

            # Assign goalkeepers to teams
            if len(goalkeepers_detections) > 0 and team_classifier is not None:
                goalkeepers_detections.class_id = resolve_goalkeepers_team_id(
                    players_detections, goalkeepers_detections
                ).astype(int)
            elif len(goalkeepers_detections) > 0:
                # Assign all to team 0 if no classifier
                goalkeepers_detections.class_id = np.zeros(len(goalkeepers_detections), dtype=int)

            # Detect pitch keypoints
            result = PITCH_DETECTION_MODEL.infer(frame, confidence=CONFIDENCE_THRESHOLD)[0]
            key_points = sv.KeyPoints.from_inference(result)

            # Filter keypoints by confidence
            filter = key_points.confidence[0] > KEYPOINT_CONFIDENCE_THRESHOLD
            frame_reference_points = key_points.xy[0][filter]
            pitch_reference_points = np.array(CONFIG.vertices)[filter]

            # Create view transformer
            view_transformer = ViewTransformer(
                source=frame_reference_points,
                target=pitch_reference_points
            )

            # Transform coordinates to pitch space
            frame_ball_xy = ball_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
            pitch_ball_xy = view_transformer.transform_points(frame_ball_xy)

            frame_players_xy = players_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
            pitch_players_xy = view_transformer.transform_points(frame_players_xy)

            frame_goalkeepers_xy = goalkeepers_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
            pitch_goalkeepers_xy = view_transformer.transform_points(frame_goalkeepers_xy)

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
                    all_tracker_ids = np.array(all_tracker_ids)
                    
                    # Calculate distances from last known ball position to all players
                    distances = np.linalg.norm(all_player_positions - last_known_ball_position, axis=1)
                    closest_player_idx = np.argmin(distances)
                    player_with_ball_tracker_id = all_tracker_ids[closest_player_idx]

            # Draw base pitch
            pitch = draw_pitch(config=CONFIG)

            # Draw Voronoi heatmap (with transparency)
            if len(players_detections) > 0:
                team_0_mask = players_detections.class_id == 0
                team_1_mask = players_detections.class_id == 1
                
                team_0_xy = pitch_players_xy[team_0_mask]
                team_1_xy = pitch_players_xy[team_1_mask]
                
                # Only draw Voronoi if both teams have at least one player
                if len(team_0_xy) > 0 and len(team_1_xy) > 0:
                    # Create heatmap layer
                    heatmap = draw_pitch(config=CONFIG)
                    heatmap = draw_pitch_voronoi_diagram(
                        config=CONFIG, 
                        team_1_xy=team_0_xy,
                        team_2_xy=team_1_xy,
                        team_1_color=TEAM_0_COLOR,
                        team_2_color=TEAM_1_COLOR,
                        pitch=heatmap
                    )
                    
                    # Blend heatmap with base pitch
                    pitch = cv2.addWeighted(pitch, 1 - HEATMAP_OPACITY, heatmap, HEATMAP_OPACITY, 0)

            # Draw player markers on top of heatmap
            # Draw ball (white with black edge)
            pitch = draw_points_on_pitch(
                config=CONFIG, 
                xy=pitch_ball_xy, 
                face_color=BALL_COLOR, 
                edge_color=sv.Color.BLACK, 
                radius=10, 
                pitch=pitch
            )

            # Draw team 0 players (cyan/blue)
            if len(players_detections) > 0:
                team_0_mask = players_detections.class_id == 0
                team_0_tracker_ids = players_detections.tracker_id[team_0_mask]
                for xy, tracker_id in zip(pitch_players_xy[team_0_mask], team_0_tracker_ids):
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
                            face_color=TEAM_0_COLOR, 
                            edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                            radius=10, 
                            pitch=pitch
                        )
                    else:
                        pitch = draw_points_on_pitch(
                            config=CONFIG, 
                            xy=np.array([xy]), 
                            face_color=TEAM_0_COLOR, 
                            edge_color=sv.Color.BLACK, 
                            radius=10, 
                            pitch=pitch
                        )

                # Draw team 1 players (pink/magenta)
                team_1_mask = players_detections.class_id == 1
                team_1_tracker_ids = players_detections.tracker_id[team_1_mask]
                for xy, tracker_id in zip(pitch_players_xy[team_1_mask], team_1_tracker_ids):
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
                            face_color=TEAM_1_COLOR, 
                            edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                            radius=10, 
                            pitch=pitch
                        )
                    else:
                        pitch = draw_points_on_pitch(
                            config=CONFIG, 
                            xy=np.array([xy]), 
                            face_color=TEAM_1_COLOR, 
                            edge_color=sv.Color.BLACK, 
                            radius=10, 
                            pitch=pitch
                        )

            # Draw goalkeepers
            if len(goalkeepers_detections) > 0:
                # Team 0 goalkeeper (cyan/blue)
                gk_team_0_mask = goalkeepers_detections.class_id == 0
                gk_team_0_tracker_ids = goalkeepers_detections.tracker_id[gk_team_0_mask]
                for xy, tracker_id in zip(pitch_goalkeepers_xy[gk_team_0_mask], gk_team_0_tracker_ids):
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
                            face_color=TEAM_0_COLOR, 
                            edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                            radius=10, 
                            pitch=pitch
                        )
                    else:
                        pitch = draw_points_on_pitch(
                            config=CONFIG, 
                            xy=np.array([xy]), 
                            face_color=TEAM_0_COLOR, 
                            edge_color=sv.Color.BLACK, 
                            radius=10, 
                            pitch=pitch
                        )

                # Team 1 goalkeeper (pink/magenta)
                gk_team_1_mask = goalkeepers_detections.class_id == 1
                gk_team_1_tracker_ids = goalkeepers_detections.tracker_id[gk_team_1_mask]
                for xy, tracker_id in zip(pitch_goalkeepers_xy[gk_team_1_mask], gk_team_1_tracker_ids):
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
                            face_color=TEAM_1_COLOR, 
                            edge_color=sv.Color.from_hex("00FF00"),  # Neon green
                            radius=10, 
                            pitch=pitch
                        )
                    else:
                        pitch = draw_points_on_pitch(
                            config=CONFIG, 
                            xy=np.array([xy]), 
                            face_color=TEAM_1_COLOR, 
                            edge_color=sv.Color.BLACK, 
                            radius=10, 
                            pitch=pitch
                        )

            # Draw referees (yellow/gold)
            if len(referees_detections) > 0:
                pitch = draw_points_on_pitch(
                    config=CONFIG, 
                    xy=pitch_referees_xy, 
                    face_color=REFEREE_COLOR, 
                    edge_color=sv.Color.BLACK, 
                    radius=10, 
                    pitch=pitch
                )

            # Resize pitch to match video dimensions
            pitch_resized = cv2.resize(pitch, (video_info.width, video_info.height))
            video_sink.write_frame(pitch_resized)

    print(f"Combined visualization complete! Output saved to: {target_video_path}")


if __name__ == "__main__":
    # Configuration
    SOURCE_VIDEO_PATH = r"content\testvid.mp4"
    TARGET_VIDEO_PATH = r"content\testvid_combined_pitch_heatmap.mp4"
    
    # Optional: Set your Roboflow API key here or use environment variable
    ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "urspUQutaAeYNtL3l5Nq")
    
    # Process the video
    process_video_combined(SOURCE_VIDEO_PATH, TARGET_VIDEO_PATH, ROBOFLOW_API_KEY)
