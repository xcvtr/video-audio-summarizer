#!/usr/bin/env pwsh
# Скрипт PowerShell для запуска видео-аудио суммаризатора.
# Можно положить в любую папку (даже вне директории проекта) и вызывать из любого места.
# Использование: .\avsum.ps1 путь_к_видео_файлу [опции]
#
# Порядок поиска папки проекта:
#   1) идём вверх от папки скрипта, пока не найдём main.py (если скрипт лежит внутри проекта/подпапки);
#   2) файл ".avsum-project" рядом со скриптом содержит путь к папке проекта;
#   3) переменная окружения AVSUM_PROJECT_DIR.

# Директория, из которой был вызван скрипт (используется для относительных путей к файлам)
$callerDir = (Get-Location).Path

# ---- Ищем директорию проекта ----
$projectDir = $null
$cur = $PSScriptRoot
$root = [System.IO.Path]::GetPathRoot($PSScriptRoot)

# 1) Вверх от папки скрипта
for ($i = 0; $i -le 12; $i++) {
    if (Test-Path (Join-Path $cur "main.py")) {
        $projectDir = $cur
        break
    }
    $parent = Split-Path -Parent $cur
    if (-not $parent -or $parent -eq $cur) { break }
    $cur = $parent
}

# 2) Файл ".avsum-project" рядом со скриптом
if (-not $projectDir) {
    $cfgFile = Join-Path $PSScriptRoot ".avsum-project"
    if (Test-Path -LiteralPath $cfgFile) {
        $val = (Get-Content -LiteralPath $cfgFile -Raw).Trim()
        if ($val -and (Test-Path (Join-Path $val "main.py"))) {
            $projectDir = $val
        }
    }
}

# 3) Переменная окружения AVSUM_PROJECT_DIR
if (-not $projectDir -and $env:AVSUM_PROJECT_DIR) {
    $val = $env:AVSUM_PROJECT_DIR
    if (Test-Path (Join-Path $val "main.py")) {
        $projectDir = $val
    }
}

if (-not $projectDir) {
    Write-Host "Ошибка: не удалось найти main.py."
    Write-Host "Папка скрипта: $PSScriptRoot"
    Write-Host ""
    Write-Host "Как исправить:"
    Write-Host "  - положите рядом со скриптом файл '.avsum-project' с путём к папке проекта, например:"
    Write-Host "        D:\Dev\video-audio-summarizer"
    Write-Host "  - либо задайте переменную окружения AVSUM_PROJECT_DIR"
    exit 1
}

Set-Location -Path $projectDir

# Преобразуем относительный путь первого аргумента в абсолютный (от директории вызова)
$args2 = @()
if ($args.Count -gt 0 -and -not ($args[0] -like "--*")) {
    $fileArg = $args[0]
    if (-not [System.IO.Path]::IsPathRooted($fileArg)) {
        $fileArg = Join-Path $callerDir $fileArg
    }
    $args2 += $fileArg
    $args2 += $args[1..($args.Count - 1)]
} else {
    $args2 = $args
}

# Используем Python из виртуального окружения venv
$Python = Join-Path $projectDir "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Ошибка: Виртуальное окружение не найдено: $Python"
    Write-Host "Создайте его: python -m venv venv && venv\Scripts\pip install -r requirements.txt"
    exit 1
}

# Нет аргументов - показываем справку
if ($args2.Count -eq 0) {
    & $Python main.py --help
    exit 0
}

& $Python main.py @args2
exit $LASTEXITCODE