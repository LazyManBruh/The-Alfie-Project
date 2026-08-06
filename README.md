# Alfie Assistant

**When life gives you lemons, make AI.**

This project is simple to understand: we're trying to make a JARVIS AI type
of assistant. That's all there is to it. For now, the AI part is in the
making, but hopefully in the future we'll try to give Alfie a body to live
in (if he tries to kill us, we are doomed).

A personal voice assistant inspired by JARVIS. Fully local: wake word (openWakeWord),
speech-to-text (Vosk), a local LLM via Ollama, and text-to-speech (Piper).

## Features

- Wake-word detection ("Hey Jarvis" by default — see Wake Word below)
- Offline speech-to-text using Vosk
- Local language model via Ollama
- Offline text-to-speech using Piper
- A small skill system that handles simple commands (time, date, weather,
  timers, media control, web search) before falling back to the LLM
- Privacy-first: only the weather and web search skills make external requests

## Setup

1. Activate the existing virtualenv and install dependencies:
   ```bash
   source /home/lazyman/alfie-env/bin/activate
   pip install -r requirements.txt
   ```
2. Make sure Ollama is running with a pulled model (`ollama pull qwen2.5:3b-instruct`).
   A small model is used by default to keep responses fast on this machine — see
   "Why a small model?" below before switching to something bigger.
3. Run it:
   ```bash
   python -m alfie_assistant
   ```
   A `config.yaml` is generated on first run in the current directory; edit it to
   change model paths, sensitivity, or which skills are enabled.

   In normal use, Alfie runs as a background service instead (see below) -
   run it directly like this only for debugging, and stop the service first
   (`systemctl --user stop alfie`) so the two don't fight over the microphone.

## Running as a background service

Alfie runs as a systemd **user** service (`~/.config/systemd/user/alfie.service`,
tracked here as `systemd/alfie.service`), not a system-wide one - it needs the
logged-in user's PipeWire/WirePlumber audio session, which a system service
wouldn't have direct access to without extra plumbing. It's already installed
and enabled to start automatically whenever you log in, and set to auto-restart
(`Restart=on-failure`, 5s delay) if it ever crashes - both were verified by
actually killing the process and watching it come back.

`systemd/alfie.service` has this exact machine's absolute paths baked in
(`/home/lazyman/...`) - on another machine, copy it to
`~/.config/systemd/user/`, fix the paths, then `systemctl --user daemon-reload`.

```bash
systemctl --user status alfie          # is it running?
journalctl --user -u alfie -f          # live logs (what it heard, timing, errors)
systemctl --user restart alfie         # after editing config.yaml or any skill
systemctl --user stop alfie            # e.g. before running it manually to debug
systemctl --user disable --now alfie   # turn the auto-start off entirely
```

Note: it currently starts on login, not before login (`loginctl show-user
lazyman` shows `Linger=no`). It could be made to survive a full logout too
via `loginctl enable-linger lazyman`, but that wasn't turned on here since
it's untested whether the audio session would actually still be reachable
without an active login on this setup.

## Usage

Say the wake word, wait for Alfie to say "Yes?", then speak your command:
- "Hey Jarvis, what time is it?"
- "Hey Jarvis, set a timer for 5 minutes."
- "Hey Jarvis, what's the weather in Paris?"
- Anything else falls through to the local LLM for open-ended chat.

## Wake Word

Currently set to a custom-trained "Hey Alfie" model
(`~/alfie_models/wake_word/hey_alfie_v1.onnx`). openWakeWord also ships
several pretrained models inside the package itself (no download needed):
`hey_jarvis`, `hey_mycroft`, `hey_marvin`, `alexa` - set `wake_word.model_path`
in `config.yaml` to any of these names to switch back, or to a path to
another custom `.onnx` model.

### Training a custom wake word

