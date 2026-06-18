# CS2 Runtime Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the C++ tool from an offline analyzer/logger into a runtime controller that uses the trained YOLO model, tracking/filtering, and the RP2350 HID bridge SDK to move the mouse and optionally left-click.

**Architecture:** Keep Python focused on model training. In C++, remove CSV/TXT log outputs, add a testable aim-command planner, require either `--hid-port COMx` or `--dry-run`, and send bounded relative movement through the SDK. Keep Windows mouse acceleration handling as calibration parameters, not OS mutation.

**Tech Stack:** C++17, XMake, OpenCV DNN, ONNX Runtime, RP2350 HID Bridge C++ SDK, existing C++ algorithm tests.

---

## File Structure

- Modify `README.md`
  - Clarify Python trainer vs C++ runtime controller.
  - Remove read-only wording where it describes the new C++ runtime.
- Modify `tools/cpp_analyzer/README.md`
  - Rename purpose to runtime controller.
  - Remove CSV and action-log sections.
  - Add SDK runtime usage and Windows mouse acceleration calibration notes.
- Modify `tools/cpp_analyzer/xmake.lua`
  - Remove CSV/action writer source files from targets.
  - Keep SDK include detection through `RP2350_HID_BRIDGE_SDK`.
  - Optionally rename target to `vision_controller`; keep `vision_analyzer_tests` unless a full target rename is executed in one task.
- Modify `tools/cpp_analyzer/include/vision_analyzer/types.hpp`
  - Remove `output_path` and `actions_output_path`.
  - Keep HID options.
  - Add `dry_run` and status interval options.
- Create `tools/cpp_analyzer/include/vision_analyzer/aim_controller.hpp`
  - Owns `AimCommand`, `AimControllerOptions`, and `AimController`.
- Create `tools/cpp_analyzer/src/aim_controller.cpp`
  - Implements movement scaling, clamping, no-target behavior, and click cooldown.
- Modify `tools/cpp_analyzer/include/vision_analyzer/hid_output.hpp`
  - Keep SDK client abstraction.
  - Remove control-planning state from `HidActionSender` after `AimController` exists.
- Modify `tools/cpp_analyzer/src/hid_output.cpp`
  - Make it execute `AimCommand` only.
  - Keep `create_rp2350_hid_client`.
- Modify `tools/cpp_analyzer/src/main.cpp`
  - Remove `CsvWriter` and `ActionWriter`.
  - Add `--dry-run`.
  - Require `--hid-port` unless dry-run.
  - Print concise console status.
- Delete `tools/cpp_analyzer/include/vision_analyzer/csv_writer.hpp`
- Delete `tools/cpp_analyzer/src/csv_writer.cpp`
- Delete `tools/cpp_analyzer/include/vision_analyzer/action_writer.hpp`
- Delete `tools/cpp_analyzer/src/action_writer.cpp`
- Modify `tools/cpp_analyzer/tests/test_algorithms.cpp`
  - Remove action-writer tests.
  - Add aim-controller tests.
  - Keep tracking/filter/NMS tests.

---

### Task 1: Update Product Target Documentation

**Files:**
- Modify: `README.md`
- Modify: `tools/cpp_analyzer/README.md`

- [ ] **Step 1: Rewrite root README project summary**

Replace the opening summary with:

```markdown
# CS2 Vision Trainer

Two-part YOLO vision workflow for CS2 experiments:

- `cs2-vision-trainer` Python package: build datasets, label CT/T body/head boxes, validate labels, train/export YOLO models, and review model misses.
- `tools/cpp_analyzer` C++ runtime: load an exported model, detect enemy heads, track and filter target motion, plan relative mouse movement, and send movement/click commands through the RP2350 HID bridge SDK.
```

- [ ] **Step 2: Rewrite C++ README title and purpose**

Replace the first section of `tools/cpp_analyzer/README.md` with:

```markdown
# CS2 Vision C++ Runtime Controller

C++ runtime for exported YOLO models. It reads frames, runs visual detection,
tracks enemy head candidates, filters and predicts the target point, converts
the result into bounded relative mouse movement, and sends commands through the
RP2350 HID bridge SDK.

The Python project trains and exports the model. This C++ tool consumes that
model at runtime.
```

- [ ] **Step 3: Remove CSV/action-log documentation**

