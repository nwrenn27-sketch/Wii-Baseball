import math
import time
from collections import deque

import cv2
import mediapipe as mp

from game.constants import SWING_VEL_THRESHOLD, SWING_HISTORY_FRAMES, SWING_COOLDOWN_MS

_HORIZONTAL_BIAS = 1.3  # |dx| must exceed |dy| by this factor to count as a swing


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
            min_detection_confidence=0.65,
            min_tracking_confidence=0.55,
        )
        self.flip_camera      = flip_camera
        self._history         = deque(maxlen=SWING_HISTORY_FRAMES)
        self._calib_samples   = []
        self._calibrating     = False
        self._calib_offset    = (0.0, 0.0)
        self.swing_detected   = False
        self.swing_velocity   = 0.0
        self.swing_angle_deg  = 0.0
        self._last_swing_ms   = 0.0
        self.latest_frame     = None
        self.latest_hand_infos = []

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
            # flipped camera: camera-left = player-right (batting hand)
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

    def release(self):
        self._hands.close()

    def _detect(self, now_ms: float):
        if (now_ms - self._last_swing_ms) <= SWING_COOLDOWN_MS:
            return
        samples = [(ts, pos) for ts, pos in self._history if pos is not None]
        if len(samples) < 3:
            return
        dx  = samples[-1][1][0] - samples[0][1][0]
        dy  = samples[-1][1][1] - samples[0][1][1]
        vel = math.sqrt(dx*dx + dy*dy) / max(1, len(samples) - 1)
        if vel < SWING_VEL_THRESHOLD:
            return
        if abs(dx) < abs(dy) * _HORIZONTAL_BIAS:
            return
        self.swing_detected  = True
        self.swing_velocity  = vel
        self.swing_angle_deg = math.degrees(math.atan2(-dy, dx))
        self._last_swing_ms  = now_ms
