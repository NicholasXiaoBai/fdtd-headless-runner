import os
import sys
import time
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from fdtd_runner import FDTDRunner  # noqa: E402


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def _wait_with_events(self, runner: FDTDRunner, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        while runner.is_running and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertFalse(runner.is_running)

    def test_worker_preserves_unicode_and_shell_metacharacters(self):
        runner = FDTDRunner()
        results = []
        runner.process_finished.connect(lambda state, code: results.append((state, code)))
        special = "D:\\实验目录\\A&B (test)\\simulation.fsp"
        child_code = (
            "import sys; p=sys.argv[1]; "
            "raise SystemExit(0 if '\\u5b9e\\u9a8c' in p and '&' in p and '(' in p else 7)"
        )
        self.assertTrue(runner.start([sys.executable, "-B", "-c", child_code, special], os.getcwd()))
        self._wait_with_events(runner)
        self.assertEqual(results, [("FINISHED", 0)])

    @unittest.skipUnless(os.name == "nt", "Windows process-tree behavior")
    def test_stop_targets_only_the_started_process_tree(self):
        runner = FDTDRunner()
        started = []
        results = []
        runner.process_started.connect(started.append)
        runner.process_finished.connect(lambda state, code: results.append((state, code)))
        self.assertTrue(
            runner.start(
                [sys.executable, "-B", "-c", "import time; time.sleep(60)"],
                os.getcwd(),
            )
        )
        deadline = time.monotonic() + 5
        while not started and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertTrue(started)
        self.assertTrue(runner.request_stop())
        self._wait_with_events(runner)
        self.assertEqual(results[0][0], "STOPPED")


if __name__ == "__main__":
    unittest.main()
