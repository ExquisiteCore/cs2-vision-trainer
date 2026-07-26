# Shared Native HID Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Python 调用端和 `vision_runtime.dll` 共享一个由 `rp2350_hid_bridge.dll` 拥有的原生 `HidSession`，同一 COM 口只打开一次，并保证视觉撤销输出不会释放调用端保持的键盘状态。

**Architecture:** `rp2350-hid-bridge-cpp` 从 header-only 生产实现升级为带稳定 C ABI 的共享库，唯一管理串口、心跳、序列号、请求/响应锁和引用计数。`rp2350-hid-bridge-python` 变为该 DLL 的 `ctypes` 包装；`vision_runtime.dll` 通过 `va_attach_hid_session` retain 同一个不透明句柄。父仓 Python SDK 负责 app-local 路径/哈希/ABI 校验、重导出 `HidSession` 和调用端友好 API。

**Tech Stack:** C++17、Win32 Serial/SetupAPI、C ABI、CMake、xmake、Python 3.11+、ctypes、uv、pytest/unittest、PowerShell、Rust RP2350 firmware tests。

---

## Execution topology

实施开始时先使用 `superpowers:using-git-worktrees`。父仓及三个会产生提交的子仓分别使用隔离 feature branch；不要直接在当前 `main` 工作树修改实现：

```text
cs2-vision-trainer                       feature/shared-hid-session-host
tools/cpp_analyzer                       feature/shared-hid-session-runtime
tools/rp2350_hid_bridge_cpp              feature/shared-hid-session-native
tools/rp2350_keymouse_bridge_firmware/
  sdk/python                             feature/shared-hid-session-python
tools/rp2350_keymouse_bridge_firmware    feature/shared-hid-session-firmware-links
```

同一个 C++ SDK提交必须同时成为父仓 `tools/rp2350_hid_bridge_cpp` 和固件仓 `sdk/cpp` 的 gitlink。Python HID SDK提交由固件仓 `sdk/python` gitlink固定。所有子仓提交推送后，才能提交上一级 gitlink。

## File and responsibility map

### Native HID SDK repository

- Create `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge/c_api.h`: stable exported C ABI, ABI info, opaque handle and command declarations.
- Create `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge/client.hpp`: public C++ RAII `HidSession` and compatibility `HidBridge` name.
- Create `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge/port_discovery.hpp`: testable Windows COM discovery parsing contract.
- Create `tools/rp2350_hid_bridge_cpp/src/c_api.cpp`: opaque handle, reference count, error translation and command forwarding.
- Create `tools/rp2350_hid_bridge_cpp/src/session_state.hpp`: internal reference/fault state and test-only transport injection.
- Create `tools/rp2350_hid_bridge_cpp/src/client.cpp`: C++ wrapper around the C ABI.
- Create `tools/rp2350_hid_bridge_cpp/src/port_discovery.cpp`: SetupAPI enumeration and VID/PID matching.
- Modify `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge/serial.hpp`: keep the proven transport state machine as internal `detail::HidBridgeCore`.
- Modify `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge.hpp`: expose C API and public client instead of the internal core.
- Create `tools/rp2350_hid_bridge_cpp/tests/test_c_api.cpp`: ABI, references, last-release shutdown and command forwarding.
- Create `tools/rp2350_hid_bridge_cpp/tests/fake_transport.hpp`: existing deterministic transport shared by core and C ABI tests.
- Modify `tools/rp2350_hid_bridge_cpp/tests/test_protocol.cpp`: test `detail::HidBridgeCore` directly.
- Modify `tools/rp2350_hid_bridge_cpp/CMakeLists.txt`: build `rp2350_hid_bridge.dll`, import library, tests and examples.

### Python HID SDK repository

- Create `tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/native.py`: app-local DLL discovery, ABI validation and ctypes signatures.
- Create `tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/_version.py`: public Python HID SDK version.
- Rewrite `tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/client.py`: `HidSession` lifecycle and compatibility `HidBridge` wrapper.
- Modify `tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/__init__.py`: export `HidSession`.
- Modify `tools/rp2350_keymouse_bridge_firmware/sdk/python/pyproject.toml`: version `0.2.0`, remove pyserial.
- Replace serial-state tests in `tools/rp2350_keymouse_bridge_firmware/sdk/python/tests/test_sdk.py` with native-wrapper tests; retain pure protocol/key/script tests.

### Vision runtime repository

- Modify `tools/cpp_analyzer/include/vision_analyzer/vision_runtime_c_api.h`: ABI `2.1`, shared-session feature bit and attach function.
- Modify `tools/cpp_analyzer/include/vision_analyzer/types.hpp`: optional attached native session pointer.
- Modify `tools/cpp_analyzer/include/vision_analyzer/hid_output.hpp` and `src/hid_output.cpp`: shared/private client factories and reference ownership.
- Modify `tools/cpp_analyzer/include/vision_analyzer/runtime_session.hpp` and `src/runtime_session.cpp`: use the configured shared session without global stop during close.
- Modify `tools/cpp_analyzer/src/calibration.cpp`: use the attached session and avoid shared `STOP_ALL` cleanup.
- Modify `tools/cpp_analyzer/src/vision_runtime_c_api.cpp`: retain/detach rules, port/session mutual exclusion and legacy emergency-stop rule.
- Modify `tools/cpp_analyzer/CMakeLists.txt` and `xmake.lua`: build/link the HID shared library instead of compiling an independent header-only client.
- Modify `tools/cpp_analyzer/tests/test_algorithms.cpp` and `tests/test_c_api.cpp`: safety semantics and ABI tests.

### Parent Python SDK and packaging

- Modify `src/cs2_vision_runtime/runtime.py`: attach bindings, `from_app_dir(app_dir, data_dir=data_dir, hid_session=hid)`, conflict checks and no global stop in `armed_output`.
- Modify `src/cs2_vision_runtime/package.py`: manifest v2 and HID DLL verification.
- Modify `src/cs2_vision_runtime/__init__.py`: re-export `HidSession`.
- Modify `src/cs2_vision_runtime/_version.py`: version `0.3.0`.
- Modify `packaging/python-runtime-sdk/pyproject.toml`, root `pyproject.toml`, `uv.lock` and `scripts/build_python_runtime_sdk.ps1`: first-party dependency and two-wheel build.
- Modify `tools/cpp_analyzer/packaging/sm61/build-portable-package.ps1`, `build-app-local-package.ps1`, `PackageTools.psm1` and `packaging/sm61/tests/run-tests.ps1`: package and verify both DLLs.
- Modify `tests/test_vision_runtime_sdk.py`, `test_runtime_package.py`, `test_runtime_sdk_distribution.py` and `test_runtime_sdk_docs.py`.
- Modify `examples/runtime_live_move.py`, `examples/runtime_app_local.py`, `docs/PYTHON_RUNTIME_SDK_INTEGRATION.md`, `docs/BUILD.md` and `docs/USAGE.md`.

## Stable interface decisions

Use these names consistently in every task:

```text
Native DLL              rp2350_hid_bridge.dll
Native handle           Rp2350HidSession*
Native ABI              1.0
Python HID class        HidSession
Python HID version      0.2.0
Vision attach export    va_attach_hid_session
Vision feature bit      VA_RUNTIME_FEATURE_SHARED_HID_SESSION = 1 << 4
Vision ABI              2.1
Vision Python version   0.3.0
Manifest version        2
Required vision flags   31
```

The app-local manifest shape is fixed as:

```json
{
  "manifest_version": 2,
  "python_sdk": {"minimum": "0.3.0", "recommended": "0.3.0"},
  "dll": {
    "file_name": "vision_runtime.dll",
    "abi_major": 2,
    "abi_minor": 1,
    "required_features": 31
  },
  "hid_bridge": {
    "dll": {
      "file_name": "rp2350_hid_bridge.dll",
      "sha256": "0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF",
      "abi_major": 1,
      "abi_minor": 0
    },
    "python_sdk": {"minimum": "0.2.0", "recommended": "0.2.0"}
  }
}
```

The value shown for `sha256` documents format only; the packaging script always writes the computed hash and tests compare it with `Get-FileSha256`.

## Spec coverage audit

| Approved requirement | Implemented and verified by |
|---|---|
| One COM, one native `HidSession`, one heartbeat/sequence reader | Tasks 1-5 and native concurrency tests |
| Python keyboard and vision mouse share one handle | Tasks 6-9 and Task 14 hardware acceptance |
| Disarm/reset/calibration do not release held keys | Tasks 7-8, 12 and 14 |
| Explicit global stop and final safety release remain | Tasks 2, 5, 7 and 14 |
| `process_next()` remains synchronous while another Python thread can use HID | Tasks 2, 5, 12 and 14 |
| Two app-local DLLs, hashes and coordinated ABI versions | Tasks 9-11 and 13 |
| No pyserial transport implementation | Tasks 4-5 and wheel tests in Task 10 |
| Faulted sessions stop accepting commands; no automatic reconnect | Tasks 2, 4-5 and error documentation in Task 12 |
| Firmware two-second control lease remains the crash fallback | Tasks 5, 12-14; firmware code is unchanged |
| Legacy private `hid_port` remains supported but cannot mix with attachment | Tasks 6-8 and migration documentation in Task 12 |

### Task 1: Isolate the proven transport as the internal native core

**Files:**
- Modify: `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge/serial.hpp:31-715`
- Modify: `tools/rp2350_hid_bridge_cpp/tests/test_protocol.cpp:16-891`
- Create: `tools/rp2350_hid_bridge_cpp/tests/fake_transport.hpp`
- Modify: `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge.hpp`

- [ ] **Step 1: Change the protocol test to name the intended internal core**

After `using namespace rp2350_hid_bridge;`, add:

```cpp
using TestHidBridge = rp2350_hid_bridge::detail::HidBridgeCore;
```

Also replace the umbrella include with `#include "rp2350_hid_bridge/serial.hpp"`. Replace test-only constructions of `HidBridge` with `TestHidBridge`. Do not change test behavior or `FakeTransport`.

Move the existing `FakeTransport` class and its required `response_frame` helper unchanged into `tests/fake_transport.hpp` under namespace `rp2350_hid_bridge::testing`; include that header from `test_protocol.cpp`. This is a code move only and makes the same deterministic transport available to Task 2.

- [ ] **Step 2: Run the C++ test build and verify the new name fails**

Run from `tools/rp2350_hid_bridge_cpp`:

