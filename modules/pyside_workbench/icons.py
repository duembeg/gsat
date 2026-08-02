"""----------------------------------------------------------------------------
    icons.py

    Load gsat's existing toolbar PNGs (images/icons/color + color-dis)
    into QIcon for the PySide workbench. Same assets as classic wx
    (images/icons.py / img2py embeds) — no new theme pack.
----------------------------------------------------------------------------"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap

# repo root: modules/pyside_workbench/icons.py → ../../
_ROOT = Path(__file__).resolve().parents[2]
_COLOR = _ROOT / "images" / "icons" / "color"
_COLOR_DIS = _ROOT / "images" / "icons" / "color-dis"

# Default toolbar glyph size (most PNGs are 16x16; a few wx embeds are 32x32).
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
    "clear_alarm": "tick-circle-gear.png",  # 32x32 source — normalized below
    "abort": "cross-circle.png",
    "local": "plug.png",
    "settings": "gear.png",
    # Remote
    "remote": "remote.png",
    "remote_disconnect": "plug-disconnect.png",
    "remote_settings": "remote_settings.png",
    "remote_gcode": "remote_gcode.png",
}

_cache: dict[str, QIcon] = {}

# Jog pad: glyph-first tiles (icon nearly fills hit target; less chrome than wx).
JOG_ICON_SIZE = QSize(48, 48)
JOG_BUTTON_SIZE = QSize(50, 50)

JOG_ICON_FILES: dict[str, str] = {
    "pos_x": "jogging_pos_x_48x48.png",
    "neg_x": "jogging_neg_x_48x48.png",
    "pos_y": "jogging_pos_y_48x48.png",
    "neg_y": "jogging_neg_y_48x48.png",
    "pos_z": "jogging_pos_z_48x48.png",
    "neg_z": "jogging_neg_z_48x48.png",
    "home_xyz": "jogging_home_xyz_48x48.png",
    "home_x": "jogging_home_x_48x48.png",
    "home_y": "jogging_home_y_48x48.png",
    "home_z": "jogging_home_z_48x48.png",
    "home_xy": "jogging_home_xy_48x48.png",
    "zero_xyz": "jogging_set_to_zero_xyz_48x48.png",
    "zero_xy": "jogging_set_to_zero_xy_48x48.png",
    "zero_z": "jogging_set_to_zero_z_48x48.png",
    "goto_zero_xy": "jogging_goto_zero_xy_48x48.png",
    "probe_z": "jogging_probe_48x48.png",
    "coolant_on": "jogging_coolant_on_48x48.png",
    "coolant_off": "jogging_coolant_off_48x48.png",
    "spindle_cw": "jogging_spindle_cw_48x48.png",
    "spindle_ccw": "jogging_spindle_ccw_48x48.png",
    "spindle_off": "jogging_spindle_off_48x48.png",
}

_jog_cache: dict[str, QIcon] = {}

# App / window icon (wx used imgGCSBlack16/32 embeds — file twins under icons/black).
_APP_ICON_CANDIDATES: tuple[Path, ...] = (
    _ROOT / "images" / "icons" / "black" / "gcs_g0_cog_16x16.png",
    _ROOT / "images" / "icons" / "black" / "gcs_g0_cog_32x32.png",
    _COLOR / "gcs_g1_cog_16x16.png",
    _COLOR / "gcs_g1_cog_32x32.png",
)
_app_icon: QIcon | None = None


def icons_root() -> Path:
    return _COLOR


def has_icon(name: str) -> bool:
    fname = ICON_FILES.get(name)
    if not fname:
        return False
    return (_COLOR / fname).is_file()


def _alpha_content_rect(img: QImage, alpha_min: int = 10) -> QRect | None:
    """Bounding box of non-transparent pixels, or None if fully transparent."""
    w, h = img.width(), img.height()
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if img.pixelColor(x, y).alpha() > alpha_min:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if max_x < 0:
        return None
    return QRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def normalize_toolbar_pixmap(
    pix: QPixmap, size: QSize = TOOLBAR_ICON_SIZE
) -> QPixmap:
    """Fit a toolbar glyph into *size* without looking tiny.

    Most assets are already 16×16. A few wx embeds (clear-alarm, break-clear
    ``x.png``) are 32×32 with the drawing centered in transparent padding.
    Scaling the full canvas to 16×16 shrinks the glyph to ~half the visual
    weight of peers — crop to content first, then scale to fill *size*.
    """
    if pix.isNull():
        return pix

    tw, th = size.width(), size.height()
    if pix.width() == tw and pix.height() == th:
        return pix

    img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    content = _alpha_content_rect(img)
    if content is None:
        return pix.scaled(
            size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    # One-pixel margin so antialiased edges are not clipped
    content = content.adjusted(-1, -1, 1, 1).intersected(img.rect())
    cropped = QPixmap.fromImage(img.copy(content))
    scaled = cropped.scaled(
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    out = QPixmap(size)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    x = (tw - scaled.width()) // 2
    y = (th - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()
    return out


def get_icon(name: str) -> QIcon:
    """Return a QIcon for a logical name, with Disabled mode from color-dis if any.

    Missing files yield an empty QIcon (callers can still show text).
    Oversized sources are normalized to TOOLBAR_ICON_SIZE.
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
        ico.addPixmap(
            normalize_toolbar_pixmap(pix),
            QIcon.Mode.Normal,
            QIcon.State.Off,
        )

    dis_path = _COLOR_DIS / fname
    if dis_path.is_file():
        dis_pix = QPixmap(str(dis_path))
        if not dis_pix.isNull():
            ico.addPixmap(
                normalize_toolbar_pixmap(dis_pix),
                QIcon.Mode.Disabled,
                QIcon.State.Off,
            )

    _cache[name] = ico
    return ico


