"""Speech recognition using VOSK."""

import json
import wave
from pathlib import Path
from typing import List
from vosk import Model, KaldiRecognizer
from src.models import TranscriptSegment


class SpeechRecognitionError(Exception):
    """Speech recognition errors."""
    pass


class SpeechRecognizer:
    """Recognizes speech from audio files using VOSK."""
    
    def __init__(self, model_path: str):
        """Initialize VOSK model.
        
        Args:
            model_path: Path to VOSK model directory
            
        Raises:
            SpeechRecognitionError: If model cannot be loaded
        """
        model_dir = Path(model_path)
        
        if not model_dir.exists():
            raise SpeechRecognitionError(
                f"VOSK model directory not found: {model_path}. "
                "Please download a VOSK model and update the path in config.yaml. "
                "Models can be downloaded from: https://alphacephei.com/vosk/models"
            )
        
        if not model_dir.is_dir():
            raise SpeechRecognitionError(
                f"VOSK model path is not a directory: {model_path}"
            )
        
        # Check if directory is empty
        if not any(model_dir.iterdir()):
            raise SpeechRecognitionError(
                f"VOSK model directory is empty: {model_path}. "
                "Please download a VOSK model and extract it to this directory."
            )
        
        try:
            self.model = Model(model_path)
        except Exception as e:
            raise SpeechRecognitionError(
                f"Failed to load VOSK model from {model_path}: {e}"
            )
    
    def transcribe(self, audio_path: str, progress_callback=None) -> List[TranscriptSegment]:
        """Transcribe audio file with timestamps.
        
        Args:
            audio_path: Path to audio file (WAV format)
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            List of transcript segments with timestamps
            
        Raises:
            SpeechRecognitionError: If transcription fails
        """
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise SpeechRecognitionError(f"Audio file not found: {audio_path}")
        
        try:
            # Open WAV file
            with wave.open(str(audio_file), "rb") as wf:
                # Check audio format
                if wf.getnchannels() != 1:
                    raise SpeechRecognitionError(
                        f"Audio must be mono (1 channel), got {wf.getnchannels()} channels"
                    )
                
                # Create recognizer
                recognizer = KaldiRecognizer(self.model, wf.getframerate())
                recognizer.SetWords(True)  # Enable word-level timestamps
                
                segments = []
                
                # Calculate total frames for progress
                total_frames = wf.getnframes()
                frames_processed = 0
                chunk_size = 4000
                
                # Process audio in chunks
                while True:
                    data = wf.readframes(chunk_size)
                    if len(data) == 0:
                        break
                    
                    frames_processed += chunk_size
                    
                    # Update progress
                    if progress_callback:
                        progress_callback(frames_processed, total_frames)
                    
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        if "result" in result and result["result"]:
                            # Extract segment with timestamps
                            segment = self._parse_result(result)
                            if segment:
                                segments.append(segment)
                
                # Get final result
                final_result = json.loads(recognizer.FinalResult())
                if "result" in final_result and final_result["result"]:
                    segment = self._parse_result(final_result)
                    if segment:
                        segments.append(segment)
                
                # Final progress update
                if progress_callback:
                    progress_callback(total_frames, total_frames)
                
                return segments
                
        except wave.Error as e:
            raise SpeechRecognitionError(f"Invalid WAV file: {e}")
        except Exception as e:
            raise SpeechRecognitionError(f"Transcription failed: {e}")
    
    def _parse_result(self, result: dict) -> TranscriptSegment:
        """Parse VOSK result into TranscriptSegment.
        
        Args:
            result: VOSK recognition result
            
        Returns:
            TranscriptSegment or None if no text
        """
        if "result" not in result or not result["result"]:
            return None
        
        words = result["result"]
        if not words:
            return None
        
        # Get start and end times from first and last words
        start_time = words[0]["start"]
        end_time = words[-1]["end"]
        
        # Combine all words into text
        text = " ".join(word["word"] for word in words)
        
        # Calculate average confidence
        confidences = [word.get("conf", 1.0) for word in words]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 1.0
        
        return TranscriptSegment(
            start_time=start_time,
            end_time=end_time,
            text=text,
            confidence=avg_confidence
        )
    
    def save_transcript(self, segments: List[TranscriptSegment], output_path: str) -> None:
        """Save transcript to file with timestamps.

        Args:
            segments: List of transcript segments
            output_path: Path for output file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            # Write Markdown header
            f.write("# Transcript\n\n")
            f.write("## Segments with timestamps\n\n")
            
            for segment in segments:
                timestamp = segment.get_start_timestamp()
                # Format as markdown list item with timestamp
                f.write(f"- **[{timestamp}]** {segment.text}\n")
    
    def load_transcript(self, transcript_path: str) -> List[TranscriptSegment]:
        """Load transcript from file.
        
        Args:
            transcript_path: Path to transcript file
            
        Returns:
            List of transcript segments
            
        Raises:
            SpeechRecognitionError: If file cannot be loaded
        """
        import re
        
        transcript_file = Path(transcript_path)
        if not transcript_file.exists():
            raise SpeechRecognitionError(f"Transcript file not found: {transcript_path}")
        
        segments = []
        
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Skip markdown headers
                    if line.startswith('#') or line.startswith('##'):
                        continue
                    
                    # Parse markdown format: - **[HH:MM:SS]** text
                    # Also support old format: [HH:MM:SS] text
                    match = re.match(r'(?:-\s*\*\*)?\[(\d{2}):(\d{2}):(\d{2})\]\*\*\s*(.+)', line)
                    if not match:
                        # Try old format without markdown
                        match = re.match(r'\[(\d{2}):(\d{2}):(\d{2})\]\s*(.+)', line)
                    
                    if match:
                        hours, minutes, seconds, text = match.groups()
                        start_time = int(hours) * 3600 + int(minutes) * 60 + int(seconds)

                        # Estimate end time (start of next segment or +3 seconds)
                        end_time = start_time + 3.0
                        
                        segment = TranscriptSegment(
                            start_time=float(start_time),
                            end_time=float(end_time),
                            text=text,
                            confidence=1.0
                        )
                        segments.append(segment)
            
            return segments
            
        except Exception as e:
            raise SpeechRecognitionError(f"Failed to load transcript: {e}")
