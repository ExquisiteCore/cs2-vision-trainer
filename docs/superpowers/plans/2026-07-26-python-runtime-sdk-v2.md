# Python Runtime SDK v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not use subagents for this repository task.

**Goal:** 将 `cs2_vision_runtime` 升级为可冻结进调用端EXE的正式Python SDK，并交付与EXE同级的 `vision_runtime.dll`、`resources/vision-runtime` 原生环境、机器可读清单和完整接入文档。

**Architecture:** Python SDK在调用端构建阶段以零依赖wheel安装，最终冻结进EXE；SDK通过 `VisionRuntime.from_app_dir()`只从EXE同级加载匹配DLL，并从 `resources/vision-runtime/runtime-manifest.json`自动配置模型、schema、TensorRT和调用端可写缓存。DLL增加ABI握手；现有SM61诊断包保持兼容，新增app-local重打包步骤生成调用端可直接覆盖到输出目录的运行环境。

**Tech Stack:** Python 3.11+、ctypes、dataclasses、contextlib、uv、pytest、C++17、C ABI、CMake/CTest、PowerShell、ONNX Runtime 1.17.3、TensorRT 8.6.1.6、CUDA 11.8、cuDNN 8.9.7、Windows x64。

---

## 文件结构

### 父仓 `cs2-vision-trainer`

- Create: `src/cs2_vision_runtime/errors.py`
  - SDK加载、兼容、DLL调用和状态异常。
- Create: `src/cs2_vision_runtime/package.py`
  - app-local清单解析、路径约束、版本/哈希验证和运行环境路径模型。
- Create: `src/cs2_vision_runtime/_version.py`
  - 单一Python SDK版本来源。
- Modify: `src/cs2_vision_runtime/runtime.py`
  - ABI预检、TensorRT setter、状态机、`from_app_dir()`、迭代器和安全武装上下文。
- Modify: `src/cs2_vision_runtime/__init__.py`
  - 公开v2类型、异常和版本。
- Modify: `tests/test_vision_runtime_sdk.py`
  - ABI、导出集合、状态机、清理顺序和新增API测试。
- Create: `tests/test_runtime_package.py`
  - 清单、路径逃逸、哈希、app-local布局和缓存命名空间测试。
- Create: `packaging/python-runtime-sdk/pyproject.toml`
  - 零依赖SDK wheel的构建元数据模板。
- Create: `packaging/python-runtime-sdk/README.md`
  - wheel内简短说明和完整文档链接。
- Create: `scripts/build_python_runtime_sdk.ps1`
  - 从规范源码创建临时构建树并用 `uv build`生成wheel。
- Create: `tests/test_runtime_sdk_distribution.py`
  - wheel构建、元数据、零依赖和干净环境导入测试。
- Create: `examples/runtime_app_local.py`
  - `from_app_dir()`完整安全示例。
- Modify: `examples/runtime_dxgi_dryrun.py`
  - 支持app-local入口，同时保留低层开发参数。
- Create: `docs/PYTHON_RUNTIME_SDK_INTEGRATION.md`
  - 调用端构建、冻结、部署和运行接入指南。
- Modify: `README.md`
- Modify: `docs/USAGE.md`
- Update gitlink: `tools/cpp_analyzer`
  - 指向包含ABI v2和app-local打包器的C++提交。

### C++子仓 `tools/cpp_analyzer`

- Modify: `include/vision_analyzer/vision_runtime_c_api.h`
  - ABI版本、能力位、`VaRuntimeAbiInfo`和 `va_get_abi_info()`。
- Modify: `src/vision_runtime_c_api.cpp`
  - 无句柄ABI查询实现。
- Modify: `tests/test_c_api.cpp`
  - 结构大小、能力位和ABI查询测试。
- Create: `packaging/sm61/build-app-local-package.ps1`
  - 从已验证SM61便携包生成EXE同级应用本地运行环境。
- Modify: `packaging/sm61/tests/run-tests.ps1`
  - app-local目录、清单和非法输入测试。
- Modify: `packaging/sm61/build-portable-package.ps1`
  - 补入DXGI dry-run示例和新版SDK接入文档输入检查。
