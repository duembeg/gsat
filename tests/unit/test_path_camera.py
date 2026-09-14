"""Orbit camera: Top / Front / Right named views."""

from modules.pyside_workbench.path_camera import Camera, view_bounds
from modules.virtual_cnc import Point, Segment


def test_top_x_right_y_up():
    c = Camera.top()
    vx0, vy0, _ = c.to_view(0, 0, 0)
    vx1, _, _ = c.to_view(1, 0, 0)
    _, vy2, _ = c.to_view(0, 1, 0)
    assert vx1 > vx0
    assert vy2 > vy0


def test_top_z_is_depth_only():
    c = Camera.top()
    vx, vy, vz = c.to_view(0, 0, 5)
    assert abs(vx) < 1e-9
    assert abs(vy) < 1e-9
    assert vz == 5.0


def test_front_z_up_x_right():
    c = Camera.front()
    vx0, vy0, _ = c.to_view(0, 0, 0)
    vx1, _, _ = c.to_view(1, 0, 0)
    _, vy2, _ = c.to_view(0, 0, 1)
    assert vx1 > vx0
    assert vy2 > vy0


def test_right_y_right_z_up():
    c = Camera.right()
    vx0, vy0, _ = c.to_view(0, 0, 0)
    vx1, _, _ = c.to_view(0, 1, 0)
    _, vy2, _ = c.to_view(0, 0, 1)
    assert vx1 > vx0
    assert vy2 > vy0


def test_snap_named_views():
    c = Camera.top().snap("front")
    assert c == Camera.front()
    assert Camera.top().snap("right") == Camera.right()
    assert Camera.front().snap("top") == Camera.top()


def test_orbit_pitch_clamped():
    c = Camera.top().orbit(0, 20)
    assert c.pitch_deg == 90.0
    c = Camera.top().orbit(0, -45)
    assert c.pitch_deg == 45.0


def test_from_view_roundtrip_top():
    c = Camera.top()
    for pt in ((0, 0, 0), (3, -2, 5), (10, 1, -4)):
        vx, vy, vz = c.to_view(*pt)
        back = c.from_view(vx, vy, vz)
        assert all(abs(a - b) < 1e-9 for a, b in zip(pt, back))


def test_from_view_roundtrip_tilted():
    c = Camera.top().orbit(35, -40)
    vx, vy, vz = c.to_view(8, 3, -1)
    back = c.from_view(vx, vy, vz)
    assert all(abs(a - b) < 1e-9 for a, b in zip((8, 3, -1), back))


def test_orbit_changes_z_on_screen():
    _, vy_top, _ = Camera.top().to_view(0, 0, 1)
    _, vy_tilt, _ = Camera.top().orbit(0, -45).to_view(0, 0, 1)
    assert abs(vy_top) < 1e-9
    assert vy_tilt > 0


def test_view_bounds_uses_camera():
    segs = (Segment(Point(0, 0, 0), Point(0, 0, 10), "rapid", 0),)
    # Top: Z is depth, XY collapsed to origin
    mn_x, mn_y, mx_x, mx_y = view_bounds(segs, Point(0, 0, 10), Camera.top())
    assert abs(mx_x - mn_x) < 1e-9
    assert abs(mx_y - mn_y) < 1e-9
    # Front: Z is screen-up
    mn_x, mn_y, mx_x, mx_y = view_bounds(segs, Point(0, 0, 10), Camera.front())
    assert mx_y - mn_y == 10.0
