"""Klipper machif against an in-process Moonraker. No printer and no LAN."""

import ast
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager

import modules.config as gc
import modules.machif_config as mi
import modules.machif_progexec as mi_progexec
from modules.machif_klipper import ID, NAME, MachIf_Klipper

from tests.unit.fake_moonraker import FakeMoonraker

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _config(port, api_key="", idle=0, dro="live", timeout_ms=5000):
    cfg = gc.ConfigData(None)
    cfg.set("/machine/Device", "klipper")
    cfg.set("/machine/Port", "")
    cfg.set("/machine/Baud", "115200")
    cfg.set("/machine/InitScriptEnable", False)
    cfg.set("/machine/InitScript", "")
    cfg.set("/machine/FilterGcodesEnable", False)
    cfg.set("/machine/FilterGcodes", "")
    cfg.set("/pysideWorkbench/VirtualCnc/Enabled", False)
    spec = "/machine/MachIfSpecific/klipper"
    cfg.set(f"{spec}/Host/Value", "127.0.0.1")
    cfg.set(f"{spec}/Port/Value", int(port))
    cfg.set(f"{spec}/ApiKey/Value", api_key)
    cfg.set(f"{spec}/UseTls/Value", False)
    cfg.set(f"{spec}/ConnectTimeout/Value", int(timeout_ms))
    cfg.set(f"{spec}/IdleTimeoutSec/Value", idle)
    cfg.set(f"{spec}/DroSource/Value", dro)
    return cfg


@contextmanager
def linked(api_key="", required_api_key=None, homed="", idle=0, dro="live", timeout_ms=8000):
    fake = FakeMoonraker(required_api_key=required_api_key, homed=homed)
    fake.start()
    old = gc.CONFIG_DATA
    gc.CONFIG_DATA = _config(fake.port, api_key=api_key, idle=idle, dro=dro, timeout_ms=timeout_ms)
    mach = MachIf_Klipper()
    mach.init()
    mach.open()
    try:
        yield fake, mach
    finally:
        try:
            mach.close()
        finally:
            gc.CONFIG_DATA = old
            fake.stop()


def _collect(mach, timeout, predicate=None):
    found = []
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        item = mach.read()
        if item:
            found.append(item)
            if predicate is not None and predicate(found):
                return found
        else:
            time.sleep(0.02)
    return found


def _has_init(items):
    return any(isinstance(d.get("r"), dict) and d["r"].get("init") for d in items)


def _ack(items, ok=None):
    acks = [d for d in items if "r" in d and "f" in d and "init" not in (d.get("r") or {})]
    if ok is True:
        acks = [d for d in acks if d["f"][1] == 0]
    elif ok is False:
        acks = [d for d in acks if d["f"][1] != 0]
    return acks


def _scripts(fake):
    return [
        r["params"].get("script")
        for r in fake.snapshot_requests()
        if r["method"] == "printer.gcode.script"
    ]


def test_registry_does_not_import_aiohttp():
    assert NAME in mi.MACHIF_LIST
    assert mi.GetMachIfId("klipper") == ID == 1400
    module = mi.GetMachIfModule(ID)
    assert module.getName() == "klipper"
    assert module is not mi.GetMachIfModule(ID)

    with open(os.path.join(_ROOT, "modules", "machif_klipper.py"), encoding="utf-8") as source_file:
        source = source_file.read()
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] != "aiohttp" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "aiohttp"

    script = (
        "import sys\n"
        "import modules.machif_config as mi\n"
        "assert 'aiohttp' not in sys.modules\n"
        "assert 'klipper' in mi.MACHIF_LIST\n"
        "assert mi.GetMachIfId('klipper') == 1400\n"
    )
    subprocess.check_call([sys.executable, "-c", script], cwd=_ROOT)


def test_open_banner_after_ready_sends_api_key():
    with linked(api_key="secret-key") as (fake, mach):
        items = _collect(mach, 8, _has_init)
        ids = [d["event"]["id"] for d in items if "event" in d]
        assert gc.EV_SER_PORT_OPEN in ids
        open_at = next(i for i, d in enumerate(items) if d.get("event", {}).get("id") == gc.EV_SER_PORT_OPEN)
        init_at = next(i for i, d in enumerate(items) if isinstance(d.get("r"), dict) and d["r"].get("init"))
        assert open_at < init_at
        banner = items[init_at]
        assert "Klipper" in banner["r"]["init"]
        assert "Moonraker" in banner["r"]["init"]
        assert banner["r"]["fb"] == "v0.12.0-test"
        assert banner["r"]["machif"] == "klipper"
        assert banner.get("rx_data")
        assert mach._dro_source == "live"

        identify = [r for r in fake.snapshot_requests() if r["method"] == "server.connection.identify"]
        assert identify
        assert identify[0]["params"]["client_name"] == "gsat"
        assert identify[0]["params"]["type"] == "desktop"
        assert identify[0]["params"]["api_key"] == "secret-key"

        sub = [r for r in fake.snapshot_requests() if r["method"] == "printer.objects.subscribe"]
        assert sub
        objects = sub[0]["params"]["objects"]
        assert "live_position" in objects["motion_report"]
        assert "gcode_position" in objects["gcode_move"]

        mach.doGetSystemInfo()
        info = _collect(mach, 1, lambda xs: any(d.get("r", {}).get("fb") and "init" not in d.get("r", {}) for d in xs))
        assert any(d.get("r", {}).get("machif") == "klipper" and d["r"].get("fb") == "v0.12.0-test" for d in info)


