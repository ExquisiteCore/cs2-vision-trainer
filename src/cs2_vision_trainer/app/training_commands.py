from __future__ import annotations

import argparse
import json
from pathlib import Path

from cs2_vision_trainer.dataset.schema import DEFAULT_CLASS_NAMES


MODEL_SCHEMA_VERSION = 1


def default_export_schema_path(exported_model_path: Path) -> Path:
    return Path(f"{exported_model_path}.schema.json")


def write_export_schema(
    *,
    schema_path: Path,
    source_model: Path,
    exported_model: Path,
    export_format: str,
    imgsz: int,
) -> Path:
    payload = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "source_model": str(source_model),
        "exported_model": str(exported_model),
        "format": export_format,
        "imgsz": imgsz,
        "classes": list(DEFAULT_CLASS_NAMES),
    }
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return schema_path


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
    exported = model.export(**kwargs)
    exported_model = Path(exported) if exported else Path(args.model).with_suffix(f".{args.format}")
    schema_path = Path(args.schema) if args.schema else default_export_schema_path(exported_model)
    write_export_schema(
        schema_path=schema_path,
        source_model=Path(args.model),
        exported_model=exported_model,
        export_format=args.format,
        imgsz=args.imgsz,
    )
    print(f"export_schema={schema_path}")
    return 0
