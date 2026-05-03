import sys
import argparse
import random
import time

import cv2
import pygame

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

    # Auto-detect: scan indices and prefer the highest available one.
    # On macOS with Continuity Camera, index 0 = iPhone (default),
    # index 1 = built-in FaceTime — so prefer the last working index.
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
        self.field  = FieldRenderer()
        self.hud    = HUD()
        self.menu   = MenuRenderer()

        # State
        self.state           = GameState.MENU
        self._result_start   = 0.0
        self._result_dur     = 0.0
        self._calib_frames   = 0
        self._swing_cooldown = False
        self._keyboard_swing = False
        self._calib_skip     = False   # SPACE skips calibration early

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        while True:
            dt = self.clock.tick(self.target_fps)
            self._process_events()
            self._update()
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
                self._calib_skip = True      # skip calibration early
            elif self.state == GameState.HALF_INNING:
                self._begin_wind_up()
            elif self.state == GameState.GAME_OVER:
                self._restart()
            elif self.state == GameState.PITCHING and not self.cam_available:
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
        self.hud.show_pitch_name(pt)
        self.field.pitcher_pose = 'throwing'
        self.state = GameState.PITCHING

    def _on_outcome(self, outcome: str):
        play_outcome_sound(outcome)
        label    = self.sb.last_hit_label
        dur      = OUT_LABEL_DURATION_MS if outcome == OUTCOME_OUT else HIT_LABEL_DURATION_MS
        self.hud.show_label(label, outcome, dur)

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

    def _update(self):
        self.menu.update()
        self.field.update()

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
            # Drive pitcher Mii animation
            p = self.pitcher.wind_up_progress
            self.field.pitcher_pose = 'wind_up' if p < 0.7 else 'throwing'
            if self.pitcher.is_ready_to_release():
                self._on_pitch_released()

        elif self.state == GameState.PITCHING:
            self.ball.update()
            # Pitcher returns to idle after releasing
            self.field.pitcher_pose = 'idle'
            # Batter swing animation fades quickly
            if self.field.batter_swing > 0:
                self.field.batter_swing = max(0.0, self.field.batter_swing - 0.06)

            if swing_fired and not self._swing_cooldown:
                self._swing_cooldown = True
                self.field.batter_swing = 1.0   # trigger batter swing pose
                vel = (self.detector.swing_velocity
                       if self.detector else random.uniform(0.06, 0.10))
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
        self.field.draw(self.screen,
                        player_score=self.sb.player_score,
                        cpu_score=self.sb.cpu_score,
                        inning=self.sb.inning)

        # Trajectory arc (first half of pitch flight)
        if self.state == GameState.PITCHING:
            pt, tx, ty = self.pitcher.get_pitch()
            self.field.draw_trajectory_arc(self.screen, self.ball, tx, ty)

        # Strike zone hint (visible while pitching)
        if self.state == GameState.PITCHING:
            zone_alpha = int(90 + 50 * (1.0 - self.ball.progress))
            self.field.draw_strike_zone(self.screen, zone_alpha)

        # Ball
        self.field.draw_ball(self.screen, self.ball)

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

        # Keyboard-only hint
        if not self.cam_available:
            self._render_kb_hint()

    def _render_wind_up_indicator(self):
        """Subtle 'READY' / 'PITCHING' overlay above pitcher's head."""
        font = pygame.font.SysFont("Arial", 18, bold=True)
        p    = self.pitcher.wind_up_progress
        msg  = "PITCHING..." if p > 0.6 else "READY..."
        txt  = font.render(msg, True, WII_YELLOW)
        txt.set_alpha(int(180 * min(1.0, p * 2)))
        from game.constants import MOUND_Y
        self.screen.blit(txt, txt.get_rect(center=(SCREEN_W // 2, MOUND_Y - 95)))

        # Progress arc
        cx, cy = SCREEN_W // 2, MOUND_Y - 70
        import math
        arc_rect = pygame.Rect(cx - 30, cy - 30, 60, 60)
        if p > 0.01:
            end_angle = -math.pi / 2 + math.pi * 2 * p
            pygame.draw.arc(self.screen, WII_BLUE, arc_rect,
                            -math.pi / 2, end_angle, 5)

    def _render_kb_hint(self):
        font = pygame.font.SysFont("Arial", 16, bold=True)
        hint = font.render("No camera — SPACE to swing", True, (180, 180, 180))
        self.screen.blit(hint, (SCREEN_W - hint.get_width() - 10, SCREEN_H - 30))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()
    game = WiiBaseball(args)
    game.run()
