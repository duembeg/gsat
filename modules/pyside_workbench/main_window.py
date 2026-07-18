"""----------------------------------------------------------------------------
    main_window.py

    Spike shell for the gsat PySide workbench:
    connect (remote WS and/or local progexec) + status + DRO + console CLI.
----------------------------------------------------------------------------"""
from __future__ import annotations

import logging

from PySide6.QtCore import Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
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

from modules.pyside_workbench.client_bridge import ClientBridge
from modules.pyside_workbench.console_panel import ConsolePanel
from modules.pyside_workbench.dro_panel import DroPanel


class MainWindow(QMainWindow):
    def __init__(self, cmd_line_options, parent=None):
        super().__init__(parent)
        self.cmd_line_options = cmd_line_options
        self.logger = logging.getLogger(__name__)

        self.setWindowTitle(f"{vinfo.__appname__} — PySide workbench (spike)")
        self.resize(900, 640)

        # Parent to QApplication lifetime is handled via window ownership;
        # bridge still parents to this window for normal Qt cleanup order.
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

        # No auto-poll timers. Backend pushes EV_DATA_*; UI only renders.
        # Manual Refresh + one-shot sync on remote connect are explicit.

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

        # Machine actions
        machine_row = QHBoxLayout()
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

        machine_row.addStretch(1)
        layout.addLayout(machine_row)

        self.connection_label = QLabel("Connection: idle")
        layout.addWidget(self.connection_label)

        body = QHBoxLayout()
        self.dro_panel = DroPanel()
        body.addWidget(self.dro_panel, 0)

        max_hist = 40
        try:
            max_hist = int(gc.CONFIG_DATA.get("/console/cli/CmdMaxHistory", 40))
        except (TypeError, ValueError):
            pass
        self.console = ConsolePanel(max_history=max_hist)
        self.console.line_submitted.connect(self.on_cli_submit)
        body.addWidget(self.console, 1)
        layout.addLayout(body, 1)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("PySide workbench spike — connect to server or open local")

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("&File")
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
    # Actions
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
        """Forward a CLI line to the backend (same rules as wx console)."""
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen
        if not machine_open or not self.bridge.is_backend_active():
            self.append_log("CLI: machine not open.")
            return
        # Match wx: block free-form send while program is running
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
        """Handle SimpleEvent from backend workers (same IDs as wx path)."""
        if te is None:
            return

        eid = te.event_id
        data = te.data

        if eid == gc.EV_DATA_STATUS:
            # Same shape as wx OnThreadEvent: parse fields + show rx_data in console
            if isinstance(data, dict):
                if "sr" in data:
                    sr = data["sr"]
                    if isinstance(sr, dict):
                        if "stat" in sr:
                            gc.STATE_DATA.machineStatusString = sr["stat"]
                        self.dro_panel.update_from_status(sr)

                # top-level fields sometimes carry fw / status bits
                self.dro_panel.update_from_status(data)

                # Backend machine text (e.g. <Idle|MPos:…>) travels here, not EV_DATA_IN
                if "rx_data" in data and data["rx_data"]:
                    self.append_log(data["rx_data"])

                if "pc" in data:
                    try:
                        gc.STATE_DATA.programCounter = int(data["pc"])
                    except (TypeError, ValueError):
                        pass

                if "swstate" in data:
                    try:
                        gc.STATE_DATA.swState = int(data["swstate"])
                    except (TypeError, ValueError):
                        pass
                    self._update_connection_ui()

        elif eid == gc.EV_DATA_IN:
            self.append_log(data)

        elif eid == gc.EV_DATA_OUT:
            # Prefix like wx; trailing newline handled in append_log
            self.append_log(f"> {data}")

        elif eid == gc.EV_SER_PORT_OPEN:
            self.append_log("Machine serial/port open.")
            self._machine_open = True
            gc.STATE_DATA.serialPortIsOpen = True
            # One-shot status after open (wx does the same); not a poll loop
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
            # One-shot field sync after connect (config / info / sw state / status)
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

        elif eid == gc.EV_ABORT:
            self.append_log(str(data) if data else "ABORT")
            # UI state only here — leave client object until EV_EXIT so we do
            # not start a second RemoteClient while the old thread is exiting.
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
            was_local = te.sender is self.bridge.machif_progexec and not self.bridge._use_remote
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
            pass  # ignore in spike

        else:
            name = gc.EV_2STR_DICT.get(eid, str(eid))
            if self.cmd_line_options.verbose:
                self.append_log(f"[{name}] {data!r}")

    @Slot(str)
    def append_log(self, text):
        """Delegate to console panel (trailing-newline normalize lives there)."""
        self.console.append_text(text)

    def _update_connection_ui(self):
        remote = self._remote_connected and self.bridge.is_remote_connected()
        connecting = self._remote_connecting
        backend = self.bridge.is_backend_active()
        host_info = self.bridge.remote_hostname()
        machine_open = self._machine_open or gc.STATE_DATA.serialPortIsOpen

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
        self.connection_label.setText("Connection: " + " | ".join(parts))

        # Keep Connect disabled while a RemoteClient object is alive (including
        # failed-connect teardown) so we do not stack threads.
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

        # CLI: open machine and not in RUN (matches wx console)
        cli_ok = (
            machine_open
            and backend
            and gc.STATE_DATA.swState != gc.STATE_RUN
        )
        self.console.set_cli_enabled(cli_ok)

        status = " | ".join(parts)
        self.statusBar().showMessage(status)

    def closeEvent(self, event: QCloseEvent):
        # Join backend threads before Qt destroys the bridge QObject
        self.bridge.shutdown(join_timeout=2.0)
        event.accept()
