"""AlfieAssistant's conversation control flow: follow-up mode (no wake word
needed after Alfie asks a question) and conversation memory (persists across
separate wake-word triggers, expires after inactivity). Uses the real
`assistant` fixture (real skills/LLM client) with only mic I/O and speak
mocked out, since those need real hardware; `llm.chat` is mocked too except
in the one integration test, so this suite doesn't need Ollama running."""

from unittest.mock import patch
import pytest
import alfie_assistant.assistant as assistant_module


def test_chains_through_questions_and_stops_on_a_plain_answer(fresh_conversation_state):
    a = fresh_conversation_state
    utterances = iter(["set a timer", "for ten seconds", "thats all thanks"])
    responses = iter([
        "How long should the timer be, sir?",
        "Timer set for ten seconds. Anything else?",
        "Very good, sir.",
    ])
    spoken = []

    with patch.object(a, "_record_utterance", side_effect=lambda *a, **k: next(utterances, "")), \
         patch.object(a.skills, "route", return_value=None), \
         patch.object(a.llm, "chat", side_effect=lambda h: next(responses)), \
         patch.object(a, "speak", side_effect=spoken.append), \
         patch.object(assistant_module, "play_chime") as chime:
        a._converse()

    assert spoken == [
        "How long should the timer be, sir?",
        "Timer set for ten seconds. Anything else?",
        "Very good, sir.",
    ]
    assert chime.call_count == 2  # once per follow-up, not after the final plain answer


def test_gives_up_silently_if_no_reply_to_a_question(fresh_conversation_state):
    a = fresh_conversation_state
    utterances = iter(["tell me a joke", ""])  # "" = timed out, no follow-up heard
    spoken = []

    with patch.object(a, "_record_utterance", side_effect=lambda *a, **k: next(utterances, "")), \
         patch.object(a.skills, "route", return_value=None), \
         patch.object(a.llm, "chat", return_value="Would you like to hear another, sir?"), \
         patch.object(a, "speak", side_effect=spoken.append), \
         patch.object(assistant_module, "play_chime"):
        a._converse()  # must return promptly, not hang waiting forever

    assert spoken == ["Would you like to hear another, sir?"]


def test_history_persists_across_separate_wake_word_triggers(fresh_conversation_state):
    a = fresh_conversation_state
    captured = []

    def fake_chat(history):
        captured.append([dict(m) for m in history])
        if len(captured) == 1:
            return "Marie Curie was a physicist and chemist, sir."
        return "She discovered polonium and radium, sir."

    with patch.object(a, "_record_utterance", return_value="who is marie curie"), \
         patch.object(a.skills, "route", return_value=None), \
         patch.object(a.llm, "chat", side_effect=fake_chat), \
         patch.object(a, "speak"), \
         patch.object(assistant_module, "play_chime"):
        a._converse()  # wake-word trigger #1

    with patch.object(a, "_record_utterance", return_value="what did she discover"), \
         patch.object(a.skills, "route", return_value=None), \
         patch.object(a.llm, "chat", side_effect=fake_chat), \
         patch.object(a, "speak"), \
         patch.object(assistant_module, "play_chime"):
        a._converse()  # a FRESH, separate wake-word trigger - not a follow-up chain

    turn_2_messages = captured[1]
    assert turn_2_messages[0] == {"role": "user", "content": "who is marie curie"}
    assert turn_2_messages[-1] == {"role": "user", "content": "what did she discover"}


def test_history_expires_after_inactivity(fresh_conversation_state):
    a = fresh_conversation_state
    a.history = [{"role": "user", "content": "old topic"}, {"role": "assistant", "content": "old answer"}]
    a.last_interaction_at -= (assistant_module.HISTORY_EXPIRY_SECONDS + 10)

    with patch.object(a, "_record_utterance", return_value="tell me a joke"), \
         patch.object(a.skills, "route", return_value=None), \
         patch.object(a.llm, "chat", return_value="Fine, sir.") as mock_chat, \
         patch.object(a, "speak"), \
         patch.object(assistant_module, "play_chime"):
        a._converse()

    messages_sent = mock_chat.call_args[0][0]
    assert messages_sent == [{"role": "user", "content": "tell me a joke"}]  # stale history dropped


@pytest.mark.integration
def test_skill_answered_turn_remembered_by_real_llm(fresh_conversation_state):
    """The full real thing: a skill (not the LLM) answers turn one, and the
    real Ollama call on turn two still recalls it - verified manually during
    development, formalized here."""
    a = fresh_conversation_state
    utterances = iter(["what is the weather in paris", "what did i just ask you"])
    spoken = []

    with patch.object(a, "_record_utterance", side_effect=lambda *a, **k: next(utterances, "")), \
         patch.object(a, "speak", side_effect=spoken.append), \
         patch.object(assistant_module, "play_chime"):
        a._converse()
        a._converse()

    assert any(w in spoken[-1].lower() for w in ("paris", "weather"))