```powershell
cmake -S . -B build-shared-plan -A x64
cmake --build build-shared-plan --config Release
```

Expected: compilation fails because `rp2350_hid_bridge::detail::HidBridgeCore` does not exist.

- [ ] **Step 3: Rename the implementation without changing protocol behavior**

In `serial.hpp`, keep `TimeoutError`, `SerialTransport`, `Win32SerialTransport` and `HidBridgeOptions` in `rp2350_hid_bridge`. Wrap only the current production class in `namespace detail` and rename it exactly:

```cpp
namespace detail {

class HidBridgeCore {
public:
    explicit HidBridgeCore(
        HidBridgeOptions options,
        std::shared_ptr<SerialTransport> transport = nullptr);

    explicit HidBridgeCore(
        std::string port,
        std::uint32_t baud = 115200,
        std::uint32_t timeout_ms = 1000,
        int retries = 2);

    HidBridgeCore(const HidBridgeCore&) = delete;
    HidBridgeCore& operator=(const HidBridgeCore&) = delete;
    ~HidBridgeCore() { close(); }

    [[nodiscard]] bool is_open() const {
        std::lock_guard<std::mutex> state_lock(state_mutex_);
        return opened_ && !closing_;
    }
};

}  // namespace detail
```

Rename all constructor/destructor references and `ActiveCommandGuard` owner types inside the existing class. Preserve the existing method bodies byte-for-byte apart from the class name and namespace.

- [ ] **Step 4: Stop exposing the internal serial header from the umbrella header**

For this task, remove only this line from `include/rp2350_hid_bridge.hpp`:

```cpp
#include "rp2350_hid_bridge/serial.hpp"
```

The public client is added in Task 3. Tests include `rp2350_hid_bridge/serial.hpp` directly.

- [ ] **Step 5: Run the existing native tests**

```powershell
cmake --build build-shared-plan --config Release
ctest --test-dir build-shared-plan -C Release --output-on-failure
```

Expected: existing protocol test passes with the same final line `C++ SDK protocol v2 tests passed`.

- [ ] **Step 6: Commit the behavior-preserving split**

```powershell
git add include/rp2350_hid_bridge/serial.hpp include/rp2350_hid_bridge.hpp tests/fake_transport.hpp tests/test_protocol.cpp
git commit -m "refactor: isolate native HID session core"
```

### Task 2: Add the stable C ABI and reference-counted session handle

**Files:**
- Create: `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge/c_api.h`
- Create: `tools/rp2350_hid_bridge_cpp/src/c_api.cpp`
- Create: `tools/rp2350_hid_bridge_cpp/src/session_state.hpp`
- Create: `tools/rp2350_hid_bridge_cpp/tests/test_c_api.cpp`
- Modify: `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge/serial.hpp`
- Modify: `tools/rp2350_hid_bridge_cpp/CMakeLists.txt`

- [ ] **Step 1: Write failing ABI and reference-lifecycle tests**

Create `tests/test_c_api.cpp` using the repository's existing `CHECK` macro style. The first tests must contain these assertions:

```cpp
static_assert(sizeof(Rp2350HidAbiInfo) == 24);
static_assert(sizeof(Rp2350HidOptions) == 32);

void test_abi_info() {
    CHECK(rp2350_hid_get_abi_info(nullptr) == RP2350_HID_STATUS_ERROR);
    Rp2350HidAbiInfo info{};
    info.struct_size = sizeof(info);
    CHECK(rp2350_hid_get_abi_info(&info) == RP2350_HID_STATUS_OK);
    CHECK(info.abi_major == 1);
    CHECK(info.abi_minor == 0);
    CHECK(info.options_size == sizeof(Rp2350HidOptions));
    CHECK((info.feature_flags & RP2350_HID_FEATURE_SHARED_SESSION) != 0);
}

void test_unopened_session_can_be_retained_and_released() {
    Rp2350HidOptions options{};
    options.struct_size = sizeof(options);
    options.port = "COM_TEST";
    options.baud = 115200;
    options.timeout_ms = 1000;
    options.retries = 2;
    options.heartbeat_interval_ms = 500;

    Rp2350HidSession* session = nullptr;
    CHECK(rp2350_hid_session_create(&options, &session) == RP2350_HID_STATUS_OK);
    CHECK(session != nullptr);
    CHECK(rp2350_hid_session_retain(session) == RP2350_HID_STATUS_OK);
    rp2350_hid_session_release(session);
    rp2350_hid_session_release(session);
}
```

Include `../src/session_state.hpp` and `fake_transport.hpp`. Add a test-created session using `detail::make_test_session(options, transport)`: open it with auto ACK enabled, retain it, release once and assert the transport is still open; release the final reference and assert one `StopAllWritten`, DTR history `{true, false}` and a closed transport.

Add a fault test: configure `FakeTransport::fail_next_write()` to throw `TransportError`, call `session_ping`, assert status `ERROR`, assert `detail::session_faulted(session)` is true, then call ping again and assert no second transport write occurred and the error contains `faulted`.

- [ ] **Step 2: Register the new test before implementation**

Add a `test_c_api` target to `CMakeLists.txt` that includes the public include directory and links `Threads::Threads`. Do not add `src/c_api.cpp` yet.

- [ ] **Step 3: Verify the test fails because the C API is missing**

```powershell
cmake -S . -B build-shared-plan -A x64
cmake --build build-shared-plan --config Release
```

Expected: compilation fails because `rp2350_hid_bridge/c_api.h` and its symbols do not exist.

- [ ] **Step 4: Create the complete public C ABI header**

Create `include/rp2350_hid_bridge/c_api.h` with this exported surface:

```c
#pragma once

#include <stdint.h>

#if defined(_WIN32) && defined(RP2350_HID_BRIDGE_BUILD_DLL)
#define RP2350_HID_API __declspec(dllexport)
#elif defined(_WIN32)
#define RP2350_HID_API __declspec(dllimport)
#else
#define RP2350_HID_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define RP2350_HID_ABI_MAJOR 1u
#define RP2350_HID_ABI_MINOR 0u
#define RP2350_HID_FEATURE_SHARED_SESSION UINT64_C(1)
#define RP2350_HID_FEATURE_PORT_DISCOVERY (UINT64_C(1) << 1)

typedef struct Rp2350HidSession Rp2350HidSession;

typedef enum Rp2350HidStatus {
    RP2350_HID_STATUS_TIMEOUT = -2,
    RP2350_HID_STATUS_ERROR = -1,
    RP2350_HID_STATUS_OK = 0,
    RP2350_HID_STATUS_FOUND = 1
} Rp2350HidStatus;

typedef struct Rp2350HidAbiInfo {
    uint32_t struct_size;
    uint32_t abi_major;
    uint32_t abi_minor;
    uint32_t options_size;
    uint64_t feature_flags;
} Rp2350HidAbiInfo;

typedef struct Rp2350HidOptions {
    uint32_t struct_size;
    const char* port;
    uint32_t baud;
    uint32_t timeout_ms;
    int32_t retries;
    uint32_t heartbeat_interval_ms;
} Rp2350HidOptions;

RP2350_HID_API int32_t rp2350_hid_get_abi_info(Rp2350HidAbiInfo* info);
RP2350_HID_API const char* rp2350_hid_last_error(void);
RP2350_HID_API int32_t rp2350_hid_find_port(
    uint16_t vid,
    uint16_t pid,
    char* output,
    uint32_t output_size
);

RP2350_HID_API int32_t rp2350_hid_session_create(
    const Rp2350HidOptions* options,
    Rp2350HidSession** session
);
RP2350_HID_API int32_t rp2350_hid_session_retain(Rp2350HidSession* session);
RP2350_HID_API void rp2350_hid_session_release(Rp2350HidSession* session);
RP2350_HID_API int32_t rp2350_hid_session_open(Rp2350HidSession* session);
RP2350_HID_API int32_t rp2350_hid_session_is_open(
    Rp2350HidSession* session,
    int32_t* is_open
);
RP2350_HID_API int32_t rp2350_hid_session_ping(Rp2350HidSession* session);
RP2350_HID_API int32_t rp2350_hid_session_info(
    Rp2350HidSession* session,
    uint8_t* output,
    uint32_t output_size,
    uint32_t* bytes_written
);
RP2350_HID_API int32_t rp2350_hid_session_caps(
    Rp2350HidSession* session,
    uint8_t* output,
    uint32_t output_size,
    uint32_t* bytes_written
);
RP2350_HID_API int32_t rp2350_hid_session_type_text(
    Rp2350HidSession* session,
    const char* text
);
RP2350_HID_API int32_t rp2350_hid_session_key_tap(
    Rp2350HidSession* session,
    const char* combo
);
RP2350_HID_API int32_t rp2350_hid_session_key_down(
    Rp2350HidSession* session,
    const char* combo
);
RP2350_HID_API int32_t rp2350_hid_session_key_up(
    Rp2350HidSession* session,
    const char* combo
);
RP2350_HID_API int32_t rp2350_hid_session_mouse_move(
    Rp2350HidSession* session,
    int16_t dx,
    int16_t dy
);
RP2350_HID_API int32_t rp2350_hid_session_mouse_click(
    Rp2350HidSession* session,
    const char* button
);
RP2350_HID_API int32_t rp2350_hid_session_mouse_down(
    Rp2350HidSession* session,
    const char* button
);
RP2350_HID_API int32_t rp2350_hid_session_mouse_up(
    Rp2350HidSession* session,
    const char* button
);
RP2350_HID_API int32_t rp2350_hid_session_mouse_wheel(
    Rp2350HidSession* session,
    int8_t delta
);
RP2350_HID_API int32_t rp2350_hid_session_wait_ms(
    Rp2350HidSession* session,
    uint32_t milliseconds
);
RP2350_HID_API int32_t rp2350_hid_session_stop_all(Rp2350HidSession* session);
RP2350_HID_API int32_t rp2350_hid_session_run_script(
    Rp2350HidSession* session,
    const char* script
);

#ifdef __cplusplus
}
#endif
```

For Task 2, define `rp2350_hid_find_port` as a temporary function that returns `RP2350_HID_STATUS_ERROR` with `port discovery is not available in this build`; advertise only `RP2350_HID_FEATURE_SHARED_SESSION` from `rp2350_hid_get_abi_info`. Task 3 replaces the temporary body and then advertises both features.

- [ ] **Step 5: Implement the opaque session and exception boundary**

Define the handle in private `src/session_state.hpp`; `src/c_api.cpp` and test-only builds include it, but no installed public header does:

