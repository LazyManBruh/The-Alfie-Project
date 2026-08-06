"""Text-to-speech using Piper (offline, CPU-friendly).

Uses Piper's in-process Python API rather than shelling out to the `piper`
CLI. The CLI reloads the ONNX model from disk on every single call (~1s of
pure overhead per utterance, and every turn makes two calls: "Yes?" plus the
actual answer); loading the voice once here and reusing it drops that to
roughly 50-100ms per synthesis.
"""

import io
import wave
from piper import PiperVoice
from piper.config import SynthesisConfig
from loguru import logger

from alfie_assistant.audio.playback import play_wav_bytes


class PiperTTS:
    def __init__(self, model_path: str, config_path: str | None = None, speaker_id: int = 0,
                 length_scale: float = 1.0, noise_scale: float = 0.667, noise_w: float = 0.8):
        self.voice = PiperVoice.load(model_path, config_path=config_path or f"{model_path}.json")
        self.syn_config = SynthesisConfig(
            speaker_id=speaker_id if self.voice.config.num_speakers > 1 else None,
            length_scale=length_scale,
            noise_scale=noise_scale,
            noise_w_scale=noise_w,
        )
        logger.info(f"Loaded Piper voice from {model_path}")

    def synthesize(self, text: str) -> bytes:
        """Synthesize speech from text and return WAV audio bytes."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            self.voice.synthesize_wav(text, wav_file, syn_config=self.syn_config)
        return buf.getvalue()

    def speak(self, text: str):
        """Synthesize and immediately play the audio."""
        play_wav_bytes(self.synthesize(text))
