@echo off
REM Скрипт для запуска сервера VOSK
REM Использование: run_vosk_server.cmd [--model-path путь] [--host хост] [--port порт]

REM Переходим в директорию проекта
cd /d "%~dp0"

REM Запускаем сервер
python -m src.vosk_server %*