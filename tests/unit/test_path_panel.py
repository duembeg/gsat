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


def test_clear_resets_path_and_marker():
    p = _panel()
    p.set_program(["G0 X5 Y5\n"])
    p.set_pc(1)
    assert p.segment_count() == 1
    p.clear()
    assert p.segment_count() == 0
    assert p.marker_position == Point(0, 0, 0)
    assert p.status.text().startswith("X0.000")


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
