"""
Base-runner animation after hits (single / double / triple / home run).

Each runner follows screen-space waypoints along the diamond (home → 1B → 2B
→ 3B → home). `RunnerAnimator` is driven from the main loop during RESULT.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pygame

from game.constants import PLATE_X, PLATE_Y
from game.field import _field_to_screen

Point = Tuple[int, int]


def _leg_screen(leg: int) -> Point:
    """leg 0 = home plate, 1 = 1B, 2 = 2B, 3 = 3B."""
    if leg == 0:
        return (PLATE_X, PLATE_Y - 14)
    if leg == 1:
        return _field_to_screen(0.55, 0.55)
    if leg == 2:
        return _field_to_screen(0.0, 0.22)
    if leg == 3:
        return _field_to_screen(-0.55, 0.55)
    return (PLATE_X, PLATE_Y - 14)


def _diamond_leg_indices(start_leg: int, bases: int) -> List[int]:
    """Return [start, ..., end] leg indices walking forward up to `bases` bags.

    Runners who score stop at home (leg 0); they do not wrap to first base.
    """
    path = [start_leg]
    cur = start_leg
    for _ in range(bases):
        cur = (cur + 1) % 4
        path.append(cur)
        if cur == 0:
            break
    return path


def build_runner_path_pixels(start_leg: int, bases: int) -> List[Point]:
    """Screen polyline for one runner from start_leg advancing `bases` bases."""
    legs = _diamond_leg_indices(start_leg, bases)
    pts = [_leg_screen(L) for L in legs]
    # Remove accidental duplicate consecutive coords
    out: List[Point] = [pts[0]]
    for p in pts[1:]:
        if p != out[-1]:
            out.append(p)
    if len(out) < 2:
        out.append((out[0][0] + 2, out[0][1]))
    return out


def _polyline_position(pts: List[Point], t: float) -> Tuple[int, int, Optional[Point]]:
    """t in [0,1] along total arc length; returns (x,y, next_point_for_facing)."""
    if len(pts) < 2:
        return pts[0][0], pts[0][1], None
    segs: List[Tuple[float, Point, Point]] = []
    total = 0.0
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        d = math.hypot(x1 - x0, y1 - y0)
        segs.append((d, pts[i], pts[i + 1]))
        total += d
    if total <= 0.01:
        return pts[0][0], pts[0][1], pts[1] if len(pts) > 1 else None
    dist = max(0.0, min(1.0, t)) * total
    acc = 0.0
    for d, a, b in segs:
        if acc + d >= dist:
            u = (dist - acc) / d if d > 1e-6 else 1.0
            x = int(a[0] + (b[0] - a[0]) * u)
            y = int(a[1] + (b[1] - a[1]) * u)
            return x, y, b
        acc += d
    return pts[-1][0], pts[-1][1], None


def _draw_runner_figure(
    surf: pygame.Surface,
    x: int,
    y: int,
    nxt: Optional[Point],
    wobble: float,
    scale: float = 1.0,
) -> None:
    """Uniform figure facing toward nxt; scale > 1 for base runners / replays."""
    if nxt:
        dx, dy = nxt[0] - x, nxt[1] - y
        n = math.hypot(dx, dy)
        if n > 1e-6:
            dx, dy = dx / n, dy / n
        else:
            dx, dy = 0.0, -1.0
    else:
        dx, dy = 0.0, -1.0

    sc = max(0.6, scale)
    shirt = (55, 110, 210)
    pants = (35, 38, 48)
    skin = (230, 195, 160)

    ang = math.atan2(dy, dx)
    c, s = math.cos(ang), math.sin(ang)

    def rot(px: float, py: float) -> Tuple[int, int]:
        return (int(x + (px * sc) * c - (py * sc) * s), int(y + (px * sc) * s + (py * sc) * c))

    rh = max(4, int(6 * sc))
    hx, hy = rot(0, -10)
    pygame.draw.circle(surf, skin, (hx, hy), rh)
    pygame.draw.circle(surf, (40, 30, 25), (hx, hy), rh, max(1, int(sc)))

    p1, p2 = rot(-4, -4), rot(4, -4)
    p3, p4 = rot(4, 6), rot(-4, 6)
    pygame.draw.polygon(surf, shirt, [p1, p2, p3, p4])
    pygame.draw.polygon(surf, (20, 40, 80), [p1, p2, p3, p4], max(1, int(sc)))

    lw = max(3, int(4 * sc))
    stride = 3 * sc * math.sin(wobble * 12.0)
    la = rot(-3 + stride * 0.3, 12)
    lb = rot(3 - stride * 0.3, 12)
    pygame.draw.line(surf, pants, rot(0, 6), la, lw)
    pygame.draw.line(surf, pants, rot(0, 6), lb, lw)


def draw_occupied_base_runners(surface: pygame.Surface, runners: list) -> None:
    """Draw larger runners standing on each occupied base (1B / 2B / 3B)."""
    if len(runners) < 3:
        return
    sc = 1.55
    # Catcher POV: "next base" screen vectors tilt badly on 1B/2B. Stand upright
    # (facing screen-up / upfield) like the batter silhouette.
    if runners[0]:
        bx, by = _leg_screen(1)
        _draw_runner_figure(surface, bx + 4, by, None, 0.0, sc)
    if runners[1]:
        bx, by = _leg_screen(2)
        _draw_runner_figure(surface, bx, by - 2, None, 0.0, sc)
    if runners[2]:
        bx, by = _leg_screen(3)
        _draw_runner_figure(surface, bx - 4, by, None, 0.0, sc)


class RunnerAnimator:
    """Plays one batch of runner paths, then goes idle."""

    DURATION_MS = 2400.0

    def __init__(self) -> None:
        self._tracks: List[List[Point]] = []
        self._elapsed_ms = 0.0
        self.active = False

    def start(self, waypoint_lists: List[List[Point]]) -> None:
        self._tracks = [p for p in waypoint_lists if len(p) >= 2]
        self._elapsed_ms = 0.0
        self.active = len(self._tracks) > 0

    def update(self, dt_ms: float) -> None:
        if not self.active:
            return
        self._elapsed_ms += float(dt_ms)
        if self._elapsed_ms >= self.DURATION_MS:
            self.active = False
            self._tracks = []

    def reset(self) -> None:
        self._tracks = []
        self._elapsed_ms = 0.0
        self.active = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self._tracks:
            return
        t = min(1.0, self._elapsed_ms / self.DURATION_MS)
        # Ease-out so runners slow into the bag
        te = 1.0 - (1.0 - t) ** 1.65
        anim_scale = 1.42
        for pts in self._tracks:
            x, y, nxt = _polyline_position(pts, te)
            _draw_runner_figure(
                surface, x, y, nxt, self._elapsed_ms / 120.0, anim_scale,
            )
