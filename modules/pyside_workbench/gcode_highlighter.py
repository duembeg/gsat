"""----------------------------------------------------------------------------
    gcode_highlighter.py

    G-code syntax highlighting rules ported from wx.stc container lexer
    (modules/wnd_gcode.py onStyleNeeded). Used with QSyntaxHighlighter under
    pure PySide6 (QScintilla pip is PyQt-only and clashes with PySide6).
----------------------------------------------------------------------------"""
from __future__ import annotations

import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


def _fmt(color: str, bold: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    return f


class GcodeHighlighter(QSyntaxHighlighter):
    """Regex styles matching classic gsat wx Scintilla container styling."""

    # Defaults similar to typical gsat config highlight colors
    def __init__(self, document, config_get=None):
        super().__init__(document)
        # Same patterns as wnd_gcode.py
        self.re_gcode = re.compile(r"[G]\d+\.?\d*", re.IGNORECASE)
        self.re_mcode = re.compile(r"[M]\d+\.?\d*", re.IGNORECASE)
        self.re_axis = re.compile(
            r"([ABCIJKUVWXYZ])(\s*[-+]?\d+\.?\d*)", re.IGNORECASE
        )
        self.re_params = re.compile(
            r"([DEFHLOPQRST])(\s*[-+]?\d+\.?\d*)", re.IGNORECASE
        )
        self.re_params2 = re.compile(r"([EF])(\s*[-+]?\d+\.?\d*)", re.IGNORECASE)
        self.re_nline = re.compile(r"N\d+", re.IGNORECASE)
        self.re_comments = [
            re.compile(r"\(.*?\)"),
            re.compile(r";.*"),
        ]
        self.apply_config(config_get)

    def apply_config(self, config_get=None) -> None:
        """Reload highlight colors from config (init + after Settings)."""
        get = config_get or (lambda _k, d=None: d)
        self.fmt_default = _fmt(get("/code/WindowForeground", "#000000") or "#000000")
        self.fmt_gcode = _fmt(get("/code/GCodeHighlight", "#0000AA") or "#0000AA", bold=True)
        self.fmt_mcode = _fmt(get("/code/MCodeHighlight", "#AA00AA") or "#AA00AA", bold=True)
        self.fmt_axis = _fmt(get("/code/AxisHighlight", "#008800") or "#008800", bold=True)
        self.fmt_param = _fmt(get("/code/ParametersHighlight", "#888800") or "#888800")
        self.fmt_param2 = _fmt(get("/code/Parameters2Highlight", "#AA5500") or "#AA5500")
        self.fmt_nline = _fmt(get("/code/GCodeLineNumberHighlight", "#666666") or "#666666")
        self.fmt_comment = _fmt(get("/code/CommentsHighlight", "#808080") or "#808080")
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        # Default is inherited; apply token formats
        for m in self.re_gcode.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_gcode)
        for m in self.re_mcode.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_mcode)
        for m in self.re_nline.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_nline)
        for m in self.re_params.finditer(text):
            self.setFormat(m.start(1), m.end(1) - m.start(1), self.fmt_param)
        for m in self.re_params2.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_param2)
        for m in self.re_axis.finditer(text):
            self.setFormat(m.start(1), m.end(1) - m.start(1), self.fmt_axis)
        # Comments last so they override keywords inside ( … ) / ;
        for regex in self.re_comments:
            for m in regex.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), self.fmt_comment)
