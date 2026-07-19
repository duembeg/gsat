"""----------------------------------------------------------------------------
    main_window.py

    Spike shell for the gsat PySide workbench:
    connect + DRO + console CLI + G-code / PC.
----------------------------------------------------------------------------"""
from __future__ import annotations

import base64
import logging
import os

from PySide6.QtCore import QByteArray, Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

import modules.config as gc
import modules.version_info as vinfo

from modules.pyside_workbench import theme
from modules.pyside_workbench.client_bridge import ClientBridge
from modules.pyside_workbench.console_panel import ConsolePanel
from modules.pyside_workbench.dro_panel import DroPanel
from modules.pyside_workbench.gcode_panel import GcodePanel
from modules.pyside_workbench.jog_panel import JogPanel


def _tool_strip(title: str) -> tuple[QFrame, QHBoxLayout]:
    """Labeled horizontal action strip (shared chrome for future panels)."""
    frame = QFrame()
    frame.setObjectName("toolbarStrip")
    outer = QHBoxLayout(frame)
    outer.setContentsMargins(8, 6, 8, 6)
    outer.setSpacing(6)
    if title:
        lbl = QLabel(title)
        lbl.setObjectName("sectionLabel")
        outer.addWidget(lbl)
    row = QHBoxLayout()
    row.setSpacing(4)
    outer.addLayout(row, 1)
    return frame, row


