"""
Swing detection via MediaPipe Hands + OpenCV.

How it works
------------
1. Each frame the webcam image is passed to `process_frame()`.
2. MediaPipe returns up to 2 hand skeletons (21 landmarks each, x/y in [0,1]).
3. We track the *wrist* landmark across SWING_HISTORY_FRAMES frames.
4. A swing is flagged when:
     • The smoothed wrist velocity exceeds SWING_VEL_THRESHOLD
     • The dominant motion direction is roughly horizontal
       (|dx| > |dy| * SWING_HORIZONTAL_BIAS)
     • A cooldown has elapsed since the last detected swing
5. `swing_velocity` (0-1+) and `swing_angle_deg` are exposed so the batter
   module can use them to scale hit power / direction.

Calibration
-----------
Call `start_calibration()`, collect CALIB_FRAMES frames, then
`finish_calibration()`.  The average resting wrist position is stored and
subtracted from all subsequent position readings so the neutral pose is
centred around (0.5, 0.5) regardless of where the player stands.

# TODO: extend to detect pitch/bowling/punch gestures for Tennis, Bowling, Boxing
"""

import math
import time
from collections import deque

import cv2
import mediapipe as mp

from game.constants import (
    SWING_VEL_THRESHOLD,
    SWING_HISTORY_FRAMES,
    SWING_COOLDOWN_MS,
    CALIB_FRAMES,
)

# How much more horizontal than vertical the motion must be to count as a swing.
SWING_HORIZONTAL_BIAS = 1.3


class HandInfo:
    """Snapshot of one hand's state for a single frame."""
    __slots__ = ("wrist", "landmarks", "handedness")

    def __init__(self, wrist, landmarks, handedness):
        self.wrist      = wrist       # (x, y) normalised [0,1]
        self.landmarks  = landmarks   # list of (x,y) for all 21 points
        self.handedness = handedness  # "Left" or "Right"


