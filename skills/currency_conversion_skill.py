"""Currency conversion skill via frankfurter.dev (free, no API key, daily
ECB reference rates). Note: frankfurter.app (the older domain some docs
still reference) 301-redirects here now - using the new domain directly
avoids an extra round trip.

Shares the exact "<number> word to word" regex shape with unit_conversion_skill,
so - same fix as that skill needed for its own collision - both sides of the
phrase must resolve to something real (a currency code here, a pint unit
there) before claiming a match, rather than just matching the pattern shape.
"""

import re
import httpx
from .base import Skill
from loguru import logger

_TIMEOUT = httpx.Timeout(connect=3.0, read=4.0, write=3.0, pool=2.0)

_CONVERT_RE = re.compile(
    r"(?:convert\s+)?(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+(?:to|in|into)\s+([a-zA-Z]+)"
)

# Common spoken names -> ISO 4217 codes, limited to what frankfurter.dev
# actually supports (checked live against its /v1/currencies endpoint).
_CURRENCY_NAMES = {
    "dollar": "USD", "dollars": "USD", "usd": "USD", "bucks": "USD",
    "euro": "EUR", "euros": "EUR", "eur": "EUR",
    "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "sterling": "GBP",
    "yen": "JPY", "jpy": "JPY",
    "yuan": "CNY", "renminbi": "CNY", "cny": "CNY",
    "rupee": "INR", "rupees": "INR", "inr": "INR",
    "franc": "CHF", "francs": "CHF", "chf": "CHF",
    "cad": "CAD",
    "aud": "AUD",
    "krona": "SEK", "sek": "SEK",
    "krone": "NOK", "nok": "NOK",
    "won": "KRW", "krw": "KRW",
    "peso": "MXN", "pesos": "MXN", "mxn": "MXN",
    "real": "BRL", "reais": "BRL", "brl": "BRL",
    "rand": "ZAR", "zar": "ZAR",
    "lira": "TRY", "try": "TRY",
    "zloty": "PLN", "pln": "PLN",
    "sgd": "SGD",
    "hkd": "HKD",
    "nzd": "NZD",
}


class CurrencyConversionSkill(Skill):
    name = "currency_conversion"

    def _resolve_code(self, word: str):
        return _CURRENCY_NAMES.get(word.lower().strip())

    def matches(self, text: str) -> bool:
        match = _CONVERT_RE.search(text.lower())
        if not match:
            return False
        _, from_word, to_word = match.groups()
        return self._resolve_code(from_word) is not None and self._resolve_code(to_word) is not None

    def handle(self, text: str) -> str:
        match = _CONVERT_RE.search(text.lower())
        if not match:
            return "I couldn't understand that conversion, sir."
        amount, from_word, to_word = match.groups()
        from_code, to_code = self._resolve_code(from_word), self._resolve_code(to_word)

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(
                    "https://api.frankfurter.dev/v1/latest",
                    params={"from": from_code, "to": to_code, "amount": amount},
                )
            if resp.status_code != 200:
                return "I couldn't fetch exchange rates right now, sir."
            converted = resp.json()["rates"][to_code]
        except Exception as e:
            logger.error(f"currency conversion failed for {from_code}->{to_code}: {e}")
            return "Sorry, I couldn't reach the exchange rate service, sir."

        value = round(converted, 2)
        if value == int(value):
            value = int(value)
        return f"That's about {value} {to_code}, sir."
