# RP2350 文档同步设计

## 目标

把固件仓库、HID Python SDK、视觉运行时合作方文档统一到已经实现的生产架构，并生成一份可单独发送的最新版接入文档，不重新制作环境 ZIP。

## 统一架构表述

- Python 主控是唯一 COM 所有者，只创建一个 `HidSession`。
- `rp2350_hid_bridge.dll` 唯一维护串口、协议 v2、心跳、序列号、ACK/NACK、命令锁和故障状态。
- HID Python SDK 与 Vision Python SDK 是两个独立 wheel，互不导入、互不重导出。
- 主控显式调用 `vision.attach_hid_session(board.native_handle, hid_dll_path=board.dll_path)`；不使用 `_binding_for_runtime()`，不手工加载 DLL，也不创建第二个 COM 客户端。
- 全局释放由主控调用 `board.stop_all()`；视觉 disarm/reset/close 只停止自身输出并释放自身引用。

## 文档范围

1. 固件根 README：把 C++ SDK 从“仅头文件”修正为共享库 SDK，并补充生产会话所有权。
2. HID Python SDK README/INTEGRATION：删除自动内部绑定和 `_binding_for_runtime()` 的旧描述，改为公开的 `native_handle + dll_path` 注入示例。
3. 合作方接入文档：增加当前固件要求、协议 v2、`ping/info/caps` 上线检查、COM 独占、两秒租约和四方向鼠标验收。
4. 环境目录：同步 `接入文档.md` 与 `docs/PARTNER_CONTROLLER_INTEGRATION.md`，更新 `ENVIRONMENT_PACKAGE.json` 中独立文档的大小和 SHA256；现有 ZIP 保持不变。

## 验证与提交

- 搜索并拒绝“仅头文件”“自动取得内部绑定”“`_binding_for_runtime()`”等过期表述。
- 运行 HID Python SDK 测试、固件测试、父仓文档契约及完整 pytest。
- 依次提交和推送 Python SDK、固件仓库、父仓，随后核对各仓库 `HEAD/main/origin/main/GitHub main` 与递归 gitlink。
- 校验独立接入文档与父仓正式文档内容一致，并核对环境元数据哈希。
