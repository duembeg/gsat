"""VirtualCnc: G0/G1 commanded-motion path (plotter, not a sim)."""

from modules.virtual_cnc import Point, VirtualCnc


def test_absolute_g0_square():
    vc = VirtualCnc()
    vc.apply_lines(
        "G90\nG0 X0 Y0\nG0 X10 Y0\nG0 X10 Y10\nG0 X0 Y10\nG0 X0 Y0\n"
    )
    assert vc.position == Point(0, 0, 0)
    ends = [s.end for s in vc.segments]
    assert ends == [
        Point(10, 0, 0),
        Point(10, 10, 0),
        Point(0, 10, 0),
        Point(0, 0, 0),
    ]
    assert all(s.kind == "rapid" for s in vc.segments)


def test_g0_then_modal_g1():
    vc = VirtualCnc()
    vc.apply_lines(["G90", "G0 X10 Y0", "G1 X10 Y10 F200", "X0 Y10"])
    assert [s.kind for s in vc.segments] == ["rapid", "feed", "feed"]
    assert vc.position == Point(0, 10, 0)


def test_g91_incremental():
    vc = VirtualCnc()
    vc.apply_lines("G91\nG1 X1 Y0\nG1 X0 Y1\n")
    assert vc.position == Point(1, 1, 0)
    assert vc.absolute is False
    assert vc.motion_kind == "feed"


def test_g91_g1_x1_same_line():
    vc = VirtualCnc()
    vc.apply_line("G91 G1 X1")
    assert vc.position == Point(1, 0, 0)
    assert vc.absolute is False
    assert vc.motion_kind == "feed"


def test_g90_after_g91_absolute_target():
    vc = VirtualCnc()
    vc.apply_line("G91 G1 X5 Y5")
    vc.apply_line("G90 G1 X0 Y0")
    assert vc.position == Point(0, 0, 0)
    assert vc.absolute is True


def test_partial_axis_keeps_yz():
    vc = VirtualCnc()
    vc.apply_line("G1 X10 Y5 Z2")
    vc.apply_line("G1 X20")
    assert vc.position == Point(20, 5, 2)


def test_comments_stripped():
    vc = VirtualCnc()
    vc.apply_line("G0 X1 Y0 ; go there")
    vc.apply_line("(note) G1 X1 Y1")
    assert vc.position == Point(1, 1, 0)
    assert [s.kind for s in vc.segments] == ["rapid", "feed"]


def test_concatenated_words():
    vc = VirtualCnc()
    vc.apply_line("G0X10Y20")
    assert vc.position == Point(10, 20, 0)


def test_space_between_letter_and_number():
    vc = VirtualCnc()
    vc.apply_line("G0 X 10 Y 20")
    assert vc.position == Point(10, 20, 0)


def test_case_insensitive():
    vc = VirtualCnc()
    vc.apply_line("g0 x3 y4")
    assert vc.position == Point(3, 4, 0)


def test_g00_g01_aliases():
    vc = VirtualCnc()
    vc.apply_line("G00 X5")
    vc.apply_line("G01 Y5")
    assert [s.kind for s in vc.segments] == ["rapid", "feed"]
    assert vc.position == Point(5, 5, 0)


def test_bare_x10_uses_default_g0():
    vc = VirtualCnc()
    seg = vc.apply_line("X10")
    assert seg is not None
    assert seg.kind == "rapid"
    assert vc.position == Point(10, 0, 0)


def test_block_x10_g1_is_feed_not_rapid():
    """Whole-block semantics: G1 applies to this line's X, not after a rapid."""
    vc = VirtualCnc()
    seg = vc.apply_line("X10 G1")
    assert seg is not None
    assert seg.kind == "feed"
    assert vc.position == Point(10, 0, 0)


def test_no_motion_until_displacement():
    vc = VirtualCnc()
    vc.apply_lines("G90\nG1 X0 Y0 Z0\n")
    assert vc.segments == ()
    assert vc.position == Point(0, 0, 0)


def test_g2_radius_mismatch_skipped():
    vc = VirtualCnc()
    vc.apply_line("G0 X10")
    vc.apply_line("G2 X20 Y10 I5 J0")
    assert vc.position == Point(10, 0, 0)
    assert "G2" in vc.skipped
    assert len(vc.segments) == 1


def test_g3_without_center_skipped():
    vc = VirtualCnc()
    vc.apply_line("G0 X1")
    vc.apply_line("G3 X5")
    assert vc.position == Point(1, 0, 0)
    assert "G3" in vc.skipped
    assert len(vc.segments) == 1


