"""
HUD for Wii Baseball — styled to match Wii Sports Baseball's UI.

Layout mirrors the real game:
  ┌─────────────────────────────────────────────────────────────┐
  │  [PITCH label top-left]    [B•• S•• O••  centre]  [INN top-right] │
  └─────────────────────────────────────────────────────────────┘

  Runners-on-base diamond  (bottom-left)
  Hit result label          (centre, large animated pop)
  Webcam overlay            (bottom-right corner)

All panels use white rounded rectangles with subtle drop-shadow,
matching the Wii Sports aesthetic.
"""

from typing import Optional
import math
import time
import pygame

from game.constants import (
    SCREEN_W, SCREEN_H,
    WHITE, BLACK,
    WII_BLUE, WII_BLUE_LITE, WII_WHITE, WII_GRAY, WII_GRAY_DARK,
    WII_YELLOW, WII_RED, WII_GREEN, WII_ORANGE,
    PANEL_WHITE, HIT_GOLD,
    PITCH_TYPES,
    HIT_LABEL_DURATION_MS, OUT_LABEL_DURATION_MS,
    TEAM_BLUE, TEAM_RED,
)
from game.batter import (
    Scoreboard,
    OUTCOME_HOME_RUN, OUTCOME_TRIPLE, OUTCOME_DOUBLE,
    OUTCOME_SINGLE, OUTCOME_FOUL, OUTCOME_OUT,
    OUTCOME_STRIKE, OUTCOME_BALL, OUTCOME_WALK,
)

# Webcam overlay
_CAM_W = 200
_CAM_H = 150
_CAM_X = SCREEN_W - _CAM_W - 12
_CAM_Y = SCREEN_H - _CAM_H - 12

# Outcome colours
_LABEL_COLORS = {
    OUTCOME_HOME_RUN: (255, 210,  15),
    OUTCOME_TRIPLE:   (255, 160,  15),
    OUTCOME_DOUBLE:   ( 60, 200, 255),
    OUTCOME_SINGLE:   ( 60, 210,  60),
    OUTCOME_FOUL:     (255, 175,  35),
    OUTCOME_OUT:      (215,  55,  55),
    OUTCOME_STRIKE:   (215,  55,  55),
    OUTCOME_BALL:     (190, 190, 210),
    OUTCOME_WALK:     (100, 240, 100),
}


def _white_panel(surf: pygame.Surface, rect: pygame.Rect, radius: int = 10):
    """Draw a white rounded panel with a blue border and soft drop shadow."""
    # Shadow
    shad = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(shad, (0, 0, 0, 60), shad.get_rect().inflate(4, 4), border_radius=radius + 2)
    surf.blit(shad, (rect.x + 2, rect.y + 3))
    # Panel body
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill((0, 0, 0, 0))
    pygame.draw.rect(panel, (248, 248, 255, 235), panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, WII_BLUE, panel.get_rect(), 2, border_radius=radius)
    surf.blit(panel, rect.topleft)


