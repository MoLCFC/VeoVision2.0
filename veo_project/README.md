# VeoVision Batch Processing

This folder contains scripts for batch processing soccer videos with AI analysis.

## Quick Start

To process all videos in `famous_clips/` with all 4 analysis scripts:

```bash
python veo_project/batch_process_all.py
```

**Custom folders:**
```bash
# Specify custom input and output folders
python veo_project/batch_process_all.py --input "regular_clips/sample_content" --output "regular_clips/data_content"

# Another example
python veo_project/batch_process_all.py --input "my_videos" --output "processed_videos"
```

**Command Line Options:**
- `--input` - Folder containing input videos (default: `famous_clips`)
- `--output` - Folder where outputs will be saved (default: `famous_clips/output`)

This will automatically:
- Find all `.mp4` files in the input folder
- Run all 4 analysis scripts on each video
- Save outputs to the output folder with descriptive names
- Show progress and timing information

## What Gets Generated

For each video (e.g., `121364_0.mp4`), the script generates 4 outputs:

1. **`121364_0_combined_result.mp4`**
   - Full player detection with team classification
   - Player tracking IDs
   - Pitch line overlay
   - Referee and goalkeeper detection

2. **`121364_0_2d_pitch.mp4`**
   - Top-down 2D tactical view
   - Player positions mapped to pitch
   - Ball position tracking
   - Team color coding

3. **`121364_0_combined_pitch_heatmap.mp4`**
   - Voronoi diagram heatmap
   - Territorial control visualization
   - Player positions with possession indicators

4. **`121364_0_ball_tracking.mp4`**
   - Ball trajectory tracking
   - Path visualization on 2D pitch
   - Historical ball movement

## Individual Scripts

You can also run individual scripts manually:

```bash
# Video processing with player detection
python veo_project/veo_scripts/video_processing_combined.py

# 2D pitch visualization
python veo_project/veo_scripts/pitch_2d_visualization.py

# Combined pitch heatmap
python veo_project/veo_scripts/combined_pitch_heatmap.py

# Ball tracking
python veo_project/veo_scripts/ball_tracking.py
```

Note: Individual scripts may need path modifications in their source code.

## Folder Structure

**Default:**
```
VeoVision/
├── veovision/                 # Shared Python package (imported by veo_scripts)
├── famous_clips/              # Input videos (default)
│   ├── barca_tiki_taka_1_1.mp4
│   ├── jamie_vardy_having_a_party_1.mp4
│   ├── yamal_goal_vs_madrid_1.mp4
│   └── data_content/          # Output folder (created automatically)
│       ├── *_combined_result.mp4
│       ├── *_2d_pitch.mp4
│       ├── *_combined_pitch_heatmap.mp4
│       ├── *_ball_tracking.mp4
│       └── *_browser.mp4 (web-ready copies)
└── veo_project/
    ├── batch_process_all.py   # Master script (run this!)
    └── veo_scripts/           # Individual processing scripts
```

**Or with custom folders:**
```
VeoVision/
├── regular_clips/
│   ├── sample_content/        # Custom input folder
│   │   ├── 121364_0.mp4
│   │   ├── 0bfacc_0.mp4
│   │   └── ...
│   └── data_content/          # Custom output folder
│       ├── *_combined_result.mp4
│       ├── *_2d_pitch.mp4
│       ├── *_combined_pitch_heatmap.mp4
│       ├── *_ball_tracking.mp4
│       └── *_browser.mp4 (web-ready copies)
```

## Requirements

- All dependencies from `requirements.txt` must be installed
- Roboflow API key (set via environment variable or uses default)
- GPU recommended for faster processing

## API Key

The script uses the Roboflow API key from:
1. Environment variable: `ROBOFLOW_API_KEY`
2. Or falls back to the default key in the code

Set it with:
```bash
# Windows PowerShell
$env:ROBOFLOW_API_KEY = "your_key_here"

# Linux/Mac
export ROBOFLOW_API_KEY="your_key_here"
```

## Processing Time

Processing time depends on:
- Video length
- Hardware (GPU vs CPU)
- Number of videos

Typical processing time per video: 5-15 minutes each

