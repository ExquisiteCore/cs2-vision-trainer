from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from cs2_vision_trainer.annotation import (
    AnnotationBox,
    AnnotatorState,
    collect_image_paths,
    draw_annotation_overlay,
    filter_images_missing_labels,
    load_current_boxes,
    normalize_box,
    point_in_box,
    save_current_boxes,
)
from cs2_vision_trainer.capture import open_frame_source
from cs2_vision_trainer.config import RuntimeConfig
from cs2_vision_trainer.dataset_builder import DatasetBuildOptions, build_yolo_dataset
from cs2_vision_trainer.detector import UltralyticsYoloDetector
from cs2_vision_trainer.frame_extractor import FrameExtractionOptions, extract_frames_from_video
from cs2_vision_trainer.render import draw_detections
from cs2_vision_trainer.review import ReviewSaveOptions, calculate_progress_bar, save_review_frame


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

    review = subparsers.add_parser("review", help="review a video and save model mistakes for relabeling")
    review.add_argument("--model", required=True, help="trained YOLO model")
    review.add_argument("--video", required=True, help="video to review")
    review.add_argument("--name", required=True, help="saved frame prefix, for example xxx_01")
    review.add_argument("--conf", type=float, default=0.25)
    review.add_argument("--labels", nargs="*", default=("enemy",))
    review.add_argument("--device", default=None)
    review.add_argument(
        "--output",
        default="datasets/cs2_enemy/images/raw",
        help="directory where mistake frames are saved for labeling",
    )
    review.add_argument("--window", default="CS2 Review", help="OpenCV window title")
    review.set_defaults(func=review_video)

    annotate = subparsers.add_parser("annotate", help="simple one-class YOLO image annotator")
    annotate.add_argument("--images", default="datasets/cs2_enemy/images/raw", help="image directory")
    annotate.add_argument("--labels", default="datasets/cs2_enemy/labels/raw", help="label directory")
    annotate.add_argument("--pattern", default="*", help="image filename pattern, for example xxx_01_error_*.jpg")
    annotate.add_argument("--missing-only", action="store_true", help="only show images without label files")
    annotate.add_argument("--class-index", type=int, default=0)
    annotate.add_argument("--window", default="CS2 Annotator")
    annotate.set_defaults(func=annotate_images)

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

    prepare = subparsers.add_parser("prepare-dataset", help="split raw labels into train/val YOLO data")
    prepare.add_argument("--root", default="datasets/cs2_enemy", help="dataset root")
    prepare.add_argument("--val-ratio", type=float, default=0.2)
    prepare.add_argument("--seed", type=int, default=7)
    prepare.add_argument("--empty-limit", type=int, default=10, help="maximum empty labels to keep")
    prepare.add_argument("--no-empty", action="store_true", help="drop empty labels")
    prepare.set_defaults(func=prepare_dataset)

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


def annotate_images(args: argparse.Namespace) -> int:
    image_paths = collect_image_paths(Path(args.images), pattern=args.pattern)
    if args.missing_only:
        image_paths = filter_images_missing_labels(image_paths, Path(args.labels))
    if not image_paths:
        print(f"no images found: {args.images} pattern={args.pattern}")
        return 1

    state = AnnotatorState(
        image_paths=image_paths,
        labels_dir=Path(args.labels),
        class_index=args.class_index,
    )
    cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(args.window, _handle_annotator_mouse, state)
    try:
        while True:
            image = cv2.imread(str(state.current_image_path))
            if image is None:
                print(f"failed to read image: {state.current_image_path}")
                return 1
            image_height, image_width = image.shape[:2]
            if state.boxes is None:
                load_current_boxes(state, image_width=image_width, image_height=image_height)
            output = draw_annotation_overlay(
                image,
                state=state,
                image_width=image_width,
                image_height=image_height,
            )
            cv2.imshow(args.window, output)
            key = cv2.waitKey(30) & 0xFF
            if key in (ord("q"), 27):
                if state.dirty:
                    save_current_boxes(state, image_width=image_width, image_height=image_height)
                    print(f"saved {state.current_label_path}")
                break
            if key in (ord("s"), ord("S")):
                save_current_boxes(state, image_width=image_width, image_height=image_height)
                print(f"saved {state.current_label_path}")
                continue
            if key in (ord("d"), ord("D"), ord(" "), 83):
                if state.dirty:
                    save_current_boxes(state, image_width=image_width, image_height=image_height)
                    print(f"saved {state.current_label_path}")
                _move_annotator(state, 1)
                continue
            if key in (ord("a"), ord("A"), 81):
                if state.dirty:
                    save_current_boxes(state, image_width=image_width, image_height=image_height)
                    print(f"saved {state.current_label_path}")
                _move_annotator(state, -1)
                continue
            if key in (ord("x"), ord("X")):
                state.boxes = []
                state.dirty = True
                continue
    finally:
        cv2.destroyWindow(args.window)
    return 0


def _move_annotator(state: AnnotatorState, delta: int) -> None:
    state.current_index = min(max(state.current_index + delta, 0), len(state.image_paths) - 1)
    state.boxes = None
    state.drawing_start = None
    state.drawing_current = None
    state.dirty = False


def _handle_annotator_mouse(event: int, x: int, y: int, _flags: int, state: AnnotatorState) -> None:
    if state.boxes is None:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        state.drawing_start = (x, y)
        state.drawing_current = (x, y)
        return
    if event == cv2.EVENT_MOUSEMOVE and state.drawing_start:
        state.drawing_current = (x, y)
        return
    if event == cv2.EVENT_LBUTTONUP and state.drawing_start:
        image = cv2.imread(str(state.current_image_path))
        if image is None:
            state.drawing_start = None
            state.drawing_current = None
            return
        image_height, image_width = image.shape[:2]
        x1, y1 = state.drawing_start
        box = normalize_box((x1, y1, x, y), image_width=image_width, image_height=image_height)
        state.drawing_start = None
        state.drawing_current = None
        if box[2] - box[0] >= 3 and box[3] - box[1] >= 3:
            state.boxes.append(AnnotationBox(class_index=state.class_index, xyxy=box))
            state.dirty = True
        return
    if event == cv2.EVENT_RBUTTONDOWN:
        for index in range(len(state.boxes) - 1, -1, -1):
            if point_in_box((x, y), state.boxes[index].xyxy):
                del state.boxes[index]
                state.dirty = True
                break


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


def prepare_dataset(args: argparse.Namespace) -> int:
    root = Path(args.root)
    summary = build_yolo_dataset(
        raw_images_dir=root / "images" / "raw",
        raw_labels_dir=root / "labels" / "raw",
        output_root=root,
        options=DatasetBuildOptions(
            val_ratio=args.val_ratio,
            seed=args.seed,
            include_empty=not args.no_empty,
            empty_limit=args.empty_limit,
        ),
    )
    print(
        f"total={summary.total_examples} "
        f"train={summary.train_examples} "
        f"val={summary.val_examples} "
        f"empty={summary.empty_examples} "
        f"yaml={summary.dataset_yaml}"
    )
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
