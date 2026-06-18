from __future__ import annotations

import argparse


def train_model(args: argparse.Namespace) -> int:
    from ultralytics import YOLO

    model = YOLO(args.model)
    kwargs = {
        "data": args.data,
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "workers": args.workers,
        "cache": args.cache,
        "patience": args.patience,
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