- Modify: `packaging/sm61/package/README_中文.md`
  - 删除旧2048-counts描述并链接Python SDK指南。

## 跨仓提交顺序

1. 在C++子仓创建 `feat/runtime-abi-v2`，完成ABI和app-local打包器，验证并提交。
2. 合并C++分支到C++ `main`，再次验证并推送。
3. 父仓功能分支更新 `tools/cpp_analyzer` gitlink。
4. 完成Python SDK、wheel、示例和文档，运行父仓与包级验证。
5. 合并父仓功能分支到父仓 `main`，再次验证并推送。

---

### Task 1: 为DLL增加可验证ABI握手

**Files:**
- Modify: `tools/cpp_analyzer/tests/test_c_api.cpp`
- Modify: `tools/cpp_analyzer/include/vision_analyzer/vision_runtime_c_api.h`
- Modify: `tools/cpp_analyzer/src/vision_runtime_c_api.cpp`

- [ ] **Step 1: 创建C++功能分支**

Run:

```powershell
git -C tools/cpp_analyzer switch -c feat/runtime-abi-v2
```

Expected: 子仓从 `ad7883f`创建命名分支，工作树清洁。

- [ ] **Step 2: 写ABI失败测试**

在 `tests/test_c_api.cpp` 增加：

```cpp
static_assert(sizeof(VaRuntimeAction) == 120);
static_assert(sizeof(VaHidCalibrationProfile) == 84);
static_assert(sizeof(VaRuntimeAbiInfo) == 32);

void test_runtime_abi_info() {
    require(va_get_abi_info(nullptr) == -1, "null ABI output must fail");

    VaRuntimeAbiInfo info{};
    info.struct_size = sizeof(info);
    require(va_get_abi_info(&info) == 0, "ABI query should succeed");
    require(info.abi_major == 2 && info.abi_minor == 0,
            "DLL must expose ABI 2.0");
    require(info.runtime_action_size == sizeof(VaRuntimeAction),
            "action size must match the public header");
    require(info.hid_calibration_profile_size == sizeof(VaHidCalibrationProfile),
            "calibration size must match the public header");
    require((info.feature_flags & VA_RUNTIME_FEATURE_TENSORRT_CACHE) != 0,
            "TensorRT cache feature must be declared");
    require((info.feature_flags & VA_RUNTIME_FEATURE_PERSISTENT_CALIBRATION) != 0,
            "persistent calibration feature must be declared");
    require((info.feature_flags & VA_RUNTIME_FEATURE_OUTPUT_ARMING) != 0,
            "output arming feature must be declared");
    require((info.feature_flags & VA_RUNTIME_FEATURE_FIRE_ARMING) != 0,
            "fire arming feature must be declared");
}
```

在测试主函数调用 `test_runtime_abi_info()`。

- [ ] **Step 3: 运行测试并确认编译失败**

Run:

```powershell
cmake -S tools/cpp_analyzer -B tools/cpp_analyzer/build-cmake -A x64
cmake --build tools/cpp_analyzer/build-cmake --config Release --target vision_runtime_c_api_tests
```

Expected: 编译失败，指出 `VaRuntimeAbiInfo`、能力宏和 `va_get_abi_info`尚未定义。

- [ ] **Step 4: 增加ABI头文件契约**

在 `vision_runtime_c_api.h` 增加：

```c
#define VA_RUNTIME_ABI_MAJOR 2u
#define VA_RUNTIME_ABI_MINOR 0u

#define VA_RUNTIME_FEATURE_TENSORRT_CACHE UINT64_C(1)
#define VA_RUNTIME_FEATURE_PERSISTENT_CALIBRATION (UINT64_C(1) << 1)
#define VA_RUNTIME_FEATURE_OUTPUT_ARMING (UINT64_C(1) << 2)
#define VA_RUNTIME_FEATURE_FIRE_ARMING (UINT64_C(1) << 3)

typedef struct VaRuntimeAbiInfo {
    uint32_t struct_size;
    uint32_t abi_major;
    uint32_t abi_minor;
    uint32_t runtime_action_size;
    uint32_t hid_calibration_profile_size;
    uint32_t reserved;
    uint64_t feature_flags;
} VaRuntimeAbiInfo;

VA_API int32_t va_get_abi_info(VaRuntimeAbiInfo* info);
```

