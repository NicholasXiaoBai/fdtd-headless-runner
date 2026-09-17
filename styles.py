"""Light and dark QSS themes for the scientific desktop UI."""

from __future__ import annotations


def application_stylesheet(theme: str) -> str:
    dark = theme == "dark"
    colors = {
        "window": "#15181D" if dark else "#F4F6F8",
        "panel": "#1C2026" if dark else "#FFFFFF",
        "panel_alt": "#20252C" if dark else "#F8FAFC",
        "border": "#323842" if dark else "#D9DEE5",
        "border_hover": "#4B5563" if dark else "#AAB3BE",
        "text": "#E7EAF0" if dark else "#1F2933",
        "muted": "#949EAC" if dark else "#667085",
        "input": "#15191F" if dark else "#FFFFFF",
        "primary": "#3B82F6" if dark else "#2563EB",
        "primary_hover": "#60A5FA" if dark else "#1D4ED8",
        "success": "#4ADE80" if dark else "#15803D",
        "success_bg": "#163522" if dark else "#EAF7EE",
        "warning": "#FBBF24" if dark else "#B45309",
        "warning_bg": "#3A2B12" if dark else "#FFF7E6",
        "danger": "#FB7185" if dark else "#C2414D",
        "danger_bg": "#3D1E25" if dark else "#FDECEF",
        "console": "#0D1117",
        "console_border": "#2B313B",
        "console_text": "#C9D1D9",
        "disabled": "#3A4049" if dark else "#D8DDE4",
    }
    return f"""
* {{
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 10pt;
    color: {colors['text']};
}}
QMainWindow, QWidget#Root {{ background: {colors['window']}; }}
QWidget {{ selection-background-color: {colors['primary']}; selection-color: #FFFFFF; }}

QFrame#Header {{
    background: {colors['window']};
    border: none;
}}
QLabel#HeaderTitle {{ font-size: 20pt; font-weight: 650; }}
QLabel#HeaderSubtitle {{ color: {colors['muted']}; font-size: 9.5pt; }}
QLabel#SectionTitle {{ font-size: 11.5pt; font-weight: 650; }}
QLabel#SectionDescription, QLabel#Muted {{ color: {colors['muted']}; font-size: 9pt; }}

QFrame#Card {{
    background: {colors['panel']};
    border: 1px solid {colors['border']};
    border-radius: 10px;
}}
QFrame#StatusPanel {{
    background: {colors['panel_alt']};
    border: 1px solid {colors['border']};
    border-radius: 8px;
}}

QLineEdit {{
    background: {colors['input']};
    border: 1px solid {colors['border']};
    border-radius: 6px;
    padding: 7px 9px;
    min-height: 20px;
}}
QLineEdit:hover {{ border-color: {colors['border_hover']}; }}
QLineEdit:focus {{ border: 1px solid {colors['primary']}; }}
QLineEdit[pathState="valid"] {{ border-color: {colors['success']}; }}
QLineEdit[pathState="invalid"] {{ border-color: {colors['danger']}; }}
QLineEdit[pathState="warning"] {{ border-color: {colors['warning']}; }}

QPushButton, QToolButton {{
    background: {colors['panel_alt']};
    border: 1px solid {colors['border']};
    border-radius: 6px;
    padding: 7px 12px;
}}
QPushButton:hover, QToolButton:hover {{ border-color: {colors['border_hover']}; background: {colors['panel']}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {colors['input']}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {colors['muted']}; background: {colors['disabled']}; border-color: {colors['disabled']}; }}
QPushButton#PrimaryButton {{
    background: {colors['primary']};
    color: #FFFFFF;
    border-color: {colors['primary']};
    font-weight: 650;
    padding: 9px 18px;
}}
QPushButton#PrimaryButton:hover {{ background: {colors['primary_hover']}; border-color: {colors['primary_hover']}; }}
QPushButton#DangerButton {{ color: {colors['danger']}; border-color: {colors['danger']}; font-weight: 600; }}
QPushButton#DangerButton:hover {{ background: {colors['danger_bg']}; }}
QToolButton#IconButton {{ padding: 6px; min-width: 22px; min-height: 22px; }}
QPushButton#GhostButton {{ background: transparent; border-color: transparent; color: {colors['muted']}; }}
QPushButton#GhostButton:hover {{ color: {colors['text']}; background: {colors['panel_alt']}; border-color: {colors['border']}; }}

QLabel[badgeState="valid"] {{ color: {colors['success']}; background: {colors['success_bg']}; border: 1px solid {colors['success']}; border-radius: 8px; padding: 3px 8px; }}
QLabel[badgeState="invalid"] {{ color: {colors['danger']}; background: {colors['danger_bg']}; border: 1px solid {colors['danger']}; border-radius: 8px; padding: 3px 8px; }}
QLabel[badgeState="warning"] {{ color: {colors['warning']}; background: {colors['warning_bg']}; border: 1px solid {colors['warning']}; border-radius: 8px; padding: 3px 8px; }}
QLabel[badgeState="neutral"] {{ color: {colors['muted']}; background: {colors['panel_alt']}; border: 1px solid {colors['border']}; border-radius: 8px; padding: 3px 8px; }}

QLabel[runState="READY"] {{ color: {colors['success']}; font-weight: 700; }}
QLabel[runState="RUNNING"] {{ color: {colors['primary_hover']}; font-weight: 700; }}
QLabel[runState="FINISHED"] {{ color: {colors['success']}; font-weight: 700; }}
QLabel[runState="FAILED"] {{ color: {colors['danger']}; font-weight: 700; }}
QLabel[runState="STOPPED"] {{ color: {colors['warning']}; font-weight: 700; }}

QPlainTextEdit#CommandPreview {{
    background: {colors['input']};
    border: 1px solid {colors['border']};
    border-radius: 6px;
    padding: 8px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 9pt;
}}
QPlainTextEdit#Console {{
    background: {colors['console']};
    color: {colors['console_text']};
    border: none;
    padding: 10px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 9.5pt;
    selection-background-color: #264F78;
}}
QFrame#ConsoleFrame {{ background: {colors['console']}; border: 1px solid {colors['console_border']}; border-radius: 10px; }}
QFrame#ConsoleHeader {{ background: #161B22; border: none; border-bottom: 1px solid {colors['console_border']}; border-top-left-radius: 10px; border-top-right-radius: 10px; }}
QFrame#ConsoleHeader QLabel {{ color: #C9D1D9; font-weight: 600; }}
QFrame#ConsoleHeader QPushButton {{ color: #9DA7B3; background: transparent; border-color: transparent; padding: 4px 8px; }}
QFrame#ConsoleHeader QPushButton:hover {{ color: #FFFFFF; background: #252C35; }}

QProgressBar {{ background: {colors['input']}; border: 1px solid {colors['border']}; border-radius: 4px; min-height: 6px; max-height: 6px; text-align: center; }}
QProgressBar::chunk {{ background: {colors['primary']}; border-radius: 3px; }}
QSplitter::handle {{ background: {colors['window']}; height: 5px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QComboBox {{ background: {colors['input']}; border: 1px solid {colors['border']}; border-radius: 6px; padding: 6px 9px; }}
QComboBox QAbstractItemView {{ background: {colors['panel']}; border: 1px solid {colors['border']}; selection-background-color: {colors['primary']}; }}
QDialog {{ background: {colors['window']}; }}
QMessageBox {{ background: {colors['window']}; }}
QToolTip {{ background: {colors['panel']}; color: {colors['text']}; border: 1px solid {colors['border']}; padding: 5px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {colors['border_hover']}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {colors['border_hover']}; border-radius: 4px; min-width: 24px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""
