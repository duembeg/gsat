"""After-run Idle wait + runtime dialog formatting (wx OnThreadEvent)."""

from modules.pyside_workbench.run_end import (
    format_run_time_dialog,
    format_run_time_hms,
    machine_status_is_drained,
    should_finish_run_end_wait,
)


def test_drained_statuses():
    for s in ("Idle", "idle", "Stop", "stop", "End", "end", " IDLE "):
        assert machine_status_is_drained(s)


def test_not_drained_while_running():
    for s in ("Run", "Jog", "Hold", "Alarm", "Home", None, "", "  "):
        assert not machine_status_is_drained(s)


def test_finish_only_when_waiting_and_idle():
    assert not should_finish_run_end_wait(waiting=False, stat="Idle")
    assert not should_finish_run_end_wait(waiting=True, stat="Run")
    assert should_finish_run_end_wait(waiting=True, stat="Idle")


def test_hms_3661():
    assert format_run_time_hms(3661) == "01:01:01"


def test_hms_zero_and_bad():
    assert format_run_time_hms(0) == "00:00:00"
    assert format_run_time_hms(None) == "00:00:00"
    assert format_run_time_hms(-3) == "00:00:00"


def test_dialog_body_contains_wx_labels():
    body = format_run_time_dialog(5, now=1_700_000_000.0)
    assert "Started:" in body
    assert "Ended:" in body
    assert "Run time:" in body
    assert "00:00:05" in body
