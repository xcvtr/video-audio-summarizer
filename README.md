# Video Summarizer

Автоматическая система суммаризации видео с использованием распознавания речи (VOSK) и AI (OpenAI-совместимый API).

## Возможности

- 🎥 Обработка видео и аудио файлов через CLI
- 🎤 Извлечение аудиодорожек из видео
- 🎵 Прямая обработка аудио файлов (MP3, WAV, M4A, AAC, FLAC, OGG, WMA)
- 📝 Распознавание речи с временными метками (VOSK)
- 🤖 Генерация структурированного резюме с помощью AI (OpenAI-совместимый API)
- 🔍 Автоматическое определение ключевых моментов (по ключевым словам и контексту)
- 📸 Создание скриншотов важных моментов (только для видео)
- 📄 Генерация Markdown-документов с резюме и транскрипцией

## Требования

- Python 3.9+
- FFmpeg (для извлечения аудио)
- VOSK модель (для распознавания речи)
- OpenAI-совместимый API ключ

## Установка

### 1. Создайте виртуальное окружение и установите зависимости

```bash
# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Либо запускайте скрипты `avsum.cmd` / `avsum.ps1` — они автоматически используют Python из `venv`.

### Глобальный вызов из любой папки (Windows)

Чтобы команда `avsum <файл>` работала из любой папки:

1. Скопируйте `avsum.cmd` (и при желании `avsum.ps1`) в папку, которая уже есть в `PATH`, например `D:\appz`.
2. Положите рядом файл `.avsum-project` — туда запишите (без кавычек, один путь) папку с проектом:
   ```
   D:\Dev\video-audio-summarizer
   ```
   Важно: не дописывайте в пути символы вроде `\v` вручную — они показывают специальные escape-символы. Откройте файл в редакторе и сохраните как обычный текст.

Либо задайте переменную окружения `AVSUM_PROJECT_DIR` с путём к папке проекта — тогда `.avsum-project` не нужен.

Порядок поиска проекта в скриптах: (1) вверх от папки скрипта, пока не найдётся `main.py`; (2) файл `.avsum-project` рядом со скриптом; (3) `AVSUM_PROJECT_DIR`.

### 2. Установите FFmpeg

**Windows:**
```bash
# Используйте chocolatey
choco install ffmpeg

# Или скачайте с https://ffmpeg.org/download.html
```

**Linux:**
```bash
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### 3. Скачайте VOSK модель

Скачайте модель для вашего языка с https://alphacephei.com/vosk/models

Например, для русского языка (рекомендуется large модель для лучшей точности):
```bash
# Создайте директорию для моделей
mkdir -p vosk

# Скачайте и распакуйте large модель
cd vosk
wget https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip
unzip vosk-model-ru-0.42.zip
mv vosk-model-ru-0.42 model-ru

# Или скачайте large модель (рекомендуется)
wget https://alphacephei.com/vosk/models/vosk-model-ru-0.42-large.zip
unzip vosk-model-ru-0.42-large.zip
mv vosk-model-ru-0.42-large model-ru-large
cd ..
```

### 4. Настройте конфигурацию

Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

Отредактируйте `.env` и добавьте ваш API ключ и параметры провайдера:
```
API_KEY=sk-your-api-key-here
API_ENDPONT=https://sprutdock.ru/v1
# AI модель задаётся в config.yaml (ai.models) — список с fallback
```

Отредактируйте `config.yaml` при необходимости:
```yaml
vosk:
  model_path: "./vosk/model-ru-large"  # По умолчанию используется large модель

keywords:
  triggers:
    - "на слайде"
    - "важно"
    - "обратите внимание"
```

## Использование

### Обработка видео

```bash
python main.py video.mp4
```

### Обработка аудио

```bash
python main.py audio.mp3
```

Поддерживаемые форматы аудио: MP3, WAV, M4A, AAC, FLAC, OGG, WMA

### Обработка нескольких файлов

```bash
python main.py video1.mp4 audio1.mp3 video2.mkv audio2.wav
```

Режим работы определяется автоматически по расширению файла.

### Выбор движка распознавания (после имени файла: `v` или `w`)

Движок можно указать в конце команды — после списка файлов:

```bash
python main.py video.mp4 w    # faster-whisper (GPU) — по умолчанию
python main.py video.mp4 v    # VOSK (CPU)
python main.py a.mp4 b.mp3 v  # несколько файлов + движок
```