class MainWindow(QMainWindow):
    def __init__(self, cmd_line_options, parent=None):
        super().__init__(parent)
        self.cmd_line_options = cmd_line_options
        self.logger = logging.getLogger(__name__)

        self.setWindowTitle(f"{vinfo.__appname__} — PySide workbench")
        self.resize(1280, 800)

        self.bridge = ClientBridge(self)
        self.bridge.backend_event.connect(self.on_backend_event)
        self.bridge.log_message.connect(self.append_log)

        self._machine_open = False
        self._remote_connected = False
        self._remote_connecting = False

        self._build_ui()
        self._build_menu()
        self._load_remote_defaults()
        self._load_layout()
        self._update_connection_ui()
        self.set_pc(0)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _make_dock(self, title: str, widget: QWidget, object_name: str) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(object_name)
        dock.setWidget(widget)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.AllDockWidgetAreas
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        return dock

    def _build_ui(self):
        # Dockable workbench (Qt equivalent of wx AUI perspectives)
        self.setDockNestingEnabled(True)
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )

        # Top: tool strips as non-dock central chrome (always visible, height-limited)
        from PySide6.QtWidgets import QSizePolicy

        chrome = QWidget()
        chrome.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        chrome_layout = QVBoxLayout(chrome)
        chrome_layout.setContentsMargins(8, 8, 8, 4)
        chrome_layout.setSpacing(8)

        # --- Connection strip ---
        conn_frame, conn_row = _tool_strip("Remote")
        conn_row.addWidget(QLabel("Host"))
        self.host_edit = QLineEdit()
        self.host_edit.setMinimumWidth(140)
        self.host_edit.setMaximumWidth(220)
        conn_row.addWidget(self.host_edit)
        conn_row.addWidget(QLabel("Port"))
        self.port_edit = QLineEdit()
        self.port_edit.setMaximumWidth(72)
        conn_row.addWidget(self.port_edit)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setObjectName("btnPrimary")
        self.btn_connect.clicked.connect(self.on_connect_remote)
        conn_row.addWidget(self.btn_connect)
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self.on_disconnect_remote)
        conn_row.addWidget(self.btn_disconnect)
        conn_row.addSpacing(12)
        self.btn_open = QPushButton("Open machine")
        self.btn_open.clicked.connect(self.on_open_machine)
        conn_row.addWidget(self.btn_open)
        self.btn_close = QPushButton("Close machine")
        self.btn_close.clicked.connect(self.on_close_machine)
        conn_row.addWidget(self.btn_close)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setToolTip("Request one status update (no auto-poll)")
        self.btn_refresh.clicked.connect(self.on_refresh_status)
        conn_row.addWidget(self.btn_refresh)
        self.btn_local = QPushButton("Local serial")
        self.btn_local.setToolTip(
            "Start MachIfExecuteThread using machine settings from ~/.gsat.json"
        )
        self.btn_local.clicked.connect(self.on_open_local)
        conn_row.addWidget(self.btn_local)
        conn_row.addStretch(1)
        self.status_badge = QLabel("offline")
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        conn_row.addWidget(self.status_badge)
        chrome_layout.addWidget(conn_frame)

        # --- Program strip ---
        prog_frame, prog_row = _tool_strip("Program")
        self.btn_open_file = QPushButton("Open G-code…")
        self.btn_open_file.clicked.connect(self.on_open_gcode)
        prog_row.addWidget(self.btn_open_file)
        prog_row.addSpacing(8)
        self.btn_set_pc = QPushButton("Set PC")
        self.btn_set_pc.setToolTip("Set program counter to selected G-code line")
        self.btn_set_pc.clicked.connect(self.on_set_pc)
        prog_row.addWidget(self.btn_set_pc)
        self.btn_reset_pc = QPushButton("Reset PC")
        self.btn_reset_pc.clicked.connect(self.on_reset_pc)
        prog_row.addWidget(self.btn_reset_pc)
        self.btn_goto_pc = QPushButton("Goto PC")
        self.btn_goto_pc.clicked.connect(self.on_goto_pc)
        prog_row.addWidget(self.btn_goto_pc)
        self.btn_break = QPushButton("Break")
        self.btn_break.setToolTip("Toggle breakpoint on selected line (F9)")
        self.btn_break.clicked.connect(self.on_break_toggle)
        prog_row.addWidget(self.btn_break)
        self.btn_break_clear = QPushButton("Clear BP")
        self.btn_break_clear.setToolTip("Remove all breakpoints")
        self.btn_break_clear.clicked.connect(self.on_break_clear)
        prog_row.addWidget(self.btn_break_clear)
        prog_row.addSpacing(10)
        self.btn_run = QPushButton("Run")
        self.btn_run.setObjectName("btnPrimary")
        self.btn_run.setToolTip("Run program from PC (F5)")
        self.btn_run.clicked.connect(self.on_run)
        prog_row.addWidget(self.btn_run)
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.clicked.connect(self.on_pause)
        prog_row.addWidget(self.btn_pause)
        self.btn_step = QPushButton("Step")
        self.btn_step.setToolTip("Step one G-code line (F10)")
        self.btn_step.clicked.connect(self.on_step)
        prog_row.addWidget(self.btn_step)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("btnDanger")
        self.btn_stop.clicked.connect(self.on_stop)
        prog_row.addWidget(self.btn_stop)
        prog_row.addStretch(1)
        chrome_layout.addWidget(prog_frame)

        self.setCentralWidget(chrome)

        # --- Dockable panels (user-rearrangeable; saved like wx AUI) ---
        self.gcode = GcodePanel()
        self.gcode.set_pc_requested.connect(self.set_pc)
        self.gcode.break_toggled.connect(self.on_break_toggled)
        self.dock_gcode = self._make_dock("G-code", self.gcode, "dockGcode")
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_gcode)

        max_hist = 100
        try:
            max_hist = int(gc.CONFIG_DATA.get("/console/cli/CmdMaxHistory", 100))
        except (TypeError, ValueError):
            pass
        self.console = ConsolePanel(max_history=max_hist, load_saved=True)
        self.console.line_submitted.connect(self.on_cli_submit)
        self.dock_console = self._make_dock("Console", self.console, "dockConsole")
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_console)

        self.dro_panel = DroPanel()
        self.dock_dro = self._make_dock("Machine Status", self.dro_panel, "dockDro")
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_dro)

        self.jog = JogPanel()
        self.jog.jog_relative.connect(self.on_jog_relative)
        self.jog.jog_stop.connect(self.on_jog_stop)
        self.jog.home_axes.connect(self.on_home_axes)
        self.dock_jog = self._make_dock("Machine Jogging", self.jog, "dockJog")
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_jog)
        self.splitDockWidget(
            self.dock_dro, self.dock_jog, Qt.Orientation.Vertical
        )

        # Default sizes (overridden by saved layout when present)
        self.resizeDocks(
            [self.dock_gcode], [700], Qt.Orientation.Horizontal
        )
        self.resizeDocks(
            [self.dock_console], [200], Qt.Orientation.Vertical
        )

        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self._status_detail = QLabel("")
        self._status_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        sb.addWidget(self._status_detail, 1)

        self._docks = {
            "gcode": self.dock_gcode,
            "console": self.dock_console,
            "dro": self.dock_dro,
            "jog": self.dock_jog,
        }

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
        view_menu.addSeparator()
        for key, dock in (
            ("&G-code", "gcode"),
            ("&Console", "console"),
            ("Machine &Status", "dro"),
            ("Machine &Jogging", "jog"),
        ):
            act = self._docks[dock].toggleViewAction()
            act.setText(key)
            view_menu.addAction(act)
        view_menu.addSeparator()
        save_layout = QAction("&Save layout", self)
        save_layout.triggered.connect(self._save_layout)
        view_menu.addAction(save_layout)
        reset_layout = QAction("&Reset layout", self)
        reset_layout.triggered.connect(self._reset_layout)
        view_menu.addAction(reset_layout)

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

    @Slot(str, str, bool, object)
    def on_jog_relative(self, axis: str, step_str: str, rapid: bool, feed):
        if not self.bridge.is_backend_active():
            self.append_log("Jog: no machine backend.")
            return
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        if not machine_open:
            self.append_log("Jog: machine not open.")
            return
        if gc.STATE_DATA.swState == gc.STATE_RUN:
            self.append_log("Jog: blocked while program is running.")
            return
        payload = {str(axis).lower(): step_str}
        if rapid:
            cmd = gc.EV_CMD_JOG_RAPID_MOVE_RELATIVE
        else:
            cmd = gc.EV_CMD_JOG_MOVE_RELATIVE
            if feed is not None:
                payload["feed"] = feed
        self.bridge.send_command(cmd, payload)

    @Slot()
    def on_jog_stop(self):
        if self.bridge.is_backend_active():
            self.bridge.send_command(gc.EV_CMD_JOG_STOP)

    @Slot(dict)
    def on_home_axes(self, axes: dict):
        if not self.bridge.is_backend_active():
            self.append_log("Home: no machine backend.")
            return
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        if not machine_open:
            self.append_log("Home: machine not open.")
            return
        self.bridge.send_command(gc.EV_CMD_HOME, dict(axes))
        self.append_log(f"Home requested: {','.join(sorted(axes.keys())).upper()}")

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

        elif eid == gc.EV_GCODE_MSG:
            # Backend hits (MSG, …) during run/step, moves to STATE_BREAK,
            # and does not send the line to the machine. UI prompts like wx.
            msg = str(data).strip() if data is not None else ""
            self.append_log(f"** MSG: {msg}")
            # Backend does not always push EV_SW_STATE on MSG; UI may still
            # think we are RUN — capture before we force BREAK for controls.
            last_sw = gc.STATE_DATA.swState
            gc.STATE_DATA.swState = gc.STATE_BREAK
            self._update_connection_ui()

            if last_sw == gc.STATE_RUN:
                reply = QMessageBox.question(
                    self,
                    "G-Code Message",
                    f"{msg}\n\nContinue program?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.on_run()
            else:
                QMessageBox.information(self, "G-Code Message", msg or "(empty MSG)")

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
        parts.append(f"stat={gc.STATE_DATA.machineStatusString or '—'}")
        parts.append(f"PC={gc.STATE_DATA.programCounter}")

        # Badge: machine / software state first (must stay obvious)
        if machine_open and gc.STATE_DATA.machineStatusString:
            badge = str(gc.STATE_DATA.machineStatusString)
            bkey = theme.state_color_key(
                gc.STATE_DATA.machineStatusString, gc.STATE_DATA.swState
            )
        elif remote:
            badge, bkey = "remote", "remote"
        elif connecting:
            badge, bkey = "connecting", "unknown"
        else:
            badge, bkey = "offline", "offline"
        if gc.STATE_DATA.swState == gc.STATE_RUN:
            badge, bkey = "RUN", "run"
        elif gc.STATE_DATA.swState == gc.STATE_BREAK:
            badge, bkey = "BREAK", "break"
        elif gc.STATE_DATA.swState == gc.STATE_PAUSE:
            badge, bkey = "PAUSE", "pause"
        color = theme.STATE_COLORS.get(bkey, theme.STATE_COLORS["unknown"])
        self.status_badge.setText(badge)
        self.status_badge.setStyleSheet(
            f"QLabel#statusBadge {{ background: {color}; color: white;"
            f" border-radius: 10px; padding: 3px 10px; font-weight: 600; }}"
        )
        self._status_detail.setText("  ·  ".join(parts))

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

        jog_ok = machine_open and backend and gc.STATE_DATA.swState != gc.STATE_RUN
        self.jog.set_enabled(jog_ok)

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

    # ------------------------------------------------------------------
    # Layout persistence (Qt saveState ≈ wx AUI perspective)
    # ------------------------------------------------------------------
    _LAYOUT_KEY = "/pysideWorkbench/Layout/Default"

    def _save_layout(self):
        """Save dock arrangement + window geometry to config (like wx SaveLayoutData)."""
        try:
            state_b64 = base64.b64encode(bytes(self.saveState())).decode("ascii")
            geo_b64 = base64.b64encode(bytes(self.saveGeometry())).decode("ascii")
            gc.CONFIG_DATA.set(f"{self._LAYOUT_KEY}/State", state_b64)
            gc.CONFIG_DATA.set(f"{self._LAYOUT_KEY}/Geometry", geo_b64)
            gc.CONFIG_DATA.save()
            self.append_log("Layout saved.")
        except Exception as exc:
            self.append_log(f"Layout save failed: {exc}")

    def _load_layout(self):
        """Restore docks/geometry if previously saved."""
        try:
            geo_b64 = gc.CONFIG_DATA.get(f"{self._LAYOUT_KEY}/Geometry", "") or ""
            state_b64 = gc.CONFIG_DATA.get(f"{self._LAYOUT_KEY}/State", "") or ""
            if geo_b64:
                self.restoreGeometry(QByteArray(base64.b64decode(geo_b64)))
            if state_b64:
                self.restoreState(QByteArray(base64.b64decode(state_b64)))
        except Exception as exc:
            self.logger.warning("Layout load failed: %s", exc)

    def _reset_layout(self):
        """Clear saved layout and restore a sensible default dock arrangement."""
        try:
            gc.CONFIG_DATA.set(f"{self._LAYOUT_KEY}/State", "")
            gc.CONFIG_DATA.set(f"{self._LAYOUT_KEY}/Geometry", "")
            gc.CONFIG_DATA.save()
        except Exception:
            pass
        # Re-dock to defaults
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_gcode)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_console)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_dro)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_jog)
        self.splitDockWidget(
            self.dock_dro, self.dock_jog, Qt.Orientation.Vertical
        )
        for d in self._docks.values():
            d.show()
        self.append_log("Layout reset to defaults.")

    def closeEvent(self, event: QCloseEvent):
        # Layout is saved only via View → Save layout (not on quit), so a
        # messy rearrange is not persisted by accident.
        try:
            self.console.save_history_to_config()
        except Exception:
            pass
        self.bridge.shutdown(join_timeout=2.0)
        event.accept()
