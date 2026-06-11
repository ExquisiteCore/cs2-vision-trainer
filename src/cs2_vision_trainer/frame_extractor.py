from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2

from cs2_vision_trainer.capture import FrameSource, VideoFrameSource


@dataclass(frozen=True)
class FrameExtractionOptions:
    stride: int = 15
    max_frames: int | None = None
    jpeg_quality: int = 95

    def validate(self) -> None:
        if self.stride <= 0:
            raise ValueError("stride must be greater than 0")
        if self.max_frames is not None and self.max_frames <= 0:
            raise ValueError("max_frames must be greater than 0")
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be between 1 and 100")


@dataclass(frozen=True)
class FrameExtractionSummary:
    read_frames: int
    saved_frames: int
    output_dir: Path


def should_save_frame(frame_index: int, options: FrameExtractionOptions) -> bool:
    return frame_index % options.stride == 0


def build_frame_path(output_dir: Path, *, video_stem: str, frame_index: int) -> Path:
    return output_dir / f"{video_stem}_frame_{frame_index:06d}.jpg"


def extract_frames_from_source(
    source: FrameSource,
    *,
    output_dir: Path,
    video_stem: str,
    options: FrameExtractionOptions,
) -> FrameExtractionSummary:
    options.validate()
    output_dir.mkdir(parents=True, exist_ok=True)
    read_frames = 0
    saved_frames = 0
    try:
        while True:
            frame = source.read()
            if frame is None:
                break
            read_frames += 1
            if not should_save_frame(frame.index, options):
                continue
            file_path = build_frame_path(output_dir, video_stem=video_stem, frame_index=frame.index)
            ok = cv2.imwrite(
                str(file_path),
                frame.image,
                [int(cv2.IMWRITE_JPEG_QUALITY), options.jpeg_quality],
            )
            if not ok:
                raise RuntimeError(f"failed to write frame: {file_path}")
            saved_frames += 1
            if options.max_frames is not None and saved_frames >= options.max_frames:
                break
    finally:
        source.release()
    return FrameExtractionSummary(
        read_frames=read_frames,
        saved_frames=saved_frames,
        output_dir=output_dir,
    )


def extract_frames_from_video(
    video_path: str | Path,
    *,
    output_dir: str | Path,
    options: FrameExtractionOptions,
) -> FrameExtractionSummary:
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(path)
    return extract_frames_from_source(
        VideoFrameSource(path),
        output_dir=Path(output_dir),
        video_stem=path.stem,
        options=options,
    )
