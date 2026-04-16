@echo off
REM Скрипт для запуска клиента VOSK
REM Использование: run_vosk_client.cmd [--server URL] [--audio-file путь] [--output путь]

REM Переходим в директорию проекта
cd /d "%~dp0"

REM Запускаем клиент
python -m src.vosk_client %*