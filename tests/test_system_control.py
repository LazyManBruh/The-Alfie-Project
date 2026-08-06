"""System control skill. Disk space and network status are tested for real
(read-only, near-instant, no real network round-trip needed for `ip route
get`). Everything else that would change real system state - volume,
brightness, screen lock - or that's genuinely destructive (shutdown/reboot)
is mocked; the shutdown/reboot commands are never actually executed, not
even here."""

from unittest.mock import patch, MagicMock
import pytest
from alfie_assistant.skills.system_control_skill import SystemControlSkill, CONFIRMATION_TIMEOUT


@pytest.fixture
def skill():
    return SystemControlSkill()


def test_shutdown_requires_confirmation_before_acting(skill):
    assert skill.handle("shut down the computer") == "Are you sure you'd like to shut down, sir?"
    with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
        assert skill.handle("yes") == "Shutting down now, sir."
    assert mock_run.call_args[0][0] == ["systemctl", "poweroff"]


def test_shutdown_cancelled_on_no(skill):
    skill.handle("shut down the computer")
    with patch("subprocess.run") as mock_run:
        assert skill.handle("no thanks") == "Understood, sir. Cancelled."
    mock_run.assert_not_called()


def test_reboot_requires_confirmation(skill):
    assert skill.handle("restart the computer") == "Are you sure you'd like to restart, sir?"
    with patch("subprocess.run", return_value=MagicMock(returncode=0)):
        assert skill.handle("go ahead") == "Restarting now, sir."


def test_stale_confirmation_expires_and_does_not_swallow_next_command(skill):
    skill.handle("restart the computer")
    skill._pending_confirmation_at -= (CONFIRMATION_TIMEOUT + 5)
    assert not skill._confirmation_pending()
    assert not skill.matches("what time is it")


def test_suspend_and_lock_execute_immediately_without_confirmation(skill):
    with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
        assert skill.handle("suspend the computer") == "Suspending now, sir."
        assert mock_run.call_args[0][0] == ["systemctl", "suspend"]

        skill.handle("lock the screen")
        assert mock_run.call_args[0][0] == ["loginctl", "lock-session"]


def test_disk_space_real(skill):
    assert "gigabytes free" in skill.handle("how much disk space do i have")


def test_network_status_real(skill):
    assert "sir" in skill.handle("am i connected to the internet").lower()
