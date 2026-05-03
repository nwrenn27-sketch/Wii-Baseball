from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pygame

from game.constants import PLATE_X, PLATE_Y
from game.field import _field_to_screen

Point = Tuple[int, int]


def _leg_screen(leg: int) -> Point:
    """leg 0 = home plate, 1 = 1B, 2 = 2B, 3 = 3B."""
    if leg == 1:
        return _field_to_screen( 0.55, 0.55)
    if leg == 2:
        return _field_to_screen( 0.00, 0.22)
    if leg == 3:
        return _field_to_screen(-0.55, 0.55)
    return (PLATE_X, PLATE_Y - 8)   # home (leg 0)


def _diamond_leg_indices(start_leg: int, bases: int) -> List[int]:
    path = [start_leg]
    cur  = start_leg
    for _ in range(bases):
        cur = (cur + 1) % 4
        path.append(cur)
        if cur == 0:
            break
    return path


def build_runner_path_pixels(start_leg: int, bases: int) -> List[Point]:
    legs = _diamond_leg_indices(start_leg, bases)
    pts  = [_leg_screen(L) for L in legs]
    out: List[Point] = [pts[0]]
    for p in pts[1:]:
        if p != out[-1]:
            out.append(p)
    if len(out) < 2:
        out.append((out[0][0] + 2, out[0][1]))
    # tag whether path ends at home (for vanish effect)
    ends_at_home = (legs[-1] == 0)
    return out, ends_at_home


def _polyline_position(pts: List[Point], t: float) -> Tuple[int, int, Optional[Point]]:
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
    acc  = 0.0
    for d, a, b in segs:
        if acc + d >= dist:
            u  = (dist - acc) / d if d > 1e-6 else 1.0
            x  = int(a[0] + (b[0] - a[0]) * u)
            y  = int(a[1] + (b[1] - a[1]) * u)
            return x, y, b
        acc += d
    return pts[-1][0], pts[-1][1], None


def _draw_runner_figure(
    surf: pygame.Surface, x: int, y: int,
    nxt: Optional[Point], wobble: float,
    scale: float = 1.0, alpha: int = 255,
) -> None:
    if alpha <= 0:
        return
    if nxt:
        dx, dy = nxt[0] - x, nxt[1] - y
        n = math.hypot(dx, dy)
        dx, dy = (dx / n, dy / n) if n > 1e-6 else (0.0, -1.0)
    else:
        dx, dy = 0.0, -1.0

    sc  = max(0.6, scale)
    ang = math.atan2(dy, dx)
    c, s = math.cos(ang), math.sin(ang)

    def rot(px: float, py: float) -> Tuple[int, int]:
        return (int(x + (px * sc) * c - (py * sc) * s),
                int(y + (px * sc) * s + (py * sc) * c))

    shirt = ( 55, 110, 210)
    pants = ( 35,  38,  48)
    skin  = (230, 195, 160)

    if alpha < 255:
        tmp = pygame.Surface((int(40 * sc), int(40 * sc)), pygame.SRCALPHA)
        ox, oy = int(20 * sc), int(20 * sc)

        def rot_local(px: float, py: float) -> Tuple[int, int]:
            return (int(ox + (px * sc) * c - (py * sc) * s),
                    int(oy + (px * sc) * s + (py * sc) * c))

        rh = max(3, int(5 * sc))
        hx, hy = rot_local(0, -10)
        pygame.draw.circle(tmp, (*skin, alpha), (hx, hy), rh)
        p1, p2 = rot_local(-3, -4), rot_local(3, -4)
        p3, p4 = rot_local(3,  5), rot_local(-3, 5)
        pygame.draw.polygon(tmp, (*shirt, alpha), [p1, p2, p3, p4])
        stride = 2.5 * sc * math.sin(wobble * 12.0)
        la = rot_local(-2 + stride * 0.3, 11)
        lb = rot_local( 2 - stride * 0.3, 11)
        lw = max(2, int(3 * sc))
        pygame.draw.line(tmp, (*pants, alpha), rot_local(0, 5), la, lw)
        pygame.draw.line(tmp, (*pants, alpha), rot_local(0, 5), lb, lw)
        surface.blit(tmp, (x - ox, y - oy))
        return

    rh = max(3, int(5 * sc))
    hx, hy = rot(0, -10)
    pygame.draw.circle(surf, skin, (hx, hy), rh)
    pygame.draw.circle(surf, (40, 30, 25), (hx, hy), rh, max(1, int(sc)))

    p1, p2 = rot(-3, -4), rot(3, -4)
    p3, p4 = rot( 3,  5), rot(-3, 5)
    pygame.draw.polygon(surf, shirt, [p1, p2, p3, p4])
    pygame.draw.polygon(surf, (20, 40, 80), [p1, p2, p3, p4], max(1, int(sc)))

    lw = max(2, int(3 * sc))
    stride = 2.5 * sc * math.sin(wobble * 12.0)
    la = rot(-2 + stride * 0.3, 11)
    lb = rot( 2 - stride * 0.3, 11)
    pygame.draw.line(surf, pants, rot(0, 5), la, lw)
    pygame.draw.line(surf, pants, rot(0, 5), lb, lw)


def draw_occupied_base_runners(surface: pygame.Surface, runners: list) -> None:
    if len(runners) < 3:
        return
    sc = 1.45
    if runners[0]:
        bx, by = _leg_screen(1)
        _draw_runner_figure(surface, bx + 4, by, _leg_screen(2), 0.0, sc)
    if runners[1]:
        bx, by = _leg_screen(2)
        _draw_runner_figure(surface, bx, by - 2, _leg_screen(3), 0.0, sc)
    if runners[2]:
        bx, by = _leg_screen(3)
        _draw_runner_figure(surface, bx - 4, by, _leg_screen(0), 0.0, sc)


class RunnerAnimator:
    DURATION_MS = 2200.0

    def __init__(self) -> None:
        # each track: (pts, ends_at_home)
        self._tracks: List[Tuple[List[Point], bool]] = []
        self._elapsed_ms = 0.0
        self.active = False

    def start(self, waypoint_lists) -> None:
        self._tracks = [(pts, ends) for pts, ends in waypoint_lists if len(pts) >= 2]
        self._elapsed_ms = 0.0
        self.active = len(self._tracks) > 0

    def update(self, dt_ms: float) -> None:
        if not self.active:
            return
        self._elapsed_ms += float(dt_ms)
        if self._elapsed_ms >= self.DURATION_MS:
            self.active   = False
            self._tracks  = []

    def reset(self) -> None:
        self._tracks     = []
        self._elapsed_ms = 0.0
        self.active      = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self._tracks:
            return
        t  = min(1.0, self._elapsed_ms / self.DURATION_MS)
        te = 1.0 - (1.0 - t) ** 1.65   # ease-out

        for pts, ends_at_home in self._tracks:
            x, y, nxt = _polyline_position(pts, te)

            # Fade out in the last 20% if the runner scores (ends at home)
            if ends_at_home and t > 0.80:
                fade = 1.0 - (t - 0.80) / 0.20
                alpha = int(255 * max(0.0, fade))
            else:
                alpha = 255

            _draw_runner_figure(surface, x, y, nxt,
                                self._elapsed_ms / 120.0, 1.38, alpha)
