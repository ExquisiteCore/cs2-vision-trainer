# Python Runtime SDK 接入指南

本文面向把 `cs2_vision_runtime` 冻结进调用端 Python EXE 的开发者。正式部署只加载
EXE 同级的 `vision_runtime.dll` 和 `resources/vision-runtime`，不要求最终用户安装
Python、wheel、CUDA Toolkit，也不要求设置 `PATH`、`PYTHONPATH` 或注册表。

## 1. 职责边界

运行时 SDK/DLL 负责加载固定模型、DXGI 采集、推理、动作规划、HID 标定数据读写和安全
输出控制。调用端负责 UI、账号与业务状态、COM 口、阵营、数据目录、标定文件选择，以及
何时显式重新标定。SDK/DLL 不理解账号；切换账号时是否改用另一份标定文件或调用
`calibrate_hid()`，完全由调用端决定。

正式调用端使用 `VisionRuntime.from_app_dir()`。`VisionRuntime()`、手工模型路径和环境变量
只保留给源码开发与诊断，不应成为发布版 EXE 的启动依赖。

## 2. 部署目录

把以下内容放到调用端输出目录：

```text
MyClient.exe
vision_runtime.dll
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

`vision_runtime.dll` 必须与 EXE 真正同级，不能从系统搜索路径或其他安装目录回退加载。
模型和原生依赖由发布包提供，调用端不要在运行时自行拼装版本。

标定、TensorRT 缓存和日志必须写到调用端指定的可写 `data_dir`，不能写入
`resources/vision-runtime`。推荐位置是 `%LOCALAPPDATA%\<调用端名称>`。

## 3. 构建零依赖 SDK wheel

开发机使用 `uv`：

```powershell
uv sync --extra dev
& .\scripts\build_python_runtime_sdk.ps1 -OutputDir .\dist\python-sdk
```

输出的 `cs2_vision_runtime_sdk-0.2.0-*.whl` 只有 Python 包装层，`Requires-Dist` 为空；
它不会包含 DLL、模型、TensorRT、CUDA 或 cuDNN。调用端项目在构建阶段安装本地 wheel：

```powershell
uv pip install --python .\.venv\Scripts\python.exe --no-deps `
  .\vendor\cs2_vision_runtime_sdk-0.2.0-py3-none-any.whl
```

建议把经过审核的 wheel 和 app-local 原生包版本固定在调用端的依赖锁或发布清单中。

## 4. PyInstaller 与 Nuitka 冻结

SDK 是普通纯 Python 包，正常导入后会被 PyInstaller 或 Nuitka 收集。建议优先使用目录型
发布；即使使用 one-file，DLL 与 resources 也应作为外部 app-local 文件放在最终 EXE
旁边，不要依赖临时解压目录。

PyInstaller 示例：

```powershell
uv run pyinstaller --noconfirm --onedir --name MyClient .\src\client_main.py
Copy-Item .\runtime-payload\vision_runtime.dll .\dist\MyClient\
Copy-Item .\runtime-payload\resources .\dist\MyClient\resources -Recurse
```

Nuitka 示例：

```powershell
uv run python -m nuitka --standalone --output-dir=.\dist .\src\client_main.py
```

随后同样把 `vision_runtime.dll` 与 `resources` 复制到生成的 EXE 同级目录。发布流水线应
检查目录结构和哈希，不能让冻结工具改名或内嵌 `vision_runtime.dll`。

## 5. 生成 app-local 原生包

先生成并验证 SM61 便携诊断包，再重打包：

```powershell
& .\tools\cpp_analyzer\packaging\sm61\build-app-local-package.ps1 `
  -PortablePackageRoot .\dist\cs2-vision-runtime-sm61 `
  -OutputRoot .\dist\MyClient `
  -PythonSdkVersion 0.2.0