class SwingDetector:
    """
    Wraps MediaPipe Hands and computes swing events from wrist velocity.

    Parameters
    ----------
    max_hands : int
        Maximum simultaneous hands MediaPipe tracks (1 or 2).
    flip_camera : bool
        Mirror the frame so it feels like a mirror (default True).
    """

    def __init__(self, max_hands: int = 2, flip_camera: bool = True):
        self._mp_hands = mp.solutions.hands
        self._mp_draw  = mp.solutions.drawing_utils
        self._hands    = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=0.65,
            min_tracking_confidence=0.55,
        )

        self.flip_camera = flip_camera

        # Ring buffer of (timestamp_ms, wrist_xy | None) per frame
        self._history: deque = deque(maxlen=SWING_HISTORY_FRAMES)

        # Calibration
        self._calib_samples: list = []
        self._calibrating: bool   = False
        self._calib_offset: tuple = (0.0, 0.0)  # subtracted from every reading

        # Swing state (reset each frame, set when swing fires)
        self.swing_detected:  bool  = False
        self.swing_velocity:  float = 0.0   # magnitude in normalised units/frame
        self.swing_angle_deg: float = 0.0   # degrees; 0=right, 90=up, -90=down
        self._last_swing_ms:  float = 0.0

        # Exposed for rendering the camera overlay
        self.latest_frame:      any  = None   # BGR frame (possibly flipped)
        self.latest_hand_infos: list = []     # List[HandInfo]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(self, bgr_frame) -> list:
        """
        Process one webcam frame.  Call once per game tick.

        Returns a list of HandInfo objects (may be empty).
        Sets `self.swing_detected` to True for exactly one frame when a
        swing fires.
        """
        if self.flip_camera:
            bgr_frame = cv2.flip(bgr_frame, 1)

        self.latest_frame = bgr_frame
        self.swing_detected = False

        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._hands.process(rgb)
        rgb.flags.writeable = True

        hand_infos: list = []
        primary_wrist = None   # wrist of first detected hand (or best candidate)

        if results.multi_hand_landmarks:
            for lm_set, classification in zip(
                results.multi_hand_landmarks,
                results.multi_handedness,
            ):
                pts = [(lm.x, lm.y) for lm in lm_set.landmark]
                wrist = pts[self._mp_hands.HandLandmark.WRIST]
                side  = classification.classification[0].label  # "Left"/"Right"
                hand_infos.append(HandInfo(wrist, pts, side))

                # Draw skeleton onto the BGR frame for the overlay window
                self._mp_draw.draw_landmarks(
                    bgr_frame, lm_set, self._mp_hands.HAND_CONNECTIONS,
                    self._mp_draw.DrawingSpec(color=(80, 80, 255), thickness=2, circle_radius=3),
                    self._mp_draw.DrawingSpec(color=(200, 200, 255), thickness=1),
                )

            # Prefer the "Right" hand (batting hand); fall back to first
            primary_wrist = None
            for hi in hand_infos:
                # Flipped camera means camera-left = player-right
                if hi.handedness == "Left":
                    primary_wrist = hi.wrist
                    break
            if primary_wrist is None:
                primary_wrist = hand_infos[0].wrist

        self.latest_hand_infos = hand_infos

        # Apply calibration offset
        wrist_corrected = None
        if primary_wrist is not None:
            cx, cy = self._calib_offset
            wrist_corrected = (primary_wrist[0] - cx, primary_wrist[1] - cy)

        now_ms = time.time() * 1000.0
        self._history.append((now_ms, wrist_corrected))

        # Calibration collection
        if self._calibrating and wrist_corrected is not None:
            self._calib_samples.append(wrist_corrected)

        # Detect swing
        if len(self._history) >= SWING_HISTORY_FRAMES:
            self._detect_swing(now_ms)

        return hand_infos

    def start_calibration(self):
        """Begin collecting calibration samples."""
        self._calib_samples = []
        self._calibrating   = True

    def finish_calibration(self) -> bool:
        """
        Compute offset from collected samples.
        Returns True if enough samples were gathered.
        """
        self._calibrating = False
        if len(self._calib_samples) < 10:
            return False
        xs = [s[0] for s in self._calib_samples]
        ys = [s[1] for s in self._calib_samples]
        # Offset so resting position maps to (0.5, 0.5)
        self._calib_offset = (
            sum(xs) / len(xs) - 0.5,
            sum(ys) / len(ys) - 0.5,
        )
        return True

    def reset_calibration(self):
        self._calib_offset = (0.0, 0.0)

    def draw_overlay(self, surface, dest_rect):
        """
        Blit the annotated webcam frame into a pygame Surface at dest_rect.
        dest_rect: pygame.Rect specifying where to draw on the game surface.
        """
        import pygame  # local import to keep this module usable without pygame
        if self.latest_frame is None:
            return
        frame = cv2.resize(self.latest_frame, (dest_rect.width, dest_rect.height))
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
        surface.blit(frame_surface, dest_rect.topleft)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _detect_swing(self, now_ms: float):
        """
        Analyse the wrist position history to detect a swing event.

        Velocity is computed as the Euclidean distance between the oldest and
        newest valid position in the history buffer, divided by the number of
        frames between them.  This gives a per-frame average speed in
        normalised [0,1] coordinates.
        """
        cooldown_ok = (now_ms - self._last_swing_ms) > SWING_COOLDOWN_MS

        samples = [(ts, pos) for ts, pos in self._history if pos is not None]
        if len(samples) < 3 or not cooldown_ok:
            return

        oldest_ts, oldest_pos = samples[0]
        newest_ts,  newest_pos = samples[-1]

        dt_frames = max(1, len(samples) - 1)
        dx = newest_pos[0] - oldest_pos[0]
        dy = newest_pos[1] - oldest_pos[1]
        dist = math.sqrt(dx * dx + dy * dy)
        velocity = dist / dt_frames

        if velocity < SWING_VEL_THRESHOLD:
            return

        # Require primarily horizontal motion (bat swings across the body)
        if abs(dx) < abs(dy) * SWING_HORIZONTAL_BIAS:
            return

        # Swing fires
        self.swing_detected  = True
        self.swing_velocity  = velocity
        self.swing_angle_deg = math.degrees(math.atan2(-dy, dx))  # screen y flipped
        self._last_swing_ms  = now_ms

    def release(self):
        """Release MediaPipe resources."""
        self._hands.close()
