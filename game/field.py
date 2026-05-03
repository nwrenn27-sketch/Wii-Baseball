"""
Wii Baseball field renderer.

Visual layout matches the real Wii Sports Baseball camera angle:
  - Camera directly behind home plate, elevated ~10 degrees
  - Full diamond visible: HP at bottom-centre, 2B at upper-centre
  - Pitcher Mii visible on mound with animated wind-up / throw
  - Batter Mii visible at bottom (right-handed stance)
  - Bleachers wrap around outfield; scoreboard on centre-field wall
  - Alternating mowing stripes on outfield grass
  - Trajectory arc dots show where pitch will cross the plate
  - Ball grows with perspective; shadow on ground

Drawing order (back → front):
  1  sky gradient
  2  clouds
  3  bleachers / stands
  4  outfield green (striped)
  5  outfield wall
  6  scoreboard (centre field)
  7  warning track
  8  infield dirt diamond
  9  foul lines
  10 base paths + bases
  11 pitcher's mound + rubber
  12 home plate
  13 pitcher Mii
  14 batter Mii
  15 ball + shadow        ← called separately by main loop
  16 strike-zone overlay  ← called separately

# TODO: reuse _draw_mii() for Tennis player sprites
# TODO: reuse _field_to_screen() for Bowling lane projection
"""

import math
import random
import pygame

from game.constants import (
    SCREEN_W, SCREEN_H,
    HORIZON_Y, PLATE_Y, PLATE_X,
    FIELD_WIDTH_NEAR, FIELD_WIDTH_FAR,
    PITCHER_DEPTH_NORM, MOUND_Y,
    # colours
    WHITE, BLACK,
    SKY_TOP, SKY_BOT, CLOUD_WHITE,
    FIELD_GREEN, FIELD_DARK, FIELD_LITE,
    INFIELD_TAN, MOUND_TAN, BASELINE_WHT, BASE_WHITE, GRASS_INFIELD,
    CROWD_BLUE, CROWD_SHADE, WALL_GREEN, WALL_TOP,
    SCOREBOARD_BG, SCOREBOARD_TXT,
    FOUL_LINE,
    MII_SKIN, MII_SKIN_SHD, MII_HAIR, MII_EYE,
    TEAM_BLUE, TEAM_RED, UNIFORM_WHITE, CAP_BLUE, CAP_RED,
    BALL_WHITE, BALL_SEAM,
    WII_YELLOW, WII_WHITE,
    STRIKE_ZONE_W, STRIKE_ZONE_H,
)

_HALF_NEAR = FIELD_WIDTH_NEAR // 2
_HALF_FAR  = FIELD_WIDTH_FAR  // 2


# ---------------------------------------------------------------------------
# Core projection helper
# ---------------------------------------------------------------------------

