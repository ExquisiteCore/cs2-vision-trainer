from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Optional


class LockState(IntEnum):
    IDLE = 0
    ACQUIRING = 1
    TRACKING = 2
    LOCKED = 3
    LOST = 4


class _CAction(ctypes.Structure):
    _fields_ = [
        ("frame_index", ctypes.c_int32),
        ("timestamp_ms", ctypes.c_double),
        ("fps", ctypes.c_double),
        ("preprocess_ms", ctypes.c_double),
        ("inference_ms", ctypes.c_double),
        ("postprocess_ms", ctypes.c_double),
        ("total_ms", ctypes.c_double),
        ("detection_count", ctypes.c_int32),
        ("has_target", ctypes.c_int32),
        ("dx", ctypes.c_int32),
        ("dy", ctypes.c_int32),
        ("click_left", ctypes.c_int32),
        ("lock_state", ctypes.c_int32),
        ("distance", ctypes.c_double),
        ("offset_x", ctypes.c_double),
        ("offset_y", ctypes.c_double),
        ("target_x", ctypes.c_double),
        ("target_y", ctypes.c_double),
    ]


@dataclass(frozen=True)
class VisionAction:
    frame_index: int
    timestamp_ms: float
    fps: float
    preprocess_ms: float
    inference_ms: float
    postprocess_ms: float
    total_ms: float
    detection_count: int
    has_target: bool
    dx: int
    dy: int
    click_left: bool
    lock_state: LockState
    distance: float
    offset_x: float
    offset_y: float
    target_x: float
    target_y: float

    @classmethod
    def from_c(cls, action: _CAction) -> "VisionAction":
        return cls(
            frame_index=action.frame_index,
            timestamp_ms=action.timestamp_ms,
            fps=action.fps,
            preprocess_ms=action.preprocess_ms,
            inference_ms=action.inference_ms,
            postprocess_ms=action.postprocess_ms,
            total_ms=action.total_ms,
            detection_count=action.detection_count,
            has_target=bool(action.has_target),
            dx=action.dx,
            dy=action.dy,
            click_left=bool(action.click_left),
            lock_state=LockState(action.lock_state),
            distance=action.distance,
            offset_x=action.offset_x,
            offset_y=action.offset_y,
            target_x=action.target_x,
            target_y=action.target_y,
        )


def _encode_path(value: str | os.PathLike[str]) -> bytes:
    return os.fsencode(os.fspath(value))


def _encode_optional(value: Optional[str | os.PathLike[str]]) -> Optional[bytes]:
    if value is None:
        return None
    return _encode_path(value)


def find_runtime_dll(explicit_path: str | os.PathLike[str] | None = None) -> Path:
    if explicit_path:
        path = Path(explicit_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"vision runtime DLL does not exist: {path}")

    env_path = os.environ.get("CS2_VISION_RUNTIME_DLL")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"CS2_VISION_RUNTIME_DLL points to a missing file: {path}")

    package_dir = Path(__file__).resolve().parent
    repo_root = package_dir.parents[1]
    candidates = [
        package_dir / "vision_runtime.dll",
        package_dir / "bin" / "vision_runtime.dll",
        repo_root / "tools" / "cpp_analyzer" / "build" / "windows" / "x64" / "release" / "vision_runtime.dll",
        repo_root / "tools" / "cpp_analyzer" / "build" / "windows" / "x64" / "debug" / "vision_runtime.dll",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = "\n".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        "vision_runtime.dll was not found. Build it with `xmake -C tools/cpp_analyzer` "
        "or set CS2_VISION_RUNTIME_DLL.\nSearched:\n" + searched
    )


