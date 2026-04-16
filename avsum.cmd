@echo off
REM Скрипт для запуска видео-аудио суммаризатора из любой папки
REM Использование: avsum путь_к_видео_файлу

REM Определяем путь к директории скрипта (проекта)
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%"

REM Сохраняем текущую директорию (откуда вызван скрипт)
set "CALLER_DIR=%CD%"

REM Переходим в директорию проекта
cd /d "%PROJECT_DIR%"

REM Обрабатываем первый аргумент (путь к файлу)
if "%~1"=="" (
    REM Нет аргументов - показываем справку
    python main.py --help
    exit /b 0
)

REM Проверяем, является ли первый аргумент опцией (начинается с --)
set "FIRST_ARG=%~1"
if "%FIRST_ARG:~0,2%"=="--" (
    REM Это опция (например --help, --verbose) - передаем все аргументы как есть
    python main.py %*
    exit /b !errorlevel!
)

REM Первый аргумент - путь к файлу
set "FILE_ARG=%~1"

REM Проверяем, является ли путь абсолютным
echo "%FILE_ARG%" | findstr /c:":" >nul
if errorlevel 1 (
    REM Относительный путь - преобразуем в абсолютный относительно CALLER_DIR
    set "ABS_PATH=%CALLER_DIR%\%FILE_ARG%"
) else (
    REM Абсолютный путь
    set "ABS_PATH=%FILE_ARG%"
)

REM Проверяем существование файла
if not exist "%ABS_PATH%" (
    echo Ошибка: Файл не найден: %ABS_PATH%
    echo.
    python main.py --help
    exit /b 1
)

REM Передаем абсолютный путь и остальные аргументы
shift
python main.py "%ABS_PATH%" %*
