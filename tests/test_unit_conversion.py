"""Unit conversion skill (via pint). Also covers the collision fix: the regex
alone is too permissive - "remind me in 5 minutes to check the oven" has the
same "<number> word to word" shape as a real conversion - so matches() must
validate both sides are real units pint recognizes, not just check the
pattern shape."""

import pytest
from alfie_assistant.skills.unit_conversion_skill import UnitConversionSkill


@pytest.fixture
def conv():
    return UnitConversionSkill()


@pytest.mark.parametrize("utterance,expected_value,expected_unit", [
    ("convert 10 miles to kilometers", 16.09, "kilometers"),
    ("convert 100 celsius to fahrenheit", 212, "fahrenheit"),
    ("convert 5 kilograms to pounds", 11.02, "pounds"),
])
def test_conversions(conv, utterance, expected_value, expected_unit):
    result = conv.handle(utterance)
    assert f"{expected_value} {expected_unit}" in result


def test_does_not_swallow_reminder_phrasing(conv):
    # Regression: used to false-match because "minutes"/"check" fit the
    # "<number> unit to unit" shape even though "check" isn't a real unit.
    assert not conv.matches("remind me in 5 minutes to check the oven")


def test_invalid_unit_reports_gracefully(conv):
    response = conv.handle("convert 10 sdfsdf to kilometers")
    assert "sir" in response.lower()
