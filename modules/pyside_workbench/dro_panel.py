"""----------------------------------------------------------------------------
    dro_panel.py

    Minimal DRO + machine status panel for the PySide workbench spike.
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


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

        dro_box = QGroupBox("DRO")
        dro_form = QFormLayout(dro_box)

        dro_font = QFont()
        dro_font.setPointSize(18)
        dro_font.setBold(True)

        self._axis_edits: dict[str, QLineEdit] = {}
        for label, key in self.AXIS_KEYS:
            edit = QLineEdit("0.000")
            edit.setReadOnly(True)
            edit.setAlignment(Qt.AlignRight)
            edit.setFont(dro_font)
            edit.setMinimumWidth(140)
            dro_form.addRow(QLabel(f"{label}:"), edit)
            self._axis_edits[key] = edit

        status_box = QGroupBox("Status")
        status_form = QFormLayout(status_box)

        self.run_status = QLineEdit("")
        self.run_status.setReadOnly(True)
        status_form.addRow("State:", self.run_status)

        self.feed_rate = QLineEdit("")
        self.feed_rate.setReadOnly(True)
        status_form.addRow("Feed:", self.feed_rate)

        self.buffer_status = QLabel("")
        status_form.addRow("Buffer:", self.buffer_status)

        self.machif_status = QLabel("")
        status_form.addRow("MachIf:", self.machif_status)

        self.version_status = QLabel("")
        status_form.addRow("FW:", self.version_status)

        self.percent_status = QLabel("")
        status_form.addRow("Sent:", self.percent_status)

        self.runtime_status = QLabel("")
        status_form.addRow("Runtime:", self.runtime_status)

        root.addWidget(dro_box)
        root.addWidget(status_box)
        root.addStretch(1)

    def clear(self):
        for edit in self._axis_edits.values():
            edit.setText("0.000")
        self.run_status.setText("")
        self.feed_rate.setText("")
        self.buffer_status.setText("")
        self.machif_status.setText("")
        self.version_status.setText("")
        self.percent_status.setText("")
        self.runtime_status.setText("")

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
