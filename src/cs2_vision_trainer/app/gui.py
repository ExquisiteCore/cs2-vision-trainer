from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText


@dataclass(frozen=True)
class GuiConfig:
    video_path: Path
    model_path: Path
    dataset_root: Path
    device: str = "0"
    player_side: str = "unknown"
    epochs: int = 40
    image_size: int = 640
    batch_size: int = 8
    frame_stride: int = 15
    max_frames: int = 5000
    extract_start_seconds: int = 160


@dataclass(frozen=True)
class WorkflowAction:
    label: str
    action: str
    detail: str


@dataclass(frozen=True)
class WorkflowSection:
    title: str
    actions: tuple[WorkflowAction, ...]


DEFAULT_GUI_CONFIG = GuiConfig(
    video_path=Path("videos/01.mp4"),
    model_path=Path("models/base/yolov8n.pt"),
    dataset_root=Path("datasets/cs2_multiclass"),
)


WORKFLOW_SECTIONS: tuple[WorkflowSection, ...] = (
    WorkflowSection(
        title="1. 导入素材",
        actions=(
            WorkflowAction("抽帧", "extract_frames", "从当前视频生成 raw 图片"),
        ),
    ),
    WorkflowSection(
        title="2. 标注样本",
        actions=(
            WorkflowAction("标注新抽帧", "annotate_extracted", "只处理当前视频抽出的图片"),
            WorkflowAction("标注错题", "annotate_mistakes", "只处理 review 保存的错题帧"),
            WorkflowAction("补标缺失", "annotate_missing", "只显示没有标签的抽帧"),
            WorkflowAction("标注全部", "annotate", "打开 raw 目录全部图片"),
        ),
    ),
    WorkflowSection(
        title="3. 校验整理",
        actions=(
            WorkflowAction("校验数据集", "validate", "检查缺标签、非法类别和坐标"),
            WorkflowAction("整理数据集", "prepare", "生成 train/val 和 dataset.yaml"),
        ),
    ),
    WorkflowSection(
        title="4. 训练测试",
        actions=(
            WorkflowAction("开始训练", "train", "从当前模型继续训练"),
            WorkflowAction("测试视频", "run", "按己方阵营显示敌方，未知则显示全部"),
            WorkflowAction("找错题", "review", "播放视频并保存漏检/误检帧"),
        ),
    ),
)


def _path_text(path: Path) -> str:
    return str(path)


def enemy_labels_for_player_side(player_side: str) -> tuple[str, ...]:
    side = player_side.strip().lower()
    if side == "ct":
        return ("t_body", "t_head")
    if side == "t":
        return ("ct_body", "ct_head")
    return ()


def _append_enemy_label_filter(command: list[str], player_side: str) -> list[str]:
    labels = enemy_labels_for_player_side(player_side)
    if labels:
        return [*command, "--labels", *labels]
    return command


