"""Reusable PySide6 widgets for paths, badges, command preview, and console."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFontDatabase, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class StatusBadge(QLabel):
    def __init__(self, text: str = "等待检查", state: str = "neutral", parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.set_state(state, text)

    def set_state(self, state: str, text: Optional[str] = None) -> None:
        self.setProperty("badgeState", state)
        if text is not None:
            self.setText(text)
        refresh_style(self)


class DropLineEdit(QLineEdit):
    path_dropped = Signal(str)

    def __init__(self, *, accepts_directory: bool = False, suffixes: Iterable[str] = (), parent=None) -> None:
        super().__init__(parent)
        self.accepts_directory = accepts_directory
        self.suffixes = {suffix.lower() for suffix in suffixes}
        self.setAcceptDrops(True)
        self.setClearButtonEnabled(True)

    def _acceptable(self, path: Path) -> bool:
        if self.accepts_directory:
            return path.is_dir()
        if not path.is_file():
            return False
        return not self.suffixes or path.suffix.lower() in self.suffixes

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile() and self._acceptable(Path(urls[0].toLocalFile())):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if self._acceptable(path):
                value = str(path)
                self.setText(value)
                self.path_dropped.emit(value)
                event.acceptProposedAction()
                return
        event.ignore()


class PathField(QWidget):
    text_changed = Signal(str)
    browse_requested = Signal()
    path_dropped = Signal(str)

    def __init__(
        self,
        label: str,
        placeholder: str,
        *,
        accepts_directory: bool = False,
        suffixes: Iterable[str] = (),
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(label)
        self.label.setObjectName("FieldLabel")
        self.status = StatusBadge("未选择", "neutral")
        top.addWidget(self.label)
        top.addStretch(1)
        top.addWidget(self.status)
        layout.addLayout(top)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)
        self.edit = DropLineEdit(accepts_directory=accepts_directory, suffixes=suffixes)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setProperty("pathState", "neutral")
        self.browse_button = QToolButton()
        self.browse_button.setObjectName("IconButton")
        self.browse_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.browse_button.setToolTip("浏览")
        self.browse_button.setAccessibleName(f"浏览 {label}")
        row.addWidget(self.edit, 1)
        row.addWidget(self.browse_button)
        layout.addLayout(row)

        self.edit.textChanged.connect(self.text_changed)
        self.edit.path_dropped.connect(self.path_dropped)
        self.browse_button.clicked.connect(self.browse_requested)

    def text(self) -> str:
        return self.edit.text().strip()

    def set_text(self, value: str) -> None:
        self.edit.setText(value)

    def set_validation(self, state: str, text: str) -> None:
        self.edit.setProperty("pathState", state)
        self.status.set_state(state, text)
        refresh_style(self.edit)


class CommandPreview(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        header = QHBoxLayout()
        self.toggle_button = QPushButton("显示命令")
        self.toggle_button.setCheckable(True)
        self.copy_button = QPushButton("复制")
        self.copy_button.setVisible(False)
        header.addWidget(self.toggle_button)
        header.addStretch(1)
        header.addWidget(self.copy_button)
        layout.addLayout(header)
        self.text = QPlainTextEdit()
        self.text.setObjectName("CommandPreview")
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setMaximumHeight(175)
        self.text.setVisible(False)
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.text.setFont(fixed_font)
        layout.addWidget(self.text)
        self.toggle_button.toggled.connect(self._set_expanded)
        self.copy_button.clicked.connect(self.copy)

    def _set_expanded(self, expanded: bool) -> None:
        self.text.setVisible(expanded)
        self.copy_button.setVisible(expanded)
        self.toggle_button.setText("隐藏命令" if expanded else "显示命令")

    def set_command(self, command: str) -> None:
        self.text.setPlainText(command)

    def command(self) -> str:
        return self.text.toPlainText()

    def is_expanded(self) -> bool:
        return self.toggle_button.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self.toggle_button.setChecked(expanded)

    def copy(self) -> None:
        QApplication.clipboard().setText(self.text.toPlainText())
        self.copy_button.setText("已复制")


class ConsoleWidget(QPlainTextEdit):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Console")
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.document().setMaximumBlockCount(50000)
        self.setPlaceholderText("仿真输出将实时显示在这里。")
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

    def append_output(self, text: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        lowered = text.lower()
        if re.search(r"\b(error|failed|fatal)\b|错误|失败", lowered):
            fmt.setForeground(QColor("#F87171"))
        elif re.search(r"\bwarning\b|警告|未检测到", lowered):
            fmt.setForeground(QColor("#FBBF24"))
        elif re.search(r"finished|已完成|已结束", lowered):
            fmt.setForeground(QColor("#4ADE80"))
        else:
            fmt.setForeground(QColor("#C9D1D9"))
        cursor.insertText(text, fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()


def make_card(title: str, description: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)
    title_label = QLabel(title)
    title_label.setObjectName("SectionTitle")
    layout.addWidget(title_label)
    if description:
        subtitle = QLabel(description)
        subtitle.setObjectName("SectionDescription")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
    return card, layout
