import json
from pathlib import Path

from cs2_vision_trainer.app.training_commands import default_export_schema_path, write_export_schema
from cs2_vision_trainer.dataset.schema import DEFAULT_CLASS_NAMES


def test_default_export_schema_path_appends_schema_json_suffix():
    assert default_export_schema_path(Path("runs/detect/train/weights/best.onnx")) == Path(
        "runs/detect/train/weights/best.onnx.schema.json"
    )


def test_write_export_schema_records_runtime_class_contract(tmp_path):
    schema_path = tmp_path / "best.onnx.schema.json"

    written = write_export_schema(
        schema_path=schema_path,
        source_model=Path("runs/detect/train/weights/best.pt"),
        exported_model=Path("runs/detect/train/weights/best.onnx"),
        export_format="onnx",
        imgsz=640,
    )

    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["classes"] == list(DEFAULT_CLASS_NAMES)
    assert payload["format"] == "onnx"
    assert payload["imgsz"] == 640
