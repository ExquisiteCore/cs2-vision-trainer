# C++ Runtime Python SDK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable `vision_runtime.dll` and Python `cs2_vision_runtime` SDK around the existing C++ runtime pipeline.

**Architecture:** Extract the CLI processing loop into `RuntimeSession`, expose that through a stable C ABI, and wrap the C ABI with Python `ctypes`. The CLI remains supported and calls the same session code.

**Tech Stack:** C++17, xmake, OpenCV, Windows DXGI, RP2350 HID C++ SDK, Python 3.11, `ctypes`, pytest.

---

### Task 1: Extract RuntimeSession

**Files:**
- Create: `tools/cpp_analyzer/include/vision_analyzer/runtime_session.hpp`
- Create: `tools/cpp_analyzer/src/runtime_session.cpp`
- Modify: `tools/cpp_analyzer/src/main.cpp`
- Modify: `tools/cpp_analyzer/tests/test_algorithms.cpp`

- [ ] Move the normal frame-processing loop from `run()` into `RuntimeSession`.
- [ ] Keep CLI-only branches in `run()`: list DXGI, probe DXGI, verify input, test HID, calibration.
- [ ] Make `RuntimeSession::process_next()` return a struct containing `FrameReport`, `AimCommand`, display frame and fused detections.
- [ ] Add a unit test that a default-constructed session reports not open before `open()`.

### Task 2: Add C ABI

**Files:**
- Create: `tools/cpp_analyzer/include/vision_analyzer/vision_runtime_c_api.h`
- Create: `tools/cpp_analyzer/src/vision_runtime_c_api.cpp`
- Create: `tools/cpp_analyzer/tests/test_c_api.cpp`

- [ ] Define exported `va_*` functions and `VaRuntimeAction`.
- [ ] Store C++ exceptions in per-handle `last_error`.
- [ ] Add tests for create/destroy, setter success, process-before-open error, and invalid video open error.

### Task 3: Build DLL

**Files:**
- Modify: `tools/cpp_analyzer/xmake.lua`

- [ ] Add shared target `vision_runtime`.
- [ ] Add binary test target `vision_runtime_c_api_tests`.
- [ ] Keep `vision_analyzer` CLI target working.
- [ ] Ensure Windows target links `d3d11` and `dxgi`.

### Task 4: Add Python SDK

**Files:**
- Create: `src/cs2_vision_runtime/__init__.py`
- Create: `src/cs2_vision_runtime/runtime.py`
- Modify: `pyproject.toml`
- Create: `tests/test_vision_runtime_sdk.py`

- [ ] Add `VisionRuntime` wrapper.
- [ ] Add `VisionAction` dataclass.
- [ ] Locate DLL from `CS2_VISION_RUNTIME_DLL`, package directory, or development build path.
- [ ] Add fake-DLL Python tests for error handling and action conversion.

### Task 5: Docs And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/BUILD.md`
- Modify: `tools/cpp_analyzer/README.md`

- [ ] Document xmake DLL build.
- [ ] Document Python SDK usage.
- [ ] Run `xmake run vision_analyzer_tests`.
- [ ] Run `xmake run vision_runtime_c_api_tests`.
- [ ] Run `uv run pytest`.
- [ ] Commit and push C++ submodule.
- [ ] Commit and push main repository submodule pointer and Python SDK files.
