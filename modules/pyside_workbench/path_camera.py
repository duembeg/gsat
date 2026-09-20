"""----------------------------------------------------------------------------
    path_camera.py

    Orbit camera for the Path plotter. Orthographic, CNC axes (Z up).
    Default is Top (looking down −Z, X right, Y up). No Qt.
----------------------------------------------------------------------------"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from modules.virtual_cnc import Point, Segment

# yaw_deg, pitch_deg — pitch 90 = top, 0 = horizon, −90 = bottom
# Isometric corner elevation (camera above/below the XY plane).
ISO_PITCH = math.degrees(math.atan(1.0 / math.sqrt(2.0)))  # ~35.264
_FACE_ORDER = ("top", "bottom", "front", "back", "left", "right")
_FACE_OPP = {
    "top": "bottom",
    "bottom": "top",
    "front": "back",
    "back": "front",
    "left": "right",
    "right": "left",
}

NAMED_VIEWS: dict[str, tuple[float, float]] = {
    "top": (0.0, 90.0),
    "bottom": (0.0, -90.0),
    "front": (0.0, 0.0),
    "back": (180.0, 0.0),
    "right": (-90.0, 0.0),
    "left": (90.0, 0.0),
    # 12 edges
    "top-front": (0.0, 45.0),
    "top-back": (180.0, 45.0),
    "top-right": (-90.0, 45.0),
    "top-left": (90.0, 45.0),
    "bottom-front": (0.0, -45.0),
    "bottom-back": (180.0, -45.0),
    "bottom-right": (-90.0, -45.0),
    "bottom-left": (90.0, -45.0),
    "front-right": (-45.0, 0.0),
    "front-left": (45.0, 0.0),
    "back-right": (-135.0, 0.0),
    "back-left": (135.0, 0.0),
    # 8 corners (trimetric)
    "top-front-right": (-45.0, ISO_PITCH),
    "top-front-left": (45.0, ISO_PITCH),
    "top-back-right": (-135.0, ISO_PITCH),
    "top-back-left": (135.0, ISO_PITCH),
    "bottom-front-right": (-45.0, -ISO_PITCH),
    "bottom-front-left": (45.0, -ISO_PITCH),
    "bottom-back-right": (-135.0, -ISO_PITCH),
    "bottom-back-left": (135.0, -ISO_PITCH),
}


def canonical_cube_region(*faces: str) -> str:
    """Join face names in stable order: top/bottom, front/back, left/right."""
    uniq = []
    for name in faces:
        key = str(name).strip().lower()
        if key in _FACE_ORDER and key not in uniq:
            uniq.append(key)
    uniq.sort(key=_FACE_ORDER.index)
    return "-".join(uniq)


def cube_region(face: str, u: float, v: float, *, t: float = 0.5, u_plus: str, v_plus: str) -> str:
    """Classify a point on a face UV square [-1,1]² into face / edge / corner."""
    face_k = str(face).strip().lower()
    u_hi = abs(u) >= t
    v_hi = abs(v) >= t
    if not u_hi and not v_hi:
        return face_k
    parts = [face_k]
    if u_hi:
        parts.append(u_plus if u > 0 else _FACE_OPP[u_plus])
    if v_hi:
        parts.append(v_plus if v > 0 else _FACE_OPP[v_plus])
    return canonical_cube_region(*parts)


@dataclass(frozen=True)
class CubeFace:
    """One cube face: origin + U/V (length 2), +U/+V neighbor face names."""

    name: str
    origin: tuple[float, float, float]
    u_vec: tuple[float, float, float]
    v_vec: tuple[float, float, float]
    u_plus: str
    v_plus: str

    def point(self, u: float, v: float) -> tuple[float, float, float]:
        """u,v in [0, 1] along the face."""
        return (
            self.origin[0] + u * self.u_vec[0] + v * self.v_vec[0],
            self.origin[1] + u * self.u_vec[1] + v * self.v_vec[1],
            self.origin[2] + u * self.u_vec[2] + v * self.v_vec[2],
        )

    def normal(self) -> tuple[float, float, float]:
        ux, uy, uz = self.u_vec
        vx, vy, vz = self.v_vec
        return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


# Outward faces, Front = −Y (operator). UV in [0,1] maps to ±1 cube.
CUBE_FACES: tuple[CubeFace, ...] = (
    CubeFace("top", (-1.0, -1.0, 1.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0), "right", "back"),
    CubeFace("bottom", (-1.0, 1.0, -1.0), (2.0, 0.0, 0.0), (0.0, -2.0, 0.0), "right", "front"),
    CubeFace("front", (-1.0, -1.0, -1.0), (2.0, 0.0, 0.0), (0.0, 0.0, 2.0), "right", "top"),
    CubeFace("back", (1.0, 1.0, -1.0), (-2.0, 0.0, 0.0), (0.0, 0.0, 2.0), "left", "top"),
    CubeFace("right", (1.0, -1.0, -1.0), (0.0, 2.0, 0.0), (0.0, 0.0, 2.0), "back", "top"),
    CubeFace("left", (-1.0, 1.0, -1.0), (0.0, -2.0, 0.0), (0.0, 0.0, 2.0), "front", "top"),
)

# Chamfered nav-cube mesh: 6 octagon faces, 12 edge quads, 8 corner triangles.
_CHAMFER = 0.32
Vec3 = tuple[float, float, float]


def facet_normal(verts: tuple[Vec3, ...]) -> Vec3:
    ax = verts[1][0] - verts[0][0]
    ay = verts[1][1] - verts[0][1]
    az = verts[1][2] - verts[0][2]
    bx = verts[-1][0] - verts[0][0]
    by = verts[-1][1] - verts[0][1]
    bz = verts[-1][2] - verts[0][2]
    return (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)


def cube_facets(chamfer: float = _CHAMFER) -> tuple[tuple[str, tuple[Vec3, ...]], ...]:
    """26 clickable facets. Keys match NAMED_VIEWS. Front is −Y."""
    c = float(chamfer)
    k = 1.0 - c
    faces: list[tuple[str, tuple[Vec3, ...]]] = [
        (
            "top",
            (
                (-k, -1.0, 1.0), (k, -1.0, 1.0), (1.0, -k, 1.0), (1.0, k, 1.0),
                (k, 1.0, 1.0), (-k, 1.0, 1.0), (-1.0, k, 1.0), (-1.0, -k, 1.0),
            ),
        ),
        (
            "bottom",
            (
                (-k, 1.0, -1.0), (k, 1.0, -1.0), (1.0, k, -1.0), (1.0, -k, -1.0),
                (k, -1.0, -1.0), (-k, -1.0, -1.0), (-1.0, -k, -1.0), (-1.0, k, -1.0),
            ),
        ),
        (
            "front",
            (
                (-k, -1.0, -1.0), (k, -1.0, -1.0), (1.0, -1.0, -k), (1.0, -1.0, k),
                (k, -1.0, 1.0), (-k, -1.0, 1.0), (-1.0, -1.0, k), (-1.0, -1.0, -k),
            ),
        ),
        (
            "back",
            (
                (k, 1.0, -1.0), (-k, 1.0, -1.0), (-1.0, 1.0, -k), (-1.0, 1.0, k),
                (-k, 1.0, 1.0), (k, 1.0, 1.0), (1.0, 1.0, k), (1.0, 1.0, -k),
            ),
        ),
        (
            "right",
            (
                (1.0, -k, -1.0), (1.0, k, -1.0), (1.0, 1.0, -k), (1.0, 1.0, k),
                (1.0, k, 1.0), (1.0, -k, 1.0), (1.0, -1.0, k), (1.0, -1.0, -k),
            ),
        ),
        (
            "left",
            (
                (-1.0, k, -1.0), (-1.0, -k, -1.0), (-1.0, -1.0, -k), (-1.0, -1.0, k),
                (-1.0, -k, 1.0), (-1.0, k, 1.0), (-1.0, 1.0, k), (-1.0, 1.0, -k),
            ),
        ),
    ]
    edges: list[tuple[str, tuple[Vec3, ...]]] = [
        ("top-front", ((-k, -1.0, k), (k, -1.0, k), (k, -k, 1.0), (-k, -k, 1.0))),
        ("top-back", ((k, 1.0, k), (-k, 1.0, k), (-k, k, 1.0), (k, k, 1.0))),
        ("top-right", ((1.0, -k, k), (1.0, k, k), (k, k, 1.0), (k, -k, 1.0))),
        ("top-left", ((-1.0, k, k), (-1.0, -k, k), (-k, -k, 1.0), (-k, k, 1.0))),
        ("bottom-front", ((k, -1.0, -k), (-k, -1.0, -k), (-k, -k, -1.0), (k, -k, -1.0))),
        ("bottom-back", ((-k, 1.0, -k), (k, 1.0, -k), (k, k, -1.0), (-k, k, -1.0))),
        ("bottom-right", ((1.0, k, -k), (1.0, -k, -k), (k, -k, -1.0), (k, k, -1.0))),
        ("bottom-left", ((-1.0, -k, -k), (-1.0, k, -k), (-k, k, -1.0), (-k, -k, -1.0))),
        ("front-right", ((k, -1.0, -k), (1.0, -k, -k), (1.0, -k, k), (k, -1.0, k))),
        ("front-left", ((-1.0, -k, -k), (-k, -1.0, -k), (-k, -1.0, k), (-1.0, -k, k))),
        ("back-right", ((1.0, k, -k), (k, 1.0, -k), (k, 1.0, k), (1.0, k, k))),
        ("back-left", ((-k, 1.0, -k), (-1.0, k, -k), (-1.0, k, k), (-k, 1.0, k))),
    ]
    corners: list[tuple[str, tuple[Vec3, ...]]] = [
        ("top-front-right", ((k, -1.0, 1.0), (1.0, -1.0, k), (1.0, -k, 1.0))),
        ("top-front-left", ((-1.0, -k, 1.0), (-1.0, -1.0, k), (-k, -1.0, 1.0))),
        ("top-back-right", ((1.0, k, 1.0), (1.0, 1.0, k), (k, 1.0, 1.0))),
        ("top-back-left", ((-k, 1.0, 1.0), (-1.0, 1.0, k), (-1.0, k, 1.0))),
        ("bottom-front-right", ((1.0, -k, -1.0), (1.0, -1.0, -k), (k, -1.0, -1.0))),
        ("bottom-front-left", ((-k, -1.0, -1.0), (-1.0, -1.0, -k), (-1.0, -k, -1.0))),
        ("bottom-back-right", ((k, 1.0, -1.0), (1.0, 1.0, -k), (1.0, k, -1.0))),
        ("bottom-back-left", ((-1.0, k, -1.0), (-1.0, 1.0, -k), (-k, 1.0, -1.0))),
    ]
    return tuple(faces + edges + corners)


@dataclass(frozen=True)
class Camera:
    """Turntable yaw around Z, pitch from top-down (90) to horizon (0)."""

    yaw_deg: float = 0.0
    pitch_deg: float = 90.0

    @classmethod
    def top(cls) -> Camera:
        return cls(*NAMED_VIEWS["top"])

    @classmethod
    def front(cls) -> Camera:
        return cls(*NAMED_VIEWS["front"])

    @classmethod
    def right(cls) -> Camera:
        return cls(*NAMED_VIEWS["right"])

    def snap(self, name: str) -> Camera:
        key = str(name).strip().lower()
        if key not in NAMED_VIEWS:
            return self
        yaw, pitch = NAMED_VIEWS[key]
        return Camera(yaw_deg=yaw, pitch_deg=pitch)

    def orbit(self, d_yaw_deg: float, d_pitch_deg: float) -> Camera:
        pitch = max(-89.0, min(90.0, self.pitch_deg + d_pitch_deg))
        yaw = (self.yaw_deg + d_yaw_deg + 180.0) % 360.0 - 180.0
        return Camera(yaw_deg=yaw, pitch_deg=pitch)

    def to_view(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """World CNC → view (x_right, y_up, depth). Camera looks toward −depth."""
        yaw = math.radians(self.yaw_deg)
        cy, sy = math.cos(yaw), math.sin(yaw)
        x1 = x * cy - y * sy
        y1 = x * sy + y * cy
        z1 = z
        a = math.radians(self.pitch_deg - 90.0)
        ca, sa = math.cos(a), math.sin(a)
        y2 = y1 * ca - z1 * sa
        z2 = y1 * sa + z1 * ca
        return x1, y2, z2

    def from_view(self, vx: float, vy: float, vz: float = 0.0) -> tuple[float, float, float]:
        """View (x_right, y_up, depth) → world CNC. Inverse of to_view."""
        a = math.radians(self.pitch_deg - 90.0)
        ca, sa = math.cos(a), math.sin(a)
        y1 = vy * ca + vz * sa
        z1 = -vy * sa + vz * ca
        x1 = vx
        yaw = math.radians(self.yaw_deg)
        cy, sy = math.cos(yaw), math.sin(yaw)
        x = x1 * cy + y1 * sy
        y = -x1 * sy + y1 * cy
        return x, y, z1


def view_bounds(
    segments: Sequence[Segment], position: Point, camera: Camera
) -> tuple[float, float, float, float]:
    """AABB of path + marker in view-space XY (y is up)."""
    pts = [position]
    for seg in segments:
        pts.append(seg.start)
        pts.append(seg.end)
    xs: list[float] = []
    ys: list[float] = []
    for p in pts:
        vx, vy, _ = camera.to_view(p.x, p.y, p.z)
        xs.append(vx)
        ys.append(vy)
    return min(xs), min(ys), max(xs), max(ys)
