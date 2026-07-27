"""----------------------------------------------------------------------------
    icons.py

    Load gsat's existing toolbar PNGs (images/icons/color + color-dis)
    into QIcon for the PySide workbench. Same assets as classic wx
    (images/icons.py / img2py embeds) — no new theme pack.
----------------------------------------------------------------------------"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap

# repo root: modules/pyside_workbench/icons.py → ../../
_ROOT = Path(__file__).resolve().parents[2]
_COLOR = _ROOT / "images" / "icons" / "color"
_COLOR_DIS = _ROOT / "images" / "icons" / "color-dis"

# Default toolbar glyph size (wx used 16x16 embeds; PNGs are typically 16).
TOOLBAR_ICON_SIZE = QSize(16, 16)

# Logical name → basename under images/icons/color/ (md5-matched to wx embeds).
# Disabled: same basename under color-dis/ when present.
ICON_FILES: dict[str, str] = {
    # Main / file
    "open": "folder-horizontal-open.png",
    "save": "save.png",
    # Program
    "run": "control.png",  # wx imgPlay
    "pause": "control-pause.png",
    "step": "control-stop.png",  # wx imgStep (historical name)
    "stop": "control-stop-square.png",
    "break": "control-record.png",
    "break_clear": "x.png",  # clear all BPs (no dedicated wx glyph)
    "set_pc": "arrow-left-marker.png",
    "reset_pc": "arrow-up-marker.png",
    "goto_pc": "marker.png",
    # Machine
    "machine_open": "plug-connect.png",
    "machine_close": "plug-disconnect.png",
    "refresh": "arrow-circle-315-gear.png",
    "cycle_start": "control-cycle-start.png",
    "feed_hold": "control-feed-hold.png",
    "queue_flush": "arrow-curve-270-gear.png",
    "machine_reset": "control-power-gear.png",
    "clear_alarm": "tick-circle-gear.png",
    "abort": "cross-circle.png",
    "local": "plug.png",
    # Remote
    "remote": "remote.png",
    "remote_disconnect": "plug-disconnect.png",
}

_cache: dict[str, QIcon] = {}


def icons_root() -> Path:
    return _COLOR


def has_icon(name: str) -> bool:
    fname = ICON_FILES.get(name)
    if not fname:
        return False
    return (_COLOR / fname).is_file()


def get_icon(name: str) -> QIcon:
    """Return a QIcon for a logical name, with Disabled mode from color-dis if any.

    Missing files yield an empty QIcon (callers can still show text).
    """
    if name in _cache:
        return _cache[name]

    fname = ICON_FILES.get(name)
    if not fname:
        ico = QIcon()
        _cache[name] = ico
        return ico

    path = _COLOR / fname
    if not path.is_file():
        ico = QIcon()
        _cache[name] = ico
        return ico

    ico = QIcon()
    pix = QPixmap(str(path))
    if not pix.isNull():
        ico.addPixmap(pix, QIcon.Mode.Normal, QIcon.State.Off)

    dis_path = _COLOR_DIS / fname
    if dis_path.is_file():
        dis_pix = QPixmap(str(dis_path))
        if not dis_pix.isNull():
            ico.addPixmap(dis_pix, QIcon.Mode.Disabled, QIcon.State.Off)

    _cache[name] = ico
    return ico


def apply_action_icon(action, name: str) -> bool:
    """Set action icon from logical name. Returns True if a pixmap was loaded."""
    ico = get_icon(name)
    if ico.isNull():
        return False
    action.setIcon(ico)
    return True
