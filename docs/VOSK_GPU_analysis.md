# VOSK на GPU: анализ возможности (GTX 1060 3GB)

Дата проверки: 2026-10-11. Все выводы ниже проверены на этой машине (Windows 11,
NVIDIA GTX 1060 3GB, CC 6.1, драйвер 576.57 / CUDA 12.9, проект `video-audio-summarizer`).

## Итог

**VOSK не может работать на GPU на Windows из официального pip-пакета — на этом
стеке GPU-пути у vosk нет.** Проверено экспериментально:

- Официальный wheel `vosk-0.3.45-py3-none-win_amd64.whl` собран **без CUDA**
  (`HAVE_CUDA` не определён).
- Функция `GpuInit()` — no-op (пустой `#if HAVE_CUDA` в `src/vosk_api.cc`),
  VRAM не занимается.
- `BatchModel(...)` (единственный GPU-класс) возвращает NULL и бросает
  "Failed to create a model" — потому что `vosk_batch_model_new` при `#else`
  возвращает `NULL` (см. `src/vosk_api.cc:223-230`).

Проверка на этой машине (venv проекта):

    vosk.GpuInit()        -> OK (но ничего не делает)
    vosk.BatchModel(...)  -> Exception: Failed to create a model
    nvidia-smi            -> VRAM не изменилась

## Почему так

1. **GPU в vosk — это только batch API** (`BatchModel`/`BatchRecognizer`),
   не streaming-путь (`KaldiRecognizer`), который использует проект
   (`src/speech_recognizer.py`, `src/vosk_server.py`). Даже собранный с CUDA,
   он ускоряет только пакетную обработку многих файлов разом.
2. **Официальных GPU-колёс нет вообще** — открытый тикет
   alphacep/vosk-api#1287 "Package vosk with GPU support" (open).
   Сборка с CUDA возможна только из исходников `vosk-api` под Linux
   (в репозитории GPU-файл один: `python/example/test_gpu_batch.py`).
3. **GPU-сборка нестабильна даже на Linux** — открытые тикеты о segfault
   (#1677, #1222), никак не сопровождается.
4. Windows-сборка из исходников с CUDA + Kaldi — это нереально для данного
   проекта (нужен MSVC + CUDA toolkit + cuDNN + сборка Kaldi; официально
   не поддерживается).

## Про 3GB

Даже если бы GPU-путь был, модели проекта не влезают в 3GB VRAM:

    vosk/model-en        68M   (влезает)
    vosk/model-ru        88M   (влезает)
    vosk/model-en-large  2.7G  (на грани)
    vosk/model-ru-large  3.5G  (НЕ влезает)

Плюс на этой карте ~1.6GB VRAM уже занято десктопом/браузером, свободно ~1.4GB.
Но это неважно: GPU-колёс vosk под Windows нет, а streaming-путь и так CPU-only.

## Рабочая альтернатива: faster-whisper (проверено на этой карте)

Практический способ получить GPU-транскрипцию, влезающую в 3GB, — заменить движок
на **faster-whisper** (CTranslate2, CUDA-EP). Он имеет официальные Windows-колёса,
поддерживает Pascal (sm_61) и int8.

Проверено на этой машине (scratch-venv, `ctranslate2 4.8.2`):

    ctranslate2.get_cuda_device_count() -> 1        # GPU виден
    supported compute types: float32, int8, int8_float32

Реальный прогон транскрипции, модель **small** (int8, CUDA):

    VRAM до загрузки модели:     1663 MiB / 3072 MiB
    VRAM после загрузки модели:  2127 MiB / 3072 MiB   (+464 MiB)
    VRAM после транскрипции:     2171 MiB / 3072 MiB
    результат: распознано, lang=ru, prob=1.0

То есть **faster-whisper small/int8 занимает ~0.5GB сверх базового — с запасом
влезает в 3GB.** Модель base/int8 ещё меньше. Скачивается с HuggingFace
(`Systran/faster-whisper-small`, уже в кэше HF на этой машине).

## Рекомендация

- VOSK на GPU — отбросить (технически невозможно на Windows из официальных колёс).
- Для GPU-транскрипции в 3GB — `faster-whisper` (`small` или `base`, `compute_type="int8"`),
  подключить как новый бэкенд рядом с локальным VOSK (CPU-фолбэк сохранить).
  Точки интеграции: `src/speech_recognizer.py` (интерфейс `transcribe(audio_path,
  progress_callback) -> List[TranscriptSegment]`) и фабрика
  `create_speech_recognizer()` в `src/speech_recognizer_client.py`.
- Требование: добавить `faster-whisper` в `requirements.txt`; модель качается
  один раз (~0.5GB на диск для small).
