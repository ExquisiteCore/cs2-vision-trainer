from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from cs2_vision_trainer.detections import Box


@dataclass(frozen=True)
class AnnotationBox:
    class_index: int
    xyxy: Box


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


@dataclass
class AnnotatorState:
    image_paths: list[Path]
    labels_dir: Path
    class_index: int = 0
    current_index: int = 0
    boxes: list[AnnotationBox] | None = None
    drawing_start: tuple[int, int] | None = None
    drawing_current: tuple[int, int] | None = None
    dirty: bool = False

    @property
    def current_image_path(self) -> Path:
        return self.image_paths[self.current_index]

    @property
    def current_label_path(self) -> Path:
        return self.labels_dir / f"{self.current_image_path.stem}.txt"


def collect_image_paths(images_dir: Path, *, pattern: str = "*") -> list[Path]:
    if not images_dir.exists():
        raise FileNotFoundError(images_dir)
    return sorted(path for path in images_dir.glob(pattern) if path.suffix.lower() in IMAGE_SUFFIXES)


def filter_images_missing_labels(image_paths: list[Path], labels_dir: Path) -> list[Path]:
    return [path for path in image_paths if not (labels_dir / f"{path.stem}.txt").exists()]


def point_in_box(point: tuple[int, int], box: Box) -> bool:
    x, y = point
    x1, y1, x2, y2 = box
    return x1 <= x <= x2 and y1 <= y <= y2


def normalize_box(xyxy: Box, *, image_width: int, image_height: int) -> Box:
    x1, y1, x2, y2 = xyxy
    left = max(0, min(x1, x2, image_width))
    right = max(0, min(max(x1, x2), image_width))
    top = max(0, min(y1, y2, image_height))
    bottom = max(0, min(max(y1, y2), image_height))
    return left, top, right, bottom


def pixel_box_to_yolo(xyxy: Box, *, image_width: int, image_height: int) -> tuple[float, float, float, float]:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    x1, y1, x2, y2 = normalize_box(xyxy, image_width=image_width, image_height=image_height)
    box_width = x2 - x1
    box_height = y2 - y1
    center_x = x1 + box_width / 2
    center_y = y1 + box_height / 2
    return (
        center_x / image_width,
        center_y / image_height,
        box_width / image_width,
        box_height / image_height,
    )


def yolo_to_pixel_box(
    values: tuple[float, float, float, float],
    *,
    image_width: int,
    image_height: int,
) -> Box:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    center_x, center_y, width, height = values
    box_width = width * image_width
    box_height = height * image_height
    x1 = round(center_x * image_width - box_width / 2)
    y1 = round(center_y * image_height - box_height / 2)
    x2 = round(center_x * image_width + box_width / 2)
    y2 = round(center_y * image_height + box_height / 2)
    return normalize_box((x1, y1, x2, y2), image_width=image_width, image_height=image_height)


def load_yolo_labels(label_path: Path, *, image_width: int, image_height: int) -> list[AnnotationBox]:
    if not label_path.exists():
        return []
    boxes: list[AnnotationBox] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) != 5:
            raise ValueError(f"invalid YOLO label line in {label_path}: {line}")
        class_index = int(parts[0])
        values = tuple(float(part) for part in parts[1:])
        boxes.append(
            AnnotationBox(
                class_index=class_index,
                xyxy=yolo_to_pixel_box(values, image_width=image_width, image_height=image_height),
            )
        )
    return boxes


def save_yolo_labels(
    label_path: Path,
    boxes: list[AnnotationBox],
    *,
    image_width: int,
    image_height: int,
) -> None:
    label_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for box in boxes:
        center_x, center_y, width, height = pixel_box_to_yolo(
            box.xyxy,
            image_width=image_width,
            image_height=image_height,
        )
        if width <= 0 or height <= 0:
            continue
        lines.append(
            f"{box.class_index} "
            f"{center_x:.6f} "
            f"{center_y:.6f} "
            f"{width:.6f} "
            f"{height:.6f}"
        )
    content = "\n".join(lines)
    if content:
        content += "\n"
    label_path.write_text(content, encoding="utf-8")


def load_current_boxes(state: AnnotatorState, *, image_width: int, image_height: int) -> None:
    state.boxes = load_yolo_labels(
        state.current_label_path,
        image_width=image_width,
        image_height=image_height,
    )
    state.dirty = False
    state.drawing_start = None
    state.drawing_current = None


def save_current_boxes(state: AnnotatorState, *, image_width: int, image_height: int) -> None:
    save_yolo_labels(
        state.current_label_path,
        state.boxes or [],
        image_width=image_width,
        image_height=image_height,
    )
    state.dirty = False


def draw_annotation_overlay(
    image_bgr: np.ndarray,
    *,
    state: AnnotatorState,
    image_width: int,
    image_height: int,
) -> np.ndarray:
    output = image_bgr.copy()
    for index, box in enumerate(state.boxes or []):
        x1, y1, x2, y2 = box.xyxy
        cv2.rectangle(output, (x1, y1), (x2, y2), (40, 220, 40), 2)
        cv2.putText(
            output,
            f"enemy {index + 1}",
            (x1, max(20, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (40, 220, 40),
            2,
            cv2.LINE_AA,
        )
    if state.drawing_start and state.drawing_current:
        x1, y1 = state.drawing_start
        x2, y2 = state.drawing_current
        preview = normalize_box((x1, y1, x2, y2), image_width=image_width, image_height=image_height)
        cv2.rectangle(output, preview[:2], preview[2:], (40, 180, 255), 2)

    _draw_annotation_help(output, state=state)
    return output


def _draw_annotation_help(output: np.ndarray, *, state: AnnotatorState) -> None:
    height, _ = output.shape[:2]
    status = "dirty" if state.dirty else "saved"
    lines = [
        f"{state.current_index + 1}/{len(state.image_paths)} {state.current_image_path.name} {status}",
        "Left drag box | Right click delete | S save | A/D prev/next | Space next | Q quit",
    ]
    y = 28
    for line in lines:
        cv2.putText(
            output,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        y += 26
    cv2.putText(
        output,
        "Labels are saved as YOLO txt files.",
        (12, max(height - 16, 16)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
