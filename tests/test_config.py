"""Config loading, including default generation."""

from alfie_assistant.config import load_config


def test_generates_default_config(tmp_path):
    config_path = tmp_path / "config.yaml"
    assert not config_path.exists()

    config = load_config(str(config_path))

    assert config_path.exists()
    assert "calculator" in config.skills.enabled
    assert config.wake_word.model_path == "hey_jarvis"


def test_loads_existing_config_and_fills_in_defaults(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("llm:\n  model: some-other-model\n")

    config = load_config(str(config_path))

    assert config.llm.model == "some-other-model"
    # Fields not present in the file should still get their dataclass defaults.
    assert config.wake_word.sensitivity == 0.6
