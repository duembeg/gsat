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

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import modules.machif_config as mi


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
    btn.setFixedWidth(72)
    hx = hex_color or "#000000"
    if not str(hx).startswith("#"):
        hx = f"#{hx}"
    btn.setProperty("hex", hx)
    btn.setStyleSheet(f"background-color: {hx}; border: 1px solid #666;")
    btn.setToolTip(hx)

    def pick(_checked=False, b=btn):
        cur = QColor(b.property("hex") or "#000000")
        c = QColorDialog.getColor(cur, parent, "Pick color")
        if c.isValid():
            hx2 = c.name()
            b.setProperty("hex", hx2)
            b.setStyleSheet(f"background-color: {hx2}; border: 1px solid #666;")
            b.setToolTip(hx2)

    btn.clicked.connect(pick)
    return btn


def _color_hex(btn: QPushButton) -> str:
    return str(btn.property("hex") or "#000000")


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

        root.addWidget(_section("Colors — foreground"))
        fg = QFormLayout()
        self.col_win_fg = _color_btn(self, str(_cfg_get(cfg, f"/{key}/WindowForeground", "#000000")))
        self.col_ln_fg = _color_btn(self, str(_cfg_get(cfg, f"/{key}/LineNumberForeground", "#606060")))
        self.col_caret_fg = _color_btn(self, str(_cfg_get(cfg, f"/{key}/CaretLineForeground", "#000000")))
        fg.addRow("Window", self.col_win_fg)
        fg.addRow("Line numbers", self.col_ln_fg)
        fg.addRow("Caret line", self.col_caret_fg)
        root.addLayout(fg)

        root.addWidget(_section("Colors — background"))
        bg = QFormLayout()
        self.col_win_bg = _color_btn(self, str(_cfg_get(cfg, f"/{key}/WindowBackground", "#FFFFFF")))
        self.col_ln_bg = _color_btn(self, str(_cfg_get(cfg, f"/{key}/LineNumberBackground", "#F0F0F0")))
        self.col_caret_bg = _color_btn(self, str(_cfg_get(cfg, f"/{key}/CaretLineBackground", "#FFF0A0")))
        bg.addRow("Window", self.col_win_bg)
        bg.addRow("Line numbers", self.col_ln_bg)
        bg.addRow("Caret line", self.col_caret_bg)
        root.addLayout(bg)

        self.syntax_btns: dict[str, QPushButton] = {}
        if syntax:
            root.addWidget(_section("Syntax highlight"))
            syn = QFormLayout()
            for label, path_suffix, default in (
                ("G-code", "GCodeHighlight", "#0000AA"),
                ("M-code", "MCodeHighlight", "#AA0000"),
                ("Axis", "AxisHighlight", "#008800"),
                ("Parameters", "ParametersHighlight", "#880088"),
                ("Parameters2", "Parameters2Highlight", "#880088"),
                ("Comments", "CommentsHighlight", "#808080"),
                ("G-code line #", "GCodeLineNumberHighlight", "#000000"),
            ):
                b = _color_btn(self, str(_cfg_get(cfg, f"/{key}/{path_suffix}", default)))
                self.syntax_btns[path_suffix] = b
                syn.addRow(label, b)
            root.addLayout(syn)

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

        self.port = QComboBox()
        self.port.setEditable(True)
        ports = self._list_ports()
        self.port.addItems(ports)
        self.port.setCurrentText(str(_cfg_get(cfg, "/machine/Port", "") or ""))
        refresh = QPushButton("Refresh ports")
        refresh.clicked.connect(self._refresh_ports)
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
        for ax in ("X", "Y", "Z", "A", "B", "C"):
            cb = QCheckBox(f"Enable {ax} axis")
            cb.setChecked(bool(_cfg_get(cfg, f"/machine/DRO/Enable{ax}", ax in ("X", "Y", "Z"))))
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

        # MachIf-specific properties (flat int/float/bool/str)
        self.spec_widgets: dict[str, QWidget] = {}
        specific = _cfg_get(cfg, "/machine/MachIfSpecific", {}) or {}
        if isinstance(specific, dict) and specific:
            root.addWidget(_section("Device-specific"))
            form_s = QFormLayout()
            for machine, props in specific.items():
                if not isinstance(props, dict):
                    continue
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
                        w = QLineEdit(str(_cfg_get(cfg, path, value) if _cfg_get(cfg, path, value) is not None else value))
                    tip = meta.get("ToolTip") or ""
                    if tip:
                        w.setToolTip(str(tip))
                    self.spec_widgets[key] = w
                    form_s.addRow(f"{machine}: {name}", w)
            root.addLayout(form_s)

        root.addStretch(1)

    def _list_ports(self) -> list[str]:
        ser = _cfg_get(self.cfg, "/temp/SerialPorts", None)
        if ser and isinstance(ser, (list, tuple)) and len(ser) > 0:
            return [str(x).split(",")[0].strip() for x in ser]
        try:
            import serial.tools.list_ports

            ports = sorted({p.device for p in serial.tools.list_ports.comports()})
            return ports or ["None"]
        except Exception:
            return ["None"]

    def _refresh_ports(self) -> None:
        cur = self.port.currentText()
        self.port.clear()
        self.port.addItems(self._list_ports())
        self.port.setCurrentText(cur)

    def apply(self) -> None:
        _cfg_set(self.cfg, "/machine/Device", self.device.currentText())
        port = self.port.currentText().split(",")[0].strip()
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
            self.ws_port = self.api_token = None

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
        self.pages: list[_SettingsPage] = []

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
