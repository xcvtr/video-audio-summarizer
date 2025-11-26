"""Output management and markdown generation."""

from datetime import datetime
from pathlib import Path
from typing import List
from src.models import TranscriptSegment, KeyMoment


class OutputManager:
    """Manages output directory structure and markdown generation."""
    
    def __init__(self, base_dir: Path):
        """Initialize with base output directory.
        
        Args:
            base_dir: Base directory for all outputs
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def create_video_directory(self, video_name: str, video_dir: Path = None) -> Path:
        """Create organized directory structure for video.
        
        Args:
            video_name: Name of the video file
            video_dir: Directory where video is located (if None, uses base_dir)
            
        Returns:
            Path to created directory
        """
        # Use video directory if provided, otherwise use base_dir
        base_path = video_dir if video_dir else self.base_dir
        
        # Create directory name with "summary" postfix
        dir_name = f"{video_name}_summary"
        
        output_dir = base_path / dir_name
        
        # Handle conflicts by adding suffix
        counter = 1
        while output_dir.exists():
            dir_name = f"{video_name}_summary_{counter}"
            output_dir = base_path / dir_name
            counter += 1
        
        # Create directory structure
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "audio").mkdir(exist_ok=True)
        (output_dir / "screenshots").mkdir(exist_ok=True)
        
        return output_dir
    
    def generate_summary_markdown(
        self,
        video_name: str,
        summary: str,
        transcript: List[TranscriptSegment],
        key_moments: List[KeyMoment],
        screenshots: List[Path],
        output_path: Path
    ) -> None:
        """Generate final markdown document with all information.
        
        Args:
            video_name: Name of the video
            summary: AI-generated summary
            transcript: Full transcript
            key_moments: List of key moments
            screenshots: List of screenshot paths
            output_path: Path for output markdown file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Title
            f.write(f"# {video_name}\n\n")
            
            # Summary section (AI already provides formatted summary with headers)
            f.write(summary)
            f.write("\n\n")
            
            # Key Moments section
            if key_moments:
                f.write("## Ключевые моменты\n\n")
                
                # Sort key moments by timestamp
                sorted_moments = sorted(key_moments, key=lambda m: m.timestamp)
                
                # Track used screenshots to avoid duplicates
                used_screenshots = set()
                
                for moment in sorted_moments:
                    timestamp_str = moment.format_timestamp()
                    f.write(f"### [{timestamp_str}] {moment.description}\n\n")
                    
                    # Find corresponding screenshot
                    screenshot = self._find_screenshot_for_timestamp(
                        moment.timestamp,
                        screenshots
                    )
                    
                    if screenshot and screenshot not in used_screenshots:
                        # Use relative path for screenshot with forward slashes (for Markdown)
                        rel_path = (Path("screenshots") / screenshot.name).as_posix()
                        f.write(f"![Скриншот в {timestamp_str}]({rel_path})\n\n")
                        used_screenshots.add(screenshot)
            
            # Full Transcript section
            f.write("## Полная транскрипция\n\n")
            for segment in transcript:
                timestamp = segment.get_start_timestamp()
                f.write(f"**[{timestamp}]** {segment.text}\n\n")
    
    def _find_screenshot_for_timestamp(
        self,
        timestamp: float,
        screenshots: List[Path]
    ) -> Path:
        """Find screenshot closest to given timestamp.
        
        Args:
            timestamp: Target timestamp in seconds
            screenshots: List of screenshot paths
            
        Returns:
            Path to closest screenshot or None
        """
        if not screenshots:
            return None
        
        # Extract timestamps from filenames
        def extract_timestamp(path: Path) -> float:
            # Filename format: HH_MM_SS.jpg
            name = path.stem
            parts = name.split('_')
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            return 0
        
        # Find closest screenshot
        closest = min(
            screenshots,
            key=lambda p: abs(extract_timestamp(p) - timestamp)
        )
        
        return closest
    
    def _generate_toc(self, summary: str) -> str:
        """Generate table of contents from summary.
        
        Args:
            summary: Summary text
            
        Returns:
            Table of contents markdown
        """
        # Simple TOC generation based on headers
        toc_lines = []
        for line in summary.split('\n'):
            if line.startswith('##'):
                # Extract header text
                header = line.lstrip('#').strip()
                # Create anchor link
                anchor = header.lower().replace(' ', '-')
                toc_lines.append(f"- [{header}](#{anchor})")
        
        if toc_lines:
            return "## Table of Contents\n\n" + "\n".join(toc_lines) + "\n\n"
        return ""
