#!/usr/bin/env python3
"""Клиент для VOSK Speech Recognition Server."""

import os
import logging
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import timedelta

import requests
from requests.exceptions import RequestException

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


class VOSKClientError(Exception):
    """Ошибка клиента VOSK."""
    pass


class VOSKClient:
    """Клиент для взаимодействия с VOSK сервером."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: int = 300):
        """
        Инициализация клиента.
        
        Args:
            base_url: Базовый URL сервера VOSK
            timeout: Таймаут запросов в секундах
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
        # Проверка соединения с сервером
        self._check_connection()
    
    def _check_connection(self) -> None:
        """Проверка соединения с сервером."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy" and data.get("model_loaded"):
                    logger.info(f"Соединение с сервером установлено: {self.base_url}")
                    logger.info(f"Модель: {data.get('model_name')}")
                else:
                    raise VOSKClientError(f"Сервер не готов: {data}")
            else:
                raise VOSKClientError(f"Сервер недоступен: HTTP {response.status_code}")
                
        except RequestException as e:
            raise VOSKClientError(f"Не удалось подключиться к серверу {self.base_url}: {e}")
    
    def health(self) -> Dict[str, Any]:
        """
        Проверка состояния сервера.
        
        Returns:
            Словарь с информацией о состоянии сервера
        """
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            raise VOSKClientError(f"Ошибка проверки состояния: {e}")
    
    def model_info(self) -> Dict[str, Any]:
        """
        Получение информации о модели.
        
        Returns:
            Словарь с информацией о модели
        """
        try:
            response = self.session.get(f"{self.base_url}/model-info", timeout=10)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            raise VOSKClientError(f"Ошибка получения информации о модели: {e}")
    
    def transcribe_file(self, audio_path: str, sample_rate: int = 16000) -> List[TranscriptSegment]:
        """
        Транскрипция аудиофайла.
        
        Args:
            audio_path: Путь к аудиофайлу (WAV формат)
            sample_rate: Частота дискретизации
            
        Returns:
            Список сегментов транскрипции
            
        Raises:
            VOSKClientError: Если произошла ошибка
            FileNotFoundError: Если файл не найден
        """
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"Аудиофайл не найден: {audio_path}")
        
        # Проверка формата файла
        if not audio_file.suffix.lower() == '.wav':
            logger.warning(f"Файл не в формате WAV: {audio_path}. Рекомендуется конвертировать в WAV.")
        
        try:
            # Отправка файла на сервер
            with open(audio_file, 'rb') as f:
                files = {'audio_file': (audio_file.name, f, 'audio/wav')}
                data = {'sample_rate': sample_rate, 'language': 'ru'}
                
                logger.info(f"Отправка файла на транскрипцию: {audio_file.name}")
                response = self.session.post(
                    f"{self.base_url}/transcribe",
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Преобразование в TranscriptSegment
                segments = []
                for segment_data in result.get('segments', []):
                    segment = TranscriptSegment(
                        start_time=segment_data.get('start_time', 0),
                        end_time=segment_data.get('end_time', 0),
                        text=segment_data.get('text', ''),
                        confidence=segment_data.get('confidence', 0.0)
                    )
                    segments.append(segment)
                
                logger.info(f"Транскрипция завершена: {len(segments)} сегментов, "
                           f"длительность: {result.get('total_duration', 0):.2f} сек")
                
                return segments
                
        except RequestException as e:
            error_msg = f"Ошибка транскрипции файла {audio_path}: "
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', str(e))
                    error_msg += error_detail
                except:
                    error_msg += str(e)
            else:
                error_msg += str(e)
            
            raise VOSKClientError(error_msg)
    
    def transcribe_audio_data(self, audio_data: bytes, filename: str = "audio.wav", 
                             sample_rate: int = 16000) -> List[TranscriptSegment]:
        """
        Транскрипция аудиоданных из памяти.
        
        Args:
            audio_data: Байты аудиофайла
            filename: Имя файла для отправки
            sample_rate: Частота дискретизации
            
        Returns:
            Список сегментов транскрипции
        """
        try:
            # Создание временного файла
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Транскрипция временного файла
            segments = self.transcribe_file(temp_path, sample_rate)
            
            # Удаление временного файла
            os.unlink(temp_path)
            
            return segments
            
        except Exception as e:
            raise VOSKClientError(f"Ошибка транскрипции аудиоданных: {e}")
    
    def batch_transcribe(self, audio_paths: List[str], sample_rate: int = 16000) -> Dict[str, List[TranscriptSegment]]:
        """
        Пакетная транскрипция нескольких файлов.
        
        Args:
            audio_paths: Список путей к аудиофайлам
            sample_rate: Частота дискретизации
            
        Returns:
            Словарь {путь_к_файлу: список_сегментов}
        """
        results = {}
        
        for i, audio_path in enumerate(audio_paths, 1):
            try:
                logger.info(f"Обработка файла {i}/{len(audio_paths)}: {audio_path}")
                segments = self.transcribe_file(audio_path, sample_rate)
                results[audio_path] = segments
                
            except Exception as e:
                logger.error(f"Ошибка обработки файла {audio_path}: {e}")
                results[audio_path] = []
        
        return results
    
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


def main():
    """Точка входа для тестирования клиента."""
    import argparse
    
    parser = argparse.ArgumentParser(description="VOSK Speech Recognition Client")
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:8000",
        help="URL сервера VOSK (по умолчанию: http://127.0.0.1:8000)"
    )
    parser.add_argument(
        "--audio-file",
        help="Путь к аудиофайлу для транскрипции"
    )
    parser.add_argument(
        "--output",
        help="Путь для сохранения транскрипта (по умолчанию: транскрипт.md)"
    )
    parser.add_argument(
        "--check-health",
        action="store_true",
        help="Проверить состояние сервера"
    )
    
    args = parser.parse_args()
    
    try:
        client = VOSKClient(base_url=args.server)
        
        if args.check_health:
            health = client.health()
            print("Состояние сервера:")
            print(f"  Статус: {health.get('status')}")
            print(f"  Модель загружена: {health.get('model_loaded')}")
            print(f"  Имя модели: {health.get('model_name')}")
            print(f"  Время работы: {health.get('uptime'):.2f} сек")
        
        elif args.audio_file:
            # Транскрипция файла
            segments = client.transcribe_file(args.audio_file)
            
            # Вывод результатов
            print(f"\nТранскрипция завершена: {len(segments)} сегментов")
            print("\nПервые 5 сегментов:")
            for i, segment in enumerate(segments[:5], 1):
                print(f"  {i}. [{segment.get_start_timestamp()}] {segment.text}")
            
            if len(segments) > 5:
                print(f"  ... и еще {len(segments) - 5} сегментов")
            
            # Сохранение транскрипта
            output_path = args.output or "transcript.md"
            client.save_transcript(segments, output_path)
            print(f"\nТранскрипт сохранен в: {output_path}")
        
        else:
            # Проверка состояния по умолчанию
            health = client.health()
            print(f"Сервер доступен: {health.get('status')}")
            model_info = client.model_info()
            print(f"Модель: {model_info.get('model_name')}")
    
    except VOSKClientError as e:
        print(f"Ошибка: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())