```cpp
struct Rp2350HidSession {
    std::atomic<std::uint32_t> references{1};
    std::atomic_bool faulted{false};
    rp2350_hid_bridge::detail::HidBridgeCore core;

    explicit Rp2350HidSession(rp2350_hid_bridge::HidBridgeOptions options)
        : core(std::move(options)) {}
};

namespace {
thread_local std::string last_error;

template <typename Function>
int32_t call_api(Function&& function) noexcept {
    try {
        last_error.clear();
        function();
        return RP2350_HID_STATUS_OK;
    } catch (const rp2350_hid_bridge::TimeoutError& error) {
        last_error = error.what();
        return RP2350_HID_STATUS_TIMEOUT;
    } catch (const std::exception& error) {
        last_error = error.what();
        return RP2350_HID_STATUS_ERROR;
    } catch (...) {
        last_error = "unknown RP2350 HID error";
        return RP2350_HID_STATUS_ERROR;
    }
}

Rp2350HidSession& require_session(Rp2350HidSession* session) {
    if (session == nullptr) {
        throw std::runtime_error("HID session handle is null");
    }
    return *session;
}

template <typename Function>
int32_t call_session(Rp2350HidSession* session, Function&& function) noexcept {
    return call_api([&] {
        Rp2350HidSession& value = require_session(session);
        if (value.faulted.load(std::memory_order_acquire)) {
            throw std::runtime_error("HID session is faulted");
        }
        try {
            function(value.core);
        } catch (const rp2350_hid_bridge::TimeoutError&) {
            value.faulted.store(true, std::memory_order_release);
            value.core.close();
            throw;
        } catch (const rp2350_hid_bridge::TransportError&) {
            value.faulted.store(true, std::memory_order_release);
            value.core.close();
            throw;
        }
    });
}
}  // namespace
```

Validate `struct_size`, non-empty port, positive baud/timeout/heartbeat and nonnegative retries in `rp2350_hid_session_create`. `retain` uses `fetch_add(1, std::memory_order_relaxed)`. `release` uses `fetch_sub(1, std::memory_order_acq_rel)` and deletes only when the previous value is `1`; the `HidBridgeCore` destructor performs the existing best-effort stop/heartbeat/DTR/close sequence.

Declare `TransportError : public std::runtime_error` beside `TimeoutError` and use it for Win32 open/configure/DTR/read/write failures. In `session_state.hpp`, provide `make_test_session(options, shared_ptr<SerialTransport>)` and `session_faulted` inside `rp2350_hid_bridge::detail`; production `c_api.cpp` uses the same handle type but never exposes those helpers through the C export table.

Before each command, reject an already faulted session. When `call_session` catches `TimeoutError` or `TransportError`, atomically set `faulted`, call `core.close()` and preserve the original message. Input-validation errors and device NACKs remain ordinary command errors and do not fault a healthy session. There is no automatic reconnect; a caller creates a new `HidSession`.

- [ ] **Step 6: Implement every command as one exact core forwarding call**

Use this mapping and the `call_session` helper; no command may implement protocol framing in `c_api.cpp`:

```text
session_open         core.open()
session_is_open      core.is_open()
session_ping         core.ping()
session_info         core.info()
session_caps         core.caps()
session_type_text    core.type_text(text)
session_key_tap      core.key_tap(combo)
session_key_down     core.key_down(combo)
session_key_up       core.key_up(combo)
session_mouse_move   core.mouse_move(dx, dy)
session_mouse_click  core.mouse_click(button)
session_mouse_down   core.mouse_down(button)
session_mouse_up     core.mouse_up(button)
session_mouse_wheel  core.mouse_wheel(delta)
session_wait_ms      core.wait_ms(milliseconds)
session_stop_all     core.stop_all()
session_run_script   core.run_script(script)
```

For `info` and `caps`, require non-null `bytes_written`, copy only when `output_size >= payload.size()`, and return an error containing `output buffer is too small` otherwise.

- [ ] **Step 7: Build the shared library target**

Change `CMakeLists.txt` so `rp2350_hid_bridge` is a shared target:

```cmake
add_library(rp2350_hid_bridge SHARED
    src/c_api.cpp
    src/port_discovery.cpp
)
target_compile_definitions(rp2350_hid_bridge PRIVATE RP2350_HID_BRIDGE_BUILD_DLL)
target_include_directories(rp2350_hid_bridge PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_features(rp2350_hid_bridge PUBLIC cxx_std_17)
target_link_libraries(rp2350_hid_bridge PRIVATE Threads::Threads)
if(WIN32)
    target_link_libraries(rp2350_hid_bridge PRIVATE setupapi)
endif()
```

Compile `test_c_api` with its own `src/c_api.cpp` translation unit and private `RP2350_HID_BRIDGE_TESTING` definition so it can use `session_state.hpp` test helpers without exporting them from the production DLL. Keep a separate small DLL-link smoke assertion in `basic_example`/CTest that calls `rp2350_hid_get_abi_info`; this verifies the import library and actual DLL export table.

Temporarily create an empty `src/port_discovery.cpp` containing only `#include "rp2350_hid_bridge/port_discovery.hpp"` after the header is added in Task 3; until then omit that source from the target. Link `test_c_api`, examples and future C++ client against the shared target.

- [ ] **Step 8: Run ABI tests and inspect exports**

```powershell
cmake -S . -B build-shared-plan -A x64
cmake --build build-shared-plan --config Release
ctest --test-dir build-shared-plan -C Release --output-on-failure
dumpbin /exports build-shared-plan\Release\rp2350_hid_bridge.dll | Select-String 'rp2350_hid_'
```

Expected: tests pass; export output includes `rp2350_hid_get_abi_info`, `rp2350_hid_session_retain`, `rp2350_hid_session_release`, keyboard, mouse and stop functions.

- [ ] **Step 9: Commit the native ABI**

```powershell
git add CMakeLists.txt include/rp2350_hid_bridge/c_api.h include/rp2350_hid_bridge/serial.hpp src/c_api.cpp src/session_state.hpp tests/test_c_api.cpp
git commit -m "feat: expose reference-counted HID C ABI"
```

### Task 3: Add native port discovery and the public C++ RAII client

**Files:**
- Create: `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge/port_discovery.hpp`
- Create: `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge/client.hpp`
- Create: `tools/rp2350_hid_bridge_cpp/src/port_discovery.cpp`
- Create: `tools/rp2350_hid_bridge_cpp/src/client.cpp`
- Modify: `tools/rp2350_hid_bridge_cpp/include/rp2350_hid_bridge.hpp`
- Modify: `tools/rp2350_hid_bridge_cpp/CMakeLists.txt`
- Modify: `tools/rp2350_hid_bridge_cpp/tests/test_c_api.cpp`
- Modify: `tools/rp2350_hid_bridge_cpp/README.md`
- Modify: `tools/rp2350_hid_bridge_cpp/INTEGRATION.md`

- [ ] **Step 1: Add failing parser and C++ wrapper tests**

Add pure parser assertions to `tests/test_c_api.cpp`:

```cpp
CHECK(rp2350_hid_bridge::detail::matches_usb_vid_pid(
    "USB\\VID_CAFE&PID_2350\\ABC", 0xCAFE, 0x2350));
CHECK(!rp2350_hid_bridge::detail::matches_usb_vid_pid(
    "USB\\VID_CAFE&PID_9999\\ABC", 0xCAFE, 0x2350));
CHECK(rp2350_hid_bridge::detail::extract_com_port(
    "USB Serial Device (COM4)") == "COM4");
CHECK(rp2350_hid_bridge::detail::extract_com_port(
    "No serial suffix").empty());
```

Add a compile/lifecycle test that constructs `HidSession` with `HidBridgeOptions`, verifies `is_open()` is false, calls `close()` twice, and constructs the compatibility name `HidBridge`.

- [ ] **Step 2: Verify parser/client symbols are missing**

```powershell
cmake --build build-shared-plan --config Release
```

Expected: compilation fails because `port_discovery.hpp`, `HidSession` and compatibility `HidBridge` do not exist.

- [ ] **Step 3: Implement testable SetupAPI parsing**

Create `port_discovery.hpp` with:

```cpp
#pragma once

#include <cstdint>
#include <string>

namespace rp2350_hid_bridge::detail {
[[nodiscard]] bool matches_usb_vid_pid(
    const std::string& instance_id,
    std::uint16_t vid,
    std::uint16_t pid
);
[[nodiscard]] std::string extract_com_port(const std::string& friendly_name);
[[nodiscard]] std::string find_windows_com_port(std::uint16_t vid, std::uint16_t pid);
}  // namespace rp2350_hid_bridge::detail
```

`matches_usb_vid_pid` uppercases the instance ID and compares fixed four-digit `VID_%04X` and `PID_%04X` tokens. `extract_com_port` accepts a final parenthesized `COM` followed only by digits. `find_windows_com_port` enumerates `GUID_DEVINTERFACE_COMPORT` through SetupAPI, obtains instance ID and friendly name, returns the first matching port, and returns an empty string when none match. Non-Windows builds return an empty string.

Connect `rp2350_hid_find_port` to this function: return `FOUND` after copying the NUL-terminated name, `OK` when no device matches, and `ERROR` when the output buffer is null/too small.

- [ ] **Step 4: Define the public C++ client without exposing implementation state**

Create `client.hpp` with this class declaration:

```cpp
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "rp2350_hid_bridge/c_api.h"
#include "rp2350_hid_bridge/serial.hpp"

namespace rp2350_hid_bridge {

class RP2350_HID_API HidSession {
public:
    explicit HidSession(HidBridgeOptions options);
    explicit HidSession(
        std::string port,
        std::uint32_t baud = 115200,
        std::uint32_t timeout_ms = 1000,
        int retries = 2);
    ~HidSession();

    HidSession(const HidSession&) = delete;
    HidSession& operator=(const HidSession&) = delete;
    HidSession(HidSession&& other) noexcept;
    HidSession& operator=(HidSession&& other) noexcept;

    void open();
    void close() noexcept;
    [[nodiscard]] bool is_open() const;
    void ping();
    [[nodiscard]] std::vector<std::uint8_t> info();
    [[nodiscard]] std::vector<std::uint8_t> caps();
    void type_text(const std::string& text);
    void key_tap(const std::string& combo);
    void key_down(const std::string& combo);
    void key_up(const std::string& combo);
    void mouse_move(std::int16_t dx, std::int16_t dy);
    void mouse_click(const std::string& button = "left");
    void mouse_down(const std::string& button = "left");
    void mouse_up(const std::string& button = "left");
    void mouse_wheel(std::int8_t delta);
    void wait_ms(std::uint32_t milliseconds);
    void stop_all();
    void run_script(const std::string& script);

private:
    void ensure_created();
    static void check_status(int32_t status);

    HidBridgeOptions options_;
    Rp2350HidSession* session_ = nullptr;
};

using HidBridge = HidSession;

}  // namespace rp2350_hid_bridge
```

