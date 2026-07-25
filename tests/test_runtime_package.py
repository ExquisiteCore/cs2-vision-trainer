import hashlib
import json
from pathlib import Path

import pytest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def make_app_layout(tmp_path: Path) -> tuple[Path, Path, dict]:
    app_dir = tmp_path / "MyClient"
    resources = app_dir / "resources" / "vision-runtime"
    model = resources / "model" / "best.onnx"
    schema = resources / "model" / "best.onnx.schema.json"
    dll = app_dir / "vision_runtime.dll"
    dll.parent.mkdir(parents=True)
    model.parent.mkdir(parents=True)
    dll.write_bytes(b"runtime-dll-v2")
    model.write_bytes(b"onnx-model")
    schema.write_text('{"classes":["ct_body","ct_head","t_body","t_head"]}', encoding="utf-8")

    native_directories = [
        "native/onnxruntime",
        "native/cuda-11.8",
        "native/cudnn-8.9",
        "native/tensorrt-8.6.1.6",
        "native/msvc-x64",
    ]
    for relative in native_directories:
        (resources / relative).mkdir(parents=True)

    manifest = {
        "manifest_version": 1,
        "package_version": "0.2.0",
        "runtime_id": "sm61-fp32-model-a-ort1.17.3-trt8.6.1.6",
        "profile": {
            "os": "windows",
            "arch": "x86_64",
            "gpu_sm": 61,
            "precision": "fp32",
        },
        "python_sdk": {"minimum": "0.2.0", "recommended": "0.2.0"},
        "dll": {
            "file_name": "vision_runtime.dll",
            "sha256": _sha256(dll),
            "abi_major": 2,
            "abi_minor": 0,
            "required_features": 15,
        },
        "backend": "ort-tensorrt",
        "model": {
            "path": "model/best.onnx",
            "sha256": _sha256(model),
            "schema_path": "model/best.onnx.schema.json",
            "schema_sha256": _sha256(schema),
        },
        "native_directories": native_directories,
        "components": {
            "onnxruntime": "1.17.3",
            "cuda": "11.8",
            "cudnn": "8.9.7",
            "tensorrt": "8.6.1.6",
        },
    }
    resources.mkdir(parents=True, exist_ok=True)
    (resources / "runtime-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return app_dir, tmp_path / "data", manifest


def write_manifest(app_dir: Path, manifest: dict) -> None:
    path = app_dir / "resources" / "vision-runtime" / "runtime-manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def test_runtime_package_loads_valid_app_local_layout(tmp_path):
    from cs2_vision_runtime.package import RuntimePackage

    app_dir, data_dir, _ = make_app_layout(tmp_path)
    package = RuntimePackage.load(app_dir, data_dir)

    assert package.app_dir == app_dir.resolve()
    assert package.dll_path == (app_dir / "vision_runtime.dll").resolve()
    assert package.model_path.name == "best.onnx"
    assert package.schema_path.name == "best.onnx.schema.json"
    assert package.backend == "ort-tensorrt"
    assert package.runtime_id.startswith("sm61-fp32-")
    assert package.cache_path == (
        data_dir / "cache" / "tensorrt" / package.runtime_id
    ).resolve()
    assert package.cache_path.is_dir()
    assert len(package.native_directories) == 5


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update(manifest_version=2), "manifest_version"),
        (lambda value: value["profile"].update(gpu_sm=75), "SM61"),
        (lambda value: value["profile"].update(precision="fp16"), "FP32"),
        (lambda value: value["python_sdk"].update(minimum="9.0.0"), "SDK"),
        (lambda value: value.update(backend="opencv-onnx"), "ort-tensorrt"),
        (lambda value: value["model"].update(path="../escape.onnx"), "escapes"),
        (lambda value: value["model"].update(path="C:/absolute.onnx"), "relative"),
    ],
)
def test_runtime_package_rejects_incompatible_manifest(tmp_path, mutate, message):
    from cs2_vision_runtime.errors import RuntimeCompatibilityError
    from cs2_vision_runtime.package import RuntimePackage

    app_dir, data_dir, manifest = make_app_layout(tmp_path)
    mutate(manifest)
    write_manifest(app_dir, manifest)

    with pytest.raises(RuntimeCompatibilityError, match=message):
        RuntimePackage.load(app_dir, data_dir)


@pytest.mark.parametrize("target", ["dll", "model", "schema"])
def test_runtime_package_rejects_tampered_critical_files(tmp_path, target):
    from cs2_vision_runtime.errors import RuntimeCompatibilityError
    from cs2_vision_runtime.package import RuntimePackage

    app_dir, data_dir, _ = make_app_layout(tmp_path)
    targets = {
        "dll": app_dir / "vision_runtime.dll",
        "model": app_dir / "resources" / "vision-runtime" / "model" / "best.onnx",
        "schema": app_dir / "resources" / "vision-runtime" / "model" / "best.onnx.schema.json",
    }
    targets[target].write_bytes(b"tampered")

    with pytest.raises(RuntimeCompatibilityError, match="SHA256"):
        RuntimePackage.load(app_dir, data_dir)


def test_runtime_package_rejects_missing_native_directory(tmp_path):
    from cs2_vision_runtime.errors import RuntimeLoadError
    from cs2_vision_runtime.package import RuntimePackage

    app_dir, data_dir, _ = make_app_layout(tmp_path)
    missing = app_dir / "resources" / "vision-runtime" / "native" / "cudnn-8.9"
    missing.rmdir()

    with pytest.raises(RuntimeLoadError, match="cudnn-8.9"):
        RuntimePackage.load(app_dir, data_dir)
