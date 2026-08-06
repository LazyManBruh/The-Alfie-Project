"""Media control skill: play/pause/resume/stop, with yt-dlp/mpv/playerctl
mocked out so the test suite doesn't spawn real processes or hit the network."""

from unittest.mock import patch, MagicMock
import pytest
from alfie_assistant.skills.media_control_skill import MediaControlSkill


@pytest.fixture
def skill():
    return MediaControlSkill()


def test_play_resolves_and_launches_mpv(skill):
    fake_resolve = MagicMock(stdout="https://example.com/audio.webm\n", returncode=0)
    fake_process = MagicMock()
    fake_process.poll.return_value = None  # still running

    with patch("subprocess.run", return_value=fake_resolve), \
         patch("subprocess.Popen", return_value=fake_process) as mock_popen:
        response = skill.handle("play bohemian rhapsody by queen")

    assert response == "Playing bohemian rhapsody by queen, sir."
    launched_cmd = mock_popen.call_args[0][0]
    assert launched_cmd[0] == "mpv"
    assert "https://example.com/audio.webm" in launched_cmd


def test_play_reports_no_results(skill):
    fake_resolve = MagicMock(stdout="", returncode=1, stderr=b"no results")
    with patch("subprocess.run", return_value=fake_resolve):
        response = skill.handle("play some incredibly obscure nonexistent song")
    assert "couldn't find" in response.lower()


def test_pause_resume_stop_control_own_process(skill):
    fake_process = MagicMock()
    fake_process.poll.return_value = None
    skill._process = fake_process  # simulate an already-playing track

    with patch("socket.socket") as mock_socket_cls:
        mock_socket_cls.return_value.__enter__.return_value = MagicMock()
        assert skill.handle("pause") == "Paused, sir."
        assert skill.handle("resume") == "Resuming, sir."

    assert skill.handle("stop") == "Stopped, sir."
    fake_process.terminate.assert_called_once()


def test_next_not_supported_while_playing(skill):
    fake_process = MagicMock()
    fake_process.poll.return_value = None
    skill._process = fake_process
    assert "one track at a time" in skill.handle("skip this song").lower()


def test_falls_back_to_playerctl_when_nothing_playing(skill):
    fake_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake_result) as mock_run:
        response = skill.handle("pause the music")
    assert response == "Paused, sir."
    assert mock_run.call_args[0][0] == ["playerctl", "pause"]
