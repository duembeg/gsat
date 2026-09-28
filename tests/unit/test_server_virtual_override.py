"""Server, console, and wx must not honor the PySide Virtual CNC flag."""

import logging

import modules.config as gc
import modules.machif_config as mi
from modules.machif_progexec import MachIfExecuteThread
from modules.machif_virtual import MachIf_Virtual


def _config(device, enabled):
    cfg = gc.ConfigData(None)
    cfg.set("/machine/Device", device)
    cfg.set("/machine/Port", "")
    cfg.set("/machine/Baud", "115200")
    cfg.set("/machine/FilterGcodesEnable", False)
    cfg.set("/machine/FilterGcodes", "")
    cfg.set("/pysideWorkbench/VirtualCnc/Enabled", enabled)
    return cfg


def _build(monkeypatch, *, device, enabled, allow_virtual=False):
    """Construct the executor without starting its thread."""
    monkeypatch.setattr(MachIfExecuteThread, "start", lambda self: None)
    old = gc.CONFIG_DATA
    gc.CONFIG_DATA = _config(device, enabled)
    try:
        return MachIfExecuteThread(None, allow_virtual=allow_virtual)
    finally:
        gc.CONFIG_DATA = old


def test_default_ignores_enabled_flag(monkeypatch, caplog):
    """gsat-server, console, and wx construct with allow_virtual left false."""
    assert gc.VERBOSE_MASK == 0
    with caplog.at_level(logging.INFO):
        exe = _build(monkeypatch, device="grbl", enabled=True)
    assert exe.allow_virtual is False
    assert exe.machIfModule.getName() == "grbl"
    assert not isinstance(exe.machIfModule, MachIf_Virtual)
    assert exe.machIfModule.getId() == mi.GetMachIfId("grbl")
    assert "init MachIf Module (grbl)" in caplog.text
    assert "init MachIf Module (virtual)" not in caplog.text


def test_local_pyside_uses_virtual_when_enabled(monkeypatch, caplog):
    with caplog.at_level(logging.INFO):
        exe = _build(monkeypatch, device="grbl", enabled=True, allow_virtual=True)
    assert isinstance(exe.machIfModule, MachIf_Virtual)
    assert exe.machIfModule.getName() == "virtual"
    assert "init MachIf Module (virtual)" in caplog.text


def test_local_pyside_uses_device_when_disabled(monkeypatch):
    exe = _build(monkeypatch, device="Smoothie", enabled=False, allow_virtual=True)
    assert exe.machIfModule.getName() == "Smoothie"
    assert not isinstance(exe.machIfModule, MachIf_Virtual)