def test_wrong_api_key_aborts():
    with linked(api_key="nope", required_api_key="secret-key") as (fake, mach):
        items = _collect(mach, 4, lambda xs: any(d.get("event", {}).get("id") == gc.EV_ABORT for d in xs))
        assert any(d.get("event", {}).get("id") == gc.EV_ABORT for d in items)
        assert not _has_init(items)
        # Give a late banner no room to sneak in after the abort.
        time.sleep(0.2)
        assert not _has_init(_collect(mach, 0.3))


def test_unhomed_move_then_home_then_ok():
    with linked() as (fake, mach):
        assert _collect(mach, 8, _has_init)
        identify = [r for r in fake.snapshot_requests() if r["method"] == "server.connection.identify"]
        assert "api_key" not in identify[0]["params"]

        mach.write("G1 X10\n")
        bad = _collect(mach, 3, lambda xs: _ack(xs, ok=False))
        errs = _ack(bad, ok=False)
        assert errs
        assert errs[0]["f"][1] != 0
        assert errs[0].get("rx_data")
        assert "home" in str(errs[0].get("rx_data_info", "")).lower()

        mach.doHome({"x": 0, "y": 0, "z": 0})
        homed = _collect(mach, 3, lambda xs: _ack(xs, ok=True))
        assert _ack(homed, ok=True)
        assert "G28 X Y Z" in _scripts(fake)

        mach.write("G1 X10\n")
        good = _collect(mach, 3, lambda xs: _ack(xs, ok=True))
        assert _ack(good, ok=True)


def test_status_work_position_velocity_and_stat():
    with linked() as (fake, mach):
        assert _collect(mach, 8, _has_init)

        # live_position is still all zeros, so the DRO must use gcode_position
        # (the formula would have produced x=3 here).
        fake.push_status({
            "motion_report": {"live_position": [0, 0, 0, 0], "live_velocity": 0},
            "gcode_move": {
                "gcode_position": [8, 9, 1, 0],
                "position": [5, 5, 5, 0],
            },
            "toolhead": {"homed_axes": "xy"},
        })
        zero = _wait_sr(mach, lambda sr: sr.get("posx") == 8 and sr.get("posy") == 9)
        assert zero["sr"]["posz"] == 1
        assert zero["sr"]["homed"] == "xy"
        assert zero["sr"]["stat"] == "Idle"
        assert zero["sr"]["ib"] == [1, 0]

        # Non-zero G92-style offset: work = live - (machine - gcode).
        # x = 12 - (10 - 4) = 6, y = 1 - (0 - 2) = 3, vel = 1.5 mm/s * 60.
        fake.push_status({
            "motion_report": {"live_position": [12, 1, 0, 0], "live_velocity": 1.5},
            "gcode_move": {
                "gcode_position": [4, 2, 0, 0],
                "position": [10, 0, 0, 0],
            },
        })
        moved = _wait_sr(mach, lambda sr: sr.get("posx") == 6)
        assert moved["sr"]["posy"] == 3
        assert moved["sr"]["posz"] == 0
        assert moved["sr"]["vel"] == 90

        # Back at a zero live sample, fall back to gcode_position again.
        fake.push_status({
            "motion_report": {"live_position": [0, 0, 0, 0], "live_velocity": 0},
            "gcode_move": {"gcode_position": [7, 8, 9, 0], "position": [3, 3, 3, 0]},
        })
        again = _wait_sr(mach, lambda sr: sr.get("posx") == 7)
        assert again["sr"]["posy"] == 8
        assert again["sr"]["posz"] == 9

        mach._dro_source = "commanded"
        fake.push_status({
            "motion_report": {"live_position": [12, 1, 0, 0], "live_velocity": 2},
            "gcode_move": {"gcode_position": [1, 2, 3, 0], "position": [9, 9, 9, 0]},
        })
        commanded = _wait_sr(mach, lambda sr: sr.get("posx") == 1 and sr.get("vel") == 120)
        assert commanded["sr"]["posy"] == 2
        assert commanded["sr"]["posz"] == 3
        mach._dro_source = "live"

        fake.push_status({
            "webhooks": {"state": "ready", "state_message": ""},
            "print_stats": {"state": "standby"},
            "idle_timeout": {"state": "Printing"},
        })
        assert _wait_sr(mach, lambda sr: sr.get("stat") == "Run")

        fake.push_status({"print_stats": {"state": "paused"}})
        assert _wait_sr(mach, lambda sr: sr.get("stat") == "Hold")

        fake.push_status({
            "webhooks": {"state": "shutdown", "state_message": "MCU shutdown"},
            "print_stats": {"state": "standby"},
            "idle_timeout": {"state": "Idle"},
        })
        alarm = _wait_sr(mach, lambda sr: sr.get("stat") == "Alarm")
        assert "MCU shutdown" in str(alarm.get("rx_data_info", ""))

        fake.push_status({"webhooks": {"state": "error", "state_message": "config error"}})
        error = _wait_sr(mach, lambda sr: sr.get("stat") == "Alarm")
        assert "config error" in str(error.get("rx_data_info", ""))

        fake.push_status({
            "webhooks": {"state": "startup", "state_message": ""},
            "print_stats": {"state": "printing"},
            "idle_timeout": {"state": "Printing"},
        })
        assert _wait_sr(mach, lambda sr: sr.get("stat") == "Sleep")

        fake.push_status({
            "webhooks": {"state": "ready", "state_message": ""},
            "print_stats": {"state": "standby"},
            "idle_timeout": {"state": "Idle"},
        })
        assert _wait_sr(mach, lambda sr: sr.get("stat") == "Idle")


