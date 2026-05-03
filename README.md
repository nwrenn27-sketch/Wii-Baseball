# Wii Baseball 🏟️

A Python recreation of Wii Sports Baseball using real-time hand tracking instead of a Wii Remote.

| Tech | Role |
|---|---|
| **MediaPipe Hands** | Wrist velocity → swing detection |
| **OpenCV** | Webcam capture + frame processing |
| **Pygame** | Rendering, menus, sound, game loop |
| **NumPy** | Procedural sound synthesis |

---

## Setup

### 1. Prerequisites

- Python 3.10, 3.11, or 3.12
- A webcam (optional — keyboard fallback is built in)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python main.py
```

#### CLI options

| Flag | Effect |
|---|---|
| `--no-camera` | Keyboard-only mode (no webcam required) |
| `--low-fps` | Run at 30 FPS to reduce CPU load |
| `--fullscreen` | Fullscreen window |
| `--innings N` | Play N innings (default 9) |

Quick demo without webcam:
```bash
python main.py --no-camera --innings 3
```

---

## Controls

| Action | Webcam mode | Keyboard fallback |
|---|---|---|
| **Swing** | Move your bat hand fast left → right | `SPACE` |
| **Start / Continue** | — | `SPACE` or `ENTER` |
| **Recalibrate camera** | `C` | `C` |
| **Back to menu / Quit** | `ESC` | `ESC` |

### How to swing (webcam)

1. Hold your dominant hand (bat hand) up in front of the camera.
2. When the ball is approaching home plate, swing your hand quickly from right to left *(mirrored view — moves left → right on screen)*.
3. **Timing matters**: swing just as the ball reaches home plate for the best contact.
4. **Velocity matters**: faster swing → more power → home run potential.

---

## Gameplay

### Pitching
The CPU pitcher throws four pitch types (drawn from Wii Sports Baseball's memory layout):

| Pitch | Behaviour |
|---|---|
| **Fastball** | Straight, fastest, slight natural drop |
| **Splitter** | Sharp downward break at the plate |
| **Curveball** | Breaks toward the right-handed batter |
| **Screwball** | Breaks away from the right-handed batter |

### Hit outcomes

| Outcome | Condition |
|---|---|
| **Strike** | Miss, or no swing on a strike |
| **Ball** | No swing on a pitch outside the zone |
| **Foul** | Late/early contact |
| **Single** | Good contact, lower power |
| **Double** | Good contact, medium power |
| **Triple** | Perfect timing, high power |
| **Home Run** | Perfect timing, very high power |
| **Walk** | 4 balls |

### Scoring
- 3 strikes = out
- 3 outs = half-inning over
- Runners advance based on hit type
- 9 innings (configurable with `--innings`)

---

## Project structure

```
Wii Baseball/
├── main.py                 ← Game loop + state machine
├── requirements.txt
├── README.md
└── game/
    ├── __init__.py
    ├── constants.py        ← All tuneable values in one place
    ├── states.py           ← GameState enum
    ├── swing_detector.py   ← MediaPipe Hands + swing logic
    ├── baseball.py         ← Ball 3D physics + screen projection
    ├── pitcher.py          ← AI pitcher (pitch selection, wind-up)
    ├── batter.py           ← Swing resolution + base-runner model
    ├── sound.py            ← Procedural sound generation
    ├── field.py            ← Pseudo-3D field renderer
    ├── hud.py              ← HUD, scoreboard, hit labels
    └── menu.py             ← Start / between-inning / game-over screens
```

---

## Calibration

On first launch with a webcam the game asks you to hold your bat hand up and stay still for ~1 second. This calibrates the neutral wrist position so the swing detector works regardless of where you stand relative to the camera.

Press **C** at any time during play to recalibrate.

---

## Tuning swing sensitivity

Edit `game/constants.py`:

```python
SWING_VEL_THRESHOLD  = 0.028   # lower = more sensitive (easier to trigger)
SWING_COOLDOWN_MS    = 800     # ms between swings
HIT_PERFECT_WINDOW   = 0.07    # timing tolerance for HR/Triple
HIT_GOOD_WINDOW      = 0.14    # timing tolerance for Double/Single
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: mediapipe` | `pip install mediapipe` |
| Black screen / no camera | Run with `--no-camera` |
| Swings not registering | Lower `SWING_VEL_THRESHOLD` in constants.py, or press C to recalibrate |
| Very slow / low FPS | Run with `--low-fps` |
| MediaPipe model download prompt | First run requires internet; subsequent runs are cached |

---

## Future expansion

The codebase has `# TODO` markers for adding:

- 🎾 **Tennis** — racket-swing detection using the same wrist-velocity system (memory addresses in `game/constants.py` comments)
- 🎳 **Bowling** — underarm throw gesture
- 🥊 **Boxing** — two-hand punch detection

---

## Credits

Pitch speed and type data informed by Wii Sports Baseball Gecko codes from the `mgtaylor2/wii-mods` repository (commit `ae75553`).

Built with Python, MediaPipe, OpenCV, and Pygame.
