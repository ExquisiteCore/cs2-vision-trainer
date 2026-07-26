# 使用教程

这份教程按实际使用顺序写。先不要管项目内部结构，照着做一遍。

## 0. 你要先知道这几个东西

项目分成两部分：

```text
Python 训练端
  用来训练 YOLO，导出 best.onnx

C++ 运行端
  用 best.onnx 读取视频或屏幕，算鼠标怎么动，必要时通过板子移动鼠标
```

最终 C++ 运行端有两种用法：

```text
CLI 用法
  直接运行 vision_analyzer.exe

Python SDK 用法
  Python 程序 import cs2_vision_runtime，然后调用 vision_runtime.dll
```

需要把 SDK 冻结进调用端 EXE 并部署 app-local 模型/TensorRT 环境时，请使用完整的
[Python Runtime SDK 接入指南](PYTHON_RUNTIME_SDK_INTEGRATION.md)。本页其余命令主要用于
源码开发、逐项诊断和硬件验收。

两种用法互相独立。直接运行 `vision_analyzer.exe` 时不经过 Python SDK；Python 包只是
给需要在自己程序里嵌入 DLL 的用户准备的可选接口。

你现在最该按这个顺序来：

```text
1. 编译 C++ runtime
2. 确认模型 best.onnx 和 schema 存在
3. 先用视频 dry-run 看识别和移动规划
4. 按需选择 CLI，或者选择 Python SDK 调 DLL
5. 最后再接 DXGI + 板子并显式解锁输出
```

如果你只是想先看 Python 到底怎么调用，直接看这三个脚本：

```text
examples/runtime_video_dryrun.py   Python 调 DLL 跑视频，不动鼠标
examples/runtime_dxgi_dryrun.py    Python 调 DLL 读屏幕，不动鼠标
examples/runtime_live_move.py      Python 调 DLL 读屏幕，并通过板子移动鼠标
```

## 1. 第一次拉代码

如果是新电脑，直接这样拉：

```powershell
git clone --recurse-submodules https://github.com/ExquisiteCore/cs2-vision-trainer.git
cd cs2-vision-trainer
git submodule update --init --recursive
```

如果你已经有项目了，在主目录执行：

```powershell
cd D:\project\cs2-vision-trainer
git pull
git submodule update --init --recursive
```

确认子仓库完整：

```powershell
git submodule status --recursive
```

至少应该看到：

```text
tools/cpp_analyzer
tools/rp2350_hid_bridge_cpp
tools/rp2350_keymouse_bridge_firmware
```

## 2. 安装 Python 依赖

在主目录执行：

```powershell
cd D:\project\cs2-vision-trainer
uv sync --extra dev
```

跑测试确认 Python 环境正常：

```powershell
uv run pytest
```

看到 `passed` 就行。

## 3. 编译 C++ 运行时

进入 C++ 目录：

```powershell
cd D:\project\cs2-vision-trainer\tools\cpp_analyzer
```

编译：

```powershell
xmake f -m release
xmake
```

跑 C++ 测试：

```powershell
xmake run vision_analyzer_tests
xmake run vision_runtime_c_api_tests
```

成功后你会有这些文件：

```text
D:\project\cs2-vision-trainer\tools\cpp_analyzer\build\windows\x64\release\vision_analyzer.exe
D:\project\cs2-vision-trainer\tools\cpp_analyzer\build\windows\x64\release\vision_runtime.dll
```

`vision_analyzer.exe` 是命令行版本。

`vision_runtime.dll` 是视觉运行库；`rp2350_hid_bridge.dll` 是唯一拥有 COM 口、心跳和
请求序列的 HID 共享库。Python 调用端必须把两者作为一组部署。

## 4. 准备模型

C++ 端需要 ONNX 模型，不直接吃 `.pt`。

你应该有这两个文件：

```text
D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx
D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx.schema.json
```

如果没有，就从 `.pt` 导出：

```powershell
cd D:\project\cs2-vision-trainer
uv run --extra dev cs2-vision-trainer export `
  --model runs\detect\train\weights\best.pt `
  --format onnx `
  --imgsz 640
```

导出后再检查：

```powershell
Get-ChildItem runs\detect\train\weights\best.onnx*
```

必须同时有 `.onnx` 和 `.onnx.schema.json`。

## 5. 先用视频测试

这个阶段不会动鼠标。

进入 C++ 目录：

```powershell
cd D:\project\cs2-vision-trainer\tools\cpp_analyzer
```

先确认视频能读：

```powershell
xmake run vision_analyzer `
  --video D:\project\cs2-vision-trainer\videos\02.mp4 `
  --verify-input
```

再跑识别和规划：

```powershell
xmake run vision_analyzer `
  --backend opencv-onnx `
  --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx `
  --schema D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx.schema.json `
  --video D:\project\cs2-vision-trainer\videos\02.mp4 `
  --player-side unknown `
  --dry-run `
  --preview `
  --action-log actions.txt