- [ ] **Step 5: Implement the C++ wrapper as C ABI forwarding only**

In `src/client.cpp`, `ensure_created()` converts stored options to `Rp2350HidOptions` and calls `rp2350_hid_session_create`. `open()` calls `ensure_created()` then `rp2350_hid_session_open`; if native open fails, it releases and nulls the candidate before rethrowing so the next `open()` creates a fresh session. `close()` releases and nulls the handle; later `open()` creates a fresh handle. `check_status` throws `TimeoutError` for `STATUS_TIMEOUT` and `std::runtime_error(rp2350_hid_last_error())` for every other nonzero status.

Use a fixed `std::array<std::uint8_t, 256>` for `info()` and `caps()`, resizing the returned vector to `bytes_written`. Every other public method is one call to the matching C ABI name from Task 2.

- [ ] **Step 6: Restore the public umbrella and build target**

`include/rp2350_hid_bridge.hpp` must include, in order:

```cpp
#include "rp2350_hid_bridge/protocol.hpp"
#include "rp2350_hid_bridge/keys.hpp"
#include "rp2350_hid_bridge/script.hpp"
#include "rp2350_hid_bridge/c_api.h"
#include "rp2350_hid_bridge/client.hpp"
```

Add `src/client.cpp` and `src/port_discovery.cpp` to the shared target, link `setupapi` on Windows, and keep the target name `rp2350_hid_bridge` so existing `target_link_libraries` calls continue working.

Add this option so a parent project can consume the SDK without building examples/tests:

```cmake
option(
    RP2350_HID_BRIDGE_BUILD_TESTS
    "Build RP2350 HID SDK tests and examples"
    ${PROJECT_IS_TOP_LEVEL}
)
```

Wrap test/example targets in `if(RP2350_HID_BRIDGE_BUILD_TESTS)`.

- [ ] **Step 7: Run C++ SDK verification**

```powershell
cmake -S . -B build-shared-plan -A x64
cmake --build build-shared-plan --config Release
ctest --test-dir build-shared-plan -C Release --output-on-failure
Get-Item build-shared-plan\Release\rp2350_hid_bridge.dll,build-shared-plan\Release\rp2350_hid_bridge.lib
```

Expected: all tests pass and both shared-library artifacts exist.

- [ ] **Step 8: Update C++ integration documentation**

Update `README.md` and `INTEGRATION.md` to state that consumers link `rp2350_hid_bridge`, deploy `rp2350_hid_bridge.dll` beside their EXE, and use `HidSession` or compatibility `HidBridge`. Replace every `header-only` statement. Document that one session is command-thread-safe, that `close()` releases one owner, and that final release performs global stop/port close.

- [ ] **Step 9: Commit the public native SDK**

```powershell
git add CMakeLists.txt README.md INTEGRATION.md include/rp2350_hid_bridge.hpp include/rp2350_hid_bridge/client.hpp include/rp2350_hid_bridge/port_discovery.hpp src/client.cpp src/port_discovery.cpp tests/test_c_api.cpp
git commit -m "feat: ship shared HID session library"
```

### Task 4: Build the Python native loader and ABI handshake

**Files:**
- Create: `tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/native.py`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/tests/test_sdk.py`

- [ ] **Step 1: Replace pyserial loader tests with failing native-loader tests**

Retain tests for `parse_combo`, `encode_frame`, `decode_frame` and `parse_script`. Add tests with a fake DLL object:

```python
def test_native_loader_reports_all_missing_exports():
    fake = SimpleNamespace(rp2350_hid_get_abi_info=lambda _value: 0)
    with self.assertRaisesRegex(RuntimeError, "rp2350_hid_session_create"):
        native_module._require_exports(fake, Path("old-hid.dll"))

def test_hid_abi_requires_1_0_and_shared_session_feature():
    valid = native_module.HidAbiInfo(
        abi_major=1,
        abi_minor=0,
        options_size=ctypes.sizeof(native_module._CHidOptions),
        feature_flags=native_module.FEATURE_SHARED_SESSION,
    )
    native_module._validate_abi(valid, Path("rp2350_hid_bridge.dll"))
    with self.assertRaisesRegex(RuntimeError, "ABI major"):
        native_module._validate_abi(
            dataclasses.replace(valid, abi_major=2),
            Path("bad.dll"),
        )
```

- [ ] **Step 2: Verify the native module is missing**

Run from the Python HID SDK repository:

```powershell
uv run python -m unittest discover -s tests -v
```

Expected: import fails because `rp2350_hid_bridge.native` does not exist.

- [ ] **Step 3: Implement deterministic HID DLL discovery**

In `native.py`, define:

```python
ABI_MAJOR = 1
MINIMUM_ABI_MINOR = 0
FEATURE_SHARED_SESSION = 1 << 0
FEATURE_PORT_DISCOVERY = 1 << 1
REQUIRED_FEATURES = FEATURE_SHARED_SESSION | FEATURE_PORT_DISCOVERY

def find_hid_dll(*, app_dir=None, dll_path=None) -> Path:
    if dll_path is not None:
        candidate = Path(dll_path).resolve()
    elif app_dir is not None:
        candidate = (Path(app_dir).resolve() / "rp2350_hid_bridge.dll")
    elif os.environ.get("RP2350_HID_BRIDGE_DLL"):
        candidate = Path(os.environ["RP2350_HID_BRIDGE_DLL"]).resolve()
    else:
        package_dir = Path(__file__).resolve().parent
        repository = package_dir.parents[4] / "rp2350_hid_bridge_cpp"
        candidates = (
            repository / "build" / "Release" / "rp2350_hid_bridge.dll",
            repository / "build-shared-plan" / "Release" / "rp2350_hid_bridge.dll",
        )
        candidate = next((value for value in candidates if value.is_file()), candidates[0])
    if not candidate.is_file():
        raise FileNotFoundError(f"RP2350 HID DLL does not exist: {candidate}")
    return candidate
```

Formal `app_dir` resolution must never fall back to `PATH` or another directory.

- [ ] **Step 4: Define exact ctypes layouts and export validation**

Implement `_CHidAbiInfo`, `_CHidOptions`, immutable `HidAbiInfo`, `_REQUIRED_EXPORTS` matching every declaration in `c_api.h`, `_require_exports`, and `_validate_abi`. Configure all pointer/integer/string signatures before creating a session. Load with `ctypes.CDLL(str(path))`, not `ctypes.PyDLL`, so native calls release the GIL.

Expose `_NativeApi.path`, `_NativeApi.abi_info`, `create(options)`, `retain(handle)`, `release(handle)`, `open(handle)`, `is_open(handle)` and one method per command. `_check` raises built-in `TimeoutError` for status `-2` and `RuntimeError` with `rp2350_hid_last_error()` for status `-1`.

- [ ] **Step 5: Run native-loader tests**

```powershell
uv run python -m unittest discover -s tests -v
```

Expected: loader/ABI tests and retained pure protocol tests pass without importing pyserial.

- [ ] **Step 6: Commit the loader**

```powershell
git add rp2350_hid_bridge/native.py tests/test_sdk.py
git commit -m "feat: load native HID session ABI"
```

### Task 5: Replace the Python serial client with `HidSession`

**Files:**
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/client.py`
- Create: `tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/_version.py`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/__init__.py`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/pyproject.toml`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/tests/test_sdk.py`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/examples/basic.py`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/examples/list_ports.py`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/examples/script_demo.py`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/README.md`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/INTEGRATION.md`

- [ ] **Step 1: Write failing public-session tests with a fake native API**

Use this fake contract in `tests/test_sdk.py`:

```python
class FakeNativeApi:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.abi_info = SimpleNamespace(abi_major=1, abi_minor=0, feature_flags=3)
        self.calls = []
        self.opened = False

    def create(self, options):
        self.calls.append(("create", options))
        return 123

    def open(self, handle):
        self.calls.append(("open", handle))
        self.opened = True

    def is_open(self, handle):
        self.calls.append(("is_open", handle))
        return self.opened

    def key_down(self, handle, combo):
        self.calls.append(("key_down", handle, combo))

    def mouse_move(self, handle, dx, dy):
        self.calls.append(("mouse_move", handle, dx, dy))

    def stop_all(self, handle):
        self.calls.append(("stop_all", handle))

    def release(self, handle):
        self.calls.append(("release", handle))
        self.opened = False
```

Test that entering opens once, keyboard and mouse use handle `123`, explicit `stop_all` forwards, exiting releases once, repeated `close()` is a no-op, and `_binding_for_runtime()` rejects a closed object.

- [ ] **Step 2: Verify `HidSession` is not exported yet**

```powershell
uv run python -m unittest discover -s tests -v
```

Expected: tests fail because `HidSession` and `_binding_for_runtime` do not exist.

- [ ] **Step 3: Implement the Python lifecycle and binding token**

Keep `HidBridgeOptions` with current fields. Add:

```python
@dataclass(frozen=True)
class _NativeSessionBinding:
    handle: int
    dll_path: Path
    abi_major: int
    abi_minor: int

class HidSession:
    def __init__(
        self,
        port: str | None = None,
        *,
        app_dir: str | os.PathLike[str] | None = None,
        dll_path: str | os.PathLike[str] | None = None,
        baudrate: int = 115200,
        timeout: float = 1.0,
        retries: int = 2,
        vid: int = DEFAULT_VID,
        pid: int = DEFAULT_PID,
        _api=None,
    ):
        self.options = HidBridgeOptions(port, baudrate, timeout, retries, vid, pid)
        self._api = _api or _NativeApi(app_dir=app_dir, dll_path=dll_path)
        self._handle = 0
        self._lock = threading.RLock()
```

`open()` resolves a missing port with native `find_port`, creates the native handle with milliseconds `round(timeout * 1000)`, opens it, and releases the candidate if open fails. Every command holds `_lock`, requires a nonzero handle, and calls the matching `_NativeApi` method. `close()` swaps `_handle` to zero under the lock then calls `release`; it does not call a second Python-side `stop_all` because native final release owns shutdown. `__del__` suppresses cleanup exceptions.

