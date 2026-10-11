"""Speech recognition using faster-whisper (CTranslate2, GPU/CPU).

Бэкенд для транскрипции через faster-whisper. Поддерживает GPU (CUDA) и CPU.
В отличие от VOSK, работает на GPU и влезает в 3GB VRAM (модель small/int8 ~0.5GB).
"""

import logging
import re
from pathlib import Path
from typing import List, Optional, Callable

from src.models import TranscriptSegment

logger = logging.getLogger(__name__)

# Классы ошибок — совместимо с остальными бэкендами
class SpeechRecognitionError(Exception):
    """Speech recognition errors."""
    pass


class WhisperRecognizer:
    """Transcribes audio files using faster-whisper (CTranslate2)."""

    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "int8", language: Optional[str] = None):
        """Initialize faster-whisper model.

        Args:
            model_size: Размер модели: tiny/base/small/medium/large-v3
            device: "auto", "cuda" или "cpu". При "auto" выбирается cuda, если доступна.
            compute_type: "int8", "float16", "float32" и т.п.
            language: Язык распознавания (None = автоопределение), напр. "ru"

        Raises:
            SpeechRecognitionError: Если модель не удалось загрузить
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language

        # Автоопределение устройства: cuda если доступна, иначе cpu
        if device == "auto":
            self.device = self._detect_device()
            logger.info(f"faster-whisper: автоопределение устройства -> {self.device}")

        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                model_size,
                device=self.device,
                compute_type=self.compute_type
            )
        except Exception as e:
            # Если GPU не поднялся (нет драйвера/не хватает VRAM) — пробуем CPU
            if device == "auto" and self.device == "cuda":
                logger.warning(f"Не удалось загрузить модель на CUDA: {e}. Пробую CPU...")
                try:
                    from faster_whisper import WhisperModel
                    self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
                    self.device = "cpu"
                except Exception as e2:
                    raise SpeechRecognitionError(
                        f"Failed to load faster-whisper model ({model_size}): {e2}"
                    )
            else:
                raise SpeechRecognitionError(
                    f"Failed to load faster-whisper model ({model_size}): {e}"
                )

        logger.info(f"faster-whisper model loaded: {model_size} ({self.device}/{self.compute_type})")

    @staticmethod
    def _detect_device() -> str:
        """Определить, доступна ли CUDA."""
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def transcribe(self, audio_path: str, progress_callback: Optional[Callable] = None) -> List[TranscriptSegment]:
        """Transcribe audio file with timestamps.

        Args:
            audio_path: Path to audio file (WAV/MP3/и т.п. — ffmpeg сам разберёт)
            progress_callback: Optional callback(current, total) для прогресса

        Returns:
            List of transcript segments with timestamps
        """
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise SpeechRecognitionError(f"Audio file not found: {audio_path}")

        try:
            segments_iter, info = self._model.transcribe(
                str(audio_file),
                language=self.language,
                beam_size=1,
                word_timestamps=True,
                vad_filter=True,
            )

            total_duration = info.duration or 0.0
            segments: List[TranscriptSegment] = []

            for seg in segments_iter:
                if progress_callback and total_duration > 0:
                    progress_callback(int(seg.end * 1000), int(total_duration * 1000))

                text = (seg.text or "").strip()
                if not text:
                    continue

                # faster-whisper отдаёт confidence только на уровне слов
                confidence = 1.0
                if seg.words:
                    confs = [w.probability for w in seg.words if w.probability is not None]
                    if confs:
                        confidence = sum(confs) / len(confs)

                segments.append(TranscriptSegment(
                    start_time=seg.start,
                    end_time=seg.end,
                    text=text,
                    confidence=confidence
                ))

            if progress_callback:
                progress_callback(int(total_duration * 1000), int(total_duration * 1000))

            logger.info(f"faster-whisper: {len(segments)} сегментов за {total_duration:.1f}s")
            return segments

        except Exception as e:
            raise SpeechRecognitionError(f"Transcription failed: {e}")

    def save_transcript(self, segments: List[TranscriptSegment], output_path: str) -> None:
        """Save transcript to file with timestamps (тот же формат, что у VOSK)."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Transcript\n\n")
            f.write("## Segments with timestamps\n\n")
            for segment in segments:
                timestamp = segment.get_start_timestamp()
                f.write(f"- **[{timestamp}]** {segment.text}\n")

    def load_transcript(self, transcript_path: str) -> List[TranscriptSegment]:
        """Load transcript from file (тот же формат, что у VOSK)."""
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
                    if line.startswith('#') or line.startswith('##'):
                        continue
                    match = re.match(r'(?:-\s*\*\*)?\[(\d{2}):(\d{2}):(\d{2})\]\*\*\s*(.+)', line)
                    if not match:
                        match = re.match(r'\[(\d{2}):(\d{2}):(\d{2})\]\s*(.+)', line)
                    if match:
                        hours, minutes, seconds, text = match.groups()
                        start_time = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
                        segments.append(TranscriptSegment(
                            start_time=float(start_time),
                            end_time=float(start_time + 3.0),
                            text=text,
                            confidence=1.0
                        ))
            return segments
        except Exception as e:
            raise SpeechRecognitionError(f"Failed to load transcript: {e}")
