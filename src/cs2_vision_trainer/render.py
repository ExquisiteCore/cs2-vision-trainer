from __future__ import annotations

import cv2
import numpy as np

from cs2_vision_trainer.detections import Detection


def draw_detections(
    frame_bgr: np.ndarray,
    detections: list[Detection],
    *,
    fps: float | None = None,
    latency_ms: float | None = None,
) -> np.ndarray:
    output = frame_bgr.copy()
    for detection in detections:
        x1, y1, x2, y2 = detection.xyxy
        color = (40, 220, 40) if detection.label == "enemy" else (40, 180, 255)
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
        label = f"{detection.label} {detection.confidence:.2f}"
        cv2.putText(
            output,
            label,
            (x1, max(20, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    metrics: list[str] = []
    if fps is not None:
        metrics.append(f"FPS {fps:.1f}")
    if latency_ms is not None:
        metrics.append(f"latency {latency_ms:.1f} ms")
    if metrics:
        cv2.putText(
            output,
            " | ".join(metrics),
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return output
