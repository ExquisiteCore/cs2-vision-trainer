# Python 调用端共享 HID 会话设计

## 状态

本设计已经完成口头方案确认，等待书面审阅。实现开始前还需单独编写实施计划。

## 目标

调用端是最终冻结为 Windows EXE 的 Python 程序。它既要通过 RP2350 发送键盘输入，也要让 `vision_runtime.dll` 发送自动瞄准鼠标输入。两类输入必须共享同一个串口会话，不得由 Python 和视觉 DLL 分别打开同一个 COM 口。

最终调用方式保持 Python 优先，并让调用端明确拥有 HID 生命周期：

```python
import os
import sys
from pathlib import Path

from cs2_vision_runtime import HidSession, VisionRuntime

app_dir = Path(sys.executable).resolve().parent
data_dir = Path(os.environ["LOCALAPPDATA"]) / "ExquisiteCore" / "MyClient"

with HidSession("COM4", app_dir=app_dir) as hid:
    with VisionRuntime.from_app_dir(
        app_dir,
        data_dir=data_dir,
        hid_session=hid,
    ) as runtime:
        hid.key_down("W")

        runtime.open_dxgi(
            adapter=0,
            output=0,
            player_side="ct",
            dry_run=False,
        )
        with runtime.armed_output(fire=False):
            for action in runtime.iter_actions():
                consume(action)

        hid.key_up("W")
```

这里没有新的 `from_bundle()` 或全局运行环境对象。`app_dir` 仍表示 EXE 所在目录；`HidSession` 可以脱离视觉运行库单独使用，`VisionRuntime` 只借用它。

## 当前问题

当前有三套互相冲突的生命周期：

1. `rp2350-hid-bridge-cpp` 是 header-only C++ SDK。`vision_runtime.dll` 把它直接编进自身，并在 `RuntimeSession::open()` 中独占打开 COM 口。
2. `rp2350-hid-bridge-python` 使用 pyserial 再实现一遍串口、序列号、响应读取、重试和心跳。它无法共享视觉 DLL 内的句柄。
3. `VisionRuntime.armed_output()` 退出时调用 `va_stop_all()`。固件的 `STOP_ALL` 是全局释放，会把调用端仍希望保持的 `W`、Shift 等键一并松开。

Windows C++ SDK 当前以 `CreateFileA(..., shareMode=0, ...)` 打开串口，因此两个实现同时打开 COM4 必然失败。即使允许共享打开，两个独立实现也会争用响应帧、序列号和心跳，协议仍会损坏。

`va_process_next()` 继续是同步调用：抓屏、推理、规划、发送当前鼠标命令并等待 ACK 后返回。这并不要求把整个视觉运行库改成异步；需要解决的是串口所有权和命令串行化。

## 方案比较

### 方案 A：Python 独占串口，视觉 DLL 只返回动作

Python 每帧读取 `dx`、`dy`、`click` 后再用 Python SDK发送。这最容易避免 COM 冲突，但会把实时输出、标定和故障处理搬出 DLL，破坏现有 DLL 运行职责，也增加逐帧 Python 调度延迟。

### 方案 B：共享一个原生 `HidSession`（采用）

`rp2350_hid_bridge.dll` 唯一拥有 COM、心跳、序列号和请求/响应锁。Python 键盘 API 和 `vision_runtime.dll` 都持有同一原生会话的引用。视觉处理仍同步，只有实际 HID 命令进入同一命令锁。

该方案保留 DLL 内的标定和自动瞄准输出，同时让 Python 调用端直接控制键盘，改动边界清晰。

### 方案 C：独立 HID 守护进程或本机 IPC 服务

单独进程独占 COM，Python 和视觉 DLL 通过管道/RPC调用。它支持跨进程共享，但引入服务部署、进程监控、IPC延迟和新的故障面。当前调用端和视觉 DLL位于同一进程，不需要这层复杂度。

## 总体架构

