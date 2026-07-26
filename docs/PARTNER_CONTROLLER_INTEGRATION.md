# Python 主控接入 CS2 Vision Runtime 环境包

本文面向负责开发和冻结 Python 主控 EXE 的合作方。环境包已经包含模型推理、GPU 运行库、
视觉 DLL 和 RP2350 板子中间件；主控不需要自己实现串口协议，也不要手工调用 ctypes.CDLL
加载任意 DLL。两个 Python SDK 会按清单和绝对路径完成加载、ABI 校验与生命周期管理。

## 1. 架构与所有权

运行时只有一个 COM 所有者：主控创建的 `HidSession`。板子中间件维护唯一串口、心跳、
序列号、响应读取、命令锁和故障状态。主控的键盘/鼠标命令与视觉产生的瞄准/左键命令，
都进入同一个原生 session。

```text
Python 主控 EXE
├─ rp2350-hid-bridge Python SDK
│  └─ rp2350_hid_bridge.dll ── 唯一 COM 连接
│     ├─ 主控键盘、鼠标、脚本命令
│     └─ 视觉瞄准、自动左键命令
└─ cs2-vision-runtime-sdk
   └─ vision_runtime.dll
      ├─ DXGI 捕获
      ├─ TensorRT/ONNX Runtime 推理
      ├─ 目标选择、跟踪和动作规划
      └─ retain 主控注入的原生 HID handle
```

这是两个独立 Python SDK：Vision wheel 不导入、不重导出也不依赖 HID Python wheel。
主控分别锁定和安装它们，并负责组装两个组件。

## 2. 环境包目录

把合作方自己的 EXE 放到解压目录根部，与两份 DLL 同级：

```text
PartnerController.exe
vision_runtime.dll
rp2350_hid_bridge.dll
resources/vision-runtime/
├─ runtime-manifest.json
├─ model/
│  ├─ best.onnx
│  └─ best.onnx.schema.json
├─ native/
│  ├─ onnxruntime/
│  ├─ cuda-11.8/
│  ├─ cudnn-8.9/
│  ├─ tensorrt-8.6.1.6/
│  └─ msvc-x64/
├─ config/
└─ licenses/
sdk/wheels/
├─ cs2_vision_runtime_sdk-0.3.0-py3-none-any.whl
└─ rp2350_hid_bridge-0.2.0-py3-none-any.whl
examples/
docs/
```

`resources/vision-runtime` 是只读运行环境。TensorRT 引擎缓存、标定、日志和用户配置必须
写入主控自己的可写 `data_dir`，不能写入环境包资源目录。

## 3. 板子固件与首次上线

本环境包使用并验证的是 RP2350 固件 `main@5329f7d`、协议 v2 和
`rp2350_hid_bridge.dll` ABI 1.0。板子连接 Windows 后必须同时枚举出 CDC COM 端口、
USB HID 键盘和 USB HID 鼠标；只出现其中一项时不要启动视觉输出。

中间件 DLL 负责 CRC 帧、协议序列号、ACK/NACK、重试、心跳和故障状态。生产主控不要
使用 pyserial 自己实现协议，也不要同时运行 hidctl、Web Serial 或其他会打开同一 COM
的程序。调试工具只能在主控完全关闭 `HidSession` 后单独使用。

省略端口时，`HidSession(app_dir=APP_DIR)` 会用默认 USB VID/PID `CAFE:2350` 自动查找
第一个匹配端口；部署多块板子时应由主控按设备身份选择并显式传入 COM。

### 3.1 无动作连通检查

首次接入先运行不会产生键鼠动作的 `ping/info/caps`：

```python
from rp2350_hid_bridge import HidSession

with HidSession("COM4", app_dir=APP_DIR) as board:
    try:
        board.ping()
        print("info", board.info().hex(" "))
        print("caps", board.caps().hex(" "))
    finally:
        board.stop_all()
```

这三条命令都成功后，才能进入鼠标方向和视觉输出验收。DLL 在 session 打开期间每
500 毫秒发送心跳；固件的两秒控制租约会在进程崩溃、DTR 断开或 USB 连接丢失后释放
保持中的键盘和鼠标状态，但正常退出仍必须显式调用 `board.stop_all()`。

### 3.2 四方向 HID 验收

固件变更、重新刷写或更换板子后，在安全且允许输入的活动窗口执行一次小幅四方向检查：

```python
with HidSession("COM4", app_dir=APP_DIR) as board:
    try:
        board.mouse_move(20, 0)
        board.mouse_move(-20, 0)
        board.mouse_move(0, 20)
        board.mouse_move(0, -20)
    finally:
        board.stop_all()
```

正负 X、正负 Y 必须都能移动且幅度近似对称。特别是 `board.mouse_move(0, 20)` 必须在
`dx=0` 时独立生效；如果只有带非零 X 的斜向命令能向下移动，说明板子固件仍不是配套
版本，不要继续做灵敏度标定或自动瞄准测试。

