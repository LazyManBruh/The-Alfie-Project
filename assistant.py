#!/usr/bin/env python3
"""
Alfie Assistant - Main entry point

State machine: listen for wake word -> record until silence -> transcribe ->
route through skills, falling back to the local LLM -> speak the response.
Runs synchronously since audio I/O and TTS/LLM calls are blocking anyway.
"""

import signal
import sys
import time
from pathlib import Path
from loguru import logger

from alfie_assistant.audio.capture import MicStream
from alfie_assistant.audio.playback import play_chime, play_wav_bytes
from alfie_assistant.wake_word.detector import WakeWordDetector
from alfie_assistant.stt.vosk_stt import VoskSTT
from alfie_assistant.llm.ollama_client import OllamaClient
from alfie_assistant.tts.piper_tts import PiperTTS
from alfie_assistant.skills import SkillManager
from alfie_assistant.config import load_config

MAX_UTTERANCE_DURATION = 10.0
FOLLOWUP_TIMEOUT = 6.0  # shorter cap when listening for a reply to Alfie's own question
MAX_FOLLOWUPS = 3  # safety valve in case a chatty response keeps ending in "?"
MAX_HISTORY_TURNS = 6  # user+assistant pairs kept for LLM context
HISTORY_EXPIRY_SECONDS = 300  # forget context after this long since the last exchange


class AlfieAssistant:
    def __init__(self, config):
        self.config = config
        self.running = False

        self.mic = MicStream(sample_rate=config.audio.sample_rate, device=config.audio.device)
        self.wake_word = WakeWordDetector(
            model_path=config.wake_word.model_path,
            sensitivity=config.wake_word.sensitivity,
            patience=config.wake_word.patience,
        )
        self.stt = VoskSTT(model_path=config.stt.model_path)
        self.llm = OllamaClient(
            host=config.llm.host,
            model=config.llm.model,
            temperature=config.llm.temperature,
        )
        self.tts = PiperTTS(
            model_path=config.tts.model_path,
            speaker_id=config.tts.speaker_id,
            length_scale=config.tts.length_scale,
            noise_scale=config.tts.noise_scale,
            noise_w=config.tts.noise_w,
        )
        self.skills = SkillManager(config.skills.enabled, context={"speak": self.speak})
        self.history = []
        self.last_interaction_at = 0.0

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info("Received signal, shutting down...")
        self.running = False

    def speak(self, text: str):
        logger.info(f"Alfie: {text}")
        t0 = time.time()
        try:
            wav = self.tts.synthesize(text)
            t1 = time.time()
            play_wav_bytes(wav)
            t2 = time.time()
            logger.info(f"[timing] tts_synthesize={t1-t0:.2f}s playback={t2-t1:.2f}s")
        finally:
            # No acoustic echo cancellation here, so drop whatever the mic
            # picked up of Alfie's own voice before listening again.
            self.mic.drain()

    def _record_utterance(self, max_duration: float = MAX_UTTERANCE_DURATION) -> str:
        """Record until Vosk's own endpointing decides the utterance is over.

        This replaced a manual RMS-based silence timer that turned out to be
        unreliable on this mic: measuring the ambient noise floor showed it sitting
        well into normal-speech RMS territory (likely AGC-related), which made any
        volume threshold useless for telling speech from silence - every recording
        was hitting the hard timeout instead of ending naturally. Vosk's endpointing
        is driven by acoustic content, not raw amplitude, so it doesn't have that
        problem; max_duration below is now just a worst-case backstop.
        """
        start = time.time()
        chunks_seen = 0

        while time.time() - start < max_duration:
            chunk = self.mic.read_chunk(timeout=1.0)
            if chunk is None:
                logger.warning("[timing] mic.read_chunk timed out with no audio")
                break
            chunks_seen += 1

            if self.stt.feed(chunk):
                logger.info(
                    f"[timing] record: {chunks_seen} chunks, "
                    f"vosk endpoint reached at {time.time()-start:.2f}s"
                )
                return self.stt.pop_result()

        logger.info(
            f"[timing] record: {chunks_seen} chunks, hit max duration ({time.time()-start:.2f}s)"
        )
        return self.stt.finalize()

    def _converse(self):
        """Handle one command, and keep listening without a wake word for as long as
        Alfie's own reply ends in a question - e.g. "Would you like me to set a timer?"
        followed directly by your answer, no "Hey Jarvis" needed. Caps at
        MAX_FOLLOWUPS so a chatty response that always ends in "?" can't hold the
        mic open forever.

        self.history persists across separate wake-word triggers (not just within
        one follow-up chain), so "Hey Jarvis, who is Marie Curie" followed a few
        seconds later by a fresh "Hey Jarvis, what did she discover" still resolves
        "she" correctly. It's cleared if more than HISTORY_EXPIRY_SECONDS has passed
        since the last exchange, so it doesn't drag stale context into an unrelated
        conversation much later. Passed to the LLM regardless of whether each turn's
        response came from a skill or the LLM itself, so the model still knows what
        was just said even on turns it wasn't asked to answer.
        """
        if self.history and time.time() - self.last_interaction_at > HISTORY_EXPIRY_SECONDS:
            logger.info(f"[history] >{HISTORY_EXPIRY_SECONDS}s since the last exchange, starting fresh")
            self.history = []

        awaiting_followup = False
        followups_left = MAX_FOLLOWUPS

        while True:
            max_duration = FOLLOWUP_TIMEOUT if awaiting_followup else MAX_UTTERANCE_DURATION
            text = self._record_utterance(max_duration)
            if not text:
                logger.info("No follow-up heard" if awaiting_followup else "No speech recognized")
                return

            logger.info(f"Heard: {text}")
            response = self.skills.route(text)
            if response is None:
                response = self.llm.chat(self.history + [{"role": "user", "content": text}])
            self.speak(response)

            self.history.append({"role": "user", "content": text})
            self.history.append({"role": "assistant", "content": response})
            self.history = self.history[-(MAX_HISTORY_TURNS * 2):]
            self.last_interaction_at = time.time()

            if response.strip().endswith("?") and followups_left > 0:
                followups_left -= 1
                logger.info("Alfie asked a question - listening for your reply, no wake word needed")
                play_chime()
                self.mic.drain()
                awaiting_followup = True
            else:
                return

    def run(self):
        self.running = True
        self.mic.start()
        logger.info(f"Alfie is listening (skills: {self.skills.list_skills()})")

        try:
            while self.running:
                chunk = self.mic.read_chunk(timeout=1.0)
                if chunk is None:
                    continue

                if self.wake_word.process_chunk(chunk):
                    self.mic.drain()
                    play_chime()
                    self.mic.drain()
                    self._converse()
        finally:
            self.mic.stop()
            self.llm.close()
            logger.info("Alfie Assistant stopped")


def main():
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    default_config_path = Path(__file__).parent / "config.yaml"
    config = load_config(str(default_config_path))
    assistant = AlfieAssistant(config)
    assistant.run()


if __name__ == "__main__":
    main()
