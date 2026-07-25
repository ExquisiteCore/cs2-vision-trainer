# Python Runtime SDK v2 设计

## 目标

把 `cs2_vision_runtime` 从父仓中的内部 `ctypes` 包装层升级为可版本校验、默认安全的 Windows x64 Python SDK。调用端是一个最终会冻结为 Windows EXE 的 Python 程序；SDK在开发和打包阶段作为依赖进入调用端，最终负责从EXE同级目录加载 `vision_runtime.dll` 和配套资源环境。最终用户不需要安装Python、wheel、CUDA Toolkit或TensorRT。

本次设计只面向 Python 调用端。原生 C/C++ 接入文档、调用端传入图像帧、完整检测框数组和异步回调不在范围内。

## 当前问题

现有实现已经通过 Python SDK 调用 DLL 完成了 GTX 1080 Ti 实机验证，但作为对外 SDK 仍有以下缺口：

1. DLL 已导出 `va_set_tensorrt_cache_path`，Python 包装层没有绑定和公开该接口。
2. Python SDK 和 DLL 没有显式 ABI 握手；旧 DLL 缺少新导出时只会抛出 `AttributeError: function ... not found`。
3. 兼容性测试只验证“Python 使用的符号存在于 C 头文件”，不能发现“C API 新增而 Python 漏绑”。
4. SDK 只能作为父仓 wheel 的一部分或通过 `PYTHONPATH` 使用；父仓 wheel 同时携带训练端依赖，不适合作为调用端的构建依赖。
5. 调用端必须手工设置 DLL 路径和运行库目录，EXE同级的应用本地运行环境没有成为正式契约。
6. 真实输出的解锁和撤销由示例手写 `try/finally`，第三方调用端容易漏掉某一步。
7. `VisionRuntime.close()` 直接销毁句柄，虽然 C++ 析构会关闭会话，但 Python 层没有显式执行和验证 `va_close()` 生命周期。
8. 配置方法在会话打开后仍可能返回成功，但多数配置只会影响下一次打开，调用端容易误以为当前会话已经更新。
9. SM61 包文档声明缓存位于资源包内，现有 Python 示例没有设置该路径，实际会使用 C++ 默认相对目录；安装到只读位置时还可能无法创建TensorRT缓存。
10. 便携包漏装了安全的 DXGI dry-run 示例，且标定说明仍残留已经移除的 2048-counts 探测描述。

## 设计原则

- Python SDK 是唯一面向调用端的接口；C ABI 是 SDK 的内部承载层。
- 最终部署采用应用本地运行时：EXE、DLL和只读资源一起安装，不依赖全局环境。
- GPU 运行库和模型作为EXE同级资源交付，不冻结进单文件EXE，也不进入SDK wheel。
- SDK wheel只用于调用端开发和构建，保持零第三方依赖，不安装 `onnxruntime-gpu`、CUDA、TensorRT、OpenCV或训练端依赖。
- 原有公开方法保持可用，新能力采用向后兼容的增量接口。
- 默认不产生 HID 移动或点击；真实输出必须在已打开会话上显式武装。
- SDK 与 DLL 在创建运行时句柄前完成 ABI 和能力检查。
- 调用端决定标定文件、账号映射和重新标定时机；SDK 和 DLL 不理解账号。

## 应用本地分发架构

最终调用端采用“EXE同级DLL + resources目录”的应用本地部署，不把约1GB的GPU环境塞入单文件EXE：

```text
MyClient/
├─ MyClient.exe
├─ vision_runtime.dll
└─ resources/
   └─ vision-runtime/
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
      │  └─ runtime-sm61.cfg
      └─ licenses/
```

调用端的Python构建环境通过零依赖wheel安装 `cs2_vision_runtime`，PyInstaller、Nuitka或等价冻结工具把纯Python SDK代码打入 `MyClient.exe`。最终用户目录不再包含 `python/`、`PYTHONPATH`或wheel安装步骤。

只读资源与可写数据严格分离。调用端提供自己的数据目录，例如：

```text
%LOCALAPPDATA%/ExquisiteCore/MyClient/
├─ cache/tensorrt/<runtime-id>/
├─ calibration/
└─ logs/
```

