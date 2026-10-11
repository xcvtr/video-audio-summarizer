"""AI-powered summarization using an OpenAI-compatible API."""

import re
from typing import List, Tuple, Optional
from openai import OpenAI
import httpx
from src.models import TranscriptSegment, KeyMoment


class APIError(Exception):
    """API-related errors."""
    pass


class AISummarizer:
    """Generates structured summaries using an OpenAI-compatible API."""

    def __init__(self, api_key: str, model: str = "nex-agi/nex-n2.5-mini:free", base_url: str = "",
                 models: Optional[List[str]] = None):
        """Initialize API client.

        Args:
            api_key: API key
            model: Одиночная модель (для обратной совместимости). Если models задан — игнорируется.
            base_url: OpenAI-совместимый base URL (из .env)
            models: Список моделей для fallback в порядке приоритета. Если задан,
                    используется он, иначе одиночная `model`.
        """
        if not api_key:
            raise APIError("API key is required")
        if not base_url:
            raise APIError("OpenAI-compatible API base URL is required (set API_ENDPONT in .env)")

        # Список моделей: models > [model]
        self.models = list(models) if models else [model]
        if not self.models:
            raise APIError("No AI model specified")
        self.model = self.models[0]

        # Disable SSL verification for corporate proxy/antivirus compatibility
        http_client = httpx.Client(verify=False)

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )

    def generate_summary(
        self,
        transcript: List[TranscriptSegment],
        video_title: str
    ) -> Tuple[str, List[KeyMoment]]:
        """Generate markdown summary and identify key moments.

        Args:
            transcript: List of transcript segments
            video_title: Title of the video

        Returns:
            Tuple of (markdown summary, list of key moments)

        Raises:
            APIError: If API call fails
        """
        if not transcript:
            return "# Summary\n\nNo transcript available.", []

        try:
            prompt = self._build_prompt(transcript, video_title)

            errors = []
            for model in self.models:
                self.model = model
                try:
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "Ты - эксперт-аналитик с глубоким пониманием контекста. Твоя задача - анализировать транскрипты с ошибками распознавания речи, исправлять эти ошибки на основе контекста и создавать подробные, структурированные резюме. Ты не копируешь транскрипт дословно, а перерабатываешь его в качественный аналитический текст с исправлением ошибок, добавлением структуры и глубины анализа."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=6000
                    )

                    # Check if response has choices
                    if not response.choices or len(response.choices) == 0:
                        raise APIError(f"API returned empty response. Full response: {response}")

                    summary_text = response.choices[0].message.content
                    print(f"\n[DEBUG] AI model used: {model}")
                    print(f"[DEBUG] Raw AI response (first 500 chars):")
                    print(summary_text[:500])
                    print(f"[DEBUG] Full response length: {len(summary_text)} chars\n")

                    # Parse response to extract summary and key moments
                    summary, key_moments = self._parse_ai_response(summary_text, transcript)
                    return summary, key_moments

                except Exception as e:
                    errors.append(f"{model}: {e}")
                    print(f"[WARN] Model {model} failed, fallback... error: {e}")

            # Все модели не сработали
            raise APIError("; ".join(errors) or "No AI model succeeded")

        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Failed to generate summary: {e}")

    def _build_prompt(self, transcript: List[TranscriptSegment], video_title: str) -> str:
        """Build prompt for AI with transcript.

        Args:
            transcript: List of transcript segments
            video_title: Title of the video

        Returns:
            Formatted prompt string
        """
        transcript_text = "\n".join([
            f"[{seg.get_start_timestamp()}] {seg.text}"
            for seg in transcript
        ])

        prompt = f"""Ты - эксперт по анализу и переработке транскриптов. Твоя задача - создать ПОДРОБНОЕ, СТРУКТУРИРОВАННОЕ и ИСПРАВЛЕННОЕ резюме на основе предоставленной транскрипции.

ВАЖНО: Транскрипция содержит ошибки распознавания речи. Твоя задача - понять смысл, исправить ошибки и создать качественное резюме.

Название: {video_title}

Транскрипция (с ошибками распознавания):
{transcript_text}

ТРЕБОВАНИЯ К РЕЗЮМЕ:

1. **КРАТКИЙ ОБЗОР** (4-6 предложений)
   - Основная тема и цель контента
   - Кто говорит/выступает (если можно определить)
   - Ключевая проблема или вопрос, который обсуждается
   - Общий контекст и значимость материала

2. **ПОДРОБНЫЙ РАЗБОР ПО ТЕМАТИЧЕСКИМ БЛОКАМ** (5-8 блоков)
   Для каждого блока:
   - Временной диапазон [HH:MM:SS - HH:MM:SS]
   - Название темы/раздела
   - Подробное содержание (5-7 предложений):
     * Что именно обсуждается
     * Какие аргументы приводятся
     * Какие примеры или кейсы упоминаются
     * Какие выводы или решения предлагаются
     * Исправь ошибки распознавания, восстанови правильный смысл

3. **АНАЛИЗ И ИНТЕРПРЕТАЦИЯ**
   - Логическая структура повествования
   - Связи между разными темами
   - Эволюция идей или аргументов
   - Скрытые смыслы или подтексты (если есть)

4. **КЛЮЧЕВЫЕ ВЫВОДЫ И РЕКОМЕНДАЦИИ**
   - Основные выводы из материала
   - Практические рекомендации или действия
   - Что можно применить на практике
   - Какие вопросы остались открытыми

5. **САМЫЕ ВАЖНЫЕ МОМЕНТЫ** (3-5 моментов)
   Для каждого важного момента:
   - Временная метка [HH:MM:SS]
   - Префикс "ВАЖНЫЙ МОМЕНТ:"
   - Подробное описание (3-4 предложения):
     * Что происходит в этот момент
     * Почему это важно
     * Какое значение имеет для общего понимания
     * Как это связано с другими частями

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:
1. НЕ КОПИРУЙ ТРАНСКРИПТ ДОСЛОВНО - создавай ПЕРЕРАБОТАННЫЙ текст
2. ИСПРАВЛЯЙ ОШИБКИ РАСПОЗНАВАНИЯ - используй контекст для восстановления правильного смысла
3. БУДЬ ПОДРОБНЫМ - не ограничивайся общими фразами, раскрывай детали
4. СТРУКТУРИРУЙ ИНФОРМАЦИЮ - используй заголовки, подзаголовки, списки
5. СОЗДАВАЙ ЦЕЛОСТНОЕ ПОВЕСТВОВАНИЕ - резюме должно читаться как связный текст
6. ФОКУСИРУЙСЯ НА СМЫСЛЕ, а не на дословном воспроизведении
7. ВСЁ НА РУССКОМ ЯЗЫКЕ с правильной грамматикой и стилем

Формат вывода: Markdown с четкой структурой и заголовками."""

        return prompt

    def _parse_ai_response(self, response: str, transcript: List[TranscriptSegment]) -> Tuple[str, List[KeyMoment]]:
        """Parse AI response to extract summary and key moments.

        Args:
            response: AI response text
            transcript: Original transcript for timestamp validation

        Returns:
            Tuple of (summary markdown, list of key moments)
        """
        # Extract key moments marked with "ВАЖНЫЙ МОМЕНТ:" or "KEY MOMENT:"
        key_moments = []

        # Improved pattern to capture more variations
        key_moment_pattern = r'(?:ВАЖНЫЙ МОМЕНТ|KEY MOMENT|Важный момент|Key moment):\s*(.*?)(?:\n|$)'
        matches = re.finditer(key_moment_pattern, response, re.IGNORECASE | re.MULTILINE)

        for match in matches:
            line = match.group(0)

            # Try to extract timestamp from the line
            timestamp_match = re.search(r'\[(\d{1,2}:\d{2}:\d{2})\]', line)
            if timestamp_match:
                timestamp_str = timestamp_match.group(1)
                # Convert timestamp to seconds
                parts = timestamp_str.split(':')
                if len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    timestamp = hours * 3600 + minutes * 60 + seconds

                    # Extract description (remove markers and timestamp)
                    description = re.sub(r'(?:ВАЖНЫЙ МОМЕНТ|KEY MOMENT|Важный момент|Key moment):\s*', '', line, flags=re.IGNORECASE)
                    description = re.sub(r'\[\d{1,2}:\d{2}:\d{2}\]', '', description).strip()

                    # Clean up description
                    description = re.sub(r'^\s*[-•*]\s*', '', description)  # Remove bullet points
                    description = description.strip()

                    if description and len(description) > 10:  # Ensure meaningful description
                        moment = KeyMoment(
                            timestamp=float(timestamp),
                            description=description[:150],  # Increased limit for better descriptions
                            importance=0.9,  # High importance for AI-identified moments
                            source="ai_analysis"
                        )
                        key_moments.append(moment)

        # Clean up the summary - remove key moment markers but keep the rest
        # We'll remove lines that start with key moment markers
        lines = response.split('\n')
        cleaned_lines = []
        for line in lines:
            if not re.match(r'^\s*(?:ВАЖНЫЙ МОМЕНТ|KEY MOMENT|Важный момент|Key moment):', line, re.IGNORECASE):
                cleaned_lines.append(line)

        summary = '\n'.join(cleaned_lines)

        return summary, key_moments