from cs2_vision_trainer.annotation import (
    AnnotationBox,
    collect_image_paths,
    filter_images_missing_labels,
    load_yolo_labels,
    pixel_box_to_yolo,
    point_in_box,
    save_yolo_labels,
    yolo_to_pixel_box,
)


def test_pixel_box_to_yolo_normalizes_center_and_size():
    values = pixel_box_to_yolo((10, 20, 30, 60), image_width=100, image_height=200)

    assert values == (0.2, 0.2, 0.2, 0.2)


def test_yolo_to_pixel_box_restores_clamped_coordinates():
    box = yolo_to_pixel_box((0.2, 0.2, 0.2, 0.2), image_width=100, image_height=200)

    assert box == (10, 20, 30, 60)


def test_save_and_load_yolo_labels_round_trip(tmp_path):
    label_path = tmp_path / "image.txt"
    boxes = [AnnotationBox(class_index=0, xyxy=(10, 20, 30, 60))]

    save_yolo_labels(label_path, boxes, image_width=100, image_height=200)
    loaded = load_yolo_labels(label_path, image_width=100, image_height=200)

    assert loaded == boxes


def test_save_yolo_labels_can_write_empty_label_file(tmp_path):
    label_path = tmp_path / "empty.txt"

    save_yolo_labels(label_path, [], image_width=100, image_height=200)

    assert label_path.exists()
    assert label_path.read_text(encoding="utf-8") == ""


def test_collect_image_paths_keeps_supported_images_sorted(tmp_path):
    (tmp_path / "b.jpg").write_bytes(b"")
    (tmp_path / "a.png").write_bytes(b"")
    (tmp_path / "note.txt").write_text("ignore", encoding="utf-8")

    paths = collect_image_paths(tmp_path)

    assert [path.name for path in paths] == ["a.png", "b.jpg"]


def test_collect_image_paths_can_filter_by_pattern(tmp_path):
    (tmp_path / "xxx_01_error_000001.jpg").write_bytes(b"")
    (tmp_path / "xxx_01_error_000002.jpg").write_bytes(b"")
    (tmp_path / "xxx_01_frame_000010.jpg").write_bytes(b"")

    paths = collect_image_paths(tmp_path, pattern="xxx_01_error_*.jpg")

    assert [path.name for path in paths] == [
        "xxx_01_error_000001.jpg",
        "xxx_01_error_000002.jpg",
    ]


def test_filter_images_missing_labels_keeps_only_images_without_label_file(tmp_path):
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir()
    labels_dir.mkdir()
    labeled = images_dir / "labeled.jpg"
    missing = images_dir / "missing.jpg"
    labeled.write_bytes(b"")
    missing.write_bytes(b"")
    (labels_dir / "labeled.txt").write_text("", encoding="utf-8")

    paths = filter_images_missing_labels([labeled, missing], labels_dir)

    assert paths == [missing]


def test_point_in_box_detects_points_inside_existing_box():
    assert point_in_box((15, 25), (10, 20, 30, 60)) is True
    assert point_in_box((5, 25), (10, 20, 30, 60)) is False
