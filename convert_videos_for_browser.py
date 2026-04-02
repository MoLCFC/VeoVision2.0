"""Launch the browser MP4 converter (implementation in `tools/convert_videos_for_browser.py`)."""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).resolve().parent / "tools" / "convert_videos_for_browser.py"
    raise SystemExit(subprocess.call([sys.executable, str(script)]))
