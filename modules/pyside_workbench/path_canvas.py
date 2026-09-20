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
    QPixmap,
    QPolygonF,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
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
_PLAY_RATES = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
_PLAY_LINES_PER_SEC = 45.0  # at 1×


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


_CUBE_SIZE = 135
_CUBE_MARGIN = 8
_CUBE_CX = _CUBE_SIZE / 2.0
_CUBE_CY = _CUBE_SIZE / 2.0
_CUBE_SCALE = 29.0  # world ±1 → pixels; ~10% over 26


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
        return (
            _CUBE_CX + vx * _CUBE_SCALE,
            _CUBE_CY - vy * _CUBE_SCALE,
            vz,
        )

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
        # Paint faces under edges under corners so chamfers stay pickable
        # when they overlap a face in 2D (face-on views).
        out.sort(key=lambda item: (item[1].count("-"), item[0]))
        return out

    def region_at(self, x: float, y: float) -> str | None:
        """Hit-test a cube region. Overlaps: corner > edge > face, then nearer."""
        hit = QPointF(x, y)
        hits: list[tuple[int, float, str]] = []
        for depth, key, poly, _is_face in self._visible_facets():
            if poly.containsPoint(hit, Qt.FillRule.OddEvenFill):
                hits.append((key.count("-"), depth, key))
        if not hits:
            return None
        return max(hits, key=lambda item: (item[0], item[1]))[2]

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

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
        self._seg_ranges: dict[int, list[int]] = {}
        self._cache_n = 0
        self._cache_cam: Camera | None = None
        self._preview_xyz: list[tuple[float, float, float, str]] = []
        self._orbit_live = False
        self._nav_preview = False
        self._stamp: QPixmap | None = None
        self._stamp_key: tuple | None = None
        self._view_segs: list[tuple[float, float, float, float, str, int]] = []
        self._upto_pc: int | None = None
        self._drawn_end = 0
        self._drawn_exact = True

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
        self._invalidate_stamp()
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

    def set_stroke_preview(self, on: bool) -> None:
        """Use the decimated stroke (pan/zoom/orbit only — not play/scrub)."""
        self._nav_preview = bool(on)
        if not on:
            self.update()

    def _invalidate_stamp(self) -> None:
        self._stamp = None
        self._stamp_key = None

    def _stamp_key_now(self) -> tuple:
        return (
            self._cache_cam,
            round(self._zoom, 6),
            round(self._pan_vx, 6),
            round(self._pan_vy, 6),
            self.width(),
            self.height(),
            self._cache_n,
        )

    def _ensure_stamp(self) -> QPixmap | None:
        """Rasterize static path (no marker/highlight) for cheap play/scrub paints."""
        w, h = self.width(), self.height()
        if w < 2 or h < 2 or self._cache_n <= 0:
            self._invalidate_stamp()
            return None
        key = self._stamp_key_now()
        if self._stamp is not None and self._stamp_key == key:
            return self._stamp
        dpr = self.devicePixelRatioF() or 1.0
        pm = QPixmap(max(1, int(w * dpr)), max(1, int(h * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor(theme.COLOR_SURFACE))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, self._cache_n < 80000)
        xf = self._xf()
        painter.setTransform(
            QTransform(xf.scale, 0.0, 0.0, -xf.scale, xf.origin_x, xf.origin_y)
        )
        rapid_pen = QPen(QColor("#64748B"))
        rapid_pen.setWidthF(1.2)
        rapid_pen.setStyle(Qt.PenStyle.DashLine)
        rapid_pen.setCosmetic(True)
        feed_pen = QPen(QColor(theme.COLOR_ACCENT))
        feed_pen.setWidthF(2.0)
        feed_pen.setCosmetic(True)
        if not self._path_rapid.isEmpty():
            painter.setPen(rapid_pen)
            painter.drawPath(self._path_rapid)
        if not self._path_feed.isEmpty():
            painter.setPen(feed_pen)
            painter.drawPath(self._path_feed)
        painter.end()
        self._stamp = pm
        self._stamp_key = key
        return pm

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
            _CUBE_MARGIN,
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_cube()
        self._invalidate_stamp()

    def set_path(
        self,
        segments: Sequence[Segment],
        position: Point,
        *,
        highlight_line: int | None = None,
        upto_pc: int | None = None,
        prefix_exact: bool = True,
    ) -> None:
        self._segments = segments
        self._position = position
        hi_changed = highlight_line != self._highlight_line
        self._highlight_line = highlight_line
        self._upto_pc = upto_pc
        self._sync_cache(hi_changed=hi_changed)
        if not self._orbit_live:
            self._sync_drawn_prefix(exact=prefix_exact)
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
            self._sync_drawn_prefix(exact=True)
            self._invalidate_stamp()
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
        self._view_segs = []
        self._drawn_end = 0
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
        self._sync_drawn_prefix(exact=True)
        self._invalidate_stamp()
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
            self._view_segs.append(
                (x0, y0, x1, y1, seg.kind, int(seg.line_index))
            )
        mx, my, _ = cam.to_view(
            self._position.x, self._position.y, self._position.z
        )
        xs.append(mx)
        ys.append(my)
        self._bounds = (min(xs), min(ys), max(xs), max(ys))

    def _target_drawn_end(self) -> int:
        n = len(self._view_segs)
        if self._upto_pc is None:
            return n
        pc = self._upto_pc
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            if self._view_segs[mid][5] < pc:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _add_view_seg(self, i: int) -> None:
        x0, y0, x1, y1, kind, _li = self._view_segs[i]
        if kind == "rapid":
            self._last_rapid = _path_add(
                self._path_rapid, self._last_rapid, x0, y0, x1, y1
            )
        else:
            self._last_feed = _path_add(
                self._path_feed, self._last_feed, x0, y0, x1, y1
            )

    def _rebuild_drawn(self, end: int, *, exact: bool) -> None:
        self._path_rapid = QPainterPath()
        self._path_feed = QPainterPath()
        self._last_rapid = None
        self._last_feed = None
        if end <= 0:
            return
        stride = 1 if exact else max(1, end // _PREVIEW_MAX)
        last_i = 0
        for i in range(0, end, stride):
            self._add_view_seg(i)
            last_i = i
        if last_i != end - 1:
            self._add_view_seg(end - 1)

    def _append_stamp_segs(self, i0: int, i1: int) -> None:
        if self._stamp is None or i0 >= i1:
            return
        painter = QPainter(self._stamp)
        xf = self._xf()
        painter.setTransform(
            QTransform(xf.scale, 0.0, 0.0, -xf.scale, xf.origin_x, xf.origin_y)
        )
        rapid_pen = QPen(QColor("#64748B"))
        rapid_pen.setWidthF(1.2)
        rapid_pen.setStyle(Qt.PenStyle.DashLine)
        rapid_pen.setCosmetic(True)
        feed_pen = QPen(QColor(theme.COLOR_ACCENT))
        feed_pen.setWidthF(2.0)
        feed_pen.setCosmetic(True)
        for i in range(i0, i1):
            x0, y0, x1, y1, kind, _li = self._view_segs[i]
            painter.setPen(rapid_pen if kind == "rapid" else feed_pen)
            painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
        painter.end()

    def _sync_drawn_prefix(self, *, exact: bool = True) -> None:
        """Show only segments with line_index < upto_pc (None = all)."""
        end = self._target_drawn_end()
        if end == self._drawn_end and self._drawn_exact == exact:
            return
        if exact and self._drawn_exact and end > self._drawn_end:
            self._append_stamp_segs(self._drawn_end, end)
            for i in range(self._drawn_end, end):
                self._add_view_seg(i)
            self._drawn_end = end
            return
        self._rebuild_drawn(end, exact=exact)
        self._drawn_end = end
        self._drawn_exact = exact
        self._invalidate_stamp()

    def _refresh_marker_axes(self) -> None:
        cam = self._camera
        mx, my, _ = cam.to_view(
            self._position.x, self._position.y, self._position.z
        )
        self._marker_view = (mx, my)

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
        xf = self._xf()
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

        used_stamp = False
        if self._use_preview_stroke():
            painter.fillRect(self.rect(), QColor(theme.COLOR_SURFACE))
            painter.setTransform(
                QTransform(xf.scale, 0.0, 0.0, -xf.scale, xf.origin_x, xf.origin_y)
            )
            self._paint_orbit_preview(painter, rapid_pen, feed_pen)
        else:
            stamp = self._ensure_stamp()
            if stamp is not None:
                painter.drawPixmap(0, 0, stamp)
                used_stamp = True
            else:
                painter.fillRect(self.rect(), QColor(theme.COLOR_SURFACE))
                painter.setTransform(
                    QTransform(xf.scale, 0.0, 0.0, -xf.scale, xf.origin_x, xf.origin_y)
                )
                if not self._path_rapid.isEmpty():
                    painter.setPen(rapid_pen)
                    painter.drawPath(self._path_rapid)
                if not self._path_feed.isEmpty():
                    painter.setPen(feed_pen)
                    painter.drawPath(self._path_feed)
            if used_stamp:
                painter.setTransform(
                    QTransform(xf.scale, 0.0, 0.0, -xf.scale, xf.origin_x, xf.origin_y)
                )
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
        self._paint_hud_triad(painter)

    def _hud_origin(self) -> tuple[float, float]:
        """Triad origin: bottom, on the nav cube's vertical centerline."""
        axis_px = 28.0
        margin = 16.0
        ox = float(self.width()) - _CUBE_MARGIN - _CUBE_SIZE / 2.0
        oy = float(self.height()) - margin - axis_px
        return ox, oy

    def _paint_hud_triad(self, painter: QPainter) -> None:
        """Lettered RGB axes, screen-fixed under the cube; follow the path camera."""
        ox, oy = self._hud_origin()
        axis_px = 28.0
        cam = self._camera
        oxv, oyv, _ = cam.to_view(0.0, 0.0, 0.0)
        font = QFont(self.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for vec, color, label in (
            ((1.0, 0.0, 0.0), QColor("#DC2626"), "X"),
            ((0.0, 1.0, 0.0), QColor("#16A34A"), "Y"),
            ((0.0, 0.0, 1.0), QColor("#2563EB"), "Z"),
        ):
            vx, vy, _ = cam.to_view(*vec)
            dx, dy = vx - oxv, vy - oyv
            length = math.hypot(dx, dy)
            if length < 1e-6:
                continue
            sx = dx / length * axis_px
            sy = -dy / length * axis_px
            painter.setPen(QPen(color, 2.0))
            painter.drawLine(QPointF(ox, oy), QPointF(ox + sx, oy + sy))
            painter.drawText(QPointF(ox + sx + 3, oy + sy + 4), label)

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
        self._invalidate_stamp()
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
    pc_seeked = Signal(int)  # preview play/scrub → MainWindow.set_pc

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pathPanel")
        self._lines: list[str] = []
        self._pc = 0
        self._live = False
        self._live_i = 0
        self._scrubbing = False
        self._full = VirtualCnc()
        self._poses: list[Point] = [Point(0.0, 0.0, 0.0)]
        self._playing = False
        self._play_dir = 1
        self._play_speed = 1.0
        self._play_accum = 0.0
        self._updating_slider = False

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

        transport = QHBoxLayout()
        transport.setSpacing(6)
        self.btn_play = QPushButton("Play")
        self.btn_play.setObjectName("pathPlay")
        self.btn_play.setToolTip(
            "Preview play along the drawn path (Preview first; does not send G-code)"
        )
        self.btn_play.clicked.connect(self.toggle_play)
        transport.addWidget(self.btn_play)
        self.chk_reverse = QCheckBox("Rev")
        self.chk_reverse.setObjectName("pathReverse")
        self.chk_reverse.setToolTip("Play toward the start of the program")
        self.chk_reverse.toggled.connect(self._on_reverse_toggled)
        transport.addWidget(self.chk_reverse)
        self.cmb_speed = QComboBox()
        self.cmb_speed.setObjectName("pathSpeed")
        self.cmb_speed.setToolTip("Preview play speed")
        for rate in _PLAY_RATES:
            self.cmb_speed.addItem(f"{rate:g}×", rate)
        self.cmb_speed.setCurrentIndex(_PLAY_RATES.index(1.0))
        self.cmb_speed.currentIndexChanged.connect(self._on_speed_changed)
        transport.addWidget(self.cmb_speed)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("pathScrub")
        self.slider.setToolTip("Scrub program counter / path marker")
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.valueChanged.connect(self._on_scrub)
        self.slider.sliderPressed.connect(self._on_scrub_pressed)
        self.slider.sliderReleased.connect(self._on_scrub_released)
        transport.addWidget(self.slider, 1)
        self.lbl_pc = QLabel("PC 0/0")
        self.lbl_pc.setObjectName("pathPcLabel")
        self.lbl_pc.setFont(theme.mono_font(10))
        transport.addWidget(self.lbl_pc)
        root.addLayout(transport)

        self._play_timer = QTimer(self)
        self._play_timer.setInterval(33)
        self._play_timer.timeout.connect(self._on_play_timer)

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
        return self._full.position if self._live else self._pose_at_pc()

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
        self._full.reset()
        self.stop_play()
        self.btn_preview.setEnabled(False)
        self._set_transport_enabled(False)
        self._refresh()

    def end_live(self) -> None:
        self._live = False
        self.btn_preview.setEnabled(True)
        self._set_transport_enabled(bool(self._lines))

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
        self._build_pc_poses()
        self.stop_play()
        n = len(self._lines)
        self._pc = n
        self._set_transport_enabled(bool(self._lines))
        self._refresh()

    def set_pc(self, pc: int) -> None:
        try:
            pc_i = int(pc)
        except (TypeError, ValueError):
            pc_i = 0
        n = len(self._lines)
        if n == 0:
            self._pc = 0
        else:
            self._pc = max(0, min(pc_i, n))
        self._sync_transport_ui()
        if self._live:
            return
        self._refresh()

    @Slot()
    def clear(self) -> None:
        self.stop_play()
        self._lines = []
        self._pc = 0
        self._full.reset()
        self._poses = [Point(0.0, 0.0, 0.0)]
        self._set_transport_enabled(False)
        self._refresh()

    def _build_pc_poses(self) -> None:
        """Position after lines[:i] for i in 0..n — O(segments) once per preview."""
        origin = Point(0.0, 0.0, 0.0)
        n = len(self._lines)
        segs = self._full.segment_list()
        if segs:
            origin = segs[0].start
        poses = [origin] * (n + 1)
        last = origin
        si = 0
        for i in range(n):
            while si < len(segs) and segs[si].line_index == i:
                last = segs[si].end
                si += 1
            poses[i + 1] = last
        self._poses = poses

    def _pose_at_pc(self) -> Point:
        poses = self._poses
        if not poses:
            return Point(0.0, 0.0, 0.0)
        i = max(0, min(self._pc, len(poses) - 1))
        return poses[i]

    def _set_transport_enabled(self, on: bool) -> None:
        on = bool(on) and not self._live
        self.btn_play.setEnabled(on)
        self.chk_reverse.setEnabled(on)
        self.cmb_speed.setEnabled(on)
        self.slider.setEnabled(on)

    def _sync_transport_ui(self) -> None:
        n = len(self._lines)
        self._updating_slider = True
        self.slider.setMaximum(n)  # n = after last line
        self.slider.setValue(self._pc if n else 0)
        self._updating_slider = False
        self.lbl_pc.setText(f"PC {self._pc}/{n}")
        self.btn_play.setText("Pause" if self._playing else "Play")

    def _seek(self, pc: int) -> None:
        n = len(self._lines)
        if n == 0:
            pc = 0
        else:
            pc = max(0, min(int(pc), n))
        self._pc = pc
        self._sync_transport_ui()
        self._refresh()
        self.pc_seeked.emit(pc)

    @Slot()
    def toggle_play(self) -> None:
        if self._playing:
            self.stop_play()
        else:
            self.start_play()

    def start_play(self) -> None:
        if self._live or not self._lines:
            return
        n = len(self._lines)
        if self._play_dir > 0 and self._pc >= n:
            self._seek(0)
        elif self._play_dir < 0 and self._pc <= 0:
            self._seek(n)
        self._playing = True
        self._play_accum = 0.0
        self._play_timer.start()
        self._sync_transport_ui()

    def stop_play(self) -> None:
        was = self._playing
        self._playing = False
        self._play_timer.stop()
        self._play_accum = 0.0
        if was:
            self._sync_transport_ui()

    @Slot()
    def _on_play_timer(self) -> None:
        self._play_tick(self._play_timer.interval() / 1000.0)

    def _play_tick(self, dt: float) -> None:
        if not self._playing or self._live:
            return
        n = len(self._lines)
        if n <= 0:
            self.stop_play()
            return
        self._play_accum += self._play_speed * _PLAY_LINES_PER_SEC * dt
        step = int(self._play_accum)
        if step <= 0:
            return
        self._play_accum -= step
        pc = self._pc + self._play_dir * step
        if pc >= n:
            self._seek(n)
            self.stop_play()
            return
        if pc < 0:
            self._seek(0)
            self.stop_play()
            return
        self._seek(pc)

    @Slot()
    def _on_speed_changed(self) -> None:
        data = self.cmb_speed.currentData()
        try:
            self._play_speed = float(data)
        except (TypeError, ValueError):
            self._play_speed = 1.0

    @Slot(bool)
    def _on_reverse_toggled(self, checked: bool) -> None:
        self._play_dir = -1 if checked else 1

    @Slot(int)
    def _on_scrub(self, value: int) -> None:
        if self._updating_slider or self._live:
            return
        self.stop_play()
        self._seek(value)

    @Slot()
    def _on_scrub_pressed(self) -> None:
        self.stop_play()
        self._scrubbing = True

    @Slot()
    def _on_scrub_released(self) -> None:
        self._scrubbing = False
        self._refresh()

    def _refresh(self) -> None:
        if self._live:
            pos = self._full.position
            hi = (
                self._full.segments[-1].line_index if self._full.segments else None
            )
        else:
            pos = self._pose_at_pc()
            hi = self._pc - 1 if self._pc > 0 else None
        self.canvas.set_path(
            self._full.segment_list(),
            pos,
            highlight_line=hi,
            upto_pc=None if self._live else self._pc,
            prefix_exact=not self._scrubbing,
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
        self._sync_transport_ui()
        self._set_transport_enabled(bool(self._lines) and not self._live)
