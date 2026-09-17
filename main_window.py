"""Modern PySide6 main window for the Lumerical FDTD runner."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from fdtd_core import (
    FDTD_EXECUTABLE_NAME,
    build_command,
    clean_path,
    command_preview,
    discover_fdtd_executable,
    format_elapsed,
    is_fdtd_executable,
    inspect_lsf,
    lsf_flags,
    test_fdtd_executable,
    validate_run_configuration,
)
from fdtd_runner import FDTDRunner
from settings_store import SettingsStore
from styles import application_stylesheet
from widgets import CommandPreview, ConsoleWidget, PathField, StatusBadge, make_card, refresh_style


APP_TITLE = "FDTD 无界面一键运行"
APP_SUBTITLE = "FSP + LSF 自动执行工具"
STATE_LABELS = {
    "READY": "就绪",
    "RUNNING": "运行中",
    "FINISHED": "已完成",
    "FAILED": "失败",
    "STOPPED": "已停止",
}


class SettingsDialog(QDialog):
    def __init__(self, theme: str, settings_path: Path, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(480)
        self.request_rescan = False
        self.request_reset_layout = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(13)
        title = QLabel("应用设置")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("界面主题"))
        theme_row.addStretch(1)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("深色", "dark")
        self.theme_combo.addItem("浅色", "light")
        self.theme_combo.setCurrentIndex(0 if theme == "dark" else 1)
        theme_row.addWidget(self.theme_combo)
        layout.addLayout(theme_row)

        config_label = QLabel(f"设置文件\n{settings_path}")
        config_label.setObjectName("Muted")
        config_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(config_label)

        self.rescan_button = QPushButton("重新自动检测 FDTD")
        self.reset_button = QPushButton("重置窗口布局")
        self.rescan_button.clicked.connect(self._rescan)
        self.reset_button.clicked.connect(self._reset_layout)
        layout.addWidget(self.rescan_button)
        layout.addWidget(self.reset_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _rescan(self) -> None:
        self.request_rescan = True
        self.accept()

    def _reset_layout(self) -> None:
        self.request_reset_layout = True
        self.accept()

    def selected_theme(self) -> str:
        return str(self.theme_combo.currentData())


class MainWindow(QMainWindow):
    fdtd_discovered = Signal(str)
    fdtd_discovery_error = Signal(str)

    def __init__(
        self,
        settings: SettingsStore,
        runner: Optional[FDTDRunner] = None,
        *,
        auto_discover: bool = True,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.runner = runner or FDTDRunner(self)
        self.current_theme = self.settings.theme()
        self.current_state = "READY"
        self.started_monotonic: Optional[float] = None
        self.pending_close = False
        self._compact_layout: Optional[bool] = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(450)
        self._save_timer.timeout.connect(self._save_paths)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed)

        self.setWindowTitle(f"{APP_TITLE} — {APP_SUBTITLE}")
        self.resize(1180, 860)
        self.setMinimumSize(680, 560)
        self.setAcceptDrops(False)
        self._build_ui()
        self._connect_signals()
        self._load_settings()
        self._apply_theme(self.current_theme, persist=False)
        self._update_all_validation()
        self._set_run_state("READY")
        self._restore_window_layout()
        self._apply_responsive_layout(self.width())
        if auto_discover:
            QTimer.singleShot(0, self._restore_or_discover_fdtd)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.root_layout = QVBoxLayout(root)
        self.root_layout.setContentsMargins(20, 15, 20, 18)
        self.root_layout.setSpacing(12)
        self.setCentralWidget(root)

        header = QFrame()
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 0, 2, 0)
        title_column = QVBoxLayout()
        title_column.setSpacing(0)
        title = QLabel(APP_TITLE)
        title.setObjectName("HeaderTitle")
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("HeaderSubtitle")
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        header_layout.addLayout(title_column)
        header_layout.addStretch(1)
        self.settings_button = QPushButton("设置")
        self.settings_button.setObjectName("GhostButton")
        self.settings_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.theme_button = QPushButton("深色模式")
        self.theme_button.setObjectName("GhostButton")
        self.theme_button.setCheckable(True)
        header_layout.addWidget(self.settings_button)
        header_layout.addWidget(self.theme_button)
        self.root_layout.addWidget(header)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.root_layout.addWidget(self.splitter, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 4)
        top_layout.setSpacing(12)
        scroll.setWidget(top)
        self.splitter.addWidget(scroll)

        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(12)
        self.files_card, files_layout = make_card(
            "仿真文件",
            "选择或拖放仿真模型和自动化脚本。",
        )
        self.fsp_field = PathField(
            "FSP 仿真文件",
            "拖放或选择 .fsp 仿真文件",
            suffixes=(".fsp",),
        )
        self.lsf_field = PathField(
            "LSF 脚本",
            "拖放或选择 .lsf 脚本",
            suffixes=(".lsf",),
        )
        files_layout.addWidget(self.fsp_field)
        files_layout.addWidget(self.lsf_field)
        files_layout.addStretch(1)

        self.environment_card, environment_layout = make_card(
            "运行环境",
            "设置运行程序和命令行日志位置，路径会自动保存。",
        )
        self.fdtd_field = PathField(
            "FDTD 可执行文件",
            "自动检测或选择 fdtd-solutions.exe",
            suffixes=(".exe",),
        )
        self.log_field = PathField(
            "日志目录",
            "默认使用 <FSP 文件夹>\\logs",
            accepts_directory=True,
        )
        environment_layout.addWidget(self.fdtd_field)
        environment_layout.addWidget(self.log_field)
        environment_layout.addStretch(1)
        self.cards_grid.addWidget(self.files_card, 0, 0)
        self.cards_grid.addWidget(self.environment_card, 0, 1)
        top_layout.addLayout(self.cards_grid)

        validation_card, validation_layout = make_card("运行检查")
        self.validation_grid = QGridLayout()
        self.validation_grid.setSpacing(8)
        self.ready_badge = StatusBadge("路径尚未完整", "neutral")
        self.exit_badge = StatusBadge("尚未检查 exit;", "neutral")
        self.visual_badge = StatusBadge("尚未检查可视化命令", "neutral")
        self.validation_grid.addWidget(self.ready_badge, 0, 0)
        self.validation_grid.addWidget(self.exit_badge, 0, 1)
        self.validation_grid.addWidget(self.visual_badge, 0, 2)
        self.validation_grid.setColumnStretch(3, 1)
        validation_layout.addLayout(self.validation_grid)
        top_layout.addWidget(validation_card)

        command_card, command_layout = make_card(
            "命令预览",
            "仅供核对；实际执行始终使用参数列表，不会执行此处显示的字符串。",
        )
        self.command_preview = CommandPreview()
        command_layout.addWidget(self.command_preview)
        top_layout.addWidget(command_card)

        actions_card, actions_layout = make_card("操作")
        self.actions_grid = QGridLayout()
        self.actions_grid.setSpacing(8)
        self.run_button = QPushButton("运行仿真")
        self.run_button.setObjectName("PrimaryButton")
        self.stop_button = QPushButton("停止仿真")
        self.stop_button.setObjectName("DangerButton")
        self.test_button = QPushButton("测试 FDTD")
        self.open_fsp_button = QPushButton("打开 FSP 文件夹")
        self.open_log_button = QPushButton("打开日志文件夹")
        for button in (self.test_button, self.open_fsp_button, self.open_log_button):
            button.setObjectName("GhostButton")
        for column, button in enumerate(self._action_buttons()):
            self.actions_grid.addWidget(button, 0, column)
        self.actions_grid.setColumnStretch(5, 1)
        actions_layout.addLayout(self.actions_grid)

        status_panel = QFrame()
        status_panel.setObjectName("StatusPanel")
        self.status_layout = QGridLayout(status_panel)
        self.status_layout.setContentsMargins(12, 9, 12, 9)
        self.status_caption = QLabel("仿真状态")
        self.status_layout.addWidget(self.status_caption, 0, 0)
        self.state_label = QLabel("就绪")
        self.state_label.setProperty("runState", "READY")
        self.status_layout.addWidget(self.state_label, 0, 1)
        self.elapsed_caption = QLabel("已用时间")
        self.elapsed_caption.setObjectName("Muted")
        self.status_layout.addWidget(self.elapsed_caption, 0, 2)
        self.elapsed_label = QLabel("00:00:00")
        self.status_layout.addWidget(self.elapsed_label, 0, 3)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumWidth(240)
        self.progress.setVisible(False)
        self.status_layout.addWidget(self.progress, 0, 4)
        self.status_layout.setColumnStretch(5, 1)
        actions_layout.addWidget(status_panel)
        top_layout.addWidget(actions_card)
        top_layout.addStretch(1)

        console_frame = QFrame()
        console_frame.setObjectName("ConsoleFrame")
        console_layout = QVBoxLayout(console_frame)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)
        console_header = QFrame()
        console_header.setObjectName("ConsoleHeader")
        console_header_layout = QHBoxLayout(console_header)
        console_header_layout.setContentsMargins(12, 7, 8, 7)
        console_header_layout.addWidget(QLabel("仿真控制台"))
        console_header_layout.addStretch(1)
        self.clear_log_button = QPushButton("清空")
        console_header_layout.addWidget(self.clear_log_button)
        console_layout.addWidget(console_header)
        self.console = ConsoleWidget()
        console_layout.addWidget(self.console, 1)
        self.splitter.addWidget(console_frame)
        # Keep the primary Run/Stop controls visible at the default window size;
        # the terminal remains resizable through the IDE-style splitter.
        self.splitter.setSizes([650, 140])

    def _action_buttons(self) -> tuple[QPushButton, ...]:
        return (
            self.run_button,
            self.stop_button,
            self.test_button,
            self.open_fsp_button,
            self.open_log_button,
        )

    def _apply_responsive_layout(self, width: int) -> None:
        if not hasattr(self, "cards_grid"):
            return
        compact = width < 980
        if compact == self._compact_layout:
            return
        self._compact_layout = compact

        for card in (self.files_card, self.environment_card):
            self.cards_grid.removeWidget(card)
        for badge in (self.ready_badge, self.exit_badge, self.visual_badge):
            self.validation_grid.removeWidget(badge)
        for button in self._action_buttons():
            self.actions_grid.removeWidget(button)
        for widget in (
            self.status_caption,
            self.state_label,
            self.elapsed_caption,
            self.elapsed_label,
            self.progress,
        ):
            self.status_layout.removeWidget(widget)

        if compact:
            self.root_layout.setContentsMargins(12, 10, 12, 12)
            self.cards_grid.addWidget(self.files_card, 0, 0)
            self.cards_grid.addWidget(self.environment_card, 1, 0)
            self.cards_grid.setColumnStretch(0, 1)
            self.cards_grid.setColumnStretch(1, 0)

            self.validation_grid.addWidget(self.ready_badge, 0, 0)
            self.validation_grid.addWidget(self.exit_badge, 0, 1)
            self.validation_grid.addWidget(self.visual_badge, 1, 0, 1, 2)
            self.validation_grid.setColumnStretch(0, 1)
            self.validation_grid.setColumnStretch(1, 1)
            self.validation_grid.setColumnStretch(2, 0)
            self.validation_grid.setColumnStretch(3, 0)

            self.actions_grid.addWidget(self.run_button, 0, 0)
            self.actions_grid.addWidget(self.stop_button, 0, 1)
            self.actions_grid.addWidget(self.test_button, 1, 0)
            self.actions_grid.addWidget(self.open_fsp_button, 1, 1)
            self.actions_grid.addWidget(self.open_log_button, 2, 0, 1, 2)
            self.actions_grid.setColumnStretch(0, 1)
            self.actions_grid.setColumnStretch(1, 1)
            self.actions_grid.setColumnStretch(5, 0)

            self.status_layout.addWidget(self.status_caption, 0, 0)
            self.status_layout.addWidget(self.state_label, 0, 1)
            self.status_layout.addWidget(self.elapsed_caption, 0, 2)
            self.status_layout.addWidget(self.elapsed_label, 0, 3)
            self.status_layout.addWidget(self.progress, 1, 0, 1, 4)
            self.status_layout.setColumnStretch(4, 0)
            self.status_layout.setColumnStretch(5, 0)
            self.progress.setMaximumWidth(16777215)
        else:
            self.root_layout.setContentsMargins(20, 15, 20, 18)
            self.cards_grid.addWidget(self.files_card, 0, 0)
            self.cards_grid.addWidget(self.environment_card, 0, 1)
            self.cards_grid.setColumnStretch(0, 1)
            self.cards_grid.setColumnStretch(1, 1)

            self.validation_grid.addWidget(self.ready_badge, 0, 0)
            self.validation_grid.addWidget(self.exit_badge, 0, 1)
            self.validation_grid.addWidget(self.visual_badge, 0, 2)
            self.validation_grid.setColumnStretch(0, 0)
            self.validation_grid.setColumnStretch(1, 0)
            self.validation_grid.setColumnStretch(2, 0)
            self.validation_grid.setColumnStretch(3, 1)

            for column, button in enumerate(self._action_buttons()):
                self.actions_grid.addWidget(button, 0, column)
            self.actions_grid.setColumnStretch(0, 0)
            self.actions_grid.setColumnStretch(1, 0)
            self.actions_grid.setColumnStretch(5, 1)

            self.status_layout.addWidget(self.status_caption, 0, 0)
            self.status_layout.addWidget(self.state_label, 0, 1)
            self.status_layout.addWidget(self.elapsed_caption, 0, 2)
            self.status_layout.addWidget(self.elapsed_label, 0, 3)
            self.status_layout.addWidget(self.progress, 0, 4)
            self.status_layout.setColumnStretch(4, 0)
            self.status_layout.setColumnStretch(5, 1)
            self.progress.setMaximumWidth(240)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_responsive_layout(event.size().width())

    def _connect_signals(self) -> None:
        for field in (self.fdtd_field, self.fsp_field, self.lsf_field, self.log_field):
            field.text_changed.connect(self._on_paths_changed)
        self.fdtd_field.browse_requested.connect(self._browse_fdtd)
        self.fsp_field.browse_requested.connect(self._browse_fsp)
        self.lsf_field.browse_requested.connect(self._browse_lsf)
        self.log_field.browse_requested.connect(self._browse_log_dir)
        self.fsp_field.path_dropped.connect(self._fsp_dropped)

        self.run_button.clicked.connect(self._run_simulation)
        self.stop_button.clicked.connect(self._confirm_stop)
        self.test_button.clicked.connect(self._test_fdtd)
        self.open_fsp_button.clicked.connect(self._open_fsp_folder)
        self.open_log_button.clicked.connect(self._open_log_folder)
        self.clear_log_button.clicked.connect(self.console.clear)
        self.settings_button.clicked.connect(self._show_settings)
        self.theme_button.toggled.connect(self._theme_toggled)
        self.fdtd_discovered.connect(self._on_fdtd_discovered)
        self.fdtd_discovery_error.connect(self.console.append_output)

        self.runner.output_received.connect(self.console.append_output)
        self.runner.process_started.connect(self._on_process_started)
        self.runner.process_finished.connect(self._on_process_finished)

    def _load_settings(self) -> None:
        self.fdtd_field.set_text(self.settings.path_value("fdtd_exe"))
        self.fsp_field.set_text(self.settings.path_value("fsp_file"))
        self.lsf_field.set_text(self.settings.path_value("lsf_file"))
        self.log_field.set_text(self.settings.path_value("log_dir"))

    def _restore_window_layout(self) -> None:
        geometry = self.settings.geometry()
        if not geometry.isEmpty():
            self.restoreGeometry(geometry)
        splitter = self.settings.splitter_state()
        if not splitter.isEmpty():
            self.splitter.restoreState(splitter)

    def _save_paths(self) -> None:
        self.settings.set_path_value("fdtd_exe", clean_path(self.fdtd_field.text()))
        self.settings.set_path_value("fsp_file", clean_path(self.fsp_field.text()))
        self.settings.set_path_value("lsf_file", clean_path(self.lsf_field.text()))
        self.settings.set_path_value("log_dir", clean_path(self.log_field.text()))
        self.settings.sync()

    def _save_window_state(self) -> bool:
        self._save_paths()
        self.settings.set_geometry(self.saveGeometry())
        self.settings.set_splitter_state(self.splitter.saveState())
        self.settings.set_theme(self.current_theme)
        return self.settings.sync()

    def _on_paths_changed(self, _value: str = "") -> None:
        self._update_all_validation()
        self._save_timer.start()

    def _update_all_validation(self) -> None:
        fdtd = self.fdtd_field.text()
        fsp = self.fsp_field.text()
        lsf = self.lsf_field.text()
        logs = self.log_field.text()

        if not fdtd:
            self.fdtd_field.set_validation("neutral", "未选择")
        elif is_fdtd_executable(fdtd):
            self.fdtd_field.set_validation("valid", "有效")
        else:
            self.fdtd_field.set_validation("invalid", "无效")

        fsp_valid = bool(fsp) and Path(fsp).is_file() and Path(fsp).suffix.lower() == ".fsp"
        self.fsp_field.set_validation(
            "valid" if fsp_valid else ("invalid" if fsp else "neutral"),
            "有效" if fsp_valid else ("无效" if fsp else "未选择"),
        )

        lsf_valid = bool(lsf) and Path(lsf).is_file() and Path(lsf).suffix.lower() == ".lsf"
        self.lsf_field.set_validation(
            "valid" if lsf_valid else ("invalid" if lsf else "neutral"),
            "有效" if lsf_valid else ("无效" if lsf else "未选择"),
        )

        log_state = "neutral"
        log_text = "未选择"
        if logs:
            log_path = Path(logs)
            if log_path.exists() and log_path.is_dir():
                log_state, log_text = "valid", "有效"
            elif not log_path.exists() and log_path.parent.is_dir():
                log_state, log_text = "warning", "运行时创建"
            else:
                log_state, log_text = "invalid", "无效"
        self.log_field.set_validation(log_state, log_text)

        if lsf_valid:
            try:
                has_exit, has_visualization = lsf_flags(Path(lsf))
                self.exit_badge.set_state(
                    "valid" if has_exit else "warning",
                    "已检测到 exit;" if has_exit else "未检测到 exit;",
                )
                self.visual_badge.set_state(
                    "warning" if has_visualization else "valid",
                    "包含可视化命令" if has_visualization else "未发现可视化命令",
                )
            except OSError:
                self.exit_badge.set_state("invalid", "LSF 读取失败")
                self.visual_badge.set_state("invalid", "LSF 读取失败")
        else:
            self.exit_badge.set_state("neutral", "尚未检查 exit;")
            self.visual_badge.set_state("neutral", "尚未检查可视化命令")

        ready = is_fdtd_executable(fdtd) and fsp_valid and lsf_valid and log_state in {"valid", "warning"}
        self.ready_badge.set_state("valid" if ready else "neutral", "可以运行" if ready else "路径尚未完整")

        command = build_command(
            fdtd or f"<{FDTD_EXECUTABLE_NAME}>",
            fsp or "<simulation.fsp>",
            lsf or "<script.lsf>",
            logs or "<log-folder>",
        )
        self.command_preview.set_command(command_preview(command))

    def _initial_directory(self, value: str) -> str:
        cleaned = clean_path(value)
        if cleaned:
            path = Path(cleaned)
            if path.is_dir():
                return str(path)
            if path.parent.is_dir():
                return str(path.parent)
        return str(Path.home())

    def _browse_fdtd(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择 fdtd-solutions.exe",
            self._initial_directory(self.fdtd_field.text()),
            "可执行文件 (*.exe);;所有文件 (*.*)",
        )
        if selected:
            self.fdtd_field.set_text(selected)
            self._save_paths()

    def _set_fsp_path(self, selected: str) -> None:
        old_fsp = clean_path(self.fsp_field.text())
        old_default = str(Path(old_fsp).parent / "logs") if old_fsp else ""
        current_log = clean_path(self.log_field.text())
        self.fsp_field.set_text(selected)
        if not current_log or current_log == old_default:
            self.log_field.set_text(str(Path(selected).parent / "logs"))

    def _browse_fsp(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择 FSP 仿真文件",
            self._initial_directory(self.fsp_field.text()),
            "Lumerical FSP (*.fsp);;所有文件 (*.*)",
        )
        if selected:
            self._set_fsp_path(selected)

    def _fsp_dropped(self, selected: str) -> None:
        if not self.log_field.text():
            self.log_field.set_text(str(Path(selected).parent / "logs"))

    def _browse_lsf(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择 LSF 脚本",
            self._initial_directory(self.lsf_field.text() or self.fsp_field.text()),
            "Lumerical 脚本 (*.lsf);;所有文件 (*.*)",
        )
        if selected:
            self.lsf_field.set_text(selected)

    def _browse_log_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择日志目录",
            self._initial_directory(self.log_field.text() or self.fsp_field.text()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if selected:
            self.log_field.set_text(selected)

    def _restore_or_discover_fdtd(self, *, force: bool = False) -> None:
        saved = "" if force else clean_path(self.fdtd_field.text())
        if is_fdtd_executable(saved):
            self.console.append_output(f"已恢复上次使用的 FDTD 路径：\n{saved}\n")
            return
        if saved:
            self.console.append_output(f"上次保存的 FDTD 路径已失效：\n{saved}\n")
            self.fdtd_field.set_text("")
        self.console.append_output("正在自动查找 fdtd-solutions.exe...\n")

        def worker() -> None:
            try:
                found = discover_fdtd_executable()
                self.fdtd_discovered.emit(str(found) if found else "")
            except Exception as exc:
                self.fdtd_discovery_error.emit(
                    f"自动查找 FDTD 时出错：{type(exc).__name__}: {exc}\n"
                )
                self.fdtd_discovered.emit("")

        threading.Thread(target=worker, name="fdtd-discovery-worker", daemon=True).start()

    def _on_fdtd_discovered(self, found: str) -> None:
        if found and (not self.fdtd_field.text() or not is_fdtd_executable(self.fdtd_field.text())):
            self.fdtd_field.set_text(found)
            self._save_paths()
            self.console.append_output(f"已自动找到 FDTD：\n{found}\n")
        elif found:
            self.console.append_output("已跳过自动查找结果，因为已手动选择 FDTD。\n")
        else:
            self.console.append_output("未在常见安装位置找到 FDTD，请使用文件夹按钮手动选择。\n")

    def _run_simulation(self) -> None:
        if self.runner.is_running:
            QMessageBox.warning(self, "仿真正在运行", "已有一个仿真正在运行。")
            return
        result = validate_run_configuration(
            self.fdtd_field.text(),
            self.fsp_field.text(),
            self.lsf_field.text(),
            self.log_field.text(),
            create_log_dir=True,
        )
        if not result.is_valid or result.configuration is None:
            QMessageBox.critical(self, "无法启动仿真", "\n\n".join(result.errors))
            self._update_all_validation()
            return

        config = result.configuration
        try:
            warnings = inspect_lsf(config.lsf_file)
        except OSError as exc:
            warnings = [f"无法检查 LSF：{exc}"]
        for warning in warnings:
            self.console.append_output(f"警告：{warning}\n")

        if not self.runner.start(config.command, config.cwd):
            QMessageBox.warning(self, "仿真正在运行", "已有一个仿真正在运行。")
            return

        self.pending_close = False
        self.started_monotonic = time.monotonic()
        self.elapsed_label.setText("00:00:00")
        self._elapsed_timer.start()
        self._set_run_state("RUNNING")
        self._save_paths()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.console.append_output("\n" + "=" * 78 + "\n")
        self.console.append_output(f"[{now}] 正在启动仿真...\n\n")
        self.console.append_output(f"FDTD 可执行文件：\n{config.fdtd_exe}\n\n")
        self.console.append_output(f"FSP 仿真文件：\n{config.fsp_file}\n\n")
        self.console.append_output(f"LSF 脚本：\n{config.lsf_file}\n\n")
        self.console.append_output(f"日志目录：\n{config.log_dir}\n\n")
        self.console.append_output(f"工作目录：\n{config.cwd}\n\n")
        self.console.append_output("状态：运行中\n")

    def _on_process_started(self, pid: int) -> None:
        self.console.append_output(f"\n进程 PID：{pid}\n\n仿真正在运行...\n")

    def _on_process_finished(self, state: str, exit_code: object) -> None:
        completed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.console.append_output(
            f"\n[{completed}] 进程已结束。\n退出代码：{exit_code}\n状态：{state}\n"
        )
        self._elapsed_timer.stop()
        self._update_elapsed()
        self._set_run_state(state)
        if self.pending_close:
            self.pending_close = False
            self._save_window_state()
            QTimer.singleShot(0, self.close)

    def _update_elapsed(self) -> None:
        if self.started_monotonic is not None:
            self.elapsed_label.setText(format_elapsed(time.monotonic() - self.started_monotonic))

    def _set_run_state(self, state: str) -> None:
        self.current_state = state
        self.state_label.setText(STATE_LABELS.get(state, state))
        self.state_label.setProperty("runState", state)
        refresh_style(self.state_label)
        running = state == "RUNNING"
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.test_button.setEnabled(not running)
        self.progress.setVisible(running)

    def _confirm_stop(self) -> None:
        if not self.runner.is_running:
            return
        answer = QMessageBox.question(
            self,
            "终止仿真",
            "确定要终止当前正在运行的 FDTD 仿真吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._begin_stop()

    def _begin_stop(self) -> None:
        if self.runner.request_stop():
            self.stop_button.setEnabled(False)
            self.console.append_output(
                f"\n[{datetime.now().strftime('%H:%M:%S')}] 已请求终止仿真...\n"
            )
            if self.runner.pid is None:
                self.console.append_output("进程仍在初始化；进程创建后将立即终止。\n")

    def _test_fdtd(self) -> None:
        problems = test_fdtd_executable(self.fdtd_field.text())
        if problems:
            QMessageBox.critical(self, "FDTD 测试失败", "\n\n".join(problems))
        else:
            QMessageBox.information(
                self,
                "FDTD 测试通过",
                "该文件存在、名称正确，并可作为 Windows 可执行文件读取。\n\n"
                "本测试没有启动 FDTD，因此不验证许可证或完整仿真。",
            )

    def _open_fsp_folder(self) -> None:
        path = clean_path(self.fsp_field.text())
        if not path:
            QMessageBox.warning(self, "打开文件夹", "请先选择 FSP 文件。")
            return
        self._open_folder(Path(path).parent)

    def _open_log_folder(self) -> None:
        path_text = clean_path(self.log_field.text())
        if not path_text:
            QMessageBox.warning(self, "打开文件夹", "请先选择日志目录。")
            return
        path = Path(path_text)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "打开文件夹", f"无法创建日志目录：\n{exc}")
            return
        self._open_folder(path)

    def _open_folder(self, path: Path) -> None:
        if not path.is_dir():
            QMessageBox.critical(self, "打开文件夹", f"文件夹不存在：\n{path}")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.critical(self, "打开文件夹", f"无法打开 Windows 文件资源管理器：\n{path}")

    def _theme_toggled(self, checked: bool) -> None:
        self._apply_theme("dark" if checked else "light")

    def _apply_theme(self, theme: str, *, persist: bool = True) -> None:
        self.current_theme = theme if theme in {"light", "dark"} else "dark"
        self.setStyleSheet(application_stylesheet(self.current_theme))
        blocker = QSignalBlocker(self.theme_button)
        self.theme_button.setChecked(self.current_theme == "dark")
        self.theme_button.setText("深色模式" if self.current_theme == "dark" else "浅色模式")
        del blocker
        if persist:
            self.settings.set_theme(self.current_theme)
            self.settings.sync()

    def _show_settings(self) -> None:
        dialog = SettingsDialog(self.current_theme, self.settings.ini_path, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._apply_theme(dialog.selected_theme())
        if dialog.request_reset_layout:
            self.settings.clear_window_layout()
            self.resize(1180, 860)
            self.splitter.setSizes([650, 140])
        if dialog.request_rescan:
            self.fdtd_field.set_text("")
            self._restore_or_discover_fdtd(force=True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.runner.is_running:
            answer = QMessageBox.question(
                self,
                "仿真仍在运行",
                "仿真仍在运行。\n\n是否关闭程序并终止仿真？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.pending_close = True
            self._begin_stop()
            event.ignore()
            return
        if not self._save_window_state():
            QMessageBox.warning(self, "设置警告", "无法保存应用设置。")
        event.accept()