```

重打包器只接受清单完整且哈希未变化的便携包。目标目录存在时，只有带
`.app-local-runtime-root` 标记的旧输出才允许替换；不会删除调用端自己创建的未知目录。

## 6. `runtime-manifest.json` 契约

`resources/vision-runtime/runtime-manifest.json` 是 SDK、DLL、模型和原生环境之间的机器
可读契约，包含：

- `manifest_version`、`package_version` 和稳定 `runtime_id`；
- Windows x86_64、SM61、FP32 profile；
- Python SDK 最低/推荐版本；
- DLL ABI 2.0、必需能力位、文件名和 SHA256；
- 固定 backend `ort-tensorrt`；
- 模型、schema 的规范相对路径和 SHA256；
- ONNX Runtime 1.17.3、CUDA 11.8、cuDNN 8.9.x、TensorRT 8.6.1.6 和 MSVC
  私有目录。

SDK 会拒绝绝对路径、`..` 路径逃逸、错误版本、错误 profile、缺失文件或哈希不匹配。
不要手工编辑清单，也不要只替换其中一个 DLL 或模型文件。

## 7. 最小启动代码

```python
from pathlib import Path
import sys

from cs2_vision_runtime import VisionRuntime

app_dir = Path(sys.executable).resolve().parent
data_dir = Path.home() / "AppData" / "Local" / "MyClient"

with VisionRuntime.from_app_dir(app_dir, data_dir=data_dir) as runtime:
    runtime.set_frame_limits(max_frames=300, warmup_frames=3)
    runtime.open_dxgi(adapter=0, output=0, player_side="ct", dry_run=True)
    for action in runtime.iter_actions():
        print(action.frame_index, action.inference_ms, action.dx, action.dy)
```

`from_app_dir()`完成清单验证、同级 DLL 加载、ABI 握手、原生目录注册、模型/schema/backend
配置和 TensorRT 缓存路径配置。任何一步失败都会销毁已创建的 native 句柄。

## 8. TensorRT 首次初始化与缓存

第一次加载新组合时，TensorRT 可能需要较长时间构建引擎，并输出 ONNX INT64 权重向
INT32 转换的 warning；这类 warning 本身不表示失败。SDK 使用清单 `runtime_id`，把缓存
写入：

```text
<data_dir>/cache/tensorrt/<runtime_id>/
```

模型、DLL 或关键加速组件更新后，重打包器会产生新的 `runtime_id`，因此不会错误复用旧
引擎。不要把 cache 打进 resources，也不要跨不同 GPU profile 强行共享。更新时发布完整
app-local 包，并允许旧缓存由调用端自己的清理策略回收。

## 9. DXGI dry-run

发布前先验证只读路径：

```powershell
.\MyClient.exe --app-dir . --data-dir "$env:LOCALAPPDATA\MyClient" `
  --adapter 0 --output 0 --player-side ct --max-frames 300
```

也可在源码仓运行：

```powershell
uv run python .\examples\runtime_dxgi_dryrun.py `
  --app-dir .\dist\MyClient `
  --data-dir "$env:LOCALAPPDATA\MyClient" `
  --max-frames 300 --show-every 1
```

dry-run 不设置 HID 端口，不武装移动或自动开火。确认能持续返回帧和动作后再测试硬件输出。

## 10. 持久标定与显式重标定

调用端决定标定文件，例如 `<data_dir>/profiles/current-hid.json`：

```python
runtime.set_hid_port("COM4")
runtime.set_hid_calibration_path(calibration_path)
profile = runtime.get_hid_calibration()
if not profile.valid or user_requested_recalibration:
    profile = runtime.calibrate_hid(adapter=0, output=0)
