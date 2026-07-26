# 构建指南

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
elf2uf2-rs，用于生成 Pico 2 BOOTSEL UF2
picotool，用于 RP2350 固件烧录
```

可选依赖：

```text
NVIDIA Driver / CUDA / cuDNN
ONNX Runtime GPU
TensorRT
```

C++ 运行时默认可以使用 `opencv-onnx` 后端，不要求 CUDA、ONNX Runtime 或
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

导出后 C++ 运行时通常使用：

```text
runs\detect\train\weights\best.onnx
runs\detect\train\weights\best.onnx.schema.json
```

## 4. C++ 运行时

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

视频试运行：

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

实时 DXGI 运行：

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
  --preview `
  --output-enabled
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
  --hid-click-cooldown 6 `
  --output-enabled
```

实时 HID 模式要求模型旁边存在模型结构说明文件，例如：

```text
best.onnx.schema.json
```

否则运行时会拒绝启动，避免类别顺序不一致。

## 4.1 Python SDK 调用运行时 DLL

主仓库提供 `cs2_vision_runtime` Python 包。它通过 `ctypes` 加载
`vision_runtime.dll` 与 `rp2350_hid_bridge.dll`，适合给其他 Python 程序直接集成。
这是可选调用方式；直接使用 `vision_analyzer.exe` 的程序不需要 Python SDK。

最小试运行示例：

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

DXGI 实时示例：

```python
from cs2_vision_runtime import HidSession, VisionRuntime

with HidSession("COM3", app_dir=app_dir) as hid:
    try:
        with VisionRuntime.from_app_dir(
            app_dir,
            data_dir=data_dir,
            hid_session=hid,
        ) as runtime:
            runtime.set_hid_calibration_path(data_dir / "hid-calibration.json")
            profile = runtime.get_hid_calibration()
            if not profile.valid:
                profile = runtime.calibrate_hid(adapter=0, output=0)
            runtime.open_dxgi(output=0, player_side="ct", dry_run=False)
            with runtime.armed_output(fire=False):
                while runtime.process_next() is not None:
                    pass
    finally:
        hid.stop_all()
```

新建运行时的移动和开火开关默认关闭。`calibrate_hid()` 是启动时受控标定；正常实时
输出仍必须显式调用 `set_output_enabled(True)`，自动开火还必须单独调用
`set_fire_enabled(True)`。推荐直接运行 `examples\runtime_live_move.py`：

```powershell
uv run python examples\runtime_live_move.py --app-dir .\dist\MyClient --hid-port COM3 --player-side ct --enable-live-output
```

只有确认需要自动开火时才额外增加 `--click`。

DLL 自动查找顺序：

```text
CS2_VISION_RUNTIME_DLL 环境变量
src\cs2_vision_runtime\vision_runtime.dll
src\cs2_vision_runtime\bin\vision_runtime.dll
tools\cpp_analyzer\build\windows\x64\release\vision_runtime.dll
tools\cpp_analyzer\build\windows\x64\debug\vision_runtime.dll
```

## 4.2 GTX 1080 Ti / SM61 便携包

便携包固定使用 ONNX Runtime GPU 1.17.3、CUDA 11.8、cuDNN 8.9.7、TensorRT
8.6.1.6 和 FP32。先使用相同 ONNX Runtime SDK 构建 Release 运行时：

```powershell
cd tools\cpp_analyzer
$env:ONNXRUNTIME_ROOT = "D:\runtime\sm61\onnxruntime-win-x64-gpu-1.17.3"
xmake f -c -m release --onnxruntime_root=$env:ONNXRUNTIME_ROOT --hid_sdk_root=..\rp2350_hid_bridge_cpp
xmake
```

TensorRT 官方 ZIP 需要登录 NVIDIA 并接受许可后手动下载。随后从 C++ 目录组装便携包；
其余公开依赖可按锁定清单下载并校验 SHA-256：

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File packaging\sm61\build-portable-package.ps1 `
  -PythonProjectRoot ..\.. `
  -OrtRoot $env:ONNXRUNTIME_ROOT `
  -ModelPath ..\..\runs\detect\train\weights\best.onnx `
  -SchemaPath ..\..\runs\detect\train\weights\best.onnx.schema.json `
  -SampleVideoPath ..\..\videos\02.mp4 `
  -TensorRtArchive D:\runtime\sm61\TensorRT-8.6.1.6.Windows10.x86_64.cuda-11.8.zip `
  -DownloadPublicDependencies
```

默认输出为父项目的 `dist\cs2-vision-runtime-sm61` 目录及同名 ZIP。包内
`一键检查并测试.cmd` 始终使用试运行模式，不会标定、移动或点击；真实输出仍需在 Python
示例中显式增加 `--enable-live-output`。

## 5. RP2350 HID 桥接器 C++ SDK

目录：

```powershell
cd tools\rp2350_hid_bridge_cpp
```

独立编译和测试：

```powershell
cmake -S . -B build
cmake --build build --config Release
.\build\Release\test_protocol.exe
```

这个 SDK 构建稳定 C ABI 的 `rp2350_hid_bridge.dll` 和 C++ RAII 包装。其他 CMake
项目可以这样引用：

```cmake
add_subdirectory(path/to/rp2350-hid-bridge-cpp)
target_link_libraries(your_app PRIVATE rp2350_hid_bridge)
```

## 6. RP2350 HID 桥接器 Python SDK

目录：

```powershell
cd tools\rp2350_keymouse_bridge_firmware\sdk\python
```

安装：

```powershell
uv sync
```

测试：

```powershell
uv run python -m unittest discover -s tests
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
cargo install elf2uf2-rs --locked
```

主机侧单元测试：

