# CS2 Vision Trainer（CS2 视觉训练器）

CS2 Vision Trainer 是一个分模块的视觉训练与运行项目。项目由 Python 训练端、C++
实时运行端、RP2350 外置键鼠桥接固件，以及对应的 C++/Python SDK 组成。

Python 部分只负责数据集、标注、训练、测试和模型导出。C++ 部分负责加载导出的
YOLO 模型，读取视频或 DXGI 屏幕画面，执行检测、目标融合、跟踪、滤波、预测和鼠标
路线规划。RP2350 固件通过 CDC 串口接收命令，并以标准 USB HID 键盘/鼠标报告输出。

项目不依赖游戏内存读取、进程注入或游戏内叠加层。

## 仓库结构

主仓库通过 Git 子模块组织运行端和硬件端代码：

```text
cs2-vision-trainer
├─ src/                              Python 训练、标注、导出、预览代码
├─ tests/                            Python 测试
├─ docs/                             设计文档和编译文档
├─ tools/
│  ├─ cpp_analyzer                   C++ 实时识别和控制端子模块
│  ├─ rp2350_hid_bridge_cpp          RP2350 HID 桥接器 C++ SDK 子模块
│  └─ rp2350_keymouse_bridge_firmware RP2350 固件工程子模块
│     └─ sdk/
│        ├─ cpp                      固件仓库内引用的 C++ SDK 子模块
│        └─ python                   固件仓库内引用的 Python SDK 子模块
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

第一次拉取必须带上子模块：

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
- C++ 运行时使用 xmake 编译、测试、视频输入验证和 DXGI 输入验证。
- C++ SDK 使用 CMake 编译测试。
- Python SDK 安装和单元测试。
- RP2350 固件 Rust 交叉编译、Pico 2 UF2 打包、仅构建验证和显式烧录方式。

第一次使用建议先看 [docs/USAGE.md](docs/USAGE.md)，它按实际操作顺序写，从编译
DLL、运行视频试运行、Python SDK 调用，到 DXGI 和板卡移动。

最小构建流程：

```powershell
# Python 训练端
uv sync --extra dev
uv run pytest

# C++ 运行时
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

导出 ONNX 时会在模型旁边生成模型结构说明 JSON。C++ 实时模式会强制校验该文件，
避免模型类别顺序错位。

## C++ 实时运行端

C++ 运行时位于 `tools\cpp_analyzer`。它读取视频或 DXGI 屏幕输入，执行 YOLO
推理、身体/头部融合、目标跟踪、卡尔曼滤波、延迟预测、相对鼠标路径规划，并通过
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

视频试运行，不移动鼠标，只输出规划日志：

```powershell
xmake run vision_analyzer --backend opencv-onnx --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx --video D:\project\cs2-vision-trainer\videos\02.mp4 --dry-run --preview --action-log actions.txt
```

真实 HID 移动前先测试板子：

```powershell
xmake run vision_analyzer --hid-port COM3 --test-hid-move 300 0
```

实时模式示例（`--output-enabled` 是实际移动的显式解锁开关）：

```powershell
xmake run vision_analyzer --backend opencv-onnx --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx --input dxgi --dxgi-output 0 --player-side ct --hid-port COM3 --hid-gain 1.0 --hid-max-step 120 --preview --output-enabled
```

启用左键输出需要额外传 `--hid-click`。调试阶段建议先不加该参数；不传
`--output-enabled` 时，运行时仍会识别和规划，但不会向 RP2350 发送真实移动或点击。

## Python 调用 C++ 运行时

C++ 运行时也可以编译为 `vision_runtime.dll`，然后通过 Python SDK
`cs2_vision_runtime` 被其他程序直接调用，不需要启动 `vision_analyzer.exe`。
Python SDK 是可选集成方式；如果你的程序直接运行 `vision_analyzer.exe`，不需要安装或
调用这个 Python 包，但父仓仍会维护它与 DLL 的接口兼容性。

编译 DLL：

```powershell
cd tools\cpp_analyzer
xmake f -m release
xmake build vision_runtime
cd ..\..
```

Python 全自动调用顺序（无 UI）：

