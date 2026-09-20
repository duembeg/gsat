"""XY view transform for the path canvas (Y-up CNC → Y-down pixels)."""

from modules.pyside_workbench.path_canvas import (
    ViewTransform,
    bounds_xy,
    fit_xy,
    view_transform,
)
from modules.virtual_cnc import Point, Segment


def test_y_up_maps_to_smaller_pixel_y():
    xf = fit_xy(0, 0, 10, 10, 200, 200, margin=0)
    _, y0 = xf.to_px(0, 0)
    _, y1 = xf.to_px(0, 10)
    assert y1 < y0


def test_x_right_maps_to_larger_pixel_x():
    xf = fit_xy(0, 0, 10, 10, 200, 200, margin=0)
    x0, _ = xf.to_px(0, 0)
    x1, _ = xf.to_px(10, 0)
    assert x1 > x0


def test_fit_corners_with_no_margin():
    xf = fit_xy(0, 0, 10, 10, 200, 200, margin=0)
    assert xf.to_px(0, 0) == (0.0, 200.0)
    assert xf.to_px(10, 10) == (200.0, 0.0)


def test_zero_span_centers_the_point():
    xf = fit_xy(3, 4, 3, 4, 100, 100, margin=10)
    px, py = xf.to_px(3, 4)
    assert abs(px - 50.0) < 1e-6
    assert abs(py - 50.0) < 1e-6
    assert xf.scale > 0


def test_bounds_include_path_and_marker():
    segs = (
        Segment(Point(0, 0, 0), Point(10, 0, 0), "rapid", 0),
        Segment(Point(10, 0, 0), Point(10, 5, 0), "feed", 1),
    )
    min_x, min_y, max_x, max_y = bounds_xy(segs, Point(-2, 8, 0))
    assert (min_x, min_y, max_x, max_y) == (-2.0, 0.0, 10.0, 8.0)


def test_view_transform_scale():
    xf = ViewTransform(scale=2.0, origin_x=10.0, origin_y=40.0)
    assert xf.to_px(5, 3) == (20.0, 34.0)
    assert xf.to_view(20.0, 34.0) == (5.0, 3.0)


def test_zoom_keeps_bounds_center():
    xf = view_transform(0, 0, 10, 10, 200, 200, zoom=2.0, margin=0)
    assert xf.to_px(5, 5) == (100.0, 100.0)
    assert xf.scale == 40.0


def test_zoom_at_pixel_keeps_that_view_point():
    """Wheel-zoom: the view point under (px,py) stays under (px,py)."""
    bounds = (0.0, 0.0, 10.0, 10.0)
    w = h = 200.0
    px, py = 150.0, 40.0
    xf0 = view_transform(*bounds, w, h, zoom=1.0, margin=0)
    vx, vy = xf0.to_view(px, py)
    new_zoom = 2.0
    fitted = fit_xy(*bounds, w, h, margin=0)
    scale = fitted.scale * new_zoom
    cx, cy = 5.0, 5.0
    pan_vx = vx - cx - (px - w / 2.0) / scale
    pan_vy = vy - cy + (py - h / 2.0) / scale
    xf1 = view_transform(
        *bounds, w, h, zoom=new_zoom, pan_vx=pan_vx, pan_vy=pan_vy, margin=0
    )
    vx1, vy1 = xf1.to_view(px, py)
    assert abs(vx1 - vx) < 1e-9
    assert abs(vy1 - vy) < 1e-9


def test_pan_shifts_origin():
    xf0 = view_transform(0, 0, 10, 10, 200, 200, margin=0)
    xf1 = view_transform(0, 0, 10, 10, 200, 200, pan_vx=1.0, margin=0)
    # +pan_vx looks further right: origin_x decreases
    assert xf1.origin_x < xf0.origin_x
