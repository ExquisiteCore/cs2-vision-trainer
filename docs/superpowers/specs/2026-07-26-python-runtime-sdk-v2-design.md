# Python Runtime SDK v2 设计

## 目标

把 `cs2_vision_runtime` 从父仓中的内部 `ctypes` 包装层升级为可独立交付、可版本校验、默认安全的 Windows x64 Python SDK。外部调用端只需要安装一个零依赖 wheel，并指向解压后的 SM61 运行环境，即可配置模型、启动 TensorRT/DXGI、读取逐帧动作、管理 HID 标定缓存以及显式控制瞄准和开火。

本次设计只面向 Python 调用端。原生 C/C++ 接入文档、调用端传入图像帧、完整检测框数组和异步回调不在范围内。

## 当前问题

现有实现已经通过 Python SDK 调用 DLL 完成了 GTX 1080 Ti 实机验证，但作为对外 SDK 仍有以下缺口：

1. DLL 已导出 `va_set_tensorrt_cache_path`，Python 包装层没有绑定和公开该接口。
2. Python SDK 和 DLL 没有显式 ABI 握手；旧 DLL 缺少新导出时只会抛出 `AttributeError: function ... not found`。
3. 兼容性测试只验证“Python 使用的符号存在于 C 头文件”，不能发现“C API 新增而 Python 漏绑”。
4. SDK 只能作为父仓 wheel 的一部分或通过 `PYTHONPATH` 使用；父仓 wheel 同时携带训练端依赖，不适合作为运行时 SDK 安装。
5. 调用端必须手工设置 DLL 路径和运行库目录，便携包根目录没有成为正式的 SDK 概念。
6. 真实输出的解锁和撤销由示例手写 `try/finally`，第三方调用端容易漏掉某一步。
7. `VisionRuntime.close()` 直接销毁句柄，虽然 C++ 析构会关闭会话，但 Python 层没有显式执行和验证 `va_close()` 生命周期。
8. 配置方法在会话打开后仍可能返回成功，但多数配置只会影响下一次打开，调用端容易误以为当前会话已经更新。
9. SM61 包文档声明缓存位于 `cache/ort-trt-sm61-fp32`，现有 Python 示例没有设置该路径，实际会使用 C++ 默认相对目录。
10. 便携包漏装了安全的 DXGI dry-run 示例，且标定说明仍残留已经移除的 2048-counts 探测描述。

## 设计原则

- Python SDK 是唯一面向调用端的接口；C ABI 是 SDK 的内部承载层。
- GPU 运行库、模型和 DLL 继续由运行环境包交付，不进入 wheel。
- SDK wheel 零第三方依赖，不安装 `onnxruntime-gpu`、CUDA、TensorRT、OpenCV 或训练端依赖。
- 原有公开方法保持可用，新能力采用向后兼容的增量接口。
- 默认不产生 HID 移动或点击；真实输出必须在已打开会话上显式武装。
- SDK 与 DLL 在创建运行时句柄前完成 ABI 和能力检查。
- 调用端决定标定文件、账号映射和重新标定时机；SDK 和 DLL 不理解账号。

## 分发架构

使用“一份源码、两种分发”的方式：

```text
调用端
  └─ cs2-vision-runtime-sdk wheel（零依赖）
       └─ cs2_vision_runtime
            └─ ctypes
                 └─ SM61 运行环境
                      ├─ app/vision_runtime.dll
                      ├─ app/onnxruntime*.dll
                      ├─ model/
                      ├─ runtime/cuda-11.8/
                      ├─ runtime/cudnn-8.9/
                      ├─ runtime/tensorrt-8.6.1.6/
                      └─ cache/ort-trt-sm61-fp32/
```

规范交付物：

- `sdk/cs2_vision_runtime-<version>-py3-none-win_amd64.whl`：供 `uv add` 或 `pip install`。
- `python/cs2_vision_runtime/`：免安装兼容方式，供便携脚本设置 `PYTHONPATH`。
- `PYTHON_SDK_INTEGRATION.md`：便携包根目录的完整中文接入指南。
- `examples/runtime_dxgi_dryrun.py`：不连接 HID 的 TensorRT/DXGI 验证示例。
- `examples/runtime_live_move.py`：需要显式武装的完整运行示例。

wheel 与便携目录必须从父仓 `src/cs2_vision_runtime` 同一份规范源码构建。组包测试需要比较关键源码文件和版本，防止两份 SDK 漂移。

## 运行环境定位

保留 `VisionRuntime(dll_path=...)`，新增推荐入口：

```python
runtime = VisionRuntime.from_bundle(r"D:\runtime\cs2-vision-runtime-sm61")
```

`from_bundle()` 执行以下行为：

1. 解析绝对运行环境根目录。
2. 验证 `app/vision_runtime.dll` 存在。
3. 验证 SM61 运行需要的 `app`、CUDA、cuDNN、TensorRT 和 MSVC 私有目录存在。
4. 使用 `os.add_dll_directory()` 注册目录并在 SDK 对象生命周期内保留句柄。
5. 加载 `vision_runtime.dll`，然后执行 ABI 兼容检查。

