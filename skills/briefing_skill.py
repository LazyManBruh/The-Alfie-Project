"""Briefing skill: one spoken summary combining time/date, weather, pending
reminders, and battery status - the pieces already built by other skills,
composed into a single coherent utterance.

Deliberately fetches its own data (wttr.in, notes.json, psutil) rather than
calling the other skills' handle() and stitching their responses together:
several of those already end in their own ", sir." or include a location
name and an emoji (weather), which reads as repetitive/awkward when several
are concatenated into one summary. A few lines of duplicated data-fetching
buys a briefing that actually sounds like one sentence instead of four
back-to-back skill answers.
"""

import json
import re
from datetime import datetime
import httpx
from .base import Skill
from . import reminder_skill
from loguru import logger

try:
    import psutil
except ImportError:
    psutil = None

_TRIGGERS = (
    "brief me", "give me a briefing", "daily briefing", "morning briefing",
    "give me a status report", "status report", "sitrep",
)

# See weather_skill.py for why this is an explicit per-phase budget.
_TIMEOUT = httpx.Timeout(connect=3.0, read=4.0, write=3.0, pool=2.0)

_WEATHER_RE = re.compile(r"([+-]?)(\d+)\xb0C")


class BriefingSkill(Skill):
    name = "briefing"

    def matches(self, text: str) -> bool:
        t = text.lower().strip()
        return any(trigger in t for trigger in _TRIGGERS)

    def handle(self, text: str) -> str:
        parts = [self._greeting(), self._time_and_date()]

        weather = self._weather()
        if weather:
            parts.append(weather)

        reminders = self._reminders_summary()
        if reminders:
            parts.append(reminders)

        battery = self._battery()
        if battery:
            parts.append(battery)

        return " ".join(parts)

    def _greeting(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning, sir."
        if hour < 18:
            return "Good afternoon, sir."
        return "Good evening, sir."

    def _time_and_date(self) -> str:
        now = datetime.now()
        return f"It's {now.strftime('%H:%M')} on {now.strftime('%A, %B %d')}."

    def _weather(self):
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get("http://wttr.in/?format=%C+%t")
                if resp.status_code != 200 or not resp.text.strip():
                    return None
                return f"Currently {self._humanize_weather(resp.text.strip())} outside."
        except Exception as e:
            logger.info(f"briefing: weather unavailable: {e}")
            return None

    def _humanize_weather(self, raw: str) -> str:
        match = _WEATHER_RE.search(raw)
        if not match:
            return raw
        sign, degrees = match.groups()
        condition = raw[: match.start()].strip()
        temp_phrase = f"minus {degrees}" if sign == "-" else degrees
        return f"{condition} and {temp_phrase} degrees"

    def _reminders_summary(self):
        if not reminder_skill.NOTES_FILE.exists():
            return None
        try:
            notes = json.loads(reminder_skill.NOTES_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if not notes:
            return None
        if len(notes) == 1:
            return f"You have one reminder: {notes[0]['text']}."
        return f"You have {len(notes)} reminders, the most recent being {notes[-1]['text']}."

    def _battery(self):
        if psutil is None:
            return None
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        state = "charging" if battery.power_plugged else "on battery power"
        return f"Battery is at {round(battery.percent)} percent, {state}."