```powershell
cargo test --target x86_64-pc-windows-msvc --lib
```

这些测试只运行纯协议/状态逻辑和模拟传输层。自动化测试禁止调用 picotool、刷写
板子、选择串口或发送真实 HID；硬件验收必须另行人工授权。

固件编译：

```powershell
cargo build --release
```

`cargo build --release` 只编译、链接并生成固件产物，不运行 Cargo runner，不调用
picotool，也不打开串口或发送 HID。

产物位置：

```text
target\thumbv8m.main-none-eabihf\release\rp2350-keymouse-bridge-firmware
```

生成可直接拖入 Pico 2 BOOTSEL 盘符的 UF2：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build-release.ps1
```

脚本会重新执行 Release 构建，校验每个 UF2 块，并使用 RP2350 ARM Secure family ID
`0xE48BFF59`。它只生成文件，不刷写、不打开串口、不发送 HID。输出为：

```text
dist\rp2350-keymouse-bridge-firmware.uf2
```

UF2 构建脚本的无硬件集成检查：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\tests\build-release-uf2.ps1
```

开发构建默认 USB VID/PID 为 `0xCAFE:0x2350`。可在编译前用十进制或
`0x` 前缀十六进制 `u16` 覆盖；非法值会让构建失败：

```powershell
$env:RP2350_USB_VID = "0x1234"
$env:RP2350_USB_PID = "0x5678"
cargo build --release
```

生产分发必须使用合法分配的 USB 标识。启动时固件读取 RP2350 OTP 芯片 ID，将 USB
序列号格式化为 `EXQC-KMOUSE-` 加 16 位大写十六进制数。当前实现没有固定或伪造的
备用序列号：`embassy_rp::otp::get_chipid()` 失败会在 USB 枚举前触发 panic。

`.cargo\config.toml` 的 runner 委托给 `tools\flash.ps1`。脚本优先使用
`PICOTOOL_PATH`，否则从 `PATH` 解析 `picotool`。以下命令只校验已有产物并输出工具
路径，不执行 picotool：

```powershell
$env:PICOTOOL_PATH = "D:\Tool\picotool\picotool.exe"
powershell -NoProfile -ExecutionPolicy Bypass -File tools\flash.ps1 target\thumbv8m.main-none-eabihf\release\rp2350-keymouse-bridge-firmware -ResolveOnly
```

刷写是独立、显式的硬件动作。仅在板子已进入 BOOTSEL 且明确决定刷写后，才移除
`-ResolveOnly`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\flash.ps1 target\thumbv8m.main-none-eabihf\release\rp2350-keymouse-bridge-firmware
```

该命令会执行 `picotool load -u -v -x -t elf`。`cargo run --release` 也会调用相同
runner，因此属于刷写动作，不是构建或测试命令；本文验证不执行它们。

### 7.1 协议 v2 与键盘状态

固件默认使用协议 v2，并继续接受 `flags=0`、序列号非零的有效 v1 请求作为基础兼容。
v1 `GET_CAPS` 只报告键盘、鼠标、ASCII 和批处理基础能力，不承诺 v2 的安全重试、
租约或取消保证；v2 的序列号 0 与 `NO_RESPONSE` 仅用于心跳。

键盘状态保存 8 个修饰位与最多 6 个不同的非修饰键码。`keycode=0` 表示纯修饰键操作，
可单独按下/释放 Shift、Ctrl、Alt 或 GUI。第 7 个不同普通键会被事务式拒绝，按键数组
和同一请求携带的修饰位都保持原状；`KEY_UP` 只清除请求指定的键和修饰位。

### 7.2 心跳、DTR、批处理与 STOP

v2 客户端打开连接后每 500 毫秒发送一次无响应心跳；有效 v2 流量刷新 2 秒控制租约。
只有存在保持中的输入、正在收集/执行的批处理或活动长操作时，租约到期才触发取消和
全输入释放。DTR 下降沿或 USB 禁用会触发相同的会话重置；v1 流量不会启动租约，避免
不发送心跳的旧客户端在 2 秒后意外释放按键。

`BATCH_BEGIN` 用影子状态收集并预验证最多 32 条命令和 8 KiB 载荷；`BATCH_END` 后
独占、按序执行。该保证只覆盖“执行前验证和不被普通命令插入”，不是对已发送物理 HID
报告的回滚。`STOP_ALL`、DTR 丢失、USB 禁用和租约到期可在等待、逐字符输入、分段
移动、点击延迟及批处理命令之间的协作边界取消；尚未执行的批处理命令会被丢弃，固件
随后尽力释放全部键盘和鼠标状态。显式批处理之外不存在隐藏的普通命令队列。

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

### C++ 运行时找不到 OpenCV

第一次 `xmake` 会安装或解析 OpenCV 包。确认机器能访问 xmake 包源，并且 MSVC 工具链
可用。

### DXGI DuplicateOutput 失败

先运行：

```powershell
xmake run vision_analyzer --probe-dxgi-outputs
```

选择 `duplicate_output=0x0` 的适配器/输出。混合显卡机器通常要选择实际连接屏幕的
显卡输出，不一定是高性能独显。

### 实时模式提示模型结构说明文件缺失

重新从 Python 端导出 ONNX：

```powershell
uv run --extra dev cs2-vision-trainer export --model runs\detect\train\weights\best.pt --format onnx --imgsz 640
```

确认 `best.onnx.schema.json` 和 `best.onnx` 在同一目录。

### 模型和视频没有出现在 GitHub

这是预期行为。`videos/`、`datasets/`、`runs/`、`models/`、`*.pt`、`*.onnx`、
`*.engine`、`*.mp4` 默认不提交。
