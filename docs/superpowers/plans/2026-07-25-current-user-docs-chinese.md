# 当前用户文档中文化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 将父仓及其相关子仓库的 8 份当前用户文档统一为简体中文，同时保持命令、路径、参数、API、协议常量和硬件型号的原始语义，并保证子模块版本关系正确。

**架构：** 按依赖关系从板控 SDK 向固件、运行时和父仓逐层修改与提交。每个独立仓库先完成本仓文档翻译和验证，再提交；随后由上层仓库更新对应 gitlink，确保父仓全新递归拉取后得到同一套版本。

**技术栈：** Markdown、PowerShell、Git 子模块、CMake/CTest、uv/unittest/pytest、Rust/Cargo、Node.js、GitHub Actions。

---

## 文件结构与职责

| 文件 | 仓库 | 本次职责 |
|---|---|---|
| `README.md` | 父仓 | 项目总览、仓库结构、快速开始、训练端、C++ 运行时、固件与 SDK 的中文入口 |
| `docs/BUILD.md` | 父仓 | 从环境准备到各子项目构建、测试、固件生成与常见问题的中文构建指南 |
| `docs/USAGE.md` | 父仓 | 从拉取、模型准备、视频验证到 DXGI 和外部键鼠控制的中文操作教程 |
| `tools/cpp_analyzer/README.md` | C++ 运行时仓库 | 运行时依赖、构建、模型契约、输入验证、试运行、HID、C API 与便携包说明 |
| `tools/cpp_analyzer/packaging/sm61/package/README_中文.md` | C++ 运行时仓库 | 审校现有 GTX 1080 Ti/SM61 中文便携包说明，统一术语并清除遗漏英文 |
| `tools/rp2350_hid_bridge_cpp/README.md` | C++ 板控 SDK 仓库 | C++ SDK 构建、集成、直接控制、脚本、协议可靠性与会话生命周期说明 |
| `tools/rp2350_keymouse_bridge_firmware/README.md` | 固件仓库 | Pico 2/RP2350 固件构建、UF2、USB 身份、验证、刷写、hidctl、SDK 与安全说明 |
| `tools/rp2350_keymouse_bridge_firmware/sdk/python/README.md` | Python 板控 SDK 仓库 | Python SDK 安装、设备发现、控制 API、脚本、错误处理与安全租约说明 |

以下内容明确不修改：历史 `docs/superpowers/plans`、除设计说明与本计划外的历史 `docs/superpowers/specs`、源代码注释、测试名、日志、许可证、第三方文档和生成产物。

## 统一翻译与检查规则

- 标题、正文、表格说明、提示、警告和故障排查使用自然的简体中文，不逐字硬译。
- 统一使用：运行时、固件、主机、桥接器、载荷、心跳、批处理、试运行、便携包、模型结构说明、子模块。
- 保留 `SDK`、`API`、`CLI`、`DXGI`、`CUDA`、`TensorRT`、`CMake`、`Cargo`、`UF2`、`RP2350`、`Pico 2` 等名称。
- 不改变代码围栏内命令、文件路径、参数、环境变量、类名、函数名、配置键、协议字段、协议常量、URL、提交哈希和需要复制执行的终端内容。
- 代码块里的纯说明性英文注释可以翻译，但命令与示例行为必须保持不变。
- 每次提交前运行 `git diff --check`，并人工查看 `git diff --word-diff`，确认没有误改命令或示例。

### Task 1：翻译并验证 C++ 板控 SDK 文档

**Files:**
- Modify: `tools/rp2350_hid_bridge_cpp/README.md`

- [ ] **Step 1：翻译概览、依赖和构建章节**

将文档标题和以下章节改为中文：`Requirements` → `环境要求`、`Build And Test` → `构建与测试`、`Use In CMake` → `在 CMake 中使用`、`Header Layout` → `头文件结构`。翻译这些章节的说明正文和产物说明；原样保留所有 PowerShell、CMake、C++ 和 `text` 代码块。