`reserved`必须为0，使结构在x64上稳定为32字节并为未来小扩展保留空间。

- [ ] **Step 5: 实现ABI查询**

在C API实现中、`va_create()`之前增加：

```cpp
int32_t va_get_abi_info(VaRuntimeAbiInfo* info) {
    if (info == nullptr || info->struct_size < sizeof(VaRuntimeAbiInfo)) {
        return -1;
    }
    const uint32_t caller_size = info->struct_size;
    *info = VaRuntimeAbiInfo{};
    info->struct_size = caller_size;
    info->abi_major = VA_RUNTIME_ABI_MAJOR;
    info->abi_minor = VA_RUNTIME_ABI_MINOR;
    info->runtime_action_size = sizeof(VaRuntimeAction);
    info->hid_calibration_profile_size = sizeof(VaHidCalibrationProfile);
    info->feature_flags =
        VA_RUNTIME_FEATURE_TENSORRT_CACHE |
        VA_RUNTIME_FEATURE_PERSISTENT_CALIBRATION |
        VA_RUNTIME_FEATURE_OUTPUT_ARMING |
        VA_RUNTIME_FEATURE_FIRE_ARMING;
    return 0;
}
```

- [ ] **Step 6: 构建并验证C API**

Run:

```powershell
cmake --build tools/cpp_analyzer/build-cmake --config Release
ctest --test-dir tools/cpp_analyzer/build-cmake -C Release --output-on-failure
```

Expected: 构建成功，CTest `2/2`通过。

- [ ] **Step 7: 提交ABI握手**

```powershell
git -C tools/cpp_analyzer add include/vision_analyzer/vision_runtime_c_api.h src/vision_runtime_c_api.cpp tests/test_c_api.cpp
git -C tools/cpp_analyzer commit -m "feat: expose runtime ABI compatibility info"
```

---

### Task 2: 为Python加载器增加版本、异常和完整导出检查

**Files:**
- Create: `src/cs2_vision_runtime/_version.py`
- Create: `src/cs2_vision_runtime/errors.py`
- Modify: `src/cs2_vision_runtime/runtime.py`
- Modify: `src/cs2_vision_runtime/__init__.py`
- Modify: `tests/test_vision_runtime_sdk.py`

- [ ] **Step 1: 写Python ABI和导出集合失败测试**

测试必须覆盖：

```python
def test_python_runtime_binds_every_c_api_export():
    assert declared_c_exports == required_python_exports

def test_runtime_rejects_missing_exports_as_one_compatibility_error():
    with pytest.raises(RuntimeCompatibilityError, match="va_get_abi_info.*va_set_tensorrt_cache_path"):
        _RuntimeApi(dll_path, _loader=fake_loader_missing_both)

def test_runtime_rejects_wrong_abi_major():
    with pytest.raises(RuntimeCompatibilityError, match="ABI major"):
        validate_abi_info(make_abi(major=1))

def test_runtime_rejects_wrong_struct_sizes():
    with pytest.raises(RuntimeCompatibilityError, match="VaRuntimeAction"):
        validate_abi_info(make_abi(action_size=1))
```

- [ ] **Step 2: 运行目标测试并确认失败**

```powershell
uv run --extra dev pytest tests/test_vision_runtime_sdk.py -q
```

Expected: 因异常类型、ABI结构、缓存绑定和完整导出集合不存在而失败。

- [ ] **Step 3: 增加版本与异常层**

`_version.py`：

```python
__version__ = "0.2.0"
```

`errors.py`：

```python
class VisionRuntimeError(RuntimeError):
    """Base error for the Python runtime SDK."""

class RuntimeLoadError(VisionRuntimeError):
    pass

class RuntimeCompatibilityError(VisionRuntimeError):
    pass

class RuntimeCallError(VisionRuntimeError):
    pass

class RuntimeStateError(VisionRuntimeError):
    pass
```

