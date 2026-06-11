# CS2 Vision Trainer Design

## Goal

Build a read-only visual analysis tool for CS2 training-range experiments. The
tool captures video or screen frames, runs YOLO enemy detection, displays
results in a separate window, and saves difficult frames for dataset iteration.

## Safety Boundary

The tool must not read game memory, inject into any process, control mouse or
keyboard input, create an in-game overlay, or bypass anti-cheat systems. It only
consumes pixels from a user-selected frame source and writes local analysis
outputs.

## Architecture

The application is a Python CLI with small modules:

- `capture`: video, webcam, and screen frame sources.
- `vision`: detection models, detection data types, filtering, and rendering.
- `training`: wrappers for YOLO training and export.
- `tools`: benchmarking and sample collection helpers.
- `cli`: command entry points for real-time detection, training, and export.

## MVP Behavior

The first version supports `run` with a YOLO model path and a source. The source
can be a video path, camera index, or `screen`. The output is an independent
OpenCV window with bounding boxes, class labels, confidence scores, FPS, and
latency. Pressing `s` saves the current frame for later labeling.

## Acceleration Plan

Development starts with Ultralytics YOLO for fast iteration. Acceleration is
handled by accepting exported ONNX or TensorRT engine models through the same
detector API. Training export commands produce ONNX or TensorRT artifacts when
the local machine has the required NVIDIA stack.

## Dataset Loop

The project supports a practical active-learning loop:

1. Run the detector in the training range.
2. Save low-confidence or mistaken frames.
3. Label frames outside the game.
4. Retrain or fine-tune YOLO.
5. Export an accelerated model.
6. Replace the runtime model and repeat.

## Initial Classes

Start with one class, `enemy`, until the detector is stable. Add `enemy_head`
later when enough high-quality head labels exist.
