from __future__ import annotations

import argparse
from pathlib import Path

from cs2_vision_trainer.dataset.builder import DatasetBuildOptions, build_yolo_dataset
from cs2_vision_trainer.dataset.extractor import FrameExtractionOptions, extract_frames_from_video
from cs2_vision_trainer.dataset.schema import DEFAULT_CLASS_NAMES
from cs2_vision_trainer.dataset.validation import validate_yolo_dataset


def extract_frames(args: argparse.Namespace) -> int:
    summary = extract_frames_from_video(
        args.video,
        output_dir=args.output,
        options=FrameExtractionOptions(
            stride=args.stride,
            max_frames=args.max_frames,
            jpeg_quality=args.jpeg_quality,
            start_time_seconds=args.start_time,
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
            class_names=tuple(args.class_names or DEFAULT_CLASS_NAMES),
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


def validate_dataset(args: argparse.Namespace) -> int:
    root = Path(args.root)
    summary = validate_yolo_dataset(
        raw_images_dir=root / "images" / "raw",
        raw_labels_dir=root / "labels" / "raw",
        class_names=tuple(args.class_names or DEFAULT_CLASS_NAMES),
    )
    print(
        f"images={summary.image_count} "
        f"labels={summary.label_count} "
        f"boxes={summary.box_count} "
        f"issues={len(summary.issues)}"
    )
    for issue in summary.issues:
        print(f"{issue.code}: {issue.path}: {issue.message}")
    return 0 if summary.ok else 1
