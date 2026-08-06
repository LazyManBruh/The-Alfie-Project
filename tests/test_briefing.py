"""Briefing skill: composes time/date, weather, reminders, and battery into
one summary. Weather/battery are mocked for the fast suite (see
test_real_weather_and_composition for the live version); reminders use the
`redirect_notes_file` autouse fixture from conftest.py."""

from unittest.mock import patch, MagicMock
import pytest
from alfie_assistant.skills.briefing_skill import BriefingSkill
from alfie_assistant.skills.reminder_skill import ReminderSkill


@pytest.fixture
def skill():
    return BriefingSkill()


def test_humanizes_weather_string(skill):
    assert skill._humanize_weather("Sunny +33°C") == "Sunny and 33 degrees"
    assert skill._humanize_weather("Partly cloudy -2°C") == "Partly cloudy and minus 2 degrees"


def test_greeting_depends_on_time_of_day(skill):
    with patch("alfie_assistant.skills.briefing_skill.datetime") as mock_dt:
        mock_dt.now.return_value.hour = 9
        assert skill._greeting() == "Good morning, sir."
        mock_dt.now.return_value.hour = 15
        assert skill._greeting() == "Good afternoon, sir."
        mock_dt.now.return_value.hour = 21
        assert skill._greeting() == "Good evening, sir."


def test_full_briefing_composes_all_sources(skill):
    ReminderSkill().handle("remind me to buy milk")
    fake_weather = MagicMock(status_code=200, text="Sunny +20°C")

    with patch("httpx.Client") as mock_client_cls, \
         patch("alfie_assistant.skills.briefing_skill.psutil") as mock_psutil:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = fake_weather
        mock_psutil.sensors_battery.return_value = MagicMock(percent=82.0, power_plugged=True)

        response = skill.handle("brief me")

    assert "sir" in response.lower()
    assert "Sunny and 20 degrees" in response
    assert "buy milk" in response
    assert "82 percent" in response
    assert "charging" in response


def test_gracefully_omits_unavailable_sources(skill):
    # No reminders set (empty notes file), weather/battery both fail - should
    # still produce a coherent greeting + time/date, not crash or return junk.
    with patch("httpx.Client", side_effect=Exception("network down")), \
         patch("alfie_assistant.skills.briefing_skill.psutil", None):
        response = skill.handle("brief me")

    assert response.startswith(("Good morning", "Good afternoon", "Good evening"))
    assert "It's" in response


@pytest.mark.integration
def test_real_weather_and_composition(skill):
    response = skill.handle("brief me")
    assert "Currently" in response and "outside" in response
