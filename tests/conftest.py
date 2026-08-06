"""Shared pytest fixtures for the Alfie test suite.

Most tests construct skill instances directly and mock their external calls
(subprocess/httpx) so the suite runs fast and without touching real hardware,
network, or system state. A handful of integration tests (marked
`@pytest.mark.integration`, skipped by default - see pytest.ini) hit the real
Ollama/Wikipedia/wttr.in/DuckDuckGo services instead.
"""

import sys
from pathlib import Path

import pytest

# So `import alfie_assistant...` works regardless of where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

ENABLED_SKILLS = [
    "time", "date", "weather", "web_search", "timer", "media_control",
    "calculator", "unit_conversion", "reminder", "system_control", "wikipedia",
    "briefing", "currency_conversion", "news",
]


@pytest.fixture(autouse=True)
def redirect_notes_file(monkeypatch, tmp_path):
    """Never let a test read or write the user's real notes.json."""
    import alfie_assistant.skills.reminder_skill as reminder_skill
    monkeypatch.setattr(reminder_skill, "NOTES_FILE", tmp_path / "notes.json")


@pytest.fixture
def skill_manager():
    """A fresh SkillManager (fresh skill instances) for every test, so
    per-skill mutable state (media_control's active process, system_control's
    pending confirmation) never leaks between tests."""
    from alfie_assistant.skills import SkillManager
    return SkillManager(ENABLED_SKILLS, context={"speak": lambda text: None})


@pytest.fixture(scope="session")
def assistant():
    """A real AlfieAssistant with real local models loaded once per test
    session (Vosk/Piper/openWakeWord are too slow to reload per test).
    Ollama is real too; tests that shouldn't hit it mock `assistant.llm.chat`.
    Never calls `.mic.start()`, so it never opens a real audio stream and
    can't conflict with the assistant running live as a systemd service.
    """
    from alfie_assistant.assistant import AlfieAssistant
    from alfie_assistant.config import load_config

    config = load_config(str(Path("/home/lazyman/alfie_assistant/config.yaml")))
    a = AlfieAssistant(config)
    yield a
    a.llm.close()


@pytest.fixture
def fresh_conversation_state(assistant):
    """Reset the shared `assistant` fixture's conversation memory before a
    test that depends on starting with no history."""
    assistant.history = []
    assistant.last_interaction_at = 0.0
    return assistant
