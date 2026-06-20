from __future__ import annotations

import argparse
from pathlib import Path

from cs2_vision_runtime import VisionRuntime


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "runs" / "detect" / "train" / "weights" / "best.onnx"
DEFAULT_SCHEMA = ROOT / "runs" / "detect" / "train" / "weights" / "best.onnx.schema.json"
DEFAULT_VIDEO = ROOT / "videos" / "02.mp4"


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} 不存在: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Use Python SDK to run the C++ runtime on a video without moving the mouse.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--backend", default="opencv-onnx")
    parser.add_argument("--max-frames", type=int, default=300)
    parser.add_argument("--show-every", type=int, default=30)
    args = parser.parse_args()

    require_file(args.model, "ONNX 模型")
    require_file(args.schema, "模型 schema")
    require_file(args.video, "视频")

    with VisionRuntime() as runtime:
        runtime.set_model(args.model, schema_path=args.schema, backend=args.backend)
        runtime.set_frame_limits(max_frames=args.max_frames, warmup_frames=3)
        runtime.open_video(args.video, dry_run=True)

        print("Python 已经成功打开 C++ DLL，并开始处理视频。")
        print("dry_run=True，所以这里只打印规划结果，不会移动鼠标。")

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

    print("处理结束。")


if __name__ == "__main__":
    main()
