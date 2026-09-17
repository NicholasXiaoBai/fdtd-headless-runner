import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from fdtd_core import (  # noqa: E402
    build_command,
    command_preview,
    discover_fdtd_executable,
    inspect_lsf,
    validate_run_configuration,
)


class CoreTests(unittest.TestCase):
    def test_command_argument_order_is_unchanged(self):
        base = "D:\\Desktop\\code\\1.NPS\\中文 光栅&FDTD\\透射(2D)"
        command = build_command(
            "D:\\Program Files\\ANSYS Inc\\v261\\Lumerical\\bin\\fdtd-solutions.exe",
            base + "\\simulation.fsp",
            base + "\\script.lsf",
            base + "\\logs",
        )
        self.assertEqual(
            command,
            [
                "D:\\Program Files\\ANSYS Inc\\v261\\Lumerical\\bin\\fdtd-solutions.exe",
                "-nw",
                "-trust-script",
                "-logall",
                "-o",
                base + "\\logs",
                "-run",
                base + "\\script.lsf",
                base + "\\simulation.fsp",
            ],
        )
        self.assertIn('"' + base + "\\logs" + '"', command_preview(command))

    def test_discovery_prefers_saved_path_and_newest_standard_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Program Files"
            older = root / "ANSYS Inc" / "v251" / "Lumerical" / "bin" / "fdtd-solutions.exe"
            newer = root / "ANSYS Inc" / "v261" / "Lumerical" / "bin" / "fdtd-solutions.exe"
            custom = Path(temp_dir) / "自定义" / "fdtd-solutions.exe"
            for path in (older, newer, custom):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"MZ")
            self.assertEqual(
                discover_fdtd_executable(search_roots=[root], environ={"PATH": ""}),
                newer,
            )
            self.assertEqual(
                discover_fdtd_executable(str(custom), search_roots=[root], environ={"PATH": ""}),
                custom,
            )

    def test_discovery_reads_ansys_environment_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ansys_root = Path(temp_dir) / "v261"
            expected = ansys_root / "Lumerical" / "bin" / "fdtd-solutions.exe"
            expected.parent.mkdir(parents=True)
            expected.write_bytes(b"MZ")
            self.assertEqual(
                discover_fdtd_executable(
                    search_roots=[], environ={"AWP_ROOT261": str(ansys_root), "PATH": ""}
                ),
                expected,
            )

    def test_lsf_inspection_remains_advisory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "检查 script.lsf"
            path.write_text("plot(x);\nvisualize(result);\n", encoding="utf-8")
            warnings = inspect_lsf(path)
        self.assertTrue(any("可视化" in warning for warning in warnings))
        self.assertTrue(any("未检测到 exit;" in warning for warning in warnings))

    @unittest.skipUnless(os.name == "nt", "Windows executable validation")
    def test_validation_creates_log_directory_and_keeps_fsp_cwd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "中文 A&B (test)"
            root.mkdir()
            exe = root / "fdtd-solutions.exe"
            fsp = root / "simulation.fsp"
            lsf = root / "script.lsf"
            exe.write_bytes(b"MZ")
            fsp.write_bytes(b"fsp")
            lsf.write_text("exit;", encoding="utf-8")
            logs = root / "logs"
            result = validate_run_configuration(str(exe), str(fsp), str(lsf), str(logs))
            self.assertTrue(result.is_valid, result.errors)
            self.assertEqual(result.configuration.cwd, root)
            self.assertTrue(logs.is_dir())


if __name__ == "__main__":
    unittest.main()
