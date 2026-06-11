from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from cs2_vision_trainer.capture import open_frame_source
from cs2_vision_trainer.config import RuntimeConfig
from cs2_vision_trainer.detector import UltralyticsYoloDetector
from cs2_vision_trainer.frame_extractor import FrameExtractionOptions, extract_frames_from_video
from cs2_vision_trainer.render import draw_detections


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cs2-vision-trainer",
        description="Read-only YOLO + OpenCV analyzer for CS2 training-range vision experiments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run real-time visual detection")
    run.add_argument("--model", required=True, help="YOLO model path: .pt, .onnx, or .engine")
    run.add_argument("--source", default="screen", help="screen, camera index, or video path")
    run.add_argument("--conf", type=float, default=0.25, help="minimum confidence")
    run.add_argument("--labels", nargs="*", default=(), help="optional class labels to keep")
    run.add_argument("--monitor", type=int, default=1, help="MSS monitor index for screen capture")
    run.add_argument("--device", default=None, help="Ultralytics device, for example 0 or cpu")
    run.add_argument("--save-dir", default="runs/samples", help="directory for saved frames")
    run.add_argument("--window", default="CS2 Vision Trainer", help="OpenCV window title")
    run.set_defaults(func=run_detection)

    train = subparsers.add_parser("train", help="train a YOLO model")
    train.add_argument("--data", required=True, help="dataset yaml path")
    train.add_argument("--model", default="yolov8n.pt", help="base model")
    train.add_argument("--epochs", type=int, default=50)
    train.add_argument("--imgsz", type=int, default=640)
    train.add_argument("--batch", type=int, default=16)
    train.add_argument("--device", default=None)
    train.set_defaults(func=train_model)

    export = subparsers.add_parser("export", help="export a YOLO model for acceleration")
    export.add_argument("--model", required=True, help="trained YOLO model")
    export.add_argument("--format", choices=["onnx", "engine"], default="onnx")
    export.add_argument("--imgsz", type=int, default=640)
    export.add_argument("--half", action="store_true", help="use FP16 where supported")
    export.add_argument("--device", default=None)
    export.set_defaults(func=export_model)

    benchmark = subparsers.add_parser("benchmark", help="benchmark model inference on a source")
    benchmark.add_argument("--model", required=True)
    benchmark.add_argument("--source", default="screen")
    benchmark.add_argument("--frames", type=int, default=120)
    benchmark.add_argument("--conf", type=float, default=0.25)
    benchmark.add_argument("--labels", nargs="*", default=())
    benchmark.add_argument("--monitor", type=int, default=1)
    benchmark.add_argument("--device", default=None)
    benchmark.set_defaults(func=benchmark_model)

    extract = subparsers.add_parser("extract-frames", help="extract training images from a video")
    extract.add_argument("--video", required=True, help="input video path")
    extract.add_argument(
        "--output",
        default="datasets/cs2_enemy/images/raw",
        help="directory for extracted jpg frames",
    )
    extract.add_argument("--stride", type=int, default=15, help="save every Nth frame")
    extract.add_argument("--max-frames", type=int, default=None, help="optional saved-frame limit")
    extract.add_argument("--jpeg-quality", type=int, default=95, help="jpeg quality from 1 to 100")
    extract.set_defaults(func=extract_frames)

    return parser


def run_detection(args: argparse.Namespace) -> int:
    config = RuntimeConfig(
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


def train_model(args: argparse.Namespace) -> int:
    from ultralytics import YOLO

    model = YOLO(args.model)
    kwargs = {
        "data": args.data,
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
    }
    if args.device:
        kwargs["device"] = args.device
    model.train(**kwargs)
    return 0


def export_model(args: argparse.Namespace) -> int:
    from ultralytics import YOLO

    model = YOLO(args.model)
    kwargs = {
        "format": args.format,
        "imgsz": args.imgsz,
        "half": args.half,
    }
    if args.device:
        kwargs["device"] = args.device
    model.export(**kwargs)
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


def extract_frames(args: argparse.Namespace) -> int:
    summary = extract_frames_from_video(
        args.video,
        output_dir=args.output,
        options=FrameExtractionOptions(
            stride=args.stride,
            max_frames=args.max_frames,
            jpeg_quality=args.jpeg_quality,
        ),
    )
    print(
        f"read_frames={summary.read_frames} "
        f"saved_frames={summary.saved_frames} "
        f"output_dir={summary.output_dir}"
    )
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
