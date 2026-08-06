"""News headlines skill via BBC's public RSS feed (no API key needed).

Reads out the top 3 headlines only - a full RSS feed dump would make for an
extremely long, unnatural-sounding spoken response.
"""

import xml.etree.ElementTree as ET
import httpx
from .base import Skill
from loguru import logger

_TIMEOUT = httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=2.0)
_FEED_URL = "http://feeds.bbci.co.uk/news/rss.xml"
_TRIGGERS = (
    "the news", "news headlines", "what's in the news", "whats in the news",
    "give me the news", "top headlines", "what's happening in the news",
)
_HEADLINE_COUNT = 3


class NewsSkill(Skill):
    name = "news"

    def matches(self, text: str) -> bool:
        t = text.lower().strip()
        return any(trigger in t for trigger in _TRIGGERS)

    def handle(self, text: str) -> str:
        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(_FEED_URL)
            if resp.status_code != 200:
                return "I couldn't reach the news right now, sir."
            root = ET.fromstring(resp.text)
            titles = [item.findtext("title") for item in root.iter("item")]
            titles = [t.strip() for t in titles if t and t.strip()][:_HEADLINE_COUNT]
        except Exception as e:
            logger.error(f"news fetch failed: {e}")
            return "Sorry, I couldn't reach the news, sir."

        if not titles:
            return "I couldn't find any headlines right now, sir."

        return f"Here are the top headlines, sir: {'; '.join(titles)}."
