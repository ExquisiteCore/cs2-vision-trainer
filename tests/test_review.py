import numpy as np

from cs2_vision_trainer.review import (
    ReviewSaveOptions,
    build_review_frame_path,
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
