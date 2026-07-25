# C++ 与 Python SDK 详细接入指南 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 RP2350 HID 桥接器的 C++ SDK 和 Python SDK 各新增一份可独立使用的中文接入指南，并让 SDK、固件仓和父仓的子模块版本保持一致。

**Architecture:** 文档只覆盖应用层接入，统一描述“应用程序 → SDK → CDC 串口 → RP2350 固件 → USB HID → 操作系统”的调用链。C++ 与 Python 指南分别保存在各自 SDK 仓库，先独立验证并提交；随后由固件仓和父仓逐层更新 gitlink，保证递归克隆得到同一套文档和 API 版本。

**Tech Stack:** Markdown、C++17、CMake/CTest、Python 3.10+、uv/unittest、PowerShell、Git 子模块、GitHub Actions。

---

## 文件结构

- Create: `tools/rp2350_hid_bridge_cpp/INTEGRATION.md`
  - C++17/Windows 应用层接入、CMake 集成、COM 端口、异常与 RAII 生命周期。
- Modify: `tools/rp2350_hid_bridge_cpp/README.md`
  - 在概览后提供详细接入指南入口。
- Create: `tools/rp2350_keymouse_bridge_firmware/sdk/python/INTEGRATION.md`
  - Python 应用层接入、uv 安装、VID/PID 自动发现、异常和上下文管理器生命周期。
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/README.md`
  - 在概览后提供详细接入指南入口。
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware/sdk/cpp`
  - 固件仓引用新增 C++ 指南后的 C++ SDK 提交。
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware/sdk/python`
  - 固件仓引用新增 Python 指南后的 Python SDK 提交。
- Update gitlink: `tools/rp2350_hid_bridge_cpp`
  - 父仓引用新增 C++ 指南后的 C++ SDK 提交。
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware`
  - 父仓引用包含两份新指南的固件仓提交。

### Task 1: 编写并发布 C++ SDK 接入指南

**Files:**
- Create: `tools/rp2350_hid_bridge_cpp/INTEGRATION.md`
- Modify: `tools/rp2350_hid_bridge_cpp/README.md`

- [ ] **Step 1: 确认 C++ SDK 工作树和公开 API 基线**

Run:

```powershell
git -C tools/rp2350_hid_bridge_cpp status --short --branch
git -C tools/rp2350_hid_bridge_cpp rev-parse HEAD
rg -n "struct HidBridgeOptions|class HidBridge|void (open|close|ping|type_text|key_tap|key_down|key_up|mouse_move|mouse_click|mouse_down|mouse_up|mouse_wheel|wait_ms|stop_all|run_script)|info\(\)|caps\(\)" tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge/serial.hpp
```

Expected: 工作树清洁，HEAD 为父仓当前 gitlink；API 扫描包含 `HidBridgeOptions`、连接方法、查询方法、所有键鼠方法和 `run_script()`。

- [ ] **Step 2: 创建 C++ 指南的结构和接入事实**

Create `tools/rp2350_hid_bridge_cpp/INTEGRATION.md` with these exact top-level sections in this order:

```markdown
# RP2350 HID 桥接器 C++ SDK 详细接入指南

## 1. 适用场景与安全提示
## 2. 工作原理与前置条件
## 3. 构建并接入 SDK
## 4. 查找并确认 COM 端口
## 5. 最小连通测试
## 6. 直接控制 API
## 7. 脚本批处理接入
## 8. 完整应用接入模板
## 9. 错误处理与恢复
## 10. 心跳、DTR、并发与会话生命周期
## 11. 正常退出与异常退出
## 12. 常见问题
## 13. 生产接入检查清单
```

Populate the sections with all of these concrete facts:

