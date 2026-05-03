import random
from dataclasses import dataclass, field

from game.constants import (
    HIT_PERFECT_WINDOW, HIT_GOOD_WINDOW, HIT_LATE_WINDOW,
    STRIKE_ZONE_W, STRIKE_ZONE_H, INNINGS,
)

_VEL_HR     = 0.090
_VEL_TRIPLE = 0.070
_VEL_DOUBLE = 0.050

OUTCOME_STRIKE   = "strike"
OUTCOME_BALL     = "ball"
OUTCOME_FOUL     = "foul"
OUTCOME_SINGLE   = "single"
OUTCOME_DOUBLE   = "double"
OUTCOME_TRIPLE   = "triple"
OUTCOME_HOME_RUN = "home_run"
OUTCOME_WALK     = "walk"
OUTCOME_OUT      = "out"

_LABELS = {
    OUTCOME_STRIKE:   "STRIKE",
    OUTCOME_BALL:     "BALL",
    OUTCOME_FOUL:     "FOUL",
    OUTCOME_SINGLE:   "SINGLE!",
    OUTCOME_DOUBLE:   "DOUBLE!",
    OUTCOME_TRIPLE:   "TRIPLE!",
    OUTCOME_HOME_RUN: "HOME RUN!!",
    OUTCOME_WALK:     "WALK",
    OUTCOME_OUT:      "OUT",
}


@dataclass
class AtBat:
    strikes: int = 0
    balls:   int = 0


@dataclass
class Scoreboard:
    inning:         int  = 1
    top_inning:     bool = True
    outs:           int  = 0
    player_score:   int  = 0
    cpu_score:      int  = 0
    runners:        list = field(default_factory=lambda: [False, False, False])
    at_bat:         AtBat = field(default_factory=AtBat)
    inning_over:    bool = False
    game_over:      bool = False
    last_outcome:   str  = ""
    last_hit_label: str  = ""


class Batter:
    def __init__(self, sb: Scoreboard):
        self.sb = sb

    def resolve_swing(self, ball, velocity: float) -> str:
        timing = abs(ball.progress - 1.0)
        in_zone = abs(ball.x) < STRIKE_ZONE_W and abs(ball.y) < STRIKE_ZONE_H

        if timing > HIT_LATE_WINDOW:
            return self._strike()

        if not in_zone and timing > HIT_GOOD_WINDOW:
            if timing < HIT_LATE_WINDOW * 1.3 and random.random() < 0.3:
                return self._foul()
            return self._strike()

        if timing < HIT_PERFECT_WINDOW:
            outcome = self._contact(velocity, timing, perfect=True)
        elif timing < HIT_GOOD_WINDOW:
            outcome = self._contact(velocity, timing, perfect=False)
        else:
            return self._foul() if random.random() < 0.55 else self._strike()

        return self._hit(outcome)

    def resolve_no_swing(self, ball) -> str:
        return self._strike() if ball.in_zone else self._ball()

    def _contact(self, vel: float, timing: float, perfect: bool) -> str:
        ev = vel * (1.0 - timing / HIT_LATE_WINDOW * 0.5)
        if perfect:
            if ev >= _VEL_HR:     return OUTCOME_HOME_RUN
            if ev >= _VEL_TRIPLE: return OUTCOME_TRIPLE
            if ev >= _VEL_DOUBLE: return OUTCOME_DOUBLE
            return OUTCOME_SINGLE
        else:
            if ev >= _VEL_HR:     return OUTCOME_DOUBLE
            if ev >= _VEL_DOUBLE: return OUTCOME_SINGLE
            return OUTCOME_FOUL if random.random() < 0.4 else OUTCOME_SINGLE

    def _hit(self, outcome: str) -> str:
        self.sb.last_outcome   = outcome
        self.sb.last_hit_label = _LABELS[outcome]
        if outcome == OUTCOME_FOUL:
            return self._foul()
        bases = {OUTCOME_SINGLE:1, OUTCOME_DOUBLE:2, OUTCOME_TRIPLE:3, OUTCOME_HOME_RUN:4}[outcome]
        self.sb.player_score += self._advance(bases)
        self.sb.at_bat = AtBat()
        self._check_over()
        return outcome

    def _strike(self) -> str:
        self.sb.at_bat.strikes += 1
        self.sb.last_outcome    = OUTCOME_STRIKE
        self.sb.last_hit_label  = "STRIKE"
        if self.sb.at_bat.strikes >= 3:
            return self._out()
        return OUTCOME_STRIKE

    def _foul(self) -> str:
        if self.sb.at_bat.strikes < 2:
            self.sb.at_bat.strikes += 1
        self.sb.last_outcome   = OUTCOME_FOUL
        self.sb.last_hit_label = "FOUL"
        return OUTCOME_FOUL

    def _ball(self) -> str:
        self.sb.at_bat.balls  += 1
        self.sb.last_outcome   = OUTCOME_BALL
        self.sb.last_hit_label = "BALL"
        if self.sb.at_bat.balls >= 4:
            self._walk()
            return OUTCOME_WALK
        return OUTCOME_BALL

    def _out(self) -> str:
        self.sb.outs          += 1
        self.sb.at_bat         = AtBat()
        self.sb.last_outcome   = OUTCOME_OUT
        self.sb.last_hit_label = "OUT"
        if self.sb.outs >= 3:
            self._end_inning()
        self._check_over()
        return OUTCOME_OUT

    def _walk(self):
        self.sb.last_hit_label = "WALK"
        runs, force = 0, True
        nr = list(self.sb.runners)
        for i in range(3):
            if force:
                if nr[i]:
                    if i + 1 >= 3: runs += 1; nr[i] = False
                    else: nr[i+1] = True; nr[i] = False
                else:
                    force = False
        nr[0] = True
        self.sb.runners      = nr
        self.sb.player_score += runs
        self.sb.at_bat        = AtBat()

    def _advance(self, bases: int) -> int:
        runs, nr = 0, [False, False, False]
        for i in range(2, -1, -1):
            if self.sb.runners[i]:
                nb = i + bases
                if nb >= 3: runs += 1
                else: nr[nb] = True
        if bases < 4:
            nb = bases - 1
            if nb >= 3: runs += 1
            else: nr[nb] = True
        else:
            runs += 1
        self.sb.runners = nr
        return runs

    def _end_inning(self):
        self.sb.outs = 0
        self.sb.runners = [False, False, False]
        self.sb.at_bat = AtBat()
        self.sb.inning_over = True
        if not self.sb.top_inning:
            self.sb.inning    += 1
            self.sb.top_inning = True
        else:
            self.sb.top_inning = False
        if self.sb.inning > INNINGS:
            self.sb.game_over = True

    def _check_over(self):
        if self.sb.inning > INNINGS:
            self.sb.game_over = True
