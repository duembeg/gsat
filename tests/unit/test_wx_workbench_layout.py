"""wx workbench layout: package path, no leftover modules.wnd_*, shim text."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest


def test_wx_workbench_package_imports_without_wx():
    import modules.wx_workbench as wx_wb

    assert wx_wb.__file__ is not None
    assert "wx_workbench" in wx_wb.__file__


def test_wx_wnd_modules_live_under_wx_workbench():
    spec = importlib.util.find_spec("modules.wx_workbench.wnd_main")
    assert spec is not None
    assert spec.origin is not None
    assert spec.origin.endswith(os.path.join("wx_workbench", "wnd_main.py"))


def test_old_modules_wnd_paths_are_gone():
    assert importlib.util.find_spec("modules.wnd_main") is None
    assert importlib.util.find_spec("modules.wnd_gcode") is None


def test_wx_wnd_main_loads_if_wx_installed():
    pytest.importorskip("wx")
    from modules.wx_workbench import wnd_main as mw

    assert hasattr(mw, "gsatMainWindow")


def test_gsat_shim_points_at_pyside_and_legacy_wx():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script = os.path.join(root, "gsat.py")
    result = subprocess.run(
        [sys.executable, script],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    text = result.stdout + result.stderr
    assert "gsat-pyside.py" in text
    assert "gsat-wx.py" in text