```python
from cs2_vision_runtime import VisionRuntime

with VisionRuntime() as rt:
    rt.set_model(
        "runs/detect/train/weights/best.onnx",
        schema_path="runs/detect/train/weights/best.onnx.schema.json",
        backend="ort-tensorrt",
    )
    rt.set_hid_port("COM3")

    # 进入对局并保持画面稳定后，每次启动调用一次。
    profile = rt.calibrate_hid(adapter=0, output=0)
    print(profile.quality, profile.x_counts_per_pixel, profile.y_counts_per_pixel)

    rt.set_fire_policy(
        body_enabled=True,
        head_confidence=0.35,
        body_confidence=0.45,
        cooldown_frames=3,
    )
    rt.open_dxgi(
        adapter=0,
        output=0,
        player_side="ct",
        hid_port="COM3",
        dry_run=False,
    )

    try:
        rt.set_output_enabled(True)  # 允许 DLL 输出瞄准移动
        rt.set_fire_enabled(True)    # 允许 DLL 自动开火
        while rt.process_next() is not None:
            pass
    finally:
        rt.set_fire_enabled(False)
        rt.set_output_enabled(False)
        rt.stop_all()
```

`set_output_enabled` 与 `set_fire_enabled` 是两个独立开关。新建运行时默认都关闭；
标定是普通输出关闭时唯一允许发送的受控测试移动。标定失败不会安装部分曲线，
请等画面稳定后重试。完整命令行示例见 `examples/runtime_live_move.py`，真实输出必须
显式增加 `--enable-live-output`，自动开火还需增加 `--click`。

如果 DLL 不在默认构建目录，可以指定环境变量：

```powershell
$env:CS2_VISION_RUNTIME_DLL="D:\path\to\vision_runtime.dll"
```

当 DLL 位于便携包的 `app` 目录时，包装层会自动注册包内的 TensorRT、cuDNN、
CUDA 和 MSVC 私有 DLL 目录，不需要修改系统 PATH 或安装完整 CUDA Toolkit。
GTX 1080 Ti/SM61 便携包的构建命令见 [docs/BUILD.md](docs/BUILD.md)，包内的一键诊断
始终采用试运行模式，不会自动解锁 RP2350 输出。

## 固件和 SDK

固件仓库位于 `tools\rp2350_keymouse_bridge_firmware`，包含：

- RP2350 Rust 固件。
- `tools\hidctl` 主机端命令行工具。
- `sdk\cpp` C++17 仅头文件 SDK。
- `sdk\python` Python SDK。
- `tools\webui` Web Serial 调试页面。

C++ 运行时默认会从 `tools\rp2350_hid_bridge_cpp` 引用 C++ SDK。固件仓库内也通过
子模块引用同一个 SDK，方便单独打开固件工程时测试。

固件开发构建默认 USB VID/PID 为 `0xCAFE:0x2350`，可用
`RP2350_USB_VID`/`RP2350_USB_PID` 在编译时覆盖。USB 序列号来自 RP2350 OTP 芯片
ID，格式为 `EXQC-KMOUSE-` 加 16 位大写十六进制数；当前代码没有共享的备用序列号，
OTP 读取失败会在 USB 枚举前触发 panic。

协议 v2 是默认版本；v1 保留标志为零、序列号非零的基础命令兼容，但不声明 v2 的
安全重试、心跳租约或取消能力。键盘状态支持 8 个修饰位、最多 6 个不同普通键，以及
`keycode=0` 的纯修饰键操作；第 7 个不同普通键会在不改变现有按键或修饰位状态的
前提下被拒绝。

v2 客户端以 500 毫秒心跳维持 2 秒控制租约；DTR 下降、USB 禁用或存在受保护工作时，
租约到期都会取消活动操作并尽力释放全部输入。批处理在 `BATCH_BEGIN` 后预验证最多
32 条命令和 8 KiB 载荷，`BATCH_END` 后独占按序执行；已经发出的物理 HID 报告不能
回滚。`STOP_ALL` 可在等待、逐字符、分段移动、延时与批处理命令的协作边界取消，
丢弃尚未执行的批处理内容并释放输入。

`cargo build --release` 只生成 ELF 固件，不刷写、不打开串口、不发送 HID。需要供 Pico 2
BOOTSEL 拖放的 UF2 时，运行固件仓库的 `tools\build-release.ps1`，产物为
`dist\rp2350-keymouse-bridge-firmware.uf2`。刷写必须单独、显式调用 `tools\flash.ps1`
（省略 `-ResolveOnly` 才会执行 picotool）。自动化测试只能使用纯逻辑/模拟传输层，
禁止刷写或发送真实 HID；本次文档验证也不执行任何刷写、串口或 HID 动作。完整命令见
[docs/BUILD.md](docs/BUILD.md)。

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
引擎、打包产物都需要在本机生成或单独分发。

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

如果某个子仓库更新了，需要在主仓库提交新的子模块指针：

```powershell
git add tools\cpp_analyzer
git commit -m "chore: update cpp analyzer submodule"
git push
```
