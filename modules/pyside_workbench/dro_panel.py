"""----------------------------------------------------------------------------
    dro_panel.py

    DRO + machine status for the PySide workbench.

    Matches wx Machine Status panel layout intent:
    - DRO box: enabled axes only (/machine/DRO/Enable*) + FR + ST
    - Status box: device name, version, buffer, sent %, runtime (host/side data)

    Interactive (when armed, machine open) — same as wx OnDroLeftUp:
    - Click axis value → Move-to numeric dialog → MOVE / RAPID_MOVE
    - Click axis letter → menu Home / Zero / Set to value → HOME / SET_AXIS
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMenu,
    QVBoxLayout,
    QWidget,
)

import modules.config as gc

from modules.pyside_workbench import theme
from modules.pyside_workbench.numeric_entry_dialog import NumericEntryDialog


class _ClickableLabel(QLabel):
    """Axis letter; left-click opens the axis menu (wx StaticText)."""

    clicked = Signal(str)  # axis letter e.g. "X"

    def __init__(self, axis: str, parent=None):
        super().__init__(axis, parent)
        self._axis = axis
        self.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._axis)
        super().mouseReleaseEvent(event)


class _ClickableDroField(QLineEdit):
    """Read-only DRO digits; left-click opens Move-to dialog (wx TextCtrl)."""

    clicked = Signal(str)  # axis letter

    def __init__(self, axis: str, initial: str, parent=None):
        super().__init__(initial, parent)
        self._axis = axis
        self.setObjectName("droAxis")
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setFont(theme.mono_font(20, bold=True))
        self.setMinimumWidth(150)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.clicked.emit(self._axis)
        super().mouseReleaseEvent(event)


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

    # Emitted for MainWindow → bridge (absolute move / set / home)
    move_to_requested = Signal(str, float)  # axis lower, position
    home_axis_requested = Signal(str)  # axis lower
    zero_axis_requested = Signal(str)  # axis lower → SET_AXIS 0
    set_axis_requested = Signal(str, float)  # axis lower, work coord

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
        self._axis_labels: dict[str, QLabel] = {}
        self._axis_enabled: dict[str, bool] = {}
        self._interactive = False
        self._dro_form = dro_form

        for label, key in self.AXIS_KEYS:
            axis = label  # "X"
            edit = _ClickableDroField(axis, "0.000")
            edit.clicked.connect(self._on_value_clicked)
            axis_lbl = _ClickableLabel(axis)
            axis_lbl.clicked.connect(self._on_letter_clicked)
            dro_form.addRow(axis_lbl, edit)
            self._axis_edits[key] = edit
            self._axis_labels[key] = axis_lbl
            # Default XYZ on until config applied (wx-ish)
            self._axis_enabled[key] = axis in ("X", "Y", "Z")

        # Feed rate (vel) — display only
        fr_lbl = QLabel("FR")
        fr_lbl.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.feed_rate = self._make_dro_field("0.00")
        dro_form.addRow(fr_lbl, self.feed_rate)

        # Machine state — display only
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
        self._apply_state_style("")
        self.set_interactive(False)
        self.apply_settings()

    def apply_settings(self) -> None:
        """Honor /machine/DRO/Enable* and font (wx Machine Status UpdateSettings)."""
        # Defaults: XYZ on, ABC off — match typical 3-axis; config overrides
        defaults = {
            "posx": True,
            "posy": True,
            "posz": True,
            "posa": False,
            "posb": False,
            "posc": False,
        }
        for label, key in self.AXIS_KEYS:
            enabled = defaults[key]
            if gc.CONFIG_DATA is not None:
                raw = gc.CONFIG_DATA.get(f"/machine/DRO/Enable{label}", None)
                if raw is not None:
                    enabled = bool(raw)
            self._axis_enabled[key] = enabled
            edit = self._axis_edits[key]
            lbl = self._axis_labels[key]
            edit.setVisible(enabled)
            lbl.setVisible(enabled)

        # Optional DRO font from machine settings
        if gc.CONFIG_DATA is not None:
            try:
                face = str(
                    gc.CONFIG_DATA.get("/machine/DRO/FontFace", "Monospace")
                    or "Monospace"
                )
                if face == "System":
                    face = "Monospace"
                size = int(gc.CONFIG_DATA.get("/machine/DRO/FontSize", 20) or 20)
                if size <= 0:
                    size = 20
                style = str(
                    gc.CONFIG_DATA.get("/machine/DRO/FontStyle", "bold") or "bold"
                ).lower()
                bold = "bold" in style
                font = theme.mono_font(size, bold=bold)
                if face and face != "Monospace":
                    font.setFamily(face)
                for edit in self._axis_edits.values():
                    edit.setFont(font)
                self.feed_rate.setFont(font)
                self.run_status.setFont(font)
            except (TypeError, ValueError):
                pass

    def update_settings(self) -> None:
        """wx machineStatusPanel.UpdateSettings entry."""
        self.apply_settings()

    def _make_dro_field(self, initial: str) -> QLineEdit:
        edit = QLineEdit(initial)
        edit.setObjectName("droAxis")
        edit.setReadOnly(True)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        edit.setFont(theme.mono_font(20, bold=True))
        edit.setMinimumWidth(150)
        edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return edit

    def set_interactive(self, enabled: bool) -> None:
        """Arm axis letter/value clicks (wx: only when serial open)."""
        self._interactive = bool(enabled)
        cursor = (
            QCursor(Qt.CursorShape.PointingHandCursor)
            if enabled
            else QCursor(Qt.CursorShape.ArrowCursor)
        )
        for key, edit in self._axis_edits.items():
            if not self._axis_enabled.get(key, False):
                continue
            edit.setEnabled(True)  # always show values; clicks gated in handlers
            edit.setCursor(cursor)
        for key, lbl in self._axis_labels.items():
            if not self._axis_enabled.get(key, False):
                continue
            lbl.setCursor(cursor)

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
            if not self._axis_enabled.get(key, False):
                continue
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
            self.run_status.setStyleSheet("")
            self._last_stat = ""
            return
        key = theme.state_color_key(stat)
        color = theme.STATE_COLORS.get(key, theme.STATE_COLORS["unknown"])
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

    # ------------------------------------------------------------------
    # Interactions (wx OnDroLeftUp)
    # ------------------------------------------------------------------
    def _on_value_clicked(self, axis: str) -> None:
        if not self._interactive:
            return
        key = f"pos{axis.lower()}"
        if not self._axis_enabled.get(key, False):
            return
        initial = ""
        edit = self._axis_edits.get(key)
        if edit is not None:
            initial = edit.text()
        dlg = NumericEntryDialog(
            self,
            title="Move to",
            caption=f"Enter new position for {axis} axis",
        )
        if initial:
            dlg.set_initial(initial)
        if dlg.exec() != NumericEntryDialog.DialogCode.Accepted:
            return
        self.move_to_requested.emit(axis.lower(), float(dlg.value()))

    def _on_letter_clicked(self, axis: str) -> None:
        if not self._interactive:
            return
        key = f"pos{axis.lower()}"
        if not self._axis_enabled.get(key, False):
            return
        menu = QMenu(self)
        act_home = menu.addAction("Home Axis")
        act_zero = menu.addAction("Zero Axis")
        act_set = menu.addAction("Set to value")
        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return
        ax = axis.lower()
        if chosen is act_home:
            self.home_axis_requested.emit(ax)
        elif chosen is act_zero:
            self.zero_axis_requested.emit(ax)
        elif chosen is act_set:
            dlg = NumericEntryDialog(
                self,
                title="Set To Value",
                caption=f"Enter new value for {axis} axis",
            )
            if dlg.exec() != NumericEntryDialog.DialogCode.Accepted:
                return
            self.set_axis_requested.emit(ax, float(dlg.value()))
