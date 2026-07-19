"""----------------------------------------------------------------------------
    console_panel.py

    Console output + CLI send line for the PySide workbench.
    Dumb UI: displays backend traffic; user lines become EV_CMD_SEND.

    History: Up/Down in the line edit; popup list via ▾ button / Ctrl+Up / F7.
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal, Slot
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class _CliLineEdit(QLineEdit):
    """Line edit that owns Up/Down history keys (no QComboBox interference)."""

    history_older = Signal()
    history_newer = Signal()
    history_popup = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        mods = event.modifiers()
        # Ctrl+Up → open history list (keep bare Up for shell browse)
        if key == Qt.Key.Key_Up and mods & Qt.KeyboardModifier.ControlModifier:
            self.history_popup.emit()
            event.accept()
            return
        if key == Qt.Key.Key_Up:
            self.history_older.emit()
            event.accept()
            return
        if key == Qt.Key.Key_Down:
            self.history_newer.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _HistoryPopup(QFrame):
    """Frameless popup list of CLI history (newest first)."""

    item_chosen = Signal(str)
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        title = QLabel("CLI history (Enter = insert, Esc = close)")
        title.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(title)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setMinimumWidth(320)
        self.list.setMinimumHeight(160)
        self.list.setMaximumHeight(280)
        self.list.itemActivated.connect(self._on_activated)
        self.list.itemDoubleClicked.connect(self._on_activated)
        lay.addWidget(self.list)

    def populate(self, history_newest_first: list[str]):
        self.list.clear()
        for line in history_newest_first:
            self.list.addItem(QListWidgetItem(line))
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.closed.emit()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.list.currentItem()
            if item is not None:
                self._choose(item.text())
            event.accept()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()

    def _on_activated(self, item: QListWidgetItem):
        if item is not None:
            self._choose(item.text())

    def _choose(self, text: str):
        self.item_chosen.emit(text)
        self.hide()


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
        self.cli.history_popup.connect(self.show_history_popup)
        cli_row.addWidget(self.cli, 1)

        self.btn_history = QPushButton("▾")
        self.btn_history.setToolTip("CLI history (Ctrl+Up or F7)")
        self.btn_history.setFixedWidth(32)
        self.btn_history.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.btn_history.clicked.connect(self.show_history_popup)
        cli_row.addWidget(self.btn_history)
        root.addLayout(cli_row)

        self._popup = _HistoryPopup(self)
        self._popup.item_chosen.connect(self._on_history_chosen)

        # Global-ish shortcuts when console has focus
        sc_f7 = QShortcut(QKeySequence("F7"), self)
        sc_f7.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_f7.activated.connect(self.show_history_popup)
        sc_ctrl_up = QShortcut(QKeySequence("Ctrl+Up"), self)
        sc_ctrl_up.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_ctrl_up.activated.connect(self.show_history_popup)

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
        self.btn_history.setEnabled(enabled and bool(self._history))
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
        self.btn_history.setEnabled(self.cli.isEnabled() and bool(self._history))

    @Slot()
    def _history_older(self):
        """Up arrow — step into previously sent commands (most recent first)."""
        if not self._history:
            return
        if self._browse_depth == 0:
            self._draft_before_browse = self.cli.text()
        if self._browse_depth < len(self._history):
            self._browse_depth += 1
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

    @Slot()
    def show_history_popup(self):
        if not self._history:
            return
        # Newest first for scanning
        newest_first = list(reversed(self._history))
        self._popup.populate(newest_first)
        # Position under CLI row
        anchor = self.btn_history.mapToGlobal(QPoint(0, self.btn_history.height()))
        # Align popup to left of line edit if possible
        left = self.cli.mapToGlobal(QPoint(0, self.cli.height()))
        self._popup.adjustSize()
        self._popup.move(left.x(), left.y() + 2)
        self._popup.show()
        self._popup.raise_()
        self._popup.list.setFocus(Qt.FocusReason.PopupFocusReason)

    @Slot(str)
    def _on_history_chosen(self, text: str):
        """Insert chosen history into CLI (do not auto-send)."""
        if self._popup.isVisible():
            self._popup.hide()
        self.cli.setText(text)
        self._browse_depth = 0
        self._draft_before_browse = ""
        self.focus_cli()
        self.cli.end(False)
