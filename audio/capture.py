"""Continuous microphone capture for Alfie Assistant.

Runs a single sounddevice input stream for the whole lifetime of the
assistant and pushes fixed-size 16-bit PCM chunks onto a queue. Both the
wake-word detector and the post-wake recording phase pull from this same
queue, so there is exactly one audio stream open at a time.
"""

import queue
import numpy as np
import sounddevice as sd
from loguru import logger

# openWakeWord expects multiples of 80ms frames at 16kHz (1280 samples)
CHUNK_SAMPLES = 1280


class MicStream:
    def __init__(self, sample_rate: int = 16000, device=None, chunk_samples: int = CHUNK_SAMPLES):
        self.sample_rate = sample_rate
        self.device = device
        self.chunk_samples = chunk_samples
        self._queue = queue.Queue()
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"Audio stream status: {status}")
        self._queue.put(bytes(indata))

    def start(self):
        if self._stream is not None:
            return
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            device=self.device,
            channels=1,
            dtype="int16",
            blocksize=self.chunk_samples,
            callback=self._callback,
        )
        self._stream.start()
        logger.debug("Microphone stream started")

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._queue.mutex:
            self._queue.queue.clear()
        logger.debug("Microphone stream stopped")

    def read_chunk(self, timeout: float = 1.0):
        """Block for up to `timeout` seconds for the next audio chunk (raw int16 bytes)."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self):
        """Discard any buffered audio (e.g. the assistant's own TTS output picked up
        by the mic, since this setup has no acoustic echo cancellation)."""
        with self._queue.mutex:
            self._queue.queue.clear()

    @staticmethod
    def rms(chunk: bytes) -> float:
        """Root-mean-square energy of a chunk, normalized to roughly [0, 1]."""
        samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(samples))))
