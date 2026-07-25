# C++ 与 Python 板控 SDK 详细接入指南设计

## 目标

分别为 RP2350 HID 桥接器的 C++ SDK 和 Python SDK 编写一份独立、完整的中文接入指南，使应用开发者无需阅读 SDK 内部实现或协议帧细节，也能完成板卡发现、连接、键鼠控制、脚本批处理、异常处理和安全退出。

## 目标读者

文档面向在 Windows 应用中接入 ExquisiteCore RP2350 KeyMouse Bridge 的开发者。读者应具备基础 C++17/CMake 或 Python 3.10+ 使用经验，但不要求了解串口帧协议、固件内部状态机或 USB HID 实现。

## 文件组织

新增两份独立指南：

- C++ SDK：`tools/rp2350_hid_bridge_cpp/INTEGRATION.md`
- Python SDK：`tools/rp2350_keymouse_bridge_firmware/sdk/python/INTEGRATION.md`

更新两个 SDK 的 `README.md`，在开头概览之后增加“详细接入指南”链接。文档放在各 SDK 仓库根目录，保证开发者单独拉取任一 SDK 时可以直接发现。

父仓和固件仓只更新必要的子模块 gitlink，不重复复制接入指南正文。

## 内容边界

### 包含

- 固件、板卡和 Windows 环境前置条件
- SDK 安装、构建和项目引用方式
- COM 口枚举、自动发现和显式端口选择
- 不产生键鼠输入的最小连通测试
- 键盘、鼠标、滚轮、等待、文本和 `STOP_ALL` API
- 脚本语法、批处理边界和执行保证
- 可直接改造的完整应用接入模板
- 超时、`BUSY`、`NACK`、参数错误和断线处理
- 心跳、DTR、并发、关闭/重新打开和会话代次语义
- 正常退出与异常退出时的输入释放
- 常见问题、调试顺序和生产接入检查清单

### 不包含

- 自定义串口传输层实现
- 协议帧编码、CRC 和底层协议扩展教程
- 固件修改、刷写实现或 USB 描述符开发
- GUI、WebUI 或特定业务应用架构
- 自动瞄准、模型推理或 C++ 视觉运行时集成

## 两份指南的统一结构

1. 适用场景与安全提示
2. 固件和板卡前置条件
3. 安装或构建 SDK
4. 查找串口与确认设备
5. 最小连通测试
6. 直接控制 API
7. 脚本批处理接入
8. 完整应用接入模板
9. 错误处理与恢复
10. 心跳、DTR、线程安全与会话生命周期
11. 正常退出和异常退出
12. 常见问题
13. 生产接入检查清单

统一术语沿用现有中文用户文档：运行时、固件、主机、桥接器、载荷、心跳、批处理、试运行、子模块。API、类名、方法名、命令、路径、协议常量和硬件型号保持原样。

## C++ 指南特有内容

- 说明 SDK 为仅头文件 C++17 库，默认真实串口传输层只支持 Windows。
- 给出 `add_subdirectory` 与手动 `target_include_directories` 两种 CMake 接入方式。
- 使用不固定生成器的 `cmake -S . -B build`，让 CMake 选择本机已安装工具链。
- 解释 `HidBridgeOptions` 的 `port`、`baud`、`timeout_ms`、`retries` 和 `heartbeat_interval_ms`。
- 最小连通测试只调用 `open()`、`ping()`、`info()`、`caps()` 和 `close()`。
- 完整模板使用命令行 `--run COMx` 作为真实输入授权，展示异常捕获、显式 `stop_all()`、`close()` 和析构兜底。
- 说明 `TimeoutError`、`std::invalid_argument` 和其他 `std::runtime_error` 的处理边界。
- 说明所有命令和脚本事务的串行化、关闭时的代次失效，以及旧脚本不会进入新会话。

## Python 指南特有内容

- 使用 `uv sync` 安装依赖，并说明从固件仓执行 `uv sync --project sdk/python` 的方式。
- 说明 `port=None` 按 VID/PID `CAFE:2350` 自动发现，也可显式传入 `COM3`。
- 解释 `HidBridgeOptions` 的 `port`、`baudrate`、`timeout`、`retries`、`vid` 和 `pid`。
- 最小连通测试使用上下文管理器，只调用 `ping()`、`info()` 和 `caps()`。
- 完整模板使用 `argparse --run` 作为真实输入授权，使用 `with HidBridge(...)` 管理会话，并在 `finally` 中调用 `stop_all()`。
- 说明 `TimeoutError`、`ValueError` 和 `RuntimeError` 的常见来源与恢复策略。
- 说明上下文管理器、心跳线程、命令锁、关闭/重新打开和旧会话失效行为。

