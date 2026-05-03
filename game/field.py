"""
Pseudo-3D baseball field renderer.

Rendering approach
------------------
The field is drawn as a series of layered polygons using Pygame draw calls.
A perspective transform maps field-space (x, z) → screen (px, py):

    py = HORIZON_Y + (PLATE_Y - HORIZON_Y) * (z / PITCHER_DEPTH_MAX)
    half_w = lerp(FIELD_WIDTH_FAR/2, FIELD_WIDTH_NEAR/2, z_norm)
    px = SCREEN_W//2 + x_field * (half_w / HALF_ZONE_WIDTH)

where z_norm = 0 at horizon, 1 at home plate.

Layers (back to front)
  1. Sky gradient
  2. Outfield green + crowd stands
  3. Warning track arc
  4. Infield dirt
  5. Base paths
  6. Bases
  7. Pitcher's mound
  8. Home plate + batter's box

Ball and its shadow are drawn by the main loop *after* calling draw_field().

# TODO: Add animated crowd sprites for Tennis / Boxing arenas
"""

import math
import pygame

from game.constants import (
    SCREEN_W, SCREEN_H,
    HORIZON_Y, PLATE_Y, PLATE_X,
    FIELD_WIDTH_NEAR, FIELD_WIDTH_FAR,
    PITCHER_DEPTH, MOUND_Y,
    SKY_TOP, SKY_BOT, CLOUD_WHITE,
    FIELD_GREEN, FIELD_DARK,
    INFIELD_TAN, MOUND_TAN, BASELINE_WHT,
    BASE_WHITE, CROWD_BLUE,
    WHITE, BLACK,
)

_HALF_NEAR = FIELD_WIDTH_NEAR // 2
_HALF_FAR  = FIELD_WIDTH_FAR  // 2


# ---------------------------------------------------------------------------
# Helper: field-space → screen-space
# ---------------------------------------------------------------------------

def _field_to_screen(x_field: float, z_norm: float) -> tuple[int, int]:
    """
    Convert field coordinates to screen pixels.

    Parameters
    ----------
    x_field : lateral offset in field units (positive = right from batter)
    z_norm  : 0 = horizon / far field, 1 = home plate
    """
    py = int(HORIZON_Y + (PLATE_Y - HORIZON_Y) * z_norm)
    half_w = _HALF_FAR + (_HALF_NEAR - _HALF_FAR) * z_norm
    px = int(SCREEN_W // 2 + x_field * half_w * 3.5)
    return px, py


# ---------------------------------------------------------------------------
# Cloud helper
# ---------------------------------------------------------------------------

class Cloud:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.speed = 0.12

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
                 int(r * 2), int(r * 1.2))
            )


# ---------------------------------------------------------------------------
# Main field renderer
# ---------------------------------------------------------------------------

