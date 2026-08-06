## Project Setup Complete

I've created the initial structure for your Alfie (formerly JARVIS) personal assistant. Here's what's been set up:

### Project Structure
```
alfie_assistant/
├── assistant.py          # Main entry point and core loop
├─ config.py             # Configuration loading (with default config.yaml generation)
├── requirements.txt     # Python dependencies
├── README.md            # Project documentation
│
├── audio/
│   ├── __init__.py
│   ├── capture.py       # Audio input using sounddevice
│   └── playback.py      # Audio output using simpleaudio/aplay fallback
│
├── wake_word/
│   ├── __init__.py
│   └── detector.py      # Wake word detection using precise-runner + pyaudio
│
├── stt/
│   ├── __init__.py
│   └─ vosk_stt.py       # Speech-to-text using Vosk
│
├── llm/
│   ├── __init__.py
│   └─ ollama_client.py  # LLM client for Ollama API
│
├── tts/
│   ├── __init__.py
│   └─ piper_tts.py      # Text-to-speech using Piper (via subprocess)
│
├── skills/
│   ├── __init__.py      # Skill manager and dynamic loading
│   ├── base.py          # Abstract base class for skills
│   ├── time_skill.py    # Report current time
│   ├── date_skill.py    # Report current date
│   ├── weather_skill.py # Weather via wttr.in (async)
│   ├── web_search_skill.py # Web search via DuckDuckGo
│   ├── timer_skill.py   # Simple countdown timer
│   └── media_control_skill.py # Media control via playerctl
│
└── tests/
    └── (placeholder for unit tests)
```

### Next Steps for You

1. **Install System Dependencies**:
   - Install PortAudio development headers (for sounddevice/pyaudio):
     ```bash
     sudo apt-get install portaudio19-dev python3-pyaudio  # Debian/Ubuntu
     ```
   - Install `playerctl` for media control:
     ```bash
     sudo apt-get install playerctl
     ```
   - Install Piper TTS binary (follow instructions at https://github.com/rhasspy/piper)
   - Install Vosk model (download from https://alphacephei.com/vosk/models and unpack)
   - Install a wake word model for Precise (you can generate one for "Hey Alfie" using the Precise trainer)

2. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Download Models**:
   - Create a `models` directory and place your Vosk model there (e.g., `models/vosk-model-small-en-us-0.15`)
   - Place your Piper ONNX model in `models/piper/en_US-lessac-medium.onnx` (or similar)
   - Place your Precise phoneme file for "hey alfie" in `models/hey_alfee.params`

4. **Create Configuration** (will be auto-generated on first run):
   - The assistant will create a default `config.yaml` in the current directory if none exists.
   - Edit this file to point to your downloaded models.

5. **Test the Assistant**:
   ```bash
   python -m alfie_assistant
   ```
   Say the wake word (default: "Hey Alfie") followed by a command like "What time is it?"

### Customization
- To add new skills, create a new file in `skills/` that inherits from `skills.base.Skill` and implements the `execute(args: dict) -> str` method.
- The skill manager will automatically discover and load any new skill modules.

### Notes
- The assistant is designed to be privacy-first: all processing (wake word, STT, LLM, TTS) runs locally.
- Only the weather and web search skills make external HTTP requests (to wttr.in and duckduckgo.com).
- You can adjust the wake word sensitivity, LLM temperature, and other parameters in config.yaml.

Let me know if you'd like me to implement any specific skill next or if you encounter any issues during setup!