Delete these sections from `tools/cpp_analyzer/README.md`:

```text
Write an additional human-readable TXT action log:
Example action line:
CSV Fields
```

Delete command examples that use `--output` or `--actions-output`.

- [ ] **Step 4: Add runtime examples**

Add this section to `tools/cpp_analyzer/README.md`:

```markdown
## Runtime Modes

Dry-run prints status without sending SDK commands:

```powershell
xmake run vision_analyzer --backend opencv-onnx --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx --video D:\project\cs2-vision-trainer\videos\02.mp4 --dry-run --preview
```

Live SDK movement:

```powershell
xmake run vision_analyzer --backend opencv-onnx --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx --video D:\project\cs2-vision-trainer\videos\02.mp4 --hid-port COM3 --hid-gain 1.0 --hid-max-step 120 --preview
```

Enable left-click candidates only after movement is calibrated:

```powershell
xmake run vision_analyzer --backend opencv-onnx --model D:\project\cs2-vision-trainer\runs\detect\train\weights\best.onnx --video D:\project\cs2-vision-trainer\videos\02.mp4 --hid-port COM3 --hid-click --hid-click-cooldown 6
```
```

- [ ] **Step 5: Add Windows mouse acceleration note**

Add:

```markdown
## Windows Mouse Acceleration

The RP2350 firmware sends standard relative USB HID mouse reports. It does not
apply a pointer curve. If the target program consumes normal Windows pointer
movement, Windows pointer speed and Enhance Pointer Precision can affect the
effective movement. If the target program consumes Raw Input, OS pointer
acceleration is typically bypassed and the result is dominated by HID counts and
in-application sensitivity.

Tune `--hid-gain` and `--hid-max-step` for the actual environment. The runtime
does not read or modify Windows pointer settings.
```

- [ ] **Step 6: Commit documentation update**

```powershell
git add README.md tools/cpp_analyzer/README.md
git commit -m "docs: retarget project as runtime controller"
```

---

### Task 2: Add Aim Controller Tests First

**Files:**
- Modify: `tools/cpp_analyzer/tests/test_algorithms.cpp`
- Create: `tools/cpp_analyzer/include/vision_analyzer/aim_controller.hpp`
- Create: `tools/cpp_analyzer/src/aim_controller.cpp`

- [ ] **Step 1: Add include for the new test**

In `tools/cpp_analyzer/tests/test_algorithms.cpp`, add:

```cpp
#include "vision_analyzer/aim_controller.hpp"
```

- [ ] **Step 2: Add failing test for movement scaling and clamp**

Add this test:

```cpp
void test_aim_controller_scales_and_clamps_target_offset() {
    AimControllerOptions options;
    options.move_gain = 0.5F;
    options.max_step = 12;
    options.click_enabled = false;
    AimController controller(options);

    FrameReport report{
        42,
        1400.0,
        120.0,
        InferenceTiming{1.0, 2.0, 3.0},
        1,
        TargetFrame{
            9,
            Detection{1, "ct_head", 0.91F, cv::Rect(950, 520, 40, 40)},
            {970.0F, 540.0F},
            {978.0F, 542.0F},
            {30.0F, -10.0F},
            31.62F,
            false,
            {976.0F, 541.0F},
            {120.0F, 6.0F},
            {10.0F, 1.0F},
            0.82F,
            2.24F,
            LockState::Locked,
            true,
        },
    };

    const AimCommand command = controller.plan(report);

    require(command.has_target, "aim command should mark target as present");
    require(command.dx == 12, "aim command should clamp scaled x movement");
    require(command.dy == -5, "aim command should scale y movement");
    require(!command.click_left, "aim command should not click when clicks are disabled");
}
```

- [ ] **Step 3: Add failing test for no target**

Add:

```cpp
void test_aim_controller_holds_when_no_target() {
    AimController controller;
    FrameReport report{};

    const AimCommand command = controller.plan(report);

    require(!command.has_target, "aim command should hold when no target exists");
    require(command.dx == 0, "aim command should not move x without target");
    require(command.dy == 0, "aim command should not move y without target");
    require(!command.click_left, "aim command should not click without target");
}
```

- [ ] **Step 4: Add failing test for click cooldown**

Add:

