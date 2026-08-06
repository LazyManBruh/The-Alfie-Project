"""Wake word detection using openWakeWord (ONNX, actively maintained).

Mycroft Precise (the original choice here) has been unmaintained since 2023
and its model file for this project was never actually populated (0 bytes).
openWakeWord ships a pretrained "hey_jarvis" model inside the package itself,
so no network download is required to get a working wake word today.
"""

import os
import numpy as np
from loguru import logger
from openwakeword.model import Model
import openwakeword


def _resolve_model_path(name_or_path: str) -> str:
    """Accept either a direct path to a .onnx model or the name of a model
    bundled with the installed openwakeword package (e.g. 'hey_jarvis')."""
    if os.path.isfile(name_or_path):
        return name_or_path

    pkg_dir = os.path.dirname(openwakeword.__file__)
    candidates = [
        os.path.join(pkg_dir, "resources", "models", f"{name_or_path}.onnx"),
        os.path.join(pkg_dir, "resources", "models", f"{name_or_path}_v0.1.onnx"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(
        f"Could not resolve wake word model '{name_or_path}'. "
        "Pass a path to a .onnx file, or a bundled name such as 'hey_jarvis', "
        "'hey_mycroft', 'hey_marvin', or 'alexa'."
    )


class WakeWordDetector:
    def __init__(self, model_path: str = "hey_jarvis", sensitivity: float = 0.6, patience: int = 3):
        """
        :param sensitivity: per-frame score threshold (0-1). Raised from openWakeWord's
            example default of 0.5 because a single noisy 80ms frame clearing 0.5 was
            triggering on ambient speech/noise that wasn't the wake word.
        :param patience: number of consecutive frames that must clear the threshold
            before firing. Requiring ~240ms of sustained activation (vs. a single 80ms
            blip) is what actually kills false positives - a stray noise spike rarely
            stays above threshold for 3 frames in a row, but saying "hey jarvis" does.
        """
        resolved = _resolve_model_path(model_path)
        self.model_name = os.path.splitext(os.path.basename(resolved))[0]
        self.threshold = sensitivity
        self.patience = patience
        self._consecutive = 0
        self.model = Model(wakeword_model_paths=[resolved])
        logger.info(
            f"Loaded wake word model '{self.model_name}' "
            f"(threshold={self.threshold}, patience={self.patience})"
        )

    def process_chunk(self, chunk: bytes) -> bool:
        """Feed one ~80ms int16 PCM chunk. Returns True if the wake word just triggered."""
        samples = np.frombuffer(chunk, dtype=np.int16)
        scores = self.model.predict(samples)
        score = scores.get(self.model_name, 0.0)

        if score >= self.threshold:
            self._consecutive += 1
        else:
            self._consecutive = 0

        if self._consecutive >= self.patience:
            logger.info(f"Wake word triggered (score={score:.2f})")
            self._consecutive = 0
            self.model.reset()
            return True
        return False

    def reset(self):
        self._consecutive = 0
        self.model.reset()
