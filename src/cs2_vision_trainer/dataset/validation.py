from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cs2_vision_trainer.dataset.annotation import IMAGE_SUFFIXES
from cs2_vision_trainer.dataset.schema import DEFAULT_CLASS_NAMES, normalize_class_names

BOUNDARY_EPSILON = 1e-6


@dataclass(frozen=True)
class DatasetValidationIssue:
    code: str
    path: Path
    message: str


@dataclass(frozen=True)
class DatasetValidationSummary:
    image_count: int
    label_count: int
    box_count: int
    issues: list[DatasetValidationIssue]

    @property
    def ok(self) -> bool:
        return not self.issues


def validate_yolo_dataset(
    *,
    raw_images_dir: Path,
    raw_labels_dir: Path,
    class_names: tuple[str, ...] = DEFAULT_CLASS_NAMES,
) -> DatasetValidationSummary:
    names = normalize_class_names(class_names)
    issues: list[DatasetValidationIssue] = []
    if not raw_images_dir.exists():
        issues.append(
            DatasetValidationIssue(
                code="missing_images_dir",
                path=raw_images_dir,
                message=f"raw image directory does not exist: {raw_images_dir}",
            )
        )
    if not raw_labels_dir.exists():
        issues.append(
            DatasetValidationIssue(
                code="missing_labels_dir",
                path=raw_labels_dir,
                message=f"raw label directory does not exist: {raw_labels_dir}",
            )
        )
    if issues:
        return DatasetValidationSummary(
            image_count=0,
            label_count=0,
            box_count=0,
            issues=issues,
        )

    images = sorted(path for path in raw_images_dir.glob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
    labels = sorted(path for path in raw_labels_dir.glob("*.txt") if path.name != "classes.txt")
    image_stems = {path.stem: path for path in images}
    label_stems = {path.stem: path for path in labels}
    box_count = 0

    for stem, image_path in image_stems.items():
        if stem not in label_stems:
            issues.append(
                DatasetValidationIssue(
                    code="missing_label",
                    path=image_path,
                    message=f"image has no label file: {image_path.name}",
                )
            )

    for stem, label_path in label_stems.items():
        if stem not in image_stems:
            issues.append(
                DatasetValidationIssue(
                    code="missing_image",
                    path=label_path,
                    message=f"label has no matching image: {label_path.name}",
                )
            )
        box_count += _validate_label_file(label_path, class_count=len(names), issues=issues)

    return DatasetValidationSummary(
        image_count=len(images),
        label_count=len(labels),
        box_count=box_count,
        issues=issues,
    )


def _validate_label_file(
    label_path: Path,
    *,
    class_count: int,
    issues: list[DatasetValidationIssue],
) -> int:
    box_count = 0
    for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        box_count += 1
        parts = stripped.split()
        if len(parts) != 5:
            issues.append(_issue("malformed_line", label_path, line_number, "YOLO label line must have 5 fields"))
            continue
        try:
            class_index = int(parts[0])
        except ValueError:
            issues.append(_issue("invalid_class", label_path, line_number, "class id must be an integer"))
            continue
        if class_index < 0 or class_index >= class_count:
            issues.append(_issue("invalid_class", label_path, line_number, f"class id {class_index} is out of range"))
        try:
            values = [float(part) for part in parts[1:]]
        except ValueError:
            issues.append(_issue("invalid_number", label_path, line_number, "coordinates must be numbers"))
            continue
        center_x, center_y, width, height = values
        if not all(_inside_unit_interval(value) for value in values):
            issues.append(_issue("invalid_coordinate", label_path, line_number, "coordinates must be in [0, 1]"))
        if width <= 0 or height <= 0:
            issues.append(_issue("invalid_size", label_path, line_number, "width and height must be positive"))
        if center_x - width / 2 < -BOUNDARY_EPSILON or center_x + width / 2 > 1 + BOUNDARY_EPSILON:
            issues.append(_issue("box_out_of_bounds", label_path, line_number, "box x range leaves image bounds"))
        if center_y - height / 2 < -BOUNDARY_EPSILON or center_y + height / 2 > 1 + BOUNDARY_EPSILON:
            issues.append(_issue("box_out_of_bounds", label_path, line_number, "box y range leaves image bounds"))
    return box_count


def _inside_unit_interval(value: float) -> bool:
    return -BOUNDARY_EPSILON <= value <= 1 + BOUNDARY_EPSILON


def _issue(code: str, path: Path, line_number: int, message: str) -> DatasetValidationIssue:
    return DatasetValidationIssue(
        code=code,
        path=path,
        message=f"{path.name}:{line_number}: {message}",
    )
