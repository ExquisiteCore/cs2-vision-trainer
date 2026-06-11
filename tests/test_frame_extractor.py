import numpy as np

from cs2_vision_trainer.capture import Frame
from cs2_vision_trainer.frame_extractor import (
    FrameExtractionOptions,
    build_frame_path,
    extract_frames_from_source,
    should_save_frame,
)


class FakeFrameSource:
    def __init__(self, count: int):
        self.count = count
        self.index = 0
        self.released = False

    def read(self):
        if self.index >= self.count:
            return None
        frame = Frame(
            image=np.zeros((4, 4, 3), dtype=np.uint8),
            index=self.index,
            timestamp=float(self.index),
        )
        self.index += 1
        return frame

    def release(self):
        self.released = True


def test_should_save_frame_keeps_every_stride_frame():
    options = FrameExtractionOptions(stride=3)

    kept = [index for index in range(8) if should_save_frame(index, options)]

    assert kept == [0, 3, 6]


def test_build_frame_path_uses_zero_padded_frame_index(tmp_path):
    path = build_frame_path(tmp_path, video_stem="test", frame_index=42)

    assert path == tmp_path / "test_frame_000042.jpg"


def test_extract_frames_from_source_respects_max_frames_and_releases_source(tmp_path):
    source = FakeFrameSource(count=10)
    options = FrameExtractionOptions(stride=2, max_frames=3)

    summary = extract_frames_from_source(
        source,
        output_dir=tmp_path,
        video_stem="test",
        options=options,
    )

    assert summary.read_frames == 5
    assert summary.saved_frames == 3
    assert source.released is True
    assert sorted(path.name for path in tmp_path.glob("*.jpg")) == [
        "test_frame_000000.jpg",
        "test_frame_000002.jpg",
        "test_frame_000004.jpg",
    ]
