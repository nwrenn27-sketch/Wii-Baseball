"""
Catcher POV field renderer.

The camera sits behind home plate looking up the center line. The ball grows
and rushes the plate (see baseball.py easing + trail). The field is built as
layered shapes: sky, stadium deck, outfield grass wings, clay runway, chalk,
mound, and plate.

Ball and trail are drawn by draw_ball() after draw().
"""

import math
import random
import pygame

from game.constants import (
    SCREEN_W, SCREEN_H,
    HORIZON_Y, PLATE_Y, PLATE_X,
    FIELD_WIDTH_NEAR, FIELD_WIDTH_FAR,
    SKY_TOP, SKY_BOT, CLOUD_WHITE,
    FIELD_GREEN, FIELD_DARK,
    MOUND_TAN, BASELINE_WHT,
    BASE_WHITE,
    WHITE, BLACK,
    TRACK_TAN_LIGHT, TRACK_TAN_MID, TRACK_TAN_DARK,
    GRASS_HI, GRASS_MID, GRASS_LO,
    STADIUM_DEEP, STADIUM_BAND, STADIUM_RAIL,
    CHALK_GLOW,
)

_HALF_NEAR = FIELD_WIDTH_NEAR // 2
_HALF_FAR = FIELD_WIDTH_FAR // 2

# Clay runway half-width at plate vs near horizon (screen px)
_RUNWAY_HALF_PLATE = 112
_RUNWAY_HALF_FAR = 14
_Y_RUNWAY_TOP = HORIZON_Y + 42


def _field_to_screen(x_field: float, z_norm: float) -> tuple[int, int]:
    """z_norm 0 = horizon, 1 = home plate."""
    py = int(HORIZON_Y + (PLATE_Y - HORIZON_Y) * z_norm)
    half_w = _HALF_FAR + (_HALF_NEAR - _HALF_FAR) * z_norm
    px = int(PLATE_X + x_field * half_w * 3.5)
    return px, py


class Cloud:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.speed = 0.09

    def update(self):
        self.x += self.speed
        if self.x > SCREEN_W + self.w:
            self.x = -self.w

    def draw(self, surface):
        for ox, oy, r in [
            (0, 0, self.h),
            (self.w * 0.25, -self.h * 0.3, self.h * 0.7),
            (-self.w * 0.25, -self.h * 0.2, self.h * 0.75),
            (self.w * 0.4, self.h * 0.1, self.h * 0.55),
        ]:
            pygame.draw.ellipse(
                surface, CLOUD_WHITE,
                (int(self.x + ox - r), int(self.y + oy - r * 0.6),
                 int(r * 2), int(r * 1.2)),
            )


