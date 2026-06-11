from __future__ import annotations

import random
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DatasetBuildOptions:
    val_ratio: float = 0.2
    seed: int = 7
    include_empty: bool = True
    empty_limit: int = 20
    class_names: tuple[str, ...] = ("enemy",)
    clear_output: bool = True

    def validate(self) -> None:
        if not 0 <= self.val_ratio < 1:
            raise ValueError("val_ratio must be in [0, 1)")
        if self.empty_limit < 0:
            raise ValueError("empty_limit must be greater than or equal to 0")
        if not self.class_names:
            raise ValueError("at least one class name is required")


@dataclass(frozen=True)
class DatasetExample:
    image_path: Path
    label_path: Path
    is_empty: bool


@dataclass(frozen=True)
class DatasetBuildSummary:
    total_examples: int
    train_examples: int
    val_examples: int
    empty_examples: int
    dataset_yaml: Path


def _is_label_file(path: Path) -> bool:
    return path.suffix.lower() == ".txt" and path.name != "classes.txt"


def _matching_image(raw_images_dir: Path, label_path: Path) -> Path | None:
    for suffix in (".jpg", ".jpeg", ".png", ".bmp"):
        candidate = raw_images_dir / f"{label_path.stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def collect_examples(
    *,
    raw_images_dir: Path,
    raw_labels_dir: Path,
    include_empty: bool,
    empty_limit: int,
) -> list[DatasetExample]:
    examples: list[DatasetExample] = []
    empty_examples: list[DatasetExample] = []
    for label_path in sorted(raw_labels_dir.glob("*.txt")):
        if not _is_label_file(label_path):
            continue
        image_path = _matching_image(raw_images_dir, label_path)
        if image_path is None:
            continue
        is_empty = label_path.read_text(encoding="utf-8").strip() == ""
        example = DatasetExample(image_path=image_path, label_path=label_path, is_empty=is_empty)
        if is_empty:
            empty_examples.append(example)
        else:
            examples.append(example)
    if include_empty and empty_limit > 0:
        examples.extend(empty_examples[:empty_limit])
    return examples


def _clear_split_dirs(output_root: Path) -> None:
    for relative in ("images/train", "images/val", "labels/train", "labels/val"):
        path = output_root / relative
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def _split_examples(
    examples: list[DatasetExample],
    *,
    val_ratio: float,
    seed: int,
) -> tuple[list[DatasetExample], list[DatasetExample]]:
    shuffled = list(examples)
    random.Random(seed).shuffle(shuffled)
    if len(shuffled) <= 1 or val_ratio == 0:
        return shuffled, []
    val_count = max(1, round(len(shuffled) * val_ratio))
    val_count = min(val_count, len(shuffled) - 1)
    return shuffled[val_count:], shuffled[:val_count]


def _copy_examples(output_root: Path, split: str, examples: list[DatasetExample]) -> None:
    image_dir = output_root / "images" / split
    label_dir = output_root / "labels" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    for example in examples:
        shutil.copy2(example.image_path, image_dir / example.image_path.name)
        shutil.copy2(example.label_path, label_dir / example.label_path.name)


def _write_dataset_yaml(output_root: Path, class_names: tuple[str, ...]) -> Path:
    dataset_yaml = output_root / "dataset.yaml"
    data = {
        "path": output_root.resolve().as_posix(),
        "train": "images/train",
        "val": "images/val",
        "names": {index: name for index, name in enumerate(class_names)},
    }
    dataset_yaml.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return dataset_yaml


def build_yolo_dataset(
    *,
    raw_images_dir: Path,
    raw_labels_dir: Path,
    output_root: Path,
    options: DatasetBuildOptions,
) -> DatasetBuildSummary:
    options.validate()
    if not raw_images_dir.exists():
        raise FileNotFoundError(raw_images_dir)
    if not raw_labels_dir.exists():
        raise FileNotFoundError(raw_labels_dir)

    examples = collect_examples(
        raw_images_dir=raw_images_dir,
        raw_labels_dir=raw_labels_dir,
        include_empty=options.include_empty,
        empty_limit=options.empty_limit,
    )
    if not examples:
        raise ValueError("no labeled examples found")

    if options.clear_output:
        _clear_split_dirs(output_root)

    train_examples, val_examples = _split_examples(
        examples,
        val_ratio=options.val_ratio,
        seed=options.seed,
    )
    _copy_examples(output_root, "train", train_examples)
    _copy_examples(output_root, "val", val_examples)
    dataset_yaml = _write_dataset_yaml(output_root, options.class_names)
    return DatasetBuildSummary(
        total_examples=len(examples),
        train_examples=len(train_examples),
        val_examples=len(val_examples),
        empty_examples=sum(1 for example in examples if example.is_empty),
        dataset_yaml=dataset_yaml,
    )
