# About The Project

![VeoVision LOGO.png](VeoVision%20LOGO.png)

# VeoVision - Soccer Video Analysis

Automated soccer video analysis tools using AI to detect players, track the ball, classify teams, and create tactical visualizations.

## Quick Start

### 🚀 Batch Process Multiple Videos (Recommended)

Process all videos in a folder with a single command! This will run all 4 analysis scripts on every video automatically.

**Default (Famous Clips):**
```bash
python veo_project/batch_process_all.py
```
This processes all videos in `famous_clips/` and saves outputs to `famous_clips/data_content/`

**Custom Folders:**
```bash
# Specify input and output folders
python veo_project/batch_process_all.py --input "regular_clips/sample_content" --output "regular_clips/data_content"

# Or any other folder
python veo_project/batch_process_all.py --input "my_videos" --output "my_results"
```

**What You Get:**

For each video (e.g., `match.mp4`), you'll get 4 outputs (plus browser-safe copies):
- ✅ `match_combined_result.mp4`             - Full player detection with tracking IDs
- ✅ `match_2d_pitch.mp4`                    - Top-down tactical view with possession
- ✅ `match_combined_pitch_heatmap.mp4`      - Heatmap with territorial control
- ✅ `match_ball_tracking.mp4`               - Ball trajectory visualization
- ✅ `*_browser.mp4` versions (H.264/AAC)    - For the web UI player

**Features:**
- 🎯 Processes all `.mp4` files in the folder automatically
- 📊 Shows progress and timing for each video
- ✓ Reports success/failure for each script
- 📁 Automatically creates output folder if needed

See `veo_project/README.md` for more details.

---

### 🖥️ Frontend Viewer (Plays processed videos)
- Start server (range-support, port 5600):  
  ```bash
  python start_video_server.py
  ```
- Open in browser: `http://localhost:5600/veo_frontend/`
- The frontend automatically prefers the `_browser.mp4` files. If you only see black players, run the converter below.

### 🎥 Make videos browser-compatible
If videos don't play in the browser, convert them (keeps originals, adds `_browser.mp4`):
```bash
python convert_videos_for_browser.py
```
You need ffmpeg installed (see `FFMPEG_INSTALL_GUIDE.md`).

---

### 📋 Manual Processing (Individual Videos)

#### 1. Installation

Install all required packages:

```bash
pip install -r requirements.txt
```

#### 2. Set Your API Key

Set your Roboflow API key as an environment variable:

**Windows PowerShell:**
```powershell
$env:ROBOFLOW_API_KEY="your_api_key_here"
```

**Linux/Mac:**
```bash
export ROBOFLOW_API_KEY="your_api_key_here"
```

Or edit the script directly and change the API key at the top.

#### 3. Process Your Video

Edit the video paths at the top of any script:

```python
SOURCE_VIDEO_PATH = r"content\your_video.mp4"
TARGET_VIDEO_PATH = r"content\your_video_output.mp4"
```

Then run:

```bash
python veo_project/veo_scripts/script_name.py
```

---

## Available Scripts

## Warning: Models can take upwards of ~20 min per 30 second input video clip depending on your CPU.
## It's also better if you can run this code using your GPU.

### 1. **video_processing_combined.py**
Original video with AI annotations

**What it does:**
- Detects players, ball, goalkeepers, referees
- Classifies players into teams (cyan/pink)
- Adds tracking IDs to all entities
- Overlays pitch lines on the video

**Output:** Original video with colored annotations and pitch lines

![example_video_processing_combined.PNG](example_video_processing_combined.PNG)

**Run:**
```bash
python veo_project/veo_scripts/video_processing_combined.py
```

---

### 2. **pitch_2d_visualization.py**
Bird's-eye tactical view with possession tracking

**What it does:**
- Creates 2D tactical pitch view
- Shows all player positions from above
- Highlights player with ball possession (neon green aura)
- Maps players to pitch coordinates

**Output:** 2D tactical diagram with possession indicator

![example_2d_pitch.PNG](example_2d_pitch.PNG)

**Run:**
```bash
python veo_project/veo_scripts/pitch_2d_visualization.py
```

---

### 3. **combined_pitch_heatmap.py**
Combined heatmap + player positions

**What it does:**
- Semi-transparent heatmap (40% opacity)
- Individual player markers overlaid
- Ball possession highlighting
- Best of both worlds

**Output:** Heatmap with player markers and possession indicator

![example_2d_heatmap.PNG](example_2d_heatmap.PNG)

**Run:**
```bash
python veo_project/veo_scripts/combined_pitch_heatmap.py
```

---

### 4. **ball_tracking.py**
Ball trajectory visualization