`_binding_for_runtime()` returns `_NativeSessionBinding(handle, api.path, abi major, abi minor)` only when `api.is_open(handle)` is true.

- [ ] **Step 4: Preserve the old constructor through a compatibility class**

Implement:

```python
class HidBridge(HidSession):
    def __init__(self, options: HidBridgeOptions | None = None, **kwargs):
        selected = options or HidBridgeOptions()
        super().__init__(
            selected.port,
            baudrate=selected.baudrate,
            timeout=selected.timeout,
            retries=selected.retries,
            vid=selected.vid,
            pid=selected.pid,
            **kwargs,
        )
```

Update `find_port()` to call the native discovery API. `list_ports()` returns a list containing the discovered COM name or an empty list; document the narrower `list[str]` result because pyserial `ListPortInfo` is no longer part of the dependency contract.

- [ ] **Step 5: Export and version the new SDK**

In `__init__.py`, export `HidSession` before `HidBridge`. In `pyproject.toml`, set:

```toml
[project]
name = "rp2350-hid-bridge"
version = "0.2.0"
requires-python = ">=3.11"
dependencies = []
```

Create `_version.py` containing exactly `__version__ = "0.2.0"`, import it from `__init__.py`, and include `"__version__"` in `__all__`.

- [ ] **Step 6: Run tests and build the wheel**

```powershell
uv lock
uv run python -m unittest discover -s tests -v
uv build --wheel
```

Expected: all SDK tests pass; wheel metadata has version `0.2.0`, contains no DLL and has no `Requires-Dist: pyserial`.

- [ ] **Step 7: Update examples and integration docs**

All examples use `with HidSession("COM4", app_dir=app_dir)`. Explain EXE-sibling DLL deployment, shared references, command thread safety, explicit `hid.stop_all()`, final-release shutdown and the firmware two-second lease. Remove pyserial installation and serial-state-machine explanations.

- [ ] **Step 8: Commit the Python HID SDK**

```powershell
git add pyproject.toml uv.lock rp2350_hid_bridge tests examples README.md INTEGRATION.md
git commit -m "feat: wrap shared native HID session"
```

### Task 6: Add the shared-session capability to the vision C ABI

**Files:**
- Modify: `tools/cpp_analyzer/include/vision_analyzer/vision_runtime_c_api.h:12-118`
- Modify: `tools/cpp_analyzer/src/vision_runtime_c_api.cpp:15-430`
- Modify: `tools/cpp_analyzer/tests/test_c_api.cpp:1-260`
- Modify: `tools/cpp_analyzer/CMakeLists.txt`
- Modify: `tools/cpp_analyzer/xmake.lua`

- [ ] **Step 1: Write failing ABI and attachment tests**

Extend `tests/test_c_api.cpp` with:

```cpp
static_assert(VA_RUNTIME_ABI_MAJOR == 2u);
static_assert(VA_RUNTIME_ABI_MINOR == 1u);

void test_shared_hid_session_attachment_and_port_exclusion() {
    Rp2350HidOptions options{};
    options.struct_size = sizeof(options);
    options.port = "COM_TEST";
    options.baud = 115200;
    options.timeout_ms = 1000;
    options.retries = 2;
    options.heartbeat_interval_ms = 500;

    Rp2350HidSession* hid = nullptr;
    require(rp2350_hid_session_create(&options, &hid) == 0,
            "unopened HID handle should be creatable without hardware");

    VaRuntime* runtime = va_create();
    require(runtime != nullptr, "runtime should exist");
    require(va_attach_hid_session(runtime, hid) == 0,
            "runtime should retain an attached HID handle");
    require(va_set_hid_port(runtime, "COM4") == -1,
            "attached session and private port must be mutually exclusive");
    require(std::strstr(va_last_error(runtime), "attached HID session") != nullptr,
            "port conflict should explain the attached session");
    require(va_close(runtime) == 0, "reset should keep the configured attachment valid");
    require(va_attach_hid_session(runtime, nullptr) == 0,
            "READY runtime should detach after reset");

    va_destroy(runtime);
    rp2350_hid_session_release(hid);
}
```

Also update `test_runtime_abi_info()` to require ABI `2.1` and the new feature bit.

- [ ] **Step 2: Verify the new C ABI does not compile**

Run from `tools/cpp_analyzer`:

```powershell
cmake -S . -B build-shared-hid-plan -A x64 `
  -DONNXRUNTIME_ROOT=D:\Tool\onnxruntime-win-x64-gpu-1.17.3 `
  -DHID_SDK_ROOT=D:\project\cs2-vision-trainer\tools\rp2350_hid_bridge_cpp
cmake --build build-shared-hid-plan --config Release
```

Expected: compilation fails because ABI minor `1`, feature bit and `va_attach_hid_session` are absent.

- [ ] **Step 3: Add the public vision declaration**

In `vision_runtime_c_api.h`, add the opaque forward declaration and feature:

```c
typedef struct VaRuntime VaRuntime;
typedef struct Rp2350HidSession Rp2350HidSession;

#define VA_RUNTIME_ABI_MAJOR 2u
#define VA_RUNTIME_ABI_MINOR 1u
#define VA_RUNTIME_FEATURE_SHARED_HID_SESSION (UINT64_C(1) << 4)

VA_API int32_t va_attach_hid_session(
    VaRuntime* runtime,
    Rp2350HidSession* session
);
```

Add the feature to `va_get_abi_info`; the combined required flags become decimal `31`.

- [ ] **Step 4: Give `VaRuntime` one persistent attachment reference**

Include `rp2350_hid_bridge/c_api.h` in `vision_runtime_c_api.cpp`. Extend the internal runtime handle:

```cpp
struct VaRuntime {
    vision_analyzer::Options options;
    vision_analyzer::RuntimeSession session;
    std::filesystem::path hid_calibration_path;
    std::string last_error;
    Rp2350HidSession* attached_hid_session = nullptr;

    ~VaRuntime() {
        session.close();
        if (attached_hid_session != nullptr) {
            rp2350_hid_session_release(attached_hid_session);
        }
    }
};
```

Implement `va_attach_hid_session` with transactional replacement: reject when `session.is_open()`, reject a non-null session while `options.hid_port` is nonempty, retain the candidate first, assign it to both `attached_hid_session` and `options.hid_session`, then release the previous pointer. Passing null clears both pointers.

- [ ] **Step 5: Enforce mutual exclusion from both API directions**

Change `va_set_hid_port` to:

```cpp
int32_t va_set_hid_port(VaRuntime* runtime, const char* port) {
    return call_api(runtime, [&] {
        const std::string candidate = port == nullptr ? std::string{} : std::string(port);
        if (!candidate.empty() && runtime->attached_hid_session != nullptr) {
            throw std::runtime_error(
                "HID port cannot be set while an attached HID session is configured"
            );
        }
        runtime->options.hid_port = candidate;
    });
}
```

- [ ] **Step 6: Link both build systems to the shared HID target**

In CMake, set `RP2350_HID_BRIDGE_BUILD_TESTS=OFF`, add the HID SDK as a subdirectory under a dedicated binary directory, and link `vision_analyzer_core` publicly to `rp2350_hid_bridge`.

Add a post-build helper for each executable/DLL that loads the HID library:

```cmake
function(vision_analyzer_copy_hid_runtime target_name)
    add_custom_command(TARGET ${target_name} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                $<TARGET_FILE:rp2350_hid_bridge>
                $<TARGET_FILE_DIR:${target_name}>
    )
endfunction()
```

Apply it to `vision_runtime`, `vision_analyzer`, `vision_analyzer_tests` and `vision_runtime_c_api_tests` so CTest and packaged Release outputs resolve the dependency without a global `PATH` entry.

In xmake, add a shared target sourced from the SDK instead of embedding the header-only client:

```lua
target("rp2350_hid_bridge_native")
    set_kind("shared")
    set_filename("rp2350_hid_bridge")
    add_files(path.join(hid_sdk_root, "src/c_api.cpp"))
    add_files(path.join(hid_sdk_root, "src/client.cpp"))
    add_files(path.join(hid_sdk_root, "src/port_discovery.cpp"))
    add_includedirs(path.join(hid_sdk_root, "include"), {public = true})
    add_defines("RP2350_HID_BRIDGE_BUILD_DLL")
    if is_plat("windows") then
        add_syslinks("setupapi")
    end
```

Add this dependency to `vision_runtime`, `vision_analyzer` and both test targets that call HID C ABI. Confirm xmake emits `rp2350_hid_bridge.dll` beside `vision_runtime.dll`.

Add `#include "rp2350_hid_bridge/c_api.h"` to `tests/test_c_api.cpp`; the vision public header intentionally uses only an opaque forward declaration.

- [ ] **Step 7: Run vision ABI tests**

```powershell
cmake --build build-shared-hid-plan --config Release
ctest --test-dir build-shared-hid-plan -C Release --output-on-failure
```

Expected: C API tests pass without opening a physical COM port.

- [ ] **Step 8: Commit the vision attachment ABI**

```powershell
git add CMakeLists.txt xmake.lua include/vision_analyzer/vision_runtime_c_api.h src/vision_runtime_c_api.cpp tests/test_c_api.cpp
git commit -m "feat: attach shared HID sessions to vision runtime"
```

### Task 7: Route runtime output and calibration through the shared session

**Files:**
- Modify: `tools/cpp_analyzer/include/vision_analyzer/types.hpp:70-95`
- Modify: `tools/cpp_analyzer/include/vision_analyzer/hid_output.hpp:14-51`
- Modify: `tools/cpp_analyzer/src/hid_output.cpp:1-139`
- Modify: `tools/cpp_analyzer/include/vision_analyzer/runtime_session.hpp:31-61`
- Modify: `tools/cpp_analyzer/src/runtime_session.cpp:16-188`
- Modify: `tools/cpp_analyzer/src/calibration.cpp:1033-1417`
- Modify: `tools/cpp_analyzer/src/runtime_options.cpp:55-79`
- Modify: `tools/cpp_analyzer/src/vision_runtime_c_api.cpp:350-430`
- Modify: `tools/cpp_analyzer/tests/test_algorithms.cpp:1924-1990`
- Modify: `tools/cpp_analyzer/tests/test_c_api.cpp`

- [ ] **Step 1: Change safety tests to the approved no-global-stop behavior**

