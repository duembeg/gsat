"""MachIf_Virtual: grbl-like ok/status without serial."""

import modules.config as gc
import modules.machif_config as mi
from modules.machif_virtual import MachIf_Virtual, virtual_cnc_enabled
from modules.virtual_cnc import Point


def _drain(mach: MachIf_Virtual) -> list[dict]:
    out = []
    while True:
        d = mach.read()
        if not d:
            break
        out.append(d)
    return out


def test_not_in_shared_machif_list():
    """wx settings Device combo must not gain a Virtual entry."""
    assert "virtual" not in [n.lower() for n in mi.MACHIF_LIST]
    assert mi.GetMachIfId("virtual") is None


def test_open_fakes_port_and_banner():
    m = MachIf_Virtual()
    m.init()
    m.open()
    assert m.isSerialPortOpen()
    events = _drain(m)
    ids = [d.get("event", {}).get("id") for d in events if "event" in d]
    assert gc.EV_SER_PORT_OPEN in ids
    inits = [d for d in events if d.get("r", {}).get("init")]
    assert inits
    assert "Virtual CNC" in inits[0]["r"]["init"]


def test_g0_write_acks_and_moves():
    m = MachIf_Virtual()
    m.open()
    _drain(m)
    n = m.write("G0 X10 Y5\n")
    assert n > 0
    assert m.vc.position == Point(10, 5, 0)
    replies = _drain(m)
    assert any(d.get("sr", {}).get("posx") == 10.0 for d in replies)
    assert any("r" in d and d.get("f", [None, 1])[1] == 0 for d in replies)


def test_question_mark_status_no_ok():
    m = MachIf_Virtual()
    m.open()
    _drain(m)
    m.write("G1 X1\n")
    _drain(m)
    m.write("?\n")
    replies = _drain(m)
    assert any(d.get("sr", {}).get("posx") == 1.0 for d in replies)
    assert not any(d.get("r") == {} and "f" in d for d in replies)


def test_home_returns_to_origin():
    m = MachIf_Virtual()
    m.open()
    _drain(m)
    m.write("G0 X8 Y8\n")
    _drain(m)
    m.write("$H\n")
    _drain(m)
    assert m.vc.position == Point(0, 0, 0)


def test_jog_prefix_stripped():
    m = MachIf_Virtual()
    m.open()
    _drain(m)
    m.write("$J=G91 X1 F1000\n")
    _drain(m)
    assert m.vc.position.x == 1.0


def test_close_queues_port_close_and_exit():
    m = MachIf_Virtual()
    m.open()
    _drain(m)
    m.close()
    events = _drain(m)
    ids = [d["event"]["id"] for d in events if "event" in d]
    assert gc.EV_SER_PORT_CLOSE in ids
    assert gc.EV_EXIT in ids
    assert not m.isSerialPortOpen()


def test_ok_to_send_never_blocks():
    m = MachIf_Virtual()
    assert m.okToSend("G0 X1\n")


def test_virtual_cnc_enabled_false_without_config(monkeypatch):
    monkeypatch.setattr(gc, "CONFIG_DATA", None)
    assert virtual_cnc_enabled() is False
