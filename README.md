# CS2 Vision Trainer

Two-part YOLO vision workflow for CS2 experiments:

- `cs2-vision-trainer` Python package: build datasets, label CT/T body/head
  boxes, validate labels, train/export YOLO models, and review model misses.
- `tools/cpp_analyzer` C++ runtime submodule: load an exported model, detect
  enemy heads, track/filter/predict the target point, plan bounded relative
  mouse movement, and send movement/click commands through the RP2350 HID bridge
  SDK.

The Python package is the training side. Runtime input output is isolated in
the C++ submodule and RP2350 firmware path. The project does not use game memory
access, process injection, or an in-game overlay.

The current dataset target is four classes:

```text
0 ct_body
1 ct_head
2 t_body
3 t_head
```

Body and head boxes should both be labeled when visible. Enemy/teammate status
is derived later from the player's current side, so the dataset itself stays
side-based. Empty frames are saved as empty label files.

## Quick Start

Start the lightweight GUI launcher:

```powershell
uv run --extra dev cs2-vision-trainer-gui
```

GUI 是中文界面。选择视频和模型后，常用按钮如下：

```text
找错题       用当前模型播放视频，保存漏检/误检画面
标注新抽帧   只标注当前视频抽出来的 xxx_frame_*.jpg
标注错题     只标注当前视频保存的 xxx_error_*.jpg
标注全部     打开全部 raw 图片，平时少用
补标缺失     只用于补救漏保存的图片；正常流程不需要
整理数据集   重新生成 train/val
开始训练     从当前模型继续训练
测试视频     用当前模型检测所选视频
```

In the GUI, set `己方阵营` to `ct` or `t` before testing if you want the video
view to show only enemies. Keep it as `unknown` to show both sides.

Command-line entry points are still available:

```powershell
uv run pytest
uv run cs2-vision-trainer run --model path\to\model.pt --source path\to\video.mp4
uv run cs2-vision-trainer run --model path\to\model.pt --source screen
```

Press `q` to quit. Press `s` to save the current frame into `runs/samples`.
This Python `run` command is a preview/review helper. Live runtime control
belongs to `tools\cpp_analyzer`.

## Project Folders

```text
videos\                         source gameplay videos
datasets\cs2_multiclass\images\raw   images waiting for labeling
datasets\cs2_multiclass\labels\raw   YOLO label files
datasets\cs2_multiclass\images\train generated training split
datasets\cs2_multiclass\images\val   generated validation split
runs\detect\train\weights       trained model output
models\base                     downloaded base YOLO weights
tools\cpp_analyzer              C++ runtime controller submodule
```

## C++ Runtime Controller

The C++ runtime consumes exported YOLO models from `runs\detect\train\weights`.
It detects enemy head candidates, runs tracking/filtering/prediction, converts
the planned target offset into relative HID counts, and sends `mouse_move` plus
optional left click through the RP2350 HID bridge SDK.

Use dry-run while tuning:

```powershell
cd tools\cpp_analyzer
xmake run vision_analyzer --backend opencv-onnx --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx --video D:\project\cs2-vision-trainer\videos\02.mp4 --dry-run --preview
xmake run vision_analyzer --backend opencv-onnx --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx --input dxgi --dxgi-output 0 --dry-run --preview
```

Use live SDK output after calibration:

```powershell
cd tools\cpp_analyzer
xmake f --hid_sdk_root=D:\project\pi\test\sdk\cpp
xmake run vision_analyzer --backend opencv-onnx --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx --input dxgi --dxgi-output 0 --player-side ct --hid-port COM3 --hid-gain 1.0 --hid-max-step 120
```

The RP2350 firmware sends standard relative USB HID mouse reports. Windows
pointer speed and Enhance Pointer Precision can affect normal pointer movement;
Raw Input paths are usually dominated by HID counts and in-application
sensitivity. Tune `--hid-gain` and `--hid-max-step`; the runtime does not read
or modify Windows pointer settings.

Live SDK output requires `--player-side ct` or `--player-side t`. The runtime
uses side-specific filtering, a 2D Kalman target estimate, and head-only click
candidates. Body detections can help tracking but do not trigger left click.

## Build A First Dataset From A Video

```powershell
uv run --extra dev cs2-vision-trainer extract-frames `
  --video videos\xxx_01.mp4 `
  --output datasets\cs2_multiclass\images\raw `
  --start-time 160 `
  --stride 15 `
  --max-frames 5000
```

For a new video, keep the video name unique and then extract frames with the
same stem:

```powershell
uv run --extra dev cs2-vision-trainer extract-frames `
  --video videos\xxx_02.mp4 `
  --output datasets\cs2_multiclass\images\raw `
  --start-time 160 `
  --stride 10 `
  --max-frames 5000
```

In the GUI, select `videos\xxx_02.mp4`, then click `标注新抽帧` to label only
`xxx_02_frame_*.jpg`.

Use the built-in annotator and switch classes with number keys:

```text
1 ct_body
2 ct_head
3 t_body
4 t_head
```

After labeling, validate and build the train/validation split:

```powershell
uv run --extra dev cs2-vision-trainer validate-dataset --root datasets\cs2_multiclass
uv run --extra dev cs2-vision-trainer prepare-dataset --root datasets\cs2_multiclass
```

Then train:

```powershell
uv run --extra dev cs2-vision-trainer train `
  --data datasets\cs2_multiclass\dataset.yaml `
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

To review only enemies from CT perspective, add `--labels t_body t_head`. From
T perspective, add `--labels ct_body ct_head`.

Controls:

```text
Space  play or pause
S      save current frame as a mistake image
A/D    previous or next frame
B/F    jump back or forward 30 frames
Q      quit
```

After saving mistake frames, open LabelImg again and label only the new
`xxx_01_error_*.jpg` files in `datasets\cs2_multiclass\images\raw`.

Or use the built-in multiclass annotator:

```powershell
uv run --extra dev cs2-vision-trainer annotate `
  --images datasets\cs2_multiclass\images\raw `
  --labels datasets\cs2_multiclass\labels\raw `
  --pattern xxx_01_error_*.jpg
```

Annotator controls:

```text
1-4         switch class
Left drag   draw a box for the active class
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
  --root datasets\cs2_multiclass `
  --val-ratio 0.2 `
  --empty-limit 100 `
  --seed 7

uv run --extra dev cs2-vision-trainer train `
  --data datasets\cs2_multiclass\dataset.yaml `
  --model runs\detect\train\weights\best.pt `
  --epochs 40 `
  --imgsz 640 `
  --batch 8 `
  --device 0
```
