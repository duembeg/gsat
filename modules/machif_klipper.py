"""----------------------------------------------------------------------------
    machif_klipper.py

    Copyright (C) 2026 Wilhelm Duembeg

    This file is part of gsat. gsat is a cross-platform GCODE debug/step for
    Grbl like GCODE interpreters. With features similar to software debuggers.
    Features such as breakpoint, change current program counter, inspection
    and modification of variables.

    gsat is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 2 of the License, or
    (at your option) any later version.

    gsat is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with gsat.  If not, see <http://www.gnu.org/licenses/>.

----------------------------------------------------------------------------"""

import asyncio
import copy
import json
import queue
import threading
import time

import modules.config as gc
import modules.machif as mi
import modules.version_info as vinfo

# aiohttp is imported inside MoonrakerThread.run. machif_config constructs
# every machif at import time, so a missing dependency must not break startup.

ID = 1400
NAME = "klipper"
BUFFER_MAX_SIZE = 1
BUFFER_INIT_VAL = 0
BUFFER_WATERMARK_PRCNT = 1.0

# Moonraker docs: poll server.info about every 2 s while klippy is starting.
SERVER_INFO_POLL_SEC = 2.0
DEFAULT_JOG_FEED = 3000
NO_HOLD_NOTE = "Klipper: no realtime hold; stop streaming / use E-stop\n"
AIOHTTP_HINT = (
    "aiohttp is required for the Klipper interface. "
    "Install it with: pip install 'aiohttp>=3.9'\n"
)

# Field lists are Moonraker subscribe/query selectors (None would mean "all").
SUBSCRIBE_OBJECTS = {
    "motion_report": ["live_position", "live_velocity"],
    "toolhead": ["homed_axes", "position", "axis_minimum", "axis_maximum"],
    "gcode_move": ["gcode_position", "position", "absolute_coordinates", "speed"],
    "idle_timeout": ["state"],
    "webhooks": ["state", "state_message"],
    "print_stats": ["state"],
}

_AXIS_ORDER = ("x", "y", "z", "a", "b", "c")


def _merge_status(cache, update):
    """Merge a Moonraker status diff. Lists replace; dicts merge one level down."""
    if not isinstance(update, dict):
        return
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(cache.get(key), dict):
            _merge_status(cache[key], value)
        else:
            cache[key] = value


def _xyz(seq):
    out = []
    for i in range(3):
        try:
            out.append(float(seq[i]))
        except (TypeError, ValueError, IndexError):
            out.append(0.0)
    return out


