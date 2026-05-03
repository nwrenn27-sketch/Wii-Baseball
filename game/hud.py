"""
HUD (Heads-Up Display) for Wii Baseball.

Draws:
  • Scoreboard panel (top-left): inning, outs, balls, strikes, score
  • Pitch-type indicator (top-right)
  • Runners-on-base diamond
  • Hit result label (centre, animated fade)
  • Webcam overlay (bottom-right corner)
  • Strike zone hint (fades when ball approaching)

Fonts are loaded from pygame's built-in font system (no external TTF needed).
"""

from typing import Optional
import pygame
import time

from game.constants import (
    SCREEN_W, SCREEN_H,
    WHITE, BLACK,
    WII_BLUE, WII_BLUE_LITE, WII_GRAY, WII_GRAY_DARK,
    WII_YELLOW, WII_RED, WII_GREEN,
    PANEL_BG, HIT_GOLD,
    PITCH_TYPES,
    HIT_LABEL_DURATION_MS,
    OUT_LABEL_DURATION_MS,
    HIT_PERFECT_WINDOW,
    HIT_GOOD_WINDOW,
    TIMING_METER_MARGIN_BOTTOM,
    TIMING_METER_W,
    TIMING_METER_H,
)
from game.batter import (
    Scoreboard,
    OUTCOME_HOME_RUN, OUTCOME_TRIPLE, OUTCOME_DOUBLE,
    OUTCOME_SINGLE, OUTCOME_FOUL, OUTCOME_OUT,
    OUTCOME_STRIKE, OUTCOME_BALL, OUTCOME_WALK,
)

# Overlay dimensions for webcam feed
CAM_OVERLAY_W = 220
CAM_OVERLAY_H = 165
CAM_OVERLAY_X = SCREEN_W - CAM_OVERLAY_W - 10
CAM_OVERLAY_Y = SCREEN_H - CAM_OVERLAY_H - 10

# Label colours
_LABEL_COLOURS = {
    OUTCOME_HOME_RUN: (255, 215,  10),
    OUTCOME_TRIPLE:   (255, 170,  10),
    OUTCOME_DOUBLE:   (100, 220, 255),
    OUTCOME_SINGLE:   ( 80, 220,  80),
    OUTCOME_FOUL:     (255, 180,  40),
    OUTCOME_OUT:      (220,  60,  60),
    OUTCOME_STRIKE:   (255,  55,  55),
    OUTCOME_BALL:     ( 70, 210, 255),
    OUTCOME_WALK:     (120, 255, 120),
}


