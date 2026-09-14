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
NAMED_VIEWS: dict[str, tuple[float, float]] = {
    "top": (0.0, 90.0),
    "front": (0.0, 0.0),
    "right": (-90.0, 0.0),
    "left": (90.0, 0.0),
    "back": (180.0, 0.0),
    "bottom": (0.0, -90.0),
}


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
