"""Wikipedia lookup skill. The exclusion-list logic (avoiding collisions with
time/date/weather/system_control's "what is X" phrasing) is tested without
network; the actual live lookup is a marked integration test."""

import pytest
from alfie_assistant.skills.wikipedia_skill import WikipediaSkill


@pytest.fixture
def skill():
    return WikipediaSkill()


@pytest.mark.parametrize("utterance", [
    "what's the time",
    "what's the date",
    "what's the weather",
    "what is my cpu usage",
    "what is the brightness",
    "what is my ip address",
    "what is 15 times 23",
])
def test_excludes_other_skills_phrasing(skill, utterance):
    assert not skill.matches(utterance)


@pytest.mark.parametrize("utterance", [
    "who is elon musk",
    "what is the eiffel tower",
    "tell me about python programming language",
])
def test_matches_genuine_factual_questions(skill, utterance):
    assert skill.matches(utterance)


@pytest.mark.integration
@pytest.mark.parametrize("utterance,expected_substring", [
    ("who is elon musk", "Musk"),
    ("what is the eiffel tower", "Eiffel Tower"),
])
def test_real_lookup(skill, utterance, expected_substring):
    assert expected_substring in skill.handle(utterance)
