"""Capture deterministic light/dark README screenshots without starting FDTD."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QApplication

from main_window import MainWindow
from settings_store import SettingsStore


def capture(theme: str, output: Path, *, width: int = 1180, height: int = 860) -> None:
    with tempfile.TemporaryDirectory(prefix="fdtd-screenshot-") as temp_dir:
        store = SettingsStore(Path(temp_dir) / "settings.ini")
        window = MainWindow(store, auto_discover=False)
        window._apply_theme(theme, persist=False)
        demo = Path(temp_dir) / "Metasurface"
        fdtd = demo / "Lumerical" / "fdtd-solutions.exe"
        fsp = demo / "unit_cell.fsp"
        lsf = demo / "run_sweep.lsf"
        logs = demo / "logs"
        fdtd.parent.mkdir(parents=True)
        logs.mkdir(parents=True)
        fdtd.write_bytes(b"MZ" + b"\x00" * 64)
        fsp.write_bytes(b"FSP screenshot placeholder")
        lsf.write_text("run;\nexit;\n", encoding="utf-8")
        window.fdtd_field.set_text(str(fdtd))
        window.fsp_field.set_text(str(fsp))
        window.lsf_field.set_text(str(lsf))
        window.log_field.set_text(str(logs))
        # Keep validation based on real temporary files, but show neutral demo
        # paths so published screenshots never expose a local username.
        display_paths = (
            (window.fdtd_field, r"C:\FDTD\bin\fdtd-solutions.exe"),
            (window.fsp_field, r"D:\Research\Metasurface\unit_cell.fsp"),
            (window.lsf_field, r"D:\Research\Metasurface\run_sweep.lsf"),
            (window.log_field, r"D:\Research\Metasurface\logs"),
        )
        blockers = [QSignalBlocker(field.edit) for field, _ in display_paths]
        for field, display_path in display_paths:
            field.edit.setText(display_path)
            field.edit.setCursorPosition(0)
        del blockers
        window.console.append_output(
            "[预览] 请配置仿真文件，通过检查后即可运行。\n"
            "警告：LSF 检查仅供提示，不会执行 Lumerical。\n"
        )
        window.resize(width, height)
        window.show()
        app.processEvents()
        output.parent.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(output), "PNG"):
            raise RuntimeError(f"Could not save screenshot: {output}")
        window.close()


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(["fdtd-screenshot"])
    image_dir = PROJECT_DIR / "docs" / "images"
    capture("dark", image_dir / "fdtd-runner-dark.png")
    capture("light", image_dir / "fdtd-runner-light.png")
    capture(
        "dark",
        image_dir / "fdtd-runner-compact.png",
        width=760,
        height=800,
    )