def _wait_sr(mach, predicate, timeout=3):
    found = _collect(
        mach,
        timeout,
        lambda xs: any(d.get("sr") and predicate(d["sr"]) for d in xs),
    )
    matches = [d for d in found if d.get("sr") and predicate(d["sr"])]
    assert matches, found
    return matches[-1]


def test_ok_to_send_tracks_one_gcode():
    with linked(homed="xyz") as (fake, mach):
        assert _collect(mach, 8, _has_init)
        assert mach.okToSend("G1 X1\n") is True
        mach.write("G1 X1\n")
        assert mach.okToSend("G1 X2\n") is False
        assert _collect(mach, 3, lambda xs: _ack(xs, ok=True))
        assert mach.okToSend("G1 X2\n") is True


def test_relative_jog_estop_and_clear_alarm():
    with linked(homed="xyz") as (fake, mach):
        assert _collect(mach, 8, _has_init)

        mach.doJogMoveRelative({"x": 1, "y": -2, "feed": 1500})
        assert _collect(mach, 3, lambda xs: _ack(xs))
        scripts = _scripts(fake)
        assert "G91\nG1 X1 Y-2 F1500\nG90" in scripts

        mach.doJogFastMoveRelative({"y": 2})
        assert _collect(mach, 3, lambda xs: len(_ack(xs)) >= 1)
        assert "G91\nG1 Y2 F3000\nG90" in _scripts(fake)

        mach.doJogMove({"x": 4})
        assert _collect(mach, 3, lambda xs: len(_ack(xs)) >= 1)
        assert "G90\nG1 X4 F3000" in _scripts(fake)

        mach.doSetAxis({"x": 0, "y": 1})
        assert _collect(mach, 3, lambda xs: len(_ack(xs)) >= 1)
        assert "G92 X0 Y1" in _scripts(fake)

        before = len(fake.snapshot_requests())
        mach.doFeedHold()
        mach.doCycleStartResume()
        mach.doQueueFlush()
        mach.doJogStop()
        notes = _collect(mach, 1, lambda xs: sum(1 for d in xs if "no realtime hold" in d.get("rx_data", "")) >= 4)
        assert sum(1 for d in notes if "no realtime hold" in d.get("rx_data", "")) >= 4
        motion = [
            r for r in fake.snapshot_requests()[before:]
            if r["method"] in ("printer.gcode.script", "printer.emergency_stop", "printer.firmware_restart")
        ]
        assert motion == []

        mach.doReset()
        alarm = _collect(mach, 3, lambda xs: any(d.get("sr", {}).get("stat") == "Alarm" for d in xs))
        assert any(d.get("sr", {}).get("stat") == "Alarm" for d in alarm)
        methods = [r["method"] for r in fake.snapshot_requests()]
        assert "printer.emergency_stop" in methods

        before = len(fake.snapshot_requests())
        mach.doClearAlarm()
        end = time.monotonic() + 3
        while time.monotonic() < end:
            methods = [r["method"] for r in fake.snapshot_requests()[before:]]
            if "printer.firmware_restart" in methods:
                break
            mach.read()
            time.sleep(0.02)
        else:
            raise AssertionError(fake.snapshot_requests()[before:])
        assert "printer.firmware_restart" in [r["method"] for r in fake.snapshot_requests()]


