#!/usr/bin/env python3
"""Тестирование сервер-клиент архитектуры."""

import sys
import os
import time
import subprocess
import threading
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_server_client():
    """Тестирование сервер-клиент архитектуры."""
    
    print("=" * 60)
    print("Тестирование сервер-клиент архитектуры VOSK")
    print("=" * 60)
    
    # Проверяем существование модели VOSK
    model_path = Path("./vosk/model-ru")
    if not model_path.exists():
        print(f"❌ Модель VOSK не найдена: {model_path}")
        print("Скачайте модель: https://alphacephei.com/vosk/models")
        return 1
    
    print(f"✅ Модель VOSK найдена: {model_path}")
    
    # Запускаем сервер в отдельном процессе
    print("\n1. Запуск сервера VOSK...")
    server_process = None
    
    try:
        # Запускаем сервер
        server_cmd = [sys.executable, "-m", "src.vosk_server", "--model-path", str(model_path), "--port", "8001"]
        server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        # Даем серверу время на запуск
        print("   Ожидание запуска сервера...")
        time.sleep(5)
        
        # Проверяем, запустился ли сервер
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate()
            print(f"❌ Сервер не запустился:")
            print(f"   STDOUT: {stdout[:200]}")
            print(f"   STDERR: {stderr[:200]}")
            return 1
        
        print("   ✅ Сервер запущен на порту 8001")
        
        # Тестируем клиент
        print("\n2. Тестирование клиента...")
        
        from src.vosk_client import VOSKClient
        
        try:
            client = VOSKClient(base_url="http://127.0.0.1:8001", timeout=10)
            
            # Проверка состояния сервера
            print("   Проверка состояния сервера...")
            health = client.health()
            print(f"   ✅ Состояние: {health.get('status')}")
            print(f"   ✅ Модель загружена: {health.get('model_loaded')}")
            print(f"   ✅ Имя модели: {health.get('model_name')}")
            
            # Информация о модели
            print("\n   Получение информации о модели...")
            model_info = client.model_info()
            print(f"   ✅ Имя модели: {model_info.get('model_name')}")
            print(f"   ✅ Путь к модели: {model_info.get('model_path')}")
            
            print("\n✅ Все тесты пройдены успешно!")
            print("\nСервер работает. Для остановки нажмите Ctrl+C.")
            
            # Ожидаем завершения (в реальном использовании сервер работает постоянно)
            try:
                server_process.wait()
            except KeyboardInterrupt:
                print("\nОстановка сервера...")
                server_process.terminate()
                server_process.wait()
                print("Сервер остановлен.")
            
            return 0
            
        except Exception as e:
            print(f"❌ Ошибка тестирования клиента: {e}")
            if server_process:
                server_process.terminate()
                server_process.wait()
            return 1
            
    except Exception as e:
        print(f"❌ Ошибка запуска сервера: {e}")
        if server_process:
            server_process.terminate()
            server_process.wait()
        return 1


def test_integration():
    """Тестирование интеграции с существующим процессором."""
    
    print("\n" + "=" * 60)
    print("Тестирование интеграции с процессором")
    print("=" * 60)
    
    from src.config import Config
    import os
    
    # Устанавливаем тестовый API ключ
    os.environ['DEEPSEEK_API_KEY'] = 'test_key'
    
    try:
        # Загружаем конфигурацию
        print("\n1. Загрузка конфигурации...")
        config = Config.load('config.yaml')
        
        print(f"   ✅ Конфигурация загружена")
        print(f"   ✅ Режим VOSK: {config.vosk_mode}")
        print(f"   ✅ URL сервера: {config.vosk_server_url}")
        
        # Тестируем создание процессора
        print("\n2. Создание процессора...")
        from src.processor import VideoProcessor
        
        processor = VideoProcessor(config)
        print(f"   ✅ Процессор создан")
        
        # Проверяем тип распознавателя
        recognizer_type = type(processor.speech_recognizer).__name__
        print(f"   ✅ Тип распознавателя: {recognizer_type}")
        
        if config.vosk_mode == "server":
            # Проверяем состояние сервера
            if hasattr(processor.speech_recognizer, 'check_server_health'):
                health = processor.speech_recognizer.check_server_health()
                print(f"   ✅ Состояние сервера: {'доступен' if health else 'недоступен'}")
        
        print("\n✅ Интеграция работает корректно!")
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка интеграции: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Основная функция тестирования."""
    
    print("Тестирование сервер-клиент архитектуры VOSK")
    print("=" * 60)
    
    # Тест 1: Сервер и клиент
    result1 = test_server_client()
    
    if result1 != 0:
        print("\n❌ Тест сервер-клиент не пройден")
        return result1
    
    # Тест 2: Интеграция
    result2 = test_integration()
    
    if result2 != 0:
        print("\n❌ Тест интеграции не пройден")
        return result2
    
    print("\n" + "=" * 60)
    print("✅ Все тесты пройдены успешно!")
    print("=" * 60)
    
    print("\nРекомендации по использованию:")
    print("1. Для запуска сервера: run_vosk_server.cmd")
    print("2. Для использования серверного режима измените config.yaml:")
    print("   vosk:")
    print("     mode: 'server'")
    print("     server:")
    print("       url: 'http://127.0.0.1:8000'")
    print("3. Для обработки видео используйте: avsum.cmd путь_к_видео")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())