- `w` — faster-whisper на GPU (CUDA), модель small/int8 ~0.5GB VRAM, влезает в 3GB
- `v` — VOSK на CPU (локальная модель из `vosk.model_path`)

Без аргумента берётся `vosk.mode` из `config.yaml` (по умолчанию `whisper`).

### Режимы работы

**Повторная AI обработка** (использует существующую транскрипцию):
```bash
python main.py video.mp4 --reprocess-ai "путь/к/папке_summary"
```
- Загружает существующий transcript.md (или transcript.txt для обратной совместимости)
- Генерирует улучшенное AI резюме (3-5 самых важных моментов)
- Создает новые скриншоты
- Обновляет summary.md

**Пересоздание скриншотов** (использует существующее резюме):
```bash
python main.py video.mp4 --debug-screenshots "путь/к/папке_summary"
```
- Парсит существующий summary.md
- Создает скриншоты для ключевых моментов
- Не изменяет summary.md

### Дополнительные опции

```bash
python main.py video.mp4 --config custom_config.yaml --verbose
```

### Примеры

**Обработка видео лекции:**
```bash
python main.py lecture.mp4
# Результат: lecture_summary/ с аудио, скриншотами и резюме
```

**Обработка аудио подкаста:**
```bash
python main.py podcast.mp3
# Результат: podcast_summary/ с транскрипцией и резюме
```

**Пакетная обработка:**
```bash
python main.py *.mp4 *.mp3
# Обработает все видео и аудио файлы в текущей папке
```

## Структура выходных файлов

### Для видео

Папка с результатами создается **рядом с исходным видео**:

```
/путь/к/видео/
├── video.mp4                   # Исходное видео
└── video_summary/              # Папка с результатами
    ├── audio/
    │   └── video.wav           # Аудиодорожка (временно, удаляется)
    ├── screenshots/
    │   ├── 00_05_23.jpg       # Скриншоты ключевых моментов
    │   ├── 00_11_25.jpg
    │   └── ...
    ├── transcript.md          # Полная транскрипция с временными метками в формате Markdown
    └── summary.md              # Итоговое резюме в Markdown
```

### Для аудио

Папка с результатами создается **рядом с исходным аудио** (как для видео):

```
/путь/к/аудио/
├── audio.mp3               # Исходное аудио
└── audio_summary/          # Папка с результатами
    ├── audio/
    │   └── audio.wav       # Аудио в формате для распознавания (сохраняется)
    ├── transcript.md       # Полная транскрипция с временными метками
    └── summary.md          # Итоговое резюме в Markdown (без скриншотов)
```

Транскрипция сохраняется отдельно в `transcript.md` и не перезаписывается резюме.

**Процесс обработки:**
- **Видео:** Извлекается аудио → WAV → транскрибация → скриншоты → резюме
- **Аудио:** Конвертация в WAV (временно) → транскрибация → резюме (без скриншотов)

## Конфигурация

### config.yaml

```yaml
# Движок распознавания речи: "whisper" (faster-whisper, GPU/CPU), "local" (VOSK, CPU), "server" (VOSK-сервер)
vosk:
  model_path: "./vosk/model-ru-large"  # Путь к VOSK модели (для режимов "local"/"server")
  mode: "whisper"                      # "whisper" | "local" | "server"
  # Режим "server"
  server:
    url: "http://127.0.0.1:8000"
    timeout: 300
  # Режим "whisper" (faster-whisper, работает на GPU)
  whisper:
    model_size: "small"     # tiny / base / small / medium / large-v3
    device: "auto"          # "auto" | "cuda" | "cpu"
    compute_type: "int8"    # int8 = минимум VRAM, влезает в 3GB

audio:
  format: "wav"                               # Формат аудио
  sample_rate: 16000                          # Частота дискретизации
  channels: 1                                 # Количество каналов (моно)

screenshots:
  format: "jpg"                               # Формат скриншотов
  quality: 95                                 # Качество JPEG (1-100)

keywords:
  triggers:                                   # Ключевые слова для определения важных моментов
    - "на слайде"
    - "важно"
    - "обратите внимание"
    - "ключевой момент"
    - "запомните"

output:
  base_dir: "./output"                        # Базовая директория для результатов
```

#### Движки распознавания речи

- **`whisper` (по умолчанию)** — faster-whisper на GPU (CUDA). Проверено на
  GTX 1060 3GB: модель `small`/int8 занимает ~0.5GB VRAM и влезает в 3GB.
  Требует: `pip install -r requirements.txt` (faster-whisper), модель скачается
  с HuggingFace при первом запуске.