- [ ] **Step 4: 增加ctypes ABI结构和必需导出表**

在 `runtime.py` 增加 `_CAbiInfo`、`RuntimeAbiInfo`、ABI常量和 `_REQUIRED_EXPORTS`。`_RuntimeApi`必须先收集全部缺失符号，再绑定签名并调用 `va_get_abi_info()`。验证失败信息包含SDK版本和DLL绝对路径。

同时绑定：

```python
dll.va_set_tensorrt_cache_path.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
dll.va_set_tensorrt_cache_path.restype = ctypes.c_int32
```

- [ ] **Step 5: 公开TensorRT缓存接口**

增加低层转发：

```python
def set_tensorrt_cache_path(self, path: str | os.PathLike[str]) -> None:
    self._check(
        self._api.set_tensorrt_cache_path(
            self._require_handle(),
            _encode_path(path),
        ),
        "set TensorRT cache path",
    )
```

扩展 `set_model(..., tensorrt_cache_path=None)`，在提供参数时调用该setter。

- [ ] **Step 6: 让SDK错误保留旧兼容性**

所有新增异常继承 `RuntimeError`。`_check(status, operation)`抛出 `RuntimeCallError(f"{operation}: {last_error}")`；现有调用端捕获 `RuntimeError`仍有效。

- [ ] **Step 7: 运行SDK测试并提交**

```powershell
uv run --extra dev pytest tests/test_vision_runtime_sdk.py -q
git add src/cs2_vision_runtime tests/test_vision_runtime_sdk.py
git commit -m "feat: validate Python SDK against runtime ABI"
```

Expected: 目标测试全部通过。

---

### Task 3: 实现app-local运行环境清单和 `from_app_dir()`

**Files:**
- Create: `src/cs2_vision_runtime/package.py`
- Modify: `src/cs2_vision_runtime/runtime.py`
- Modify: `src/cs2_vision_runtime/__init__.py`
- Create: `tests/test_runtime_package.py`

- [ ] **Step 1: 写清单失败测试夹具**

测试创建临时布局：

```text
MyClient.exe
vision_runtime.dll
resources/vision-runtime/runtime-manifest.json
resources/vision-runtime/model/best.onnx
resources/vision-runtime/model/best.onnx.schema.json
resources/vision-runtime/native/<five directories>
```

分别断言缺失文件、错误manifest版本、非SM61 profile、绝对路径、`../`逃逸、DLL哈希错误、模型哈希错误、schema哈希错误和SDK版本过低均抛出 `RuntimeCompatibilityError`或 `RuntimeLoadError`。

- [ ] **Step 2: 运行清单测试并确认失败**

```powershell
uv run --extra dev pytest tests/test_runtime_package.py -q
```

Expected: `cs2_vision_runtime.package`不存在。

- [ ] **Step 3: 实现清单数据模型**

实现不可变 `RuntimePackage`，至少包含：

```python
@dataclass(frozen=True)
class RuntimePackage:
    app_dir: Path
    resources_dir: Path
    manifest_path: Path
    dll_path: Path
    model_path: Path
    schema_path: Path
    native_directories: tuple[Path, ...]
    backend: str
    runtime_id: str
    cache_path: Path
```

提供：

```python
@classmethod
def load(cls, app_dir: Path, data_dir: Path, *, verify_native_hashes: bool = False) -> RuntimePackage:
    ...
```

使用 `Path.resolve()`和 `relative_to(resources_dir)`阻止路径逃逸；使用 `hashlib.sha256()`验证DLL、模型和schema。版本比较只接受严格三段数字版本，不引入第三方依赖。

- [ ] **Step 4: 实现 `VisionRuntime.from_app_dir()`**

```python
@classmethod
def from_app_dir(cls, app_dir, *, data_dir):
    package = RuntimePackage.load(Path(app_dir), Path(data_dir))
    runtime = cls(
        dll_path=package.dll_path,
        dll_directories=package.native_directories,
    )
    runtime.set_model(
        package.model_path,
        schema_path=package.schema_path,
        backend=package.backend,
        tensorrt_cache_path=package.cache_path,
    )
    runtime._runtime_package = package
    return runtime
```