def test_g3_quarter_circle_ijk():
    vc = VirtualCnc(x=10, y=0)
    vc.apply_line("G3 X0 Y10 I-10 J0")
    assert abs(vc.position.x) < 1e-9
    assert abs(vc.position.y - 10) < 1e-9
    assert vc.skipped == ()
    assert len(vc.segments) >= 4
    assert all(s.kind == "arc" for s in vc.segments)
    mids = [s.end for s in vc.segments[:-1]]
    assert any(abs(p.x - p.y) < 0.6 and p.x > 4 for p in mids)


def test_g2_cw_quarter_circle():
    vc = VirtualCnc(x=10, y=0)
    vc.apply_line("G2 X0 Y-10 I-10 J0")
    assert abs(vc.position.x) < 1e-9
    assert abs(vc.position.y + 10) < 1e-9
    mids = [s.end for s in vc.segments]
    assert any(p.y < -4 and p.x > 4 for p in mids)


def test_g3_r_form_minor():
    vc = VirtualCnc(x=10, y=0)
    vc.apply_line("G3 X0 Y10 R10")
    assert abs(vc.position.x) < 1e-9
    assert abs(vc.position.y - 10) < 1e-9
    assert vc.skipped == ()
    mids = [s.end for s in vc.segments[:-1]]
    assert any(abs(p.x - p.y) < 0.6 and p.x > 4 for p in mids)


def test_g2_full_circle_ijk():
    vc = VirtualCnc(x=10, y=0)
    vc.apply_line("G2 I-10 J0")
    assert abs(vc.position.x - 10) < 1e-9
    assert abs(vc.position.y) < 1e-9
    assert len(vc.segments) >= 8
    xs = [s.end.x for s in vc.segments]
    assert min(xs) < 1.0


def test_g3_helical_z():
    vc = VirtualCnc(x=10, y=0, z=0)
    vc.apply_line("G3 X0 Y10 Z5 I-10 J0")
    assert abs(vc.position.z - 5) < 1e-9
    zs = [s.end.z for s in vc.segments]
    assert zs[0] < zs[-1]


def test_g91_arc_incremental_end():
    vc = VirtualCnc(x=10, y=0)
    vc.apply_line("G91 G3 X-10 Y10 I-10 J0")
    assert abs(vc.position.x) < 1e-9
    assert abs(vc.position.y - 10) < 1e-9


def test_g18_arc_still_skipped():
    vc = VirtualCnc()
    vc.apply_line("G18")
    vc.apply_line("G2 X1 Z1 I1 K0")
    assert vc.position == Point(0, 0, 0)
    assert "G2" in vc.skipped


def test_unknown_noop():
    vc = VirtualCnc()
    assert vc.apply_line("M3 S1000") is None
    assert vc.apply_line("G4 P0.05") is None
    assert vc.apply_line("") is None
    assert vc.apply_line("; comment only") is None
    assert vc.position == Point(0, 0, 0)
    assert vc.segments == ()


def test_g20_does_not_rescale():
    vc = VirtualCnc()
    vc.apply_line("G20")
    vc.apply_line("G0 X1")
    assert vc.position.x == 1.0


def test_z_only_is_segment():
    vc = VirtualCnc()
    seg = vc.apply_line("G0 Z5")
    assert seg is not None
    assert seg.start == Point(0, 0, 0)
    assert seg.end == Point(0, 0, 5)
    assert seg.kind == "rapid"


def test_reset_clears_path_and_pose():
    vc = VirtualCnc(x=1, y=2, z=3, absolute=False, motion="feed")
    vc.apply_line("G1 X1")
    vc.apply_line("G2 X2 I1")
    assert vc.segments
    vc.reset()
    assert vc.position == Point(1, 2, 3)
    assert vc.absolute is False
    assert vc.motion_kind == "feed"
    assert vc.segments == ()
    assert vc.skipped == ()


def test_bounds_simple_box():
    vc = VirtualCnc()
    vc.apply_lines("G0 X10 Y0\nG1 X10 Y10\nG1 X0 Y10\nG1 X0 Y0\n")
    lo, hi = vc.bounds()
    assert lo == Point(0, 0, 0)
    assert hi == Point(10, 10, 0)


def test_bounds_empty():
    assert VirtualCnc().bounds() is None


def test_line_index_from_apply_lines():
    vc = VirtualCnc()
    vc.apply_lines(["G0 X1", "G1 Y1"])
    assert vc.segments[0].line_index == 0
    assert vc.segments[1].line_index == 1


def test_apply_lines_returns_new_segments():
    vc = VirtualCnc()
    first = vc.apply_lines("G0 X1")
    second = vc.apply_lines("G1 Y1")
    assert len(first) == 1
    assert len(second) == 1
    assert len(vc.segments) == 2
    assert first[0].kind == "rapid"
    assert second[0].kind == "feed"
