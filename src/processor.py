"""Video processing orchestration."""

from pathlib import Path
from typing import List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from src.config import Config
from src.models import ProcessingResult
from src.audio_extractor import AudioExtractor, AudioExtractionError
from src.speech_recognizer import SpeechRecognizer, SpeechRecognitionError
from src.keyword_detector import KeywordDetector
from src.ai_summarizer import AISummarizer, APIError
from src.screenshot_capturer import ScreenshotCapturer, ScreenshotError
from src.output_manager import OutputManager


class VideoProcessingError(Exception):
    """Base exception for video processing errors."""
    pass


class VideoProcessor:
    """Orchestrates the entire video processing pipeline."""
    
    def __init__(self, config: Config):
        """Initialize processor with configuration.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.console = Console()
        
        # Initialize components
        self.audio_extractor = AudioExtractor(config)
        
        # Инициализация распознавателя речи в зависимости от режима
        if config.vosk_mode == "whisper":
            from src.speech_recognizer_whisper import WhisperRecognizer
            try:
                self.speech_recognizer = WhisperRecognizer(
                    model_size=config.whisper_model_size,
                    device=config.whisper_device,
                    compute_type=config.whisper_compute_type,
                    language=config.whisper_language,
                )
                self.console.print(
                    f"[green][OK][/green] faster-whisper ({config.whisper_model_size}, "
                    f"{self.speech_recognizer.device}/{config.whisper_compute_type})"
                )
            except Exception as e:
                self.console.print(f"[yellow]⚠[/yellow] Не удалось загрузить faster-whisper: {e}")
                self.console.print("[yellow]⚠[/yellow] Переключение на локальный режим VOSK...")
                from src.speech_recognizer import SpeechRecognizer
                self.speech_recognizer = SpeechRecognizer(config.vosk_model_path)
        elif config.vosk_mode == "server":
            from src.speech_recognizer_client import SpeechRecognizerClient
            try:
                self.speech_recognizer = SpeechRecognizerClient(
                    server_url=config.vosk_server_url,
                    timeout=config.vosk_server_timeout
                )
                self.console.print(f"[green][OK][/green] Используется серверный режим VOSK: {config.vosk_server_url}")
            except Exception as e:
                self.console.print(f"[yellow]⚠[/yellow] Не удалось подключиться к серверу VOSK: {e}")
                self.console.print("[yellow]⚠[/yellow] Переключение на локальный режим...")
                from src.speech_recognizer import SpeechRecognizer
                self.speech_recognizer = SpeechRecognizer(config.vosk_model_path)
        else:
            from src.speech_recognizer import SpeechRecognizer
            self.speech_recognizer = SpeechRecognizer(config.vosk_model_path)
            self.console.print(f"[green][OK][/green] Используется локальный режим VOSK")
        
        self.keyword_detector = KeywordDetector(config.keyword_triggers)
        print(f"[DEBUG] AI Model: {config.ai_model}")
        print(f"[DEBUG] AI Models (fallback): {config.ai_models}")
        print(f"[DEBUG] API Base URL: {config.ai_base_url}")
        print(f"[DEBUG] API Key (first 10 chars): {config.deepseek_api_key[:10]}...")
        self.ai_summarizer = AISummarizer(config.deepseek_api_key, config.ai_model, config.ai_base_url,
                                          models=config.ai_models)
        self.screenshot_capturer = ScreenshotCapturer(config)
        self.output_manager = OutputManager(Path(config.output_base_dir))
    
    def process_file(self, file_path: str) -> ProcessingResult:
        """Process video or audio file.
        
        Args:
            file_path: Path to video or audio file
            
        Returns:
            ProcessingResult with status and output paths
        """
        file = Path(file_path)
        file_ext = file.suffix.lower()
        
        # Determine if it's audio or video
        audio_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.wma'}
        
        if file_ext in audio_extensions:
            return self.process_audio(file_path)
        else:
            return self.process_video(file_path)
    
    def process_video(self, video_path: str) -> ProcessingResult:
        """Process single video through entire pipeline.
        
        Args:
            video_path: Path to video file
            
        Returns:
            ProcessingResult with status and output paths
        """
        video_file = Path(video_path)
        video_name = video_file.stem
        
        self.console.print(f"\n[bold blue]Processing video:[/bold blue] {video_name}")
        
        try:
            # Create output directory next to video file
            output_dir = self._create_output_directory(video_path, video_name)
            
            result = ProcessingResult(
                video_path=video_path,
                output_dir=output_dir,
                success=False
            )
            
            # Step 1: Extract audio
            self.console.print("[yellow]→[/yellow] Extracting audio...")
            audio_path = output_dir / "audio" / "audio.wav"
            try:
                self.audio_extractor.extract(video_path, str(audio_path))
                result.audio_path = audio_path
                self.console.print("[green][OK][/green] Audio extracted")
            except AudioExtractionError as e:
                result.error = str(e)
                self.console.print(f"[red]✗[/red] Audio extraction failed: {e}")
                return result
            
            # Step 2: Transcribe speech
            from rich.progress import BarColumn, TimeRemainingColumn
            with Progress(
                SpinnerColumn(),
                TextColumn("[yellow]Transcribing speech...[/yellow]"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("transcribe", total=100)
                
                def update_progress(current, total):
                    if total > 0:
                        percentage = (current / total) * 100
                        progress.update(task, completed=percentage)
                
                try:
                    transcript = self.speech_recognizer.transcribe(str(audio_path), progress_callback=update_progress)
                    transcript_path = output_dir / "transcript.md"
                    self.speech_recognizer.save_transcript(transcript, str(transcript_path))
                    result.transcript_path = transcript_path
                    progress.update(task, completed=100)
                    self.console.print(f"[green][OK][/green] Transcribed {len(transcript)} segments")
                except SpeechRecognitionError as e:
                    progress.update(task, completed=100)
                    result.error = str(e)
                    self.console.print(f"[red]✗[/red] Speech recognition failed: {e}")
                    return result
            
            if not transcript:
                result.error = "No speech recognized"
                self.console.print(f"[red]✗[/red] Speech recognition failed: No speech recognized")
                return result
            
            # Step 2.5: Convert WAV to MP3
            self.console.print("[yellow]→[/yellow] Converting audio to MP3...")
            try:
                mp3_path = self.audio_extractor.convert_to_mp3(str(audio_path), video_name)
                result.audio_path = mp3_path
                self.console.print("[green][OK][/green] Audio converted to MP3")
            except AudioExtractionError as e:
                self.console.print(f"[yellow]![/yellow] MP3 conversion failed: {e}")
                # Continue with WAV file
            
            # Step 3: Detect keywords
            self.console.print("[yellow]→[/yellow] Detecting key moments...")
            keyword_moments = self.keyword_detector.detect(transcript)
            self.console.print(f"[green][OK][/green] Found {len(keyword_moments)} keyword moments")
            
            # Step 4: Generate AI summary
            with Progress(
                SpinnerColumn(),
                TextColumn("[yellow]Generating AI summary...[/yellow]"),
                console=self.console
            ) as progress:
                task = progress.add_task("summarize", total=None)
                try:
                    summary, ai_moments = self.ai_summarizer.generate_summary(transcript, video_name)
                    progress.update(task, completed=True)
                except APIError as e:
                    progress.update(task, completed=True)
                    summary = f"# {video_name}\n\n## Транскрипция\n\nAI резюме недоступно."
                    ai_moments = []
                    error_msg = str(e)
            
            # Print result after progress bar is closed
            if 'error_msg' in locals():
                self.console.print(f"[yellow]![/yellow] AI summary failed: {error_msg}")
                self.console.print("[yellow]→[/yellow] Continuing with transcript only...")
            else:
                self.console.print(f"[green][OK][/green] Summary generated with {len(ai_moments)} AI moments")
            
            # Combine key moments
            all_moments = keyword_moments + ai_moments
            
            # Step 5: Capture screenshots
            if all_moments:
                with Progress(
                    SpinnerColumn(),
                    TextColumn(f"[yellow]Capturing {len(all_moments)} screenshots...[/yellow]"),
                    console=self.console
                ) as progress:
                    task = progress.add_task("screenshots", total=len(all_moments))
                    try:
                        timestamps = [m.timestamp for m in all_moments]
                        screenshots = self.screenshot_capturer.capture(
                            video_path,
                            timestamps,
                            output_dir / "screenshots"
                        )
                        result.screenshots = screenshots
                        progress.update(task, completed=len(all_moments))
                    except ScreenshotError as e:
                        progress.update(task, completed=len(all_moments))
                        screenshots = []
                        screenshot_error = str(e)
                
                # Print result after progress bar is closed
                if 'screenshot_error' in locals():
                    self.console.print(f"[yellow]![/yellow] Screenshot capture failed: {screenshot_error}")
                else:
                    self.console.print(f"[green][OK][/green] Captured {len(screenshots)} screenshots")
            else:
                screenshots = []
                self.console.print("[yellow]![/yellow] No key moments found, skipping screenshots")
            
            # Step 6: Generate final markdown
            self.console.print("[yellow]→[/yellow] Generating summary document...")
            summary_path = output_dir / "summary.md"
            self.output_manager.generate_summary_markdown(
                video_name,
                summary,
                transcript,
                all_moments,
                screenshots,
                summary_path
            )
            result.summary_path = summary_path
            self.console.print("[green][OK][/green] Summary document created")
            
            result.success = True
            self.console.print(f"[bold green][OK] Processing complete![/bold green] Output: {output_dir}")
            
            return result
            
        except Exception as e:
            self.console.print(f"[bold red]✗ Processing failed:[/bold red] {e}")
            return ProcessingResult(
                video_path=video_path,
                output_dir=output_dir if 'output_dir' in locals() else Path("."),
                success=False,
                error=str(e)
            )
    
    def process_audio(self, audio_path: str) -> ProcessingResult:
        """Process audio file (no video, no screenshots).
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            ProcessingResult with status and output paths
        """
        audio_file = Path(audio_path)
        audio_name = audio_file.stem
        audio_dir = audio_file.parent
        
        self.console.print(f"\n[bold blue]Processing audio:[/bold blue] {audio_name}")
        
        try:
            # Create output directory next to audio file (папка с именем файла)
            output_dir = self._create_output_directory(audio_path, audio_name)
            
            result = ProcessingResult(
                video_path=audio_path,
                output_dir=output_dir,
                success=False
            )
            
            # Step 1: Convert audio to VOSK format if needed
            self.console.print("[yellow]→[/yellow] Preparing audio...")
            temp_wav = output_dir / "audio" / "audio.wav"
            
            try:
                # Convert to VOSK-compatible format
                self.audio_extractor._convert_to_vosk_format(audio_path, str(temp_wav))
                result.audio_path = temp_wav
                self.console.print("[green][OK][/green] Audio prepared")
            except AudioExtractionError as e:
                result.error = str(e)
                self.console.print(f"[red]✗[/red] Audio preparation failed: {e}")
                return result
            
            # Step 2: Transcribe speech
            from rich.progress import BarColumn, TimeRemainingColumn
            with Progress(
                SpinnerColumn(),
                TextColumn("[yellow]Transcribing speech...[/yellow]"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("transcribe", total=100)
                
                def update_progress(current, total):
                    if total > 0:
                        percentage = (current / total) * 100
                        progress.update(task, completed=percentage)
                
                try:
                    transcript = self.speech_recognizer.transcribe(str(temp_wav), progress_callback=update_progress)
                    transcript_path = output_dir / "transcript.md"
                    self.speech_recognizer.save_transcript(transcript, str(transcript_path))
                    result.transcript_path = transcript_path
                    progress.update(task, completed=100)
                    self.console.print(f"[green][OK][/green] Transcribed {len(transcript)} segments")
                except SpeechRecognitionError as e:
                    progress.update(task, completed=100)
                    result.error = str(e)
                    self.console.print(f"[red]✗[/red] Speech recognition failed: {e}")
                    return result

            # Удаляем временно конвертированное аудио (транскрипт уже сохранён)
            try:
                if temp_wav.exists():
                    temp_wav.unlink()
                audio_subdir = temp_wav.parent
                if audio_subdir.exists() and not any(audio_subdir.iterdir()):
                    audio_subdir.rmdir()
            except Exception as e:
                self.console.print(f"[yellow]![/yellow] Не удалось удалить временное аудио: {e}")

            if not transcript:
                result.error = "No speech recognized"
                self.console.print(f"[red]✗[/red] Speech recognition failed: No speech recognized")
                return result
            
            # Step 3: Detect keywords
            self.console.print("[yellow]→[/yellow] Detecting key moments...")
            keyword_moments = self.keyword_detector.detect(transcript)
            self.console.print(f"[green][OK][/green] Found {len(keyword_moments)} keyword moments")
            
            # Step 4: Generate AI summary
            with Progress(
                SpinnerColumn(),
                TextColumn("[yellow]Generating AI summary...[/yellow]"),
                console=self.console
            ) as progress:
                task = progress.add_task("summarize", total=None)
                try:
                    summary, ai_moments = self.ai_summarizer.generate_summary(transcript, audio_name)
                    progress.update(task, completed=True)
                except APIError as e:
                    progress.update(task, completed=True)
                    summary = f"# {audio_name}\n\n## Транскрипция\n\nAI резюме недоступно."
                    ai_moments = []
                    error_msg = str(e)
            
            # Print result after progress bar is closed
            if 'error_msg' in locals():
                self.console.print(f"[yellow]![/yellow] AI summary failed: {error_msg}")
                self.console.print("[yellow]→[/yellow] Continuing with transcript only...")
            else:
                self.console.print(f"[green][OK][/green] Summary generated with {len(ai_moments)} AI moments")
            
            # Combine key moments (no screenshots for audio)
            all_moments = keyword_moments + ai_moments
            
            # Step 5: Generate final markdown (no screenshots)
            self.console.print("[yellow]→[/yellow] Generating summary document...")
            summary_path = output_dir / "summary.md"
            self.output_manager.generate_summary_markdown(
                audio_name,
                summary,
                transcript,
                all_moments,
                [],  # No screenshots for audio
                summary_path
            )
            result.summary_path = summary_path
            self.console.print("[green][OK][/green] Summary document created")
            
            result.success = True
            self.console.print(f"[bold green][OK] Processing complete![/bold green] Output: {output_dir}")
            
            return result
            
        except Exception as e:
            self.console.print(f"[bold red]✗ Processing failed:[/bold red] {e}")
            return ProcessingResult(
                video_path=audio_path,
                output_dir=output_dir if 'output_dir' in locals() else audio_dir,
                success=False,
                error=str(e)
            )
    
    def process_multiple(self, file_paths: List[str]) -> List[ProcessingResult]:
        """Process multiple video or audio files.
        
        Args:
            file_paths: List of video or audio file paths
            
        Returns:
            List of processing results
        """
        results = []
        
        for file_path in file_paths:
            # Check if file exists
            if not Path(file_path).exists():
                self.console.print(f"[red]✗[/red] File not found: {file_path}")
                results.append(ProcessingResult(
                    video_path=file_path,
                    output_dir=Path("."),
                    success=False,
                    error=f"File not found: {file_path}"
                ))
                continue
            
            # Process file (auto-detect video or audio)
            result = self.process_file(file_path)
            results.append(result)
        
        # Print summary statistics
        success_count = sum(1 for r in results if r.success)
        error_count = len(results) - success_count
        
        self.console.print("\n[bold]Processing Summary:[/bold]")
        self.console.print(f"  Total files: {len(results)}")
        self.console.print(f"  [green]Successful: {success_count}[/green]")
        self.console.print(f"  [red]Failed: {error_count}[/red]")
        
        return results
    
    def debug_generate_screenshots(self, results_dir: str, video_path: str) -> ProcessingResult:
        """Debug mode: Generate screenshots from existing results.
        
        Args:
            results_dir: Path to existing results directory
            video_path: Path to original video file
            
        Returns:
            ProcessingResult
        """
        results_path = Path(results_dir)
        if not results_path.exists():
            self.console.print(f"[red]✗[/red] Results directory not found: {results_dir}")
            return ProcessingResult(
                video_path=video_path,
                output_dir=results_path,
                success=False,
                error=f"Results directory not found: {results_dir}"
            )
        
        self.console.print(f"[cyan]Loading existing results from:[/cyan] {results_dir}")
        
        # Read existing summary to extract key moments
        summary_path = results_path / "summary.md"
        if not summary_path.exists():
            self.console.print(f"[red]✗[/red] Summary file not found: {summary_path}")
            return ProcessingResult(
                video_path=video_path,
                output_dir=results_path,
                success=False,
                error="Summary file not found"
            )
        
        # Parse key moments from summary
        key_moments = self._parse_key_moments_from_summary(summary_path)
        self.console.print(f"[green][OK][/green] Found {len(key_moments)} key moments in summary")
        
        if not key_moments:
            self.console.print(f"[yellow]![/yellow] No key moments found in summary")
            return ProcessingResult(
                video_path=video_path,
                output_dir=results_path,
                success=True
            )
        
        # Generate screenshots
        screenshots_dir = results_path / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)
        
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[yellow]Generating {len(key_moments)} screenshots...[/yellow]"),
            console=self.console
        ) as progress:
            task = progress.add_task("screenshots", total=len(key_moments))
            try:
                timestamps = [m.timestamp for m in key_moments]
                screenshots = self.screenshot_capturer.capture(
                    video_path,
                    timestamps,
                    screenshots_dir
                )
                progress.update(task, completed=len(key_moments))
            except ScreenshotError as e:
                progress.update(task, completed=len(key_moments))
                screenshots = []
                screenshot_error = str(e)
        
        # Print result
        if 'screenshot_error' in locals():
            self.console.print(f"[yellow]![/yellow] Screenshot capture failed: {screenshot_error}")
        else:
            self.console.print(f"[green][OK][/green] Generated {len(screenshots)} screenshots")
        
        return ProcessingResult(
            video_path=video_path,
            output_dir=results_path,
            success=True,
            screenshots=screenshots
        )
    
    def _parse_key_moments_from_summary(self, summary_path: Path) -> List:
        """Parse key moments from existing summary file.
        
        Args:
            summary_path: Path to summary.md file
            
        Returns:
            List of KeyMoment objects
        """
        from src.models import KeyMoment
        import re
        
        key_moments = []
        
        try:
            content = summary_path.read_text(encoding='utf-8')
            
            # Find the "Ключевые моменты" section
            # Look for section that starts with "## Ключевые моменты" and ends with next "## " or end of file
            key_moments_section_match = re.search(
                r'## Ключевые моменты\s*\n(.*?)(?=\n## [^\#]|\Z)',
                content,
                re.DOTALL | re.MULTILINE
            )
            
            if not key_moments_section_match:
                self.console.print(f"[yellow]![/yellow] 'Ключевые моменты' section not found in summary")
                return []
            
            key_moments_section = key_moments_section_match.group(1)
            
            # Find all timestamps in format ### [HH:MM:SS] (may have additional text after)
            timestamp_pattern = r'###\s*\[(\d{2}:\d{2}:\d{2})\]'
            matches = re.finditer(timestamp_pattern, key_moments_section, re.MULTILINE)
            
            for match in matches:
                timestamp_str = match.group(1)
                
                # Convert timestamp to seconds
                parts = timestamp_str.split(':')
                if len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    timestamp = hours * 3600 + minutes * 60 + seconds
                    
                    moment = KeyMoment(
                        timestamp=float(timestamp),
                        description=f"Key moment at {timestamp_str}",
                        importance=0.8,
                        source="parsed"
                    )
                    key_moments.append(moment)
        
        except Exception as e:
            self.console.print(f"[yellow]![/yellow] Error parsing summary: {e}")
        
        return key_moments
    
    def reprocess_ai_summary(self, results_dir: str, video_path: str) -> ProcessingResult:
        """Reprocess AI summary from existing transcript.
        
        Args:
            results_dir: Path to existing results directory
            video_path: Path to original video file
            
        Returns:
            ProcessingResult
        """
        results_path = Path(results_dir)
        if not results_path.exists():
            self.console.print(f"[red]✗[/red] Results directory not found: {results_dir}")
            return ProcessingResult(
                video_path=video_path,
                output_dir=results_path,
                success=False,
                error=f"Results directory not found: {results_dir}"
            )
        
        self.console.print(f"[cyan]Loading existing transcript from:[/cyan] {results_dir}")
        
        # Read existing transcript
        transcript_path = results_path / "transcript.md"
        if not transcript_path.exists():
            # Try old .txt format for backward compatibility
            old_transcript_path = results_path / "transcript.txt"
            if old_transcript_path.exists():
                transcript_path = old_transcript_path
                self.console.print(f"[yellow]⚠[/yellow] Using old .txt transcript format: {transcript_path}")
            else:
                self.console.print(f"[red]✗[/red] Transcript file not found: {transcript_path}")
                return ProcessingResult(
                    video_path=video_path,
                    output_dir=results_path,
                    success=False,
                    error="Transcript file not found"
                )
        
        # Load transcript
        try:
            transcript = self.speech_recognizer.load_transcript(str(transcript_path))
            self.console.print(f"[green][OK][/green] Loaded {len(transcript)} transcript segments")
        except Exception as e:
            self.console.print(f"[red]✗[/red] Failed to load transcript: {e}")
            return ProcessingResult(
                video_path=video_path,
                output_dir=results_path,
                success=False,
                error=f"Failed to load transcript: {e}"
            )
        
        # Detect keywords
        self.console.print("[yellow]→[/yellow] Detecting key moments...")
        keyword_moments = self.keyword_detector.detect(transcript)
        self.console.print(f"[green][OK][/green] Found {len(keyword_moments)} keyword moments")
        
        # Generate AI summary with improved prompt
        video_name = Path(video_path).stem
        with Progress(
            SpinnerColumn(),
            TextColumn("[yellow]Generating improved AI summary...[/yellow]"),
            console=self.console
        ) as progress:
            task = progress.add_task("summarize", total=None)
            try:
                summary, ai_moments = self.ai_summarizer.generate_summary(transcript, video_name)
                progress.update(task, completed=True)
            except APIError as e:
                progress.update(task, completed=True)
                summary = f"# {video_name}\n\n## Транскрипция\n\nAI резюме недоступно."
                ai_moments = []
                error_msg = str(e)
        
        # Print result
        if 'error_msg' in locals():
            self.console.print(f"[yellow]![/yellow] AI summary failed: {error_msg}")
        else:
            self.console.print(f"[green][OK][/green] Summary generated with {len(ai_moments)} AI moments")
        
        # Combine key moments
        all_moments = keyword_moments + ai_moments
        
        # Capture screenshots
        if all_moments:
            with Progress(
                SpinnerColumn(),
                TextColumn(f"[yellow]Capturing {len(all_moments)} screenshots...[/yellow]"),
                console=self.console
            ) as progress:
                task = progress.add_task("screenshots", total=len(all_moments))
                try:
                    timestamps = [m.timestamp for m in all_moments]
                    screenshots = self.screenshot_capturer.capture(
                        video_path,
                        timestamps,
                        results_path / "screenshots"
                    )
                    progress.update(task, completed=len(all_moments))
                except ScreenshotError as e:
                    progress.update(task, completed=len(all_moments))
                    screenshots = []
                    screenshot_error = str(e)
            
            # Print result
            if 'screenshot_error' in locals():
                self.console.print(f"[yellow]![/yellow] Screenshot capture failed: {screenshot_error}")
            else:
                self.console.print(f"[green][OK][/green] Captured {len(screenshots)} screenshots")
        else:
            screenshots = []
            self.console.print("[yellow]![/yellow] No key moments found")
        
        # Generate final markdown
        self.console.print("[yellow]→[/yellow] Generating summary document...")
        summary_path = results_path / "summary.md"
        self.output_manager.generate_summary_markdown(
            video_name,
            summary,
            transcript,
            all_moments,
            screenshots,
            summary_path
        )
        self.console.print("[green][OK][/green] Summary document updated")
        
        return ProcessingResult(
            video_path=video_path,
            output_dir=results_path,
            success=True,
            transcript_path=transcript_path,
            summary_path=summary_path,
            screenshots=screenshots
        )
    
    def _create_output_directory(self, video_path: str, video_name: str) -> Path:
        """Create organized output directory for video.
        
        Args:
            video_path: Path to video file
            video_name: Name of the video
            
        Returns:
            Path to created directory
        """
        video_file = Path(video_path)
        video_dir = video_file.parent
        return self.output_manager.create_video_directory(video_name, video_dir)
