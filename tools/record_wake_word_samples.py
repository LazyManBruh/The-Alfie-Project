#!/usr/bin/env python3
"""
Interactive recording tool for collecting real training data for the custom
"Hey Alfie" wake word model.

Run this yourself (it needs your actual voice) - I can't do this part:

    python tools/record_wake_word_samples.py

Records three sets of 2.0-second, 16kHz mono WAV clips into
~/alfie_wakeword_training/:

1. positive/         - you saying "Hey Alfie"
2. negative_speech/  - you talking normally (anything EXCEPT the wake word)
3. negative_ambient/ - background noise with nobody talking

2.0 seconds was picked deliberately: openWakeWord's embedding pipeline turns
exactly a 2.0s clip into exactly 16 embedding frames, which is the input
shape the classifier (trained by tools/train_wake_word.py) expects - so
every clip is just recorded directly at that length, no padding/trimming
needed to line things up afterward.

You can re-run this script to add more samples later; it won't overwrite
what's already there.
"""

import sys
import time
import wave
from pathlib import Path
import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from alfie_assistant.audio.playback import play_chime

SAMPLE_RATE = 16000
CLIP_SECONDS = 2.0
CLIP_SAMPLES = int(SAMPLE_RATE * CLIP_SECONDS)
OUTPUT_ROOT = Path.home() / "alfie_wakeword_training"


def record_clip() -> np.ndarray:
    audio = sd.rec(CLIP_SAMPLES, samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    return audio.flatten()


def save_clip(audio: np.ndarray, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())


def record_set(subdir: str, count: int, prefix: str, instructions: str, cue_each_time: bool):
    out_dir = OUTPUT_ROOT / subdir
    existing = len(list(out_dir.glob("*.wav"))) if out_dir.exists() else 0

    print(f"\n=== {instructions} ===")
    print(f"Recording {count} clips of {CLIP_SECONDS}s each.")
    input("Press Enter when ready...")

    if not cue_each_time:
        play_chime()

    for i in range(count):
        if cue_each_time:
            time.sleep(0.6)
            play_chime()
        audio = record_clip()
        save_clip(audio, out_dir / f"{prefix}_{existing + i:04d}.wav")
        print(f"  [{i + 1}/{count}] saved")

    print(f"Done. {count} clips saved to {out_dir}")


def main():
    print("Alfie wake word training data recorder")
    print(f"Saving to {OUTPUT_ROOT}\n")
    print("Three parts: saying the wake word, talking normally, and silence.")
    print("You can Ctrl+C between parts and re-run later to pick up where you left off")
    print("(just note how many of each you've already got in the folder).")

    record_set(
        "positive", 80, "positive",
        "Part 1: say 'Hey Alfie' after each beep - vary tone/pace/distance a bit",
        cue_each_time=True,
    )
    record_set(
        "negative_speech", 45, "neg_speech",
        "Part 2: talk normally for a while - anything except 'Hey Alfie' "
        "(read something aloud, describe your day, count numbers)",
        cue_each_time=False,
    )
    record_set(
        "negative_ambient", 30, "neg_ambient",
        "Part 3: stay quiet - this captures your room/mic's normal background noise",
        cue_each_time=False,
    )

    print("\nAll done! Run tools/train_wake_word.py next to train the model.")


if __name__ == "__main__":
    main()
