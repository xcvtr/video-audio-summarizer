"""Configuration management for video summarizer."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import yaml
from dotenv import load_dotenv
import os


class ConfigurationError(Exception):
    """Configuration-related errors."""
    pass


@dataclass
class Config:
    """Application configuration."""

    vosk_model_path: str
    deepseek_api_key: str
    output_base_dir: str
    audio_format: str = "wav"
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    screenshot_format: str = "jpg"
    screenshot_quality: int = 95
    keyword_triggers: List[str] = field(default_factory=list)
    # Новые поля для серверного режима
    vosk_mode: str = "local"  # "local", "server" или "whisper"
    vosk_server_url: str = "http://127.0.0.1:8000"
    vosk_server_timeout: int = 300
    # faster-whisper (GPU) режим
    whisper_model_size: str = "small"
    whisper_device: str = "auto"  # "auto", "cuda" или "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: Optional[str] = None  # None = автоопределение
    # AI model (по умолчанию, если не задан в .env)
    ai_model: str = "nex-agi/nex-n2.5-mini:free"
    # Base URL OpenAI-совместимого API (обязателен, задаётся в .env)
    ai_base_url: str = ""
    
    def __post_init__(self):
        """Post-initialization to resolve relative paths."""
        # Determine project root (where main.py is located)
        self.project_root = Path(__file__).parent.parent
        
        # Resolve relative paths
        self.vosk_model_path = self._resolve_path(self.vosk_model_path)
        self.output_base_dir = self._resolve_path(self.output_base_dir)
    
    def _resolve_path(self, path_str: str) -> str:
        """Resolve relative path relative to project root.
        
        Args:
            path_str: Path string (can be absolute or relative)
            
        Returns:
            Resolved absolute path
        """
        path = Path(path_str)
        
        # If path is absolute, return as is
        if path.is_absolute():
            return str(path)
        
        # Try relative to project root
        project_relative = self.project_root / path
        if project_relative.exists():
            return str(project_relative)
        
        # Return original path (will fail validation if doesn't exist)
        return str(path)
    
    @classmethod
    def load(cls, config_path: str = "config.yaml") -> "Config":
        """Load configuration from YAML and .env files.

        Args:
            config_path: Path to config.yaml file

        Returns:
            Config instance

        Raises:
            ConfigurationError: If configuration files are missing or invalid
        """
        # Try to find config.yaml in multiple locations
        config_file = Path(config_path)
        
        # If config_path is not absolute, try multiple locations
        if not config_file.is_absolute():
            # 1. First try: current working directory
            if not config_file.exists():
                # 2. Second try: project root (where main.py is located)
                project_root = Path(__file__).parent.parent
                project_config = project_root / config_path
                if project_config.exists():
                    config_file = project_config
                    print(f"Found config.yaml in project root: {config_file}")
        
        # Load .env file - try multiple locations
        # 1. First try: same directory as config.yaml
        config_dir = config_file.parent
        env_path = config_dir / ".env"

        # 2. Second try: current working directory
        if not env_path.exists():
            env_path = Path(".env")

        # 3. Third try: project root (where main.py is located)
        if not env_path.exists():
            # Try to find project root by looking for main.py
            project_root = Path(__file__).parent.parent
            env_path = project_root / ".env"

        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded .env from: {env_path}")

        # Check for API key
        api_key = (
            os.getenv("API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
        )
        if not api_key:
            raise ConfigurationError(
                "API_KEY not found in .env file. "
                "Please create a .env file with your API key. "
                "See .env.example for reference."
            )
        
        # DEBUG: Print API key (first 10 chars)
        print(f"[DEBUG] API key loaded: {api_key[:10]}...")

        # Load YAML config
        if not config_file.exists():
            raise ConfigurationError(
                f"Configuration file '{config_path}' not found. "
                "Tried locations: current directory, project root. "
                "Expected parameters: vosk.model_path, audio.format, "
                "audio.sample_rate, audio.channels, screenshots.format, "
                "screenshots.quality, keywords.triggers, output.base_dir"
            )
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing config.yaml: {e}")
        
        # Extract configuration values
        try:
            vosk_config = yaml_config.get('vosk', {})
            
            config = cls(
                vosk_model_path=vosk_config.get('model_path', './vosk/model-ru-large'),
                deepseek_api_key=api_key,
                output_base_dir=yaml_config['output']['base_dir'],
                audio_format=yaml_config.get('audio', {}).get('format', 'wav'),
                audio_sample_rate=yaml_config.get('audio', {}).get('sample_rate', 16000),
                audio_channels=yaml_config.get('audio', {}).get('channels', 1),
                screenshot_format=yaml_config.get('screenshots', {}).get('format', 'jpg'),
                screenshot_quality=yaml_config.get('screenshots', {}).get('quality', 95),
                keyword_triggers=yaml_config.get('keywords', {}).get('triggers', []),
                # Новые настройки
                vosk_mode=vosk_config.get('mode', 'local'),
                vosk_server_url=vosk_config.get('server', {}).get('url', 'http://127.0.0.1:8000'),
                vosk_server_timeout=vosk_config.get('server', {}).get('timeout', 300),
                # faster-whisper настройки
                whisper_model_size=vosk_config.get('whisper', {}).get('model_size', 'small'),
                whisper_device=vosk_config.get('whisper', {}).get('device', 'auto'),
                whisper_compute_type=vosk_config.get('whisper', {}).get('compute_type', 'int8'),
                whisper_language=vosk_config.get('whisper', {}).get('language') or None,
                # AI model and API base URL (from .env)
                ai_model=os.getenv('API_MODEL') or os.getenv('AI_MODEL', 'nex-agi/nex-n2.5-mini:free'),
                # Поддерживаем оба написания: API_ENDPONT (в .env) и API_ENDPOINT / AI_BASE_URL
                ai_base_url=(
                    os.getenv('API_ENDPONT')
                    or os.getenv('API_ENDPOINT')
                    or os.getenv('AI_BASE_URL', '')
                )
            )
        except KeyError as e:
            raise ConfigurationError(f"Missing required configuration key: {e}")
        
        # Validate configuration
        config.validate()
        
        return config
    
    def validate(self) -> None:
        """Validate configuration parameters.
        
        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Validate audio parameters first (before checking files)
        if self.audio_sample_rate <= 0:
            raise ConfigurationError("audio_sample_rate must be positive")
        
        if self.audio_channels not in [1, 2]:
            raise ConfigurationError("audio_channels must be 1 (mono) or 2 (stereo)")
        
        # Validate screenshot parameters
        if not (0 < self.screenshot_quality <= 100):
            raise ConfigurationError("screenshot_quality must be between 1 and 100")
        
        # Validate VOSK model path
        model_path = Path(self.vosk_model_path)
        if not model_path.exists():
            # Try to provide helpful error message
            original_path = Path("./vosk/model-ru-large")
            project_relative = self.project_root / original_path
            
            error_msg = f"VOSK model directory not found: {self.vosk_model_path}\n"
            error_msg += f"  Original path in config.yaml: {original_path}\n"
            error_msg += f"  Resolved relative to project: {project_relative}\n"
            error_msg += "  Please download a VOSK model and update the path in config.yaml"
            
            raise ConfigurationError(error_msg)
        
        # Validate output directory can be created
        output_dir = Path(self.output_base_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ConfigurationError(f"Cannot create output directory: {e}")
