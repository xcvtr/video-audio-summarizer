#!/usr/bin/env pwsh
# Скрипт PowerShell для запуска видео-аудио суммаризатора из любой папки
# Использование: .\avsum.ps1 путь_к_видео_файлу

# Переходим в директорию скрипта (где находится main.py)
Set-Location -Path $PSScriptRoot

# Запускаем обработку
python main.py @args