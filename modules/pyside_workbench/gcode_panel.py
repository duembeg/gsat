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
    QPalette,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QShortcut,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import modules.config as gc

from modules.pyside_workbench.gcode_highlighter import GcodeHighlighter

# Cap all-match highlights so huge NGC files stay snappy
_FIND_HIGHLIGHT_MAX = 400


class _LineNumberArea(QWidget):
    """Gutter widget: line numbers + BP/PC strips (must handle its own clicks)."""

    def __init__(self, editor: "_GcodeEdit"):
        super().__init__(editor)
        self._editor = editor
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint(event)

    def mousePressEvent(self, event):
        # Clicks land here (not on the QPlainTextEdit) — toggle BP only in BP strip
        if event.button() == Qt.MouseButton.LeftButton:
            if self._editor.handle_gutter_click(event.position().toPoint()):
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Ignore double-click on gutter (wx toggles break on single margin click)
        event.accept()


class _GcodeEdit(QPlainTextEdit):
    """Editor core with line numbers, BP margin click, double-click set PC."""

    set_pc_requested = Signal(int)
    break_toggle_requested = Signal(int)

    # Match wx.stc margin order: line# | breakpoint | PC  (no drawn separators)
    MARGIN_BP = 16
    MARGIN_PC = 16
    # Minimum digit columns so 1000+ line files fit (grows with blockCount)
    MIN_LINE_DIGITS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        # Prefer Expanding so the center can fill, but with a small sizeHint so the
        # bottom Console dock is free to take most of the window height.
        sp = self.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        sp.setVerticalPolicy(QSizePolicy.Policy.Expanding)
        self.setSizePolicy(sp)

        self._line_number_area = _LineNumberArea(self)
        self._breakpoints: set[int] = set()
        self._pc = 0
        self._gutter_bg = QColor("#F0F0F0")
        self._gutter_fg = QColor("#606060")
        self._pc_color = QColor("#FFF0A0")
        self._bp_color = QColor("#FFCCCC")
        self._show_line_numbers = True
        self._show_caret_line = True
        # Find/replace ExtraSelections (merged after PC/BP/caret)
        self._find_selections: list = []

        get = (
            (lambda k, d=None: gc.CONFIG_DATA.get(k, d))
            if gc.CONFIG_DATA
            else (lambda k, d=None: d)
        )
        self._highlighter = GcodeHighlighter(self.document(), config_get=get)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_extras)

        self.apply_settings()
        self._update_line_number_area_width(0)
        self._highlight_current_extras()

    def apply_settings(self) -> None:
        """Apply /code/* font, colors, gutter, syntax (init + Settings OK)."""
        get = (
            (lambda k, d=None: gc.CONFIG_DATA.get(k, d))
            if gc.CONFIG_DATA
            else (lambda k, d=None: d)
        )

        face = str(get("/code/FontFace", "Monospace") or "Monospace")
        if face == "System":
            face = "Monospace"
        try:
            size = int(get("/code/FontSize", 10) or 10)
        except (TypeError, ValueError):
            size = 10
        if size <= 0:
            size = 10
        style = str(get("/code/FontStyle", "normal") or "normal").lower()
        font = QFont(face)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        font.setPointSize(size)
        font.setBold("bold" in style)
        font.setItalic("italic" in style)
        self.setFont(font)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))

        bg = str(get("/code/WindowBackground", "#FFFFFF") or "#FFFFFF")
        fg = str(get("/code/WindowForeground", "#000000") or "#000000")
        # Palette + stylesheet: QSS alone can lose to app Fusion palette
        self.setObjectName("gcodeEdit")
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(bg))
        pal.setColor(self.foregroundRole(), QColor(fg))
        pal.setColor(QPalette.ColorRole.Base, QColor(bg))
        pal.setColor(QPalette.ColorRole.Text, QColor(fg))
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            f"QPlainTextEdit#gcodeEdit {{"
            f" background-color: {bg}; color: {fg};"
            f" border: 1px solid #D0D5DD; border-radius: 4px; padding: 2px;"
            f"}}"
        )
        self.setReadOnly(bool(get("/code/ReadOnly", False)))

        self._gutter_bg = QColor(
            str(get("/code/LineNumberBackground", "#F0F0F0") or "#F0F0F0")
        )
        self._gutter_fg = QColor(
            str(get("/code/LineNumberForeground", "#606060") or "#606060")
        )
        self._pc_color = QColor(
            str(get("/code/CaretLineBackground", "#FFF0A0") or "#FFF0A0")
        )
        self._show_line_numbers = bool(get("/code/LineNumber", True))
        self._show_caret_line = bool(get("/code/CaretLine", True))

        if self._highlighter is not None:
            self._highlighter.apply_config(get)
        self._line_number_area.update()
        self._highlight_current_extras()
        self._update_line_number_area_width(0)

    # --- line numbers + marker strips (wx order: line# | BP | PC) ---
    def _line_number_column_width(self) -> int:
        n = max(1, self.blockCount())
        digits = max(self.MIN_LINE_DIGITS, len(str(n)))
        char_w = max(self.fontMetrics().horizontalAdvance("9"), 8)
        return 6 + char_w * digits + 8

    def _bp_strip_left(self) -> int:
        return self._line_number_column_width()

    def _pc_strip_left(self) -> int:
        return self._line_number_column_width() + self.MARGIN_BP

    def line_number_area_width(self) -> int:
        """line# | BP | PC — same order as wx.stc margins 0/1/2."""
        return self._line_number_column_width() + self.MARGIN_BP + self.MARGIN_PC

    def _update_line_number_area_width(self, _=None):
        w = self.line_number_area_width()
        self.setViewportMargins(w, 0, 0, 0)
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

    def minimumSizeHint(self) -> QSize:
        # Qt default is ~70×70; allow shrinking further for a large console dock
        return QSize(80, 40)

    def sizeHint(self) -> QSize:
        # Prefer short/narrow center — typical G-code lines are not wide;
        # console under center should claim more vertical space.
        return QSize(160, 80)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint(self, event):
        painter = QPainter(self._line_number_area)
        # Flat gutter like wx (no separator lines between strips)
        painter.fillRect(event.rect(), self._gutter_bg)

        # wx STC_STYLE_LINENUMBER uses bold; keep gutter digits consistent every row
        # (do not setFont only when drawing ▶ — that left PC-row digits looking thinner)
        font_ln = QFont(self.font())
        font_ln.setBold(True)
        font_pc = QFont(self.font())
        font_pc.setBold(True)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())
        row_h = self.fontMetrics().height()
        ln_w = self._line_number_column_width()
        bp_left = self._bp_strip_left()
        pc_left = self._pc_strip_left()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                cy = top + row_h // 2
                is_pc = block_number == self._pc

                # 1) Line number (left, right-aligned in its column)
                if self._show_line_numbers:
                    number = str(block_number + 1)
                    painter.setFont(font_ln)
                    painter.setPen(self._gutter_fg)
                    painter.drawText(
                        2,
                        top,
                        ln_w - 4,
                        row_h,
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        number,
                    )

                # 2) Breakpoint strip (middle) — clickable via handle_gutter_click
                if block_number in self._breakpoints:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor("#CC0000"))
                    r = 5
                    cx = bp_left + self.MARGIN_BP // 2
                    painter.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)

                # 3) PC strip (right of BP, before code)
                if is_pc:
                    painter.setPen(QColor("#008800"))
                    painter.setFont(font_pc)
                    painter.drawText(
                        pc_left,
                        top,
                        self.MARGIN_PC,
                        row_h,
                        Qt.AlignmentFlag.AlignCenter,
                        "▶",
                    )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def handle_gutter_click(self, pos) -> bool:
        """Map a click in the gutter widget; toggle BP only if in BP strip.

        Returns True if the click was consumed.
        """
        x = pos.x()
        y = pos.y()
        bp_left = self._bp_strip_left()
        bp_right = bp_left + self.MARGIN_BP
        if not (bp_left <= x < bp_right):
            return False

        block = self.firstVisibleBlock()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        while block.isValid():
            bottom = top + int(self.blockBoundingRect(block).height())
            if top <= y < bottom:
                self.break_toggle_requested.emit(block.blockNumber())
                return True
            block = block.next()
            top = bottom
        return False

    def mouseDoubleClickEvent(self, event):
        # Double-click in text viewport → set PC
        self.set_pc_requested.emit(self.textCursor().blockNumber())
        # Prefer line under mouse
        cursor = self.cursorForPosition(event.position().toPoint())
        self.set_pc_requested.emit(cursor.blockNumber())
        event.accept()

    def set_breakpoints(self, bps: set[int]):
        self._breakpoints = set(bps)
        self._line_number_area.update()
        self._highlight_current_extras()

    def set_pc_line(self, pc: int):
        self._pc = pc
        self._line_number_area.update()
        self._highlight_current_extras()

    def set_find_selections(self, selections: list) -> None:
        """Find-match highlights (merged into PC/BP/caret extras)."""
        self._find_selections = list(selections or [])
        self._highlight_current_extras()

    def clear_find_selections(self) -> None:
        if self._find_selections:
            self._find_selections = []
            self._highlight_current_extras()

    def _highlight_current_extras(self):
        extras = []

        # Caret line (wx CaretLine) — under PC/BP
        if self._show_caret_line:
            cur_line = self.textCursor().blockNumber()
            if 0 <= cur_line < self.blockCount() and cur_line != self._pc:
                sel = QTextEdit.ExtraSelection()
                # Slightly weaker than PC highlight
                caret_bg = QColor(self._pc_color)
                caret_bg.setAlpha(80)
                sel.format.setBackground(caret_bg)
                sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                sel.cursor = self.textCursor()
                extras.append(sel)

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

        # Find matches last so current hit stays readable over line paints
        extras.extend(self._find_selections)

        self.setExtraSelections(extras)


