"""Reminders & notes skill. The `redirect_notes_file` autouse fixture (see
conftest.py) points NOTES_FILE at a pytest tmp_path for every test in this
suite, so nothing here ever touches the user's real reminders."""

import time
import pytest
from alfie_assistant.skills.reminder_skill import ReminderSkill


@pytest.fixture
def reminder():
    spoken = []
    skill = ReminderSkill(context={"speak": spoken.append})
    return skill, spoken


def test_remember_and_list(reminder):
    skill, _ = reminder
    assert skill.handle("remember that the wifi password is sunflower") == "I'll remember that, sir."
    assert skill.handle("remind me to buy milk") == "I'll remember that, sir."
    response = skill.handle("what do you remember")
    assert "wifi password is sunflower" in response
    assert "buy milk" in response


def test_forget_one_and_clear(reminder):
    skill, _ = reminder
    skill.handle("remember that the wifi password is sunflower")
    skill.handle("remind me to buy milk")

    assert skill.handle("forget that the wifi password is sunflower") == "I've forgotten that, sir."
    response = skill.handle("what do you remember")
    assert "buy milk" in response and "wifi password" not in response

    assert skill.handle("clear my reminders") == "I've cleared all your reminders, sir."
    assert skill.handle("what do you remember") == "You don't have any reminders, sir."


def test_persists_across_instances():
    ReminderSkill().handle("remember that the garage code is 4321")
    response = ReminderSkill().handle("what do you remember")
    assert "garage code is 4321" in response


def test_timed_reminder_fires_with_custom_message(reminder):
    skill, spoken = reminder
    assert "3 seconds" in skill.handle("remind me in 3 seconds to check the oven")
    time.sleep(3.5)
    assert spoken == ["Reminder, sir: check the oven."]
