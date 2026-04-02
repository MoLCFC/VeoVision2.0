"""Launch the range-aware static server (implementation in `tools/start_video_server.py`)."""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).resolve().parent / "tools" / "start_video_server.py"
    raise SystemExit(subprocess.call([sys.executable, str(script)]))
