"""----------------------------------------------------------------------------
    virtual_cnc.py

    Commanded-motion path interpreter: G0/G1/G2/G3 → polyline. Not a
    material-removal sim, not a MachIf, no Qt.

    Arcs (G17 XY): IJK offsets (incremental from start) or R. Tessellated to
    short chords. Other planes stay skipped.
----------------------------------------------------------------------------"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal, Sequence

MotionKind = Literal["rapid", "feed", "arc", "jog"]
Plane = Literal["xy", "xz", "yz"]

_COMMENTS = (re.compile(r"\(.*\)"), re.compile(r";.*"))
# Letter + number, optional space (G0X10 and X 10). Requires at least one digit.
_WORD = re.compile(r"([A-Za-z])\s*([-+]?(?:\d+\.?\d*|\.\d+))")

_ARC_STEP_RAD = math.radians(5.0)
_ARC_R_TOL = 1e-4


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Segment:
    start: Point
    end: Point
    kind: MotionKind
    line_index: int


def _strip_comments(line: str) -> str:
    for regex in _COMMENTS:
        line = regex.sub("", line)
    return line


def _g_is(value: float, code: int) -> bool:
    return value == float(code)


def _sweep(a0: float, a1: float, clockwise: bool) -> float:
    """Signed angle from a0 to a1. Full circle if start==end (±2π)."""
    da = a1 - a0
    if clockwise:
        while da > 1e-12:
            da -= 2.0 * math.pi
        if da > -1e-12:
            da = -2.0 * math.pi
    else:
        while da < -1e-12:
            da += 2.0 * math.pi
        if da < 1e-12:
            da = 2.0 * math.pi
    return da


def _center_from_r(
    sx: float, sy: float, ex: float, ey: float, r: float, clockwise: bool
) -> tuple[float, float] | None:
    dx, dy = ex - sx, ey - sy
    chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return None
    ar = abs(r)
    half = chord / 2.0
    if half > ar + 1e-9:
        return None
    h = math.sqrt(max(ar * ar - half * half, 0.0))
    mx, my = (sx + ex) / 2.0, (sy + ey) / 2.0
    ux, uy = -dy / chord, dx / chord
    candidates = ((mx + h * ux, my + h * uy), (mx - h * ux, my - h * uy))
    want_major = r < 0
    best: tuple[float, float] | None = None
    for cx, cy in candidates:
        a0 = math.atan2(sy - cy, sx - cx)
        a1 = math.atan2(ey - cy, ex - cx)
        da = _sweep(a0, a1, clockwise)
        major = abs(da) > math.pi + 1e-9
        if major == want_major:
            best = (cx, cy)
            break
    return best


def _tessellate_xy(
    start: Point,
    end: Point,
    cx: float,
    cy: float,
    clockwise: bool,
) -> list[Point]:
    r0 = math.hypot(start.x - cx, start.y - cy)
    r1 = math.hypot(end.x - cx, end.y - cy)
    if r0 < 1e-12:
        return []
    if abs(r0 - r1) > _ARC_R_TOL * max(1.0, r0, r1):
        return []
    a0 = math.atan2(start.y - cy, start.x - cx)
    a1 = math.atan2(end.y - cy, end.x - cx)
    same = (
        abs(start.x - end.x) < 1e-12
        and abs(start.y - end.y) < 1e-12
    )
    if same:
        da = -2.0 * math.pi if clockwise else 2.0 * math.pi
    else:
        da = _sweep(a0, a1, clockwise)
    n = max(1, int(math.ceil(abs(da) / _ARC_STEP_RAD)))
    pts: list[Point] = []
    for i in range(1, n + 1):
        t = i / n
        if i == n:
            pts.append(end)
            break
        ang = a0 + da * t
        pts.append(
            Point(
                cx + r0 * math.cos(ang),
                cy + r0 * math.sin(ang),
                start.z + (end.z - start.z) * t,
            )
        )
    return pts


class VirtualCnc:
    """Apply G0/G1/G2/G3 lines to a polyline. Block semantics (modes then move)."""

    def __init__(
        self,
        *,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        absolute: bool = True,
        motion: MotionKind = "rapid",
    ) -> None:
        self._init_x = float(x)
        self._init_y = float(y)
        self._init_z = float(z)
        self._init_absolute = bool(absolute)
        self._init_motion: MotionKind = motion
        self._position = Point(self._init_x, self._init_y, self._init_z)
        self._absolute = self._init_absolute
        self._motion: MotionKind = self._init_motion
        self._arc_cw = True
        self._plane: Plane = "xy"
        self._segments: list[Segment] = []
        self._skipped: list[str] = []

    @property
    def position(self) -> Point:
        return self._position

    @property
    def absolute(self) -> bool:
        return self._absolute

    @property
    def motion_kind(self) -> MotionKind:
        return self._motion

    @property
    def segments(self) -> tuple[Segment, ...]:
        return tuple(self._segments)

    def segment_list(self) -> list[Segment]:
        """Live list (no copy) for the Path canvas cache."""
        return self._segments

    @property
    def skipped(self) -> tuple[str, ...]:
        return tuple(self._skipped)

    def reset(self) -> None:
        self._position = Point(self._init_x, self._init_y, self._init_z)
        self._absolute = self._init_absolute
        self._motion = self._init_motion
        self._arc_cw = True
        self._plane = "xy"
        self._segments.clear()
        self._skipped.clear()

    def _target(self, axes: dict[str, float]) -> Point:
        start = self._position
        nx, ny, nz = start.x, start.y, start.z
        if self._absolute:
            if "X" in axes:
                nx = axes["X"]
            if "Y" in axes:
                ny = axes["Y"]
            if "Z" in axes:
                nz = axes["Z"]
        else:
            if "X" in axes:
                nx += axes["X"]
            if "Y" in axes:
                ny += axes["Y"]
            if "Z" in axes:
                nz += axes["Z"]
        return Point(nx, ny, nz)

    def _append_linear(
        self,
        start: Point,
        end: Point,
        line_index: int,
        *,
        kind: MotionKind | None = None,
    ) -> Segment | None:
        self._position = end
        if end == start:
            return None
        seg = Segment(
            start, end, kind if kind is not None else self._motion, line_index
        )
        self._segments.append(seg)
        return seg

    def _append_arc(
        self,
        start: Point,
        end: Point,
        offsets: dict[str, float],
        r_word: float | None,
        line_index: int,
        code: str,
    ) -> Segment | None:
        if self._plane != "xy":
            self._skipped.append(code)
            return None
        cx: float | None = None
        cy: float | None = None
        if r_word is not None:
            c = _center_from_r(
                start.x, start.y, end.x, end.y, r_word, self._arc_cw
            )
            if c is None:
                self._skipped.append(code)
                return None
            cx, cy = c
        elif "I" in offsets or "J" in offsets:
            cx = start.x + offsets.get("I", 0.0)
            cy = start.y + offsets.get("J", 0.0)
        else:
            self._skipped.append(code)
            return None
        pts = _tessellate_xy(start, end, cx, cy, self._arc_cw)
        if not pts:
            self._skipped.append(code)
            return None
        last: Segment | None = None
        prev = start
        for p in pts:
            if p == prev:
                continue
            last = Segment(prev, p, "arc", line_index)
            self._segments.append(last)
            prev = p
        self._position = end
        return last

    def apply_line(
        self, line: str, *, line_index: int = -1, jog: bool = False
    ) -> Segment | None:
        """Parse one G-code block. Returns last new segment if XYZ moved.

        jog=True: emit kind "jog" (pad G91 G01 or $J=). Does not change modal G0/G1.
        """
        payload = _strip_comments(line).strip()
        if not payload:
            return None

        words = _WORD.findall(payload)
        if not words:
            return None

        axes: dict[str, float] = {}
        offsets: dict[str, float] = {}
        r_word: float | None = None
        new_absolute: bool | None = None
        new_motion: MotionKind | None = None
        new_arc_cw: bool | None = None
        new_plane: Plane | None = None

        for letter, number in words:
            letter = letter.upper()
            try:
                value = float(number)
            except ValueError:
                continue
            if letter == "G":
                if _g_is(value, 0):
                    new_motion = "rapid"
                elif _g_is(value, 1):
                    new_motion = "feed"
                elif _g_is(value, 2):
                    new_motion = "arc"
                    new_arc_cw = True
                elif _g_is(value, 3):
                    new_motion = "arc"
                    new_arc_cw = False
                elif _g_is(value, 90):
                    new_absolute = True
                elif _g_is(value, 91):
                    new_absolute = False
                elif _g_is(value, 17):
                    new_plane = "xy"
                elif _g_is(value, 18):
                    new_plane = "xz"
                elif _g_is(value, 19):
                    new_plane = "yz"
            elif letter in "XYZ":
                axes[letter] = value
            elif letter in "IJK":
                offsets[letter] = value
            elif letter == "R":
                r_word = value

        if new_absolute is not None:
            self._absolute = new_absolute
        if new_plane is not None:
            self._plane = new_plane
        if jog:
            if not axes:
                return None
            start = self._position
            end = self._target(axes)
            return self._append_linear(start, end, line_index, kind="jog")
        if new_motion is not None:
            self._motion = new_motion
            if new_arc_cw is not None:
                self._arc_cw = new_arc_cw

        if self._motion != "arc" and not axes:
            return None

        start = self._position
        end = self._target(axes) if axes else start

        if self._motion == "arc":
            has_center = bool(offsets) or r_word is not None
            if not axes and not has_center:
                return None  # G2/G3 mode only
            code = "G2" if self._arc_cw else "G3"
            return self._append_arc(start, end, offsets, r_word, line_index, code)

        if not axes:
            return None
        return self._append_linear(start, end, line_index)

    def apply_lines(self, lines: Sequence[str] | str) -> tuple[Segment, ...]:
        seq = lines.splitlines() if isinstance(lines, str) else lines
        produced: list[Segment] = []
        for i, line in enumerate(seq):
            before = len(self._segments)
            self.apply_line(line, line_index=i)
            produced.extend(self._segments[before:])
        return tuple(produced)

    def bounds(self) -> tuple[Point, Point] | None:
        if not self._segments:
            return None
        xs: list[float] = []
        ys: list[float] = []
        zs: list[float] = []
        for seg in self._segments:
            for p in (seg.start, seg.end):
                xs.append(p.x)
                ys.append(p.y)
                zs.append(p.z)
        return (
            Point(min(xs), min(ys), min(zs)),
            Point(max(xs), max(ys), max(zs)),
        )
