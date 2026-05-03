import math
import time
from collections import deque

import cv2
import mediapipe as mp

from game.constants import SWING_VEL_THRESHOLD, SWING_HISTORY_FRAMES, SWING_COOLDOWN_MS

_HORIZONTAL_BIAS = 1.3


class HandInfo:
    __slots__ = ("wrist", "landmarks", "handedness")
    def __init__(self, wrist, landmarks, handedness):
        self.wrist      = wrist
        self.landmarks  = landmarks
        self.handedness = handedness


class SwingDetector:
    def __init__(self, max_hands: int = 2, flip_camera: bool = True):
        self._mp_hands = mp.solutions.hands
        self._mp_draw  = mp.solutions.drawing_utils
        self._hands    = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=0.60,
            min_tracking_confidence=0.50,
        )
        self.flip_camera         = flip_camera
        self._history            = deque(maxlen=SWING_HISTORY_FRAMES)
        self._calib_samples      = []
        self._calibrating        = False
        self._calib_offset       = (0.0, 0.0)
        self.swing_detected      = False
        self.swing_velocity      = 0.0
        self.swing_angle_deg     = 0.0
        self._last_swing_ms      = 0.0
        self._swing_flash_until  = 0.0
        self.live_velocity       = 0.0   # updated every frame, used for velocity bar
        self.latest_frame        = None
        self.latest_hand_infos   = []

    @property
    def hand_visible(self) -> bool:
        return bool(self.latest_hand_infos)

    def process_frame(self, bgr_frame) -> list:
        if self.flip_camera:
            bgr_frame = cv2.flip(bgr_frame, 1)
        self.latest_frame   = bgr_frame
        self.swing_detected = False

        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._hands.process(rgb)
        rgb.flags.writeable = True

        hand_infos    = []
        primary_wrist = None

        if results.multi_hand_landmarks:
            for lm_set, cls in zip(results.multi_hand_landmarks, results.multi_handedness):
                pts   = [(lm.x, lm.y) for lm in lm_set.landmark]
                wrist = pts[self._mp_hands.HandLandmark.WRIST]
                side  = cls.classification[0].label
                hand_infos.append(HandInfo(wrist, pts, side))
                self._mp_draw.draw_landmarks(
                    bgr_frame, lm_set, self._mp_hands.HAND_CONNECTIONS,
                    self._mp_draw.DrawingSpec(color=(80, 80, 255), thickness=2, circle_radius=3),
                    self._mp_draw.DrawingSpec(color=(200, 200, 255), thickness=1),
                )
            primary_wrist = next((h.wrist for h in hand_infos if h.handedness == "Left"), hand_infos[0].wrist)

        self.latest_hand_infos = hand_infos

        wrist_corrected = None
        if primary_wrist is not None:
            cx, cy = self._calib_offset
            wrist_corrected = (primary_wrist[0] - cx, primary_wrist[1] - cy)

        now_ms = time.time() * 1000.0
        self._history.append((now_ms, wrist_corrected))

        if self._calibrating and wrist_corrected is not None:
            self._calib_samples.append(wrist_corrected)

        self._update_live_velocity()

        if len(self._history) >= SWING_HISTORY_FRAMES:
            self._detect(now_ms)

        return hand_infos

    def start_calibration(self):
        self._calib_samples = []
        self._calibrating   = True

    def finish_calibration(self) -> bool:
        self._calibrating = False
        if len(self._calib_samples) < 10:
            return False
        xs = [s[0] for s in self._calib_samples]
        ys = [s[1] for s in self._calib_samples]
        self._calib_offset = (sum(xs)/len(xs) - 0.5, sum(ys)/len(ys) - 0.5)
        return True

    def draw_overlay(self, surface, dest_rect):
        import pygame
        if self.latest_frame is None:
            return
        frame = cv2.resize(self.latest_frame, (dest_rect.width, dest_rect.height))
        surf  = pygame.surfarray.make_surface(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).swapaxes(0, 1))
        surface.blit(surf, dest_rect.topleft)

        now_ms = time.time() * 1000.0
        flashing = now_ms < self._swing_flash_until

        # Swing flash: bright green border + SWING text
        if flashing:
            t = 1.0 - (now_ms - (self._swing_flash_until - 300)) / 300.0
            alpha = int(255 * max(0.0, t))
            flash = pygame.Surface((dest_rect.width, dest_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(flash, (0, 255, 80, 60), flash.get_rect())
            pygame.draw.rect(flash, (0, 255, 80, alpha), flash.get_rect(), 4)
            surface.blit(flash, dest_rect.topleft)
            fnt = pygame.font.SysFont("Arial", 20, bold=True)
            sw_txt = fnt.render("SWING!", True, (0, 255, 80))
            sw_txt.set_alpha(alpha)
            surface.blit(sw_txt, sw_txt.get_rect(center=(dest_rect.centerx, dest_rect.top + 18)))

        # Velocity bar (bottom of overlay)
        bar_w = dest_rect.width - 12
        bar_h = 8
        bx    = dest_rect.left + 6
        by    = dest_rect.bottom - bar_h - 4
        fill  = int(bar_w * min(1.0, self.live_velocity / (SWING_VEL_THRESHOLD * 2.5)))

        bar_bg = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        bar_bg.fill((0, 0, 0, 140))
        surface.blit(bar_bg, (bx, by))

        if fill > 2:
            r = int(255 * min(1.0, self.live_velocity / SWING_VEL_THRESHOLD))
            g = int(255 * max(0.0, 1.0 - self.live_velocity / SWING_VEL_THRESHOLD))
            bar_col = pygame.Surface((fill, bar_h), pygame.SRCALPHA)
            bar_col.fill((r, g, 40, 210))
            surface.blit(bar_col, (bx, by))

        # Hand tracking status dot
        fnt_s = pygame.font.SysFont("Arial", 12, bold=True)
        dot_col = (50, 230, 80) if self.hand_visible else (220, 60, 60)
        pygame.draw.circle(surface, dot_col, (dest_rect.left + 10, dest_rect.top + 10), 5)
        status = "TRACKING" if self.hand_visible else "NO HAND"
        st = fnt_s.render(status, True, dot_col)
        surface.blit(st, (dest_rect.left + 18, dest_rect.top + 4))

    def release(self):
        self._hands.close()

    def _update_live_velocity(self):
        samples = [(ts, pos) for ts, pos in self._history if pos is not None]
        if len(samples) < 2:
            self.live_velocity = 0.0
            return
        peak = 0.0
        for i in range(1, len(samples)):
            dt = (samples[i][0] - samples[i-1][0]) / 1000.0
            if dt <= 0:
                continue
            dx = samples[i][1][0] - samples[i-1][1][0]
            dy = samples[i][1][1] - samples[i-1][1][1]
            v = math.sqrt(dx*dx + dy*dy) / dt * 0.033  # scale to per-frame equivalent
            peak = max(peak, v)
        self.live_velocity = peak

    def _detect(self, now_ms: float):
        if (now_ms - self._last_swing_ms) <= SWING_COOLDOWN_MS:
            return
        samples = [(ts, pos) for ts, pos in self._history if pos is not None]
        if len(samples) < 3:
            return

        # Peak frame-to-frame velocity (time-normalized)
        peak_vel = 0.0
        for i in range(1, len(samples)):
            dt = (samples[i][0] - samples[i-1][0]) / 1000.0
            if dt <= 0:
                continue
            dx = samples[i][1][0] - samples[i-1][1][0]
            dy = samples[i][1][1] - samples[i-1][1][1]
            v = math.sqrt(dx*dx + dy*dy) / dt * 0.033
            peak_vel = max(peak_vel, v)

        if peak_vel < SWING_VEL_THRESHOLD:
            return

        overall_dx = samples[-1][1][0] - samples[0][1][0]
        overall_dy = samples[-1][1][1] - samples[0][1][1]
        if abs(overall_dx) < abs(overall_dy) * _HORIZONTAL_BIAS:
            return

        self.swing_detected      = True
        self.swing_velocity      = peak_vel
        self.swing_angle_deg     = math.degrees(math.atan2(-overall_dy, overall_dx))
        self._last_swing_ms      = now_ms
        self._swing_flash_until  = now_ms + 300
