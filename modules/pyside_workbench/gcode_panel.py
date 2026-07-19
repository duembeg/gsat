"""----------------------------------------------------------------------------
    gcode_panel.py

    G-code view for the PySide workbench: syntax highlight, PC line, breakpoints.

    Note on QScintilla: the PyPI ``QScintilla`` / ``PyQt6-QScintilla`` wheels are
    **PyQt-only** and conflict with a PySide6 QApplication (Qt ABI mismatch).
    This panel uses pure PySide6 QPlainTextEdit + QSyntaxHighlighter with the
    **same regex rules** as wx.stc container lexer (modules/wnd_gcode.py).
    PC / breakpoint markers use ExtraSelections + a breakpoint margin.
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QTextCursor,
    QTextFormat,
    QShortcut,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import modules.config as gc

from modules.pyside_workbench.gcode_highlighter import GcodeHighlighter


class _LineNumberArea(QWidget):
    def __init__(self, editor: "_GcodeEdit"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint(event)


class _GcodeEdit(QPlainTextEdit):
    """Editor core with line numbers, BP margin click, double-click set PC."""

    set_pc_requested = Signal(int)
    break_toggle_requested = Signal(int)

    # Breakpoint / PC glyph strip (left of line numbers)
    MARGIN_BP = 20
    # Minimum digit columns so 1000+ line files fit (grows with blockCount)
    MIN_LINE_DIGITS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        mono.setPointSize(10)
        self.setFont(mono)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))

        self._line_number_area = _LineNumberArea(self)
        self._breakpoints: set[int] = set()
        self._pc = 0

        # Config colors (before signals that may paint)
        bg = (
            gc.CONFIG_DATA.get("/code/WindowBackground", "#FFFFFF")
            if gc.CONFIG_DATA
            else "#FFFFFF"
        )
        fg = (
            gc.CONFIG_DATA.get("/code/WindowForeground", "#000000")
            if gc.CONFIG_DATA
            else "#000000"
        )
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: {bg}; color: {fg}; }}"
        )

        get = (
            (lambda k, d=None: gc.CONFIG_DATA.get(k, d))
            if gc.CONFIG_DATA
            else (lambda k, d=None: d)
        )
        self._highlighter = GcodeHighlighter(self.document(), config_get=get)

        self._pc_color = QColor(
            get("/code/CaretLineBackground", "#FFF0A0") or "#FFF0A0"
        )
        self._bp_color = QColor("#FFCCCC")

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_extras)

        self._update_line_number_area_width(0)
        self._highlight_current_extras()

    # --- line numbers ---
    def line_number_area_width(self) -> int:
        """Width for BP/PC margin + full line numbers (supports 1000+ lines).

        AlignRight with a too-narrow box clips the *left* digits (10 → \"0\"),
        so size from digit count with comfortable padding.
        """
        n = max(1, self.blockCount())
        digits = max(self.MIN_LINE_DIGITS, len(str(n)))
        char_w = max(self.fontMetrics().horizontalAdvance("9"), 8)
        # BP strip | gap | digits | right pad before text
        return self.MARGIN_BP + 6 + char_w * digits + 10

    def _update_line_number_area_width(self, _=None):
        w = self.line_number_area_width()
        self.setViewportMargins(w, 0, 0, 0)
        # Keep margin widget geometry in sync when digit width jumps (9→10, 99→100)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), w, cr.height())
        )
        self._line_number_area.update()

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#F0F0F0"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                # Breakpoint glyph
                if block_number in self._breakpoints:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor("#CC0000"))
                    r = 5
                    cx = self.MARGIN_BP // 2
                    cy = top + self.fontMetrics().height() // 2
                    painter.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)

                # Line number (right-aligned in the digit column only)
                number = str(block_number + 1)
                painter.setPen(QColor("#606060"))
                num_left = self.MARGIN_BP + 4
                num_width = self._line_number_area.width() - num_left - 6
                painter.drawText(
                    num_left,
                    top,
                    max(num_width, 1),
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    number,
                )

                # PC arrow
                if block_number == self._pc:
                    painter.setPen(QColor("#008800"))
                    painter.setFont(self.font())
                    painter.drawText(
                        2,
                        top,
                        self.MARGIN_BP - 2,
                        self.fontMetrics().height(),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        "▶",
                    )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def mousePressEvent(self, event):
        # Click in BP margin → toggle breakpoint
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().x() < self.MARGIN_BP:
                # map y to block
                y = int(event.position().y())
                block = self.firstVisibleBlock()
                top = int(
                    self.blockBoundingGeometry(block)
                    .translated(self.contentOffset())
                    .top()
                )
                while block.isValid():
                    bottom = top + int(self.blockBoundingRect(block).height())
                    if top <= y < bottom:
                        self.break_toggle_requested.emit(block.blockNumber())
                        event.accept()
                        return
                    block = block.next()
                    top = bottom
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Double-click line body → set PC
        if event.position().x() >= self.MARGIN_BP:
            cursor = self.cursorForPosition(event.position().toPoint())
            self.set_pc_requested.emit(cursor.blockNumber())
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def set_breakpoints(self, bps: set[int]):
        self._breakpoints = set(bps)
        self._line_number_area.update()
        self._highlight_current_extras()

    def set_pc_line(self, pc: int):
        self._pc = pc
        self._line_number_area.update()
        self._highlight_current_extras()

    def _highlight_current_extras(self):
        extras = []

        # PC line
        if 0 <= self._pc < self.blockCount():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(self._pc_color)
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            cursor = QTextCursor(self.document().findBlockByNumber(self._pc))
            sel.cursor = cursor
            extras.append(sel)

        # Breakpoint lines (lighter red) if not PC
        for bp in self._breakpoints:
            if bp == self._pc or bp < 0 or bp >= self.blockCount():
                continue
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(self._bp_color)
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            cursor = QTextCursor(self.document().findBlockByNumber(bp))
            sel.cursor = cursor
            extras.append(sel)

        self.setExtraSelections(extras)


class GcodePanel(QWidget):
    """G-code panel: syntax highlight, PC, breakpoints (0-based lines)."""

    set_pc_requested = Signal(int)
    break_toggled = Signal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._lines: list[str] = []
        self._pc = 0
        self._path = ""
        self._breakpoints: set[int] = set()

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

        self.editor = _GcodeEdit()
        self.editor.set_pc_requested.connect(self.set_pc_requested.emit)
        self.editor.break_toggle_requested.connect(self.toggle_breakpoint)
        root.addWidget(self.editor, 1)

        # Keep attribute name used by older smoke tests / callers
        self.list = self  # proxy selected_line helpers if needed

        hint = QLabel(
            "Double-click line: Set PC  ·  Click left margin / F9: breakpoint  ·  "
            "Highlight = wx-style G/M/axis/comments"
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(hint)

        sc = QShortcut(QKeySequence("F9"), self.editor)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.toggle_break_selected)

    # ------------------------------------------------------------------
    # Public API (stable for main_window / smoke)
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
        return self.editor.textCursor().blockNumber()

    def get_breakpoints(self) -> set[int]:
        return set(self._breakpoints)

    def clear(self):
        self._lines = []
        self._path = ""
        self._pc = 0
        self._breakpoints.clear()
        self.editor.setPlainText("")
        self.editor.set_breakpoints(set())
        self.editor.set_pc_line(0)
        self.title_label.setText("G-code: (none)")
        self.pc_label.setText("PC: 0")
        self.bp_label.setText("BP: 0")

    def load_lines(self, path: str, lines: list[str]):
        self._path = path or ""
        self._lines = list(lines)
        self._breakpoints.clear()
        # Plain text without forcing extra trailing blank if file had none
        text = "".join(self._lines)
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)
        # Recalc gutter after blockCount is known (1000+ line files)
        self.editor._update_line_number_area_width()
        self.editor.set_breakpoints(set())
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
            self.editor.set_pc_line(0)
            return

        pc = max(0, min(int(pc), n - 1))
        self._pc = pc
        self.pc_label.setText(f"PC: {pc}  (line {pc + 1})")
        self.editor.set_pc_line(pc)
        if scroll:
            block = self.editor.document().findBlockByNumber(pc)
            cursor = QTextCursor(block)
            self.editor.setTextCursor(cursor)
            self.editor.centerCursor()

    def goto_pc(self):
        self.set_pc(self._pc, scroll=True)

    def toggle_breakpoint(self, line: int) -> bool:
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
        self.editor.set_breakpoints(self._breakpoints)
        self.bp_label.setText(f"BP: {len(self._breakpoints)}")
        self.break_toggled.emit(line, enabled)
        return enabled

    @Slot()
    def toggle_break_selected(self):
        self.toggle_breakpoint(self.selected_line())

    def clear_breakpoints(self):
        self._breakpoints.clear()
        self.editor.set_breakpoints(set())
        self.bp_label.setText("BP: 0")

    def set_breakpoints(self, breakpoints) -> None:
        self._breakpoints = set(int(x) for x in (breakpoints or set()))
        self.editor.set_breakpoints(self._breakpoints)
        self.bp_label.setText(f"BP: {len(self._breakpoints)}")

    # Compatibility shims used by smoke tests that poked the old list widget
    def item(self, row: int):
        return _RowProxy(self, row)

    def setCurrentRow(self, row: int):
        if 0 <= row < self.line_count():
            block = self.editor.document().findBlockByNumber(row)
            self.editor.setTextCursor(QTextCursor(block))

    def count(self) -> int:
        return self.line_count()


class _RowProxy:
    """Minimal stand-in for QListWidgetItem used in smoke assertions."""

    def __init__(self, panel: GcodePanel, row: int):
        self._panel = panel
        self._row = row

    def text(self) -> str:
        marks = ""
        if self._row in self._panel._breakpoints:
            marks += "●"
        if self._row == self._panel._pc:
            marks += "▶"
        if 0 <= self._row < len(self._panel._lines):
            body = self._panel._lines[self._row].rstrip("\r\n")
        else:
            body = ""
        return f"{marks}{self._row + 1} | {body}"