class FieldRenderer:
    def __init__(self):
        self._clouds = [
            Cloud( 150, 60, 180, 38),
            Cloud( 500, 40, 220, 42),
            Cloud( 900, 70, 160, 35),
            Cloud(1150, 50, 200, 40),
        ]

        # Pre-compute static geometry
        self._sky_rect = pygame.Rect(0, 0, SCREEN_W, HORIZON_Y + 20)

        # Left & right foul-line vanishing-point corners (screen space)
        self._foul_left_far  = _field_to_screen(-1.4, 0.02)
        self._foul_right_far = _field_to_screen( 1.4, 0.02)
        self._foul_left_near  = (PLATE_X - _HALF_NEAR, PLATE_Y)
        self._foul_right_near = (PLATE_X + _HALF_NEAR, PLATE_Y)

        # Outfield arc control points
        self._outfield_pts = self._make_outfield_arc()

        # Pre-built surface for sky gradient (drawn once, reused)
        self._sky_surf = self._build_sky()

    # ------------------------------------------------------------------
    # Per-frame draw
    # ------------------------------------------------------------------

    def update(self):
        for c in self._clouds:
            c.update()

    def draw(self, surface: pygame.Surface):
        """Draw the complete field.  Call once per frame before drawing ball."""

        # 1. Sky
        surface.blit(self._sky_surf, (0, 0))
        for c in self._clouds:
            c.draw(surface)

        # 2. Outfield + crowd stands
        self._draw_outfield(surface)

        # 3. Warning track (arc near outfield wall)
        self._draw_warning_track(surface)

        # 4. Infield dirt
        self._draw_infield(surface)

        # 5. Foul lines
        self._draw_foul_lines(surface)

        # 6. Base paths
        self._draw_base_paths(surface)

        # 7. Bases
        self._draw_bases(surface)

        # 8. Pitcher's mound
        self._draw_mound(surface)

        # 9. Home plate + batter's box
        self._draw_home_plate(surface)

    def draw_ball(self, surface: pygame.Surface, ball):
        """Draw the ball and its ground shadow.  Call after draw()."""
        from game.constants import BALL_WHITE, BALL_SEAM
        if not ball.active and ball.progress < 1.0:
            return

        sx, sy = ball.get_screen_pos()
        r      = ball.get_radius()

        # Shadow (slightly offset on ground)
        shx, shy = ball.get_shadow_pos()
        shadow_r  = max(2, r - 2)
        shadow_surf = pygame.Surface((shadow_r * 2 + 2, shadow_r + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (40, 40, 40, 90),
                            (0, 0, shadow_r * 2, shadow_r))
        surface.blit(shadow_surf, (shx - shadow_r, shy - shadow_r // 2))

        # Ball body
        pygame.draw.circle(surface, BALL_WHITE, (sx, sy), r)

        # Seam lines (simple arcs)
        if r >= 6:
            pygame.draw.arc(surface, BALL_SEAM,
                            (sx - r + 2, sy - r, r, r * 2),
                            math.pi * 0.2, math.pi * 0.8, max(1, r // 5))
            pygame.draw.arc(surface, BALL_SEAM,
                            (sx + 2, sy - r, r, r * 2),
                            math.pi * 1.2, math.pi * 1.8, max(1, r // 5))

        # Outline
        pygame.draw.circle(surface, (200, 200, 190), (sx, sy), r, 1)

    def draw_strike_zone(self, surface: pygame.Surface, alpha: int = 120):
        """
        Draw a translucent strike zone rectangle near home plate.
        Useful during calibration and while ball is approaching.
        """
        from game.constants import STRIKE_ZONE_W, STRIKE_ZONE_H

        # Project zone corners to screen
        tl = _field_to_screen(-STRIKE_ZONE_W, 1.0)
        br = _field_to_screen( STRIKE_ZONE_W, 1.0)
        zone_w = br[0] - tl[0]
        zone_h = int(STRIKE_ZONE_H * (PLATE_Y - HORIZON_Y) * 1.1)
        zone_rect = pygame.Rect(tl[0], tl[1] - zone_h, zone_w, zone_h)

        zone_surf = pygame.Surface((zone_w, zone_h), pygame.SRCALPHA)
        zone_surf.fill((255, 255, 255, alpha // 3))
        pygame.draw.rect(zone_surf, (255, 255, 255, alpha), zone_surf.get_rect(), 2)
        surface.blit(zone_surf, zone_rect.topleft)

    # ------------------------------------------------------------------
    # Private draw helpers
    # ------------------------------------------------------------------

    def _draw_outfield(self, surface):
        # Green outfield polygon from horizon line down to infield edge
        outfield_pts = self._outfield_pts
        pygame.draw.polygon(surface, FIELD_GREEN, outfield_pts)

        # Crowd stand strip at horizon
        stand_rect = pygame.Rect(0, HORIZON_Y - 55, SCREEN_W, 60)
        pygame.draw.rect(surface, CROWD_BLUE, stand_rect)

        # Outfield wall (dark stripe above crowd)
        wall_rect = pygame.Rect(0, HORIZON_Y - 60, SCREEN_W, 8)
        pygame.draw.rect(surface, (30, 60, 30), wall_rect)

    def _draw_warning_track(self, surface):
        # Dirt arc near outfield wall
        pts = [
            (PLATE_X - _HALF_FAR * 5, HORIZON_Y + 15),
            (PLATE_X + _HALF_FAR * 5, HORIZON_Y + 15),
            _field_to_screen( 1.1, 0.15),
            _field_to_screen(-1.1, 0.15),
        ]
        pygame.draw.polygon(surface, INFIELD_TAN, pts)

    def _draw_infield(self, surface):
        # Large dirt infield diamond
        pts = [
            _field_to_screen(-0.85, 0.42),  # 3B side left
            _field_to_screen( 0.85, 0.42),  # 1B side right
            _field_to_screen( 0.00, 0.15),  # centre field gap
            _field_to_screen(-0.00, 0.15),
        ]
        # Trapezoid infield dirt
        pts = [
            _field_to_screen(-0.85, 0.45),
            _field_to_screen( 0.85, 0.45),
            _field_to_screen( 0.60, 0.05),
            _field_to_screen(-0.60, 0.05),
        ]
        pygame.draw.polygon(surface, INFIELD_TAN, pts)

        # Grass stripes on infield (alternating light/dark)
        for i in range(6):
            z0 = 0.10 + i * 0.06
            z1 = z0 + 0.03
            color = FIELD_GREEN if i % 2 == 0 else FIELD_DARK
            stripe_pts = [
                _field_to_screen(-0.82, z0),
                _field_to_screen( 0.82, z0),
                _field_to_screen( 0.82, z1),
                _field_to_screen(-0.82, z1),
            ]
            pygame.draw.polygon(surface, color, stripe_pts)

    def _draw_foul_lines(self, surface):
        pygame.draw.line(surface, BASELINE_WHT,
                         (PLATE_X, PLATE_Y), self._foul_left_far, 2)
        pygame.draw.line(surface, BASELINE_WHT,
                         (PLATE_X, PLATE_Y), self._foul_right_far, 2)

    def _draw_base_paths(self, surface):
        # Draw base-path lines connecting the bases
        b1 = _field_to_screen( 0.55, 0.55)
        b2 = _field_to_screen( 0.00, 0.22)
        b3 = _field_to_screen(-0.55, 0.55)
        hp = (PLATE_X, PLATE_Y - 10)

        pygame.draw.line(surface, BASELINE_WHT, hp, b1, 2)
        pygame.draw.line(surface, BASELINE_WHT, b1, b2, 2)
        pygame.draw.line(surface, BASELINE_WHT, b2, b3, 2)
        pygame.draw.line(surface, BASELINE_WHT, b3, hp, 2)

    def _draw_bases(self, surface):
        base_size = 12
        for pos, z in [
            (( 0.55, 0.55), "1B"),
            (( 0.00, 0.22), "2B"),
            ((-0.55, 0.55), "3B"),
        ]:
            sx, sy = _field_to_screen(pos[0], pos[1])
            scale  = 0.5 + 0.5 * pos[1]   # smaller when farther away
            bs = max(5, int(base_size * scale))
            rect = pygame.Rect(sx - bs // 2, sy - bs // 2, bs, bs)
            pygame.draw.rect(surface, BASE_WHITE, rect)
            pygame.draw.rect(surface, (180, 170, 140), rect, 1)

    def _draw_mound(self, surface):
        # Small ellipse for pitcher's mound
        mx, my = _field_to_screen(0.0, 0.40)
        pygame.draw.ellipse(surface, MOUND_TAN, (mx - 18, my - 7, 36, 14))
        pygame.draw.ellipse(surface, (160, 125, 80), (mx - 18, my - 7, 36, 14), 1)

        # Pitcher rubber
        pygame.draw.rect(surface, WHITE, (mx - 5, my - 2, 10, 4))

    def _draw_home_plate(self, surface):
        hp_pts = [
            (PLATE_X,       PLATE_Y - 14),
            (PLATE_X + 10,  PLATE_Y -  8),
            (PLATE_X + 10,  PLATE_Y +  4),
            (PLATE_X - 10,  PLATE_Y +  4),
            (PLATE_X - 10,  PLATE_Y -  8),
        ]
        pygame.draw.polygon(surface, WHITE,  hp_pts)
        pygame.draw.polygon(surface, (180, 170, 150), hp_pts, 1)

        # Batter's boxes (left & right)
        for dx in [-30, 14]:
            pygame.draw.rect(surface, (220, 210, 180),
                             (PLATE_X + dx, PLATE_Y - 22, 16, 28), 1)

    def _make_outfield_arc(self) -> list:
        """Generate an outfield polygon that looks like a rounded outfield wall."""
        cx = SCREEN_W // 2
        cy = HORIZON_Y + 12
        pts = []
        # Left foul line start
        pts.append((0, HORIZON_Y + 15))
        pts.append((0, PLATE_Y))
        pts.append((SCREEN_W, PLATE_Y))
        pts.append((SCREEN_W, HORIZON_Y + 15))
        return pts

    def _build_sky(self) -> pygame.Surface:
        """Create a sky gradient surface."""
        surf = pygame.Surface((SCREEN_W, HORIZON_Y + 25))
        for y in range(HORIZON_Y + 25):
            t = y / (HORIZON_Y + 25)
            r = int(SKY_TOP[0] + (SKY_BOT[0] - SKY_TOP[0]) * t)
            g = int(SKY_TOP[1] + (SKY_BOT[1] - SKY_TOP[1]) * t)
            b = int(SKY_TOP[2] + (SKY_BOT[2] - SKY_TOP[2]) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (SCREEN_W, y))
        return surf
