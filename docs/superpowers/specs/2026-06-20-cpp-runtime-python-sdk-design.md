# C++ Runtime Python SDK Design

## Goal

Expose the existing C++ vision runtime as a reusable Windows DLL, then provide a
Python SDK that other programs can import without shelling out to
`vision_analyzer.exe`.

## Approved Approach

Use a standard C ABI DLL plus a Python `ctypes` wrapper.

This keeps the runtime usable from Python, C#, Rust, Node native bindings, and
other C/C++ programs. It also avoids binding the runtime to one Python version,
which would happen with a direct `pybind11` `.pyd` module.

## Architecture

The C++ CLI currently owns the runtime loop. The implementation will extract
that loop into a stateful `RuntimeSession` class:

```text
RuntimeSession
├─ FrameSource: video or DXGI
├─ Detector: OpenCV/ORT/TensorRT backend
├─ TrackManager / TargetSelector / AnalysisState
├─ AimController
└─ optional HidActionSender
```

`vision_analyzer.exe` will continue to work by calling `RuntimeSession`. The new
`vision_runtime.dll` will expose a C API around the same session class.

Python will load the DLL through `ctypes` and provide an idiomatic
`VisionRuntime` class.

## C API

The C API uses opaque handles and plain structs only:

```text
va_create / va_destroy
va_last_error
va_load_config
va_set_model / va_set_schema / va_set_backend
va_open_video / va_open_dxgi
va_set_player_side / va_set_hid_port / va_set_dry_run
va_set_hid_click / va_set_hid_tuning / va_set_thresholds
va_process_next
va_stop_all
```

`va_process_next` returns:

```text
1  frame processed and action filled
0  end of stream or max frame limit
-1 error; read va_last_error
```

The output struct includes frame index, timestamp, detection count, movement
delta, click decision, lock state, target offsets, target point, FPS and timing.

## Python API

Python package name:

```text
cs2_vision_runtime
```

Minimal usage:

```python
from cs2_vision_runtime import VisionRuntime

rt = VisionRuntime()
rt.set_model("runs/detect/train/weights/best.onnx")
rt.open_video("videos/02.mp4", dry_run=True)

while True:
    action = rt.process_next()
    if action is None:
        break
    print(action.dx, action.dy, action.click_left)
```

DXGI usage:

```python
rt.open_dxgi(output=0, player_side="ct", hid_port="COM3", dry_run=False)
```

## Error Handling

C++ stores the last exception message per handle. C API functions return `-1`
on error. Python translates that into `RuntimeError` with `va_last_error`.

## Build

xmake will build:

```text
vision_analyzer.exe
vision_runtime.dll
vision_runtime.lib
vision_runtime_c_api_tests.exe
```

The DLL target uses the same OpenCV, ONNX Runtime, DXGI and RP2350 SDK settings
as the CLI target.

## Scope

In scope:

- DLL for video and DXGI runtime processing.
- Python wrapper for configuration, input opening and per-frame actions.
- Unit tests for C API handle/error behavior.
- Python tests for wrapper behavior with a fake DLL API.
- Documentation updates.

Out of scope for this pass:

- Python-side preview windows.
- Packaging the DLL into a wheel.
- Async callbacks.
- UI integration.
