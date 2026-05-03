import math
import time
from collections import deque
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from game.constants import SWING_VEL_THRESHOLD, SWING_HISTORY_FRAMES, SWING_COOLDOWN_MS

_HORIZONTAL_BIAS = 1.3
_MODEL_PATH = str(Path(__file__).parent.parent / "hand_landmarker.task")

_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]


class HandInfo:
    __slots__ = ("wrist", "landmarks", "handedness")
    def __init__(self, wrist, landmarks, handedness):
        self.wrist      = wrist
        self.landmarks  = landmarks
        self.handedness = handedness


class SwingDetector:
    def __init__(self, max_hands: int = 2, flip_camera: bool = True):
        base_opts = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
        opts = mp_vision.HandLandmarkerOptions(
            base_options=base_opts,
            num_hands=max_hands,
            min_hand_detection_confidence=0.60,
            min_hand_presence_confidence=0.50,
            min_tracking_confidence=0.50,
            running_mode=mp_vision.RunningMode.VIDEO,
        )
        self._landmarker         = mp_vision.HandLandmarker.create_from_options(opts)
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
        self.live_velocity       = 0.0
        self.latest_frame        = None
        self.latest_hand_infos   = []
        self._start_ms           = time.time() * 1000.0

    @property
    def hand_visible(self) -> bool:
        return bool(self.latest_hand_infos)

    def process_frame(self, bgr_frame) -> list:
        if self.flip_camera:
            bgr_frame = cv2.flip(bgr_frame, 1)

        self.swing_detected = False
        now_ms = time.time() * 1000.0
        timestamp_ms = int(now_ms - self._start_ms)

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB,
                            data=cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB))
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        hand_infos    = []
        primary_wrist = None

        if result.hand_landmarks:
            for lm_list, handedness_list in zip(result.hand_landmarks, result.handedness):
                pts   = [(lm.x, lm.y) for lm in lm_list]
                wrist = pts[0]
                side  = handedness_list[0].category_name
                hand_infos.append(HandInfo(wrist, pts, side))
                self._draw_landmarks(bgr_frame, pts)

            primary_wrist = next(
                (h.wrist for h in hand_infos if h.handedness == "Left"),
                hand_infos[0].wrist
            )

        self.latest_frame      = bgr_frame
        self.latest_hand_infos = hand_infos

        wrist_corrected = None
        if primary_wrist is not None:
            cx, cy = self._calib_offset
            wrist_corrected = (primary_wrist[0] - cx, primary_wrist[1] - cy)

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

        now_ms   = time.time() * 1000.0
        flashing = now_ms < self._swing_flash_until

        if flashing:
            t     = 1.0 - (now_ms - (self._swing_flash_until - 300)) / 300.0
            alpha = int(255 * max(0.0, t))
            flash = pygame.Surface((dest_rect.width, dest_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(flash, (0, 255, 80, 60), flash.get_rect())
            pygame.draw.rect(flash, (0, 255, 80, alpha), flash.get_rect(), 4)
            surface.blit(flash, dest_rect.topleft)
            fnt    = pygame.font.SysFont("Arial", 20, bold=True)
            sw_txt = fnt.render("SWING!", True, (0, 255, 80))
            sw_txt.set_alpha(alpha)
            surface.blit(sw_txt, sw_txt.get_rect(center=(dest_rect.centerx, dest_rect.top + 18)))

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

        fnt_s   = pygame.font.SysFont("Arial", 12, bold=True)
        dot_col = (50, 230, 80) if self.hand_visible else (220, 60, 60)
        pygame.draw.circle(surface, dot_col, (dest_rect.left + 10, dest_rect.top + 10), 5)
        status  = "TRACKING" if self.hand_visible else "NO HAND"
        st = fnt_s.render(status, True, dot_col)
        surface.blit(st, (dest_rect.left + 18, dest_rect.top + 4))

    def release(self):
        self._landmarker.close()

    def _draw_landmarks(self, bgr_frame, pts):
        h, w = bgr_frame.shape[:2]
        for a, b in _CONNECTIONS:
            x1, y1 = int(pts[a][0] * w), int(pts[a][1] * h)
            x2, y2 = int(pts[b][0] * w), int(pts[b][1] * h)
            cv2.line(bgr_frame, (x1, y1), (x2, y2), (200, 200, 255), 1)
        for x, y in pts:
            cv2.circle(bgr_frame, (int(x * w), int(y * h)), 3, (80, 80, 255), -1)

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
            v  = math.sqrt(dx*dx + dy*dy) / dt * 0.033
            peak = max(peak, v)
        self.live_velocity = peak

    def _detect(self, now_ms: float):
        if (now_ms - self._last_swing_ms) <= SWING_COOLDOWN_MS:
            return
        samples = [(ts, pos) for ts, pos in self._history if pos is not None]
        if len(samples) < 3:
            return

        peak_vel = 0.0
        for i in range(1, len(samples)):
            dt = (samples[i][0] - samples[i-1][0]) / 1000.0
            if dt <= 0:
                continue
            dx = samples[i][1][0] - samples[i-1][1][0]
            dy = samples[i][1][1] - samples[i-1][1][1]
            v  = math.sqrt(dx*dx + dy*dy) / dt * 0.033
            peak_vel = max(peak_vel, v)

        if peak_vel < SWING_VEL_THRESHOLD:
            return

        overall_dx = samples[-1][1][0] - samples[0][1][0]
        overall_dy = samples[-1][1][1] - samples[0][1][1]
        if abs(overall_dx) < abs(overall_dy) * _HORIZONTAL_BIAS:
            return

        self.swing_detected     = True
        self.swing_velocity     = peak_vel
        self.swing_angle_deg    = math.degrees(math.atan2(-overall_dy, overall_dx))
        self._last_swing_ms     = now_ms
        self._swing_flash_until = now_ms + 300
