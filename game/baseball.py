"""
Ball physics for Wii Baseball.

Coordinate system (3-D field space)
------------------------------------
  x  : lateral offset from centre (metres, positive = right from batter POV)
  y  : vertical offset from strike-zone centre (positive = up)
  z  : depth from home plate toward outfield (0 = home plate, 1 = pitcher mound,
       values > 1 continue to outfield)

The ball starts at z=PITCHER_DEPTH (≈0.60) and travels toward z=0.
Progress (float 0→1) tracks how far the ball has moved from its starting depth
to home plate (progress=1.0 means the ball is at z=0, over the plate).

Screen projection
-----------------
`get_screen_pos()` converts (x, y, z) to pixels: pitcher toward the horizon
(top of screen), plate at the bottom — catcher POV. Radius grows sharply as
the ball approaches the plate.
"""

import math
from collections import deque

from game.constants import (
    PITCH_TYPES,
    PITCHER_DEPTH,
    PITCH_SPEED_SCALE,
    PLATE_X,
    HORIZON_Y,
    PLATE_Y,
    FIELD_WIDTH_NEAR,
    FIELD_WIDTH_FAR,
    STRIKE_ZONE_W,
    STRIKE_ZONE_H,
)


class Ball:
    """
    A pitched baseball.

    Attributes exposed for game logic
    ----------------------------------
    progress  : float   0 = just left pitcher's hand, 1 = arrived at plate
    active    : bool    True while the ball is in flight
    in_zone   : bool    True when the ball is in the strike zone at progress=1
    x, y, z   : floats  current 3-D position
    """

    RADIUS_FAR  = 3    # tiny dot at pitcher release
    RADIUS_NEAR = 11   # small at plate

    def __init__(self):
        self.pitch_type: str  = "fastball"
        self.active:     bool = False
        self.progress:   float = 0.0
        self._trail: deque = deque(maxlen=12)
        self._pass_t:    int  = 0   # frames of visual continuation after plate

        # 3-D position
        self.x: float = 0.0   # lateral (field units)
        self.y: float = 0.0   # vertical
        self.z: float = PITCHER_DEPTH

        # Accumulated velocity components (applied each frame)
        self._vx: float = 0.0
        self._vy: float = 0.0
        self._vz: float = 0.0   # always negative (toward plate)

        # Target landing spot (determines in_zone)
        self._target_x: float = 0.0
        self._target_y: float = 0.0

        self.in_zone: bool = False

    # ------------------------------------------------------------------
    # Launch
    # ------------------------------------------------------------------

    def throw(self, pitch_type: str, target_x: float = 0.0, target_y: float = 0.0):
        """
        Initialise a new pitch.

        Parameters
        ----------
        pitch_type : key from PITCH_TYPES
        target_x   : desired plate crossing X (field units, ±STRIKE_ZONE_W is in zone)
        target_y   : desired plate crossing Y (field units, ±STRIKE_ZONE_H is in zone)
        """
        self.pitch_type = pitch_type
        self.active     = True
        self.progress   = 0.0
        self.in_zone    = False
        self._target_x  = target_x
        self._target_y  = target_y

        pd = PITCH_TYPES[pitch_type]
        self._speed  = 0.014           # fixed speed for all pitch types
        self._xa     = pd["x_accel"]
        self._ya     = pd["y_accel"]
        self._trail.clear()
        self._pass_t = 0

        # Start at pitcher's mound, centred
        self.z  = PITCHER_DEPTH
        self.x  = 0.0
        self.y  = 0.08   # slight height above plate level (release height)
        self._vx = 0.0
        self._vy = 0.0
        self._vz = -self._speed   # moving toward plate (z decreases)

    # ------------------------------------------------------------------
    # Update (called every frame)
    # ------------------------------------------------------------------

    def update(self):
        """Advance ball by one frame."""
        # Visual pass-through: continue moving after crossing plate
        if self._pass_t > 0:
            self._pass_t -= 1
            self.z += self._vz
            sx, sy = self.get_screen_pos()
            self._trail.append((sx, sy, self.get_radius()))
            return

        if not self.active:
            return

        self._vx += self._xa
        self._vy += self._ya

        self.x += self._vx
        self.y += self._vy
        pull = 0.012 + 0.26 * ((1.0 - (self.z / PITCHER_DEPTH)) ** 2.4)
        self.x += (self._target_x - self.x) * pull
        self.y += (self._target_y - self.y) * pull

        self.z += self._vz

        self.progress = max(0.0, min(1.0, 1.0 - (self.z / PITCHER_DEPTH)))

        if self.z <= 0.0:
            self.in_zone = (abs(self.x) < STRIKE_ZONE_W and abs(self.y) < STRIKE_ZONE_H)
            self.progress = 1.0
            self.active   = False
            self._pass_t  = 16   # ~0.27 s of visual continuation

        if self.active:
            sx, sy = self.get_screen_pos()
            self._trail.append((sx, sy, self.get_radius()))

    # ------------------------------------------------------------------
    # Screen projection
    # ------------------------------------------------------------------

    def get_screen_pos(self) -> tuple[int, int]:
        """
        Return (screen_x, screen_y) for the current ball position.

        z_norm = 1 - self.z maps z=PITCHER_DEPTH(0.60) → 0.40 (pitcher position)
        and z=0 → 1.0 (plate), aligning the ball with the drawn pitcher character.
        """
        z_norm = 1.0 - self.z   # 0.40 at pitcher, 1.0 at plate
        screen_y = int(HORIZON_Y + (PLATE_Y - HORIZON_Y) * z_norm)

        t = self.z / PITCHER_DEPTH   # 1=pitcher, 0=plate (for half_w interpolation)
        half_w = (FIELD_WIDTH_NEAR / 2) * (1.0 - t) + (FIELD_WIDTH_FAR / 2) * t
        scale  = half_w / max(STRIKE_ZONE_W * 3, 0.001)

        screen_x = int(PLATE_X + self.x * scale)
        screen_y -= int(self.y * scale * 0.62)

        return screen_x, screen_y

    def get_radius(self) -> int:
        """Ball pixel radius — accelerates growth near the plate (toward camera)."""
        t = max(0.0, min(1.0, self.z / PITCHER_DEPTH))
        inv = 1.0 - t
        eased = inv ** 2.05
        r = self.RADIUS_FAR + (self.RADIUS_NEAR - self.RADIUS_FAR) * eased
        return max(2, int(r))

    def get_shadow_pos(self) -> tuple[int, int]:
        """Shadow on the ground (same vertical path as the ball body)."""
        z_norm = 1.0 - self.z
        screen_y = int(HORIZON_Y + (PLATE_Y - HORIZON_Y) * z_norm)
        t = self.z / PITCHER_DEPTH
        half_w = (FIELD_WIDTH_NEAR / 2) * (1.0 - t) + (FIELD_WIDTH_FAR / 2) * t
        screen_x = int(PLATE_X + self.x * (half_w / max(STRIKE_ZONE_W * 3, 0.001)))
        return screen_x, screen_y

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_in_strike_zone_now(self) -> bool:
        """True when ball is within the strike zone (useful during flight)."""
        return (
            abs(self.x) < STRIKE_ZONE_W and
            abs(self.y) < STRIKE_ZONE_H
        )
