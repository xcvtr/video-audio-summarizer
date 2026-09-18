#!/usr/bin/env python3
"""VOSK Speech Recognition Server.

Сервер для транскрипции речи с использованием модели VOSK.
Модель загружается один раз при старте сервера.
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import timedelta

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from vosk import Model, KaldiRecognizer, SetLogLevel

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Отключаем логи VOSK
SetLogLevel(-1)


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


class TranscriptionRequest(BaseModel):
    """Запрос на транскрипцию."""
    audio_path: Optional[str] = None
    sample_rate: int = 16000
    language: str = "ru"


class TranscriptionResponse(BaseModel):
    """Ответ с транскрипцией."""
    segments: List[Dict[str, Any]]
    total_duration: float
    language: str
    model_name: str


class HealthResponse(BaseModel):
    """Ответ о состоянии сервера."""
    status: str
    model_loaded: bool
    model_name: Optional[str]
    uptime: float


class VOSKServer:
    """Сервер для транскрипции речи с использованием VOSK."""
    
    def __init__(self, model_path: str, host: str = "127.0.0.1", port: int = 8000):
        """
        Инициализация сервера.
        
        Args:
            model_path: Путь к модели VOSK
            host: Хост для запуска сервера
            port: Порт для запуска сервера
        """
        self.model_path = Path(model_path)
        self.host = host
        self.port = port
        self.start_time = time.time()
        
        # Загрузка модели
        self.model = None
        self.model_name = None
        self._load_model()
        
        # Создание FastAPI приложения
        self.app = FastAPI(
            title="VOSK Speech Recognition Server",
            description="Сервер для транскрипции речи с использованием модели VOSK",
            version="1.0.0"
        )
        
        # Регистрация эндпоинтов
        self._setup_routes()
    
    def _load_model(self) -> None:
        """Загрузка модели VOSK."""
        try:
            logger.info(f"Загрузка модели VOSK из {self.model_path}...")
            
            # Проверка существования директории
            if not self.model_path.exists():
                raise FileNotFoundError(f"Директория модели не найдена: {self.model_path}")
            
            # Проверка, что директория не пустая
            if not any(self.model_path.iterdir()):
                raise ValueError(f"Директория модели пуста: {self.model_path}")
            
            # Загрузка модели
            self.model = Model(str(self.model_path))
            self.model_name = self.model_path.name
            logger.info(f"Модель VOSK загружена: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки модели: {e}")
            raise
    
    def _setup_routes(self) -> None:
        """Настройка маршрутов API."""
        
        @self.app.get("/", include_in_schema=False)
        async def root():
            return {"message": "VOSK Speech Recognition Server"}
        
        @self.app.get("/health", response_model=HealthResponse)
        async def health():
            """Проверка состояния сервера."""
            return HealthResponse(
                status="healthy" if self.model else "unhealthy",
                model_loaded=self.model is not None,
                model_name=self.model_name,
                uptime=time.time() - self.start_time
            )
        
        @self.app.get("/model-info")
        async def model_info():
            """Информация о загруженной модели."""
            if not self.model:
                raise HTTPException(status_code=503, detail="Модель не загружена")
            
            return {
                "model_name": self.model_name,
                "model_path": str(self.model_path),
                "loaded": True,
                "vocab_size": self.model.vocab_size() if hasattr(self.model, 'vocab_size') else "unknown"
            }
        
        @self.app.post("/transcribe", response_model=TranscriptionResponse)
        async def transcribe(
            audio_file: UploadFile = File(...),
            sample_rate: int = 16000,
            language: str = "ru"
        ):
            """
            Транскрипция аудиофайла.
            
            Поддерживаемые форматы: WAV (16kHz, mono, PCM)
            """
            if not self.model:
                raise HTTPException(status_code=503, detail="Модель не загружена")
            
            # Проверка формата файла
            if not audio_file.filename.lower().endswith('.wav'):
                raise HTTPException(
                    status_code=400, 
                    detail="Поддерживается только формат WAV. Используйте ffmpeg для конвертации."
                )
            
            try:
                logger.info(f"Транскрипция файла: {audio_file.filename}")
                
                # Чтение аудиофайла
                audio_data = await audio_file.read()
                
                # Транскрипция
                segments = self._transcribe_audio(audio_data, sample_rate)
                
                # Расчет общей длительности
                total_duration = segments[-1].end_time if segments else 0
                
                return TranscriptionResponse(
                    segments=[asdict(segment) for segment in segments],
                    total_duration=total_duration,
                    language=language,
                    model_name=self.model_name
                )
                
            except Exception as e:
                logger.error(f"Ошибка транскрипции: {e}")
                raise HTTPException(status_code=500, detail=f"Ошибка транскрипции: {str(e)}")
        
        @self.app.post("/transcribe-file", response_model=TranscriptionResponse)
        async def transcribe_file(request: TranscriptionRequest):
            """
            Транскрипция аудиофайла по пути.
            
            Используется для локальных файлов на сервере.
            """
            if not self.model:
                raise HTTPException(status_code=503, detail="Модель не загружена")
            
            if not request.audio_path:
                raise HTTPException(status_code=400, detail="Не указан путь к аудиофайлу")
            
            audio_path = Path(request.audio_path)
            if not audio_path.exists():
                raise HTTPException(status_code=404, detail=f"Файл не найден: {request.audio_path}")
            
            try:
                logger.info(f"Транскрипция файла по пути: {audio_path}")
                
                # Чтение аудиофайла
                with open(audio_path, 'rb') as f:
                    audio_data = f.read()
                
                # Транскрипция
                segments = self._transcribe_audio(audio_data, request.sample_rate)
                
                # Расчет общей длительности
                total_duration = segments[-1].end_time if segments else 0
                
                return TranscriptionResponse(
                    segments=[asdict(segment) for segment in segments],
                    total_duration=total_duration,
                    language=request.language,
                    model_name=self.model_name
                )
                
            except Exception as e:
                logger.error(f"Ошибка транскрипции: {e}")
                raise HTTPException(status_code=500, detail=f"Ошибка транскрипции: {str(e)}")
    
    def _transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> List[TranscriptSegment]:
        """
        Транскрипция аудиоданных.
        
        Args:
            audio_data: Байты аудиофайла в формате WAV
            sample_rate: Частота дискретизации
            
        Returns:
            Список сегментов транскрипции
        """
        recognizer = KaldiRecognizer(self.model, sample_rate)
        recognizer.SetWords(True)
        
        segments = []
        
        # Обработка аудиоданных
        chunk_size = 4000
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            if recognizer.AcceptWaveform(chunk):
                result = recognizer.Result()
                if result:
                    self._process_result(result, segments)
        
        # Финальный результат
        final_result = recognizer.FinalResult()
        if final_result:
            self._process_result(final_result, segments)
        
        return segments
    
    def _process_result(self, result: str, segments: List[TranscriptSegment]) -> None:
        """
        Обработка результата распознавания.
        
        Args:
            result: JSON строка с результатом распознавания
            segments: Список для добавления сегментов
        """
        import json
        try:
            data = json.loads(result)
            if 'result' in data:
                for word in data['result']:
                    segment = TranscriptSegment(
                        start_time=word['start'],
                        end_time=word['end'],
                        text=word['word'],
                        confidence=word.get('conf', 0.0)
                    )
                    segments.append(segment)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Ошибка обработки результата: {e}")
    
    def run(self) -> None:
        """Запуск сервера."""
        logger.info(f"Запуск сервера VOSK на {self.host}:{self.port}")
        logger.info(f"Модель: {self.model_name}")
        
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )


def main():
    """Точка входа для запуска сервера."""
    import argparse
    
    parser = argparse.ArgumentParser(description="VOSK Speech Recognition Server")
    parser.add_argument(
        "--model-path",
        default="./vosk/model-ru-large",
        help="Путь к модели VOSK (по умолчанию: ./vosk/model-ru-large)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Хост для запуска сервера (по умолчанию: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Порт для запуска сервера (по умолчанию: 8000)"
    )
    
    args = parser.parse_args()
    
    try:
        server = VOSKServer(
            model_path=args.model_path,
            host=args.host,
            port=args.port
        )
        server.run()
    except Exception as e:
        logger.error(f"Ошибка запуска сервера: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()