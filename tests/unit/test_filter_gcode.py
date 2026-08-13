"""FilterGcodes: substring match after comment strip (Run and Step share this)."""

from modules.machif_progexec import MachIfExecuteThread


class _FilterHost:
    """Stand-in — do not construct MachIfExecuteThread (it starts a thread)."""

    filterGCodesEnable = True
    filterGCodesList = ["M2", "T1", "G64"]

    prepare = MachIfExecuteThread.prepare_program_gcode_line


def _prep(line: str, *, enable=True, tokens=None) -> str:
    h = _FilterHost()
    h.filterGCodesEnable = enable
    if tokens is not None:
        h.filterGCodesList = tokens
    return MachIfExecuteThread.prepare_program_gcode_line(h, line)


def test_g64_with_param_is_filtered():
    assert _prep("G64 P0.00500") == ""


def test_g0_not_filtered():
    assert _prep("G0 X10").strip() == "G0 X10"


def test_comment_only_g64_not_in_payload():
    # Comment stripped first; leftover motion stays
    assert _prep("G0 X1 ; G64 hidden").strip() == "G0 X1"


def test_inline_comment_then_g64():
    assert _prep("(note) G64 P1") == ""


def test_disabled_filter_passes_g64():
    assert "G64" in _prep("G64 P1", enable=False)


def test_empty_token_ignored():
    # Empty string is in every line — must not blank everything
    out = _prep("G0 X1", tokens=["", "G64"])
    assert "G0" in out


def test_m03_contains_m0_substring():
    # Historical matching is substring, not whole-word
    assert _prep("M03", tokens=["M0"]) == ""
