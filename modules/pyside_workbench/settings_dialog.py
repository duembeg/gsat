"""----------------------------------------------------------------------------
    settings_dialog.py

    PySide settings notebook matching classic wx gsatSettingsDialog pages
    and the same ~/.gsat.json keys. Local (full) and remote (Machine+Remote)
    modes mirror wx.

    Architecture note: keep as-is for cutover; later we may always-remote
    and split client vs server config ownership.
----------------------------------------------------------------------------"""
from __future__ import annotations

import secrets
import string
from typing import Any, Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import modules.config as gc
import modules.machif_config as mi
from modules.pyside_workbench import icons as wb_icons


def _cfg_get(cfg, path: str, default=None):
    if cfg is None:
        return default
    try:
        val = cfg.get(path, default)
    except Exception:
        return default
    return default if val is None else val


def _cfg_set(cfg, path: str, value) -> None:
    cfg.set(path, value)


def _scroll(page: QWidget) -> QScrollArea:
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QScrollArea.Shape.NoFrame)
    sc.setWidget(page)
    return sc


def _section(title: str) -> QLabel:
    lab = QLabel(title)
    f = lab.font()
    f.setBold(True)
    lab.setFont(f)
    return lab


def _color_btn(parent: QWidget, hex_color: str) -> QPushButton:
    btn = QPushButton()
    btn.setFixedSize(56, 26)
    hx = hex_color or "#000000"
    if not str(hx).startswith("#"):
        hx = f"#{hx}"
    btn.setProperty("hex", hx)
    btn.setStyleSheet(
        f"background-color: {hx}; border: 1px solid #666; border-radius: 4px;"
    )
    btn.setToolTip(hx)

    def pick(_checked=False, b=btn):
        cur = QColor(b.property("hex") or "#000000")
        c = QColorDialog.getColor(cur, parent, "Pick color")
        if c.isValid():
            hx2 = c.name()
            b.setProperty("hex", hx2)
            b.setStyleSheet(
                f"background-color: {hx2}; border: 1px solid #666; border-radius: 4px;"
            )
            b.setToolTip(hx2)

    btn.clicked.connect(pick)
    return btn


def _color_hex(btn: QPushButton) -> str:
    return str(btn.property("hex") or "#000000")


def _color_field(parent: QWidget, label: str, hex_color: str) -> tuple[QWidget, QPushButton]:
    """Compact label + swatch chip for wrapping grid cells."""
    chip = QWidget(parent)
    chip.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    row = QHBoxLayout(chip)
    row.setContentsMargins(0, 0, 4, 0)
    row.setSpacing(6)
    lab = QLabel(label)
    lab.setObjectName("colorChipLabel")
    lab.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
    lab.setMinimumWidth(88)
    btn = _color_btn(parent, hex_color)
    row.addWidget(lab)
    row.addWidget(btn)
    row.addStretch(1)
    return chip, btn


