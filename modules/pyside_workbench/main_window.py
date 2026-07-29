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
    QDialog,
    QDockWidget,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
    QToolBar,
    QToolButton,
    QWidget,
)

import modules.config as gc
import modules.version_info as vinfo

from modules.pyside_workbench import theme
from modules.pyside_workbench.client_bridge import ClientBridge
from modules.pyside_workbench.console_panel import ConsolePanel
from modules.pyside_workbench.dro_panel import DroPanel
from modules.pyside_workbench.gcode_panel import GcodePanel
from modules.pyside_workbench import icons as wb_icons
from modules.pyside_workbench.jog_panel import JogPanel
from modules.pyside_workbench.settings_dialog import SettingsDialog


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

        self.act_settings = QAction("&Settings…", self)
        self.act_settings.setShortcut(QKeySequence.StandardKey.Preferences)
        self.act_settings.setToolTip("Application and machine settings")
        self.act_settings.triggered.connect(self.on_settings)

        self.act_remote_settings = QAction("Remote settings…", self)
        self.act_remote_settings.setToolTip(
            "Edit machine/remote config from the connected server (wx Remote Settings)"
        )
        self.act_remote_settings.triggered.connect(self.on_remote_settings)

        self.act_quit = QAction("E&xit", self)
        self.act_quit.setShortcut("Ctrl+Q")
        self.act_quit.triggered.connect(self.close)

        # Last remote config payload (EV_RMT_CONFIG_DATA), if any
        self._remote_config_data = None

        # File history (File menu + Open toolbar split-button dropdown)
        self._file_history: list[str] = []
        self._recent_menu = None  # File → Open Recent
        self._open_dropdown_menu = QMenu(self)  # toolbar Open ▾ (wx SetToolDropDown)
        self.btn_open = None  # set in _build_toolbars

        # Remote — one toggle (remote.png, not machine plugs); tooltip flips with state
        self.act_remote = QAction("Connect remote", self)
        self.act_remote.setCheckable(True)
        self.act_remote.setToolTip("Connect remote — WebSocket to gsat-server")
        self.act_remote.triggered.connect(self.on_remote_toggle)

        # Machine — one Connect toggle (wx); icon + tooltip flip with open state
        self.act_machine_connect = QAction("&Connect", self)
        self.act_machine_connect.setCheckable(True)
        self.act_machine_connect.setToolTip(
            "Machine Connect — open serial/machine session"
        )
        self.act_machine_connect.triggered.connect(self.on_machine_connect)
        self.act_machine_refresh = QAction("Refresh", self)
        self.act_machine_refresh.setShortcut("Ctrl+R")
        self.act_machine_refresh.setToolTip("Request one status update")
        self.act_machine_refresh.triggered.connect(self.on_refresh_status)
        self.act_cycle_start = QAction("Cycle Start", self)
        self.act_cycle_start.setToolTip("Machine cycle start / resume after feed hold")
        self.act_cycle_start.triggered.connect(self.on_cycle_start)
        self.act_feed_hold = QAction("Feed Hold", self)
        self.act_feed_hold.setToolTip("Machine feed hold")
        self.act_feed_hold.triggered.connect(self.on_feed_hold)
        self.act_queue_flush = QAction("Queue Flush", self)
        self.act_queue_flush.setToolTip("Flush planner / serial queue")
        self.act_queue_flush.triggered.connect(self.on_queue_flush)
        self.act_machine_reset = QAction("Reset", self)
        self.act_machine_reset.setToolTip("Soft-reset the controller")
        self.act_machine_reset.triggered.connect(self.on_machine_reset)
        self.act_clear_alarm = QAction("Clear Alarm", self)
        self.act_clear_alarm.setToolTip("Clear controller alarm lock")
        self.act_clear_alarm.triggered.connect(self.on_clear_alarm)
        self.act_abort = QAction("Abort", self)
        self.act_abort.setToolTip("Feed hold + stop program (emergency-ish stop)")
        self.act_abort.triggered.connect(self.on_abort)
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
        self.act_break_clear = QAction("Clear all breakpoints", self)
        self.act_break_clear.setToolTip("Clear all breakpoints")
        self.act_break_clear.triggered.connect(self.on_break_clear)
        self.act_set_pc = QAction("Set PC", self)
        self.act_set_pc.triggered.connect(self.on_set_pc)
        self.act_reset_pc = QAction("Reset PC", self)
        self.act_reset_pc.triggered.connect(self.on_reset_pc)
        self.act_goto_pc = QAction("Goto PC", self)
        self.act_goto_pc.triggered.connect(self.on_goto_pc)

        self._apply_action_icons()

    def _apply_action_icons(self):
        """Attach existing gsat PNGs (same set as wx toolbars)."""
        for act, name in (
            (self.act_open_gcode, "open"),
            (self.act_save, "save"),
            (self.act_save_as, "save"),
            (self.act_run, "run"),
            (self.act_pause, "pause"),
            (self.act_step, "step"),
            (self.act_stop, "stop"),
            (self.act_break, "break"),
            (self.act_break_clear, "break_clear"),
            (self.act_set_pc, "set_pc"),
            (self.act_reset_pc, "reset_pc"),
            (self.act_goto_pc, "goto_pc"),
            (self.act_machine_refresh, "refresh"),
            (self.act_cycle_start, "cycle_start"),
            (self.act_feed_hold, "feed_hold"),
            (self.act_queue_flush, "queue_flush"),
            (self.act_machine_reset, "machine_reset"),
            (self.act_clear_alarm, "clear_alarm"),
            (self.act_abort, "abort"),
            (self.act_local, "local"),
            (self.act_remote, "remote"),
            (self.act_settings, "settings"),
            (self.act_remote_settings, "remote_settings"),
        ):
            wb_icons.apply_action_icon(act, name)

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

    def _apply_default_dock_arrangement(self) -> None:
        """Default like wx: G-code center, Console under center only, DRO|Jog right column.

        Qt dock *corners* control whether the bottom dock is a full-width row
        or only under the center (column-style with the right stack). User can
        still drag docks to other areas (full-width bottom, left, float, etc.).
        """
        # Right column owns top/bottom-right → full-height right stack;
        # bottom dock stays under central (G-code) only — wx column look.
        self.setCorner(
            Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setCorner(
            Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setCorner(
            Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.setCorner(
            Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.BottomDockWidgetArea
        )

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_console)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_dro)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_jog)
        self.splitDockWidget(self.dock_dro, self.dock_jog, Qt.Orientation.Vertical)

        self.dock_console.show()
        self.dock_dro.show()
        self.dock_jog.show()
        self.resizeDocks([self.dock_console], [220], Qt.Orientation.Vertical)
        self.resizeDocks(
            [self.dock_dro, self.dock_jog], [400, 280], Qt.Orientation.Vertical
        )

    def _build_ui(self):
        """Dockable panels (wx AUI-like): toolbars for actions, docks for content."""
        self.setDockNestingEnabled(True)
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.GroupedDragging
        )

        # G-code is the center workspace (like wx CenterPane — not a dock)
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

        self.dro_panel = DroPanel()
        self.dro_panel.move_to_requested.connect(self.on_dro_move_to)
        self.dro_panel.home_axis_requested.connect(self.on_dro_home_axis)
        self.dro_panel.zero_axis_requested.connect(self.on_dro_zero_axis)
        self.dro_panel.set_axis_requested.connect(self.on_dro_set_axis)
        self.dock_dro = self._make_dock("Machine Status", self.dro_panel, "dockDro")

        self.jog = JogPanel()
        self.jog.jog_relative.connect(self.on_jog_relative)
        self.jog.jog_stop.connect(self.on_jog_stop)
        self.jog.home_axes.connect(self.on_home_axes)
        self.dock_jog = self._make_dock("Machine Jogging", self.jog, "dockJog")

        self._apply_default_dock_arrangement()

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

    def _style_action_toolbar(self, tb: QToolBar) -> None:
        """Icon-first toolbars like classic wx (tooltips keep the labels)."""
        tb.setIconSize(wb_icons.TOOLBAR_ICON_SIZE)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        tb.setMovable(True)

    def _build_toolbars(self):
        """QToolBars for actions — not docks (matches wx MAIN/PROGRAM/MACHINE/REMOTE)."""
        # Main — wx app toolbar: icon + text; Open is split (▾ = recent)
        self.tb_main = QToolBar("Main")
        self.tb_main.setObjectName("toolbarMain")
        self.tb_main.setIconSize(wb_icons.TOOLBAR_ICON_SIZE)
        self.tb_main.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.tb_main.setMovable(True)
        self.btn_open = QToolButton(self)
        self.btn_open.setObjectName("btnOpenGcode")
        self.btn_open.setDefaultAction(self.act_open_gcode)
        self.btn_open.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.btn_open.setMenu(self._open_dropdown_menu)
        self.btn_open.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_open.setIconSize(wb_icons.TOOLBAR_ICON_SIZE)
        self.btn_open.setToolTip(
            "Open G-code file — arrow shows recent files (same as classic wx)"
        )
        self.tb_main.addWidget(self.btn_open)
        self.tb_main.addAction(self.act_save)
        self.tb_main.addAction(self.act_save_as)
        self.tb_main.addSeparator()
        self.tb_main.addAction(self.act_settings)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tb_main)
        self._rebuild_recent_menu()

        # Program (run / PC / break)
        self.tb_program = QToolBar("Program")
        self.tb_program.setObjectName("toolbarProgram")
        self._style_action_toolbar(self.tb_program)
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

        # Machine (wx: Connect toggle + refresh + cycle/hold/flush/reset/clear/abort)
        self.tb_machine = QToolBar("Machine")
        self.tb_machine.setObjectName("toolbarMachine")
        self._style_action_toolbar(self.tb_machine)
        self.tb_machine.addAction(self.act_machine_connect)
        self.tb_machine.addAction(self.act_machine_refresh)
        self.tb_machine.addSeparator()
        for act in (
            self.act_cycle_start,
            self.act_feed_hold,
            self.act_queue_flush,
            self.act_machine_reset,
            self.act_clear_alarm,
            self.act_abort,
        ):
            self.tb_machine.addAction(act)
        self.tb_machine.addSeparator()
        self.tb_machine.addAction(self.act_local)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tb_machine)

        # Remote (host/port widgets + connect — lab-friendly)
        self.tb_remote = QToolBar("Remote")
        self.tb_remote.setObjectName("toolbarRemote")
        # Keep host/port labels readable; action buttons still use icons.
        self.tb_remote.setIconSize(wb_icons.TOOLBAR_ICON_SIZE)
        self.tb_remote.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.tb_remote.setMovable(True)
        self.tb_remote.addWidget(QLabel(" Host "))
        self.host_edit = QLineEdit()
        self.host_edit.setMinimumWidth(120)
        self.host_edit.setMaximumWidth(180)
        # No clear-button "x" — looks misaligned on the toolbar; select-all + type is fine
        self.tb_remote.addWidget(self.host_edit)
        self.tb_remote.addWidget(QLabel(" Port "))
        self.port_edit = QLineEdit()
        self.port_edit.setMaximumWidth(64)
        self.tb_remote.addWidget(self.port_edit)
        self.tb_remote.addAction(self.act_remote)
        self.tb_remote.addAction(self.act_remote_settings)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tb_remote)

        self._toolbars = {
            "main": self.tb_main,
            "program": self.tb_program,
            "machine": self.tb_machine,
            "remote": self.tb_remote,
        }
        # Tooltips already set; ensure icon-only buttons still show status tips
        for tb in self._toolbars.values():
            for btn in tb.findChildren(QToolButton):
                act = btn.defaultAction()
                if act is not None and act.toolTip():
                    btn.setToolTip(act.toolTip())

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
        file_menu.addAction(self.act_settings)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        # Machine
        machine_menu = self.menuBar().addMenu("&Machine")
        machine_menu.addAction(self.act_machine_connect)
        machine_menu.addAction(self.act_machine_refresh)
        machine_menu.addSeparator()
        machine_menu.addAction(self.act_cycle_start)
        machine_menu.addAction(self.act_feed_hold)
        machine_menu.addAction(self.act_queue_flush)
        machine_menu.addAction(self.act_machine_reset)
        machine_menu.addAction(self.act_clear_alarm)
        machine_menu.addSeparator()
        machine_menu.addAction(self.act_abort)
        machine_menu.addSeparator()
        machine_menu.addAction(self.act_local)

        # Remote
        remote_menu = self.menuBar().addMenu("R&emote")
        remote_menu.addAction(self.act_remote)
        remote_menu.addAction(self.act_remote_settings)

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

    def _populate_recent_entries(self, menu: QMenu, *, include_clear: bool) -> None:
        """Fill a menu with numbered recent paths (wx FileHistory / dropdown style)."""
        menu.clear()
        if not self._file_history:
            empty = QAction("(no recent files)", self)
            empty.setEnabled(False)
            menu.addAction(empty)
            return
        for i, path in enumerate(self._file_history):
            # wx: "&0 path", "&1 path", …
            label = f"&{i}  {path}"
            act = QAction(label, self)
            act.setData(path)
            act.triggered.connect(self._on_recent_file)
            menu.addAction(act)
        if include_clear:
            menu.addSeparator()
            clear_act = QAction("Clear recent files", self)
            clear_act.triggered.connect(self._clear_recent_files)
            menu.addAction(clear_act)

    def _rebuild_recent_menu(self) -> None:
        """Refresh File → Open Recent and toolbar Open ▾ from config history."""
        self._load_file_history()
        if self._recent_menu is not None:
            self._populate_recent_entries(self._recent_menu, include_clear=True)
        # Toolbar dropdown mirrors wx AUI open dropdown (paths only, no Clear)
        self._populate_recent_entries(self._open_dropdown_menu, include_clear=False)

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
        # scroll=None → honor /code/AutoScroll (Always / On Goto PC / …)
        self.gcode.set_pc(pc, scroll=None)

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

    def _dro_cmd_ready(self) -> bool:
        """wx DRO clicks: machine open, backend up, not streaming program."""
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        if not machine_open or not self.bridge.is_backend_active():
            return False
        if gc.STATE_DATA.swState == gc.STATE_RUN:
            return False
        return True

    @Slot(str, float)
    def on_dro_move_to(self, axis: str, value: float):
        """Absolute move to DRO-entered position (wx number-field click)."""
        if not self._dro_cmd_ready():
            self.append_log("DRO move: machine not ready.")
            return
        ax = str(axis).lower()
        payload: dict = {ax: value}
        rapid = bool(getattr(gc.STATE_DATA, "joggingRapid", False))
        if rapid:
            self.bridge.send_command(gc.EV_CMD_RAPID_MOVE, payload)
            self.append_log(f"DRO rapid move {ax.upper()}={value}")
        else:
            feed = getattr(gc.STATE_DATA, "joggingFeedRate", None)
            if feed is None:
                try:
                    feed = float(gc.CONFIG_DATA.get("/jogging/JogFeedRate", 1000) or 1000)
                except (TypeError, ValueError):
                    feed = 1000.0
            payload["feed"] = feed
            self.bridge.send_command(gc.EV_CMD_MOVE, payload)
            self.append_log(f"DRO move {ax.upper()}={value} F{feed}")

    @Slot(str)
    def on_dro_home_axis(self, axis: str):
        if not self._dro_cmd_ready():
            self.append_log("DRO home: machine not ready.")
            return
        ax = str(axis).lower()
        self.bridge.send_command(gc.EV_CMD_HOME, {ax: 0})
        self.append_log(f"DRO home {ax.upper()}")

    @Slot(str)
    def on_dro_zero_axis(self, axis: str):
        """Work-zero current position on axis (SET_AXIS 0), not a move."""
        if not self._dro_cmd_ready():
            self.append_log("DRO zero: machine not ready.")
            return
        ax = str(axis).lower()
        self.bridge.send_command(gc.EV_CMD_SET_AXIS, {ax: 0})
        self.append_log(f"DRO zero {ax.upper()} (set work to 0)")

    @Slot(str, float)
    def on_dro_set_axis(self, axis: str, value: float):
        """Set work coordinate without moving (wx Set to value)."""
        if not self._dro_cmd_ready():
            self.append_log("DRO set axis: machine not ready.")
            return
        ax = str(axis).lower()
        self.bridge.send_command(gc.EV_CMD_SET_AXIS, {ax: value})
        self.append_log(f"DRO set {ax.upper()}={value} (work coord)")

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
    def on_remote_toggle(self):
        """One control: connect when offline, disconnect when up or connecting."""
        client_alive = self.bridge.is_remote_connected()
        if self._remote_connected or self._remote_connecting or client_alive:
            self.on_disconnect_remote()
        else:
            self.on_connect_remote()
        self._update_connection_ui()

    def _sync_remote_affordance(self, *, remote: bool, connecting: bool) -> None:
        """remote.png always (not machine plugs); tooltip/check flip with state."""
        wb_icons.apply_action_icon(self.act_remote, "remote")
        if connecting:
            self.act_remote.setToolTip(
                "Disconnect remote — cancel connection attempt"
            )
            self.act_remote.setChecked(True)
            self.act_remote.setText("Disconnect remote")
        elif remote:
            self.act_remote.setToolTip(
                "Disconnect remote — leave gsat-server WebSocket"
            )
            self.act_remote.setChecked(True)
            self.act_remote.setText("Disconnect remote")
        else:
            self.act_remote.setToolTip(
                "Connect remote — WebSocket to gsat-server"
            )
            self.act_remote.setChecked(False)
            self.act_remote.setText("Connect remote")

    @Slot()
    def on_open_machine(self):
        """Open machine session (remote EV_CMD_OPEN or local thread)."""
        self.bridge.open_machine()

    @Slot()
    def on_close_machine(self):
        """Close machine session (remote EV_CMD_CLOSE or local exit)."""
        self.bridge.close_machine()

    @Slot()
    def on_machine_connect(self):
        """wx Machine Connect: toggle open/close; UI state comes from backend events."""
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        if machine_open:
            self.on_close_machine()
        else:
            self.on_open_machine()
        # Icon/check/tooltip refresh on EV_SER_PORT_*; don't force from click alone.
        self._update_connection_ui()

    def _sync_machine_connect_affordance(self, machine_open: bool) -> None:
        """Flip Connect icon + tooltip so they match the live session state."""
        if machine_open:
            wb_icons.apply_action_icon(self.act_machine_connect, "machine_open")
            self.act_machine_connect.setToolTip(
                "Machine Disconnect — close serial/machine session"
            )
            self.act_machine_connect.setChecked(True)
        else:
            wb_icons.apply_action_icon(self.act_machine_connect, "machine_close")
            self.act_machine_connect.setToolTip(
                "Machine Connect — open serial/machine session"
            )
            self.act_machine_connect.setChecked(False)

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

    def _machine_cmd_ready(self) -> bool:
        """True when backend is up and machine serial/session is open (wx rule)."""
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        return bool(machine_open and self.bridge.is_backend_active())

    def _send_machine_cmd(self, event_id, label: str) -> bool:
        if not self._machine_cmd_ready():
            self.append_log(f"{label}: machine not open.")
            return False
        self.bridge.send_command(event_id)
        self.append_log(f"{label} requested.")
        return True

    @Slot()
    def on_cycle_start(self):
        self._send_machine_cmd(gc.EV_CMD_CYCLE_START, "Cycle Start")

    @Slot()
    def on_feed_hold(self):
        self._send_machine_cmd(gc.EV_CMD_FEED_HOLD, "Feed Hold")

    @Slot()
    def on_queue_flush(self):
        self._send_machine_cmd(gc.EV_CMD_QUEUE_FLUSH, "Queue Flush")

    @Slot()
    def on_machine_reset(self):
        self._send_machine_cmd(gc.EV_CMD_RESET, "Reset")

    @Slot()
    def on_clear_alarm(self):
        self._send_machine_cmd(gc.EV_CMD_CLEAR_ALARM, "Clear Alarm")

    @Slot()
    def on_abort(self):
        """wx Abort: feed hold on the controller, then stop program execution."""
        if not self._machine_cmd_ready():
            self.append_log("Abort: machine not open.")
            return
        self.bridge.send_command(gc.EV_CMD_FEED_HOLD)
        self.bridge.send_command(gc.EV_CMD_STOP)
        self.append_log(
            "Abort: feed-hold + stop sent "
            "(use Cycle Start to resume motion on the controller)."
        )

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

    @Slot()
    def on_settings(self):
        """Local settings (wx OnSettings) — full notebook, local CONFIG_DATA."""
        if gc.CONFIG_DATA is None:
            QMessageBox.warning(self, "Settings", "Config is not loaded.")
            return
        old_port = gc.CONFIG_DATA.get("/machine/Port")
        old_baud = gc.CONFIG_DATA.get("/machine/Baud")
        dlg = SettingsDialog(self, config_data=gc.CONFIG_DATA)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            gc.CONFIG_DATA.save()
        except Exception as exc:
            self.append_log(f"Settings save failed: {exc}")
            QMessageBox.warning(self, "Settings", f"Save failed:\n{exc}")
            return
        self._apply_settings_to_ui()
        # Notify local backend of config change (wx)
        if (
            self.bridge.is_backend_active()
            and not self.bridge.is_remote_connected()
        ):
            self.bridge.send_command(gc.EV_CMD_UPDATE_CONFIG)
        # Re-open machine if port/baud changed while open (wx)
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        if machine_open and (
            old_port != gc.CONFIG_DATA.get("/machine/Port")
            or old_baud != gc.CONFIG_DATA.get("/machine/Baud")
        ):
            self.append_log("Port/baud changed — closing machine session.")
            self.on_close_machine()
        self.append_log("Settings saved.")
        self._update_connection_ui()

    @Slot()
    def on_remote_settings(self):
        """Server machine/remote config (wx OnRemoteSettings)."""
        if not self.bridge.is_remote_connected():
            QMessageBox.information(
                self,
                "Remote settings",
                "Connect to a remote server first.",
            )
            return
        if self._remote_config_data is None:
            self.bridge.send_command(gc.EV_CMD_GET_CONFIG)
            QMessageBox.information(
                self,
                "Remote settings",
                "Requested server config.\n"
                "Open Remote settings again after the console shows "
                "“Received remote config data.”",
            )
            return
        dlg = SettingsDialog(
            self,
            config_data=gc.CONFIG_DATA,
            config_remote_data=self._remote_config_data,
            title="Remote Settings",
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.bridge.send_command(gc.EV_CMD_UPDATE_CONFIG, self._remote_config_data)
        self.append_log("Remote settings sent to server.")

    def _apply_settings_to_ui(self) -> None:
        """Push a subset of settings into live widgets after local save."""
        # Remote toolbar host/port from profile
        try:
            idx = int(gc.CONFIG_DATA.get("/remotes/Index", 0) or 0)
            host = gc.CONFIG_DATA.get(f"/remotes/remote{idx}/Host", "") or ""
            port = gc.CONFIG_DATA.get(f"/remotes/remote{idx}/WebSocketPort", 61803)
            if not self.bridge.is_remote_connected() and not self._remote_connecting:
                self.host_edit.setText(str(host))
                self.port_edit.setText(str(port))
        except Exception:
            pass
        # Jog defaults
        try:
            feed = float(gc.CONFIG_DATA.get("/jogging/JogFeedRate", 1000) or 1000)
            self.jog.feed_spin.setValue(feed)
            rapid = bool(gc.CONFIG_DATA.get("/jogging/JogRapid", False))
            self.jog.rapid_check.setChecked(rapid)
            gc.STATE_DATA.joggingFeedRate = feed
            gc.STATE_DATA.joggingRapid = rapid
        except Exception:
            pass
        # G-code colors (highlighter re-reads config on next open; refresh style now)
        try:
            bg = gc.CONFIG_DATA.get("/code/WindowBackground", "#FFFFFF") or "#FFFFFF"
            fg = gc.CONFIG_DATA.get("/code/WindowForeground", "#000000") or "#000000"
            self.gcode.editor.setStyleSheet(
                f"QPlainTextEdit {{ background: {bg}; color: {fg}; }}"
            )
        except Exception:
            pass
        try:
            self.gcode.reload_auto_scroll_setting()
        except Exception:
            pass

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
            # Keep for Remote Settings dialog (wx configRemoteData)
            self._remote_config_data = data
            self._update_connection_ui()

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
        # Always interactive: offline → connect; up/connecting → disconnect
        self.act_remote.setEnabled(True)
        self._sync_remote_affordance(remote=remote, connecting=connecting)
        self.act_remote_settings.setEnabled(remote or client_alive)
        self.act_local.setEnabled(not busy_remote and not backend)
        # Connect toggle: open when closed (remote or free local); close when open
        can_open = remote or (not busy_remote and not backend)
        can_close = backend and not connecting
        self.act_machine_connect.setEnabled(
            not connecting and (can_open or can_close)
        )
        self._sync_machine_connect_affordance(machine_open)
        self.act_machine_refresh.setEnabled(backend and not connecting)

        # Controller-side machine ops (wx: enabled when serial/session open)
        machine_cmd_ok = machine_open and backend and not connecting
        self.act_cycle_start.setEnabled(machine_cmd_ok)
        self.act_feed_hold.setEnabled(machine_cmd_ok)
        self.act_queue_flush.setEnabled(machine_cmd_ok)
        self.act_machine_reset.setEnabled(machine_cmd_ok)
        self.act_clear_alarm.setEnabled(machine_cmd_ok)
        self.act_abort.setEnabled(machine_cmd_ok)

        self.host_edit.setEnabled(not busy_remote)
        self.port_edit.setEnabled(not busy_remote)

        cli_ok = machine_open and backend and gc.STATE_DATA.swState != gc.STATE_RUN
        self.console.set_cli_enabled(cli_ok)

        jog_ok = machine_open and backend and gc.STATE_DATA.swState != gc.STATE_RUN
        self.jog.set_enabled(jog_ok)
        # DRO letter/value clicks (wx OnDroLeftUp when serial open)
        self.dro_panel.set_interactive(jog_ok)

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
        if self.btn_open is not None:
            self.btn_open.setEnabled(not busy_program)
        self._open_dropdown_menu.setEnabled(not busy_program)

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
    # Layout persistence (Qt dock saveState ≈ wx AUI perspective)
    # ------------------------------------------------------------------
    _LAYOUT_KEY = "/pysideWorkbench/Layout/Default"

    def _save_layout(self):
        """Save dock arrangement + window geometry (menu only, not on quit)."""
        try:
            state_b64 = base64.b64encode(bytes(self.saveState())).decode("ascii")
            geo_b64 = base64.b64encode(bytes(self.saveGeometry())).decode("ascii")
            gc.CONFIG_DATA.set(f"{self._LAYOUT_KEY}/State", state_b64)
            gc.CONFIG_DATA.set(f"{self._LAYOUT_KEY}/Geometry", geo_b64)
            # Clear one-shot splitter keys from the brief splitter experiment
            for sub in ("SplitMain", "SplitLeft", "SplitRight"):
                gc.CONFIG_DATA.set(f"{self._LAYOUT_KEY}/{sub}", "")
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
        """Clear saved layout and restore default dock arrangement (wx-like)."""
        try:
            for sub in (
                "State",
                "Geometry",
                "SplitMain",
                "SplitLeft",
                "SplitRight",
            ):
                gc.CONFIG_DATA.set(f"{self._LAYOUT_KEY}/{sub}", "")
            gc.CONFIG_DATA.save()
        except Exception:
            pass
        self._apply_default_dock_arrangement()
        for tb in self._toolbars.values():
            tb.show()
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        self.append_log(
            "Layout reset: G-code center, Console under it, Status|Jog right "
            "(drag docks to full-width bottom or other areas as needed)."
        )

    def closeEvent(self, event: QCloseEvent):
        # Layout is saved only via View → Save layout (not on quit), so a
        # messy rearrange is not persisted by accident.
        try:
            self.console.save_history_to_config()
        except Exception:
            pass
        self.bridge.shutdown(join_timeout=2.0)
        event.accept()
