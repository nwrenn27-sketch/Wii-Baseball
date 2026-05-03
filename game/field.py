import math
import pygame

from game.constants import (
    SCREEN_W, SCREEN_H,
    HORIZON_Y, PLATE_Y, PLATE_X,
    FIELD_WIDTH_NEAR, FIELD_WIDTH_FAR,
    WHITE, BLACK,
    BALL_WHITE, BALL_SEAM,
)

_HALF_NEAR = FIELD_WIDTH_NEAR // 2
_HALF_FAR  = FIELD_WIDTH_FAR  // 2

# Google-style palette
_SKY        = (120, 200, 255)
_SKY_LOW    = (160, 220, 255)
_GRASS_OUT  = ( 72, 168,  68)
_GRASS_IN   = ( 88, 190,  80)
_DIRT       = (195, 155, 100)
_DIRT_EDGE  = (165, 125,  75)
_CHALK      = (245, 242, 228)
_BASE_COL   = (250, 248, 238)
_MOUND_COL  = (185, 148,  95)
_CROWD_A    = ( 60, 120, 210)
_CROWD_B    = (200,  60,  60)
_CROWD_C    = (240, 200,  40)
_SKIN       = (255, 210, 165)
_HELMET_BLUE= ( 28,  72, 188)
_HELMET_RED = (190,  32,  32)
_UNIFORM_W  = (240, 242, 248)
_UNIFORM_G  = (175, 178, 192)
_PANTS_GRY  = (140, 143, 158)


def _field_to_screen(x_field: float, z_norm: float) -> tuple[int, int]:
    """z_norm 0 = horizon, 1 = home plate."""
    py = int(HORIZON_Y + (PLATE_Y - HORIZON_Y) * z_norm)
    half_w = _HALF_FAR + (_HALF_NEAR - _HALF_FAR) * z_norm
    px = int(PLATE_X + x_field * half_w * 3.5)
    return px, py


# ── base positions (reused everywhere) ─────────────────────────────────────
def _base_pos(which: str) -> tuple[int, int]:
    if which == "1B":
        return _field_to_screen( 0.55, 0.55)
    if which == "2B":
        return _field_to_screen( 0.00, 0.22)
    if which == "3B":
        return _field_to_screen(-0.55, 0.55)
    return (PLATE_X, PLATE_Y - 8)   # home


