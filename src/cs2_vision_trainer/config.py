from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PreviewConfig:
    """Python-side visual preview config for dataset review and model checks."""

    model: str
    source: str = "screen"
    confidence: float = 0.25
    labels: tuple[str, ...] = ()
    monitor: int = 1
    window_name: str = "CS2 Vision Trainer"
    save_dir: str = "runs/samples"

    def validate(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.model:
            raise ValueError("model path is required")
