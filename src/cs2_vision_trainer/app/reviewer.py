from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from cs2_vision_trainer.detector import UltralyticsYoloDetector
from cs2_vision_trainer.render import draw_detections
from cs2_vision_trainer.review import ReviewSaveOptions, calculate_progress_bar, save_review_frame


def review_video(args: argparse.Namespace) -> int:
    video_path = Path(args.video)
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"failed to open video: {video_path}")

    detector = UltralyticsYoloDetector(
        args.model,
        min_confidence=args.conf,
        allowed_labels=set(args.labels) if args.labels else None,
        device=args.device,
    )
    save_options = ReviewSaveOptions(output_dir=Path(args.output), name=args.name)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_index = 0
    paused = True
    saved_count = 0

    cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
    try:
        while True:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                break

            start = time.perf_counter()
            detections = detector.predict(frame)
            latency_ms = (time.perf_counter() - start) * 1000
            output = draw_detections(frame, detections, latency_ms=latency_ms)
            _draw_review_help(
                output,
                frame_index=frame_index,
                total_frames=total_frames,
                paused=paused,
                saved_count=saved_count,
            )
            cv2.imshow(args.window, output)

            key = cv2.waitKey(0 if paused else 1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                paused = not paused
                if not paused:
                    frame_index = min(frame_index + 1, max(total_frames - 1, 0))
                continue
            if key in (ord("s"), ord("S")):
                saved_path = save_review_frame(frame, save_options)
                saved_count += 1
                print(f"saved {saved_path}")
                continue
            if key in (ord("d"), ord("D"), 83):
                frame_index = min(frame_index + 1, max(total_frames - 1, 0))
                paused = True
                continue
            if key in (ord("a"), ord("A"), 81):
                frame_index = max(frame_index - 1, 0)
                paused = True
                continue
            if key in (ord("f"), ord("F")):
                frame_index = min(frame_index + 30, max(total_frames - 1, 0))
                paused = True
                continue
            if key in (ord("b"), ord("B")):
                frame_index = max(frame_index - 30, 0)
                paused = True
                continue

            if not paused:
                frame_index += 1
                if total_frames > 0:
                    frame_index = min(frame_index, total_frames - 1)
    finally:
        capture.release()
        cv2.destroyWindow(args.window)
    print(f"saved_count={saved_count} output={save_options.output_dir}")
    return 0


def _draw_review_help(
    frame_bgr,
    *,
    frame_index: int,
    total_frames: int,
    paused: bool,
    saved_count: int,
) -> None:
    status = "PAUSED" if paused else "PLAY"
    total = str(total_frames) if total_frames > 0 else "?"
    lines = [
        f"{status} frame {frame_index + 1}/{total} saved {saved_count}",
        "Space play/pause | S save mistake | A/D prev/next | B/F +/-30 | Q quit",
    ]
    y = 58
    for line in lines:
        cv2.putText(
            frame_bgr,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        y += 26
    _draw_progress_bar(frame_bgr, frame_index=frame_index, total_frames=total_frames)


def _draw_progress_bar(frame_bgr, *, frame_index: int, total_frames: int) -> None:
    height, width = frame_bgr.shape[:2]
    margin = 14
    bar_height = 16
    label_gap = 8
    bar_width = max(width - margin * 2, 0)
    state = calculate_progress_bar(frame_index=frame_index, total_frames=total_frames, width=bar_width)
    y1 = max(height - 38, 0)
    y2 = min(y1 + bar_height, height - 1)
    x1 = margin
    x2 = min(margin + bar_width, width - 1)
    cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (45, 45, 45), -1)
    if state.filled_width > 0:
        cv2.rectangle(
            frame_bgr,
            (x1, y1),
            (min(x1 + state.filled_width, x2), y2),
            (40, 220, 40),
            -1,
        )
    cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (230, 230, 230), 1)
    cv2.putText(
        frame_bgr,
        state.label,
        (x1, max(y1 - label_gap, 16)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
