@echo off
setlocal EnableDelayedExpansion
REM Скрипт для запуска видео-аудио суммаризатора.
REM Можно положить в любую папку (даже вне директории проекта) и вызывать из любого места.
REM Использование: avsum путь_к_видео_файлу [опции]
REM
REM Порядок поиска папки проекта:
REM   1) идём вверх от папки скрипта, пока не найдём main.py (если скрипт лежит внутри проекта/подпапки);
REM   2) файл ".avsum-project" рядом со скриптом содержит путь к папке проекта;
REM   3) переменная окружения AVSUM_PROJECT_DIR.

REM Директория, из которой был вызван скрипт (используется для относительных путей к файлам)
set "CALLER_DIR=%CD%"

REM ---- Ищем директорию проекта: от папки, где лежит скрипт, идём вверх, пока не найдём main.py ----
set "CUR=%~dp0"
set "ROOT=%~d0\"
set /a DEPTH=0

:find_project
if exist "%CUR%main.py" goto project_found

for %%A in ("%CUR%..\") do set "CUR=%%~fA"
if not "%CUR:~-1%"=="\" set "CUR=%CUR%\"
if /i "%CUR%"=="%ROOT%" goto project_not_found
set /a DEPTH+=1
if %DEPTH% GEQ 12 goto project_not_found
goto find_project

:project_not_found
REM main.py не найден выше по дереву. Пробуем вспомогательные источники.
set "CUR="

REM ---- 2) Файл ".avsum-project" рядом со скриптом ----
if exist "%~dp0.avsum-project" (
    set /p CFGVAL=<"%~dp0.avsum-project"
    if defined CFGVAL (
        if not "!CFGVAL:~-1!"=="\" set "CFGVAL=!CFGVAL!\"
        if exist "!CFGVAL!main.py" set "CUR=!CFGVAL!"
    )
)

REM ---- 3) Переменная окружения AVSUM_PROJECT_DIR ----
if not defined CUR (
    if defined AVSUM_PROJECT_DIR (
        set "EV=!AVSUM_PROJECT_DIR!"
        if not "!EV:~-1!"=="\" set "EV=!EV!\"
        if exist "!EV!main.py" set "CUR=!EV!"
    )
)

if not defined CUR goto project_missing
goto project_found

:project_found
set "PROJECT_DIR=%CUR%"
cd /d "%PROJECT_DIR%"

REM ---- Проверяем виртуальное окружение ----
set "PY=%PROJECT_DIR%venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Ошибка: Виртуальное окружение не найдено: %PY%
    echo Создайте его: python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

REM ---- Нет аргументов - показываем справку ----
if "%~1"=="" (
    "%PY%" main.py --help
    exit /b 0
)

REM ---- Первый аргумент - опция (--...) : передаём все аргументы как есть ----
set "FIRST_ARG=%~1"
if "%FIRST_ARG:~0,2%"=="--" (
    "%PY%" main.py %*
    exit /b !errorlevel!
)

REM ---- Первый аргумент - путь к файлу (относительный -> абсолютный от CALLER_DIR) ----
set "FILE_ARG=%~1"
REM Абсолютный путь: второй символ ":" (диск, C:) или первый "\" (корень/UNC)
set "CH1=%FILE_ARG:~0,1%"
set "CH2=%FILE_ARG:~1,1%"
if "%CH2%"==":" (
    set "ABS_PATH=%FILE_ARG%"
) else if "%CH1%"=="\" (
    set "ABS_PATH=%FILE_ARG%"
) else (
    set "ABS_PATH=%CALLER_DIR%\%FILE_ARG%"
)

REM ---- Проверяем существование файла ----
if not exist "%ABS_PATH%" (
    echo Ошибка: Файл не найден: %ABS_PATH%
    "%PY%" main.py --help
    exit /b 1
)

REM ---- Запускаем обработку с абсолютным путём ----
"%PY%" main.py "%ABS_PATH%" %2 %3 %4 %5 %6 %7 %8 %9
exit /b !errorlevel!

:project_missing
echo Ошибка: не удалось найти main.py.
echo Папка скрипта: %~dp0
echo
echo Как исправить:
echo   - положите рядом со скриптом файл ".avsum-project" с путём к папке проекта, например:
echo         D:\Dev\video-audio-summarizer
echo   - либо задайте переменную окружения AVSUM_PROJECT_DIR
exit /b 1