from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class ReviewSaveOptions:
    output_dir: Path
    name: str
    jpeg_quality: int = 95

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("name is required")
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be between 1 and 100")


@dataclass(frozen=True)
class ProgressBarState:
    ratio: float
    filled_width: int
    label: str


def calculate_progress_bar(*, frame_index: int, total_frames: int, width: int) -> ProgressBarState:
    if width < 0:
        raise ValueError("width must be greater than or equal to 0")
    if total_frames <= 0:
        return ProgressBarState(ratio=0.0, filled_width=0, label=f"0.0% frame {frame_index + 1}/?")

    clamped_index = min(max(frame_index, 0), total_frames - 1)
    ratio = (clamped_index + 1) / total_frames
    filled_width = round(width * ratio)
    label = f"{ratio * 100:.1f}% frame {clamped_index + 1}/{total_frames}"
    return ProgressBarState(ratio=ratio, filled_width=filled_width, label=label)


def build_review_frame_path(output_dir: Path, *, name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        path = output_dir / f"{name}_error_{index:06d}.jpg"
        if not path.exists():
            return path
        index += 1


def save_review_frame(frame_bgr: np.ndarray, options: ReviewSaveOptions) -> Path:
    options.validate()
    path = build_review_frame_path(options.output_dir, name=options.name)
    ok = cv2.imwrite(
        str(path),
        frame_bgr,
        [int(cv2.IMWRITE_JPEG_QUALITY), options.jpeg_quality],
    )
    if not ok:
        raise RuntimeError(f"failed to write review frame: {path}")
    return path