Replace the old disarm assertion in `test_algorithms.cpp`:

```cpp
sender.set_enabled(false);
require(client.stop_calls == 0,
        "disarming vision output must preserve caller-owned keyboard state");
sender.execute(command);
require(client.moves.size() == 1,
        "disarmed sender must suppress subsequent movement");
```

Rename the test to `test_hid_action_sender_disarms_without_global_stop`. Change `test_hid_close_continues_after_stop_failure` into:

```cpp
void test_hid_close_does_not_issue_global_stop() {
    RecordingHidClient client;
    close_hid_client_noexcept(&client);
    require(client.stop_calls == 0, "client close must not issue shared STOP_ALL");
    require(client.close_calls == 1, "client close must release its reference");
}
```

- [ ] **Step 2: Add C API tests for shared emergency-stop ownership**

After attaching the unopened HID handle in `tests/test_c_api.cpp`, assert:

```cpp
require(va_stop_all(runtime) == -1,
        "shared runtime must reject its legacy global stop API");
require(std::strstr(va_last_error(runtime), "hid.stop_all") != nullptr,
        "shared stop error should direct Python ownership to HidSession");
```

- [ ] **Step 3: Run tests and verify current STOP_ALL behavior fails**

```powershell
cmake --build build-shared-hid-plan --config Release
ctest --test-dir build-shared-hid-plan -C Release --output-on-failure
```

Expected: algorithm tests fail because disarm and close currently call `stop_all()`.

- [ ] **Step 4: Add the attached handle to runtime options**

Forward-declare `Rp2350HidSession` in `types.hpp` and add:

```cpp
Rp2350HidSession* hid_session = nullptr;
```

Update option validation so live output and calibration require either a nonempty `hid_port` or non-null `hid_session`, and reject when both are configured.

- [ ] **Step 5: Implement private and shared native clients**

In `hid_output.hpp`, declare overloads:

```cpp
[[nodiscard]] std::unique_ptr<HidClient> create_rp2350_hid_client(
    const std::string& port
);
[[nodiscard]] std::unique_ptr<HidClient> create_rp2350_hid_client(
    Rp2350HidSession* session
);
```

In `hid_output.cpp`, replace the embedded C++ `HidBridge` member with a raw native handle owned by reference. The private-port constructor calls `session_create`, `session_open`, ping/info/caps and owns the initial reference. The attached-session constructor calls `retain`, then ping/info/caps. Both destructors call only `release`; native final release decides whether global shutdown is required.

`move_relative`, `click_left` and explicit `stop_all` call the C ABI and translate failures with `rp2350_hid_last_error()`. `close()` atomically swaps the pointer to null and releases it once.

- [ ] **Step 6: Remove implicit global stops**

Implement these exact rules:

```cpp
void close_hid_client_noexcept(HidClient* client) noexcept {
    if (client != nullptr) {
        client->close();
    }
}

void HidActionSender::set_enabled(bool enabled) {
    std::scoped_lock lock(output_mutex_);
    enabled_.store(enabled);
}
```

Keep `HidActionSender::stop_all()` only for the explicit legacy API.

- [ ] **Step 7: Select the configured session in runtime and calibration**

In `RuntimeSession::open`:

```cpp
if (!options_.dry_run) {
    hid_client_ = options_.hid_session != nullptr
        ? create_rp2350_hid_client(options_.hid_session)
        : create_rp2350_hid_client(options_.hid_port);
    hid_sender_ = std::make_unique<HidActionSender>(*hid_client_);
    hid_sender_->set_enabled(options_.output_enabled);
}
```

Use the same conditional construction in `run_hid_calibration`. Its success and failure cleanup calls `close_hid_client_noexcept` only; do not call `stop_all`. Retain the existing balanced inverse movement attempt so the camera is returned when a probe throws.

- [ ] **Step 8: Restrict the legacy global stop**

In `va_stop_all`, reject when `attached_hid_session` is non-null with the exact message:

```text
shared HID session is owned by the caller; use hid.stop_all()
```

Private-port mode continues calling `runtime->session.stop_all()`.

- [ ] **Step 9: Run all vision tests**

```powershell
cmake --build build-shared-hid-plan --config Release
ctest --test-dir build-shared-hid-plan -C Release --output-on-failure
```

Expected: algorithm and C API tests pass; no test requires COM hardware.

- [ ] **Step 10: Commit shared output semantics**

```powershell
git add include/vision_analyzer/types.hpp include/vision_analyzer/hid_output.hpp include/vision_analyzer/runtime_session.hpp src/hid_output.cpp src/runtime_session.cpp src/calibration.cpp src/runtime_options.cpp src/vision_runtime_c_api.cpp tests/test_algorithms.cpp tests/test_c_api.cpp
git commit -m "fix: preserve caller keys when vision output disarms"
```

### Task 8: Expose shared `HidSession` through the main Python runtime SDK

**Files:**
- Modify: `src/cs2_vision_runtime/runtime.py:14-1010`
- Modify: `src/cs2_vision_runtime/__init__.py`
- Modify: `src/cs2_vision_runtime/_version.py`
- Modify: `tests/test_vision_runtime_sdk.py`

- [ ] **Step 1: Add failing Python binding and lifecycle tests**

Extend `FakeApi` with:

```python
path = Path("C:/app/vision_runtime.dll")

def attach_hid_session(self, handle, hid_handle):
    self.calls.append(("attach_hid_session", hid_handle))
    return self.next_status
```

Use a fake HID object:

```python
class FakeHidSession:
    def __init__(self, dll_path: Path, handle: int = 456):
        self.binding = SimpleNamespace(
            handle=handle,
            dll_path=dll_path.resolve(),
            abi_major=1,
            abi_minor=0,
        )

    def _binding_for_runtime(self):
        return self.binding
```

Add tests that `attach_hid_session` is READY-only, passes `456`, rejects later `set_hid_port`, survives `reset`, and is released by runtime destruction. Change `armed_output` expected cleanup to only:

```python
[
    ("set_output_enabled", True),
    ("set_fire_enabled", True),
    ("set_fire_enabled", False),
    ("set_output_enabled", False),
]
```

Add a shared-mode test asserting `runtime.stop_all()` raises `RuntimeStateError` containing `hid.stop_all` without calling the DLL.

- [ ] **Step 2: Verify Python tests fail against ABI 2.0 behavior**

```powershell
uv run pytest tests/test_vision_runtime_sdk.py -q
```

Expected: failures for missing attach export, required feature `31`, ABI minor `1`, and obsolete `stop_all` cleanup calls.

- [ ] **Step 3: Bind the new export and ABI requirement**

Set:

```python
_MINIMUM_ABI_MINOR = 1
_FEATURE_SHARED_HID_SESSION = 1 << 4
_REQUIRED_FEATURES = 31
```

Add `va_attach_hid_session` to `_REQUIRED_EXPORTS`; configure it as two `ctypes.c_void_p` arguments returning `c_int32`; add `_RuntimeApi.attach_hid_session(handle, hid_handle)`.

- [ ] **Step 4: Add the public attach method and conflict state**

`VisionRuntime.__init__` initializes `self._hid_session = None`. Implement:

```python
def attach_hid_session(self, hid_session) -> None:
    self._require_state("attach HID session", RuntimeState.READY)
    binding = hid_session._binding_for_runtime()
    expected_hid_dll = (self._api.path.parent / "rp2350_hid_bridge.dll").resolve()
    if binding.dll_path != expected_hid_dll:
        raise RuntimeCompatibilityError(
            f"HID session DLL must match the vision runtime directory: "
            f"expected {expected_hid_dll}, got {binding.dll_path}"
        )
    self._check(
        self._api.attach_hid_session(self._require_handle(), binding.handle),
        "attach HID session",
    )
    self._hid_session = hid_session
```

`set_hid_port(nonempty)` and `open_dxgi(hid_port=nonempty)` raise `RuntimeStateError` before a DLL call when `_hid_session` is set. `reset()` keeps `_hid_session`. `close()` destroys the runtime first, then clears the Python reference.

- [ ] **Step 5: Extend the app-local factory**

Use the exact signature:

```python
@classmethod
def from_app_dir(
    cls,
    app_dir,
    *,
    data_dir,
    hid_session=None,
) -> "VisionRuntime":
```

After loading `RuntimePackage`, compare `hid_session._binding_for_runtime().dll_path` with `package.hid_dll_path`. Raise `RuntimeCompatibilityError` on mismatch before constructing the vision DLL. After model configuration, call `attach_hid_session` when supplied.

- [ ] **Step 6: Remove global stop from normal output cleanup**

`armed_output()` cleanup order remains fire false then output false, but remove `self.stop_all` from the cleanup tuple. `stop_all()` raises `RuntimeStateError("shared HID session is caller-owned; use hid.stop_all()")` when `_hid_session` is not null; legacy private-port behavior is unchanged.

- [ ] **Step 7: Re-export and version using the checked-out first-party SDK**

Set `__version__ = "0.3.0"`. In `__init__.py`:

```python
from rp2350_hid_bridge import HidSession
```

and add `"HidSession"` to `__all__`.

Until Task 10 records the dependency in the parent lock, make the checked-out HID package available to focused parent tests:

```powershell
$env:PYTHONPATH=(Resolve-Path 'tools\rp2350_keymouse_bridge_firmware\sdk\python').Path
```

- [ ] **Step 8: Run focused Python tests**

```powershell
$env:PYTHONPATH=(Resolve-Path 'tools\rp2350_keymouse_bridge_firmware\sdk\python').Path
uv run pytest tests/test_vision_runtime_sdk.py -q
```

Expected: all runtime SDK tests pass with no `stop_all` in normal cleanup.

- [ ] **Step 9: Commit the Python runtime API**

```powershell
git add src/cs2_vision_runtime tests/test_vision_runtime_sdk.py
git commit -m "feat: attach caller-owned HID sessions in Python SDK"
```

### Task 9: Upgrade app-local package validation to manifest v2

**Files:**
- Modify: `src/cs2_vision_runtime/package.py`
- Modify: `tests/test_runtime_package.py`
- Modify: `tests/test_vision_runtime_sdk.py`

- [ ] **Step 1: Update the fixture to require both DLLs**

In `make_app_layout`, create `app_dir / "rp2350_hid_bridge.dll"`, use `manifest_version: 2`, Python runtime `0.3.0`, vision ABI `2.1`, flags `31`, and this section:

