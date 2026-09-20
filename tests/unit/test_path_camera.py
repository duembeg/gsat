"""Orbit camera: Top / Front / Right named views."""

from modules.pyside_workbench.path_camera import (
    ISO_PITCH,
    NAMED_VIEWS,
    Camera,
    canonical_cube_region,
    cube_facets,
    cube_region,
    view_bounds,
)
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


def test_cube_facets_face_outward():
    from modules.pyside_workbench.path_camera import facet_normal

    for key, verts in cube_facets():
        nx, ny, nz = facet_normal(verts)
        cx = sum(v[0] for v in verts) / len(verts)
        cy = sum(v[1] for v in verts) / len(verts)
        cz = sum(v[2] for v in verts) / len(verts)
        assert cx * nx + cy * ny + cz * nz > 0, key


def test_cube_facets_match_named_views():
    keys = [k for k, _v in cube_facets()]
    assert len(keys) == 26
    assert set(keys) == set(NAMED_VIEWS)


def test_named_views_has_26_regions():
    assert len(NAMED_VIEWS) == 26
    for key in (
        "top",
        "front-right",
        "top-front-right",
        "bottom-back-left",
    ):
        assert key in NAMED_VIEWS
        yaw, pitch = NAMED_VIEWS[key]
        snapped = Camera.top().snap(key)
        assert snapped.yaw_deg == yaw
        assert snapped.pitch_deg == pitch


def test_canonical_region_order():
    assert canonical_cube_region("right", "top", "front") == "top-front-right"
    assert canonical_cube_region("front", "right") == "front-right"


def test_cube_region_face_edge_corner():
    assert cube_region("top", 0.0, 0.0, u_plus="right", v_plus="back") == "top"
    assert cube_region("top", 0.8, 0.0, u_plus="right", v_plus="back") == "top-right"
    assert cube_region("top", 0.8, -0.8, u_plus="right", v_plus="back") == "top-front-right"
    assert cube_region("front", 0.8, 0.8, u_plus="right", v_plus="top") == "top-front-right"


def test_corner_snap_is_isometric_pitch():
    c = Camera.top().snap("top-front-right")
    assert abs(c.yaw_deg + 45.0) < 1e-9
    assert abs(c.pitch_deg - ISO_PITCH) < 1e-9


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
