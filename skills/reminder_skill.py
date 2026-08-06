"""Reminders & notes skill.

Two related but distinct things:
- Timed reminders ("remind me in 20 minutes to call the plumber") work like
  the timer skill - a threading.Timer that speaks a custom message when it
  fires - so they're lost if the assistant restarts before they go off,
  same limitation as timers.
- Untimed notes ("remember that the wifi password is ...") are persisted to
  disk, since there's no timing concern stopping that.
"""

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from .base import Skill

NOTES_FILE = Path.home() / ".local" / "share" / "alfie" / "notes.json"

_DURATION_RE = re.compile(r"(\d+)\s*(second|minute|hour)s?", re.IGNORECASE)
_TIMED_RE = re.compile(r"remind me in\s+(.+?)\s+to\s+(.+)")
_UNTIMED_REMIND_RE = re.compile(r"remind me to\s+(.+)")
_REMEMBER_RE = re.compile(r"remember (?:that|to)\s+(.+)")
_FORGET_RE = re.compile(r"forget(?: that)?\s+(.+)")

_LIST_PHRASES = [
    "what do you remember", "what are my reminders", "my reminders",
    "list my reminders", "read my reminders", "list my notes", "what are my notes",
]
_CLEAR_PHRASES = [
    "forget everything", "clear my reminders", "clear all reminders",
    "delete my reminders", "clear my notes",
]


class ReminderSkill(Skill):
    name = "reminder"

    def _load(self):
        if not NOTES_FILE.exists():
            return []
        try:
            return json.loads(NOTES_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, notes):
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        NOTES_FILE.write_text(json.dumps(notes, indent=2))

    def _parse_duration(self, text: str):
        m = _DURATION_RE.search(text)
        if not m:
            return None
        amount = int(m.group(1))
        unit = m.group(2).lower()
        seconds = amount * {"second": 1, "minute": 60, "hour": 3600}[unit]
        label = f"{amount} {unit}{'s' if amount != 1 else ''}"
        return seconds, label

    def matches(self, text: str) -> bool:
        t = text.lower().strip()
        if any(p in t for p in _LIST_PHRASES) or any(p in t for p in _CLEAR_PHRASES):
            return True
        return bool(
            _TIMED_RE.search(t) or _UNTIMED_REMIND_RE.search(t)
            or _REMEMBER_RE.search(t) or _FORGET_RE.search(t)
        )

    def handle(self, text: str) -> str:
        t = text.lower().strip().rstrip("?.! ")

        if any(p in t for p in _CLEAR_PHRASES):
            self._save([])
            return "I've cleared all your reminders, sir."

        if any(p in t for p in _LIST_PHRASES):
            notes = self._load()
            if not notes:
                return "You don't have any reminders, sir."
            spoken = "; ".join(n["text"] for n in notes)
            return f"You asked me to remember: {spoken}."

        timed = _TIMED_RE.search(t)
        if timed:
            duration_text, task = timed.groups()
            parsed = self._parse_duration(duration_text)
            if not parsed:
                return "I didn't catch how long to wait, sir."
            seconds, label = parsed
            speak = self.context.get("speak")

            def on_fire():
                if speak:
                    speak(f"Reminder, sir: {task}.")

            timer = threading.Timer(seconds, on_fire)
            timer.daemon = True
            timer.start()
            return f"I'll remind you to {task} in {label}, sir."

        forget = _FORGET_RE.search(t)
        if forget:
            target = forget.group(1)
            notes = self._load()
            remaining = [n for n in notes if target not in n["text"].lower()]
            self._save(remaining)
            if len(remaining) < len(notes):
                return "I've forgotten that, sir."
            return "I couldn't find that in your reminders, sir."

        match = _UNTIMED_REMIND_RE.search(t) or _REMEMBER_RE.search(t)
        if match:
            task = match.group(1)
            notes = self._load()
            notes.append({"text": task, "at": datetime.now().isoformat(timespec="seconds")})
            self._save(notes)
            return "I'll remember that, sir."

        return "I didn't quite catch what to remember, sir."
