"""System control skill: volume, disk/battery/CPU/memory info, brightness,
screenshots, network status, locking/suspending, opening a small set of
installed desktop apps, and shutting down/restarting the machine.

Deliberately does NOT launch an arbitrary voice-transcribed program name -
a misheard word turning into an unexpected subprocess call is exactly the
kind of thing to avoid. Only apps explicitly listed in _APPS, and only if
actually present on this machine, can be launched.

Shutdown and restart require a spoken "yes" confirmation first, since unlike
everything else here they're destructive (unsaved work) and a misheard
command triggering one for real would be a genuinely bad time. This piggybacks
on the assistant's existing follow-up mechanism: any response ending in "?"
gets a reply listened for without repeating the wake word, so asking "Are you
sure, sir?" here just works. The pending confirmation expires on its own after
CONFIRMATION_TIMEOUT so a stale "shutdown?" from one exchange can't get
accidentally confirmed by an unrelated later command.
"""

import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from .base import Skill
from loguru import logger

try:
    import psutil
except ImportError:
    psutil = None

_APPS = {
    "web browser": "firefox",
    "browser": "firefox",
    "firefox": "firefox",
    "chromium": "chromium",
    "terminal": "kitty",
    "file manager": "nautilus",
    "files": "nautilus",
}

_VOLUME_SET_RE = re.compile(r"volume (?:to|at)?\s*(\d+)\s*%?")
_BRIGHTNESS_SET_RE = re.compile(r"brightness (?:to|at)?\s*(\d+)\s*%?")

_YES_WORDS = ("yes", "yeah", "yep", "yup", "confirm", "confirmed", "do it", "go ahead", "sure", "please do")

_SHUTDOWN_PHRASES = ("shut down", "shutdown", "power off", "turn off the computer")
_REBOOT_PHRASES = ("restart the computer", "restart the system", "reboot")

CONFIRMATION_TIMEOUT = 20.0


