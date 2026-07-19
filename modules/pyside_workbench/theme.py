"""----------------------------------------------------------------------------
    theme.py

    Shared visual system for the PySide workbench.

    Design decisions (keep future panels consistent):
    - Fusion base + compact stylesheet (not a full custom paint engine)
    - Cool neutral chrome; state color only for machine/run status
    - Monospace for DRO, G-code, console (debug density)
    - Grouped action bars over one endless button row
    - Machine state must stay obvious (Idle / Run / Hold / Alarm / Break)
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory


# --- palette tokens ---
COLOR_BG = "#F4F5F7"
COLOR_SURFACE = "#FFFFFF"
COLOR_BORDER = "#D0D5DD"
COLOR_TEXT = "#1A1D23"
COLOR_MUTED = "#5C6570"
COLOR_ACCENT = "#2563EB"
COLOR_ACCENT_HOVER = "#1D4ED8"

# Machine / run state (used by status badge + DRO state field)
STATE_COLORS = {
    "idle": "#15803D",
    "run": "#2563EB",
    "hold": "#CA8A04",
    "alarm": "#DC2626",
    "break": "#C2410C",
    "pause": "#CA8A04",
    "jog": "#7C3AED",
    "unknown": "#5C6570",
    "remote": "#0E7490",
    "offline": "#94A3B8",
}


def mono_font(point_size: int = 11, bold: bool = False) -> QFont:
    f = QFont("Monospace")
    f.setStyleHint(QFont.StyleHint.TypeWriter)
    f.setPointSize(point_size)
    f.setBold(bold)
    return f


def state_color_key(stat: str | None, sw_state: int | None = None) -> str:
    """Map machine status string / sw state to a token key."""
    s = (stat or "").strip().lower()
    if "alarm" in s:
        return "alarm"
    if "hold" in s or "door" in s:
        return "hold"
    if "jog" in s:
        return "jog"
    if "run" in s or "cycle" in s:
        return "run"
    if "idle" in s:
        return "idle"
    # software states from config.py
    try:
        import modules.config as gc

        if sw_state == gc.STATE_RUN:
            return "run"
        if sw_state == gc.STATE_BREAK:
            return "break"
        if sw_state == gc.STATE_PAUSE:
            return "pause"
        if sw_state == gc.STATE_IDLE:
            return "idle"
        if sw_state == gc.STATE_ABORT:
            return "alarm"
    except Exception:
        pass
    return "unknown"


def apply_app_theme(app: QApplication) -> None:
    """Apply Fusion + workbench stylesheet once at startup."""
    if "Fusion" in QStyleFactory.keys():
        app.setStyle(QStyleFactory.create("Fusion"))

    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(COLOR_BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(COLOR_SURFACE))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#EEF0F3"))
    pal.setColor(QPalette.ColorRole.Text, QColor(COLOR_TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(COLOR_SURFACE))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(COLOR_ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)

    app.setStyleSheet(WORKBENCH_QSS)


WORKBENCH_QSS = f"""
/* --- global --- */
QMainWindow, QDialog {{
    background: {COLOR_BG};
    color: {COLOR_TEXT};
}}
QMenuBar {{
    background: {COLOR_SURFACE};
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 2px 4px;
}}
QMenuBar::item:selected {{
    background: #E8EEF9;
    color: {COLOR_TEXT};
}}
QStatusBar {{
    background: {COLOR_SURFACE};
    border-top: 1px solid {COLOR_BORDER};
    color: {COLOR_MUTED};
    font-size: 12px;
}}
QToolBar {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    spacing: 4px;
    padding: 4px 6px;
    margin: 0px;
}}
QToolBar::separator {{
    width: 1px;
    background: {COLOR_BORDER};
    margin: 4px 6px;
}}
QToolButton, QPushButton {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 5px;
    padding: 5px 10px;
    min-height: 22px;
}}
QToolButton:hover, QPushButton:hover {{
    background: #EEF2FF;
    border-color: #93C5FD;
}}
QToolButton:pressed, QPushButton:pressed {{
    background: #DBEAFE;
}}
QToolButton:disabled, QPushButton:disabled {{
    color: #A0A8B3;
    background: #F8F9FB;
    border-color: #E5E7EB;
}}
QPushButton#btnPrimary {{
    background: {COLOR_ACCENT};
    color: white;
    border-color: {COLOR_ACCENT};
    font-weight: 600;
}}
QPushButton#btnPrimary:hover {{
    background: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
QPushButton#btnDanger {{
    background: #FEF2F2;
    border-color: #FECACA;
    color: #B91C1C;
}}
QPushButton#btnDanger:hover {{
    background: #FEE2E2;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 4px 6px;
    min-height: 22px;
    selection-background-color: {COLOR_ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
QGroupBox {{
    font-weight: 600;
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    background: {COLOR_SURFACE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {COLOR_MUTED};
}}
QSplitter::handle {{
    background: {COLOR_BORDER};
}}
QSplitter::handle:horizontal {{
    width: 3px;
}}
QSplitter::handle:vertical {{
    height: 3px;
}}
QLabel#sectionLabel {{
    color: {COLOR_MUTED};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}}
QLabel#statusBadge {{
    border-radius: 10px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 12px;
    color: white;
    background: {STATE_COLORS["offline"]};
}}
QFrame#toolbarStrip {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
}}
QPlainTextEdit#consoleView {{
    font-family: monospace;
    font-size: 11px;
    background: #0F172A;
    color: #E2E8F0;
    border: 1px solid #1E293B;
    border-radius: 4px;
    padding: 4px;
}}
QLineEdit#cliInput {{
    font-family: monospace;
    font-size: 12px;
}}
QLineEdit#droAxis {{
    font-family: monospace;
    font-size: 20px;
    font-weight: 700;
    background: #0B1220;
    color: #F8FAFC;
    border: 1px solid #1E293B;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 28px;
}}
QLineEdit#droState {{
    font-family: monospace;
    font-size: 14px;
    font-weight: 700;
    border-radius: 4px;
    padding: 4px 8px;
}}
"""
