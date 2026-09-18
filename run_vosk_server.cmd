@echo off
REM Скрипт для запуска сервера VOSK
REM Использование: run_vosk_server.cmd [--model-path путь] [--host хост] [--port порт]

REM Переходим в директорию проекта
cd /d "%~dp0"

REM Используем Python из виртуального окружения venv
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Ошибка: Виртуальное окружение не найдено: %PY%
    echo Создайте его: python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

REM Запускаем сервер
"%PY%" -m src.vosk_server %*