若自动配置任一步失败，必须调用 `close()`销毁句柄后重新抛出原错误。

- [ ] **Step 5: 运行清单和SDK测试**

```powershell
uv run --extra dev pytest tests/test_runtime_package.py tests/test_vision_runtime_sdk.py -q
```

- [ ] **Step 6: 提交app-local加载器**

```powershell
git add src/cs2_vision_runtime tests/test_runtime_package.py tests/test_vision_runtime_sdk.py
git commit -m "feat: load app-local vision runtime packages"
```

---

### Task 4: 增加SDK状态机、动作迭代和安全输出上下文

**Files:**
- Modify: `src/cs2_vision_runtime/runtime.py`
- Modify: `src/cs2_vision_runtime/__init__.py`
- Modify: `tests/test_vision_runtime_sdk.py`

- [ ] **Step 1: 写状态和清理失败测试**

覆盖：

- `READY → OPEN → READY → CLOSED`。
- OPEN后调用模型、backend、缓存、阈值、ROI、调优或标定路径setter抛 `RuntimeStateError`。
- READY时 `process_next()`、`iter_actions()`和 `armed_output()`拒绝。
- `iter_actions()`逐帧产出并在C API返回0时结束。
- `armed_output(fire=True)`调用顺序为 output on、fire on、fire off、output off、stop all。
- 处理循环抛错时仍执行全部撤销，原始错误优先。
- `close()`显式调用native close，再无条件destroy；重复close无操作。

- [ ] **Step 2: 运行测试确认失败**

```powershell
uv run --extra dev pytest tests/test_vision_runtime_sdk.py -q
```

- [ ] **Step 3: 实现状态机**

增加公开字符串枚举：

```python
class RuntimeState(str, Enum):
    READY = "ready"
    OPEN = "open"
    CLOSED = "closed"
```

为配置、打开、处理和控制方法增加集中 `_require_state()`；失败的 `open_*`保持READY。

- [ ] **Step 4: 实现动作迭代**

```python
def iter_actions(self):
    self._require_state(RuntimeState.OPEN)
    while True:
        action = self.process_next()
        if action is None:
            return
        yield action
```

- [ ] **Step 5: 实现安全武装上下文**

使用 `@contextmanager`实现 `armed_output(fire=False)`。退出时逐项尝试 fire off、output off、stop all；处理异常不能被清理异常覆盖，正常退出时报告第一个清理错误。

- [ ] **Step 6: 修正关闭生命周期**

`close()`保存句柄、将状态置CLOSED、尝试 `va_close()`、最终始终 `va_destroy()`。`__exit__`在活动异常存在时不得用清理错误覆盖原始异常。

- [ ] **Step 7: 运行测试并提交**

```powershell
uv run --extra dev pytest tests/test_vision_runtime_sdk.py tests/test_runtime_package.py -q
git add src/cs2_vision_runtime tests/test_vision_runtime_sdk.py
git commit -m "feat: enforce safe runtime lifecycle in Python"
```

---

### Task 5: 生成零依赖Python SDK wheel

**Files:**
- Create: `packaging/python-runtime-sdk/pyproject.toml`
- Create: `packaging/python-runtime-sdk/README.md`
- Create: `scripts/build_python_runtime_sdk.ps1`
- Create: `tests/test_runtime_sdk_distribution.py`

- [ ] **Step 1: 写分发失败测试**

测试执行构建脚本到临时目录，打开wheel ZIP并断言：

- 包含 `cs2_vision_runtime`全部规范源码。
- METADATA名称为 `cs2-vision-runtime-sdk`、版本为 `0.2.0`。
- `Requires-Python: >=3.11`。
- 没有 `Requires-Dist`。
- 不包含DLL、模型、CUDA、TensorRT或训练端包。
- 在全新临时venv中可导入并读取 `__version__`。

- [ ] **Step 2: 运行测试确认失败**

```powershell
uv run --extra dev pytest tests/test_runtime_sdk_distribution.py -q
```

- [ ] **Step 3: 创建wheel模板**

