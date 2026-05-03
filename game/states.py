from enum import Enum, auto

class GameState(Enum):
    MENU        = auto()
    CALIBRATION = auto()
    WIND_UP     = auto()
    PITCHING    = auto()
    RESULT      = auto()
    HALF_INNING = auto()
    GAME_OVER   = auto()
