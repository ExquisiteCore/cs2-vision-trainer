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
    parser = argparse.ArgumentParser(description="Use Python SDK to run DXGI screen capture without moving the mouse.")
    parser.add_argument(
        "--app-dir",
        type=Path,
        help="frozen client directory containing vision_runtime.dll and resources",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="caller-owned writable data directory; required with --app-dir",
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--backend", default="opencv-onnx")
    parser.add_argument("--adapter", type=int, default=0)
    parser.add_argument("--output", type=int, default=0)
    parser.add_argument("--player-side", choices=["unknown", "ct", "t"], default="ct")
    parser.add_argument("--max-frames", type=int, default=300)
    parser.add_argument("--show-every", type=int, default=30)
    args = parser.parse_args()

    if args.app_dir is not None and args.data_dir is None:
        parser.error("--data-dir is required with --app-dir")

    if args.app_dir is not None:
        runtime = VisionRuntime.from_app_dir(
            args.app_dir.resolve(),
            data_dir=args.data_dir.resolve(),
        )
    else:
        require_file(args.model, "ONNX 模型")
        require_file(args.schema, "模型 schema")
        runtime = VisionRuntime()
        try:
            runtime.set_model(
                args.model,
                schema_path=args.schema,
                backend=args.backend,
            )
        except BaseException:
            runtime.close()
            raise

    with runtime:
        runtime.set_frame_limits(max_frames=args.max_frames, warmup_frames=3)
        runtime.open_dxgi(
            adapter=args.adapter,
            output=args.output,
            player_side=args.player_side,
            dry_run=True,
        )

        print("Python 已经通过 C++ DLL 打开 DXGI 屏幕输入。")
        print("dry_run=True，所以这里只打印规划结果，不会移动鼠标。")

        for action in runtime.iter_actions():
            if action.frame_index % args.show_every == 0:
                print(
                    f"frame={action.frame_index} "
                    f"target={int(action.has_target)} "
                    f"dx={action.dx} dy={action.dy} "
                    f"click={int(action.click_left)} "
                    f"lock={action.lock_state.name} "
                    f"det={action.detection_count}"
                )

    print("处理结束。")


if __name__ == "__main__":
    main()