```

成功标定由 DLL 原子保存。文件损坏、保存失败或重标定失败都不会用无效数据覆盖旧 profile。
切换账号时，调用端可以选择另一个路径并显式调用 `calibrate_hid()`；SDK 不维护账号映射。
标定必须在 `open_dxgi()` 之前、已进入对局且画面稳定时执行。

## 11. `VisionAction` 字段

`iter_actions()`逐帧返回不可变 `VisionAction`：

- 帧与性能：`frame_index`、`timestamp_ms`、`fps`、`preprocess_ms`、
  `inference_ms`、`postprocess_ms`、`total_ms`；
- 检测与锁定：`detection_count`、`has_target`、`lock_state`、`distance`；
- 输出计划：`dx`、`dy`、`click_left`；
- 目标几何：`offset_x`、`offset_y`、`target_x`、`target_y`。

动作只是本帧规划结果；只有调用端显式武装真实输出后，DLL 才会把移动/点击发给 HID。

## 12. 瞄准、开火与安全停止

```python
runtime.open_dxgi(
    adapter=0,
    output=0,
    player_side="ct",
    hid_port="COM4",
    dry_run=False,
)

with runtime.armed_output(fire=user_enabled_auto_fire):
    for action in runtime.iter_actions():
        consume(action)
```

进入 `armed_output()` 时先开启移动，再按参数开启开火；退出、`Ctrl+C` 或处理异常时固定尝试
“关闭开火 → 关闭移动 → `stop_all()`”。处理异常优先保留，清理中的错误不会覆盖原始错误。
正常退出若清理失败，则报告第一个清理错误。移动与开火是独立权限，默认都关闭。

运行时状态为 `READY → OPEN → READY → CLOSED`。模型、backend、缓存、阈值、ROI、调优
和标定配置只能在 READY 修改；逐帧处理和输出控制只能在 OPEN 使用。`reset()`关闭当前输入
并回到 READY，`close()`幂等且会先 native close，再无条件 destroy。

## 13. 异常、线程边界与诊断顺序

公开异常都继承 `VisionRuntimeError` 和 `RuntimeError`：

- `RuntimeLoadError`：目录、清单、DLL 或资源缺失；
- `RuntimeCompatibilityError`：ABI、版本、能力位、路径或哈希不匹配；
- `RuntimeCallError`：DLL 已加载，但某次 native 调用失败；
- `RuntimeStateError`：调用顺序不合法。

每个 `VisionRuntime` 实例应由一个调用线程串行使用。SDK 不创建后台处理线程，不提供异步
回调；需要与 UI 协作时，由调用端把整个运行循环放到自己的工作线程，通过线程安全队列
传递 `VisionAction`，不要从多个线程同时操作同一实例。

诊断顺序：先检查目录和 `runtime-manifest.json`，再看异常类型与完整消息；然后执行 DXGI
dry-run；再检查 COM/板卡与持久标定；最后才显式解锁真实输出。不要通过修改系统 PATH、
复制未知 CUDA DLL 或跳过哈希来掩盖兼容错误。

## 14. 发布前检查清单

- [ ] wheel 版本与清单 `python_sdk.recommended` 一致，且 wheel 无运行依赖。
- [ ] `vision_runtime.dll` 与 EXE 同级，resources 目录结构完整。
- [ ] 清单 DLL、模型、schema SHA256 与实际文件一致，ABI 为 2.0。
- [ ] ONNX Runtime/TensorRT/CUDA/cuDNN/MSVC 均来自同一已验证包。
- [ ] 干净机器无需 Python、PATH、PYTHONPATH 或全局 CUDA 即可启动。
- [ ] TensorRT 首次构建和第二次缓存复用都通过。
- [ ] DXGI dry-run 连续处理预期帧数且不选择 HID 端口。
- [ ] 调用端数据目录可写，标定文件与缓存不写入安装目录。
- [ ] 有效标定能跨进程加载；显式重标定失败不会破坏旧 profile。
- [ ] 移动、开火分别测试，异常和 `Ctrl+C` 都能安全撤销并停止。
- [ ] PyInstaller/Nuitka 最终产物在真实 EXE 目录调用 `from_app_dir()`成功。
