"""Wikipedia lookup skill - REST summary API, no API key needed.

More reliable than the web_search skill's DuckDuckGo HTML scraping for actual
factual "who/what is X" questions (that skill targets open-ended "search for
X" queries instead). "what is"/"what's" is broad enough to accidentally
swallow other skills' phrasing (the time, date, weather, and system_control
skills all use "what is"/"what's" too), so anything containing their keywords
is explicitly left alone here rather than raced against them.
"""

import re
import httpx
from .base import Skill
from loguru import logger

_LEAD_TRIGGERS = ["who is", "who was", "what is", "what's", "whats", "what are", "tell me about"]
_MATH_HINTS = re.compile(r"\b(times|plus|minus|divided|percent|multiplied)\b|[+\-*/]")
_EXCLUDE_KEYWORDS = {
    "time", "date", "day", "weather", "timer", "reminder", "remind", "remember",
    "music", "song", "volume", "battery", "disk space", "free space", "storage",
    "brightness", "cpu", "memory usage", "ram usage", "ip address", "screenshot",
    "connected to the internet", "internet connection", "network status",
    "the news", "news headlines", "top headlines",
}
_HEADERS = {"User-Agent": "AlfieAssistant/1.0 (personal local voice assistant)"}
# A flat `timeout=10.0` applies to EACH phase independently (connect/TLS handshake,
# read, write, pool) - a hung TLS handshake can overshoot that nominal number by a
# lot in practice (observed: ~15.75s from a "10s" timeout) before finally erroring.
# Tight explicit per-phase budgets bound how long a live conversation goes silent
# on a network hiccup, which matters a lot more here than getting the occasional
# slow-but-would-have-succeeded request.
_TIMEOUT = httpx.Timeout(connect=3.0, read=4.0, write=3.0, pool=2.0)


class WikipediaSkill(Skill):
    name = "wikipedia"

    def _extract_topic(self, text: str):
        t = text.lower().strip().rstrip("?.! ")
        for lead in _LEAD_TRIGGERS:
            if t.startswith(lead):
                return t[len(lead):].strip()
        return None

    def matches(self, text: str) -> bool:
        topic = self._extract_topic(text)
        if not topic:
            return False
        if re.search(r"\d", topic) and _MATH_HINTS.search(topic):
            return False  # let the calculator skill handle this
        if any(kw in topic for kw in _EXCLUDE_KEYWORDS):
            return False  # let the more specific skill handle this
        return True

    def handle(self, text: str) -> str:
        topic = self._extract_topic(text)
        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS) as client:
                search = client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={"action": "opensearch", "search": topic, "limit": 1, "format": "json"},
                )
                titles = search.json()[1] if search.status_code == 200 else []
                if not titles:
                    return f"I couldn't find anything on {topic}, sir."
                title = titles[0]

                summary = client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}")
                extract = summary.json().get("extract", "") if summary.status_code == 200 else ""
                if not extract:
                    return f"I couldn't find anything on {topic}, sir."

                sentence = extract.split(". ")[0].rstrip(".") + "."
                return sentence
        except Exception as e:
            logger.error(f"wikipedia lookup failed for {topic!r}: {e}")
            return "Sorry, I couldn't reach Wikipedia, sir."