```text
Python 调用端 EXE
│
├─ HidSession.key_down/key_up/stop_all
│  └─ Python 轻量包装
│     └─ rp2350_hid_bridge.dll
│        ├─ 唯一 COM 句柄
│        ├─ 唯一心跳线程和序列号
│        ├─ 请求/响应命令锁
│        └─ 引用计数会话
│
└─ VisionRuntime.process_next/calibrate_hid
   └─ vision_runtime.dll
      └─ retain 同一个原生 HidSession
         └─ mouse_move/mouse_click
```

核心不变量是：

```text
一个物理 COM 口 = 一个原生 HidSession = 一个协议会话
```

## 仓库职责

### `rp2350-hid-bridge-cpp`

该仓库成为唯一原生实现，交付：

- `rp2350_hid_bridge.dll` 和构建期 import library。
- 稳定的 C ABI、ABI 握手和不透明 `Rp2350HidSession` 句柄。
- 串口、DTR、心跳、序列号、重试、响应读取、命令串行化和会话故障状态。
- 完整键盘、鼠标和脚本命令。
- C++ RAII 包装，保持现有 `HidBridge` 主要源代码用法兼容。

C++ 类对象、STL 容器和异常不跨 DLL 边界。跨仓调用只使用 C ABI、不透明指针、固定宽度整数和 UTF-8 字符串。

### `rp2350-hid-bridge-python`

该仓库保留为 Python SDK，但不再用 pyserial 单独打开 COM，也不再维护第二套协议状态机。它通过 `ctypes.CDLL` 包装 `rp2350_hid_bridge.dll`，公开新的推荐名称 `HidSession`。

为减少迁移成本：

- 现有 `HidBridgeOptions` 保留。
- 现有 `HidBridge` 作为 `HidSession` 的兼容名称保留。
- `key_down()`、`key_up()`、`mouse_move()`、`run_script()`、`stop_all()` 等公开方法保持。
- Python wheel 不携带 DLL；DLL作为 EXE 同级运行时制品交付。
- pyserial 从运行时依赖中移除。端口自动发现改由原生 DLL 提供；显式 `COM4` 始终可用。

### `cpp_analyzer` / `vision_runtime.dll`

视觉仓不定义通用键盘 SDK。它只增加“附加已有会话”的能力，并通过原生 HID C ABI发送鼠标移动和点击。

现有 `set_hid_port()` 和 `--hid-port` 保留为兼容模式：未附加会话时，视觉运行库可以创建并独占自己的原生会话。新 Python 调用端必须传入共享 `HidSession`，不能再同时传 `hid_port`。

### 父仓 `cs2-vision-trainer`

父仓负责：

- 在 `cs2_vision_runtime` 中接入并重新导出 `HidSession`。
- 验证两个 DLL、两个 ABI 和应用本地清单。
- 更新 Python 示例、接入文档、打包器和跨仓集成测试。
- 固定兼容的子模块提交。

## 原生 HID C ABI

首个共享会话 ABI 为 `1.0`。C 头文件至少提供：

```c
typedef struct Rp2350HidSession Rp2350HidSession;

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

int32_t rp2350_hid_get_abi_info(Rp2350HidAbiInfo* info);
int32_t rp2350_hid_session_create(
    const Rp2350HidOptions* options,
    Rp2350HidSession** session
);
int32_t rp2350_hid_session_open(Rp2350HidSession* session);
int32_t rp2350_hid_session_retain(Rp2350HidSession* session);
void rp2350_hid_session_release(Rp2350HidSession* session);
const char* rp2350_hid_last_error(void);
```

命令函数继续覆盖 ping、info、caps、文本、键盘、相对鼠标、按钮、滚轮、等待、脚本和 `stop_all`。所有函数用状态码返回错误；`rp2350_hid_last_error()` 是线程局部错误字符串，避免并发调用互相覆盖。

会话规则：

