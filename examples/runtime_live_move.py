from __future__ import annotations

import argparse
import os
from pathlib import Path

from cs2_vision_runtime import VisionRuntime
from rp2350_hid_bridge import HidSession


DEFAULT_DATA_DIR = Path(
    os.environ.get("LOCALAPPDATA", Path.cwd() / "data")
) / "CS2VisionClient"


def process_loop(vision: VisionRuntime, show_every: int) -> None:
    while True:
        action = vision.process_next()
        if action is None:
            return
        if action.frame_index % show_every == 0:
            print(
                f"frame={action.frame_index} target={int(action.has_target)} "
                f"dx={action.dx} dy={action.dy} click={int(action.click_left)} "
                f"lock={action.lock_state.name} det={action.detection_count}"
            )


def run_armed_loop(
    vision: VisionRuntime,
    *,
    fire_enabled: bool,
    show_every: int,
) -> None:
    with vision.armed_output(fire=fire_enabled):
        process_loop(vision, show_every)


def load_or_calibrate(
    runtime: VisionRuntime,
    calibration_path: Path,
    *,
    recalibrate: bool,
    adapter: int,
    output: int,
):
    runtime.set_hid_calibration_path(calibration_path)
    cached = runtime.get_hid_calibration()
    if cached.valid and not recalibrate:
        print(f"已加载本地标定，不移动鼠标: {calibration_path}")
        return cached
    print("开始调用 DLL 标定；成功后会原子保存到本地……")
    return runtime.calibrate_hid(adapter=adapter, output=output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run app-local DXGI aim through one caller-owned RP2350 HID session."
    )
    parser.add_argument(
        "--app-dir",
        type=Path,
        required=True,
        help="directory containing both runtime DLLs and resources",
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--adapter", type=int, default=0)
    parser.add_argument("--output", type=int, default=0)
    parser.add_argument("--player-side", choices=["ct", "t"], default="ct")
    parser.add_argument("--hid-port", required=True, help="board serial port, for example COM4")
    parser.add_argument(
        "--calibration-path",
        type=Path,
        help="caller-owned calibration file; defaults below data-dir",
    )
    parser.add_argument(
        "--recalibrate",
        action="store_true",
        help="explicitly ignore a valid cached calibration and recalibrate",
    )
    parser.add_argument("--click", action="store_true", help="allow automatic fire")
    parser.add_argument(
        "--enable-live-output",
        action="store_true",
        help="confirm physical RP2350 mouse output",
    )
    parser.add_argument("--show-every", type=int, default=30)
    args = parser.parse_args()

    if args.show_every <= 0:
        parser.error("--show-every must be greater than zero")
    if not args.enable_live_output:
        print("未提供 --enable-live-output；没有打开 COM、标定或物理输出。")
        return

    app_dir = args.app_dir.resolve()
    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    calibration_path = (
        args.calibration_path.resolve()
        if args.calibration_path is not None
        else data_dir / "hid-calibration.json"
    )

    with HidSession(args.hid_port, app_dir=app_dir) as board:
        try:
            with VisionRuntime.from_app_dir(
                app_dir,
                data_dir=data_dir,
            ) as vision:
                vision.attach_hid_session(
                    board.native_handle,
                    hid_dll_path=board.dll_path,
                )
                print("一个 COM 口已由调用端打开，并共享给 vision_runtime.dll。")
                print("正在读取本地标定；仅在缺失或显式重标定时移动视角……")
                profile = load_or_calibrate(
                    vision,
                    calibration_path,
                    recalibrate=args.recalibrate,
                    adapter=args.adapter,
                    output=args.output,
                )
                print(
                    f"标定完成 quality={profile.quality:.3f} "
                    f"noise={profile.noise_px:.3f} samples={profile.accepted_samples}"
                )
                vision.set_fire_policy(
                    body_enabled=True,
                    head_confidence=0.35,
                    body_confidence=0.45,
                    cooldown_frames=3,
                )
                vision.open_dxgi(
                    adapter=args.adapter,
                    output=args.output,
                    player_side=args.player_side,
                    dry_run=False,
                )

                print("DXGI 已打开；Ctrl+C 只撤销视觉输出，随后结束整个 HID 会话。")
                with vision.armed_output(fire=args.click):
                    process_loop(vision, args.show_every)
        finally:
            board.stop_all()


if __name__ == "__main__":
    main()
