"""----------------------------------------------------------------------------
    client_bridge.py

    Thread-safe bridge between gsat backend event producers
    (MachIfExecuteThread, RemoteClient) and the PySide GUI thread.

    Backend workers call add_event() / notify listeners; this object mirrors
    the wx main-window pattern (EventQueueIf + UI-thread wakeup) using Qt
    signals instead of wx.PostEvent.
----------------------------------------------------------------------------"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Signal, Slot

try:
    from shiboken6 import isValid as _qt_is_valid
except ImportError:  # pragma: no cover
    def _qt_is_valid(_obj):
        return True

import modules.config as gc
import modules.machif_progexec as mi_progexec
import modules.remote_ws_client as rcws


class ClientBridge(QObject, gc.EventQueueIf):
    """Event listener for backend threads; re-emits on the Qt event loop."""

    backend_event = Signal(object)  # gc.SimpleEvent
    log_message = Signal(str)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        gc.EventQueueIf.__init__(self)

        self.logger = logging.getLogger(__name__)
        self.remote_client = None
        self.machif_progexec = None

        # local vs remote: when remote is connected, commands go there
        self._use_remote = False
        self._shutting_down = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # EventQueueIf override — called from worker threads
    # ------------------------------------------------------------------
    def add_event(self, event_id, event_data=None, sender=None):
        if self._shutting_down:
            return

        if type(event_id) is gc.SimpleEvent:
            te = event_id
        else:
            te = gc.SimpleEvent(event_id, event_data, sender)

        # Keep queue for parity with existing EventQueueIf consumers
        try:
            self._eventQueue.put(te)
        except Exception:
            pass

        # Qt queues cross-thread emits onto the receiver's thread.
        # Guard against race where the C++ QObject is already destroyed
        # while a backend thread is still shutting down.
        if self._shutting_down or not _qt_is_valid(self):
            return

        try:
            self.backend_event.emit(te)
        except RuntimeError:
            # "Internal C++ object already deleted"
            pass

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect_remote(self, host: str, port: int, api_token: str | None = None):
        """Start a WebSocket remote client to gsat-server."""
        if self._shutting_down:
            return

        if self.remote_client is not None:
            self._safe_log("Already connected (or connecting) to remote.")
            return

        self.close_local()

        token = api_token
        if token is None:
            idx = gc.CONFIG_DATA.get("/remotes/Index", 0)
            token = gc.CONFIG_DATA.get(f"/remotes/remote{idx}/ApiToken", "")

        self._safe_log(f"Connecting to ws://{host}:{port} ...")
        self.remote_client = rcws.RemoteClient(
            self, host=host, port=int(port), api_token=token
        )
        self.machif_progexec = self.remote_client
        self._use_remote = True

    def disconnect_remote(self):
        """Ask remote client to exit; cleanup finishes on EV_EXIT."""
        if self.remote_client is None:
            return

        self._safe_log("Disconnecting remote ...")
        try:
            self.remote_client.add_event(gc.EV_CMD_EXIT, sender=self)
        except Exception as exc:  # noqa: BLE001 — surface to UI log
            self._safe_log(f"Remote disconnect error: {exc}")
            self.remote_client = None
            if self._use_remote:
                self.machif_progexec = None
            self._use_remote = False

    def open_local(self):
        """Start local MachIfExecuteThread (opens serial from config)."""
        if self._shutting_down:
            return

        if self.remote_client is not None:
            self._safe_log(
                "Close remote connection before opening a local machine link."
            )
            return

        if self.machif_progexec is not None:
            self._safe_log("Local machine interface already running.")
            return

        self._safe_log("Starting local machine interface ...")
        self.machif_progexec = mi_progexec.MachIfExecuteThread(self)
        self._use_remote = False

    def close_local(self):
        if self.remote_client is not None:
            return

        if self.machif_progexec is None:
            return

        self._safe_log("Closing local machine interface ...")
        self.machif_progexec.add_event(gc.EV_CMD_EXIT)
        # thread posts EV_EXIT when done

    def open_machine(self):
        """Open machine on remote server (local path opens on thread start)."""
        if self.remote_client is not None:
            self.remote_client.add_event(gc.EV_CMD_OPEN)
            self._safe_log("Requested machine open on remote.")
        elif self.machif_progexec is None:
            self.open_local()
        else:
            self._safe_log("Local machine interface already open.")

    def close_machine(self):
        if self.remote_client is not None:
            self.remote_client.add_event(gc.EV_CMD_CLOSE)
            self._safe_log("Requested machine close on remote.")
        else:
            self.close_local()

    def request_status(self):
        """Explicit user/initial refresh only — never call from a UI timer."""
        if self.machif_progexec is not None:
            self.machif_progexec.add_event(gc.EV_CMD_GET_STATUS)

    def request_initial_remote_sync(self):
        """One-shot pulls after remote socket opens (matches classic wx once)."""
        if self.remote_client is None:
            return
        self.remote_client.add_event(gc.EV_CMD_GET_CONFIG)
        self.remote_client.add_event(gc.EV_CMD_GET_SYSTEM_INFO)
        self.remote_client.add_event(gc.EV_CMD_GET_SW_STATE)
        # Status if a machine session is already open on the server
        self.remote_client.add_event(gc.EV_CMD_GET_STATUS)
        # Program fingerprint for MD5-gated Step/Run (no full G-code unless auto)
        self.request_gcode_md5()

    def request_gcode_md5(self):
        """Ask backend for current program MD5 (multi-UI; does not reset server)."""
        if self.machif_progexec is None:
            return
        self.machif_progexec.add_event(gc.EV_CMD_GET_GCODE_MD5, sender=self)

    def send_command(self, event_id, data=None):
        """Forward an explicit user command to the backend (no polling helpers)."""
        if self.machif_progexec is not None:
            self.machif_progexec.add_event(event_id, data, sender=self)

    def send_line(self, line: str) -> bool:
        """Send one CLI line to the machine (``EV_CMD_SEND`` + trailing newline).

        Returns False if no backend is available.
        """
        if self.machif_progexec is None:
            self._safe_log("Cannot send: no machine backend.")
            return False
        text = str(line).rstrip("\r\n")
        if not text:
            return False
        # Backend expects a line terminator (same as wx console)
        self.machif_progexec.add_event(gc.EV_CMD_SEND, text + "\n", sender=self)
        return True

    def shutdown(self, join_timeout: float = 2.0):
        """Best-effort teardown on app exit.

        Stops accepting events first so backend threads cannot emit into a
        dying QObject, then asks workers to exit and waits briefly.
        """
        self._shutting_down = True

        remote = self.remote_client
        local = None if self._use_remote else self.machif_progexec

        def _stop_worker(worker, exit_sender=None):
            if worker is None:
                return
            try:
                worker.remove_event_listener(self)
            except Exception:
                pass
            try:
                if exit_sender is not None:
                    worker.add_event(gc.EV_CMD_EXIT, sender=exit_sender)
                else:
                    worker.add_event(gc.EV_CMD_EXIT)
            except Exception:
                pass
            join = getattr(worker, "join", None)
            is_alive = getattr(worker, "is_alive", None)
            if callable(join) and callable(is_alive) and is_alive():
                join(timeout=join_timeout)

        _stop_worker(remote, exit_sender=self)
        _stop_worker(local)

        self.remote_client = None
        self.machif_progexec = None
        self._use_remote = False

    # ------------------------------------------------------------------
    # Helpers called from main window after processing events
    # ------------------------------------------------------------------
    @Slot(object)
    def on_remote_exited(self, sender):
        if self.remote_client is not None and id(sender) == id(self.remote_client):
            self.remote_client = None
            if self._use_remote:
                self.machif_progexec = None
            self._use_remote = False

    @Slot(object)
    def on_local_exited(self, sender):
        if (
            self.machif_progexec is not None
            and not self._use_remote
            and id(sender) == id(self.machif_progexec)
        ):
            self.machif_progexec = None

    def is_remote_connected(self) -> bool:
        return self.remote_client is not None

    def is_backend_active(self) -> bool:
        return self.machif_progexec is not None

    def remote_hostname(self) -> str:
        if self.remote_client is not None:
            try:
                return self.remote_client.get_hostname() or ""
            except Exception:
                return ""
        return ""

    def _safe_log(self, msg: str):
        if self._shutting_down or not _qt_is_valid(self):
            return
        try:
            self.log_message.emit(msg if msg.endswith("\n") else f"{msg}\n")
        except RuntimeError:
            pass