- `create` 建立对象和首个引用，但不打开串口；`open` 幂等。
- `retain`/`release` 管理跨 Python 和视觉 DLL的共享生命周期。
- 最后一个引用释放时，原生层尽力 `STOP_ALL`、停止心跳、取消 DTR并关闭串口。
- 普通命令共享一个递归事务锁，完整的“发送、等待匹配 ACK/NACK”不可交错。
- 心跳只共享底层写锁，不消费普通响应序列号。
- `run_script` 的一个批处理片段保持事务独占；实时瞄准期间调用端不应执行长脚本。
- 串口读写或协议状态不可恢复时，会话进入 `FAULTED`，停止接受新命令并触发关闭；不在底层自动重连。
- 关闭会等待活动命令离开，不能在线程仍读取旧会话时复用对象。

Python `HidSession.close()` 释放 Python 所持引用。若视觉运行库仍持有引用，物理会话保持到最后一个引用释放；因此错误的上下文嵌套不会产生悬空指针。推荐嵌套仍是 HID 在外、视觉运行时在内。

## 视觉 DLL 接口与所有权

视觉 C ABI 由 `2.0` 增量升级到 `2.1`，新增能力位 `VA_RUNTIME_FEATURE_SHARED_HID_SESSION` 和接口：

```c
typedef struct Rp2350HidSession Rp2350HidSession;

VA_API int32_t va_attach_hid_session(
    VaRuntime* runtime,
    Rp2350HidSession* session
);
```

规则：

- 只能在 `READY` 状态附加或替换会话。
- 非空会话在附加成功时由 `VaRuntime` `retain`；替换、解除附加或 `va_destroy()` 时 `release`。
- `NULL` 表示解除附加。
- 已附加会话时，`open_dxgi(..., dry_run=0)` 和 `va_calibrate_hid()` 使用该会话，不再打开 COM。
- 已附加会话时再设置或传入非空 `hid_port` 是调用错误，不能静默选择其一。
- 未附加会话时，原有端口模式仍由视觉运行库创建私有原生会话。
- `va_close()`/Python `reset()` 只关闭当前视觉处理会话，`VaRuntime` 的附加引用保留，以便重新打开；最终 Python `close()` 调用 `va_destroy()` 后才释放该引用。

视觉内部 `HidClient` 区分“共享引用”和“私有会话”，但两者都调用同一个 HID DLL。`RuntimeSession` 不再编入一份独立的 header-only 串口实现。

## Python 公共 API

调用端只需要 Python API：

```python
from cs2_vision_runtime import HidSession, VisionRuntime

with HidSession(
    "COM4",
    app_dir=app_dir,
    timeout=1.0,
    retries=2,
) as hid:
    with VisionRuntime.from_app_dir(
        app_dir,
        data_dir=data_dir,
        hid_session=hid,
    ) as runtime:
        ...
```

`cs2_vision_runtime` 依赖并重新导出第一方 `rp2350_hid_bridge` Python 包；最终 EXE冻结两个纯 Python 包。调用端也可以直接从 `rp2350_hid_bridge` 导入 `HidSession`。

`VisionRuntime` 增加：

```python
runtime.attach_hid_session(hid_session)
```

以及 `from_app_dir(..., hid_session=...)` 便利参数。Python 层在调用 C ABI前检查：

- `HidSession` 尚未关闭并已成功打开。
- 会话加载的 `rp2350_hid_bridge.dll` 与当前 app-local 清单声明的是同一个规范化绝对路径。
- HID ABI满足清单和视觉 DLL要求。
- 共享会话与 `hid_port` 参数不能同时出现。

不把原生句柄作为面向业务的整数属性公开；两个第一方包装包通过受控的内部绑定对象传递句柄。

## 同步、线程与阻塞

`VisionRuntime.process_next()` 和 `iter_actions()` 保持同步，不在 SDK 内新增后台推理线程。调用端若需要键盘逻辑与推理循环独立运行，使用两个 Python 线程：

- 视觉工作线程调用 `process_next()`。
- 控制线程调用同一个 `hid.key_down()` / `key_up()`。

包装层使用 `ctypes.CDLL`，原生调用期间释放 GIL。底层 `HidSession` 是命令线程安全的；两个线程只在实际串口请求/响应期间通过命令锁短暂串行。抓屏和 TensorRT 推理不占用 HID 命令锁，因此不会阻止控制线程发送键盘命令。

