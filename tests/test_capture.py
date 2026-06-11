from pathlib import Path

from cs2_vision_trainer.capture import parse_source_spec


def test_parse_source_spec_accepts_screen_source():
    spec = parse_source_spec("screen")

    assert spec.kind == "screen"
    assert spec.value == "screen"


def test_parse_source_spec_accepts_camera_index():
    spec = parse_source_spec("0")

    assert spec.kind == "camera"
    assert spec.value == 0


def test_parse_source_spec_treats_other_values_as_video_paths():
    spec = parse_source_spec(r"D:\clips\training.mp4")

    assert spec.kind == "video"
    assert spec.value == Path(r"D:\clips\training.mp4")
