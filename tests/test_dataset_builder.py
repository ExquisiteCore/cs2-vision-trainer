from pathlib import Path

import yaml

from cs2_vision_trainer.dataset_builder import DatasetBuildOptions, build_yolo_dataset
from cs2_vision_trainer.dataset.schema import DEFAULT_CLASS_NAMES


def write_pair(root: Path, name: str, label: str | None) -> None:
    (root / "images" / "raw").mkdir(parents=True, exist_ok=True)
    (root / "labels" / "raw").mkdir(parents=True, exist_ok=True)
    (root / "images" / "raw" / f"{name}.jpg").write_bytes(b"fake image")
    if label is not None:
        (root / "labels" / "raw" / f"{name}.txt").write_text(label, encoding="utf-8")


def test_build_yolo_dataset_copies_labeled_images_and_generates_yaml(tmp_path):
    raw_root = tmp_path / "raw"
    output_root = tmp_path / "dataset"
    write_pair(raw_root, "a", "0 0.5 0.5 0.1 0.1\n")
    write_pair(raw_root, "b", "0 0.4 0.4 0.2 0.2\n")
    write_pair(raw_root, "c", "0 0.3 0.3 0.3 0.3\n")

    summary = build_yolo_dataset(
        raw_images_dir=raw_root / "images" / "raw",
        raw_labels_dir=raw_root / "labels" / "raw",
        output_root=output_root,
        options=DatasetBuildOptions(
            val_ratio=1 / 3,
            seed=1,
            include_empty=False,
            class_names=("ct_body",),
        ),
    )

    assert summary.total_examples == 3
    assert summary.train_examples == 2
    assert summary.val_examples == 1
    dataset = yaml.safe_load((output_root / "dataset.yaml").read_text(encoding="utf-8"))
    assert dataset["train"] == "images/train"
    assert dataset["val"] == "images/val"
    assert dataset["names"] == {0: "ct_body"}
    assert len(list((output_root / "images" / "train").glob("*.jpg"))) == 2
    assert len(list((output_root / "labels" / "val").glob("*.txt"))) == 1


def test_dataset_builder_defaults_to_multiclass_cs2_schema(tmp_path):
    raw_root = tmp_path / "raw"
    output_root = tmp_path / "dataset"
    write_pair(raw_root, "a", "0 0.5 0.5 0.1 0.1\n")

    build_yolo_dataset(
        raw_images_dir=raw_root / "images" / "raw",
        raw_labels_dir=raw_root / "labels" / "raw",
        output_root=output_root,
        options=DatasetBuildOptions(val_ratio=0, include_empty=False),
    )

    dataset = yaml.safe_load((output_root / "dataset.yaml").read_text(encoding="utf-8"))
    assert dataset["names"] == {index: name for index, name in enumerate(DEFAULT_CLASS_NAMES)}


def test_build_yolo_dataset_can_keep_limited_empty_labels(tmp_path):
    raw_root = tmp_path / "raw"
    output_root = tmp_path / "dataset"
    write_pair(raw_root, "has_ct", "0 0.5 0.5 0.1 0.1\n")
    write_pair(raw_root, "empty_a", "")
    write_pair(raw_root, "empty_b", "")

    summary = build_yolo_dataset(
        raw_images_dir=raw_root / "images" / "raw",
        raw_labels_dir=raw_root / "labels" / "raw",
        output_root=output_root,
        options=DatasetBuildOptions(
            val_ratio=0.5,
            seed=1,
            include_empty=True,
            empty_limit=1,
        ),
    )

    assert summary.total_examples == 2
    assert summary.empty_examples == 1
