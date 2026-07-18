"""PySide6 workbench client for gsat.

Thin desktop shell over the existing machine/server core — not a second CNC stack.
"""

__all__ = ["run_app"]


def run_app(cmd_line_options):
    from modules.pyside_workbench.app import run_app as _run_app
    return _run_app(cmd_line_options)