SDK只自动选择TensorRT缓存子目录。标定文件仍由调用端按自己的业务和账号规则显式选择；DLL和SDK不识别账号。

规范开发交付物：

- `cs2_vision_runtime-<version>-py3-none-any.whl`：调用端构建依赖；SDK加载运行时时仍严格要求Windows x64。
- `vision_runtime.dll`：最终与调用端EXE同级。
- `resources/vision-runtime/`：模型、原生依赖、配置、许可证和清单。
- `PYTHON_SDK_INTEGRATION.md`：面向调用端开发者的完整中文接入指南。
- dry-run与真实输出示例：用于开发阶段验证，不要求复制到最终用户目录。

wheel、DLL和资源目录必须从同一发布流水线生成。运行环境清单记录三者的版本关系，阻止调用端把新SDK、旧DLL和旧模型资源混用。

## 运行环境定位

保留低层 `VisionRuntime(dll_path=...)` 供测试和开发，新增最终调用端推荐入口：

```python
runtime = VisionRuntime.from_app_dir(
    app_dir,
    data_dir=data_dir,
)
```

`app_dir`通常为 `Path(sys.executable).resolve().parent`。`from_app_dir()`执行以下行为：

1. 解析EXE目录、同级 `vision_runtime.dll` 和 `resources/vision-runtime/runtime-manifest.json`。
2. 校验清单版本、SM61/FP32 profile、SDK最低版本、DLL ABI要求和关键资源路径。
3. 验证模型、schema、ONNX Runtime、CUDA、cuDNN、TensorRT和MSVC私有目录存在。
4. 使用 `os.add_dll_directory()`注册原生目录，并在SDK对象生命周期内保留句柄。
5. 加载同级 `vision_runtime.dll`并执行DLL ABI握手。
6. 从清单自动设置模型、schema、`ort-tensorrt` backend和调用端数据目录下的TensorRT缓存。
7. 返回处于 `READY`、尚未连接HID和打开DXGI的运行时。

调用端不再重复调用 `set_model()`、`set_backend()`或 `set_tensorrt_cache_path()`。这些参数属于我们交付的运行环境。低层接口仍保留给开发测试和未来非标准运行包。

开发环境自动发现顺序保持确定性：

1. 显式 `from_app_dir(app_dir, data_dir=...)`。
2. 显式 `dll_path`和低层逐项配置。
3. `CS2_VISION_RUNTIME_DLL`。
4. xmake Release或CMake `build-cmake/Release`开发目录。

正式调用端必须使用 `from_app_dir()`，不依赖当前工作目录、系统 `PATH`、注册表或全局CUDA/TensorRT安装。

## 运行环境清单

`resources/vision-runtime/runtime-manifest.json`是EXE、SDK、DLL、模型和原生环境之间的机器可读契约。至少包含：

- `manifest_version`和运行环境 `package_version`。
- 稳定的 `runtime_id`，用于隔离TensorRT缓存。
- 固定profile：Windows x64、NVIDIA SM61、FP32。
- Python SDK最低版本和推荐版本。
- DLL ABI主/次版本及必需能力位。
- 同级DLL文件名和SHA256。
- backend固定为 `ort-tensorrt`。
- 模型和schema相对路径、SHA256及类别顺序标识。
- ONNX Runtime、CUDA、cuDNN、TensorRT和MSVC目录及版本。
- 许可证目录和构建来源标识。

SDK启动时执行快速契约校验：版本、路径、文件存在性、模型/schema哈希和DLL哈希。超大原生依赖的完整哈希由发布流水线和安装/更新器验证，避免每次启动都扫描约1GB文件。调用端可在诊断模式显式请求完整清单校验。

清单中的路径必须是相对 `resources/vision-runtime` 的规范化相对路径，禁止绝对路径和逃逸资源根目录的 `..`。同级 `vision_runtime.dll`由独立字段声明并固定解析到 `app_dir`，不能从任意搜索路径加载。

## DLL ABI 握手

C ABI 新增只读查询结构和函数，供 Python SDK 在 `va_create()` 前调用：

```c
typedef struct VaRuntimeAbiInfo {
    uint32_t struct_size;
    uint32_t abi_major;
    uint32_t abi_minor;
    uint32_t runtime_action_size;
    uint32_t hid_calibration_profile_size;
    uint64_t feature_flags;
} VaRuntimeAbiInfo;

VA_API int32_t va_get_abi_info(VaRuntimeAbiInfo* info);
```

