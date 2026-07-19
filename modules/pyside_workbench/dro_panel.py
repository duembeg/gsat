"""----------------------------------------------------------------------------
    dro_panel.py

    DRO + machine status for the PySide workbench (polished shell).
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from modules.pyside_workbench import theme


class DroPanel(QWidget):
    """Displays position (DRO) and a few status fields from EV_DATA_STATUS."""

    AXIS_KEYS = (
        ("X", "posx"),
        ("Y", "posy"),
        ("Z", "posz"),
        ("A", "posa"),
        ("B", "posb"),
        ("C", "posc"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        dro_box = QGroupBox("DRO")
        dro_form = QFormLayout(dro_box)
        dro_form.setSpacing(6)
        dro_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._axis_edits: dict[str, QLineEdit] = {}
        for label, key in self.AXIS_KEYS:
            edit = QLineEdit("0.000")
            edit.setObjectName("droAxis")
            edit.setReadOnly(True)
            edit.setAlignment(Qt.AlignmentFlag.AlignRight)
            edit.setFont(theme.mono_font(20, bold=True))
            edit.setMinimumWidth(150)
            axis_lbl = QLabel(label)
            axis_lbl.setStyleSheet("font-weight: 700; font-size: 14px;")
            dro_form.addRow(axis_lbl, edit)
            self._axis_edits[key] = edit

        status_box = QGroupBox("Status")
        status_form = QFormLayout(status_box)
        status_form.setSpacing(4)

        self.run_status = QLineEdit("")
        self.run_status.setObjectName("droState")
        self.run_status.setReadOnly(True)
        self.run_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.run_status.setFont(theme.mono_font(13, bold=True))
        status_form.addRow("State:", self.run_status)

        self.feed_rate = QLineEdit("")
        self.feed_rate.setReadOnly(True)
        self.feed_rate.setFont(theme.mono_font(11))
        self.feed_rate.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_form.addRow("Feed:", self.feed_rate)

        self.buffer_status = QLabel("—")
        self.buffer_status.setFont(theme.mono_font(11))
        status_form.addRow("Buffer:", self.buffer_status)

        self.machif_status = QLabel("—")
        status_form.addRow("MachIf:", self.machif_status)

        self.version_status = QLabel("—")
        self.version_status.setWordWrap(True)
        status_form.addRow("FW:", self.version_status)

        self.percent_status = QLabel("—")
        self.percent_status.setFont(theme.mono_font(11))
        status_form.addRow("Sent:", self.percent_status)

        self.runtime_status = QLabel("—")
        self.runtime_status.setFont(theme.mono_font(11))
        status_form.addRow("Runtime:", self.runtime_status)

        root.addWidget(dro_box)
        root.addWidget(status_box)

        self._last_stat = ""

    def clear(self):
        for edit in self._axis_edits.values():
            edit.setText("0.000")
        self.run_status.setText("")
        self._apply_state_style("")
        self.feed_rate.setText("")
        self.buffer_status.setText("—")
        self.machif_status.setText("—")
        self.version_status.setText("—")
        self.percent_status.setText("—")
        self.runtime_status.setText("—")

    def update_from_status(self, status_data: dict | None):
        if not status_data:
            return

        for _label, key in self.AXIS_KEYS:
            if key in status_data:
                try:
                    val = f"{float(status_data[key]):.3f}"
                except (TypeError, ValueError):
                    val = str(status_data[key])
                edit = self._axis_edits[key]
                if edit.text() != val:
                    edit.setText(val)

        if "stat" in status_data and status_data["stat"] is not None:
            text = str(status_data["stat"])
            if self.run_status.text() != text:
                self.run_status.setText(text)
            self._apply_state_style(text)

        if "vel" in status_data:
            try:
                fr = f"{float(status_data['vel']):.2f}"
            except (TypeError, ValueError):
                fr = str(status_data["vel"])
            if self.feed_rate.text() != fr:
                self.feed_rate.setText(fr)

        ib = status_data.get("ib")
        if ib is not None and isinstance(ib, (list, tuple)) and len(ib) >= 2:
            self.buffer_status.setText(f"{ib[1]}/{ib[0]}")

        if "machif" in status_data:
            self.machif_status.setText(str(status_data["machif"]))

        fv = status_data.get("fv")
        fb = status_data.get("fb")
        if fb is not None and fv is not None:
            self.version_status.setText(f"fb[{fb}] fv[{fv}]")
        elif fb is not None:
            self.version_status.setText(str(fb))

        if "prcnt" in status_data:
            self.percent_status.setText(str(status_data["prcnt"]))

        if "rtime" in status_data:
            rtime = status_data["rtime"]
            try:
                rtime = float(rtime)
                hours, rem = divmod(int(rtime), 3600)
                minutes, seconds = divmod(rem, 60)
                self.runtime_status.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            except (TypeError, ValueError):
                self.runtime_status.setText(str(rtime))

    def _apply_state_style(self, stat: str):
        key = theme.state_color_key(stat)
        color = theme.STATE_COLORS.get(key, theme.STATE_COLORS["unknown"])
        # Light tint background + bold colored text
        self.run_status.setStyleSheet(
            f"QLineEdit#droState {{"
            f" color: {color};"
            f" background: {color}18;"
            f" border: 1px solid {color}55;"
            f" font-weight: 700;"
            f"}}"
        )
        self._last_stat = stat
