"""Configuration loading for Alfie Assistant"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from loguru import logger


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    device: Optional[int] = None


@dataclass
class WakeWordConfig:
    model_path: str = "hey_jarvis"
    sensitivity: float = 0.6
    patience: int = 3


@dataclass
class STTConfig:
    model_path: str = "/home/lazyman/alfie_models/vosk/vosk-model-small-en-us-0.15"


@dataclass
class LLMConfig:
    host: str = "http://localhost:11434"
    model: str = "qwen2.5:3b-instruct"
    temperature: float = 0.6


@dataclass
class TTSConfig:
    model_path: str = "/home/lazyman/alfie_models/piper/en_GB-alan-medium.onnx"
    speaker_id: int = 0
    length_scale: float = 1.05
    noise_scale: float = 0.55
    noise_w: float = 0.6


@dataclass
class SkillsConfig:
    enabled: List[str] = field(default_factory=lambda: [
        "time", "date", "weather", "web_search", "timer", "media_control",
        "calculator", "unit_conversion", "reminder", "system_control", "wikipedia",
        "briefing", "currency_conversion", "news", "network_check",
    ])


@dataclass
class Config:
    audio: AudioConfig
    wake_word: WakeWordConfig
    stt: STTConfig
    llm: LLMConfig
    tts: TTSConfig
    skills: SkillsConfig


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file, creating a default one on first run."""
    path = Path(config_path)
    if not path.exists():
        defaults = Config(
            audio=AudioConfig(),
            wake_word=WakeWordConfig(),
            stt=STTConfig(),
            llm=LLMConfig(),
            tts=TTSConfig(),
            skills=SkillsConfig(),
        )
        config_dict = {
            "audio": defaults.audio.__dict__,
            "wake_word": defaults.wake_word.__dict__,
            "stt": defaults.stt.__dict__,
            "llm": defaults.llm.__dict__,
            "tts": defaults.tts.__dict__,
            "skills": defaults.skills.__dict__,
        }
        with open(path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False)
        logger.info(f"Created default config at {path}")
    else:
        with open(path) as f:
            config_dict = yaml.safe_load(f)

    return Config(
        audio=AudioConfig(**config_dict.get("audio", {})),
        wake_word=WakeWordConfig(**config_dict.get("wake_word", {})),
        stt=STTConfig(**config_dict.get("stt", {})),
        llm=LLMConfig(**config_dict.get("llm", {})),
        tts=TTSConfig(**config_dict.get("tts", {})),
        skills=SkillsConfig(**config_dict.get("skills", {})),
    )
