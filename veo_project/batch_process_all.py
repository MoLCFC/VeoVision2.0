"""
Batch Processing Script for VeoVision
======================================
This script processes all videos in the sample_content folder and runs all 4 analysis scripts on each video:
1. video_processing_combined.py - Full player detection with team classification
2. pitch_2d_visualization.py - 2D top-down tactical view
3. combined_pitch_heatmap.py - Heatmap with Voronoi diagram
4. ball_tracking.py - Ball tracking visualization

All outputs are saved to the data_content folder with descriptive names.

Usage:
    python batch_process_all.py

The script will automatically:
- Find all .mp4 files in regular_clips/sample_content/
- Process each video with all 4 scripts
- Save outputs to regular_clips/data_content/
"""

import os
import sys
import glob
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the processing functions from each script
from veo_project.veo_scripts.video_processing_combined import process_video
from veo_project.veo_scripts.pitch_2d_visualization import process_video_2d_pitch
from veo_project.veo_scripts.combined_pitch_heatmap import process_video_combined
# Note: ball_tracking.py doesn't have a function interface, we'll need to handle it differently


def process_ball_tracking(source_path: str, target_path: str, roboflow_api_key: str):
    """
    Process ball tracking by modifying and running the ball_tracking script.
    This is a workaround since ball_tracking.py doesn't expose a function interface.
    """
    from collections import deque
    from typing import List, Union
    import numpy as np
    import cv2
    from tqdm import tqdm
    import supervision as sv
    from inference import get_model
    from veovision.view import ViewTransformer
    from veovision.configs_soccer import SoccerPitchConfiguration
    from veovision.annotators_soccer import (
        draw_pitch,
        draw_points_on_pitch,
        draw_paths_on_pitch,
    )
    
    # Configuration
    BALL_ID = 0
    MAXLEN = 5
    MAX_DISTANCE_THRESHOLD = 280
    PLAYER_DETECTION_MODEL_ID = "veovision-tnp3c/1"
    PITCH_DETECTION_MODEL_ID = "football-field-detection-f07vi/15"
    
    def replace_outliers_based_on_distance(
        positions: List[np.ndarray],
        distance_threshold: float
    ) -> List[np.ndarray]:
        last_valid_position: Union[np.ndarray, None] = None
        cleaned_positions: List[np.ndarray] = []

        for position in positions:
            if len(position) == 0:
                cleaned_positions.append(position)
            else:
                if last_valid_position is None:
                    cleaned_positions.append(position)
                    last_valid_position = position
                else:
                    distance = np.linalg.norm(position - last_valid_position)
                    if distance > distance_threshold:
                        cleaned_positions.append(np.array([], dtype=np.float64))
                    else:
                        cleaned_positions.append(position)
                        last_valid_position = position

        return cleaned_positions

    def select_ball_anchor(
        anchors: np.ndarray,
        confidences: np.ndarray,
        previous_anchor: Union[np.ndarray, None],
    ) -> np.ndarray:
        if len(anchors) == 0:
            return np.array([], dtype=np.float64)
        if len(anchors) == 1:
            return anchors[0]
        if previous_anchor is None or len(previous_anchor) == 0:
            return anchors[int(np.argmax(confidences))]
        distances = np.linalg.norm(anchors - previous_anchor, axis=1)
        score = distances - (confidences * 35.0)
        return anchors[int(np.argmin(score))]
    
    # Load models
    print("  Loading detection models for ball tracking...")
    PLAYER_DETECTION_MODEL = get_model(
        model_id=PLAYER_DETECTION_MODEL_ID,
        api_key=roboflow_api_key
    )
    
    PITCH_DETECTION_MODEL = get_model(
        model_id=PITCH_DETECTION_MODEL_ID,
        api_key=roboflow_api_key
    )
    
    CONFIG = SoccerPitchConfiguration()
    
    # PASS 1: Collect ball path
    print(f"  Pass 1: Collecting ball trajectory...")
    video_info = sv.VideoInfo.from_video_path(source_path)
    frame_generator = sv.get_video_frames_generator(source_path)
    
    path_raw = []
    M = deque(maxlen=MAXLEN)
    last_ball_pitch_xy: Union[np.ndarray, None] = None
    
    for frame in tqdm(frame_generator, total=video_info.total_frames, desc="    Tracking ball"):
        result = PLAYER_DETECTION_MODEL.infer(frame, confidence=0.3)[0]
        detections = sv.Detections.from_inference(result)
    
        ball_detections = detections[detections.class_id == BALL_ID]
        ball_detections.xyxy = sv.pad_boxes(xyxy=ball_detections.xyxy, px=10)
    
        result = PITCH_DETECTION_MODEL.infer(frame, confidence=0.3)[0]
        key_points = sv.KeyPoints.from_inference(result)
    
        filter = key_points.confidence[0] > 0.5
        if np.count_nonzero(filter) < 4:
            path_raw.append(np.empty((0, 2), dtype=np.float32))
            continue
        frame_reference_points = key_points.xy[0][filter]
        pitch_reference_points = np.array(CONFIG.vertices)[filter]
    
        transformer = ViewTransformer(
            source=frame_reference_points,
            target=pitch_reference_points
        )
        M.append(transformer.m)
        transformer.m = np.mean(np.array(M), axis=0)
    
        frame_ball_xy = ball_detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
        if len(frame_ball_xy) == 0:
            path_raw.append(np.empty((0, 2), dtype=np.float32))
            continue

        ball_confidences = ball_detections.confidence if ball_detections.confidence is not None else np.ones(len(frame_ball_xy), dtype=np.float32)
        selected_frame_ball_xy = select_ball_anchor(
            anchors=frame_ball_xy,
            confidences=ball_confidences,
            previous_anchor=last_ball_pitch_xy,
        )
        selected_pitch_ball_xy = transformer.transform_points(points=np.array([selected_frame_ball_xy], dtype=np.float32))
        if len(selected_pitch_ball_xy) > 0:
            last_ball_pitch_xy = selected_pitch_ball_xy[0]
        path_raw.append(selected_pitch_ball_xy)
    
    # Clean path data
    print("  Cleaning ball trajectory...")
    path = [
        np.empty((0, 2), dtype=np.float32) if coordinates.shape[0] >= 2 else coordinates
        for coordinates in path_raw
    ]
    path = [coordinates.flatten() for coordinates in path]
    
    path = replace_outliers_based_on_distance(path, MAX_DISTANCE_THRESHOLD)

    smoothed_path: List[np.ndarray] = []
    smooth_window: deque[np.ndarray] = deque(maxlen=3)
    for point in path:
        if len(point) == 0:
            smoothed_path.append(point)
            continue
        smooth_window.append(point)
        smoothed_path.append(np.mean(np.array(smooth_window), axis=0))
    path = smoothed_path
    
    valid_positions = len([p for p in path if len(p) > 0])
    print(f"  Collected {valid_positions} valid ball positions out of {len(path)} frames")
    
    if valid_positions == 0:
        print("  WARNING: No ball detected in video!")
        return False
    
    # PASS 2: Generate video
    print("  Pass 2: Generating output video...")
    video_sink = sv.VideoSink(target_path, video_info=video_info)
    frame_generator = sv.get_video_frames_generator(source_path)
    
    accumulated_path = []
    
    with video_sink:
        for idx, frame in enumerate(tqdm(frame_generator, total=video_info.total_frames, desc="    Rendering")):
            if idx < len(path):
                accumulated_path.append(path[idx])
            
            pitch = draw_pitch(config=CONFIG)
            
            if pitch is None or pitch.size == 0:
                continue
            
            valid_accumulated = [p for p in accumulated_path if len(p) > 0]
            if valid_accumulated:
                pitch = draw_paths_on_pitch(
                    config=CONFIG,
                    paths=[valid_accumulated],
                    color=sv.Color.WHITE,
                    pitch=pitch
                )
            
            if idx < len(path_raw) and len(path_raw[idx]) > 0:
                pitch = draw_points_on_pitch(
                    config=CONFIG,
                    xy=path_raw[idx],
                    face_color=sv.Color.from_hex('#FFD700'),
                    edge_color=sv.Color.BLACK,
                    radius=12,
                    pitch=pitch
                )
            
            if pitch is not None and pitch.shape[0] > 0 and pitch.shape[1] > 0:
                pitch_resized = cv2.resize(pitch, (video_info.width, video_info.height))
                video_sink.write_frame(pitch_resized)
    
    print(f"  Ball tracking complete!")
    return True


