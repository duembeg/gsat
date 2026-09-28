"""In-process Moonraker stand-in for machif_klipper tests.

Listens on 127.0.0.1 with an ephemeral port. No hardware and no LAN.
"""

import asyncio
import copy
import json
import re
import threading
import time

from aiohttp import web

_MOVE_RE = re.compile(r"\bG0+\b|\bG0*1\b")
_G28_RE = re.compile(r"\bG28\b")


def _merge(cache, update):
    if not isinstance(update, dict):
        return
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(cache.get(key), dict):
            _merge(cache[key], value)
        else:
            cache[key] = value


def _initial_status(homed):
    return {
        "motion_report": {
            "live_position": [0.0, 0.0, 0.0, 0.0],
            "live_velocity": 0.0,
        },
        "toolhead": {
            "homed_axes": homed,
            "position": [0.0, 0.0, 0.0, 0.0],
            "axis_minimum": [0.0, 0.0, 0.0, 0.0],
            "axis_maximum": [250.0, 210.0, 220.0, 0.0],
        },
        "gcode_move": {
            "gcode_position": [0.0, 0.0, 0.0, 0.0],
            "position": [0.0, 0.0, 0.0, 0.0],
            "absolute_coordinates": True,
            "speed": 0.0,
        },
        "idle_timeout": {"state": "Idle"},
        "webhooks": {"state": "ready", "state_message": "Printer is ready"},
        "print_stats": {"state": "standby"},
    }


