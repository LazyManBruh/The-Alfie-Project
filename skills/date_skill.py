"""Date skill for reporting the current date"""

from datetime import datetime
from .base import Skill


class DateSkill(Skill):
    name = "date"

    def matches(self, text: str) -> bool:
        t = text.lower()
        return ("date" in t or "day is it" in t) and ("what" in t or "today" in t)

    def handle(self, text: str) -> str:
        today = datetime.now()
        return f"Today is {today.strftime('%A, %B %d, %Y')}."
