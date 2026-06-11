from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog
from tkinter.scrolledtext import ScrolledText


@dataclass(frozen=True)
class GuiConfig:
    video_path: Path
    model_path: Path
    dataset_root: Path
    device: str = "0"
    epochs: int = 40
    image_size: int = 640
    batch_size: int = 8


def _path_text(path: Path) -> str:
    return str(path)


def build_command(config: GuiConfig, action: str) -> list[str]:
    dataset_yaml = config.dataset_root / "dataset.yaml"
    raw_images = config.dataset_root / "images" / "raw"
    raw_labels = config.dataset_root / "labels" / "raw"
    command = ["cs2-vision-trainer"]
    if action == "review":
        return [
            *command,
            "review",
            "--model",
            _path_text(config.model_path),
            "--video",
            _path_text(config.video_path),
            "--name",
            config.video_path.stem,
            "--device",
            config.device,
        ]
    if action == "annotate":
        return [
            *command,
            "annotate",
            "--images",
            _path_text(raw_images),
            "--labels",
            _path_text(raw_labels),
        ]
    if action == "prepare":
        return [
            *command,
            "prepare-dataset",
            "--root",
            _path_text(config.dataset_root),
            "--val-ratio",
            "0.2",
            "--empty-limit",
            "100",
            "--seed",
            "7",
        ]
    if action == "train":
        return [
            *command,
            "train",
            "--data",
            _path_text(dataset_yaml),
            "--model",
            _path_text(config.model_path),
            "--epochs",
            str(config.epochs),
            "--imgsz",
            str(config.image_size),
            "--batch",
            str(config.batch_size),
            "--device",
            config.device,
        ]
    if action == "run":
        return [
            *command,
            "run",
            "--model",
            _path_text(config.model_path),
            "--source",
            _path_text(config.video_path),
            "--labels",
            "enemy",
            "--device",
            config.device,
        ]
    raise ValueError(f"unknown GUI action: {action}")


class TrainerGui:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("CS2 Vision Trainer")
        self.root.geometry("920x620")
        self.video_var = tk.StringVar(value="videos\\xxx_01.mp4")
        self.model_var = tk.StringVar(value="runs\\detect\\train\\weights\\best.pt")
        self.dataset_var = tk.StringVar(value="datasets\\cs2_enemy")
        self.device_var = tk.StringVar(value="0")
        self.epochs_var = tk.StringVar(value="40")
        self.imgsz_var = tk.StringVar(value="640")
        self.batch_var = tk.StringVar(value="8")
        self._build_layout()

    def _build_layout(self) -> None:
        container = tk.Frame(self.root, padx=14, pady=14)
        container.pack(fill=tk.BOTH, expand=True)

        self._row_file(container, 0, "Video", self.video_var, self._pick_video)
        self._row_file(container, 1, "Model", self.model_var, self._pick_model)
        self._row_file(container, 2, "Dataset", self.dataset_var, self._pick_dataset)
        self._row_entry(container, 3, "Device", self.device_var, width=8)
        self._row_entry(container, 4, "Epochs", self.epochs_var, width=8)
        self._row_entry(container, 5, "Image size", self.imgsz_var, width=8)
        self._row_entry(container, 6, "Batch", self.batch_var, width=8)

        button_frame = tk.Frame(container)
        button_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(12, 8))
        buttons = [
            ("Review mistakes", "review"),
            ("Annotate images", "annotate"),
            ("Prepare dataset", "prepare"),
            ("Train", "train"),
            ("Test video", "run"),
        ]
        for index, (label, action) in enumerate(buttons):
            tk.Button(
                button_frame,
                text=label,
                command=lambda selected=action: self._run_action(selected),
                width=18,
            ).grid(row=0, column=index, padx=(0, 8), pady=4)

        utility_frame = tk.Frame(container)
        utility_frame.grid(row=8, column=0, columnspan=3, sticky="ew")
        tk.Button(utility_frame, text="Open dataset folder", command=self._open_dataset_folder).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )
        tk.Button(utility_frame, text="Clear log", command=self._clear_log).pack(side=tk.LEFT)

        self.log = ScrolledText(container, height=18)
        self.log.grid(row=9, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        container.columnconfigure(1, weight=1)
        container.rowconfigure(9, weight=1)

    def _row_file(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
        command,
    ) -> None:
        tk.Label(parent, text=label, width=12, anchor="w").grid(row=row, column=0, sticky="w", pady=4)
        tk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        tk.Button(parent, text="Browse", command=command, width=10).grid(row=row, column=2, padx=(8, 0), pady=4)

    def _row_entry(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
        *,
        width: int,
    ) -> None:
        tk.Label(parent, text=label, width=12, anchor="w").grid(row=row, column=0, sticky="w", pady=4)
        tk.Entry(parent, textvariable=variable, width=width).grid(row=row, column=1, sticky="w", pady=4)

    def _pick_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Select video",
            filetypes=[("Videos", "*.mp4 *.avi *.mkv"), ("All files", "*.*")],
        )
        if path:
            self.video_var.set(path)

    def _pick_model(self) -> None:
        path = filedialog.askopenfilename(
            title="Select model",
            filetypes=[("YOLO models", "*.pt *.onnx *.engine"), ("All files", "*.*")],
        )
        if path:
            self.model_var.set(path)

    def _pick_dataset(self) -> None:
        path = filedialog.askdirectory(title="Select dataset root")
        if path:
            self.dataset_var.set(path)

    def _config(self) -> GuiConfig:
        return GuiConfig(
            video_path=Path(self.video_var.get()),
            model_path=Path(self.model_var.get()),
            dataset_root=Path(self.dataset_var.get()),
            device=self.device_var.get().strip() or "0",
            epochs=int(self.epochs_var.get()),
            image_size=int(self.imgsz_var.get()),
            batch_size=int(self.batch_var.get()),
        )

    def _run_action(self, action: str) -> None:
        try:
            command = build_command(self._config(), action)
        except Exception as exc:
            self._append_log(f"Config error: {exc}\n")
            return
        self._append_log(f"\n> {' '.join(command)}\n")
        thread = threading.Thread(target=self._run_process, args=(command,), daemon=True)
        thread.start()

    def _run_process(self, command: list[str]) -> None:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:
            self._append_log(f"Failed to start: {exc}\n")
            return
        assert process.stdout is not None
        for line in process.stdout:
            self._append_log(line)
        code = process.wait()
        self._append_log(f"[exit {code}]\n")

    def _open_dataset_folder(self) -> None:
        path = Path(self.dataset_var.get())
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _clear_log(self) -> None:
        self.log.delete("1.0", tk.END)

    def _append_log(self, text: str) -> None:
        self.root.after(0, self._append_log_on_ui, text)

    def _append_log_on_ui(self, text: str) -> None:
        self.log.insert(tk.END, text)
        self.log.see(tk.END)

    def run(self) -> int:
        self.root.mainloop()
        return 0


def main() -> int:
    return TrainerGui().run()
