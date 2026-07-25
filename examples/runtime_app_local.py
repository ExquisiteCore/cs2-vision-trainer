from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cs2_vision_runtime import VisionRuntime


DEFAULT_APP_DIR = Path(sys.executable).resolve().parent
DEFAULT_DATA_DIR = Path(
    os.environ.get("LOCALAPPDATA", DEFAULT_APP_DIR / "data")
) / "CS2VisionClient"


def print_action(action) -> None:
    print(
        f"frame={action.frame_index} target={int(action.has_target)} "
        f"dx={action.dx} dy={action.dy} click={int(action.click_left)} "
        f"lock={action.lock_state.name} det={action.detection_count} "
        f"inference_ms={action.inference_ms:.2f} total_ms={action.total_ms:.2f}"
    )


def process_actions(runtime: VisionRuntime, show_every: int) -> None:
    for action in runtime.iter_actions():
        if action.frame_index % show_every == 0:
            print_action(action)


def load_or_calibrate(
    runtime: VisionRuntime,
    calibration_path: Path,
    *,
    recalibrate: bool,
    adapter: int,
    output: int,
):
    runtime.set_hid_calibration_path(calibration_path)
    profile = runtime.get_hid_calibration()
    if profile.valid and not recalibrate:
        print(f"已加载标定文件，不移动视角: {calibration_path}")
        return profile
    print("开始执行受控灵敏度标定；成功后由 DLL 原子保存……")
    return runtime.calibrate_hid(adapter=adapter, output=output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the frozen-client app-local vision runtime package."
    )
    parser.add_argument("--app-dir", type=Path, default=DEFAULT_APP_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--adapter", type=int, default=0)
    parser.add_argument("--output", type=int, default=0)
    parser.add_argument("--player-side", choices=["ct", "t"], default="ct")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--show-every", type=int, default=30)
    parser.add_argument("--hid-port", help="RP2350 serial port, for example COM4")
    parser.add_argument("--calibration-path", type=Path)
    parser.add_argument("--recalibrate", action="store_true")
    parser.add_argument("--click", action="store_true")
    parser.add_argument("--enable-live-output", action="store_true")
    args = parser.parse_args()

    if args.show_every <= 0:
        parser.error("--show-every must be greater than zero")
    if args.enable_live_output and not args.hid_port:
        parser.error("--hid-port is required with --enable-live-output")

    app_dir = args.app_dir.resolve()
    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    calibration_path = (
        args.calibration_path.resolve()
        if args.calibration_path is not None
        else data_dir / "hid-calibration.json"
    )

    with VisionRuntime.from_app_dir(app_dir, data_dir=data_dir) as runtime:
        runtime.set_frame_limits(max_frames=args.max_frames, warmup_frames=3)
        runtime.set_fire_policy(
            body_enabled=True,
            head_confidence=0.35,
            body_confidence=0.45,
            cooldown_frames=3,
        )

        if args.enable_live_output:
            runtime.set_hid_port(args.hid_port)
            profile = load_or_calibrate(
                runtime,
                calibration_path,
                recalibrate=args.recalibrate,
                adapter=args.adapter,
                output=args.output,
            )
            print(
                f"标定 quality={profile.quality:.3f} "
                f"noise={profile.noise_px:.3f} samples={profile.accepted_samples}"
            )

        runtime.open_dxgi(
            adapter=args.adapter,
            output=args.output,
            player_side=args.player_side,
            dry_run=not args.enable_live_output,
        )

        if args.enable_live_output:
            print("真实输出已显式解锁；退出时 SDK 会撤销开火、移动并 stop_all。")
            with runtime.armed_output(fire=args.click):
                process_actions(runtime, args.show_every)
        else:
            print("DXGI dry-run：未选择 HID 端口，不会产生鼠标或按键输出。")
            process_actions(runtime, args.show_every)


if __name__ == "__main__":
    main()