`packaging/python-runtime-sdk/pyproject.toml`使用独立构建元数据；构建脚本从根目录 `_version.py`读取版本，把规范包和README复制到临时 `src`布局，再执行：

```powershell
uv build --wheel --out-dir $OutputDir $stageRoot
```

脚本只允许删除自己创建且位于临时目录下的stage，输出目录由调用端显式传入。

- [ ] **Step 4: 运行分发测试并提交**

```powershell
uv run --extra dev pytest tests/test_runtime_sdk_distribution.py -q
git add packaging/python-runtime-sdk scripts/build_python_runtime_sdk.ps1 tests/test_runtime_sdk_distribution.py
git commit -m "build: package zero-dependency runtime SDK"
```

---

### Task 6: 生成EXE同级app-local原生运行环境

**Files:**
- Create: `tools/cpp_analyzer/packaging/sm61/build-app-local-package.ps1`
- Modify: `tools/cpp_analyzer/packaging/sm61/tests/run-tests.ps1`

- [ ] **Step 1: 写PowerShell失败测试**

用临时假便携包验证：

- 缺少已验证源manifest时拒绝。
- 输出包含根目录 `vision_runtime.dll`和 `resources/vision-runtime`。
- ORT DLL位于 `native/onnxruntime`，CUDA/cuDNN/TensorRT/MSVC位于对应目录。
- 模型、schema、config和licenses被复制。
- 不复制 `vision_analyzer.exe`、Python、examples、logs和旧cache。
- 清单路径均为规范相对路径并包含DLL/模型/schema SHA256。
- 已存在且没有app-local标记的目标目录拒绝覆盖。
- 清单中的DLL ABI为2.0，SDK版本为0.2.0。

- [ ] **Step 2: 运行包测试确认失败**

```powershell
& tools/cpp_analyzer/packaging/sm61/tests/run-tests.ps1
```

- [ ] **Step 3: 实现安全重打包脚本**

脚本参数：

```powershell
param(
    [Parameter(Mandatory)] [string] $PortablePackageRoot,
    [Parameter(Mandatory)] [string] $OutputRoot,
    [string] $PythonSdkVersion = '0.2.0'
)
```

复用 `PackageTools.psm1`的路径、哈希和manifest验证函数。只从已通过现有manifest验证的便携包读取，写入 `.app-local-runtime-root`标记后才允许后续替换。

- [ ] **Step 4: 运行C++和包级测试**

```powershell
cmake --build tools/cpp_analyzer/build-cmake --config Release
ctest --test-dir tools/cpp_analyzer/build-cmake -C Release --output-on-failure
& tools/cpp_analyzer/packaging/sm61/tests/run-tests.ps1
```

- [ ] **Step 5: 提交app-local打包器**

```powershell
git -C tools/cpp_analyzer add packaging/sm61
git -C tools/cpp_analyzer commit -m "feat: build app-local SM61 runtime payloads"
```

---

### Task 7: 更新示例、便携包输入和Python接入文档

**Files:**
- Create: `examples/runtime_app_local.py`
- Modify: `examples/runtime_dxgi_dryrun.py`
- Create: `docs/PYTHON_RUNTIME_SDK_INTEGRATION.md`
- Modify: `README.md`
- Modify: `docs/USAGE.md`
- Modify: `tools/cpp_analyzer/packaging/sm61/build-portable-package.ps1`
- Modify: `tools/cpp_analyzer/packaging/sm61/package/README_中文.md`
- Modify: `tools/cpp_analyzer/packaging/sm61/tests/run-tests.ps1`

- [ ] **Step 1: 写示例和文档契约测试**

父仓测试验证 `runtime_app_local.py`使用 `from_app_dir()`、调用端数据目录、持久标定和 `armed_output()`。包级测试要求DXGI dry-run和Python接入指南作为便携包构建输入，并拒绝文档中的旧 `2048 counts`描述。

- [ ] **Step 2: 编写app-local示例**

示例默认 `app_dir=Path(sys.executable).resolve().parent`，允许 `--app-dir`和 `--data-dir`覆盖；没有 `--enable-live-output`时只执行dry-run并且不设置HID端口。真实输出使用安全上下文。

