# CS2 Vision Trainer

CS2 Vision Trainer 是一个分模块的视觉训练与运行项目。项目由 Python 训练端、C++
实时运行端、RP2350 外置键鼠桥接固件，以及对应的 C++/Python SDK 组成。

Python 部分只负责数据集、标注、训练、测试和模型导出。C++ 部分负责加载导出的
YOLO 模型，读取视频或 DXGI 屏幕画面，执行检测、目标融合、跟踪、滤波、预测和鼠标
路线规划。RP2350 固件通过 CDC 串口接收命令，并以标准 USB HID 键盘/鼠标报告输出。

项目不依赖游戏内存读取、进程注入或游戏内 overlay。

## 仓库结构

主仓库通过 Git submodule 组织运行端和硬件端代码：

```text
cs2-vision-trainer
├─ src/                              Python 训练、标注、导出、预览代码
├─ tests/                            Python 测试
├─ docs/                             设计文档和编译文档
├─ tools/
│  ├─ cpp_analyzer                   C++ 实时识别和控制端 submodule
│  ├─ rp2350_hid_bridge_cpp          RP2350 HID Bridge C++ SDK submodule
│  └─ rp2350_keymouse_bridge_firmware RP2350 固件工程 submodule
│     └─ sdk/
│        ├─ cpp                      固件仓库内引用的 C++ SDK submodule
│        └─ python                   固件仓库内引用的 Python SDK submodule
├─ videos/                           本地视频样本，不提交
├─ datasets/                         本地数据集，不提交
├─ runs/                             训练输出，不提交
└─ models/                           本地模型文件，不提交
```

远端仓库：

```text
https://github.com/ExquisiteCore/cs2-vision-trainer
https://github.com/ExquisiteCore/cs2-vision-cpp-analyzer
https://github.com/ExquisiteCore/rp2350-hid-bridge-cpp
https://github.com/ExquisiteCore/rp2350-hid-bridge-python
https://github.com/ExquisiteCore/rp2350-keymouse-bridge-firmware
```

## 快速拉取

第一次拉取必须带上 submodule：

```powershell
git clone --recurse-submodules https://github.com/ExquisiteCore/cs2-vision-trainer.git
cd cs2-vision-trainer
git submodule update --init --recursive
```

如果已经普通 `git clone` 过，再补一次：

```powershell
git submodule update --init --recursive
```

检查子仓库是否完整：

```powershell
git submodule status --recursive
```

正常情况下会看到 `tools/cpp_analyzer`、`tools/rp2350_hid_bridge_cpp`、
`tools/rp2350_keymouse_bridge_firmware`，以及固件下面的 `sdk/cpp` 和
`sdk/python`。

## 编译文档

详细编译步骤见 [docs/BUILD.md](docs/BUILD.md)。里面包含：

- Python 训练端环境安装、测试、GUI 启动。
- C++ runtime 使用 xmake 编译、测试、视频输入验证和 DXGI 输入验证。
- C++ SDK 使用 CMake 编译测试。
- Python SDK 安装和单元测试。
- RP2350 固件 Rust 交叉编译、hidctl 工具编译和 picotool 烧录方式。

最小构建流程：

```powershell
# Python 训练端
uv sync --extra dev
uv run pytest

# C++ runtime
cd tools\cpp_analyzer
xmake f -m release
xmake
xmake run vision_analyzer_tests

# 回到主仓库
cd ..\..
```

## Python 训练端

当前数据集类别固定为：

```text
0 ct_body
1 ct_head
2 t_body
3 t_head
```

身体和头部框都应该在可见时标注。己方/敌方关系不写进标签，运行时通过
`--player-side ct` 或 `--player-side t` 判断。

启动中文 GUI：

```powershell
uv run --extra dev cs2-vision-trainer-gui
```

常用 CLI：

```powershell
uv run --extra dev cs2-vision-trainer extract-frames --video videos\01.mp4 --output datasets\cs2_multiclass\images\raw --stride 10 --max-frames 3000
uv run --extra dev cs2-vision-trainer annotate --images datasets\cs2_multiclass\images\raw --labels datasets\cs2_multiclass\labels\raw
uv run --extra dev cs2-vision-trainer validate-dataset --root datasets\cs2_multiclass
uv run --extra dev cs2-vision-trainer prepare-dataset --root datasets\cs2_multiclass
uv run --extra dev cs2-vision-trainer train --data datasets\cs2_multiclass\dataset.yaml --model models\base\yolov8n.pt --epochs 50 --imgsz 640 --batch 8 --device 0
uv run --extra dev cs2-vision-trainer export --model runs\detect\train\weights\best.pt --format onnx --imgsz 640
```

导出 ONNX 时会在模型旁边生成 schema JSON。C++ live 模式会强制校验这个 schema，
避免模型类别顺序错位。

## C++ 实时运行端

C++ runtime 位于 `tools\cpp_analyzer`。它读取视频或 DXGI 屏幕输入，执行 YOLO
推理、body/head 融合、目标跟踪、Kalman 滤波、延迟预测、相对鼠标路径规划，并通过
RP2350 C++ SDK 输出移动和可选左键。

验证视频输入：

```powershell
cd tools\cpp_analyzer
xmake run vision_analyzer --video D:\project\cs2-vision-trainer\videos\02.mp4 --verify-input
```

验证当前屏幕输入：

```powershell
xmake run vision_analyzer --list-dxgi-outputs
xmake run vision_analyzer --probe-dxgi-outputs
xmake run vision_analyzer --input dxgi --dxgi-output 0 --verify-input --dxgi-debug
```

视频 dry-run，不移动鼠标，只输出规划日志：

```powershell
xmake run vision_analyzer --backend opencv-onnx --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx --video D:\project\cs2-vision-trainer\videos\02.mp4 --dry-run --preview --action-log actions.txt
```

真实 HID 移动前先测试板子：

```powershell
xmake run vision_analyzer --hid-port COM3 --test-hid-move 300 0
```

live 模式示例：

```powershell
xmake run vision_analyzer --backend opencv-onnx --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx --input dxgi --dxgi-output 0 --player-side ct --hid-port COM3 --hid-gain 1.0 --hid-max-step 120 --preview
```

启用左键输出需要额外传 `--hid-click`。调试阶段建议先不加该参数。

## 固件和 SDK

固件仓库位于 `tools\rp2350_keymouse_bridge_firmware`，包含：

- RP2350 Rust 固件。
- `tools\hidctl` 主机端命令行工具。
- `sdk\cpp` C++17 header-only SDK。
- `sdk\python` Python SDK。
- `tools\webui` Web Serial 调试页面。

C++ runtime 默认会从 `tools\rp2350_hid_bridge_cpp` 引用 C++ SDK。固件仓库内也用
submodule 引用了同一个 SDK，方便单独打开固件工程时测试。

## 本地数据和模型

以下内容默认不提交到 Git：

```text
videos/
datasets/
runs/
models/
dist/
*.pt
*.onnx
*.engine
*.mp4
*.avi
*.mkv
```

也就是说，公开仓库只保存源码、配置、文档和测试。视频、训练数据、模型权重、TensorRT
engine、打包产物都需要在本机生成或单独分发。

## 常用维护命令

更新所有子仓库到当前主仓库记录的提交：

```powershell
git submodule update --init --recursive
```

查看主仓库和子仓库状态：

```powershell
git status --short
git submodule status --recursive
```

如果某个子仓库更新了，需要在主仓库提交新的 submodule 指针：

```powershell
git add tools\cpp_analyzer
git commit -m "chore: update cpp analyzer submodule"
git push
```
