import pytest

from cs2_vision_trainer.config import SafetyConfig


def test_default_safety_config_is_read_only():
    config = SafetyConfig()

    assert config.allow_game_memory_access is False
    assert config.allow_input_control is False
    assert config.allow_process_injection is False
    assert config.allow_in_game_overlay is False
    config.validate()


def test_safety_config_rejects_input_control():
    config = SafetyConfig(allow_input_control=True)

    with pytest.raises(ValueError, match="input control"):
        config.validate()


def test_safety_config_rejects_process_injection():
    config = SafetyConfig(allow_process_injection=True)

    with pytest.raises(ValueError, match="process injection"):
        config.validate()