## 4. 构建环境安装 SDK

冻结 EXE 前，在主控项目自己的虚拟环境中分别安装两个 wheel：

```powershell
uv pip install --python .\.venv\Scripts\python.exe --no-deps `
  .\sdk\wheels\rp2350_hid_bridge-0.2.0-py3-none-any.whl `
  .\sdk\wheels\cs2_vision_runtime_sdk-0.3.0-py3-none-any.whl
```

`--no-deps` 是预期用法：环境包提供原生运行环境，两个 wheel 都只包含 Python 包装代码。
冻结完成后，目标机器不需要单独安装 Python，也不需要安装 CUDA Toolkit 或修改系统 PATH。

## 5. 正确启动顺序

必须遵循以下顺序：

1. 计算 EXE 根目录 `app_dir` 和主控可写目录 `data_dir`。
2. `HidSession(..., app_dir=app_dir)` 加载同级 `rp2350_hid_bridge.dll` 并打开一次 COM。
3. `VisionRuntime.from_app_dir()` 读取 manifest，验证并加载 `vision_runtime.dll`、模型和 GPU 依赖。
4. 主控调用 `vision.attach_hid_session(board.native_handle, hid_dll_path=board.dll_path)`。
5. 加载已有标定；只有调用端明确要求时才重新标定。
6. 打开 DXGI，再显式进入 `armed_output()`。
7. 视觉退出后先释放 vision 引用，最后由主控调用 `board.stop_all()` 并关闭板子 session。

不要手工调用 ctypes.CDLL。`HidSession` 与 `VisionRuntime` 会加载正确的 app-local DLL；
手工从其他目录加载第二份 `rp2350_hid_bridge.dll`，会让原生 handle 属于不同 DLL 实例，
不能交叉 retain/release。

## 6. 完整主控示例

```python
from __future__ import annotations

import os
import sys
from pathlib import Path

from rp2350_hid_bridge import HidSession
from cs2_vision_runtime import VisionRuntime


APP_DIR = Path(sys.executable).resolve().parent
DATA_DIR = Path(os.environ["LOCALAPPDATA"]) / "PartnerController"
CALIBRATION_PATH = DATA_DIR / "hid-calibration.json"


def run() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with HidSession("COM4", app_dir=APP_DIR) as board:
        try:
            with VisionRuntime.from_app_dir(
                APP_DIR,
                data_dir=DATA_DIR,
            ) as vision:
                vision.attach_hid_session(
                    board.native_handle,
                    hid_dll_path=board.dll_path,
                )

                vision.set_hid_calibration_path(CALIBRATION_PATH)
                profile = vision.get_hid_calibration()
                if not profile.valid:
                    profile = vision.calibrate_hid(adapter=0, output=0)

                vision.set_fire_policy(
                    body_enabled=True,
                    head_confidence=0.35,
                    body_confidence=0.45,
                    cooldown_frames=3,
                )
                vision.open_dxgi(
                    adapter=0,
                    output=0,
                    player_side="ct",
                    dry_run=False,
                )

                # 主控可以通过同一个 board 独立控制键盘和鼠标。
                board.key_down("W")
                try:
                    with vision.armed_output(fire=False):
                        while True:
                            action = vision.process_next()
                            if action is None:
                                break
                            consume_action(action)
                finally:
                    board.key_up("W")
        finally:
            board.stop_all()


def consume_action(action) -> None:
    print(
        action.frame_index,
        action.has_target,
        action.dx,
        action.dy,
        action.click_left,
        action.lock_state.name,
    )


if __name__ == "__main__":
    run()
```

自动开火必须由主控明确授权，把 `armed_output(fire=False)` 改为
`armed_output(fire=True)` 才会发送左键。新建 runtime 默认不允许物理移动或点击。

## 7. 生命周期和停止语义

推荐外层 board、内层 vision。`attach_hid_session()` 会在原生层 retain handle；
`vision.close()` 或上下文退出只 release 视觉引用，不关闭主控持有的 COM。

| 操作 | 视觉输出 | 主控保持的键 | 全局释放 |
|---|---|---|---|
| `armed_output()` 退出 | 关闭 | 保持 | 否 |
| `vision.reset()` | 关闭当前视觉会话 | 保持 | 否 |
| `vision.close()` | release 视觉引用 | 保持 | 否 |
| 标定结束或失败 | 停止标定移动 | 保持 | 否 |
| `board.stop_all()` | 停止 | 全部释放 | 是 |
| board 最后引用关闭 | 停止 | 全部释放 | 尽力释放后断开 |

共享模式中不要调用视觉 runtime 的全局停止接口。全局键鼠状态属于主控，只能由
`board.stop_all()` 决定何时释放。

## 8. 标定文件

`set_hid_calibration_path()` 只选择调用端文件，不区分账号。`get_hid_calibration()` 会读取
已有 profile；只有 `valid` 为假或用户明确修改游戏灵敏度时，主控才调用
`calibrate_hid()`。不要每次启动都强制重标定。

