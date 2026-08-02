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

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

# Repo root: modules/pyside_workbench/theme.py → ../../
_ROOT = Path(__file__).resolve().parents[2]
_ICON_COLOR = _ROOT / "images" / "icons" / "color"
# QSS cannot draw checkbox ticks / spin arrows without images
_CHECK_TICK_BLUE = _ICON_COLOR / "checkbox_tick_blue.png"
_SPIN_UP = _ICON_COLOR / "spin_up.png"
_SPIN_DOWN = _ICON_COLOR / "spin_down.png"


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


def _qss_file_url(path: Path) -> str:
    """Absolute path for QSS ``url(...)`` (works when CWD is not the repo)."""
    return path.resolve().as_posix()


def build_workbench_qss() -> str:
    """Assemble stylesheet with resolved asset URLs (checkbox tick, spin arrows).

    Solid accent fill alone (no ``image``) produces a blue box with no
    checkmark — Fusion does not paint a tick on a fully restyled indicator.
    Gallery: checkbox C; spin E (accent steppers); primary OK C (soft blue).
    """
    extras: list[str] = []

    tick = _qss_file_url(_CHECK_TICK_BLUE) if _CHECK_TICK_BLUE.is_file() else ""
    if tick:
        # Option C: soft accent wash + blue tick (not solid fill, not plain white)
        extras.append(
            f"""
QCheckBox::indicator:checked {{
    background: {COLOR_PRESS_BG};
    border: 1.5px solid {COLOR_ACCENT};
    image: url({tick});
}}
QCheckBox::indicator:checked:hover {{
    background: {COLOR_HOVER_BG};
    border-color: {COLOR_ACCENT};
    image: url({tick});
}}
QCheckBox::indicator:checked:disabled {{
    background: {COLOR_DISABLED_BG};
    border-color: {COLOR_DISABLED_BORDER};
    image: url({tick});
}}
"""
        )
    else:
        extras.append(
            f"""
QCheckBox::indicator:checked {{
    background: {COLOR_PRESS_BG};
    border: 1.5px solid {COLOR_ACCENT};
}}
"""
        )

    # Spin option E: stacked steppers with accent-tinted strip + arrow images
    up = _qss_file_url(_SPIN_UP) if _SPIN_UP.is_file() else ""
    down = _qss_file_url(_SPIN_DOWN) if _SPIN_DOWN.is_file() else ""
    if up and down:
        extras.append(
            f"""
QSpinBox, QDoubleSpinBox {{
    padding-right: 2px;
    border-color: {COLOR_HOVER_BORDER};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border: none;
    border-left: 1px solid {COLOR_HOVER_BORDER};
    border-top-right-radius: 4px;
    background: {COLOR_HOVER_BG};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border: none;
    border-left: 1px solid {COLOR_HOVER_BORDER};
    border-top: 1px solid {COLOR_HOVER_BORDER};
    border-bottom-right-radius: 4px;
    background: {COLOR_HOVER_BG};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {COLOR_PRESS_BG};
}}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background: #C7D7FE;
}}
QSpinBox::up-button:disabled, QDoubleSpinBox::up-button:disabled,
QSpinBox::down-button:disabled, QDoubleSpinBox::down-button:disabled {{
    background: {COLOR_DISABLED_BG};
    border-left-color: {COLOR_DISABLED_BORDER};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({up});
    width: 9px;
    height: 9px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({down});
    width: 9px;
    height: 9px;
}}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled,
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{
    width: 9px;
    height: 9px;
}}
"""
        )

    return WORKBENCH_QSS + "\n" + "\n".join(extras)


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

    app.setStyleSheet(build_workbench_qss())


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
/* Primary OK — gallery option C: soft blue tint (not solid brick) */
QPushButton#btnPrimary {{
    background: {COLOR_PRESS_BG};
    color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_HOVER_BORDER};
    font-weight: 600;
}}
QPushButton#btnPrimary:hover {{
    background: #C7D7FE;
    border-color: #93C5FD;
    color: {COLOR_ACCENT_HOVER};
}}
QPushButton#btnPrimary:pressed {{
    background: #A5B4FC;
    border-color: #818CF8;
    color: #1E3A8A;
}}
QPushButton#btnPrimary:disabled {{
    background: {COLOR_DISABLED_BG};
    border-color: {COLOR_DISABLED_BORDER};
    color: {COLOR_DISABLED_TEXT};
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
    min-height: 24px;
    selection-background-color: {COLOR_ACCENT};
}}
/* Spin steppers styled in build_workbench_qss() (gallery option B) */
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
    width: 16px;
    height: 16px;
    border: 1.5px solid {COLOR_BORDER};
    border-radius: 3px;
    background: {COLOR_SURFACE};
}}
/* checked rules appended in build_workbench_qss() with tick image url */
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
    background: {STATE_COLORS['offline']};
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
QScrollArea#jogScroll {{
    background: transparent;
    border: none;
}}
QWidget#jogPanelContent {{
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
    /* Keep 50×50 tiles — do not allow dock squeeze to zero-out min size */
    min-width: 50px;
    max-width: 50px;
    min-height: 50px;
    max-height: 50px;
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
