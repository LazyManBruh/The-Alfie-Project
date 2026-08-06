#!/usr/bin/env python3
"""
Trains a custom "Hey Alfie" wake word model for openWakeWord.

Combines:
1. Real recordings from tools/record_wake_word_samples.py (~/alfie_wakeword_training/)
2. Synthetic positive/negative clips generated here via Piper across many
   different speakers (for diversity beyond what's practical to record by hand)

...into a small PyTorch classifier trained on top of openWakeWord's existing,
already-trained embedding model - the same one every pretrained model
(hey_jarvis, alexa, etc.) sits on top of. This deliberately avoids the
official openWakeWord training pipeline's dependency stack (TensorFlow
2.8.1 doesn't even install on this Python version) and its tens of GB of
background-noise/feature datasets, at the cost of a smaller, less rigorously
validated training set than that pipeline would use.

Run: python tools/train_wake_word.py
Output: ~/alfie_models/wake_word/hey_alfie_v1.onnx
"""

import io
import sys
import wave
from pathlib import Path

import numpy as np
import torch
from torch import nn
from piper import PiperVoice
from piper.config import SynthesisConfig
from openwakeword.utils import AudioFeatures

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

SAMPLE_RATE = 16000
CLIP_SECONDS = 2.0
CLIP_SAMPLES = int(SAMPLE_RATE * CLIP_SECONDS)

REAL_DATA_ROOT = Path.home() / "alfie_wakeword_training"
PIPER_MODELS_DIR = Path.home() / "alfie_models" / "piper"
OUTPUT_DIR = Path.home() / "alfie_models" / "wake_word"
OUTPUT_MODEL = OUTPUT_DIR / "hey_alfie_v1.onnx"

WAKE_PHRASES = ["Hey Alfie", "Hey, Alfie."]

NEGATIVE_PHRASES = [
    # hard negatives - phonetically close to the wake word
    "Hey Alfredo", "Hey Alfonso", "Hey Ralphie", "Hey Algae", "A Alfie",
    "Hey Alpha", "Hey Elfie", "Okay Alfie", "Hey out fee",
    # other assistants - should never cross-trigger
    "Hey Jarvis", "Hey Siri", "Okay Google", "Alexa",
    # things a user would actually say to this assistant
    "What time is it", "What's the weather like today", "Set a timer for five minutes",
    "Play some music", "Pause the music", "How much disk space do I have",
    "What's my battery level", "Remind me to buy milk", "What is fifteen times twenty three",
    "Convert ten miles to kilometers", "Who is Marie Curie", "Tell me a joke",
    "Good morning", "How are you today", "Take a screenshot", "Lock the screen",
    "Turn up the volume", "What's my IP address", "Search for the Eiffel Tower",
    # general conversational filler
    "I think I'll go for a walk later", "Can you believe the weather we've been having",
    "Let's grab some coffee this afternoon", "The meeting got moved to three o'clock",
    "I need to pick up groceries after work", "Did you watch the game last night",
    "This coffee is really good", "I'm going to finish this book tonight",
    "The traffic was terrible this morning", "We should plan a trip soon",
]


def load_voice(name):
    return PiperVoice.load(str(PIPER_MODELS_DIR / f"{name}.onnx"))


def fit_clip(samples):
    """Fit audio into exactly CLIP_SAMPLES, center-padding/cropping - not
    forcing one fixed alignment lets the model see the phrase in a variety
    of positions across the training set, which helps it generalize rather
    than overfitting to one exact position."""
    if len(samples) >= CLIP_SAMPLES:
        start = (len(samples) - CLIP_SAMPLES) // 2
        return samples[start:start + CLIP_SAMPLES]
    pad_total = CLIP_SAMPLES - len(samples)
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left
    return np.concatenate([
        np.zeros(pad_left, dtype=np.int16), samples, np.zeros(pad_right, dtype=np.int16)
    ])