自动发现顺序保持确定性：

1. 显式 `dll_path` 或 `from_bundle(root)`。
2. `CS2_VISION_RUNTIME_DLL`。
3. 新增 `CS2_VISION_RUNTIME_HOME`，解析为 `<home>/app/vision_runtime.dll`。
4. Python 包相邻的受支持布局。
5. 开发构建目录，包括 xmake Release 和 CMake `build-cmake/Release`。

SDK 不永久修改系统 `PATH`、注册表或系统 DLL 目录。

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

当提供 `tensorrt_cache_path` 时，SDK调用DLL现有的 `va_set_tensorrt_cache_path`。接入指南统一使用运行环境下的绝对缓存路径。更换模型、GPU、ORT、CUDA、cuDNN或TensorRT后由调用端清理旧缓存。

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
from pathlib import Path

from cs2_vision_runtime import VisionRuntime

bundle = Path(r"D:\runtime\cs2-vision-runtime-sm61")

with VisionRuntime.from_bundle(bundle) as runtime:
    runtime.set_model(
        bundle / "model" / "best.onnx",
        schema_path=bundle / "model" / "best.onnx.schema.json",
        backend="ort-tensorrt",
        tensorrt_cache_path=bundle / "cache" / "ort-trt-sm61-fp32",
    )
    runtime.set_hid_port("COM4")
    runtime.set_hid_calibration_path(bundle / "hid-calibration.json")

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

第一次创建TensorRT引擎时可能长时间停留在模型初始化阶段。INT64权重向INT32转换是警告而不是失败；SDK以 `open_dxgi()` 是否成功返回和后续是否产生 `VisionAction` 判断运行结果。

## wheel与版本

独立发行名称为 `cs2-vision-runtime-sdk`，导入名保持 `cs2_vision_runtime`。初始v2版本为 `0.2.0`，支持 Python 3.11及以上、Windows x64。

wheel不包含：

- `vision_runtime.dll`。
- ONNX Runtime Provider。
- CUDA、cuDNN或TensorRT。
- 模型和schema。
- RP2350固件。

便携包清单记录 Python SDK 版本和 DLL ABI 版本。包内 wheel、免安装源码和 DLL 必须来自同一次构建；组包过程拒绝版本或源码不一致的组合。

## 接入文档结构

新增 `docs/PYTHON_RUNTIME_SDK_INTEGRATION.md`，组包时复制为根目录 `PYTHON_SDK_INTEGRATION.md`。内容按以下顺序组织：

1. 适用范围、Windows x64和安全说明。
2. wheel安装与免安装两种方式。
3. 运行环境目录和 `from_bundle()`。
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
- `from_bundle()`路径和私有DLL目录顺序。
- TensorRT缓存setter和扩展后的 `set_model()`调用顺序。
- READY/OPEN/CLOSED状态转换和非法调用。
- `iter_actions()`正常结束与错误传播。
- `armed_output()`正常、处理错误和部分清理失败时的完整撤销顺序。
- `close()`显式关闭、无条件销毁和幂等。

### 分发与包级测试

- 使用 `uv build`生成独立wheel。
- 在全新临时虚拟环境中安装wheel并导入，不安装训练端依赖。
- 比较wheel与便携目录中的SDK版本和关键源码。
- 包清单要求wheel、接入文档、DXGI dry-run和live示例存在。
- CTest、父仓pytest和SM61 PowerShell包测试全部通过。
- 真实硬件验证沿用已通过的GTX 1080 Ti、COM4、灵敏度2.52流程，不在自动测试中发送HID。

## 兼容与迁移

- `VisionRuntime(dll_path=...)`和原有逐项配置代码继续支持。
- `RuntimeCompatibilityError`仍是 `RuntimeError`，旧的上层异常捕获保持有效。
- 旧DLL不满足ABI v2时明确拒绝；更新SDK时必须同时更新匹配的运行环境包。
- 原父仓wheel可以在迁移期继续包含 `cs2_vision_runtime`，但独立SDK wheel是对外推荐方式。完成迁移后再通过单独版本决定是否从训练端wheel移除，避免本次升级破坏现有用户。

## 不在本次范围

- Python端传入自定义图像帧。
- 返回所有原始检测框和分类数组。
- asyncio、回调、后台采集线程或多进程调度。
- GUI、账号管理和自动选择标定文件。
- 在wheel内分发GPU运行库、模型或固件。
- 修改目标选择、瞄准、开火、标定算法或RP2350协议。

## 完成标准

- 外部项目可以用一个零依赖wheel安装SDK，并通过 `from_bundle()`加载SM61运行环境。
- Python完整暴露当前支持的DLL运行时能力，包括TensorRT缓存。
- SDK在创建句柄前阻止旧DLL、结构错位和能力缺失。
- SDK提供可测试的生命周期和安全输出上下文。
- wheel、免安装源码、DLL和文档的版本关系由包级测试约束。
- 接入指南的示例只使用当前公开API并能通过语法及模拟调用测试。
- 自动测试不产生物理HID输入；最终真实输出仍需调用端显式武装。
