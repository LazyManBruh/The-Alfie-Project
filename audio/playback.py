"""Audio playback for Alfie Assistant."""

import io
import subprocess
import tempfile
import wave
import os
import numpy as np
from loguru import logger


def play_wav_bytes(wav_data: bytes):
    """Play WAV audio data through the default output device."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_data)
        temp_path = f.name
    try:
        player = "paplay" if _has("paplay") else "aplay"
        result = subprocess.run([player, temp_path], capture_output=True)
        if result.returncode != 0:
            logger.error(f"{player} failed: {result.stderr.decode(errors='replace')}")
    finally:
        os.unlink(temp_path)


def make_chime_wav(freqs=(880, 1320), tone_ms=70, sample_rate=22050, volume=0.3) -> bytes:
    """A short two-tone acknowledgment beep, synthesized directly (no TTS involved).

    Used instead of a spoken "Yes, sir?" - speaking that phrase and waiting for it to
    finish playing took ~1-1.5s per turn for no functional reason. A ~140ms chime gives
    the same "I heard you, go ahead" feedback almost instantly, the same way Alexa/Google
    Home do it.
    """
    tones = []
    for freq in freqs:
        t = np.linspace(0, tone_ms / 1000, int(sample_rate * tone_ms / 1000), endpoint=False)
        tones.append((np.sin(2 * np.pi * freq * t) * volume * 32767).astype(np.int16))
    audio = np.concatenate(tones)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio.tobytes())
    return buf.getvalue()


def play_chime():
    play_wav_bytes(make_chime_wav())


def _has(binary: str) -> bool:
    return subprocess.run(["which", binary], capture_output=True).returncode == 0