```python
"hid_bridge": {
    "dll": {
        "file_name": "rp2350_hid_bridge.dll",
        "sha256": _sha256(hid_dll),
        "abi_major": 1,
        "abi_minor": 0,
    },
    "python_sdk": {"minimum": "0.2.0", "recommended": "0.2.0"},
},
```

Assert `package.hid_dll_path`, `hid_abi_major`, `hid_abi_minor`, `hid_python_sdk_minimum` and `hid_python_sdk_recommended`.

- [ ] **Step 2: Add tamper and path-escape tests for the HID DLL**

Add cases for a changed HID hash, missing HID DLL, `../rp2350_hid_bridge.dll`, ABI major `2`, and minimum Python HID SDK `9.0.0`. Expected exceptions are `RuntimeCompatibilityError` for contract/hash issues and `RuntimeLoadError` for a missing file.

- [ ] **Step 3: Verify manifest v1 code rejects the new fixture**

```powershell
$env:PYTHONPATH=(Resolve-Path 'tools\rp2350_keymouse_bridge_firmware\sdk\python').Path
uv run pytest tests/test_runtime_package.py -q
```

Expected: fixture load fails because the loader currently accepts only manifest version `1` and has no HID fields.

- [ ] **Step 4: Extend `RuntimePackage` and loader**

Add fields:

```python
hid_dll_path: Path
hid_abi_major: int
hid_abi_minor: int
hid_python_sdk_minimum: str
hid_python_sdk_recommended: str
```

Require manifest version `2`. Resolve the HID DLL filename strictly under `app_dir`, verify SHA256, require ABI `1.0`, validate both three-part SDK versions and require installed `rp2350_hid_bridge.__version__` to meet the minimum. Keep native GPU directories and cache behavior unchanged.

- [ ] **Step 5: Pass the exact package path to `HidSession` comparisons**

Update the `from_app_dir` fake package in `test_vision_runtime_sdk.py` to include `hid_dll_path`, and add one mismatch test proving attachment fails before `_RuntimeApi` is created.

- [ ] **Step 6: Run package and runtime tests**

```powershell
$env:PYTHONPATH=(Resolve-Path 'tools\rp2350_keymouse_bridge_firmware\sdk\python').Path
uv run pytest tests/test_runtime_package.py tests/test_vision_runtime_sdk.py -q
```

Expected: both test modules pass.

- [ ] **Step 7: Commit manifest validation**

```powershell
git add src/cs2_vision_runtime/package.py tests/test_runtime_package.py tests/test_vision_runtime_sdk.py
git commit -m "feat: validate app-local HID runtime component"
```

### Task 10: Build and test the two Python SDK wheels

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `packaging/python-runtime-sdk/pyproject.toml`
- Modify: `packaging/python-runtime-sdk/README.md`
- Modify: `scripts/build_python_runtime_sdk.ps1`
- Modify: `tests/test_runtime_sdk_distribution.py`

- [ ] **Step 1: Change distribution tests to expect two first-party wheels**

Make `_build_wheels` return a dictionary by normalized project name. Assert:

```python
assert set(wheels) == {"cs2_vision_runtime_sdk", "rp2350_hid_bridge"}
assert "Version: 0.3.0" in runtime_metadata
assert "Requires-Dist: rp2350-hid-bridge==0.2.0" in runtime_metadata
assert "Version: 0.2.0" in hid_metadata
assert "Requires-Dist: pyserial" not in hid_metadata
```

Install both concrete paths in the clean-environment test:

```python
subprocess.run(
    [
        uv,
        "pip",
        "install",
        "--python",
        str(venv_python),
        "--no-deps",
        str(wheels["rp2350_hid_bridge"]),
        str(wheels["cs2_vision_runtime_sdk"]),
    ],
    check=True,
)
```

Then import `HidSession` and `VisionRuntime` and print both versions.

- [ ] **Step 2: Verify the current one-wheel builder fails**

```powershell
uv run pytest tests/test_runtime_sdk_distribution.py -q
```

Expected: test fails because only one `0.2.0` runtime wheel is built.

- [ ] **Step 3: Add the first-party dependency to project metadata**

In the root `pyproject.toml`, add `rp2350-hid-bridge==0.2.0` to dependencies and add this key to the existing `[tool.uv.sources]` table:

```toml
[tool.uv.sources]
rp2350-hid-bridge = { path = "tools/rp2350_keymouse_bridge_firmware/sdk/python", editable = true }
```

Preserve the existing PyTorch source entries. In the standalone runtime template add:

```toml
dependencies = ["rp2350-hid-bridge==0.2.0"]
```

- [ ] **Step 4: Build the HID wheel before the runtime wheel**

In `build_python_runtime_sdk.ps1`, resolve:

```powershell
$hidProjectRoot = Join-Path $projectRoot 'tools\rp2350_keymouse_bridge_firmware\sdk\python'
```

Run `uv build --wheel --out-dir $outputFullPath $hidProjectRoot` before staging the runtime package. Require exactly one `rp2350_hid_bridge-0.2.0-*.whl` and one `cs2_vision_runtime_sdk-0.3.0-*.whl`; reject extra matching versions.

- [ ] **Step 5: Refresh the lock and run distribution tests**

```powershell
uv lock
uv run pytest tests/test_runtime_sdk_distribution.py -q
```

Expected: two wheels build, install without third-party dependencies, and import in a clean virtual environment.

- [ ] **Step 6: Commit wheel integration**

```powershell
git add pyproject.toml uv.lock packaging/python-runtime-sdk scripts/build_python_runtime_sdk.ps1 tests/test_runtime_sdk_distribution.py
git commit -m "build: publish coordinated Python runtime wheels"
```

### Task 11: Package both native DLLs and manifest v2

**Files:**
- Modify: `tools/cpp_analyzer/packaging/sm61/PackageTools.psm1`
- Modify: `tools/cpp_analyzer/packaging/sm61/build-portable-package.ps1`
- Modify: `tools/cpp_analyzer/packaging/sm61/build-app-local-package.ps1`
- Modify: `tools/cpp_analyzer/packaging/sm61/tests/run-tests.ps1`
- Modify: `tools/cpp_analyzer/packaging/sm61/package/README_中文.md`

- [ ] **Step 1: Update packaging tests before scripts**

The portable fixture must contain:

```text
app/rp2350_hid_bridge.dll
app/rp2350_hid_bridge.lib
app/rp2350_hid_bridge_c_api.h
python/rp2350_hid_bridge/__init__.py
python/rp2350_hid_bridge/_version.py
python/rp2350_hid_bridge/native.py
python/rp2350_hid_bridge/client.py
```

The app-local expected output adds root `rp2350_hid_bridge.dll`. Assertions become manifest version `2`, runtime ABI `2.1`, flags `31`, HID ABI `1.0`, HID Python SDK `0.2.0`, and HID SHA256 equal to the copied root file.

- [ ] **Step 2: Verify the app-local packaging test fails**

Run from `tools/cpp_analyzer`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\sm61\tests\run-tests.ps1 `
  -PythonProjectRoot D:\project\cs2-vision-trainer
```

Expected: app-local layout test fails because the portable/app-local scripts know only `vision_runtime.dll` and manifest v1.

- [ ] **Step 3: Move the protocol-v2 binary gate to the HID DLL**

Rename `Assert-Rp2350ProtocolV2Binary` to `Assert-Rp2350SharedLibrary`. Require the binary to contain both `RP2350 protocol v2 capabilities are required` and at least one C export-name string such as `rp2350_hid_session_mouse_move`. Call it for `rp2350_hid_bridge.dll`, not `vision_runtime.dll`.

- [ ] **Step 4: Include HID artifacts in the portable package**

Require `rp2350_hid_bridge.dll` and `.lib` in `ReleaseRoot`, copy them under `app`, and copy `include/rp2350_hid_bridge/c_api.h` as `app/rp2350_hid_bridge_c_api.h`. Change the manifest component to:

```powershell
[pscustomobject][ordered]@{
    id = 'rp2350-hid-sdk'
    version = 'abi-1.0-protocol-v2'
    sourceMode = 'shared-library'
}
```

Resolve the checked-out Python HID package from `$PythonProjectRoot\tools\rp2350_keymouse_bridge_firmware\sdk\python\rp2350_hid_bridge`, require its `.py` files, create `python\rp2350_hid_bridge` in the portable output, and copy those files beside `python\cs2_vision_runtime`. This keeps the portable diagnostic scripts importable after the main SDK re-exports `HidSession`.

- [ ] **Step 5: Build app-local manifest v2**

Require `app\rp2350_hid_bridge.dll` in the verified portable source, copy it beside `vision_runtime.dll`, compute `$hidDllHash`, include its first 12 hash characters in `runtime_id`, and write the exact `hid_bridge` object defined at the top of this plan. Change default `PythonSdkVersion` to `0.3.0`; hardcode coordinated HID Python SDK `0.2.0` in this release profile.

The runtime ID regex becomes:

```text
^sm61-ort1173-trt861-fp32-[0-9A-F]{36}$
```

- [ ] **Step 6: Run packaging safety tests**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\sm61\tests\run-tests.ps1 `
  -PythonProjectRoot D:\project\cs2-vision-trainer
```

Expected: all package tests pass and the app-local fixture contains exactly two root runtime DLLs.

- [ ] **Step 7: Commit native packaging**

```powershell
git add packaging/sm61
git commit -m "build: package shared HID runtime DLL"
```

### Task 12: Update Python examples and integration documentation

**Files:**
- Modify: `examples/runtime_live_move.py`
- Modify: `examples/runtime_app_local.py`
- Modify: `examples/runtime_dxgi_dryrun.py`
- Modify: `docs/PYTHON_RUNTIME_SDK_INTEGRATION.md`
- Modify: `docs/BUILD.md`
- Modify: `docs/USAGE.md`
- Modify: `README.md`
- Modify: `tests/test_runtime_sdk_docs.py`
- Modify: `tests/test_vision_runtime_sdk.py`

- [ ] **Step 1: Make documentation tests require the shared-session contract**

Require these tokens in the live/app-local example and guide:

```text
HidSession
hid_session=hid
rp2350_hid_bridge.dll
hid.stop_all()
一个 COM 口
process_next()
同步
线程
```

Require that `run_armed_loop` and the `armed_output` example do not contain `runtime.stop_all()`.

- [ ] **Step 2: Verify docs tests fail**

```powershell
uv run pytest tests/test_runtime_sdk_docs.py tests/test_vision_runtime_sdk.py -q
```