- [ ] **Step 3: 编写完整接入指南**

`docs/PYTHON_RUNTIME_SDK_INTEGRATION.md`必须包含：

1. 调用端与运行环境职责。
2. `uv`安装SDK构建依赖。
3. PyInstaller/Nuitka冻结原则。
4. EXE同级DLL和resources目录。
5. `runtime-manifest.json`契约。
6. `from_app_dir()`最小代码。
7. TensorRT首次初始化、缓存和更新规则。
8. DXGI dry-run。
9. 调用端选择标定文件和显式重标定。
10. `VisionAction`字段。
11. 瞄准、开火和安全停止。
12. 异常类型、线程边界和诊断顺序。
13. 发布前检查清单。

- [ ] **Step 4: 更新现有入口和修正文档**

README与USAGE只链接完整指南。便携包中文README删除2048探测说明，改为中心ROI光流、探测上限120。构建器补入 `runtime_dxgi_dryrun.py`和接入指南。

- [ ] **Step 5: 运行文档和示例验证**

```powershell
uv run --extra dev pytest -q
uv run python -m py_compile examples/runtime_app_local.py examples/runtime_dxgi_dryrun.py examples/runtime_live_move.py
git diff --check
```

- [ ] **Step 6: 分仓提交**

先提交C++包文档和构建器，再提交父仓示例与指南：

```powershell
git -C tools/cpp_analyzer add packaging/sm61
git -C tools/cpp_analyzer commit -m "docs: package Python runtime SDK integration assets"

git add examples docs README.md
git commit -m "docs: add Python runtime SDK integration guide"
```

---

### Task 8: 全量验证、合并两个main并推送

**Files:**
- Update gitlink: `tools/cpp_analyzer`

- [ ] **Step 1: 验证C++子仓**

```powershell
cmake --build tools/cpp_analyzer/build-cmake --config Release
ctest --test-dir tools/cpp_analyzer/build-cmake -C Release --output-on-failure
& tools/cpp_analyzer/packaging/sm61/tests/run-tests.ps1
git -C tools/cpp_analyzer diff --check
git -C tools/cpp_analyzer status --short --branch
```

Expected: 构建成功，CTest 2/2、包测试全部通过，工作树清洁。

- [ ] **Step 2: 合并并推送C++ main**

在C++主工作树执行fast-forward或普通无冲突合并，合并后重复Step 1测试，再：

```powershell
git -C tools/cpp_analyzer push origin main
```

- [ ] **Step 3: 更新父仓gitlink并全量测试**

```powershell
git add tools/cpp_analyzer
git commit -m "chore: update runtime SDK native component"
uv run --extra dev pytest
uv run python -m py_compile examples/runtime_app_local.py examples/runtime_dxgi_dryrun.py examples/runtime_live_move.py
git diff --check
```

Expected: 父仓全部pytest通过，示例语法通过。

- [ ] **Step 4: 构建wheel和app-local测试制品**

```powershell
& scripts/build_python_runtime_sdk.ps1 -OutputDir dist/python-sdk
```

使用已验证SM61便携包调用 `build-app-local-package.ps1`，然后用干净Python进程构造 `VisionRuntime.from_app_dir()`并完成DLL加载/ABI检查；不打开DXGI、不连接COM、不发送HID。

- [ ] **Step 5: 检查提交和范围**

```powershell
git status --short --branch
git log --oneline --decorate -12
git diff main...HEAD --stat
rg -n "TBD|TODO|2048 counts|from_bundle" docs src examples
```

Expected: 只有已批准的SDK、app-local环境、示例、文档和子模块更新；无占位符和旧接口描述。

- [ ] **Step 6: 合并父仓main并重复父仓测试**

将 `feat/python-runtime-sdk-v2`合并回父仓 `main`。在父仓main重新运行完整pytest、wheel构建和文档/示例验证。

- [ ] **Step 7: 推送父仓main**

```powershell
git push origin main
```

- [ ] **Step 8: 清理功能worktree和分支**

仅在两个远端main推送成功后，从父仓主工作树移除 `.worktrees/python-runtime-sdk-v2`、prune worktree并删除已合并分支。
