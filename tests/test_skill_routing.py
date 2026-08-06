"""Regression tests for skill routing: which skill (if any) claims each
utterance.

This exists because five real collisions were found during development -
timer/reminder ("remind me in" claimed by both), calculator/time ("times"
containing the substring "time"), unit_conversion/reminder (its regex
matched "<number> word to word" shapes that weren't unit conversions at
all), and Wikipedia's broad "what is X" trigger swallowing other skills'
phrasing twice (once for time/date/weather, again for the system_control
additions). Each one was only caught by manually re-running an ad-hoc sweep
script after the fact. This formalizes that sweep so it runs automatically
instead of relying on remembering to re-check.
"""

import pytest

CASES = [
    # (utterance, expected skill name, or None if it should fall through to the LLM)
    ("what time is it", "time"),
    ("what is the date today", "date"),
    ("what is the weather in paris", "weather"),
    ("set a timer for ten seconds", "timer"),
    ("remind me in 5 minutes to check the oven", "reminder"),
    ("remind me to buy milk", "reminder"),
    ("remember that the wifi password is sunflower", "reminder"),
    ("what do you remember", "reminder"),
    ("forget that the wifi password is sunflower", "reminder"),
    ("clear my reminders", "reminder"),
    ("play some jazz", "media_control"),
    ("play bohemian rhapsody by queen", "media_control"),
    ("pause the music", "media_control"),
    ("skip this song", "media_control"),
    ("search for the eiffel tower", "web_search"),
    ("who is elon musk", "wikipedia"),
    ("what is the capital of france", "wikipedia"),
    ("tell me about python programming language", "wikipedia"),
    ("what is 15 times 23", "calculator"),
    ("what is 20 percent of 150", "calculator"),
    ("calculate 100 divided by 4", "calculator"),
    ("convert 10 miles to kilometers", "unit_conversion"),
    ("convert 100 celsius to fahrenheit", "unit_conversion"),
    ("what is my battery level", "system_control"),
    ("how much disk space do i have", "system_control"),
    ("turn the volume up", "system_control"),
    ("set volume to 40 percent", "system_control"),
    ("mute", "system_control"),
    ("open firefox", "system_control"),
    ("shut down the computer", "system_control"),
    ("restart the computer", "system_control"),
    ("restart the timer", "timer"),  # regression case - NOT system_control
    ("suspend the computer", "system_control"),
    ("go to sleep", "system_control"),
    ("lock the screen", "system_control"),
    ("take a screenshot", "system_control"),
    ("what is the brightness", "system_control"),
    ("turn the brightness up", "system_control"),
    ("what is my cpu usage", "system_control"),
    ("how much memory am i using", "system_control"),
    ("am i connected to the internet", "system_control"),
    ("what is my ip address", "system_control"),
    ("brief me", "briefing"),
    ("give me a morning briefing", "briefing"),
    ("status report", "briefing"),
    ("sitrep", "briefing"),
    ("convert 50 dollars to euros", "currency_conversion"),
    ("convert 10 pounds to dollars", "currency_conversion"),
    ("convert 10 pounds to kilograms", "unit_conversion"),  # regression: "pounds" ambiguity
    ("what is in the news", "news"),
    ("give me the news", "news"),
    ("top headlines", "news"),
    ("ping google.com", "network_check"),
    ("is port 443 open on google.com", "network_check"),
    ("google.com port 443", "network_check"),
    # These should fall through to the LLM - no skill should claim them.
    ("tell me a joke", None),
    ("good morning", None),
    ("pause", None),  # no context word and no active player - ambiguous alone
    ("stop", None),
    ("turn off the music", None),  # known gap: media_control doesn't cover "turn off"
]


@pytest.mark.parametrize("utterance,expected", CASES)
def test_routing(skill_manager, utterance, expected):
    claimants = [name for name, skill in skill_manager.skills.items() if skill.matches(utterance)]
    assert len(claimants) <= 1, f"{utterance!r} was claimed by multiple skills: {claimants}"
    actual = claimants[0] if claimants else None
    assert actual == expected, f"{utterance!r} -> expected {expected!r}, got {actual!r}"