def batch_process_videos(input_folder="famous_clips", output_folder="famous_clips/output"):
    """
    Main batch processing function that processes all videos in the specified folder.
    
    Args:
        input_folder: Folder containing input videos (relative to VeoVision root)
        output_folder: Folder where outputs will be saved (relative to VeoVision root)
    """
    # Setup paths
    script_dir = Path(__file__).parent.parent  # VeoVision root
    sample_content_dir = script_dir / input_folder
    data_content_dir = script_dir / output_folder
    
    # Create output directory if it doesn't exist
    data_content_dir.mkdir(parents=True, exist_ok=True)
    
    # Get API key
    ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "urspUQutaAeYNtL3l5Nq")
    
    # Find all MP4 files in sample_content
    video_files = list(sample_content_dir.glob("*.mp4"))
    
    if not video_files:
        print(f"No video files found in {sample_content_dir}")
        return
    
    print("="*80)
    print("VeoVision Batch Processing")
    print("="*80)
    print(f"Found {len(video_files)} video(s) to process")
    print(f"Input folder: {sample_content_dir}")
    print(f"Output folder: {data_content_dir}")
    print("="*80)
    
    # Process each video
    total_start_time = datetime.now()
    
    for idx, video_path in enumerate(video_files, 1):
        video_name = video_path.stem  # filename without extension
        print(f"\n{'='*80}")
        print(f"Processing Video {idx}/{len(video_files)}: {video_path.name}")
        print(f"{'='*80}")
        
        video_start_time = datetime.now()
        
        # Define output paths for all 4 scripts
        outputs = {
            "combined": data_content_dir / f"{video_name}_combined_result.mp4",
            "2d_pitch": data_content_dir / f"{video_name}_2d_pitch.mp4",
            "heatmap": data_content_dir / f"{video_name}_combined_pitch_heatmap.mp4",
            "ball_tracking": data_content_dir / f"{video_name}_ball_tracking.mp4"
        }
        
        # Track success/failure
        results = {}
        
        # 1. Video Processing Combined (Full player detection with team classification)
        print(f"\n[1/4] Running: Video Processing Combined")
        print("-" * 80)
        try:
            process_video(
                source_video_path=str(video_path),
                target_video_path=str(outputs["combined"]),
                roboflow_api_key=ROBOFLOW_API_KEY
            )
            results["combined"] = "✓ Success"
        except Exception as e:
            print(f"ERROR: {e}")
            results["combined"] = f"✗ Failed: {e}"
        
        # 2. 2D Pitch Visualization
        print(f"\n[2/4] Running: 2D Pitch Visualization")
        print("-" * 80)
        try:
            process_video_2d_pitch(
                source_video_path=str(video_path),
                target_video_path=str(outputs["2d_pitch"]),
                roboflow_api_key=ROBOFLOW_API_KEY
            )
            results["2d_pitch"] = "✓ Success"
        except Exception as e:
            print(f"ERROR: {e}")
            results["2d_pitch"] = f"✗ Failed: {e}"
        
        # 3. Combined Pitch Heatmap
        print(f"\n[3/4] Running: Combined Pitch Heatmap")
        print("-" * 80)
        try:
            process_video_combined(
                source_video_path=str(video_path),
                target_video_path=str(outputs["heatmap"]),
                roboflow_api_key=ROBOFLOW_API_KEY
            )
            results["heatmap"] = "✓ Success"
        except Exception as e:
            print(f"ERROR: {e}")
            results["heatmap"] = f"✗ Failed: {e}"
        
        # 4. Ball Tracking
        print(f"\n[4/4] Running: Ball Tracking")
        print("-" * 80)
        try:
            success = process_ball_tracking(
                source_path=str(video_path),
                target_path=str(outputs["ball_tracking"]),
                roboflow_api_key=ROBOFLOW_API_KEY
            )
            results["ball_tracking"] = "✓ Success" if success else "✗ Failed: No ball detected"
        except Exception as e:
            print(f"ERROR: {e}")
            results["ball_tracking"] = f"✗ Failed: {e}"
        
        # Summary for this video
        video_end_time = datetime.now()
        video_duration = video_end_time - video_start_time
        
        print(f"\n{'='*80}")
        print(f"Video {idx}/{len(video_files)} Processing Complete: {video_path.name}")
        print(f"Time taken: {video_duration}")
        print("-" * 80)
        print("Results:")
        for script_name, result in results.items():
            print(f"  {script_name:20s}: {result}")
        print(f"{'='*80}")
    
    # Final summary
    total_end_time = datetime.now()
    total_duration = total_end_time - total_start_time
    
    print(f"\n{'='*80}")
    print("BATCH PROCESSING COMPLETE")
    print(f"{'='*80}")
    print(f"Total videos processed: {len(video_files)}")
    print(f"Total time taken: {total_duration}")
    print(f"Output location: {data_content_dir}")
    print(f"{'='*80}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Batch process soccer videos with VeoVision AI analysis"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="famous_clips",
        help="Input folder containing videos (default: famous_clips)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="famous_clips/output",
        help="Output folder for processed videos (default: famous_clips/output)"
    )

    ##CHANGE THE DEFAULT INPUT AND OUTPUT FOLDERS TO THE REGULAR_CLIPS 
    
    args = parser.parse_args()
    batch_process_videos(input_folder=args.input, output_folder=args.output)

