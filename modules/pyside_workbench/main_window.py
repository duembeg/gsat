"""----------------------------------------------------------------------------
    main_window.py

    Spike shell for the gsat PySide workbench:
    connect + DRO + console CLI + G-code / PC.
----------------------------------------------------------------------------"""
from __future__ import annotations

import logging
import os

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

import modules.config as gc
import modules.version_info as vinfo

from modules.pyside_workbench.client_bridge import ClientBridge
from modules.pyside_workbench.console_panel import ConsolePanel
from modules.pyside_workbench.dro_panel import DroPanel
from modules.pyside_workbench.gcode_panel import GcodePanel


class MainWindow(QMainWindow):
    def __init__(self, cmd_line_options, parent=None):
        super().__init__(parent)
        self.cmd_line_options = cmd_line_options
        self.logger = logging.getLogger(__name__)

        self.setWindowTitle(f"{vinfo.__appname__} — PySide workbench (spike)")
        self.resize(1100, 720)

        self.bridge = ClientBridge(self)
        self.bridge.backend_event.connect(self.on_backend_event)
        self.bridge.log_message.connect(self.append_log)

        self._machine_open = False
        self._remote_connected = False
        self._remote_connecting = False

        self._build_ui()
        self._build_menu()
        self._load_remote_defaults()
        self._update_connection_ui()
        self.set_pc(0)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Remote connection strip
        remote_row = QHBoxLayout()
        remote_row.addWidget(QLabel("Host:"))
        self.host_edit = QLineEdit()
        self.host_edit.setMinimumWidth(160)
        remote_row.addWidget(self.host_edit)

        remote_row.addWidget(QLabel("Port:"))
        self.port_edit = QLineEdit()
        self.port_edit.setMaximumWidth(80)
        remote_row.addWidget(self.port_edit)

        self.btn_connect = QPushButton("Connect remote")
        self.btn_connect.clicked.connect(self.on_connect_remote)
        remote_row.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self.on_disconnect_remote)
        remote_row.addWidget(self.btn_disconnect)

        remote_row.addStretch(1)
        layout.addLayout(remote_row)

        # Machine + program actions
        machine_row = QHBoxLayout()
        self.btn_open_file = QPushButton("Open G-code…")
        self.btn_open_file.clicked.connect(self.on_open_gcode)
        machine_row.addWidget(self.btn_open_file)

        self.btn_open = QPushButton("Open machine")
        self.btn_open.clicked.connect(self.on_open_machine)
        machine_row.addWidget(self.btn_open)

        self.btn_close = QPushButton("Close machine")
        self.btn_close.clicked.connect(self.on_close_machine)
        machine_row.addWidget(self.btn_close)

        self.btn_refresh = QPushButton("Refresh status")
        self.btn_refresh.setToolTip("Request one status update (no auto-poll)")
        self.btn_refresh.clicked.connect(self.on_refresh_status)
        machine_row.addWidget(self.btn_refresh)

        self.btn_local = QPushButton("Open local (serial)")
        self.btn_local.setToolTip(
            "Start MachIfExecuteThread using machine settings from ~/.gsat.json"
        )
        self.btn_local.clicked.connect(self.on_open_local)
        machine_row.addWidget(self.btn_local)

        machine_row.addSpacing(12)

        self.btn_set_pc = QPushButton("Set PC")
        self.btn_set_pc.setToolTip("Set program counter to selected G-code line")
        self.btn_set_pc.clicked.connect(self.on_set_pc)
        machine_row.addWidget(self.btn_set_pc)

        self.btn_reset_pc = QPushButton("Reset PC")
        self.btn_reset_pc.clicked.connect(self.on_reset_pc)
        machine_row.addWidget(self.btn_reset_pc)

        self.btn_goto_pc = QPushButton("Goto PC")
        self.btn_goto_pc.clicked.connect(self.on_goto_pc)
        machine_row.addWidget(self.btn_goto_pc)

        self.btn_break = QPushButton("Break")
        self.btn_break.setToolTip("Toggle breakpoint on selected line (F9)")
        self.btn_break.clicked.connect(self.on_break_toggle)
        machine_row.addWidget(self.btn_break)

        self.btn_break_clear = QPushButton("Clear BP")
        self.btn_break_clear.setToolTip("Remove all breakpoints")
        self.btn_break_clear.clicked.connect(self.on_break_clear)
        machine_row.addWidget(self.btn_break_clear)

        self.btn_run = QPushButton("Run")
        self.btn_run.setToolTip("Run program from PC (EV_CMD_RUN)")
        self.btn_run.clicked.connect(self.on_run)
        machine_row.addWidget(self.btn_run)

        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setToolTip("Pause program (EV_CMD_PAUSE)")
        self.btn_pause.clicked.connect(self.on_pause)
        machine_row.addWidget(self.btn_pause)

        self.btn_step = QPushButton("Step")
        self.btn_step.setToolTip("Step one G-code line (EV_CMD_STEP)")
        self.btn_step.clicked.connect(self.on_step)
        machine_row.addWidget(self.btn_step)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self.on_stop)
        machine_row.addWidget(self.btn_stop)

        machine_row.addStretch(1)
        layout.addLayout(machine_row)

        self.connection_label = QLabel("Connection: idle")
        layout.addWidget(self.connection_label)

        # Main body: G-code | DRO / console
        body = QSplitter(Qt.Orientation.Horizontal)

        self.gcode = GcodePanel()
        self.gcode.set_pc_requested.connect(self.set_pc)
        self.gcode.break_toggled.connect(self.on_break_toggled)
        body.addWidget(self.gcode)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.dro_panel = DroPanel()
        right_layout.addWidget(self.dro_panel, 0)

        max_hist = 40
        try:
            max_hist = int(gc.CONFIG_DATA.get("/console/cli/CmdMaxHistory", 40))
        except (TypeError, ValueError):
            pass
        self.console = ConsolePanel(max_history=max_hist)
        self.console.line_submitted.connect(self.on_cli_submit)
        right_layout.addWidget(self.console, 1)
        body.addWidget(right)

        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 2)
        layout.addWidget(body, 1)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage(
            "PySide workbench — open G-code, connect, step"
        )

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("&File")
        open_gcode = QAction("&Open G-code…", self)
        open_gcode.setShortcut(QKeySequence.StandardKey.Open)
        open_gcode.triggered.connect(self.on_open_gcode)
        file_menu.addAction(open_gcode)
        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        machine_menu = self.menuBar().addMenu("&Machine")
        connect_action = QAction("Connect &remote", self)
        connect_action.triggered.connect(self.on_connect_remote)
        machine_menu.addAction(connect_action)

        open_action = QAction("&Open machine", self)
        open_action.triggered.connect(self.on_open_machine)
        machine_menu.addAction(open_action)

        close_action = QAction("&Close machine", self)
        close_action.triggered.connect(self.on_close_machine)
        machine_menu.addAction(close_action)

        refresh_action = QAction("&Refresh status", self)
        refresh_action.triggered.connect(self.on_refresh_status)
        machine_menu.addAction(refresh_action)

        program_menu = self.menuBar().addMenu("&Program")
        set_pc = QAction("Set &PC", self)
        set_pc.triggered.connect(self.on_set_pc)
        program_menu.addAction(set_pc)
        reset_pc = QAction("&Reset PC", self)
        reset_pc.triggered.connect(self.on_reset_pc)
        program_menu.addAction(reset_pc)
        goto_pc = QAction("&Goto PC", self)
        goto_pc.triggered.connect(self.on_goto_pc)
        program_menu.addAction(goto_pc)
        program_menu.addSeparator()
        break_action = QAction("Toggle &Breakpoint", self)
        break_action.setShortcut("F9")
        break_action.triggered.connect(self.on_break_toggle)
        program_menu.addAction(break_action)
        break_clear = QAction("Remove &All Breakpoints", self)
        break_clear.triggered.connect(self.on_break_clear)
        program_menu.addAction(break_clear)
        program_menu.addSeparator()
        run_action = QAction("&Run", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.on_run)
        program_menu.addAction(run_action)
        pause_action = QAction("Pa&use", self)
        pause_action.triggered.connect(self.on_pause)
        program_menu.addAction(pause_action)
        step_action = QAction("S&tep", self)
        step_action.setShortcut("F10")
        step_action.triggered.connect(self.on_step)
        program_menu.addAction(step_action)
        stop_action = QAction("St&op", self)
        stop_action.triggered.connect(self.on_stop)
        program_menu.addAction(stop_action)

        view_menu = self.menuBar().addMenu("&View")
        focus_cli = QAction("Focus &CLI", self)
        focus_cli.setShortcut(QKeySequence("Ctrl+L"))
        focus_cli.triggered.connect(self.console.focus_cli)
        view_menu.addAction(focus_cli)

        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.on_about)
        help_menu.addAction(about_action)

    def _load_remote_defaults(self):
        idx = gc.CONFIG_DATA.get("/remotes/Index", 0)
        host = gc.CONFIG_DATA.get(f"/remotes/remote{idx}/Host", "localhost") or "localhost"
        port = gc.CONFIG_DATA.get(f"/remotes/remote{idx}/WebSocketPort", 61803)
        self.host_edit.setText(str(host))
        self.port_edit.setText(str(port))

    # ------------------------------------------------------------------
    # G-code / PC
    # ------------------------------------------------------------------
    @Slot()
    def on_open_gcode(self):
        start = gc.STATE_DATA.gcodeFileName or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open G-code",
            start if os.path.isdir(os.path.dirname(start) or start) else os.path.expanduser("~"),
            "G-code (*.ngc *.nc *.gcode);;All files (*.*)",
        )
        if not path:
            return
        self.open_gcode_path(path)

    def open_gcode_path(self, path: str) -> bool:
        try:
            n = self.gcode.load_file(path)
        except OSError as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return False

        gc.STATE_DATA.gcodeFileName = path
        gc.STATE_DATA.gcodeFileLines = self.gcode.lines()
        gc.STATE_DATA.fileIsOpen = True
        gc.STATE_DATA.programCounter = 0
        gc.STATE_DATA.breakPoints = set()

        self.setWindowTitle(
            f"{os.path.basename(path)} — {vinfo.__appname__} (PySide)"
        )
        self.append_log(f"Opened {path} ({n} lines)")
        self.statusBar().showMessage(os.path.basename(path))
        self._update_connection_ui()
        return True

    def set_pc(self, pc: int | None = None):
        if pc is None:
            pc = self.gcode.selected_line()
        try:
            pc = int(pc)
        except (TypeError, ValueError):
            pc = 0
        if self.gcode.line_count() == 0:
            pc = 0
        else:
            pc = max(0, min(pc, self.gcode.line_count() - 1))
        gc.STATE_DATA.programCounter = pc
        self.gcode.set_pc(pc, scroll=True)

    @Slot()
    def on_set_pc(self):
        self.set_pc(self.gcode.selected_line())

    @Slot()
    def on_reset_pc(self):
        self.set_pc(0)

    @Slot()
    def on_goto_pc(self):
        self.gcode.goto_pc()

    @Slot()
    def on_break_toggle(self):
        if self.gcode.line_count() == 0:
            return
        if gc.STATE_DATA.swState not in (
            gc.STATE_IDLE,
            gc.STATE_BREAK,
            gc.STATE_PAUSE,
        ):
            self.append_log("Breakpoint: only when idle/break/pause.")
            return
        enabled = self.gcode.toggle_breakpoint(self.gcode.selected_line())
        gc.STATE_DATA.breakPoints = self.gcode.get_breakpoints()
        line = self.gcode.selected_line()
        self.append_log(
            f"Breakpoint {'set' if enabled else 'cleared'} at line {line + 1}"
        )

    @Slot(int, bool)
    def on_break_toggled(self, line: int, enabled: bool):
        gc.STATE_DATA.breakPoints = self.gcode.get_breakpoints()

    @Slot()
    def on_break_clear(self):
        self.gcode.clear_breakpoints()
        gc.STATE_DATA.breakPoints = set()
        self.append_log("All breakpoints cleared.")

    def _program_payload(self) -> dict:
        """Build dict for EV_CMD_STEP / RUN (same keys as wx)."""
        lines = self.gcode.lines()
        gc.STATE_DATA.gcodeFileLines = lines
        gc.STATE_DATA.breakPoints = self.gcode.get_breakpoints()
        payload = {
            "gcodePC": gc.STATE_DATA.programCounter,
            "breakPoints": self.gcode.get_breakpoints(),
        }
        if lines:
            if gc.STATE_DATA.gcodeFileName:
                payload["gcodeFileName"] = gc.STATE_DATA.gcodeFileName
            # Always send lines for spike simplicity (no MD5 cache yet)
            payload["gcodeLines"] = lines
        return payload

    def _can_run_or_step(self) -> bool:
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        return (
            self.bridge.is_backend_active()
            and machine_open
            and self.gcode.line_count() > 0
            and gc.STATE_DATA.swState
            in (gc.STATE_IDLE, gc.STATE_BREAK, gc.STATE_PAUSE)
        )

    @Slot()
    def on_run(self):
        if not self._can_run_or_step():
            self.append_log("Run: need open machine, G-code, and idle/break/pause.")
            return
        self.bridge.send_command(gc.EV_CMD_RUN, self._program_payload())
        self.gcode.goto_pc()
        self.append_log("Run started.")

    @Slot()
    def on_pause(self):
        if not self.bridge.is_backend_active():
            return
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        if not machine_open:
            return
        if gc.STATE_DATA.swState in (
            gc.STATE_IDLE,
            gc.STATE_PAUSE,
            gc.STATE_ABORT,
        ):
            self.append_log("Pause: nothing to pause.")
            return
        self.bridge.send_command(gc.EV_CMD_PAUSE)
        self.append_log("Pause requested.")

    @Slot()
    def on_step(self):
        if not self._can_run_or_step():
            self.append_log("Step: need open machine, G-code, and idle/break/pause.")
            return
        self.bridge.send_command(gc.EV_CMD_STEP, self._program_payload())
        self.gcode.goto_pc()

    @Slot()
    def on_stop(self):
        if self.bridge.is_backend_active():
            self.bridge.send_command(gc.EV_CMD_STOP)
            self.append_log("Stop requested.")

    # ------------------------------------------------------------------
    # Connection actions
    # ------------------------------------------------------------------
    @Slot()
    def on_connect_remote(self):
        host = self.host_edit.text().strip() or "localhost"
        try:
            port = int(self.port_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid port", "Port must be an integer.")
            return

        self.bridge.connect_remote(host, port)
        self._remote_connecting = True
        self._remote_connected = False
        self._update_connection_ui()

    @Slot()
    def on_disconnect_remote(self):
        self.bridge.disconnect_remote()
        self._update_connection_ui()

    @Slot()
    def on_open_machine(self):
        self.bridge.open_machine()

    @Slot()
    def on_close_machine(self):
        self.bridge.close_machine()

    @Slot()
    def on_open_local(self):
        if self.bridge.is_remote_connected():
            QMessageBox.information(
                self,
                "Remote active",
                "Disconnect remote before opening a local serial machine interface.",
            )
            return
        self.bridge.open_local()

    @Slot()
    def on_refresh_status(self):
        self.bridge.request_status()

    @Slot(str)
    def on_cli_submit(self, line: str):
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        if not machine_open or not self.bridge.is_backend_active():
            self.append_log("CLI: machine not open.")
            return
        if gc.STATE_DATA.swState == gc.STATE_RUN:
            self.append_log("CLI: blocked while program is running (stop first).")
            return
        if not self.bridge.send_line(line):
            self.append_log("CLI: send failed (no backend).")

    @Slot()
    def on_about(self):
        QMessageBox.about(
            self,
            "About gsat PySide workbench",
            f"{vinfo.__appname__} {vinfo.__version__}\n\n"
            "PySide6 workbench spike — thin client over existing gsat core.\n"
            "Classic wx UI remains the production desktop until cutover.",
        )

    # ------------------------------------------------------------------
    # Backend events (GUI thread)
    # ------------------------------------------------------------------
    @Slot(object)
    def on_backend_event(self, te):
        if te is None:
            return

        eid = te.event_id
        data = te.data

        if eid == gc.EV_DATA_STATUS:
            if isinstance(data, dict):
                if "sr" in data:
                    sr = data["sr"]
                    if isinstance(sr, dict):
                        if "stat" in sr:
                            gc.STATE_DATA.machineStatusString = sr["stat"]
                        self.dro_panel.update_from_status(sr)

                self.dro_panel.update_from_status(data)

                if "rx_data" in data and data["rx_data"]:
                    self.append_log(data["rx_data"])

                if "pc" in data:
                    try:
                        self.set_pc(int(data["pc"]))
                    except (TypeError, ValueError):
                        pass

                if "swstate" in data:
                    try:
                        gc.STATE_DATA.swState = int(data["swstate"])
                    except (TypeError, ValueError):
                        pass
                    self._update_connection_ui()

        elif eid == gc.EV_PC_UPDATE:
            try:
                self.set_pc(int(data))
            except (TypeError, ValueError):
                pass

        elif eid == gc.EV_DATA_IN:
            self.append_log(data)

        elif eid == gc.EV_DATA_OUT:
            self.append_log(f"> {data}")

        elif eid == gc.EV_SER_PORT_OPEN:
            self.append_log("Machine serial/port open.")
            self._machine_open = True
            gc.STATE_DATA.serialPortIsOpen = True
            self.bridge.request_status()
            self._update_connection_ui()

        elif eid == gc.EV_SER_PORT_CLOSE:
            self.append_log("Machine serial/port closed.")
            self._machine_open = False
            gc.STATE_DATA.serialPortIsOpen = False
            self.dro_panel.clear()
            self._update_connection_ui()

        elif eid == gc.EV_RMT_PORT_OPEN:
            msg = data if data else "Remote connected."
            self.append_log(str(msg).rstrip("\n"))
            self._remote_connecting = False
            self._remote_connected = True
            self.bridge.request_initial_remote_sync()
            self._update_connection_ui()

        elif eid == gc.EV_RMT_PORT_CLOSE:
            msg = data if data else "Remote disconnected."
            self.append_log(str(msg).rstrip("\n"))
            self._remote_connecting = False
            self._remote_connected = False
            self._machine_open = False
            gc.STATE_DATA.serialPortIsOpen = False
            self.dro_panel.clear()
            self._update_connection_ui()

        elif eid == gc.EV_RMT_HELLO:
            if data:
                self.append_log(data)

        elif eid == gc.EV_RMT_GOOD_BYE:
            if data:
                self.append_log(data)

        elif eid == gc.EV_RMT_CONFIG_DATA:
            self.append_log("Received remote config data.")

        elif eid == gc.EV_DEVICE_DETECTED:
            self.append_log("Device detected.")
            gc.STATE_DATA.deviceDetected = True

        elif eid == gc.EV_SW_STATE:
            try:
                gc.STATE_DATA.swState = int(data)
            except (TypeError, ValueError):
                pass
            self._update_connection_ui()

        elif eid == gc.EV_STEP_END:
            self._update_connection_ui()

        elif eid == gc.EV_RUN_END:
            self._update_connection_ui()

        elif eid == gc.EV_BRK_PT_STOP:
            self.append_log("Hit breakpoint.")
            self._update_connection_ui()

        elif eid == gc.EV_BRK_PT:
            # Remote/backend breakpoint set
            try:
                bps = set(data) if data is not None else set()
            except TypeError:
                bps = set()
            self.gcode.set_breakpoints(bps)
            gc.STATE_DATA.breakPoints = self.gcode.get_breakpoints()

        elif eid == gc.EV_BRK_PT_CHG:
            if self.bridge.is_backend_active():
                self.bridge.send_command(gc.EV_CMD_GET_BRK_PT)

        elif eid == gc.EV_ABORT:
            self.append_log(str(data) if data else "ABORT")
            if te.sender is self.bridge.remote_client or self._remote_connecting:
                self._remote_connecting = False
                self._remote_connected = False
                self._machine_open = False
                gc.STATE_DATA.serialPortIsOpen = False
                self.dro_panel.clear()
            elif te.sender is self.bridge.machif_progexec:
                self._machine_open = False
                gc.STATE_DATA.serialPortIsOpen = False
                self.dro_panel.clear()
            self._update_connection_ui()

        elif eid == gc.EV_EXIT:
            self.append_log("Backend thread exited.")
            was_remote = te.sender is self.bridge.remote_client
            was_local = (
                te.sender is self.bridge.machif_progexec
                and not self.bridge._use_remote
            )
            self.bridge.on_remote_exited(te.sender)
            self.bridge.on_local_exited(te.sender)
            self._remote_connecting = False
            if was_remote or not self.bridge.is_remote_connected():
                self._remote_connected = False
            if was_local or not self.bridge.is_backend_active():
                self._machine_open = False
                gc.STATE_DATA.serialPortIsOpen = False
            self._update_connection_ui()

        elif eid == gc.EV_GCODE_MD5:
            pass

        else:
            name = gc.EV_2STR_DICT.get(eid, str(eid))
            if self.cmd_line_options.verbose:
                self.append_log(f"[{name}] {data!r}")

    @Slot(str)
    def append_log(self, text):
        self.console.append_text(text)

    def _update_connection_ui(self):
        remote = self._remote_connected and self.bridge.is_remote_connected()
        connecting = self._remote_connecting
        backend = self.bridge.is_backend_active()
        host_info = self.bridge.remote_hostname()
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        has_gcode = self.gcode.line_count() > 0
        idleish = gc.STATE_DATA.swState in (
            gc.STATE_IDLE,
            gc.STATE_BREAK,
            gc.STATE_PAUSE,
        )

        parts = []
        if remote:
            parts.append(f"remote={host_info or 'connected'}")
        elif connecting:
            parts.append("remote=connecting…")
        else:
            parts.append("remote=off")

        if machine_open:
            parts.append("machine=open")
        elif backend and not remote and not connecting:
            parts.append("machine=local-starting")
        else:
            parts.append("machine=closed")

        parts.append(f"swState={gc.STATE_DATA.swState}")
        parts.append(f"stat={gc.STATE_DATA.machineStatusString}")
        parts.append(f"PC={gc.STATE_DATA.programCounter}")
        self.connection_label.setText("Connection: " + " | ".join(parts))

        client_alive = self.bridge.is_remote_connected()
        busy_remote = remote or connecting or client_alive
        self.btn_connect.setEnabled(not busy_remote)
        self.btn_disconnect.setEnabled(client_alive or connecting)
        self.btn_local.setEnabled(not busy_remote and not backend)
        self.btn_open.setEnabled(remote or (not busy_remote and not backend))
        self.btn_close.setEnabled(backend and not connecting)
        self.btn_refresh.setEnabled(backend and not connecting)

        self.host_edit.setEnabled(not busy_remote)
        self.port_edit.setEnabled(not busy_remote)

        cli_ok = machine_open and backend and gc.STATE_DATA.swState != gc.STATE_RUN
        self.console.set_cli_enabled(cli_ok)

        self.btn_set_pc.setEnabled(has_gcode and idleish)
        self.btn_reset_pc.setEnabled(has_gcode and idleish)
        self.btn_goto_pc.setEnabled(has_gcode)
        self.btn_break.setEnabled(has_gcode and idleish)
        self.btn_break_clear.setEnabled(has_gcode and idleish)
        can_run = machine_open and backend and has_gcode and idleish
        self.btn_run.setEnabled(can_run)
        self.btn_step.setEnabled(can_run)
        self.btn_pause.setEnabled(
            machine_open
            and backend
            and gc.STATE_DATA.swState
            not in (gc.STATE_IDLE, gc.STATE_PAUSE, gc.STATE_ABORT)
        )
        self.btn_stop.setEnabled(
            machine_open
            and backend
            and gc.STATE_DATA.swState
            not in (gc.STATE_IDLE, gc.STATE_ABORT)
        )

        self.statusBar().showMessage(" | ".join(parts))

    def closeEvent(self, event: QCloseEvent):
        self.bridge.shutdown(join_timeout=2.0)
        event.accept()
