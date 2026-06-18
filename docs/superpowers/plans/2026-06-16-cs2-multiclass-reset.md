# CS2 Multiclass Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reset the training assets and reorganize the project for four-class CS2 CT/T body/head detection.

**Architecture:** Move business logic into `runtime`, `dataset`, `review`, and `app` packages. Keep top-level console entry points as wrappers. Add dataset validation and multiclass annotation while preserving existing workflows.

**Tech Stack:** Python 3.11, OpenCV, Ultralytics YOLO, NumPy, PyYAML, pytest, Tkinter.

---

### Task 1: Lock The New Dataset Contract With Tests

**Files:**
- Modify: `tests/test_dataset_builder.py`
- Modify: `tests/test_gui.py`
- Create: `tests/test_dataset_validation.py`
- Modify: `tests/test_annotation.py`

- [ ] Add tests proving the default class names are `ct_body`, `ct_head`, `t_body`, and `t_head`.
- [ ] Add tests proving the GUI defaults to `datasets/cs2_multiclass` and derives enemy filters from the selected player side.
- [ ] Add tests proving dataset validation reports missing labels and invalid class ids.
- [ ] Add tests proving annotation state carries class names and writes selected class ids.
- [ ] Run `uv run pytest tests/test_dataset_builder.py tests/test_gui.py tests/test_dataset_validation.py tests/test_annotation.py -q` and verify failures come from missing behavior.

### Task 2: Reorganize Runtime And Dataset Modules

**Files:**
- Create: `src/cs2_vision_trainer/runtime/`
- Create: `src/cs2_vision_trainer/dataset/`
- Create: `src/cs2_vision_trainer/review/`
- Modify: top-level compatibility modules in `src/cs2_vision_trainer/`

- [ ] Move detection, capture, detector, and render logic under `runtime`.
- [ ] Move annotation, frame extraction, and dataset building under `dataset`.
- [ ] Move review save/progress logic under `review`.
- [ ] Keep top-level modules as imports from the new packages so existing tests and imports continue to work.
- [ ] Run `uv run pytest tests/test_capture.py tests/test_detections.py tests/test_detector_filters.py tests/test_frame_extractor.py tests/test_review.py -q`.

### Task 3: Split CLI And GUI App Logic

**Files:**
- Create: `src/cs2_vision_trainer/app/`
- Modify: `src/cs2_vision_trainer/cli.py`
- Modify: `src/cs2_vision_trainer/gui.py`

- [ ] Move command parser and command handlers into `app`.
- [ ] Keep `cs2_vision_trainer.cli:main` and `cs2_vision_trainer.gui:main` as stable wrappers.
- [ ] Add `validate-dataset` command.
- [ ] Make GUI defaults use the multiclass dataset root and CT/T side-aware filters.
- [ ] Run `uv run cs2-vision-trainer --help` and `uv run cs2-vision-trainer validate-dataset --help`.

### Task 4: Rebuild Empty Dataset Skeleton And Docs

**Files:**
- Create: `datasets/cs2_multiclass/dataset.yaml`
- Modify: `README.md`

- [ ] Recreate empty `videos`, `runs`, and `datasets/cs2_multiclass` directory skeletons.
- [ ] Write the four-class `dataset.yaml`.
- [ ] Update README to describe the clean multiclass workflow.
- [ ] Run `uv run pytest -q`.
