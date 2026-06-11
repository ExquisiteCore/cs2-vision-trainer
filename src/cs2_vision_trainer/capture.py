from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import mss
import numpy as np


@dataclass(frozen=True)
class Frame:
    image: np.ndarray
    index: int
    timestamp: float


@dataclass(frozen=True)
class SourceSpec:
    kind: str
    value: str | int | Path


class FrameSource(Protocol):
    def read(self) -> Frame | None:
        ...

    def release(self) -> None:
        ...


def parse_source_spec(source: str) -> SourceSpec:
    normalized = source.strip()
    if normalized.lower() == "screen":
        return SourceSpec(kind="screen", value="screen")
    if normalized.isdigit():
        return SourceSpec(kind="camera", value=int(normalized))
    return SourceSpec(kind="video", value=Path(normalized))


class VideoFrameSource:
    def __init__(self, source: str | int | Path) -> None:
        self._capture = cv2.VideoCapture(str(source) if isinstance(source, Path) else source)
        if not self._capture.isOpened():
            raise RuntimeError(f"failed to open video source: {source}")
        self._index = 0

    def read(self) -> Frame | None:
        ok, image = self._capture.read()
        if not ok:
            return None
        frame = Frame(image=image, index=self._index, timestamp=time.perf_counter())
        self._index += 1
        return frame

    def release(self) -> None:
        self._capture.release()


class ScreenFrameSource:
    def __init__(self, *, monitor: int = 1) -> None:
        self._mss = mss.mss()
        if monitor >= len(self._mss.monitors):
            raise ValueError(f"monitor index {monitor} is unavailable")
        self._monitor = self._mss.monitors[monitor]
        self._index = 0

    def read(self) -> Frame:
        raw = np.asarray(self._mss.grab(self._monitor))
        image = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
        frame = Frame(image=image, index=self._index, timestamp=time.perf_counter())
        self._index += 1
        return frame

    def release(self) -> None:
        self._mss.close()


def open_frame_source(source: str, *, monitor: int = 1) -> FrameSource:
    spec = parse_source_spec(source)
    if spec.kind == "screen":
        return ScreenFrameSource(monitor=monitor)
    return VideoFrameSource(spec.value)
