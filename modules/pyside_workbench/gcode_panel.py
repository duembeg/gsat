"""----------------------------------------------------------------------------
    gcode_panel.py

    Simple G-code list + PC + breakpoint markers for the PySide workbench.
    Read-oriented spike view — not full STC/QScintilla parity yet.
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class GcodePanel(QWidget):
    """Displays file lines, PC highlight, and breakpoint markers (0-based lines)."""

    set_pc_requested = Signal(int)
    break_toggled = Signal(int, bool)  # line, enabled

    def __init__(self, parent=None):
        super().__init__(parent)

        self._lines: list[str] = []
        self._pc = 0
        self._path = ""
        self._breakpoints: set[int] = set()
        self._pc_bg = QBrush(QColor(255, 240, 160))
        self._bp_bg = QBrush(QColor(255, 220, 220))

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
        self.bp_label = QLabel("BP: 0")
        header.addWidget(self.bp_label)
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

        hint = QLabel(
            "Double-click: Set PC  ·  F9: toggle breakpoint  ·  ▶ PC  ·  ● break"
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(hint)

        # F9 when list has focus
        sc = QShortcut(QKeySequence("F9"), self.list)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.toggle_break_selected)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def path(self) -> str:
        return self._path

    def lines(self) -> list[str]:
        return list(self._lines)

    def line_count(self) -> int:
        return len(self._lines)

    def current_pc(self) -> int:
        return self._pc

    def selected_line(self) -> int:
        row = self.list.currentRow()
        return row if row >= 0 else self._pc

    def get_breakpoints(self) -> set[int]:
        return set(self._breakpoints)

    def clear(self):
        self._lines = []
        self._path = ""
        self._pc = 0
        self._breakpoints.clear()
        self.list.clear()
        self.title_label.setText("G-code: (none)")
        self.pc_label.setText("PC: 0")
        self.bp_label.setText("BP: 0")

    def load_lines(self, path: str, lines: list[str]):
        self._path = path or ""
        self._lines = list(lines)
        self._breakpoints.clear()
        self.list.clear()

        for i, raw in enumerate(self._lines):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(item)
            self._paint_row(i)

        base = path.rsplit("/", 1)[-1] if path else "(memory)"
        n = len(self._lines)
        self.title_label.setText(f"G-code: {base}  ({n} lines)")
        self.bp_label.setText("BP: 0")
        self.set_pc(0, scroll=True)

    def load_file(self, path: str) -> int:
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
            self._paint_row(old)
        if 0 <= pc < self.list.count():
            self._paint_row(pc)
            if scroll:
                self.list.setCurrentRow(pc)
                item = self.list.item(pc)
                if item is not None:
                    self.list.scrollToItem(
                        item, QListWidget.ScrollHint.PositionAtCenter
                    )

    def goto_pc(self):
        self.set_pc(self._pc, scroll=True)

    def toggle_breakpoint(self, line: int) -> bool:
        """Toggle break at line; return True if now enabled."""
        n = len(self._lines)
        if n == 0:
            return False
        line = max(0, min(int(line), n - 1))
        if line in self._breakpoints:
            self._breakpoints.discard(line)
            enabled = False
        else:
            self._breakpoints.add(line)
            enabled = True
        self._paint_row(line)
        self.bp_label.setText(f"BP: {len(self._breakpoints)}")
        self.break_toggled.emit(line, enabled)
        return enabled

    @Slot()
    def toggle_break_selected(self):
        self.toggle_breakpoint(self.selected_line())

    def clear_breakpoints(self):
        old = set(self._breakpoints)
        self._breakpoints.clear()
        for line in old:
            if 0 <= line < self.list.count():
                self._paint_row(line)
        self.bp_label.setText("BP: 0")

    def set_breakpoints(self, breakpoints) -> None:
        """Replace breakpoint set (e.g. sync from remote)."""
        old = set(self._breakpoints)
        self._breakpoints = set(int(x) for x in (breakpoints or set()))
        for line in old | self._breakpoints:
            if 0 <= line < self.list.count():
                self._paint_row(line)
        self.bp_label.setText(f"BP: {len(self._breakpoints)}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _paint_row(self, row: int):
        item = self.list.item(row)
        if item is None or row >= len(self._lines):
            return
        raw = self._lines[row].rstrip("\r\n")
        width = max(3, len(str(max(len(self._lines), 1))))
        bp = "●" if row in self._breakpoints else " "
        pc = "▶" if row == self._pc else " "
        item.setText(f"{bp}{pc}{row + 1:>{width}} | {raw}")

        if row == self._pc:
            item.setBackground(self._pc_bg)
        elif row in self._breakpoints:
            item.setBackground(self._bp_bg)
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
