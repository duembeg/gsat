#!/usr/bin/env python
"""----------------------------------------------------------------------------
    pyside_dev_loop.py

    Dev harness for the PySide workbench spike:
      1. Open the UI
      2. Remote-connect (host/port from config or CLI)
      3. Open machine
      4. Tiny relative jog + reverse (proves event path)

    Usage (from repo root, with a venv that has PySide6):

      python tools/pyside_dev_loop.py
      python tools/pyside_dev_loop.py --host river --port 61803 --jog 0.1
      python tools/pyside_dev_loop.py --no-jog   # connect/open only
----------------------------------------------------------------------------"""
from __future__ import annotations

import argparse
import os
import sys

# Repo root on path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import modules.config as gc
import modules.pyside_workbench as pyside_workbench  # noqa: F401 — package
from modules.pyside_workbench.main_window import MainWindow


def parse_args():
    p = argparse.ArgumentParser(description="PySide workbench dev loop")
    p.add_argument("--host", default=None, help="Remote host (default: config)")
    p.add_argument("--port", type=int, default=None, help="WS port (default: config)")
    p.add_argument(
        "--jog",
        type=float,
        default=0.1,
        help="Relative X jog distance (mm); 0 disables jog",
    )
    p.add_argument("--feed", type=float, default=500.0, help="Jog feed rate")
    p.add_argument("--axis", default="x", choices=list("xyzabc"), help="Jog axis")
    p.add_argument("--no-jog", action="store_true", help="Skip jog steps")
    p.add_argument("--no-open", action="store_true", help="Skip machine open")
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose (default on for dev)",
    )
    return p.parse_args()


def main():
    args = parse_args()

    class Opts:
        verbose = True
        vverbose = False
        verbose_mask = 0
        server = False
        config = None

    opts = Opts()
    if args.verbose:
        opts.verbose = True

    config_fname = os.path.abspath(os.path.expanduser("~/.gsat.json"))
    gc.init_config(opts, config_fname, "log_file_pyside_dev")

    idx = gc.CONFIG_DATA.get("/remotes/Index", 0)
    host = args.host or gc.CONFIG_DATA.get(f"/remotes/remote{idx}/Host", "localhost")
    port = args.port or int(
        gc.CONFIG_DATA.get(f"/remotes/remote{idx}/WebSocketPort", 61803)
    )

    app = QApplication(sys.argv)
    app.setApplicationName("gsat-pyside-dev")

    win = MainWindow(opts)
    win.host_edit.setText(str(host))
    win.port_edit.setText(str(port))
    win.setWindowTitle(win.windowTitle() + " [dev-loop]")
    win.show()
    win.append_log(f"[dev-loop] host={host} port={port}")

    axis = args.axis.lower()
    dist = 0.0 if args.no_jog else float(args.jog)
    feed = float(args.feed)

    def connect():
        win.append_log("[dev-loop] Connect remote …")
        win.on_connect_remote()

    def open_machine():
        if args.no_open:
            win.append_log("[dev-loop] skip machine open")
            return
        win.append_log("[dev-loop] Open machine …")
        win.on_open_machine()

    def jog_out():
        if dist == 0:
            win.append_log("[dev-loop] skip jog")
            return
        if not win.bridge.is_backend_active():
            win.append_log("[dev-loop] no backend — skip jog")
            return
        payload = {axis: f"{dist:.3f}", "feed": feed}
        win.append_log(f"[dev-loop] jog +{axis} {payload}")
        win.bridge.send_command(gc.EV_CMD_JOG_MOVE_RELATIVE, payload)

    def jog_back():
        if dist == 0:
            return
        if not win.bridge.is_backend_active():
            return
        payload = {axis: f"{-dist:.3f}", "feed": feed}
        win.append_log(f"[dev-loop] jog -{axis} {payload}")
        win.bridge.send_command(gc.EV_CMD_JOG_MOVE_RELATIVE, payload)

    def refresh():
        win.append_log("[dev-loop] Refresh status")
        win.on_refresh_status()

    # Staggered sequence (UI stays open for manual poke afterward)
    QTimer.singleShot(400, connect)
    QTimer.singleShot(2000, open_machine)
    QTimer.singleShot(3500, refresh)
    QTimer.singleShot(4500, jog_out)
    QTimer.singleShot(7000, jog_back)
    QTimer.singleShot(8500, refresh)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
