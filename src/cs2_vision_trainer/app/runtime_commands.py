from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from cs2_vision_trainer.capture import open_frame_source
from cs2_vision_trainer.config import PreviewConfig
from cs2_vision_trainer.detector import UltralyticsYoloDetector
from cs2_vision_trainer.render import draw_detections


def run_detection(args: argparse.Namespace) -> int:
    config = PreviewConfig(
        model=args.model,
        source=args.source,
        confidence=args.conf,
        labels=tuple(args.labels),
        monitor=args.monitor,
        window_name=args.window,
        save_dir=args.save_dir,
    )
    config.validate()
    save_dir = Path(config.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    source = open_frame_source(config.source, monitor=config.monitor)
    detector = UltralyticsYoloDetector(
        config.model,
        min_confidence=config.confidence,
        allowed_labels=set(config.labels) if config.labels else None,
        device=args.device,
    )
    cv2.namedWindow(config.window_name, cv2.WINDOW_NORMAL)
    last_display_time = time.perf_counter()
    fps = 0.0
    try:
        while True:
            frame = source.read()
            if frame is None:
                break
            start = time.perf_counter()
            detections = detector.predict(frame.image)
            latency_ms = (time.perf_counter() - start) * 1000
            now = time.perf_counter()
            frame_delta = now - last_display_time
            if frame_delta > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / frame_delta) if fps else 1.0 / frame_delta
            last_display_time = now
            output = draw_detections(frame.image, detections, fps=fps, latency_ms=latency_ms)
            cv2.imshow(config.window_name, output)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("s"):
                file_path = save_dir / f"frame_{frame.index:06d}.jpg"
                cv2.imwrite(str(file_path), frame.image)
                print(f"saved {file_path}")
    finally:
        source.release()
        cv2.destroyWindow(config.window_name)
    return 0


def benchmark_model(args: argparse.Namespace) -> int:
    source = open_frame_source(args.source, monitor=args.monitor)
    detector = UltralyticsYoloDetector(
        args.model,
        min_confidence=args.conf,
        allowed_labels=set(args.labels) if args.labels else None,
        device=args.device,
    )
    costs: list[float] = []
    try:
        for _ in range(args.frames):
            frame = source.read()
            if frame is None:
                break
            start = time.perf_counter()
            detector.predict(frame.image)
            costs.append((time.perf_counter() - start) * 1000)
    finally:
        source.release()
    if not costs:
        print("no frames processed")
        return 1
    average = sum(costs) / len(costs)
    print(f"frames={len(costs)} avg_inference_ms={average:.2f} fps={1000 / average:.1f}")
    return 0
