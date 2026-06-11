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