标定必须在已经进入对局、画面稳定、游戏接收鼠标输入时执行。标定成功会原子写入文件；
损坏文件、保存失败或重新标定失败不会覆盖此前有效 profile。

## 9. 同步、线程和命令并发

`process_next()` 是同步调用，适合放到专用视觉线程。`ctypes.CDLL` 调用原生函数时释放
GIL；DXGI 和模型推理不占用 HID 命令锁，只有一次“发送请求 → 等待 ACK/NACK”事务在
中间件内部串行。因此主控线程可以同时调用短的 `board.key_down()`、`key_up()`、
`mouse_move()`，不会出现两个串口读取者或重复序列号。

不要让多个线程同时调用同一个 `VisionRuntime`。长时间 `board.run_script()` 会占用命令
序列并推迟视觉鼠标请求，实时阶段应拆成短命令。

## 10. GPU 环境和 TensorRT 缓存

环境包固定提供：

- ONNX Runtime GPU 1.17.3；
- CUDA 11.8 app-local runtime；
- cuDNN 8.9.x；
- TensorRT 8.6.1.6；
- MSVC x64 运行库；
- SM61 FP32 模型和 schema。

不要从系统 PATH 混入其他版本。TensorRT 第一次遇到新 DLL/模型组合时会构建引擎，可能
需要数分钟；缓存位置为 `<data_dir>/cache/tensorrt/<runtime_id>/`。随后启动会复用缓存。

## 11. PyInstaller 和 Nuitka

PyInstaller/Nuitka 只负责冻结两个 Python 包和主控代码。两份 DLL 与
`resources/vision-runtime` 保持为 EXE 同级的外部 app-local 文件，不要塞进 one-file
临时目录。

```powershell
uv run pyinstaller --noconfirm --onedir --name PartnerController .\src\main.py
Copy-Item .\vision_runtime.dll .\dist\PartnerController\
Copy-Item .\rp2350_hid_bridge.dll .\dist\PartnerController\
Copy-Item .\resources .\dist\PartnerController\resources -Recurse
```

Nuitka 同理：

```powershell
uv run python -m nuitka --standalone --output-dir=.\dist .\src\main.py
```

## 12. 异常处理

- `RuntimeLoadError`：DLL、manifest、模型或原生依赖缺失；
- `RuntimeCompatibilityError`：DLL 路径、SHA256、ABI、能力位或模型契约不匹配；
- `RuntimeCallError`：DLL 已加载，但 DXGI、TensorRT、标定或 HID 原生调用失败；
- `RuntimeStateError`：调用顺序错误，例如 shared session 已附加后又设置私有 HID port。

串口运行中故障时，中间件 session 进入 FAULTED，主控和视觉会收到同一原始错误；当前
版本不会静默自动重连。主控应停止业务、记录错误并由用户重新建立完整 session。

## 13. 固定接口与版本

| 组件 | 版本/ABI |
|---|---|
| `cs2-vision-runtime-sdk` | 0.3.0 |
| `vision_runtime.dll` | ABI 2.1，required features 31 |
| `rp2350-hid-bridge` Python SDK | 0.2.0 |
| `rp2350_hid_bridge.dll` | ABI 1.0，协议 v2 |
| RP2350 板子固件 | `main@5329f7d`，协议 v2 |
| app-local manifest | version 2 |

主控依赖锁管理两个 Python 包版本；Vision manifest 只约束原生 HID DLL 的文件名、SHA256
和 ABI，不管理 HID Python wheel 版本。

## 14. 接入验收清单

- [ ] EXE、`vision_runtime.dll` 和 `rp2350_hid_bridge.dll` 位于同一根目录。
- [ ] `resources/vision-runtime/runtime-manifest.json`、模型和 native 目录完整。
- [ ] 板子固件为配套协议 v2 版本，CDC、HID 键盘和 HID 鼠标均已枚举。
- [ ] `board.ping()`、`board.info()` 和 `board.caps()` 均通过。
- [ ] 正负 X、正负 Y 四方向小幅移动均生效，纯正向 Y 不依赖非零 X。
- [ ] 主控只创建一个 `HidSession`，COM 只打开一次。
- [ ] `board.dll_path` 与环境包根目录中的 HID DLL 是同一绝对路径。
- [ ] cached calibration 启动时不移动视角。
- [ ] DXGI dry-run 能处理预期帧数且不打开 COM。
- [ ] 真实模式下自动瞄准正常；只有明确授权后才允许自动左键。
- [ ] vision disarm/close 后，主控保持的 W/Shift 不被释放。
- [ ] vision 线程运行时，主控短键盘/鼠标命令无超时或序列错误。
- [ ] `board.stop_all()` 能立即释放全部键鼠状态。
- [ ] TensorRT 首次构建与第二次缓存复用都通过。
- [ ] PyInstaller/Nuitka 产物从 EXE 同级目录成功加载完整环境。