def synth_clip(voice, text, num_speakers, rng):
    speaker_id = rng.integers(num_speakers) if num_speakers > 1 else None
    syn_config = SynthesisConfig(
        speaker_id=speaker_id,
        length_scale=rng.uniform(0.85, 1.15),
        noise_scale=rng.uniform(0.5, 0.8),
        noise_w_scale=rng.uniform(0.6, 0.9),
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        voice.synthesize_wav(text, wf, syn_config=syn_config)
    buf.seek(0)
    with wave.open(buf, "rb") as wf:
        sr = wf.getframerate()
        pcm = wf.readframes(wf.getnframes())
    samples = np.frombuffer(pcm, dtype=np.int16)
    if sr != SAMPLE_RATE:
        target_len = max(1, int(len(samples) / sr * SAMPLE_RATE))
        samples = np.interp(
            np.linspace(0, len(samples), target_len, endpoint=False),
            np.arange(len(samples)), samples
        ).astype(np.int16)
    return fit_clip(samples)


def load_real_clips(subdir):
    directory = REAL_DATA_ROOT / subdir
    clips = []
    if not directory.exists():
        return clips
    for wav_path in sorted(directory.glob("*.wav")):
        with wave.open(str(wav_path), "rb") as wf:
            pcm = wf.readframes(wf.getnframes())
        samples = np.frombuffer(pcm, dtype=np.int16)
        clips.append(fit_clip(samples))
    return clips


def generate_synthetic(phrases, per_phrase, voices_and_counts, rng):
    clips = []
    for text in phrases:
        for voice, num_speakers in voices_and_counts:
            for _ in range(per_phrase):
                clips.append(synth_clip(voice, text, num_speakers, rng))
    return clips


class WakeWordClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(16 * 96, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x)


def train(embeddings, labels, epochs=200, patience=15, seed=42):
    rng = np.random.RandomState(seed)
    indices = np.arange(len(embeddings))
    rng.shuffle(indices)
    split = int(len(indices) * 0.85)
    train_idx, val_idx = indices[:split], indices[split:]

    X_train = torch.tensor(embeddings[train_idx], dtype=torch.float32)
    y_train = torch.tensor(labels[train_idx], dtype=torch.float32).unsqueeze(1)
    X_val = torch.tensor(embeddings[val_idx], dtype=torch.float32)
    y_val = torch.tensor(labels[val_idx], dtype=torch.float32).unsqueeze(1)

    print(f"\nTraining on {len(X_train)} examples, validating on {len(X_val)}...")

    model = WakeWordClassifier()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCELoss()

    best_val_loss = float("inf")
    best_state = None
    patience_counter = 0

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        pred = model(X_train)
        loss = loss_fn(pred, y_train)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_pred = model(X_val)
            val_loss = loss_fn(val_pred, y_val).item()
            val_acc = ((val_pred > 0.5).float() == y_val).float().mean().item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        if epoch % 20 == 0:
            print(f"  epoch {epoch}: train_loss={loss.item():.4f} val_loss={val_loss:.4f} val_acc={val_acc:.3f}")

        if patience_counter >= patience:
            print(f"  early stopping at epoch {epoch}")
            break

    model.load_state_dict(best_state)
    model.eval()

    with torch.no_grad():
        final_pred = model(X_val)
        pos_mask = y_val.squeeze(1) == 1
        neg_mask = y_val.squeeze(1) == 0
        recall = (final_pred[pos_mask] > 0.5).float().mean().item() if pos_mask.sum() > 0 else float("nan")
        fp_rate = (final_pred[neg_mask] > 0.5).float().mean().item() if neg_mask.sum() > 0 else float("nan")
        overall_acc = ((final_pred > 0.5).float() == y_val).float().mean().item()

    print(f"\nFinal validation accuracy: {overall_acc:.3f}")
    print(f"Recall on positive examples: {recall:.3f}  (higher = fewer missed wake words)")
    print(f"False positive rate on negatives: {fp_rate:.3f}  (lower = fewer false triggers)")

    return model


def export(model, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.randn(1, 16, 96)
    torch.onnx.export(
        model, dummy, str(output_path),
        input_names=["input"], output_names=["output"], opset_version=17,
    )
    print(f"\nSaved to {output_path}")


def main(synthetic_only=False, per_phrase_positive=60, per_phrase_negative=3):
    rng = np.random.default_rng(42)

    print("Loading Piper voices for synthetic data generation...")
    lessac = load_voice("en_US-lessac-medium")
    alan = load_voice("en_GB-alan-medium")
    libritts = load_voice("en_US-libritts_r-medium")
    voices = [(lessac, 1), (alan, 1), (libritts, 904)]

    print("Generating synthetic positive clips...")
    synthetic_pos = generate_synthetic(WAKE_PHRASES, per_phrase_positive, voices, rng)
    print(f"  {len(synthetic_pos)} synthetic positive clips")

    print("Generating synthetic negative clips...")
    synthetic_neg = generate_synthetic(NEGATIVE_PHRASES, per_phrase_negative, voices, rng)
    print(f"  {len(synthetic_neg)} synthetic negative clips")

    real_pos, real_neg_speech, real_neg_ambient = [], [], []
    if not synthetic_only:
        print("Loading real recorded clips...")
        real_pos = load_real_clips("positive")
        real_neg_speech = load_real_clips("negative_speech")
        real_neg_ambient = load_real_clips("negative_ambient")
        print(f"  {len(real_pos)} real positive, {len(real_neg_speech)} real negative speech, "
              f"{len(real_neg_ambient)} real ambient")
        if len(real_pos) < 20:
            print("WARNING: fewer than 20 real positive samples - run "
                  "tools/record_wake_word_samples.py for better accuracy.")

    positive_clips = synthetic_pos + real_pos
    negative_clips = synthetic_neg + real_neg_speech + real_neg_ambient
    print(f"\nTotal: {len(positive_clips)} positive, {len(negative_clips)} negative")

    print("\nExtracting embeddings (openWakeWord's melspectrogram + embedding model)...")
    af = AudioFeatures()
    all_clips = np.array(positive_clips + negative_clips, dtype=np.int16)
    labels = np.array([1.0] * len(positive_clips) + [0.0] * len(negative_clips), dtype=np.float32)
    embeddings = af.embed_clips(all_clips, batch_size=128)
    print(f"  embeddings shape: {embeddings.shape}")

    model = train(embeddings, labels)
    export(model, OUTPUT_MODEL)


if __name__ == "__main__":
    synthetic_only = "--synthetic-only" in sys.argv
    main(synthetic_only=synthetic_only)