class _RuntimeApi:
    def __init__(self, dll_path: str | os.PathLike[str] | None = None):
        self.path = find_runtime_dll(dll_path)
        self._dll = ctypes.CDLL(str(self.path))
        self._configure()

    def _configure(self) -> None:
        dll = self._dll
        dll.va_create.argtypes = []
        dll.va_create.restype = ctypes.c_void_p
        dll.va_destroy.argtypes = [ctypes.c_void_p]
        dll.va_destroy.restype = None
        dll.va_last_error.argtypes = [ctypes.c_void_p]
        dll.va_last_error.restype = ctypes.c_char_p

        for name in [
            "va_load_config",
            "va_set_model",
            "va_set_schema",
            "va_set_backend",
            "va_set_player_side",
            "va_set_hid_port",
        ]:
            function = getattr(dll, name)
            function.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            function.restype = ctypes.c_int32

        dll.va_set_dry_run.argtypes = [ctypes.c_void_p, ctypes.c_int32]
        dll.va_set_dry_run.restype = ctypes.c_int32
        dll.va_set_hid_click.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32]
        dll.va_set_hid_click.restype = ctypes.c_int32
        dll.va_set_hid_tuning.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_int32, ctypes.c_float]
        dll.va_set_hid_tuning.restype = ctypes.c_int32
        dll.va_set_thresholds.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_float]
        dll.va_set_thresholds.restype = ctypes.c_int32
        dll.va_set_dxgi_roi.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
        dll.va_set_dxgi_roi.restype = ctypes.c_int32
        dll.va_set_frame_limits.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32]
        dll.va_set_frame_limits.restype = ctypes.c_int32
        dll.va_open_video.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int32]
        dll.va_open_video.restype = ctypes.c_int32
        dll.va_open_dxgi.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
        dll.va_open_dxgi.restype = ctypes.c_int32
        dll.va_process_next.argtypes = [ctypes.c_void_p, ctypes.POINTER(_CAction)]
        dll.va_process_next.restype = ctypes.c_int32
        dll.va_stop_all.argtypes = [ctypes.c_void_p]
        dll.va_stop_all.restype = ctypes.c_int32
        dll.va_close.argtypes = [ctypes.c_void_p]
        dll.va_close.restype = ctypes.c_int32

    def create(self) -> int:
        return int(self._dll.va_create() or 0)

    def destroy(self, handle: int) -> None:
        self._dll.va_destroy(handle)

    def last_error(self, handle: int) -> str:
        value = self._dll.va_last_error(handle)
        return value.decode("utf-8", errors="replace") if value else ""

    def load_config(self, handle: int, path: bytes) -> int:
        return int(self._dll.va_load_config(handle, path))

    def set_model(self, handle: int, path: bytes) -> int:
        return int(self._dll.va_set_model(handle, path))

    def set_schema(self, handle: int, path: Optional[bytes]) -> int:
        return int(self._dll.va_set_schema(handle, path))

    def set_backend(self, handle: int, backend: bytes) -> int:
        return int(self._dll.va_set_backend(handle, backend))

    def set_player_side(self, handle: int, side: bytes) -> int:
        return int(self._dll.va_set_player_side(handle, side))

    def set_hid_port(self, handle: int, port: Optional[bytes]) -> int:
        return int(self._dll.va_set_hid_port(handle, port))

    def set_dry_run(self, handle: int, dry_run: bool) -> int:
        return int(self._dll.va_set_dry_run(handle, int(dry_run)))

    def set_hid_click(self, handle: int, enabled: bool, cooldown_frames: int) -> int:
        return int(self._dll.va_set_hid_click(handle, int(enabled), cooldown_frames))

    def set_hid_tuning(self, handle: int, gain: float, max_step: int, deadzone_px: float) -> int:
        return int(self._dll.va_set_hid_tuning(handle, gain, max_step, deadzone_px))

    def set_thresholds(self, handle: int, confidence: float, nms_threshold: float) -> int:
        return int(self._dll.va_set_thresholds(handle, confidence, nms_threshold))

    def set_dxgi_roi(self, handle: int, x: int, y: int, width: int, height: int) -> int:
        return int(self._dll.va_set_dxgi_roi(handle, x, y, width, height))

    def set_frame_limits(self, handle: int, max_frames: int, warmup_frames: int) -> int:
        return int(self._dll.va_set_frame_limits(handle, max_frames, warmup_frames))

    def open_video(self, handle: int, path: bytes, dry_run: bool) -> int:
        return int(self._dll.va_open_video(handle, path, int(dry_run)))

    def open_dxgi(self, handle: int, adapter: int, output: int, dry_run: bool) -> int:
        return int(self._dll.va_open_dxgi(handle, adapter, output, int(dry_run)))

    def process_next(self, handle: int, action: _CAction) -> int:
        return int(self._dll.va_process_next(handle, ctypes.byref(action)))

    def stop_all(self, handle: int) -> int:
        return int(self._dll.va_stop_all(handle))

    def close(self, handle: int) -> int:
        return int(self._dll.va_close(handle))


