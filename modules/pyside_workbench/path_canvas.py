"""----------------------------------------------------------------------------
    path_canvas.py

    PySide plotter of commanded motion (VirtualCnc segments). Not a
    material-removal sim. Orthographic camera (Top default), corner view cube,
    rapid vs feed, PC marker.
----------------------------------------------------------------------------"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from modules.pyside_workbench import theme
from modules.pyside_workbench.path_camera import Camera, cube_facets, facet_normal
from modules.virtual_cnc import Point, Segment, VirtualCnc

_MARGIN_PX = 20.0
_MIN_SPAN = 1e-9
_MARKER_R = 5.0
_ZOOM_MIN = 0.05
_ZOOM_MAX = 80.0
_ZOOM_STEP = 1.15
# Max vertices in the live-orbit subsample (world XYZ, reprojected each move).
_PREVIEW_MAX = 4096


@dataclass(frozen=True)
class ViewTransform:
    """World XY (Y-up) → widget pixels (Y-down)."""

    scale: float
    origin_x: float
    origin_y: float

    def to_px(self, x: float, y: float) -> tuple[float, float]:
        return (self.origin_x + x * self.scale, self.origin_y - y * self.scale)

    def to_view(self, px: float, py: float) -> tuple[float, float]:
        s = self.scale if self.scale else 1.0
        return ((px - self.origin_x) / s, (self.origin_y - py) / s)


def bounds_xy(
    segments: Sequence[Segment], position: Point
) -> tuple[float, float, float, float]:
    """Axis-aligned XY bounds of path + marker (min_x, min_y, max_x, max_y)."""
    xs = [position.x]
    ys = [position.y]
    for seg in segments:
        xs.append(seg.start.x)
        xs.append(seg.end.x)
        ys.append(seg.start.y)
        ys.append(seg.end.y)
    return min(xs), min(ys), max(xs), max(ys)


def fit_xy(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    width: float,
    height: float,
    *,
    margin: float = _MARGIN_PX,
) -> ViewTransform:
    """Uniform scale + center the XY AABB in the widget."""
    w = max(float(width), 1.0)
    h = max(float(height), 1.0)
    span_x = max(max_x - min_x, _MIN_SPAN)
    span_y = max(max_y - min_y, _MIN_SPAN)
    inner_w = max(w - 2.0 * margin, 1.0)
    inner_h = max(h - 2.0 * margin, 1.0)
    scale = min(inner_w / span_x, inner_h / span_y)
    world_cx = (min_x + max_x) / 2.0
    world_cy = (min_y + max_y) / 2.0
    origin_x = (w / 2.0) - world_cx * scale
    origin_y = (h / 2.0) + world_cy * scale
    return ViewTransform(scale=scale, origin_x=origin_x, origin_y=origin_y)


def view_transform(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    width: float,
    height: float,
    *,
    zoom: float = 1.0,
    pan_vx: float = 0.0,
    pan_vy: float = 0.0,
    margin: float = _MARGIN_PX,
) -> ViewTransform:
    """Fitted view, then user zoom (about bounds center) and pan in view units."""
    fitted = fit_xy(
        min_x, min_y, max_x, max_y, width, height, margin=margin
    )
    z = min(_ZOOM_MAX, max(_ZOOM_MIN, float(zoom)))
    if z == 1.0 and pan_vx == 0.0 and pan_vy == 0.0:
        return fitted
    scale = fitted.scale * z
    w = max(float(width), 1.0)
    h = max(float(height), 1.0)
    cx = (min_x + max_x) / 2.0 + pan_vx
    cy = (min_y + max_y) / 2.0 + pan_vy
    return ViewTransform(
        scale=scale,
        origin_x=(w / 2.0) - cx * scale,
        origin_y=(h / 2.0) + cy * scale,
    )


_CUBE_SIZE = 112
_CUBE_MARGIN = 8


class ViewCube(QWidget):
    """CAD nav cube: click face / edge / corner to align; drag to orbit."""

    snap_requested = Signal(str)
    orbit_delta = Signal(float, float)  # d_yaw_deg, d_pitch_deg
    orbit_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pathViewCube")
        self.setFixedSize(_CUBE_SIZE, _CUBE_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setToolTip(
            "Drag to orbit · click a face, edge, or corner to align the view"
        )
        self._camera = Camera.top()
        self._press: QPoint | None = None
        self._dragged = False
        self._hover: str | None = None

    def set_camera(self, camera: Camera) -> None:
        self._camera = camera
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(_CUBE_SIZE, _CUBE_SIZE)

    def _project_cube(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        vx, vy, vz = self._camera.to_view(x, y, z)
        # Cube sits in the right half; axes occupy the left.
        cx, cy = 68.0, 56.0
        scale = 24.0
        return cx + vx * scale, cy - vy * scale, vz

    def _visible_facets(self) -> list[tuple[float, str, QPolygonF, bool]]:
        """(depth, region_key, poly, is_face) far → near."""
        out: list[tuple[float, str, QPolygonF, bool]] = []
        for key, verts in cube_facets():
            nx, ny, nz = facet_normal(verts)
            _, _, n_z = self._camera.to_view(nx, ny, nz)
            if n_z <= 0.08:
                continue
            pts = [self._project_cube(*v) for v in verts]
            depth = sum(p[2] for p in pts) / len(pts)
            poly = QPolygonF([QPointF(p[0], p[1]) for p in pts])
            out.append((depth, key, poly, "-" not in key))
        out.sort(key=lambda item: item[0])
        return out

    def region_at(self, x: float, y: float) -> str | None:
        """Hit-test a cube region key, or None. Nearer facets win."""
        hit = QPointF(x, y)
        for _depth, key, poly, _is_face in reversed(self._visible_facets()):
            if poly.containsPoint(hit, Qt.FillRule.OddEvenFill):
                return key
        return None

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawEllipse(QRect(2, 2, _CUBE_SIZE - 4, _CUBE_SIZE - 4))
        ring = QPen(QColor("#C5CAD3"))
        ring.setWidthF(1.2)
        p.setPen(ring)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRect(10, 8, 92, 92))
        p.setPen(QPen(QColor("#94A3B8"), 1.4))
        cx, cy, r = 56.0, 54.0, 48.0
        for ang in (0, 90, 180, 270):
            a = math.radians(ang)
            tx, ty = cx + r * math.sin(a), cy - r * math.cos(a)
            left = math.radians(ang - 16)
            right = math.radians(ang + 16)
            p.drawLine(
                QPointF(tx, ty),
                QPointF(cx + (r - 7) * math.sin(left), cy - (r - 7) * math.cos(left)),
            )
            p.drawLine(
                QPointF(tx, ty),
                QPointF(cx + (r - 7) * math.sin(right), cy - (r - 7) * math.cos(right)),
            )

        font = QFont(self.font())
        font.setPointSize(8)
        font.setBold(True)
        p.setFont(font)
        hi = QColor(theme.COLOR_ACCENT)
        hi.setAlpha(90)
        for _depth, key, poly, is_face in self._visible_facets():
            p.setPen(QPen(QColor("#9AA3B0"), 1.0))
            if key == self._hover:
                p.setBrush(hi)
            elif is_face:
                p.setBrush(QColor("#F4F6F8"))
            else:
                p.setBrush(QColor("#DDE3EA"))
            p.drawPolygon(poly)
            if is_face:
                c = poly.boundingRect().center()
                p.setPen(QColor("#334155"))
                p.drawText(
                    QRect(int(c.x()) - 24, int(c.y()) - 8, 48, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    key.upper(),
                )

        ox, oy = 28.0, 72.0
        ccx, ccy, _ = self._project_cube(0, 0, 0)
        for vec, color, label in (
            ((1.15, 0, 0), QColor("#DC2626"), "X"),
            ((0, 1.15, 0), QColor("#16A34A"), "Y"),
            ((0, 0, 1.15), QColor("#2563EB"), "Z"),
        ):
            px, py, _ = self._project_cube(*vec)
            p.setPen(QPen(color, 2.0))
            p.drawLine(QPointF(ox, oy), QPointF(ox + (px - ccx), oy + (py - ccy)))
            p.setPen(color)
            p.drawText(QPointF(ox + (px - ccx) + 2, oy + (py - ccy) + 4), label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()
            self._dragged = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._press is None:
            hover = self.region_at(pos.x(), pos.y())
            if hover != self._hover:
                self._hover = hover
                self.update()
            event.accept()
            return
        dx = pos.x() - self._press.x()
        dy = pos.y() - self._press.y()
        if abs(dx) + abs(dy) > 3:
            self._dragged = True
            self.orbit_delta.emit(dx * 0.6, dy * 0.6)
            self._press = pos
        event.accept()

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover is not None:
            self._hover = None
            self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._press is not None:
            if not self._dragged:
                pos = event.position()
                region = self.region_at(pos.x(), pos.y())
                if region:
                    self.snap_requested.emit(region)
            self._press = None
            self._dragged = False
            self.orbit_finished.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


def _path_add(
    path: QPainterPath,
    last: tuple[float, float] | None,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> tuple[float, float]:
    if last is not None and last[0] == x0 and last[1] == y0:
        path.lineTo(x1, y1)
    else:
        path.moveTo(x0, y0)
        path.lineTo(x1, y1)
    return (x1, y1)


class PathCanvas(QWidget):
    """Paints G0/G1/G2/G3 segments with an orthographic camera and a view cube.

    Geometry is projected once into a view-space QPainterPath. Resize/pan/zoom
    only change the widget transform. During orbit drag a decimated world-space
    subsample is reprojected each move; full cache rebuilds on release.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pathCanvas")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.setMinimumSize(120, 120)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._segments: Sequence[Segment] = ()
        self._position = Point(0.0, 0.0, 0.0)
        self._highlight_line: int | None = None
        self._camera = Camera.top()
        self.view_cube = ViewCube(self)
        self.view_cube.set_camera(self._camera)
        self.view_cube.snap_requested.connect(self.snap_view)
        self.view_cube.orbit_delta.connect(self.orbit)
        self.view_cube.orbit_finished.connect(self._end_orbit_gesture)
        self._place_cube()

        self._path_rapid = QPainterPath()
        self._path_feed = QPainterPath()
        self._path_hi_r = QPainterPath()
        self._path_hi_f = QPainterPath()
        self._last_rapid: tuple[float, float] | None = None
        self._last_feed: tuple[float, float] | None = None
        self._bounds = (0.0, 0.0, 0.0, 0.0)
        self._marker_view = (0.0, 0.0)
        self._axis_view: list[tuple[float, float]] = []
        self._seg_ranges: dict[int, list[int]] = {}
        self._cache_n = 0
        self._cache_cam: Camera | None = None
        self._preview_xyz: list[tuple[float, float, float, str]] = []
        self._orbit_live = False
        self._nav_preview = False

        self._orbit_timer = QTimer(self)
        self._orbit_timer.setSingleShot(True)
        self._orbit_timer.setInterval(32)
        self._orbit_timer.timeout.connect(self._rebuild_view_cache)

        self._nav_timer = QTimer(self)
        self._nav_timer.setSingleShot(True)
        self._nav_timer.setInterval(80)
        self._nav_timer.timeout.connect(self._end_nav_preview)

        self._zoom = 1.0
        self._pan_vx = 0.0
        self._pan_vy = 0.0
        self._pan_from: QPoint | None = None
        self._pan_vx0 = 0.0
        self._pan_vy0 = 0.0
        self._orbit_from: QPoint | None = None
        self._orbit_pivot: Point | None = None
        self._orbit_px = 0.0
        self._orbit_py = 0.0
        self._lock_view_scale: float | None = None

    def fit_view(self) -> None:
        """Reset zoom/pan so the path fills the widget (named-view default)."""
        self._clear_orbit_pivot()
        self._nav_preview = False
        if self._nav_timer.isActive():
            self._nav_timer.stop()
        self._zoom = 1.0
        self._pan_vx = 0.0
        self._pan_vy = 0.0
        self.update()

    def _xf(self) -> ViewTransform:
        return view_transform(
            *self._bounds,
            self.width(),
            self.height(),
            zoom=self._zoom,
            pan_vx=self._pan_vx,
            pan_vy=self._pan_vy,
        )

    @property
    def camera(self) -> Camera:
        return self._camera

    def snap_view(self, name: str) -> None:
        self._clear_orbit_pivot()
        self._camera = self._camera.snap(name)
        self.view_cube.set_camera(self._camera)
        self._rebuild_view_cache()

    def is_orbit_preview(self) -> bool:
        return self._orbit_live

    def is_nav_preview(self) -> bool:
        return self._nav_preview

    def _use_preview_stroke(self) -> bool:
        return bool(
            self._preview_xyz
            and (self._orbit_live or self._nav_preview)
        )

    def _end_nav_preview(self) -> None:
        self._nav_preview = False
        self.update()

    def preview_count(self) -> int:
        return len(self._preview_xyz)

    def orbit(self, d_yaw_deg: float, d_pitch_deg: float) -> None:
        if self._orbit_pivot is None:
            # View-cube drag: tumble about the point in the middle of the view.
            self._capture_orbit_pivot(self.width() / 2.0, self.height() / 2.0)
        self._orbit_live = True
        self._camera = self._camera.orbit(d_yaw_deg, d_pitch_deg)
        self.view_cube.set_camera(self._camera)
        self._keep_orbit_pivot()
        self._refresh_marker_axes()
        # Cheap subsample paint this frame; full project waits for release.
        if self._orbit_timer.isActive():
            self._orbit_timer.stop()
        self.update()

    def _clear_orbit_pivot(self) -> None:
        self._orbit_pivot = None

    def _end_orbit_gesture(self) -> None:
        if self._orbit_timer.isActive():
            self._orbit_timer.stop()
        self._orbit_live = False
        # Keep pixels-per-view-unit; orbit changes the AABB so the same
        # zoom multiplier would otherwise jump the apparent zoom.
        if self.width() > 0 and self.height() > 0:
            self._lock_view_scale = self._xf().scale
        self._rebuild_view_cache()
        self._clear_orbit_pivot()

    def _capture_orbit_pivot(self, px: float, py: float) -> None:
        """World point on the click ray (view-depth of the tool marker)."""
        if self.width() < 1 or self.height() < 1:
            return
        xf = self._xf()
        vx, vy = xf.to_view(px, py)
        _, _, vz = self._camera.to_view(
            self._position.x, self._position.y, self._position.z
        )
        wx, wy, wz = self._camera.from_view(vx, vy, vz)
        self._orbit_pivot = Point(wx, wy, wz)
        self._orbit_px = float(px)
        self._orbit_py = float(py)

    def _set_pan_for_view_point(
        self, vx: float, vy: float, px: float, py: float
    ) -> None:
        min_x, min_y, max_x, max_y = self._bounds
        fitted = fit_xy(min_x, min_y, max_x, max_y, self.width(), self.height())
        scale = fitted.scale * self._zoom
        if scale <= 0:
            return
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        w = float(max(self.width(), 1))
        h = float(max(self.height(), 1))
        self._pan_vx = vx - cx - (px - w / 2.0) / scale
        self._pan_vy = vy - cy + (py - h / 2.0) / scale

    def _keep_orbit_pivot(self) -> None:
        if self._orbit_pivot is None:
            return
        vx, vy, _ = self._camera.to_view(
            self._orbit_pivot.x, self._orbit_pivot.y, self._orbit_pivot.z
        )
        self._set_pan_for_view_point(vx, vy, self._orbit_px, self._orbit_py)

    def _place_cube(self) -> None:
        self.view_cube.move(
            max(0, self.width() - _CUBE_SIZE - _CUBE_MARGIN),
            max(0, self.height() - _CUBE_SIZE - _CUBE_MARGIN),
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_cube()

    def set_path(
        self,
        segments: Sequence[Segment],
        position: Point,
        *,
        highlight_line: int | None = None,
    ) -> None:
        self._segments = segments
        self._position = position
        hi_changed = highlight_line != self._highlight_line
        self._highlight_line = highlight_line
        self._sync_cache(hi_changed=hi_changed)
        self.update()

    def _rebuild_preview_samples(self) -> None:
        """World-space subsample for live orbit (O(n) index, no projection)."""
        segs = self._segments
        n = len(segs)
        if n == 0:
            self._preview_xyz = []
            return
        stride = max(1, (n + _PREVIEW_MAX - 1) // _PREVIEW_MAX)
        out: list[tuple[float, float, float, str]] = []
        for i in range(0, n, stride):
            s = segs[i]
            out.append((s.start.x, s.start.y, s.start.z, s.kind))
        last = segs[-1]
        end = (last.end.x, last.end.y, last.end.z, last.kind)
        if not out or out[-1][:3] != end[:3]:
            out.append(end)
        self._preview_xyz = out

    def _sync_cache(self, *, hi_changed: bool = False) -> None:
        n = len(self._segments)
        if self._orbit_live:
            self._refresh_marker_axes()
            return
        cam_changed = self._cache_cam != self._camera
        if cam_changed or n < self._cache_n:
            self._rebuild_view_cache()
            return
        if n > self._cache_n:
            self._project_slice(self._cache_n, n)
            self._cache_n = n
            self._rebuild_preview_samples()
            self._refresh_marker_axes()
            self._rebuild_hi_paths()
            return
        self._refresh_marker_axes()
        if hi_changed:
            self._rebuild_hi_paths()

    def _rebuild_view_cache(self) -> None:
        self._path_rapid = QPainterPath()
        self._path_feed = QPainterPath()
        self._last_rapid = None
        self._last_feed = None
        self._seg_ranges = {}
        self._cache_n = 0
        self._cache_cam = self._camera
        n = len(self._segments)
        if n:
            self._project_slice(0, n)
            self._cache_n = n
        self._rebuild_preview_samples()
        self._apply_locked_view_scale()
        self._refresh_marker_axes()
        self._rebuild_hi_paths()
        self._keep_orbit_pivot()
        self.update()

    def _apply_locked_view_scale(self) -> None:
        locked = self._lock_view_scale
        self._lock_view_scale = None
        if locked is None or locked <= 0:
            return
        if self.width() < 1 or self.height() < 1:
            return
        fitted = fit_xy(*self._bounds, self.width(), self.height())
        if fitted.scale <= 0:
            return
        self._zoom = min(_ZOOM_MAX, max(_ZOOM_MIN, locked / fitted.scale))

    def _project_slice(self, i0: int, i1: int) -> None:
        cam = self._camera
        xs: list[float] = []
        ys: list[float] = []
        if i0 == 0:
            pass
        else:
            xs.extend(self._bounds[0::2])
            ys.extend(self._bounds[1::2])
        for i in range(i0, i1):
            seg = self._segments[i]
            x0, y0, _ = cam.to_view(seg.start.x, seg.start.y, seg.start.z)
            x1, y1, _ = cam.to_view(seg.end.x, seg.end.y, seg.end.z)
            xs.extend((x0, x1))
            ys.extend((y0, y1))
            rng = self._seg_ranges.get(seg.line_index)
            if rng is None:
                self._seg_ranges[seg.line_index] = [i, i + 1]
            else:
                rng[1] = i + 1
            if seg.kind == "rapid":
                self._last_rapid = _path_add(
                    self._path_rapid, self._last_rapid, x0, y0, x1, y1
                )
            else:
                self._last_feed = _path_add(
                    self._path_feed, self._last_feed, x0, y0, x1, y1
                )
        mx, my, _ = cam.to_view(
            self._position.x, self._position.y, self._position.z
        )
        xs.append(mx)
        ys.append(my)
        self._bounds = (min(xs), min(ys), max(xs), max(ys))

    def _refresh_marker_axes(self) -> None:
        cam = self._camera
        mx, my, _ = cam.to_view(
            self._position.x, self._position.y, self._position.z
        )
        self._marker_view = (mx, my)
        span = max(abs(v) for v in self._bounds) if self._cache_n else 1.0
        axis_len = max(span, 1.0) * 0.2
        ox, oy, _ = cam.to_view(0.0, 0.0, 0.0)
        self._axis_view = [(ox, oy)]
        for vec in ((axis_len, 0.0, 0.0), (0.0, axis_len, 0.0), (0.0, 0.0, axis_len)):
            vx, vy, _ = cam.to_view(*vec)
            self._axis_view.append((vx, vy))

    def _rebuild_hi_paths(self) -> None:
        self._path_hi_r = QPainterPath()
        self._path_hi_f = QPainterPath()
        hi = self._highlight_line
        if hi is None or hi < 0:
            return
        rng = self._seg_ranges.get(hi)
        if not rng:
            return
        cam = self._camera
        last_r = last_f = None
        for i in range(rng[0], rng[1]):
            seg = self._segments[i]
            x0, y0, _ = cam.to_view(seg.start.x, seg.start.y, seg.start.z)
            x1, y1, _ = cam.to_view(seg.end.x, seg.end.y, seg.end.z)
            if seg.kind == "rapid":
                last_r = _path_add(self._path_hi_r, last_r, x0, y0, x1, y1)
            else:
                last_f = _path_add(self._path_hi_f, last_f, x0, y0, x1, y1)

    def _paint_orbit_preview(
        self, painter: QPainter, rapid_pen: QPen, feed_pen: QPen
    ) -> None:
        """Reproject the world subsample with the live camera (O(preview))."""
        cam = self._camera
        rapid = QPainterPath()
        feed = QPainterPath()
        last_r: tuple[float, float] | None = None
        last_f: tuple[float, float] | None = None
        prev: tuple[float, float, str] | None = None
        for x, y, z, kind in self._preview_xyz:
            vx, vy, _ = cam.to_view(x, y, z)
            if prev is not None:
                px, py, pk = prev
                if kind == "rapid" and pk == "rapid":
                    last_r = _path_add(rapid, last_r, px, py, vx, vy)
                else:
                    last_f = _path_add(feed, last_f, px, py, vx, vy)
            prev = (vx, vy, kind)
        if not rapid.isEmpty():
            painter.setPen(rapid_pen)
            painter.drawPath(rapid)
        if not feed.isEmpty():
            painter.setPen(feed_pen)
            painter.drawPath(feed)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        n = self._cache_n
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            n < 80000 and not self._use_preview_stroke(),
        )
        painter.fillRect(self.rect(), QColor(theme.COLOR_SURFACE))

        xf = self._xf()
        # view (x right, y up) → widget pixels
        painter.setTransform(
            QTransform(xf.scale, 0.0, 0.0, -xf.scale, xf.origin_x, xf.origin_y)
        )

        if len(self._axis_view) == 4:
            origin = QPointF(*self._axis_view[0])
            for pt, color in (
                (self._axis_view[1], QColor("#FECACA")),
                (self._axis_view[2], QColor("#BBF7D0")),
                (self._axis_view[3], QColor("#BFDBFE")),
            ):
                pen = QPen(color, 1.0)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawLine(origin, QPointF(*pt))

        rapid_pen = QPen(QColor("#64748B"))
        rapid_pen.setWidthF(1.2)
        rapid_pen.setStyle(Qt.PenStyle.DashLine)
        rapid_pen.setCosmetic(True)
        feed_pen = QPen(QColor(theme.COLOR_ACCENT))
        feed_pen.setWidthF(2.0)
        feed_pen.setCosmetic(True)
        hi_rapid = QPen(QColor("#475569"))
        hi_rapid.setWidthF(2.4)
        hi_rapid.setStyle(Qt.PenStyle.DashLine)
        hi_rapid.setCosmetic(True)
        hi_feed = QPen(QColor(theme.COLOR_ACCENT_HOVER))
        hi_feed.setWidthF(3.0)
        hi_feed.setCosmetic(True)

        if self._use_preview_stroke():
            self._paint_orbit_preview(painter, rapid_pen, feed_pen)
        else:
            if not self._path_rapid.isEmpty():
                painter.setPen(rapid_pen)
                painter.drawPath(self._path_rapid)
            if not self._path_feed.isEmpty():
                painter.setPen(feed_pen)
                painter.drawPath(self._path_feed)
            if not self._path_hi_r.isEmpty():
                painter.setPen(hi_rapid)
                painter.drawPath(self._path_hi_r)
            if not self._path_hi_f.isEmpty():
                painter.setPen(hi_feed)
                painter.drawPath(self._path_hi_f)

        painter.resetTransform()
        mx, my = xf.to_px(*self._marker_view)
        painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
        painter.setBrush(QColor("#EA580C"))
        painter.drawEllipse(QPointF(mx, my), _MARKER_R, _MARKER_R)

    def wheelEvent(self, event: QWheelEvent) -> None:
        dy = event.angleDelta().y()
        if dy == 0:
            event.ignore()
            return
        factor = _ZOOM_STEP if dy > 0 else 1.0 / _ZOOM_STEP
        pos = event.position()
        self._zoom_at(factor, pos.x(), pos.y())
        event.accept()

    def _zoom_at(self, factor: float, px: float, py: float) -> None:
        xf = self._xf()
        vx, vy = xf.to_view(px, py)
        new_zoom = min(_ZOOM_MAX, max(_ZOOM_MIN, self._zoom * factor))
        if new_zoom == self._zoom:
            return
        min_x, min_y, max_x, max_y = self._bounds
        fitted = fit_xy(min_x, min_y, max_x, max_y, self.width(), self.height())
        scale = fitted.scale * new_zoom
        if scale <= 0:
            return
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        w = float(self.width())
        h = float(self.height())
        self._zoom = new_zoom
        self._pan_vx = vx - cx - (px - w / 2.0) / scale
        self._pan_vy = vy - cy + (py - h / 2.0) / scale
        self._nav_preview = True
        self._nav_timer.start()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            pos = event.position()
            self._capture_orbit_pivot(pos.x(), pos.y())
            self._orbit_from = pos.toPoint()
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            event.accept()
            return
        if event.button() in (
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.MiddleButton,
        ):
            self._pan_from = event.position().toPoint()
            self._pan_vx0 = self._pan_vx
            self._pan_vy0 = self._pan_vy
            self._nav_preview = True
            if self._nav_timer.isActive():
                self._nav_timer.stop()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._orbit_from is not None:
            pos = event.position().toPoint()
            d = pos - self._orbit_from
            if d.x() or d.y():
                # Same mapping as the view cube (right = yaw, up = look up).
                self.orbit(d.x() * 0.6, d.y() * 0.6)
                self._orbit_from = pos
            event.accept()
            return
        if self._pan_from is None:
            return
        xf = self._xf()
        s = xf.scale if xf.scale else 1.0
        d = event.position().toPoint() - self._pan_from
        self._pan_vx = self._pan_vx0 - d.x() / s
        self._pan_vy = self._pan_vy0 + d.y() / s
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._orbit_from is not None:
            self._orbit_from = None
            self._end_orbit_gesture()
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            event.accept()
            return
        if self._pan_from is not None:
            self._pan_from = None
            self._nav_preview = False
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.fit_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class PathPanel(QWidget):
    """Dockable path plotter: preview open G-code, marker follows PC.

    Live mode: append commanded lines as they are sent to Virtual CNC.
    """

    preview_requested = Signal()
    machine_target_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pathPanel")
        self._lines: list[str] = []
        self._pc = 0
        self._live = False
        self._live_i = 0
        self._full = VirtualCnc()
        self._head = VirtualCnc()

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        tools = QHBoxLayout()
        tools.setSpacing(6)
        self.btn_preview = QPushButton("Preview")
        self.btn_preview.setObjectName("pathPreview")
        self.btn_preview.setToolTip("Rebuild path from the open G-code file")
        self.btn_preview.clicked.connect(self.preview_requested.emit)
        tools.addWidget(self.btn_preview)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setObjectName("pathClear")
        self.btn_clear.setToolTip("Clear path and marker")
        self.btn_clear.clicked.connect(self.clear)
        tools.addWidget(self.btn_clear)
        self.btn_fit = QPushButton("Fit")
        self.btn_fit.setObjectName("pathFit")
        self.btn_fit.setToolTip(
            "Fit path in view (double-click canvas). "
            "Wheel zoom, left-drag pan, right-drag rotate."
        )
        tools.addWidget(self.btn_fit)
        self.chk_machine = QCheckBox("Machine target")
        self.chk_machine.setObjectName("pathMachineTarget")
        self.chk_machine.setToolTip(
            "When Connect is pressed, open Virtual CNC instead of serial "
            "(plot commanded motion, no hardware)"
        )
        self.chk_machine.toggled.connect(self.machine_target_toggled.emit)
        tools.addWidget(self.chk_machine)
        tools.addStretch(1)
        root.addLayout(tools)

        self.canvas = PathCanvas()
        self.btn_fit.clicked.connect(self.canvas.fit_view)
        root.addWidget(self.canvas, 1)

        self.status = QLabel()
        self.status.setObjectName("pathStatus")
        self.status.setFont(theme.mono_font(10))
        self.status.setStyleSheet(f"color: {theme.COLOR_MUTED};")
        self.status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        root.addWidget(self.status)
        self._refresh()

    @property
    def marker_position(self) -> Point:
        return self._full.position if self._live else self._head.position

    @property
    def segments(self) -> tuple[Segment, ...]:
        return self._full.segments

    def segment_count(self) -> int:
        return len(self._full.segment_list())

    def is_live(self) -> bool:
        return self._live

    def begin_live(self) -> None:
        """Clear the plot and append from the machine send stream."""
        self._live = True
        self._live_i = 0
        self._lines = []
        self._pc = 0
        self._full.reset()
        self._head.reset()
        self.btn_preview.setEnabled(False)
        self._refresh()

    def end_live(self) -> None:
        self._live = False
        self.btn_preview.setEnabled(True)

    def apply_live_line(self, line: str) -> Segment | None:
        """Plot one commanded line (EV_DATA_OUT while Virtual is open)."""
        if not self._live:
            return None
        payload = line.strip()
        if payload.startswith("$J="):
            payload = payload[3:]
        seg = self._full.apply_line(payload, line_index=self._live_i)
        self._live_i += 1
        self._refresh()
        return seg

    def set_program(self, lines: Sequence[str]) -> None:
        if self._live:
            return
        self._lines = list(lines)
        self._full.reset()
        self._full.apply_lines(self._lines)
        self._rebuild_head()
        self._refresh()

    def set_pc(self, pc: int) -> None:
        try:
            pc_i = int(pc)
        except (TypeError, ValueError):
            pc_i = 0
        self._pc = max(0, pc_i)
        if self._live:
            return
        self._rebuild_head()
        self._refresh()

    @Slot()
    def clear(self) -> None:
        self._lines = []
        self._pc = 0
        self._full.reset()
        self._head.reset()
        self._refresh()

    def _rebuild_head(self) -> None:
        self._head.reset()
        if self._pc > 0 and self._lines:
            self._head.apply_lines(self._lines[: self._pc])

    def _refresh(self) -> None:
        if self._live:
            pos = self._full.position
            hi = (
                self._full.segments[-1].line_index if self._full.segments else None
            )
        else:
            pos = self._head.position
            hi = self._pc - 1 if self._pc > 0 else None
        self.canvas.set_path(
            self._full.segment_list(),
            pos,
            highlight_line=hi,
        )
        n = self.segment_count()
        msg = (
            f"X{pos.x:.3f} Y{pos.y:.3f} Z{pos.z:.3f}  ·  {n} seg"
            f"{'' if n == 1 else 's'}"
        )
        if self._live:
            msg += "  ·  live"
        skipped = self._full.skipped
        if skipped:
            codes = ", ".join(sorted(set(skipped)))
            msg += f"  ·  skipped {codes}"
        self.status.setText(msg)
