from argparse import Namespace
from pathlib import Path

from cs2_vision_trainer.app.dataset_commands import prepare_dataset
from cs2_vision_trainer.dataset.validation import validate_yolo_dataset


def write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake image")


def write_label(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_validate_yolo_dataset_reports_missing_label_file(tmp_path):
    images = tmp_path / "images" / "raw"
    labels = tmp_path / "labels" / "raw"
    write_image(images / "frame.jpg")
    labels.mkdir(parents=True)

    summary = validate_yolo_dataset(raw_images_dir=images, raw_labels_dir=labels)

    assert summary.image_count == 1
    assert summary.label_count == 0
    assert [issue.code for issue in summary.issues] == ["missing_label"]


def test_validate_yolo_dataset_reports_missing_raw_directories(tmp_path):
    summary = validate_yolo_dataset(
        raw_images_dir=tmp_path / "images" / "raw",
        raw_labels_dir=tmp_path / "labels" / "raw",
    )

    assert summary.image_count == 0
    assert summary.label_count == 0
    assert [issue.code for issue in summary.issues] == ["missing_images_dir", "missing_labels_dir"]


def test_validate_yolo_dataset_reports_invalid_class_id(tmp_path):
    images = tmp_path / "images" / "raw"
    labels = tmp_path / "labels" / "raw"
    write_image(images / "frame.jpg")
    write_label(labels / "frame.txt", "9 0.5 0.5 0.2 0.2\n")

    summary = validate_yolo_dataset(raw_images_dir=images, raw_labels_dir=labels)

    assert summary.box_count == 1
    assert [issue.code for issue in summary.issues] == ["invalid_class"]


def test_validate_yolo_dataset_allows_small_boundary_rounding_error(tmp_path):
    images = tmp_path / "images" / "raw"
    labels = tmp_path / "labels" / "raw"
    write_image(images / "frame.jpg")
    write_label(labels / "frame.txt", "0 0.748437 0.653704 0.196875 0.692593\n")

    summary = validate_yolo_dataset(raw_images_dir=images, raw_labels_dir=labels)

    assert summary.box_count == 1
    assert summary.issues == []


def test_prepare_dataset_fails_when_validation_reports_issues(tmp_path, capsys):
    root = tmp_path / "dataset"
    write_image(root / "images" / "raw" / "frame.jpg")
    (root / "labels" / "raw").mkdir(parents=True)

    code = prepare_dataset(
        Namespace(
            root=str(root),
            val_ratio=0.2,
            seed=7,
            no_empty=False,
            empty_limit=100,
            class_names=(),
        )
    )

    assert code == 1
    assert "dataset validation failed" in capsys.readouterr().out