class SystemControlSkill(Skill):
    name = "system_control"

    def __init__(self, context=None):
        super().__init__(context)
        self._pending_confirmation = None
        self._pending_confirmation_at = 0.0

    # --- confirmation state -------------------------------------------------

    def _confirmation_pending(self) -> bool:
        if self._pending_confirmation is None:
            return False
        if time.time() - self._pending_confirmation_at > CONFIRMATION_TIMEOUT:
            self._pending_confirmation = None
            return False
        return True

    # --- routing -------------------------------------------------------------

    def matches(self, text: str) -> bool:
        t = text.lower().strip()
        if self._confirmation_pending():
            return True
        if any(kw in t for kw in ("volume", "mute", "unmute")):
            return True
        if any(kw in t for kw in ("disk space", "free space", "storage space")):
            return True
        if "battery" in t:
            return True
        if any(kw in t for kw in ("cpu usage", "memory usage", "ram usage", "how much memory", "how much ram")):
            return True
        if any(kw in t for kw in ("screenshot", "take a picture of my screen", "take a screen shot")):
            return True
        if "brightness" in t:
            return True
        if any(kw in t for kw in ("connected to the internet", "internet connection", "ip address", "am i online", "network status")):
            return True
        if any(kw in t for kw in ("lock the screen", "lock my screen", "lock the computer")):
            return True
        if "suspend" in t or "go to sleep" in t or ("sleep" in t and "computer" in t):
            return True
        if any(p in t for p in _SHUTDOWN_PHRASES) or any(p in t for p in _REBOOT_PHRASES):
            return True
        if t.startswith("open ") and self._resolve_app(t):
            return True
        return False

    def handle(self, text: str) -> str:
        t = text.lower().strip()

        if self._confirmation_pending():
            return self._resolve_confirmation(t)

        if "unmute" in t:
            return self._run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"], "Unmuted, sir.")
        if "mute" in t:
            return self._run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"], "Muted, sir.")
        if "volume" in t:
            return self._handle_volume(t)
        if any(kw in t for kw in ("disk space", "free space", "storage space")):
            return self._disk_space()
        if "battery" in t:
            return self._battery()
        if any(kw in t for kw in ("cpu usage", "memory usage", "ram usage", "how much memory", "how much ram")):
            return self._resource_usage(t)
        if any(kw in t for kw in ("screenshot", "take a picture of my screen", "take a screen shot")):
            return self._screenshot()
        if "brightness" in t:
            return self._handle_brightness(t)
        if any(kw in t for kw in ("connected to the internet", "internet connection", "ip address", "am i online", "network status")):
            return self._network_status(t)
        if any(kw in t for kw in ("lock the screen", "lock my screen", "lock the computer")):
            return self._run(["loginctl", "lock-session"], "Locking the screen now, sir.")
        if "suspend" in t or "go to sleep" in t or ("sleep" in t and "computer" in t):
            return self._run(["systemctl", "suspend"], "Suspending now, sir.")
        if any(p in t for p in _SHUTDOWN_PHRASES):
            self._pending_confirmation = "shutdown"
            self._pending_confirmation_at = time.time()
            return "Are you sure you'd like to shut down, sir?"
        if any(p in t for p in _REBOOT_PHRASES):
            self._pending_confirmation = "reboot"
            self._pending_confirmation_at = time.time()
            return "Are you sure you'd like to restart, sir?"
        if t.startswith("open "):
            return self._open_app(t)

        return "I'm not sure what you'd like me to do there, sir."

    def _resolve_confirmation(self, t: str) -> str:
        action = self._pending_confirmation
        self._pending_confirmation = None
        if not any(w in t for w in _YES_WORDS):
            return "Understood, sir. Cancelled."
        if action == "shutdown":
            return self._run(["systemctl", "poweroff"], "Shutting down now, sir.")
        if action == "reboot":
            return self._run(["systemctl", "reboot"], "Restarting now, sir.")
        return "Cancelled, sir."

    # --- shared subprocess helper ---------------------------------------------

    def _run(self, cmd: list, ok_message: str) -> str:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode == 0:
                return ok_message
            logger.error(f"{' '.join(cmd)} failed: {result.stderr.decode(errors='replace')}")
            return "I couldn't do that, sir."
        except FileNotFoundError:
            return "That's not available on this system, sir."
        except subprocess.TimeoutExpired:
            return ok_message  # shutdown/reboot/suspend often don't return before the system acts

    # --- volume ----------------------------------------------------------------

    def _handle_volume(self, t: str) -> str:
        m = _VOLUME_SET_RE.search(t)
        if m:
            pct = m.group(1)
            return self._run(
                ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{pct}%"],
                f"Volume set to {pct} percent, sir.",
            )
        if any(kw in t for kw in ("up", "increase", "louder", "raise")):
            return self._run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "5%+"], "Turned it up, sir.")
        if any(kw in t for kw in ("down", "decrease", "quieter", "lower")):
            return self._run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"], "Turned it down, sir.")
        return "Would you like the volume up or down, sir?"

    # --- info: disk / battery / cpu / memory ------------------------------------

    def _disk_space(self) -> str:
        total, used, free = shutil.disk_usage("/")
        free_gb = free // (2**30)
        total_gb = total // (2**30)
        return f"You have {free_gb} gigabytes free out of {total_gb}, sir."

    def _battery(self) -> str:
        if psutil is None:
            return "I can't check the battery on this system, sir."
        battery = psutil.sensors_battery()
        if battery is None:
            return "There's no battery on this system, sir."
        state = "charging" if battery.power_plugged else "on battery"
        return f"The battery is at {round(battery.percent)} percent, {state}, sir."

    def _resource_usage(self, t: str) -> str:
        if psutil is None:
            return "I can't check that on this system, sir."
        if "cpu" in t:
            return f"CPU usage is at {round(psutil.cpu_percent(interval=0.3))} percent, sir."
        return f"Memory usage is at {round(psutil.virtual_memory().percent)} percent, sir."

    # --- screenshot --------------------------------------------------------------

    def _screenshot(self) -> str:
        pictures_dir = Path.home() / "Pictures"
        pictures_dir.mkdir(exist_ok=True)
        filename = pictures_dir / f"screenshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        try:
            result = subprocess.run(["scrot", str(filename)], capture_output=True, timeout=5)
            if result.returncode == 0:
                return f"Done, sir. Saved to {filename.name}."
            return "I couldn't take a screenshot, sir."
        except FileNotFoundError:
            return "I don't have a screenshot tool available, sir."

    # --- brightness ----------------------------------------------------------------

    def _handle_brightness(self, t: str) -> str:
        m = _BRIGHTNESS_SET_RE.search(t)
        if m:
            pct = m.group(1)
            return self._run(["brightnessctl", "set", f"{pct}%"], f"Brightness set to {pct} percent, sir.")
        if any(kw in t for kw in ("up", "increase", "brighter", "raise")):
            return self._run(["brightnessctl", "set", "10%+"], "Brightened it up, sir.")
        if any(kw in t for kw in ("down", "decrease", "dimmer", "lower", "dim")):
            return self._run(["brightnessctl", "set", "10%-"], "Dimmed it down, sir.")
        return "Would you like the screen brighter or dimmer, sir?"

    # --- network -------------------------------------------------------------------

    def _network_status(self, t: str) -> str:
        # `ip route get` doubles as both a connectivity check (does it resolve a
        # route at all?) and an IP lookup (its output includes "src <local-ip>") -
        # more portable than `hostname -I`, which isn't supported by every
        # `hostname` implementation (isn't on this machine's, for instance).
        try:
            result = subprocess.run(
                ["ip", "route", "get", "1.1.1.1"], capture_output=True, text=True, timeout=3
            )
        except Exception:
            return "I couldn't check your connection, sir."

        if result.returncode != 0:
            return "It looks like you're offline, sir."
        if "ip address" not in t:
            return "Yes, you're connected to the internet, sir."

        match = re.search(r"src (\S+)", result.stdout)
        return f"Your IP address is {match.group(1)}, sir." if match else "I couldn't determine your IP address, sir."

    # --- apps ------------------------------------------------------------------------

    def _resolve_app(self, t: str):
        target = t[len("open "):].strip().rstrip("?.! ") if t.startswith("open ") else t
        for phrase, binary in _APPS.items():
            if phrase in target and shutil.which(binary):
                return binary
        return None

    def _open_app(self, t: str) -> str:
        binary = self._resolve_app(t)
        if not binary:
            return "I don't know how to open that, sir."
        try:
            subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Opening {binary}, sir."
        except Exception as e:
            logger.error(f"failed to launch {binary}: {e}")
            return f"I couldn't open {binary}, sir."