def _fmt_num(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


class MoonrakerThread(threading.Thread, gc.EventQueueIf):
    """asyncio Moonraker websocket. Same outward events as SerialPortThread.

    In: EV_CMD_TXDATA (dict with method/params/kind/token), EV_CMD_EXIT.
    Out: EV_RXDATA (tagged dict), EV_SER_PORT_OPEN/CLOSE, EV_ABORT, EV_EXIT.
    """

    def __init__(self, listener, url, api_key, connect_timeout_ms, idle_timeout_sec):
        threading.Thread.__init__(self, name="moonraker")
        gc.EventQueueIf.__init__(self)
        self.daemon = True

        self._url = url
        self._api_key = api_key or ""
        self._connect_timeout_s = max(0.1, float(connect_timeout_ms) / 1000.0)
        self._idle_timeout_sec = float(idle_timeout_sec or 0)
        self._cache = {}
        self._printer_info = {}
        self._pending = {}
        self._next_id = 0
        self._ws = None
        self._stopped = False
        self._handshake_done = False
        self._opened = False
        self._stop_event = None

        if listener is not None:
            self.add_event_listener(listener)

        self.start()

    def run(self):
        try:
            import aiohttp
        except ImportError:
            self.notify_event_listeners(gc.EV_ABORT, AIOHTTP_HINT)
            self.notify_event_listeners(gc.EV_EXIT, "")
            return

        self._aiohttp = aiohttp
        try:
            asyncio.run(self._async_main())
        except Exception as exc:
            self.notify_event_listeners(gc.EV_ABORT, f"Klipper: {exc}\n")
        finally:
            if self._opened:
                self.notify_event_listeners(gc.EV_SER_PORT_CLOSE, 0)
            self.notify_event_listeners(gc.EV_EXIT, "")

    async def _async_main(self):
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        self._user_q = asyncio.Queue()
        self._send_lock = asyncio.Lock()

        timeout = self._aiohttp.ClientTimeout(total=None, sock_connect=self._connect_timeout_s)
        async with self._aiohttp.ClientSession(timeout=timeout) as session:
            try:
                self._ws = await session.ws_connect(
                    self._url,
                    heartbeat=30.0,
                    timeout=self._aiohttp.ClientWSTimeout(ws_receive=None, ws_close=10.0),
                )
            except Exception as exc:
                self.notify_event_listeners(gc.EV_ABORT, f"Klipper: connect failed: {exc}\n")
                return

            self._opened = True
            self.notify_event_listeners(gc.EV_SER_PORT_OPEN, self._url)
            reader = asyncio.create_task(self._read_loop())
            watcher = asyncio.create_task(self._watch_commands())
            try:
                await self._handshake()
                if not self._stopped:
                    self._handshake_done = True
                    await self._serve()
            finally:
                self._stopped = True
                self._stop_event.set()
                reader.cancel()
                watcher.cancel()
                for task in (reader, watcher):
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
                if self._ws is not None and not self._ws.closed:
                    await self._ws.close()

    async def _read_loop(self):
        ws_type = self._aiohttp.WSMsgType
        try:
            async for msg in self._ws:
                if msg.type == ws_type.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict):
                        self._on_message(data)
                elif msg.type in (ws_type.CLOSED, ws_type.CLOSING, ws_type.ERROR):
                    break
        finally:
            self._fail_pending("Moonraker connection closed")
            self._stopped = True
            if self._stop_event is not None:
                self._stop_event.set()

    def _fail_pending(self, message):
        err = {"code": 1, "message": message}
        for meta in list(self._pending.values()):
            fut = meta.get("future")
            if fut is not None and not fut.done():
                fut.set_result({"error": err})
        self._pending.clear()

    def _on_message(self, data):
        if "id" in data and data["id"] in self._pending:
            meta = self._pending.pop(data["id"])
            fut = meta.get("future")
            if fut is not None and not fut.done():
                fut.set_result(data)
            return

        method = data.get("method")
        params = data.get("params") or []
        if method == "notify_status_update":
            diff = params[0] if params else {}
            if isinstance(diff, dict):
                _merge_status(self._cache, diff)
            self._emit_status()
        elif method == "notify_gcode_response":
            text = params[0] if params else ""
            self.notify_event_listeners(gc.EV_RXDATA, {"_gsat": "gcode", "text": text})
        elif method == "notify_klippy_shutdown":
            _merge_status(self._cache, {"webhooks": {"state": "shutdown"}})
            self._emit_status()
        elif method == "notify_klippy_disconnected":
            self.notify_event_listeners(
                gc.EV_RXDATA, {"_gsat": "klippy", "state": "disconnected"}
            )
        elif method == "notify_klippy_ready" and self._handshake_done:
            asyncio.create_task(self._on_klippy_ready())

    def _emit_status(self):
        self.notify_event_listeners(
            gc.EV_RXDATA,
            {"_gsat": "status", "status": copy.deepcopy(self._cache)},
        )

    async def _watch_commands(self):
        while not self._stopped:
            drained = False
            while True:
                try:
                    event = self._eventQueue.get_nowait()
                except queue.Empty:
                    break
                drained = True
                if event.event_id == gc.EV_CMD_EXIT:
                    self._stopped = True
                    self._stop_event.set()
                    return
                if event.event_id == gc.EV_CMD_TXDATA and isinstance(event.data, dict):
                    await self._user_q.put(event.data)
            if not drained:
                await asyncio.sleep(0.02)

    async def _rpc(self, method, params, timeout=None):
        self._next_id += 1
        rid = self._next_id
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": rid,
        }
        fut = self._loop.create_future()
        self._pending[rid] = {"method": method, "future": fut}
        try:
            async with self._send_lock:
                await self._ws.send_str(json.dumps(payload))
        except Exception as exc:
            self._pending.pop(rid, None)
            if not fut.done():
                fut.set_result({"error": {"code": 1, "message": str(exc)}})
            return fut.result()

        stop_task = asyncio.create_task(self._stop_event.wait())
        try:
            done, _pending = await asyncio.wait(
                {fut, stop_task},
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            stop_task.cancel()

        if fut in done:
            return fut.result()
        self._pending.pop(rid, None)
        if not fut.done():
            fut.cancel()
        if self._stopped or self._stop_event.is_set():
            return {"error": {"code": 1, "message": "connection closed"}}
        return {"error": {"code": 1, "message": f"{method} timed out"}}

    async def _sleep(self, seconds):
        end = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < end:
            if self._stopped or self._stop_event.is_set():
                return
            await asyncio.sleep(min(0.05, end - time.monotonic()))

    async def _handshake(self):
        params = {
            "client_name": "gsat",
            "version": vinfo.__version__,
            "type": "desktop",
            "url": "https://github.com/duembeg/gsat",
        }
        # api_key stays in the RPC params only. Do not log params.
        if self._api_key:
            params["api_key"] = self._api_key

        ident = await self._rpc(
            "server.connection.identify", params, timeout=self._connect_timeout_s
        )
        if self._stopped:
            return
        if not ident or ident.get("error"):
            msg = _error_message(ident, "identify rejected")
            self.notify_event_listeners(gc.EV_ABORT, f"Klipper: {msg}\n")
            self._stopped = True
            return

        deadline = time.monotonic() + self._connect_timeout_s
        state = None
        while not self._stopped:
            info = await self._rpc("server.info", {}, timeout=self._connect_timeout_s)
            if self._stopped:
                return
            if not info or info.get("error"):
                msg = _error_message(info, "server.info failed")
                self.notify_event_listeners(gc.EV_ABORT, f"Klipper: {msg}\n")
                self._stopped = True
                return
            state = (info.get("result") or {}).get("klippy_state")
            if state == "ready":
                break
            now = time.monotonic()
            if now >= deadline:
                self.notify_event_listeners(
                    gc.EV_ABORT,
                    f"Klipper: klippy not ready (state={state}) "
                    f"within {self._connect_timeout_s:.0f}s\n",
                )
                self._stopped = True
                return
            await self._sleep(min(SERVER_INFO_POLL_SEC, deadline - now))
        if self._stopped or state != "ready":
            return

        pinfo = await self._rpc("printer.info", {}, timeout=self._connect_timeout_s)
        if self._stopped:
            return
        if not pinfo or pinfo.get("error"):
            msg = _error_message(pinfo, "printer.info failed")
            self.notify_event_listeners(gc.EV_ABORT, f"Klipper: {msg}\n")
            self._stopped = True
            return
        self._printer_info = pinfo.get("result") or {}

        sub = await self._rpc(
            "printer.objects.subscribe",
            {"objects": SUBSCRIBE_OBJECTS},
            timeout=self._connect_timeout_s,
        )
        if self._stopped:
            return
        if not sub or sub.get("error"):
            msg = _error_message(sub, "subscribe failed")
            self.notify_event_listeners(gc.EV_ABORT, f"Klipper: {msg}\n")
            self._stopped = True
            return
        _merge_status(self._cache, (sub.get("result") or {}).get("status") or {})

        if self._idle_timeout_sec > 0:
            script = f"SET_IDLE_TIMEOUT TIMEOUT={self._idle_timeout_sec:g}"
            idle = await self._rpc(
                "printer.gcode.script",
                {"script": script},
                timeout=self._connect_timeout_s,
            )
            if idle and idle.get("error"):
                msg = _error_message(idle, "SET_IDLE_TIMEOUT failed")
                self.notify_event_listeners(
                    gc.EV_RXDATA, {"_gsat": "note", "text": f"Klipper: {msg}\n"}
                )

        if self._stopped:
            return
        self._emit_status()
        self.notify_event_listeners(
            gc.EV_RXDATA,
            {
                "_gsat": "ready",
                "info": self._printer_info,
                "status": copy.deepcopy(self._cache),
            },
        )

    async def _on_klippy_ready(self):
        """Klippy came back (firmware restart). Refresh info and subscriptions."""
        if self._stopped or self._ws is None or self._ws.closed:
            return
        pinfo = await self._rpc("printer.info", {})
        if pinfo and not pinfo.get("error"):
            self._printer_info = pinfo.get("result") or self._printer_info
        sub = await self._rpc(
            "printer.objects.subscribe", {"objects": SUBSCRIBE_OBJECTS}
        )
        if sub and not sub.get("error"):
            _merge_status(self._cache, (sub.get("result") or {}).get("status") or {})
        if self._idle_timeout_sec > 0 and not self._stopped:
            script = f"SET_IDLE_TIMEOUT TIMEOUT={self._idle_timeout_sec:g}"
            await self._rpc("printer.gcode.script", {"script": script})
        if self._stopped:
            return
        self._emit_status()
        self.notify_event_listeners(
            gc.EV_RXDATA,
            {
                "_gsat": "ready",
                "info": self._printer_info,
                "status": copy.deepcopy(self._cache),
            },
        )

    async def _serve(self):
        while not self._stopped:
            try:
                item = await asyncio.wait_for(self._user_q.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            await self._dispatch_user(item)

    async def _dispatch_user(self, item):
        method = item.get("method")
        params = item.get("params") or {}
        kind = item.get("kind") or ""
        token = item.get("token")
        resp = await self._rpc(method, params)
        if self._stopped and (not resp or resp.get("error", {}).get("message") == "connection closed"):
            return
        if (
            method == "printer.objects.query"
            and resp
            and not resp.get("error")
        ):
            _merge_status(self._cache, (resp.get("result") or {}).get("status") or {})
            self._emit_status()
            return
        self.notify_event_listeners(
            gc.EV_RXDATA,
            {
                "_gsat": "rpc",
                "method": method,
                "kind": kind,
                "token": token,
                "error": None if not resp else resp.get("error"),
                "result": None if not resp else resp.get("result"),
            },
        )


def _error_message(resp, fallback):
    if not isinstance(resp, dict):
        return fallback
    err = resp.get("error")
    if isinstance(err, dict) and err.get("message"):
        return str(err.get("message"))
    if err:
        return str(err)
    return fallback


class MachIf_Klipper(mi.MachIf_Base):
    """Klipper through Moonraker. No SerialPortThread."""

    def __init__(self):
        super().__init__(
            ID, NAME, BUFFER_MAX_SIZE, BUFFER_INIT_VAL, BUFFER_WATERMARK_PRCNT
        )
        self._thread = None
        self._host = ""
        self._port = 7125
        self._api_key = ""
        self._use_tls = False
        self._connect_timeout_ms = 5000
        self._idle_timeout_sec = 0
        self._dro_source = "live"
        self._status = {}
        self._printer_info = {}
        self._outstanding = 0
        self._inflight_gcode = None
        self._rpc_token = 0
        self._seen_nonzero_live = False
        self._klippy_disconnected = False

    def _init(self):
        self._outstanding = 0
        self._inflight_gcode = None
        self._seen_nonzero_live = False
        self._klippy_disconnected = False

    def factory(self):
        return MachIf_Klipper()

    def _cfg(self, key, default):
        if gc.CONFIG_DATA is None:
            return default
        val = gc.CONFIG_DATA.get(f"/machine/MachIfSpecific/klipper/{key}/Value", default)
        return default if val is None else val

    def init(self):
        host = str(self._cfg("Host", "") or "").strip()
        try:
            port = int(self._cfg("Port", 7125))
        except (TypeError, ValueError):
            port = 7125
        try:
            timeout_ms = int(self._cfg("ConnectTimeout", 5000))
        except (TypeError, ValueError):
            timeout_ms = 5000
        try:
            idle = float(self._cfg("IdleTimeoutSec", 0) or 0)
        except (TypeError, ValueError):
            idle = 0.0

        self._host = host
        self._port = port
        self._api_key = str(self._cfg("ApiKey", "") or "")
        self._use_tls = bool(self._cfg("UseTls", False))
        self._connect_timeout_ms = timeout_ms
        self._idle_timeout_sec = idle
        self._dro_source = str(self._cfg("DroSource", "live") or "live")
        # Base init reads the serial port. Klipper ignores /machine/Port and Baud.
        self.serialName = host
        self.serialBaud = port

    def encode(self, data, bookkeeping=True):
        if isinstance(data, bytes):
            data = data.decode("utf-8", "replace")
        return data

    def decode(self, data):
        return {}

    def okToSend(self, data):
        return self._outstanding < 1

    def isSerialPortOpen(self):
        return self._serialPortOpen

    def tick(self):
        pass

    def open(self):
        if not self._host:
            self.add_event(gc.EV_ABORT, "Klipper: Moonraker host is empty\n")
            return
        scheme = "wss" if self._use_tls else "ws"
        url = f"{scheme}://{self._host}:{self._port}/websocket"
        self._status = {}
        self._printer_info = {}
        self._init()
        self._thread = MoonrakerThread(
            self,
            url,
            self._api_key,
            self._connect_timeout_ms,
            self._idle_timeout_sec,
        )

    def close(self):
        thread = self._thread
        self._thread = None
        if thread is None:
            return
        if thread.is_alive():
            thread.add_event(gc.EV_CMD_EXIT, None)
            thread.join(timeout=5.0)
        else:
            thread.join(timeout=0.1)

    def read(self):
        dict_data = {}
        try:
            event = self._eventQueue.get_nowait()
        except queue.Empty:
            return dict_data

        if event.event_id == gc.EV_RXDATA:
            dict_data = self._handle_rx(event.data)
        elif event.event_id == gc.EV_TXDATA:
            if event.data:
                dict_data["tx_data"] = event.data
        elif event.event_id in (
            gc.EV_EXIT,
            gc.EV_ABORT,
            gc.EV_SER_PORT_OPEN,
            gc.EV_SER_PORT_CLOSE,
        ):
            if event.event_id == gc.EV_ABORT:
                self._outstanding = 0
                self._inflight_gcode = None
            dict_data["event"] = {"id": event.event_id, "data": event.data}
            if event.event_id == gc.EV_SER_PORT_OPEN:
                self._serialPortOpen = True
            elif event.event_id == gc.EV_SER_PORT_CLOSE:
                self._serialPortOpen = False
        return dict_data

    def _handle_rx(self, data):
        if not isinstance(data, dict):
            text = "" if data is None else str(data)
            if text and not text.endswith("\n"):
                text += "\n"
            return {"rx_data": text} if text else {}

        kind = data.get("_gsat")
        if kind == "status":
            self._status = data.get("status") or {}
            return self._sr_dict()
        if kind == "ready":
            self._printer_info = data.get("info") or {}
            if data.get("status"):
                self._status = data["status"]
            self._klippy_disconnected = False
            return self._banner_dict()
        if kind == "gcode":
            text = str(data.get("text") or "")
            if text and not text.endswith("\n"):
                text += "\n"
            return {"rx_data": text} if text else {}
        if kind == "note":
            text = str(data.get("text") or "")
            if text and not text.endswith("\n"):
                text += "\n"
            return {"rx_data": text} if text else {}
        if kind == "klippy":
            if data.get("state") == "disconnected":
                self._klippy_disconnected = True
                out = self._sr_dict()
                out["rx_data"] = "Klipper disconnected\n"
                return out
            self._klippy_disconnected = False
            return {}
        if kind == "sysinfo":
            ver = str(data.get("version") or "")
            text = str(data.get("text") or "Klipper\n")
            return {"r": {"fb": ver, "machif": NAME}, "rx_data": text}
        if kind == "rpc":
            return self._handle_rpc(data)
        return {}

    def _handle_rpc(self, data):
        kind = data.get("kind")
        err = data.get("error")
        if kind == "gcode" and data.get("token") == self._inflight_gcode:
            self._outstanding = 0
            self._inflight_gcode = None
        if err:
            msg, code = _rpc_error(err)
            if kind == "gcode":
                return {
                    "r": {},
                    "f": [0, code, 0],
                    "rx_data": f"error: {msg}\n",
                    "rx_data_info": msg,
                }
            return {"rx_data": f"error: {msg}\n", "rx_data_info": msg}
        if kind == "gcode":
            return {"r": {}, "f": [0, 0, 0], "rx_data": "ok\n"}
        if data.get("result") is not None:
            return {"rx_data": "ok\n"}
        return {}

    def _banner_dict(self):
        ver = str((self._printer_info or {}).get("software_version") or "")
        banner = f"Klipper {ver} via Moonraker".strip()
        return {
            "r": {"init": banner, "fb": ver, "machif": NAME},
            "rx_data": banner + "\n",
        }

    def _homed_axes(self):
        toolhead = self._status.get("toolhead") or {}
        return str(toolhead.get("homed_axes") or "")

    def _map_stat(self):
        webhooks = self._status.get("webhooks") or {}
        state = str(webhooks.get("state") or "")
        message = str(webhooks.get("state_message") or "")
        if state in ("shutdown", "error"):
            return "Alarm", message
        if state == "startup" or self._klippy_disconnected:
            return "Sleep", ""
        print_state = (self._status.get("print_stats") or {}).get("state")
        if print_state == "paused":
            return "Hold", ""
        idle = (self._status.get("idle_timeout") or {}).get("state")
        if idle == "Printing":
            return "Run", ""
        return "Idle", ""

    def _dro(self):
        motion = self._status.get("motion_report") or {}
        gcode_move = self._status.get("gcode_move") or {}
        live = _xyz(motion.get("live_position"))
        gcode_pos = _xyz(gcode_move.get("gcode_position"))
        machine_pos = _xyz(gcode_move.get("position"))
        try:
            vel_mm_s = float(motion.get("live_velocity") or 0.0)
        except (TypeError, ValueError):
            vel_mm_s = 0.0

        if any(v != 0.0 for v in live) or vel_mm_s != 0.0:
            self._seen_nonzero_live = True

        # Right after homing, before the first move, live_position is all
        # zeros while gcode_position already has the real commanded point.
        commanded = str(self._dro_source).lower() == "commanded"
        zero_rest = all(v == 0.0 for v in live) and vel_mm_s == 0.0
        if commanded or zero_rest or not self._seen_nonzero_live:
            return gcode_pos, vel_mm_s * 60.0

        work = []
        for i in range(3):
            work.append(live[i] - (machine_pos[i] - gcode_pos[i]))
        return work, vel_mm_s * 60.0

    def _sr_dict(self):
        pos, vel = self._dro()
        stat, info = self._map_stat()
        sr = {
            "stat": stat,
            "posx": pos[0],
            "posy": pos[1],
            "posz": pos[2],
            "vel": vel,
            "ib": [1, self._outstanding],
            "homed": self._homed_axes(),
        }
        out = {"sr": sr}
        if info:
            out["rx_data"] = f"{stat}\n"
            out["rx_data_info"] = info
        return out

    def _note(self, text):
        self.add_event(gc.EV_RXDATA, {"_gsat": "note", "text": text})

    def _rpc(self, method, params, kind, token=None):
        item = {"method": method, "params": params or {}, "kind": kind, "token": token}
        if self._thread is None:
            self.add_event(
                gc.EV_RXDATA,
                {
                    "_gsat": "rpc",
                    "method": method,
                    "kind": kind,
                    "token": token,
                    "error": {"code": 1, "message": "Klipper is not connected"},
                    "result": None,
                },
            )
            return
        self._thread.add_event(gc.EV_CMD_TXDATA, item)

    def write(self, txData, raw_write=False):
        if isinstance(txData, bytes):
            txData = txData.decode("utf-8", "replace")
        if txData is None:
            return 0
        script = str(txData).strip()
        if not script:
            return 0
        if self._thread is None:
            return 0
        self._rpc_token += 1
        token = self._rpc_token
        self._inflight_gcode = token
        self._outstanding = 1
        self._rpc("printer.gcode.script", {"script": script}, kind="gcode", token=token)
        return len(str(txData))

    def _axis_words(self, axes):
        words = []
        for axis in _AXIS_ORDER:
            if axes and axis in axes:
                words.append(f"{axis.upper()}{_fmt_num(axes.get(axis))}")
        return words

    def _feed(self, axes):
        if not axes or "feed" not in axes or axes.get("feed") in (None, ""):
            return DEFAULT_JOG_FEED
        return axes.get("feed")

    def _send_motion(self, axes, absolute):
        feed = _fmt_num(self._feed(axes))
        words = self._axis_words(axes)
        line = "G1" if not words else "G1 " + " ".join(words)
        line = f"{line} F{feed}"
        if absolute:
            script = f"G90\n{line}"
        else:
            script = f"G91\n{line}\nG90"
        self.add_event(gc.EV_TXDATA, script + "\n")
        self.write(script + "\n")

    def doMove(self, dict_axis_coor):
        self._send_motion(dict_axis_coor, absolute=True)

    def doMoveRelative(self, dict_axis_coor):
        self._send_motion(dict_axis_coor, absolute=False)

    def doFastMove(self, dict_axis_coor):
        self._send_motion(dict_axis_coor, absolute=True)

    def doFastMoveRelative(self, dict_axis_coor):
        self._send_motion(dict_axis_coor, absolute=False)

    def doJogMove(self, dict_axis_coor):
        self.doMove(dict_axis_coor)

    def doJogMoveRelative(self, dict_axis_coor):
        self.doMoveRelative(dict_axis_coor)

    def doJogFastMove(self, dict_axis_coor):
        self.doFastMove(dict_axis_coor)

    def doJogFastMoveRelative(self, dict_axis_coor):
        self.doFastMoveRelative(dict_axis_coor)

    def doHome(self, dict_axis):
        # Klipper G28 takes axis letters (G28 X Y Z), not coordinates.
        words = []
        for axis in _AXIS_ORDER:
            if dict_axis and axis in dict_axis:
                words.append(axis.upper())
        script = "G28" if not words else "G28 " + " ".join(words)
        self.add_event(gc.EV_TXDATA, script + "\n")
        self.write(script + "\n")

    def doSetAxis(self, dict_axis_coor):
        words = self._axis_words(dict_axis_coor)
        script = "G92" if not words else "G92 " + " ".join(words)
        self.add_event(gc.EV_TXDATA, script + "\n")
        self.write(script + "\n")

    def doReset(self):
        self._outstanding = 0
        self._inflight_gcode = None
        self._init()
        self.add_event(gc.EV_TXDATA, "printer.emergency_stop\n")
        self._rpc("printer.emergency_stop", {}, kind="estop")

    def doClearAlarm(self):
        self.add_event(gc.EV_TXDATA, "printer.firmware_restart\n")
        self._rpc("printer.firmware_restart", {}, kind="restart")

    def doGetStatus(self):
        self._rpc("printer.objects.query", {"objects": SUBSCRIBE_OBJECTS}, kind="query")

    def doGetSystemInfo(self):
        ver = str((self._printer_info or {}).get("software_version") or "")
        banner = f"Klipper {ver} via Moonraker".strip()
        self.add_event(
            gc.EV_RXDATA,
            {"_gsat": "sysinfo", "version": ver, "text": banner + "\n"},
        )

    def doFeedHold(self):
        self._note(NO_HOLD_NOTE)

    def doCycleStartResume(self):
        self._note(NO_HOLD_NOTE)

    def doQueueFlush(self):
        self._note(NO_HOLD_NOTE)

    def doJogStop(self):
        self._note(NO_HOLD_NOTE)

    def doProbe(self, dict_axis_coor):
        self._note("Klipper: probing is not part of this interface\n")

    def doInitComm(self):
        pass


def _rpc_error(err):
    if isinstance(err, dict):
        msg = str(err.get("message") or "error")
        try:
            code = int(err.get("code") or 1)
        except (TypeError, ValueError):
            code = 1
    else:
        msg = str(err or "error")
        code = 1
    if code == 0:
        code = 1
    return msg, code
