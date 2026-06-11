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

## Build A First Dataset From A Video

```powershell
uv run --extra dev cs2-vision-trainer extract-frames `
  --video test.mp4 `
  --output datasets\cs2_enemy\images\raw `
  --stride 15 `
  --max-frames 300
```

Open the extracted images in a labeling tool and draw one class for the first
model:

```text
enemy
```

After labeling, build the train/validation split:

```powershell
uv run --extra dev cs2-vision-trainer prepare-dataset --root datasets\cs2_enemy
```

Then train:

```powershell
uv run --extra dev cs2-vision-trainer train `
  --data datasets\cs2_enemy\dataset.yaml `
  --model yolov8n.pt `
  --epochs 50 `
  --imgsz 640 `
  --batch 8 `
  --device 0
```
