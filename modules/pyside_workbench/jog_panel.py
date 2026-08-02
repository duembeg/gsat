"""----------------------------------------------------------------------------
    jog_panel.py

    Machine jogging panel for the PySide workbench (thin client).
    Layout parity with classic wx gsatJoggingPanel; presentation aims for a
    cleaner professional pad (flat icon tiles, light surface card) rather
    than cloning wx chrome.

    Emits requests only — main window forwards EV_CMD_* / serial lines.
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import modules.config as gc
from modules.pyside_workbench import icons as wb_icons


def _section_label(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("sectionLabel")
    return lab


class JogPanel(QWidget):
    """Machine Jogging pad + custom buttons."""

    # axis lower-case key, signed step string, rapid bool, feed float|None
    jog_relative = Signal(str, str, bool, object)
    jog_stop = Signal()
    home_axes = Signal(dict)  # e.g. {'x': 0, 'y': 0}
    zero_axes = Signal(dict)  # SET_AXIS work coords
    # absolute jog dict (axis→0), rapid bool, feed float|None
    jog_absolute = Signal(dict, bool, object)
    probe_axes = Signal(dict)  # EV_CMD_PROBE_HELPER payload
    # multi-line G-code script (spindle/coolant/custom)
    gcode_script = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("jogPanel")

        # Outer shell: scroll when dock is shorter/narrower than content
        # (avoids step/rapid controls painting over the fixed icon pad).
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("jogScroll")
        # False: never compress content into the viewport (that caused STEP
        # SIZE / Rapid to paint over the fixed icon pad when the dock is short).
        self._scroll.setWidgetResizable(False)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self._scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        content = QWidget()
        content.setObjectName("jogPanelContent")
        self._content = content
        root = QVBoxLayout(content)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)
        root.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)
        self._content_layout = root

        # ------------------------------------------------------------------
        # Icon pad card — same grid positions as wx CreateJoggingControls.
        # Fixed size: dock squeeze must not shrink tiles (tiny/invisible icons).
        # ------------------------------------------------------------------
        pad_frame = QFrame()
        pad_frame.setObjectName("jogPad")
        pad_frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        pad_sz = wb_icons.jog_pad_content_size()
        pad_frame.setFixedSize(pad_sz)
        pad_frame.setMinimumSize(pad_sz)
        self._pad_frame = pad_frame

        pad_outer = QVBoxLayout(pad_frame)
        m = wb_icons.JOG_PAD_MARGIN
        pad_outer.setContentsMargins(m, m, m, m)
        pad_outer.setSpacing(0)

        pad = QGridLayout()
        pad.setSpacing(wb_icons.JOG_PAD_SPACING)
        pad.setContentsMargins(0, 0, 0, 0)
        pad.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        # Never let the grid redistribute extra space into button cells
        for c in range(wb_icons.JOG_PAD_COLS):
            pad.setColumnMinimumWidth(c, wb_icons.JOG_BUTTON_SIZE.width())
            pad.setColumnStretch(c, 0)
        for r in range(wb_icons.JOG_PAD_ROWS):
            pad.setRowMinimumHeight(r, wb_icons.JOG_BUTTON_SIZE.height())
            pad.setRowStretch(r, 0)

        btn_w = wb_icons.JOG_BUTTON_SIZE.width()
        btn_h = wb_icons.JOG_BUTTON_SIZE.height()

        def icon_btn(icon_name: str, tip: str) -> QToolButton:
            b = QToolButton()
            b.setObjectName("jogPadButton")
            b.setAutoRaise(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            b.setFixedSize(btn_w, btn_h)
            b.setMinimumSize(btn_w, btn_h)
            b.setMaximumSize(btn_w, btn_h)
            b.setIconSize(wb_icons.JOG_ICON_SIZE)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            if not wb_icons.apply_jog_button_icon(b, icon_name):
                b.setText(icon_name.replace("_", "\n")[:8])
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            return b

        # Row 0
        self.btn_home_xyz = icon_btn("home_xyz", "Home XYZ axis")
        self.btn_y_pos = icon_btn("pos_y", "Move Y axis positive by step size")
        self.btn_home_x = icon_btn("home_x", "Home X axis")
        self.btn_z_pos = icon_btn("pos_z", "Move Z axis positive by step size")
        self.btn_zero_xyz = icon_btn("zero_xyz", "Zero all axes (work coords)")
        self.btn_zero_xy = icon_btn("zero_xy", "Zero X and Y axes")
        self.btn_zero_z = icon_btn("zero_z", "Zero Z axis")

        # Row 1
        self.btn_x_neg = icon_btn("neg_x", "Move X axis negative by step size")
        self.btn_goto_zero_xy = icon_btn("goto_zero_xy", "Move XY axes to zero")
        self.btn_x_pos = icon_btn("pos_x", "Move X axis positive by step size")
        self.btn_home_z = icon_btn("home_z", "Home Z axis")
        self.btn_coolant_on = icon_btn("coolant_on", "Coolant ON")
        self.btn_coolant_off = icon_btn("coolant_off", "Coolant OFF")
        self.btn_probe_z = icon_btn("probe_z", "Probe Z")

        # Row 2
        self.btn_y_neg = icon_btn("neg_y", "Move Y axis negative by step size")
        self.btn_home_y = icon_btn("home_y", "Home Y axis")
        self.btn_z_neg = icon_btn("neg_z", "Move Z axis negative by step size")
        self.btn_spindle_cw = icon_btn("spindle_cw", "Spindle CW ON")
        self.btn_spindle_ccw = icon_btn("spindle_ccw", "Spindle CCW ON")
        self.btn_spindle_off = icon_btn("spindle_off", "Spindle OFF")

        pad.addWidget(self.btn_home_xyz, 0, 0)
        pad.addWidget(self.btn_y_pos, 0, 1)
        pad.addWidget(self.btn_home_x, 0, 2)
        pad.addWidget(self.btn_z_pos, 0, 3)
        pad.addWidget(self.btn_zero_xyz, 0, 4)
        pad.addWidget(self.btn_zero_xy, 0, 5)
        pad.addWidget(self.btn_zero_z, 0, 6)

        pad.addWidget(self.btn_x_neg, 1, 0)
        pad.addWidget(self.btn_goto_zero_xy, 1, 1)
        pad.addWidget(self.btn_x_pos, 1, 2)
        pad.addWidget(self.btn_home_z, 1, 3)
        pad.addWidget(self.btn_coolant_on, 1, 4)
        pad.addWidget(self.btn_coolant_off, 1, 5)
        pad.addWidget(self.btn_probe_z, 1, 6)

        pad.addWidget(self.btn_y_neg, 2, 1)
        pad.addWidget(self.btn_home_y, 2, 2)
        pad.addWidget(self.btn_z_neg, 2, 3)
        pad.addWidget(self.btn_spindle_cw, 2, 4)
        pad.addWidget(self.btn_spindle_ccw, 2, 5)
        pad.addWidget(self.btn_spindle_off, 2, 6)

        pad_outer.addLayout(pad)
        root.addWidget(pad_frame, 0, Qt.AlignmentFlag.AlignLeft)

        # Axis jog
        self.btn_y_pos.clicked.connect(lambda: self._jog("y", True))
        self.btn_y_neg.clicked.connect(lambda: self._jog("y", False))
        self.btn_x_pos.clicked.connect(lambda: self._jog("x", True))
        self.btn_x_neg.clicked.connect(lambda: self._jog("x", False))
        self.btn_z_pos.clicked.connect(lambda: self._jog("z", True))
        self.btn_z_neg.clicked.connect(lambda: self._jog("z", False))

        # Home
        self.btn_home_xyz.clicked.connect(
            lambda: self.home_axes.emit({"x": 0, "y": 0, "z": 0})
        )
        self.btn_home_x.clicked.connect(lambda: self.home_axes.emit({"x": 0}))
        self.btn_home_y.clicked.connect(lambda: self.home_axes.emit({"y": 0}))
        self.btn_home_z.clicked.connect(lambda: self.home_axes.emit({"z": 0}))

        # Zero work coords
        self.btn_zero_xyz.clicked.connect(
            lambda: self.zero_axes.emit({"x": 0, "y": 0, "z": 0})
        )
        self.btn_zero_xy.clicked.connect(
            lambda: self.zero_axes.emit({"x": 0, "y": 0})
        )
        self.btn_zero_z.clicked.connect(lambda: self.zero_axes.emit({"z": 0}))

        self.btn_goto_zero_xy.clicked.connect(self._goto_zero_xy)
        self.btn_probe_z.clicked.connect(lambda: self.probe_axes.emit({"z": -1}))

        self.btn_spindle_cw.clicked.connect(self._spindle_cw)
        self.btn_spindle_ccw.clicked.connect(self._spindle_ccw)
        self.btn_spindle_off.clicked.connect(
            lambda: self.gcode_script.emit(gc.DEVICE_CMD_SPINDLE_OFF)
        )
        self.btn_coolant_on.clicked.connect(
            lambda: self.gcode_script.emit(gc.DEVICE_CMD_COOLANT_ON)
        )
        self.btn_coolant_off.clicked.connect(
            lambda: self.gcode_script.emit(gc.DEVICE_CMD_COOLANT_OFF)
        )

        # ------------------------------------------------------------------
        # Step size + feed / rapid + spindle rpm
        # ------------------------------------------------------------------
        lower = QHBoxLayout()
        lower.setSpacing(16)
        lower.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Step size block
        step_col = QVBoxLayout()
        step_col.setSpacing(6)
        step_col.addWidget(_section_label("Step size"))

        step_spin_row = QHBoxLayout()
        step_spin_row.setSpacing(6)
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setObjectName("jogSpin")
        self.step_spin.setDecimals(3)
        self.step_spin.setRange(0.0, 9999.0)
        self.step_spin.setSingleStep(0.1)
        self.step_spin.setToolTip("Jog controls step size")
        self.step_spin.setMinimumWidth(100)
        try:
            default_step = float(
                gc.CONFIG_DATA.get("/jogging/JogStepSize", 1.0) or 1.0
            )
        except (TypeError, ValueError):
            default_step = 1.0
        if default_step <= 0:
            default_step = 1.0
        self.step_spin.setValue(default_step)
        step_spin_row.addWidget(self.step_spin)

        self._step_preset_0p05 = self._make_preset("0.05", 0.05)
        step_spin_row.addWidget(self._step_preset_0p05)
        step_spin_row.addStretch(1)
        step_col.addLayout(step_spin_row)

        presets = QGridLayout()
        presets.setSpacing(4)
        self._step_preset_btns: list[QPushButton] = []
        for i, val in enumerate((0.1, 0.5, 1.0, 5.0, 10.0, 20.0, 50.0, 100.0)):
            label = str(int(val)) if val >= 1 else str(val)
            b = self._make_preset(label, val)
            presets.addWidget(b, i // 4, i % 4)
            self._step_preset_btns.append(b)
        step_col.addLayout(presets)
        lower.addLayout(step_col)

        # Feed / rapid / spindle
        feed_col = QVBoxLayout()
        feed_col.setSpacing(6)

        self.rapid_check = QCheckBox("Rapid")
        self.rapid_check.setObjectName("jogRapid")
        self.rapid_check.setToolTip(
            "Enables rapid jog positioning, otherwise feed rate"
        )
        try:
            self.rapid_check.setChecked(bool(gc.STATE_DATA.joggingRapid))
        except Exception:
            self.rapid_check.setChecked(
                bool(gc.CONFIG_DATA.get("/jogging/JogRapid", False))
            )
        self.rapid_check.toggled.connect(self._on_rapid_toggled)
        feed_col.addWidget(self.rapid_check)

        self.feed_spin = QDoubleSpinBox()
        self.feed_spin.setObjectName("jogSpin")
        self.feed_spin.setDecimals(0)
        self.feed_spin.setRange(0, 99999)
        self.feed_spin.setSingleStep(1)
        self.feed_spin.setToolTip("Jog feed rate")
        self.feed_spin.setMinimumWidth(100)
        try:
            feed = float(gc.STATE_DATA.joggingFeedRate)
        except Exception:
            try:
                feed = float(gc.CONFIG_DATA.get("/jogging/JogFeedRate", 1000) or 1000)
            except (TypeError, ValueError):
                feed = 1000.0
        self.feed_spin.setValue(feed)
        self.feed_spin.valueChanged.connect(self._on_feed_changed)
        feed_col.addWidget(self.feed_spin)

        feed_col.addWidget(_section_label("Spindle (rpm)"))
        self.spindle_spin = QDoubleSpinBox()
        self.spindle_spin.setObjectName("jogSpin")
        self.spindle_spin.setDecimals(0)
        self.spindle_spin.setRange(0, 99999)
        self.spindle_spin.setSingleStep(100)
        self.spindle_spin.setToolTip("Spindle speed for CW/CCW ON")
        self.spindle_spin.setMinimumWidth(100)
        try:
            sp = float(gc.CONFIG_DATA.get("/jogging/SpindleSpeed", 0) or 0)
        except (TypeError, ValueError):
            sp = 0.0
        self.spindle_spin.setValue(sp)
        feed_col.addWidget(self.spindle_spin)

        feed_col.addStretch(1)
        lower.addLayout(feed_col)
        lower.addStretch(1)
        root.addLayout(lower)

        # ------------------------------------------------------------------
        # Custom buttons
        # ------------------------------------------------------------------
        root.addWidget(_section_label("Custom buttons"))
        self._custom_grid = QGridLayout()
        self._custom_grid.setSpacing(6)
        self._custom_buttons: list[QPushButton] = []
        self._custom_meta: list[dict] = []
        root.addLayout(self._custom_grid)
        self._rebuild_custom_buttons()

        # No stretch: content height must stay the sum of children (no squeeze)

        self._scroll.setWidget(content)
        shell.addWidget(self._scroll)

        # Panel may shrink; content is fixed natural size → scrollbars, no overlap
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._sync_content_size()

        self._machine_widgets = [
            self.btn_x_pos,
            self.btn_x_neg,
            self.btn_y_pos,
            self.btn_y_neg,
            self.btn_z_pos,
            self.btn_z_neg,
            self.btn_home_xyz,
            self.btn_home_x,
            self.btn_home_y,
            self.btn_home_z,
            self.btn_zero_xyz,
            self.btn_zero_xy,
            self.btn_zero_z,
            self.btn_goto_zero_xy,
            self.btn_probe_z,
            self.btn_coolant_on,
            self.btn_coolant_off,
            self.btn_spindle_cw,
            self.btn_spindle_ccw,
            self.btn_spindle_off,
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def minimumSizeHint(self) -> QSize:
        # Allow a short dock; user scrolls for the rest
        pad = wb_icons.jog_pad_content_size()
        return QSize(min(280, pad.width() + 16), 160)

    def sizeHint(self) -> QSize:
        # Prefer full pad + step/feed/customs so factory dock starts unscrolled
        pad = wb_icons.jog_pad_content_size()
        return QSize(pad.width() + 24, pad.height() + 280)

    def set_enabled(self, enabled: bool):
        """Enable machine actions when session is open and not streaming."""
        for w in self._machine_widgets:
            w.setEnabled(enabled)
        for btn, meta in zip(self._custom_buttons, self._custom_meta):
            script = (meta.get("script") or "").strip()
            btn.setEnabled(bool(enabled and script))

    def update_settings(self) -> None:
        """Reload feed/rapid/spindle/custom from config (wx UpdateSettings)."""
        try:
            feed = float(gc.CONFIG_DATA.get("/jogging/JogFeedRate", 1000) or 1000)
            self.feed_spin.setValue(feed)
            gc.STATE_DATA.joggingFeedRate = feed
        except Exception:
            pass
        try:
            rapid = bool(gc.CONFIG_DATA.get("/jogging/JogRapid", False))
            self.rapid_check.setChecked(rapid)
            gc.STATE_DATA.joggingRapid = rapid
        except Exception:
            pass
        try:
            sp = float(gc.CONFIG_DATA.get("/jogging/SpindleSpeed", 0) or 0)
            self.spindle_spin.setValue(sp)
        except Exception:
            pass
        self._rebuild_custom_buttons()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _sync_content_size(self) -> None:
        """Lock content to full layout size so QScrollArea never compresses it."""
        content = getattr(self, "_content", None)
        if content is None:
            return
        layout = content.layout()
        if layout is not None:
            layout.activate()
        # sizeHint after activate is the non-overlapping stack height
        sh = content.sizeHint()
        pad = wb_icons.jog_pad_content_size()
        w = max(sh.width(), pad.width() + 16, content.minimumSizeHint().width())
        h = max(sh.height(), pad.height() + 200, content.minimumSizeHint().height())
        content.setFixedSize(w, h)
        content.updateGeometry()

    def _make_preset(self, label: str, value: float) -> QPushButton:
        b = QPushButton(label)
        b.setObjectName("jogPresetButton")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedWidth(44)
        b.setToolTip(f"Set step size to {label}")
        b.clicked.connect(lambda checked=False, v=value: self.step_spin.setValue(v))
        return b

    def _rebuild_custom_buttons(self) -> None:
        while self._custom_grid.count():
            item = self._custom_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._custom_buttons.clear()
        self._custom_meta.clear()

        customs = {}
        try:
            customs = gc.CONFIG_DATA.get("/jogging/CustomButtons", {}) or {}
        except Exception:
            customs = {}
        if not isinstance(customs, dict):
            customs = {}

        if not customs:
            for i in range(1, 5):
                lab = gc.CONFIG_DATA.get(f"/jogging/Custom{i}Label", f"Custom {i}")
                scr = gc.CONFIG_DATA.get(f"/jogging/Custom{i}Script", "") or ""
                customs[f"Custom{i}"] = {"Label": lab, "Script": scr}

        cols = 4
        for idx, name in enumerate(sorted(customs.keys())):
            meta = customs[name] or {}
            label = str(meta.get("Label") or name)
            script = str(meta.get("Script") or "")
            btn = QPushButton(label)
            btn.setObjectName("jogCustomButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(script if script else "(no script)")
            btn.setMinimumWidth(72)
            btn.clicked.connect(
                lambda checked=False, s=script: self._emit_script(s)
            )
            row, col = divmod(idx, cols)
            self._custom_grid.addWidget(btn, row, col)
            self._custom_buttons.append(btn)
            self._custom_meta.append(
                {"name": name, "label": label, "script": script}
            )
            btn.setEnabled(False)

        # Custom row height can change; keep scroll content non-compressed
        if getattr(self, "_scroll", None) is not None:
            self._sync_content_size()

    def _emit_script(self, script: str) -> None:
        script = (script or "").strip()
        if not script:
            return
        self.gcode_script.emit(script)

    def _jog_params(self) -> tuple[bool, object]:
        rapid = self.rapid_check.isChecked()
        feed = None if rapid else float(self.feed_spin.value())
        try:
            gc.STATE_DATA.joggingRapid = rapid
            gc.STATE_DATA.joggingFeedRate = float(self.feed_spin.value())
        except Exception:
            pass
        return rapid, feed

    def _jog(self, axis: str, positive: bool):
        step = float(self.step_spin.value())
        if not positive:
            step = -step
        step_str = gc.NUMBER_FORMAT_STRING % step
        rapid, feed = self._jog_params()
        self.jog_relative.emit(axis, step_str, rapid, feed)

    def _goto_zero_xy(self):
        rapid, feed = self._jog_params()
        self.jog_absolute.emit({"x": 0, "y": 0}, rapid, feed)

    def _spindle_cw(self):
        speed = int(round(self.spindle_spin.value()))
        self.gcode_script.emit(f"{gc.DEVICE_CMD_SPINDLE_CW_ON} S{speed}")

    def _spindle_ccw(self):
        speed = int(round(self.spindle_spin.value()))
        self.gcode_script.emit(f"{gc.DEVICE_CMD_SPINDLE_CCW_ON} S{speed}")

    @Slot(bool)
    def _on_rapid_toggled(self, checked: bool):
        try:
            gc.STATE_DATA.joggingRapid = bool(checked)
        except Exception:
            pass

    @Slot(float)
    def _on_feed_changed(self, value: float):
        try:
            gc.STATE_DATA.joggingFeedRate = float(value)
        except Exception:
            pass
