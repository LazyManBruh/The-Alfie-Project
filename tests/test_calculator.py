"""Calculator skill - exists specifically because the LLM got a plain
multiplication wrong (and mixed in a stray Chinese character) during testing.
This must never touch the LLM; the assertions here are exact expected values,
not "did it return something plausible"."""

import pytest
from alfie_assistant.skills.calculator_skill import CalculatorSkill


@pytest.fixture
def calc():
    return CalculatorSkill()


@pytest.mark.parametrize("utterance,expected", [
    ("what is 15 times 23", 345),
    ("what is 20 percent of 150", 30),
    ("calculate 100 divided by 4", 25),
    ("what is 7 plus 8 minus 2", 13),
    ("what's 9 minus 20", -11),
])
def test_arithmetic(calc, utterance, expected):
    assert calc.handle(utterance) == f"That's {expected}, sir."


def test_division_by_zero_fails_gracefully(calc):
    response = calc.handle("what is 5 divided by 0")
    assert "sir" in response.lower()  # a spoken failure message, not a crash


@pytest.mark.parametrize("utterance", [
    "what is the capital of france",  # no digits/operators - not calculator's job
    "what time is it",
])
def test_non_math_does_not_match(calc, utterance):
    assert not calc.matches(utterance)