class VisionRuntime:
    def __init__(self, dll_path: str | os.PathLike[str] | None = None, *, _api=None):
        self._api = _api if _api is not None else _RuntimeApi(dll_path)
        self._handle = self._api.create()
        if not self._handle:
            raise RuntimeError("failed to create vision runtime")

    def __enter__(self) -> "VisionRuntime":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _require_handle(self) -> int:
        if not self._handle:
            raise RuntimeError("vision runtime is closed")
        return self._handle

    def _check(self, status: int) -> None:
        if status == 0:
            return
        handle = self._require_handle()
        message = self._api.last_error(handle) or "vision runtime call failed"
        raise RuntimeError(message)

    def load_config(self, path: str | os.PathLike[str]) -> None:
        self._check(self._api.load_config(self._require_handle(), _encode_path(path)))

    def set_model(
        self,
        model_path: str | os.PathLike[str],
        *,
        schema_path: str | os.PathLike[str] | None = None,
        backend: str | None = None,
    ) -> None:
        handle = self._require_handle()
        self._check(self._api.set_model(handle, _encode_path(model_path)))
        if schema_path is not None:
            self._check(self._api.set_schema(handle, _encode_path(schema_path)))
        if backend is not None:
            self.set_backend(backend)

    def set_schema(self, schema_path: str | os.PathLike[str] | None) -> None:
        self._check(self._api.set_schema(self._require_handle(), _encode_optional(schema_path)))

    def set_backend(self, backend: str) -> None:
        self._check(self._api.set_backend(self._require_handle(), backend.encode("utf-8")))

    def set_player_side(self, side: str) -> None:
        self._check(self._api.set_player_side(self._require_handle(), side.encode("utf-8")))

    def set_hid_port(self, port: str | None) -> None:
        self._check(self._api.set_hid_port(self._require_handle(), None if port is None else port.encode("utf-8")))

    def set_dry_run(self, dry_run: bool) -> None:
        self._check(self._api.set_dry_run(self._require_handle(), dry_run))

    def set_hid_click(self, enabled: bool, cooldown_frames: int = 6) -> None:
        self._check(self._api.set_hid_click(self._require_handle(), enabled, cooldown_frames))

    def set_hid_tuning(self, gain: float = 1.0, max_step: int = 120, deadzone_px: float = 1.5) -> None:
        self._check(self._api.set_hid_tuning(self._require_handle(), gain, max_step, deadzone_px))

    def set_thresholds(self, confidence: float = 0.25, nms_threshold: float = 0.45) -> None:
        self._check(self._api.set_thresholds(self._require_handle(), confidence, nms_threshold))

    def set_dxgi_roi(self, x: int, y: int, width: int, height: int) -> None:
        self._check(self._api.set_dxgi_roi(self._require_handle(), x, y, width, height))

    def set_frame_limits(self, max_frames: int = 0, warmup_frames: int = 3) -> None:
        self._check(self._api.set_frame_limits(self._require_handle(), max_frames, warmup_frames))

    def open_video(self, video_path: str | os.PathLike[str], *, dry_run: bool = True) -> None:
        self._check(self._api.open_video(self._require_handle(), _encode_path(video_path), dry_run))

    def open_dxgi(
        self,
        *,
        adapter: int = 0,
        output: int = 0,
        dry_run: bool = True,
        player_side: str | None = None,
        hid_port: str | None = None,
    ) -> None:
        if player_side is not None:
            self.set_player_side(player_side)
        if hid_port is not None:
            self.set_hid_port(hid_port)
        self._check(self._api.open_dxgi(self._require_handle(), adapter, output, dry_run))

    def process_next(self) -> VisionAction | None:
        action = _CAction()
        status = self._api.process_next(self._require_handle(), action)
        if status == 1:
            return VisionAction.from_c(action)
        if status == 0:
            return None
        message = self._api.last_error(self._require_handle()) or "vision runtime processing failed"
        raise RuntimeError(message)

    def stop_all(self) -> None:
        self._check(self._api.stop_all(self._require_handle()))

    def reset(self) -> None:
        self._check(self._api.close(self._require_handle()))

    def close(self) -> None:
        if self._handle:
            handle = self._handle
            self._handle = 0
            self._api.destroy(handle)
