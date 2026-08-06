"""Time skill for reporting the current time"""

import re
from datetime import datetime
from .base import Skill

_TIME_WORD = re.compile(r"\btime\b")


class TimeSkill(Skill):
    name = "time"

    def matches(self, text: str) -> bool:
        t = text.lower()
        # \b word boundary matters here - "times" (as in "15 times 23")
        # contains "time" as a substring and would otherwise false-match.
        return bool(_TIME_WORD.search(t)) and ("what" in t or "tell me" in t or "current" in t)

    def handle(self, text: str) -> str:
        now = datetime.now()
        return f"It's {now.strftime('%H:%M')}."
