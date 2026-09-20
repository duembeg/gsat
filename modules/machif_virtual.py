"""----------------------------------------------------------------------------
    machif_virtual.py

    PySide-only virtual machine target: same progexec send/ack path as a
    serial board, no UART. Speaks a small grbl-like ok/status dialect so
    Run / Step / CLI work. Motion goes through VirtualCnc.

    Not listed in MACHIF_CLS_LIST (wx settings stay unchanged). Enabled via
    /pysideWorkbench/VirtualCnc/Enabled.
----------------------------------------------------------------------------"""
from __future__ import annotations

import queue
import re

import modules.config as gc
import modules.machif as mi
from modules.virtual_cnc import VirtualCnc

ID = 1900
NAME = "virtual"
BUFFER_MAX_SIZE = 127
BUFFER_INIT_VAL = 0
BUFFER_WATERMARK_PRCNT = 0.90

CONFIG_KEY = "/pysideWorkbench/VirtualCnc/Enabled"

_STATUS = re.compile(
    r"<(\w+)\|WPos:([-+]?\d+\.?\d*),([-+]?\d+\.?\d*),([-+]?\d+\.?\d*)\|FS:"
)


def virtual_cnc_enabled() -> bool:
    if gc.CONFIG_DATA is None:
        return False
    try:
        return bool(gc.CONFIG_DATA.get(CONFIG_KEY, False))
    except Exception:
        return False


