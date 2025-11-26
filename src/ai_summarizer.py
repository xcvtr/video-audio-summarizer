"""AI-powered summarization using DeepSeek API."""

import re
from typing import List, Tuple
from openai import OpenAI
from src.models import TranscriptSegment, KeyMoment


class APIError(Exception):
    """API-related errors."""
    pass


class AISummarizer:
    """Generates structured summaries using DeepSeek API."""
    
    def __init__(self, api_key: str):
        """Initialize DeepSeek API client.
        
        Args:
            api_key: DeepSeek API key
        """
        if not api_key:
            raise APIError("DeepSeek API key is required")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
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
            
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are an expert analyst that creates detailed, comprehensive summaries of video and audio transcripts. You provide in-depth analysis with specific details, examples, and thorough explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            summary_text = response.choices[0].message.content
            
            # Parse response to extract summary and key moments
            summary, key_moments = self._parse_ai_response(summary_text, transcript)
            
            return summary, key_moments
            
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
        
        prompt = f"""Создай ПОДРОБНОЕ структурированное резюме этой видео-транскрипции в формате Markdown НА РУССКОМ ЯЗЫКЕ.

Название: {video_title}

Транскрипция:
{transcript_text}

ТРЕБОВАНИЯ К РЕЗЮМЕ:

1. **Краткий обзор** (3-4 предложения)
   - О чем это видео/аудио
   - Основная тема и контекст
   - Кто выступает (если понятно из контекста)

2. **Основные темы с временными метками** (формат HH:MM:SS)
   - Разбей контент на 5-8 тематических блоков
   - Укажи временной диапазон для каждого блока
   - Дай краткое описание каждой темы

3. **Детальный разбор ключевых моментов**
   - Для КАЖДОЙ основной темы напиши подробный параграф (3-5 предложений)
   - Раскрой суть обсуждаемых вопросов
   - Укажи конкретные факты, цифры, примеры, если они упоминались
   - Объясни логику рассуждений и выводы
   - Используй подзаголовки для структурирования

4. **Практические выводы и рекомендации**
   - Что конкретно предлагается делать
   - Какие решения были приняты
   - Какие действия рекомендуются

5. **САМЫЕ ВАЖНЫЕ МОМЕНТЫ** (3-5 штук)
   - Выбери ТОЛЬКО критически важные моменты с ключевыми решениями или выводами
   - Для каждого напиши 2-3 предложения с подробным объяснением
   - Отметь префиксом "ВАЖНЫЙ МОМЕНТ:" с временной меткой [HH:MM:SS]
   - Объясни, ПОЧЕМУ этот момент важен

ВАЖНО: 
- Резюме должно быть ПОДРОБНЫМ и ИНФОРМАТИВНЫМ
- Не ограничивайся общими фразами - раскрывай детали
- Используй конкретику из транскрипции
- Структурируй информацию с помощью заголовков и списков
- ВСЁ НА РУССКОМ ЯЗЫКЕ

Форматируй ответ в Markdown с правильными заголовками и структурой."""
        
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
        
        # Find all lines with key moment markers and extract timestamps
        key_moment_pattern = r'(?:ВАЖНЫЙ МОМЕНТ|KEY MOMENT):.*?(\d{1,2}:\d{2}:\d{2})'
        matches = re.finditer(key_moment_pattern, response, re.IGNORECASE)
        
        for match in matches:
            timestamp_str = match.group(1)
            # Convert timestamp to seconds
            parts = timestamp_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                timestamp = hours * 3600 + minutes * 60 + seconds
                
                # Extract description (text after timestamp)
                line = match.group(0)
                description = re.sub(r'(?:ВАЖНЫЙ МОМЕНТ|KEY MOMENT):\s*', '', line, flags=re.IGNORECASE)
                description = description.replace(timestamp_str, '').strip()
                
                moment = KeyMoment(
                    timestamp=float(timestamp),
                    description=description[:100],  # Limit description length
                    importance=0.9,  # High importance for AI-identified moments
                    source="context"
                )
                key_moments.append(moment)
        
        # Clean up the summary (remove key moment markers for cleaner output)
        summary = re.sub(r'(?:ВАЖНЫЙ МОМЕНТ|KEY MOMENT):\s*', '', response, flags=re.IGNORECASE)
        
        return summary, key_moments