The official openWakeWord training pipeline needs `tensorflow-cpu==2.8.1`
(no wheel for this machine's Python) plus tens of GB of background-noise/
feature datasets - not practical here. Instead, `tools/train_wake_word.py`
trains a small PyTorch classifier directly on top of openWakeWord's existing,
already-trained embedding model (the same one every pretrained model sits on
top of), combining:

- Real recordings of you saying the phrase, via `tools/record_wake_word_samples.py`
  (needs your actual voice, and running it stops the live service first so
  they don't fight over the mic)
- Synthetic clips generated with Piper across ~900 different voices, for
  volume/diversity beyond what's practical to record by hand

```bash
systemctl --user stop alfie
python tools/record_wake_word_samples.py   # ~5-8 minutes, needs your voice
python tools/train_wake_word.py            # a minute or two on this CPU
systemctl --user start alfie
```

Update `wake_word.model_path` in `config.yaml` to the printed output path
and restart the service.

Known trade-off: the current model scores 99% validation accuracy and a 0.9%
false-positive rate on held-out data from the same recording session, but a
follow-up sanity check on completely fresh synthetic audio found it also
fires on "Hey Alfredo" (phonetically very close to "Hey Alfie") - a small
custom-trained model isn't going to match the robustness of the officially
trained pretrained models. If false triggers or misses turn out to be a
problem in daily use, recording more/more varied real samples and re-running
`train_wake_word.py` is the lever to pull.

## Why a small model?

This machine has 13GB of RAM. Ollama keeps recently-used models loaded in
memory (default 5 minutes), and having two large models loaded at once
(discovered during setup: qwen2.5:14b + qwen3.5, ~16GB combined) pushed the
system into heavy swapping — turning ~1 second responses into 45+ seconds.
`qwen2.5:3b-instruct` stays fast and leaves headroom for everything else you
run day to day. If you want smarter (slower) answers, change `llm.model` in
`config.yaml`, but avoid running voice queries while another large model is
also loaded (`ollama ps` shows what's currently in memory).

## Known limitation: no echo cancellation

There's no acoustic echo cancellation here, so Alfie can't hear you interrupt
while it's talking, and it discards whatever the mic picks up during its own
speech (see `mic.drain()` in `assistant.py`) rather than trying to filter it
out. Keep the wake word and your command as one clean utterance after Alfie
finishes speaking.

## Skills

Built-in skills (in `skills/`), matched by keyword before falling back to the LLM:
- `time`, `date`: report current time/date
- `weather`: via wttr.in, optionally "weather in <city>"
- `timer`: "set a timer for 5 minutes" (announced by voice when it expires)
- `reminder`: timed ("remind me in 20 minutes to check the oven") or untimed,
  persisted-to-disk notes ("remember that...", "what do you remember")
- `calculator`: arithmetic via a restricted AST evaluator, not the LLM (the
  LLM got a plain multiplication wrong during testing - see tests/)
- `unit_conversion`: "convert 10 miles to kilometers", via `pint`
- `media_control`: "play `<song/artist/genre>`" streams audio via yt-dlp + mpv
  (no local library or streaming account configured, so this searches
  YouTube and plays the top result's audio). "pause"/"resume"/"stop" control
  that stream directly; if nothing's playing that we started ourselves, they
  fall back to `playerctl` in case something else (e.g. a browser tab) is
  playing. No queue, so "next"/"skip" aren't supported for streamed tracks.
- `web_search`: "search for ..." / "look up ..." via DuckDuckGo's HTML page
- `wikipedia`: "who/what is ..." / "tell me about ..." via Wikipedia's summary API
- `system_control`: volume, disk space, battery, CPU/memory usage, screen
  brightness, screenshots, network status/IP, locking/suspending, opening a
  few installed apps, and shutting down/restarting (the last two require a
  spoken "yes" confirmation first - see `tests/test_system_control.py`)

Add a new skill by creating `skills/<name>_skill.py` with a `<Name>Skill`
class inheriting from `skills.base.Skill`, implementing `matches(text)` and
`handle(text)`. **Run the test suite after** (see below) - several of the
skills above only got their current keyword boundaries because adding a new
one collided with an existing one.

## Testing

```bash
pip install -r requirements-dev.txt
pytest              # fast suite: ~95 tests, no network/system side effects, ~6s
pytest -m integration   # + real Wikipedia and Ollama calls (needs both reachable)
```

This exists because five separate routing collisions were found the hard way
during development - e.g. "what is 15 **times** 23" was being claimed by the
time skill too, because "time" is a literal substring of "times". Each one
was only caught by manually re-running an ad-hoc sweep script after the fact;
`tests/test_skill_routing.py` formalizes that sweep so it runs automatically.

Nothing in the default suite touches real hardware or system state - the
shutdown/reboot confirmation flow is tested by mocking the actual
`subprocess.run` call, so it's never actually executed, not even in tests.

## License

MIT