同一个 `VisionRuntime` 仍限定在单一工作线程使用。线程安全保证属于 `HidSession` 命令层，不扩展到视觉运行时状态机。

## 输出与全局释放语义

固件只有一份键盘和鼠标状态，`STOP_ALL` 必然是全局操作。必须遵守以下语义：

| 事件 | 鼠标自动输出 | 调用端保持的 `W` / Shift | 是否发送全局 `STOP_ALL` |
|---|---|---|---|
| `set_output_enabled(False)` | 立即停止后续移动/点击 | 保持 | 否 |
| `armed_output()` 退出 | 先关闭开火，再关闭移动输出 | 保持 | 否 |
| 共享模式下 `VisionRuntime.reset()` | 停止当前视觉会话，保留附加引用 | 保持 | 否 |
| 共享模式下 `VisionRuntime.close()` | 停止视觉会话并释放运行时引用 | 保持，除非这是 HID 最后一个引用 | 通常否；最后引用按会话终止路径释放 |
| 标定成功或失败返回 | 停止继续发送标定移动 | 保持 | 否 |
| 显式 `hid.stop_all()` | 停止 | 全部释放 | 是 |
| 最后一个 `HidSession` 引用关闭 | 停止 | 全部释放 | 尽力发送，然后断开 |
| 串口/DTR/USB断开 | 停止 | 全部释放 | 固件安全重置 |
| 两秒控制租约超时 | 停止 | 全部释放 | 固件安全重置 |

因此需要修改当前行为：

- `HidActionSender::set_enabled(false)` 只改变武装状态，不再调用 `stop_all()`。
- `VisionRuntime.armed_output()` 的 `finally` 只逐项关闭开火和移动输出，不再调用 `runtime.stop_all()`。
- 共享模式下视觉关闭、解除附加和标定清理不得全局释放键盘。
- `VisionRuntime.stop_all()` 只作为旧私有端口模式的兼容紧急接口保留；共享模式调用时明确报错并要求调用 `hid.stop_all()`。

相对鼠标移动和当前的点击命令本身不产生长期按住状态，所以停止继续发送即可完成视觉侧撤销。未来若视觉运行库引入 `mouse_down`，必须跟踪并只释放视觉自己持有的按钮，不能以 `STOP_ALL` 代替所有权管理。

## 应用本地打包

最终目录增加一个同级 DLL：

```text
MyClient/
├─ MyClient.exe
├─ vision_runtime.dll
├─ rp2350_hid_bridge.dll
└─ resources/
   └─ vision-runtime/
      ├─ runtime-manifest.json
      ├─ model/
      ├─ native/
      ├─ config/
      └─ licenses/
```

`runtime-manifest.json` 升级为版本 2，并增加：

- HID DLL文件名和 SHA256。
- HID C ABI 主/次版本。
- Python HID SDK最低/推荐版本。
- 视觉 DLL所需的共享会话能力位。

加载顺序固定为：验证清单与两个 DLL哈希、注册 app-local DLL目录、加载 HID DLL并握手、加载视觉 DLL并握手、验证传入会话来自同一个 HID DLL、最后附加会话。不得从系统 `PATH` 回退加载同名 HID DLL。

开发制品版本同步提升：

- `rp2350_hid_bridge.dll` ABI `1.0`。
- `rp2350_hid_bridge` Python SDK `0.2.0`。
- `vision_runtime.dll` ABI `2.1`。
- `cs2-vision-runtime-sdk` `0.3.0`。

两个 DLL、两个 Python wheel、资源清单和模型环境必须由同一发布流水线组装并测试。

## 错误处理

- COM 已被其他进程占用：`HidSession.open()` 失败，错误包含端口和 Win32错误，不创建视觉会话。
- HID ABI、路径或哈希不匹配：在附加前抛出兼容性异常，不把外部句柄交给视觉 DLL。
- 运行中串口故障：原生会话进入 `FAULTED`；当前命令失败，视觉 `process_next()` 或 Python键盘调用向上报告原始 HID错误。
- 同时传 `hid_session` 与 `hid_port`：Python层抛 `RuntimeStateError`，C ABI也做防御性拒绝。
- 调用端错误地先关闭 Python `HidSession`：只释放 Python引用；视觉引用仍有效，直到视觉运行时解除附加。
- 正常进程退出：上下文管理器/最终引用释放尽力 `STOP_ALL` 并关闭串口。
- 强制结束或进程崩溃：不能依赖 Python清理；固件两秒租约和 DTR/USB断开负责最终释放。