class FakeMoonraker:
    """aiohttp websocket server that speaks the Moonraker subset GSAT uses."""

    def __init__(self, required_api_key=None, homed="", gcode_delay=0.0):
        # required_api_key is None when the printer trusts the client.
        # A string (including "") means identify must present that exact key.
        self.required_api_key = required_api_key
        self.gcode_delay = float(gcode_delay or 0.0)
        self.status = _initial_status(homed)
        self.requests = []
        self.host = "127.0.0.1"
        self.port = None
        self._lock = threading.Lock()
        self._clients = []
        self._loop = None
        self._thread = None
        self._stop_fut = None
        self._ready = threading.Event()
        self._error = None

    def start(self):
        self._thread = threading.Thread(target=self._thread_main, name="fake-moonraker", daemon=True)
        self._thread.start()
        if not self._ready.wait(5):
            raise RuntimeError(self._error or "fake Moonraker did not start")
        if self._error is not None:
            raise RuntimeError(self._error)
        return self.port

    def stop(self):
        loop = self._loop
        fut = self._stop_fut
        if loop is not None and fut is not None and loop.is_running() and not fut.done():
            loop.call_soon_threadsafe(fut.set_result, None)
        if self._thread is not None:
            self._thread.join(timeout=3)

    def snapshot_requests(self):
        with self._lock:
            return copy.deepcopy(self.requests)

    def push_status(self, diff):
        if self._loop is None:
            raise RuntimeError("fake Moonraker is not running")
        fut = asyncio.run_coroutine_threadsafe(self._broadcast_diff(diff), self._loop)
        fut.result(timeout=2)

    def _record(self, method, params, rid):
        with self._lock:
            self.requests.append({"method": method, "params": copy.deepcopy(params), "id": rid})

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._serve())
        except Exception as exc:
            self._error = exc
            self._ready.set()
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    async def _serve(self):
        app = web.Application()
        app.router.add_get("/websocket", self._handle)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, 0)
        try:
            await site.start()
            sockets = list(site._server.sockets)
            self.port = sockets[0].getsockname()[1]
            self._stop_fut = self._loop.create_future()
            self._ready.set()
            await self._stop_fut
        finally:
            await self._close_clients()
            await runner.cleanup()

    async def _close_clients(self):
        with self._lock:
            clients = list(self._clients)
        for conn in clients:
            try:
                if not conn.ws.closed:
                    await conn.ws.close()
            except Exception:
                pass

    async def _handle(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        conn = _Connection(self, ws)
        with self._lock:
            self._clients.append(conn)
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    # A slow gcode.script must not block emergency_stop.
                    asyncio.create_task(conn.handle(msg.data))
                elif msg.type in (web.WSMsgType.ERROR, web.WSMsgType.CLOSE, web.WSMsgType.CLOSED):
                    break
        finally:
            with self._lock:
                if conn in self._clients:
                    self._clients.remove(conn)
        return ws

    async def _broadcast_diff(self, diff):
        _merge(self.status, diff)
        note = {
            "jsonrpc": "2.0",
            "method": "notify_status_update",
            "params": [diff, time.time()],
        }
        raw = json.dumps(note)
        with self._lock:
            clients = list(self._clients)
        for conn in clients:
            await conn.send_raw(raw)


class _Connection:
    def __init__(self, owner, ws):
        self.owner = owner
        self.ws = ws
        self.info_calls = 0
        self._send_lock = asyncio.Lock()

    async def handle(self, raw):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        method = data.get("method")
        params = data.get("params") or {}
        rid = data.get("id")
        self.owner._record(method, params, rid)

        if method == "server.connection.identify":
            await self._identify(rid, params)
        elif method == "server.info":
            await self._server_info(rid)
        elif method == "printer.info":
            await self._result(rid, {
                "state": self.owner.status["webhooks"]["state"],
                "state_message": self.owner.status["webhooks"]["state_message"],
                "software_version": "v0.12.0-test",
                "hostname": "mk4sklipper",
            })
        elif method == "printer.objects.subscribe":
            await self._result(rid, {"status": copy.deepcopy(self.owner.status), "eventtime": time.time()})
        elif method == "printer.objects.query":
            await self._result(rid, {"status": copy.deepcopy(self.owner.status), "eventtime": time.time()})
        elif method == "printer.gcode.script":
            await self._gcode(rid, params.get("script") or "")
        elif method == "printer.emergency_stop":
            await self._estop(rid)
        elif method == "printer.firmware_restart":
            await self._firmware_restart(rid)
        else:
            await self._error(rid, -32601, f"Method not found: {method}")

    async def send_raw(self, raw):
        if self.ws.closed:
            return
        try:
            async with self._send_lock:
                if self.ws.closed:
                    return
                await self.ws.send_str(raw)
        except Exception:
            return

    async def _identify(self, rid, params):
        required = self.owner.required_api_key
        if required is not None and params.get("api_key") != required:
            await self._error(rid, 401, "Unauthorized")
            return
        await self._result(rid, {"connection_id": 1})

    async def _server_info(self, rid):
        self.info_calls += 1
        state = "startup" if self.info_calls == 1 else "ready"
        await self._result(rid, {
            "klippy_connected": state == "ready",
            "klippy_state": state,
            "moonraker_version": "v0.8.0-test",
        })

    async def _gcode(self, rid, script):
        if self.owner.gcode_delay and _G28_RE.search(str(script).upper()):
            await asyncio.sleep(self.owner.gcode_delay)
        if "X999" in script:
            await self._error(rid, 400, "Move out of range")
            return
        if _is_move(script) and not _axes_homed(self.owner.status["toolhead"]["homed_axes"]):
            await self._error(rid, 400, "Must home axis first")
            return
        if _G28_RE.search(script.upper()):
            self.owner.status["toolhead"]["homed_axes"] = "xyz"
            await self._result(rid, "ok")
            await self.owner._broadcast_diff({"toolhead": {"homed_axes": "xyz"}})
            return
        await self._result(rid, "ok")

    async def _estop(self, rid):
        await self._result(rid, "ok")
        note = {
            "jsonrpc": "2.0",
            "method": "notify_klippy_shutdown",
            "params": [],
        }
        await self.send_raw(json.dumps(note))
        await self.owner._broadcast_diff({
            "webhooks": {
                "state": "shutdown",
                "state_message": "Shutdown due to emergency stop",
            },
            "idle_timeout": {"state": "Idle"},
        })

    async def _firmware_restart(self, rid):
        self.owner.status["toolhead"]["homed_axes"] = ""
        await self._result(rid, "ok")
        note = {
            "jsonrpc": "2.0",
            "method": "notify_klippy_ready",
            "params": [],
        }
        await self.send_raw(json.dumps(note))
        await self.owner._broadcast_diff({
            "webhooks": {"state": "ready", "state_message": "Printer is ready"},
            "idle_timeout": {"state": "Idle"},
            "print_stats": {"state": "standby"},
            "toolhead": {"homed_axes": ""},
        })

    async def _result(self, rid, result):
        await self.send_raw(json.dumps({
            "jsonrpc": "2.0",
            "id": rid,
            "result": result,
        }))

    async def _error(self, rid, code, message):
        await self.send_raw(json.dumps({
            "jsonrpc": "2.0",
            "id": rid,
            "error": {"code": code, "message": message},
        }))


def _axes_homed(homed):
    text = str(homed or "")
    return all(axis in text for axis in ("x", "y", "z"))


def _is_move(script):
    for raw in str(script).splitlines():
        line = raw.split(";", 1)[0].upper()
        if not line.strip() or _G28_RE.search(line):
            continue
        if _MOVE_RE.search(line):
            return True
    return False
