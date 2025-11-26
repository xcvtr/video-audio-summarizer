"""Data models for video summarizer."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class TranscriptSegment:
    """Represents a segment of recognized speech with timestamps."""
    
    start_time: float  # seconds
    end_time: float    # seconds
    text: str
    confidence: float
    
    def format_timestamp(self, seconds: float) -> str:
        """Format seconds to HH:MM:SS.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def get_start_timestamp(self) -> str:
        """Get formatted start timestamp."""
        return self.format_timestamp(self.start_time)
    
    def get_end_timestamp(self) -> str:
        """Get formatted end timestamp."""
        return self.format_timestamp(self.end_time)


@dataclass
class KeyMoment:
    """Represents an important moment in the video."""
    
    timestamp: float      # seconds
    description: str
    importance: float     # 0.0 to 1.0
    source: str          # "keyword" or "context"
    
    def format_timestamp(self) -> str:
        """Format timestamp to HH:MM:SS.
        
        Returns:
            Formatted timestamp string
        """
        hours = int(self.timestamp // 3600)
        minutes = int((self.timestamp % 3600) // 60)
        secs = int(self.timestamp % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass
class ProcessingResult:
    """Result of processing a single video."""
    
    video_path: str
    output_dir: Path
    success: bool
    error: Optional[str] = None
    audio_path: Optional[Path] = None
    transcript_path: Optional[Path] = None
    summary_path: Optional[Path] = None
    screenshots: List[Path] = field(default_factory=list)