def _field_to_screen(x_field: float, z_norm: float) -> tuple[int, int]:
    """
    Map field-space → screen pixels.

    x_field : lateral offset (positive = right from batter's perspective)
    z_norm  : 0.0 = far/horizon  →  1.0 = home plate
    """
    py     = int(HORIZON_Y + (PLATE_Y - HORIZON_Y) * z_norm)
    half_w = _HALF_FAR + (_HALF_NEAR - _HALF_FAR) * z_norm
    px     = int(SCREEN_W // 2 + x_field * half_w * 3.8)
    return px, py


# ---------------------------------------------------------------------------
# Cloud sprite
# ---------------------------------------------------------------------------

class _Cloud:
    def __init__(self, x, y, w, h, speed):
        self.x, self.y, self.w, self.h, self.speed = x, y, w, h, speed

    def update(self):
        self.x += self.speed
        if self.x > SCREEN_W + self.w:
            self.x = -self.w

    def draw(self, surf):
        blobs = [(0, 0, self.h),
                 ( self.w * 0.28, -self.h * 0.32, self.h * 0.72),
                 (-self.w * 0.28, -self.h * 0.24, self.h * 0.76),
                 ( self.w * 0.42,  self.h * 0.10, self.h * 0.56)]
        for ox, oy, r in blobs:
            pygame.draw.ellipse(
                surf, CLOUD_WHITE,
                (int(self.x + ox - r), int(self.y + oy - r * 0.6),
                 int(r * 2), int(r * 1.2))
            )


# ---------------------------------------------------------------------------
# Mii character renderer
# ---------------------------------------------------------------------------

def _draw_mii(surf, cx: int, cy: int, scale: float,
              body_color, cap_color,
              pose: str = 'idle',
              facing: int = 1):
    """
    Draw a simplified Mii character.

    pose    : 'idle' | 'wind_up' | 'throwing' | 'batting' | 'swing'
    facing  : +1 = facing right, -1 = facing left
    cy      : bottom of feet
    """
    f = facing  # shorthand for flip
    s = scale

    # -- derived positions --
    feet_y   = cy
    leg_h    = int(28 * s)
    body_h   = int(38 * s)
    body_w   = int(34 * s)
    neck_h   = int(6 * s)
    head_r   = int(24 * s)

    body_top = feet_y - leg_h - body_h
    neck_y   = body_top - neck_h
    head_cy  = neck_y - head_r

    # ---- SHADOW (ground ellipse) ----
    shad = pygame.Surface((int(60*s), int(14*s)), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 55), shad.get_rect())
    surf.blit(shad, (cx - int(30*s), feet_y - int(7*s)))

    # ---- LEGS ----
    trouser = (40, 48, 110)
    leg_w   = int(12 * s)
    for lx_off in [-int(9*s), int(9*s) - leg_w + int(2*s)]:
        lx = cx + lx_off
        pygame.draw.rect(surf, trouser, (lx, feet_y - leg_h, leg_w, leg_h))
    # shoes
    shoe_col = (30, 30, 30)
    for sx_off, sw in [(-int(12*s), int(14*s)), (int(4*s), int(14*s))]:
        pygame.draw.ellipse(surf, shoe_col,
                            (cx + sx_off, feet_y - int(6*s), sw, int(8*s)))

    # ---- BODY (jersey) ----
    bx = cx - body_w // 2
    pygame.draw.rect(surf, body_color,
                     (bx, body_top, body_w, body_h), border_radius=int(5*s))
    # jersey stripe
    stripe_col = tuple(max(0, c - 40) for c in body_color)
    pygame.draw.line(surf, stripe_col,
                     (cx, body_top + int(4*s)), (cx, body_top + body_h - int(4*s)),
                     max(1, int(2*s)))

    # ---- ARMS ----
    arm_col  = MII_SKIN
    arm_w    = max(3, int(8 * s))
    shoulder = (cx + f * int(15*s), body_top + int(8*s))

    if pose == 'wind_up':
        elbow = (cx + f * int(22*s), body_top - int(18*s))
        hand  = (cx + f * int(8*s),  body_top - int(38*s))
    elif pose == 'throwing':
        elbow = (cx + f * int(30*s), body_top + int(4*s))
        hand  = (cx + f * int(48*s), body_top + int(22*s))
    elif pose == 'batting':
        # bat held back, both hands high behind shoulder
        elbow = (cx - f * int(18*s), body_top - int(10*s))
        hand  = (cx - f * int(10*s), body_top - int(28*s))
    elif pose == 'swing':
        elbow = (cx + f * int(30*s), body_top - int(5*s))
        hand  = (cx + f * int(44*s), body_top + int(8*s))
    else:
        elbow = (cx + f * int(26*s), body_top + int(18*s))
        hand  = (cx + f * int(28*s), body_top + int(32*s))

    pygame.draw.line(surf, arm_col, shoulder, elbow, arm_w)
    pygame.draw.line(surf, arm_col, elbow,    hand,  arm_w)
    # glove / hand
    pygame.draw.circle(surf, arm_col, hand, max(3, int(6*s)))

    # ---- NECK ----
    pygame.draw.rect(surf, MII_SKIN,
                     (cx - int(5*s), neck_y, int(10*s), neck_h + int(2*s)))

    # ---- HEAD ----
    pygame.draw.circle(surf, MII_SKIN, (cx, head_cy), head_r)
    # cheek shading
    pygame.draw.circle(surf, MII_SKIN_SHD,
                       (cx + f * int(12*s), head_cy + int(6*s)),
                       max(2, int(7*s)))

    # Eyes
    eye_y = head_cy - int(4*s)
    for ex_off in [-int(8*s), int(8*s)]:
        # white of eye
        pygame.draw.ellipse(surf, WHITE,
                            (cx + ex_off - int(5*s), eye_y - int(5*s),
                             int(10*s), int(9*s)))
        # pupil
        pygame.draw.circle(surf, MII_EYE,
                           (cx + ex_off + f * int(1*s), eye_y),
                           max(2, int(3*s)))

    # Eyebrows
    brow_col = MII_HAIR
    brow_y   = eye_y - int(9*s)
    for bx_off in [-int(8*s), int(8*s)]:
        pygame.draw.line(surf, brow_col,
                         (cx + bx_off - int(5*s), brow_y + int(2*s)),
                         (cx + bx_off + int(5*s), brow_y - int(1*s)),
                         max(1, int(2*s)))

    # Mouth  (small smile)
    mouth_rect = pygame.Rect(cx - int(7*s), head_cy + int(8*s),
                             int(14*s), int(10*s))
    pygame.draw.arc(surf, (180, 80, 80), mouth_rect,
                    math.pi * 1.15, math.pi * 1.85,
                    max(1, int(2*s)))

    # ---- CAP ----
    cap_r = head_r + int(2*s)
    # Cap dome (top half of a circle)
    cap_surf = pygame.Surface((cap_r * 2 + 2, cap_r + 4), pygame.SRCALPHA)
    pygame.draw.circle(cap_surf, cap_color, (cap_r + 1, cap_r + 2), cap_r)
    # Mask off bottom half so only the top shows
    pygame.draw.rect(cap_surf, (0, 0, 0, 0),
                     (0, cap_r + 2, cap_r * 2 + 2, cap_r + 4))
    surf.blit(cap_surf, (cx - cap_r - 1, head_cy - cap_r - 2))

    # Cap brim
    brim_pts = [
        (cx - int(cap_r * 0.4), head_cy + int(2*s)),
        (cx + f * int(cap_r * 1.5), head_cy + int(2*s)),
        (cx + f * int(cap_r * 1.5), head_cy + int(2*s) + int(6*s)),
        (cx - int(cap_r * 0.4), head_cy + int(4*s)),
    ]
    pygame.draw.polygon(surf, cap_color, brim_pts)