ABI 主版本表示不兼容的结构或语义变化；次版本表示向后兼容能力扩展。首个正式握手版本为 `2.0`。

能力位至少包括：

- TensorRT 缓存路径配置。
- 持久化 HID 标定。
- 独立移动输出武装。
- 独立开火武装。

Python SDK 加载时必须：

1. 一次检查全部必需导出并报告完整缺失列表。
2. 调用 `va_get_abi_info()`。
3. 检查 ABI 主版本一致、DLL 次版本不低于 SDK 最低要求。
4. 检查 `VaRuntimeAction` 和 `VaHidCalibrationProfile` 的 C/ctypes 大小一致。
5. 检查当前 SDK 所需能力位全部存在。

旧 DLL 缺少握手函数时抛出 `RuntimeCompatibilityError`，错误中包含 DLL 绝对路径、SDK 版本、缺失导出和更新建议，不再直接泄漏 `ctypes.AttributeError`。

## Python 公共 API

### 保留接口

保留现有 `VisionRuntime`、`VisionAction`、`HidCalibrationProfile`、`LockState` 和所有配置、打开、处理、标定、输出及关闭方法。现有调用端不需要改名。

### 新增数据类型

```python
@dataclass(frozen=True)
class RuntimeAbiInfo:
    abi_major: int
    abi_minor: int
    runtime_action_size: int
    hid_calibration_profile_size: int
    feature_flags: int
```

新增异常均继承 `RuntimeError`，保持旧的捕获逻辑有效：

- `RuntimeLoadError`：DLL或私有运行目录缺失、DLL加载失败。
- `RuntimeCompatibilityError`：导出、ABI、结构大小或能力不匹配。
- `RuntimeCallError`：DLL返回失败，包含操作名与 `va_last_error()`。
- `RuntimeStateError`：调用顺序不合法。

### 模型与TensorRT配置

新增公开方法：

```python
runtime.set_tensorrt_cache_path(path)
```

扩展现有方法但保持兼容：

```python
runtime.set_model(
    model_path,
    *,
    schema_path=None,
    backend=None,
    tensorrt_cache_path=None,
)
```

当提供 `tensorrt_cache_path` 时，SDK调用DLL现有的 `va_set_tensorrt_cache_path`。这些接口用于低层开发模式；正式调用端的 `from_app_dir()`根据清单自动完成模型和TensorRT配置。

清单必须提供稳定的 `runtime_id`或等价缓存命名空间。SDK把TensorRT缓存放在调用端 `data_dir/cache/tensorrt/<runtime-id>`，因此更换模型、GPU profile、ORT、CUDA、cuDNN或TensorRT时会自然切换缓存目录，不要求业务代码理解引擎兼容规则。调用端仍可通过低层setter明确覆盖。

### 逐帧迭代

新增：

```python
for action in runtime.iter_actions():
    print(action.frame_index, action.inference_ms, action.dx, action.dy)
```

`iter_actions()`只封装现有 `process_next()` 状态码，不吞掉 DLL 错误，不创建后台线程，不改变帧生命周期。

### 安全输出上下文

新增：

```python
with runtime.armed_output(fire=False):
    for action in runtime.iter_actions():
        ...
```

进入顺序：

1. `set_output_enabled(True)`。
2. 仅当 `fire=True` 时调用 `set_fire_enabled(True)`。

退出顺序：

1. `set_fire_enabled(False)`。
2. `set_output_enabled(False)`。
3. `stop_all()`。

如果循环本身抛出异常，原始异常优先；清理仍逐项尝试，不能因为前一项失败而跳过后一项。正常路径上的清理失败以 `RuntimeCallError` 报告。

### 生命周期状态

Python 层维护三个状态：

- `READY`：句柄有效，会话未打开，可以配置、加载标定或执行标定。
- `OPEN`：视频或DXGI会话已打开，可以处理帧并动态控制输出与开火。
- `CLOSED`：句柄已销毁，只允许重复调用 `close()`。

规则：