class FieldRenderer:
    def __init__(self):
        self._sky_surf = self._build_sky()
        # Pre-bake crowd dots (fixed seed = deterministic)
        import random as _rng
        rng = _rng.Random(7)
        self._crowd = [
            (rng.randint(0, SCREEN_W), rng.randint(4, HORIZON_Y - 60),
             _CROWD_A if rng.random() < 0.5 else (_CROWD_B if rng.random() < 0.5 else _CROWD_C))
            for _ in range(320)
        ]

    def update(self):
        pass  # reserved for future animations

    def draw(self, surface: pygame.Surface):
        surface.blit(self._sky_surf, (0, 0))
        self._draw_crowd(surface)
        self._draw_outfield(surface)
        self._draw_infield_dirt(surface)
        self._draw_base_paths(surface)
        self._draw_bases(surface)
        self._draw_mound(surface)
        self._draw_home_plate(surface)
        self._draw_pitcher(surface)
        self._draw_batter(surface)

    # ── ball ────────────────────────────────────────────────────────────────

    def draw_ball(self, surface: pygame.Surface, ball):
        if not ball.active and ball.progress < 1.0:
            return

        sx, sy = ball.get_screen_pos()
        r = ball.get_radius()

        # Motion trail
        trail = list(ball._trail)
        if len(trail) >= 2:
            for i, (tx, ty, tr) in enumerate(trail):
                age = (i + 1) / max(len(trail), 1)
                alpha = int(20 + 80 * age)
                rr = max(2, int(tr * 0.65))
                ts = pygame.Surface((rr * 2 + 2, rr * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(ts, (255, 255, 255, alpha), (rr + 1, rr + 1), rr)
                surface.blit(ts, (tx - rr - 1, ty - rr - 1))

        # Shadow
        shx, shy = ball.get_shadow_pos()
        sr = max(2, int(r * 0.55))
        ss = pygame.Surface((sr * 2 + 2, sr + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(ss, (0, 0, 0, 55), (0, 0, sr * 2, sr))
        surface.blit(ss, (shx - sr, shy - sr // 2))

        # Ball body
        pygame.draw.circle(surface, (40, 40, 40), (sx, sy), r + 2)
        pygame.draw.circle(surface, BALL_WHITE, (sx, sy), r)

        if r >= 6:
            seam_w = max(2, r // 4)
            pygame.draw.arc(surface, BALL_SEAM,
                            (sx - r + 2, sy - r, r, r * 2),
                            math.pi * 0.2, math.pi * 0.8, seam_w)
            pygame.draw.arc(surface, BALL_SEAM,
                            (sx + 2, sy - r, r, r * 2),
                            math.pi * 1.2, math.pi * 1.8, seam_w)

    # ── strike zone ─────────────────────────────────────────────────────────

    def draw_strike_zone(self, surface: pygame.Surface, alpha: int = 120):
        from game.constants import STRIKE_ZONE_W, STRIKE_ZONE_H
        tl = _field_to_screen(-STRIKE_ZONE_W, 1.0)
        br = _field_to_screen( STRIKE_ZONE_W, 1.0)
        zone_w = max(24, br[0] - tl[0])
        zone_h = int(STRIKE_ZONE_H * (PLATE_Y - HORIZON_Y) * 1.05)
        zone_rect = pygame.Rect(tl[0], tl[1] - zone_h, zone_w, zone_h)

        zs = pygame.Surface((zone_w, zone_h), pygame.SRCALPHA)
        zs.fill((255, 255, 255, max(0, alpha // 5)))
        pygame.draw.rect(zs, (255, 255, 255, min(220, alpha + 40)),
                         zs.get_rect(), 3, border_radius=4)
        surface.blit(zs, zone_rect.topleft)

        brk, thick, cr = min(18, zone_w // 5), 4, (255, 80, 80)
        x0, y0 = zone_rect.left, zone_rect.top
        x1, y1 = zone_rect.right - 1, zone_rect.bottom - 1
        for px, py, ex, ey in [
            (x0, y0, x0 + brk, y0), (x0, y0, x0, y0 + brk),
            (x1, y0, x1 - brk, y0), (x1, y0, x1, y0 + brk),
            (x0, y1, x0 + brk, y1), (x0, y1, x0, y1 - brk),
            (x1, y1, x1 - brk, y1), (x1, y1, x1, y1 - brk),
        ]:
            pygame.draw.line(surface, cr, (px, py), (ex, ey), thick)

    # ── private layers ───────────────────────────────────────────────────────

    def _build_sky(self) -> pygame.Surface:
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        h = HORIZON_Y + 20
        for y in range(h):
            t = y / max(h, 1)
            r = int(_SKY[0] * (1 - t) + _SKY_LOW[0] * t)
            g = int(_SKY[1] * (1 - t) + _SKY_LOW[1] * t)
            b = int(_SKY[2] * (1 - t) + _SKY_LOW[2] * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (SCREEN_W, y))
        surf.fill(_GRASS_OUT, (0, h, SCREEN_W, SCREEN_H - h))
        return surf

    def _draw_crowd(self, surface: pygame.Surface):
        # Simple colored band
        pygame.draw.rect(surface, (45, 55, 100), (0, 0, SCREEN_W, HORIZON_Y - 50))
        pygame.draw.rect(surface, (55, 70, 125), (0, HORIZON_Y - 50, SCREEN_W, 32))
        pygame.draw.rect(surface, (70, 85, 145), (0, HORIZON_Y - 20, SCREEN_W, 10))
        for cx, cy, col in self._crowd:
            pygame.draw.circle(surface, col, (cx, cy), 3)
            pygame.draw.circle(surface, (220, 215, 210), (cx, cy - 4), 2)

    def _draw_outfield(self, surface: pygame.Surface):
        # Bright green outfield polygon
        left_far  = _field_to_screen(-1.5, 0.02)
        right_far = _field_to_screen( 1.5, 0.02)
        left_near = (0,          PLATE_Y)
        right_near= (SCREEN_W,   PLATE_Y)
        pts = [left_far, right_far, right_near, left_near]
        pygame.draw.polygon(surface, _GRASS_OUT, pts)

        # Mowing stripes
        for i in range(8):
            z0 = 0.04 + i * 0.12
            z1 = z0  + 0.06
            col = _GRASS_IN if i % 2 == 0 else _GRASS_OUT
            for side in (-1, 1):
                stripe = [
                    _field_to_screen(side * 0.25, z0),
                    _field_to_screen(side * 1.4,  z0),
                    _field_to_screen(side * 1.4,  z1),
                    _field_to_screen(side * 0.25, z1),
                ]
                pygame.draw.polygon(surface, col, stripe)

    def _draw_infield_dirt(self, surface: pygame.Surface):
        # Dirt diamond around the bases
        hp  = (PLATE_X, PLATE_Y - 8)
        b1  = _base_pos("1B")
        b2  = _base_pos("2B")
        b3  = _base_pos("3B")

        # Expand each corner outward slightly for the dirt patch
        def _expand(pt, cx, cy, amt=28):
            dx, dy = pt[0] - cx, pt[1] - cy
            d = math.hypot(dx, dy)
            if d < 1:
                return pt
            return (int(pt[0] + dx / d * amt), int(pt[1] + dy / d * amt))

        cx = (hp[0] + b1[0] + b2[0] + b3[0]) // 4
        cy = (hp[1] + b1[1] + b2[1] + b3[1]) // 4
        dirt_pts = [_expand(p, cx, cy) for p in [hp, b1, b2, b3]]
        pygame.draw.polygon(surface, _DIRT, dirt_pts)
        pygame.draw.polygon(surface, _DIRT_EDGE, dirt_pts, 3)

    def _draw_base_paths(self, surface: pygame.Surface):
        hp = (PLATE_X, PLATE_Y - 8)
        b1 = _base_pos("1B")
        b2 = _base_pos("2B")
        b3 = _base_pos("3B")
        for a, b in [(hp, b1), (b1, b2), (b2, b3), (b3, hp)]:
            pygame.draw.line(surface, _CHALK, a, b, 4)
            pygame.draw.line(surface, WHITE,  a, b, 2)

    def _draw_bases(self, surface: pygame.Surface):
        for name in ("1B", "2B", "3B"):
            bx, by = _base_pos(name)
            z = {"1B": 0.55, "2B": 0.22, "3B": 0.55}[name]
            scale = 0.5 + 0.5 * z
            sz = max(5, int(14 * scale))
            rect = pygame.Rect(bx - sz // 2, by - sz // 2, sz, sz)
            pygame.draw.rect(surface, _BASE_COL, rect, border_radius=2)
            pygame.draw.rect(surface, (160, 152, 132), rect, 1, border_radius=2)

    def _draw_mound(self, surface: pygame.Surface):
        mx, my = _field_to_screen(0.0, 0.40)
        pygame.draw.ellipse(surface, (55, 100, 55), (mx - 36, my - 14, 72, 28))
        pygame.draw.ellipse(surface, _MOUND_COL,   (mx - 32, my - 12, 64, 24))
        pygame.draw.rect(surface, WHITE,            (mx - 5,  my -  2, 10,  4))

    def _draw_home_plate(self, surface: pygame.Surface):
        pts = [
            (PLATE_X,      PLATE_Y - 14),
            (PLATE_X + 11, PLATE_Y -  8),
            (PLATE_X + 11, PLATE_Y +  4),
            (PLATE_X - 11, PLATE_Y +  4),
            (PLATE_X - 11, PLATE_Y -  8),
        ]
        pygame.draw.polygon(surface, WHITE, pts)
        pygame.draw.polygon(surface, (165, 155, 130), pts, 2)

    def _draw_pitcher(self, surface: pygame.Surface):
        px, py = _field_to_screen(0.0, 0.40)
        py -= 16
        _draw_google_character(surface, px, py, _HELMET_RED, _UNIFORM_W, scale=0.75)

    def _draw_batter(self, surface: pygame.Surface):
        bx = PLATE_X + 28
        by = PLATE_Y - 30
        _draw_google_character(surface, bx, by, _HELMET_BLUE, _UNIFORM_G,
                               scale=1.0, batting_stance=True)


def _draw_google_character(
    surface: pygame.Surface,
    cx: int, cy: int,
    helmet_col: tuple,
    shirt_col:  tuple,
    scale: float = 1.0,
    batting_stance: bool = False,
):
    """Google Baseball-style round cartoon character."""
    s = max(0.5, scale)

    head_r  = int(13 * s)
    body_w  = int(18 * s)
    body_h  = int(16 * s)
    leg_w   = int(5  * s)
    leg_h   = int(14 * s)
    arm_w   = int(4  * s)

    # shadow
    sh = pygame.Surface((head_r * 4, head_r), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 45), sh.get_rect())
    surface.blit(sh, (cx - head_r * 2, cy + body_h + leg_h // 2))

    # legs
    leg_col = _PANTS_GRY
    if batting_stance:
        pygame.draw.rect(surface, leg_col,
                         (cx - body_w // 2 - 2, cy + body_h - 4, leg_w, leg_h + 4),
                         border_radius=3)
        pygame.draw.rect(surface, leg_col,
                         (cx + body_w // 2 - leg_w + 2, cy + body_h - 4, leg_w, leg_h + 4),
                         border_radius=3)
    else:
        pygame.draw.rect(surface, leg_col,
                         (cx - leg_w - 2, cy + body_h - 4, leg_w, leg_h),
                         border_radius=3)
        pygame.draw.rect(surface, leg_col,
                         (cx + 2, cy + body_h - 4, leg_w, leg_h),
                         border_radius=3)

    # body
    body_rect = pygame.Rect(cx - body_w // 2, cy, body_w, body_h)
    pygame.draw.rect(surface, shirt_col, body_rect, border_radius=4)
    pygame.draw.rect(surface, (max(0, shirt_col[0] - 40),
                               max(0, shirt_col[1] - 40),
                               max(0, shirt_col[2] - 40)), body_rect, 1, border_radius=4)

    # arms
    if batting_stance:
        # both arms holding bat (right side)
        for oy in (-4, 2):
            pygame.draw.rect(surface, shirt_col,
                             (cx + body_w // 2, cy + body_h // 2 + oy, int(16 * s), arm_w),
                             border_radius=2)
        # bat
        bat_x = cx + body_w // 2 + int(14 * s)
        pygame.draw.line(surface, (120, 80, 40),
                         (bat_x, cy - int(10 * s)), (bat_x + int(4 * s), cy + int(16 * s)), max(2, int(3 * s)))
    else:
        pygame.draw.rect(surface, shirt_col,
                         (cx - body_w // 2 - int(14 * s), cy + int(4 * s), int(14 * s), arm_w),
                         border_radius=2)
        pygame.draw.rect(surface, shirt_col,
                         (cx + body_w // 2, cy + int(4 * s), int(10 * s), arm_w),
                         border_radius=2)

    # head
    pygame.draw.circle(surface, _SKIN, (cx, cy - head_r + 4), head_r)

    # eyes
    eye_r = max(2, int(2.5 * s))
    pygame.draw.circle(surface, (30, 30, 80), (cx - int(4 * s), cy - head_r + 2), eye_r)
    pygame.draw.circle(surface, (30, 30, 80), (cx + int(4 * s), cy - head_r + 2), eye_r)
    pygame.draw.circle(surface, WHITE,         (cx - int(4 * s) + 1, cy - head_r + 1), max(1, eye_r - 1))
    pygame.draw.circle(surface, WHITE,         (cx + int(4 * s) + 1, cy - head_r + 1), max(1, eye_r - 1))

    # smile
    smile_rect = pygame.Rect(cx - int(5 * s), cy - head_r + int(5 * s), int(10 * s), int(5 * s))
    pygame.draw.arc(surface, (180, 80, 80), smile_rect, math.pi, math.pi * 2, max(1, int(1.5 * s)))

    # helmet (flat cap style)
    helmet_pts = [
        (cx - head_r - int(2 * s), cy - head_r + int(4 * s)),
        (cx + head_r,              cy - head_r + int(4 * s)),
        (cx + head_r,              cy - head_r - int(2 * s)),
        (cx,                       cy - head_r * 2 - int(2 * s)),
        (cx - head_r - int(2 * s), cy - head_r),
    ]
    pygame.draw.polygon(surface, helmet_col, helmet_pts)
    # brim
    pygame.draw.line(surface, (max(0, helmet_col[0] - 30),
                               max(0, helmet_col[1] - 30),
                               max(0, helmet_col[2] - 30)),
                     (cx - head_r - int(2 * s), cy - head_r + int(4 * s)),
                     (cx + head_r + int(6 * s), cy - head_r + int(4 * s)),
                     max(2, int(3 * s)))
