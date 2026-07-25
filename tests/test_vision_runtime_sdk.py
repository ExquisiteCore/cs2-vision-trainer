import ctypes
import importlib.util
import re
from pathlib import Path

import pytest

from cs2_vision_runtime.runtime import (
    _CAction,
    _CCalibrationProfile,
    _runtime_dll_directories,
    VisionAction,
    VisionRuntime,
)
from cs2_vision_runtime import LockState


def test_python_runtime_c_api_matches_pinned_cpp_header():
    project_root = Path(__file__).resolve().parents[1]
    python_source = (project_root / "src" / "cs2_vision_runtime" / "runtime.py").read_text(encoding="utf-8")
    cpp_header = (
        project_root
        / "tools"
        / "cpp_analyzer"
        / "include"
        / "vision_analyzer"
        / "vision_runtime_c_api.h"
    ).read_text(encoding="utf-8")

    required = set(re.findall(r"\bva_[a-z0-9_]+", python_source))
    declared = set(re.findall(r"\bva_[a-z0-9_]+(?=\s*\()", cpp_header))

    assert required <= declared, f"Python wrapper requires missing C API exports: {sorted(required - declared)}"


class FakeApi:
    def __init__(self):
        self.destroyed = []
        self.calls = []
        self.error = ""
        self.next_status = 0

    def create(self):
        return 123

    def destroy(self, handle):
        self.destroyed.append(handle)

    def last_error(self, handle):
        return self.error

    def load_config(self, handle, path):
        self.calls.append(("load_config", path))
        return 0

    def set_model(self, handle, path):
        self.calls.append(("set_model", path))
        return 0

    def set_schema(self, handle, path):
        self.calls.append(("set_schema", path))
        return 0

    def set_backend(self, handle, backend):
        self.calls.append(("set_backend", backend))
        return 0

    def set_player_side(self, handle, side):
        self.calls.append(("set_player_side", side))
        return 0

    def set_hid_port(self, handle, port):
        self.calls.append(("set_hid_port", port))
        return 0

    def set_dry_run(self, handle, dry_run):
        self.calls.append(("set_dry_run", dry_run))
        return 0

    def set_output_enabled(self, handle, enabled):
        self.calls.append(("set_output_enabled", bool(enabled)))
        return 0

    def set_fire_enabled(self, handle, enabled):
        self.calls.append(("set_fire_enabled", bool(enabled)))
        return 0

    def set_fire_policy(self, handle, body, head_conf, body_conf, cooldown):
        self.calls.append(("set_fire_policy", bool(body), head_conf, body_conf, cooldown))
        return 0

    def calibrate_hid(self, handle, adapter, output, profile):
        self.calls.append(("calibrate_hid", adapter, output))
        profile.schema_version = 1
        profile.valid = 1
        profile.frame_width = 1920
        profile.frame_height = 1080
        profile.x_shift_px[:] = (8.0, 32.0, 96.0)
        profile.x_counts_per_pixel[:] = (2.0, 3.0, 4.0)
        profile.y_shift_px[:] = (8.0, 32.0, 96.0)
        profile.y_counts_per_pixel[:] = (-2.0, -3.0, -4.0)
        profile.deadzone_px = 1.0
        profile.max_step = 120
        profile.noise_px = 0.25
        profile.quality = 0.9
        profile.accepted_samples = 24
        return 0

    def set_hid_click(self, handle, enabled, cooldown_frames):
        self.calls.append(("set_hid_click", enabled, cooldown_frames))
        return 0

    def set_hid_tuning(self, handle, gain, max_step, deadzone_px):
        self.calls.append(("set_hid_tuning", gain, max_step, deadzone_px))
        return 0

    def set_thresholds(self, handle, confidence, nms_threshold):
        self.calls.append(("set_thresholds", confidence, nms_threshold))
        return 0

    def set_dxgi_roi(self, handle, x, y, width, height):
        self.calls.append(("set_dxgi_roi", x, y, width, height))
        return 0

    def set_frame_limits(self, handle, max_frames, warmup_frames):
        self.calls.append(("set_frame_limits", max_frames, warmup_frames))
        return 0

    def open_video(self, handle, path, dry_run):
        self.calls.append(("open_video", path, dry_run))
        return 0

    def open_dxgi(self, handle, adapter, output, dry_run):
        self.calls.append(("open_dxgi", adapter, output, dry_run))
        return 0

    def process_next(self, handle, action):
        if self.next_status != 1:
            return self.next_status
        action.frame_index = 42
        action.timestamp_ms = 123.0
        action.fps = 144.0
        action.inference_ms = 3.5
        action.total_ms = 4.5
        action.detection_count = 2
        action.has_target = 1
        action.dx = 12
        action.dy = -5
        action.click_left = 1
        action.lock_state = int(LockState.LOCKED)
        action.distance = 13.0
        action.offset_x = 12.0
        action.offset_y = -5.0
        action.target_x = 960.0
        action.target_y = 540.0
        return 1

    def stop_all(self, handle):
        self.calls.append(("stop_all",))
        return 0

    def close(self, handle):
        self.calls.append(("close",))
        return 0