class MachIf_Virtual(mi.MachIf_Base):
    """In-process plotter target. No SerialPortThread."""

    def __init__(self):
        super().__init__(
            ID, NAME, BUFFER_MAX_SIZE, BUFFER_INIT_VAL, BUFFER_WATERMARK_PRCNT
        )
        self.vc = VirtualCnc()
        self._stat = "Idle"
        self.cmdClearAlarm = "$X\n"
        self.cmdHome = "$H\n"
        self.cmdInitComm = ""
        self.cmdQueueFlush = ""
        self.cmdReset = "\x18"
        self.cmdStatus = "?"
        self.cmdSystemInfo = "$I\n"
        self.cmdPostInit = "$I\n"
        self._pending_jog = False

    def _init(self):
        self._stat = "Idle"
        self._pending_jog = False

    def doJogMove(self, dict_axis_coor):
        self._pending_jog = True
        super().doJogMove(dict_axis_coor)

    def doJogMoveRelative(self, dict_axis_coor):
        self._pending_jog = True
        super().doJogMoveRelative(dict_axis_coor)

    def doJogFastMove(self, dict_axis_coor):
        self._pending_jog = True
        super().doJogFastMove(dict_axis_coor)

    def doJogFastMoveRelative(self, dict_axis_coor):
        self._pending_jog = True
        super().doJogFastMoveRelative(dict_axis_coor)

    def factory(self):
        return MachIf_Virtual()

    def init(self):
        # No serial name/baud — open() does not touch a port.
        self.serialName = NAME
        self.serialBaud = 0

    def encode(self, data, bookkeeping=True):
        if isinstance(data, bytes):
            data = data.decode("utf-8", "replace")
        return super().encode(data)

    def okToSend(self, data):
        return True

    def isSerialPortOpen(self):
        return self._serialPortOpen

    def _status_line(self) -> str:
        p = self.vc.position
        return (
            f"<{self._stat}|WPos:{p.x:.3f},{p.y:.3f},{p.z:.3f}|FS:0,0>\n"
        )

    def _queue_rx(self, text: str) -> None:
        self.add_event(gc.EV_RXDATA, text)

    def _queue_ok(self) -> None:
        self._queue_rx(self._status_line())
        self._queue_rx("ok\n")

    def decode(self, data):
        data_dict: dict = {}
        if not data:
            return data_dict
        text = data if isinstance(data, str) else data.decode("utf-8", "replace")
        stripped = text.strip()

        if stripped.startswith("Grbl") or "Virtual CNC" in stripped:
            data_dict["r"] = {"init": stripped, "machif": NAME}
            data_dict["rx_data"] = text
            return data_dict

        if stripped == "ok":
            data_dict["r"] = {}
            data_dict["f"] = [0, 0, 0]
            data_dict["rx_data"] = text
            return data_dict

        match = _STATUS.search(text)
        if match is not None:
            data_dict["sr"] = {
                "stat": match.group(1),
                "posx": float(match.group(2)),
                "posy": float(match.group(3)),
                "posz": float(match.group(4)),
                "vel": 0.0,
            }
            data_dict["rx_data"] = text
        else:
            data_dict["rx_data"] = text
        return data_dict

    def open(self):
        self.vc.reset()
        self._stat = "Idle"
        self._serialPortOpen = True
        self.add_event(gc.EV_SER_PORT_OPEN, None)
        self._queue_rx("Grbl 1.1f [Virtual CNC]\n")
        self._queue_rx(self._status_line())

    def close(self):
        self._serialPortOpen = False
        self.add_event(gc.EV_SER_PORT_CLOSE, None)
        self.add_event(gc.EV_EXIT, None)

    def read(self):
        """Same event dispatch as MachIf_Base.read, without a serial thread."""
        dict_data: dict = {}
        try:
            e = self._eventQueue.get_nowait()
        except queue.Empty:
            return dict_data

        if e.event_id == gc.EV_RXDATA:
            if e.data:
                dict_data = self.decode(e.data)
                dict_data["rx_data"] = e.data
        elif e.event_id == gc.EV_TXDATA:
            if e.data:
                dict_data["tx_data"] = e.data
        elif e.event_id in (
            gc.EV_EXIT,
            gc.EV_ABORT,
            gc.EV_SER_PORT_OPEN,
            gc.EV_SER_PORT_CLOSE,
        ):
            dict_data["event"] = {"id": e.event_id, "data": e.data}
            if e.event_id == gc.EV_SER_PORT_OPEN:
                self._serialPortOpen = True
            elif e.event_id == gc.EV_SER_PORT_CLOSE:
                self._serialPortOpen = False
        return dict_data

    def _handle_line(self, line: str) -> None:
        raw = line.strip()
        if not raw:
            return
        if raw == "?" or raw == self.cmdStatus:
            self._queue_rx(self._status_line())
            return
        if raw == "!":
            self._stat = "Hold"
            self._queue_rx(self._status_line())
            return
        if raw == "~":
            self._stat = "Idle"
            self._queue_rx(self._status_line())
            return
        if raw == "$X":
            self._stat = "Idle"
            self._queue_ok()
            return
        if raw == "$I":
            self._queue_rx("[VER:1.1f.virtual:]\n")
            self._queue_ok()
            return
        if raw == "$H":
            self.vc.apply_line("G90 G0 X0 Y0 Z0")
            self._stat = "Idle"
            self._queue_ok()
            return
        if raw == "\x18" or line == self.cmdReset:
            self.vc.reset()
            self._stat = "Idle"
            self._queue_rx("Grbl 1.1f [Virtual CNC]\n")
            self._queue_ok()
            return
        payload = raw
        is_jog = payload.startswith("$J=") or (
            self._pending_jog and any(ch in payload.upper() for ch in "XYZ")
        )
        if payload.startswith("$J="):
            payload = payload[3:]
        if is_jog:
            self._pending_jog = False
        self._stat = "Idle"
        self.vc.apply_line(payload, jog=is_jog)
        self._queue_ok()

    def write(self, txData, raw_write=False):
        if isinstance(txData, bytes):
            txData = txData.decode("utf-8", "replace")
        sent = 0
        if not txData:
            return 0
        # Reset is a raw ctrl-x, not a newline-delimited line
        if txData == "\x18":
            self._handle_line(txData)
            return 1
        lines = txData.splitlines(True)
        if not lines:
            lines = [txData]
        for line in lines:
            self._handle_line(line)
            sent += len(line)
        return sent

    def doInitComm(self):
        pass

    def doGetSystemInfo(self):
        self._queue_rx("[VER:1.1f.virtual:]\n")

    def tick(self):
        pass
