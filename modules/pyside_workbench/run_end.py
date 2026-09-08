"""----------------------------------------------------------------------------
    run_end.py

    After EV_RUN_END the software has finished *sending* lines; the controller
    may still be draining the planner. wx waits until machine status is Idle
    (or Stop/End) before optional DisplayRunTimeDialog.

    Pure helpers — no Qt — so unit tests do not need a QApplication.
----------------------------------------------------------------------------"""
from __future__ import annotations

import time

# wx OnThreadEvent: machineStatusString in ["Idle", "idle", "Stop", "stop", "End", "end"]
_IDLE_STATUSES = frozenset({"idle", "stop", "end"})


def machine_status_is_drained(stat: str | None) -> bool:
    """True when the controller has finished executing the streamed program."""
    if stat is None:
        return False
    return str(stat).strip().lower() in _IDLE_STATUSES


def should_finish_run_end_wait(*, waiting: bool, stat: str | None) -> bool:
    return bool(waiting) and machine_status_is_drained(stat)


def format_run_time_hms(rtime_sec) -> str:
    """wx ``%02d:%02d:%02d`` from progexec ``rtime`` seconds."""
    try:
        rtime = float(rtime_sec)
    except (TypeError, ValueError):
        rtime = 0.0
    if rtime < 0:
        rtime = 0.0
    hours, rem = divmod(int(rtime), 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_run_time_dialog(rtime_sec, now: float | None = None) -> str:
    """wx runtime MessageBox body: Started / Ended / Run time."""
    try:
        rtime = float(rtime_sec)
    except (TypeError, ValueError):
        rtime = 0.0
    if rtime < 0:
        rtime = 0.0
    t_end = time.time() if now is None else float(now)
    t_start = t_end - rtime
    start_s = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(t_start))
    end_s = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(t_end))
    return (
        f"Started:\t{start_s}\n"
        f"Ended:\t{end_s}\n"
        f"Run time:\t{format_run_time_hms(rtime)}"
    )
