import random
import time

from game.constants import (
    PITCH_SEQUENCE, STRIKE_ZONE_W, STRIKE_ZONE_H,
    WIND_UP_MS, PITCH_RELEASE_DELAY_MS,
)

_BALL_MARGIN_X = 0.18
_BALL_MARGIN_Y = 0.12

_STRIKE_MATRIX = {
    (0,0):0.65,(0,1):0.55,(0,2):0.45,(0,3):0.85,
    (1,0):0.70,(1,1):0.60,(1,2):0.50,(1,3):0.90,
    (2,0):0.60,(2,1):0.55,(2,2):0.50,(2,3):0.92,
}


class Pitcher:
    def __init__(self):
        self._seq_idx       = 0
        self._winding_up    = False
        self._wind_start    = 0.0
        self._ready         = False
        self.current_type   = "fastball"
        self._target_x      = 0.0
        self._target_y      = 0.0
        self.wind_up_progress = 0.0

    def begin_wind_up(self, strikes: int = 0, balls: int = 0):
        self._winding_up      = True
        self._ready           = False
        self.wind_up_progress = 0.0
        self._wind_start      = time.time()
        self.current_type, self._target_x, self._target_y = self._choose(strikes, balls)

    def update(self):
        if not self._winding_up:
            return
        elapsed = (time.time() - self._wind_start) * 1000.0
        total   = WIND_UP_MS + PITCH_RELEASE_DELAY_MS
        self.wind_up_progress = min(1.0, elapsed / total)
        if elapsed >= total:
            self._winding_up = False
            self._ready      = True

    def is_ready_to_release(self) -> bool:
        return self._ready

    def on_released(self):
        self._ready = False

    def get_pitch(self) -> tuple[str, float, float]:
        return self.current_type, self._target_x, self._target_y

    def _choose(self, strikes: int, balls: int) -> tuple[str, float, float]:
        if strikes == 2:
            pitch = random.choice(["curveball", "screwball", "splitter"])
        elif balls == 3:
            pitch = "fastball"
        else:
            pitch = PITCH_SEQUENCE[self._seq_idx % len(PITCH_SEQUENCE)]
            self._seq_idx += 1

        prob = _STRIKE_MATRIX.get((min(strikes, 2), min(balls, 3)), 0.60)
        if random.random() < prob:
            tx = random.uniform(-STRIKE_ZONE_W * 0.7, STRIKE_ZONE_W * 0.7)
            ty = random.uniform(-STRIKE_ZONE_H * 0.6, STRIKE_ZONE_H * 0.6)
        else:
            side = random.choice([-1, 1])
            tx = side * (STRIKE_ZONE_W + random.uniform(0.04, _BALL_MARGIN_X))
            ty = random.uniform(-STRIKE_ZONE_H - _BALL_MARGIN_Y, STRIKE_ZONE_H + _BALL_MARGIN_Y)

        return pitch, tx, ty
