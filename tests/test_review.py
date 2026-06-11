import numpy as np

from cs2_vision_trainer.review import (
    ProgressBarState,
    ReviewSaveOptions,
    build_review_frame_path,
    calculate_progress_bar,
    save_review_frame,
)


def test_build_review_frame_path_uses_next_available_index(tmp_path):
    (tmp_path / "xxx_01_error_000001.jpg").write_bytes(b"existing")

    path = build_review_frame_path(tmp_path, name="xxx_01")

    assert path == tmp_path / "xxx_01_error_000002.jpg"


def test_save_review_frame_writes_image_to_dataset_raw_dir(tmp_path):
    frame = np.zeros((8, 8, 3), dtype=np.uint8)

    path = save_review_frame(
        frame,
        ReviewSaveOptions(output_dir=tmp_path, name="xxx_01"),
    )

    assert path == tmp_path / "xxx_01_error_000001.jpg"
    assert path.exists()


def test_calculate_progress_bar_uses_current_frame_ratio():
    state = calculate_progress_bar(frame_index=24, total_frames=100, width=200)

    assert state == ProgressBarState(ratio=0.25, filled_width=50, label="25.0% frame 25/100")


def test_calculate_progress_bar_handles_unknown_total_frames():
    state = calculate_progress_bar(frame_index=0, total_frames=0, width=200)

    assert state == ProgressBarState(ratio=0.0, filled_width=0, label="0.0% frame 1/?")
