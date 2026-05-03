"""
Wii Baseball — main entry point.

State machine
-------------
  MENU          → wait for SPACE/ENTER
  CALIBRATION   → collect mediapipe wrist samples for CALIB_FRAMES frames
  WIND_UP       → pitcher animation; transition to PITCHING when ready
  PITCHING      → ball in flight; detect swing or wait for ball to cross plate
  RESULT        → display outcome label; pause briefly, then loop back
  HALF_INNING   → 3 outs reached; show between-innings screen
  GAME_OVER     → final score; SPACE restarts, ESC quits

Camera note
-----------
If no webcam is found, the game falls back to keyboard-only mode:
  SPACE = swing (timing meter at bottom of screen)

Performance
-----------
Webcam processing runs at the game FPS.  MediaPipe is kept at its default
threading model which is adequate for 60 FPS on modern hardware.
To reduce CPU use, pass --low-fps on the command line for 30 FPS mode.

Usage
-----
  python main.py [--low-fps] [--no-camera] [--fullscreen] [--innings N] [--camera N]
"""

import sys
import argparse
import random
import time

import cv2
import pygame

# -- Local modules ----------------------------------------------------------
from game.constants import (
    SCREEN_W, SCREEN_H, FPS, TITLE, INNINGS,
    CALIB_FRAMES, WIND_UP_MS, PITCH_RELEASE_DELAY_MS,
    HIT_LABEL_DURATION_MS, OUT_LABEL_DURATION_MS,
    WHITE, BLACK, WII_BLUE, WII_YELLOW,
)
from game.states         import GameState
from game.swing_detector import SwingDetector
from game.baseball       import Ball
from game.pitcher        import Pitcher
from game.batter         import Batter, Scoreboard, AtBat
from game.batter         import (OUTCOME_OUT, OUTCOME_HOME_RUN, OUTCOME_TRIPLE,
                                  OUTCOME_DOUBLE, OUTCOME_SINGLE, OUTCOME_WALK,
                                  OUTCOME_FOUL, OUTCOME_STRIKE, OUTCOME_BALL)
from game.field          import FieldRenderer
from game.hud            import HUD
from game.menu           import MenuRenderer
from game.runner_anim    import RunnerAnimator, draw_occupied_base_runners
import game.sound        as sound

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Wii Baseball")
    p.add_argument("--low-fps",    action="store_true", help="Run at 30 FPS")
    p.add_argument("--no-camera",  action="store_true", help="Keyboard-only (no webcam)")
    p.add_argument("--fullscreen", action="store_true", help="Fullscreen mode")
    p.add_argument("--innings",    type=int, default=INNINGS, help="Number of innings")
    p.add_argument("--camera",     type=int, default=-1,      help="Camera index (default: auto)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Camera helpers
# ---------------------------------------------------------------------------

def open_camera(no_camera: bool, camera_index: int = -1):
    if no_camera:
        return None, False

    def _try(idx):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS,          30)
            return cap
        cap.release()
        return None

    if camera_index >= 0:
        cap = _try(camera_index)
        return (cap, True) if cap else (None, False)

    # Prefer the last working index (e.g. built-in cam over Continuity on macOS).
    best = None
    for idx in range(4):
        cap = _try(idx)
        if cap:
            if best:
                best.release()
            best = cap
    return (best, True) if best else (None, False)


def read_frame(cap):
    """Read one webcam frame; return None on failure."""
    if cap is None:
        return None
    ret, frame = cap.read()
    return frame if ret else None


# ---------------------------------------------------------------------------
# Sound helpers
# ---------------------------------------------------------------------------

def play_outcome_sound(outcome: str):
    mapping = {
        OUTCOME_HOME_RUN: ("home_run", 0.9),
        OUTCOME_TRIPLE:   ("crack",    0.85),
        OUTCOME_DOUBLE:   ("crack",    0.75),
        OUTCOME_SINGLE:   ("crack",    0.65),
        OUTCOME_FOUL:     ("foul",     0.7),
        OUTCOME_STRIKE:   ("strike",   0.6),
        OUTCOME_BALL:     ("ball",     0.5),
        OUTCOME_OUT:      ("out",      0.7),
        OUTCOME_WALK:     ("walk",     0.65),
    }
    name, vol = mapping.get(outcome, ("ball", 0.5))
    sound.play(name, vol)
    if outcome in (OUTCOME_HOME_RUN, OUTCOME_TRIPLE):
        pygame.time.set_timer(pygame.USEREVENT + 10, 350, loops=1)   # delayed crowd cheer


# ---------------------------------------------------------------------------
# Game class
# ---------------------------------------------------------------------------

