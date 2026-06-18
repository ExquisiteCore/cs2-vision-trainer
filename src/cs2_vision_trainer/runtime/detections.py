from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    xyxy: Box

    @property
    def width(self) -> int:
        x1, _, x2, _ = self.xyxy
        return max(0, x2 - x1)

    @property
    def height(self) -> int:
        _, y1, _, y2 = self.xyxy
        return max(0, y2 - y1)

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.xyxy
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def area(self) -> int:
        return self.width * self.height


def filter_detections(
    detections: Iterable[Detection],
    *,
    min_confidence: float,
    allowed_labels: set[str] | None = None,
) -> list[Detection]:
    result: list[Detection] = []
    for detection in detections:
        if detection.confidence < min_confidence:
            continue
        if allowed_labels and detection.label not in allowed_labels:
            continue
        result.append(detection)
    return result
