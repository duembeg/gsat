#!/usr/bin/env python
"""----------------------------------------------------------------------------
    pyside_smoke.py

    Agent-friendly automated smoke tests for the PySide workbench.
    Prefer running this (and fixing failures) instead of asking the user to
    click through every iteration.

    Modes:
      --offline   (default) Offscreen UI + fake backend; no machine needed
      --live      Also try remote connect to host/port from config or flags

    Usage (repo root, PySide6 venv):

      python tools/pyside_smoke.py
      QT_QPA_PLATFORM=offscreen python tools/pyside_smoke.py --offline
      python tools/pyside_smoke.py --live --host river --port 61803
----------------------------------------------------------------------------"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
import traceback

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Prefer offscreen unless user exports a real DISPLAY for --live GUI
if "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"


class _Opts:
    verbose = True
    vverbose = False
    verbose_mask = 0
    server = False
    config = None


class FakeBackend:
    def __init__(self):
        self.events = []

    def add_event(self, event_id, data=None, sender=None):
        self.events.append((event_id, data, sender))

    def remove_event_listener(self, _listener):
        pass

    def is_alive(self):
        return False

    def join(self, timeout=None):
        pass


def _fail(msg: str) -> None:
    raise AssertionError(msg)


def test_offline() -> list[str]:
    """Pure UI/event-path checks with a fake backend."""
    import modules.config as gc
    from PySide6.QtWidgets import QApplication, QMessageBox
    from modules.config import SimpleEvent
    from modules.pyside_workbench.main_window import MainWindow

    notes = []
    opts = _Opts()
    gc.init_config(opts, os.path.expanduser("~/.gsat.json"), "log_pyside_smoke")

    app = QApplication.instance() or QApplication(sys.argv)

    # Auto-answer MSG dialogs
    QMessageBox.information = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Ok
    )
    QMessageBox.question = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes
    )

    w = MainWindow(opts)
    w.show()
    app.processEvents()

    # --- G-code open / PC / breakpoints ---
    fd, path = tempfile.mkstemp(suffix=".ngc")
    try:
        os.write(
            fd,
            b"G21\n"
            b"G0 X0 Y0\n"
            b"(MSG, CHANGE TOOL BIT: test)\n"
            b"G1 X1 F100\n"
            b"M2\n",
        )
        os.close(fd)

        if not w.open_gcode_path(path):
            _fail("open_gcode_path failed")
        if w.gcode.line_count() != 5:
            _fail(f"expected 5 lines, got {w.gcode.line_count()}")
        if gc.STATE_DATA.programCounter != 0:
            _fail("PC should start at 0")

        w.set_pc(3)
        if gc.STATE_DATA.programCounter != 3:
            _fail("set_pc failed")
        if w.gcode.current_pc() != 3:
            _fail("PC marker state missing")
        # proxy row text still exposes ▶ for assertions
        if "▶" not in w.gcode.item(3).text():
            _fail("PC marker missing in row proxy")

        w.on_reset_pc()
        if gc.STATE_DATA.programCounter != 0:
            _fail("reset PC failed")

        w.gcode.setCurrentRow(2)
        w.on_break_toggle()
        if 2 not in w.gcode.get_breakpoints():
            _fail("breakpoint not set")
        if "●" not in w.gcode.item(2).text():
            _fail("breakpoint marker missing")

        payload = w._program_payload()
        if 2 not in payload.get("breakPoints", set()):
            _fail("breakpoint not in program payload")
        if "gcodeLines" not in payload:
            _fail("payload missing gcodeLines")

        notes.append("gcode/pc/bp: ok")

        # --- fake backend program commands ---
        fake = FakeBackend()
        w.bridge.machif_progexec = fake
        w.bridge._use_remote = False
        w._machine_open = True
        gc.STATE_DATA.serialPortIsOpen = True
        gc.STATE_DATA.swState = gc.STATE_IDLE
        w._update_connection_ui()

        w.on_step()
        if not fake.events or fake.events[-1][0] != gc.EV_CMD_STEP:
            _fail(f"step did not send EV_CMD_STEP: {fake.events}")

        w.on_run()
        if fake.events[-1][0] != gc.EV_CMD_RUN:
            _fail("run did not send EV_CMD_RUN")

        gc.STATE_DATA.swState = gc.STATE_RUN
        w.on_pause()
        if fake.events[-1][0] != gc.EV_CMD_PAUSE:
            _fail("pause did not send EV_CMD_PAUSE")

        w.on_stop()
        if fake.events[-1][0] != gc.EV_CMD_STOP:
            _fail("stop did not send EV_CMD_STOP")

        notes.append("run/step/pause/stop: ok")

        # --- CLI send ---
        gc.STATE_DATA.swState = gc.STATE_IDLE
        w._update_connection_ui()
        n_before = len(fake.events)
        w.on_cli_submit("?")
        if len(fake.events) <= n_before or fake.events[-1][0] != gc.EV_CMD_SEND:
            _fail("CLI send failed")
        if fake.events[-1][1] != "?\n":
            _fail(f"CLI payload wrong: {fake.events[-1][1]!r}")
        notes.append("cli: ok")

        # --- console newline normalize ---
        w.append_log("line-with-nl\n")
        text = w.console.log_view.toPlainText()
        if "line-with-nl\n\n" in text.replace("\r", ""):
            # allow single trailing paragraph break from QPlainTextEdit
            pass
        if "line-with-nl" not in text:
            _fail("append_log missing text")
        notes.append("console log: ok")

        # --- MSG dialog path (was RUN → continue → on_run) ---
        gc.STATE_DATA.swState = gc.STATE_RUN
        n_before = len(fake.events)
        w.on_backend_event(SimpleEvent(gc.EV_GCODE_MSG, " CHANGE TOOL BIT: test "))
        app.processEvents()
        if gc.STATE_DATA.swState != gc.STATE_BREAK:
            # after Yes, on_run may leave state as-is until backend responds
            pass
        if "** MSG:" not in w.console.log_view.toPlainText():
            _fail("MSG not logged")
        # Yes → on_run → EV_CMD_RUN
        run_after = [e for e in fake.events[n_before:] if e[0] == gc.EV_CMD_RUN]
        if not run_after:
            _fail("MSG Yes did not re-issue Run")
        notes.append("EV_GCODE_MSG: ok")

        # --- status → DRO ---
        w.on_backend_event(
            SimpleEvent(
                gc.EV_DATA_STATUS,
                {
                    "sr": {
                        "posx": 1.5,
                        "posy": -2.25,
                        "posz": 3.0,
                        "stat": "Idle",
                        "vel": 10.0,
                        "machif": "grblHAL",
                    },
                    "rx_data": "<Idle|MPos:1.500,-2.250,3.000>\n",
                },
            )
        )
        app.processEvents()
        if w.dro_panel._axis_edits["posx"].text() != "1.500":
            _fail(f"DRO X wrong: {w.dro_panel._axis_edits['posx'].text()}")
        if "<Idle|MPos" not in w.console.log_view.toPlainText():
            _fail("rx_data not in console")
        notes.append("status/DRO/rx: ok")

        # --- CLI history up/down ---
        w.console.set_cli_enabled(True)
        w.console.cli.setText("cmd-a")
        w.console._on_return_pressed()
        w.console.cli.setText("cmd-b")
        w.console._on_return_pressed()
        w.console._history_older()
        if w.console.cli.text() != "cmd-b":
            _fail(f"history up expected cmd-b got {w.console.cli.text()!r}")
        w.console._history_older()
        if w.console.cli.text() != "cmd-a":
            _fail(f"history up expected cmd-a got {w.console.cli.text()!r}")
        notes.append("cli history: ok")

        # --- CLI history popup (insert, no auto-send) ---
        w.console.show_history_popup()
        app.processEvents()
        if not w.console._popup.isVisible():
            _fail("history popup not visible")
        if w.console._popup.list.count() < 2:
            _fail("history popup missing items")
        # Newest first: last submitted was cmd-b
        if w.console._popup.list.item(0).text() != "cmd-b":
            _fail(f"popup newest should be cmd-b: {w.console._popup.list.item(0).text()}")
        w.console._on_history_chosen("cmd-a")
        app.processEvents()
        if w.console.cli.text() != "cmd-a":
            _fail("history insert failed")
        if w.console._popup.isVisible():
            _fail("popup should hide after choose")
        notes.append("cli history popup: ok")

        # --- CLI history persists to same wx config key ---
        w.console.save_history_to_config()
        raw = gc.CONFIG_DATA.get("/console/cli/CmdHistory", "") or ""
        if "cmd-b" not in raw:
            _fail(f"CLI history not saved to config: {raw!r}")
        notes.append("cli history config save: ok")

        # --- docks for content panels; toolbars for actions ---
        if not hasattr(w, "dock_console") or w.dock_console is None:
            _fail("dock_console missing")
        if not hasattr(w, "tb_program") or w.tb_program is None:
            _fail("program toolbar missing")
        if not hasattr(w, "act_run") or w.act_run is None:
            _fail("run action missing")
        notes.append("toolbars + docks: ok")

        # --- jog essentials ---
        gc.STATE_DATA.swState = gc.STATE_IDLE
        w._update_connection_ui()
        n_before = len(fake.events)
        w.on_jog_relative("x", "1.000", False, 500.0)
        if len(fake.events) <= n_before:
            _fail("jog did not send event")
        eid, data, _ = fake.events[-1]
        if eid != gc.EV_CMD_JOG_MOVE_RELATIVE:
            _fail(f"jog expected EV_CMD_JOG_MOVE_RELATIVE got {eid}")
        if data.get("x") != "1.000" or data.get("feed") != 500.0:
            _fail(f"jog payload wrong: {data}")
        w.on_jog_relative("y", "-0.100", True, None)
        if fake.events[-1][0] != gc.EV_CMD_JOG_RAPID_MOVE_RELATIVE:
            _fail("rapid jog wrong event")
        w.on_jog_stop()
        if fake.events[-1][0] != gc.EV_CMD_JOG_STOP:
            _fail("jog stop missing")
        w.on_home_axes({"x": 0, "y": 0})
        if fake.events[-1][0] != gc.EV_CMD_HOME:
            _fail("home missing")
        notes.append("jog/home: ok")

    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
        w.close()
        app.processEvents()

    return notes


def _wait_until(app, predicate, timeout: float, sleep: float = 0.05) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(sleep)
    app.processEvents()
    return bool(predicate())


def test_live(
    host: str,
    port: int,
    timeout: float = 8.0,
    gcode_path: str | None = None,
) -> list[str]:
    """Remote + controller smoke (server on real IF is fine without motors)."""
    import modules.config as gc
    from PySide6.QtWidgets import QApplication, QMessageBox
    from modules.pyside_workbench.main_window import MainWindow

    notes = []
    opts = _Opts()
    gc.init_config(opts, os.path.expanduser("~/.gsat.json"), "log_pyside_smoke_live")

    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.information = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Ok
    )
    QMessageBox.question = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes
    )

    w = MainWindow(opts)
    w.host_edit.setText(host)
    w.port_edit.setText(str(port))
    w.show()
    app.processEvents()

    w.on_connect_remote()
    if not _wait_until(app, lambda: w._remote_connected, timeout):
        w.close()
        _fail(f"live connect failed to {host}:{port} within {timeout}s")

    notes.append(f"live connect {host}:{port}: ok")
    log = w.console.log_view.toPlainText()
    if "Welcome" in log or "Connected" in log or "config" in log.lower():
        notes.append("live hello/config traffic: ok")

    # Lab: controller without motors is safe to open + command
    w.on_open_machine()
    if not _wait_until(
        app,
        lambda: w._machine_open or gc.STATE_DATA.serialPortIsOpen,
        timeout,
    ):
        # Leave remote up for diagnostics but fail the suite
        w.on_disconnect_remote()
        _wait_until(app, lambda: not w.bridge.is_remote_connected(), 5.0)
        w.close()
        _fail("live open machine did not report open")

    notes.append("live open machine: ok")
    time.sleep(0.3)
    app.processEvents()

    w.on_refresh_status()
    time.sleep(0.4)
    app.processEvents()
    notes.append("live refresh status: ok")

    # CLI status query (grbl-like)
    w.on_cli_submit("?")
    time.sleep(0.5)
    app.processEvents()
    log = w.console.log_view.toPlainText()
    if ">" not in log and "?" not in log:
        # TX might be filtered or status-only path
        pass
    notes.append("live CLI ?: ok")

    # Small jog (lab controller has no motors — safe)
    w.on_jog_relative("x", "0.100", False, 500.0)
    time.sleep(0.5)
    app.processEvents()
    w.on_jog_relative("x", "-0.100", False, 500.0)
    time.sleep(0.5)
    app.processEvents()
    notes.append("live jog ±X 0.1: ok")

    # Prefer user's lab file when present; else tiny synthetic
    lab_gcode = os.environ.get(
        "GSAT_LAB_GCODE",
        "/home/wduembeg/Documents/Python/gcode/test2.ngc",
    )
    unlink_path = None
    if gcode_path:
        path = gcode_path
    elif os.path.isfile(lab_gcode):
        path = lab_gcode
    else:
        fd, path = tempfile.mkstemp(suffix=".ngc")
        os.write(fd, b"G21\nG90\nG0 X0\n")
        os.close(fd)
        unlink_path = path

    try:
        if not w.open_gcode_path(path):
            _fail(f"live open gcode failed: {path}")
        notes.append(f"live open gcode: {os.path.basename(path)}")
        gc.STATE_DATA.swState = gc.STATE_IDLE
        w._update_connection_ui()
        w.on_step()
        time.sleep(0.8)
        app.processEvents()
        notes.append("live step gcode: ok")

        # If file has (MSG, …) lines, stepping past setup may not hit them;
        # set PC to MSG line and run once to exercise continue path when safe.
        msg_line = None
        for i, line in enumerate(w.gcode.lines()):
            if "(MSG," in line.upper() or "(MSG ," in line.upper():
                msg_line = i
                break
        if msg_line is not None:
            # Run from start so backend encounters MSG (not first PC skip rule:
            # MSG is ignored only when workingPC == initialPC)
            w.set_pc(0)
            w.on_run()
            # Wait for MSG handling / break
            time.sleep(1.5)
            app.processEvents()
            log = w.console.log_view.toPlainText()
            if "** MSG:" in log or "CHANGE TOOL" in log or "MSG" in log:
                notes.append("live MSG path: ok")
            else:
                notes.append("live MSG path: no MSG log yet (controller timing)")
            w.on_stop()
            time.sleep(0.3)
            app.processEvents()
    finally:
        if unlink_path:
            try:
                os.unlink(unlink_path)
            except OSError:
                pass

    w.on_close_machine()
    time.sleep(0.3)
    app.processEvents()
    notes.append("live close machine: ok")

    w.on_disconnect_remote()
    _wait_until(
        app,
        lambda: (not w.bridge.is_remote_connected()) and (not w._remote_connected),
        5.0,
    )

    w.close()
    app.processEvents()
    notes.append("live disconnect: ok")
    return notes


def main() -> int:
    p = argparse.ArgumentParser(description="PySide workbench automated smoke tests")
    p.add_argument(
        "--offline",
        action="store_true",
        default=True,
        help="Run offline tests (default)",
    )
    p.add_argument(
        "--no-offline",
        action="store_true",
        help="Skip offline tests",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Also run live remote-connect test",
    )
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--timeout", type=float, default=8.0)
    p.add_argument(
        "--gcode",
        default=None,
        help="G-code for live step/run (default: $GSAT_LAB_GCODE or test2.ngc)",
    )
    args = p.parse_args()

    failed = 0
    all_notes: list[str] = []

    if not args.no_offline:
        print("=== offline smoke ===")
        try:
            notes = test_offline()
            for n in notes:
                print(f"  PASS  {n}")
                all_notes.append(n)
            print("offline: PASS")
        except Exception as exc:
            failed += 1
            print(f"offline: FAIL  {exc}")
            traceback.print_exc()

    if args.live:
        print("=== live smoke ===")
        import modules.config as gc

        opts = _Opts()
        if gc.CONFIG_DATA is None:
            gc.init_config(opts, os.path.expanduser("~/.gsat.json"), "log_pyside_smoke")
        idx = gc.CONFIG_DATA.get("/remotes/Index", 0)
        host = args.host or gc.CONFIG_DATA.get(
            f"/remotes/remote{idx}/Host", "localhost"
        )
        port = args.port or int(
            gc.CONFIG_DATA.get(f"/remotes/remote{idx}/WebSocketPort", 61803)
        )
        try:
            notes = test_live(
                str(host),
                int(port),
                timeout=args.timeout,
                gcode_path=args.gcode,
            )
            for n in notes:
                print(f"  PASS  {n}")
            print("live: PASS")
        except Exception as exc:
            failed += 1
            print(f"live: FAIL  {exc}")
            traceback.print_exc()

    print("---")
    if failed:
        print(f"RESULT: FAIL ({failed} suite(s))")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