def test_action_conversion_from_c_struct():
    raw = _CAction()
    raw.frame_index = 7
    raw.has_target = 1
    raw.dx = 3
    raw.dy = -2
    raw.click_left = 1
    raw.lock_state = int(LockState.TRACKING)

    action = VisionAction.from_c(raw)

    assert action.frame_index == 7
    assert action.has_target is True
    assert action.dx == 3
    assert action.dy == -2
    assert action.click_left is True
    assert action.lock_state is LockState.TRACKING


def test_runtime_wrapper_forwards_configuration():
    api = FakeApi()
    runtime = VisionRuntime(_api=api)

    runtime.set_model("best.onnx", schema_path="best.onnx.schema.json", backend="opencv-onnx")
    runtime.set_player_side("ct")
    runtime.set_hid_port("COM3")
    runtime.open_video("videos/02.mp4", dry_run=True)
    runtime.close()

    assert ("set_model", b"best.onnx") in api.calls
    assert ("set_schema", b"best.onnx.schema.json") in api.calls
    assert ("set_backend", b"opencv-onnx") in api.calls
    assert ("set_player_side", b"ct") in api.calls
    assert ("set_hid_port", b"COM3") in api.calls
    assert ("open_video", b"videos/02.mp4", True) in api.calls
    assert api.destroyed == [123]


def test_process_next_returns_action_or_none():
    api = FakeApi()
    runtime = VisionRuntime(_api=api)

    assert runtime.process_next() is None

    api.next_status = 1
    action = runtime.process_next()

    assert action is not None
    assert action.frame_index == 42
    assert action.dx == 12
    assert action.dy == -5
    assert action.click_left is True
    assert action.lock_state is LockState.LOCKED


def test_runtime_error_uses_last_error():
    api = FakeApi()
    runtime = VisionRuntime(_api=api)
    api.error = "bad model"

    def fail_set_model(handle, path):
        return -1

    api.set_model = fail_set_model

    with pytest.raises(RuntimeError, match="bad model"):
        runtime.set_model("bad.onnx")


def test_calibration_ctypes_layout_matches_c_abi():
    assert ctypes.sizeof(_CCalibrationProfile) == 84


def test_portable_runtime_discovers_private_dll_directories(tmp_path):
    package = tmp_path / "portable"
    dll = package / "app" / "vision_runtime.dll"
    dll.parent.mkdir(parents=True)
    dll.touch()
    expected = [
        package / "app",
        package / "runtime" / "tensorrt-8.6.1.6",
        package / "runtime" / "cudnn-8.9",
        package / "runtime" / "cuda-11.8",
        package / "runtime" / "msvc-x64",
    ]
    for directory in expected[1:]:
        directory.mkdir(parents=True)

    assert _runtime_dll_directories(dll) == expected


def test_runtime_forwards_live_control_and_fire_policy():
    api = FakeApi()
    runtime = VisionRuntime(_api=api)
    runtime.set_output_enabled(True)
    runtime.set_fire_enabled(True)
    runtime.set_fire_policy(
        body_enabled=True,
        head_confidence=0.35,
        body_confidence=0.45,
        cooldown_frames=3,
    )
    assert ("set_output_enabled", True) in api.calls
    assert ("set_fire_enabled", True) in api.calls
    assert ("set_fire_policy", True, 0.35, 0.45, 3) in api.calls


def test_runtime_converts_calibration_profile():
    api = FakeApi()
    runtime = VisionRuntime(_api=api)
    profile = runtime.calibrate_hid(adapter=1, output=2)
    assert profile.valid is True
    assert profile.x_shift_px == (8.0, 32.0, 96.0)
    assert profile.y_counts_per_pixel[0] < 0.0
    assert profile.accepted_samples == 24
    assert ("calibrate_hid", 1, 2) in api.calls


def test_calibration_failure_uses_last_error():
    api = FakeApi()
    runtime = VisionRuntime(_api=api)
    api.error = "calibration scene is unstable"
    api.calibrate_hid = lambda handle, adapter, output, profile: -1

    with pytest.raises(RuntimeError, match="unstable"):
        runtime.calibrate_hid()


def test_armed_loop_always_disarms_after_processing_error():
    example_path = Path(__file__).parents[1] / "examples" / "runtime_live_move.py"
    spec = importlib.util.spec_from_file_location("runtime_live_move", example_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run_armed_loop = module.run_armed_loop

    class ExplodingRuntime:
        def __init__(self):
            self.calls = []

        def set_output_enabled(self, value):
            self.calls.append(("output", value))

        def set_fire_enabled(self, value):
            self.calls.append(("fire", value))

        def process_next(self):
            raise RuntimeError("capture failed")

        def stop_all(self):
            self.calls.append(("stop_all",))

    runtime = ExplodingRuntime()
    with pytest.raises(RuntimeError, match="capture failed"):
        run_armed_loop(runtime, fire_enabled=True, show_every=30)
    assert runtime.calls == [
        ("output", True),
        ("fire", True),
        ("fire", False),
        ("output", False),
        ("stop_all",),
    ]
