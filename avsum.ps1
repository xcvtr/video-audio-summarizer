#!/usr/bin/env pwsh
# Скрипт PowerShell для запуска видео-аудио суммаризатора из любой папки
# Использование: .\avsum.ps1 путь_к_видео_файлу

# Переходим в директорию скрипта (где находится main.py)
Set-Location -Path $PSScriptRoot

# Используем Python из виртуального окружения venv
$Python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Ошибка: Виртуальное окружение не найдено: $Python"
    Write-Host "Создайте его: python -m venv venv && venv\Scripts\pip install -r requirements.txt"
    exit 1
}

# Запускаем обработку
& $Python main.py @args