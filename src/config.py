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
        # Load .env file from current directory
        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(env_path)
        
        # Check for API key
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ConfigurationError(
                "DEEPSEEK_API_KEY not found in .env file. "
                "Please create a .env file with your DeepSeek API key. "
                "See .env.example for reference."
            )
        
        # Load YAML config
        config_file = Path(config_path)
        if not config_file.exists():
            raise ConfigurationError(
                f"Configuration file '{config_path}' not found. "
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
            config = cls(
                vosk_model_path=yaml_config['vosk']['model_path'],
                deepseek_api_key=api_key,
                output_base_dir=yaml_config['output']['base_dir'],
                audio_format=yaml_config.get('audio', {}).get('format', 'wav'),
                audio_sample_rate=yaml_config.get('audio', {}).get('sample_rate', 16000),
                audio_channels=yaml_config.get('audio', {}).get('channels', 1),
                screenshot_format=yaml_config.get('screenshots', {}).get('format', 'jpg'),
                screenshot_quality=yaml_config.get('screenshots', {}).get('quality', 95),
                keyword_triggers=yaml_config.get('keywords', {}).get('triggers', [])
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
            raise ConfigurationError(
                f"VOSK model directory not found: {self.vosk_model_path}. "
                "Please download a VOSK model and update the path in config.yaml"
            )
        
        # Validate output directory can be created
        output_dir = Path(self.output_base_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ConfigurationError(f"Cannot create output directory: {e}")
