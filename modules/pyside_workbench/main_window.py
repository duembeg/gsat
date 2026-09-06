"""----------------------------------------------------------------------------
    main_window.py

    Spike shell for the gsat PySide workbench:
    connect + DRO + console CLI + G-code / PC.
----------------------------------------------------------------------------"""
from __future__ import annotations

import base64
import hashlib
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
from modules.pyside_workbench import run_end as run_end_util


def _gcode_lines_md5(lines) -> str:
    """Same fingerprint as wx / machif_progexec (cache key, not security)."""
    return hashlib.md5(str(lines if lines is not None else []).encode("utf-8")).hexdigest()


class MainWindow(QMainWindow):
    def __init__(self, cmd_line_options, parent=None):
        super().__init__(parent)
        self.cmd_line_options = cmd_line_options
        self.logger = logging.getLogger(__name__)

        self.setWindowTitle(f"{vinfo.__appname__} — PySide workbench")
        # Factory first impression: compact G-code, taller console, roomy right
        # column (DRO|Jog unscrolled). Saved layouts override.
        self.resize(1400, 1080)

        self.bridge = ClientBridge(self)
        self.bridge.backend_event.connect(self.on_backend_event)
        self.bridge.log_message.connect(self.append_log)

        self._machine_open = False
        self._remote_connected = False
        self._remote_connecting = False
        # Last program MD5 reported by backend (wx: machifProgExecGcodeMd5).
        # Client-only; reconnect adopts server value via EV_GCODE_MD5 — never
        # clears server buffer (multi-UI / headless).
        self._backend_gcode_md5 = 0
        # wx runEndWaitingForMachIfIdle: software sent all lines, wait for Idle
        self._run_end_waiting_idle = False
        self._progexec_rtime = 0.0
        self._reload_runtime_dialog_setting()

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

        # Edit — G-code find/replace (VS Code–style in-panel bar, not a toolbar)
        self.act_find = QAction("&Find…", self)
        self.act_find.setShortcut(QKeySequence.StandardKey.Find)
        self.act_find.setToolTip("Find in G-code (Ctrl+F)")
        self.act_find.triggered.connect(self.on_find)
        self.act_replace = QAction("&Replace…", self)
        self.act_replace.setShortcut(QKeySequence.StandardKey.Replace)
        self.act_replace.setToolTip("Find and replace in G-code (Ctrl+H)")
        self.act_replace.triggered.connect(self.on_replace)
        # Next/prev: F3 / Shift+F3 only (no menu; avoid platform Ctrl+G / Ctrl+Shift+G)
        self.act_find_next = QAction(self)
        self.act_find_next.setShortcut(QKeySequence("F3"))
        self.act_find_next.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_find_next.triggered.connect(self.on_find_next)
        self.addAction(self.act_find_next)
        self.act_find_prev = QAction(self)
        self.act_find_prev.setShortcut(QKeySequence("Shift+F3"))
        self.act_find_prev.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_find_prev.triggered.connect(self.on_find_prev)
        self.addAction(self.act_find_prev)

        self.act_remote_settings = QAction("Remote settings…", self)
        self.act_remote_settings.setToolTip(
            "Edit machine/remote config from the connected server (wx Remote Settings)"
        )
        self.act_remote_settings.triggered.connect(self.on_remote_settings)

        # Explicit pull — not automatic (may overwrite local editor G-code)
        self.act_remote_get_gcode = QAction("Get G-code", self)
        self.act_remote_get_gcode.setToolTip(
            "Get G-code from remote server (backend program buffer). "
            "Not automatic so you can keep or replace local editor content."
        )
        self.act_remote_get_gcode.triggered.connect(self.on_remote_get_gcode)

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
        # Local serial open is Machine Connect when not remote (wx); no separate action.

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
            (self.act_remote, "remote"),
            (self.act_settings, "settings"),
            (self.act_remote_settings, "remote_settings"),
            (self.act_remote_get_gcode, "remote_gcode"),
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

    def _apply_dock_corners(self) -> None:
        """Column-style: right docks own the right edge full height.

        Bottom dock (Console) only sits under the center (G-code), not under
        DRO/Jog — so Console height is not tied to Jog in one shared row.
        restoreState() can clobber this; call again after layout load.
        """
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

    def _apply_default_dock_arrangement(self, apply_factory_sizes: bool = True) -> None:
        """Default like wx: G-code center, Console under center, DRO|Jog right column.

        User can still drag docks to a full-width bottom row, etc. Saved layouts
        via View → Save layout override this until View → Reset layout.

        ``apply_factory_sizes``: when False, only place docks (used before
        restoreState so we do not bake 400/280 into a layout that is about to
        be replaced). When True (reset / no save / recovery), apply factory
        dock pixel sizes.
        """
        self._apply_dock_corners()

        # Force docks out of any previous area (reset / recovery from row layout)
        for d in (self.dock_console, self.dock_dro, self.dock_jog):
            self.removeDockWidget(d)

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_console)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_dro)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_jog)
        self.splitDockWidget(self.dock_dro, self.dock_jog, Qt.Orientation.Vertical)

        self.dock_console.show()
        self.dock_dro.show()
        self.dock_jog.show()
        if apply_factory_sizes:
            # Console ~2× older factory (was ~170–180): debug log needs room.
            # G-code center stays relatively short/narrow (typical lines are short).
            # Right column: enough for DRO+Jog without scrollbars.
            self.resizeDocks([self.dock_console], [340], Qt.Orientation.Vertical)
            self.resizeDocks(
                [self.dock_dro, self.dock_jog], [530, 460], Qt.Orientation.Vertical
            )
            self._ensure_jog_dock_width(force_resize=True)

    def _ensure_jog_dock_width(self, force_resize: bool = False) -> None:
        """Keep right column wide enough for the fixed jog pad.

        After restoreState, only raise the minimum and grow if the dock is
        *already too narrow* — never force a default width (that clobbers
        saved horizontal and can reshuffle the DRO|Jog vertical split).
        """
        try:
            # Content ~396 + dock title chrome; factory prefers a bit wider so
            # the center G-code pane is not huge (typical G-code lines are short).
            content_w = int(self.jog._content.width()) if hasattr(self.jog, "_content") else 0
            jog_w = max(440, content_w + 36, int(self.jog.minimumSizeHint().width()))
        except Exception:
            jog_w = 440
        try:
            self.dock_jog.setMinimumWidth(jog_w)
            cur = int(self.dock_jog.width())
            if force_resize or cur < jog_w:
                self.resizeDocks(
                    [self.dock_jog], [jog_w if force_resize else max(jog_w, cur)],
                    Qt.Orientation.Horizontal,
                )
        except Exception:
            pass

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
        self.jog.zero_axes.connect(self.on_jog_zero_axes)
        self.jog.jog_absolute.connect(self.on_jog_absolute)
        self.jog.probe_axes.connect(self.on_jog_probe)
        self.jog.gcode_script.connect(self.on_jog_gcode_script)
        self.dock_jog = self._make_dock("Machine Jogging", self.jog, "dockJog")
        # Modest min only; full pad min + factory sizes applied after we know
        # whether a saved layout will restore (see _load_layout).
        try:
            self.dock_jog.setMinimumWidth(200)
        except Exception:
            pass

        # Place docks only — do not bake factory 400/280 before restoreState
        self._apply_default_dock_arrangement(apply_factory_sizes=False)

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
        self.tb_remote.addAction(self.act_remote_get_gcode)
        self.tb_remote.addAction(self.act_remote_settings)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tb_remote)

        self._toolbars = {
            "main": self.tb_main,
            "program": self.tb_program,
            "machine": self.tb_machine,
            "remote": self.tb_remote,
        }
        # Tooltips + role styling (theme: flat strip tools; danger = abort)
        for tb in self._toolbars.values():
            for btn in tb.findChildren(QToolButton):
                act = btn.defaultAction()
                if act is not None and act.toolTip():
                    btn.setToolTip(act.toolTip())
                if act is self.act_abort:
                    btn.setObjectName("toolButtonDanger")
                    # Re-apply so objectName stylesheet selectors take effect
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)

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

        # Edit — find/replace on G-code panel (no search toolbar)
        # Next/prev are F3 / Shift+F3 only — no menu entries
        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.act_find)
        edit_menu.addAction(self.act_replace)

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

        # Remote
        remote_menu = self.menuBar().addMenu("R&emote")
        remote_menu.addAction(self.act_remote)
        remote_menu.addAction(self.act_remote_get_gcode)
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
        """Build dict for EV_CMD_STEP / RUN (same keys and MD5 policy as wx).

        - Always send ``gcodePC`` and ``breakPoints`` (BPs can change without
          text change).
        - Send ``gcodeLines`` only when local MD5 ≠ last backend MD5
          (``EV_GCODE_MD5`` / first upload).
        """
        lines = self.gcode.lines()
        gc.STATE_DATA.gcodeFileLines = lines
        bps = self.gcode.get_breakpoints()
        gc.STATE_DATA.breakPoints = bps
        payload = {
            "gcodePC": gc.STATE_DATA.programCounter,
            "breakPoints": bps,
        }
        if gc.STATE_DATA.gcodeFileName:
            payload["gcodeFileName"] = gc.STATE_DATA.gcodeFileName
        if lines:
            h = _gcode_lines_md5(lines)
            if self._backend_gcode_md5 != h:
                payload["gcodeLines"] = lines
        return payload

    def _backend_has_program(self) -> bool:
        """True if local editor or known backend buffer has G-code (multi-UI)."""
        if self.gcode.line_count() > 0:
            return True
        empty_h = _gcode_lines_md5([])
        md5 = self._backend_gcode_md5
        return bool(md5) and md5 != 0 and md5 != empty_h

    def _can_run_or_step(self) -> bool:
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        return (
            self.bridge.is_backend_active()
            and machine_open
            and self._backend_has_program()
            and gc.STATE_DATA.swState
            in (gc.STATE_IDLE, gc.STATE_BREAK, gc.STATE_PAUSE)
        )

    def _on_ev_gcode_md5(self, data) -> None:
        """Adopt backend program fingerprint (wx EV_GCODE_MD5 handler)."""
        self._backend_gcode_md5 = data
        # Optional auto-pull of full G-code when remote buffer differs (wx).
        try:
            idx = int(gc.CONFIG_DATA.get("/remotes/Index", 0) or 0)
            auto = bool(
                gc.CONFIG_DATA.get(
                    f"/remotes/remote{idx}/AutoGcodeRequest", False
                )
            )
        except Exception:
            auto = False
        if not auto or not self.bridge.is_remote_connected():
            return
        empty_h = _gcode_lines_md5([])
        if not data or data == empty_h:
            return
        local_h = _gcode_lines_md5(self.gcode.lines())
        if local_h == data:
            return
        # Explicit pull — same event as Remote → Get G-code
        self.bridge.send_command(gc.EV_CMD_GET_GCODE)
        self.append_log("Auto G-code request (remote MD5 differs from local).")

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

    def _jog_cmd_ready(self, label: str = "Jog") -> bool:
        """Machine open, backend up, not streaming program (wx jog enable)."""
        if not self.bridge.is_backend_active():
            self.append_log(f"{label}: no machine backend.")
            return False
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        if not machine_open:
            self.append_log(f"{label}: machine not open.")
            return False
        if gc.STATE_DATA.swState == gc.STATE_RUN:
            self.append_log(f"{label}: blocked while program is running.")
            return False
        return True

    @Slot(dict)
    def on_jog_zero_axes(self, axes: dict):
        """Work-zero axes from jog pad (wx SetToZero* → EV_CMD_SET_AXIS)."""
        if not self._jog_cmd_ready("Zero"):
            return
        self.bridge.send_command(gc.EV_CMD_SET_AXIS, dict(axes))
        self.append_log(
            f"Zero work: {','.join(sorted(axes.keys())).upper()}"
        )

    @Slot(dict, bool, object)
    def on_jog_absolute(self, axes: dict, rapid: bool, feed):
        """Absolute jog (wx GoToZeroXY → EV_CMD_JOG_MOVE / RAPID)."""
        if not self._jog_cmd_ready("Jog abs"):
            return
        payload = dict(axes)
        if rapid:
            self.bridge.send_command(gc.EV_CMD_JOG_RAPID_MOVE, payload)
            self.append_log(
                f"Jog rapid → {', '.join(f'{k.upper()}={v}' for k, v in axes.items())}"
            )
        else:
            if feed is not None:
                payload["feed"] = feed
            self.bridge.send_command(gc.EV_CMD_JOG_MOVE, payload)
            self.append_log(
                f"Jog → {', '.join(f'{k.upper()}={v}' for k, v in axes.items())}"
                + (f" F{feed}" if feed is not None else "")
            )

    @Slot(dict)
    def on_jog_probe(self, axes: dict):
        """Probe helper (wx Probe Z → EV_CMD_PROBE_HELPER)."""
        if not self._jog_cmd_ready("Probe"):
            return
        self.bridge.send_command(gc.EV_CMD_PROBE_HELPER, dict(axes))
        self.append_log(
            f"Probe requested: {','.join(sorted(axes.keys())).upper()}"
        )

    @Slot(str)
    def on_jog_gcode_script(self, script: str):
        """Spindle/coolant/custom buttons → serial lines (wx SerialWrite)."""
        if not self._jog_cmd_ready("Machine cmd"):
            return
        lines = [ln.strip() for ln in str(script).splitlines() if ln.strip()]
        if not lines:
            return
        for line in lines:
            if not self.bridge.send_line(line):
                self.append_log(f"Machine cmd send failed: {line}")
                return
        if len(lines) == 1:
            self.append_log(f"Sent: {lines[0]}")
        else:
            self.append_log(f"Sent {len(lines)} G-code lines (custom).")

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
    def on_find(self):
        """Edit → Find: open G-code in-panel find bar (Ctrl+F)."""
        self.gcode.show_find(replace=False)

    @Slot()
    def on_find_next(self):
        self.gcode.find_next()

    @Slot()
    def on_find_prev(self):
        self.gcode.find_prev()

    @Slot()
    def on_replace(self):
        """Edit → Replace: open find bar in replace mode (Ctrl+H)."""
        self.gcode.show_find(replace=True)

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

    @Slot()
    def on_remote_get_gcode(self):
        """wx OnRemoteGetGcode: request program buffer from server (explicit only)."""
        if not self.bridge.is_remote_connected():
            self.append_log("Get G-code: not connected to remote.")
            return
        self.bridge.send_command(gc.EV_CMD_GET_GCODE)
        self.append_log("Requested G-code from remote server…")

    def _on_ev_gcode(self, data) -> None:
        """Handle EV_GCODE from remote GET_GCODE (wx OnRemoteGetGcode result)."""
        # Server sends dict; local progexec may send a bare list of lines
        if isinstance(data, dict):
            lines = data.get("gcodeLines") or []
            fname = data.get("gcodeFileName") or ""
            pc = data.get("gcodePC", 0)
            bps = data.get("breakPoints") or set()
        elif isinstance(data, (list, tuple)):
            lines = list(data)
            fname = ""
            pc = 0
            bps = set()
        else:
            self.append_log("Get G-code: unexpected payload type.")
            return

        if not lines:
            self.append_log("Get G-code: remote has no program loaded.")
            return

        # wx: if editor modified, offer save before override
        if self.gcode.editor.document().isModified():
            reply = QMessageBox.question(
                self,
                "Get Remote G-code",
                "Current G-code has been modified.\n"
                "Save before override from remote?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                self.append_log("Get G-code: cancelled.")
                return
            if reply == QMessageBox.StandardButton.Yes:
                self.on_save_gcode_as()

        # Normalize lines to list[str] with newlines preserved where possible
        norm: list[str] = []
        for ln in lines:
            s = str(ln)
            if s and not s.endswith("\n"):
                s = s + "\n"
            norm.append(s)

        path = str(fname) if fname else ""
        self.gcode.load_lines(path, norm)
        self.gcode.editor.document().setModified(False)
        gc.STATE_DATA.gcodeFileName = path
        gc.STATE_DATA.gcodeFileLines = self.gcode.lines()
        gc.STATE_DATA.fileIsOpen = True
        try:
            pc_i = int(pc)
        except (TypeError, ValueError):
            pc_i = 0
        self.set_pc(pc_i)
        try:
            bp_set = set(int(x) for x in bps)
        except (TypeError, ValueError):
            bp_set = set()
        self.gcode.set_breakpoints(bp_set)
        gc.STATE_DATA.breakPoints = bp_set

        base = os.path.basename(path) if path else "(remote)"
        self.setWindowTitle(f"{base} — {vinfo.__appname__} — PySide workbench")
        self.append_log(f"Loaded G-code from remote: {base} ({len(norm)} lines)")
        self._update_connection_ui()

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
        # Jog panel (feed/rapid/spindle/custom — wx UpdateSettings)
        try:
            self.jog.update_settings()
        except Exception as exc:
            self.logger.warning("Jog settings apply failed: %s", exc)
        # G-code + console fonts/colors/syntax (wx UpdateSettings on each panel)
        try:
            self.gcode.update_settings()
        except Exception as exc:
            self.logger.warning("G-code settings apply failed: %s", exc)
        try:
            self.console.update_settings()
        except Exception as exc:
            self.logger.warning("Console settings apply failed: %s", exc)
        try:
            self.dro_panel.update_settings()
        except Exception as exc:
            self.logger.warning("DRO settings apply failed: %s", exc)
        self._reload_runtime_dialog_setting()

    def _reload_runtime_dialog_setting(self) -> None:
        show = False
        if gc.CONFIG_DATA is not None:
            show = bool(gc.CONFIG_DATA.get("/mainApp/DisplayRunTimeDialog", False))
        self._display_runtime_dialog = show

    def _cancel_run_end_wait(self) -> None:
        """Abort/close: do not show the runtime dialog."""
        self._run_end_waiting_idle = False

    def _reset_machine_session_flags(self, *, drop_remote_config: bool = False) -> None:
        """wx abort/close/remote-drop: do not leave RUN / detected / old remote blob.

        Enablement already keys off ``_machine_open``; ``swState`` must still
        reset or the status badge can stay RUN after disconnect.
        """
        self._cancel_run_end_wait()
        self._machine_open = False
        gc.STATE_DATA.serialPortIsOpen = False
        gc.STATE_DATA.deviceDetected = False
        gc.STATE_DATA.swState = gc.STATE_IDLE
        gc.STATE_DATA.machineStatusString = ""
        if drop_remote_config:
            self._remote_config_data = None

    def _maybe_finish_run_end_wait(self) -> None:
        """wx: after EV_RUN_END, wait until machine Idle/Stop/End then optional dialog."""
        if not run_end_util.should_finish_run_end_wait(
            waiting=self._run_end_waiting_idle,
            stat=gc.STATE_DATA.machineStatusString,
        ):
            return
        self._run_end_waiting_idle = False
        self._update_connection_ui()
        if self._display_runtime_dialog:
            self._show_run_time_dialog()

    def _show_run_time_dialog(self) -> None:
        body = run_end_util.format_run_time_dialog(self._progexec_rtime)
        QMessageBox.information(self, "G-Code Program", body)

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
                        if "rtime" in sr:
                            try:
                                self._progexec_rtime = float(sr["rtime"])
                            except (TypeError, ValueError):
                                pass
                        self.dro_panel.update_from_status(sr)

                self.dro_panel.update_from_status(data)
                if "stat" in data and data["stat"] is not None:
                    gc.STATE_DATA.machineStatusString = data["stat"]
                if "rtime" in data:
                    try:
                        self._progexec_rtime = float(data["rtime"])
                    except (TypeError, ValueError):
                        pass

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

                self._maybe_finish_run_end_wait()

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
            # Learn program fingerprint after session open (local or remote)
            self.bridge.request_gcode_md5()
            self._update_connection_ui()

        elif eid == gc.EV_SER_PORT_CLOSE:
            self.append_log("Machine serial/port closed.")
            self._reset_machine_session_flags(drop_remote_config=False)
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
            # Client-only: forget last-known MD5 for this UI session so a new
            # connect re-learns from EV_GCODE_MD5. Does not clear server buffer.
            self._backend_gcode_md5 = 0
            self._reset_machine_session_flags(drop_remote_config=True)
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
            # Software finished sending; wait for controller Idle before dialog
            self._run_end_waiting_idle = True
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
            drop_remote = (
                te.sender is self.bridge.remote_client or self._remote_connecting
            )
            if drop_remote:
                self._remote_connecting = False
                self._remote_connected = False
            self._reset_machine_session_flags(drop_remote_config=drop_remote)
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
            if was_remote:
                self._reset_machine_session_flags(drop_remote_config=True)
                self.dro_panel.clear()
            elif was_local or not self.bridge.is_backend_active():
                self._reset_machine_session_flags(drop_remote_config=False)
                self.dro_panel.clear()
            self._update_connection_ui()

        elif eid == gc.EV_GCODE_MD5:
            self._on_ev_gcode_md5(data)

        elif eid == gc.EV_GCODE:
            self._on_ev_gcode(data)

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
        self.act_remote_get_gcode.setEnabled(remote or client_alive)
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
        """Restore docks/geometry if previously saved.

        restoreState can place Jog next to Console (shared bottom row) and can
        reset dock corners — re-assert column corners afterward. If the saved
        layout clearly put Jog on the bottom band with Console, recover the
        factory column arrangement (user can re-save after intentional rearrange).

        Important: do **not** call resizeDocks with factory sizes after a
        successful restore — that was resetting DRO|Jog split heights.
        """
        try:
            geo_b64 = gc.CONFIG_DATA.get(f"{self._LAYOUT_KEY}/Geometry", "") or ""
            state_b64 = gc.CONFIG_DATA.get(f"{self._LAYOUT_KEY}/State", "") or ""
            has_state = bool(state_b64)
            if geo_b64:
                self.restoreGeometry(QByteArray(base64.b64decode(geo_b64)))
            if has_state:
                self.restoreState(QByteArray(base64.b64decode(state_b64)))
            # Always re-apply corners after restore (Qt often drops them)
            self._apply_dock_corners()
            # Recover from the known-bad "Console | Jog" bottom row save
            if (
                has_state
                and self.dockWidgetArea(self.dock_jog)
                == Qt.DockWidgetArea.BottomDockWidgetArea
                and self.dockWidgetArea(self.dock_console)
                == Qt.DockWidgetArea.BottomDockWidgetArea
            ):
                self.logger.info(
                    "Saved layout had Console+Jog on bottom row; "
                    "restoring column default (DRO|Jog right)."
                )
                self._apply_default_dock_arrangement(apply_factory_sizes=True)
            elif has_state:
                # Keep restored DRO|Jog|console sizes; only grow if too narrow
                self._ensure_jog_dock_width(force_resize=False)
            else:
                # No saved state — apply factory pixel sizes once
                self._apply_default_dock_arrangement(apply_factory_sizes=True)
        except Exception as exc:
            self.logger.warning("Layout load failed: %s", exc)
            try:
                self._apply_default_dock_arrangement(apply_factory_sizes=True)
            except Exception:
                pass

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
        self._apply_default_dock_arrangement(apply_factory_sizes=True)
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
