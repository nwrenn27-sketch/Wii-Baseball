SCREEN_W = 1280
SCREEN_H = 720
FPS = 60
TITLE = "Wii Baseball"

HORIZON_Y          = 188
PLATE_Y            = 632
PLATE_X            = SCREEN_W // 2
FIELD_WIDTH_NEAR   = 660
FIELD_WIDTH_FAR    = 72
PITCHER_DEPTH_NORM = 0.40
MOUND_Y            = int(PLATE_Y - (PLATE_Y - HORIZON_Y) * PITCHER_DEPTH_NORM)

WHITE        = (255, 255, 255)
BLACK        = (  0,   0,   0)
SKY_TOP      = (110, 198, 255)
SKY_BOT      = (185, 228, 255)
CLOUD_WHITE  = (245, 248, 255)
FIELD_GREEN  = ( 76, 168,  68)
FIELD_DARK   = ( 52, 128,  48)
FIELD_LITE   = ( 96, 188,  80)
INFIELD_TAN  = (178, 138,  84)
MOUND_TAN    = (192, 158, 108)
BASELINE_WHT = (235, 228, 208)
BASE_WHITE   = (248, 246, 232)
FOUL_LINE    = (235, 228, 208)
GRASS_INFIELD= ( 82, 172,  70)
CROWD_BLUE   = ( 55,  90, 175)
CROWD_SHADE  = ( 40,  70, 145)
WALL_GREEN   = ( 38, 100,  42)
WALL_TOP     = ( 50, 120,  50)
SCOREBOARD_BG = ( 22,  48,  22)
SCOREBOARD_TXT= (255, 220,  30)
WII_BLUE      = ( 24,  82, 208)
WII_BLUE_LITE = ( 80, 148, 255)
WII_WHITE     = (248, 248, 255)
WII_GRAY      = (198, 200, 212)
WII_GRAY_DARK = (120, 122, 138)
WII_YELLOW    = (255, 212,  28)
WII_RED       = (218,  48,  48)
WII_GREEN     = ( 58, 182,  58)
WII_ORANGE    = (240, 140,  20)
PANEL_BG      = ( 28,  28,  58, 210)
PANEL_WHITE   = (248, 248, 255, 235)
HIT_GOLD      = (255, 200,  18)
BALL_WHITE    = (250, 248, 242)
BALL_SEAM     = (196,  56,  56)
MII_SKIN      = (255, 218, 168)
MII_SKIN_SHD  = (230, 188, 138)
MII_HAIR      = ( 60,  40,  20)
MII_EYE       = ( 30,  30,  90)
TEAM_BLUE     = ( 28,  72, 188)
TEAM_RED      = (200,  36,  36)
UNIFORM_WHITE = (240, 240, 248)
UNIFORM_GREY  = (180, 182, 195)
CAP_BLUE      = ( 22,  60, 165)
CAP_RED       = (175,  28,  28)

PITCH_TYPES = {
    "fastball": {"display": "Fastball",  "speed": 0.0185, "x_accel":  0.0,    "y_accel": 0.0002, "color": (255, 200,  60)},
    "splitter": {"display": "Splitter",  "speed": 0.0140, "x_accel":  0.0,    "y_accel": 0.0020, "color": ( 60, 200, 255)},
    "curveball":{"display": "Curveball", "speed": 0.0122, "x_accel": -0.0014, "y_accel": 0.0008, "color": (255,  80, 200)},
    "screwball":{"display": "Screwball", "speed": 0.0122, "x_accel":  0.0014, "y_accel": 0.0008, "color": (160,  80, 255)},
}
PITCH_SEQUENCE = ["fastball", "curveball", "splitter", "screwball"]

STRIKE_ZONE_W = 0.27
STRIKE_ZONE_H = 0.20

SWING_VEL_THRESHOLD  = 0.022
SWING_HISTORY_FRAMES = 6
SWING_COOLDOWN_MS    = 700
HIT_PERFECT_WINDOW   = 0.07
HIT_GOOD_WINDOW      = 0.14
HIT_LATE_WINDOW      = 0.20

INNINGS         = 9
OUTS_PER_INNING = 3
STRIKES_PER_OUT = 3
BALLS_PER_WALK  = 4

HIT_LABEL_DURATION_MS  = 2200
OUT_LABEL_DURATION_MS  = 1800
WIND_UP_MS             = 1200
PITCH_RELEASE_DELAY_MS = 350

CALIB_FRAMES = 40
