# 主控拥有的进程内 HID 中间件设计

## 状态

同进程方案 A 已获口头确认。本文件用于书面审阅；用户确认后再编写实施计划，不直接从本设计进入代码修改。

## 问题与设计修正

调用端是一个冻结为 Windows EXE 的 Python 主控程序。它需要同时：

- 通过 RP2350 控制业务键盘和鼠标输入；
- 调用 `vision_runtime.dll` 完成 DXGI、模型推理、标定、自动瞄准和自动开火。

物理 COM 口必须只有一个所有者，否则会出现重复打开、两个心跳、两个请求序列号和响应竞争。

此前设计虽然把 COM、心跳和协议状态统一进了 `rp2350_hid_bridge.dll`，但又让 `cs2-vision-runtime-sdk` 依赖并重新导出 `HidSession`，还让 `VisionRuntime.from_app_dir()` 直接接收具体的 Python HID 对象。这把主控编排职责放进了视觉 SDK，造成不必要的高层耦合。

修正后的原则是：

```text
板子中间件属于主控，不属于视觉 SDK。
视觉 DLL 只接受一个原生不透明句柄，不理解主控的 Python HID 类型。
```

## 采用的架构

采用同一主控进程内的 DLL 中间件，不创建独立 broker 进程：

```text
Python 主控 EXE
│
├─ rp2350-hid-bridge Python SDK
│  └─ rp2350_hid_bridge.dll
│     ├─ 唯一 COM 句柄
│     ├─ 唯一心跳、序列号和响应读取者
│     ├─ 键盘、鼠标、脚本和 STOP_ALL
│     └─ 引用计数 Rp2350HidSession*
│
└─ cs2-vision-runtime Python SDK
   └─ vision_runtime.dll
      └─ retain 主控传入的 Rp2350HidSession*
         └─ 只发送视觉产生的移动和点击命令
```

核心不变量：

```text
一个物理 COM 口 = 一个原生 Rp2350HidSession = 一个协议状态机
```

主控分别依赖两个独立 SDK，并负责将二者组装。视觉 SDK 不替主控创建、导入或管理板子 SDK。

## 方案比较

### 方案 1：显式不透明句柄（采用）

主控先创建并打开板子 session，再将 `native_handle` 和加载该句柄的 DLL 绝对路径传给视觉 SDK。视觉 DLL retain 句柄，使用完后 release。

优点：依赖显式、无全局状态、无 IPC、延迟最低、生命周期可测试。缺点：主控必须保持正确的上下文嵌套，并保证句柄来自同一份 DLL。

### 方案 2：命令回调表（暂不采用）

主控向视觉 DLL 传入 `mouse_move`、`mouse_click` 等函数指针和 context。它可让视觉 DLL 完全不链接 RP2350 DLL，但跨 DLL 回调、异常边界、线程和回调生命周期更复杂。当前只有一种板子中间件，没有必要为未知后端提前付出成本。

### 方案 3：DLL 内全局 session 注册表（拒绝）

主控注册名称，视觉端按名称查找。它隐藏了所有权，容易产生名称冲突、旧 session 复用和释放顺序问题，比显式依赖注入更难验证。

### 独立 broker 进程（本次不采用）

独立 EXE 通过命名管道或 RPC 接收命令，适合跨进程共享，但会增加部署、IPC 延迟、服务监控和新的故障面。当前主控与视觉 DLL 位于同一进程，不需要该复杂度。

## 仓库与组件边界

### `rp2350-hid-bridge-cpp`

该仓库交付独立中间件：

- `rp2350_hid_bridge.dll`、import library 和 C 头文件；
- 稳定 C ABI 1.0；
- 不透明 `Rp2350HidSession*`；
- COM、DTR、心跳、请求序号、响应读取、重试、命令锁和 FAULTED 状态；
- 键盘、鼠标、滚轮、脚本、标定所需移动和 `STOP_ALL`；
- `create/open/retain/release` 引用计数生命周期。

它不知道视觉模型、Python 主控或业务账号。

### `rp2350-hid-bridge-python`

这是主控单独使用的板子 SDK：

- 使用 `ctypes.CDLL` 包装 `rp2350_hid_bridge.dll`；
- 公开 `HidSession` 的完整键盘和鼠标 API；
- 公开只读的 `native_handle: int` 与 `dll_path: Path`，供主控把原生连接注入其他组件；
- 保持上下文管理、幂等关闭和故障上报；
- 不依赖视觉 SDK，也不提供视觉适配代码。

### `cpp_analyzer` / `vision_runtime.dll`

视觉仓只适配一个已经存在的中间件 session：

```c
typedef struct Rp2350HidSession Rp2350HidSession;

VA_API int32_t va_attach_hid_session(
    VaRuntime* runtime,
    Rp2350HidSession* session
);
```

规则：

- 只能在 `READY` 状态附加；
- 附加成功时 retain，`va_destroy()` 或显式解除时 release；
- `reset()` 只关闭当前视觉输入，保留附加引用；
- attached 模式下实时输出与标定均使用该 session，不打开第二个 COM；
- attached session 与旧 `hid_port` 私有模式互斥；
- 视觉撤销、reset、close 和标定清理不发送全局 `STOP_ALL`；
- 旧私有端口模式作为兼容路径保留。

