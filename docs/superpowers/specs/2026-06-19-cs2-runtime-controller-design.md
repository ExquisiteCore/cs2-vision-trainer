# CS2 Runtime Controller Design

## Goal

Reposition the repository as two cooperating tools:

- Python package `cs2-vision-trainer`: build, review, label, validate, and train the YOLO model.
- C++ tool in `tools/cpp_analyzer`: load an exported model, detect enemy heads at runtime, track and smooth targets, plan relative mouse movement, and send movement/click commands through the RP2350 HID bridge SDK.

CSV and text action logs are no longer product outputs. The C++ runtime keeps only minimal console telemetry and an explicit dry-run mode for tuning.

## Current Context

The Python side already owns the dataset lifecycle and model training flow. It should stay focused on dataset generation, annotation, validation, training, export, and review.

The C++ side currently mixes three concerns: ONNX inference, offline reporting, and the first version of SDK action output. It still exposes `--output`, `--actions-output`, `CsvWriter`, and `ActionWriter`, which conflict with the new runtime-controller goal.

The SDK at `D:\project\pi\test\sdk\cpp` is header-only. It wraps a Windows serial client, `rp2350_hid_bridge::HidBridge`, which sends framed CDC commands to the RP2350 firmware. The firmware decodes `MouseMoveRel(dx, dy)`, splits the i16 movement into standard HID mouse reports with i8 x/y fields, and sends click reports by pressing a button, waiting, then releasing it.

## Architecture

The C++ runtime should be organized as a live control pipeline:

1. Capture video frames from a video source first, and later from a live capture source if needed.
2. Run ONNX/ORT detection.
3. Postprocess with class-aware NMS.
4. Track targets using IoU, center distance, velocity, and stability.
5. Select a target, prioritizing enemy heads.
6. Predict and filter the aim point.
7. Convert the target offset into a bounded relative HID mouse command.
8. Send `mouse_move(dx, dy)` and optional `mouse_click("left")` through the SDK.

The runtime must have two modes:

- `--hid-port COMx`: live SDK output.
- `--dry-run`: no SDK output, only console status. This mode is for calibration and test runs.

If neither `--hid-port` nor `--dry-run` is provided, the program should fail early with a clear error.

## Output Policy

Remove CSV as a first-class feature:

- Delete `CsvWriter` and CSV-specific CLI options.
- Delete `ActionWriter` and TXT action-log options.
- Remove README sections that describe CSV fields and action text logs.
- Keep console status such as frame count, detections, target id, lock state, movement delta, and SDK mode.

The C++ runtime should not write per-frame files unless a later explicit debugging feature adds that back.

## Control Planning

Add a testable control-planning unit between tracking and SDK output. It should accept a `FrameReport` and return a small command object:

```cpp
struct AimCommand {
    bool has_target = false;
    std::int16_t dx = 0;
    std::int16_t dy = 0;
    bool click_left = false;
    LockState lock_state = LockState::Idle;
};
```

Movement conversion:

- Use target offset from the predicted/filtered target pipeline.
- Apply `hid_move_gain`.
- Round to the nearest integer.
- Clamp each axis to `hid_max_step`.
- Drop zero movement.

Click conversion:

- Only click when `--hid-click` is enabled.
- Only click when `fire_candidate` is true.
- Enforce `hid_click_cooldown_frames`.

This logic must stay independent of the concrete SDK client so tests can use a recording fake client.

## SDK And Firmware Behavior

The SDK sends CDC commands; the RP2350 firmware emits standard USB HID mouse reports. Important implementation details:

- SDK `mouse_move(dx, dy)` encodes i16 relative movement.
- Firmware `move_mouse` splits large dx/dy into repeated i8 HID reports.
- Firmware `mouse_click(left)` sends press, waits `MOUSE_CLICK_DELAY_MS`, then release.
- Firmware `stop_all` releases keyboard and mouse buttons.
- The firmware does not implement acceleration or pointer curves. It only sends relative HID reports.

## Windows Mouse Acceleration

The controller must not assume that screen pixels map linearly to HID counts.

If the target program consumes normal Windows pointer movement, the Windows pointer speed and "Enhance pointer precision" setting may change the effective movement curve. If the target program consumes Raw Input, OS pointer acceleration is typically bypassed and the effective response is dominated by raw HID counts and in-game sensitivity.

The implementation should handle this by exposing runtime tuning knobs:

- `--hid-gain`
- `--hid-max-step`
- `--hid-click-cooldown`
- `--dry-run`

The first implementation should not try to read or mutate Windows pointer settings. Calibration belongs in runtime parameters and documentation.

## Testing

Required test coverage:

- Aim command generation from a target offset.
- Movement gain and clamp.
- No-target behavior.
- Click disabled by default.
- Click enabled with cooldown.
- CLI rejects missing `--hid-port` unless `--dry-run` is present.
- C++ build still succeeds with SDK include path.
- SDK protocol test still passes.

Manual hardware validation remains separate:

- Confirm the board is visible as a COM port.
- Run a dry-run video.
- Run live SDK movement with `--hid-click` absent.
- Enable click only after movement is calibrated.

## Out Of Scope

- Rewriting the Python trainer.
- Rewriting firmware.
- Changing Windows pointer settings programmatically.
- Adding a GUI for runtime tuning.
- Adding live game capture beyond the existing C++ video path.

