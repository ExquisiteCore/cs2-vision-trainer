from __future__ import annotations

import argparse
from pathlib import Path

from cs2_vision_runtime import VisionRuntime


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "runs" / "detect" / "train" / "weights" / "best.onnx"
DEFAULT_SCHEMA = ROOT / "runs" / "detect" / "train" / "weights" / "best.onnx.schema.json"


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} 不存在: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Use Python SDK to run DXGI live movement through the RP2350 board.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--backend", default="opencv-onnx")
    parser.add_argument("--adapter", type=int, default=0)
    parser.add_argument("--output", type=int, default=0)
    parser.add_argument("--player-side", choices=["ct", "t"], default="ct")
    parser.add_argument("--hid-port", required=True, help="board serial port, for example COM3")
    parser.add_argument("--gain", type=float, default=0.5)
    parser.add_argument("--max-step", type=int, default=80)
    parser.add_argument("--deadzone", type=float, default=2.0)
    parser.add_argument("--click", action="store_true", help="enable left click output")
    parser.add_argument("--show-every", type=int, default=30)
    args = parser.parse_args()

    require_file(args.model, "ONNX 模型")
    require_file(args.schema, "模型 schema")

    with VisionRuntime() as runtime:
        runtime.set_model(args.model, schema_path=args.schema, backend=args.backend)
        runtime.set_hid_tuning(gain=args.gain, max_step=args.max_step, deadzone_px=args.deadzone)
        runtime.set_hid_click(args.click, cooldown_frames=6)
        runtime.open_dxgi(
            adapter=args.adapter,
            output=args.output,
            player_side=args.player_side,
            hid_port=args.hid_port,
            dry_run=False,
        )

        print("Python 已经通过 C++ DLL 打开 DXGI，并会通过板子移动鼠标。")
        print(f"click={int(args.click)}；默认不加 --click 就不会左键。")

        while True:
            action = runtime.process_next()
            if action is None:
                break

            if action.frame_index % args.show_every == 0:
                print(
                    f"frame={action.frame_index} "
                    f"target={int(action.has_target)} "
                    f"dx={action.dx} dy={action.dy} "
                    f"click={int(action.click_left)} "
                    f"lock={action.lock_state.name} "
                    f"det={action.detection_count}"
                )


if __name__ == "__main__":
    main()