- [ ] **Step 2：翻译 API 和协议章节**

将 `Direct Control API`、`Script API`、`Protocol Helpers`、`Protocol v2 Reliability`、`Protocol v2 Safety Lease`、`Concurrency And Session Lifecycle`、`Notes` 分别译为 `直接控制 API`、`脚本 API`、`协议辅助接口`、`协议 v2 可靠性`、`协议 v2 安全租约`、`并发与会话生命周期`、`注意事项`。正文采用设计说明中的统一术语；原样保留 API 名称、异常类型、键名、协议常量及示例代码。

- [ ] **Step 3：检查 C++ SDK README 的结构与残留英文**

Run:

```powershell
git -C tools\rp2350_hid_bridge_cpp diff --check
$count = (Select-String -LiteralPath tools\rp2350_hid_bridge_cpp\README.md -Pattern '^```').Count
if ($count % 2 -ne 0) { throw "README.md 的 Markdown 围栏未闭合" }
rg -n "^(#{1,6}\s+)?[A-Za-z][A-Za-z0-9 ,.'()/+&:-]*$" tools\rp2350_hid_bridge_cpp\README.md
```

Expected: `git diff --check` 无输出；围栏检查不抛错；`rg` 结果只剩代码、标识符、硬件/工具名称或确需保留的英文。

- [ ] **Step 4：构建并测试 C++ SDK**

Run:

```powershell
cmake -S tools\rp2350_hid_bridge_cpp -B tools\rp2350_hid_bridge_cpp\build
cmake --build tools\rp2350_hid_bridge_cpp\build --config Release
ctest --test-dir tools\rp2350_hid_bridge_cpp\build -C Release --output-on-failure
```

Expected: 配置与构建成功，`protocol` 测试通过；测试不需要连接真实板卡。

- [ ] **Step 5：提交 C++ SDK 文档**

Run:

```powershell
git -C tools\rp2350_hid_bridge_cpp add README.md
git -C tools\rp2350_hid_bridge_cpp commit -m "docs: translate C++ SDK guide to Chinese"
```

Expected: C++ SDK 仓库生成一个只包含 `README.md` 的提交。

### Task 2：翻译并验证 Python 板控 SDK 文档

**Files:**
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/README.md`

- [ ] **Step 1：翻译安装、发现与直接控制章节**

将标题和 `Requirements`、`Install`、`Find The Device`、`Direct Control API` 译为中文。说明 `port=None` 自动发现、`CAFE:2350`、COM 口和上下文管理器行为时，保留包名、类名、参数名、键名与全部命令/代码块。

- [ ] **Step 2：翻译脚本、错误与会话安全章节**

将 `Script API`、`Error Handling`、`Protocol v2 Safety Lease`、`Concurrency And Session Lifecycle`、`Notes` 分别译为 `脚本 API`、`错误处理`、`协议 v2 安全租约`、`并发与会话生命周期`、`注意事项`。准确保留 `HidBridgeError`、`HidBridgeNackError`、`HidBridgeTransportError`、`STOP_ALL` 等标识符的含义。

- [ ] **Step 3：检查 Python SDK README 的结构与残留英文**

Run:

