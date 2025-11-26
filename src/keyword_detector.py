"""Keyword detection in transcripts."""

from typing import List
from src.models import TranscriptSegment, KeyMoment


class KeywordDetector:
    """Detects key moments based on keywords in transcript."""
    
    def __init__(self, keywords: List[str]):
        """Initialize with list of trigger keywords.
        
        Args:
            keywords: List of keywords to detect
        """
        self.keywords = [self._normalize_text(kw) for kw in keywords]
    
    def detect(self, transcript: List[TranscriptSegment]) -> List[KeyMoment]:
        """Detect key moments based on keywords.
        
        Args:
            transcript: List of transcript segments
            
        Returns:
            List of detected key moments
        """
        key_moments = []
        
        for segment in transcript:
            normalized_text = self._normalize_text(segment.text)
            
            for keyword in self.keywords:
                if keyword in normalized_text:
                    # Use the start time of the segment where keyword was found
                    moment = KeyMoment(
                        timestamp=segment.start_time,
                        description=f"Keyword detected: '{keyword}' in '{segment.text[:50]}...'",
                        importance=0.8,  # Default importance for keyword matches
                        source="keyword"
                    )
                    key_moments.append(moment)
                    break  # Only add one moment per segment
        
        return key_moments
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for keyword matching.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text (lowercase, stripped)
        """
        return text.lower().strip()
