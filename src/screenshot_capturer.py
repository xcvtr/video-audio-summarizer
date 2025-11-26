"""Screenshot capture from video files."""

import cv2
from pathlib import Path
from typing import List
from src.config import Config


class ScreenshotError(Exception):
    """Screenshot capture errors."""
    pass


class ScreenshotCapturer:
    """Captures screenshots from video at specified timestamps."""
    
    def __init__(self, config: Config):
        """Initialize with screenshot configuration.
        
        Args:
            config: Application configuration
        """
        self.config = config
    
    def capture(
        self,
        video_path: str,
        timestamps: List[float],
        output_dir: Path
    ) -> List[Path]:
        """Capture screenshots at specified timestamps using FFmpeg.
        
        Args:
            video_path: Path to video file
            timestamps: List of timestamps in seconds
            output_dir: Directory for output screenshots
            
        Returns:
            List of paths to captured screenshots
            
        Raises:
            ScreenshotError: If capture fails
        """
        import subprocess
        import shutil
        
        video_file = Path(video_path)
        if not video_file.exists():
            raise ScreenshotError(f"Video file not found: {video_path}")
        
        # Check FFmpeg availability
        if not shutil.which("ffmpeg"):
            raise ScreenshotError("FFmpeg is not installed or not available in PATH")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        screenshots = []
        
        try:
            for timestamp in timestamps:
                # Generate filename
                filename = self._format_filename(timestamp)
                output_path = output_dir / filename
                
                # Format timestamp for FFmpeg (HH:MM:SS)
                hours = int(timestamp // 3600)
                minutes = int((timestamp % 3600) // 60)
                seconds = timestamp % 60
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
                
                # Use FFmpeg to extract frame
                # -ss: seek to timestamp
                # -i: input file
                # -frames:v 1: extract one frame
                # -q:v: quality (2 is high quality)
                cmd = [
                    "ffmpeg",
                    "-ss", time_str,
                    "-i", str(video_file),
                    "-frames:v", "1",
                    "-q:v", "2",
                    "-y",  # Overwrite
                    str(output_path)
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True
                )
                
                # Check if file was created
                if output_path.exists() and output_path.stat().st_size > 0:
                    screenshots.append(output_path)
            
            return screenshots
            
        except Exception as e:
            raise ScreenshotError(f"Failed to capture screenshots: {e}")
    
    def _format_filename(self, timestamp: float) -> str:
        """Format screenshot filename with timestamp.
        
        Args:
            timestamp: Timestamp in seconds
            
        Returns:
            Formatted filename (e.g., "00_05_23.jpg")
        """
        hours = int(timestamp // 3600)
        minutes = int((timestamp % 3600) // 60)
        seconds = int(timestamp % 60)
        
        return f"{hours:02d}_{minutes:02d}_{seconds:02d}.{self.config.screenshot_format}"