```

你会看到一个预览窗口：

```text
白色十字      画面中心
检测框        YOLO 检测结果
红点/紫点     当前追踪和规划目标
```

`actions.txt` 是每帧规划出来的鼠标动作：

```text
frame timestamp_ms target dx dy click lock distance offset_x offset_y
```

重点看：

```text
target=1   说明选中了目标
dx/dy      说明这一帧计划让鼠标移动多少
click=1    说明如果不是 dry-run，这一帧会左键
```

## 6. 用 Python SDK 调 DLL 跑视频

这个也是不会动鼠标的测试。

最简单是直接运行项目里已经写好的示例：

```powershell
cd D:\project\cs2-vision-trainer
uv run python examples\runtime_video_dryrun.py
```

这个脚本本质上就是下面这段代码：

```python
from cs2_vision_runtime import VisionRuntime

MODEL = r"D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx"
SCHEMA = r"D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx.schema.json"
VIDEO = r"D:\project\cs2-vision-trainer\videos\02.mp4"

with VisionRuntime() as rt:
    rt.set_model(MODEL, schema_path=SCHEMA, backend="opencv-onnx")
    rt.set_frame_limits(max_frames=300, warmup_frames=3)
    rt.open_video(VIDEO, dry_run=True)

    while True:
        action = rt.process_next()
        if action is None:
            break

        if action.frame_index % 30 == 0:
            print(
                "frame=", action.frame_index,
                "target=", int(action.has_target),
                "dx=", action.dx,
                "dy=", action.dy,
                "click=", int(action.click_left),
                "lock=", action.lock_state.name,
            )
```

如果输出类似这样，说明 Python 已经成功调用 C++ DLL：

```text
frame= 0 target= 0 dx= 0 dy= 0 click= 0 lock= IDLE
frame= 30 target= 1 dx= 12 dy= -3 click= 0 lock= TRACKING
```

如果报找不到 DLL，手动指定：

```powershell
$env:CS2_VISION_RUNTIME_DLL="D:\project\cs2-vision-trainer\tools\cpp_analyzer\build\windows\x64\release\vision_runtime.dll"
uv run python examples\runtime_video_dryrun.py
```

## 7. 检查 DXGI 屏幕输入

先不要接鼠标移动，先确认能读当前屏幕。

```powershell
cd D:\project\cs2-vision-trainer\tools\cpp_analyzer
xmake run vision_analyzer --list-dxgi-outputs
xmake run vision_analyzer --probe-dxgi-outputs
```

找 `duplicate_output=0x0` 的那一项。

假设是 output 0：

```powershell
xmake run vision_analyzer `
  --input dxgi `
  --dxgi-output 0 `
  --verify-input `
  --dxgi-debug
```

能输出宽高和 RGB 均值，就说明屏幕输入通了。

## 8. 使用 Python SDK 进行 DXGI 试运行

这个阶段仍然不会动鼠标，直接使用仓库里的现成脚本：

```powershell
cd D:\project\cs2-vision-trainer
uv run python examples\runtime_dxgi_dryrun.py --backend opencv-onnx --output 0
```

脚本只调用 DLL 读取 DXGI 和生成规划动作，不设置 HID 端口，也不会解锁真实输出。

## 9. 检查板子是否能移动鼠标

先找板子的 COM 口。

可以用设备管理器看，也可以用固件 Python SDK：

```powershell
cd D:\project\cs2-vision-trainer\tools\rp2350_keymouse_bridge_firmware\sdk\python
uv run python examples\list_ports.py
```

假设板子是 `COM3`。

如果板子还没有固件，可以在固件仓库生成 Pico 2 BOOTSEL UF2：

```powershell
cd D:\project\cs2-vision-trainer\tools\rp2350_keymouse_bridge_firmware
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build-release.ps1
```

产物是 `dist\rp2350-keymouse-bridge-firmware.uf2`。这个脚本只生成 UF2，不会刷写；把
Pico 2 置于 BOOTSEL 后，由你手动复制到板子的盘符。

先只移动，不点击：

```powershell
cd D:\project\cs2-vision-trainer\tools\cpp_analyzer
xmake run vision_analyzer --hid-port COM3 --test-hid-move 300 0
```

如果鼠标向右动了，说明板子和 HID SDK 是通的。

## 10. 实时 DXGI + 板子移动

这一阶段会产生真实鼠标移动。可以选 CLI 或 Python SDK，两条路径不需要同时使用。

### 10.1 直接使用 C++ CLI（不使用 Python SDK）

先在已经进入对局且画面稳定时标定：

```powershell
cd D:\project\cs2-vision-trainer\tools\cpp_analyzer
xmake run vision_analyzer `
  --calibrate-hid `
  --hid-port COM3 `
  --dxgi-output 0 `
  --calibration-output hid-calibration.txt `
  --calibration-config-output hid-tuned.cfg
```

