"""PathPanel: preview G0/G1 path; marker is position after lines[:pc]."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from modules.pyside_workbench.path_canvas import PathPanel
from modules.virtual_cnc import Point

_APP = QApplication.instance() or QApplication([])


def _panel() -> PathPanel:
    return PathPanel()


def test_preview_builds_segments():
    p = _panel()
    p.set_program(["G90\n", "G0 X10 Y0\n", "G1 X10 Y10 F100\n", "G1 X0 Y10\n"])
    assert p.segment_count() == 3
    assert [s.kind for s in p.segments] == ["rapid", "feed", "feed"]


def test_scrub_reveals_prefix_hides_future():
    p = _panel()
    p.set_program(["G0 X10\n", "G1 Y10\n", "G1 X0\n"])
    assert p._pc == 3
    assert p.canvas._drawn_end == 3
    p.set_pc(0)
    assert p.canvas._drawn_end == 0
    assert p.marker_position == Point(0, 0, 0)
    p.set_pc(1)
    assert p.canvas._drawn_end == 1
    assert p.marker_position == Point(10, 0, 0)
    p.set_pc(3)
    assert p.canvas._drawn_end == 3
    assert p.marker_position == Point(0, 10, 0)


def test_pc_zero_marker_at_origin():
    p = _panel()
    p.set_program(["G0 X10\n", "G1 Y10\n"])
    p.set_pc(0)
    assert p.marker_position == Point(0, 0, 0)


def test_pc_after_first_move():
    p = _panel()
    p.set_program(["G0 X10\n", "G1 Y10\n"])
    p.set_pc(1)
    assert p.marker_position == Point(10, 0, 0)
    p.set_pc(2)
    assert p.marker_position == Point(10, 10, 0)


def test_scrub_emits_pc_seeked():
    p = _panel()
    p.set_program(["G0 X1\n", "G1 X2\n", "G1 X3\n"])
    got: list[int] = []
    p.pc_seeked.connect(got.append)
    p._on_scrub(2)
    assert got == [2]
    assert p._pc == 2
    assert p.marker_position == Point(2, 0, 0)
    assert p.slider.value() == 2


def test_play_tick_advances_and_emits():
    p = _panel()
    p.set_program(["G0 X1\n", "G1 X2\n", "G1 X3\n", "G1 X4\n"])
    p.set_pc(0)
    got: list[int] = []
    p.pc_seeked.connect(got.append)
    p._playing = True
    p._play_speed = 1.0
    p._play_dir = 1
    p._play_tick(1.0 / 45.0)  # one line at 1×
    assert got
    assert p._pc >= 1
    p.stop_play()
    assert not p._playing


def test_clear_seeks_to_start_keeps_play():
    p = _panel()
    p.set_program(["G0 X1\n", "G1 X2\n"])
    p.set_pc(2)
    p.clear()
    assert p._pc == 0
    assert p.canvas._drawn_end == 0
    assert p.marker_position == Point(0, 0, 0)
    assert p.btn_play.isEnabled()
    assert p.segment_count() == 2
    p.start_play()
    assert p._playing
    p.stop_play()


def test_play_reveals_exact_prefix_not_subsample():
    p = _panel()
    p.set_program(["G0 X1\n", "G1 Y1\n", "G1 X0\n"])
    n = p.segment_count()
    p.set_pc(0)
    p.start_play()
    assert p._playing
    assert not p.canvas.is_nav_preview()
    p._play_tick(0.05)
    assert p.segment_count() == n
    assert p.canvas._drawn_end == p._pc
    assert p.canvas._drawn_exact is True
    p.stop_play()
    assert not p.canvas.is_nav_preview()


def test_live_pc_moves_scrub_thumb():
    p = _panel()
    p.set_program(["G0 X1\n", "G1 X2\n", "G1 X3\n"])
    assert p.slider.value() == 3
    p.begin_live()
    assert p._lines  # keep program so the bar has a range
    p.set_pc(2)
    assert p.slider.value() == 2
    p.end_live()
    p.set_program(["G0 X1\n", "G1 X2\n", "G1 X3\n"])
    p.set_pc(2)
    assert p.slider.value() == 2
    assert p.canvas._drawn_end == 2


def test_scrub_drag_is_exact_prefix():
    p = _panel()
    p.set_program([f"G1 X{i}\n" for i in range(1, 81)])
    assert p.canvas._drawn_end == 80
    p._on_scrub_pressed()
    p._on_scrub(40)
    assert p.canvas._drawn_end == 40
    assert p.canvas._paths_end == 80
    assert p.canvas._drawn_exact is True
    assert not p.canvas.is_nav_preview()
    p._on_scrub(24)
    assert p.canvas._drawn_end == 24
    assert p.canvas._paths_end == 80
    p._on_scrub_released()
    assert p.canvas._drawn_end == 24
    assert p.canvas._paths_end == 24
    assert p.canvas._drawn_exact is True


def test_reverse_scrub_defers_path_rebuild():
    p = _panel()
    p.set_program([f"G1 X{i}\n" for i in range(1, 81)])
    p._on_scrub_pressed()
    p._on_scrub(79)
    assert p.canvas._drawn_end == 79
    assert p.canvas._paths_end == 80
    p._on_scrub(40)
    assert p.canvas._drawn_end == 40
    assert p.canvas._paths_end == 80
    p._on_scrub(50)
    assert p.canvas._drawn_end == 50
    assert p.canvas._paths_end == 50
    p._on_scrub_released()
    assert p.canvas._paths_end == 50


def test_reverse_play_defers_until_stop():
    p = _panel()
    p.set_program(["G0 X1\n", "G1 X2\n", "G1 X3\n", "G1 X4\n"])
    p._play_dir = -1
    p.start_play()
    assert p.canvas._defer_stamp
    p._play_tick(1.0 / 45.0)
    assert p._pc == 3
    assert p.canvas._drawn_end == 3
    assert p.canvas._paths_end == 4
    p.stop_play()
    assert not p.canvas._defer_stamp
    assert p.canvas._paths_end == 3


def test_forward_grow_stays_incremental():
    p = _panel()
    p.set_program(["G0 X1\n", "G1 X2\n", "G1 X3\n"])
    p.set_pc(0)
    assert p.canvas._drawn_end == 0
    assert p.canvas._paths_end == 0
    p.set_pc(1)
    assert p.canvas._drawn_end == 1
    assert p.canvas._paths_end == 1
    p.set_pc(2)
    assert p.canvas._drawn_end == 2
    assert p.canvas._paths_end == 2


def test_scrub_back_removes_ink():
    p = _panel()
    p.set_program(["G0 X1\n", "G1 X2\n", "G1 X3\n", "G1 X4\n"])
    p.set_pc(4)
    assert p.canvas._drawn_end == 4
    p.set_pc(1)
    assert p.canvas._drawn_end == 1
    assert p.canvas._paths_end == 1
    assert p.canvas._drawn_exact is True
    p.set_pc(0)
    assert p.canvas._drawn_end == 0
    assert p.canvas._paths_end == 0
    assert p.marker_position == Point(0, 0, 0)


def test_play_disabled_in_live_mode():
    p = _panel()
    p.set_program(["G0 X1\n"])
    p.begin_live()
    p.start_play()
    assert not p._playing
    assert not p.btn_play.isEnabled()
    p.end_live()
    p.set_program(["G0 X1\n"])
    assert p.btn_play.isEnabled()


def test_clear_resets_path_and_marker():
    p = _panel()
    p.set_program(["G0 X5 Y5\n"])
    p.set_pc(1)
    assert p.segment_count() == 1
    p.clear()
    assert p.segment_count() == 1
    assert p._pc == 0
    assert p.canvas._drawn_end == 0
    assert p.marker_position == Point(0, 0, 0)
    assert p.status.text().startswith("X0.000")
    assert p.btn_play.isEnabled()
    assert p.slider.isEnabled()
    assert p.slider.value() == 0


def test_skipped_arcs_noted_in_status():
    p = _panel()
    p.set_program(["G0 X1\n", "G2 X9\n"])
    assert p.segment_count() == 1
    assert "skipped G2" in p.status.text()


def test_preview_interpolates_g3():
    p = _panel()
    p.set_program(["G0 X10 Y0\n", "G3 X0 Y10 I-10 J0\n"])
    assert p.segment_count() > 2
    assert all(s.kind == "arc" for s in p.segments[1:])


def test_empty_program():
    p = _panel()
    p.set_program([])
    assert p.segment_count() == 0
    assert p.marker_position == Point(0, 0, 0)


def test_right_drag_orbits_not_pan():
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent

    p = _panel()
    yaw0 = p.canvas.camera.yaw_deg
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(40, 40),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )
    p.canvas.mousePressEvent(press)
    assert p.canvas._orbit_from is not None
    assert p.canvas._pan_from is None
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(80, 55),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )
    p.canvas.mouseMoveEvent(move)
    assert p.canvas.camera.yaw_deg != yaw0
    assert p.canvas._pan_from is None
    assert p.canvas.is_orbit_preview()


def test_pan_uses_preview_until_release():
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent

    p = _panel()
    p.canvas.resize(400, 400)
    p.set_program([f"G1 X{i} Y{i % 9}\n" for i in range(80)])
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(40, 40),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    p.canvas.mousePressEvent(press)
    assert p.canvas.is_nav_preview()
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(90, 55),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    p.canvas.mouseMoveEvent(move)
    assert p.canvas._pan_vx != 0.0 or p.canvas._pan_vy != 0.0
    rel = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(90, 55),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    p.canvas.mouseReleaseEvent(rel)
    assert not p.canvas.is_nav_preview()
    assert p.canvas._pan_from is None


def test_orbit_drag_uses_preview_until_release():
    p = _panel()
    p.canvas.resize(400, 400)
    p.set_program([f"G1 X{i} Y{i % 9}\n" for i in range(200)])
    assert p.canvas.preview_count() >= 2
    assert p.canvas.preview_count() <= 4096
    assert not p.canvas.is_orbit_preview()
    cached = p.canvas._cache_cam
    p.canvas._capture_orbit_pivot(80, 80)
    p.canvas.orbit(20, 12)
    assert p.canvas.is_orbit_preview()
    assert p.canvas.camera != cached
    assert p.canvas._cache_cam == cached  # full path not rebuilt mid-drag
    p.canvas._end_orbit_gesture()
    assert not p.canvas.is_orbit_preview()
    assert p.canvas._cache_cam == p.canvas.camera


def test_orbit_release_preserves_pixel_scale():
    p = _panel()
    p.canvas.resize(400, 400)
    p.set_program(
        ["G0 X0 Y0\n", "G1 X50 Y0\n", "G1 X50 Y40\n", "G1 X0 Y40\n"]
    )
    p.canvas._zoom = 3.0
    p.canvas.repaint()
    scale0 = p.canvas._xf().scale
    p.canvas._capture_orbit_pivot(200, 200)
    p.canvas.orbit(40, 25)
    p.canvas._end_orbit_gesture()
    scale1 = p.canvas._xf().scale
    assert scale0 > 0
    assert abs(scale1 - scale0) / scale0 < 0.05


def test_orbit_keeps_clicked_world_point_on_screen():
    p = _panel()
    p.canvas.resize(400, 400)
    p.set_program(["G0 X50 Y10\n", "G1 X50 Y20\n"])
    p.canvas.repaint()
    xf = p.canvas._xf()
    vx, vy, _ = p.canvas.camera.to_view(50, 10, 0)
    px, py = xf.to_px(vx, vy)
    p.canvas._capture_orbit_pivot(px, py)
    p.canvas.orbit(25, 15)
    p.canvas._rebuild_view_cache()
    xf2 = p.canvas._xf()
    vx2, vy2, _ = p.canvas.camera.to_view(50, 10, 0)
    px2, py2 = xf2.to_px(vx2, vy2)
    assert abs(px2 - px) < 2.0
    assert abs(py2 - py) < 2.0


def test_fit_resets_zoom_and_pan():
    p = _panel()
    p.canvas._zoom = 4.0
    p.canvas._pan_vx = 3.0
    p.canvas._pan_vy = -1.0
    p.canvas.fit_view()
    assert p.canvas._zoom == 1.0
    assert p.canvas._pan_vx == 0.0
    assert p.canvas._pan_vy == 0.0


def test_canvas_defaults_to_top_view():
    p = _panel()
    assert abs(p.canvas.camera.pitch_deg - 90.0) < 1e-9
    assert p.canvas.view_cube.objectName() == "pathViewCube"
    p.canvas.snap_view("front")
    assert abs(p.canvas.camera.pitch_deg) < 1e-9
    p.canvas.snap_view("right")
    assert abs(p.canvas.camera.yaw_deg + 90.0) < 1e-9
    p.canvas.snap_view("top")
    assert abs(p.canvas.camera.pitch_deg - 90.0) < 1e-9


def _facet_center(cube, key: str):
    poly = next(
        poly for _d, k, poly, _f in cube._visible_facets() if k == key
    )
    return poly.boundingRect().center()


def test_view_cube_is_top_right():
    p = _panel()
    p.canvas.resize(400, 300)
    p.canvas._place_cube()
    cube = p.canvas.view_cube
    assert cube.x() == 400 - 135 - 8
    assert cube.y() == 8
    ox, _oy = p.canvas._hud_origin()
    assert abs(ox - (cube.x() + cube.width() / 2.0)) < 1e-6


def test_view_cube_face_and_corner_hits_from_top():
    p = _panel()
    cube = p.canvas.view_cube
    top = _facet_center(cube, "top")
    assert cube.region_at(top.x(), top.y()) == "top"
    corner = _facet_center(cube, "top-front-right")
    assert cube.region_at(corner.x(), corner.y()) == "top-front-right"
    # Face-on Top: edge strips overlap the octagon in 2D — must still pick the edge
    front_e = _facet_center(cube, "top-front")
    assert cube.region_at(front_e.x(), front_e.y()) == "top-front"
    right_e = _facet_center(cube, "top-right")
    assert cube.region_at(right_e.x(), right_e.y()) == "top-right"
    p.canvas.snap_view("top-front")
    assert abs(p.canvas.camera.pitch_deg - 45.0) < 1e-6
    p.canvas.snap_view("top-front-right")
    assert abs(p.canvas.camera.yaw_deg + 45.0) < 1e-6
    p.canvas.snap_view("front-right")
    assert abs(p.canvas.camera.yaw_deg + 45.0) < 1e-6
    assert abs(p.canvas.camera.pitch_deg) < 1e-6
    p.canvas.snap_view("top-front-right")
    p.canvas.view_cube.set_camera(p.canvas.camera)
    edge_poly = next(
        poly
        for _d, key, poly, _f in cube._visible_facets()
        if key == "top-front"
    )
    c = edge_poly.boundingRect().center()
    assert cube.region_at(c.x(), c.y()) == "top-front"


def test_live_appends_and_ignores_file_preview():
    p = _panel()
    p.set_program(["G0 X99\n"])
    p.begin_live()
    assert p.is_live()
    assert p.segment_count() == 0
    p.apply_live_line("G0 X10\n")
    p.apply_live_line("G1 Y5\n")
    assert p.segment_count() == 2
    assert [s.kind for s in p.segments] == ["rapid", "feed"]
    assert p.segments[0].line_index != p.segments[1].line_index
    assert p.marker_position == Point(10, 5, 0)
    p.set_program(["G0 X1\n"])  # must not clobber live path
    assert p.marker_position == Point(10, 5, 0)
    p.end_live()
    assert not p.is_live()
