import pytest

from cs2_vision_trainer.config import PreviewConfig


def test_preview_config_accepts_valid_model_and_confidence():
    config = PreviewConfig(model="runs/detect/train/weights/best.pt")

    assert config.source == "screen"
    assert config.confidence == 0.25
    config.validate()


def test_preview_config_rejects_invalid_confidence():
    config = PreviewConfig(model="model.pt", confidence=1.5)

    with pytest.raises(ValueError, match="confidence"):
        config.validate()


def test_preview_config_rejects_missing_model():
    config = PreviewConfig(model="")

    with pytest.raises(ValueError, match="model path"):
        config.validate()