class WiiBaseball:
    def __init__(self, args):
        # pygame setup
        pygame.init()
        flags = pygame.FULLSCREEN if args.fullscreen else 0
        self.screen  = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
        pygame.display.set_caption(TITLE)
        self.clock   = pygame.time.Clock()
        self.target_fps = 30 if args.low_fps else FPS

        sound.init()

        # Camera
        self.cap, self.cam_available = open_camera(args.no_camera, args.camera)
        self.detector = SwingDetector(max_hands=2, flip_camera=True) if self.cam_available else None

        # Game objects
        self.ball    = Ball()
        self.pitcher = Pitcher()
        self.sb      = Scoreboard()
        self.batter  = Batter(self.sb)

        # Override innings if CLI arg given
        import game.constants as gc
        if args.innings != INNINGS:
            gc.INNINGS = args.innings

        # Renderers
        self.field       = FieldRenderer()
        self.hud         = HUD()
        self.menu        = MenuRenderer()
        self.runner_anim = RunnerAnimator()

        # State
        self.state           = GameState.MENU
        self._result_start   = 0.0
        self._result_dur     = 0.0
        self._calib_frames   = 0
        self._swing_cooldown = False   # guard double-triggers
        self._keyboard_swing = False   # keyboard fallback flag
        self._calib_skip     = False   # SPACE skips calibration early

        # Keyboard-only swing: track last space press timing
        self._kb_swing_t       = 0.0
        self._kb_swing_pending = False

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        while True:
            dt_ms = float(self.clock.tick(self.target_fps))
            self._process_events()
            self._update(dt_ms)
            self._render()
            pygame.display.flip()

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------

    def _process_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()

            if event.type == pygame.KEYDOWN:
                self._on_keydown(event.key)

            # Delayed crowd cheer trigger
            if event.type == pygame.USEREVENT + 10:
                sound.play("crowd", 0.7)

    def _on_keydown(self, key):
        if key == pygame.K_ESCAPE:
            if self.state == GameState.MENU:
                self._quit()
            else:
                self.state = GameState.MENU

        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            if self.state == GameState.MENU:
                self._start_game()
            elif self.state == GameState.CALIBRATION:
                self._calib_skip = True
            elif self.state == GameState.HALF_INNING:
                self._begin_wind_up()
            elif self.state == GameState.GAME_OVER:
                self._restart()
            elif self.state == GameState.PITCHING and not self.cam_available:
                # Keyboard swing: trigger a swing with the current ball progress
                self._keyboard_swing = True

        elif key == pygame.K_c:
            if self.state not in (GameState.MENU, GameState.GAME_OVER):
                self._start_calibration()

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _start_game(self):
        self.sb = Scoreboard()
        self.batter = Batter(self.sb)
        if self.cam_available:
            self._start_calibration()
        else:
            self._begin_wind_up()

    def _start_calibration(self):
        self.state = GameState.CALIBRATION
        self._calib_frames = 0
        if self.detector:
            self.detector.start_calibration()

    def _begin_wind_up(self):
        self.runner_anim.reset()
        self.state = GameState.WIND_UP
        self.ball.active = False
        self.pitcher.begin_wind_up(self.sb.at_bat.strikes, self.sb.at_bat.balls)
        self._swing_cooldown = False
        self._keyboard_swing = False
        sound.play("wind_up", 0.5)

    def _on_pitch_released(self):
        pt, tx, ty = self.pitcher.get_pitch()
        self.pitcher.on_released()
        self.ball.throw(pt, tx, ty)
        self.state = GameState.PITCHING

    def _on_outcome(self, outcome: str):
        play_outcome_sound(outcome)
        label    = self.sb.last_hit_label
        dur      = OUT_LABEL_DURATION_MS if outcome == OUTCOME_OUT else HIT_LABEL_DURATION_MS
        if outcome in (OUTCOME_STRIKE, OUTCOME_BALL):
            dur = max(dur, 2800)
        sub      = self.sb.call_subtitle
        self.sb.call_subtitle = ""
        self.hud.show_label(label, outcome, dur, sub)

        if self.sb.pending_runner_paths:
            self.runner_anim.start(self.sb.pending_runner_paths)
            self.sb.pending_runner_paths = []

        if self.sb.game_over:
            self.state         = GameState.GAME_OVER
            self._result_start = time.time()
            return

        if self.sb.inning_over:
            self.sb.inning_over = False
            self.state          = GameState.HALF_INNING
            return

        self.state         = GameState.RESULT
        self._result_start = time.time()
        self._result_dur   = dur / 1000.0

    def _restart(self):
        self.state  = GameState.MENU
        self.sb     = Scoreboard()
        self.batter = Batter(self.sb)
        self.ball   = Ball()

    def _quit(self):
        if self.cap:
            self.cap.release()
        if self.detector:
            self.detector.release()
        pygame.quit()
        sys.exit(0)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def _update(self, dt_ms: float):
        self.menu.update()
        self.field.update()
        self.runner_anim.update(dt_ms)

        # Webcam frame (always consume to keep buffer fresh)
        frame = read_frame(self.cap)

        # MediaPipe processing
        swing_fired = False
        if self.detector and frame is not None:
            self.detector.process_frame(frame)
            swing_fired = self.detector.swing_detected

        # Keyboard-only swing fallback
        if self._keyboard_swing:
            swing_fired = True
            self._keyboard_swing = False

        # --- State-specific updates ---
        if self.state == GameState.CALIBRATION:
            self._update_calibration(frame)

        elif self.state == GameState.WIND_UP:
            self.pitcher.update()
            if self.pitcher.is_ready_to_release():
                self._on_pitch_released()

        elif self.state == GameState.PITCHING:
            self.ball.update()

            if swing_fired and not self._swing_cooldown:
                self._swing_cooldown = True
                vel = (
                    self.detector.swing_velocity
                    if self.detector
                    else random.uniform(0.06, 0.10)
                )
                outcome = self.batter.resolve_swing(self.ball, vel)
                self.ball.active = False
                self._on_outcome(outcome)

            elif not self.ball.active:
                # Ball reached home plate without a swing
                outcome = self.batter.resolve_no_swing(self.ball)
                self._on_outcome(outcome)

        elif self.state == GameState.RESULT:
            if time.time() - self._result_start >= self._result_dur:
                self._begin_wind_up()

    def _update_calibration(self, frame):
        if frame is None or self._calib_skip:
            self._calib_skip = False
            self._begin_wind_up()
            return

        self._calib_frames += 1
        progress = min(1.0, self._calib_frames / CALIB_FRAMES)

        if self._calib_frames >= CALIB_FRAMES:
            if self.detector:
                self.detector.finish_calibration()
            self._begin_wind_up()

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render(self):
        if self.state == GameState.MENU:
            self.menu.draw_start_menu(self.screen)
            return

        if self.state == GameState.GAME_OVER:
            self.menu.draw_game_over(self.screen, self.sb.player_score, self.sb.cpu_score)
            return

        if self.state == GameState.HALF_INNING:
            self.menu.draw_half_inning(
                self.screen, self.sb.inning, self.sb.top_inning,
                self.sb.player_score, self.sb.cpu_score
            )
            return

        # --- Playing field ---
        self.field.draw(self.screen)

        # Strike zone hint (visible while pitching)
        if self.state == GameState.PITCHING:
            # Keep zone readable whole flight; brighten slightly as pitch arrives
            zone_alpha = int(105 + 75 * (1.0 - self.ball.progress))
            zone_alpha = min(220, zone_alpha)
            self.field.draw_strike_zone(self.screen, zone_alpha)

        # Ball
        self.field.draw_ball(self.screen, self.ball)

        # Runners standing on bases (hide while hit-replay animation is playing)
        if self.state in (GameState.WIND_UP, GameState.PITCHING):
            draw_occupied_base_runners(self.screen, self.sb.runners)
        elif self.state == GameState.RESULT and not self.runner_anim.active:
            draw_occupied_base_runners(self.screen, self.sb.runners)

        # Runner animation (after hits, during RESULT)
        self.runner_anim.draw(self.screen)

        # Pitcher wind-up indicator
        if self.state == GameState.WIND_UP:
            self._render_wind_up_indicator()

        # Calibration overlay
        if self.state == GameState.CALIBRATION:
            progress = min(1.0, self._calib_frames / CALIB_FRAMES)
            self.hud.draw_calibration_prompt(self.screen, progress)
            return

        # HUD (after field so it renders on top)
        self.hud.draw(
            self.screen, self.sb,
            self.pitcher.current_type,
            self.detector,
        )

        if self.state == GameState.PITCHING:
            self.hud.draw_timing_meter(
                self.screen, self.ball.progress, self.ball.active
            )

        # Keyboard-only hint
        if not self.cam_available:
            self._render_kb_hint()

    def _render_wind_up_indicator(self):
        """Show a subtle wind-up progress arc above the pitcher."""
        font = pygame.font.SysFont("Arial", 20, bold=True)
        p    = self.pitcher.wind_up_progress
        msgs = ["READY...", "SET...", "WINDING UP..."]
        idx  = min(len(msgs) - 1, int(p * len(msgs)))
        surf = font.render(msgs[idx], True, WII_YELLOW)

        from game.constants import MOUND_Y, PLATE_X
        surface = self.screen
        surface.blit(surf, surf.get_rect(center=(PLATE_X, MOUND_Y - 40)))

        # Progress arc
        cx, cy = PLATE_X, MOUND_Y - 70
        import math
        arc_rect = pygame.Rect(cx - 30, cy - 30, 60, 60)
        if p > 0.01:
            end_angle = -math.pi / 2 + math.pi * 2 * p
            pygame.draw.arc(self.screen, WII_BLUE, arc_rect,
                            -math.pi / 2, end_angle, 5)

    def _render_kb_hint(self):
        font = pygame.font.SysFont("Arial", 16, bold=True)
        hint = font.render("No camera — SPACE when timing needle is in yellow/green", True, (180, 180, 180))
        self.screen.blit(hint, (SCREEN_W - hint.get_width() - 10, SCREEN_H - 82))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()
    game = WiiBaseball(args)
    game.run()