**What it does:**
- Tracks ball throughout the video
- Shows accumulated path over time
- Highlights current ball position (golden marker)
- Removes outlier detections

**Output:** 2D pitch with ball's path traced in white

![example_ball_tracking.PNG](example_ball_tracking.PNG)

**Run:**
```bash
python veo_project/veo_scripts/ball_tracking.py
```

---

## Configuration

All scripts follow the same pattern. Edit at the top of each script:

```python
# Configure your video paths
SOURCE_VIDEO_PATH = r"content\your_video.mp4"
TARGET_VIDEO_PATH = r"content\your_output.mp4"

# Optional: Set API key directly
ROBOFLOW_API_KEY = "your_api_key_here"
```

### Advanced Settings

**Ball Tracking:**
```python
MAXLEN = 5  # Smoothing frames (higher = smoother)
MAX_DISTANCE_THRESHOLD = 500  # Outlier detection sensitivity
```

**Heatmap Opacity:**
```python
HEATMAP_OPACITY = 0.4  # 0.0 = invisible, 1.0 = solid
```

**Detection Confidence:**
```python
confidence=0.3  # Lower = more detections, higher = fewer but more accurate
```

---

## Troubleshooting

### "No ball detected"
- Lower confidence threshold: change `confidence=0.3` to `confidence=0.1`
- Check if ball is visible in your video
- Use a higher quality video

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "Video not found"
- Use absolute paths: `r"C:\full\path\to\video.mp4"`
- Or put videos in `content/` folder

### Slow processing
- Use GPU if available (automatically detected)
- Reduce video resolution before processing
- Process shorter clips for testing

### Out of memory
- Process shorter video segments
- Reduce video resolution
- Close other applications

---

## Repository layout

```
VeoVision/
├── veovision/              # Core library (pitch config, homography, teams, drawing)
├── tools/                  # CLI: video server + browser MP4 converter (sources live here)
├── veo_project/
│   ├── batch_process_all.py
│   └── veo_scripts/        # Per-task pipelines (import from veovision)
├── veo_frontend/           # Web viewer
├── requirements.txt        # Python dependencies
├── start_video_server.py   # Launcher (delegates to tools/)
└── convert_videos_for_browser.py
```
Root-level `teams.py`, `view.py`, `configs_soccer.py`, and `annotators_soccer.py` are thin shims so older `from teams import …` imports (e.g. notebooks) still work.

---

## Output Examples

### video_processing_combined.py
Original video with:
- Colored ellipses around players (cyan/pink for teams, yellow for refs)
- Golden triangles marking the ball
- Tracking ID numbers
- Pitch line overlay

### pitch_2d_visualization.py
Top-down tactical view showing:
- Player positions mapped to 2D pitch
- Neon green glow around player with ball
- Team colors clearly visible

### voronoi_heatmap.py
Colored regions showing:
- Which team controls each area of the pitch
- Territorial advantage visualization
- Clean, abstract representation

### combined_pitch_heatmap.py
Best of both worlds:
- Transparent heatmap showing control
- Individual player dots overlaid
- Ball possession indicator
- Comprehensive tactical view

### ball_tracking.py
Ball movement visualization:
- White trail showing ball's path
- Golden dot for current position
- Clean trajectory over time

---

## Video Requirements

**Supported formats:** MP4, AVI, MOV

**Recommended:**
- Resolution: 720p or 1080p
- Frame rate: 25-30 FPS
- Full pitch visible in frame
- Good lighting conditions
- Clear view of players and ball

**Works best with:**
- Wide-angle camera shots
- Stable camera position
- Minimal camera movement
- High contrast between teams

---

## Tips for Best Results

1. **Use high-quality video** - Better input = better output
2. **Test with short clips first** - Process 10-30 seconds to verify settings
3. **Adjust confidence thresholds** - Lower for more detections, higher for accuracy
4. **Check your API key** - Make sure it's set correctly
5. **Use appropriate script** - Each script serves different analysis needs

---

## Processing Time

Approximate processing speeds (on standard GPU):

| Video Length | Resolution | Processing Time |
|--------------|-----------|----------------|
| 30 seconds   | 720p      | 1-2 minutes    |
| 1 minute     | 720p      | 2-4 minutes    |
| 5 minutes    | 720p      | 10-20 minutes  |
| 30 seconds   | 1080p     | 2-4 minutes    |
| 1 minute     | 1080p     | 4-8 minutes    |

*Times vary based on hardware and video complexity*

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify all dependencies are installed
3. Test with provided sample videos first
4. Review script configuration settings

---

## Credits

Built with:
- Supervision - Computer vision tools
- Roboflow - Object detection models
- OpenCV - Video processing
- PyTorch & Transformers - Team classification

---

**Ready to analyze your soccer videos? Start with any script above!**
