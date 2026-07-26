# RP2350 Documentation Synchronization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正所有已发现的 RP2350 旧架构文档，补齐合作方板子上线说明，并交付可独立发送的最新版 Markdown 文档。

**Architecture:** 以“主控唯一拥有 `HidSession`，视觉运行时只接收公开的原生 handle/path”为唯一文档契约。子仓库先提交，父仓随后更新 gitlink 和合作方文档，环境目录只同步文档而不重新打包。

**Tech Stack:** Markdown、Python SDK 文档契约测试、pytest、Rust cargo test、Git submodules。

---

### Task 1: 修正固件与 HID SDK 文档

**Files:**
- Modify: `tools/rp2350_keymouse_bridge_firmware/README.md`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/README.md`
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/INTEGRATION.md`

- [ ] **Step 1:** 将固件 README 的“仅头文件 SDK”改为共享库 SDK，并说明一个 COM 只允许一个原生 session。
- [ ] **Step 2:** 将 Python SDK 文档改为主控显式读取 `native_handle`、`dll_path` 并调用 `vision.attach_hid_session()`。
- [ ] **Step 3:** 搜索确认生产文档不再出现 `_binding_for_runtime()` 或“视觉 SDK 自动取得内部绑定”。
- [ ] **Step 4:** 运行 `uv run --project sdk/python python -m unittest discover -s sdk/python/tests -v` 和固件主机测试。

### Task 2: 补齐合作方接入文档

**Files:**
- Modify: `docs/PARTNER_CONTROLLER_INTEGRATION.md`
- Modify: `tests/test_runtime_sdk_docs.py`

- [ ] **Step 1:** 增加固件版本、USB 复合设备、协议 v2 和中间件职责说明。
- [ ] **Step 2:** 增加 `ping/info/caps` 上线检查和禁止并发打开 COM 的说明。
- [ ] **Step 3:** 增加正负 X/Y 四方向小幅移动与 `stop_all()` 验收步骤。
- [ ] **Step 4:** 扩充文档契约断言并先验证针对旧文档失败、更新后通过。
- [ ] **Step 5:** 运行父仓完整 `uv run --extra dev pytest -q`。

### Task 3: 按依赖顺序提交并推送

**Files:**
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware/sdk/python`
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware`

- [ ] **Step 1:** 在 Python SDK `main` 提交文档并推送。
- [ ] **Step 2:** 在固件 `main` 提交 README 和 Python SDK gitlink 并推送。
- [ ] **Step 3:** 在父仓 `main` 提交合作方文档、测试、设计/计划和固件 gitlink 并推送。
- [ ] **Step 4:** 比较所有仓库的 HEAD、local main、origin/main、GitHub main 和递归 gitlink。

### Task 4: 更新独立交付文档

**Files:**
- Modify: `dist/releases/cs2-vision-controller-environment-sm61-0.3.0/接入文档.md`
- Modify: `dist/releases/cs2-vision-controller-environment-sm61-0.3.0/docs/PARTNER_CONTROLLER_INTEGRATION.md`
- Modify: `dist/releases/cs2-vision-controller-environment-sm61-0.3.0/ENVIRONMENT_PACKAGE.json`

- [ ] **Step 1:** 将父仓最新版合作方文档同步到两个环境目录文档位置。
- [ ] **Step 2:** 更新独立文档大小和 SHA256 元数据。
- [ ] **Step 3:** 验证三份 Markdown 字节一致，元数据与文件一致。
- [ ] **Step 4:** 保持现有 ZIP 不变，向用户提供独立 `接入文档.md` 的绝对路径。
