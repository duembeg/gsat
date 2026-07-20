"""----------------------------------------------------------------------------
    dro_panel.py

    DRO + machine status for the PySide workbench.

    Matches wx Machine Status panel layout intent:
    - DRO box: X/Y/Z/A/B/C + FR (feed) + ST (state) — same big mono fields
    - Status box: device name, version, buffer, sent %, runtime (host/side data)
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from modules.pyside_workbench import theme


class DroPanel(QWidget):
    """Displays position (DRO), feed rate, run state, and device status fields."""

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

        # --- DRO: axes + FR + ST (physical machine display) ---
        dro_box = QGroupBox("DRO")
        dro_form = QFormLayout(dro_box)
        dro_form.setSpacing(6)
        dro_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._axis_edits: dict[str, QLineEdit] = {}
        for label, key in self.AXIS_KEYS:
            edit = self._make_dro_field("0.000")
            axis_lbl = QLabel(label)
            axis_lbl.setStyleSheet("font-weight: 700; font-size: 14px;")
            dro_form.addRow(axis_lbl, edit)
            self._axis_edits[key] = edit

        # Feed rate (vel) — same row style as axes (wx CreateDroBox)
        fr_lbl = QLabel("FR")
        fr_lbl.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.feed_rate = self._make_dro_field("0.00")
        dro_form.addRow(fr_lbl, self.feed_rate)

        # Machine state — same size/font as axes (wx ST in DRO box)
        st_lbl = QLabel("ST")
        st_lbl.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.run_status = self._make_dro_field("")
        self.run_status.setObjectName("droState")
        self.run_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        dro_form.addRow(st_lbl, self.run_status)

        # --- Status: host / device side metadata (not DRO digits) ---
        status_box = QGroupBox("Status")
        status_form = QFormLayout(status_box)
        status_form.setSpacing(4)

        self.machif_status = QLabel("—")
        status_form.addRow("Device:", self.machif_status)

        self.version_status = QLabel("—")
        self.version_status.setWordWrap(True)
        status_form.addRow("Version:", self.version_status)

        self.buffer_status = QLabel("—")
        self.buffer_status.setFont(theme.mono_font(11))
        status_form.addRow("Buffer:", self.buffer_status)

        self.percent_status = QLabel("—")
        self.percent_status.setFont(theme.mono_font(11))
        status_form.addRow("Sent:", self.percent_status)

        self.runtime_status = QLabel("—")
        self.runtime_status.setFont(theme.mono_font(11))
        status_form.addRow("Runtime:", self.runtime_status)

        root.addWidget(dro_box)
        root.addWidget(status_box)

        self._last_stat = ""
        # ST shares DRO chrome from the start (not only after first status push)
        self._apply_state_style("")

    def _make_dro_field(self, initial: str) -> QLineEdit:
        edit = QLineEdit(initial)
        edit.setObjectName("droAxis")
        edit.setReadOnly(True)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        edit.setFont(theme.mono_font(20, bold=True))
        edit.setMinimumWidth(150)
        return edit

    def clear(self):
        for edit in self._axis_edits.values():
            edit.setText("0.000")
        self.feed_rate.setText("0.00")
        self.run_status.setText("")
        self._apply_state_style("")
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

        if "vel" in status_data:
            try:
                fr = f"{float(status_data['vel']):.2f}"
            except (TypeError, ValueError):
                fr = str(status_data["vel"])
            if self.feed_rate.text() != fr:
                self.feed_rate.setText(fr)

        if "stat" in status_data and status_data["stat"] is not None:
            text = str(status_data["stat"])
            if self.run_status.text() != text:
                self.run_status.setText(text)
            self._apply_state_style(text)

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
        """Color ST field while keeping DRO-sized mono look."""
        if not stat:
            # Match #droAxis chrome until we know machine state
            self.run_status.setStyleSheet("")
            self._last_stat = ""
            return
        key = theme.state_color_key(stat)
        color = theme.STATE_COLORS.get(key, theme.STATE_COLORS["unknown"])
        # Keep dark DRO field background; tint text/border by state
        self.run_status.setStyleSheet(
            f"QLineEdit#droState {{"
            f" font-family: monospace; font-size: 20px; font-weight: 700;"
            f" color: {color};"
            f" background: #0B1220;"
            f" border: 1px solid {color};"
            f" border-radius: 4px; padding: 4px 8px; min-height: 28px;"
            f"}}"
        )
        self._last_stat = stat