class HUD:
    def __init__(self):
        pygame.font.init()
        self._font_sm  = pygame.font.SysFont("Arial", 16, bold=True)
        self._font_md  = pygame.font.SysFont("Arial", 22, bold=True)
        self._font_lg  = pygame.font.SysFont("Arial", 38, bold=True)
        self._font_xl  = pygame.font.SysFont("Arial", 64, bold=True)
        self._font_xxl = pygame.font.SysFont("Arial", 86, bold=True)
        self._font_cnt = pygame.font.SysFont("Arial", 28, bold=True)

        self._hit_label:    str   = ""
        self._hit_subtitle: str  = ""
        self._hit_color:    tuple = WHITE
        self._hit_start_ms: float = 0.0
        self._hit_duration: float = HIT_LABEL_DURATION_MS

        # Cached panel surface (re-drawn when state changes)
        self._panel_surf = None  # type: Optional[pygame.Surface]
        self._panel_hash: int = -1

        # Runners diamond pre-rendered coords
        self._diamond_origin = (80, 180)   # top-left of runners widget
        self._d_size = 20
        self._runner_pos = {
            0: (self._diamond_origin[0] + 32, self._diamond_origin[1] + 22),  # 1B
            1: (self._diamond_origin[0] + 16, self._diamond_origin[1] +  4),  # 2B
            2: (self._diamond_origin[0] +  0, self._diamond_origin[1] + 22),  # 3B
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_label(self, label: str, outcome: str = "", duration_ms: float = 0,
                   subtitle: str = ""):
        self._hit_label     = label
        self._hit_subtitle  = subtitle or ""
        self._hit_color     = _LABEL_COLOURS.get(outcome, WHITE)
        self._hit_start_ms  = time.time() * 1000.0
        self._hit_duration  = duration_ms or HIT_LABEL_DURATION_MS

    def draw(self, surface: pygame.Surface, sb: Scoreboard,
             current_pitch_type: str, swing_detector=None):
        """Draw all HUD elements."""
        self._draw_scoreboard(surface, sb)
        self._draw_pitch_indicator(surface, current_pitch_type)
        self._draw_runners(surface, sb.runners)
        self._draw_count_bar(surface, sb)
        self._draw_hit_label(surface)

        # Webcam overlay
        if swing_detector is not None:
            overlay_rect = pygame.Rect(
                CAM_OVERLAY_X, CAM_OVERLAY_Y, CAM_OVERLAY_W, CAM_OVERLAY_H
            )
            # Border
            pygame.draw.rect(surface, WII_BLUE_LITE, overlay_rect.inflate(4, 4), 2)
            try:
                swing_detector.draw_overlay(surface, overlay_rect)
            except Exception:
                pass
            # Label
            lbl = self._font_sm.render("CAMERA", True, WII_GRAY)
            surface.blit(lbl, (CAM_OVERLAY_X + 4, CAM_OVERLAY_Y - 18))

    def draw_timing_meter(self, surface: pygame.Surface, ball_progress: float, ball_active: bool):
        """
        Horizontal meter: needle tracks pitch progress (release → plate).
        Yellow band = good timing window; green = perfect. Commit swing when
        the needle is in those bands at the right moment.
        """
        if not ball_active:
            return

        bx = SCREEN_W // 2 - TIMING_METER_W // 2
        by = SCREEN_H - TIMING_METER_MARGIN_BOTTOM - TIMING_METER_H
        pad = 6
        inner_w = TIMING_METER_W - pad * 2
        top = by + 4
        h_inner = TIMING_METER_H - 8
        left = bx + pad
        right = left + inner_w

        pygame.draw.rect(surface, WII_GRAY_DARK, (bx, by, TIMING_METER_W, TIMING_METER_H), border_radius=8)
        pygame.draw.rect(surface, WII_BLUE_LITE, (bx, by, TIMING_METER_W, TIMING_METER_H), 2, border_radius=8)

        x_good = left + int(max(0.0, 1.0 - HIT_GOOD_WINDOW) * inner_w)
        pygame.draw.rect(
            surface, (210, 170, 50),
            (x_good, top, right - x_good, h_inner),
            border_radius=5,
        )
        x_perf = left + int(max(0.0, 1.0 - HIT_PERFECT_WINDOW) * inner_w)
        pygame.draw.rect(
            surface, (55, 190, 95),
            (x_perf, top, right - x_perf, h_inner),
            border_radius=5,
        )

        prog = max(0.0, min(1.0, ball_progress))
        nx = left + int(prog * inner_w)
        pygame.draw.line(surface, BLACK, (nx, by + 2), (nx, by + TIMING_METER_H - 2), 4)
        pygame.draw.line(surface, WHITE, (nx, by + 2), (nx, by + TIMING_METER_H - 2), 2)

        cap = self._font_sm.render(
            "TIMING — press SPACE (or swing on camera) when needle is in yellow or green",
            True,
            WII_GRAY,
        )
        surface.blit(cap, cap.get_rect(center=(SCREEN_W // 2, by - 14)))

    def draw_calibration_prompt(self, surface: pygame.Surface, progress: float):
        """Show calibration instruction overlay."""
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        title = self._font_xl.render("CALIBRATION", True, WII_YELLOW)
        surface.blit(title, title.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 80)))

        instr = self._font_lg.render("Hold your bat hand up and stay still...", True, WHITE)
        surface.blit(instr, instr.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))

        # Progress bar
        bar_w = 400
        bar_h = 24
        bx = SCREEN_W // 2 - bar_w // 2
        by = SCREEN_H // 2 + 60
        pygame.draw.rect(surface, WII_GRAY_DARK, (bx, by, bar_w, bar_h), border_radius=12)
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            pygame.draw.rect(surface, WII_GREEN, (bx, by, fill_w, bar_h), border_radius=12)
        pygame.draw.rect(surface, WII_BLUE_LITE, (bx, by, bar_w, bar_h), 2, border_radius=12)

        pct = self._font_md.render(f"{int(progress * 100)}%", True, WHITE)
        surface.blit(pct, pct.get_rect(center=(SCREEN_W // 2, by + bar_h // 2)))

    # ------------------------------------------------------------------
    # Private draw methods
    # ------------------------------------------------------------------

    def _draw_scoreboard(self, surface: pygame.Surface, sb: Scoreboard):
        panel = pygame.Surface((160, 110), pygame.SRCALPHA)
        panel.fill(PANEL_BG)

        inning_str = f"{'TOP' if sb.top_inning else 'BOT'} {sb.inning}"
        self._blit_label(panel, inning_str, self._font_sm,  (80, 8),  WII_BLUE_LITE)
        self._blit_label(panel, f"YOU  {sb.player_score:2d}", self._font_md, (80, 28), WII_YELLOW)
        self._blit_label(panel, f"CPU  {sb.cpu_score:2d}",   self._font_md, (80, 52), WII_GRAY)

        # Outs dots
        self._blit_label(panel, "OUTS", self._font_sm, (80, 78), WII_GRAY)
        for i in range(3):
            colour = WII_RED if i < sb.outs else WII_GRAY_DARK
            pygame.draw.circle(panel, colour, (108 + i * 16, 94), 6)

        pygame.draw.rect(panel, WII_BLUE, panel.get_rect(), 2, border_radius=6)
        surface.blit(panel, (10, 10))

    def _draw_pitch_indicator(self, surface: pygame.Surface, pitch_type: str):
        if pitch_type not in PITCH_TYPES:
            return
        pd    = PITCH_TYPES[pitch_type]
        panel = pygame.Surface((160, 40), pygame.SRCALPHA)
        panel.fill(PANEL_BG)
        label = self._font_sm.render(f"PITCH: {pd['display']}", True, pd["color"])
        panel.blit(label, label.get_rect(center=(80, 20)))
        pygame.draw.rect(panel, pd["color"], panel.get_rect(), 2, border_radius=6)
        surface.blit(panel, (SCREEN_W - 170, 10))

    def _draw_runners(self, surface: pygame.Surface, runners: list):
        """Draw runners-on-base diamond widget."""
        ox, oy = 14, 130
        sz = 18
        # Draw diamond shape (home, 1B, 2B, 3B)
        positions = {
            "2B": (ox + 24, oy),
            "1B": (ox + 44, oy + 20),
            "3B": (ox +  4, oy + 20),
            "HP": (ox + 24, oy + 40),
        }
        runner_flags = {
            "1B": runners[0] if len(runners) > 0 else False,
            "2B": runners[1] if len(runners) > 1 else False,
            "3B": runners[2] if len(runners) > 2 else False,
        }
        lines = [("HP","1B"),("1B","2B"),("2B","3B"),("3B","HP")]
        for a, b in lines:
            pygame.draw.line(surface, WII_GRAY_DARK,
                             positions[a], positions[b], 2)
        for base_name, (bx, by) in positions.items():
            if base_name == "HP":
                colour = WII_GRAY_DARK
            else:
                colour = WII_YELLOW if runner_flags.get(base_name) else WII_GRAY_DARK
            pygame.draw.rect(surface, colour,
                             (bx - sz // 2, by - sz // 2, sz, sz), 0)
            pygame.draw.rect(surface, WII_GRAY,
                             (bx - sz // 2, by - sz // 2, sz, sz), 1)

    def _draw_count_bar(self, surface: pygame.Surface, sb: Scoreboard):
        """Balls / Strikes mini-bar."""
        panel = pygame.Surface((200, 36), pygame.SRCALPHA)
        panel.fill(PANEL_BG)

        # Balls
        self._blit_label(panel, "B:", self._font_sm, (12, 18), WII_GREEN, anchor="ml")
        for i in range(4):
            col = WII_GREEN if i < sb.at_bat.balls else WII_GRAY_DARK
            pygame.draw.circle(panel, col, (34 + i * 14, 18), 5)

        # Strikes
        self._blit_label(panel, "S:", self._font_sm, (100, 18), WII_RED, anchor="ml")
        for i in range(3):
            col = WII_RED if i < sb.at_bat.strikes else WII_GRAY_DARK
            pygame.draw.circle(panel, col, (122 + i * 14, 18), 5)

        pygame.draw.rect(panel, WII_BLUE, panel.get_rect(), 1, border_radius=4)
        surface.blit(panel, (10, 120))

    def _draw_hit_label(self, surface: pygame.Surface):
        if not self._hit_label:
            return
        now_ms  = time.time() * 1000.0
        elapsed = now_ms - self._hit_start_ms
        if elapsed > self._hit_duration:
            self._hit_label = ""
            self._hit_subtitle = ""
            return

        # Fade out in last 400 ms
        alpha = 255
        fade_start = self._hit_duration - 400
        if elapsed > fade_start:
            alpha = int(255 * (1.0 - (elapsed - fade_start) / 400))

        # Scale: pop up to 1.15x, then settle
        scale = 1.0
        if elapsed < 150:
            scale = 1.0 + 0.15 * (elapsed / 150)
        elif elapsed < 300:
            scale = 1.15 - 0.15 * ((elapsed - 150) / 150)

        cx = SCREEN_W // 2
        main_font = self._font_xxl if self._hit_label in ("STRIKE", "BALL") else self._font_xl
        txt_surf = main_font.render(self._hit_label, True, self._hit_color)

        if scale != 1.0:
            new_size = (int(txt_surf.get_width() * scale),
                        int(txt_surf.get_height() * scale))
            txt_surf = pygame.transform.scale(txt_surf, new_size)

        txt_surf.set_alpha(alpha)
        cy = SCREEN_H // 2 - 80 if self._hit_subtitle else SCREEN_H // 2 - 60
        rect = txt_surf.get_rect(center=(cx, cy))
        # Panel behind STRIKE/BALL for contrast on busy field
        if self._hit_label in ("STRIKE", "BALL"):
            pad = pygame.Rect(rect).inflate(36, 22)
            bg = pygame.Surface((pad.w, pad.h), pygame.SRCALPHA)
            bg.fill((8, 10, 18, min(200, alpha * 4 // 5)))
            pygame.draw.rect(bg, (255, 255, 255, min(120, alpha // 2)), bg.get_rect(), 3, border_radius=12)
            surface.blit(bg, pad.topleft)

        shadow = main_font.render(self._hit_label, True, BLACK)
        if scale != 1.0:
            shadow = pygame.transform.scale(shadow, (txt_surf.get_width(), txt_surf.get_height()))
        shadow.set_alpha(alpha // 2)
        surface.blit(shadow, (rect.x + 4, rect.y + 4))
        surface.blit(txt_surf, rect)

        if self._hit_subtitle:
            sub = self._font_md.render(self._hit_subtitle, True, WII_GRAY)
            sub.set_alpha(alpha)
            srect = sub.get_rect(center=(cx, rect.bottom + 22))
            surface.blit(sub, srect)

    @staticmethod
    def _blit_label(surf, text, font, pos, color, anchor="center"):
        rendered = font.render(text, True, color)
        rect = rendered.get_rect()
        if anchor == "center":
            rect.center = pos
        elif anchor == "ml":
            rect.midleft = pos
        surf.blit(rendered, rect)
