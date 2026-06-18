from pathlib import Path

from cs2_vision_trainer.gui import (
    DEFAULT_GUI_CONFIG,
    WORKFLOW_SECTIONS,
    GuiConfig,
    build_command,
    enemy_labels_for_player_side,
)


def test_default_gui_config_starts_from_clean_multiclass_training_paths():
    assert DEFAULT_GUI_CONFIG.video_path == Path("videos/01.mp4")
    assert DEFAULT_GUI_CONFIG.model_path == Path("models/base/yolov8n.pt")
    assert DEFAULT_GUI_CONFIG.dataset_root == Path("datasets/cs2_multiclass")
    assert DEFAULT_GUI_CONFIG.player_side == "unknown"
    assert DEFAULT_GUI_CONFIG.extract_start_seconds == 160
    assert DEFAULT_GUI_CONFIG.max_frames == 5000


def test_build_command_for_review_uses_selected_video_and_model():
    config = GuiConfig(
        video_path=Path("videos/xxx_01.mp4"),
        model_path=Path("runs/detect/train/weights/best.pt"),
        dataset_root=Path("datasets/cs2_multiclass"),
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
        dataset_root=Path("datasets/cs2_multiclass"),
        device="0",
    )

    command = build_command(config, "train")

    assert command == [
        "cs2-vision-trainer",
        "train",
        "--data",
        "datasets\\cs2_multiclass\\dataset.yaml",
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
        dataset_root=Path("datasets/cs2_multiclass"),
        device="0",
    )

    command = build_command(config, "annotate_mistakes")

    assert command == [
        "cs2-vision-trainer",
        "annotate",
        "--images",
        "datasets\\cs2_multiclass\\images\\raw",
        "--labels",
        "datasets\\cs2_multiclass\\labels\\raw",
        "--pattern",
        "xxx_01_error_*.jpg",
    ]


def test_build_command_for_annotate_extracted_filters_current_video_frames():
    config = GuiConfig(
        video_path=Path("videos/xxx_02.mp4"),
        model_path=Path("runs/detect/train-2/weights/best.pt"),
        dataset_root=Path("datasets/cs2_multiclass"),
        device="0",
    )

    command = build_command(config, "annotate_extracted")

    assert command == [
        "cs2-vision-trainer",
        "annotate",
        "--images",
        "datasets\\cs2_multiclass\\images\\raw",
        "--labels",
        "datasets\\cs2_multiclass\\labels\\raw",
        "--pattern",
        "xxx_02_frame_*.jpg",
    ]


def test_build_command_for_annotate_missing_filters_unlabeled_extracted_frames():
    config = GuiConfig(
        video_path=Path("videos/xxx_02.mp4"),
        model_path=Path("runs/detect/train-2/weights/best.pt"),
        dataset_root=Path("datasets/cs2_multiclass"),
        device="0",
    )

    command = build_command(config, "annotate_missing")

    assert command == [
        "cs2-vision-trainer",
        "annotate",
        "--images",
        "datasets\\cs2_multiclass\\images\\raw",
        "--labels",
        "datasets\\cs2_multiclass\\labels\\raw",
        "--pattern",
        "xxx_02_frame_*.jpg",
        "--missing-only",
    ]


def test_build_command_for_extract_frames_uses_selected_video_and_dataset_raw_images():
    config = GuiConfig(
        video_path=Path("videos/xxx_02.mp4"),
        model_path=Path("models/base/yolov8n.pt"),
        dataset_root=Path("datasets/cs2_multiclass"),
        device="0",
    )

    command = build_command(config, "extract_frames")

    assert command == [
        "cs2-vision-trainer",
        "extract-frames",
        "--video",
        "videos\\xxx_02.mp4",
        "--output",
        "datasets\\cs2_multiclass\\images\\raw",
        "--stride",
        "15",
        "--max-frames",
        "5000",
        "--start-time",
        "160",
    ]


def test_build_command_for_validate_dataset_uses_selected_dataset_root():
    config = GuiConfig(
        video_path=Path("videos/xxx_02.mp4"),
        model_path=Path("models/base/yolov8n.pt"),
        dataset_root=Path("datasets/cs2_multiclass"),
        device="0",
    )

    command = build_command(config, "validate")

    assert command == [
        "cs2-vision-trainer",
        "validate-dataset",
        "--root",
        "datasets\\cs2_multiclass",
    ]


def test_workflow_sections_are_ordered_as_training_pipeline():
    assert [section.title for section in WORKFLOW_SECTIONS] == [
        "1. 导入素材",
        "2. 标注样本",
        "3. 校验整理",
        "4. 训练测试",
    ]


def test_enemy_labels_for_player_side_maps_ct_to_t_targets():
    assert enemy_labels_for_player_side("ct") == ("t_body", "t_head")


def test_enemy_labels_for_player_side_maps_t_to_ct_targets():
    assert enemy_labels_for_player_side("t") == ("ct_body", "ct_head")


def test_enemy_labels_for_player_side_returns_empty_for_unknown():
    assert enemy_labels_for_player_side("unknown") == ()


def test_build_command_for_run_filters_opposite_team_when_player_side_is_ct():
    config = GuiConfig(
        video_path=Path("videos/xxx_01.mp4"),
        model_path=Path("runs/detect/train/weights/best.pt"),
        dataset_root=Path("datasets/cs2_multiclass"),
        device="0",
        player_side="ct",
    )

    command = build_command(config, "run")

    assert command == [
        "cs2-vision-trainer",
        "run",
        "--model",
        "runs\\detect\\train\\weights\\best.pt",
        "--source",
        "videos\\xxx_01.mp4",
        "--labels",
        "t_body",
        "t_head",
        "--device",
        "0",
    ]


def test_build_command_for_run_keeps_all_teams_when_player_side_is_unknown():
    config = GuiConfig(
        video_path=Path("videos/xxx_01.mp4"),
        model_path=Path("runs/detect/train/weights/best.pt"),
        dataset_root=Path("datasets/cs2_multiclass"),
        device="0",
        player_side="unknown",
    )

    command = build_command(config, "run")

    assert command == [
        "cs2-vision-trainer",
        "run",
        "--model",
        "runs\\detect\\train\\weights\\best.pt",
        "--source",
        "videos\\xxx_01.mp4",
        "--device",
        "0",
    ]
