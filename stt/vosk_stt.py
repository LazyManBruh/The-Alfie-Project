"""Speech-to-text using Vosk (offline, CPU-friendly).

Vosk's own endpointing (built into the Kaldi decoding graph, based on acoustic
content) decides when an utterance is over - `feed()` returns True at that
point. This is what actually drives end-of-utterance detection now; it's not
vulnerable to the mic gain/AGC issues that made a simple RMS threshold
unreliable on some hardware.
"""

import json
import os
import vosk
from vosk import Model, KaldiRecognizer
from loguru import logger

vosk.SetLogLevel(-1)  # silence Kaldi's very verbose stderr logging


class VoskSTT:
    def __init__(self, model_path: str, sample_rate: int = 16000):
        if not os.path.isdir(model_path):
            raise ValueError(f"Vosk model not found at {model_path}")
        self.sample_rate = sample_rate
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, sample_rate)
        logger.info(f"Loaded Vosk model from {model_path}")

    def feed(self, chunk: bytes) -> bool:
        """Feed one chunk of raw 16-bit PCM audio. Returns True if Vosk's own
        endpointing decided the utterance just ended - call pop_result() right after."""
        return self.recognizer.AcceptWaveform(chunk)

    def pop_result(self) -> str:
        """Call immediately after feed() returns True: get the completed utterance's
        text, and reset for the next one."""
        text = json.loads(self.recognizer.Result()).get("text", "").strip()
        self._reset()
        return text

    def finalize(self) -> str:
        """Force-end an in-progress utterance (e.g. on timeout) and reset for next time."""
        text = json.loads(self.recognizer.FinalResult()).get("text", "").strip()
        self._reset()
        return text

    def _reset(self):
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
