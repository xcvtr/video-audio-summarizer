"""Debug script to test screenshot capture on already processed video."""

import sys
from pathlib import Path
from src.config import Config
from src.screenshot_capturer import ScreenshotCapturer
from src.models import KeyMoment
import re

def extract_key_moments_from_summary(summary_path: Path):
    """Extract key moments from existing summary.md file."""
    key_moments = []
    
    with open(summary_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all timestamps in format [HH:MM:SS]
    pattern = r'\[(\d{2}):(\d{2}):(\d{2})\]'
    matches = re.finditer(pattern, content)
    
    seen_timestamps = set()
    for match in matches:
        hours, minutes, seconds = map(int, match.groups())
        timestamp = hours * 3600 + minutes * 60 + seconds
        
        # Avoid duplicates
        if timestamp not in seen_timestamps:
            seen_timestamps.add(timestamp)
            key_moments.append(KeyMoment(
                timestamp=float(timestamp),
                description=f"Moment at {match.group(0)}",
                importance=0.8,
                source="debug"
            ))
    
    return key_moments

def main():
    # Find the latest output directory
    output_base = Path("output")
    if not output_base.exists():
        print("No output directory found")
        return 1
    
    # Get all subdirectories sorted by modification time
    subdirs = [d for d in output_base.iterdir() if d.is_dir()]
    if not subdirs:
        print("No processed videos found")
        return 1
    
    latest_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
    print(f"Using latest output: {latest_dir}")
    
    # Find summary.md
    summary_path = latest_dir / "summary.md"
    if not summary_path.exists():
        print(f"No summary.md found in {latest_dir}")
        return 1
    
    # Extract key moments
    print("Extracting key moments from summary...")
    key_moments = extract_key_moments_from_summary(summary_path)
    print(f"Found {len(key_moments)} key moments")
    
    # Find original video path
    # Try to reconstruct from directory name
    video_name = latest_dir.name.rsplit('_', 2)[0]  # Remove timestamp suffix
    video_path = f"G:\\Videos\\Health\\{video_name}.mp4"
    
    print(f"Video path: {video_path}")
    if not Path(video_path).exists():
        print(f"Video not found at {video_path}")
        print("Please provide video path as argument:")
        print(f"  python debug_screenshots.py \"path/to/video.mp4\"")
        if len(sys.argv) > 1:
            video_path = sys.argv[1]
        else:
            return 1
    
    # Load config
    print("Loading configuration...")
    config = Config.load()
    
    # Create screenshot capturer
    print("Initializing screenshot capturer...")
    capturer = ScreenshotCapturer(config)
    
    # Create screenshots directory
    screenshots_dir = latest_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    # Capture screenshots
    print(f"Capturing {len(key_moments)} screenshots...")
    timestamps = [m.timestamp for m in key_moments]
    
    try:
        screenshots = capturer.capture(video_path, timestamps, screenshots_dir)
        print(f"✓ Successfully captured {len(screenshots)} screenshots")
        
        # List created files
        print("\nCreated files:")
        for screenshot in screenshots:
            print(f"  - {screenshot.name}")
        
        return 0
    except Exception as e:
        print(f"✗ Error capturing screenshots: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
