"""Network diagnostics skill: ping a host, check if a TCP port is open.

Deliberately scoped narrow - one host, one port, a couple of ping packets.
Not a port scanner: this machine already has dedicated recon tooling for
that, and a voice assistant utility skill shouldn't casually grow into one.
"""

import re
import socket
import subprocess
from .base import Skill
from loguru import logger

_PING_RE = re.compile(r"^ping\s+([\w.-]+)", re.IGNORECASE)
_PORT_ON_RE = re.compile(
    r"port\s+(\d{1,5})\s+(?:is\s+)?open\s+on\s+([\w.-]+)|port\s+(\d{1,5})\s+on\s+([\w.-]+)",
    re.IGNORECASE,
)
_HOST_PORT_RE = re.compile(r"([\w.-]+)\s+port\s+(\d{1,5})", re.IGNORECASE)

PING_COUNT = 2
PING_WAIT = 1
PORT_TIMEOUT = 3.0


class NetworkCheckSkill(Skill):
    name = "network_check"

    def matches(self, text: str) -> bool:
        t = text.lower().strip()
        return bool(_PING_RE.match(t)) or self._extract_port_check(t) is not None

    def _extract_port_check(self, t: str):
        m = _PORT_ON_RE.search(t)
        if m:
            port = m.group(1) or m.group(3)
            host = m.group(2) or m.group(4)
            return host, int(port)
        m = _HOST_PORT_RE.search(t)
        if m:
            return m.group(1), int(m.group(2))
        return None

    def handle(self, text: str) -> str:
        t = text.lower().strip()

        ping_match = _PING_RE.match(t)
        if ping_match:
            return self._ping(ping_match.group(1))

        port_check = self._extract_port_check(t)
        if port_check:
            host, port = port_check
            return self._check_port(host, port)

        return "I didn't catch what to check, sir."

    def _ping(self, host: str) -> str:
        try:
            result = subprocess.run(
                ["ping", "-c", str(PING_COUNT), "-W", str(PING_WAIT), host],
                capture_output=True, text=True, timeout=PING_COUNT * PING_WAIT + 3,
            )
        except FileNotFoundError:
            return "I don't have ping available on this system, sir."
        except subprocess.TimeoutExpired:
            return f"{host} isn't responding, sir."

        if result.returncode != 0:
            return f"I couldn't reach {host}, sir."

        match = re.search(r"= [\d.]+/([\d.]+)/[\d.]+", result.stdout)
        if match:
            avg_ms = round(float(match.group(1)))
            return f"{host} is up, sir - average round trip is {avg_ms} milliseconds."
        return f"{host} is up, sir."

    def _check_port(self, host: str, port: int) -> str:
        # socket.create_connection((host, port)) resolves ALL addresses (a host
        # with both IPv4 and IPv6 records) and retries each with the FULL
        # timeout on failure - worst case is timeout * address count, not
        # timeout (measured 6s from a nominal "3s" against a filtered port on
        # a dual-stack host). Resolving once and connecting to a single
        # address bounds it to one attempt.
        try:
            family, socktype, proto, _, sockaddr = socket.getaddrinfo(
                host, port, proto=socket.IPPROTO_TCP
            )[0]
        except socket.gaierror:
            return f"I couldn't resolve {host}, sir."

        try:
            with socket.socket(family, socktype, proto) as sock:
                sock.settimeout(PORT_TIMEOUT)
                sock.connect(sockaddr)
            return f"Port {port} is open on {host}, sir."
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            logger.info(f"port check {host}:{port} failed: {e}")
            return f"Port {port} appears closed on {host}, sir."