- SDK 是仅头文件 C++17 库；协议和解析器可移植，但默认真实串口传输使用 Win32 API。
- 板卡必须刷入协议 v2 固件，Windows 应看到 CDC COM 口和标准 HID 键盘/鼠标设备。
- 数据流写为 `应用程序 → C++ SDK → CDC 串口 → RP2350 固件 → USB HID 键盘/鼠标 → 操作系统`。
- `HidBridgeOptions` table must list `port`, `baud`, `timeout_ms`, `retries`, and `heartbeat_interval_ms`, with defaults `115200`, `1000`, `2`, and `500` where applicable.
- CMake instructions must show both `add_subdirectory()`/`target_link_libraries()` and manual `target_include_directories()`/`target_compile_features()` integration.
- Configure with `cmake -S . -B build`; do not force Visual Studio, Ninja, MSVC, or MinGW.
- COM discovery must use Windows Device Manager or `Get-CimInstance Win32_SerialPort`; the code must use an explicit `COMx` port.
- `TYPE_ASCII` supports US-keyboard ASCII, not Unicode or layout-independent text.
- One key combination supports modifiers plus at most one normal key; supported mouse buttons are `left`, `right`, and `middle`.
- Explain that `mouse_move()` accepts signed 16-bit deltas, `mouse_wheel()` accepts signed 8-bit deltas, and `wait_ms()` accepts non-negative 32-bit milliseconds.
- The script command table must list `type`, `key tap|down|up`, `mouse move`, `mouse click|down|up`, `mouse wheel`, `wait`, and `stop` with valid argument shapes.
- Explain script serialization, `stop` segment boundaries, and automatic `STOP_ALL` attempt after a script failure.
- The error matrix must distinguish `TimeoutError`, `std::invalid_argument`, and `std::runtime_error`, including port open failure, `BUSY` exhaustion, `NACK`, invalid input, and stale/closed sessions.
- Do not recommend infinite retry after unknown execution state. On final failure, close the old session, inspect the device, and reconnect only under explicit application policy.
- Explain the 500 ms heartbeat, two-second firmware lease, DTR assertion/deassertion, shared command lock, session generation, stale script rejection, and best-effort `STOP_ALL` during `close()`.
- State that destructor cleanup and `close()` cannot guarantee cleanup after abrupt process/OS failure; the firmware lease and DTR/USB reset provide the final safety boundary.

- [ ] **Step 3: Add the non-HID C++ connectivity example**

In section 5 include this complete example; it must not call any method that emits keyboard or mouse input:

```cpp
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

#include "rp2350_hid_bridge.hpp"

int main(int argc, char** argv) {
#ifdef _WIN32
    if (argc != 2) {
        std::cerr << "usage: bridge_probe COMx\n";
        return 2;
    }

    try {
        rp2350_hid_bridge::HidBridgeOptions options;
        options.port = argv[1];
        options.timeout_ms = 1000;
        options.retries = 2;

        rp2350_hid_bridge::HidBridge hid(options);
        hid.open();
        hid.ping();

        const auto print_bytes = [](const char* name, const auto& bytes) {
            std::cout << name << ':';
            for (const auto byte : bytes) {
                std::cout << ' ' << std::hex << std::setw(2)
                          << std::setfill('0') << static_cast<int>(byte);
            }
            std::cout << std::dec << '\n';
        };

        print_bytes("info", hid.info());
        print_bytes("caps", hid.caps());
        hid.close();
        return 0;
    } catch (const rp2350_hid_bridge::TimeoutError& exc) {
        std::cerr << "device timeout: " << exc.what() << '\n';
    } catch (const std::invalid_argument& exc) {
        std::cerr << "invalid option: " << exc.what() << '\n';
    } catch (const std::runtime_error& exc) {
        std::cerr << "bridge error: " << exc.what() << '\n';
    }
    return 1;
#else
    std::cerr << "the default serial transport currently requires Windows\n";
    return 3;
#endif
}
```

Document that the reader saves the source as `bridge_probe.cpp`, and place this complete `CMakeLists.txt` beside it when the SDK is stored under `third_party/rp2350_hid_bridge_cpp`:

```cmake
cmake_minimum_required(VERSION 3.20)
project(bridge_probe LANGUAGES CXX)

add_subdirectory(third_party/rp2350_hid_bridge_cpp)
add_executable(bridge_probe bridge_probe.cpp)
target_link_libraries(bridge_probe PRIVATE rp2350_hid_bridge)
```

Document the build/run commands from that application directory:

```powershell
cmake -S . -B build
cmake --build build --config Release
.\build\Release\bridge_probe.exe COM3
```

Clarify that `ping()`, `info()`, and `caps()` only query the bridge and do not generate HID reports.

- [ ] **Step 4: Add the explicitly armed C++ application template**

In section 8 include this complete `--run COMx` template. Its default path performs no device connection and no HID input, while every armed success/failure path attempts input release and closes the session:

```cpp
#include <iostream>
#include <stdexcept>
#include <string>

#include "rp2350_hid_bridge.hpp"

namespace {

void run_input(const std::string& port) {
    rp2350_hid_bridge::HidBridgeOptions options;
    options.port = port;
    options.timeout_ms = 1000;
    options.retries = 2;
    options.heartbeat_interval_ms = 500;

    rp2350_hid_bridge::HidBridge hid(options);
    hid.open();
    try {
        std::cout << "warning: real HID input is enabled; verify the active window\n";
        hid.mouse_move(20, 0);
        hid.mouse_click("left");
        hid.key_tap("ENTER");
        hid.type_text("hello from rp2350");
        hid.wait_ms(100);
        hid.stop_all();
        hid.close();
    } catch (...) {
        try {
            hid.stop_all();
        } catch (...) {
        }
        hid.close();
        throw;
    }
}

}  // namespace

int main(int argc, char** argv) {
#ifdef _WIN32
    if (argc != 3 || std::string(argv[1]) != "--run") {
        std::cout << "未启用真实输入。确认活动窗口安全后，使用 --run COMx。\n";
        return 0;
    }

    try {
        run_input(argv[2]);
        return 0;
    } catch (const rp2350_hid_bridge::TimeoutError& exc) {
        std::cerr << "设备响应超时：" << exc.what() << '\n';
    } catch (const std::invalid_argument& exc) {
        std::cerr << "参数错误：" << exc.what() << '\n';
    } catch (const std::runtime_error& exc) {
        std::cerr << "桥接器错误：" << exc.what() << '\n';
    }
    return 1;
#else
    std::cerr << "默认串口传输当前只支持 Windows。\n";
    return 3;
#endif
}
```

Explain that `--run` is an explicit arming condition, not a dry-run flag, and that the example deliberately returns before constructing `HidBridge` when it is absent.

- [ ] **Step 5: Add the C++ README entry**

Immediately after the two-paragraph introduction in `tools/rp2350_hid_bridge_cpp/README.md`, add:

```markdown
> 首次接入项目时，请阅读 [C++ SDK 详细接入指南](INTEGRATION.md)。指南包含安全的连通测试、完整应用模板、错误恢复和会话生命周期说明。
```

- [ ] **Step 6: Validate C++ documentation and examples**

Run:

```powershell
rg -n "^## [1-9]|^## 1[0-3]|--run COMx|TimeoutError|std::invalid_argument|std::runtime_error|heartbeat_interval_ms|STOP_ALL|两秒|DTR" tools/rp2350_hid_bridge_cpp/INTEGRATION.md
rg -n "INTEGRATION\.md" tools/rp2350_hid_bridge_cpp/README.md
git -C tools/rp2350_hid_bridge_cpp diff --check
cmake -S tools/rp2350_hid_bridge_cpp -B tools/rp2350_hid_bridge_cpp/build
cmake --build tools/rp2350_hid_bridge_cpp/build --config Release
ctest --test-dir tools/rp2350_hid_bridge_cpp/build -C Release --output-on-failure
```

Expected: all 13 sections and safety/lifecycle terms are found; README link resolves to the new file; `git diff --check` has no output; configure/build succeeds; CTest reports `100% tests passed`.

- [ ] **Step 7: Commit and push the C++ SDK**

Run:

```powershell
git -C tools/rp2350_hid_bridge_cpp add INTEGRATION.md README.md
git -C tools/rp2350_hid_bridge_cpp commit -m "docs: add detailed C++ SDK integration guide"
git -C tools/rp2350_hid_bridge_cpp push origin main
git -C tools/rp2350_hid_bridge_cpp status --short --branch
```

Expected: commit succeeds, `origin/main` advances, and the C++ SDK worktree is clean and synchronized.

### Task 2: 编写并发布 Python SDK 接入指南

**Files:**
- Create: `tools/rp2350_keymouse_bridge_firmware/sdk/python/INTEGRATION.md`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/README.md`

- [ ] **Step 1: 确认 Python SDK 工作树和公开 API 基线**

Run:

```powershell
git -C tools/rp2350_keymouse_bridge_firmware/sdk/python status --short --branch
git -C tools/rp2350_keymouse_bridge_firmware/sdk/python rev-parse HEAD
rg -n "HidBridge|HidBridgeOptions|find_port|list_ports|parse_combo|parse_script" tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/__init__.py
```

Expected: 工作树清洁；`__all__` 公开上述应用层入口。

- [ ] **Step 2: 创建 Python 指南的结构和接入事实**

Create `tools/rp2350_keymouse_bridge_firmware/sdk/python/INTEGRATION.md` with these exact top-level sections in this order:

```markdown
# RP2350 HID 桥接器 Python SDK 详细接入指南

