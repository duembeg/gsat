"""----------------------------------------------------------------------------
    gcode_panel.py

    Simple G-code list + program-counter (PC) marker for the PySide workbench.
    Read-oriented spike view — not a full editor/parity with wx STC.
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class GcodePanel(QWidget):
    """Displays file lines and highlights the current PC line (0-based)."""

    # Emitted when user wants PC set to a line (0-based)
    set_pc_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._lines: list[str] = []  # as stored for backend (with newlines)
        self._pc = 0
        self._path = ""
        self._pc_bg = QBrush(QColor(255, 240, 160))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        header = QHBoxLayout()
        self.title_label = QLabel("G-code: (none)")
        self.title_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        header.addWidget(self.title_label, 1)
        self.pc_label = QLabel("PC: 0")
        header.addWidget(self.pc_label)
        root.addLayout(header)

        self.list = QListWidget()
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        mono.setPointSize(10)
        self.list.setFont(mono)
        self.list.setUniformItemSizes(True)
        self.list.setAlternatingRowColors(True)
        self.list.itemDoubleClicked.connect(self._on_double_click)
        root.addWidget(self.list, 1)

        hint = QLabel("Double-click a line to Set PC  ·  PC line marked with ▶")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(hint)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def path(self) -> str:
        return self._path

    def lines(self) -> list[str]:
        """Lines including original terminators where possible (backend format)."""
        return list(self._lines)

    def line_count(self) -> int:
        return len(self._lines)

    def current_pc(self) -> int:
        return self._pc

    def selected_line(self) -> int:
        row = self.list.currentRow()
        return row if row >= 0 else self._pc

    def clear(self):
        self._lines = []
        self._path = ""
        self._pc = 0
        self.list.clear()
        self.title_label.setText("G-code: (none)")
        self.pc_label.setText("PC: 0")

    def load_lines(self, path: str, lines: list[str]):
        """Load lines; each element should end with ``\\n`` when possible."""
        self._path = path or ""
        self._lines = list(lines)
        self.list.clear()

        width = max(3, len(str(max(len(self._lines), 1))))
        for i, raw in enumerate(self._lines):
            text = raw.rstrip("\r\n")
            item = QListWidgetItem(f" {i + 1:>{width}} | {text}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(item)

        base = path.rsplit("/", 1)[-1] if path else "(memory)"
        n = len(self._lines)
        self.title_label.setText(f"G-code: {base}  ({n} lines)")
        self.set_pc(0, scroll=True)

    def load_file(self, path: str) -> int:
        """Read a text file; return number of lines. Raises OSError on failure."""
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        lines = content.splitlines(True)
        self.load_lines(path, lines)
        return len(lines)

    @Slot(int)
    def set_pc(self, pc: int, scroll: bool = True):
        n = len(self._lines)
        if n == 0:
            self._pc = 0
            self.pc_label.setText("PC: 0")
            return

        pc = max(0, min(int(pc), n - 1))
        old = self._pc
        self._pc = pc
        self.pc_label.setText(f"PC: {pc}  (line {pc + 1})")

        if 0 <= old < self.list.count() and old != pc:
            self._paint_row(old, is_pc=False)
        if 0 <= pc < self.list.count():
            self._paint_row(pc, is_pc=True)
            if scroll:
                self.list.setCurrentRow(pc)
                item = self.list.item(pc)
                if item is not None:
                    self.list.scrollToItem(
                        item, QListWidget.ScrollHint.PositionAtCenter
                    )

    def goto_pc(self):
        self.set_pc(self._pc, scroll=True)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _paint_row(self, row: int, is_pc: bool):
        item = self.list.item(row)
        if item is None or row >= len(self._lines):
            return
        raw = self._lines[row].rstrip("\r\n")
        width = max(3, len(str(max(len(self._lines), 1))))
        mark = "▶" if is_pc else " "
        item.setText(f"{mark}{row + 1:>{width}} | {raw}")
        if is_pc:
            item.setBackground(self._pc_bg)
        else:
            item.setBackground(QBrush())

    @Slot(QListWidgetItem)
    def _on_double_click(self, item: QListWidgetItem):
        if item is None:
            return
        line = item.data(Qt.ItemDataRole.UserRole)
        if line is None:
            line = self.list.row(item)
        self.set_pc_requested.emit(int(line))