class FieldRenderer:
    def __init__(self):
        rng = random.Random(42)
        self._clouds = [
            Cloud(120, 48, 200, 36),
            Cloud(520, 32, 260, 40),
            Cloud(980, 55, 180, 34),
        ]
        self._foul_left_far = _field_to_screen(-1.45, 0.03)
        self._foul_right_far = _field_to_screen(1.45, 0.03)
        self._foul_left_near = (PLATE_X - _HALF_NEAR, PLATE_Y)
        self._foul_right_near = (PLATE_X + _HALF_NEAR, PLATE_Y)
        self._outfield_pts = self._make_outfield_arc()
        self._sky_surf = self._build_sky()
        self._seat_dots = [
            (rng.randint(40, SCREEN_W - 40), rng.randint(8, HORIZON_Y - 70))
            for _ in range(160)
        ]
        self._scuff_pts = []
        for _ in range(90):
            self._scuff_pts.append(
                (
                    rng.randint(
                        int(PLATE_X - _RUNWAY_HALF_PLATE + 8),
                        int(PLATE_X + _RUNWAY_HALF_PLATE - 8),
                    ),
                    rng.randint(int(_Y_RUNWAY_TOP + 6), int(PLATE_Y - 10)),
                )
            )

    def update(self):
        for c in self._clouds:
            c.update()

    def draw(self, surface: pygame.Surface):
        surface.blit(self._sky_surf, (0, 0))
        for c in self._clouds:
            c.draw(surface)

        self._draw_stadium(surface)
        self._draw_outfield_grass(surface)
        self._draw_warning_arc(surface)
        self._draw_runway(surface)
        self._draw_grass_stripes(surface)
        self._draw_foul_lines(surface)
        self._draw_base_paths(surface)
        self._draw_bases(surface)
        self._draw_mound(surface)
        self._draw_home_plate(surface)
        self._draw_batter_from_behind(surface)
        self._draw_catcher_vignette(surface)

    def draw_ball(self, surface: pygame.Surface, ball):
        from game.constants import BALL_WHITE, BALL_SEAM

        if not ball.active and ball.progress < 1.0:
            return

        sx, sy = ball.get_screen_pos()
        r = ball.get_radius()

        # Motion trail (older samples = smaller / more transparent)
        trail = list(ball._trail)
        if len(trail) >= 2:
            for i, (tx, ty, tr) in enumerate(trail):
                if (tx, ty) == (sx, sy) and i == len(trail) - 1:
                    continue
                age = (i + 1) / max(len(trail), 1)
                alpha = int(55 * age)
                rr = max(2, int(tr * (0.35 + 0.45 * age)))
                if alpha < 8:
                    continue
                ts = pygame.Surface((rr * 2 + 2, rr * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(ts, (255, 255, 250, alpha), (rr + 1, rr + 1), rr)
                surface.blit(ts, (tx - rr - 1, ty - rr - 1))

        shx, shy = ball.get_shadow_pos()
        shadow_r = max(2, int(r * (0.42 + 0.2 * (1.0 - ball.progress))))
        shadow_surf = pygame.Surface((shadow_r * 2 + 4, shadow_r + 4), pygame.SRCALPHA)
        pygame.draw.ellipse(
            shadow_surf, (25, 25, 30, min(110, 40 + int(70 * (1.0 - ball.progress)))),
            (0, 0, shadow_r * 2, shadow_r),
        )
        surface.blit(shadow_surf, (shx - shadow_r, shy - shadow_r // 2))

        # Specular highlight + core
        if r >= 5:
            glow = pygame.Surface((r * 6, r * 6), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 255, 255, 35), (r * 3, r * 3), int(r * 2.2))
            surface.blit(glow, (sx - r * 3, sy - r * 3))

        pygame.draw.circle(surface, (235, 232, 220), (sx, sy), r)
        pygame.draw.circle(surface, BALL_WHITE, (sx - max(1, r // 8), sy - max(1, r // 8)), max(2, r - 2))

        if r >= 6:
            pygame.draw.arc(
                surface, BALL_SEAM,
                (sx - r + 2, sy - r, r, r * 2),
                math.pi * 0.2, math.pi * 0.8, max(1, r // 5),
            )
            pygame.draw.arc(
                surface, BALL_SEAM,
                (sx + 2, sy - r, r, r * 2),
                math.pi * 1.2, math.pi * 1.8, max(1, r // 5),
            )

        pygame.draw.circle(surface, (160, 155, 145), (sx, sy), r, 1)

    def draw_strike_zone(self, surface: pygame.Surface, alpha: int = 120):
        from game.constants import STRIKE_ZONE_W, STRIKE_ZONE_H

        tl = _field_to_screen(-STRIKE_ZONE_W, 1.0)
        br = _field_to_screen(STRIKE_ZONE_W, 1.0)
        zone_w = max(24, br[0] - tl[0])
        zone_h = int(STRIKE_ZONE_H * (PLATE_Y - HORIZON_Y) * 1.05)
        zone_rect = pygame.Rect(tl[0], tl[1] - zone_h, zone_w, zone_h)

        zone_surf = pygame.Surface((zone_w, zone_h), pygame.SRCALPHA)
        for y in range(zone_h):
            k = y / max(zone_h, 1)
            a = int((alpha // 4) * (0.35 + 0.65 * k))
            pygame.draw.line(zone_surf, (255, 255, 255, a), (0, y), (zone_w, y))
        pygame.draw.rect(zone_surf, (255, 255, 255, min(200, alpha + 40)), zone_surf.get_rect(), 2)
        surface.blit(zone_surf, zone_rect.topleft)

    # ------------------------------------------------------------------
    # Layers
    # ------------------------------------------------------------------

    def _build_sky(self) -> pygame.Surface:
        surf = pygame.Surface((SCREEN_W, HORIZON_Y + 32))
        h = HORIZON_Y + 32
        for y in range(h):
            t = y / max(h, 1)
            t2 = t * t
            r = int(SKY_TOP[0] * (1 - t) + SKY_BOT[0] * t + 18 * t2)
            g = int(SKY_TOP[1] * (1 - t) + SKY_BOT[1] * t + 8 * t2)
            b = int(SKY_TOP[2] * (1 - t) + SKY_BOT[2] * t)
            pygame.draw.line(surf, (min(255, r), min(255, g), min(255, b)), (0, y), (SCREEN_W, y))
        # Horizon haze band
        band = pygame.Surface((SCREEN_W, 28), pygame.SRCALPHA)
        for y in range(28):
            a = int(55 * (y / 28.0))
            pygame.draw.line(band, (240, 248, 255, a), (0, y), (SCREEN_W, y))
        surf.blit(band, (0, h - 36))
        return surf

    def _draw_stadium(self, surface):
        # Upper bowl
        pygame.draw.rect(surface, STADIUM_DEEP, (0, 0, SCREEN_W, HORIZON_Y - 48))
        for i, y0 in enumerate(range(12, HORIZON_Y - 52, 14)):
            t = i / max(1, (HORIZON_Y - 52) // 14)
            col = (
                int(STADIUM_DEEP[0] * (1 - t) + STADIUM_BAND[0] * t),
                int(STADIUM_DEEP[1] * (1 - t) + STADIUM_BAND[1] * t),
                int(STADIUM_DEEP[2] * (1 - t) + STADIUM_BAND[2] * t),
            )
            pygame.draw.line(surface, col, (0, y0), (SCREEN_W, y0), 3)

        deck_h = 52
        pygame.draw.rect(
            surface, STADIUM_BAND,
            pygame.Rect(0, HORIZON_Y - deck_h - 8, SCREEN_W, deck_h),
        )
        pygame.draw.rect(surface, STADIUM_RAIL, (0, HORIZON_Y - 14, SCREEN_W, 6))

        for (dx, dy) in self._seat_dots:
            pygame.draw.circle(surface, (min(255, 180 + (dx % 40)), 200, 220), (dx, dy), 1)

    def _draw_outfield_grass(self, surface):
        pygame.draw.polygon(surface, FIELD_GREEN, self._outfield_pts)

        lf = self._foul_left_far
        rf = self._foul_right_far
        lp = (PLATE_X - _RUNWAY_HALF_PLATE, PLATE_Y)
        rp = (PLATE_X + _RUNWAY_HALF_PLATE, PLATE_Y)
        lt = (PLATE_X - _RUNWAY_HALF_FAR - 4, _Y_RUNWAY_TOP)
        rt = (PLATE_X + _RUNWAY_HALF_FAR + 4, _Y_RUNWAY_TOP)

        pygame.draw.polygon(surface, GRASS_MID, [(0, PLATE_Y), lp, lt, lf, (0, HORIZON_Y + 8)])
        pygame.draw.polygon(surface, GRASS_MID, [(SCREEN_W, PLATE_Y), rp, rt, rf, (SCREEN_W, HORIZON_Y + 8)])

        # Tiered tone on wings
        for i, col in enumerate((GRASS_LO, GRASS_HI)):
            z0 = 0.12 + i * 0.22
            z1 = z0 + 0.18
            strip_l = [
                _field_to_screen(-1.5, z0),
                _field_to_screen(-0.32, z0),
                _field_to_screen(-0.32, z1),
                _field_to_screen(-1.5, z1),
            ]
            strip_r = [
                _field_to_screen(1.5, z0),
                _field_to_screen(0.32, z0),
                _field_to_screen(0.32, z1),
                _field_to_screen(1.5, z1),
            ]
            pygame.draw.polygon(surface, col, strip_l)
            pygame.draw.polygon(surface, col, strip_r)

    def _draw_warning_arc(self, surface):
        pts = [
            (PLATE_X - _HALF_FAR * 6, HORIZON_Y + 8),
            (PLATE_X + _HALF_FAR * 6, HORIZON_Y + 8),
            _field_to_screen(1.05, 0.12),
            _field_to_screen(-1.05, 0.12),
        ]
        pygame.draw.polygon(surface, (165, 125, 72), pts)
        pygame.draw.polygon(surface, (120, 88, 52), pts, 1)

    def _draw_runway(self, surface):
        y_top = _Y_RUNWAY_TOP
        clay = [
            (PLATE_X - _RUNWAY_HALF_PLATE, PLATE_Y),
            (PLATE_X + _RUNWAY_HALF_PLATE, PLATE_Y),
            (PLATE_X + _RUNWAY_HALF_FAR, y_top),
            (PLATE_X - _RUNWAY_HALF_FAR, y_top),
        ]
        pygame.draw.polygon(surface, TRACK_TAN_MID, clay)
        pygame.draw.polygon(surface, TRACK_TAN_DARK, clay, 2)

        # Lighter spine down the middle (depth)
        spine = [
            (PLATE_X - 28, PLATE_Y - 2),
            (PLATE_X + 28, PLATE_Y - 2),
            (PLATE_X + 5, y_top + 4),
            (PLATE_X - 5, y_top + 4),
        ]
        pygame.draw.polygon(surface, TRACK_TAN_LIGHT, spine)

        for gx, gy in self._scuff_pts:
            pygame.draw.circle(surface, TRACK_TAN_DARK, (gx, gy), 1)

        self._draw_center_chalk(surface, y_top)

    def _draw_center_chalk(self, surface, y_top):
        n = 22
        for i in range(n):
            if i % 2 == 1:
                continue
            z = 0.08 + (i / n) * 0.88
            px, py = _field_to_screen(0.0, z)
            pygame.draw.circle(surface, CHALK_GLOW, (px, py), 2)
            pygame.draw.circle(surface, WHITE, (px, py), 1)

    def _draw_grass_stripes(self, surface):
        for i in range(7):
            z0 = 0.08 + i * 0.065
            z1 = z0 + 0.034
            col = FIELD_GREEN if i % 2 == 0 else FIELD_DARK
            for sign in (-1, 1):
                poly = [
                    _field_to_screen(sign * 0.95, z0),
                    _field_to_screen(sign * 0.38, z0),
                    _field_to_screen(sign * 0.38, z1),
                    _field_to_screen(sign * 0.95, z1),
                ]
                pygame.draw.polygon(surface, col, poly)

    def _draw_foul_lines(self, surface):
        chalk_w = 4
        pygame.draw.line(surface, BASELINE_WHT, (PLATE_X, PLATE_Y), self._foul_left_far, chalk_w)
        pygame.draw.line(surface, BASELINE_WHT, (PLATE_X, PLATE_Y), self._foul_right_far, chalk_w)
        pygame.draw.line(surface, (210, 205, 190), (PLATE_X, PLATE_Y), self._foul_left_far, 1)
        pygame.draw.line(surface, (210, 205, 190), (PLATE_X, PLATE_Y), self._foul_right_far, 1)

    def _draw_base_paths(self, surface):
        b1 = _field_to_screen(0.55, 0.55)
        b2 = _field_to_screen(0.0, 0.22)
        b3 = _field_to_screen(-0.55, 0.55)
        hp = (PLATE_X, PLATE_Y - 10)
        c = (215, 210, 195)
        pygame.draw.line(surface, c, hp, b1, 2)
        pygame.draw.line(surface, c, b1, b2, 2)
        pygame.draw.line(surface, c, b2, b3, 2)
        pygame.draw.line(surface, c, b3, hp, 2)

    def _draw_bases(self, surface):
        base_size = 12
        for pos in [(0.55, 0.55), (0.0, 0.22), (-0.55, 0.55)]:
            sx, sy = _field_to_screen(pos[0], pos[1])
            scale = 0.45 + 0.55 * pos[1]
            bs = max(4, int(base_size * scale))
            rect = pygame.Rect(sx - bs // 2, sy - bs // 2, bs, bs)
            pygame.draw.rect(surface, BASE_WHITE, rect)
            pygame.draw.rect(surface, (165, 155, 130), rect, 1)

    def _draw_mound(self, surface):
        mx, my = _field_to_screen(0.0, 0.40)
        w, h = 52, 20
        pygame.draw.ellipse(surface, (45, 85, 48), (mx - w // 2 - 4, my - h // 2 - 3, w + 8, h + 6))
        pygame.draw.ellipse(surface, MOUND_TAN, (mx - w // 2, my - h // 2, w, h))
        pygame.draw.ellipse(surface, (145, 112, 72), (mx - w // 2, my - h // 2, w, h), 2)
        pygame.draw.rect(surface, WHITE, (mx - 7, my - 3, 14, 5))
        pygame.draw.rect(surface, (200, 200, 200), (mx - 7, my - 3, 14, 5), 1)

    def _draw_home_plate(self, surface):
        hp_pts = [
            (PLATE_X, PLATE_Y - 16),
            (PLATE_X + 12, PLATE_Y - 9),
            (PLATE_X + 12, PLATE_Y + 5),
            (PLATE_X - 12, PLATE_Y + 5),
            (PLATE_X - 12, PLATE_Y - 9),
        ]
        pygame.draw.polygon(surface, WHITE, hp_pts)
        pygame.draw.polygon(surface, (175, 168, 150), hp_pts, 2)

        for dx in (-34, 16):
            pygame.draw.rect(
                surface, (235, 225, 200),
                (PLATE_X + dx, PLATE_Y - 24, 18, 32), 2,
            )

        # Catcher box dirt smudge
        pygame.draw.ellipse(
            surface, (TRACK_TAN_DARK[0], TRACK_TAN_DARK[1], TRACK_TAN_DARK[2]),
            (PLATE_X - 70, PLATE_Y - 8, 140, 22), 1,
        )

    def _draw_batter_from_behind(self, surface):
        """Narrow silhouette — batter between you and the pitcher."""
        leg_l = (PLATE_X - 22, PLATE_Y - 4)
        leg_r = (PLATE_X + 22, PLATE_Y - 4)
        pygame.draw.rect(surface, (28, 32, 38), (leg_l[0] - 9, leg_l[1] - 52, 16, 54), border_radius=4)
        pygame.draw.rect(surface, (28, 32, 38), (leg_r[0] - 7, leg_r[1] - 52, 16, 54), border_radius=4)
        pygame.draw.rect(surface, (40, 48, 56), (PLATE_X - 28, PLATE_Y - 118, 56, 62), border_radius=10)
        pygame.draw.line(surface, (55, 40, 28), (PLATE_X - 40, PLATE_Y - 108), (PLATE_X + 50, PLATE_Y - 100), 5)

    def _draw_catcher_vignette(self, surface):
        v = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for x in range(0, 120, 2):
            a = int(70 * (1.0 - x / 120.0))
            pygame.draw.line(v, (0, 0, 0, a), (x, PLATE_Y - 140), (x, SCREEN_H))
        for x in range(0, 120, 2):
            a = int(70 * (1.0 - x / 120.0))
            pygame.draw.line(v, (0, 0, 0, a), (SCREEN_W - 1 - x, PLATE_Y - 140), (SCREEN_W - 1 - x, SCREEN_H))
        pygame.draw.rect(v, (0, 0, 0, 55), (0, PLATE_Y + 8, SCREEN_W, SCREEN_H - PLATE_Y - 8))
        surface.blit(v, (0, 0))

    def _make_outfield_arc(self) -> list:
        return [
            (0, HORIZON_Y + 4),
            (0, PLATE_Y),
            (SCREEN_W, PLATE_Y),
            (SCREEN_W, HORIZON_Y + 4),
        ]
