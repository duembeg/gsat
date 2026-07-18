"""----------------------------------------------------------------------------
    console_panel.py

    Console output + CLI send line for the PySide workbench.
    Dumb UI: displays backend traffic; user lines become EV_CMD_SEND.
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class _CliLineEdit(QLineEdit):
    """Line edit that owns Up/Down history keys (no QComboBox interference)."""

    history_older = Signal()
    history_newer = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Up:
            self.history_older.emit()
            event.accept()
            return
        if key == Qt.Key.Key_Down:
            self.history_newer.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ConsolePanel(QWidget):
    """Log view + command line. Emits ``line_submitted`` with the raw command
    (no trailing newline); main window / bridge adds ``\\n`` for the backend.
    """

    line_submitted = Signal(str)

    def __init__(self, parent=None, max_history: int = 40):
        super().__init__(parent)
        self._max_history = max(1, int(max_history))
        # Chronological: index 0 = oldest, -1 = most recently sent
        self._history: list[str] = []
        # Browse depth from the "live" empty line: 0 = drafting new,
        # 1 = last sent, 2 = one before that, … (shell Up/Down)
        self._browse_depth = 0
        self._draft_before_browse = ""
        self._last_submitted = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Console — machine RX/TX and events …")
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        root.addWidget(self.log_view, 1)

        cli_row = QHBoxLayout()
        cli_row.setContentsMargins(0, 0, 0, 0)
        cli_row.addWidget(QLabel("CLI:"))

        self.cli = _CliLineEdit()
        self.cli.setPlaceholderText(
            "Send line to machine (Enter) — e.g. ?  G0 X0  $J=G91 X1 F500"
        )
        self.cli.setClearButtonEnabled(True)
        self.cli.returnPressed.connect(self._on_return_pressed)
        self.cli.history_older.connect(self._history_older)
        self.cli.history_newer.connect(self._history_newer)
        # Keep "cli" as the line edit for enable/focus API used by main window
        cli_row.addWidget(self.cli, 1)
        root.addLayout(cli_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @Slot(object)
    def append_text(self, text):
        """Append console text; strip trailing newlines (Qt adds one)."""
        if text is None:
            return
        text = str(text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.rstrip("\n")
        if not text:
            return
        self.log_view.appendPlainText(text)

    def set_cli_enabled(self, enabled: bool):
        self.cli.setEnabled(enabled)
        if enabled:
            self.cli.setPlaceholderText(
                "Send line to machine (Enter) — e.g. ?  G0 X0  $J=G91 X1 F500"
            )
        else:
            self.cli.setPlaceholderText(
                "Connect and open machine to send commands"
            )

    def focus_cli(self):
        self.cli.setFocus(Qt.FocusReason.OtherFocusReason)
        self.cli.selectAll()

    # ------------------------------------------------------------------
    # CLI submit / history
    # ------------------------------------------------------------------
    @Slot()
    def _on_return_pressed(self):
        line = self.cli.text().strip()
        if not line:
            return
        if not self.cli.isEnabled():
            return

        self._remember(line)
        self.cli.clear()
        self._browse_depth = 0
        self._draft_before_browse = ""
        self.line_submitted.emit(line)

    def _remember(self, line: str):
        if line == self._last_submitted and self._history and self._history[-1] == line:
            return
        if line in self._history:
            self._history.remove(line)
        self._history.append(line)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        self._last_submitted = line

    @Slot()
    def _history_older(self):
        """Up arrow — step into previously sent commands (most recent first)."""
        if not self._history:
            return
        if self._browse_depth == 0:
            # Preserve whatever the user was typing before browsing
            self._draft_before_browse = self.cli.text()
        if self._browse_depth < len(self._history):
            self._browse_depth += 1
        # depth 1 → history[-1] (last sent), depth 2 → history[-2], …
        self.cli.setText(self._history[-self._browse_depth])
        self.cli.end(False)

    @Slot()
    def _history_newer(self):
        """Down arrow — step back toward the live draft."""
        if self._browse_depth <= 0:
            return
        self._browse_depth -= 1
        if self._browse_depth == 0:
            self.cli.setText(self._draft_before_browse)
        else:
            self.cli.setText(self._history[-self._browse_depth])
        self.cli.end(False)
