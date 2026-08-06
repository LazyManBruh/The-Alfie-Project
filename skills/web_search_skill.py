"""Web search skill using DuckDuckGo's HTML front-end"""

import re
import urllib.parse
from html.parser import HTMLParser
import httpx
from .base import Skill

# See weather_skill.py / wikipedia_skill.py for why this is an explicit per-phase
# budget instead of a flat timeout=15.0 float.
_TIMEOUT = httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=2.0)


class _SnippetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.recording = False
        self.snippet = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "class" and value and "result__snippet" in value:
                    self.recording = True

    def handle_data(self, data):
        if self.recording and not self.snippet:
            self.snippet = data.strip()


class WebSearchSkill(Skill):
    name = "web_search"

    def matches(self, text: str) -> bool:
        t = text.lower()
        return any(k in t for k in ["search for", "look up", "google "])

    def _extract_query(self, text: str) -> str:
        m = re.search(r"(?:search for|look up|google)\s+(.+)", text, re.IGNORECASE)
        return m.group(1).strip().rstrip("?.") if m else text.strip()

    def handle(self, text: str) -> str:
        query = self._extract_query(text)
        if not query:
            return "What would you like me to search for?"
        encoded = urllib.parse.quote_plus(query)
        url = f"https://duckduckgo.com/html/?q={encoded}"
        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200:
                    return "The search failed."
                parser = _SnippetParser()
                parser.feed(resp.text)
                if parser.snippet:
                    return " ".join(parser.snippet.split())
                return "I couldn't find a clear answer for that."
        except Exception:
            return "Sorry, I couldn't reach the web to search."
