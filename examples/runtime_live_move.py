from __future__ import annotations

import argparse
from pathlib import Path

from cs2_vision_runtime import VisionRuntime


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_MODEL = ROOT / "model" / "best.onnx"
PACKAGE_SCHEMA = ROOT / "model" / "best.onnx.schema.json"
DEFAULT_MODEL = PACKAGE_MODEL if PACKAGE_MODEL.exists() else ROOT / "runs" / "detect" / "train" / "weights" / "best.onnx"
DEFAULT_SCHEMA = PACKAGE_SCHEMA if PACKAGE_SCHEMA.exists() else ROOT / "runs" / "detect" / "train" / "weights" / "best.onnx.schema.json"
DEFAULT_CALIBRATION_PATH = ROOT / "hid-calibration.json"


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} 不存在: {path}")


def process_loop(runtime: VisionRuntime, show_every: int) -> None:
    while True:
        action = runtime.process_next()
        if action is None:
            return
        if action.frame_index % show_every == 0:
            print(
                f"frame={action.frame_index} target={int(action.has_target)} "
                f"dx={action.dx} dy={action.dy} click={int(action.click_left)} "
                f"lock={action.lock_state.name} det={action.detection_count}"
            )


def run_armed_loop(
    runtime: VisionRuntime,
    *,
    fire_enabled: bool,
    show_every: int,
) -> None:
    try:
        runtime.set_output_enabled(True)
        runtime.set_fire_enabled(fire_enabled)
        process_loop(runtime, show_every)
    finally:
        try:
            runtime.set_fire_enabled(False)
        finally:
            try:
                runtime.set_output_enabled(False)
            finally:
                runtime.stop_all()


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
    parser = argparse.ArgumentParser(description="Use Python SDK to run DXGI live movement through the RP2350 board.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--backend", default="ort-tensorrt")
    parser.add_argument("--adapter", type=int, default=0)
    parser.add_argument("--output", type=int, default=0)
    parser.add_argument("--player-side", choices=["ct", "t"], default="ct")
    parser.add_argument("--hid-port", required=True, help="board serial port, for example COM3")
    parser.add_argument(
        "--calibration-path",
        type=Path,
        default=DEFAULT_CALIBRATION_PATH,
        help="调用端选择的单个本地标定文件",
    )
    parser.add_argument(
        "--recalibrate",
        action="store_true",
        help="由调用端显式要求忽略有效缓存并重新标定",
    )
    parser.add_argument("--click", action="store_true", help="让 DLL 自动开火")
    parser.add_argument(
        "--enable-live-output",
        action="store_true",
        help="确认允许 RP2350 真实移动与按键输出",
    )
    parser.add_argument("--show-every", type=int, default=30)
    args = parser.parse_args()

    if not args.enable_live_output:
        print("未提供 --enable-live-output；没有标定，也没有开启任何物理输出。")
        return

    require_file(args.model, "ONNX 模型")
    require_file(args.schema, "模型 schema")

    with VisionRuntime() as runtime:
        runtime.set_model(args.model, schema_path=args.schema, backend=args.backend)
        runtime.set_hid_port(args.hid_port)
        print("正在读取调用端指定的本地标定；仅在缺失或显式重标定时移动视角……")
        profile = load_or_calibrate(
            runtime,
            args.calibration_path,
            recalibrate=args.recalibrate,
            adapter=args.adapter,
            output=args.output,
        )
        print(
            f"标定完成 quality={profile.quality:.3f} noise={profile.noise_px:.3f} "
            f"samples={profile.accepted_samples}"
        )
        runtime.set_fire_policy(
            body_enabled=True,
            head_confidence=0.35,
            body_confidence=0.45,
            cooldown_frames=3,
        )
        runtime.open_dxgi(
            adapter=args.adapter,
            output=args.output,
            player_side=args.player_side,
            hid_port=args.hid_port,
            dry_run=False,
        )

        print("DXGI 已打开；现在由 Python 分别解锁移动输出和自动开火。")
        print(f"fire_enabled={int(args.click)}；按 Ctrl+C 会在 finally 中撤销输出。")
        run_armed_loop(runtime, fire_enabled=args.click, show_every=args.show_every)


if __name__ == "__main__":
    main()
