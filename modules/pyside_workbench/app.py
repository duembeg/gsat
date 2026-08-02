"""----------------------------------------------------------------------------
    app.py

    QApplication bootstrap for the gsat PySide workbench.
----------------------------------------------------------------------------"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from modules.pyside_workbench import icons as wb_icons
from modules.pyside_workbench.main_window import MainWindow
from modules.pyside_workbench.theme import apply_app_theme


def run_app(cmd_line_options) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("gsat-pyside")
    app.setOrganizationName("gsat")
    apply_app_theme(app)
    # Title bar / taskbar (wx SetIcon never stuck reliably; Qt handles this well)
    wb_icons.apply_app_icon(app)

    window = MainWindow(cmd_line_options)
    # Also on the window — some WMs only pick up the window icon
    wb_icons.apply_app_icon(app, window)
    window.show()

    return app.exec()
