# Build Guide

本文档说明主仓库和所有子仓库的编译、测试和验证方式。命令默认在 Windows
PowerShell 中执行。

## 1. 基础环境

建议使用 Windows 10/11 x64。需要安装：

```text
Git
Python 3.11+
uv
Visual Studio 2022 Build Tools，包含 MSVC C++ 工具链
xmake
CMake 3.20+
Rust stable，支持 edition 2024
picotool，用于 RP2350 固件烧录
```

可选依赖：

```text
NVIDIA Driver / CUDA / cuDNN
ONNX Runtime GPU
TensorRT
```

C++ runtime 默认可以使用 `opencv-onnx` 后端，不要求 CUDA、ONNX Runtime 或
TensorRT。GPU 后端只在需要加速时配置。

## 2. 拉取源码

公开仓库可以直接用 HTTPS 拉取：

```powershell
git clone --recurse-submodules https://github.com/ExquisiteCore/cs2-vision-trainer.git
cd cs2-vision-trainer
git submodule update --init --recursive
```

验证：

```powershell
git submodule status --recursive
```

应该至少包含：

```text
tools/cpp_analyzer
tools/rp2350_hid_bridge_cpp
tools/rp2350_keymouse_bridge_firmware
tools/rp2350_keymouse_bridge_firmware/sdk/cpp
tools/rp2350_keymouse_bridge_firmware/sdk/python
```

## 3. Python 训练端

安装依赖：

```powershell
uv sync --extra dev
```

如果需要 ONNX Runtime GPU Python 包：

```powershell
uv sync --extra dev --extra accel
```

运行测试：

```powershell
uv run pytest
```

启动 GUI：

```powershell
uv run --extra dev cs2-vision-trainer-gui
```

训练和导出示例：

```powershell
uv run --extra dev cs2-vision-trainer prepare-dataset --root datasets\cs2_multiclass

uv run --extra dev cs2-vision-trainer train `
  --data datasets\cs2_multiclass\dataset.yaml `
  --model models\base\yolov8n.pt `
  --epochs 50 `
  --imgsz 640 `
  --batch 8 `
  --device 0

uv run --extra dev cs2-vision-trainer export `
  --model runs\detect\train\weights\best.pt `
  --format onnx `
  --imgsz 640
```

导出后 C++ runtime 通常使用：

```text
runs\detect\train\weights\best.onnx
runs\detect\train\weights\best.onnx.schema.json
```

## 4. C++ Runtime

目录：

```powershell
cd tools\cpp_analyzer
```

默认 release 编译：

```powershell
xmake f -m release
xmake
```

运行 C++ 单元测试：

```powershell
xmake run vision_analyzer_tests
```

构建 DLL 和 C API 测试：

```powershell
xmake build vision_runtime
xmake run vision_runtime_c_api_tests
```

DLL 产物位置：

```text
tools\cpp_analyzer\build\windows\x64\release\vision_runtime.dll
tools\cpp_analyzer\build\windows\x64\release\vision_runtime.lib
```

如果要显式指定 SDK：

```powershell
xmake f -m release --hid_sdk_root=..\rp2350_hid_bridge_cpp
xmake
```

如果要启用 ONNX Runtime 后端：

```powershell
$env:ONNXRUNTIME_ROOT = "D:\SDK\onnxruntime-win-x64-gpu"
xmake f -m release --onnxruntime_root=$env:ONNXRUNTIME_ROOT --hid_sdk_root=..\rp2350_hid_bridge_cpp
xmake
```

验证视频输入：

```powershell
xmake run vision_analyzer --video D:\project\cs2-vision-trainer\videos\02.mp4 --verify-input
```

验证 DXGI 屏幕输入：

```powershell
xmake run vision_analyzer --list-dxgi-outputs
xmake run vision_analyzer --probe-dxgi-outputs
xmake run vision_analyzer --input dxgi --dxgi-adapter 0 --dxgi-output 0 --verify-input --dxgi-debug
```

视频 dry-run：

```powershell
xmake run vision_analyzer `
  --backend opencv-onnx `
  --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx `
  --video D:\project\cs2-vision-trainer\videos\02.mp4 `
  --player-side unknown `
  --dry-run `
  --preview `
  --action-log actions.txt
```

真实 HID 输出前，先检查板子是否能动：

```powershell
xmake run vision_analyzer --hid-port COM3 --test-hid-move 300 0
```

live DXGI 运行：

```powershell
xmake run vision_analyzer `
  --backend opencv-onnx `
  --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx `
  --input dxgi `
  --dxgi-output 0 `
  --player-side ct `
  --hid-port COM3 `
  --hid-gain 1.0 `
  --hid-max-step 120 `
  --preview
```

启用点击：

```powershell
xmake run vision_analyzer `
  --backend opencv-onnx `
  --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx `
  --input dxgi `
  --dxgi-output 0 `
  --player-side ct `
  --hid-port COM3 `
  --hid-click `
  --hid-click-cooldown 6
