"""
Convert videos to browser-compatible MP4 format
This script re-encodes videos to H.264 codec which all browsers support
"""

import os
import subprocess
from pathlib import Path
from tqdm import tqdm


def convert_video_to_browser_compatible(input_path, output_path):
    """Convert video to browser-compatible H.264 MP4"""

    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            ffmpeg_exe = 'ffmpeg'
        except Exception:
            print("ERROR: Neither imageio-ffmpeg nor system ffmpeg is available")
            print("Solution: Run 'pip install imageio-ffmpeg'")
            return False

    # Processed clips are usually video-only; forcing AAC on silent inputs often breaks ffmpeg.
    # Web playback needs H.264 + yuv420p; audio is optional for this dashboard.
    cmd = [
        ffmpeg_exe,
        '-y',
        '-i', str(input_path),
        '-map', '0:v:0',
        '-c:v', 'libx264',
        '-profile:v', 'baseline',
        '-pix_fmt', 'yuv420p',
        '-an',
        '-movflags', '+faststart',
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        print(f"ERROR converting {input_path}:")
        print(result.stderr)
        out_p = Path(output_path)
        if out_p.exists():
            try:
                out_p.unlink()
            except OSError:
                pass
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def convert_all_videos():
    """Convert all videos in data_content folders (paths relative to repo root)."""
    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)

    base_dir = Path('.')

    folders = [
        base_dir / 'regular_clips' / 'data_content',
        base_dir / 'famous_clips' / 'data_content',
        base_dir / 'uploaded_clips' / 'data_content',
    ]

    total_converted = 0
    total_failed = 0

    for folder in folders:
        if not folder.exists():
            print(f"Folder not found: {folder}")
            continue

        print(f"\n{'='*60}")
        print(f"Processing folder: {folder}")
        print(f"{'='*60}")

        mp4_files = [f for f in folder.glob('*.mp4') if '_browser' not in f.stem]

        if not mp4_files:
            print(f"No MP4 files found in {folder}")
            continue

        print(f"Found {len(mp4_files)} videos to convert\n")

        for video_file in tqdm(mp4_files, desc="Converting"):
            output_file = folder / f"{video_file.stem}_browser.mp4"

            if output_file.exists():
                print(f"Skipping {video_file.name} (already converted)")
                total_converted += 1
                continue

            if convert_video_to_browser_compatible(video_file, output_file):
                total_converted += 1
            else:
                total_failed += 1
                if output_file.exists():
                    output_file.unlink()

    print(f"\n{'='*60}")
    print(f"CONVERSION COMPLETE")
    print(f"{'='*60}")
    print(f"Successfully converted: {total_converted}")
    print(f"Failed: {total_failed}")
    print(f"{'='*60}")
    print(f"\nOriginal files kept. Browser versions saved with '_browser' suffix.")


if __name__ == "__main__":
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)

    print("""
╔══════════════════════════════════════════════════════╗
║   VeoVision - Browser-Compatible Video Converter     ║
╚══════════════════════════════════════════════════════╝

This script will convert all processed videos to a
browser-compatible format (H.264 video, no audio track).

Original files will be kept.
Converted files will have '_browser' suffix.

""")

    response = input("Continue? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        convert_all_videos()
    else:
        print("Cancelled.")
