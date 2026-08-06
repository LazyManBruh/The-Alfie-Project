"""Weather skill using wttr.in"""

import re
import httpx
from .base import Skill

# A flat `timeout=10.0` applies to EACH phase independently (connect/TLS handshake,
# read, write, pool), so a hung handshake can overshoot that nominal number by a lot
# in practice - measured ~15.75s from a "10s" timeout in the wikipedia skill, which
# hits the same underlying httpx behavior. Tight explicit per-phase budgets bound how
# long a live conversation goes silent on a network hiccup.
_TIMEOUT = httpx.Timeout(connect=3.0, read=4.0, write=3.0, pool=2.0)


class WeatherSkill(Skill):
    name = "weather"

    def matches(self, text: str) -> bool:
        return "weather" in text.lower()

    def _extract_location(self, text: str) -> str:
        m = re.search(r"weather (?:in|for|at)\s+(.+)", text, re.IGNORECASE)
        return m.group(1).strip().rstrip("?.") if m else ""

    def handle(self, text: str) -> str:
        location = self._extract_location(text)
        url = f"http://wttr.in/{location}?format=3" if location else "http://wttr.in/?format=3"
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(url)
                weather = resp.text.strip()
                if resp.status_code == 200 and weather:
                    return weather
                return "I couldn't get the weather right now."
        except Exception:
            return "Sorry, I couldn't reach the weather service."