- 模型、backend、缓存、阈值、ROI、帧限制、HID调优和标定路径只能在 `READY` 修改。
- `open_video()`/`open_dxgi()`成功后进入 `OPEN`；失败时回到 `READY`。
- `process_next()`、`iter_actions()`和输出武装只允许在 `OPEN`。
- `reset()`显式调用 `va_close()`并回到 `READY`，允许重新配置和打开。
- `close()`先尝试 `va_close()`，再无条件 `va_destroy()`，最后进入 `CLOSED`；重复调用保持无操作。
- 单个 `VisionRuntime` 实例不提供线程安全保证。多线程调用端必须把一个实例限制在一个线程，或使用独立实例。

## 标定职责边界

Python SDK继续提供低层、可组合的持久化标定接口：

```python
runtime.set_hid_calibration_path(path)
profile = runtime.get_hid_calibration()
if not profile.valid or recalibrate:
    profile = runtime.calibrate_hid(adapter=0, output=0)
```

SDK不自动识别账号、游戏设置或灵敏度变化。调用端负责选择文件和传入明确的 `recalibrate` 业务条件。文档说明当前中心ROI光流标定的探测上限为120 counts，不再描述旧的2048-counts方案。

## 推荐调用流程

```python
import os
import sys
from pathlib import Path

from cs2_vision_runtime import VisionRuntime

app_dir = Path(sys.executable).resolve().parent
data_dir = Path(os.environ["LOCALAPPDATA"]) / "ExquisiteCore" / "MyClient"

with VisionRuntime.from_app_dir(app_dir, data_dir=data_dir) as runtime:
    runtime.set_hid_port("COM4")
    calibration_path = data_dir / "calibration" / "current.json"
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    runtime.set_hid_calibration_path(calibration_path)

    profile = runtime.get_hid_calibration()
    if not profile.valid:
        profile = runtime.calibrate_hid(adapter=0, output=0)

    runtime.set_fire_policy(
        body_enabled=True,
        head_confidence=0.35,
        body_confidence=0.45,
        cooldown_frames=3,
    )
    runtime.open_dxgi(
        adapter=0,
        output=0,
        player_side="ct",
        hid_port="COM4",
        dry_run=False,
    )

    with runtime.armed_output(fire=False):
        for action in runtime.iter_actions():
            print(action.frame_index, action.has_target, action.dx, action.dy)
```

调用端应把标定路径替换为自己的数据模型，例如 `data_dir / "calibration" / profile_name`。示例中的SDK不生成或理解 `profile_name`。

第一次创建TensorRT引擎时可能长时间停留在模型初始化阶段。调用端应在工作线程执行同步的 `open_video()`/`open_dxgi()`，并在UI显示“正在初始化模型”；同一个 `VisionRuntime` 实例后续仍由该工作线程使用。INT64权重向INT32转换是警告而不是失败；SDK以 `open_dxgi()` 是否成功返回和后续是否产生 `VisionAction` 判断运行结果。

## 构建依赖与最终部署

调用端开发环境使用发行名称 `cs2-vision-runtime-sdk`，导入名保持 `cs2_vision_runtime`。初始v2版本为 `0.2.0`，支持Python 3.11及以上、Windows x64。调用端可以通过私有制品、仓库路径或本地wheel把SDK加入 `uv`依赖，再由自己的PyInstaller、Nuitka或等价流程冻结进EXE。

SDK wheel不包含：

- `vision_runtime.dll`。
- ONNX Runtime Provider。
- CUDA、cuDNN或TensorRT。
- 模型和schema。
- RP2350固件。

最终用户目录不需要保留wheel。`runtime-manifest.json`记录Python SDK最低/推荐版本、DLL ABI、模型和所有原生组件版本。调用端发布流水线在冻结EXE后复制同一次发布的 `vision_runtime.dll` 与 `resources/vision-runtime`，并运行一个不产生HID输出的启动检查。

不采用把所有资源塞入单文件EXE的方案。原生依赖和模型保持应用本地文件，便于Windows加载、TensorRT诊断、增量更新和许可证交付。

## 接入文档结构

新增 `docs/PYTHON_RUNTIME_SDK_INTEGRATION.md`，同时作为调用端开发制品发布。内容按以下顺序组织：