```powershell
git -C tools\rp2350_keymouse_bridge_firmware\sdk\python diff --check
$count = (Select-String -LiteralPath tools\rp2350_keymouse_bridge_firmware\sdk\python\README.md -Pattern '^```').Count
if ($count % 2 -ne 0) { throw "Python SDK README.md 的 Markdown 围栏未闭合" }
rg -n "^(#{1,6}\s+)?[A-Za-z][A-Za-z0-9 ,.'()/+&:-]*$" tools\rp2350_keymouse_bridge_firmware\sdk\python\README.md
```

Expected: `git diff --check` 无输出；围栏闭合；`rg` 结果只包含允许保留的代码、API、键名和专有名词。

- [ ] **Step 4：运行 Python SDK 单元测试**

Run:

```powershell
uv run --project tools\rp2350_keymouse_bridge_firmware\sdk\python python -m unittest discover -s tools\rp2350_keymouse_bridge_firmware\sdk\python\tests -v
```

Expected: Python SDK 全部单元测试通过，不连接真实板卡。

- [ ] **Step 5：提交 Python SDK 文档**

Run:

```powershell
git -C tools\rp2350_keymouse_bridge_firmware\sdk\python add README.md
git -C tools\rp2350_keymouse_bridge_firmware\sdk\python commit -m "docs: translate Python SDK guide to Chinese"
```

Expected: Python SDK 仓库生成一个只包含 `README.md` 的提交。

### Task 3：翻译并验证 C++ 运行时文档

**Files:**
- Modify: `tools/cpp_analyzer/README.md`
- Modify: `tools/cpp_analyzer/packaging/sm61/package/README_中文.md`

- [ ] **Step 1：翻译运行时的环境与构建章节**

将运行时标题以及 `Requirements`、`Build with xmake`、`GTX 1080 Ti Production Runtime`、`Build with CMake` 分别译为中文。保留 `xmake`、CMake、ONNX Runtime、OpenCV、CUDA/TensorRT、SM61、环境变量、产物路径和所有命令。

- [ ] **Step 2：翻译模型、输入和试运行章节**

将 `Model Contract`、`Verify Inputs`、`Offline Dry-Run` 译为 `模型契约`、`输入验证`、`离线试运行`。模型结构说明、类别顺序、路径规则、退出码和诊断命令必须与当前程序行为一致，代码块只翻译纯说明性注释。

- [ ] **Step 3：翻译实时 HID、算法和接口章节**

将 `Live HID Mode`、`HID Calibration`、`Backends`、`Algorithm Notes`、`Windows Pointer Settings`、`CLI Help`、`C API DLL`、`GTX 1080 Ti Portable Package` 分别译为 `实时 HID 模式`、`HID 校准`、`后端`、`算法说明`、`Windows 指针设置`、`CLI 帮助`、`C API DLL`、`GTX 1080 Ti 便携包`。保留 CLI 参数、配置键、C API 符号、协议常量和示例代码。

- [ ] **Step 4：审校 SM61 包内中文说明**

逐段检查 `packaging/sm61/package/README_中文.md` 的首次测试、屏幕测试、日志缓存、故障处理、DLL 接入和 Python 示例。修正遗漏英文说明与不一致术语；不得改变脚本名、参数、目录布局或复制执行命令。

- [ ] **Step 5：检查两份运行时文档**

Run:

```powershell
git -C tools\cpp_analyzer diff --check
$files = @(
  'tools\cpp_analyzer\README.md',
  'tools\cpp_analyzer\packaging\sm61\package\README_中文.md'
)
foreach ($file in $files) {
  $count = (Select-String -LiteralPath $file -Pattern '^```').Count
  if ($count % 2 -ne 0) { throw "$file 的 Markdown 围栏未闭合" }
}
rg -n "^(#{1,6}\s+)?[A-Za-z][A-Za-z0-9 ,.'()/+&:-]*$" $files
```

Expected: 差异检查和围栏检查通过；残留英文只属于代码、API、专有名词或命令输出。

- [ ] **Step 6：运行 C++ 运行时与便携包测试**

Run:

```powershell
Push-Location tools\cpp_analyzer
try {
  xmake f -m release
  xmake
  xmake run vision_analyzer_tests
  xmake run vision_runtime_c_api_tests
  powershell -NoProfile -ExecutionPolicy Bypass -File packaging\sm61\tests\run-tests.ps1
} finally {
  Pop-Location
}
```

Expected: 两个 C++ 测试目标和全部 SM61 打包脚本测试通过。

- [ ] **Step 7：提交 C++ 运行时文档**

Run:

```powershell
git -C tools\cpp_analyzer add README.md packaging/sm61/package/README_中文.md
git -C tools\cpp_analyzer commit -m "docs: translate runtime guides to Chinese"
```

Expected: C++ 运行时仓库生成一个只包含两份目标文档的提交。

### Task 4：翻译固件文档并同步 SDK gitlink

**Files:**
- Modify: `tools/rp2350_keymouse_bridge_firmware/README.md`
- Modify gitlink: `tools/rp2350_keymouse_bridge_firmware/sdk/cpp`
- Modify gitlink: `tools/rp2350_keymouse_bridge_firmware/sdk/python`

- [ ] **Step 1：推送两个已验证的叶子 SDK 提交**

Run:

```powershell
git -C tools\rp2350_hid_bridge_cpp push
git -C tools\rp2350_keymouse_bridge_firmware\sdk\python push
```

Expected: C++ SDK 与 Python SDK 的中文 README 提交出现在各自远程当前分支；命令无 non-fast-forward 错误。

- [ ] **Step 2：让固件内的 C++ SDK 从远程取得同一提交**

Run:

```powershell
git -C tools\rp2350_keymouse_bridge_firmware\sdk\cpp fetch origin main
git -C tools\rp2350_keymouse_bridge_firmware\sdk\cpp checkout --detach origin/main
$direct = git -C tools\rp2350_hid_bridge_cpp rev-parse HEAD
$nested = git -C tools\rp2350_keymouse_bridge_firmware\sdk\cpp rev-parse HEAD
if ($direct -ne $nested) { throw "两份 C++ SDK 未指向同一提交：$direct != $nested" }
```

Expected: 两个 C++ SDK 路径输出完全相同的提交哈希；固件仓显示 `sdk/cpp` 与 `sdk/python` gitlink 待更新。

- [ ] **Step 3：翻译仓库、构建和 UF2 章节**

将固件标题以及 `Repository Layout`、`Requirements`、`Build Firmware`、`Build a BOOTSEL UF2`、`USB identity` 译为 `仓库结构`、`环境要求`、`构建固件`、`构建 BOOTSEL UF2`、`USB 身份`。准确说明 `cargo build --release` 与 `tools/build-release.ps1` 的区别，保留 `CAFE:2350`、UF2 family ID `0xE48BFF59`、产物路径和所有命令。

- [ ] **Step 4：翻译验证、刷写和 hidctl 章节**

将 `Automated Verification`、`Flash Firmware`、`Build hidctl`、`Manual hardware acceptance` 译为 `自动化验证`、`刷写固件`、`构建 hidctl`、`手动硬件验收`。保留安全边界：普通构建和测试不得刷板、打开串口或发送 HID；只有明确的刷写和硬件验收命令会访问设备。

- [ ] **Step 5：翻译 SDK、协议、LED 与注意事项章节**

将 `SDK Usage`、`Protocol and safety summary`、`LED Status`、`Notes` 译为 `SDK 使用`、`协议与安全摘要`、`LED 状态`、`注意事项`。统一使用“主机、桥接器、心跳、批处理、安全租约”，保留命令字、错误码、常量、LED 模式和 API 名称。

- [ ] **Step 6：检查固件 README 与 gitlink 差异**

Run:

```powershell
git -C tools\rp2350_keymouse_bridge_firmware diff --check
$count = (Select-String -LiteralPath tools\rp2350_keymouse_bridge_firmware\README.md -Pattern '^```').Count
if ($count % 2 -ne 0) { throw "固件 README.md 的 Markdown 围栏未闭合" }
rg -n "^(#{1,6}\s+)?[A-Za-z][A-Za-z0-9 ,.'()/+&:-]*$" tools\rp2350_keymouse_bridge_firmware\README.md
git -C tools\rp2350_keymouse_bridge_firmware diff --submodule=log -- README.md sdk/cpp sdk/python
```

Expected: 文档结构检查通过；差异仅包含固件 README 翻译和两个 SDK gitlink 前移。

- [ ] **Step 7：执行与固件 CI 相同的非硬件验证**

Run:

```powershell
Push-Location tools\rp2350_keymouse_bridge_firmware
try {
  cargo fmt --all -- --check
  cargo test --target x86_64-pc-windows-msvc --lib
  cargo clippy --release -- -D warnings
  cargo build --release
  cargo test --manifest-path tools/hidctl/Cargo.toml --target x86_64-pc-windows-msvc
  node --test tools/webui/tests/protocol.test.mjs
  uv run --project sdk/python python -m unittest discover -s sdk/python/tests -v
  cmake -S sdk/cpp -B sdk/cpp/build
  cmake --build sdk/cpp/build --config Release
  ctest --test-dir sdk/cpp/build -C Release --output-on-failure
  powershell -NoProfile -ExecutionPolicy Bypass -File tools/tests/build-release-uf2.ps1
} finally {
  Pop-Location
}
```

Expected: 格式检查、Rust/C++/Python/WebUI 测试、Release 固件构建和 UF2 集成检查全部通过；不会刷写板卡或发送键鼠输入。

- [ ] **Step 8：提交固件文档与 SDK gitlink**

Run:

```powershell
git -C tools\rp2350_keymouse_bridge_firmware add README.md sdk/cpp sdk/python
git -C tools\rp2350_keymouse_bridge_firmware commit -m "docs: translate firmware guide and update SDKs"
```

Expected: 固件仓库生成一个包含 `README.md` 和两个 SDK gitlink 更新的提交。

### Task 5：审校父仓用户文档并更新子模块引用

**Files:**
- Modify: `README.md`
- Modify: `docs/BUILD.md`
- Modify: `docs/USAGE.md`
- Modify gitlink: `tools/cpp_analyzer`
- Modify gitlink: `tools/rp2350_hid_bridge_cpp`
- Modify gitlink: `tools/rp2350_keymouse_bridge_firmware`

- [ ] **Step 1：推送已验证的运行时与固件提交**

Run:

```powershell
git -C tools\cpp_analyzer push
git -C tools\rp2350_keymouse_bridge_firmware push
```

Expected: 运行时和固件的新提交均已存在于各自远程当前分支，使父仓即将记录的 gitlink 可被全新拉取。

- [ ] **Step 2：审校父仓 README**

保留项目名 `CS2 Vision Trainer`，可在首次出现处补充“CS2 视觉训练器”。把 `C++ runtime` 等用户可见英文标题统一为 `C++ 运行时`，检查仓库结构、快速拉取、训练流程、运行时、Python 调 DLL、固件与 SDK、数据模型和维护命令的说明。不得改动命令、路径、包名、CLI 参数或示例代码。

- [ ] **Step 3：审校构建指南**

将 `# Build Guide` 改为 `# 构建指南`，把 `C++ Runtime`、`HID Bridge`、`Heartbeat`、`Batch` 等可翻译标题和说明统一为约定中文。逐节核对 Python 训练端、C++ 运行时、Runtime DLL、SM61 便携包、两个 SDK、固件/UF2 和常见问题，确保命令仍对应当前目录结构与当前构建方式。

