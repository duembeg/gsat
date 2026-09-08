"""Program MD5 fingerprint + MaxMessageBytes MB/bytes helpers."""

import pytest

import modules.config as gc
from modules.pyside_workbench.main_window import _gcode_lines_md5


def test_md5_matches_str_list_hash():
    lines = ["G21\n", "G0 X0\n"]
    import hashlib

    expect = hashlib.md5(str(lines).encode("utf-8")).hexdigest()
    assert _gcode_lines_md5(lines) == expect


def test_md5_none_is_empty_list():
    assert _gcode_lines_md5(None) == _gcode_lines_md5([])


def test_md5_order_matters():
    assert _gcode_lines_md5(["A", "B"]) != _gcode_lines_md5(["B", "A"])


def test_mb_roundtrip_16():
    b = gc.remote_message_mb_to_bytes(16)
    assert b == 16 * 1024 * 1024
    assert gc.remote_message_bytes_to_mb(b) == 16.0


def test_mb_floor_one():
    with pytest.raises(ValueError, match="at least 1 MB"):
        gc.remote_message_mb_to_bytes(0.5)


def test_mb_rejects_non_number():
    with pytest.raises(ValueError, match="must be a number"):
        gc.remote_message_mb_to_bytes("nope")