视觉 DLL 可以链接 `rp2350_hid_bridge.dll` 的 C ABI，但不能依赖其 Python 包。

### `cs2-vision-runtime-sdk`

视觉 Python SDK保持独立、纯视觉职责：

- 不导入或重新导出 `HidSession`；
- 不声明 `rp2350-hid-bridge` wheel 依赖；
- `VisionRuntime.from_app_dir()` 不接收具体 HID Python 对象；
- 只把主控传入的原生值转发给 `va_attach_hid_session`。

公共接口：

```python
vision.attach_hid_session(
    board.native_handle,
    hid_dll_path=board.dll_path,
)
```

视觉 SDK只理解：

- 非零原生句柄；
- 中间件 DLL 的规范化绝对路径；
- manifest 中声明的 HID C ABI 与 DLL 哈希。

它不调用 `_binding_for_runtime()`，不检查 Python 对象类型，也不持有 Python `HidSession` 引用。生命周期由原生 retain/release 和主控上下文共同保证。

### `rp2350-keymouse-bridge-firmware`

固件业务代码不需要改变。继续保留协议 v2、两秒控制租约、DTR/USB 断开释放和紧急 `STOP_ALL`。仓库只固定经过验证的 C++/Python SDK gitlink。

## 主控公共用法

```python
from rp2350_hid_bridge import HidSession
from cs2_vision_runtime import VisionRuntime

with HidSession("COM4", app_dir=app_dir) as board:
    try:
        with VisionRuntime.from_app_dir(
            app_dir,
            data_dir=data_dir,
        ) as vision:
            vision.attach_hid_session(
                board.native_handle,
                hid_dll_path=board.dll_path,
            )

            board.key_down("W")

            vision.open_dxgi(
                adapter=0,
                output=0,
                player_side="ct",
                dry_run=False,
            )
            with vision.armed_output(fire=False):
                while vision.process_next() is not None:
                    pass

            board.key_up("W")
    finally:
        board.stop_all()
```

主控还可以直接调用 `board.mouse_move()`、`mouse_click()`、`run_script()` 等能力。视觉只是第二个命令生产者，不拥有中间件。

## 句柄、DLL 身份与安全校验

原生指针只能交给加载同一份 `rp2350_hid_bridge.dll` 的视觉 DLL。不同路径的两份 DLL 即使 ABI 相同，也可能拥有不同堆、全局注册状态和函数地址，不能交叉 retain/release。

因此 Python 接口同时要求 `native_handle` 和 `hid_dll_path`：

1. `VisionRuntime.from_app_dir()` 从 manifest 得到正式 HID DLL 绝对路径；
2. `attach_hid_session()` 对传入路径进行规范化；
3. 路径不一致时，在调用 C ABI前抛 `RuntimeCompatibilityError`；
4. 句柄为零时抛 `RuntimeStateError`；
5. C ABI再次验证句柄并执行 retain。

正式调用端必须让 `HidSession(..., app_dir=app_dir)` 与 `VisionRuntime.from_app_dir(app_dir, ...)` 使用同一个目录。

## 生命周期与停止语义

推荐所有权顺序：

```text
主控创建 board session（外层）
  → 创建 vision runtime（内层）
    → attach，vision retain
    → 运行推理/标定
    → vision close，release
  → 主控按业务需要 stop_all
→ board close，最后引用关闭 COM
```

| 事件 | 视觉输出 | 主控保持的 W/Shift | 全局 STOP_ALL |
|---|---|---|---|
| `armed_output()` 退出 | 关闭开火和自动移动 | 保持 | 否 |
| vision `reset()` | 停止当前视觉会话 | 保持 | 否 |
| vision `close()` | release 视觉引用 | 保持 | 否 |
| 标定结束或失败 | 停止标定移动 | 保持 | 否 |
| `board.stop_all()` | 停止 | 全部释放 | 是 |
| board 最后引用关闭 | 停止 | 全部释放 | 尽力发送后断开 |
| USB/DTR 断开或两秒租约超时 | 停止 | 全部释放 | 固件安全重置 |

共享模式下 `VisionRuntime.stop_all()` 不应成为公共正常路径；调用时明确提示由主控使用 `board.stop_all()`。旧私有端口模式可保留兼容行为。

## 同步与线程模型

`vision.process_next()` 保持同步。建议：

- 视觉工作线程调用 `process_next()`；
- 主控线程调用 `board.key_down()`、`key_up()` 或短鼠标命令。

`ctypes.CDLL` 原生调用期间释放 GIL。DXGI 与 TensorRT 推理不持有 HID 命令锁；只有实际的“发送请求 → 等待 ACK/NACK”往返进入同一个原生命令锁。因此键盘和视觉鼠标不会抢 COM、读线程或序列号。

长 `run_script()` 会占用命令序列并延迟实时瞄准，本次不设计优先级队列；实时阶段应使用短命令。

## 分发边界

