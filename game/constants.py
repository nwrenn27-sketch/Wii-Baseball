"""
Game-wide constants for Wii Baseball.
Pitch memory addresses and speed values are informed by wiisports.md Gecko codes:
  fastball  = 0x803C5E5C (0x411CCCCC fast value)
  splitter  = 0x803C5E60
  curveball = 0x803C5E6C
  screwball = 0x803C5E74
  physics   = 0x803C5EAC (0xBD6F9DB2 boost/decay modifier)

# TODO: Add Tennis module (memory map: 0x8038B264 player speed, 0x8038B26C ball speed)
# TODO: Add Bowling module
# TODO: Add Boxing module
"""

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
SCREEN_W = 1280
SCREEN_H = 720
FPS = 60
TITLE = "Wii Baseball"

# ---------------------------------------------------------------------------
# Field geometry  (tuned to match Wii Sports Baseball camera angle)
#
#  z_norm convention used by field_to_screen():
#    0.0  = horizon / far outfield (top of field on screen)
#    1.0  = home plate            (bottom of field on screen)
#
#  Screen Y mapping:
#    HORIZON_Y          → z_norm = 0  (top of green field area)
#    PLATE_Y            → z_norm = 1  (home plate)
# ---------------------------------------------------------------------------
HORIZON_Y         = 188   # px: sky / outfield boundary
PLATE_Y           = 632   # px: home plate position
PLATE_X           = SCREEN_W // 2

FIELD_WIDTH_NEAR  = 660   # px: field width at home plate level
FIELD_WIDTH_FAR   = 72    # px: field width at horizon

# Normalised depth where pitcher's mound sits (0=horizon, 1=plate)
PITCHER_DEPTH_NORM = 0.40

# Derived screen Y of pitcher's mound
MOUND_Y = int(PLATE_Y - (PLATE_Y - HORIZON_Y) * PITCHER_DEPTH_NORM)

# ---------------------------------------------------------------------------
# Colors  (Wii Sports palette)
# ---------------------------------------------------------------------------
WHITE        = (255, 255, 255)
BLACK        = (  0,   0,   0)

# Sky
SKY_TOP      = (110, 198, 255)
SKY_BOT      = (185, 228, 255)
CLOUD_WHITE  = (245, 248, 255)

# Field
FIELD_GREEN  = ( 76, 168,  68)   # main outfield green
FIELD_DARK   = ( 52, 128,  48)   # alternating stripe
FIELD_LITE   = ( 96, 188,  80)   # light stripe
INFIELD_TAN  = (178, 138,  84)   # dirt
MOUND_TAN    = (192, 158, 108)
BASELINE_WHT = (235, 228, 208)
BASE_WHITE   = (248, 246, 232)
FOUL_LINE    = (235, 228, 208)
GRASS_INFIELD= ( 82, 172,  70)   # small grass patch inside diamond

# Stadium
CROWD_BLUE   = ( 55,  90, 175)   # bleacher seats
CROWD_SHADE  = ( 40,  70, 145)
WALL_GREEN   = ( 38, 100,  42)   # outfield wall face
WALL_TOP     = ( 50, 120,  50)
SCOREBOARD_BG= ( 22,  48,  22)
SCOREBOARD_TXT= (255, 220,  30)

# UI  (Wii Sports white-panel style)
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

# Ball
BALL_WHITE    = (250, 248, 242)
BALL_SEAM     = (196,  56,  56)

# Mii skin / uniform colours
MII_SKIN      = (255, 218, 168)
MII_SKIN_SHD  = (230, 188, 138)
MII_HAIR      = ( 60,  40,  20)
MII_EYE       = ( 30,  30,  90)
TEAM_BLUE     = ( 28,  72, 188)   # pitching team jersey
TEAM_RED      = (200,  36,  36)   # batting team jersey
UNIFORM_WHITE = (240, 240, 248)
UNIFORM_GREY  = (180, 182, 195)
CAP_BLUE      = ( 22,  60, 165)
CAP_RED       = (175,  28,  28)

# ---------------------------------------------------------------------------
# Pitch data
# Speeds: ~2 s travel time at 60 FPS.
# x_accel: positive = toward right-handed batter box; y_accel: positive = drop.
# ---------------------------------------------------------------------------
PITCH_TYPES = {
    "fastball": {
        "display":  "Fastball",
        "speed":    0.0185,
        "x_accel":  0.0,
        "y_accel":  0.0002,
        "color":    (255, 200,  60),
    },
    "splitter": {
        "display":  "Splitter",
        "speed":    0.0140,
        "x_accel":  0.0,
        "y_accel":  0.0020,
        "color":    ( 60, 200, 255),
    },
    "curveball": {
        "display":  "Curveball",
        "speed":    0.0122,
        "x_accel": -0.0014,
        "y_accel":  0.0008,
        "color":    (255,  80, 200),
    },
    "screwball": {
        "display":  "Screwball",
        "speed":    0.0122,
        "x_accel":  0.0014,
        "y_accel":  0.0008,
        "color":    (160,  80, 255),
    },
}
PITCH_SEQUENCE = ["fastball", "curveball", "splitter", "screwball"]

# ---------------------------------------------------------------------------
# Strike zone  (normalised field units; 0,0 = centre of plate)
# ---------------------------------------------------------------------------
STRIKE_ZONE_W = 0.27
STRIKE_ZONE_H = 0.20

# ---------------------------------------------------------------------------
# Swing detection
# ---------------------------------------------------------------------------
SWING_VEL_THRESHOLD  = 0.028
SWING_HISTORY_FRAMES = 8
SWING_COOLDOWN_MS    = 800

HIT_PERFECT_WINDOW  = 0.07
HIT_GOOD_WINDOW     = 0.14
HIT_LATE_WINDOW     = 0.20

# ---------------------------------------------------------------------------
# Base-running / rules
# ---------------------------------------------------------------------------
BASES           = ["1B", "2B", "3B", "HOME"]
INNINGS         = 9
OUTS_PER_INNING = 3
STRIKES_PER_OUT = 3
BALLS_PER_WALK  = 4

# ---------------------------------------------------------------------------
# Animation timings
# ---------------------------------------------------------------------------
HIT_LABEL_DURATION_MS  = 2200
OUT_LABEL_DURATION_MS  = 1800
WIND_UP_MS             = 1200
PITCH_RELEASE_DELAY_MS = 350

# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------
CALIB_FRAMES = 60
