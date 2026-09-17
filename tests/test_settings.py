import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from settings_store import SettingsStore  # noqa: E402


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_legacy_json_migration_and_qsettings_restore(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "settings.json"
            ini = root / "settings.ini"
            legacy.write_text(
                json.dumps(
                    {
                        "fdtd_exe": "D:/FDTD/fdtd-solutions.exe",
                        "fsp_file": "D:/data/test.fsp",
                        "lsf_file": "D:/data/test.lsf",
                        "log_dir": "D:/data/logs",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            first = SettingsStore(ini, legacy)
            self.assertEqual(first.path_value("fsp_file"), "D:/data/test.fsp")
            first.set_theme("light")
            first.set_path_value("fsp_file", "D:/新目录/new.fsp")
            self.assertTrue(first.sync())
            restored = SettingsStore(ini, legacy)
            self.assertEqual(restored.theme(), "light")
            self.assertEqual(restored.path_value("fsp_file"), "D:/新目录/new.fsp")


if __name__ == "__main__":
    unittest.main()