class _FindReplaceBar(QWidget):
    """VS Code–style find/replace strip (not a main-window toolbar)."""

    closed = Signal()

    def __init__(self, panel: "GcodePanel", parent=None):
        super().__init__(parent)
        self._panel = panel
        self._replace_mode = False
        self._match_count = 0
        self._match_index = 0  # 1-based when matches exist
        self.setObjectName("gcodeFindBar")
        self.setVisible(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.returnPressed.connect(lambda: self.find_next(wrap=True))
        self.find_edit.textChanged.connect(self._on_query_changed)
        row1.addWidget(self.find_edit, 1)

        self.btn_prev = QPushButton("▲")
        self.btn_prev.setFixedWidth(28)
        self.btn_prev.setToolTip("Previous match — Shift+F3")
        self.btn_prev.clicked.connect(lambda: self.find_prev(wrap=True))
        row1.addWidget(self.btn_prev)

        self.btn_next = QPushButton("▼")
        self.btn_next.setFixedWidth(28)
        self.btn_next.setToolTip("Next match — F3")
        self.btn_next.clicked.connect(lambda: self.find_next(wrap=True))
        row1.addWidget(self.btn_next)

        self.cb_case = QCheckBox("Match case")
        self.cb_case.toggled.connect(self._on_query_changed)
        row1.addWidget(self.cb_case)

        self.count_label = QLabel("")
        self.count_label.setMinimumWidth(72)
        self.count_label.setStyleSheet("color: #5C6570;")
        row1.addWidget(self.count_label)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedWidth(28)
        self.btn_close.setToolTip("Close (Esc)")
        self.btn_close.setObjectName("findBarClose")
        self.btn_close.clicked.connect(self.hide_bar)
        row1.addWidget(self.btn_close)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace")
        self.replace_edit.returnPressed.connect(self.replace_one)
        row2.addWidget(self.replace_edit, 1)
        self.btn_replace = QPushButton("Replace")
        self.btn_replace.clicked.connect(self.replace_one)
        row2.addWidget(self.btn_replace)
        self.btn_replace_all = QPushButton("Replace all")
        self.btn_replace_all.clicked.connect(self.replace_all)
        row2.addWidget(self.btn_replace_all)
        root.addLayout(row2)
        self._replace_row = row2
        self._set_replace_visible(False)

        # Esc on the bar
        sc_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        sc_esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_esc.activated.connect(self.hide_bar)

    def _set_replace_visible(self, on: bool) -> None:
        self._replace_mode = on
        self.replace_edit.setVisible(on)
        self.btn_replace.setVisible(on)
        self.btn_replace_all.setVisible(on)

    def open_bar(self, *, replace: bool = False, seed: str = "") -> None:
        self._set_replace_visible(replace)
        self.setVisible(True)
        if seed:
            self.find_edit.setText(seed)
            self.find_edit.selectAll()
        elif not self.find_edit.text():
            # Seed from current editor selection (single line)
            ed = self._panel.editor
            cur = ed.textCursor()
            if cur.hasSelection():
                sel = cur.selectedText().replace("\u2029", "\n")
                if "\n" not in sel and sel:
                    self.find_edit.setText(sel)
                    self.find_edit.selectAll()
        self.find_edit.setFocus()
        self.find_edit.selectAll()
        self._refresh_highlights(move_to_match=False)

    def hide_bar(self) -> None:
        self.setVisible(False)
        self._panel.editor.clear_find_selections()
        self.count_label.setText("")
        self._panel.editor.setFocus()
        self.closed.emit()

    def is_open(self) -> bool:
        return self.isVisible()

    def _find_flags(self, *, backward: bool = False) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if self.cb_case.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def _on_query_changed(self, *_args) -> None:
        self._refresh_highlights(move_to_match=True)

    def _all_match_cursors(self) -> list[QTextCursor]:
        query = self.find_edit.text()
        if not query:
            return []
        doc = self._panel.editor.document()
        flags = self._find_flags()
        out: list[QTextCursor] = []
        c = doc.find(query, 0, flags)
        while not c.isNull() and len(out) < _FIND_HIGHLIGHT_MAX:
            out.append(c)
            c = doc.find(query, c, flags)
        return out

    def _refresh_highlights(self, *, move_to_match: bool) -> None:
        query = self.find_edit.text()
        matches = self._all_match_cursors() if query else []
        self._match_count = len(matches)

        extras = []
        current_pos = self._panel.editor.textCursor().position()
        current_bg = QColor("#F59E0B")  # current hit
        other_bg = QColor("#FDE68A")  # other hits

        self._match_index = 0
        for i, c in enumerate(matches):
            sel = QTextEdit.ExtraSelection()
            is_cur = c.selectionStart() <= current_pos <= c.selectionEnd()
            if is_cur and self._match_index == 0:
                self._match_index = i + 1
            sel.format.setBackground(current_bg if is_cur else other_bg)
            sel.cursor = c
            extras.append(sel)

        # If no cursor-on-match, still paint first as "other"
        if matches and self._match_index == 0:
            # Prefer first match after cursor for count display after move
            self._match_index = 0

        self._panel.editor.set_find_selections(extras)

        if not query:
            self.count_label.setText("")
            self.count_label.setStyleSheet("color: #5C6570;")
            return

        if self._match_count == 0:
            self.count_label.setText("No results")
            self.count_label.setStyleSheet("color: #B91C1C;")
            if move_to_match:
                pass
            return

        # Cap note
        label_n = self._match_count
        more = "+" if label_n >= _FIND_HIGHLIGHT_MAX else ""
        if self._match_index > 0:
            self.count_label.setText(f"{self._match_index} of {label_n}{more}")
        else:
            self.count_label.setText(f"{label_n}{more} matches")
        self.count_label.setStyleSheet("color: #5C6570;")

        if move_to_match and matches:
            # Jump to first match at/after caret without wrapping preference
            self.find_next(wrap=True, from_refresh=True)

    def find_next(self, *, wrap: bool = True, from_refresh: bool = False) -> bool:
        return self._find_step(backward=False, wrap=wrap)

    def find_prev(self, *, wrap: bool = True) -> bool:
        return self._find_step(backward=True, wrap=wrap)

    def _find_step(self, *, backward: bool, wrap: bool) -> bool:
        query = self.find_edit.text()
        if not query:
            return False
        ed = self._panel.editor
        doc = ed.document()
        flags = self._find_flags(backward=backward)
        start = ed.textCursor()
        found = doc.find(query, start, flags)
        if found.isNull() and wrap:
            # wrap: from start or end of document
            if backward:
                end_c = QTextCursor(doc)
                end_c.movePosition(QTextCursor.MoveOperation.End)
                found = doc.find(query, end_c, flags)
            else:
                found = doc.find(query, 0, flags)
        if found.isNull():
            self._refresh_highlights(move_to_match=False)
            self.count_label.setText("No results")
            self.count_label.setStyleSheet("color: #B91C1C;")
            return False

        self._panel._ignore_caret_for_follow = True
        try:
            ed.setTextCursor(found)
            ed.centerCursor()
        finally:
            self._panel._ignore_caret_for_follow = False

        # Rebuild highlights so current hit colors correctly
        matches = self._all_match_cursors()
        self._match_count = len(matches)
        pos = found.selectionStart()
        extras = []
        self._match_index = 0
        for i, c in enumerate(matches):
            sel = QTextEdit.ExtraSelection()
            is_cur = c.selectionStart() == pos
            if is_cur:
                self._match_index = i + 1
            sel.format.setBackground(
                QColor("#F59E0B") if is_cur else QColor("#FDE68A")
            )
            sel.cursor = c
            extras.append(sel)
        ed.set_find_selections(extras)
        more = "+" if self._match_count >= _FIND_HIGHLIGHT_MAX else ""
        if self._match_index:
            self.count_label.setText(f"{self._match_index} of {self._match_count}{more}")
        else:
            self.count_label.setText(f"{self._match_count}{more} matches")
        self.count_label.setStyleSheet("color: #5C6570;")
        return True

    def replace_one(self) -> None:
        query = self.find_edit.text()
        if not query:
            return
        ed = self._panel.editor
        cur = ed.textCursor()
        selected = cur.selectedText().replace("\u2029", "\n")
        if self.cb_case.isChecked():
            matches = selected == query
        else:
            matches = selected.lower() == query.lower()
        if matches and selected:
            cur.insertText(self.replace_edit.text())
        self.find_next(wrap=True)

    def replace_all(self) -> None:
        query = self.find_edit.text()
        if not query:
            return
        repl = self.replace_edit.text()
        ed = self._panel.editor
        doc = ed.document()
        flags = self._find_flags()
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        n = 0
        # Safety cap: empty/odd queries must not loop forever
        c = doc.find(query, 0, flags)
        while not c.isNull() and n < 100_000:
            c.insertText(repl)
            n += 1
            c = doc.find(query, c.position(), flags)
        cursor.endEditBlock()
        self._refresh_highlights(move_to_match=False)
        self.count_label.setText(f"Replaced {n}" if n else "No results")
        self.count_label.setStyleSheet(
            "color: #5C6570;" if n else "color: #B91C1C;"
        )


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

        # Allow the center pane to collapse vertically (console dock expand)
        sp = self.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        sp.setVerticalPolicy(QSizePolicy.Policy.Expanding)
        self.setSizePolicy(sp)

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

        # Find/replace: under header, above editor (VS Code–style in-panel)
        self.find_bar = _FindReplaceBar(self)
        root.addWidget(self.find_bar)

        self.editor = _GcodeEdit()
        self.editor.set_pc_requested.connect(self.set_pc_requested.emit)
        self.editor.break_toggle_requested.connect(self.toggle_breakpoint)
        # wx AutoScroll: user caret move stops follow for modes On Kill Focus / On Goto PC
        self.editor.cursorPositionChanged.connect(self._on_editor_caret_changed)
        self.editor.installEventFilter(self)
        root.addWidget(self.editor, 1)

        # Keep attribute name used by older smoke tests / callers
        self.list = self  # proxy selected_line helpers if needed

        # Word-wrap so this footer does not force a ~500px min width on the panel
        hint = QLabel(
            "Gutter: line# | ● break | ▶ PC  ·  F9 break  ·  "
            "Ctrl+F find  ·  F3/Shift+F3 next/prev  ·  Ctrl+H replace"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(hint)

        sc = QShortcut(QKeySequence("F9"), self.editor)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.toggle_break_selected)

        # /code/AutoScroll: 0 Never, 1 Always, 2 On Kill Focus, 3 On Goto PC
        self._auto_scroll_mode = 3
        self._follow_pc = True
        self._ignore_caret_for_follow = False
        self.reload_auto_scroll_setting()

    # ------------------------------------------------------------------
    # Find / replace (Edit menu + shortcuts)
    # ------------------------------------------------------------------
    def show_find(self, *, replace: bool = False) -> None:
        """Open in-panel find (or replace) bar — browser/VS Code style."""
        self.find_bar.open_bar(replace=replace)

    def find_next(self) -> None:
        if not self.find_bar.is_open():
            self.show_find(replace=False)
            return
        self.find_bar.find_next(wrap=True)

    def find_prev(self) -> None:
        if not self.find_bar.is_open():
            self.show_find(replace=False)
            return
        self.find_bar.find_prev(wrap=True)

    def hide_find(self) -> None:
        if self.find_bar.is_open():
            self.find_bar.hide_bar()

    def minimumSizeHint(self) -> QSize:
        # header + short editor + wrapped hint — keep low so console can dominate
        return QSize(100, 64)

    def sizeHint(self) -> QSize:
        # Soft preference only: narrow/short so factory layout favors console + right column
        return QSize(160, 120)

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
        self.editor.clear_find_selections()
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
        self.editor.clear_find_selections()
        if self.find_bar.is_open():
            self.find_bar._refresh_highlights(move_to_match=False)
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

    def document_text(self) -> str:
        return self.editor.toPlainText()

    def save_file(self, path: str) -> int:
        """Write editor contents to path; resync internal lines. Returns line count."""
        text = self.editor.toPlainText()
        # Preserve trailing newline if content is non-empty
        if text and not text.endswith("\n"):
            text = text + "\n"
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        self._path = path
        self._lines = text.splitlines(True)
        base = path.rsplit("/", 1)[-1]
        self.title_label.setText(f"G-code: {base}  ({len(self._lines)} lines)")
        return len(self._lines)

    def reload_auto_scroll_setting(self) -> None:
        """Load /code/AutoScroll from config (call after Settings OK)."""
        mode = 3
        if gc.CONFIG_DATA is not None:
            try:
                raw = gc.CONFIG_DATA.get("/code/AutoScroll", 3)
                # careful: 0 is valid (Never) — do not use `or 3`
                mode = 3 if raw is None else int(raw)
            except (TypeError, ValueError):
                mode = 3
        self._auto_scroll_mode = max(0, min(3, mode))
        # wx InitConfig: modes 1–3 start with follow enabled
        self._follow_pc = self._auto_scroll_mode in (1, 2, 3)

    def update_settings(self) -> None:
        """wx Gcode.UpdateSettings: re-read /code/* and restyle editor."""
        self.reload_auto_scroll_setting()
        self.editor.apply_settings()

    def _should_scroll_on_pc_update(self) -> bool:
        """Whether PC marker moves should keep the PC line in view (wx UpdatePC)."""
        if self._auto_scroll_mode == 0:
            return False
        if self._auto_scroll_mode == 1:
            return True
        # 2 On Kill Focus / 3 On Goto PC: follow until user moves caret
        return bool(self._follow_pc)

    def _scroll_to_pc(self) -> None:
        """Bring PC line into view without treating it as a user caret move."""
        self._ignore_caret_for_follow = True
        try:
            block = self.editor.document().findBlockByNumber(self._pc)
            cursor = QTextCursor(block)
            self.editor.setTextCursor(cursor)
            self.editor.centerCursor()
        finally:
            self._ignore_caret_for_follow = False

    def _on_editor_caret_changed(self) -> None:
        # wx CaretChange: for modes >= 2, user navigation cancels auto-follow
        if self._ignore_caret_for_follow:
            return
        if self._auto_scroll_mode >= 2:
            self._follow_pc = False

    def eventFilter(self, obj, event):
        # wx OnKill Focus: mode 2 re-enables follow when leaving the editor
        from PySide6.QtCore import QEvent

        if obj is self.editor and event.type() == QEvent.Type.FocusOut:
            if self._auto_scroll_mode == 2:
                self._follow_pc = True
        return super().eventFilter(obj, event)

    @Slot(int)
    def set_pc(self, pc: int, scroll: bool | None = None):
        """Update PC marker.

        ``scroll``:
          * ``None`` — use AutoScroll policy (default for backend PC updates)
          * ``True`` / ``False`` — force
        """
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
        do_scroll = self._should_scroll_on_pc_update() if scroll is None else bool(scroll)
        if do_scroll:
            self._scroll_to_pc()

    def goto_pc(self):
        """wx GoToPC: always jump to PC; mode 3 re-enables follow-the-PC."""
        if self._auto_scroll_mode == 3:
            self._follow_pc = True
        # Explicit user Goto PC always scrolls (wx always GotoLine)
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
