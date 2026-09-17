from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PySide6.QtWidgets import QApplication

from fdtd_core import command_preview
from main_window import MainWindow
from settings_store import SettingsStore


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication(["fdtd-runner-tests"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="fdtd-gui-test-")
        root = Path(self.temp_dir.name)
        self.exe = root / "安装 目录" / "fdtd-solutions.exe"
        self.fsp = root / "仿真 文件" / "case & one.fsp"
        self.lsf = root / "脚本" / "run (final).lsf"
        self.log_dir = root / "日志 目录"
        for file_path in (self.exe, self.fsp, self.lsf):
            file_path.parent.mkdir(parents=True, exist_ok=True)
        self.exe.write_bytes(b"MZ" + b"\x00" * 64)
        self.fsp.write_bytes(b"fsp")
        self.lsf.write_text("run;\nexit;\n", encoding="utf-8")
        self.store = SettingsStore(root / "settings.ini")
        self.window = MainWindow(self.store, auto_discover=False)
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()
        self.temp_dir.cleanup()

    def _fill_valid_paths(self) -> None:
        self.window.fdtd_field.set_text(str(self.exe))
        self.window.fsp_field.set_text(str(self.fsp))
        self.window.lsf_field.set_text(str(self.lsf))
        self.window.log_field.set_text(str(self.log_dir))
        self.app.processEvents()

    def test_validation_and_exact_command_preview(self) -> None:
        self._fill_valid_paths()
        expected = command_preview(
            [
                str(self.exe),
                "-nw",
                "-trust-script",
                "-logall",
                "-o",
                str(self.log_dir),
                "-run",
                str(self.lsf),
                str(self.fsp),
            ]
        )
        self.assertEqual(self.window.command_preview.command(), expected)
        self.assertTrue(self.window.run_button.isEnabled())
        self.assertEqual(self.window.fdtd_field.status.text(), "有效")
        self.assertEqual(self.window.fsp_field.status.text(), "有效")
        self.assertEqual(self.window.lsf_field.status.text(), "有效")

    def test_state_switching_console_and_collapsible_preview(self) -> None:
        self.assertFalse(self.window.command_preview.is_expanded())
        self.window.command_preview.set_expanded(True)
        self.assertTrue(self.window.command_preview.is_expanded())
        self.window._set_run_state("RUNNING")
        self.assertFalse(self.window.run_button.isEnabled())
        self.assertTrue(self.window.stop_button.isEnabled())
        self.assertTrue(self.window.progress.isVisible())
        self.window.console.append_output("WARNING: test\nERROR: test\n")
        self.assertIn("ERROR: test", self.window.console.toPlainText())
        self.window._set_run_state("FINISHED")
        self.assertTrue(self.window.run_button.isEnabled())
        self.assertFalse(self.window.stop_button.isEnabled())

    def test_settings_save_and_restore(self) -> None:
        self._fill_valid_paths()
        self.window._apply_theme("light")
        self.window._save_paths()
        self.window._save_window_state()
        self.store.sync()

        restored = MainWindow(SettingsStore(self.store.ini_path), auto_discover=False)
        try:
            self.assertEqual(restored.fdtd_field.text(), str(self.exe))
            self.assertEqual(restored.fsp_field.text(), str(self.fsp))
            self.assertEqual(restored.lsf_field.text(), str(self.lsf))
            self.assertEqual(restored.log_field.text(), str(self.log_dir))
            self.assertEqual(restored.current_theme, "light")
        finally:
            restored.close()

    def test_responsive_layout_switches_between_two_and_one_columns(self) -> None:
        self.window.resize(760, 720)
        self.app.processEvents()
        files_index = self.window.cards_grid.indexOf(self.window.files_card)
        environment_index = self.window.cards_grid.indexOf(self.window.environment_card)
        self.assertEqual(self.window.cards_grid.getItemPosition(files_index)[:2], (0, 0))
        self.assertEqual(self.window.cards_grid.getItemPosition(environment_index)[:2], (1, 0))

        self.window.resize(1180, 860)
        self.app.processEvents()
        files_index = self.window.cards_grid.indexOf(self.window.files_card)
        environment_index = self.window.cards_grid.indexOf(self.window.environment_card)
        self.assertEqual(self.window.cards_grid.getItemPosition(files_index)[:2], (0, 0))
        self.assertEqual(self.window.cards_grid.getItemPosition(environment_index)[:2], (0, 1))

    def test_file_picker_results_and_drop_filters(self) -> None:
        self.log_dir.mkdir(parents=True)
        with patch("main_window.QFileDialog.getOpenFileName", return_value=(str(self.fsp), "")):
            self.window._browse_fsp()
        self.assertEqual(self.window.fsp_field.text(), str(self.fsp))

        with patch("main_window.QFileDialog.getOpenFileName", return_value=(str(self.lsf), "")):
            self.window._browse_lsf()
        self.assertEqual(self.window.lsf_field.text(), str(self.lsf))

        with patch(
            "main_window.QFileDialog.getExistingDirectory", return_value=str(self.log_dir)
        ):
            self.window._browse_log_dir()
        self.assertEqual(self.window.log_field.text(), str(self.log_dir))
        self.assertTrue(self.window.fsp_field.edit._acceptable(self.fsp))
        self.assertFalse(self.window.fsp_field.edit._acceptable(self.lsf))
        self.assertTrue(self.window.log_field.edit._acceptable(self.log_dir))


if __name__ == "__main__":
    unittest.main()
