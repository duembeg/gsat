"""gsat-server prints a listen banner before any client connects."""

import importlib.util
import os


def _load_server():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "gsat-server.py"))
    spec = importlib.util.spec_from_file_location("gsat_server_mod", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_listening_lines_match_the_ui_welcome_facts():
    server = _load_server()
    lines = server.listening_lines(
        "v1.10.0",
        "websocket",
        "mill (192.168.1.20)",
        61803,
        "/home/user/.gsat.json",
        "3.12.3",
        "Linux",
    )
    assert lines[0] == "gsat server v1.10.0 listening"
    assert "websocket" in lines[1]
    assert "mill (192.168.1.20)" in lines[1]
    assert "61803" in lines[1]
    assert lines[2] == "config: /home/user/.gsat.json"
    assert lines[3] == "python: 3.12.3"
    assert lines[4] == "system: Linux"
