"""
Batter logic: converts swing events + ball state into hit outcomes.

Hit outcome determination
-------------------------
1. Miss:     swing detected but ball progress < HIT_LATE_WINDOW away from 1.0,
             OR swing detected with no ball active.
2. Foul:     swing within HIT_LATE_WINDOW but outside HIT_GOOD_WINDOW, OR
             swing aimed outside fair territory angle.
3. Single:   swing within HIT_GOOD_WINDOW, low-to-medium velocity.
4. Double:   swing within HIT_GOOD_WINDOW, medium velocity.
5. Triple:   swing within HIT_PERFECT_WINDOW, high velocity.
6. Home run: swing within HIT_PERFECT_WINDOW, very high velocity.

The ball must be in the strike zone (or close) for any "hit" outcome.
A swing on a ball outside the zone can only result in "foul" or "strike".

Base-runner model
-----------------
`runners` is a list of occupied base indices (0=1B, 1=2B, 2=3B).
`advance_runners(bases)` moves each runner forward by `bases` positions;
runners reaching index ≥ 3 score.

# TODO: Add player stamina/fatigue multiplier for late-game precision loss
"""

import random
from dataclasses import dataclass, field

from game.constants import (
    HIT_PERFECT_WINDOW,
    HIT_GOOD_WINDOW,
    HIT_LATE_WINDOW,
    SWING_VEL_THRESHOLD,
    STRIKE_ZONE_W,
    STRIKE_ZONE_H,
)

# Velocity thresholds (normalised mediapipe units / frame)
_VEL_HOME_RUN = 0.090
_VEL_TRIPLE   = 0.070
_VEL_DOUBLE   = 0.050

# Outcome constants
OUTCOME_STRIKE   = "strike"
OUTCOME_BALL     = "ball"
OUTCOME_FOUL     = "foul"
OUTCOME_SINGLE   = "single"
OUTCOME_DOUBLE   = "double"
OUTCOME_TRIPLE   = "triple"
OUTCOME_HOME_RUN = "home_run"
OUTCOME_WALK     = "walk"
OUTCOME_OUT      = "out"


@dataclass
class AtBat:
    """Mutable per-pitch counts."""
    strikes: int = 0
    balls:   int = 0


@dataclass
class Scoreboard:
    """Full game score state."""
    inning:       int        = 1
    top_inning:   bool       = True   # True = top (player bats), False = bottom (CPU)
    outs:         int        = 0
    player_score: int        = 0
    cpu_score:    int        = 0
    # 0=1B, 1=2B, 2=3B; value is True if occupied
    runners:      list       = field(default_factory=lambda: [False, False, False])
    at_bat:       AtBat      = field(default_factory=AtBat)
    inning_over:  bool       = False
    game_over:    bool       = False
    last_outcome: str        = ""
    last_hit_label: str      = ""