检查生成的 `hid-tuned.cfg`，然后显式增加 `--output-enabled` 启动真实移动：

```powershell
xmake run vision_analyzer `
  --config hid-tuned.cfg `
  --backend opencv-onnx `
  --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx `
  --input dxgi `
  --dxgi-output 0 `
  --player-side ct `
  --hid-port COM3 `
  --preview `
  --output-enabled
```

不加 `--output-enabled` 时只识别和规划，不会向板子发送移动或点击。

### 10.2 使用 Python SDK 调 DLL

现成示例由调用端创建一个 `HidSession`，把同一个原生句柄交给视觉 DLL，然后按需加载
或执行标定：

```powershell
cd D:\project\cs2-vision-trainer
uv run python examples\runtime_live_move.py `
  --app-dir .\dist\MyClient `
  --data-dir "$env:LOCALAPPDATA\MyClient" `
  --hid-port COM3 `
  --player-side ct `
  --enable-live-output
```

`--enable-live-output` 是显式硬件授权；不加时脚本会在标定前直接退出。按 `Ctrl+C` 时，
退出 `armed_output()` 只关闭开火和视觉移动，不会释放调用端保持的键；最外层会话结束
时才在 `finally` 中调用 `hid.stop_all()`。

## 11. 开启左键

确认移动和标定正常后，再打开点击。

CLI 路径在实时命令中增加：

```text
--hid-click
```

Python 示例增加：

```text
--click
```

Python SDK 的移动与开火是两个独立开关：`set_output_enabled(True)` 只解锁移动，
`set_fire_enabled(True)` 才解锁自动开火。视觉撤销不会全局释放，紧急停止或整个控制
会话结束时由调用端执行 `hid.stop_all()`。

## 12. 最常见的问题

### 找不到 vision_runtime.dll 或 rp2350_hid_bridge.dll

先编译：

```powershell
cd D:\project\cs2-vision-trainer\tools\cpp_analyzer
xmake f -m release
xmake build vision_runtime
```

或者设置环境变量：

```powershell
$env:CS2_VISION_RUNTIME_DLL="D:\project\cs2-vision-trainer\tools\cpp_analyzer\build\windows\x64\release\vision_runtime.dll"
```

### 缺少模型结构说明文件

重新导出 ONNX：

```powershell
cd D:\project\cs2-vision-trainer
uv run --extra dev cs2-vision-trainer export `
  --model runs\detect\train\weights\best.pt `
  --format onnx `
  --imgsz 640
```

### DXGI 读不到画面

先跑：

```powershell
cd D:\project\cs2-vision-trainer\tools\cpp_analyzer
xmake run vision_analyzer --probe-dxgi-outputs
```

换 `duplicate_output=0x0` 的 output。

### Python SDK 能跑视频，但 DXGI 不行

说明 DLL 和模型没问题，问题在屏幕捕获。

优先检查：

```text
output 是否选错
是否远程桌面
是否 HDR / 独显集显输出不一致
程序是否有权限
```

### 鼠标能动，但方向或幅度不对

先回到稳定画面重新运行启动标定。标定质量差时不要继续实时输出；确认 DXGI 输出、
分辨率、鼠标灵敏度和窗口状态没有变化。

需要手工微调旧的标量参数时再使用：

```python
rt.set_hid_tuning(gain=0.5, max_step=80, deadzone_px=2.0)
```

经验：

```text
移动太慢      提高 gain
移动太猛      降低 gain 或 max_step
小范围抖动    提高 deadzone_px
追不上目标    提高 max_step 或 gain
```

## 13. 你现在最短应该跑哪几条

如果你只使用 C++ CLI，按这几条即可，不需要 Python SDK：

```powershell
cd D:\project\cs2-vision-trainer
uv sync --extra dev

cd tools\cpp_analyzer
xmake f -m release
xmake
xmake run vision_analyzer_tests
xmake run vision_runtime_c_api_tests

xmake run vision_analyzer --video D:\project\cs2-vision-trainer\videos\02.mp4 --verify-input
```

如果还要确认可选 Python SDK 与真实 DLL 兼容，再执行：

```powershell
cd D:\project\cs2-vision-trainer
$env:CS2_VISION_RUNTIME_DLL="D:\project\cs2-vision-trainer\tools\cpp_analyzer\build\windows\x64\release\vision_runtime.dll"

uv run pytest tests\test_vision_runtime_sdk.py
uv run python -c "from cs2_vision_runtime import VisionRuntime; rt=VisionRuntime(); rt.close(); print('ok')"
```

看到 `ok`，说明 Python 已经能加载 C++ DLL。