```

live HID 模式要求模型旁边存在 schema，例如：

```text
best.onnx.schema.json
```

否则 runtime 会拒绝启动，避免类别顺序不一致。

## 4.1 Python SDK 调用 Runtime DLL

主仓库提供 `cs2_vision_runtime` Python 包。它通过 `ctypes` 加载
`vision_runtime.dll`，适合给其他 Python 程序直接集成。

最小 dry-run 示例：

```python
from cs2_vision_runtime import VisionRuntime

with VisionRuntime() as runtime:
    runtime.set_model(
        "runs/detect/train/weights/best.onnx",
        schema_path="runs/detect/train/weights/best.onnx.schema.json",
        backend="opencv-onnx",
    )
    runtime.open_video("videos/02.mp4", dry_run=True)

    while True:
        action = runtime.process_next()
        if action is None:
            break
        print(action.frame_index, action.dx, action.dy, action.click_left)
```

DXGI live 示例：

```python
from cs2_vision_runtime import VisionRuntime

with VisionRuntime() as runtime:
    runtime.set_model(
        "runs/detect/train/weights/best.onnx",
        schema_path="runs/detect/train/weights/best.onnx.schema.json",
        backend="opencv-onnx",
    )
    runtime.set_hid_tuning(gain=1.0, max_step=120, deadzone_px=1.5)
    runtime.set_hid_click(enabled=False)
    runtime.open_dxgi(output=0, player_side="ct", hid_port="COM3", dry_run=False)

    while True:
        action = runtime.process_next()
        if action is None:
            break
```

DLL 自动查找顺序：

```text
CS2_VISION_RUNTIME_DLL 环境变量
src\cs2_vision_runtime\vision_runtime.dll
src\cs2_vision_runtime\bin\vision_runtime.dll
tools\cpp_analyzer\build\windows\x64\release\vision_runtime.dll
tools\cpp_analyzer\build\windows\x64\debug\vision_runtime.dll
```

## 5. RP2350 HID Bridge C++ SDK

目录：

```powershell
cd tools\rp2350_hid_bridge_cpp
```

独立编译和测试：

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
.\build\Release\test_protocol.exe
```

这个 SDK 是 header-only。其他 CMake 项目可以这样引用：

```cmake
add_subdirectory(path/to/rp2350-hid-bridge-cpp)
target_link_libraries(your_app PRIVATE rp2350_hid_bridge)
```

## 6. RP2350 HID Bridge Python SDK

目录：

```powershell
cd tools\rp2350_keymouse_bridge_firmware\sdk\python
```

安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -e .
```

测试：

```powershell
.\.venv\Scripts\python -m unittest discover -s tests
```

列出串口：

```powershell
.\.venv\Scripts\python examples\list_ports.py
```

连接板子并执行 ping：

```powershell
.\.venv\Scripts\python examples\basic.py --port COM3
```

## 7. RP2350 固件

目录：

```powershell
cd tools\rp2350_keymouse_bridge_firmware
```

安装 Rust 目标：

```powershell
rustup target add thumbv8m.main-none-eabihf
```

主机侧单元测试：

```powershell
cargo test --target x86_64-pc-windows-msvc --lib
```

固件编译：

```powershell
cargo build --release
```

产物位置：

```text
target\thumbv8m.main-none-eabihf\release\rp2350-keymouse-bridge-firmware
```

`.cargo\config.toml` 已经配置了默认 target 和 picotool runner。设置
`PICOTOOL_PATH` 后可以直接烧录：

```powershell
$env:PICOTOOL_PATH = "D:\Tool\picotool\picotool.exe"
cargo run --release
```

也可以手动调用 picotool：

```powershell
& $env:PICOTOOL_PATH load -u -v -x -t elf target\thumbv8m.main-none-eabihf\release\rp2350-keymouse-bridge-firmware
```

`tools\hidctl` 是主机端串口调试工具：

```powershell
cargo build --manifest-path tools\hidctl\Cargo.toml --release --target x86_64-pc-windows-msvc
.\tools\hidctl\target\x86_64-pc-windows-msvc\release\hidctl.exe --help
```

## 8. 常见问题

### 子模块为空

执行：

```powershell
git submodule update --init --recursive
```

### C++ runtime 找不到 OpenCV

第一次 `xmake` 会安装或解析 OpenCV 包。确认机器能访问 xmake 包源，并且 MSVC 工具链
可用。

### DXGI DuplicateOutput 失败

先运行：

```powershell
xmake run vision_analyzer --probe-dxgi-outputs
```

选择 `duplicate_output=0x0` 的 adapter/output。混合显卡机器通常要选择实际连接屏幕的
显卡输出，不一定是高性能独显。

### live 模式提示 schema 缺失

重新从 Python 端导出 ONNX：

```powershell
uv run --extra dev cs2-vision-trainer export --model runs\detect\train\weights\best.pt --format onnx --imgsz 640
```

确认 `best.onnx.schema.json` 和 `best.onnx` 在同一目录。

### 模型和视频没有出现在 GitHub

这是预期行为。`videos/`、`datasets/`、`runs/`、`models/`、`*.pt`、`*.onnx`、
`*.engine`、`*.mp4` 默认不提交。