class HUD:
    def __init__(self):
        pygame.font.init()
        self._f_sm  = pygame.font.SysFont("Arial", 15, bold=True)
        self._f_md  = pygame.font.SysFont("Arial", 20, bold=True)
        self._f_lg  = pygame.font.SysFont("Arial", 32, bold=True)
        self._f_xl  = pygame.font.SysFont("Arial", 58, bold=True)
        self._f_cnt = pygame.font.SysFont("Arial", 24, bold=True)

        self._label:    str   = ""
        self._label_col: tuple = WHITE
        self._label_t0: float  = 0.0
        self._label_dur: float = HIT_LABEL_DURATION_MS

        # Pitch-type name shown briefly after wind-up
        self._pitch_label:    str   = ""
        self._pitch_label_t0: float = 0.0
        self._pitch_label_dur: float = 1600.0   # ms

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_label(self, text: str, outcome: str = "", duration_ms: float = 0):
        self._label     = text
        self._label_col = _LABEL_COLORS.get(outcome, WHITE)
        self._label_t0  = time.time() * 1000.0
        self._label_dur = duration_ms or HIT_LABEL_DURATION_MS

    def show_pitch_name(self, pitch_type: str):
        pd = PITCH_TYPES.get(pitch_type, {})
        self._pitch_label     = pd.get("display", "")
        self._pitch_label_t0  = time.time() * 1000.0

    def draw(self, surface: pygame.Surface, sb: Scoreboard,
             current_pitch_type: str, swing_detector=None):

        self._draw_bso_bar(surface, sb)
        self._draw_inning_panel(surface, sb)
        self._draw_pitch_type(surface, current_pitch_type)
        self._draw_runners(surface, sb.runners)
        self._draw_pitch_name_label(surface)
        self._draw_hit_label(surface)

        if swing_detector is not None:
            self._draw_cam_overlay(surface, swing_detector)

    def draw_calibration_prompt(self, surface: pygame.Surface, progress: float):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 168))
        surface.blit(overlay, (0, 0))

        title = self._f_xl.render("CALIBRATION", True, WII_YELLOW)
        surface.blit(title, title.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 90)))

        instr = self._f_lg.render("Raise your bat hand and hold still", True, WHITE)
        surface.blit(instr, instr.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 10)))

        bw, bh = 380, 22
        bx = SCREEN_W // 2 - bw // 2
        by = SCREEN_H // 2 + 52
        pygame.draw.rect(surface, WII_GRAY_DARK, (bx, by, bw, bh), border_radius=11)
        fw = int(bw * max(0, min(1, progress)))
        if fw > 4:
            pygame.draw.rect(surface, WII_GREEN, (bx, by, fw, bh), border_radius=11)
        pygame.draw.rect(surface, WII_BLUE_LITE, (bx, by, bw, bh), 2, border_radius=11)
        pct = self._f_md.render(f"{int(progress * 100)}%", True, WHITE)
        surface.blit(pct, pct.get_rect(center=(SCREEN_W // 2, by + bh // 2)))

    # ------------------------------------------------------------------
    # Private drawing methods
    # ------------------------------------------------------------------

    def _draw_bso_bar(self, surf: pygame.Surface, sb: Scoreboard):
        """
        Centre-top BSO panel — matches Wii Sports' classic layout.
        Format:  BALL ●●○○  STRIKE ●●○  OUT ●○○
        """
        pw, ph = 360, 42
        px = SCREEN_W // 2 - pw // 2
        py = 8
        rect = pygame.Rect(px, py, pw, ph)
        _white_panel(surf, rect, radius=12)

        # --- BALLS ---
        lbl = self._f_sm.render("BALL", True, WII_BLUE)
        surf.blit(lbl, (px + 14, py + 6))
        for i in range(4):
            col = WII_GREEN if i < sb.at_bat.balls else (210, 212, 225)
            pygame.draw.circle(surf, col, (px + 14 + i * 16, py + 28), 6)
            pygame.draw.circle(surf, (140, 142, 158), (px + 14 + i * 16, py + 28), 6, 1)

        # --- STRIKES ---
        lbl = self._f_sm.render("STRIKE", True, WII_BLUE)
        surf.blit(lbl, (px + 108, py + 6))
        for i in range(3):
            col = WII_RED if i < sb.at_bat.strikes else (210, 212, 225)
            pygame.draw.circle(surf, col, (px + 108 + i * 16, py + 28), 6)
            pygame.draw.circle(surf, (140, 142, 158), (px + 108 + i * 16, py + 28), 6, 1)

        # --- OUTS ---
        lbl = self._f_sm.render("OUT", True, WII_BLUE)
        surf.blit(lbl, (px + 210, py + 6))
        for i in range(3):
            col = WII_ORANGE if i < sb.outs else (210, 212, 225)
            pygame.draw.circle(surf, col, (px + 210 + i * 16, py + 28), 6)
            pygame.draw.circle(surf, (140, 142, 158), (px + 210 + i * 16, py + 28), 6, 1)

        # Vertical dividers
        for dx in [96, 196, 288]:
            pygame.draw.line(surf, (190, 192, 210),
                             (px + dx, py + 6), (px + dx, py + ph - 6), 1)

    def _draw_inning_panel(self, surf: pygame.Surface, sb: Scoreboard):
        """Top-right panel: inning + score."""
        pw, ph = 168, 58
        px = SCREEN_W - pw - 10
        py = 8
        rect = pygame.Rect(px, py, pw, ph)
        _white_panel(surf, rect, radius=10)

        half   = "▲" if sb.top_inning else "▼"
        inn_t  = self._f_sm.render(f"{half} {sb.inning}", True, WII_BLUE)
        surf.blit(inn_t, inn_t.get_rect(center=(px + pw // 2, py + 12)))

        score_t = self._f_cnt.render(
            f"YOU  {sb.player_score:2d}  –  CPU  {sb.cpu_score:2d}",
            True, (30, 30, 60))
        surf.blit(score_t, score_t.get_rect(center=(px + pw // 2, py + 36)))

    def _draw_pitch_type(self, surf: pygame.Surface, pitch_type: str):
        """Small top-left pill showing current pitch type with its colour."""
        pd = PITCH_TYPES.get(pitch_type)
        if not pd:
            return
        pw, ph = 140, 30
        px, py = 10, 10
        rect = pygame.Rect(px, py, pw, ph)

        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.rect(panel, (0, 0, 0, 140), panel.get_rect(), border_radius=15)
        pygame.draw.rect(panel, pd["color"], panel.get_rect(), 2, border_radius=15)
        surf.blit(panel, rect.topleft)

        lbl = self._f_sm.render(pd["display"], True, WHITE)
        surf.blit(lbl, lbl.get_rect(center=(px + pw // 2, py + ph // 2)))

    def _draw_runners(self, surf: pygame.Surface, runners: list):
        """
        Runners-on-base diamond widget, bottom-left.
        Matches Wii Sports' rotated-square diamond with yellow = occupied.
        """
        ox, oy = 18, SCREEN_H - 110
        sz = 18
        gap = 34
        # Diamond positions (screen): 2B top, 1B right, 3B left, HP bottom
        pos = {
            "2B": (ox + gap, oy),
            "1B": (ox + gap * 2, oy + gap),
            "HP": (ox + gap, oy + gap * 2),
            "3B": (ox,       oy + gap),
        }
        run = {"1B": runners[0] if runners else False,
               "2B": runners[1] if len(runners) > 1 else False,
               "3B": runners[2] if len(runners) > 2 else False}

        # Connecting lines
        order = ["HP", "1B", "2B", "3B", "HP"]
        for i in range(len(order) - 1):
            pygame.draw.line(surf, (180, 182, 200),
                             pos[order[i]], pos[order[i + 1]], 2)

        for base, (bx, by) in pos.items():
            filled = run.get(base, False)
            col = WII_YELLOW if filled else (210, 212, 230)
            pts = [(bx, by - sz // 2), (bx + sz // 2, by),
                   (bx, by + sz // 2), (bx - sz // 2, by)]
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, WII_BLUE if filled else (150, 152, 170),
                                 pts, 2)

    def _draw_pitch_name_label(self, surf: pygame.Surface):
        """Brief pitch-type announcement fading out after wind-up."""
        if not self._pitch_label:
            return
        elapsed = time.time() * 1000.0 - self._pitch_label_t0
        if elapsed > self._pitch_label_dur:
            self._pitch_label = ""
            return
        alpha = int(255 * max(0.0, 1.0 - elapsed / self._pitch_label_dur))
        txt = self._f_lg.render(self._pitch_label, True, WII_YELLOW)
        txt.set_alpha(alpha)
        surf.blit(txt, txt.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 80)))

    def _draw_hit_label(self, surf: pygame.Surface):
        if not self._label:
            return
        elapsed = time.time() * 1000.0 - self._label_t0
        if elapsed > self._label_dur:
            self._label = ""
            return

        # Pop scale: burst to 1.18x, settle back to 1.0x
        if elapsed < 140:
            scale = 1.0 + 0.18 * (elapsed / 140)
        elif elapsed < 300:
            scale = 1.18 - 0.18 * ((elapsed - 140) / 160)
        else:
            scale = 1.0

        fade_start = self._label_dur - 400
        alpha = 255 if elapsed < fade_start else int(
            255 * (1.0 - (elapsed - fade_start) / 400))

        # Shadow
        shd = self._f_xl.render(self._label, True, BLACK)
        if scale != 1.0:
            ns = (int(shd.get_width() * scale), int(shd.get_height() * scale))
            shd = pygame.transform.smoothscale(shd, ns)
        shd.set_alpha(alpha // 2)
        cx, cy = SCREEN_W // 2, SCREEN_H // 2 - 55
        surf.blit(shd, shd.get_rect(center=(cx + 3, cy + 3)))

        # Text
        txt = self._f_xl.render(self._label, True, self._label_col)
        if scale != 1.0:
            ns = (int(txt.get_width() * scale), int(txt.get_height() * scale))
            txt = pygame.transform.smoothscale(txt, ns)
        txt.set_alpha(alpha)
        surf.blit(txt, txt.get_rect(center=(cx, cy)))

    def _draw_cam_overlay(self, surf: pygame.Surface, detector):
        rect = pygame.Rect(_CAM_X, _CAM_Y, _CAM_W, _CAM_H)
        # Border
        border = pygame.Surface((_CAM_W + 4, _CAM_H + 4), pygame.SRCALPHA)
        pygame.draw.rect(border, (0, 0, 0, 120), border.get_rect(), border_radius=6)
        pygame.draw.rect(border, WII_BLUE_LITE, border.get_rect(), 2, border_radius=6)
        surf.blit(border, (rect.x - 2, rect.y - 2))
        # Camera image
        try:
            detector.draw_overlay(surf, rect)
        except Exception:
            pass
        # Label
        lbl = self._f_sm.render("CAM", True, WII_GRAY)
        surf.blit(lbl, (rect.x + 4, rect.y - 17))
