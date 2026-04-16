#!/usr/bin/env python3
"""Клиентская реализация SpeechRecognizer для работы с VOSK сервером."""

import os
import logging
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass

from .vosk_client import VOSKClient, VOSKClientError, TranscriptSegment as ClientTranscriptSegment

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """Сегмент транскрипции с временными метками."""
    start_time: float
    end_time: float
    text: str
    confidence: float = 0.0
    
    def get_start_timestamp(self) -> str:
        """Возвращает временную метку в формате HH:MM:SS."""
        seconds = int(self.start_time)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class SpeechRecognitionError(Exception):
    """Ошибка распознавания речи."""
    pass


class SpeechRecognizerClient:
    """Клиент для распознавания речи через VOSK сервер."""
    
    def __init__(self, server_url: str = "http://127.0.0.1:8000", timeout: int = 300):
        """
        Инициализация клиента.
        
        Args:
            server_url: URL сервера VOSK
            timeout: Таймаут запросов в секундах
        """
        self.server_url = server_url
        self.timeout = timeout
        self.client = None
        
        try:
            self.client = VOSKClient(base_url=server_url, timeout=timeout)
            logger.info(f"Клиент инициализирован для сервера: {server_url}")
        except VOSKClientError as e:
            raise SpeechRecognitionError(f"Не удалось инициализировать клиент: {e}")
    
    def transcribe(self, audio_path: str, progress_callback: Optional[Callable] = None) -> List[TranscriptSegment]:
        """
        Транскрипция аудиофайла через сервер.
        
        Args:
            audio_path: Путь к аудиофайлу (WAV формат)
            progress_callback: Опциональный callback для отслеживания прогресса
            
        Returns:
            Список сегментов транскрипции
            
        Raises:
            SpeechRecognitionError: Если произошла ошибка
        """
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise SpeechRecognitionError(f"Аудиофайл не найден: {audio_path}")
        
        # Проверка формата файла
        if not audio_file.suffix.lower() == '.wav':
            logger.warning(f"Файл не в формате WAV: {audio_path}. Рекомендуется конвертировать в WAV.")
        
        try:
            # Вызов callback для начала обработки
            if progress_callback:
                progress_callback(0, 100)
            
            logger.info(f"Начало транскрипции через сервер: {audio_file.name}")
            
            # Транскрипция через клиент
            client_segments = self.client.transcribe_file(str(audio_path))
            
            # Конвертация в локальный формат
            segments = []
            for client_segment in client_segments:
                segment = TranscriptSegment(
                    start_time=client_segment.start_time,
                    end_time=client_segment.end_time,
                    text=client_segment.text,
                    confidence=client_segment.confidence
                )
                segments.append(segment)
            
            # Вызов callback для завершения
            if progress_callback:
                progress_callback(100, 100)
            
            logger.info(f"Транскрипция завершена: {len(segments)} сегментов")
            
            return segments
            
        except VOSKClientError as e:
            raise SpeechRecognitionError(f"Ошибка транскрипции через сервер: {e}")
        except Exception as e:
            raise SpeechRecognitionError(f"Неожиданная ошибка: {e}")
    
    def save_transcript(self, segments: List[TranscriptSegment], output_path: str) -> None:
        """
        Сохранение транскрипта в файл.
        
        Args:
            segments: Список сегментов транскрипции
            output_path: Путь для сохранения файла
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # Заголовок Markdown
            f.write("# Transcript\n\n")
            f.write("## Segments with timestamps\n\n")
            
            for segment in segments:
                timestamp = segment.get_start_timestamp()
                f.write(f"- **[{timestamp}]** {segment.text}\n")
        
        logger.info(f"Транскрипт сохранен: {output_path}")
    
    def load_transcript(self, transcript_path: str) -> List[TranscriptSegment]:
        """
        Загрузка транскрипта из файла.
        
        Args:
            transcript_path: Путь к файлу транскрипта
            
        Returns:
            Список сегментов транскрипции
            
        Raises:
            SpeechRecognitionError: Если произошла ошибка загрузки
        """
        import re
        
        transcript_file = Path(transcript_path)
        if not transcript_file.exists():
            raise SpeechRecognitionError(f"Файл транскрипта не найден: {transcript_path}")
        
        segments = []
        
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Пропуск заголовков Markdown
                    if line.startswith('#') or line.startswith('##'):
                        continue
                    
                    # Парсинг формата Markdown: - **[HH:MM:SS]** text
                    # Также поддержка старого формата: [HH:MM:SS] text
                    match = re.match(r'(?:-\s*\*\*)?\[(\d{2}):(\d{2}):(\d{2})\]\*\*\s*(.+)', line)
                    if not match:
                        # Попытка старого формата без Markdown
                        match = re.match(r'\[(\d{2}):(\d{2}):(\d{2})\]\s*(.+)', line)
                    
                    if match:
                        hours, minutes, seconds, text = match.groups()
                        start_time = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
                        
                        # Оценка времени окончания (начало следующего сегмента или +3 секунды)
                        end_time = start_time + 3.0
                        
                        segment = TranscriptSegment(
                            start_time=start_time,
                            end_time=end_time,
                            text=text,
                            confidence=0.0
                        )
                        segments.append(segment)
            
            logger.info(f"Загружено {len(segments)} сегментов из {transcript_path}")
            return segments
            
        except Exception as e:
            raise SpeechRecognitionError(f"Ошибка загрузки транскрипта: {e}")
    
    def check_server_health(self) -> bool:
        """
        Проверка состояния сервера.
        
        Returns:
            True если сервер доступен и готов, иначе False
        """
        try:
            health = self.client.health()
            return health.get('status') == 'healthy' and health.get('model_loaded')
        except:
            return False
    
    def get_model_info(self) -> dict:
        """
        Получение информации о модели на сервере.
        
        Returns:
            Словарь с информацией о модели
        """
        try:
            return self.client.model_info()
        except VOSKClientError as e:
            raise SpeechRecognitionError(f"Ошибка получения информации о модели: {e}")


# Фабричная функция для создания SpeechRecognizer
def create_speech_recognizer(use_server: bool = True, server_url: str = "http://127.0.0.1:8000", 
                           model_path: Optional[str] = None):
    """
    Создание экземпляра распознавателя речи.
    
    Args:
        use_server: Использовать серверный режим (True) или локальный (False)
        server_url: URL сервера VOSK (только для серверного режима)
        model_path: Путь к модели VOSK (только для локального режима)
        
    Returns:
        Экземпляр SpeechRecognizerClient или оригинального SpeechRecognizer
    """
    if use_server:
        try:
            return SpeechRecognizerClient(server_url=server_url)
        except SpeechRecognitionError as e:
            logger.warning(f"Не удалось создать клиент для сервера: {e}")
            logger.warning("Попытка использовать локальный режим...")
    
    # Локальный режим (оригинальный SpeechRecognizer)
    from .speech_recognizer import SpeechRecognizer
    if not model_path:
        raise ValueError("Для локального режима необходимо указать model_path")
    
    return SpeechRecognizer(model_path=model_path)


def main():
    """Точка входа для тестирования клиента."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Speech Recognizer Client")
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:8000",
        help="URL сервера VOSK (по умолчанию: http://127.0.0.1:8000)"
    )
    parser.add_argument(
        "--audio-file",
        required=True,
        help="Путь к аудиофайлу для транскрипции"
    )
    parser.add_argument(
        "--output",
        default="transcript.md",
        help="Путь для сохранения транскрипта (по умолчанию: transcript.md)"
    )
    parser.add_argument(
        "--check-health",
        action="store_true",
        help="Проверить состояние сервера"
    )
    
    args = parser.parse_args()
    
    try:
        recognizer = SpeechRecognizerClient(server_url=args.server)
        
        if args.check_health:
            if recognizer.check_server_health():
                print("✅ Сервер доступен и готов")
                model_info = recognizer.get_model_info()
                print(f"   Модель: {model_info.get('model_name')}")
            else:
                print("❌ Сервер недоступен или не готов")
        
        else:
            # Транскрипция файла
            segments = recognizer.transcribe(args.audio_file)
            
            # Вывод результатов
            print(f"\n✅ Транскрипция завершена: {len(segments)} сегментов")
            print("\nПервые 5 сегментов:")
            for i, segment in enumerate(segments[:5], 1):
                print(f"  {i}. [{segment.get_start_timestamp()}] {segment.text}")
            
            if len(segments) > 5:
                print(f"  ... и еще {len(segments) - 5} сегментов")
            
            # Сохранение транскрипта
            recognizer.save_transcript(segments, args.output)
            print(f"\n📄 Транскрипт сохранен в: {args.output}")
    
    except SpeechRecognitionError as e:
        print(f"❌ Ошибка: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())