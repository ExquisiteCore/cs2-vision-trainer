from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from cs2_vision_trainer.runtime.detections import Detection, filter_detections


def normalize_names(names: Mapping[int, str] | Sequence[str]) -> dict[int, str]:
    if isinstance(names, Mapping):
        return {int(index): str(label) for index, label in names.items()}
    return {index: str(label) for index, label in enumerate(names)}


def select_class_indices(
    names: Mapping[int, str] | Sequence[str],
    allowed_labels: set[str] | None,
) -> set[int] | None:
    if not allowed_labels:
        return None
    normalized = normalize_names(names)
    selected = {index for index, label in normalized.items() if label in allowed_labels}
    return selected


class UltralyticsYoloDetector:
    """YOLO detector with lazy model loading."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        min_confidence: float = 0.25,
        allowed_labels: set[str] | None = None,
        device: str | None = None,
    ) -> None:
        self.model_path = str(model_path)
        self.min_confidence = min_confidence
        self.allowed_labels = allowed_labels
        self.device = device
        self._model: Any | None = None

    @property
    def model(self) -> Any:
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.model_path)
        return self._model

    def predict(self, frame_bgr: np.ndarray) -> list[Detection]:
        names = normalize_names(self.model.names)
        classes = select_class_indices(names, self.allowed_labels)
        kwargs: dict[str, Any] = {
            "verbose": False,
            "conf": self.min_confidence,
        }
        if self.device:
            kwargs["device"] = self.device
        if classes is not None:
            kwargs["classes"] = sorted(classes)

        result = self.model.predict(frame_bgr, **kwargs)[0]
        detections: list[Detection] = []
        boxes = result.boxes
        if boxes is None:
            return []

        xyxy_values = boxes.xyxy.cpu().numpy()
        confidence_values = boxes.conf.cpu().numpy()
        class_values = boxes.cls.cpu().numpy()
        for xyxy, confidence, class_index in zip(xyxy_values, confidence_values, class_values):
            x1, y1, x2, y2 = [int(round(value)) for value in xyxy]
            label = names.get(int(class_index), str(int(class_index)))
            detections.append(
                Detection(
                    label=label,
                    confidence=float(confidence),
                    xyxy=(x1, y1, x2, y2),
                )
            )
        return filter_detections(
            detections,
            min_confidence=self.min_confidence,
            allowed_labels=self.allowed_labels,
        )