最终 app-local 原生目录仍包含：

```text
MyClient.exe
vision_runtime.dll
rp2350_hid_bridge.dll
resources/vision-runtime/runtime-manifest.json
```

保留两份 DLL 是主控同时使用两个原生组件，不代表两个 Python SDK存在依赖。

分发规则修正为：

- `cs2-vision-runtime-sdk` wheel 恢复为零运行依赖，不携带或依赖 HID Python wheel；
- `rp2350-hid-bridge` wheel 由其自己的仓库独立构建和发布；
- 主控项目自行锁定并安装两个 wheel；
- 父仓的聚合诊断包可以同时复制两个独立 Python 包供示例使用，但不能把这种聚合写成视觉 SDK依赖。

manifest v2继续记录视觉 DLL和原生 HID DLL 的文件名、SHA256、ABI 2.1/1.0及能力位，因为 `vision_runtime.dll` 在运行时链接该原生组件。移除 HID Python SDK最低/推荐版本字段；Python包版本属于主控依赖锁，不属于视觉原生运行时契约。

## 错误处理

- 主控无法打开 COM：`HidSession.open()` 失败，vision 尚未 attach。
- 句柄为零或 session 已关闭：attach 失败，不进入 OPEN。
- HID DLL路径与 app-local manifest 不一致：Python层在 C 调用前拒绝。
- attached session 与 `hid_port` 同时配置：Python和 C ABI均拒绝。
- 运行中串口故障：原生 session 进入 FAULTED，不自动重连；键盘或视觉调用收到同一原始错误。
- 主控错误地先结束 Python对象：vision retain 仍保证原生对象存活，但推荐外层 board、内层 vision。
- 进程崩溃无法执行 Python清理：依赖 DTR/USB 断开和固件两秒租约最终释放。

## 需要撤回与保留的现有改动

### 保留

- `rp2350_hid_bridge.dll`、稳定 C ABI、原生 session、引用计数和 FAULTED状态；
- `va_attach_hid_session` 与 vision ABI 2.1；
- 单一 COM、心跳、序列号和响应读取；
- vision disarm 不发送全局 `STOP_ALL`；
- 两个 app-local DLL及其哈希/ABI校验；
- 固件安全租约和全部底层测试。

### 撤回或改造

- 删除 `cs2_vision_runtime.HidSession` 重导出；
- 删除 vision wheel 对 `rp2350-hid-bridge` 的依赖；
- 删除 `from_app_dir(..., hid_session=...)`；
- 将 `VisionRuntime.attach_hid_session(hid_object)` 改为原始 `native_handle + hid_dll_path`；
- 删除视觉 manifest 对 HID Python SDK版本的要求；
- 双 wheel 聚合构建恢复为各 SDK独立构建；
- 示例和文档改成主控分别导入两个独立 SDK并显式编排。

## 测试策略

### 原生中间件

- C ABI、retain/release、最后引用关闭和 FAULTED状态；
- 两线程键盘/鼠标命令不交错帧、响应和序列号；
- 真实 DLL导出和 ABI marker。

### 视觉 DLL

- attach 的 READY限制、空句柄、retain/release和私有端口互斥；
- attached session 用于标定与实时输出且不第二次打开 COM；
- disarm/reset/close/标定清理均不发送 `STOP_ALL`。

### Python SDK解耦

- `cs2-vision-runtime-sdk` 在未安装 `rp2350-hid-bridge` 时可以独立导入和运行 dry-run；
- wheel metadata 不含 `rp2350-hid-bridge`；
- `cs2_vision_runtime` 不导出 `HidSession`；
- raw handle与 DLL路径正确时 attach；路径不一致、零句柄或错误状态时拒绝；
- board SDK独立公开 `native_handle` 和 `dll_path`。

### 跨仓和硬件

1. 主控 `board.key_down("W")`；
2. vision attach 同一 handle 并发送鼠标移动；
3. vision disarm，验证 W仍保持且无 `STOP_ALL`；
4. 主控继续发送键盘和鼠标命令；
5. vision close，验证 board仍有效；
6. `board.stop_all()`，验证此时才全局释放；
7. 视觉线程阻塞在 `process_next()` 时，主控线程持续发送键盘命令，无超时、重复 COM或序列错误。

## 不在本次范围

- 独立 broker EXE、命名管道或 RPC；
- 回调 vtable和可插拔的未知 HID后端；
- 修改固件协议、租约或键位模型；
- 视觉推理异步化、优先级命令队列或自动重连；
- 模型、目标选择、瞄准曲线和光流标定算法。

## 完成标准

- 主控分别使用两个独立 Python SDK；视觉 SDK不导入、重导出或依赖板子 Python SDK；
- 主控唯一创建板子 session，并通过原生 handle显式注入 vision；
- 同一进程只打开一次 COM，所有命令共享同一原生协议状态机；
- 主控可独立发送键盘和鼠标，vision只发送自己的瞄准/点击命令；
- vision disarm/reset/close不会释放主控保持输入；
- 原生、两个 Python SDK、vision C ABI、打包和真实 COM硬件测试全部通过。