def test_idle_timeout_sent_on_ready():
    with linked(idle=30) as (fake, mach):
        assert _collect(mach, 8, _has_init)
        assert "SET_IDLE_TIMEOUT TIMEOUT=30" in _scripts(fake)


def test_close_emits_port_close_and_exit():
    fake = FakeMoonraker()
    fake.start()
    old = gc.CONFIG_DATA
    gc.CONFIG_DATA = _config(fake.port)
    mach = MachIf_Klipper()
    mach.init()
    mach.open()
    thread = mach._thread
    try:
        assert _collect(mach, 8, _has_init)
        mach.close()
        items = _collect(mach, 2, lambda xs: {d.get("event", {}).get("id") for d in xs} >= {gc.EV_SER_PORT_CLOSE, gc.EV_EXIT})
        ids = [d["event"]["id"] for d in items if "event" in d]
        assert gc.EV_SER_PORT_CLOSE in ids
        assert gc.EV_EXIT in ids
        close_at = ids.index(gc.EV_SER_PORT_CLOSE)
        exit_at = ids.index(gc.EV_EXIT)
        assert close_at < exit_at
        thread.join(timeout=1)
        assert thread.is_alive() is False
        assert mach.isSerialPortOpen() is False
    finally:
        gc.CONFIG_DATA = old
        if mach._thread is not None:
            mach.close()
        fake.stop()


class _Sink(gc.EventQueueIf):
    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self.seen = []

    def add_event(self, event_id, event_data=None, sender=None):
        super().add_event(event_id, event_data, sender)
        if isinstance(event_id, gc.SimpleEvent):
            event = event_id
        else:
            event = gc.SimpleEvent(event_id, event_data, sender)
        with self._lock:
            self.seen.append(event)

    def has(self, event_id):
        with self._lock:
            return any(event.event_id == event_id for event in self.seen)


def test_step_advances_on_ok_and_stops_on_error():
    fake = FakeMoonraker(homed="xyz")
    fake.start()
    old = gc.CONFIG_DATA
    gc.CONFIG_DATA = _config(fake.port)
    sink = _Sink()
    exe = None
    try:
        exe = mi_progexec.MachIfExecuteThread(sink)
        end = time.monotonic() + 8
        while time.monotonic() < end:
            if sink.has(gc.EV_DEVICE_DETECTED) and exe.machIfModule.isSerialPortOpen():
                break
            time.sleep(0.02)
        else:
            raise AssertionError("progexec did not see the Klipper banner")

        lines = ["G1 X1", "G1 X2", "G1 X999"]
        exe.add_event(gc.EV_CMD_STEP, {
            "gcodeFileName": "step.gcode",
            "gcodeLines": lines,
            "gcodePC": 0,
            "breakPoints": set(),
        })
        assert _wait_pc(exe, 1)
        assert exe.swState == gc.STATE_IDLE

        exe.add_event(gc.EV_CMD_STEP, {})
        assert _wait_pc(exe, 2)
        assert exe.swState == gc.STATE_IDLE

        exe.add_event(gc.EV_CMD_STEP, {})
        assert _wait_state(exe, lambda: exe.swState in (gc.STATE_IDLE, gc.STATE_BREAK) and "X999" in "\n".join(_scripts(fake)))
        assert exe.workingProgramCounter == 2
        assert exe.swState in (gc.STATE_IDLE, gc.STATE_BREAK)
        sent = [s for s in _scripts(fake) if s.startswith("G1")]
        assert sent[:3] == ["G1 X1", "G1 X2", "G1 X999"]
    finally:
        if exe is not None:
            exe.add_event(gc.EV_CMD_EXIT, None)
            exe.join(timeout=3)
            module = exe.machIfModule
            if module is not None and getattr(module, "_thread", None) is not None:
                module.close()
            if exe.is_alive():
                exe.join(timeout=3)
        gc.CONFIG_DATA = old
        fake.stop()


def _wait_pc(exe, pc, timeout=5):
    return _wait_state(
        exe,
        lambda: exe.workingProgramCounter == pc and exe.swState == gc.STATE_IDLE,
        timeout,
    )


def _wait_state(exe, predicate, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    raise AssertionError(
        f"timeout pc={exe.workingProgramCounter} state={exe.swState}"
    )
