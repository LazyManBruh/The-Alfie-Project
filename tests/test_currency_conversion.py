"""Currency conversion skill via frankfurter.dev. Also covers the same class
of collision fix as unit_conversion_skill: both sides of the phrase must
resolve to a real currency code, not just fit the "<number> word to word"
pattern shape - and the genuinely ambiguous cases ("pounds" as currency vs.
weight) must route correctly depending on the other side of the conversion."""

from unittest.mock import patch, MagicMock
import pytest
from alfie_assistant.skills.currency_conversion_skill import CurrencyConversionSkill
from alfie_assistant.skills.unit_conversion_skill import UnitConversionSkill


@pytest.fixture
def skill():
    return CurrencyConversionSkill()


def test_matches_known_currency_pairs(skill):
    assert skill.matches("convert 50 dollars to euros")
    assert skill.matches("convert 10 pounds to dollars")


def test_does_not_match_unit_conversion_phrasing(skill):
    assert not skill.matches("convert 10 miles to kilometers")
    assert not skill.matches("convert 100 celsius to fahrenheit")


def test_pounds_ambiguity_resolves_by_context():
    currency, units = CurrencyConversionSkill(), UnitConversionSkill()

    # "pounds" -> weight when paired with another weight unit
    assert units.matches("convert 10 pounds to kilograms")
    assert not currency.matches("convert 10 pounds to kilograms")

    # "pounds" -> currency when paired with another currency
    assert currency.matches("convert 10 pounds to dollars")
    assert not units.matches("convert 10 pounds to dollars")


def test_conversion_calls_frankfurter_with_resolved_codes(skill):
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"amount": 50.0, "base": "USD", "rates": {"EUR": 43.42}}

    with patch("httpx.Client") as mock_client_cls:
        mock_get = mock_client_cls.return_value.__enter__.return_value.get
        mock_get.return_value = fake_response
        response = skill.handle("convert 50 dollars to euros")

    assert response == "That's about 43.42 EUR, sir."
    params = mock_get.call_args.kwargs["params"]
    assert params == {"from": "USD", "to": "EUR", "amount": "50"}


def test_api_failure_reported_gracefully(skill):
    with patch("httpx.Client", side_effect=Exception("network down")):
        response = skill.handle("convert 50 dollars to euros")
    assert "sir" in response.lower()


@pytest.mark.integration
def test_real_conversion(skill):
    response = skill.handle("convert 50 dollars to euros")
    assert "EUR" in response