- [ ] **Step 4：审校使用教程**

检查 `docs/USAGE.md` 的拉取、依赖、运行时构建、模型准备、视频、DXGI、板卡鼠标、实时输出、左键和故障排查流程。把用户说明中的 `dry-run` 统一为“试运行”，把 `runtime` 统一为“运行时”；保留文件名、CLI 参数、输出文本、API 和配置键。

- [ ] **Step 5：检查父仓三份文档与相对链接**

Run:

```powershell
git diff --check
$files = @('README.md', 'docs\BUILD.md', 'docs\USAGE.md')
foreach ($file in $files) {
  $count = (Select-String -LiteralPath $file -Pattern '^```').Count
  if ($count % 2 -ne 0) { throw "$file 的 Markdown 围栏未闭合" }
}
$links = [regex]'\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)'
foreach ($file in $files) {
  $base = Split-Path -Parent (Resolve-Path -LiteralPath $file)
  foreach ($match in $links.Matches((Get-Content -LiteralPath $file -Raw))) {
    $target = ($match.Groups[1].Value -split '#', 2)[0]
    if ($target -and -not (Test-Path -LiteralPath (Join-Path $base $target))) {
      throw "$file 存在失效相对链接：$target"
    }
  }
}
rg -n "^(#{1,6}\s+)?[A-Za-z][A-Za-z0-9 ,.'()/+&:-]*$" $files
```

Expected: 差异、围栏和相对链接检查通过；残留英文只属于项目名、API、工具名、路径、代码或命令。

- [ ] **Step 6：运行父仓 Python 测试**

Run:

```powershell
uv run --extra dev pytest
```

Expected: 父仓测试套件全部通过，包括运行时 Python 包的导出符号和模型结构说明相关测试。

- [ ] **Step 7：提交父仓用户文档和子模块引用**

Run:

```powershell
git add README.md docs/BUILD.md docs/USAGE.md tools/cpp_analyzer tools/rp2350_hid_bridge_cpp tools/rp2350_keymouse_bridge_firmware
git commit -m "docs: translate current user guides to Chinese"
```

Expected: 父仓提交包含三份用户文档和三个直接子模块 gitlink；不包含历史计划/设计文档的翻译或其他源代码变化。

### Task 6：执行跨仓最终验证、推送父仓并等待 CI

**Files:**
- Verify: 全部 8 份目标文档
- Verify: 父仓与固件仓的全部相关 gitlink

- [ ] **Step 1：统一检查 8 份文档的围栏、相对链接和残留英文**

Run:

```powershell
$files = @(
  'README.md',
  'docs\BUILD.md',
  'docs\USAGE.md',
  'tools\cpp_analyzer\README.md',
  'tools\cpp_analyzer\packaging\sm61\package\README_中文.md',
  'tools\rp2350_hid_bridge_cpp\README.md',
  'tools\rp2350_keymouse_bridge_firmware\README.md',
  'tools\rp2350_keymouse_bridge_firmware\sdk\python\README.md'
)
foreach ($file in $files) {
  $count = (Select-String -LiteralPath $file -Pattern '^```').Count
  if ($count % 2 -ne 0) { throw "$file 的 Markdown 围栏未闭合" }
}
$links = [regex]'\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)'
foreach ($file in $files) {
  $base = Split-Path -Parent (Resolve-Path -LiteralPath $file)
  foreach ($match in $links.Matches((Get-Content -LiteralPath $file -Raw))) {
    $target = ($match.Groups[1].Value -split '#', 2)[0]
    if ($target -and -not (Test-Path -LiteralPath (Join-Path $base $target))) {
      throw "$file 存在失效相对链接：$target"
    }
  }
}
rg -n "^(#{1,6}\s+)?[A-Za-z][A-Za-z0-9 ,.'()/+&:-]*$" $files
```

Expected: 围栏和链接检查无错误；逐条审阅 `rg` 输出后，没有未解释的英文用户说明。

- [ ] **Step 2：验证父仓、固件和两份 C++ SDK 的提交关系**

Run:

```powershell
$directCpp = git -C tools\rp2350_hid_bridge_cpp rev-parse HEAD
$nestedCpp = git -C tools\rp2350_keymouse_bridge_firmware\sdk\cpp rev-parse HEAD
$firmwareCppLink = git -C tools\rp2350_keymouse_bridge_firmware rev-parse HEAD:sdk/cpp
$firmwarePythonLink = git -C tools\rp2350_keymouse_bridge_firmware rev-parse HEAD:sdk/python
$nestedPython = git -C tools\rp2350_keymouse_bridge_firmware\sdk\python rev-parse HEAD
if ($directCpp -ne $nestedCpp -or $directCpp -ne $firmwareCppLink) { throw 'C++ SDK 提交不一致' }
if ($nestedPython -ne $firmwarePythonLink) { throw 'Python SDK gitlink 与工作区不一致' }
$parentRuntime = git rev-parse HEAD:tools/cpp_analyzer
$parentCpp = git rev-parse HEAD:tools/rp2350_hid_bridge_cpp
$parentFirmware = git rev-parse HEAD:tools/rp2350_keymouse_bridge_firmware
if ($parentRuntime -ne (git -C tools\cpp_analyzer rev-parse HEAD)) { throw '父仓运行时 gitlink 不一致' }
if ($parentCpp -ne $directCpp) { throw '父仓 C++ SDK gitlink 不一致' }
if ($parentFirmware -ne (git -C tools\rp2350_keymouse_bridge_firmware rev-parse HEAD)) { throw '父仓固件 gitlink 不一致' }
git submodule status --recursive
```

Expected: 直接与嵌套 C++ SDK 为同一提交；Python SDK、运行时、固件和父仓 gitlink 全部与各自工作区 HEAD 一致；递归子模块状态没有 `-`、`+` 或 `U` 前缀。

- [ ] **Step 3：确认各仓工作区干净且提交范围正确**

Run:

```powershell
$repos = @(
  '.',
  'tools\cpp_analyzer',
  'tools\rp2350_hid_bridge_cpp',
  'tools\rp2350_keymouse_bridge_firmware',
  'tools\rp2350_keymouse_bridge_firmware\sdk\cpp',
  'tools\rp2350_keymouse_bridge_firmware\sdk\python'
)
foreach ($repo in $repos) {
  $status = git -C $repo status --porcelain --ignore-submodules=none
  if ($status) { throw "$repo 工作区不干净：`n$status" }
}
git show --stat --oneline HEAD
git -C tools\cpp_analyzer show --stat --oneline HEAD
git -C tools\rp2350_hid_bridge_cpp show --stat --oneline HEAD
git -C tools\rp2350_keymouse_bridge_firmware show --stat --oneline HEAD
git -C tools\rp2350_keymouse_bridge_firmware\sdk\python show --stat --oneline HEAD
```

Expected: 六个工作区均无未提交变化；最新提交统计只包含计划内文档和必要 gitlink。

- [ ] **Step 4：推送父仓**

Run:

```powershell
git push
```

Expected: 父仓当前分支成功推送，远程能够递归解析所有新 gitlink。

- [ ] **Step 5：等待固件 CI 并记录结果**

Run:

```powershell
$firmwareSha = git -C tools\rp2350_keymouse_bridge_firmware rev-parse HEAD
$runs = gh run list --repo ExquisiteCore/rp2350-keymouse-bridge-firmware --workflow ci.yml --branch main --limit 10 --json databaseId,headSha,status,conclusion,url | ConvertFrom-Json
$run = $runs | Where-Object headSha -eq $firmwareSha | Select-Object -First 1
if (-not $run) { throw "未找到固件提交 $firmwareSha 对应的 CI" }
gh run watch $run.databaseId --repo ExquisiteCore/rp2350-keymouse-bridge-firmware --exit-status
gh run view $run.databaseId --repo ExquisiteCore/rp2350-keymouse-bridge-firmware --json headSha,status,conclusion,url
```

Expected: 对应固件提交的 CI 状态为 `completed`、结论为 `success`。

- [ ] **Step 6：向用户汇报交付结果**

报告 8 份已中文化文档、五个仓库的新提交哈希、父仓/固件仓 gitlink 一致性、本地测试结果、固件 CI 链接，并明确说明未翻译历史计划、历史设计和源代码内容。