```cpp
void test_aim_controller_respects_click_cooldown() {
    AimControllerOptions options;
    options.click_enabled = true;
    options.click_cooldown_frames = 2;
    AimController controller(options);

    FrameReport report{
        1,
        33.0,
        120.0,
        InferenceTiming{},
        1,
        TargetFrame{
            3,
            Detection{1, "ct_head", 0.95F, cv::Rect(950, 520, 40, 40)},
            {970.0F, 540.0F},
            {960.0F, 540.0F},
            {0.0F, 0.0F},
            0.0F,
            false,
            {960.0F, 540.0F},
            {0.0F, 0.0F},
            {0.0F, 0.0F},
            0.90F,
            0.0F,
            LockState::Locked,
            true,
        },
    };

    const AimCommand first = controller.plan(report);
    const AimCommand second = controller.plan(report);
    const AimCommand third = controller.plan(report);

    require(first.click_left, "first fire candidate should click");
    require(!second.click_left, "second frame should be blocked by cooldown");
    require(!third.click_left, "third frame should still be blocked while cooldown counts down");
}
```

- [ ] **Step 5: Register tests in `main`**

Call the tests:

```cpp
test_aim_controller_scales_and_clamps_target_offset();
test_aim_controller_holds_when_no_target();
test_aim_controller_respects_click_cooldown();
```

- [ ] **Step 6: Run test to verify failure**

Run:

```powershell
xmake run vision_analyzer_tests
```

Expected: compile failure because `vision_analyzer/aim_controller.hpp` does not exist.

---

### Task 3: Implement Aim Controller

**Files:**
- Create: `tools/cpp_analyzer/include/vision_analyzer/aim_controller.hpp`
- Create: `tools/cpp_analyzer/src/aim_controller.cpp`
- Modify: `tools/cpp_analyzer/xmake.lua`

- [ ] **Step 1: Create header**

Create `tools/cpp_analyzer/include/vision_analyzer/aim_controller.hpp`:

```cpp
#pragma once

#include <cstdint>

#include "vision_analyzer/types.hpp"

namespace vision_analyzer {

struct AimCommand {
    bool has_target = false;
    std::int16_t dx = 0;
    std::int16_t dy = 0;
    bool click_left = false;
    LockState lock_state = LockState::Idle;
};

struct AimControllerOptions {
    float move_gain = 1.0F;
    int max_step = 120;
    bool click_enabled = false;
    int click_cooldown_frames = 6;
};

class AimController {
public:
    explicit AimController(AimControllerOptions options = {});

    [[nodiscard]] AimCommand plan(const FrameReport& report);

private:
    AimControllerOptions options_;
    int click_cooldown_remaining_ = 0;
};

}  // namespace vision_analyzer
```

- [ ] **Step 2: Create implementation**

Create `tools/cpp_analyzer/src/aim_controller.cpp`:

```cpp
#include "vision_analyzer/aim_controller.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace vision_analyzer {
namespace {

[[nodiscard]] std::int16_t scaled_step(float value, float gain, int max_step) {
    const int limited_max = std::clamp(max_step, 0, static_cast<int>(std::numeric_limits<std::int16_t>::max()));
    const int rounded = static_cast<int>(std::lround(value * gain));
    return static_cast<std::int16_t>(std::clamp(rounded, -limited_max, limited_max));
}

void validate_options(const AimControllerOptions& options) {
    if (!std::isfinite(options.move_gain)) {
        throw std::runtime_error("aim move gain must be finite");
    }
    if (options.max_step < 0) {
        throw std::runtime_error("aim max step must be greater than or equal to 0");
    }
    if (options.click_cooldown_frames < 0) {
        throw std::runtime_error("aim click cooldown must be greater than or equal to 0");
    }
}

}  // namespace

AimController::AimController(AimControllerOptions options)
    : options_(options) {
    validate_options(options_);
}

AimCommand AimController::plan(const FrameReport& report) {
    if (click_cooldown_remaining_ > 0) {
        --click_cooldown_remaining_;
    }

    if (!report.target.has_value()) {
        return {};
    }

    const auto& target = *report.target;
    AimCommand command;
    command.has_target = true;
    command.dx = scaled_step(target.offset.x, options_.move_gain, options_.max_step);
    command.dy = scaled_step(target.offset.y, options_.move_gain, options_.max_step);
    command.lock_state = target.lock_state;

    if (options_.click_enabled && target.fire_candidate && click_cooldown_remaining_ == 0) {
        command.click_left = true;
        click_cooldown_remaining_ = options_.click_cooldown_frames;
    }

    return command;
}

}  // namespace vision_analyzer
```