class _WrappingGrid(QWidget):
    """Row-first wrap that forms an aligned grid as width changes.

    Unlike free flow (uneven chip widths → ragged columns), all cells share
    a uniform column width (max chip width in the group), so row N lines up
    under row 0. Column count = how many cells fit in the available width.

    Height is set explicitly after layout — relying only on height-for-width
    inside a QScrollArea collapsed the host to 0px and hid all chips.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        h_spacing: int = 12,
        v_spacing: int = 8,
    ):
        super().__init__(parent)
        self._widgets: list[QWidget] = []
        self._h = h_spacing
        self._v = v_spacing
        self._cols = -1
        self._cell_w = 0
        self._cell_h = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(h_spacing)
        self._grid.setVerticalSpacing(v_spacing)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )

    def addWidget(self, widget: QWidget) -> None:
        self._widgets.append(widget)
        self._cols = -1
        self._relayout()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._relayout()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # First show often has width 0 during construction — relayout once visible
        self._cols = -1
        self._relayout()

    def sizeHint(self) -> QSize:
        if not self._widgets:
            return QSize(0, 0)
        cell_w, cell_h = self._cell_metrics()
        n = len(self._widgets)
        cols = min(n, max(1, self._cols if self._cols > 0 else 4))
        rows = (n + cols - 1) // cols
        return QSize(
            cols * cell_w + max(0, cols - 1) * self._h,
            rows * cell_h + max(0, rows - 1) * self._v,
        )

    def minimumSizeHint(self) -> QSize:
        if not self._widgets:
            return QSize(0, 0)
        cell_w, cell_h = self._cell_metrics()
        return QSize(cell_w, cell_h)

    def _cell_metrics(self) -> tuple[int, int]:
        cell_w = 1
        cell_h = 26  # at least color button height
        for w in self._widgets:
            sh = w.sizeHint()
            # sizeHint can be 0 before style polish — use minSizeHint too
            mh = w.minimumSizeHint()
            cell_w = max(cell_w, sh.width(), mh.width(), w.minimumWidth())
            cell_h = max(cell_h, sh.height(), mh.height(), 26)
        cell_w = max(cell_w, 148)
        return cell_w, cell_h

    def _relayout(self) -> None:
        if not self._widgets:
            return
        cell_w, cell_h = self._cell_metrics()
        avail = max(self.width(), cell_w)
        cols = max(1, (avail + self._h) // (cell_w + self._h))
        cols = min(cols, len(self._widgets))
        if (
            cols == self._cols
            and cell_w == self._cell_w
            and cell_h == self._cell_h
            and self.height() > 0
        ):
            return
        self._cols = cols
        self._cell_w = cell_w
        self._cell_h = cell_h

        for w in self._widgets:
            self._grid.removeWidget(w)

        for i, w in enumerate(self._widgets):
            w.setMinimumWidth(cell_w)
            w.setMaximumWidth(16777215)
            w.setMinimumHeight(cell_h)
            r, c = divmod(i, cols)
            self._grid.addWidget(w, r, c, Qt.AlignmentFlag.AlignLeft)

        for c in range(cols):
            self._grid.setColumnMinimumWidth(c, cell_w)
            self._grid.setColumnStretch(c, 0)

        rows = (len(self._widgets) + cols - 1) // cols
        total_h = rows * cell_h + max(0, rows - 1) * self._v
        # Force non-zero height so VBox/ScrollArea cannot collapse the host
        self.setMinimumHeight(total_h)
        self.setMaximumHeight(total_h)
        self.updateGeometry()


class _SettingsPage(QWidget):
    def apply(self) -> None:
        raise NotImplementedError


class GeneralPage(_SettingsPage):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        root = QVBoxLayout(self)
        root.addWidget(_section("General"))
        self.cb_runtime = QCheckBox("Display run time dialog at program end")
        self.cb_runtime.setChecked(bool(_cfg_get(cfg, "/mainApp/DisplayRunTimeDialog", False)))
        root.addWidget(self.cb_runtime)

        root.addWidget(_section("Files"))
        self.cb_backup = QCheckBox("Create a backup copy of file before saving")
        self.cb_backup.setChecked(bool(_cfg_get(cfg, "/mainApp/BackupFile", False)))
        root.addWidget(self.cb_backup)

        form = QFormLayout()
        self.sp_history = QSpinBox()
        self.sp_history.setRange(0, 100)
        self.sp_history.setValue(int(_cfg_get(cfg, "/mainApp/FileHistory/FilesMaxHistory", 10) or 10))
        form.addRow("Recent file history size", self.sp_history)
        root.addLayout(form)

        root.addWidget(_section("Tools"))
        form2 = QFormLayout()
        self.sp_in2mm = QSpinBox()
        self.sp_in2mm.setRange(0, 100)
        self.sp_in2mm.setValue(int(_cfg_get(cfg, "/mainApp/RoundInch2mm", 4) or 4))
        form2.addRow("Inch to mm round digits", self.sp_in2mm)
        self.sp_mm2in = QSpinBox()
        self.sp_mm2in.setRange(0, 100)
        self.sp_mm2in.setValue(int(_cfg_get(cfg, "/mainApp/Roundmm2Inch", 4) or 4))
        form2.addRow("mm to Inch round digits", self.sp_mm2in)
        root.addLayout(form2)
        root.addStretch(1)

    def apply(self) -> None:
        _cfg_set(self.cfg, "/mainApp/DisplayRunTimeDialog", self.cb_runtime.isChecked())
        _cfg_set(self.cfg, "/mainApp/BackupFile", self.cb_backup.isChecked())
        _cfg_set(self.cfg, "/mainApp/FileHistory/FilesMaxHistory", self.sp_history.value())
        _cfg_set(self.cfg, "/mainApp/RoundInch2mm", self.sp_in2mm.value())
        _cfg_set(self.cfg, "/mainApp/Roundmm2Inch", self.sp_mm2in.value())


class OutputStylePage(_SettingsPage):
    """Shared console/gcode style fields (wx wnd_output / console / gcode)."""

    def __init__(self, cfg, key: str, parent=None, *, syntax: bool = False, cli: bool = False):
        super().__init__(parent)
        self.cfg = cfg
        self.key = key  # "code" or "console"
        self.syntax = syntax
        self.cli = cli
        root = QVBoxLayout(self)

        root.addWidget(_section("Scrolling"))
        form = QFormLayout()
        self.auto_scroll = QComboBox()
        # wx: gcode has "On Goto PC" (index 3); console only Never/Always/On Kill Focus
        if key == "code":
            self.auto_scroll.addItems(
                ["Never", "Always", "On Kill Focus", "On Goto PC"]
            )
            max_idx = 3
            default = 3  # sensible for large files: follow PC when Goto PC / run
        else:
            self.auto_scroll.addItems(["Never", "Always", "On Kill Focus"])
            max_idx = 2
            default = 1
        try:
            raw = _cfg_get(cfg, f"/{key}/AutoScroll", default)
            # 0 is valid ("Never") — do not coalesce with `or`
            idx = default if raw is None else int(raw)
        except (TypeError, ValueError):
            idx = default
        self.auto_scroll.setCurrentIndex(max(0, min(max_idx, idx)))
        if key == "code":
            self.auto_scroll.setToolTip(
                "Never: no auto scroll on PC updates.\n"
                "Always: keep PC line visible when PC moves.\n"
                "On Kill Focus: follow PC until you move the caret; resume after focus leaves.\n"
                "On Goto PC: follow PC after Goto PC (or run) until you move the caret — "
                "best for long files so ▶ stays in view."
            )
        form.addRow("Auto Scroll", self.auto_scroll)
        root.addLayout(form)

        root.addWidget(_section("General"))
        self.cb_readonly = QCheckBox("ReadOnly")
        self.cb_readonly.setChecked(bool(_cfg_get(cfg, f"/{key}/ReadOnly", False)))
        self.cb_linenum = QCheckBox("Line Numbers")
        self.cb_linenum.setChecked(bool(_cfg_get(cfg, f"/{key}/LineNumber", True)))
        self.cb_caret = QCheckBox("Highlight Caret Line")
        self.cb_caret.setChecked(bool(_cfg_get(cfg, f"/{key}/CaretLine", True)))
        root.addWidget(self.cb_readonly)
        root.addWidget(self.cb_linenum)
        root.addWidget(self.cb_caret)

        form_f = QFormLayout()
        self.font_face = QLineEdit(str(_cfg_get(cfg, f"/{key}/FontFace", "Monospace") or "Monospace"))
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 72)
        self.font_size.setValue(int(_cfg_get(cfg, f"/{key}/FontSize", 10) or 10))
        self.font_style = QLineEdit(str(_cfg_get(cfg, f"/{key}/FontStyle", "normal") or "normal"))
        form_f.addRow("Font face", self.font_face)
        form_f.addRow("Font size", self.font_size)
        form_f.addRow("Font style (normal/bold/italic)", self.font_style)
        root.addLayout(form_f)

        # Colors: row-first wrap into an aligned grid (columns line up across rows)
        root.addWidget(_section("Colors — foreground"))
        fg_host = _WrappingGrid(self)
        chip, self.col_win_fg = _color_field(
            self, "Window", str(_cfg_get(cfg, f"/{key}/WindowForeground", "#000000"))
        )
        fg_host.addWidget(chip)
        chip, self.col_ln_fg = _color_field(
            self,
            "Line numbers",
            str(_cfg_get(cfg, f"/{key}/LineNumberForeground", "#606060")),
        )
        fg_host.addWidget(chip)
        chip, self.col_caret_fg = _color_field(
            self,
            "Caret line",
            str(_cfg_get(cfg, f"/{key}/CaretLineForeground", "#000000")),
        )
        fg_host.addWidget(chip)
        root.addWidget(fg_host)

        root.addWidget(_section("Colors — background"))
        bg_host = _WrappingGrid(self)
        chip, self.col_win_bg = _color_field(
            self, "Window", str(_cfg_get(cfg, f"/{key}/WindowBackground", "#FFFFFF"))
        )
        bg_host.addWidget(chip)
        chip, self.col_ln_bg = _color_field(
            self,
            "Line numbers",
            str(_cfg_get(cfg, f"/{key}/LineNumberBackground", "#F0F0F0")),
        )
        bg_host.addWidget(chip)
        chip, self.col_caret_bg = _color_field(
            self,
            "Caret line",
            str(_cfg_get(cfg, f"/{key}/CaretLineBackground", "#FFF0A0")),
        )
        bg_host.addWidget(chip)
        root.addWidget(bg_host)

        self.syntax_btns: dict[str, QPushButton] = {}
        if syntax:
            root.addWidget(_section("Syntax highlight"))
            syn_host = _WrappingGrid(self)
            for label, path_suffix, default in (
                ("G-code", "GCodeHighlight", "#0000AA"),
                ("M-code", "MCodeHighlight", "#AA0000"),
                ("Axis", "AxisHighlight", "#008800"),
                ("Parameters", "ParametersHighlight", "#880088"),
                ("Parameters2", "Parameters2Highlight", "#880088"),
                ("Comments", "CommentsHighlight", "#808080"),
                ("G-code line #", "GCodeLineNumberHighlight", "#000000"),
            ):
                chip, b = _color_field(
                    self,
                    label,
                    str(_cfg_get(cfg, f"/{key}/{path_suffix}", default)),
                )
                self.syntax_btns[path_suffix] = b
                syn_host.addWidget(chip)
            root.addWidget(syn_host)

        if cli:
            root.addWidget(_section("CLI history"))
            form_c = QFormLayout()
            self.cb_save_hist = QCheckBox("Save command history")
            self.cb_save_hist.setChecked(bool(_cfg_get(cfg, f"/{key}/cli/SaveCmdHistory", True)))
            self.sp_hist = QSpinBox()
            self.sp_hist.setRange(0, 10000)
            self.sp_hist.setValue(int(_cfg_get(cfg, f"/{key}/cli/CmdMaxHistory", 100) or 100))
            form_c.addRow(self.cb_save_hist)
            form_c.addRow("Max history", self.sp_hist)
            root.addLayout(form_c)

        root.addStretch(1)

    def apply(self) -> None:
        k = self.key
        _cfg_set(self.cfg, f"/{k}/AutoScroll", self.auto_scroll.currentIndex())
        _cfg_set(self.cfg, f"/{k}/ReadOnly", self.cb_readonly.isChecked())
        _cfg_set(self.cfg, f"/{k}/LineNumber", self.cb_linenum.isChecked())
        _cfg_set(self.cfg, f"/{k}/CaretLine", self.cb_caret.isChecked())
        _cfg_set(self.cfg, f"/{k}/FontFace", self.font_face.text().strip() or "Monospace")
        _cfg_set(self.cfg, f"/{k}/FontSize", self.font_size.value())
        _cfg_set(self.cfg, f"/{k}/FontStyle", self.font_style.text().strip() or "normal")
        _cfg_set(self.cfg, f"/{k}/WindowForeground", _color_hex(self.col_win_fg))
        _cfg_set(self.cfg, f"/{k}/WindowBackground", _color_hex(self.col_win_bg))
        _cfg_set(self.cfg, f"/{k}/LineNumberForeground", _color_hex(self.col_ln_fg))
        _cfg_set(self.cfg, f"/{k}/LineNumberBackground", _color_hex(self.col_ln_bg))
        _cfg_set(self.cfg, f"/{k}/CaretLineForeground", _color_hex(self.col_caret_fg))
        _cfg_set(self.cfg, f"/{k}/CaretLineBackground", _color_hex(self.col_caret_bg))
        for suffix, btn in self.syntax_btns.items():
            _cfg_set(self.cfg, f"/{k}/{suffix}", _color_hex(btn))
        if self.cli:
            _cfg_set(self.cfg, f"/{k}/cli/SaveCmdHistory", self.cb_save_hist.isChecked())
            _cfg_set(self.cfg, f"/{k}/cli/CmdMaxHistory", self.sp_hist.value())


class _PortComboBox(QComboBox):
    """Editable port combo that re-scans the OS list when the drop-down opens (wx)."""

    about_to_popup = Signal()

    def showPopup(self) -> None:
        self.about_to_popup.emit()
        super().showPopup()


class MachinePage(_SettingsPage):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        root = QVBoxLayout(self)

        form = QFormLayout()
        self.device = QComboBox()
        names = sorted(mi.MACHIF_LIST, key=str.lower)
        self.device.addItems(names if names else ["grblHAL"])
        cur = str(_cfg_get(cfg, "/machine/Device", "grblHAL") or "grblHAL")
        i = self.device.findText(cur)
        self.device.setCurrentIndex(i if i >= 0 else 0)
        form.addRow("Device", self.device)

        # Serial port: editable combo + list with "device, description" (wx).
        # Re-scan on drop-down open; strip description on select; optional Refresh.
        self.port = _PortComboBox()
        self.port.setEditable(True)
        self.port.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.port.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.port.setMinimumContentsLength(18)
        # Seed with path-only config value (list filled on first popup / refresh)
        self.port.setCurrentText(str(_cfg_get(cfg, "/machine/Port", "") or ""))
        self.port.about_to_popup.connect(self._on_port_popup)
        self.port.activated.connect(self._on_port_activated)
        # Also strip if user types "port, desc" and leaves the field
        self.port.lineEdit().editingFinished.connect(self._strip_port_field)

        refresh = QPushButton("Refresh")
        refresh.setToolTip("Re-scan serial ports (same as opening the port list)")
        refresh.clicked.connect(lambda: self._refresh_ports(description=True))

        port_wrap = QWidget()
        port_row = QHBoxLayout(port_wrap)
        port_row.setContentsMargins(0, 0, 0, 0)
        port_row.addWidget(self.port, 1)
        port_row.addWidget(refresh)
        form.addRow("Serial Port", port_wrap)

        self.baud = QComboBox()
        self.baud.setEditable(True)
        for b in ("1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200", "230400"):
            self.baud.addItem(b)
        self.baud.setCurrentText(str(_cfg_get(cfg, "/machine/Baud", "115200") or "115200"))
        form.addRow("Baud Rate", self.baud)
        root.addLayout(form)

        # Initial scan so the drop-down already has items (wx also fills soon after open)
        self._refresh_ports(description=True)

        self._axis_list = ("X", "Y", "Z", "A", "B", "C")

        root.addWidget(_section("DRO"))
        dro = QFormLayout()
        self.dro_font = QLineEdit(str(_cfg_get(cfg, "/machine/DRO/FontFace", "Monospace") or "Monospace"))
        self.dro_size = QSpinBox()
        self.dro_size.setRange(6, 72)
        self.dro_size.setValue(int(_cfg_get(cfg, "/machine/DRO/FontSize", 20) or 20))
        self.dro_style = QLineEdit(str(_cfg_get(cfg, "/machine/DRO/FontStyle", "bold") or "bold"))
        dro.addRow("Font face", self.dro_font)
        dro.addRow("Font size", self.dro_size)
        dro.addRow("Font style", self.dro_style)
        self.dro_axes: dict[str, QCheckBox] = {}
        for ax in self._axis_list:
            cb = QCheckBox(f"Enable {ax} axis")
            cb.setChecked(bool(_cfg_get(cfg, f"/machine/DRO/Enable{ax}", ax in ("X", "Y", "Z"))))
            # Probe groups follow enabled DRO axes (wx HideProperty on probe cats)
            cb.toggled.connect(self._update_conditional_sections)
            self.dro_axes[ax] = cb
            dro.addRow(cb)
        root.addLayout(dro)

        root.addWidget(_section("General"))
        self.cb_init = QCheckBox("Enable init script")
        self.cb_init.setChecked(bool(_cfg_get(cfg, "/machine/InitScriptEnable", False)))
        self.cb_filter = QCheckBox("Enable filter G-codes")
        self.cb_filter.setChecked(bool(_cfg_get(cfg, "/machine/FilterGcodesEnable", False)))
        self.filter_list = QLineEdit(str(_cfg_get(cfg, "/machine/FilterGcodes", "") or ""))
        form_g = QFormLayout()
        form_g.addRow(self.cb_init)
        form_g.addRow(self.cb_filter)
        form_g.addRow("Filter G-codes list", self.filter_list)
        root.addLayout(form_g)

        root.addWidget(_section("Init script"))
        self.init_script = QTextEdit()
        self.init_script.setPlainText(str(_cfg_get(cfg, "/machine/InitScript", "") or ""))
        self.init_script.setMinimumHeight(120)
        root.addWidget(self.init_script)

        # MachIf-specific: one group per controller; only selected Device is shown
        # (wx PropertyGrid HideProperty on non-selected categories).
        self.spec_widgets: dict[str, QWidget] = {}
        self.spec_groups: dict[str, QGroupBox] = {}
        specific = _cfg_get(cfg, "/machine/MachIfSpecific", {}) or {}
        if isinstance(specific, dict) and specific:
            root.addWidget(_section("Device-specific"))
            for machine, props in specific.items():
                if not isinstance(props, dict) or not props:
                    continue
                box = QGroupBox(f"{machine} specific")
                form_s = QFormLayout(box)
                for prop, meta in props.items():
                    if not isinstance(meta, dict) or "Value" not in meta:
                        continue
                    name = meta.get("Name", prop)
                    value = meta.get("Value")
                    path = f"/machine/MachIfSpecific/{machine}/{prop}/Value"
                    key = f"{machine}|{prop}"
                    if isinstance(value, bool):
                        w = QCheckBox()
                        w.setChecked(bool(_cfg_get(cfg, path, value)))
                    elif isinstance(value, int) and not isinstance(value, bool):
                        w = QSpinBox()
                        w.setRange(-10_000_000, 10_000_000)
                        w.setValue(int(_cfg_get(cfg, path, value) or 0))
                    elif isinstance(value, float):
                        w = QDoubleSpinBox()
                        w.setDecimals(4)
                        w.setRange(-1e9, 1e9)
                        w.setValue(float(_cfg_get(cfg, path, value) or 0.0))
                    else:
                        w = QLineEdit(
                            str(
                                _cfg_get(cfg, path, value)
                                if _cfg_get(cfg, path, value) is not None
                                else value
                            )
                        )
                    tip = meta.get("ToolTip") or ""
                    if tip:
                        w.setToolTip(str(tip))
                    self.spec_widgets[key] = w
                    form_s.addRow(str(name), w)
                self.spec_groups[machine] = box
                root.addWidget(box)

        # Probe: per-axis Offset / Feed / Travel / Retract (wx Probe Settings).
        # Only axes enabled in DRO are shown (wx hides disabled probe categories).
        root.addWidget(_section("Probe"))
        self.probe_groups: dict[str, QGroupBox] = {}
        self.probe_widgets: dict[str, dict[str, QWidget]] = {}
        probe_cfg = _cfg_get(cfg, "/machine/Probe", {}) or {}
        if not isinstance(probe_cfg, dict):
            probe_cfg = {}
        for ax in self._axis_list:
            ax_cfg = probe_cfg.get(ax, {}) if isinstance(probe_cfg.get(ax), dict) else {}
            box = QGroupBox(f"{ax} Probe")
            fl = QFormLayout(box)
            w_off = QDoubleSpinBox()
            w_off.setDecimals(4)
            w_off.setRange(-1e6, 1e6)
            w_off.setValue(float(ax_cfg.get("Offset", 0) or 0))
            w_off.setToolTip("Axis value after the probe triggers")
            w_fr = QSpinBox()
            w_fr.setRange(0, 10_000_000)
            w_fr.setValue(int(ax_cfg.get("FeedRate", 0) or 0))
            w_fr.setToolTip("Probe seek feed rate")
            w_tl = QDoubleSpinBox()
            w_tl.setDecimals(4)
            w_tl.setRange(-1e6, 1e6)
            w_tl.setValue(float(ax_cfg.get("TravelLimit", 0) or 0))
            w_tl.setToolTip("Max travel before probe gives up")
            w_rd = QDoubleSpinBox()
            w_rd.setDecimals(4)
            w_rd.setRange(-1e6, 1e6)
            w_rd.setValue(float(ax_cfg.get("Retract", 0) or 0))
            w_rd.setToolTip("Retract distance after touch")
            fl.addRow("Offset", w_off)
            fl.addRow("Feed rate", w_fr)
            fl.addRow("Travel limit", w_tl)
            fl.addRow("Retract distance", w_rd)
            self.probe_widgets[ax] = {
                "Offset": w_off,
                "FeedRate": w_fr,
                "TravelLimit": w_tl,
                "Retract": w_rd,
            }
            self.probe_groups[ax] = box
            root.addWidget(box)

        # Device change shows only that controller's MachIf group (wx UpdateUI)
        self.device.currentTextChanged.connect(self._update_conditional_sections)
        self._update_conditional_sections()

        root.addStretch(1)

    def _update_conditional_sections(self, *_args) -> None:
        """wx UpdateUI: show selected Device MachIf props; probe axes for enabled DRO."""
        device = self.device.currentText().strip()
        for machine, box in self.spec_groups.items():
            box.setVisible(machine == device)
        for ax, box in self.probe_groups.items():
            cb = self.dro_axes.get(ax)
            box.setVisible(bool(cb is not None and cb.isChecked()))

    @staticmethod
    def _port_device_only(value: str) -> str:
        """wx OnSpComboBoxSelect: keep path only before optional ', description'."""
        return str(value or "").split(",")[0].strip()

    @staticmethod
    def _is_windows_com_name(device: str) -> bool:
        """True for Windows-style ``COM12`` names (case-insensitive)."""
        import re

        return bool(re.match(r"^COM\d+$", (device or "").strip(), re.IGNORECASE))

    @staticmethod
    def _unix_serial_device_ok(device: str) -> bool:
        """wx non-Windows filter: Linux ``USB``/``ACM`` and macOS ``cu`` (case-sensitive).

        Matches wx ``GetListOfSerialPorts`` / fail-safe globs
        ``/dev/ttyUSB*``, ``/dev/ttyACM*``, ``/dev/cu*``.
        """
        dev = device or ""
        return "USB" in dev or "ACM" in dev or "cu" in dev

    @classmethod
    def _serial_device_allowed(cls, device: str) -> bool:
        """Whether a device path belongs in the port list.

        Filter is driven by **path shape** (not client ``os.name``) so Remote
        Settings can filter a Linux/macOS server list when the UI runs on
        Windows, and vice versa:

        * ``COM*`` — Windows; no further filter (wx shows all COM ports)
        * Unix-like paths — require USB / ACM / cu (Linux + macOS)
        * placeholder ``None`` — always kept
        """
        dev = (device or "").strip()
        if not dev or dev == "None":
            return True
        if cls._is_windows_com_name(dev):
            return True
        # Unix-style absolute paths and common bare names from server scans
        if (
            dev.startswith("/")
            or dev.startswith("tty")
            or dev.startswith("cu")
            or "/dev/" in dev
        ):
            return cls._unix_serial_device_ok(dev)
        # Local Windows scan may use other names; keep them (wx: no filter on nt)
        import os

        if os.name == "nt":
            return True
        return cls._unix_serial_device_ok(dev)

    def _format_port_entry(self, device: str, description: str | None, want_desc: bool) -> str:
        if not want_desc:
            return device
        desc = (description or "").strip()
        return f"{device}, {desc}" if desc else device

    def _filter_port_strings(self, entries: list[str], description: bool) -> list[str]:
        """Apply wx-style filter to preformatted ``device`` or ``device, desc`` rows."""
        out: list[str] = []
        for raw in entries:
            s = str(raw).strip()
            if not s:
                continue
            dev = self._port_device_only(s)
            if not self._serial_device_allowed(dev):
                continue
            if description:
                out.append(s)  # keep server "device, description" when present
            else:
                out.append(dev)
        return out

    def _list_ports(self, description: bool = True) -> list[str]:
        """Match wx ``GetListOfSerialPorts``.

        Prefer ``/temp/SerialPorts`` (remote server scan), still applying the
        same USB/ACM/cu (Unix) vs all-COM (Windows) filter as local scan.
        With ``description``, entries are ``\"device, description\"``.
        """
        ser = _cfg_get(self.cfg, "/temp/SerialPorts", None)
        if ser and isinstance(ser, (list, tuple)) and len(ser) > 0:
            out = self._filter_port_strings([str(x) for x in ser], description)
            return out or ["None"]

        try:
            import os
            import glob
            import serial.tools.list_ports

            ser_list_info = list(serial.tools.list_ports.comports())
            ser_list: list[str] = []

            if ser_list_info:
                for ser in ser_list_info:
                    dev = str(getattr(ser, "device", "") or "")
                    if not self._serial_device_allowed(dev):
                        continue
                    desc = getattr(ser, "description", "") or ""
                    ser_list.append(self._format_port_entry(dev, desc, description))
                ser_list.sort()
            else:
                ser_list = ["None"]

            return ser_list if ser_list else ["None"]
        except ImportError:
            # wx fail-safe: COM probe on Windows; USB/ACM/cu globs elsewhere
            try:
                import os
                import glob

                if os.name == "nt":
                    ser_list = []
                    try:
                        import serial

                        for i in range(256):
                            try:
                                serial.Serial(i)
                                ser_list.append(f"COM{i + 1}")
                            except Exception:
                                pass
                    except Exception:
                        ser_list = []
                    return ser_list if ser_list else ["None"]
                ser_list = (
                    glob.glob("/dev/ttyUSB*")
                    + glob.glob("/dev/ttyACM*")
                    + glob.glob("/dev/cu*")
                )
                ser_list.sort()
                return ser_list if ser_list else ["None"]
            except Exception:
                return ["None"]
        except Exception:
            return ["None"]

    def _refresh_ports(self, description: bool = True) -> None:
        """Re-fill the combo list; keep current port path in the edit field."""
        cur = self._port_device_only(self.port.currentText())
        self.port.blockSignals(True)
        try:
            self.port.clear()
            items = self._list_ports(description=description)
            self.port.addItems(items)
            # Keep short path in the field (not the long description line)
            self.port.setCurrentText(cur if cur else "")
            # Widen popup to fit "device, description" without resizing the field forever
            fm = self.port.fontMetrics()
            max_w = self.port.width()
            for text in items:
                max_w = max(max_w, fm.horizontalAdvance(text) + 48)
            self.port.view().setMinimumWidth(min(max_w, 520))
        finally:
            self.port.blockSignals(False)

    def _on_port_popup(self) -> None:
        """wx OnSpComboBoxDropDown — refresh list every time the menu opens."""
        self._refresh_ports(description=True)

    def _on_port_activated(self, index: int) -> None:
        """wx OnSpComboBoxSelect — store port path only after choosing a list row."""
        if index < 0:
            return
        text = self.port.itemText(index)
        self.port.setCurrentText(self._port_device_only(text))

    def _strip_port_field(self) -> None:
        """If user typed or left a 'port, desc' string, keep path only."""
        cur = self.port.currentText()
        stripped = self._port_device_only(cur)
        if stripped != cur:
            self.port.setCurrentText(stripped)

    def apply(self) -> None:
        _cfg_set(self.cfg, "/machine/Device", self.device.currentText())
        port = self._port_device_only(self.port.currentText())
        _cfg_set(self.cfg, "/machine/Port", port)
        _cfg_set(self.cfg, "/machine/Baud", self.baud.currentText().strip())
        _cfg_set(self.cfg, "/machine/DRO/FontFace", self.dro_font.text().strip())
        _cfg_set(self.cfg, "/machine/DRO/FontSize", self.dro_size.value())
        _cfg_set(self.cfg, "/machine/DRO/FontStyle", self.dro_style.text().strip() or "normal")
        for ax, cb in self.dro_axes.items():
            _cfg_set(self.cfg, f"/machine/DRO/Enable{ax}", cb.isChecked())
        _cfg_set(self.cfg, "/machine/InitScriptEnable", self.cb_init.isChecked())
        _cfg_set(self.cfg, "/machine/FilterGcodesEnable", self.cb_filter.isChecked())
        fl = ",".join(x.strip() for x in self.filter_list.text().split(",") if x.strip())
        _cfg_set(self.cfg, "/machine/FilterGcodes", fl)
        _cfg_set(self.cfg, "/machine/InitScript", self.init_script.toPlainText())
        # Save all MachIf slots (including hidden controllers) — same as wx
        for key, w in self.spec_widgets.items():
            machine, prop = key.split("|", 1)
            path = f"/machine/MachIfSpecific/{machine}/{prop}/Value"
            if isinstance(w, QCheckBox):
                _cfg_set(self.cfg, path, w.isChecked())
            elif isinstance(w, QSpinBox):
                _cfg_set(self.cfg, path, w.value())
            elif isinstance(w, QDoubleSpinBox):
                _cfg_set(self.cfg, path, float(w.value()))
            elif isinstance(w, QLineEdit):
                _cfg_set(self.cfg, path, w.text())
        # Probe — all axes (wx saves even when probe category is hidden)
        for ax, fields in self.probe_widgets.items():
            _cfg_set(self.cfg, f"/machine/Probe/{ax}/Offset", float(fields["Offset"].value()))
            _cfg_set(self.cfg, f"/machine/Probe/{ax}/FeedRate", int(fields["FeedRate"].value()))
            _cfg_set(
                self.cfg, f"/machine/Probe/{ax}/TravelLimit", float(fields["TravelLimit"].value())
            )
            _cfg_set(self.cfg, f"/machine/Probe/{ax}/Retract", float(fields["Retract"].value()))


class JoggingPage(_SettingsPage):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        root = QVBoxLayout(self)
        root.addWidget(_section("Jogging"))
        self.cb_numpad = QCheckBox("Numeric Keypad as cnc pendant")
        self.cb_numpad.setChecked(bool(_cfg_get(cfg, "/jogging/NumKeypadPendant", False)))
        self.cb_zsafe = QCheckBox("Z jog safe move")
        self.cb_zsafe.setChecked(bool(_cfg_get(cfg, "/jogging/ZJogSafeMove", False)))
        self.cb_rapid = QCheckBox("Rapid Jog")
        self.cb_rapid.setChecked(bool(_cfg_get(cfg, "/jogging/JogRapid", False)))
        root.addWidget(self.cb_numpad)
        root.addWidget(self.cb_zsafe)
        root.addWidget(self.cb_rapid)

        form = QFormLayout()
        self.feed = QDoubleSpinBox()
        self.feed.setRange(0, 99999)
        self.feed.setDecimals(0)
        self.feed.setValue(float(_cfg_get(cfg, "/jogging/JogFeedRate", 1000) or 1000))
        form.addRow("Jog feed rate (units/min)", self.feed)
        self.spindle = QDoubleSpinBox()
        self.spindle.setRange(0, 99999)
        self.spindle.setDecimals(0)
        self.spindle.setValue(float(_cfg_get(cfg, "/jogging/SpindleSpeed", 10000) or 10000))
        form.addRow("Spindle speed (RPM)", self.spindle)
        root.addLayout(form)

        # Custom buttons (label + script) if present
        self.custom: list[dict[str, Any]] = []
        customs = _cfg_get(cfg, "/jogging/CustomButtons", {}) or {}
        if isinstance(customs, dict) and customs:
            root.addWidget(_section("Custom controls"))
            for name in sorted(customs.keys()):
                meta = customs[name] or {}
                box = QGroupBox(str(name))
                fl = QFormLayout(box)
                lab = QLineEdit(str(meta.get("Label", "") if isinstance(meta, dict) else ""))
                scr = QTextEdit()
                scr.setPlainText(str(meta.get("Script", "") if isinstance(meta, dict) else ""))
                scr.setMaximumHeight(80)
                fl.addRow("Label", lab)
                fl.addRow("Script", scr)
                root.addWidget(box)
                self.custom.append({"name": name, "label": lab, "script": scr})
        root.addStretch(1)

    def apply(self) -> None:
        _cfg_set(self.cfg, "/jogging/NumKeypadPendant", self.cb_numpad.isChecked())
        _cfg_set(self.cfg, "/jogging/ZJogSafeMove", self.cb_zsafe.isChecked())
        _cfg_set(self.cfg, "/jogging/JogRapid", self.cb_rapid.isChecked())
        _cfg_set(self.cfg, "/jogging/JogFeedRate", self.feed.value())
        _cfg_set(self.cfg, "/jogging/SpindleSpeed", self.spindle.value())
        for c in self.custom:
            name = c["name"]
            _cfg_set(self.cfg, f"/jogging/CustomButtons/{name}/Label", c["label"].text())
            _cfg_set(self.cfg, f"/jogging/CustomButtons/{name}/Script", c["script"].toPlainText())


class RemotePage(_SettingsPage):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.idx = int(_cfg_get(cfg, "/remotes/Index", 0) or 0)
        self.iface = str(
            _cfg_get(cfg, f"/remotes/remote{self.idx}/Interface", "websocket") or "websocket"
        )
        root = QVBoxLayout(self)
        root.addWidget(_section("Remote connection"))
        form = QFormLayout()
        is_server = bool(_cfg_get(cfg, "/temp/RemoteServer", False))

        self.host = None
        self.auto_gcode = None
        if not is_server:
            self.host = QLineEdit(str(_cfg_get(cfg, f"/remotes/remote{self.idx}/Host", "localhost") or ""))
            form.addRow("Host name", self.host)
            self.auto_gcode = QCheckBox("Auto G-code request")
            self.auto_gcode.setChecked(
                bool(_cfg_get(cfg, f"/remotes/remote{self.idx}/AutoGcodeRequest", False))
            )

        if self.iface == "websocket":
            self.ws_port = QLineEdit(
                str(_cfg_get(cfg, f"/remotes/remote{self.idx}/WebSocketPort", 61803) or 61803)
            )
            form.addRow("WebSocket port", self.ws_port)
            tok_row = QHBoxLayout()
            self.api_token = QLineEdit(
                str(_cfg_get(cfg, f"/remotes/remote{self.idx}/ApiToken", "") or "")
            )
            gen = QPushButton("Generate")
            gen.clicked.connect(self._gen_token)
            tok_row.addWidget(self.api_token, 1)
            tok_row.addWidget(gen)
            form.addRow("API token", tok_row)
            default_bytes = getattr(
                gc, "REMOTE_MAX_MESSAGE_BYTES_DEFAULT", 16 * 1024 * 1024
            )
            stored = _cfg_get(
                cfg,
                f"/remotes/remote{self.idx}/MaxMessageBytes",
                default_bytes,
            )
            try:
                mb_val = gc.remote_message_bytes_to_mb(stored)
            except Exception:
                mb_val = float(getattr(gc, "REMOTE_MAX_MESSAGE_MB_DEFAULT", 16))
            # Prefer whole numbers when exact (e.g. 16 not 16.0)
            if abs(mb_val - round(mb_val)) < 1e-9:
                mb_display = str(int(round(mb_val)))
            else:
                mb_display = f"{mb_val:g}"
            self.max_msg = QLineEdit(mb_display)
            self.max_msg.setToolTip(
                "Engine.IO / Socket.IO max message size in MB (default 16). "
                "Must match on gsat-server (restart server after change). "
                "Needed so first Step/Run of large G-code is not dropped. "
                "Stored in config as bytes."
            )
            form.addRow("Max message size (MB)", self.max_msg)
            self.tcp_port = self.udp_port = self.udp_bcast = None
        else:
            self.tcp_port = QLineEdit(
                str(_cfg_get(cfg, f"/remotes/remote{self.idx}/TcpPort", 61801) or 61801)
            )
            self.udp_port = QLineEdit(
                str(_cfg_get(cfg, f"/remotes/remote{self.idx}/UdpPort", 61802) or 61802)
            )
            self.udp_bcast = QCheckBox("Enable UDP broadcast")
            self.udp_bcast.setChecked(
                bool(_cfg_get(cfg, f"/remotes/remote{self.idx}/UdpBroadcast", False))
            )
            form.addRow("TCP port", self.tcp_port)
            form.addRow("UDP port", self.udp_port)
            form.addRow(self.udp_bcast)
            self.ws_port = self.api_token = self.max_msg = None

        root.addLayout(form)
        if self.auto_gcode is not None:
            root.addWidget(self.auto_gcode)
        root.addStretch(1)

    def _gen_token(self) -> None:
        alphabet = string.ascii_letters + string.digits
        self.api_token.setText("".join(secrets.choice(alphabet) for _ in range(16)))

    def apply(self) -> None:
        if self.host is not None:
            _cfg_set(self.cfg, f"/remotes/remote{self.idx}/Host", self.host.text().strip())
        if self.auto_gcode is not None:
            _cfg_set(
                self.cfg,
                f"/remotes/remote{self.idx}/AutoGcodeRequest",
                self.auto_gcode.isChecked(),
            )
        if self.iface == "websocket":
            try:
                port = int(str(self.ws_port.text()).strip())
            except ValueError as exc:
                raise ValueError("WebSocket port must be an integer") from exc
            _cfg_set(self.cfg, f"/remotes/remote{self.idx}/WebSocketPort", port)
            _cfg_set(self.cfg, f"/remotes/remote{self.idx}/ApiToken", self.api_token.text())
            try:
                max_b = gc.remote_message_mb_to_bytes(str(self.max_msg.text()).strip())
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
            _cfg_set(self.cfg, f"/remotes/remote{self.idx}/MaxMessageBytes", max_b)
        else:
            try:
                tcp = int(str(self.tcp_port.text()).strip())
                udp = int(str(self.udp_port.text()).strip())
            except ValueError as exc:
                raise ValueError("TCP/UDP ports must be integers") from exc
            _cfg_set(self.cfg, f"/remotes/remote{self.idx}/TcpPort", tcp)
            _cfg_set(self.cfg, f"/remotes/remote{self.idx}/UdpPort", udp)
            _cfg_set(
                self.cfg,
                f"/remotes/remote{self.idx}/UdpBroadcast",
                self.udp_bcast.isChecked(),
            )


class CompVisionPage(_SettingsPage):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        root = QVBoxLayout(self)
        root.addWidget(_section("Computer vision"))
        self.cb_en = QCheckBox("Enable")
        self.cb_en.setChecked(bool(_cfg_get(cfg, "/cv2/Enable", False)))
        self.cb_cross = QCheckBox("Crosshair")
        self.cb_cross.setChecked(bool(_cfg_get(cfg, "/cv2/Crosshair", True)))
        root.addWidget(self.cb_en)
        root.addWidget(self.cb_cross)
        form = QFormLayout()
        self.dev = QSpinBox()
        self.dev.setRange(0, 64)
        self.dev.setValue(int(_cfg_get(cfg, "/cv2/CaptureDevice", 0) or 0))
        self.period = QSpinBox()
        self.period.setRange(1, 1_000_000)
        self.period.setValue(int(_cfg_get(cfg, "/cv2/CapturePeriod", 100) or 100))
        self.width = QSpinBox()
        self.width.setRange(1, 10000)
        self.width.setValue(int(_cfg_get(cfg, "/cv2/CaptureWidth", 640) or 640))
        self.height = QSpinBox()
        self.height.setRange(1, 10000)
        self.height.setValue(int(_cfg_get(cfg, "/cv2/CaptureHeight", 480) or 480))
        form.addRow("Capture device", self.dev)
        form.addRow("Capture period (ms)", self.period)
        form.addRow("Capture width", self.width)
        form.addRow("Capture height", self.height)
        root.addLayout(form)
        root.addStretch(1)

    def apply(self) -> None:
        _cfg_set(self.cfg, "/cv2/Enable", self.cb_en.isChecked())
        _cfg_set(self.cfg, "/cv2/Crosshair", self.cb_cross.isChecked())
        _cfg_set(self.cfg, "/cv2/CaptureDevice", self.dev.value())
        _cfg_set(self.cfg, "/cv2/CapturePeriod", self.period.value())
        _cfg_set(self.cfg, "/cv2/CaptureWidth", self.width.value())
        _cfg_set(self.cfg, "/cv2/CaptureHeight", self.height.value())


class SettingsDialog(QDialog):
    """wx-parity settings notebook.

    * ``config_data`` — local CONFIG_DATA (always passed)
    * ``config_remote_data`` — if set, dialog edits that blob and only shows
      Machine + Remote pages (wx remote settings mode)

    Local Settings and Remote Settings share the same ``MachinePage`` /
    ``RemotePage`` classes (wx reuses those notebooks too). Serial-port
    polish (descriptions, refresh-on-popup, path strip, Refresh button)
    therefore applies to both; remote port lists prefer
    ``/temp/SerialPorts`` from the server snapshot when present.
    """

    def __init__(
        self,
        parent=None,
        config_data=None,
        config_remote_data=None,
        title: str | None = None,
    ):
        super().__init__(parent)
        self.config_local = config_data
        self.config_remote = config_remote_data
        self.cfg = config_remote_data if config_remote_data is not None else config_data
        self.setWindowTitle(title or ("Remote Settings" if config_remote_data else "Settings"))
        self.resize(900, 640)
        self.setModal(True)

        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        # wx notebook used 16×16 ImageList on each page (Factory.GetIcon)
        self.tabs.setIconSize(wb_icons.TOOLBAR_ICON_SIZE)
        self.pages: list[_SettingsPage] = []

        # Same MachinePage / RemotePage for local and remote modes (wx-style reuse).
        if config_remote_data is not None:
            builders: list[tuple[str, Callable[[], _SettingsPage]]] = [
                ("Machine", lambda: MachinePage(self.cfg)),
                ("Remote", lambda: RemotePage(self.cfg)),
            ]
        else:
            builders = [
                ("General", lambda: GeneralPage(self.cfg)),
                ("G-code", lambda: OutputStylePage(self.cfg, "code", syntax=True)),
                ("Console", lambda: OutputStylePage(self.cfg, "console", cli=True)),
                ("Machine", lambda: MachinePage(self.cfg)),
                ("Jogging", lambda: JoggingPage(self.cfg)),
                ("CompVision", lambda: CompVisionPage(self.cfg)),
                ("Remote", lambda: RemotePage(self.cfg)),
            ]

        for name, factory in builders:
            page = factory()
            self.pages.append(page)
            icon_key = wb_icons.SETTINGS_TAB_ICONS.get(name)
            ico = wb_icons.get_icon(icon_key) if icon_key else None
            if ico is not None and not ico.isNull():
                self.tabs.addTab(_scroll(page), ico, name)
            else:
                self.tabs.addTab(_scroll(page), name)

        root.addWidget(self.tabs, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setObjectName("btnPrimary")
            ok_btn.setDefault(True)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_ok(self) -> None:
        try:
            for page in self.pages:
                page.apply()
        except ValueError as exc:
            QMessageBox.warning(self, "Settings", str(exc))
            return
        self.accept()

    def update_config_data(self) -> None:
        """wx name: pages already applied on OK; kept for API symmetry."""
        for page in self.pages:
            page.apply()
