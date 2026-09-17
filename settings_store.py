"""QSettings-backed application preferences with legacy JSON migration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QSettings


PATH_KEYS = ("fdtd_exe", "fsp_file", "lsf_file", "log_dir")


class SettingsStore:
    def __init__(self, ini_path: Path, legacy_json_path: Optional[Path] = None) -> None:
        self.ini_path = Path(ini_path)
        self.legacy_json_path = Path(legacy_json_path) if legacy_json_path else None
        self.settings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self._migrate_legacy_json()

    def _migrate_legacy_json(self) -> None:
        if self.settings.value("migration/legacy_json", False, type=bool):
            return
        if self.legacy_json_path and self.legacy_json_path.is_file():
            try:
                with self.legacy_json_path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    for key in PATH_KEYS:
                        current = self.settings.value(f"paths/{key}", "", type=str)
                        legacy = data.get(key, "")
                        if not current and isinstance(legacy, str):
                            self.settings.setValue(f"paths/{key}", legacy)
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        self.settings.setValue("migration/legacy_json", True)
        self.settings.sync()

    def path_value(self, key: str) -> str:
        if key not in PATH_KEYS:
            raise KeyError(key)
        return self.settings.value(f"paths/{key}", "", type=str)

    def set_path_value(self, key: str, value: str) -> None:
        if key not in PATH_KEYS:
            raise KeyError(key)
        self.settings.setValue(f"paths/{key}", value)

    def theme(self) -> str:
        value = self.settings.value("appearance/theme", "dark", type=str).lower()
        return value if value in {"light", "dark"} else "dark"

    def set_theme(self, value: str) -> None:
        self.settings.setValue("appearance/theme", value if value in {"light", "dark"} else "dark")

    def geometry(self) -> QByteArray:
        value = self.settings.value("window/geometry", QByteArray())
        return value if isinstance(value, QByteArray) else QByteArray()

    def set_geometry(self, value: QByteArray) -> None:
        self.settings.setValue("window/geometry", value)

    def splitter_state(self) -> QByteArray:
        value = self.settings.value("window/splitter", QByteArray())
        return value if isinstance(value, QByteArray) else QByteArray()

    def set_splitter_state(self, value: QByteArray) -> None:
        self.settings.setValue("window/splitter", value)

    def sync(self) -> bool:
        self.settings.sync()
        return self.settings.status() == QSettings.Status.NoError

    def clear_window_layout(self) -> None:
        self.settings.remove("window/geometry")
        self.settings.remove("window/splitter")
        self.settings.sync()
