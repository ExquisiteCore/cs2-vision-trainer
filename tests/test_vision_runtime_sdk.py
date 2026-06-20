import pytest

from cs2_vision_runtime.runtime import _CAction, VisionAction, VisionRuntime
from cs2_vision_runtime import LockState


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
