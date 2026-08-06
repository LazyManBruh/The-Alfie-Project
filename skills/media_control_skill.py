"""Media control skill: play music and control playback.

No local music library and no streaming service account configured on this
machine, so "play <something>" resolves a YouTube audio URL via yt-dlp and
streams it with mpv (audio only). Bare transport commands (pause/resume/
stop/next/previous) control that mpv instance directly through its IPC
socket when we're the one who started it; otherwise they fall back to
playerctl, in case some other MPRIS-aware player (e.g. a browser tab) is
running instead.

Known limitation: this streams one track at a time, resolved fresh per
request - there's no queue, so "next"/"previous" aren't meaningful for
something we started and just say so rather than pretending to support it.
"""

import json
import os
import socket
import subprocess
from .base import Skill
from loguru import logger

IPC_SOCKET = "/tmp/alfie-mpv.sock"

_FILLER_WORDS = {"some", "the", "a", "please", "me", "for", "us", "music", "song", "songs"}

_ACTION_KEYWORDS = {
    "pause": ["pause"],
    "resume": ["resume", "unpause", "play"],
    "stop": ["stop"],
    "next": ["next", "skip"],
    "previous": ["previous", "prev", "back"],
}
_CONTEXT_KEYWORDS = ["music", "song", "track", "player", "playback"]


class MediaControlSkill(Skill):
    name = "media_control"

    def __init__(self, context=None):
        super().__init__(context)
        self._process = None

    # --- routing ---------------------------------------------------------

    def matches(self, text: str) -> bool:
        t = text.lower().strip()
        if t.startswith("play") and self._search_query(t):
            return True
        return self._transport_action(t) is not None

    def handle(self, text: str) -> str:
        t = text.lower().strip()
        query = self._search_query(t) if t.startswith("play") else ""
        if query:
            return self._play(query)
        return self._transport(self._transport_action(t))

    # --- "play <query>": search + stream ----------------------------------

    def _search_query(self, t: str) -> str:
        if not t.startswith("play"):
            return ""
        remainder = t[len("play"):].strip()
        words = [w for w in remainder.split() if w not in _FILLER_WORDS]
        return " ".join(words)

    def _play(self, query: str) -> str:
        self._stop_process()
        try:
            result = subprocess.run(
                ["yt-dlp", "-f", "bestaudio", "-g", f"ytsearch1:{query}"],
                capture_output=True, text=True, timeout=20,
            )
        except FileNotFoundError:
            return "I need yt-dlp installed to stream music, sir."
        except subprocess.TimeoutExpired:
            return f"The search for {query} is taking too long, sir."

        url = next((ln.strip() for ln in reversed(result.stdout.splitlines()) if ln.strip()), None)
        if not url:
            logger.error(f"yt-dlp found nothing for {query!r}: {result.stderr.strip()[-300:]}")
            return f"I couldn't find anything for {query}, sir."

        if os.path.exists(IPC_SOCKET):
            os.unlink(IPC_SOCKET)
        self._process = subprocess.Popen(
            ["mpv", "--no-video", "--no-terminal", f"--input-ipc-server={IPC_SOCKET}", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return f"Playing {query}, sir."

    # --- transport control -------------------------------------------------

    def _transport_action(self, t: str):
        has_context = any(kw in t for kw in _CONTEXT_KEYWORDS)
        for action, keywords in _ACTION_KEYWORDS.items():
            if any(kw in t for kw in keywords) and (has_context or self._own_player_active()):
                return action
        return None

    def _own_player_active(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _transport(self, action):
        if not action:
            return "I didn't catch which media action you wanted, sir."

        if self._own_player_active():
            if action == "pause":
                return self._send_ipc({"command": ["set_property", "pause", True]}, "Paused, sir.")
            if action == "resume":
                return self._send_ipc({"command": ["set_property", "pause", False]}, "Resuming, sir.")
            if action == "stop":
                self._stop_process()
                return "Stopped, sir."
            if action in ("next", "previous"):
                return "I can only play one track at a time for now, sir."

        # No stream of ours running - try controlling some other MPRIS player
        # (a browser tab playing something, for instance) via playerctl.
        playerctl_action = "play" if action == "resume" else action
        try:
            result = subprocess.run(["playerctl", playerctl_action], capture_output=True, timeout=5)
            if result.returncode == 0:
                return f"{action.capitalize()}d, sir."
            return f"There's nothing playing for me to {action}, sir."
        except FileNotFoundError:
            return "There's nothing playing right now, sir."
        except Exception:
            return "Something went wrong controlling playback, sir."

    # --- mpv IPC + process management --------------------------------------

    def _send_ipc(self, command: dict, ok_message: str) -> str:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(2.0)
                sock.connect(IPC_SOCKET)
                sock.sendall((json.dumps(command) + "\n").encode("utf-8"))
            return ok_message
        except OSError as e:
            logger.error(f"mpv IPC command failed: {e}")
            return "I lost the connection to the player, sir."

    def _stop_process(self):
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
        self._process = None
        if os.path.exists(IPC_SOCKET):
            try:
                os.unlink(IPC_SOCKET)
            except OSError:
                pass
