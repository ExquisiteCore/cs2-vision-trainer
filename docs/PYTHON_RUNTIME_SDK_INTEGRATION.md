# Python Runtime SDK 接入指南

本文面向把调用端 Python 程序冻结成 EXE 的开发者。正式方案由两个纯 Python wheel、
两个 app-local DLL 和一个只读资源目录组成；最终用户不需要安装 Python、CUDA Toolkit，
也不需要修改系统 `PATH`、`PYTHONPATH` 或注册表。

## 1. 运行结构与职责

调用端拥有唯一的 `HidSession`。它只打开一个 COM 口，并同时供调用端的键盘控制和
`vision_runtime.dll` 的鼠标瞄准使用。`VisionRuntime.from_app_dir()` 通过
`hid_session=hid` 把同一个原生句柄附加给视觉 DLL，不会再次打开串口。

SDK/DLL 负责 DXGI、TensorRT 推理、动作规划、受控标定和输出权限；调用端负责 UI、
业务状态、COM 口、数据目录、标定文件，以及何时重新标定或执行全局安全释放。
SDK 不识别账号，也不替调用端决定配置变化。

协调版本固定为：

- `cs2-vision-runtime-sdk==0.3.0`，vision ABI 2.1，required features 31；
- `rp2350-hid-bridge==0.2.0`，`rp2350_hid_bridge.dll` ABI 1.0；
- `runtime-manifest.json` manifest version 2。

## 2. 正式部署目录

```text
MyClient.exe
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
```

两个 DLL 必须与真实 EXE 同级。模型、schema 和 GPU 依赖必须来自同一个已验证包，
不能从系统搜索路径回退。标定、日志和 TensorRT 缓存写入调用端指定的可写
`data_dir`，不能写入 `resources/vision-runtime`。

## 3. 构建并安装两个 wheel

开发机使用 `uv`：

```powershell
uv sync --extra dev
& .\scripts\build_python_runtime_sdk.ps1 -OutputDir .\dist\python-sdk
```

输出：

```text
rp2350_hid_bridge-0.2.0-py3-none-any.whl
cs2_vision_runtime_sdk-0.3.0-py3-none-any.whl
```

runtime wheel 固定依赖 HID wheel。两者都只包含 Python 代码，不内嵌 DLL、模型或 GPU
运行库。调用端项目应同时固定并安装这两个审核后的文件：

```powershell
uv pip install --python .\.venv\Scripts\python.exe --no-deps `
  .\vendor\rp2350_hid_bridge-0.2.0-py3-none-any.whl `
  .\vendor\cs2_vision_runtime_sdk-0.3.0-py3-none-any.whl
```

## 4. PyInstaller 与 Nuitka

PyInstaller 和 Nuitka 会把两个 Python 包收集进调用端。建议使用目录型发布；即使使用
one-file，也要把两个 DLL 和 resources 作为 EXE 同级的外部文件，不依赖临时解压目录。

```powershell
uv run pyinstaller --noconfirm --onedir --name MyClient .\src\client_main.py
Copy-Item .\runtime-payload\vision_runtime.dll .\dist\MyClient\
Copy-Item .\runtime-payload\rp2350_hid_bridge.dll .\dist\MyClient\
Copy-Item .\runtime-payload\resources .\dist\MyClient\resources -Recurse
```

Nuitka 示例：

```powershell
uv run python -m nuitka --standalone --output-dir=.\dist .\src\client_main.py
```

随后复制同样的两个 DLL 与 resources。发布流水线必须校验文件名和哈希，不能让冻结工具
改名、内嵌或拆散这一组 app-local 组件。

## 5. 生成 app-local 原生包

先生成并验证 SM61 便携包，再重打包：

```powershell
& .\tools\cpp_analyzer\packaging\sm61\build-app-local-package.ps1 `
  -PortablePackageRoot .\dist\cs2-vision-runtime-sm61 `
  -OutputRoot .\dist\MyClient `
  -PythonSdkVersion 0.3.0
```

重打包器只接受哈希完整的 portable 包。输出已有内容时，只允许替换带
`.app-local-runtime-root` 标记的旧输出，不会删除调用端的未知目录。

## 6. manifest v2 契约

`resources/vision-runtime/runtime-manifest.json` 同时绑定：

- Python SDK 0.3.0 与 vision DLL ABI 2.1、features 31、SHA256；
- HID Python SDK 0.2.0 与 HID DLL ABI 1.0、SHA256；
- Windows x86_64、SM61、FP32 profile；
- ONNX Runtime 1.17.3、CUDA 11.8、cuDNN 8.9.x、TensorRT 8.6.1.6；
- 模型、schema、原生目录和稳定 `runtime_id`。

SDK 会拒绝绝对路径、`..` 逃逸、错误 ABI、版本过旧、文件缺失和哈希不一致。
不要手工编辑清单，也不要单独替换某一份 DLL 或模型。

## 7. DXGI dry-run

dry-run 不创建 `HidSession`，用于先验证目录、TensorRT、模型和 DXGI：

```powershell
uv run python .\examples\runtime_dxgi_dryrun.py `
  --app-dir .\dist\MyClient `
  --data-dir "$env:LOCALAPPDATA\MyClient" `
  --max-frames 300 --show-every 1
```

最小代码：

