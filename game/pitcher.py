"""
AI pitcher for Wii Baseball.

The pitcher cycles through a configurable sequence of pitch types and
adds slight random variation to location so the batter can't time the zone.
It also manages the wind-up animation state (WIND_UP → release → PITCHING).

Pitch selection strategy
------------------------
- Rounds cycle through PITCH_SEQUENCE deterministically for variety.
- Each 3rd pitch the pitcher tries to "waste" a pitch (wider miss of zone).
- If batter has 2 strikes, pitcher favours breaking pitches.
- If batter has 3 balls, pitcher throws more strikes.

# TODO: expose difficulty levels (Easy narrows zone variation, Hard adds deception)
"""

import random
import time

from game.constants import (
    PITCH_TYPES,
    PITCH_SEQUENCE,
    STRIKE_ZONE_W,
    STRIKE_ZONE_H,
    WIND_UP_MS,
    PITCH_RELEASE_DELAY_MS,
)


class Pitcher:
    """
    Manages pitch selection, targeting, and wind-up timing.

    Usage
    -----
    pitcher = Pitcher()
    pitcher.begin_wind_up(strikes, balls)     # start sequence
    if pitcher.is_ready_to_release():         # returns True when wind-up done
        pitch_type, tx, ty = pitcher.get_pitch()
        ball.throw(pitch_type, tx, ty)
        pitcher.on_released()
    """

    # How far outside the zone a "ball" pitch can wander
    _BALL_MARGIN_X = 0.18
    _BALL_MARGIN_Y = 0.12

    # Max random jitter on a strike pitch
    _STRIKE_JITTER_X = 0.10
    _STRIKE_JITTER_Y = 0.06

    def __init__(self):
        self._sequence_idx: int  = 0
        self._pitch_count:  int  = 0

        self._winding_up:  bool  = False
        self._wind_start:  float = 0.0   # time.time() when wind-up began
        self._ready:       bool  = False  # wind-up complete, waiting for release

        self.current_type: str   = "fastball"
        self._target_x:    float = 0.0
        self._target_y:    float = 0.0

        # Wind-up animation progress 0→1
        self.wind_up_progress: float = 0.0

    # ------------------------------------------------------------------
    # Wind-up
    # ------------------------------------------------------------------

    def begin_wind_up(self, strikes: int = 0, balls: int = 0):
        """Start the wind-up phase. Call once per at-bat pitch."""
        self._winding_up       = True
        self._ready            = False
        self.wind_up_progress  = 0.0
        self._wind_start       = time.time()
        self.current_type, self._target_x, self._target_y = (
            self._choose_pitch(strikes, balls)
        )

    def update(self):
        """Call every frame to advance wind-up timer."""
        if not self._winding_up:
            return
        elapsed_ms = (time.time() - self._wind_start) * 1000.0
        total_ms   = WIND_UP_MS + PITCH_RELEASE_DELAY_MS
        self.wind_up_progress = min(1.0, elapsed_ms / total_ms)
        if elapsed_ms >= total_ms:
            self._winding_up = False
            self._ready      = True

    def is_ready_to_release(self) -> bool:
        """True for exactly the first frame after wind-up completes."""
        return self._ready

    def on_released(self):
        """Call immediately after `ball.throw()` to clear the ready flag."""
        self._ready = False
        self._pitch_count += 1

    def get_pitch(self) -> tuple[str, float, float]:
        """Return (pitch_type, target_x, target_y) for `ball.throw()`."""
        return self.current_type, self._target_x, self._target_y

    # ------------------------------------------------------------------
    # Pitch selection
    # ------------------------------------------------------------------

    def _choose_pitch(self, strikes: int, balls: int) -> tuple[str, float, float]:
        """
        Select pitch type and target location based on count context.
        """
        # Decide type
        if strikes == 2:
            # Try to fool the batter with a breaking pitch
            pitch_type = random.choice(["curveball", "screwball", "splitter"])
        elif balls == 3:
            # Groove a fastball to avoid the walk
            pitch_type = "fastball"
        else:
            # Deterministic cycle for variety
            pitch_type = PITCH_SEQUENCE[self._sequence_idx % len(PITCH_SEQUENCE)]
            self._sequence_idx += 1

        # Decide location (strike or ball)
        throw_strike = self._should_throw_strike(strikes, balls)

        if throw_strike:
            # Target inside the strike zone with jitter
            tx = random.uniform(-STRIKE_ZONE_W * 0.7, STRIKE_ZONE_W * 0.7)
            ty = random.uniform(-STRIKE_ZONE_H * 0.6, STRIKE_ZONE_H * 0.6)
        else:
            # Miss the zone intentionally
            side = random.choice([-1, 1])
            tx = side * (STRIKE_ZONE_W + random.uniform(0.04, self._BALL_MARGIN_X))
            ty = random.uniform(
                -STRIKE_ZONE_H - self._BALL_MARGIN_Y,
                 STRIKE_ZONE_H + self._BALL_MARGIN_Y,
            )

        return pitch_type, tx, ty

    @staticmethod
    def _should_throw_strike(strikes: int, balls: int) -> bool:
        """
        Probability matrix for throwing strikes.
        Higher with fewer balls; lower with fewer strikes.
        """
        matrix = {
            # (strikes, balls): probability_of_strike
            (0, 0): 0.65,
            (0, 1): 0.55,
            (0, 2): 0.45,
            (0, 3): 0.85,
            (1, 0): 0.70,
            (1, 1): 0.60,
            (1, 2): 0.50,
            (1, 3): 0.90,
            (2, 0): 0.60,
            (2, 1): 0.55,
            (2, 2): 0.50,
            (2, 3): 0.92,
        }
        prob = matrix.get((min(strikes, 2), min(balls, 3)), 0.60)
        return random.random() < prob
