"""Timer skill for setting countdown timers"""

import re
import threading
from .base import Skill


class TimerSkill(Skill):
    name = "timer"

    def matches(self, text: str) -> bool:
        t = text.lower()
        return "timer" in t

    def _parse_duration(self, text: str):
        m = re.search(r"(\d+)\s*(second|minute|hour)s?", text, re.IGNORECASE)
        if not m:
            return 60, "1 minute"
        amount = int(m.group(1))
        unit = m.group(2).lower()
        seconds = amount * {"second": 1, "minute": 60, "hour": 3600}[unit]
        label = f"{amount} {unit}{'s' if amount != 1 else ''}"
        return seconds, label

    def handle(self, text: str) -> str:
        seconds, label = self._parse_duration(text)
        speak = self.context.get("speak")

        def on_expire():
            if speak:
                speak(f"Your {label} timer is up.")

        timer = threading.Timer(seconds, on_expire)
        timer.daemon = True
        timer.start()
        return f"Timer set for {label}."
