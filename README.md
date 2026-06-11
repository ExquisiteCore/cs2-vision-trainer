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

Start the lightweight GUI launcher:

```powershell
uv run --extra dev cs2-vision-trainer-gui
```

The GUI lets you pick a video/model and launch review, annotation, dataset
preparation, training, and video testing without typing the full commands.

Command-line entry points are still available:

```powershell
uv run pytest
uv run cs2-vision-trainer run --model path\to\model.pt --source path\to\video.mp4
uv run cs2-vision-trainer run --model path\to\model.pt --source screen
```

Press `q` to quit. Press `s` to save the current frame into `runs/samples`.

## Project Folders

```text
videos\                         source gameplay videos
datasets\cs2_enemy\images\raw   images waiting for LabelImg labeling
datasets\cs2_enemy\labels\raw   LabelImg YOLO label files
datasets\cs2_enemy\images\train generated training split
datasets\cs2_enemy\images\val   generated validation split
runs\detect\train\weights       trained model output
models\base                     downloaded base YOLO weights
```

## Build A First Dataset From A Video

```powershell
uv run --extra dev cs2-vision-trainer extract-frames `
  --video videos\xxx_01.mp4 `
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
  --model models\base\yolov8n.pt `
  --epochs 50 `
  --imgsz 640 `
  --batch 8 `
  --device 0
```

## Review Model Mistakes

Use review mode to pause a video, step through frames, and save mistake frames
directly into the raw training-image folder for relabeling:

```powershell
uv run --extra dev cs2-vision-trainer review `
  --model runs\detect\train\weights\best.pt `
  --video videos\xxx_01.mp4 `
  --name xxx_01 `
  --device 0
```

Controls:

```text
Space  play or pause
S      save current frame as a mistake image
A/D    previous or next frame
B/F    jump back or forward 30 frames
Q      quit
```

After saving mistake frames, open LabelImg again and label only the new
`xxx_01_error_*.jpg` files in `datasets\cs2_enemy\images\raw`.

Or use the built-in one-class annotator instead of LabelImg:

```powershell
uv run --extra dev cs2-vision-trainer annotate `
  --images datasets\cs2_enemy\images\raw `
  --labels datasets\cs2_enemy\labels\raw
```

Annotator controls:

```text
Left drag   draw an enemy box
Right click delete the clicked box
S           save current label file
A/D         previous or next image
Space       save and go to next image
X           clear all boxes on current image
Q           save current image if needed, then quit
```

Then rebuild the dataset and continue training from the current best model:

```powershell
uv run --extra dev cs2-vision-trainer prepare-dataset `
  --root datasets\cs2_enemy `
  --val-ratio 0.2 `
  --empty-limit 100 `
  --seed 7

uv run --extra dev cs2-vision-trainer train `
  --data datasets\cs2_enemy\dataset.yaml `
  --model runs\detect\train\weights\best.pt `
  --epochs 40 `
  --imgsz 640 `
  --batch 8 `
  --device 0
```
