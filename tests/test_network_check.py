"""Network check skill: ping and single-port TCP checks.

The mocked timing test below is a real regression test, not a style
preference: `socket.create_connection` resolves every address a host has
(IPv4 + IPv6) and retries each with the FULL timeout on failure, so a
filtered port on a dual-stack host took 6s from a nominal "3s" timeout
before this was fixed to resolve once and connect to a single address.
"""

import socket
import time
from unittest.mock import patch, MagicMock
import pytest
from alfie_assistant.skills.network_check_skill import NetworkCheckSkill, PORT_TIMEOUT


@pytest.fixture
def skill():
    return NetworkCheckSkill()


def test_matches_ping_and_port_phrasing(skill):
    assert skill.matches("ping google.com")
    assert skill.matches("is port 443 open on google.com")
    assert skill.matches("check port 443 on google.com")
    assert skill.matches("google.com port 443")


def test_does_not_match_unrelated_text(skill):
    assert not skill.matches("what is 15 times 23")
    assert not skill.matches("convert 10 miles to kilometers")


def test_ping_parses_real_output_format(skill):
    fake_result = MagicMock(
        returncode=0,
        stdout="rtt min/avg/max/mdev = 9.893/12.450/15.001/2.1 ms\n",
    )
    with patch("subprocess.run", return_value=fake_result):
        response = skill.handle("ping google.com")
    assert response == "google.com is up, sir - average round trip is 12 milliseconds."


def test_ping_unreachable_reported_gracefully(skill):
    fake_result = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=fake_result):
        response = skill.handle("ping nonexistent.invalid")
    assert "couldn't reach" in response.lower()


def test_port_check_bounded_to_single_timeout_on_failure(skill):
    """Regression test: this must take ~PORT_TIMEOUT, not PORT_TIMEOUT times
    the number of addresses the host resolves to."""
    fake_sock = MagicMock()
    fake_sock.__enter__.return_value = fake_sock
    fake_sock.connect.side_effect = socket.timeout("timed out")

    with patch("socket.getaddrinfo", return_value=[
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", 443)),
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 443)),
    ]), patch("socket.socket", return_value=fake_sock):
        t0 = time.time()
        response = skill.handle("is port 443 open on example.com")
        elapsed = time.time() - t0

    assert "closed" in response.lower()
    # Only the first resolved address should ever be tried.
    assert fake_sock.connect.call_count == 1
    assert elapsed < 0.5  # connect() is mocked, so this should be near-instant


def test_port_check_reports_unresolvable_host(skill):
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("not found")):
        response = skill.handle("is port 443 open on nonexistent.invalid")
    assert "couldn't resolve" in response.lower()


@pytest.mark.integration
def test_real_ping_and_port_check(skill):
    assert "up" in skill.handle("ping google.com").lower()
    assert "open" in skill.handle("is port 443 open on google.com").lower()