class Batter:
    """
    Handles swing resolution and score tracking.

    Usage
    -----
    batter = Batter(scoreboard)
    outcome = batter.resolve_swing(ball, swing_velocity)
    # outcome is one of the OUTCOME_* constants or None if ball not in range
    """

    def __init__(self, scoreboard: Scoreboard):
        self.sb = scoreboard

    # ------------------------------------------------------------------
    # Swing resolution
    # ------------------------------------------------------------------

    def resolve_swing(self, ball, swing_velocity: float) -> str:
        """
        Determine the outcome of a swing event.

        Parameters
        ----------
        ball           : baseball.Ball instance (current pitch in flight)
        swing_velocity : float from SwingDetector.swing_velocity

        Returns
        -------
        One of the OUTCOME_* string constants.
        """
        sb = self.sb
        ab = sb.at_bat

        timing_error = abs(ball.progress - 1.0)   # 0 = perfectly timed
        in_zone = (abs(ball.x) < STRIKE_ZONE_W and abs(ball.y) < STRIKE_ZONE_H)

        # ------ Miss: swing too early or ball not contactable ------
        if timing_error > HIT_LATE_WINDOW:
            return self._apply_strike(OUTCOME_STRIKE)

        # ------ Ball outside zone entirely ------
        if not in_zone and timing_error > HIT_GOOD_WINDOW:
            # Foul tip is still possible on edge pitches
            if timing_error < HIT_LATE_WINDOW * 1.3 and random.random() < 0.3:
                return self._apply_foul()
            return self._apply_strike(OUTCOME_STRIKE)

        # ------ Contact (ball at least near plate) ------
        if timing_error < HIT_PERFECT_WINDOW:
            outcome = self._contact_outcome(swing_velocity, timing_error, perfect=True)
        elif timing_error < HIT_GOOD_WINDOW:
            outcome = self._contact_outcome(swing_velocity, timing_error, perfect=False)
        else:
            # Late/early but still made contact
            if random.random() < 0.55:
                return self._apply_foul()
            return self._apply_strike(OUTCOME_STRIKE)

        return self._apply_hit(outcome)

    def resolve_no_swing(self, ball) -> str:
        """
        Called when the ball reaches home plate with no swing.
        Returns OUTCOME_STRIKE or OUTCOME_BALL.
        """
        if ball.in_zone:
            return self._apply_strike(OUTCOME_STRIKE)
        else:
            return self._apply_ball()

    # ------------------------------------------------------------------
    # Internal outcome helpers
    # ------------------------------------------------------------------

    def _contact_outcome(self, velocity: float, timing_error: float, perfect: bool) -> str:
        # Degrade velocity based on timing imperfection
        effective_vel = velocity * (1.0 - timing_error / HIT_LATE_WINDOW * 0.5)

        if perfect:
            if effective_vel >= _VEL_HOME_RUN:
                return OUTCOME_HOME_RUN
            if effective_vel >= _VEL_TRIPLE:
                return OUTCOME_TRIPLE
            if effective_vel >= _VEL_DOUBLE:
                return OUTCOME_DOUBLE
            return OUTCOME_SINGLE
        else:
            if effective_vel >= _VEL_HOME_RUN:
                return OUTCOME_DOUBLE
            if effective_vel >= _VEL_DOUBLE:
                return OUTCOME_SINGLE
            # Weak contact: chance of foul
            if random.random() < 0.4:
                return OUTCOME_FOUL
            return OUTCOME_SINGLE

    def _apply_hit(self, outcome: str) -> str:
        self.sb.last_outcome   = outcome
        self.sb.last_hit_label = self._label(outcome)

        if outcome == OUTCOME_FOUL:
            return self._apply_foul()

        bases_advanced = {
            OUTCOME_SINGLE:   1,
            OUTCOME_DOUBLE:   2,
            OUTCOME_TRIPLE:   3,
            OUTCOME_HOME_RUN: 4,
        }[outcome]

        runs = self._advance_runners(bases_advanced)
        self.sb.player_score += runs

        # Reset at-bat after a hit
        self.sb.at_bat = AtBat()
        self._check_game_over()
        return outcome

    def _apply_strike(self, outcome: str) -> str:
        self.sb.at_bat.strikes += 1
        self.sb.last_outcome   = outcome
        self.sb.last_hit_label = "STRIKE"
        if self.sb.at_bat.strikes >= 3:
            return self._apply_out()
        return outcome

    def _apply_foul(self) -> str:
        # Foul can't advance you past 2 strikes to 3
        if self.sb.at_bat.strikes < 2:
            self.sb.at_bat.strikes += 1
        self.sb.last_outcome   = OUTCOME_FOUL
        self.sb.last_hit_label = "FOUL"
        return OUTCOME_FOUL

    def _apply_ball(self) -> str:
        self.sb.at_bat.balls += 1
        self.sb.last_outcome  = OUTCOME_BALL
        self.sb.last_hit_label = "BALL"
        if self.sb.at_bat.balls >= 4:
            # Walk: batter takes 1B, force advance runners
            self._apply_walk()
            return OUTCOME_WALK
        return OUTCOME_BALL

    def _apply_out(self) -> str:
        self.sb.outs += 1
        self.sb.at_bat = AtBat()
        self.sb.last_outcome   = OUTCOME_OUT
        self.sb.last_hit_label = "OUT"
        if self.sb.outs >= 3:
            self._end_half_inning()
        self._check_game_over()
        return OUTCOME_OUT

    def _apply_walk(self):
        self.sb.last_hit_label = "WALK"
        # Push runners along: batter to 1B, chain force plays
        force = True
        new_runners = list(self.sb.runners)
        runs = 0
        for base in range(3):
            if force:
                if new_runners[base]:
                    # Force advance
                    if base + 1 >= 3:
                        runs += 1
                        new_runners[base] = False
                    else:
                        new_runners[base + 1] = True
                        new_runners[base]     = False
                else:
                    force = False
        new_runners[0] = True   # batter goes to 1B
        self.sb.runners      = new_runners
        self.sb.player_score += runs
        self.sb.at_bat        = AtBat()

    def _advance_runners(self, bases: int) -> int:
        """Move all runners forward by `bases`.  Returns number of runs scored."""
        runs = 0
        # Process runners from 3B backward to avoid double-advancing
        new_runners = [False, False, False]
        for base_idx in range(2, -1, -1):
            if self.sb.runners[base_idx]:
                new_base = base_idx + bases
                if new_base >= 3:
                    runs += 1
                else:
                    new_runners[new_base] = True

        # Batter goes to `bases` base (or scores on HR)
        if bases < 4:
            new_base = bases - 1
            if new_base >= 3:
                runs += 1
            else:
                new_runners[new_base] = True
        else:
            runs += 1   # batter scores on HR

        self.sb.runners = new_runners
        return runs

    def _end_half_inning(self):
        self.sb.outs        = 0
        self.sb.runners     = [False, False, False]
        self.sb.at_bat      = AtBat()
        self.sb.inning_over = True

        if not self.sb.top_inning:
            self.sb.inning     += 1
            self.sb.top_inning  = True
        else:
            self.sb.top_inning  = False

        from game.constants import INNINGS
        if self.sb.inning > INNINGS:
            self.sb.game_over = True

    def _check_game_over(self):
        from game.constants import INNINGS
        if self.sb.inning > INNINGS:
            self.sb.game_over = True

    @staticmethod
    def _label(outcome: str) -> str:
        return {
            OUTCOME_STRIKE:   "STRIKE",
            OUTCOME_BALL:     "BALL",
            OUTCOME_FOUL:     "FOUL",
            OUTCOME_SINGLE:   "SINGLE!",
            OUTCOME_DOUBLE:   "DOUBLE!",
            OUTCOME_TRIPLE:   "TRIPLE!",
            OUTCOME_HOME_RUN: "HOME RUN!!",
            OUTCOME_WALK:     "WALK",
            OUTCOME_OUT:      "OUT",
        }.get(outcome, outcome.upper())
