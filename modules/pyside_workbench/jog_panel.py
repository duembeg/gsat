"""----------------------------------------------------------------------------
    jog_panel.py

    Essential jog controls for the PySide workbench (thin client).
    Emits jog requests; main window forwards EV_CMD_JOG_* to the backend.
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import modules.config as gc


class JogPanel(QWidget):
    """±X/Y/Z jog, step, feed/rapid, stop. No interactive-hold or custom scripts."""

    # axis lower-case key, signed step string, rapid bool, feed float|None
    jog_relative = Signal(str, str, bool, object)
    jog_stop = Signal()
    home_axes = Signal(dict)  # e.g. {'x': 0, 'y': 0}

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        box = QGroupBox("Jog")
        box_layout = QVBoxLayout(box)

        # Axis pad
        pad = QGridLayout()
        self.btn_y_pos = QPushButton("+Y")
        self.btn_y_neg = QPushButton("-Y")
        self.btn_x_neg = QPushButton("-X")
        self.btn_x_pos = QPushButton("+X")
        self.btn_z_pos = QPushButton("+Z")
        self.btn_z_neg = QPushButton("-Z")
        for b in (
            self.btn_y_pos,
            self.btn_y_neg,
            self.btn_x_neg,
            self.btn_x_pos,
            self.btn_z_pos,
            self.btn_z_neg,
        ):
            b.setMinimumSize(48, 36)

        pad.addWidget(self.btn_y_pos, 0, 1)
        pad.addWidget(self.btn_x_neg, 1, 0)
        pad.addWidget(self.btn_x_pos, 1, 2)
        pad.addWidget(self.btn_y_neg, 2, 1)
        pad.addWidget(self.btn_z_pos, 0, 3)
        pad.addWidget(self.btn_z_neg, 2, 3)
        box_layout.addLayout(pad)

        self.btn_y_pos.clicked.connect(lambda: self._jog("y", True))
        self.btn_y_neg.clicked.connect(lambda: self._jog("y", False))
        self.btn_x_pos.clicked.connect(lambda: self._jog("x", True))
        self.btn_x_neg.clicked.connect(lambda: self._jog("x", False))
        self.btn_z_pos.clicked.connect(lambda: self._jog("z", True))
        self.btn_z_neg.clicked.connect(lambda: self._jog("z", False))

        # Step / feed
        opts = QHBoxLayout()
        opts.addWidget(QLabel("Step:"))
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setDecimals(3)
        self.step_spin.setRange(0.001, 10000.0)
        self.step_spin.setSingleStep(0.1)
        try:
            default_step = float(gc.CONFIG_DATA.get("/jogging/JogStepSize", 1.0) or 1.0)
        except (TypeError, ValueError):
            default_step = 1.0
        # config key may not exist
        if default_step <= 0:
            default_step = 1.0
        self.step_spin.setValue(default_step)
        opts.addWidget(self.step_spin)

        for preset in (0.1, 0.5, 1.0, 5.0, 10.0):
            b = QPushButton(str(preset))
            b.setMaximumWidth(40)
            b.clicked.connect(lambda checked=False, v=preset: self.step_spin.setValue(v))
            opts.addWidget(b)
        box_layout.addLayout(opts)

        feed_row = QHBoxLayout()
        feed_row.addWidget(QLabel("Feed:"))
        self.feed_spin = QDoubleSpinBox()
        self.feed_spin.setDecimals(0)
        self.feed_spin.setRange(1, 50000)
        self.feed_spin.setSingleStep(50)
        try:
            feed = float(gc.STATE_DATA.joggingFeedRate)
        except Exception:
            try:
                feed = float(gc.CONFIG_DATA.get("/jogging/JogFeedRate", 1000) or 1000)
            except (TypeError, ValueError):
                feed = 1000.0
        self.feed_spin.setValue(feed)
        feed_row.addWidget(self.feed_spin)

        self.rapid_check = QCheckBox("Rapid")
        try:
            self.rapid_check.setChecked(bool(gc.STATE_DATA.joggingRapid))
        except Exception:
            self.rapid_check.setChecked(
                bool(gc.CONFIG_DATA.get("/jogging/JogRapid", False))
            )
        feed_row.addWidget(self.rapid_check)
        box_layout.addLayout(feed_row)

        # Stop + home essentials
        act = QHBoxLayout()
        self.btn_stop = QPushButton("Jog stop")
        self.btn_stop.setToolTip("EV_CMD_JOG_STOP")
        self.btn_stop.clicked.connect(self.jog_stop.emit)
        act.addWidget(self.btn_stop)

        self.btn_home_xy = QPushButton("Home XY")
        self.btn_home_xy.clicked.connect(lambda: self.home_axes.emit({"x": 0, "y": 0}))
        act.addWidget(self.btn_home_xy)

        self.btn_home_z = QPushButton("Home Z")
        self.btn_home_z.clicked.connect(lambda: self.home_axes.emit({"z": 0}))
        act.addWidget(self.btn_home_z)

        self.btn_home_all = QPushButton("Home XYZ")
        self.btn_home_all.clicked.connect(
            lambda: self.home_axes.emit({"x": 0, "y": 0, "z": 0})
        )
        act.addWidget(self.btn_home_all)
        box_layout.addLayout(act)

        root.addWidget(box)
        root.addStretch(1)

        self._axis_buttons = [
            self.btn_x_pos,
            self.btn_x_neg,
            self.btn_y_pos,
            self.btn_y_neg,
            self.btn_z_pos,
            self.btn_z_neg,
            self.btn_stop,
            self.btn_home_xy,
            self.btn_home_z,
            self.btn_home_all,
            self.step_spin,
            self.feed_spin,
            self.rapid_check,
        ]

    def set_enabled(self, enabled: bool):
        for w in self._axis_buttons:
            w.setEnabled(enabled)

    def _jog(self, axis: str, positive: bool):
        step = float(self.step_spin.value())
        if not positive:
            step = -step
        step_str = gc.NUMBER_FORMAT_STRING % step
        rapid = self.rapid_check.isChecked()
        feed = None if rapid else float(self.feed_spin.value())
        # Keep state in sync for other panels / future use
        try:
            gc.STATE_DATA.joggingRapid = rapid
            gc.STATE_DATA.joggingFeedRate = float(self.feed_spin.value())
        except Exception:
            pass
        self.jog_relative.emit(axis, step_str, rapid, feed)
