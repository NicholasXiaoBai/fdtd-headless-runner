"""Pure FDTD runner configuration, validation, and discovery helpers.

This module intentionally has no GUI dependency.  The command order and
validation behavior are the compatibility boundary for every front end.
"""

from __future__ import annotations

import locale
import os
import re
import string
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence


FDTD_EXECUTABLE_NAME = "fdtd-solutions.exe"


@dataclass(frozen=True)
class RunConfiguration:
    fdtd_exe: Path
    fsp_file: Path
    lsf_file: Path
    log_dir: Path

    @property
    def cwd(self) -> Path:
        return self.fsp_file.parent

    @property
    def command(self) -> list[str]:
        return build_command(
            str(self.fdtd_exe),
            str(self.fsp_file),
            str(self.lsf_file),
            str(self.log_dir),
        )


@dataclass(frozen=True)
class ValidationResult:
    configuration: Optional[RunConfiguration]
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return self.configuration is not None and not self.errors


def clean_path(value: str) -> str:
    """Trim whitespace and one matching pair of pasted quotation marks."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def build_command(fdtd_exe: str, fsp_file: str, lsf_file: str, log_dir: str) -> list[str]:
    """Return the exact argv list passed to subprocess.Popen.

    Do not reorder this list without an explicit compatibility decision.
    """
    return [
        fdtd_exe,
        "-nw",
        "-trust-script",
        "-logall",
        "-o",
        log_dir,
        "-run",
        lsf_file,
        fsp_file,
    ]


def command_preview(command: Sequence[str]) -> str:
    """Format argv one item per line for display only."""
    path_positions = {0, 5, 7, 8}
    lines: list[str] = []
    for index, item in enumerate(command):
        if index in path_positions:
            escaped = item.replace('"', '\\"')
            lines.append(f'"{escaped}"')
        else:
            lines.append(item)
    return "\n".join(lines)


def format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def read_script_text(path: Path) -> str:
    """Read LSF robustly without allowing a decode failure to abort a run."""
    data = path.read_bytes()
    encodings = ["utf-8-sig", locale.getpreferredencoding(False), "utf-16"]
    tried: set[str] = set()
    for encoding in encodings:
        normalized = encoding.lower()
        if normalized in tried:
            continue
        tried.add(normalized)
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            pass
    return data.decode("utf-8", errors="replace")


def inspect_lsf(path: Path) -> list[str]:
    """Return advisory messages; never edit or reject the script."""
    text = read_script_text(path)
    warnings: list[str] = []
    if re.search(r"\b(?:plot|visualize)\s*\(", text, flags=re.IGNORECASE):
        warnings.append("LSF 中包含可视化命令；这些命令在无界面模式下可能没有必要。")
    if re.search(r"\bexit\s*;", text, flags=re.IGNORECASE):
        warnings.append("LSF 中包含 exit; 命令。")
    else:
        warnings.append("未检测到 exit; 命令；脚本结束后 FDTD 进程可能仍保持运行。")
    return warnings


def lsf_flags(path: Path) -> tuple[bool, bool]:
    """Return (has_exit, has_visualization) for compact GUI validation."""
    text = read_script_text(path)
    has_exit = bool(re.search(r"\bexit\s*;", text, flags=re.IGNORECASE))
    has_visualization = bool(
        re.search(r"\b(?:plot|visualize)\s*\(", text, flags=re.IGNORECASE)
    )
    return has_exit, has_visualization


def validate_run_configuration(
    fdtd_exe: str,
    fsp_file: str,
    lsf_file: str,
    log_dir: str,
    *,
    create_log_dir: bool = True,
) -> ValidationResult:
    """Validate inputs and, for an actual run, prove the log folder is writable."""
    fdtd_text = clean_path(fdtd_exe)
    fsp_text = clean_path(fsp_file)
    lsf_text = clean_path(lsf_file)
    log_text = clean_path(log_dir)
    errors: list[str] = []

    fdtd = Path(fdtd_text) if fdtd_text else None
    fsp = Path(fsp_text) if fsp_text else None
    lsf = Path(lsf_text) if lsf_text else None
    logs = Path(log_text) if log_text else None

    if fdtd is None or not fdtd.is_file():
        errors.append("FDTD 可执行文件不存在或不是文件。")
    elif fdtd.suffix.lower() != ".exe":
        errors.append("FDTD 可执行文件必须使用 .exe 扩展名。")
    elif fdtd.name.lower() != FDTD_EXECUTABLE_NAME:
        errors.append(f"所选可执行文件必须命名为 {FDTD_EXECUTABLE_NAME}。")

    if fsp is None or not fsp.is_file():
        errors.append("FSP 仿真文件不存在或不是文件。")
    elif fsp.suffix.lower() != ".fsp":
        errors.append("FSP 仿真文件必须使用 .fsp 扩展名。")

    if lsf is None or not lsf.is_file():
        errors.append("LSF 脚本不存在或不是文件。")
    elif lsf.suffix.lower() != ".lsf":
        errors.append("LSF 脚本必须使用 .lsf 扩展名。")

    if logs is None:
        errors.append("必须指定日志目录。")
    elif create_log_dir:
        try:
            logs.mkdir(parents=True, exist_ok=True)
            if not logs.is_dir():
                raise NotADirectoryError(str(logs))
            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix=".lumerical_runner_write_test_",
                dir=logs,
                encoding="utf-8",
                delete=True,
            ) as probe:
                probe.write("write test")
                probe.flush()
        except OSError as exc:
            errors.append(f"无法创建或写入日志目录：\n{exc}")

    if errors or fdtd is None or fsp is None or lsf is None or logs is None:
        return ValidationResult(None, tuple(errors))
    return ValidationResult(RunConfiguration(fdtd, fsp, lsf, logs), ())


def test_fdtd_executable(path_value: str) -> list[str]:
    """Perform the existing safe static executable test without launching FDTD."""
    path_text = clean_path(path_value)
    path = Path(path_text) if path_text else None
    problems: list[str] = []
    if path is None or not path.is_file():
        problems.append("所选可执行文件不存在或不是文件。")
    elif path.name.lower() != FDTD_EXECUTABLE_NAME:
        problems.append(f"所选文件的名称不是 {FDTD_EXECUTABLE_NAME}。")
    elif path.suffix.lower() != ".exe":
        problems.append("所选文件没有 .exe 扩展名。")
    else:
        try:
            with path.open("rb") as handle:
                signature = handle.read(2)
            if signature != b"MZ":
                problems.append("所选文件没有 Windows 可执行文件签名。")
        except OSError as exc:
            problems.append(f"Windows 无法读取该可执行文件：{exc}")
    return problems


def is_fdtd_executable(path_value: str | Path) -> bool:
    if not path_value:
        return False
    try:
        path = Path(path_value)
        return path.is_file() and path.name.lower() == FDTD_EXECUTABLE_NAME
    except OSError:
        return False


def _windows_program_files_roots(environ: Mapping[str, str]) -> list[Path]:
    roots: list[Path] = []
    env_lookup = {key.casefold(): value for key, value in environ.items()}
    for key in ("programw6432", "programfiles", "programfiles(x86)"):
        value = env_lookup.get(key, "").strip()
        if value:
            roots.append(Path(value))

    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            drive_mask = kernel32.GetLogicalDrives()
        except (AttributeError, OSError):
            kernel32 = None
            drive_mask = 0
        for index, letter in enumerate(string.ascii_uppercase):
            if drive_mask & (1 << index):
                drive = Path(f"{letter}:\\")
                drive_type = kernel32.GetDriveTypeW(str(drive)) if kernel32 is not None else 0
                if drive_type in (2, 3):
                    roots.extend([drive / "Program Files", drive / "Program Files (x86)"])
    return roots


def _fdtd_version_key(path: Path) -> tuple[int, str]:
    versions = []
    for part in path.parts:
        match = re.fullmatch(r"v(\d+)", part, flags=re.IGNORECASE)
        if match:
            versions.append(int(match.group(1)))
    return (max(versions, default=0), str(path).casefold())


def discover_fdtd_executable(
    saved_path: str = "",
    *,
    search_roots: Optional[list[Path]] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Optional[Path]:
    """Restore a valid saved path, then search only bounded standard locations."""
    saved = clean_path(saved_path)
    if saved and is_fdtd_executable(saved):
        return Path(saved)

    env = dict(os.environ if environ is None else environ)
    env_lookup = {key.casefold(): value for key, value in env.items()}
    candidates: list[Path] = []

    for key, value in env.items():
        if re.fullmatch(r"AWP_ROOT\d+", key, flags=re.IGNORECASE) and value.strip():
            candidates.append(Path(value.strip()) / "Lumerical" / "bin" / FDTD_EXECUTABLE_NAME)

    for key in ("lumerical_root", "lumerical_dir"):
        value = env_lookup.get(key, "").strip()
        if value:
            root = Path(value)
            candidates.extend([root / "bin" / FDTD_EXECUTABLE_NAME, root / FDTD_EXECUTABLE_NAME])

    for path_dir in env_lookup.get("path", "").split(os.pathsep):
        if path_dir.strip():
            candidates.append(Path(path_dir.strip()) / FDTD_EXECUTABLE_NAME)

    roots = search_roots if search_roots is not None else _windows_program_files_roots(env)
    patterns = (
        f"ANSYS Inc/v*/Lumerical/bin/{FDTD_EXECUTABLE_NAME}",
        f"ANSYS Inc/ANSYS Student/v*/Lumerical/bin/{FDTD_EXECUTABLE_NAME}",
        f"Lumerical/v*/bin/{FDTD_EXECUTABLE_NAME}",
        f"Lumerical/*/bin/{FDTD_EXECUTABLE_NAME}",
    )
    for root in roots:
        for pattern in patterns:
            try:
                candidates.extend(root.glob(pattern))
            except OSError:
                continue

    unique: dict[str, Path] = {}
    for candidate in candidates:
        if is_fdtd_executable(candidate):
            unique.setdefault(str(candidate).casefold(), candidate)
    if not unique:
        return None
    return max(unique.values(), key=_fdtd_version_key)
