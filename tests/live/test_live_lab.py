"""Live lab: gsat-server + motorless controller.

Skipped unless GSAT_LIVE_HOST is set (default pytest).
Fails if the host is set but unreachable.
"""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.live


def test_live_lab_connect_open_step():
    host = os.environ.get("GSAT_LIVE_HOST", "").strip()
    if not host:
        pytest.skip("GSAT_LIVE_HOST not set")

    port = int(os.environ.get("GSAT_LIVE_PORT", "61803"))
    timeout = float(os.environ.get("GSAT_LIVE_TIMEOUT", "12"))
    gcode = os.environ.get("GSAT_LAB_GCODE") or None

    from tools.pyside_smoke import test_live

    notes = test_live(host, port, timeout=timeout, gcode_path=gcode)
    assert notes, "live suite produced no notes"
    joined = " ".join(notes)
    assert "live connect" in joined
    assert "live open machine" in joined
    assert "live step" in joined
