"""----------------------------------------------------------------------------
    app.py

    QApplication bootstrap for the gsat PySide workbench.
----------------------------------------------------------------------------"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from modules.pyside_workbench.main_window import MainWindow
from modules.pyside_workbench.theme import apply_app_theme


def run_app(cmd_line_options) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("gsat-pyside")
    app.setOrganizationName("gsat")
    apply_app_theme(app)

    window = MainWindow(cmd_line_options)
    window.show()

    return app.exec()