## 示例与安全边界

每份指南包含两套自包含示例：

1. 最小连通测试只读取设备信息，不产生键盘或鼠标报告。
2. 完整接入模板只有在显式传入 `--run` 后才执行真实输入。

完整模板必须满足：

- 默认不产生真实键鼠输入。
- 在真实输入前明确提示活动窗口风险。
- 捕获异常并输出可诊断错误。
- 成功、失败和提前退出路径都尝试执行 `stop_all()`。
- C++ 模板最终调用 `close()`；Python 模板使用上下文管理器完成关闭。
- 不把析构或上下文退出描述为绝对可靠的进程崩溃保护；进程丢失时的最终保护来自固件的两秒控制租约和 DTR/USB 安全重置。

应用数据流统一描述为：

`应用程序 → C++/Python SDK → CDC 串口 → RP2350 固件 → USB HID 键盘/鼠标 → 操作系统`

## 错误处理设计

两份指南使用统一问题分类，并映射到各语言的实际异常类型：

| 场景 | C++ | Python | 建议处理 |
|---|---|---|---|
| 找不到端口 | 打开时抛出 `std::runtime_error` | 自动发现失败时抛出 `RuntimeError` | 检查固件、USB 枚举、COM 口和 VID/PID |
| 端口占用或串口失败 | `std::runtime_error` | pyserial 异常或 `RuntimeError` | 关闭其他客户端后重新打开 |
| 响应超时 | `TimeoutError` | `TimeoutError` | 记录错误，关闭旧会话，确认连接后重试 |
| 固件 `BUSY` 重试耗尽 | `std::runtime_error` | `RuntimeError` | 等待当前操作结束，不并发创建第二客户端 |
| 固件 `NACK` | `std::runtime_error`，包含错误名和编号 | `RuntimeError`，包含错误名和编号 | 修正命令、参数或固件/SDK 版本 |
| 参数无效 | `std::invalid_argument` | `ValueError` | 在发送前修正组合键、文本、滚轮或数值范围 |
| 会话已关闭或被重新打开 | `std::runtime_error` | `RuntimeError` | 停止旧任务，只在新会话重新提交 |

文档不建议在未知执行状态下盲目无限重试。SDK 已负责协议 v2 允许的超时与 `BUSY` 重试；上层应用应在最终失败后关闭会话、检查设备状态，再由明确的业务逻辑决定是否重连。

## 验证与提交顺序

1. 编写 C++ `INTEGRATION.md` 并更新 C++ SDK `README.md`。
2. 检查示例只使用当前公开 API，运行 CMake 构建和 `ctest`。
3. 提交并推送 C++ SDK。
4. 编写 Python `INTEGRATION.md` 并更新 Python SDK `README.md`。
5. 检查示例只使用 `__all__` 导出的 API，运行 39 项 SDK 单元测试。
6. 提交并推送 Python SDK。
7. 在固件仓从远程更新 `sdk/cpp`，同时记录新的 `sdk/python` gitlink。
8. 验证两份 C++ SDK 指向同一提交，运行固件无硬件测试并提交、推送固件仓。
9. 更新父仓的直接 C++ SDK 与固件 gitlink，运行父仓测试并提交、推送。
10. 检查 Markdown 围栏、README 相对链接、残留英文、所有仓库清洁状态和固件 CI。

## 完成标准

- 两个 SDK 仓库各有一份可独立阅读的中文 `INTEGRATION.md`。
- 两个 README 都能直接进入对应详细接入指南。
- 两份指南均包含安全的最小连通测试和带显式武装条件的完整模板。
- 示例、异常类型和生命周期说明与当前代码一致。
- 文档不展开协议底层和自定义传输层内容。
- 两份 C++ SDK gitlink 一致，父仓与固件仓可递归拉取全部新文档。
- SDK、固件和父仓相关测试通过，固件 CI 成功。