## 测试策略

### 原生 HID DLL

- C ABI 导出、ABI结构大小、空指针和版本握手。
- `create/open/retain/release` 引用计数和最后引用关闭。
- 两线程键盘/鼠标命令的帧、序列号和响应不交错。
- 心跳、普通命令、脚本事务、关闭和故障转换。
- 最后关闭尽力 `STOP_ALL`；非最后引用释放不关闭物理会话。
- 原有 C++ SDK测试继续通过，C++兼容包装只走 DLL核心。

### Python HID SDK

- 不安装 pyserial 也能导入和调用模拟 HID DLL。
- `HidSession` 上下文、异常映射、幂等关闭和线程并发。
- `HidBridge`/`HidBridgeOptions` 兼容入口。
- 显式 app-local DLL定位，不从 `PATH` 回退。

### 视觉 DLL

- `va_attach_hid_session` 的 retain/release、READY状态限制和空句柄防御。
- 附加会话与端口模式互斥。
- 共享会话用于实时移动和标定，不产生第二次 COM open。
- `set_output_enabled(false)`、`armed_output()`退出、标定退出和 runtime close 均不发送 `STOP_ALL`。
- 旧私有端口模式仍能打开、移动、关闭并在最后释放时全局停止。

### 跨仓集成

使用可观察的假串口执行以下顺序：

1. Python `hid.key_down("W")`。
2. 视觉运行时附加同一会话并发送鼠标移动。
3. 撤销 `armed_output()`，验证没有 `STOP_ALL` 或 `KEY_UP`。
4. 再发送 Python键盘命令，验证会话仍可用。
5. 关闭视觉运行时，验证 `W` 仍保持。
6. 调用 `hid.stop_all()`，此时才验证全局释放。

还要验证 manifest v2、两个 DLL哈希、冻结 EXE目录加载、Python双线程压力和真实 COM4硬件冒烟。

## 迁移与兼容

- 现有只使用 `VisionRuntime.set_hid_port("COM4")` 的调用端继续工作，但不能同时再创建 Python HID会话。
- 需要键盘和视觉并行的调用端迁移到 `HidSession(...); VisionRuntime.from_app_dir(..., hid_session=hid)`。
- 现有 `HidBridge` Python名称保留，内部从 pyserial 实现切换为原生 DLL。
- 旧 manifest v1和视觉 ABI 2.0不支持共享会话；新 SDK在启动时给出明确升级错误，不静默降级到双开 COM。
- 升级后的正式包始终携带两个同级 DLL，即使当前运行是 DXGI dry-run。

## 不在本次范围

- 把视觉推理改成 asyncio、回调或内建后台线程。
- 让多个进程共享同一个 RP2350会话。
- 修改固件协议命令、两秒租约或 HID状态模型。
- 账号、键位策略、移动逻辑或业务宏。
- 自动重连和断线后重放按键状态。
- 修改目标选择、模型推理、瞄准曲线或标定算法。

## 完成标准

- Python调用端能够用一个 `HidSession` 同时发送键盘，并供视觉 DLL发送鼠标。
- 同一进程只打开一次 COM，只有一个心跳、序列号和响应读取者。
- 视觉撤销输出、关闭或标定结束不会释放调用端保持的键。
- 显式 `hid.stop_all()`、整个 HID会话结束、连接断开或固件租约超时仍能全局安全释放。
- `process_next()` 保持同步；另一 Python线程可在推理期间通过同一会话发送键盘。
- 新 app-local 包包含并校验两个 DLL，调用端不需要 pyserial、全局 PATH或单独安装原生环境。
- C++、两个 Python SDK、视觉 C ABI、打包和跨仓测试全部通过。
