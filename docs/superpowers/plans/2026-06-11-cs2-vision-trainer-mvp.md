# CS2 Vision Trainer MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only YOLO + OpenCV runtime that can detect training-range enemies from video, camera, or screen frames.

**Architecture:** A Python package split into capture, vision, training, and CLI modules. The runtime consumes pixels only, routes frames through a detector abstraction, renders detections in an independent OpenCV window, and saves sample frames for later labeling.

**Tech Stack:** Python 3.11+, OpenCV, Ultralytics YOLO, NumPy, MSS, pytest, optional ONNX Runtime GPU.

---

### Task 1: Core Data Types And Safety Guard

**Files:**
- Create: `src/cs2_vision_trainer/config.py`
- Create: `src/cs2_vision_trainer/detections.py`
- Test: `tests/test_config.py`
- Test: `tests/test_detections.py`

- [ ] Write tests that prove unsafe capabilities are rejected and detection geometry is stable.
- [ ] Run `uv run pytest tests/test_config.py tests/test_detections.py -q` and verify import failures.
- [ ] Implement the minimal config and detection modules.
- [ ] Re-run the same tests and verify they pass.

### Task 2: YOLO Detector And Renderer

**Files:**
- Create: `src/cs2_vision_trainer/detector.py`
- Create: `src/cs2_vision_trainer/render.py`
- Test: `tests/test_detector_filters.py`

- [ ] Write tests for class-name filtering and confidence filtering.
- [ ] Run the detector filter test and verify it fails before implementation.
- [ ] Implement lazy Ultralytics model loading and detection filtering.
- [ ] Implement OpenCV rendering helpers.
- [ ] Re-run tests.

### Task 3: Frame Sources

**Files:**
- Create: `src/cs2_vision_trainer/capture.py`
- Test: `tests/test_capture.py`

- [ ] Write tests for source parsing: `screen`, camera index, and video path.
- [ ] Run the capture tests and verify failure before implementation.
- [ ] Implement frame source parsing and source classes.
- [ ] Re-run tests.

### Task 4: CLI Runtime

**Files:**
- Create: `src/cs2_vision_trainer/cli.py`
- Modify: `README.md`

- [ ] Implement `run`, `train`, `export`, and `benchmark` command skeletons.
- [ ] Implement real-time loop for `run`.
- [ ] Verify `uv run cs2-vision-trainer --help` and `uv run cs2-vision-trainer run --help`.

### Task 5: Verification And Commit

**Files:**
- All project files.

- [ ] Run `uv run pytest -q`.
- [ ] Run CLI help commands.
- [ ] Review `git status --short`.
- [ ] Commit the initial project.
