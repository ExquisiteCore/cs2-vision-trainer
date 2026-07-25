from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._version import __version__
from .errors import RuntimeCompatibilityError, RuntimeLoadError


_RUNTIME_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def _version_tuple(value: str, label: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise RuntimeCompatibilityError(
            f"{label} must use numeric major.minor.patch format: {value!r}"
        )
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeCompatibilityError(f"runtime manifest {label} must be an object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeCompatibilityError(
            f"runtime manifest {label} must be a non-empty string"
        )
    return value


def _resolve_resource(resources_dir: Path, value: Any, label: str) -> Path:
    text = _require_string(value, label)
    relative = Path(text)
    if relative.is_absolute():
        raise RuntimeCompatibilityError(
            f"runtime manifest {label} must be relative: {text}"
        )
    resolved = (resources_dir / relative).resolve()
    try:
        resolved.relative_to(resources_dir)
    except ValueError as error:
        raise RuntimeCompatibilityError(
            f"runtime manifest {label} escapes the resources directory: {text}"
        ) from error
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _verify_file(path: Path, expected_sha256: Any, label: str) -> None:
    if not path.is_file():
        raise RuntimeLoadError(f"runtime {label} is missing: {path}")
    expected = _require_string(expected_sha256, f"{label}.sha256").upper()
    actual = _sha256(path)
    if actual != expected:
        raise RuntimeCompatibilityError(
            f"runtime {label} SHA256 mismatch: expected {expected}, got {actual}: {path}"
        )


@dataclass(frozen=True)
class RuntimePackage:
    app_dir: Path
    resources_dir: Path
    manifest_path: Path
    package_version: str
    runtime_id: str
    dll_path: Path
    model_path: Path
    schema_path: Path
    native_directories: tuple[Path, ...]
    backend: str
    cache_path: Path
    required_abi_major: int
    required_abi_minor: int
    required_features: int

    @classmethod
    def load(
        cls,
        app_dir: Path,
        data_dir: Path,
        *,
        verify_native_hashes: bool = False,
    ) -> "RuntimePackage":
        del verify_native_hashes  # Reserved for the diagnostic full-integrity pass.
        resolved_app = Path(app_dir).resolve()
        resolved_data = Path(data_dir).resolve()
        resources = (resolved_app / "resources" / "vision-runtime").resolve()
        manifest_path = resources / "runtime-manifest.json"
        if not manifest_path.is_file():
            raise RuntimeLoadError(f"runtime manifest is missing: {manifest_path}")

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RuntimeCompatibilityError(
                f"failed to read runtime manifest {manifest_path}: {error}"
            ) from error
        manifest = _require_mapping(manifest, "root")

        if manifest.get("manifest_version") != 1:
            raise RuntimeCompatibilityError(
                f"unsupported runtime manifest_version: {manifest.get('manifest_version')!r}"
            )

        package_version = _require_string(
            manifest.get("package_version"), "package_version"
        )
        _version_tuple(package_version, "package_version")
        runtime_id = _require_string(manifest.get("runtime_id"), "runtime_id")
        if not _RUNTIME_ID_PATTERN.fullmatch(runtime_id):
            raise RuntimeCompatibilityError(
                f"runtime_id contains unsupported characters: {runtime_id!r}"
            )

        profile = _require_mapping(manifest.get("profile"), "profile")
        if profile.get("os") != "windows" or profile.get("arch") != "x86_64":
            raise RuntimeCompatibilityError(
                "runtime profile must target Windows x86_64"
            )
        if profile.get("gpu_sm") != 61:
            raise RuntimeCompatibilityError("runtime profile must target NVIDIA SM61")
        if profile.get("precision") != "fp32":
            raise RuntimeCompatibilityError("runtime profile must use FP32")

        sdk = _require_mapping(manifest.get("python_sdk"), "python_sdk")
        minimum_sdk = _require_string(sdk.get("minimum"), "python_sdk.minimum")
        if _version_tuple(__version__, "SDK version") < _version_tuple(
            minimum_sdk, "python_sdk.minimum"
        ):
            raise RuntimeCompatibilityError(
                f"Python SDK {__version__} is older than runtime-required SDK {minimum_sdk}"
            )

        backend = _require_string(manifest.get("backend"), "backend")
        if backend != "ort-tensorrt":
            raise RuntimeCompatibilityError(
                f"SM61 runtime backend must be ort-tensorrt, got {backend}"
            )

        dll = _require_mapping(manifest.get("dll"), "dll")
        dll_name = _require_string(dll.get("file_name"), "dll.file_name")
        if Path(dll_name).name != dll_name:
            raise RuntimeCompatibilityError(
                f"runtime DLL file_name must be relative to app_dir: {dll_name}"
            )
        dll_path = (resolved_app / dll_name).resolve()
        _verify_file(dll_path, dll.get("sha256"), "DLL")

        model = _require_mapping(manifest.get("model"), "model")
        model_path = _resolve_resource(resources, model.get("path"), "model.path")
        schema_path = _resolve_resource(
            resources, model.get("schema_path"), "model.schema_path"
        )
        _verify_file(model_path, model.get("sha256"), "model")
        _verify_file(schema_path, model.get("schema_sha256"), "schema")

        native_values = manifest.get("native_directories")
        if not isinstance(native_values, list) or not native_values:
            raise RuntimeCompatibilityError(
                "runtime manifest native_directories must be a non-empty array"
            )
        native_directories = tuple(
            _resolve_resource(resources, value, f"native_directories[{index}]")
            for index, value in enumerate(native_values)
        )
        for directory in native_directories:
            if not directory.is_dir():
                raise RuntimeLoadError(f"runtime native directory is missing: {directory}")

        required_components = {
            "onnxruntime": "1.17.3",
            "cuda": "11.8",
            "tensorrt": "8.6.1.6",
        }
        components = _require_mapping(manifest.get("components"), "components")
        for name, expected in required_components.items():
            if components.get(name) != expected:
                raise RuntimeCompatibilityError(
                    f"runtime component {name} must be {expected}, got {components.get(name)!r}"
                )
        cudnn = _require_string(components.get("cudnn"), "components.cudnn")
        if not cudnn.startswith("8.9."):
            raise RuntimeCompatibilityError(
                f"runtime component cudnn must be 8.9.x, got {cudnn}"
            )

        cache_path = (
            resolved_data / "cache" / "tensorrt" / runtime_id
        ).resolve()
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RuntimeLoadError(
                f"failed to create TensorRT cache directory {cache_path}: {error}"
            ) from error

        try:
            required_abi_major = int(dll["abi_major"])
            required_abi_minor = int(dll["abi_minor"])
            required_features = int(dll["required_features"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeCompatibilityError(
                "runtime manifest DLL ABI fields must be integers"
            ) from error

        return cls(
            app_dir=resolved_app,
            resources_dir=resources,
            manifest_path=manifest_path,
            package_version=package_version,
            runtime_id=runtime_id,
            dll_path=dll_path,
            model_path=model_path,
            schema_path=schema_path,
            native_directories=native_directories,
            backend=backend,
            cache_path=cache_path,
            required_abi_major=required_abi_major,
            required_abi_minor=required_abi_minor,
            required_features=required_features,
        )
