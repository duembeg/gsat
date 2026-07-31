"""----------------------------------------------------------------------------
    theme.py

    Shared visual system for the PySide workbench.

    Design decisions (keep future panels consistent):
    - Fusion base + compact QSS (not a full custom paint engine)
    - Cool neutral chrome; state color only for machine/run status
    - Monospace for DRO, G-code, console (debug density)
    - Grouped action bars over one endless button row
    - Machine state must stay obvious (Idle / Run / Hold / Alarm / Break)

    Component roles (same language as the jog pad polish — not one flat look):
    - toolbar strip …………… soft surface + separators; scannable bar
    - toolbar tool button … nearly flat glyph tiles, soft hover/checked
    - form QPushButton …… outlined, light fill on hover
    - pad button …………… densest flat tiles (jogPadButton)
    - primary / danger …… accent fill / red tint (object names)
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
COLOR_HOVER_BG = "#EEF2FF"
COLOR_HOVER_BORDER = "#BFDBFE"
COLOR_PRESS_BG = "#DBEAFE"
COLOR_PRESS_BORDER = "#93C5FD"
COLOR_DISABLED_BG = "#F8F9FB"
COLOR_DISABLED_BORDER = "#E8EAED"
COLOR_DISABLED_TEXT = "#A0A8B3"
COLOR_DANGER = "#B91C1C"
COLOR_DANGER_BG = "#FEF2F2"
COLOR_DANGER_BORDER = "#FECACA"
COLOR_DANGER_HOVER = "#FEE2E2"

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
/* =========================================================================
   Shell
   ========================================================================= */
QMainWindow, QDialog {{
    background: {COLOR_BG};
    color: {COLOR_TEXT};
}}
QMenuBar {{
    background: {COLOR_SURFACE};
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 2px 6px;
}}
QMenuBar::item {{
    padding: 4px 8px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: {COLOR_HOVER_BG};
    color: {COLOR_TEXT};
}}
QMenu {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {COLOR_HOVER_BG};
}}
QMenu::separator {{
    height: 1px;
    background: {COLOR_BORDER};
    margin: 4px 8px;
}}
QStatusBar {{
    background: {COLOR_SURFACE};
    border-top: 1px solid {COLOR_BORDER};
    color: {COLOR_MUTED};
    font-size: 12px;
}}
QDockWidget {{
    color: {COLOR_TEXT};
    titlebar-close-icon: none;
}}
QDockWidget::title {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    text-align: left;
}}

/* =========================================================================
   Toolbars — soft strip; buttons stay glyph-first (not heavy boxes)
   ========================================================================= */
QToolBar {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    spacing: 2px;
    padding: 3px 5px;
    margin: 1px 2px;
}}
QToolBar::separator {{
    width: 1px;
    background: {COLOR_BORDER};
    margin: 6px 5px;
}}
/* Icon-only (and text-beside) tools on a strip */
QToolBar QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 6px;
    margin: 0px 1px;
    min-height: 0px;
    min-width: 0px;
}}
QToolBar QToolButton:hover {{
    background: {COLOR_HOVER_BG};
    border: 1px solid {COLOR_HOVER_BORDER};
}}
QToolBar QToolButton:pressed {{
    background: {COLOR_PRESS_BG};
    border: 1px solid {COLOR_PRESS_BORDER};
}}
QToolBar QToolButton:checked {{
    background: {COLOR_PRESS_BG};
    border: 1px solid {COLOR_PRESS_BORDER};
}}
QToolBar QToolButton:disabled {{
    background: transparent;
    border: 1px solid transparent;
    color: {COLOR_DISABLED_TEXT};
}}
/* Main bar Open split + text-beside need a little more room */
QToolBar QToolButton#btnOpenGcode {{
    padding: 4px 10px;
    font-weight: 500;
}}
/* Abort / other destructive toolbar tools */
QToolBar QToolButton#toolButtonDanger {{
    background: transparent;
    border: 1px solid transparent;
}}
QToolBar QToolButton#toolButtonDanger:hover {{
    background: {COLOR_DANGER_HOVER};
    border: 1px solid {COLOR_DANGER_BORDER};
}}
QToolBar QToolButton#toolButtonDanger:pressed {{
    background: #FECACA;
    border: 1px solid #F87171;
}}
QToolBar QToolButton#toolButtonDanger:disabled {{
    background: transparent;
    border: 1px solid transparent;
}}

/* =========================================================================
   Form buttons — outlined soft (dialogs, panels); not flat pad tiles
   ========================================================================= */
QPushButton {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 5px 12px;
    min-height: 24px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {COLOR_HOVER_BG};
    border-color: {COLOR_HOVER_BORDER};
}}
QPushButton:pressed {{
    background: {COLOR_PRESS_BG};
    border-color: {COLOR_PRESS_BORDER};
}}
QPushButton:disabled {{
    color: {COLOR_DISABLED_TEXT};
    background: {COLOR_DISABLED_BG};
    border-color: {COLOR_DISABLED_BORDER};
}}
QPushButton:checked {{
    background: {COLOR_PRESS_BG};
    border-color: {COLOR_PRESS_BORDER};
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
QPushButton#btnPrimary:pressed {{
    background: #1E40AF;
    border-color: #1E40AF;
}}
QPushButton#btnPrimary:disabled {{
    background: #93C5FD;
    border-color: #93C5FD;
    color: #F8FAFC;
}}
QPushButton#btnDanger {{
    background: {COLOR_DANGER_BG};
    border-color: {COLOR_DANGER_BORDER};
    color: {COLOR_DANGER};
}}
QPushButton#btnDanger:hover {{
    background: {COLOR_DANGER_HOVER};
    border-color: #F87171;
}}
QDialogButtonBox QPushButton {{
    min-width: 80px;
    padding: 6px 14px;
}}
/* Standalone tool buttons (not in a toolbar) — same soft language */
QToolButton {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 0px;
}}
QToolButton:hover {{
    background: {COLOR_HOVER_BG};
    border-color: {COLOR_HOVER_BORDER};
}}
QToolButton:pressed {{
    background: {COLOR_PRESS_BG};
    border-color: {COLOR_PRESS_BORDER};
}}
QToolButton:disabled {{
    color: {COLOR_DISABLED_TEXT};
    background: {COLOR_DISABLED_BG};
    border-color: {COLOR_DISABLED_BORDER};
}}

/* =========================================================================
   Inputs / chrome
   ========================================================================= */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 5px;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: {COLOR_ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background: {COLOR_DISABLED_BG};
    color: {COLOR_DISABLED_TEXT};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QGroupBox {{
    font-weight: 600;
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 10px;
    background: {COLOR_SURFACE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {COLOR_MUTED};
}}
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    background: {COLOR_SURFACE};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 14px;
    margin-right: 2px;
    color: {COLOR_MUTED};
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-bottom: 1px solid {COLOR_SURFACE};
    color: {COLOR_TEXT};
}}
QTabBar::tab:hover:!selected {{
    background: {COLOR_HOVER_BG};
    color: {COLOR_TEXT};
}}
QCheckBox {{
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 3px;
    background: {COLOR_SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: {COLOR_HOVER_BORDER};
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
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #C5CAD3;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #A8B0BC;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #C5CAD3;
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
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
    border-radius: 8px;
}}

/* Console fg/bg/font come from /console/* via ConsolePanel — do not hardcode. */
QPlainTextEdit#consoleView {{
    font-family: monospace;
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 4px;
}}
QLineEdit#cliInput {{
    font-family: monospace;
    font-size: 12px;
}}
QLineEdit#droAxis, QLineEdit#droState {{
    font-family: monospace;
    font-size: 20px;
    font-weight: 700;
    background: #0B1220;
    color: #F8FAFC;
    border: 1px solid #1E293B;
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 28px;
}}

/* =========================================================================
   Jog pad roles (densest flat tiles — same tokens, less chrome)
   ========================================================================= */
QWidget#jogPanel {{
    background: transparent;
}}
QFrame#jogPad {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
}}
QToolButton#jogPadButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 1px;
    margin: 0px;
    min-height: 0px;
    min-width: 0px;
}}
QToolButton#jogPadButton:hover {{
    background: {COLOR_HOVER_BG};
    border: 1px solid {COLOR_HOVER_BORDER};
}}
QToolButton#jogPadButton:pressed {{
    background: {COLOR_PRESS_BG};
    border: 1px solid {COLOR_PRESS_BORDER};
}}
QToolButton#jogPadButton:disabled {{
    background: transparent;
    border: 1px solid transparent;
}}
QPushButton#jogPresetButton {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 5px;
    padding: 3px 4px;
    min-height: 24px;
    min-width: 36px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#jogPresetButton:hover {{
    background: {COLOR_HOVER_BG};
    border-color: {COLOR_HOVER_BORDER};
}}
QPushButton#jogPresetButton:pressed {{
    background: {COLOR_PRESS_BG};
}}
QPushButton#jogCustomButton {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 28px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#jogCustomButton:hover {{
    background: {COLOR_HOVER_BG};
    border-color: {COLOR_HOVER_BORDER};
}}
QPushButton#jogCustomButton:disabled {{
    color: {COLOR_DISABLED_TEXT};
    background: {COLOR_DISABLED_BG};
    border-color: {COLOR_DISABLED_BORDER};
}}
QDoubleSpinBox#jogSpin {{
    min-height: 26px;
    padding: 3px 6px;
    font-size: 13px;
}}
QCheckBox#jogRapid {{
    spacing: 6px;
    font-weight: 500;
}}
"""
