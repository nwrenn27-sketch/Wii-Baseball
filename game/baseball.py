import math

from game.constants import (
    PITCH_TYPES,
    PITCHER_DEPTH_NORM as PITCHER_DEPTH,
    SCREEN_W, HORIZON_Y, PLATE_Y,
    FIELD_WIDTH_NEAR, FIELD_WIDTH_FAR,
    STRIKE_ZONE_W, STRIKE_ZONE_H,
)

_HALF_SCALE = max(STRIKE_ZONE_W * 3, 0.001)


class Ball:
    RADIUS_FAR  = 4
    RADIUS_NEAR = 18

    def __init__(self):
        self.pitch_type = "fastball"
        self.active     = False
        self.progress   = 0.0
        self.x = self.y = 0.0
        self.z = PITCHER_DEPTH
        self._vx = self._vy = self._vz = 0.0
        self._target_x = self._target_y = 0.0
        self.in_zone = False

    def throw(self, pitch_type: str, target_x: float = 0.0, target_y: float = 0.0):
        self.pitch_type = pitch_type
        self.active     = True
        self.progress   = 0.0
        self.in_zone    = False
        self._target_x  = target_x
        self._target_y  = target_y
        pd = PITCH_TYPES[pitch_type]
        self._xa  = pd["x_accel"]
        self._ya  = pd["y_accel"]
        self.z    = PITCHER_DEPTH
        self.x    = 0.0
        self.y    = 0.08
        self._vx  = self._vy = 0.0
        self._vz  = -pd["speed"]

    def update(self):
        if not self.active:
            return
        self._vx += self._xa
        self._vy += self._ya
        self.x   += self._vx
        self.y   += self._vy
        self.z   += self._vz
        self.progress = max(0.0, min(1.0, 1.0 - self.z / PITCHER_DEPTH))
        if self.z <= 0.0:
            self.z = 0.0
            self.active  = False
            self.progress = 1.0
            self.in_zone = (
                abs(self.x - self._target_x) < STRIKE_ZONE_W and
                abs(self.y - self._target_y) < STRIKE_ZONE_H
            )

    def _scale(self):
        t = self.z / PITCHER_DEPTH
        half_w = (FIELD_WIDTH_FAR / 2) + (FIELD_WIDTH_NEAR / 2 - FIELD_WIDTH_FAR / 2) * t
        return half_w / _HALF_SCALE, t

    def get_screen_pos(self) -> tuple[int, int]:
        scale, t = self._scale()
        sx = int(SCREEN_W // 2 + self.x * scale)
        sy = int(PLATE_Y - (PLATE_Y - HORIZON_Y) * (1.0 - t))
        sy -= int(self.y * scale * 0.6)
        return sx, sy

    def get_radius(self) -> int:
        t = max(0.0, min(1.0, self.z / PITCHER_DEPTH))
        return max(2, int(self.RADIUS_FAR + (self.RADIUS_NEAR - self.RADIUS_FAR) * (1.0 - t)))

    def get_shadow_pos(self) -> tuple[int, int]:
        scale, t = self._scale()
        return (
            int(SCREEN_W // 2 + self.x * scale),
            int(PLATE_Y - (PLATE_Y - HORIZON_Y) * (1.0 - t)),
        )
