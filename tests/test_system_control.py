"""System control skill. Disk space and network status are tested for real
(read-only, near-instant, no real network round-trip needed for `ip route
get`). Everything else that would change real system state - volume,
brightness, screen lock - or that's genuinely destructive (shutdown/reboot)
is mocked; the shutdown/reboot commands are never actually executed, not
even here."""

import glob
import os
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


def test_open_unknown_app(skill):
    assert skill.handle("open some obscure unlisted thing") == "I don't know how to open that, sir."


def test_open_app_success_cleans_up_stderr_file(skill):
    def fake_popen(cmd, stdout=None, stderr=None):
        process = MagicMock()
        process.poll.return_value = None  # still running
        return process

    leftover_before = set(glob.glob("/tmp/*-firefox-stderr.log*"))
    with patch("subprocess.Popen", side_effect=fake_popen):
        response = skill.handle("open firefox")
    leftover_after = set(glob.glob("/tmp/*-firefox-stderr.log*"))

    assert response == "Opening firefox, sir."
    assert leftover_after == leftover_before  # no temp file left behind


def test_open_app_that_exits_immediately_reports_and_logs_stderr(skill):
    """Regression test: this used to discard stderr entirely (DEVNULL), so a
    launch failure left zero trace anywhere. Now it should be captured and
    logged, and the response should say it failed instead of claiming success.

    (loguru doesn't route through stdlib logging here, so pytest's `caplog`
    can't see it - patching the module's `logger` directly instead.)
    """

    def fake_popen(cmd, stdout=None, stderr=None):
        stderr.write("some real startup error\n")
        stderr.flush()
        process = MagicMock()
        process.poll.return_value = 1  # exited already, non-zero
        return process

    leftover_before = set(glob.glob("/tmp/*-firefox-stderr.log*"))
    with patch("subprocess.Popen", side_effect=fake_popen), \
         patch("alfie_assistant.skills.system_control_skill.logger") as mock_logger:
        response = skill.handle("open firefox")
    leftover_after = set(glob.glob("/tmp/*-firefox-stderr.log*"))

    assert response == "I couldn't open firefox, sir - it closed immediately."
    logged_message = mock_logger.error.call_args[0][0]
    assert "some real startup error" in logged_message
    assert leftover_after == leftover_before  # no temp file left behind


def test_disk_space_real(skill):
    assert "gigabytes free" in skill.handle("how much disk space do i have")


def test_network_status_real(skill):
    assert "sir" in skill.handle("am i connected to the internet").lower()
