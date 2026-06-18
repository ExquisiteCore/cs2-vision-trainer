from __future__ import annotations

import argparse

from cs2_vision_trainer.app.annotator import annotate_images
from cs2_vision_trainer.app.dataset_commands import extract_frames, prepare_dataset, validate_dataset
from cs2_vision_trainer.app.reviewer import review_video
from cs2_vision_trainer.app.runtime_commands import benchmark_model, run_detection
from cs2_vision_trainer.app.training_commands import export_model, train_model
from cs2_vision_trainer.dataset.schema import DEFAULT_CLASS_NAMES

DEFAULT_DATASET_ROOT = "datasets/cs2_multiclass"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cs2-vision-trainer",
        description="YOLO dataset, training, export, and review tools for CS2 vision experiments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="preview visual detection for dataset review")
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
    train.add_argument("--model", default="models/base/yolov8n.pt", help="base model")
    train.add_argument("--epochs", type=int, default=50)
    train.add_argument("--imgsz", type=int, default=640)
    train.add_argument("--batch", type=int, default=16)
    train.add_argument("--device", default=None)
    train.add_argument("--workers", type=int, default=4, help="training dataloader workers")
    train.add_argument("--cache", default=False, action="store_true", help="cache images during training")
    train.add_argument("--patience", type=int, default=50, help="early stopping patience")
    train.set_defaults(func=train_model)

    export = subparsers.add_parser("export", help="export a YOLO model for acceleration")
    export.add_argument("--model", required=True, help="trained YOLO model")
    export.add_argument("--format", choices=["onnx", "engine"], default="onnx")
    export.add_argument("--imgsz", type=int, default=640)
    export.add_argument("--half", action="store_true", help="use FP16 where supported")
    export.add_argument("--device", default=None)
    export.set_defaults(func=export_model)

    benchmark = subparsers.add_parser("benchmark", help="benchmark Python-side model preview inference")
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
    review.add_argument("--labels", nargs="*", default=())
    review.add_argument("--device", default=None)
    review.add_argument(
        "--output",
        default=f"{DEFAULT_DATASET_ROOT}/images/raw",
        help="directory where mistake frames are saved for labeling",
    )
    review.add_argument("--window", default="CS2 Review", help="OpenCV window title")
    review.set_defaults(func=review_video)

    annotate = subparsers.add_parser("annotate", help="simple multiclass YOLO image annotator")
    annotate.add_argument("--images", default=f"{DEFAULT_DATASET_ROOT}/images/raw", help="image directory")
    annotate.add_argument("--labels", default=f"{DEFAULT_DATASET_ROOT}/labels/raw", help="label directory")
    annotate.add_argument("--pattern", default="*", help="image filename pattern, for example xxx_01_error_*.jpg")
    annotate.add_argument("--missing-only", action="store_true", help="only show images without label files")
    annotate.add_argument("--class-index", type=int, default=0)
    annotate.add_argument("--class-names", nargs="*", default=DEFAULT_CLASS_NAMES)
    annotate.add_argument("--window", default="CS2 Annotator")
    annotate.set_defaults(func=annotate_images)

    extract = subparsers.add_parser("extract-frames", help="extract training images from a video")
    extract.add_argument("--video", required=True, help="input video path")
    extract.add_argument(
        "--output",
        default=f"{DEFAULT_DATASET_ROOT}/images/raw",
        help="directory for extracted jpg frames",
    )
    extract.add_argument("--stride", type=int, default=15, help="save every Nth frame")
    extract.add_argument("--max-frames", type=int, default=None, help="optional saved-frame limit")
    extract.add_argument("--start-time", type=float, default=0, help="skip the first N seconds before extracting")
    extract.add_argument("--jpeg-quality", type=int, default=95, help="jpeg quality from 1 to 100")
    extract.set_defaults(func=extract_frames)

    prepare = subparsers.add_parser("prepare-dataset", help="split raw labels into train/val YOLO data")
    prepare.add_argument("--root", default=DEFAULT_DATASET_ROOT, help="dataset root")
    prepare.add_argument("--val-ratio", type=float, default=0.2)
    prepare.add_argument("--seed", type=int, default=7)
    prepare.add_argument("--empty-limit", type=int, default=100, help="maximum empty labels to keep")
    prepare.add_argument("--no-empty", action="store_true", help="drop empty labels")
    prepare.add_argument("--class-names", nargs="*", default=DEFAULT_CLASS_NAMES)
    prepare.set_defaults(func=prepare_dataset)

    validate = subparsers.add_parser("validate-dataset", help="validate raw YOLO labels before training")
    validate.add_argument("--root", default=DEFAULT_DATASET_ROOT, help="dataset root")
    validate.add_argument("--class-names", nargs="*", default=DEFAULT_CLASS_NAMES)
    validate.set_defaults(func=validate_dataset)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
