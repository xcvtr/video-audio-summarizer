"""Audio extraction from video files."""

import subprocess
import shutil
from pathlib import Path
from typing import Optional
from src.config import Config


class AudioExtractionError(Exception):
    """Audio extraction errors."""
    pass


class AudioExtractor:
    """Extracts and converts audio from video files."""
    
    def __init__(self, config: Config):
        """Initialize with audio configuration.
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Check FFmpeg availability
        if not self._check_ffmpeg_available():
            raise AudioExtractionError(
                "FFmpeg is not installed or not available in PATH. "
                "Please install FFmpeg to use this application."
            )
    
    def _check_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is installed.
        
        Returns:
            True if FFmpeg is available, False otherwise
        """
        return shutil.which("ffmpeg") is not None
    
    def extract(self, video_path: str, output_path: str) -> Path:
        """Extract audio from video and convert to required format.
        
        Args:
            video_path: Path to input video file
            output_path: Path for output audio file
            
        Returns:
            Path to extracted audio file
            
        Raises:
            AudioExtractionError: If extraction fails
        """
        video_file = Path(video_path)
        if not video_file.exists():
            raise AudioExtractionError(f"Video file not found: {video_path}")
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Extract audio and convert to VOSK format
            self._convert_to_vosk_format(str(video_file), str(output_file))
            
            if not output_file.exists() or output_file.stat().st_size == 0:
                raise AudioExtractionError(
                    f"Video file '{video_path}' does not contain an audio track"
                )
            
            return output_file
            
        except subprocess.CalledProcessError as e:
            # Decode stderr with error handling for non-UTF8 characters
            stderr_str = e.stderr.decode('utf-8', errors='replace') if isinstance(e.stderr, bytes) else str(e.stderr)
            # Check if error is due to missing audio track
            if "does not contain any stream" in stderr_str or \
               "Output file is empty" in stderr_str:
                raise AudioExtractionError(
                    f"Video file '{video_path}' does not contain an audio track"
                )
            raise AudioExtractionError(f"Failed to extract audio: {stderr_str}")
        except Exception as e:
            raise AudioExtractionError(f"Failed to extract audio: {e}")
    
    def _convert_to_vosk_format(self, audio_path: str, output_path: str) -> Path:
        """Convert audio to VOSK-compatible format (16kHz, mono, WAV).
        
        Args:
            audio_path: Path to input audio/video file
            output_path: Path for output audio file
            
        Returns:
            Path to converted audio file
            
        Raises:
            AudioExtractionError: If conversion fails
        """
        try:
            # FFmpeg command to extract audio and convert to VOSK format
            # Use audio codec copy first to extract, then convert
            # -i: input file
            # -vn: no video
            # -acodec: audio codec
            # -ar: audio sample rate
            # -ac: audio channels
            # -y: overwrite output file
            cmd = [
                "ffmpeg",
                "-i", audio_path,
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # PCM 16-bit little-endian
                "-ar", str(self.config.audio_sample_rate),  # Sample rate
                "-ac", str(self.config.audio_channels),  # Channels (mono)
                "-y",  # Overwrite
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            
            return Path(output_path)
            
        except subprocess.CalledProcessError as e:
            # Try alternative approach: extract audio stream first
            try:
                cmd_fallback = [
                    "ffmpeg",
                    "-i", audio_path,
                    "-vn",
                    "-acodec", "libmp3lame",
                    "-ar", str(self.config.audio_sample_rate),
                    "-ac", str(self.config.audio_channels),
                    "-y",
                    output_path
                ]
                result = subprocess.run(
                    cmd_fallback,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    check=True
                )
                return Path(output_path)
            except subprocess.CalledProcessError as e2:
                raise AudioExtractionError(
                    f"FFmpeg conversion failed: {e2.stderr}"
                )
    
    def convert_to_mp3(self, wav_path: str, video_name: str) -> Path:
        """Convert WAV to MP3 and delete WAV file.
        
        Args:
            wav_path: Path to WAV file
            video_name: Original video name (without extension)
            
        Returns:
            Path to MP3 file
            
        Raises:
            AudioExtractionError: If conversion fails
        """
        wav_file = Path(wav_path)
        if not wav_file.exists():
            raise AudioExtractionError(f"WAV file not found: {wav_path}")
        
        # Create MP3 path with video name
        mp3_path = wav_file.parent / f"{video_name}.mp3"
        
        try:
            # Convert WAV to MP3 using FFmpeg
            # -i: input file
            # -codec:a libmp3lame: MP3 codec
            # -b:a: audio bitrate
            # -y: overwrite output file
            cmd = [
                "ffmpeg",
                "-i", str(wav_file),
                "-codec:a", "libmp3lame",
                "-b:a", "192k",
                "-y",
                str(mp3_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            
            # Delete WAV file after successful conversion
            if mp3_path.exists() and mp3_path.stat().st_size > 0:
                wav_file.unlink()
                return mp3_path
            else:
                raise AudioExtractionError("MP3 file was not created or is empty")
            
        except subprocess.CalledProcessError as e:
            stderr_str = e.stderr.decode('utf-8', errors='replace') if isinstance(e.stderr, bytes) else str(e.stderr)
            raise AudioExtractionError(
                f"MP3 conversion failed: {stderr_str}"
            )
