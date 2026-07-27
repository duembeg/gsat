"""----------------------------------------------------------------------------
    numeric_entry_dialog.py

    Qt equivalent of classic gsatNumericEntryDialog: caption + float field,
    OK enabled only when the text is a valid number.
----------------------------------------------------------------------------"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class NumericEntryDialog(QDialog):
    def __init__(self, parent=None, title: str = "", caption: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title or "Numeric entry")
        self.setModal(True)
        self.resize(280, 140)

        root = QVBoxLayout(self)
        self._caption = QLabel(caption)
        self._caption.setWordWrap(True)
        root.addWidget(self._caption)

        self._entry = QLineEdit()
        self._entry.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._entry.setClearButtonEnabled(True)
        self._entry.returnPressed.connect(self._try_accept)
        self._entry.textChanged.connect(self._on_text)
        root.addWidget(self._entry)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok.setEnabled(False)
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._entry.setFocus()

    def _on_text(self, _text: str = "") -> None:
        try:
            float(self._entry.text().strip())
            self._ok.setEnabled(True)
        except ValueError:
            self._ok.setEnabled(False)

    def _try_accept(self) -> None:
        if self._ok.isEnabled():
            self.accept()

    def value(self) -> float:
        return float(self._entry.text().strip())

    def set_initial(self, text: str) -> None:
        self._entry.setText(str(text))
        self._entry.selectAll()
        self._on_text()