- **`local`** — VOSK на CPU (прежний режим по умолчанию). Требует скачанной
  модели VOSK по пути `vosk.model_path`.
- **`server`** — VOSK-сервер (FastAPI), модель грузится один раз.

Подробности про GPU и VOSK — см. `docs/VOSK_GPU_analysis.md`.

### .env

```env
API_KEY=sk-your-api-key-here
API_ENDPONT=https://sprutdock.ru/v1
# AI модель задаётся в config.yaml (ai.models) — список с fallback, здесь не указывается.
```

### AI-модели (fallback)

Список моделей и порядок перебора задаётся в `config.yaml` (`ai.models`). При генерации резюме модели пробуются по порядку, пока одна не ответит — если первая недоступна или выдаёт ошибку, автоматически переключается на следующую:

```yaml
ai:
  models:
    - "apodex/apodex-1.1-mini:free"        # 1-я (бесплатная)
    - "dots-studio/dots-3-note-preview:free" # 2-я (бесплатная)
    - "nvidia/nemotron-3.5-lightning:free"   # 3-я (бесплатная)
    - "~deepseek/deepseek-flash-latest"      # 4-я (платная, последний резерв)
```

## Разработка

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=src --cov-report=html

# Только unit тесты
pytest tests/test_*.py -k "not property"

# Только property-based тесты
pytest tests/test_*_properties.py
```

### Структура проекта

```
.
├── src/
│   ├── __init__.py
│   ├── cli.py                  # CLI интерфейс
│   ├── config.py               # Управление конфигурацией
│   ├── models.py               # Модели данных
│   ├── audio_extractor.py      # Извлечение аудио
│   ├── speech_recognizer.py    # Распознавание речи (локальный режим)
│   ├── speech_recognizer_client.py # Клиент для серверного режима
│   ├── vosk_server.py          # Сервер VOSK
│   ├── vosk_client.py          # Клиент VOSK
│   ├── keyword_detector.py     # Определение ключевых слов
│   ├── ai_summarizer.py        # AI суммаризация
│   ├── screenshot_capturer.py  # Создание скриншотов
│   ├── output_manager.py       # Управление выходными файлами
│   └── processor.py            # Оркестрация обработки
├── tests/
│   └── ...                     # Тесты
├── config.yaml                 # Конфигурация
├── .env.example                # Пример файла с секретами
├── requirements.txt            # Зависимости Python
├── avsum.cmd                   # Скрипт запуска из любой директории
├── avsum.ps1                   # PowerShell скрипт
├── run_vosk_server.cmd         # Скрипт запуска сервера VOSK
├── run_vosk_client.cmd         # Скрипт запуска клиента VOSK
└── README.md                   # Этот файл
```

## Сервер-клиент архитектура (опционально)

Для ускорения обработки при работе с несколькими файлами можно использовать сервер-клиент архитектуру, где модель VOSK загружается один раз при запуске сервера.

### Запуск сервера VOSK

```bash
# Запуск сервера с моделью по умолчанию
python -m src.vosk_server

# Или с указанием параметров
python -m src.vosk_server --model-path ./vosk/model-ru --host 127.0.0.1 --port 8000

# Используя скрипт
run_vosk_server.cmd
```

### Использование клиента

```bash
# Проверка состояния сервера
python -m src.vosk_client --server http://127.0.0.1:8000 --check-health

# Транскрипция аудиофайла
python -m src.vosk_client --server http://127.0.0.1:8000 --audio-file audio.wav --output transcript.md

# Используя скрипт
run_vosk_client.cmd --audio-file audio.wav
```

### Настройка серверного режима в конфигурации

Измените `config.yaml` для использования серверного режима:

```yaml
vosk:
  model_path: "./vosk/model-ru-large"
  # Режим работы: "local" - локальная модель, "server" - через сервер
  mode: "server"
  # Настройки для серверного режима
  server:
    url: "http://127.0.0.1:8000"
    timeout: 300  # секунды
```

### API сервера

Сервер предоставляет следующие эндпоинты:

- `GET /health` - проверка состояния сервера
- `GET /model-info` - информация о загруженной модели
- `POST /transcribe` - транскрипция аудиофайла (WAV формат)
- `POST /transcribe-file` - транскрипция файла по локальному пути

## Лицензия

MIT

## Поддержка

Для вопросов и проблем создайте issue в репозитории проекта.