- [ ] **Step 3: Add file to test target**

Modify `tools/cpp_analyzer/xmake.lua` test target:

```lua
add_files("src/types.cpp", "src/postprocess.cpp", "src/tracking.cpp", "src/hid_output.cpp", "src/aim_controller.cpp")
```

- [ ] **Step 4: Run tests**

Run:

```powershell
xmake run vision_analyzer_tests
```

Expected: aim-controller tests pass. Any action-writer tests still present may fail after later removal, so do not delete action writer yet in this task.

- [ ] **Step 5: Commit**

```powershell
git add tools/cpp_analyzer/include/vision_analyzer/aim_controller.hpp tools/cpp_analyzer/src/aim_controller.cpp tools/cpp_analyzer/tests/test_algorithms.cpp tools/cpp_analyzer/xmake.lua
git commit -m "feat: add aim command planner"
```

---

### Task 4: Simplify HID Output To Execute Aim Commands

**Files:**
- Modify: `tools/cpp_analyzer/include/vision_analyzer/hid_output.hpp`
- Modify: `tools/cpp_analyzer/src/hid_output.cpp`
- Modify: `tools/cpp_analyzer/tests/test_algorithms.cpp`

- [ ] **Step 1: Add HID executor test**

Replace the existing `test_hid_action_sender_maps_target_offset_to_mouse_move_and_click` with:

```cpp
void test_hid_action_sender_executes_aim_command() {
    RecordingHidClient client;
    HidActionSender sender(client);

    sender.execute(AimCommand{
        true,
        12,
        -5,
        true,
        LockState::Locked,
    });

    require(client.moves.size() == 1, "HID sender should emit one relative move");
    require(client.moves[0].first == 12, "HID sender should forward x movement");
    require(client.moves[0].second == -5, "HID sender should forward y movement");
    require(client.left_clicks == 1, "HID sender should forward click command");
}
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
xmake run vision_analyzer_tests
```

Expected: compile failure because `HidActionSender::execute(AimCommand)` does not exist.

- [ ] **Step 3: Modify header**

Change `HidActionSender` in `hid_output.hpp` to:

```cpp
class HidActionSender {
public:
    explicit HidActionSender(HidClient& client);

    void execute(const AimCommand& command);
    void stop_all();

private:
    HidClient& client_;
};
```

Add include:

```cpp
#include "vision_analyzer/aim_controller.hpp"
```

Remove `HidActionOptions` from `hid_output.hpp`.

- [ ] **Step 4: Modify implementation**

Replace `HidActionSender` implementation in `hid_output.cpp` with:

```cpp
HidActionSender::HidActionSender(HidClient& client)
    : client_(client) {}

void HidActionSender::execute(const AimCommand& command) {
    if (!command.has_target) {
        return;
    }
    if (command.dx != 0 || command.dy != 0) {
        client_.move_relative(command.dx, command.dy);
    }
    if (command.click_left) {
        client_.click_left();
    }
}

void HidActionSender::stop_all() {
    client_.stop_all();
}
```

Remove `scaled_step`, `validate_options`, `HidActionOptions`, and cooldown fields from `hid_output.cpp`.

- [ ] **Step 5: Run tests**

Run:

```powershell
xmake run vision_analyzer_tests
```

Expected: tests pass.

- [ ] **Step 6: Commit**

```powershell
git add tools/cpp_analyzer/include/vision_analyzer/hid_output.hpp tools/cpp_analyzer/src/hid_output.cpp tools/cpp_analyzer/tests/test_algorithms.cpp
git commit -m "refactor: separate aim planning from hid output"
```

---

### Task 5: Remove CSV And TXT Writers

**Files:**
- Delete: `tools/cpp_analyzer/include/vision_analyzer/csv_writer.hpp`
- Delete: `tools/cpp_analyzer/src/csv_writer.cpp`
- Delete: `tools/cpp_analyzer/include/vision_analyzer/action_writer.hpp`
- Delete: `tools/cpp_analyzer/src/action_writer.cpp`
- Modify: `tools/cpp_analyzer/tests/test_algorithms.cpp`
- Modify: `tools/cpp_analyzer/xmake.lua`