def build_command(config: GuiConfig, action: str) -> list[str]:
    dataset_yaml = config.dataset_root / "dataset.yaml"
    raw_images = config.dataset_root / "images" / "raw"
    raw_labels = config.dataset_root / "labels" / "raw"
    command = ["cs2-vision-trainer"]
    if action == "extract_frames":
        return [
            *command,
            "extract-frames",
            "--video",
            _path_text(config.video_path),
            "--output",
            _path_text(raw_images),
            "--stride",
            str(config.frame_stride),
            "--max-frames",
            str(config.max_frames),
            "--start-time",
            str(config.extract_start_seconds),
        ]
    if action == "review":
        return _append_enemy_label_filter(
            [
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
            ],
            config.player_side,
        )
    if action == "annotate":
        return [
            *command,
            "annotate",
            "--images",
            _path_text(raw_images),
            "--labels",
            _path_text(raw_labels),
        ]
    if action == "annotate_mistakes":
        return [
            *command,
            "annotate",
            "--images",
            _path_text(raw_images),
            "--labels",
            _path_text(raw_labels),
            "--pattern",
            f"{config.video_path.stem}_error_*.jpg",
        ]
    if action == "annotate_extracted":
        return [
            *command,
            "annotate",
            "--images",
            _path_text(raw_images),
            "--labels",
            _path_text(raw_labels),
            "--pattern",
            f"{config.video_path.stem}_frame_*.jpg",
        ]
    if action == "annotate_missing":
        return [
            *command,
            "annotate",
            "--images",
            _path_text(raw_images),
            "--labels",
            _path_text(raw_labels),
            "--pattern",
            f"{config.video_path.stem}_frame_*.jpg",
            "--missing-only",
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
    if action == "validate":
        return [
            *command,
            "validate-dataset",
            "--root",
            _path_text(config.dataset_root),
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
        return _append_enemy_label_filter(
            [
                *command,
                "run",
                "--model",
                _path_text(config.model_path),
                "--source",
                _path_text(config.video_path),
            ],
            config.player_side,
        ) + [
            "--device",
            config.device,
        ]
    raise ValueError(f"unknown GUI action: {action}")


class TrainerGui:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("CS2 Vision Trainer")
        self.root.geometry("1120x760")
        self.root.minsize(980, 680)
        self.video_var = tk.StringVar(value=_path_text(DEFAULT_GUI_CONFIG.video_path))
        self.model_var = tk.StringVar(value=_path_text(DEFAULT_GUI_CONFIG.model_path))
        self.dataset_var = tk.StringVar(value=_path_text(DEFAULT_GUI_CONFIG.dataset_root))
        self.device_var = tk.StringVar(value=DEFAULT_GUI_CONFIG.device)
        self.player_side_var = tk.StringVar(value=DEFAULT_GUI_CONFIG.player_side)
        self.epochs_var = tk.StringVar(value=str(DEFAULT_GUI_CONFIG.epochs))
        self.imgsz_var = tk.StringVar(value=str(DEFAULT_GUI_CONFIG.image_size))
        self.batch_var = tk.StringVar(value=str(DEFAULT_GUI_CONFIG.batch_size))
        self.stride_var = tk.StringVar(value=str(DEFAULT_GUI_CONFIG.frame_stride))
        self.max_frames_var = tk.StringVar(value=str(DEFAULT_GUI_CONFIG.max_frames))
        self.start_seconds_var = tk.StringVar(value=str(DEFAULT_GUI_CONFIG.extract_start_seconds))
        self.status_var = tk.StringVar(value="准备构建 CT/T 四类数据集")
        self._style = ttk.Style(self.root)
        self._configure_style()
        self._build_layout()

    def _configure_style(self) -> None:
        self.root.configure(bg="#121417")
        self._style.theme_use("clam")
        self._style.configure("App.TFrame", background="#121417")
        self._style.configure("Panel.TFrame", background="#1B1F24", borderwidth=1, relief="solid")
        self._style.configure("Card.TFrame", background="#20262D", borderwidth=1, relief="solid")
        self._style.configure("TLabel", background="#121417", foreground="#E5E7EB", font=("Segoe UI", 10))
        self._style.configure("Title.TLabel", background="#121417", foreground="#F9FAFB", font=("Segoe UI Semibold", 18))
        self._style.configure("Subtitle.TLabel", background="#121417", foreground="#9CA3AF", font=("Segoe UI", 10))
        self._style.configure("PanelTitle.TLabel", background="#1B1F24", foreground="#F9FAFB", font=("Segoe UI Semibold", 11))
        self._style.configure("PanelText.TLabel", background="#1B1F24", foreground="#A7B0BA", font=("Segoe UI", 9))
        self._style.configure("CardTitle.TLabel", background="#20262D", foreground="#F9FAFB", font=("Segoe UI Semibold", 10))
        self._style.configure("CardText.TLabel", background="#20262D", foreground="#A7B0BA", font=("Segoe UI", 9))
        self._style.configure("TEntry", fieldbackground="#0F1216", foreground="#F9FAFB", insertcolor="#F9FAFB")
        self._style.configure("TButton", padding=(10, 7), font=("Segoe UI", 9))
        self._style.configure("Primary.TButton", padding=(12, 8), font=("Segoe UI Semibold", 9))

    def _build_layout(self) -> None:
        container = self._build_scroll_container()

        header = ttk.Frame(container, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        ttk.Label(header, text="CS2 Vision Trainer", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="CT/T 四类数据闭环：抽帧、标注、校验、训练、复盘",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Label(header, textvariable=self.status_var, style="Subtitle.TLabel").grid(row=0, column=1, rowspan=2, sticky="e")
        header.columnconfigure(1, weight=1)

        config_panel = ttk.Frame(container, style="Panel.TFrame", padding=14)
        config_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        ttk.Label(config_panel, text="配置", style="PanelTitle.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self._row_file(config_panel, 1, "视频", self.video_var, self._pick_video)
        self._row_file(config_panel, 2, "模型", self.model_var, self._pick_model)
        self._row_file(config_panel, 3, "数据集", self.dataset_var, self._pick_dataset)
        self._row_entry(config_panel, 4, "显卡编号", self.device_var, width=10)
        self._row_choice(config_panel, 5, "己方阵营", self.player_side_var, values=("unknown", "ct", "t"))
        self._row_entry(config_panel, 6, "训练轮数", self.epochs_var, width=10)
        self._row_entry(config_panel, 7, "图片尺寸", self.imgsz_var, width=10)
        self._row_entry(config_panel, 8, "批大小", self.batch_var, width=10)
        self._row_entry(config_panel, 9, "抽帧间隔", self.stride_var, width=10)
        self._row_entry(config_panel, 10, "最多帧数", self.max_frames_var, width=10)
        self._row_entry(config_panel, 11, "起始秒数", self.start_seconds_var, width=10)
        self._class_summary(config_panel, 12)

        utility_frame = ttk.Frame(config_panel, style="Panel.TFrame")
        utility_frame.grid(row=13, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        ttk.Button(utility_frame, text="打开数据集目录", command=self._open_dataset_folder).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(utility_frame, text="清空日志", command=self._clear_log).pack(side=tk.LEFT)
        config_panel.columnconfigure(1, weight=1)

        workflow_panel = ttk.Frame(container, style="App.TFrame")
        workflow_panel.grid(row=1, column=1, sticky="nsew")
        for index, section in enumerate(WORKFLOW_SECTIONS):
            self._workflow_section(workflow_panel, index, section)
        workflow_panel.columnconfigure(0, weight=1)

        log_panel = ttk.Frame(container, style="Panel.TFrame", padding=10)
        log_panel.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(16, 0))
        ttk.Label(log_panel, text="运行日志", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.log = ScrolledText(
            log_panel,
            height=14,
            bg="#0F1216",
            fg="#E5E7EB",
            insertbackground="#E5E7EB",
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        self.log.grid(row=1, column=0, sticky="nsew")
        log_panel.columnconfigure(0, weight=1)
        log_panel.rowconfigure(1, weight=1)

        container.columnconfigure(0, weight=0, minsize=360)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(1, weight=1)
        container.rowconfigure(2, weight=1)

    def _build_scroll_container(self) -> ttk.Frame:
        outer = ttk.Frame(self.root, style="App.TFrame")
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, bg="#121417", highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        container = ttk.Frame(canvas, style="App.TFrame", padding=18)
        window_id = canvas.create_window((0, 0), window=container, anchor="nw")

        def sync_scroll_region(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def sync_content_width(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        container.bind("<Configure>", sync_scroll_region)
        canvas.bind("<Configure>", sync_content_width)
        canvas.bind_all("<MouseWheel>", lambda event: self._scroll_main_canvas(event, canvas))
        canvas.bind_all("<Button-4>", lambda event: self._scroll_main_canvas(event, canvas))
        canvas.bind_all("<Button-5>", lambda event: self._scroll_main_canvas(event, canvas))
        return container

    def _scroll_main_canvas(self, event: tk.Event, canvas: tk.Canvas) -> None:
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if self._is_log_widget(widget):
            return
        if getattr(event, "num", None) == 4:
            canvas.yview_scroll(-1, "units")
            return
        if getattr(event, "num", None) == 5:
            canvas.yview_scroll(1, "units")
            return
        delta = getattr(event, "delta", 0)
        if delta:
            canvas.yview_scroll(int(-delta / 120), "units")

    def _is_log_widget(self, widget: tk.Widget | None) -> bool:
        while widget is not None:
            if widget is getattr(self, "log", None):
                return True
            widget = widget.master
        return False

    def _class_summary(self, parent: tk.Widget, row: int) -> None:
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Label(frame, text="类别", style="PanelText.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="1 ct_body   2 ct_head\n3 t_body    4 t_head",
            style="PanelText.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(
            frame,
            text="敌我由己方阵营在测试阶段推导",
            style="PanelText.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))

    def _workflow_section(self, parent: tk.Widget, row: int, section: WorkflowSection) -> None:
        section_frame = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        section_frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(section_frame, text=section.title, style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        for index, action in enumerate(section.actions, start=1):
            card = ttk.Frame(section_frame, style="Card.TFrame", padding=10)
            card.grid(row=index, column=0, sticky="ew", pady=(0, 8))
            ttk.Label(card, text=action.label, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Label(card, text=action.detail, style="CardText.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))
            ttk.Button(
                card,
                text="运行",
                style="Primary.TButton",
                command=lambda selected=action.action: self._run_action(selected),
            ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
            card.columnconfigure(0, weight=1)
        section_frame.columnconfigure(0, weight=1)

    def _row_file(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
        command,
    ) -> None:
        ttk.Label(parent, text=label, style="PanelText.TLabel", width=12, anchor="w").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=5)
        ttk.Button(parent, text="选择", command=command, width=8).grid(row=row, column=2, padx=(8, 0), pady=5)

    def _row_entry(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
        *,
        width: int,
    ) -> None:
        ttk.Label(parent, text=label, style="PanelText.TLabel", width=12, anchor="w").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable, width=width).grid(row=row, column=1, sticky="w", pady=5)

    def _row_choice(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
        *,
        values: tuple[str, ...],
    ) -> None:
        ttk.Label(parent, text=label, style="PanelText.TLabel", width=12, anchor="w").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=10).grid(row=row, column=1, sticky="w", pady=5)

    def _pick_video(self) -> None:
        path = filedialog.askopenfilename(
            title="选择视频",
            filetypes=[("视频文件", "*.mp4 *.avi *.mkv"), ("所有文件", "*.*")],
        )
        if path:
            self.video_var.set(path)

    def _pick_model(self) -> None:
        path = filedialog.askopenfilename(
            title="选择模型",
            filetypes=[("YOLO 模型", "*.pt *.onnx *.engine"), ("所有文件", "*.*")],
        )
        if path:
            self.model_var.set(path)

    def _pick_dataset(self) -> None:
        path = filedialog.askdirectory(title="选择数据集目录")
        if path:
            self.dataset_var.set(path)

    def _config(self) -> GuiConfig:
        return GuiConfig(
            video_path=Path(self.video_var.get()),
            model_path=Path(self.model_var.get()),
            dataset_root=Path(self.dataset_var.get()),
            device=self.device_var.get().strip() or "0",
            player_side=self.player_side_var.get().strip().lower() or "unknown",
            epochs=int(self.epochs_var.get()),
            image_size=int(self.imgsz_var.get()),
            batch_size=int(self.batch_var.get()),
            frame_stride=int(self.stride_var.get()),
            max_frames=int(self.max_frames_var.get()),
            extract_start_seconds=int(self.start_seconds_var.get()),
        )

    def _run_action(self, action: str) -> None:
        try:
            command = build_command(self._config(), action)
        except Exception as exc:
            self._append_log(f"配置错误：{exc}\n")
            return
        self.status_var.set(f"运行中：{action}")
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
            self._append_log(f"启动失败：{exc}\n")
            return
        assert process.stdout is not None
        for line in process.stdout:
            self._append_log(line)
        code = process.wait()
        self._append_log(f"[退出码 {code}]\n")
        self.status_var.set("空闲")

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