1. 适用范围、Windows x64和安全说明。
2. 调用端构建环境安装SDK和冻结EXE。
3. 最终目录布局与 `from_app_dir()`。
4. SDK/DLL ABI兼容检查。
5. 模型、schema、TensorRT和缓存配置。
6. 视频与DXGI dry-run。
7. 持久化HID标定。
8. `VisionAction`字段。
9. 真实瞄准与开火武装。
10. `reset()`、`close()`和异常退出。
11. 异常类型与排查顺序。
12. 调用端接入检查清单。

父仓README、`docs/USAGE.md`和便携包中文README只保留简短入口，避免复制完整正文。

## 测试策略

### C ABI

- `VaRuntimeAbiInfo`字段、大小和能力位测试。
- `VaRuntimeAction`和`VaHidCalibrationProfile`静态大小检查。
- `va_get_abi_info()`空指针和正常返回测试。
- DLL导出表检查。

### Python单元测试

- C头文件公开函数与Python绑定的双向集合一致。
- 缺少一个或多个导出时一次报告完整列表。
- ABI主/次版本、结构大小和能力位不匹配分别拒绝。
- `from_app_dir()`路径、清单解析和私有DLL目录顺序。
- 清单版本、profile、相对路径逃逸、DLL/模型/schema哈希和组件版本错误分别拒绝。
- 正式模式只从 `app_dir/vision_runtime.dll` 加载，不接受PATH中的同名旧DLL。
- TensorRT缓存setter和扩展后的 `set_model()`调用顺序。
- READY/OPEN/CLOSED状态转换和非法调用。
- `iter_actions()`正常结束与错误传播。
- `armed_output()`正常、处理错误和部分清理失败时的完整撤销顺序。
- `close()`显式关闭、无条件销毁和幂等。

### 分发与包级测试

- 使用 `uv build`生成独立、零依赖的调用端开发wheel。
- 在全新临时虚拟环境中安装wheel并导入，不安装训练端依赖。
- 使用最小PyInstaller或Nuitka冒烟宿主验证SDK可以冻结并从EXE同级加载测试DLL；自动测试保持dry-run，不连接HID。
- 构造临时 `MyClient.exe`目录布局，验证 `from_app_dir()`只依赖EXE目录、同级DLL、resources和data目录。
- 包清单要求接入文档、DXGI dry-run和live示例存在。
- CTest、父仓pytest和SM61 PowerShell包测试全部通过。
- 真实硬件验证沿用已通过的GTX 1080 Ti、COM4、灵敏度2.52流程，不在自动测试中发送HID。

## 兼容与迁移

- `VisionRuntime(dll_path=...)`和原有逐项配置代码继续支持。
- `RuntimeCompatibilityError`仍是 `RuntimeError`，旧的上层异常捕获保持有效。
- 旧DLL不满足ABI v2时明确拒绝；更新SDK时必须同时更新匹配的运行环境包。
- 原父仓wheel可以在迁移期继续包含 `cs2_vision_runtime`。独立SDK wheel只用于调用端开发和冻结构建，不是最终用户需要安装的组件。完成迁移后再通过单独版本决定是否从训练端wheel移除，避免本次升级破坏现有用户。

## 不在本次范围

- Python端传入自定义图像帧。
- 返回所有原始检测框和分类数组。
- asyncio、回调、后台采集线程或多进程调度。
- GUI、账号管理和自动选择标定文件。
- 在SDK wheel或单文件EXE内分发GPU运行库、模型或固件。
- 修改目标选择、瞄准、开火、标定算法或RP2350协议。

## 完成标准

- 调用端构建环境可以用一个零依赖wheel安装SDK，并把SDK冻结进EXE。
- 最终EXE可以通过 `from_app_dir()`加载同级DLL和 `resources/vision-runtime`，不需要Python、wheel、PATH或PYTHONPATH。
- Python完整暴露当前支持的DLL运行时能力，包括TensorRT缓存。
- SDK在创建句柄前阻止旧DLL、结构错位和能力缺失。
- SDK提供可测试的生命周期和安全输出上下文。
- SDK、EXE同级DLL、资源清单、模型和原生依赖的版本关系由包级测试约束。
- 接入指南的示例只使用当前公开API并能通过语法及模拟调用测试。
- 自动测试不产生物理HID输入；最终真实输出仍需调用端显式武装。