Expected: failures identify the old private-port example and old global-stop cleanup.

- [ ] **Step 3: Rewrite the live example around one caller-owned session**

Use this lifecycle in `runtime_live_move.py`:

```python
with HidSession(args.hid_port, app_dir=args.app_dir) as hid:
    with VisionRuntime.from_app_dir(
        args.app_dir,
        data_dir=args.data_dir,
        hid_session=hid,
    ) as runtime:
        profile = load_or_calibrate(
            runtime,
            args.calibration_path,
            recalibrate=args.recalibrate,
            adapter=args.adapter,
            output=args.output,
        )
        runtime.open_dxgi(
            adapter=args.adapter,
            output=args.output,
            player_side=args.player_side,
            dry_run=False,
        )
        with runtime.armed_output(fire=args.click):
            process_loop(runtime, args.show_every)
```

Keep `hid.stop_all()` only in the outermost explicit emergency/whole-session cleanup path; normal `armed_output` exit must not call it. The dry-run example creates no HID session.

- [ ] **Step 4: Document the blocking and concurrency model**

State exactly: `process_next()` remains synchronous in its worker thread; `ctypes.CDLL` releases the GIL; capture/TensorRT inference does not hold the HID command lock; keyboard and mouse requests serialize only for their request/ACK round trips; long `run_script()` calls can delay aim commands.

Include the final directory:

```text
MyClient.exe
vision_runtime.dll
rp2350_hid_bridge.dll
resources/vision-runtime/runtime-manifest.json
```

Document global release only for explicit `hid.stop_all()`, final HID session end/port disconnect, process cleanup and firmware lease timeout. Explain that runtime disarm/reset preserves held keys.

- [ ] **Step 5: Run docs and SDK tests**

```powershell
uv run pytest tests/test_runtime_sdk_docs.py tests/test_vision_runtime_sdk.py -q
```

Expected: documentation contract and example behavior tests pass.

- [ ] **Step 6: Commit caller-facing integration changes**

```powershell
git add README.md docs examples tests/test_runtime_sdk_docs.py tests/test_vision_runtime_sdk.py
git commit -m "docs: document shared HID session integration"
```

### Task 13: Synchronize submodules and run automated verification

**Files:**
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware/sdk/cpp`
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware/sdk/python`
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware`
- Update gitlink: `tools/rp2350_hid_bridge_cpp`
- Update gitlink: `tools/cpp_analyzer`

- [ ] **Step 1: Push child feature branches so upper repositories can pin them**

```powershell
git -C tools\rp2350_hid_bridge_cpp push -u origin feature/shared-hid-session-native
git -C tools\rp2350_keymouse_bridge_firmware\sdk\python push -u origin feature/shared-hid-session-python
git -C tools\cpp_analyzer push -u origin feature/shared-hid-session-runtime
```

Expected: each remote branch points at its verified child commit.

- [ ] **Step 2: Make the firmware repository pin the exact two SDK commits**

Fetch the pushed child commits in the nested SDK directories and check them out detached. Verify:

```powershell
git -C tools\rp2350_keymouse_bridge_firmware\sdk\cpp fetch origin feature/shared-hid-session-native
git -C tools\rp2350_keymouse_bridge_firmware\sdk\cpp checkout --detach FETCH_HEAD

$directCpp = git -C tools\rp2350_hid_bridge_cpp rev-parse HEAD
$nestedCpp = git -C tools\rp2350_keymouse_bridge_firmware\sdk\cpp rev-parse HEAD
if ($directCpp -ne $nestedCpp) { throw 'direct and firmware C++ SDK commits differ' }

$pythonHead = git -C tools\rp2350_keymouse_bridge_firmware\sdk\python rev-parse HEAD
git -C tools\rp2350_keymouse_bridge_firmware status --short
```

Expected: firmware root reports only `sdk/cpp` and `sdk/python` gitlink changes.

- [ ] **Step 3: Run nested SDK and firmware verification**

From `tools/rp2350_keymouse_bridge_firmware`:

```powershell
uv run --project sdk/python python -m unittest discover -s sdk/python/tests -v
cmake -S sdk/cpp -B sdk/cpp/build-shared-final -A x64
cmake --build sdk/cpp/build-shared-final --config Release
ctest --test-dir sdk/cpp/build-shared-final -C Release --output-on-failure
cargo test --target x86_64-pc-windows-msvc --lib
cargo clippy --release -- -D warnings
cargo build --release --locked
powershell -NoProfile -ExecutionPolicy Bypass -File tools/tests/build-release-uf2.ps1
```

Expected: Python/C++ SDK tests pass, firmware tests/clippy/release pass, and the UF2 build script succeeds.

- [ ] **Step 4: Commit and push firmware gitlinks**

```powershell
git add sdk/cpp sdk/python
git commit -m "chore: update shared HID session SDKs"
git push -u origin feature/shared-hid-session-firmware-links
```

- [ ] **Step 5: Run the complete vision build through both build systems**

From `tools/cpp_analyzer`:

```powershell
cmake -S . -B build-shared-hid-final -A x64 `
  -DONNXRUNTIME_ROOT=D:\Tool\onnxruntime-win-x64-gpu-1.17.3 `
  -DHID_SDK_ROOT=D:\project\cs2-vision-trainer\tools\rp2350_hid_bridge_cpp
cmake --build build-shared-hid-final --config Release
ctest --test-dir build-shared-hid-final -C Release --output-on-failure

xmake f -c -m release `
  --onnxruntime_root=D:\Tool\onnxruntime-win-x64-gpu-1.17.3 `
  --hid_sdk_root=D:\project\cs2-vision-trainer\tools\rp2350_hid_bridge_cpp
xmake
Get-Item build\windows\x64\release\vision_runtime.dll,build\windows\x64\release\rp2350_hid_bridge.dll
```

Expected: CTest and xmake succeed; both DLLs are present in the release directory.

- [ ] **Step 6: Run the complete parent Python and packaging suite**

From the parent repository:

```powershell
uv sync
uv run pytest -q
powershell -NoProfile -ExecutionPolicy Bypass -File tools\cpp_analyzer\packaging\sm61\tests\run-tests.ps1 `
  -PythonProjectRoot D:\project\cs2-vision-trainer
git diff --check
```

Expected: all parent tests and packaging safety tests pass; `git diff --check` prints nothing.

- [ ] **Step 7: Commit parent code and exact submodule pointers**

```powershell
git add pyproject.toml uv.lock src packaging scripts examples docs tests tools/cpp_analyzer tools/rp2350_hid_bridge_cpp tools/rp2350_keymouse_bridge_firmware
git commit -m "feat: share one HID session across Python and vision DLL"
```

- [ ] **Step 8: Verify recursive gitlink equality and clean trees**

```powershell
$directCpp = git -C tools\rp2350_hid_bridge_cpp rev-parse HEAD
$nestedCpp = git -C tools\rp2350_keymouse_bridge_firmware\sdk\cpp rev-parse HEAD
$firmwareCpp = git -C tools\rp2350_keymouse_bridge_firmware rev-parse HEAD:sdk/cpp
$firmwarePython = git -C tools\rp2350_keymouse_bridge_firmware rev-parse HEAD:sdk/python
$nestedPython = git -C tools\rp2350_keymouse_bridge_firmware\sdk\python rev-parse HEAD
if ($directCpp -ne $nestedCpp -or $directCpp -ne $firmwareCpp) { throw 'C++ SDK gitlinks differ' }
if ($firmwarePython -ne $nestedPython) { throw 'Python SDK gitlink differs' }
git submodule status --recursive
git status --short --branch
```

Expected: direct/nested C++ hashes match, Python hashes match, and no repository contains unstaged files.

### Task 14: Perform hardware acceptance and finish the branches

**Files:**
- No source changes unless hardware evidence reveals a reproducible defect.

- [ ] **Step 1: Build a real app-local payload with two DLLs**

Use the verified portable package and run:

```powershell
& .\tools\cpp_analyzer\packaging\sm61\build-app-local-package.ps1 `
  -PortablePackageRoot .\dist\cs2-vision-runtime-sm61 `
  -OutputRoot .\dist\MyClientRuntime `
  -PythonSdkVersion 0.3.0
```

Expected: output root contains `vision_runtime.dll`, `rp2350_hid_bridge.dll` and manifest version `2`.

- [ ] **Step 2: Verify cached calibration loads without moving the camera**

From the packaged client environment:

```powershell
python .\examples\runtime_live_move.py `
  --app-dir .\dist\MyClientRuntime `
  --data-dir "$env:LOCALAPPDATA\ExquisiteCore\MyClient" `
  --hid-port COM4 `
  --player-side ct `
  --calibration-path .\hid-calibration.json `
  --enable-live-output `
  --show-every 1
```

Expected: existing valid profile loads, COM4 opens once, TensorRT initializes, actions stream and auto aim works.

- [ ] **Step 3: Verify caller keyboard state survives vision disarm**

Use a short Python acceptance script built from the public example lifecycle: call `hid.key_down("W")`, arm vision output, process several frames, exit `armed_output`, wait one second, then call `hid.key_up("W")`. Observe that movement from held `W` continues during the one-second gap and stops only at `key_up`; no `STOP_ALL` is logged at visual disarm.

- [ ] **Step 4: Verify explicit global safety stop**

Hold `W` and Shift through `HidSession`, then call `hid.stop_all()`. Expected: both keys release immediately. Close the process without explicit stop in a second run; expected: final session release or the firmware two-second lease releases all input.

- [ ] **Step 5: Verify Python control can run during blocking inference**

Run `process_next()` in a worker thread and send alternating `key_down`/`key_up` commands from the controller thread during active TensorRT inference. Expected: no sequence mismatch, timeout, duplicate COM open or corrupted response; mouse and keyboard actions both continue.

- [ ] **Step 6: Record acceptance evidence**

Record the exact parent/submodule commits, manifest runtime ID, both DLL SHA256 values, calibration quality, processed-frame output and hardware observations in the implementation handoff message. Do not commit machine-specific calibration files, caches or logs.

- [ ] **Step 7: Finish and integrate branches**

After automated and hardware verification, invoke `superpowers:verification-before-completion`, then `superpowers:requesting-code-review`, then `superpowers:finishing-a-development-branch`. Because the requested final state is `main`, merge verified child branches first, update upper gitlinks to the resulting main commits, rerun recursive status checks, merge the parent branch to `main`, and push every repository. Delete feature branches only after all remote `main` branches and recursive gitlinks agree.
