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
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QToolBar,
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

        self._create_actions()
        self._build_ui()
        self._build_toolbars()
        self._build_menu()
        self._load_remote_defaults()
        self._load_layout()
        self._update_connection_ui()
        self.set_pc(0)

    # ------------------------------------------------------------------
    # Actions (shared by menus + toolbars — same pattern as wx)
    # ------------------------------------------------------------------
    def _create_actions(self):
        self.act_open_gcode = QAction("&Open…", self)
        self.act_open_gcode.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open_gcode.setToolTip("Open G-code file")
        self.act_open_gcode.triggered.connect(self.on_open_gcode)

        self.act_save = QAction("&Save", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.setToolTip("Save G-code file")
        self.act_save.triggered.connect(self.on_save_gcode)

        self.act_save_as = QAction("Save &As…", self)
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_as.triggered.connect(self.on_save_gcode_as)

        self.act_quit = QAction("E&xit", self)
        self.act_quit.setShortcut("Ctrl+Q")
        self.act_quit.triggered.connect(self.close)

        # File history (filled by _rebuild_recent_menu)
        self._file_history: list[str] = []
        self._recent_menu = None

        # Remote
        self.act_remote_connect = QAction("Connect remote", self)
        self.act_remote_connect.setToolTip("Connect to gsat-server (WebSocket)")
        self.act_remote_connect.triggered.connect(self.on_connect_remote)
        self.act_remote_disconnect = QAction("Disconnect", self)
        self.act_remote_disconnect.triggered.connect(self.on_disconnect_remote)

        # Machine
        self.act_machine_open = QAction("Open machine", self)
        self.act_machine_open.setToolTip("Open serial/machine on server or local")
        self.act_machine_open.triggered.connect(self.on_open_machine)
        self.act_machine_close = QAction("Close machine", self)
        self.act_machine_close.triggered.connect(self.on_close_machine)
        self.act_machine_refresh = QAction("Refresh", self)
        self.act_machine_refresh.setShortcut("Ctrl+R")
        self.act_machine_refresh.setToolTip("Request one status update")
        self.act_machine_refresh.triggered.connect(self.on_refresh_status)
        self.act_local = QAction("Local serial", self)
        self.act_local.setToolTip("Start local MachIfExecuteThread")
        self.act_local.triggered.connect(self.on_open_local)

        # Program
        self.act_run = QAction("Run", self)
        self.act_run.setShortcut("F5")
        self.act_run.setToolTip("Run from PC")
        self.act_run.triggered.connect(self.on_run)
        self.act_pause = QAction("Pause", self)
        self.act_pause.triggered.connect(self.on_pause)
        self.act_step = QAction("Step", self)
        self.act_step.setShortcut("F10")
        self.act_step.triggered.connect(self.on_step)
        self.act_stop = QAction("Stop", self)
        self.act_stop.triggered.connect(self.on_stop)
        self.act_break = QAction("Break", self)
        self.act_break.setShortcut("F9")
        self.act_break.setToolTip("Toggle breakpoint on selected line")
        self.act_break.triggered.connect(self.on_break_toggle)
        self.act_break_clear = QAction("Clear BP", self)
        self.act_break_clear.triggered.connect(self.on_break_clear)
        self.act_set_pc = QAction("Set PC", self)
        self.act_set_pc.triggered.connect(self.on_set_pc)
        self.act_reset_pc = QAction("Reset PC", self)
        self.act_reset_pc.triggered.connect(self.on_reset_pc)
        self.act_goto_pc = QAction("Goto PC", self)
        self.act_goto_pc.triggered.connect(self.on_goto_pc)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _make_dock(self, title: str, widget: QWidget, object_name: str) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(object_name)
        dock.setWidget(widget)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        return dock

    def _build_ui(self):
        # Content panels = docks; actions = toolbars (wx AUI model)
        self.setDockNestingEnabled(True)
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )

        # G-code is the center workspace (like wx CenterPane)
        self.gcode = GcodePanel()
        self.gcode.set_pc_requested.connect(self.set_pc)
        self.gcode.break_toggled.connect(self.on_break_toggled)
        self.setCentralWidget(self.gcode)

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
        self.splitDockWidget(self.dock_dro, self.dock_jog, Qt.Orientation.Vertical)

        self.resizeDocks([self.dock_console], [200], Qt.Orientation.Vertical)

        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self._status_detail = QLabel("")
        self._status_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        sb.addWidget(self._status_detail, 1)
        self.status_badge = QLabel("offline")
        self.status_badge.setObjectName("statusBadge")
        sb.addPermanentWidget(self.status_badge)

        self._docks = {
            "console": self.dock_console,
            "dro": self.dock_dro,
            "jog": self.dock_jog,
        }

    def _build_toolbars(self):
        """QToolBars for actions — not docks (matches wx MAIN/PROGRAM/MACHINE/REMOTE)."""
        # Main
        self.tb_main = QToolBar("Main")
        self.tb_main.setObjectName("toolbarMain")
        self.tb_main.setMovable(True)
        self.tb_main.addAction(self.act_open_gcode)
        self.tb_main.addAction(self.act_save)
        self.tb_main.addAction(self.act_save_as)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tb_main)

        # Program (run / PC / break)
        self.tb_program = QToolBar("Program")
        self.tb_program.setObjectName("toolbarProgram")
        self.tb_program.setMovable(True)
        for act in (
            self.act_run,
            self.act_pause,
            self.act_step,
            self.act_stop,
        ):
            self.tb_program.addAction(act)
        self.tb_program.addSeparator()
        self.tb_program.addAction(self.act_break)
        self.tb_program.addAction(self.act_break_clear)
        self.tb_program.addSeparator()
        self.tb_program.addAction(self.act_set_pc)
        self.tb_program.addAction(self.act_reset_pc)
        self.tb_program.addAction(self.act_goto_pc)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tb_program)

        # Machine
        self.tb_machine = QToolBar("Machine")
        self.tb_machine.setObjectName("toolbarMachine")
        self.tb_machine.setMovable(True)
        self.tb_machine.addAction(self.act_machine_open)
        self.tb_machine.addAction(self.act_machine_close)
        self.tb_machine.addAction(self.act_machine_refresh)
        self.tb_machine.addSeparator()
        self.tb_machine.addAction(self.act_local)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tb_machine)

        # Remote (host/port widgets + connect — lab-friendly)
        self.tb_remote = QToolBar("Remote")
        self.tb_remote.setObjectName("toolbarRemote")
        self.tb_remote.setMovable(True)
        self.tb_remote.addWidget(QLabel(" Host "))
        self.host_edit = QLineEdit()
        self.host_edit.setMinimumWidth(120)
        self.host_edit.setMaximumWidth(180)
        self.host_edit.setClearButtonEnabled(True)
        self.tb_remote.addWidget(self.host_edit)
        self.tb_remote.addWidget(QLabel(" Port "))
        self.port_edit = QLineEdit()
        self.port_edit.setMaximumWidth(64)
        self.tb_remote.addWidget(self.port_edit)
        self.tb_remote.addAction(self.act_remote_connect)
        self.tb_remote.addAction(self.act_remote_disconnect)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tb_remote)

        self._toolbars = {
            "main": self.tb_main,
            "program": self.tb_program,
            "machine": self.tb_machine,
            "remote": self.tb_remote,
        }

    def _build_menu(self):
        # File (wx: Open, Recent, Save, Save As, Exit)
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.act_open_gcode)
        self._recent_menu = file_menu.addMenu("Open &Recent")
        self._rebuild_recent_menu()
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        # Machine
        machine_menu = self.menuBar().addMenu("&Machine")
        machine_menu.addAction(self.act_machine_open)
        machine_menu.addAction(self.act_machine_close)
        machine_menu.addAction(self.act_machine_refresh)
        machine_menu.addSeparator()
        machine_menu.addAction(self.act_local)

        # Remote
        remote_menu = self.menuBar().addMenu("R&emote")
        remote_menu.addAction(self.act_remote_connect)
        remote_menu.addAction(self.act_remote_disconnect)

        # Run (wx name) — program controls
        run_menu = self.menuBar().addMenu("&Run")
        run_menu.addAction(self.act_run)
        run_menu.addAction(self.act_pause)
        run_menu.addAction(self.act_step)
        run_menu.addAction(self.act_stop)
        run_menu.addSeparator()
        run_menu.addAction(self.act_break)
        run_menu.addAction(self.act_break_clear)
        run_menu.addSeparator()
        run_menu.addAction(self.act_set_pc)
        run_menu.addAction(self.act_reset_pc)
        run_menu.addAction(self.act_goto_pc)

        # View
        view_menu = self.menuBar().addMenu("&View")
        focus_cli = QAction("Focus &CLI", self)
        focus_cli.setShortcut(QKeySequence("Ctrl+L"))
        focus_cli.triggered.connect(self.console.focus_cli)
        view_menu.addAction(focus_cli)
        view_menu.addSeparator()
        for label, key in (
            ("&Main Tool Bar", "main"),
            ("&Program Tool Bar", "program"),
            ("M&achine Tool Bar", "machine"),
            ("&Remote Tool Bar", "remote"),
        ):
            act = self._toolbars[key].toggleViewAction()
            act.setText(label)
            view_menu.addAction(act)
        view_menu.addSeparator()
        for key, dock in (
            ("&Console", "console"),
            ("Machine &Status", "dro"),
            ("Machine &Jogging", "jog"),
        ):
            act = self._docks[dock].toggleViewAction()
            act.setText(key)
            view_menu.addAction(act)
        view_menu.addSeparator()
        load_layout = QAction("&Load layout", self)
        load_layout.triggered.connect(self._load_layout)
        view_menu.addAction(load_layout)
        save_layout = QAction("S&ave layout", self)
        save_layout.triggered.connect(self._save_layout)
        view_menu.addAction(save_layout)
        reset_layout = QAction("R&eset layout", self)
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
    # File history (same config keys as wx FileHistory)
    # ------------------------------------------------------------------
    def _max_file_history(self) -> int:
        try:
            return int(
                gc.CONFIG_DATA.get("/mainApp/FileHistory/FilesMaxHistory", 10) or 10
            )
        except (TypeError, ValueError):
            return 10

    def _load_file_history(self) -> list[str]:
        """Load recent files from config (File1 = most recent, like wx)."""
        out: list[str] = []
        nmax = self._max_file_history()
        for i in range(1, nmax + 1):
            fn = gc.CONFIG_DATA.get(f"/mainApp/FileHistory/File{i}")
            if fn and isinstance(fn, str) and fn.strip():
                path = fn.strip()
                if path not in out:
                    out.append(path)
        self._file_history = out
        return out

    def _save_file_history(self) -> None:
        nmax = self._max_file_history()
        # Clear then write (File1 newest)
        for i in range(1, nmax + 1):
            path = self._file_history[i - 1] if i - 1 < len(self._file_history) else ""
            gc.CONFIG_DATA.set(f"/mainApp/FileHistory/File{i}", path)
        try:
            gc.CONFIG_DATA.save()
        except Exception:
            pass

    def _add_to_file_history(self, path: str) -> None:
        path = os.path.abspath(path)
        if path in self._file_history:
            self._file_history.remove(path)
        self._file_history.insert(0, path)
        nmax = self._max_file_history()
        self._file_history = self._file_history[:nmax]
        self._save_file_history()
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        if self._recent_menu is None:
            return
        self._recent_menu.clear()
        self._load_file_history()
        if not self._file_history:
            empty = QAction("(no recent files)", self)
            empty.setEnabled(False)
            self._recent_menu.addAction(empty)
            return
        for i, path in enumerate(self._file_history):
            # wx style: &0 path, &1 path, …
            label = f"&{i}  {path}"
            act = QAction(label, self)
            act.setData(path)
            act.triggered.connect(self._on_recent_file)
            self._recent_menu.addAction(act)
        self._recent_menu.addSeparator()
        clear_act = QAction("Clear recent files", self)
        clear_act.triggered.connect(self._clear_recent_files)
        self._recent_menu.addAction(clear_act)

    @Slot()
    def _on_recent_file(self):
        act = self.sender()
        if act is None:
            return
        path = act.data()
        if not path:
            return
        if not os.path.isfile(path):
            QMessageBox.warning(
                self,
                "File not found",
                f"The file doesn't exist.\n\nFile: {path}\n\n"
                "It will be removed from recent files.",
            )
            if path in self._file_history:
                self._file_history.remove(path)
                self._save_file_history()
                self._rebuild_recent_menu()
            return
        self.open_gcode_path(path)

    @Slot()
    def _clear_recent_files(self):
        self._file_history = []
        self._save_file_history()
        self._rebuild_recent_menu()

    # ------------------------------------------------------------------
    # G-code / PC
    # ------------------------------------------------------------------
    @Slot()
    def on_open_gcode(self):
        start = gc.STATE_DATA.gcodeFileName or os.path.expanduser("~")
        start_dir = start
        if start and not os.path.isdir(start):
            start_dir = os.path.dirname(start) or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a file",
            start_dir,
            "G-code (*.ngc *.nc *.gcode);;ngc (*.ngc);;nc (*.nc);;gcode (*.gcode);;All files (*.*)",
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

        path = os.path.abspath(path)
        gc.STATE_DATA.gcodeFileName = path
        gc.STATE_DATA.gcodeFileLines = self.gcode.lines()
        gc.STATE_DATA.fileIsOpen = True
        gc.STATE_DATA.programCounter = 0
        gc.STATE_DATA.breakPoints = set()

        self._add_to_file_history(path)

        self.setWindowTitle(
            f"{os.path.basename(path)} — {vinfo.__appname__} (PySide)"
        )
        self.append_log(f"Opened {path} ({n} lines)")
        self.statusBar().showMessage(os.path.basename(path))
        self._update_connection_ui()
        return True

    @Slot()
    def on_save_gcode(self):
        if not gc.STATE_DATA.fileIsOpen or not gc.STATE_DATA.gcodeFileName:
            self.on_save_gcode_as()
            return
        self._write_gcode_file(gc.STATE_DATA.gcodeFileName)

    @Slot()
    def on_save_gcode_as(self):
        start = gc.STATE_DATA.gcodeFileName or os.path.expanduser("~")
        start_dir = os.path.dirname(start) if start else os.path.expanduser("~")
        start_file = os.path.basename(start) if start else "untitled.ngc"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Create a file",
            os.path.join(start_dir, start_file),
            "G-code (*.ngc *.nc *.gcode);;All files (*.*)",
        )
        if not path:
            return
        if self._write_gcode_file(path):
            self._add_to_file_history(path)

    def _write_gcode_file(self, path: str) -> bool:
        try:
            # Optional backup like wx
            if (
                gc.CONFIG_DATA.get("/mainApp/BackupFile", False)
                and os.path.isfile(path)
            ):
                import shutil

                shutil.copyfile(path, path + "~")
            n = self.gcode.save_file(path)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        path = os.path.abspath(path)
        gc.STATE_DATA.gcodeFileName = path
        gc.STATE_DATA.gcodeFileLines = self.gcode.lines()
        gc.STATE_DATA.fileIsOpen = True
        self.setWindowTitle(
            f"{os.path.basename(path)} — {vinfo.__appname__} (PySide)"
        )
        self.append_log(f"Saved {path} ({n} lines)")
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
        self.act_remote_connect.setEnabled(not busy_remote)
        self.act_remote_disconnect.setEnabled(client_alive or connecting)
        self.act_local.setEnabled(not busy_remote and not backend)
        self.act_machine_open.setEnabled(remote or (not busy_remote and not backend))
        self.act_machine_close.setEnabled(backend and not connecting)
        self.act_machine_refresh.setEnabled(backend and not connecting)

        self.host_edit.setEnabled(not busy_remote)
        self.port_edit.setEnabled(not busy_remote)

        cli_ok = machine_open and backend and gc.STATE_DATA.swState != gc.STATE_RUN
        self.console.set_cli_enabled(cli_ok)

        jog_ok = machine_open and backend and gc.STATE_DATA.swState != gc.STATE_RUN
        self.jog.set_enabled(jog_ok)

        # Block open/save while streaming (like wx)
        busy_program = machine_open and gc.STATE_DATA.swState in (
            gc.STATE_RUN,
            gc.STATE_STEP,
        )
        self.act_open_gcode.setEnabled(not busy_program)
        self.act_save.setEnabled(has_gcode and not busy_program)
        self.act_save_as.setEnabled(has_gcode and not busy_program)
        if self._recent_menu is not None:
            self._recent_menu.setEnabled(not busy_program)

        self.act_set_pc.setEnabled(has_gcode and idleish)
        self.act_reset_pc.setEnabled(has_gcode and idleish)
        self.act_goto_pc.setEnabled(has_gcode)
        self.act_break.setEnabled(has_gcode and idleish)
        self.act_break_clear.setEnabled(has_gcode and idleish)
        can_run = machine_open and backend and has_gcode and idleish
        self.act_run.setEnabled(can_run)
        self.act_step.setEnabled(can_run)
        self.act_pause.setEnabled(
            machine_open
            and backend
            and gc.STATE_DATA.swState
            not in (gc.STATE_IDLE, gc.STATE_PAUSE, gc.STATE_ABORT)
        )
        self.act_stop.setEnabled(
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
        # Re-dock content panels; re-show toolbars
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_console)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_dro)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_jog)
        self.splitDockWidget(self.dock_dro, self.dock_jog, Qt.Orientation.Vertical)
        for d in self._docks.values():
            d.show()
        for tb in self._toolbars.values():
            tb.show()
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
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
