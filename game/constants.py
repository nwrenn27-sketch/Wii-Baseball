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
# Field geometry (pseudo-3D projection)
# ---------------------------------------------------------------------------
HORIZON_Y = 300          # Higher horizon = more overhead/isometric Google Baseball angle
PLATE_Y   = 668          # Home plate slightly lower — ball finishes “in your lap”
# Symmetric catcher / umpire camera — plate centered, look straight at pitcher.
BATTER_VIEW_OFFSET_X = 0
PLATE_X   = SCREEN_W // 2 + BATTER_VIEW_OFFSET_X
FIELD_WIDTH_NEAR  = 700  # Narrower near plate for isometric view
FIELD_WIDTH_FAR   = 40   # Tight vanishing point toward pitcher
PITCHER_DEPTH     = 0.60 # Normalized depth (0=plate, 1=horizon) where pitcher stands
MOUND_Y = int(PLATE_Y - (PLATE_Y - HORIZON_Y) * PITCHER_DEPTH)

# ---------------------------------------------------------------------------
# Colors  (Wii Sports palette)
# ---------------------------------------------------------------------------
WHITE        = (255, 255, 255)
BLACK        = (  0,   0,   0)
SKY_TOP      = ( 92, 185, 255)
SKY_BOT      = (175, 220, 255)
CLOUD_WHITE  = (240, 245, 255)
FIELD_GREEN  = ( 58, 150,  58)
FIELD_DARK   = ( 40, 110,  40)
INFIELD_TAN  = (180, 140,  80)
MOUND_TAN    = (190, 155, 100)
BASELINE_WHT = (230, 230, 210)
BASE_WHITE   = (245, 245, 230)
FOUL_YELLOW  = (220, 200,  60)
CROWD_BLUE   = ( 60, 100, 180)
SHADOW_GRAY  = ( 80,  80,  80, 120)

# Catcher POV field (dirt runway, stadium, grass tiers)
TRACK_TAN_LIGHT = (210, 172, 120)
TRACK_TAN_MID   = (175, 135, 88)
TRACK_TAN_DARK  = (130, 98,  62)
GRASS_HI        = (78,  178, 88)
GRASS_MID       = (52,  142, 62)
GRASS_LO        = (34,  98,  44)
STADIUM_DEEP    = (28,  34,  48)
STADIUM_BAND    = (48,  56,  72)
STADIUM_RAIL    = (90,  98, 115)
CHALK_GLOW      = (255, 252, 245)

# UI
WII_BLUE      = ( 20,  80, 200)
WII_BLUE_LITE = ( 80, 140, 255)
WII_GRAY      = (200, 200, 210)
WII_GRAY_DARK = (120, 120, 135)
WII_YELLOW    = (255, 210,  30)
WII_RED       = (220,  50,  50)
WII_GREEN     = ( 60, 180,  60)
PANEL_BG      = ( 30,  30,  60, 200)
HIT_GOLD      = (255, 200,  20)

# Ball
BALL_WHITE    = (248, 248, 240)
BALL_SEAM     = (200,  60,  60)

# ---------------------------------------------------------------------------
# Pitch data
# Speeds tuned to give ~2 sec travel from mound to plate at 60 FPS.
# x_accel: positive = toward right batter box; y_accel: positive = drop.
# ---------------------------------------------------------------------------
PITCH_TYPES = {
    "fastball": {
        "display":  "Fastball",
        "speed":    0.0180,   # normalized-depth units per frame
        "x_accel":  0.0,
        "y_accel":  0.0003,   # slight natural drop
        "color":    (255, 200,  60),
    },
    "splitter": {
        "display":  "Splitter",
        "speed":    0.0140,
        "x_accel":  0.0,
        "y_accel":  0.0018,   # sharp downward break
        "color":    ( 60, 200, 255),
    },
    "curveball": {
        "display":  "Curveball",
        "speed":    0.0120,
        "x_accel": -0.0012,   # breaks toward right-handed batter
        "y_accel":  0.0008,
        "color":    (255,  80, 200),
    },
    "screwball": {
        "display":  "Screwball",
        "speed":    0.0120,
        "x_accel":  0.0012,   # breaks away from right-handed batter
        "y_accel":  0.0008,
        "color":    (160,  80, 255),
    },
}
PITCH_SEQUENCE = ["fastball", "curveball", "splitter", "screwball"]

# Global pitch speed multiplier (slightly slower flight = easier meter timing)
PITCH_SPEED_SCALE = 0.88

# ---------------------------------------------------------------------------
# Strike zone  (normalized field units; 0,0 = centre of plate)
# ---------------------------------------------------------------------------
STRIKE_ZONE_W = 0.28   # half-width
STRIKE_ZONE_H = 0.22   # half-height

# ---------------------------------------------------------------------------
# Swing detection thresholds
# ---------------------------------------------------------------------------
SWING_VEL_THRESHOLD  = 0.028   # minimum wrist velocity (normalised 0-1 / frame)
SWING_HISTORY_FRAMES = 8       # frames to look back when computing velocity
SWING_COOLDOWN_MS    = 800     # ms before another swing can register

# Timing window (how close ball progress must be to 1.0 for a hit)
HIT_PERFECT_WINDOW  = 0.07
HIT_GOOD_WINDOW     = 0.14
HIT_LATE_WINDOW     = 0.20

# Timing meter (drawn during pitch; needle tracks ball progress 0→plate)
TIMING_METER_MARGIN_BOTTOM = 48
TIMING_METER_W = 520
TIMING_METER_H = 26

# ---------------------------------------------------------------------------
# Base-running
# ---------------------------------------------------------------------------
BASES = ["1B", "2B", "3B", "HOME"]

# ---------------------------------------------------------------------------
# Game rules
# ---------------------------------------------------------------------------
INNINGS       = 9
OUTS_PER_INNING = 3
STRIKES_PER_OUT = 3
BALLS_PER_WALK  = 4

# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------
HIT_LABEL_DURATION_MS = 2200
OUT_LABEL_DURATION_MS = 1800
WIND_UP_MS            = 1200   # pitcher wind-up before releasing ball
PITCH_RELEASE_DELAY_MS = 400   # extra pause between wind-up end and ball spawn

# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------
CALIB_FRAMES = 60  # frames to average during calibration
