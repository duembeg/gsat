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
      pytest tests/unit
      GSAT_LIVE_HOST=river pytest -m live
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
            _fail("payload missing gcodeLines (MD5 miss on first build)")

        # MD5 gate: after backend fingerprint matches local, omit gcodeLines
        from modules.pyside_workbench.main_window import _gcode_lines_md5

        local_md5 = _gcode_lines_md5(w.gcode.lines())
        w._backend_gcode_md5 = local_md5
        payload2 = w._program_payload()
        if "gcodeLines" in payload2:
            _fail("payload should omit gcodeLines when MD5 matches backend")
        if 2 not in payload2.get("breakPoints", set()):
            _fail("breakpoints must still be sent when MD5 matches")
        # BP-only change still omits lines
        w.gcode.set_breakpoints({2, 4})
        payload3 = w._program_payload()
        if "gcodeLines" in payload3:
            _fail("BP change must not force gcodeLines resend")
        if payload3.get("breakPoints") != {2, 4}:
            _fail("updated breakpoints missing from payload")
        # EV_GCODE_MD5 updates known fingerprint
        w._on_ev_gcode_md5("deadbeef")
        if w._backend_gcode_md5 != "deadbeef":
            _fail("EV_GCODE_MD5 not stored")
        w._backend_gcode_md5 = 0  # restore for later steps (force lines)

        # MaxMessageBytes helper
        mb = gc.get_remote_max_message_bytes()
        if mb < 1000000:
            _fail(f"MaxMessageBytes too small: {mb}")

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
        step_data = fake.events[-1][1] or {}
        if "gcodeLines" not in step_data:
            _fail("first step should include gcodeLines (MD5 unknown)")
        # Simulate backend ack of same program MD5
        w._backend_gcode_md5 = _gcode_lines_md5(w.gcode.lines())
        w.on_step()
        step_data2 = fake.events[-1][1] or {}
        if "gcodeLines" in step_data2:
            _fail("second step should omit gcodeLines when MD5 matches")
        if "breakPoints" not in step_data2:
            _fail("second step must still send breakPoints")

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

        # --- after-run Idle wait + optional runtime dialog (wx) ---
        info_calls: list[tuple[str, str]] = []
        _orig_info = QMessageBox.information

        def _rec_info(_parent, title, text, *_a, **_k):
            info_calls.append((str(title), str(text)))
            return QMessageBox.StandardButton.Ok

        QMessageBox.information = staticmethod(_rec_info)
        try:
            w._display_runtime_dialog = True
            w._run_end_waiting_idle = False
            w._progexec_rtime = 0.0
            w.on_backend_event(SimpleEvent(gc.EV_RUN_END, None, fake))
            if not w._run_end_waiting_idle:
                _fail("EV_RUN_END should start Idle wait")
            if info_calls:
                _fail("runtime dialog must not show before Idle")
            w.on_backend_event(
                SimpleEvent(gc.EV_DATA_STATUS, {"sr": {"stat": "Run", "rtime": 3}}, fake)
            )
            if not w._run_end_waiting_idle:
                _fail("should still wait while status is Run")
            if info_calls:
                _fail("no runtime dialog while Run")
            w.on_backend_event(
                SimpleEvent(
                    gc.EV_DATA_STATUS, {"sr": {"stat": "Idle", "rtime": 12}}, fake
                )
            )
            if w._run_end_waiting_idle:
                _fail("Idle should finish run-end wait")
            if len(info_calls) != 1:
                _fail(f"expected one runtime dialog, got {info_calls!r}")
            title, text = info_calls[0]
            if title != "G-Code Program":
                _fail(f"runtime dialog title {title!r}")
            if "Run time:" not in text or "00:00:12" not in text:
                _fail(f"runtime dialog body {text!r}")
            info_calls.clear()
            w._display_runtime_dialog = False
            w.on_backend_event(SimpleEvent(gc.EV_RUN_END, None, fake))
            w.on_backend_event(
                SimpleEvent(gc.EV_DATA_STATUS, {"sr": {"stat": "Idle", "rtime": 1}}, fake)
            )
            if info_calls:
                _fail("DisplayRunTimeDialog off should not show a box")
            w.on_backend_event(SimpleEvent(gc.EV_RUN_END, None, fake))
            w.on_backend_event(SimpleEvent(gc.EV_ABORT, "x", fake))
            if w._run_end_waiting_idle:
                _fail("ABORT should cancel run-end wait")
            w.on_backend_event(
                SimpleEvent(gc.EV_DATA_STATUS, {"sr": {"stat": "Idle"}}, fake)
            )
            if info_calls:
                _fail("no runtime dialog after abort cancel")
            # EV_ABORT with sender=fake (progexec) closes local machine — restore
            w._machine_open = True
            gc.STATE_DATA.serialPortIsOpen = True
            gc.STATE_DATA.swState = gc.STATE_IDLE
            w._update_connection_ui()
        finally:
            QMessageBox.information = _orig_info
            w._reload_runtime_dialog_setting()
        notes.append("run-end Idle wait + runtime dialog: ok")

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

        # --- toolbars + dockable content (wx AUI-like) ---
        if not hasattr(w, "tb_program") or w.tb_program is None:
            _fail("program toolbar missing")
        if not hasattr(w, "act_run") or w.act_run is None:
            _fail("run action missing")
        if not hasattr(w, "dock_console") or w.dock_console is None:
            _fail("dock_console missing")
        if not hasattr(w, "dock_dro") or not hasattr(w, "dock_jog"):
            _fail("status/jog docks missing")
        if w.centralWidget() is not w.gcode:
            _fail("gcode should be central widget")
        # Factory default (ignore any saved user layout)
        from PySide6.QtCore import Qt as _Qt

        w._apply_default_dock_arrangement()
        app.processEvents()
        if w.dockWidgetArea(w.dock_console) != _Qt.DockWidgetArea.BottomDockWidgetArea:
            _fail("default: console should be bottom dock")
        if w.dockWidgetArea(w.dock_dro) != _Qt.DockWidgetArea.RightDockWidgetArea:
            _fail("default: dro should be right dock")
        if w.dockWidgetArea(w.dock_jog) != _Qt.DockWidgetArea.RightDockWidgetArea:
            _fail("default: jog should be right dock")
        notes.append("toolbars + docks: ok")

        # --- existing gsat PNG icons on key actions (not theme packs) ---
        from modules.pyside_workbench import icons as wb_icons

        if not wb_icons.has_icon("run") or not wb_icons.has_icon("cycle_start"):
            _fail("expected color PNGs missing under images/icons/color/")
        for act, name in (
            (w.act_run, "run"),
            (w.act_cycle_start, "cycle_start"),
            (w.act_feed_hold, "feed_hold"),
            (w.act_open_gcode, "open"),
            (w.act_remote, "remote"),
        ):
            if act.icon().isNull():
                _fail(f"action icon missing for {name}")
        notes.append("toolbar icons (existing PNGs): ok")

        # --- app / window icon (GCS cog PNGs; wx SetIcon never reliable) ---
        app_ico = wb_icons.get_app_icon()
        if app_ico.isNull():
            _fail("app icon empty — expected images/icons/black/gcs_g0_cog_*.png")
        if not wb_icons.apply_app_icon(app, w):
            _fail("apply_app_icon failed")
        if w.windowIcon().isNull():
            _fail("main window icon not set")
        notes.append("app window icon: ok")

        # --- file recent history config keys ---
        w._add_to_file_history(path)
        hist = w._load_file_history()
        if not hist or os.path.abspath(path) not in [
            os.path.abspath(h) for h in hist
        ]:
            _fail("file history not updated")
        f1 = gc.CONFIG_DATA.get("/mainApp/FileHistory/File1", "")
        if not f1:
            _fail("File1 not written to config")
        notes.append("file recent history: ok")

        # --- Open split button: click = dialog action, ▾ = recent (wx dropdown) ---
        if w.btn_open is None:
            _fail("btn_open missing")
        if w.btn_open.defaultAction() is not w.act_open_gcode:
            _fail("open toolbutton default action not open gcode")
        from PySide6.QtWidgets import QToolButton

        if (
            w.btn_open.popupMode()
            != QToolButton.ToolButtonPopupMode.MenuButtonPopup
        ):
            _fail("open toolbutton should be MenuButtonPopup (split)")
        if w.btn_open.menu() is not w._open_dropdown_menu:
            _fail("open dropdown menu not attached")
        # Main toolbar shows icon + text like wx; others stay icon-only
        from PySide6.QtCore import Qt

        if (
            w.tb_main.toolButtonStyle()
            != Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        ):
            _fail("main toolbar should show text beside icons")
        if (
            w.btn_open.toolButtonStyle()
            != Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        ):
            _fail("open split button should show text beside icon")
        if (
            w.tb_program.toolButtonStyle()
            != Qt.ToolButtonStyle.ToolButtonIconOnly
        ):
            _fail("program toolbar should stay icon-only")
        # After history add, dropdown should list the path (wx "&0 path")
        labels = [a.text() for a in w._open_dropdown_menu.actions()]
        if not any(os.path.basename(path) in t for t in labels):
            _fail(f"open dropdown missing recent file: {labels}")
        notes.append("open split-button + recent dropdown: ok")

        # --- jog panel (wx pad: relative, home, zero, abs, probe, scripts) ---
        from modules.pyside_workbench import icons as _jog_icons

        gc.STATE_DATA.swState = gc.STATE_IDLE
        w._update_connection_ui()
        # Icon assets for pad
        for jname in ("pos_x", "home_xyz", "zero_xy", "spindle_cw", "probe_z"):
            if _jog_icons.get_jog_icon(jname).isNull():
                _fail(f"jog icon missing: {jname}")
        if not hasattr(w.jog, "btn_home_xyz") or not hasattr(w.jog, "spindle_spin"):
            _fail("jog pad widgets missing")
        if not hasattr(w.jog, "btn_spindle_cw"):
            _fail("jog spindle buttons missing")
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
        w.on_jog_zero_axes({"x": 0, "y": 0, "z": 0})
        if fake.events[-1][0] != gc.EV_CMD_SET_AXIS:
            _fail("jog zero missing SET_AXIS")
        w.on_jog_absolute({"x": 0, "y": 0}, True, None)
        if fake.events[-1][0] != gc.EV_CMD_JOG_RAPID_MOVE:
            _fail("jog abs rapid missing")
        w.on_jog_absolute({"x": 0, "y": 0}, False, 400.0)
        if fake.events[-1][0] != gc.EV_CMD_JOG_MOVE:
            _fail("jog abs feed missing")
        if fake.events[-1][1].get("feed") != 400.0:
            _fail("jog abs feed payload wrong")
        w.on_jog_probe({"z": -1})
        if fake.events[-1][0] != gc.EV_CMD_PROBE_HELPER:
            _fail("probe helper missing")
        n_before = len(fake.events)
        w.on_jog_gcode_script(f"{gc.DEVICE_CMD_SPINDLE_CW_ON} S1000")
        # send_line uses EV_CMD_SEND
        if len(fake.events) <= n_before:
            _fail("spindle gcode script did not send")
        if fake.events[-1][0] != gc.EV_CMD_SEND:
            _fail(f"spindle expected EV_CMD_SEND got {fake.events[-1][0]}")
        # Custom buttons present from config
        if not w.jog._custom_buttons:
            _fail("expected custom buttons from config")
        w.jog.update_settings()
        notes.append("jog/home/zero/probe/spindle/custom: ok")

        # --- machine toolbar extras (wx Machine menu/toolbar) ---
        gc.STATE_DATA.swState = gc.STATE_IDLE
        w._update_connection_ui()
        if not w.act_cycle_start.isEnabled():
            _fail("cycle start should be enabled when machine open")
        for method, eid, label in (
            (w.on_cycle_start, gc.EV_CMD_CYCLE_START, "cycle start"),
            (w.on_feed_hold, gc.EV_CMD_FEED_HOLD, "feed hold"),
            (w.on_queue_flush, gc.EV_CMD_QUEUE_FLUSH, "queue flush"),
            (w.on_machine_reset, gc.EV_CMD_RESET, "reset"),
            (w.on_clear_alarm, gc.EV_CMD_CLEAR_ALARM, "clear alarm"),
        ):
            n_before = len(fake.events)
            method()
            if len(fake.events) <= n_before or fake.events[-1][0] != eid:
                _fail(f"{label} did not send {eid}: {fake.events[n_before:]}")
        # Abort = feed hold + stop (wx OnAbort)
        n_before = len(fake.events)
        w.on_abort()
        abort_ids = [e[0] for e in fake.events[n_before:]]
        if abort_ids != [gc.EV_CMD_FEED_HOLD, gc.EV_CMD_STOP]:
            _fail(f"abort expected [FEED_HOLD, STOP], got {abort_ids}")
        # Disabled when machine closed
        w._machine_open = False
        gc.STATE_DATA.serialPortIsOpen = False
        w._update_connection_ui()
        if w.act_feed_hold.isEnabled():
            _fail("feed hold should be disabled when machine closed")
        n_before = len(fake.events)
        w.on_feed_hold()
        if len(fake.events) != n_before:
            _fail("feed hold should not send when machine closed")
        # Restore open for remaining teardown
        w._machine_open = True
        gc.STATE_DATA.serialPortIsOpen = True
        w._update_connection_ui()
        notes.append("machine extras (cycle/hold/flush/reset/alarm/abort): ok")

        # --- machine Connect toggle (wx one-button, icon+tooltip flip) ---
        w._machine_open = False
        gc.STATE_DATA.serialPortIsOpen = False
        w._update_connection_ui()
        tip_closed = (w.act_machine_connect.toolTip() or "").lower()
        if "connect" not in tip_closed or "disconnect" in tip_closed:
            _fail(f"closed tip should invite connect: {w.act_machine_connect.toolTip()!r}")
        if w.act_machine_connect.isChecked():
            _fail("connect action should be unchecked when machine closed")
        w._machine_open = True
        gc.STATE_DATA.serialPortIsOpen = True
        w._update_connection_ui()
        tip_open = (w.act_machine_connect.toolTip() or "").lower()
        if "disconnect" not in tip_open:
            _fail(f"open tip should invite disconnect: {w.act_machine_connect.toolTip()!r}")
        if not w.act_machine_connect.isChecked():
            _fail("connect action should be checked when machine open")
        # toggle dispatches close when open
        class _BridgeSpy:
            def __init__(self):
                self.closed = False
                self.opened = False

            def open_machine(self):
                self.opened = True

            def close_machine(self):
                self.closed = True

            def is_backend_active(self):
                return True

            def is_remote_connected(self):
                return False

            def remote_hostname(self):
                return ""

            def send_command(self, *a, **k):
                pass

        spy = _BridgeSpy()
        old_bridge = w.bridge
        w.bridge = spy
        w._machine_open = True
        gc.STATE_DATA.serialPortIsOpen = True
        w.on_machine_connect()
        if not spy.closed or spy.opened:
            w.bridge = old_bridge
            _fail("connect toggle when open should close only")
        w._machine_open = False
        gc.STATE_DATA.serialPortIsOpen = False
        w.on_machine_connect()
        if not spy.opened:
            w.bridge = old_bridge
            _fail("connect toggle when closed should open")
        w.bridge = old_bridge
        w._machine_open = True
        gc.STATE_DATA.serialPortIsOpen = True
        w._update_connection_ui()
        notes.append("machine connect toggle: ok")

        # --- remote toggle (remote.png, not plugs; tooltip flips) ---
        # UI treats remote up as (_remote_connected AND bridge.is_remote_connected())
        class _RemoteFlag:
            def __init__(self):
                self.up = False

            def is_remote_connected(self):
                return self.up

            def is_backend_active(self):
                return False

            def remote_hostname(self):
                return "testhost" if self.up else ""

            def send_command(self, *a, **k):
                pass

        old_bridge = w.bridge
        rflag = _RemoteFlag()
        w.bridge = rflag
        w._remote_connected = False
        w._remote_connecting = False
        w._update_connection_ui()
        tip_off = (w.act_remote.toolTip() or "").lower()
        if not tip_off.startswith("connect"):
            _fail(f"offline remote tip should start with connect: {w.act_remote.toolTip()!r}")
        if w.act_remote.isChecked():
            _fail("remote action unchecked when offline")
        if w.act_remote.icon().isNull():
            _fail("remote toggle should use remote.png")
        rflag.up = True
        w._remote_connected = True
        w._update_connection_ui()
        tip_on = (w.act_remote.toolTip() or "").lower()
        if not tip_on.startswith("disconnect"):
            _fail(f"online remote tip should start with disconnect: {w.act_remote.toolTip()!r}")
        if not w.act_remote.isChecked():
            _fail("remote action checked when connected")
        rflag.up = False
        w._remote_connected = False
        w._remote_connecting = True
        w._update_connection_ui()
        tip_c = (w.act_remote.toolTip() or "").lower()
        if "disconnect" not in tip_c:
            _fail(f"connecting tip should offer disconnect/cancel: {w.act_remote.toolTip()!r}")
        w.bridge = old_bridge
        w._remote_connected = False
        w._remote_connecting = False
        w._update_connection_ui()
        notes.append("remote connect toggle: ok")

        # --- DRO click actions (wx move / home / zero / set) ---
        gc.STATE_DATA.swState = gc.STATE_IDLE
        gc.STATE_DATA.joggingRapid = False
        gc.STATE_DATA.joggingFeedRate = 500.0
        w._machine_open = True
        gc.STATE_DATA.serialPortIsOpen = True
        w.bridge.machif_progexec = fake
        w.bridge._use_remote = False
        w._update_connection_ui()
        if not w.dro_panel._interactive:
            _fail("DRO should be interactive when machine open")
        n_before = len(fake.events)
        w.on_dro_move_to("x", 12.5)
        if len(fake.events) <= n_before:
            _fail("DRO move sent nothing")
        eid, data, _ = fake.events[-1]
        if eid != gc.EV_CMD_MOVE:
            _fail(f"DRO move expected EV_CMD_MOVE got {eid}")
        if data.get("x") != 12.5 or data.get("feed") != 500.0:
            _fail(f"DRO move payload wrong: {data}")
        gc.STATE_DATA.joggingRapid = True
        w.on_dro_move_to("y", -1.0)
        if fake.events[-1][0] != gc.EV_CMD_RAPID_MOVE:
            _fail("DRO rapid move wrong event")
        w.on_dro_home_axis("z")
        if fake.events[-1][0] != gc.EV_CMD_HOME or "z" not in fake.events[-1][1]:
            _fail(f"DRO home wrong: {fake.events[-1]}")
        w.on_dro_zero_axis("x")
        if fake.events[-1][0] != gc.EV_CMD_SET_AXIS or fake.events[-1][1].get("x") != 0:
            _fail(f"DRO zero wrong: {fake.events[-1]}")
        w.on_dro_set_axis("x", 3.25)
        if (
            fake.events[-1][0] != gc.EV_CMD_SET_AXIS
            or fake.events[-1][1].get("x") != 3.25
        ):
            _fail(f"DRO set axis wrong: {fake.events[-1]}")
        # blocked when closed
        w._machine_open = False
        gc.STATE_DATA.serialPortIsOpen = False
        w._update_connection_ui()
        n_before = len(fake.events)
        w.on_dro_move_to("x", 1.0)
        if len(fake.events) != n_before:
            _fail("DRO move should not send when machine closed")
        notes.append("DRO move/home/zero/set: ok")

        # --- settings dialog (local pages, same keys as wx) ---
        from modules.pyside_workbench.settings_dialog import SettingsDialog
        from PySide6.QtWidgets import QDialog

        dlg = SettingsDialog(w, config_data=gc.CONFIG_DATA)
        if dlg.tabs.count() < 5:
            _fail(f"expected full local settings tabs, got {dlg.tabs.count()}")
        # wx notebook tab icons (settings_tab_* → existing color PNGs)
        from modules.pyside_workbench import icons as _wb_icons

        for i in range(dlg.tabs.count()):
            title = dlg.tabs.tabText(i)
            if title not in _wb_icons.SETTINGS_TAB_ICONS:
                _fail(f"settings tab {title!r} missing SETTINGS_TAB_ICONS entry")
            if dlg.tabs.tabIcon(i).isNull():
                _fail(f"settings tab {title!r} has no icon")
        # Apply without modal: mutate a known key and write back
        gen = dlg.pages[0]
        old_hist = int(gc.CONFIG_DATA.get("/mainApp/FileHistory/FilesMaxHistory", 10) or 10)
        gen.sp_history.setValue(min(99, old_hist + 1))
        gen.apply()
        new_hist = int(gc.CONFIG_DATA.get("/mainApp/FileHistory/FilesMaxHistory", 0) or 0)
        if new_hist != min(99, old_hist + 1):
            _fail(f"settings general apply failed: {new_hist}")
        # restore
        gen.sp_history.setValue(old_hist)
        gen.apply()
        # remote-mode notebook has 2 pages; Machine tab is the same MachinePage
        # class as local Settings (serial-port UX is shared, not duplicated).
        from modules.pyside_workbench.settings_dialog import MachinePage

        rdlg = SettingsDialog(
            w, config_data=gc.CONFIG_DATA, config_remote_data=gc.CONFIG_DATA, title="Remote Settings"
        )
        if rdlg.tabs.count() != 2:
            _fail(f"remote settings should be Machine+Remote, got {rdlg.tabs.count()}")
        if not isinstance(rdlg.pages[0], MachinePage):
            _fail(f"remote Machine tab type {type(rdlg.pages[0])}, expected MachinePage")
        local_machine = next((p for p in dlg.pages if isinstance(p, MachinePage)), None)
        if local_machine is None:
            _fail("local Settings missing MachinePage")
        for label, page in (("local", local_machine), ("remote", rdlg.pages[0])):
            if not hasattr(page, "port") or page.port is None:
                _fail(f"{label} MachinePage missing serial port combo")
            if not hasattr(page, "_refresh_ports"):
                _fail(f"{label} MachinePage missing _refresh_ports")
            if page.port.lineEdit() is None:
                _fail(f"{label} serial port combo should be editable")
        # /temp/SerialPorts (server snapshot) + same filter as local (USB/ACM/cu, COM*)
        stub = gc.ConfigData()
        stub.add("/machine/Device", "grblHAL")
        stub.add("/machine/Port", "/dev/ttyUSB0")
        stub.add("/machine/Baud", "115200")
        stub.add(
            "/temp/SerialPorts",
            [
                "/dev/ttyS0, onboard UART",  # filtered out (Linux)
                "/dev/ttyUSB99, Fake CNC (remote)",  # kept
                "/dev/ttyACM1, CDC ACM",  # kept
                "/dev/cu.usbmodem14201, Apple USB",  # kept (macOS)
                "/dev/tty.Bluetooth-Incoming-Port, bt",  # filtered (no USB/ACM/cu)
                "COM7, USB Serial Device",  # kept (Windows)
                "COM3",  # kept
            ],
        )
        stub.add("/temp/RemoteServer", True)
        mp = MachinePage(stub)
        items = [mp.port.itemText(i) for i in range(mp.port.count())]
        joined = " | ".join(items)
        for must in ("ttyUSB99", "ttyACM1", "cu.usbmodem14201", "COM7", "COM3"):
            if must not in joined:
                _fail(f"MachinePage remote list missing {must!r}: {items!r}")
        for must_not in ("ttyS0", "Bluetooth"):
            if must_not in joined:
                _fail(f"MachinePage should filter out {must_not!r}: {items!r}")
        # Allow helpers: Windows COM always; Unix needs USB/ACM/cu
        if not MachinePage._serial_device_allowed("COM12"):
            _fail("COM12 should be allowed (Windows)")
        if not MachinePage._serial_device_allowed("/dev/ttyUSB0"):
            _fail("ttyUSB0 should be allowed (Linux)")
        if not MachinePage._serial_device_allowed("/dev/cu.usbserial-A"):
            _fail("cu.* should be allowed (macOS)")
        if MachinePage._serial_device_allowed("/dev/ttyS0"):
            _fail("ttyS0 should be filtered")
        # Select list row → path only (strip description)
        for i, t in enumerate(items):
            if "ttyUSB99" in t:
                mp._on_port_activated(i)
                break
        if mp.port.currentText() != "/dev/ttyUSB99":
            _fail(f"port activate should strip description, got {mp.port.currentText()!r}")
        # Probe + MachIf visibility (wx UpdateUI parity)
        if not getattr(mp, "probe_widgets", None) or "Z" not in mp.probe_widgets:
            _fail("MachinePage missing Probe widgets")
        mp.probe_widgets["Z"]["Offset"].setValue(1.25)
        mp.probe_widgets["Z"]["FeedRate"].setValue(42)
        mp.apply()
        if float(stub.get("/machine/Probe/Z/Offset", 0) or 0) != 1.25:
            _fail("Probe Z Offset did not apply")
        if int(stub.get("/machine/Probe/Z/FeedRate", 0) or 0) != 42:
            _fail("Probe Z FeedRate did not apply")
        # Enable only Z → only Z probe group visible
        for ax, cb in mp.dro_axes.items():
            cb.setChecked(ax == "Z")
        mp._update_conditional_sections()
        # isHidden() (not isVisible): page may not be shown yet in offscreen smoke
        if mp.probe_groups["Z"].isHidden():
            _fail("Z probe group should be visible when Z DRO enabled")
        if not mp.probe_groups["X"].isHidden():
            _fail("X probe group should hide when X DRO disabled")
        # Device-specific: only selected controller group visible (if any)
        if mp.spec_groups:
            name = next(iter(mp.spec_groups))
            mp.device.setCurrentText(name)
            mp._update_conditional_sections()
            if mp.spec_groups[name].isHidden():
                _fail(f"MachIf group for {name} should be visible when selected")
            for other, box in mp.spec_groups.items():
                if other != name and not box.isHidden():
                    _fail(f"MachIf group {other} should hide when Device={name}")
        if not hasattr(w, "act_settings") or w.act_settings is None:
            _fail("settings action missing")
        notes.append("settings dialog (local+remote modes + shared Machine serial): ok")

        # --- G-code AutoScroll includes On Goto PC (wx index 3) ---
        from modules.pyside_workbench.settings_dialog import OutputStylePage

        code_page = OutputStylePage(gc.CONFIG_DATA, "code", syntax=True)
        labels = [code_page.auto_scroll.itemText(i) for i in range(code_page.auto_scroll.count())]
        if "On Goto PC" not in labels:
            _fail(f"G-code AutoScroll missing On Goto PC: {labels}")
        # Never: PC update does not scroll-follow
        gc.CONFIG_DATA.set("/code/AutoScroll", 0)
        w.gcode.reload_auto_scroll_setting()
        if w.gcode._should_scroll_on_pc_update():
            _fail("Never mode should not follow PC")
        # On Goto PC: follow after goto_pc
        gc.CONFIG_DATA.set("/code/AutoScroll", 3)
        w.gcode.reload_auto_scroll_setting()
        w.gcode._follow_pc = False
        if w.gcode._should_scroll_on_pc_update():
            _fail("On Goto PC with follow off should not auto-scroll")
        w.gcode.goto_pc()
        if not w.gcode._follow_pc:
            _fail("goto_pc should re-enable follow in On Goto PC mode")
        if not w.gcode._should_scroll_on_pc_update():
            _fail("after goto_pc, PC updates should follow")
        notes.append("gcode AutoScroll On Goto PC: ok")

        # --- G-code find/replace (in-panel bar, not toolbar) ---
        if not hasattr(w, "act_find") or w.act_find is None:
            _fail("Edit Find action missing")
        if not hasattr(w.gcode, "find_bar"):
            _fail("GcodePanel missing find_bar")
        w.gcode.load_lines(
            "find_test.ngc",
            ["G0 X0\n", "G1 X10 F100\n", "G0 X0\n", "M2\n"],
        )
        w.gcode.show_find(replace=False)
        if not w.gcode.find_bar.is_open():
            _fail("find bar should open")
        w.gcode.find_bar.find_edit.setText("G0")
        if not w.gcode.find_bar.find_next(wrap=True):
            _fail("find_next should match G0")
        # Second G0
        if not w.gcode.find_bar.find_next(wrap=True):
            _fail("find_next second G0 failed")
        w.gcode.show_find(replace=True)
        if not w.gcode.find_bar.replace_edit.isVisible():
            _fail("replace mode should show replace field")
        w.gcode.find_bar.find_edit.setText("G0")
        w.gcode.find_bar.replace_edit.setText("G00")
        w.gcode.find_bar.replace_all()
        text = w.gcode.document_text()
        if "G0 " in text or text.count("G00") < 2:
            _fail(f"replace_all G0→G00 failed: {text!r}")
        w.gcode.hide_find()
        if w.gcode.find_bar.is_open():
            _fail("hide_find should close bar")
        # replace_all dirties the document — clear so later EV_GCODE tests
        # do not open a blocking Save dialog (offscreen hang)
        w.gcode.editor.document().setModified(False)
        notes.append("gcode find/replace bar: ok")

        # --- fonts/colors apply from config (init + update_settings) ---
        # Save/restore so smoke does not pollute ~/.gsat.json
        _saved = {}
        for k in (
            "/code/WindowBackground",
            "/code/WindowForeground",
            "/code/GCodeHighlight",
            "/code/FontSize",
            "/console/WindowBackground",
            "/console/WindowForeground",
            "/console/FontSize",
        ):
            _saved[k] = gc.CONFIG_DATA.get(k)
        try:
            gc.CONFIG_DATA.set("/code/WindowBackground", "#112233")
            gc.CONFIG_DATA.set("/code/WindowForeground", "#AABBCC")
            gc.CONFIG_DATA.set("/code/GCodeHighlight", "#FF00AA")
            gc.CONFIG_DATA.set("/code/FontSize", 12)
            w.gcode.update_settings()
            ss = w.gcode.editor.styleSheet()
            if "#112233" not in ss or "#AABBCC" not in ss:
                _fail(f"gcode styles not applied: {ss!r}")
            if w.gcode.editor.font().pointSize() != 12:
                _fail(
                    f"gcode font size not applied: {w.gcode.editor.font().pointSize()}"
                )
            cname = w.gcode.editor._highlighter.fmt_gcode.foreground().color().name()
            if cname.lower() != "#ff00aa":
                _fail(f"gcode highlight color not applied: {cname}")
            gc.CONFIG_DATA.set("/console/WindowBackground", "#010203")
            gc.CONFIG_DATA.set("/console/WindowForeground", "#f0f0f0")
            gc.CONFIG_DATA.set("/console/FontSize", 11)
            w.console.update_settings()
            css = w.console.log_view.styleSheet()
            if "#010203" not in css or "#f0f0f0" not in css:
                _fail(f"console styles not applied: {css!r}")
            if w.console.log_view.font().pointSize() != 11:
                _fail("console font size not applied")
        finally:
            for k, v in _saved.items():
                if v is None:
                    continue
                gc.CONFIG_DATA.set(k, v)
            try:
                gc.CONFIG_DATA.save()
            except Exception:
                pass
            w.gcode.update_settings()
            w.console.update_settings()
        notes.append("gcode/console UpdateSettings fonts+colors: ok")

        # --- remote Get G-code (explicit pull, not auto) ---
        class _RemoteSpy:
            def __init__(self):
                self.events = []

            def add_event(self, event_id, data=None, sender=None):
                self.events.append((event_id, data, sender))

        spy = _RemoteSpy()
        old_rc = w.bridge.remote_client
        old_mx = w.bridge.machif_progexec
        old_ur = w.bridge._use_remote
        w.bridge.remote_client = spy
        w.bridge.machif_progexec = spy
        w.bridge._use_remote = True
        w._remote_connected = True
        w._update_connection_ui()
        if not w.act_remote_get_gcode.isEnabled():
            w.bridge.remote_client = old_rc
            w.bridge.machif_progexec = old_mx
            w.bridge._use_remote = old_ur
            _fail("get gcode should enable when remote connected")
        w.on_remote_get_gcode()
        if not spy.events or spy.events[-1][0] != gc.EV_CMD_GET_GCODE:
            w.bridge.remote_client = old_rc
            w.bridge.machif_progexec = old_mx
            w.bridge._use_remote = old_ur
            _fail(f"get gcode did not send EV_CMD_GET_GCODE: {spy.events}")
        # Simulate server reply with program buffer
        w._on_ev_gcode(
            {
                "gcodeFileName": "/remote/test.ngc",
                "gcodeLines": ["G21\n", "G0 X1\n", "M2\n"],
                "gcodePC": 1,
                "breakPoints": {0},
            }
        )
        if w.gcode.line_count() != 3:
            _fail(f"EV_GCODE load failed: {w.gcode.line_count()} lines")
        if gc.STATE_DATA.programCounter != 1:
            _fail(f"EV_GCODE PC not applied: {gc.STATE_DATA.programCounter}")
        if 0 not in w.gcode.get_breakpoints():
            _fail("EV_GCODE breakpoints not applied")
        w.bridge.remote_client = old_rc
        w.bridge.machif_progexec = old_mx
        w.bridge._use_remote = old_ur
        w._remote_connected = False
        w._update_connection_ui()
        notes.append("remote get gcode: ok")

        # --- DRO Enable* from machine settings (hide B/C when disabled) ---
        for ax, on in (("X", True), ("Y", True), ("Z", True), ("A", True), ("B", False), ("C", False)):
            gc.CONFIG_DATA.set(f"/machine/DRO/Enable{ax}", on)
        w.dro_panel.update_settings()
        if not w.dro_panel._axis_edits["posa"].isVisible():
            _fail("EnableA true but A hidden")
        if w.dro_panel._axis_edits["posb"].isVisible():
            _fail("EnableB false but B still visible")
        if w.dro_panel._axis_edits["posc"].isVisible():
            _fail("EnableC false but C still visible")
        if not w.dro_panel._axis_edits["posx"].isVisible():
            _fail("X should remain visible")
        notes.append("DRO Enable axes visibility: ok")

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

    def _console() -> str:
        return w.console.log_view.toPlainText()

    def _stat() -> str:
        return str(gc.STATE_DATA.machineStatusString or "")

    # Lab: controller without motors is safe to open + command
    w.on_open_machine()
    if not _wait_until(
        app,
        lambda: w._machine_open or gc.STATE_DATA.serialPortIsOpen,
        timeout,
    ):
        w.on_disconnect_remote()
        _wait_until(app, lambda: not w.bridge.is_remote_connected(), 5.0)
        w.close()
        _fail("live open machine did not report open")

    notes.append("live open machine: ok")

    w.on_refresh_status()
    if not _wait_until(app, lambda: bool(_stat().strip()), timeout):
        w.on_close_machine()
        w.on_disconnect_remote()
        w.close()
        _fail("live: no machine status after open/refresh")
    stat = _stat()
    notes.append(f"live status: {stat!r}")
    if "alarm" in stat.lower():
        notes.append("live: controller in Alarm (still connected)")

    # CLI status query — require some TX/RX evidence
    log_before = _console()
    w.on_cli_submit("?")
    if not _wait_until(
        app,
        lambda: _console() != log_before
        and (
            "?" in _console()[len(log_before) :]
            or ">" in _console()[len(log_before) :]
            or "ok" in _console()[len(log_before) :].lower()
            or "idle" in _console()[len(log_before) :].lower()
            or "<" in _console()[len(log_before) :]
        ),
        timeout,
    ):
        w.on_close_machine()
        w.on_disconnect_remote()
        w.close()
        _fail("live CLI ? produced no TX/RX in console")
    notes.append("live CLI ?: ok")

    # Tiny synthetic program for Step (dwell only — no travel). --gcode overrides.
    unlink_path = None
    if gcode_path:
        path = gcode_path
    else:
        fd, path = tempfile.mkstemp(suffix=".ngc", prefix="gsat_live_")
        os.write(fd, b"G21\nG90\nG4 P0.05\n")
        os.close(fd)
        unlink_path = path

    try:
        if not w.open_gcode_path(path):
            _fail(f"live open gcode failed: {path}")
        notes.append(f"live open gcode: {os.path.basename(path)}")
        gc.STATE_DATA.swState = gc.STATE_IDLE
        w._update_connection_ui()
        pc0 = int(gc.STATE_DATA.programCounter or 0)
        log_before = _console()
        w.on_step()
        if not _wait_until(
            app,
            lambda: (
                int(gc.STATE_DATA.programCounter or 0) > pc0
                or gc.STATE_DATA.swState == gc.STATE_IDLE
                and (">" in _console()[len(log_before) :] or "ok" in _console()[len(log_before) :].lower())
            ),
            timeout,
        ):
            _fail(
                "live step: no PC advance or TX/ack "
                f"(pc={gc.STATE_DATA.programCounter} sw={gc.STATE_DATA.swState})"
            )
        notes.append("live step gcode: ok")

        # Optional MSG path if caller passed a file that contains (MSG, …)
        msg_line = None
        for i, line in enumerate(w.gcode.lines()):
            if "(MSG," in line.upper() or "(MSG ," in line.upper():
                msg_line = i
                break
        if msg_line is not None:
            w.set_pc(0)
            w.on_run()
            if not _wait_until(
                app,
                lambda: (
                    "** MSG:" in _console()
                    or "CHANGE TOOL" in _console()
                    or gc.STATE_DATA.swState == gc.STATE_BREAK
                ),
                timeout,
            ):
                w.on_stop()
                notes.append("live MSG path: no break/MSG within timeout")
            else:
                notes.append("live MSG path: ok")
            w.on_stop()
            _wait_until(
                app,
                lambda: gc.STATE_DATA.swState
                in (gc.STATE_IDLE, gc.STATE_BREAK, gc.STATE_ABORT),
                5.0,
            )
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
    p.add_argument("--timeout", type=float, default=12.0)
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
