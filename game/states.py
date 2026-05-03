"""Game state enum used by the main loop state machine."""

from enum import Enum, auto


class GameState(Enum):
    MENU        = auto()  # Title / start screen
    CALIBRATION = auto()  # One-time camera calibration
    WIND_UP     = auto()  # Pitcher winding up
    PITCHING    = auto()  # Ball in flight
    RESULT      = auto()  # Showing hit/out/ball result label
    HALF_INNING = auto()  # Between half-innings (3 outs)
    GAME_OVER   = auto()  # Final score screen