```python
with VisionRuntime.from_app_dir(app_dir, data_dir=data_dir) as runtime:
    runtime.open_dxgi(adapter=0, output=0, player_side="ct", dry_run=True)
    for action in runtime.iter_actions():
        print(action.frame_index, action.inference_ms, action.dx, action.dy)
```

`VisionAction` 是不可变的逐帧结果，包含帧号、耗时、检测数、锁定状态、目标几何以及
`dx`、`dy`、`click_left` 等规划字段。

## 8. 一个 COM 口的正式生命周期

```python
from cs2_vision_runtime import HidSession, VisionRuntime

with HidSession("COM4", app_dir=app_dir) as hid:
    try:
        with VisionRuntime.from_app_dir(
            app_dir,
            data_dir=data_dir,
            hid_session=hid,
        ) as runtime:
            runtime.set_hid_calibration_path(calibration_path)
            profile = runtime.get_hid_calibration()
            if not profile.valid or user_requested_recalibration:
                profile = runtime.calibrate_hid(adapter=0, output=0)

            runtime.open_dxgi(
                adapter=0,
                output=0,
                player_side="ct",
                dry_run=False,
            )
            with runtime.armed_output(fire=user_enabled_auto_fire):
                while True:
                    action = runtime.process_next()
                    if action is None:
                        break
                    consume(action)
    finally:
        hid.stop_all()
```

`set_hid_calibration_path()`、`get_hid_calibration()` 和 `calibrate_hid()` 都在 attached
session 上工作。成功 profile 原子保存；文件损坏、保存失败或重标定失败不会覆盖旧
profile。标定必须在 `open_dxgi()` 前、已进入对局且画面稳定时执行。

## 9. 输出撤销与全局释放

进入 `armed_output()` 时先允许移动，再按参数允许开火。正常退出、`Ctrl+C` 或处理异常时，
它只执行“关闭开火 → 关闭视觉移动”，不会释放调用端仍保持的 W、Shift 或鼠标按钮。
`reset()` 和视觉 runtime 关闭同样保留 caller-owned HID 状态。

全局释放只发生在以下边界：

- 调用端显式执行 `hid.stop_all()`；
- 最后一个 HID session 结束或端口断开；
- 进程清理；
- 固件两秒控制租约超时。

因此暂停自动瞄准不会误松开调用端键盘；结束整个控制会话时，最外层 finally 才调用
`hid.stop_all()`。原生 session 进入 FAULTED 后会拒绝新命令，不会静默自动重连。

## 10. 同步调用与线程模型

`process_next()` 在其调用线程中保持同步；建议把视觉循环放到调用端自己的工作线程。
`ctypes.CDLL` 调用原生函数时释放 GIL，因此控制线程可以同时通过同一个 `HidSession`
发送键盘命令。DXGI 捕获和 TensorRT 推理不持有 HID 命令锁；键盘和鼠标请求仅在各自的
request/ACK 往返期间串行化，所以不会争抢 COM 口或破坏序列号。

不要从多个线程同时操作同一个 `VisionRuntime`。可以让一个视觉线程调用
`process_next()`，另一个控制线程调用 `hid.key_down()`、`hid.key_up()`。长时间
`hid.run_script()` 会占用命令序列并推迟瞄准命令，应拆成短命令或放在非实时阶段。

## 11. TensorRT 首次初始化与缓存

首次加载新组合时，TensorRT 可能花数分钟生成 FP32 引擎，并输出 ONNX INT64 权重转
INT32 的 warning；该 warning 本身不表示失败。缓存写入：

```text
<data_dir>/cache/tensorrt/<runtime_id>/
```

DLL、HID DLL 或模型变化后，包会生成新的 `runtime_id`，避免错误复用旧引擎。

## 12. 异常与诊断

- `RuntimeLoadError`：目录、清单、DLL 或资源缺失；
- `RuntimeCompatibilityError`：ABI、版本、能力位、路径或哈希不匹配；
- `RuntimeCallError`：DLL 已加载，但原生调用失败；
- `RuntimeStateError`：调用顺序冲突，例如 attached session 又设置私有 HID port。

诊断顺序：先检查两份 DLL 和 `runtime-manifest.json`，再执行 DXGI dry-run，再检查
COM/板卡和持久标定，最后显式解锁真实输出。不要通过修改系统 PATH、复制未知 GPU DLL
或跳过哈希来掩盖兼容问题。

## 13. 发布前检查清单

- [ ] 两个 wheel 版本分别为 0.3.0 和 0.2.0，依赖关系已锁定。
- [ ] 两个 DLL 与 EXE 同级，resources 目录完整。
- [ ] manifest v2 中 vision ABI 2.1/features 31、HID ABI 1.0 和全部 SHA256 正确。
- [ ] 干净机器无需 Python、全局 CUDA、PATH 或 PYTHONPATH 即可启动。
- [ ] TensorRT 首次构建和第二次缓存复用都通过。
- [ ] DXGI dry-run 连续处理预期帧数且未打开 COM。
- [ ] cached calibration 跨进程加载，显式重标定失败不会破坏旧 profile。
- [ ] vision disarm 后调用端保持的键不松开，`hid.stop_all()` 能立即全局释放。
- [ ] 视觉工作线程运行时，控制线程仍能可靠发送键盘命令。
- [ ] PyInstaller/Nuitka 最终 EXE 目录通过 `VisionRuntime.from_app_dir()` 验证。