def apply_action_icon(action, name: str) -> bool:
    """Set action icon from logical name. Returns True if a pixmap was loaded."""
    ico = get_icon(name)
    if ico.isNull():
        return False
    action.setIcon(ico)
    return True


def get_jog_icon(name: str) -> QIcon:
    """Load a jog-pad icon at native/48px size (not toolbar 16px normalize)."""
    if name in _jog_cache:
        return _jog_cache[name]

    fname = JOG_ICON_FILES.get(name)
    if not fname:
        ico = QIcon()
        _jog_cache[name] = ico
        return ico

    path = _COLOR / fname
    if not path.is_file():
        ico = QIcon()
        _jog_cache[name] = ico
        return ico

    ico = QIcon()
    pix = QPixmap(str(path))
    if not pix.isNull():
        # Keep large glyphs for the pad; only downscale if huge
        if pix.width() > JOG_ICON_SIZE.width() or pix.height() > JOG_ICON_SIZE.height():
            pix = pix.scaled(
                JOG_ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        ico.addPixmap(pix, QIcon.Mode.Normal, QIcon.State.Off)
    _jog_cache[name] = ico
    return ico


def apply_jog_button_icon(button, name: str) -> bool:
    """Set a jog QAbstractButton to the wx-style 48px glyph."""
    ico = get_jog_icon(name)
    if ico.isNull():
        return False
    button.setIcon(ico)
    button.setIconSize(JOG_ICON_SIZE)
    return True


def get_app_icon() -> QIcon:
    """Multi-size app icon (title bar / taskbar) from existing GCS cog PNGs.

    Uses the same art family as classic wx ``imgGCSBlack*`` embeds
    (``images/icons/black/gcs_g0_cog_*.png``), plus color cog variants.
    Scaled 48/64 sizes are added so window managers pick a sharper tile.
    """
    global _app_icon
    if _app_icon is not None:
        return _app_icon

    ico = QIcon()
    largest: QPixmap | None = None
    for path in _APP_ICON_CANDIDATES:
        if not path.is_file():
            continue
        pix = QPixmap(str(path))
        if pix.isNull():
            continue
        ico.addPixmap(pix, QIcon.Mode.Normal, QIcon.State.Off)
        if largest is None or pix.width() > largest.width():
            largest = pix

    if largest is not None and not largest.isNull():
        for side in (48, 64):
            if largest.width() >= side:
                continue
            scaled = largest.scaled(
                side,
                side,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if not scaled.isNull():
                ico.addPixmap(scaled, QIcon.Mode.Normal, QIcon.State.Off)

    _app_icon = ico
    return ico


def apply_app_icon(app, window=None) -> bool:
    """Set QApplication (and optional main window) icon. Returns True if loaded."""
    ico = get_app_icon()
    if ico.isNull():
        return False
    try:
        app.setWindowIcon(ico)
    except Exception:
        return False
    if window is not None:
        try:
            window.setWindowIcon(ico)
        except Exception:
            pass
    return True
