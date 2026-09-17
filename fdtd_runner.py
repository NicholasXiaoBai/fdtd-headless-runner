"""Threaded FDTD subprocess runner with Qt signals and no QWidget dependency."""

from __future__ import annotations

import locale
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import QObject, Signal


class FDTDRunner(QObject):
    """Run one FDTD process at a time without blocking the Qt main thread.

    The Popen flags, merged stdout/stderr stream, and taskkill fallback preserve
    the behavior of the previous Tkinter implementation.
    """

    output_received = Signal(str)
    process_started = Signal(int)
    process_finished = Signal(str, object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._process_lock = threading.Lock()
        self._termination_lock = threading.Lock()
        self._process: Optional[subprocess.Popen[str]] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_requested = False

    @property
    def is_running(self) -> bool:
        with self._process_lock:
            return self._running

    @property
    def pid(self) -> Optional[int]:
        with self._process_lock:
            return self._process.pid if self._process is not None else None

    def start(self, command: Sequence[str], cwd: str | Path) -> bool:
        with self._process_lock:
            if self._running:
                return False
            self._running = True
            self._stop_requested = False
            self._process = None
        command_copy = [str(part) for part in command]
        cwd_copy = str(cwd)
        self._worker_thread = threading.Thread(
            target=self._process_worker,
            args=(command_copy, cwd_copy),
            name="fdtd-process-worker",
            daemon=True,
        )
        self._worker_thread.start()
        return True

    def request_stop(self) -> bool:
        with self._process_lock:
            if not self._running or self._stop_requested:
                return False
            self._stop_requested = True
            process = self._process
        if process is not None:
            threading.Thread(
                target=self._terminate_process_tree,
                args=(process,),
                name="fdtd-termination-worker",
                daemon=True,
            ).start()
        return True

    def wait(self, timeout: Optional[float] = None) -> bool:
        worker = self._worker_thread
        if worker is None:
            return True
        worker.join(timeout)
        return not worker.is_alive()

    def _process_worker(self, command: list[str], cwd: str) -> None:
        process: Optional[subprocess.Popen[str]] = None
        state = "FAILED"
        exit_code: Optional[int] = None
        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW

            output_encoding = locale.getpreferredencoding(False) or "utf-8"
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding=output_encoding,
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                shell=False,
            )
            with self._process_lock:
                self._process = process
                should_stop = self._stop_requested

            self.process_started.emit(process.pid)
            if should_stop:
                self._terminate_process_tree(process)

            if process.stdout is not None:
                for line in iter(process.stdout.readline, ""):
                    if line:
                        self.output_received.emit(line)
                process.stdout.close()

            exit_code = process.wait()
            with self._process_lock:
                was_stopped = self._stop_requested
            state = "STOPPED" if was_stopped else ("FINISHED" if exit_code == 0 else "FAILED")
        except Exception as exc:
            with self._process_lock:
                was_stopped = self._stop_requested
            state = "STOPPED" if was_stopped else "FAILED"
            self.output_received.emit(f"\n运行 FDTD 失败：{type(exc).__name__}: {exc}\n")
        finally:
            with self._process_lock:
                if self._process is process:
                    self._process = None
                self._running = False
            self.process_finished.emit(state, exit_code)

    def _terminate_process_tree(self, process: subprocess.Popen[str]) -> None:
        with self._termination_lock:
            if process.poll() is not None:
                return
            try:
                if os.name == "nt":
                    killer = subprocess.Popen(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding=locale.getpreferredencoding(False) or "utf-8",
                        errors="replace",
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        shell=False,
                    )
                    output, _ = killer.communicate(timeout=20)
                    if output.strip():
                        self.output_received.emit(output.rstrip() + "\n")
                    if killer.returncode != 0 and process.poll() is None:
                        process.terminate()
                else:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
            except Exception as exc:
                self.output_received.emit(f"终止进程时出错：{type(exc).__name__}: {exc}\n")
                try:
                    if process.poll() is None:
                        process.terminate()
                except OSError as fallback_exc:
                    self.output_received.emit(f"备用终止操作失败：{fallback_exc}\n")
