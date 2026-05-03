"""
Menu screens for Wii Baseball.

Screens implemented
-------------------
  draw_start_menu()       – title screen, waits for SPACE / Enter
  draw_half_inning()      – "Change sides" between innings
  draw_game_over()        – final score + win/loss message + restart prompt

All screens use Wii Sports-inspired rounded panels and a blue gradient bg.

# TODO: Add sport-select hub screen (Baseball, Tennis, Bowling, Boxing)
"""

import math
import pygame

from game.constants import (
    SCREEN_W, SCREEN_H,
    WHITE, BLACK,
    WII_BLUE, WII_BLUE_LITE, WII_YELLOW, WII_RED, WII_GREEN, WII_GRAY,
    PANEL_BG, FIELD_GREEN, SKY_TOP,
)


class MenuRenderer:
    def __init__(self):
        pygame.font.init()
        self._font_sm  = pygame.font.SysFont("Arial", 18, bold=True)
        self._font_md  = pygame.font.SysFont("Arial", 26, bold=True)
        self._font_lg  = pygame.font.SysFont("Arial", 44, bold=True)
        self._font_xl  = pygame.font.SysFont("Arial", 72, bold=True)
        self._font_xxl = pygame.font.SysFont("Arial", 96, bold=True)
        self._tick: float = 0.0

    def update(self):
        self._tick += 0.04

    def draw_start_menu(self, surface: pygame.Surface):
        """Draw the animated title / start screen."""
        self._draw_bg(surface)

        # Title card
        card_rect = pygame.Rect(SCREEN_W // 2 - 340, 100, 680, 260)
        self._draw_panel(surface, card_rect)

        # "Wii" in blue
        wii_txt = self._font_xxl.render("Wii", True, WII_BLUE_LITE)
        surface.blit(wii_txt, wii_txt.get_rect(center=(SCREEN_W // 2 - 130, 200)))

        # "Baseball" in white with outline
        for offset in [(2,2),(-2,-2),(2,-2),(-2,2)]:
            bs = self._font_xxl.render("Baseball", True, BLACK)
            surface.blit(bs, bs.get_rect(center=(SCREEN_W // 2 + 90 + offset[0],
                                                  210 + offset[1])))
        bs = self._font_xxl.render("Baseball", True, WHITE)
        surface.blit(bs, bs.get_rect(center=(SCREEN_W // 2 + 90, 210)))

        # Tagline
        tag = self._font_md.render("Hand-Tracking Edition · Powered by MediaPipe", True, WII_GRAY)
        surface.blit(tag, tag.get_rect(center=(SCREEN_W // 2, 310)))

        # Pulsing prompt
        alpha = int(128 + 127 * math.sin(self._tick * 2))
        prompt = self._font_lg.render("Press SPACE or ENTER to Play", True, WII_YELLOW)
        prompt.set_alpha(alpha)
        surface.blit(prompt, prompt.get_rect(center=(SCREEN_W // 2, 430)))

        # Controls box
        ctrl_rect = pygame.Rect(SCREEN_W // 2 - 280, 500, 560, 160)
        self._draw_panel(surface, ctrl_rect, alpha=180)
        controls = [
            ("Swing",       "Move bat hand fast (left→right)"),
            ("Calibrate",   "C  — recalibrate camera"),
            ("Quit",        "ESC"),
        ]
        for i, (key, desc) in enumerate(controls):
            k_surf = self._font_md.render(key + ":", True, WII_BLUE_LITE)
            d_surf = self._font_sm.render(desc, True, WII_GRAY)
            y = ctrl_rect.top + 18 + i * 42
            surface.blit(k_surf, (ctrl_rect.left + 16, y))
            surface.blit(d_surf, (ctrl_rect.left + 130, y + 6))

    def draw_half_inning(self, surface: pygame.Surface, inning: int, top: bool,
                         player_score: int, cpu_score: int):
        """Show between-innings message."""
        self._draw_bg(surface)
        card = pygame.Rect(SCREEN_W // 2 - 300, SCREEN_H // 2 - 140, 600, 280)
        self._draw_panel(surface, card)

        half = "TOP" if top else "BOTTOM"
        h_txt = self._font_xl.render(f"{half} OF INNING {inning}", True, WII_YELLOW)
        surface.blit(h_txt, h_txt.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 70)))

        sc_txt = self._font_lg.render(
            f"You {player_score}  –  CPU {cpu_score}", True, WHITE)
        surface.blit(sc_txt, sc_txt.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 10)))

        alpha = int(128 + 127 * math.sin(self._tick * 2))
        prompt = self._font_md.render("Press SPACE to continue", True, WII_GRAY)
        prompt.set_alpha(alpha)
        surface.blit(prompt, prompt.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 80)))

    def draw_game_over(self, surface: pygame.Surface,
                       player_score: int, cpu_score: int):
        """Final score screen."""
        self._draw_bg(surface)

        won = player_score > cpu_score

        card = pygame.Rect(SCREEN_W // 2 - 340, 80, 680, 480)
        self._draw_panel(surface, card)

        result_color = WII_GREEN if won else WII_RED
        result_text  = "YOU WIN!" if won else "GAME OVER"
        if player_score == cpu_score:
            result_color = WII_YELLOW
            result_text  = "TIE GAME"

        r_surf = self._font_xxl.render(result_text, True, result_color)
        surface.blit(r_surf, r_surf.get_rect(center=(SCREEN_W // 2, 180)))

        # Score
        sc_surf = self._font_xl.render(
            f"YOU {player_score}  –  CPU {cpu_score}", True, WHITE)
        surface.blit(sc_surf, sc_surf.get_rect(center=(SCREEN_W // 2, 290)))

        # Flavour
        if won:
            flavour = "Outstanding batting performance!"
        elif player_score == cpu_score:
            flavour = "What a close game!"
        else:
            flavour = "Better luck next time!"
        fl_surf = self._font_md.render(flavour, True, WII_GRAY)
        surface.blit(fl_surf, fl_surf.get_rect(center=(SCREEN_W // 2, 370)))

        # Prompts
        pr_surf = self._font_md.render("SPACE / ENTER — Play Again     ESC — Quit", True, WII_GRAY)
        alpha = int(128 + 127 * math.sin(self._tick * 2))
        pr_surf.set_alpha(alpha)
        surface.blit(pr_surf, pr_surf.get_rect(center=(SCREEN_W // 2, 470)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _draw_bg(self, surface: pygame.Surface):
        for y in range(SCREEN_H):
            t = y / SCREEN_H
            r = int(SKY_TOP[0] * (1 - t) + WII_BLUE[0] * t)
            g = int(SKY_TOP[1] * (1 - t) + WII_BLUE[1] * t)
            b = int(SKY_TOP[2] * (1 - t) + WII_BLUE[2] * t)
            pygame.draw.line(surface, (r, g, b), (0, y), (SCREEN_W, y))

    @staticmethod
    def _draw_panel(surface: pygame.Surface, rect: pygame.Rect, alpha: int = 200):
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((20, 30, 60, alpha))
        pygame.draw.rect(panel, WII_BLUE_LITE, panel.get_rect(), 2, border_radius=14)
        surface.blit(panel, rect.topleft)
