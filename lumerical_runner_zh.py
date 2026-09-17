"""Entry point for the PySide6 FDTD 无界面一键运行 application."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from fdtd_core import build_command, discover_fdtd_executable
from main_window import MainWindow
from settings_store import SettingsStore


APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
SETTINGS_INI = APP_DIR / "settings.ini"
LEGACY_SETTINGS_JSON = APP_DIR / "settings.json"


def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", APP_DIR))
    return base / relative_path


def packaged_self_test() -> int:
    """Verify imports and invariant command construction without starting FDTD."""
    sample = build_command("fdtd-solutions.exe", "测试.fsp", "测试.lsf", "日志")
    command_ok = sample == [
        "fdtd-solutions.exe",
        "-nw",
        "-trust-script",
        "-logall",
        "-o",
        "日志",
        "-run",
        "测试.lsf",
        "测试.fsp",
    ]
    discovery_api_ok = discover_fdtd_executable(
        search_roots=[], environ={"PATH": ""}
    ) is None
    return 0 if command_ok and discovery_api_ok else 1


def create_application(argv: list[str]) -> QApplication:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(argv)
    app.setApplicationName("FDTD 无界面一键运行")
    app.setApplicationDisplayName("FDTD 无界面一键运行")
    app.setOrganizationName("FDTD Headless Tools")
    app.setFont(QFont("Segoe UI", 10))
    icon_path = resource_path("assets/fdtd_runner.ico")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    return app


def main() -> int:
    app = create_application(sys.argv)
    settings = SettingsStore(SETTINGS_INI, LEGACY_SETTINGS_JSON)
    window = MainWindow(settings)
    window.show()
    return app.exec()


def gui_smoke_test() -> int:
    """Create the complete GUI offscreen and exit without starting FDTD."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = create_application(sys.argv)
    with tempfile.TemporaryDirectory(prefix="fdtd-runner-smoke-") as temp_dir:
        settings = SettingsStore(Path(temp_dir) / "settings.ini")
        window = MainWindow(settings, auto_discover=False)
        window.show()
        result = {"code": 1}

        def verify_and_exit() -> None:
            checks = [
                window.windowTitle().startswith("FDTD 无界面一键运行"),
                window.run_button.text() == "运行仿真",
                window.stop_button.isEnabled() is False,
                window.command_preview.is_expanded() is False,
                window.console.isReadOnly(),
                not app.windowIcon().isNull(),
            ]
            result["code"] = 0 if all(checks) else 1
            window.close()
            app.exit(result["code"])

        QTimer.singleShot(250, verify_and_exit)
        app.exec()
        return result["code"]


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(packaged_self_test())
    if "--gui-smoke-test" in sys.argv:
        raise SystemExit(gui_smoke_test())
    if "--offscreen" in sys.argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    raise SystemExit(main())
