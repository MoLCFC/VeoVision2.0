import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

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

# ========================
# CONFIGURATION
# ========================

SOURCE_VIDEO_PATH = r"old_content\testvid.mp4"
TARGET_VIDEO_PATH = r"old_content\testvid_ball_tracking.mp4"

ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "urspUQutaAeYNtL3l5Nq")
PLAYER_DETECTION_MODEL_ID = "veovision-tnp3c/1"
PITCH_DETECTION_MODEL_ID = "football-field-detection-f07vi/15"

BALL_ID = 0
MAXLEN = 5
MAX_DISTANCE_THRESHOLD = 280

# ========================
# UTILITY FUNCTIONS
# ========================

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


# ========================
# LOAD MODELS
# ========================

print("Loading detection models...")
PLAYER_DETECTION_MODEL = get_model(
    model_id=PLAYER_DETECTION_MODEL_ID,
    api_key=ROBOFLOW_API_KEY
)

PITCH_DETECTION_MODEL = get_model(
    model_id=PITCH_DETECTION_MODEL_ID,
    api_key=ROBOFLOW_API_KEY
)

CONFIG = SoccerPitchConfiguration()

# ========================
# PASS 1: COLLECT BALL PATH
# ========================

print(f"Processing video: {SOURCE_VIDEO_PATH}")
video_info = sv.VideoInfo.from_video_path(SOURCE_VIDEO_PATH)
frame_generator = sv.get_video_frames_generator(SOURCE_VIDEO_PATH)

path_raw = []
M = deque(maxlen=MAXLEN)
last_ball_pitch_xy: Union[np.ndarray, None] = None

print("Pass 1: Collecting ball trajectory...")
for frame in tqdm(frame_generator, total=video_info.total_frames, desc="Tracking ball"):
    result = PLAYER_DETECTION_MODEL.infer(frame, confidence=0.3)[0]
    detections = sv.Detections.from_inference(result)

    ball_detections = detections[detections.class_id == BALL_ID]
    ball_detections.xyxy = sv.pad_boxes(xyxy=ball_detections.xyxy, px=10)

    result = PITCH_DETECTION_MODEL.infer(frame, confidence=0.3)[0]
    key_points = sv.KeyPoints.from_inference(result)

    if (
        key_points.confidence is None
        or len(key_points.confidence) == 0
        or key_points.xy is None
        or len(key_points.xy) == 0
    ):
        path_raw.append(np.empty((0, 2), dtype=np.float32))
        continue

    keypoint_filter = key_points.confidence[0] > 0.5
    if np.count_nonzero(keypoint_filter) < 4:
        path_raw.append(np.empty((0, 2), dtype=np.float32))
        continue

    frame_reference_points = key_points.xy[0][keypoint_filter]
    pitch_reference_points = np.array(CONFIG.vertices)[keypoint_filter]

    try:
        transformer = ViewTransformer(
            source=frame_reference_points,
            target=pitch_reference_points
        )
    except ValueError:
        path_raw.append(np.empty((0, 2), dtype=np.float32))
        continue
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
    pitch_ball_xy = transformer.transform_points(points=np.array([selected_frame_ball_xy], dtype=np.float32))
    if len(pitch_ball_xy) > 0:
        last_ball_pitch_xy = pitch_ball_xy[0]

    path_raw.append(pitch_ball_xy)

# ========================
# CLEAN PATH DATA
# ========================

print("Cleaning ball trajectory...")
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
print(f"Collected {valid_positions} valid ball positions out of {len(path)} frames")

if valid_positions == 0:
    print("\nWARNING: No ball detected in video!")
    print("Try lowering the confidence threshold or check if ball is visible.")
    exit(1)

# ========================
# PASS 2: GENERATE VIDEO
# ========================

print("Pass 2: Generating output video...")
video_sink = sv.VideoSink(TARGET_VIDEO_PATH, video_info=video_info)
frame_generator = sv.get_video_frames_generator(SOURCE_VIDEO_PATH)

accumulated_path = []

with video_sink:
    for idx, frame in enumerate(tqdm(frame_generator, total=video_info.total_frames, desc="Rendering")):
        if idx < len(path):
            accumulated_path.append(path[idx])
        
        pitch = draw_pitch(config=CONFIG)
        
        # Validate pitch was created
        if pitch is None or pitch.size == 0:
            continue
        
        # Only draw paths if we have valid positions
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
        
        # Validate pitch before resizing
        if pitch is not None and pitch.shape[0] > 0 and pitch.shape[1] > 0:
            pitch_resized = cv2.resize(pitch, (video_info.width, video_info.height))
            video_sink.write_frame(pitch_resized)

print(f"Ball tracking video saved to: {TARGET_VIDEO_PATH}")
print("Done!")
