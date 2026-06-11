from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyConfig:
    """Runtime guard for keeping the tool read-only."""

    allow_game_memory_access: bool = False
    allow_input_control: bool = False
    allow_process_injection: bool = False
    allow_in_game_overlay: bool = False

    def validate(self) -> None:
        if self.allow_game_memory_access:
            raise ValueError("game memory access is not allowed")
        if self.allow_input_control:
            raise ValueError("input control is not allowed")
        if self.allow_process_injection:
            raise ValueError("process injection is not allowed")
        if self.allow_in_game_overlay:
            raise ValueError("in-game overlay is not allowed")


@dataclass(frozen=True)
class RuntimeConfig:
    model: str
    source: str = "screen"
    confidence: float = 0.25
    labels: tuple[str, ...] = ()
    monitor: int = 1
    window_name: str = "CS2 Vision Trainer"
    save_dir: str = "runs/samples"
    safety: SafetyConfig = SafetyConfig()

    def validate(self) -> None:
        self.safety.validate()
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.model:
            raise ValueError("model path is required")
