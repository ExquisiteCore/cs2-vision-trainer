from pathlib import Path

from cs2_vision_trainer.gui import GuiConfig, build_command


def test_build_command_for_review_uses_selected_video_and_model():
    config = GuiConfig(
        video_path=Path("videos/xxx_01.mp4"),
        model_path=Path("runs/detect/train/weights/best.pt"),
        dataset_root=Path("datasets/cs2_enemy"),
        device="0",
    )

    command = build_command(config, "review")

    assert command == [
        "cs2-vision-trainer",
        "review",
        "--model",
        "runs\\detect\\train\\weights\\best.pt",
        "--video",
        "videos\\xxx_01.mp4",
        "--name",
        "xxx_01",
        "--device",
        "0",
    ]


def test_build_command_for_training_continues_from_selected_model():
    config = GuiConfig(
        video_path=Path("videos/xxx_01.mp4"),
        model_path=Path("runs/detect/train/weights/best.pt"),
        dataset_root=Path("datasets/cs2_enemy"),
        device="0",
    )

    command = build_command(config, "train")

    assert command == [
        "cs2-vision-trainer",
        "train",
        "--data",
        "datasets\\cs2_enemy\\dataset.yaml",
        "--model",
        "runs\\detect\\train\\weights\\best.pt",
        "--epochs",
        "40",
        "--imgsz",
        "640",
        "--batch",
        "8",
        "--device",
        "0",
    ]


def test_build_command_for_annotate_mistakes_filters_current_video_errors():
    config = GuiConfig(
        video_path=Path("videos/xxx_01.mp4"),
        model_path=Path("runs/detect/train/weights/best.pt"),
        dataset_root=Path("datasets/cs2_enemy"),
        device="0",
    )

    command = build_command(config, "annotate_mistakes")

    assert command == [
        "cs2-vision-trainer",
        "annotate",
        "--images",
        "datasets\\cs2_enemy\\images\\raw",
        "--labels",
        "datasets\\cs2_enemy\\labels\\raw",
        "--pattern",
        "xxx_01_error_*.jpg",
    ]