- [ ] **Step 1: Remove action writer test and include**

From `tools/cpp_analyzer/tests/test_algorithms.cpp`, remove:

```cpp
#include "vision_analyzer/action_writer.hpp"
```

Remove the entire function:

```cpp
void test_action_writer_outputs_human_readable_move_and_click_candidate()
```

Remove its call from `main`.

- [ ] **Step 2: Delete writer files**

Delete:

```text
tools/cpp_analyzer/include/vision_analyzer/csv_writer.hpp
tools/cpp_analyzer/src/csv_writer.cpp
tools/cpp_analyzer/include/vision_analyzer/action_writer.hpp
tools/cpp_analyzer/src/action_writer.cpp
```

- [ ] **Step 3: Remove writer files from xmake**

Ensure `tools/cpp_analyzer/xmake.lua` has no references to:

```text
csv_writer.cpp
action_writer.cpp
```

The test target should include:

```lua
add_files("src/types.cpp", "src/postprocess.cpp", "src/tracking.cpp", "src/hid_output.cpp", "src/aim_controller.cpp")
```

- [ ] **Step 4: Run tests**

Run:

```powershell
xmake run vision_analyzer_tests
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tools/cpp_analyzer
git commit -m "refactor: remove offline action logs"
```

---

### Task 6: Make Runtime CLI Require HID Or Dry Run

**Files:**
- Modify: `tools/cpp_analyzer/include/vision_analyzer/types.hpp`
- Modify: `tools/cpp_analyzer/src/main.cpp`
- Modify: `tools/cpp_analyzer/xmake.lua`

- [ ] **Step 1: Update options**

In `types.hpp`, replace output fields with:

```cpp
bool dry_run = false;
int status_every_frames = 30;
```

Keep:

```cpp
std::string hid_port;
float hid_move_gain = 1.0F;
int hid_max_step = 120;
bool hid_click_enabled = false;
int hid_click_cooldown_frames = 6;
```

- [ ] **Step 2: Remove output args from parser**

In `main.cpp`, remove parse branches:

```cpp
} else if (key == "--output") {
    options.output_path = require_value(key);
} else if (key == "--actions-output") {
    options.actions_output_path = require_value(key);
```

Add:

```cpp
} else if (key == "--dry-run") {
    options.dry_run = true;
} else if (key == "--status-every") {
    options.status_every_frames = std::stoi(require_value(key));
```

- [ ] **Step 3: Add runtime validation**

Add helper near `parse_args`:

```cpp
void validate_options(const Options& options) {
    if (options.hid_port.empty() && !options.dry_run) {
        throw std::runtime_error("use --hid-port COMx for live SDK output or --dry-run for tuning");
    }
    if (options.status_every_frames <= 0) {
        throw std::runtime_error("--status-every must be greater than 0");
    }
}
```

Call after parsing in `main`:

```cpp
const auto options = vision_analyzer::parse_args(argc, argv);
vision_analyzer::validate_options(options);
vision_analyzer::run(options);
```

- [ ] **Step 4: Remove writer construction**

Delete from `run`:

```cpp
CsvWriter writer(options.output_path);
writer.write_header();
std::unique_ptr<ActionWriter> action_writer;
if (!options.actions_output_path.empty()) {
    action_writer = std::make_unique<ActionWriter>(options.actions_output_path);
}
```

Delete per-frame calls:

```cpp
writer.write_report(report);
if (action_writer) {
    action_writer->write_report(report);
}
```

- [ ] **Step 5: Add aim controller and SDK execution**

In `run`, create:

```cpp
AimController aim_controller(AimControllerOptions{
    options.hid_move_gain,
    options.hid_max_step,
    options.hid_click_enabled,
    options.hid_click_cooldown_frames,
});
```

Create SDK only when not dry-run:

```cpp
std::unique_ptr<HidClient> hid_client;
std::unique_ptr<HidActionSender> hid_sender;
if (!options.dry_run) {
    hid_client = create_rp2350_hid_client(options.hid_port);
    hid_sender = std::make_unique<HidActionSender>(*hid_client);
}
```