## 1. 适用场景与安全提示
## 2. 工作原理与前置条件
## 3. 安装 SDK
## 4. 查找并确认串口
## 5. 最小连通测试
## 6. 直接控制 API
## 7. 脚本批处理接入
## 8. 完整应用接入模板
## 9. 错误处理与恢复
## 10. 心跳、DTR、并发与会话生命周期
## 11. 正常退出与异常退出
## 12. 常见问题
## 13. 生产接入检查清单
```

Populate the sections with all of these concrete facts:

- Python 3.10+ and `pyserial>=3.5` are required; real device examples use a Windows COM port.
- Standalone install uses `uv sync`; from the firmware repository use `uv sync --project sdk/python`.
- Data flow is `应用程序 → Python SDK → CDC 串口 → RP2350 固件 → USB HID 键盘/鼠标 → 操作系统`.
- `HidBridgeOptions` table lists `port`, `baudrate`, `timeout`, `retries`, `vid`, and `pid`, with defaults `None`, `115200`, `1.0`, `2`, `0xCAFE`, and `0x2350`.
- `port=None` calls `find_port()` with VID/PID; explicit `COM3` bypasses automatic selection; `list_ports()` is available for diagnostics.
- Direct-control, input range, ASCII, key-combination, mouse-button, script-boundary, serialization, and retry guidance must match Task 1.
- The error matrix distinguishes built-in `TimeoutError`, `ValueError`, `RuntimeError`, and pyserial/open failures. It covers missing port, occupied port, `BUSY` exhaustion, `NACK`, invalid arguments, and stale/closed sessions.
- Do not recommend blind infinite retries. After a final failure, exit the old context, inspect the device, and reconnect only under explicit application policy.
- Explain the heartbeat thread, shared locks, DTR, two-second firmware lease, context manager, lifecycle generation, stale script rejection, best-effort `STOP_ALL`, and refusal to open while an old heartbeat worker is still stopping.
- State that `with`/`close()` cannot guarantee cleanup after an abrupt process/OS failure; the firmware lease and DTR/USB reset are the final safety boundary.

- [ ] **Step 3: Add the non-HID Python connectivity example**

In section 5 include this complete example; it must only query the bridge:

```python
import argparse