def _draw_bat(surf, hand_pos: tuple, facing: int, scale: float,
              pose: str = 'batting'):
    """Draw a baseball bat held by the batter."""
    hx, hy = hand_pos
    f = facing
    s = scale

    if pose == 'swing':
        tip = (hx + f * int(70*s), hy - int(20*s))
    else:
        # bat held up behind shoulder
        tip = (hx - f * int(20*s), hy - int(65*s))

    # Barrel (thick end)
    pygame.draw.line(surf, (180, 110, 50), (hx, hy), tip, max(4, int(8*s)))
    pygame.draw.circle(surf, (160, 90, 40), tip, max(3, int(6*s)))
    # Handle taper
    pygame.draw.line(surf, (140, 80, 30), (hx, hy),
                     (hx + (tip[0]-hx)//3, hy + (tip[1]-hy)//3),
                     max(2, int(5*s)))


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

class FieldRenderer:
    def __init__(self):
        self._clouds = [
            _Cloud( 100, 55, 200, 42, 0.10),
            _Cloud( 480, 35, 240, 48, 0.14),
            _Cloud( 850, 62, 175, 36, 0.08),
            _Cloud(1100, 48, 220, 44, 0.12),
        ]
        # Font must be created before _build_static_field() calls _draw_scoreboard()
        self._sb_font = pygame.font.SysFont("Arial", 18, bold=True)

        self._sky_surf    = self._build_sky()
        self._field_surf  = self._build_static_field()

        # Crowd dots (generated once, drawn every frame)
        self._crowd_dots  = self._gen_crowd_dots()

        # Batter swing state (0=idle, 1=full swing) — set by main loop
        self.batter_swing: float = 0.0
        # Pitcher pose — set by main loop
        self.pitcher_pose: str   = 'idle'   # 'idle'|'wind_up'|'throwing'

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(self):
        for c in self._clouds:
            c.update()

    # ------------------------------------------------------------------
    # Public draw API
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface,
             player_score: int = 0, cpu_score: int = 0,
             inning: int = 1):
        """Draw the complete field. Call once per frame before drawing ball."""

        # 1. Sky
        surface.blit(self._sky_surf, (0, 0))
        for c in self._clouds:
            c.draw(surface)

        # 2. Static field (bleachers, grass, infield, bases …)
        surface.blit(self._field_surf, (0, 0))

        # 3. Crowd dots (subtle movement would go here)
        for dot in self._crowd_dots:
            pygame.draw.circle(surface, dot[2], (dot[0], dot[1]), dot[3])

        # 4. Scoreboard numbers (dynamic)
        self._draw_scoreboard_numbers(surface, player_score, cpu_score, inning)

        # 5. Pitcher Mii
        pitcher_scale = 0.72
        px, py = _field_to_screen(0.0, PITCHER_DEPTH_NORM)
        py += 8   # offset so feet touch mound
        _draw_mii(surface, px, py, pitcher_scale,
                  TEAM_BLUE, CAP_BLUE,
                  pose=self.pitcher_pose, facing=1)

        # 6. Batter Mii (right-handed, bottom-right of plate)
        batter_pose = 'swing' if self.batter_swing > 0.5 else 'batting'
        batter_x    = PLATE_X + 55
        batter_y    = PLATE_Y + 22
        batter_scale= 0.95
        _draw_mii(surface, batter_x, batter_y, batter_scale,
                  TEAM_RED, CAP_RED,
                  pose=batter_pose, facing=-1)
        # Bat
        bat_hand = (batter_x - int(10 * batter_scale),
                    batter_y - int(72 * batter_scale))
        if batter_pose == 'swing':
            bat_hand = (batter_x + int(44 * batter_scale),
                        batter_y - int(72 * batter_scale) + int(8 * batter_scale))
        _draw_bat(surface, bat_hand, -1, batter_scale, batter_pose)

    def draw_ball(self, surface: pygame.Surface, ball):
        """Draw ball + shadow. Call after draw()."""
        if not ball.active and ball.progress < 1.0:
            return

        sx, sy = ball.get_screen_pos()
        r      = ball.get_radius()

        # Shadow
        shx, shy = ball.get_shadow_pos()
        sr = max(2, int(r * 0.65))
        shad = pygame.Surface((sr * 4, sr * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(shad, (0, 0, 0, 80), shad.get_rect())
        surface.blit(shad, (shx - sr * 2, shy - sr))

        # Ball body
        pygame.draw.circle(surface, BALL_WHITE, (sx, sy), r)

        # Seam arcs (only visible when ball is large enough)
        if r >= 7:
            seam_w = max(1, r // 4)
            pygame.draw.arc(surface, BALL_SEAM,
                            (sx - r + 3, sy - r, r, r * 2),
                            math.pi * 0.15, math.pi * 0.85, seam_w)
            pygame.draw.arc(surface, BALL_SEAM,
                            (sx + 3,     sy - r, r, r * 2),
                            math.pi * 1.15, math.pi * 1.85, seam_w)

        # Outline
        pygame.draw.circle(surface, (205, 202, 192), (sx, sy), r, 1)

    def draw_trajectory_arc(self, surface: pygame.Surface, ball,
                            target_x: float, target_y: float):
        """
        Draw a dotted arc from current ball position to where it will
        cross home plate. Wii Baseball shows this as a small dotted curve
        that fades as the ball gets close.
        Visible during the first half of the ball's journey.
        """
        if not ball.active or ball.progress > 0.55:
            return

        alpha = int(200 * (1.0 - ball.progress / 0.55))
        sx, sy = ball.get_screen_pos()

        # Target screen position (where ball will be at plate)
        from game.constants import PITCHER_DEPTH_NORM as PD
        tx_screen, ty_screen = _field_to_screen(target_x, 1.0)
        ty_screen -= int(target_y * (PLATE_Y - HORIZON_Y) * 0.6)

        # Interpolate 6 dots along a curved path
        n_dots = 7
        for i in range(1, n_dots):
            t = i / n_dots
            # Lerp with slight upward arc in the middle
            ix = int(sx + (tx_screen - sx) * t)
            iy = int(sy + (ty_screen - sy) * t - math.sin(t * math.pi) * 18)
            dot_r = max(2, int(4 * (1.0 - t * 0.4)))
            dot_surf = pygame.Surface((dot_r * 2 + 2, dot_r * 2 + 2), pygame.SRCALPHA)
            col_alpha = int(alpha * (1.0 - t * 0.5))
            pygame.draw.circle(dot_surf, (*WII_YELLOW, col_alpha),
                               (dot_r + 1, dot_r + 1), dot_r)
            surface.blit(dot_surf, (ix - dot_r - 1, iy - dot_r - 1))

    def draw_strike_zone(self, surface: pygame.Surface, alpha: int = 130):
        """
        Wii-style white-bordered strike zone box floating over home plate.
        """
        tl = _field_to_screen(-STRIKE_ZONE_W, 1.0)
        br = _field_to_screen( STRIKE_ZONE_W, 1.0)
        zw = br[0] - tl[0]
        zh = int(STRIKE_ZONE_H * (PLATE_Y - HORIZON_Y) * 1.5)
        zx = tl[0]
        zy = tl[1] - zh

        sz = pygame.Surface((zw, zh), pygame.SRCALPHA)
        sz.fill((255, 255, 255, alpha // 5))
        pygame.draw.rect(sz, (255, 255, 255, alpha), sz.get_rect(), 2, border_radius=3)
        # Inner dotted lines for quadrants
        mid_x = zw // 2
        mid_y = zh // 2
        for gx in [mid_x]:
            for gy in range(0, zh, 6):
                pygame.draw.rect(sz, (255, 255, 255, alpha // 2), (gx, gy, 1, 3))
        for gy in [mid_y]:
            for gx in range(0, zw, 6):
                pygame.draw.rect(sz, (255, 255, 255, alpha // 2), (gx, gy, 3, 1))

        surface.blit(sz, (zx, zy))

    # ------------------------------------------------------------------
    # Pre-built static field surface
    # ------------------------------------------------------------------

    def _build_static_field(self) -> pygame.Surface:
        surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

        self._draw_bleachers(surf)
        self._draw_outfield_wall(surf)
        self._draw_scoreboard(surf)
        self._draw_outfield_grass(surf)
        self._draw_warning_track(surf)
        self._draw_infield_dirt(surf)
        self._draw_foul_lines(surf)
        self._draw_base_paths(surf)
        self._draw_bases(surf)
        self._draw_mound(surf)
        self._draw_home_plate(surf)

        return surf

    # ------------------------------------------------------------------
    # Static field elements
    # ------------------------------------------------------------------

    def _draw_bleachers(self, surf):
        """Wrap-around bleacher stands behind outfield wall."""
        # Full-width band at top
        pygame.draw.rect(surf, CROWD_SHADE, (0, HORIZON_Y - 62, SCREEN_W, 68))
        pygame.draw.rect(surf, CROWD_BLUE,  (0, HORIZON_Y - 54, SCREEN_W, 58))

        # Draw seat rows as horizontal stripes
        for row in range(5):
            y = HORIZON_Y - 50 + row * 10
            col = CROWD_BLUE if row % 2 == 0 else CROWD_SHADE
            pygame.draw.rect(surf, col, (0, y, SCREEN_W, 9))

    def _draw_outfield_wall(self, surf):
        """Green outfield wall strip just above the grass."""
        # Wall face
        pygame.draw.rect(surf, WALL_GREEN,
                         (0, HORIZON_Y - 4, SCREEN_W, 16))
        # Top cap
        pygame.draw.rect(surf, WALL_TOP,
                         (0, HORIZON_Y - 8, SCREEN_W, 5))
        # Padding strip (yellow)
        pygame.draw.rect(surf, (200, 185, 50),
                         (0, HORIZON_Y + 8, SCREEN_W, 4))

    def _draw_scoreboard(self, surf):
        """Centre-field scoreboard on the outfield wall."""
        sbw, sbh = 220, 52
        sbx = SCREEN_W // 2 - sbw // 2
        sby = HORIZON_Y - 60
        pygame.draw.rect(surf, SCOREBOARD_BG, (sbx, sby, sbw, sbh), border_radius=6)
        pygame.draw.rect(surf, (60, 140, 60), (sbx, sby, sbw, sbh), 2, border_radius=6)

        label = self._sb_font.render("SCORE", True, (120, 200, 120))
        surf.blit(label, label.get_rect(center=(SCREEN_W // 2, sby + 13)))

    def _draw_scoreboard_numbers(self, surf, p_score, c_score, inning):
        """Overwrite just the score numbers on the scoreboard each frame."""
        sbw = 220
        sbx = SCREEN_W // 2 - sbw // 2
        sby = HORIZON_Y - 60

        pygame.draw.rect(surf, SCOREBOARD_BG,
                         (sbx + 2, sby + 24, sbw - 4, 24))

        score_str = f"YOU {p_score}  —  CPU {c_score}   INN {inning}"
        sc = self._sb_font.render(score_str, True, SCOREBOARD_TXT)
        surf.blit(sc, sc.get_rect(center=(SCREEN_W // 2, sby + 36)))

    def _draw_outfield_grass(self, surf):
        """Full outfield polygon with alternating mowing stripes."""
        # Base fill
        field_pts = [
            (0,         HORIZON_Y + 12),
            (SCREEN_W,  HORIZON_Y + 12),
            (SCREEN_W,  PLATE_Y + 40),
            (0,         PLATE_Y + 40),
        ]
        pygame.draw.polygon(surf, FIELD_GREEN, field_pts)

        # Alternating stripes (perspective-correct bands)
        n_stripes = 14
        for i in range(n_stripes):
            t0 = i       / n_stripes
            t1 = (i + 1) / n_stripes
            y0 = int(HORIZON_Y + 12 + (PLATE_Y + 28 - HORIZON_Y) * t0)
            y1 = int(HORIZON_Y + 12 + (PLATE_Y + 28 - HORIZON_Y) * t1)
            col = FIELD_DARK if i % 2 == 0 else FIELD_LITE
            pygame.draw.rect(surf, col, (0, y0, SCREEN_W, y1 - y0))

    def _draw_warning_track(self, surf):
        """Reddish-tan warning track arc inside the outfield wall."""
        pts = [
            (0,          HORIZON_Y + 12),
            (SCREEN_W,   HORIZON_Y + 12),
            _field_to_screen( 1.35, 0.06),
            _field_to_screen( 0.90, 0.14),
            _field_to_screen( 0.00, 0.16),
            _field_to_screen(-0.90, 0.14),
            _field_to_screen(-1.35, 0.06),
        ]
        pygame.draw.polygon(surf, (168, 126, 76), pts)

    def _draw_infield_dirt(self, surf):
        """Brown dirt infield diamond."""
        # Large dirt area
        hp = (PLATE_X, PLATE_Y)
        b1 = _field_to_screen( 0.57, 0.48)
        b2 = _field_to_screen( 0.00, 0.70)
        b3 = _field_to_screen(-0.57, 0.48)

        pygame.draw.polygon(surf, INFIELD_TAN, [hp, b1, b2, b3])

        # Grass circle inside the diamond (Wii has a circular grass patch)
        center_x = (hp[0] + b1[0] + b2[0] + b3[0]) // 4
        center_y = (hp[1] + b1[1] + b2[1] + b3[1]) // 4
        grass_r  = int((b2[1] - hp[1]) * 0.36)
        pygame.draw.circle(surf, GRASS_INFIELD, (center_x, center_y), grass_r)

    def _draw_foul_lines(self, surf):
        hp = (PLATE_X, PLATE_Y)
        lf_far = _field_to_screen(-1.55, 0.01)
        rf_far = _field_to_screen( 1.55, 0.01)
        pygame.draw.line(surf, FOUL_LINE, hp, lf_far, 2)
        pygame.draw.line(surf, FOUL_LINE, hp, rf_far, 2)

    def _draw_base_paths(self, surf):
        hp = (PLATE_X, PLATE_Y)
        b1 = _field_to_screen( 0.57, 0.48)
        b2 = _field_to_screen( 0.00, 0.70)
        b3 = _field_to_screen(-0.57, 0.48)

        for start, end in [(hp, b1), (b1, b2), (b2, b3), (b3, hp)]:
            pygame.draw.line(surf, BASELINE_WHT, start, end, 2)

    def _draw_bases(self, surf):
        """White square bases at 1B, 2B, 3B."""
        bases = [
            (_field_to_screen( 0.57, 0.48), "1B"),
            (_field_to_screen( 0.00, 0.70), "2B"),
            (_field_to_screen(-0.57, 0.48), "3B"),
        ]
        for (bx, by), label in bases:
            z_norm = 0.48 if label != "2B" else 0.70
            bs = max(7, int(14 * z_norm))
            rect = pygame.Rect(bx - bs // 2, by - bs // 2, bs, bs)
            pygame.draw.rect(surf, BASE_WHITE, rect)
            pygame.draw.rect(surf, (190, 180, 150), rect, 1)

    def _draw_mound(self, surf):
        mx, my = _field_to_screen(0.0, PITCHER_DEPTH_NORM)
        pygame.draw.ellipse(surf, MOUND_TAN, (mx - 22, my - 8, 44, 16))
        pygame.draw.ellipse(surf, (160, 124, 78), (mx - 22, my - 8, 44, 16), 1)
        # Pitcher's rubber (white strip)
        pygame.draw.rect(surf, WHITE, (mx - 6, my - 3, 12, 5))

    def _draw_home_plate(self, surf):
        """Classic pentagonal home plate."""
        pts = [
            (PLATE_X,      PLATE_Y - 16),
            (PLATE_X + 11, PLATE_Y -  9),
            (PLATE_X + 11, PLATE_Y +  3),
            (PLATE_X - 11, PLATE_Y +  3),
            (PLATE_X - 11, PLATE_Y -  9),
        ]
        pygame.draw.polygon(surf, WHITE, pts)
        pygame.draw.polygon(surf, (185, 175, 148), pts, 1)

        # Batter's boxes (light chalk lines)
        for dx in [-34, 12]:
            pygame.draw.rect(surf, BASELINE_WHT,
                             (PLATE_X + dx, PLATE_Y - 26, 22, 32), 1)

    # ------------------------------------------------------------------
    # Crowd dots  (static positions, generated once)
    # ------------------------------------------------------------------

    def _gen_crowd_dots(self) -> list:
        rng = random.Random(42)
        dots = []
        colours = [(255, 80, 80), (80, 80, 255), (255, 255, 80),
                   (80, 255, 80), (255, 255, 255), (255, 160, 80)]
        for _ in range(320):
            x = rng.randint(0, SCREEN_W)
            y = rng.randint(HORIZON_Y - 54, HORIZON_Y - 6)
            col = rng.choice(colours)
            r   = rng.randint(2, 5)
            dots.append((x, y, col, r))
        return dots

    # ------------------------------------------------------------------
    # Sky gradient surface (built once)
    # ------------------------------------------------------------------

    def _build_sky(self) -> pygame.Surface:
        h    = HORIZON_Y + 10
        surf = pygame.Surface((SCREEN_W, h))
        for y in range(h):
            t = y / h
            r = int(SKY_TOP[0] + (SKY_BOT[0] - SKY_TOP[0]) * t)
            g = int(SKY_TOP[1] + (SKY_BOT[1] - SKY_TOP[1]) * t)
            b = int(SKY_TOP[2] + (SKY_BOT[2] - SKY_TOP[2]) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (SCREEN_W, y))
        return surf