After `report` is complete:

```cpp
const AimCommand command = aim_controller.plan(report);
if (hid_sender) {
    hid_sender->execute(command);
}
if (processed_index % options.status_every_frames == 0) {
    std::cout << "frame=" << report.frame_index
              << " det=" << report.detection_count
              << " target=" << (command.has_target ? 1 : 0)
              << " dx=" << command.dx
              << " dy=" << command.dy
              << " click=" << (command.click_left ? 1 : 0)
              << " lock=" << lock_state_name(command.lock_state)
              << '\n';
}
```

- [ ] **Step 6: Update help text**

Help text must include:

```text
vision_analyzer --backend opencv-onnx --model best.onnx --video input.mp4 (--hid-port COMx | --dry-run) [--preview]
  --dry-run       run detection and planning without SDK output
  --status-every N print one status line every N processed frames, default 30
```

Remove help text for `--output` and `--actions-output`.

- [ ] **Step 7: Run build**

Run:

```powershell
xmake
xmake run vision_analyzer --help
```

Expected: build succeeds and help shows `--dry-run` but not `--output` or `--actions-output`.

- [ ] **Step 8: Commit**

```powershell
git add tools/cpp_analyzer/include/vision_analyzer/types.hpp tools/cpp_analyzer/src/main.cpp tools/cpp_analyzer/xmake.lua
git commit -m "feat: require hid output or dry run"
```

---

### Task 7: Update C++ Runtime Tests And Verification

**Files:**
- Modify: `tools/cpp_analyzer/tests/test_algorithms.cpp`
- Modify: `tools/cpp_analyzer/README.md`

- [ ] **Step 1: Confirm C++ algorithm tests**

Run:

```powershell
xmake run vision_analyzer_tests
```

Expected:

```text
algorithm tests passed
```

- [ ] **Step 2: Confirm C++ build**

Run:

```powershell
xmake
```

Expected:

```text
build ok
```

- [ ] **Step 3: Confirm help text**

Run:

```powershell
xmake run vision_analyzer --help
```

Expected help text includes:

```text
--dry-run
--hid-port COMx
--hid-gain 1.0
--hid-max-step N
--hid-click
```

Expected help text does not include:

```text
--output
--actions-output
CSV
```

- [ ] **Step 4: Confirm SDK protocol test**

Run:

```powershell
D:\project\pi\test\sdk\cpp\build\Debug\test_protocol.exe
```

Expected:

```text
C++ SDK protocol tests passed
```

- [ ] **Step 5: Confirm Python trainer tests**

Run from repository root:

```powershell
uv run pytest
```

Expected:

```text
49 passed
```

- [ ] **Step 6: Commit verification cleanup**

Only commit if files changed in this task:

```powershell
git add tools/cpp_analyzer/tests/test_algorithms.cpp tools/cpp_analyzer/README.md
git commit -m "test: verify runtime controller flow"
```

---

### Task 8: Hardware Calibration Checklist

**Files:**
- Modify: `tools/cpp_analyzer/README.md`

- [ ] **Step 1: Add calibration section**

Add:

```markdown
## Hardware Calibration Checklist

1. Confirm the board appears as a COM port.
2. Run `--dry-run --preview` on a representative video.
3. Run live movement without `--hid-click`.
4. Start with a low gain such as `--hid-gain 0.25`.
5. Increase `--hid-gain` until the filtered target point converges without oscillation.
6. Reduce `--hid-max-step` if movement jumps too far per frame.
7. Enable `--hid-click` only after movement is stable.
8. If movement differs between desktop and target application, treat that as a Raw Input or pointer-acceleration difference and calibrate gain for the target application.
```

- [ ] **Step 2: Commit docs**

```powershell
git add tools/cpp_analyzer/README.md
git commit -m "docs: add runtime controller calibration checklist"
```

---

## Self-Review

- Spec coverage: The plan covers project retargeting, CSV/TXT removal, SDK runtime mode, dry-run mode, aim-command planning, Windows acceleration notes, and verification.
- Placeholder scan: No placeholder tokens or vague test instructions are present.
- Type consistency: `AimCommand`, `AimControllerOptions`, `AimController`, `HidActionSender::execute`, and `Options` fields are used consistently across tasks.
