# CS2 Vision Trainer

Read-only YOLO + OpenCV vision analyzer for CS2 training-range experiments.

This project is intentionally limited to visual analysis:

- no game memory access
- no process injection
- no mouse or keyboard automation
- no in-game overlay
- no anti-cheat bypass behavior

The first milestone is a real-time detector window that can read from a video
file, webcam, or screen capture and draw YOLO detections in an independent
OpenCV window.

## Quick Start

```powershell
uv run pytest
uv run cs2-vision-trainer run --model path\to\model.pt --source path\to\video.mp4
uv run cs2-vision-trainer run --model path\to\model.pt --source screen
```

Press `q` to quit. Press `s` to save the current frame into `runs/samples`.