from rp2350_hid_bridge import HidBridge, HidBridgeOptions


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 RP2350 HID 桥接器连接")
    parser.add_argument("--port", default=None, help="例如 COM3；省略时按 VID/PID 自动查找")
    args = parser.parse_args()

    try:
        options = HidBridgeOptions(port=args.port, timeout=1.0, retries=2)
        with HidBridge(options) as hid:
            hid.ping()
            print("info:", hid.info().hex(" "))
            print("caps:", hid.caps().hex(" "))
        return 0
    except TimeoutError as exc:
        print(f"设备响应超时：{exc}")
    except ValueError as exc:
        print(f"参数错误：{exc}")
    except RuntimeError as exc:
        print(f"桥接器错误：{exc}")
    except OSError as exc:
        print(f"串口错误：{exc}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Document both run modes:

```powershell
uv run python bridge_probe.py
uv run python bridge_probe.py --port COM3
```

Clarify that `ping()`, `info()`, and `caps()` do not generate HID input.

- [ ] **Step 4: Add the explicitly armed Python application template**

In section 8 include this complete `argparse` program with `--run` and optional `--port`. The default path prints a safety message and returns without creating `HidBridge`; the armed path releases input inside the context manager:

```python
import argparse

from rp2350_hid_bridge import HidBridge, HidBridgeOptions


def run_input(port: str | None) -> None:
    options = HidBridgeOptions(port=port, timeout=1.0, retries=2)
    with HidBridge(options) as hid:
        try:
            print("警告：真实 HID 输入已启用，请先确认当前活动窗口。")
            hid.mouse_move(20, 0)
            hid.mouse_click("left")
            hid.key_tap("ENTER")
            hid.type_text("hello from rp2350")
            hid.wait_ms(100)
        finally:
            try:
                hid.stop_all()
            except Exception as stop_exc:
                print(f"STOP_ALL 发送失败：{stop_exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="RP2350 HID 桥接器接入模板")
    parser.add_argument("--run", action="store_true", help="明确允许发送真实 HID 输入")
    parser.add_argument("--port", default=None, help="例如 COM3；省略时自动查找")
    args = parser.parse_args()

    if not args.run:
        print("未启用真实输入。确认活动窗口安全后，添加 --run。")
        return 0

    try:
        run_input(args.port)
        return 0
    except TimeoutError as exc:
        print(f"设备响应超时：{exc}")
    except ValueError as exc:
        print(f"参数错误：{exc}")
    except RuntimeError as exc:
        print(f"桥接器错误：{exc}")
    except OSError as exc:
        print(f"串口错误：{exc}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Explain that the inner `finally` runs before context-manager shutdown, so it can request `STOP_ALL` while the serial session is still open; `__exit__()` then performs its own best-effort stop and close.

- [ ] **Step 5: Add the Python README entry**

Immediately after the two-paragraph introduction in `tools/rp2350_keymouse_bridge_firmware/sdk/python/README.md`, add:

```markdown
> 首次接入项目时，请阅读 [Python SDK 详细接入指南](INTEGRATION.md)。指南包含自动发现、安全的连通测试、完整应用模板、错误恢复和会话生命周期说明。
```

- [ ] **Step 6: Validate Python documentation and SDK tests**

Run from `tools/rp2350_keymouse_bridge_firmware`:

```powershell
rg -n "^## [1-9]|^## 1[0-3]|--run|TimeoutError|ValueError|RuntimeError|CAFE|2350|STOP_ALL|两秒|DTR" sdk/python/INTEGRATION.md
rg -n "INTEGRATION\.md" sdk/python/README.md
git -C sdk/python diff --check
uv sync --project sdk/python
uv run --project sdk/python python -m unittest discover -s sdk/python/tests -v
```

Expected: all 13 sections and safety/lifecycle terms are found; README link resolves; `git diff --check` has no output; unittest prints `Ran 39 tests` and `OK`.

- [ ] **Step 7: Commit and push the Python SDK**

Run from `tools/rp2350_keymouse_bridge_firmware`:

```powershell
git -C sdk/python add INTEGRATION.md README.md
git -C sdk/python commit -m "docs: add detailed Python SDK integration guide"
git -C sdk/python push origin main
git -C sdk/python status --short --branch
```

Expected: commit succeeds, `origin/main` advances, and the Python SDK worktree is clean and synchronized.

### Task 3: 同步固件仓的两个 SDK 版本

**Files:**
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware/sdk/cpp`
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware/sdk/python`

- [ ] **Step 1: Fetch and update the firmware C++ SDK gitlink**

Run from `tools/rp2350_keymouse_bridge_firmware`:

```powershell
git submodule update --remote sdk/cpp
git submodule status sdk/cpp sdk/python
```

Expected: `sdk/cpp` points at the Task 1 commit on the C++ SDK `origin/main`; `sdk/python` points at the Task 2 commit already present in its worktree.

- [ ] **Step 2: Prove both C++ SDK locations resolve to the same commit**

Run from the parent repository:

```powershell
git -C tools/rp2350_hid_bridge_cpp rev-parse HEAD
git -C tools/rp2350_keymouse_bridge_firmware/sdk/cpp rev-parse HEAD
git -C tools/rp2350_keymouse_bridge_firmware/sdk/python rev-parse HEAD
```

Expected: the first two hashes are identical; the Python hash equals the Task 2 commit.

- [ ] **Step 3: Run the firmware repository's no-hardware CI-equivalent checks**

Run from `tools/rp2350_keymouse_bridge_firmware`:

```powershell
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
```

Expected: formatting and Clippy produce no errors; Rust, hidctl, WebUI, Python, and C++ SDK tests all pass; release firmware builds successfully without requiring attached hardware.

- [ ] **Step 4: Commit and push firmware gitlinks**

Run from the parent repository:

```powershell
git -C tools/rp2350_keymouse_bridge_firmware add sdk/cpp sdk/python
git -C tools/rp2350_keymouse_bridge_firmware commit -m "chore: update SDK integration guides"
git -C tools/rp2350_keymouse_bridge_firmware push origin main
git -C tools/rp2350_keymouse_bridge_firmware status --short --branch
```

Expected: firmware commit changes exactly the two SDK gitlinks, push succeeds, and the firmware worktree is clean.

- [ ] **Step 5: Verify firmware GitHub Actions**

Run:

```powershell
gh run list --repo ExquisiteCore/rp2350-keymouse-bridge-firmware --branch main --limit 1
$runId = gh run list --repo ExquisiteCore/rp2350-keymouse-bridge-firmware --branch main --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $runId --repo ExquisiteCore/rp2350-keymouse-bridge-firmware --exit-status
```

Expected: the workflow for the Task 3 firmware commit completes successfully.

### Task 4: 同步父仓并完成递归验证

**Files:**
- Update gitlink: `tools/rp2350_hid_bridge_cpp`
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware`

- [ ] **Step 1: Inspect the exact parent gitlink changes**

Run from the parent repository:

```powershell
git status --short
git diff --submodule=log -- tools/rp2350_hid_bridge_cpp tools/rp2350_keymouse_bridge_firmware
```

Expected: only the direct C++ SDK gitlink and firmware gitlink are changed; the previously committed design and plan files are not modified.

- [ ] **Step 2: Verify recursive submodule consistency and document links**

Run:

```powershell
git submodule status --recursive
Test-Path tools/rp2350_hid_bridge_cpp/INTEGRATION.md
Test-Path tools/rp2350_keymouse_bridge_firmware/sdk/cpp/INTEGRATION.md
Test-Path tools/rp2350_keymouse_bridge_firmware/sdk/python/INTEGRATION.md
git -C tools/rp2350_hid_bridge_cpp rev-parse HEAD
git -C tools/rp2350_keymouse_bridge_firmware/sdk/cpp rev-parse HEAD
```

Expected: all three `Test-Path` calls print `True`; no recursive submodule line starts with `-`, `+`, or `U`; both C++ hashes match.

- [ ] **Step 3: Run final Markdown and parent tests**

Run:

```powershell
git diff --check
uv run --extra dev pytest
```

Expected: `git diff --check` has no output and the complete parent Python test suite passes.

- [ ] **Step 4: Commit and push the parent gitlinks**

Run:

```powershell
git add tools/rp2350_hid_bridge_cpp tools/rp2350_keymouse_bridge_firmware
git commit -m "chore: update RP2350 SDK integration guides"
git push origin main
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
```

Expected: push succeeds; the parent worktree is clean; ahead/behind is `0 0`.

- [ ] **Step 5: Perform the final remote and content audit**

Run:

```powershell
git ls-tree HEAD tools/rp2350_hid_bridge_cpp tools/rp2350_keymouse_bridge_firmware
git -C tools/rp2350_keymouse_bridge_firmware ls-tree HEAD sdk/cpp sdk/python
rg -n "详细接入指南" tools/rp2350_hid_bridge_cpp/README.md tools/rp2350_keymouse_bridge_firmware/sdk/python/README.md
rg -n "TBD|TODO|待定|稍后补充|implement later|fill in details" tools/rp2350_hid_bridge_cpp/INTEGRATION.md tools/rp2350_keymouse_bridge_firmware/sdk/python/INTEGRATION.md
```

Expected: all four gitlinks resolve to the commits produced in Tasks 1-3; both README links are found; placeholder scan returns no matches.

## Self-Review

- Spec coverage: Tasks 1 and 2 cover both independent SDK guides, safe probes, explicit `--run` templates, installation/build, discovery, direct APIs, scripts, failure recovery, heartbeat/DTR/concurrency/session lifecycle, shutdown, troubleshooting, and production checklists.
- Repository consistency: Tasks 3 and 4 update the nested and parent gitlinks in dependency order and explicitly compare the two C++ SDK hashes.
- Safety: Neither connectivity example emits HID reports; both full templates require explicit arming and attempt `STOP_ALL` on success and failure.
- Scope: No step adds protocol-frame tutorials, custom transports, firmware implementation guidance, GUI integration, model inference, or vision-runtime integration.
- Placeholder scan: The implementation instructions contain no deferred content markers; each modified file, command, expected result, API name, and example cleanup path is specified.
- Type consistency: C++ uses `baud`, `timeout_ms`, `heartbeat_interval_ms`, signed `int16_t` mouse movement, and signed `int8_t` wheel values; Python uses `baudrate`, `timeout`, `vid`, and `pid`; exception names match the current SDK implementations.
