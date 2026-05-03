"""
Sound manager for Wii Baseball.

All sounds are generated procedurally using numpy + pygame.sndarray so no
external audio assets are required.  Sounds are generated once on first use
and cached.

Sound design
------------
  crack   – short transient burst simulating bat-on-ball contact
  crowd   – crowd cheer for big hits
  strike  – low "whoosh" for a missed swing
  ball    – soft pop when called ball
  out     – game-show-style descending tone
  walk    – ascending short jingle
  home_run– fanfare chord
  wind_up – subtle pitch-up sound for pitcher animation

# TODO: Replace procedural sounds with sampled WAV files when assets are available
# TODO: Add Tennis racket / Bowling pin sounds in future sport modules
"""

import math
from typing import Optional
import numpy as np
import pygame

_SAMPLE_RATE = 44100
_CHANNELS    = 1        # mono

_cache: dict = {}


def init():
    """Initialise pygame mixer.  Call once before any play() calls."""
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=_SAMPLE_RATE, size=-16, channels=_CHANNELS, buffer=512)


def play(name: str, volume: float = 1.0):
    """Play a named sound effect.  Silently skips if pygame.mixer not ready."""
    if not pygame.mixer.get_init():
        return
    sound = _get(name)
    if sound:
        sound.set_volume(max(0.0, min(1.0, volume)))
        sound.play()


# ------------------------------------------------------------------
# Sound generation
# ------------------------------------------------------------------

def _get(name: str) -> Optional[object]:
    if name not in _cache:
        _cache[name] = _generate(name)
    return _cache[name]


def _generate(name: str) -> Optional[object]:
    generators = {
        "crack":    _gen_crack,
        "crowd":    _gen_crowd,
        "strike":   _gen_strike,
        "ball":     _gen_ball,
        "out":      _gen_out,
        "walk":     _gen_walk,
        "home_run": _gen_home_run,
        "wind_up":  _gen_wind_up,
        "foul":     _gen_foul,
    }
    gen = generators.get(name)
    if gen is None:
        return None
    try:
        samples = gen()
        samples = np.clip(samples, -32767, 32767).astype(np.int16)
        sound = pygame.sndarray.make_sound(samples)
        return sound
    except Exception:
        return None


def _sine(freq, duration, amp=0.5, fade_out=True):
    n = int(_SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    wave = (np.sin(2 * math.pi * freq * t) * amp * 32767).astype(np.float32)
    if fade_out:
        env = np.linspace(1.0, 0.0, n)
        wave *= env
    return wave


def _noise(duration, amp=0.3):
    n = int(_SAMPLE_RATE * duration)
    return (np.random.uniform(-1, 1, n) * amp * 32767).astype(np.float32)


def _gen_crack():
    # Sharp transient: noise burst + tone click
    n = int(_SAMPLE_RATE * 0.12)
    t = np.linspace(0, 0.12, n, endpoint=False)
    noise = np.random.uniform(-1, 1, n).astype(np.float32)
    tone  = np.sin(2 * math.pi * 220 * t).astype(np.float32)
    env   = np.exp(-t * 60)
    wave  = (noise * 0.6 + tone * 0.4) * env * 0.8 * 32767
    return wave.astype(np.float32)


def _gen_crowd():
    # Rising crowd noise
    n = int(_SAMPLE_RATE * 1.2)
    t = np.linspace(0, 1.2, n, endpoint=False)
    noise = np.random.uniform(-1, 1, n).astype(np.float32)
    env   = np.clip(t * 2, 0, 1) * np.exp(-(t - 1.0) ** 2 * 5)
    wave  = noise * env * 0.35 * 32767
    return wave.astype(np.float32)


def _gen_strike():
    # Whoosh
    n = int(_SAMPLE_RATE * 0.18)
    t = np.linspace(0, 0.18, n, endpoint=False)
    freq = 600 * np.exp(-t * 15)
    phase = np.cumsum(2 * math.pi * freq / _SAMPLE_RATE)
    wave  = np.sin(phase).astype(np.float32)
    env   = np.exp(-t * 10) * 0.5
    return (wave * env * 32767).astype(np.float32)


def _gen_ball():
    # Soft pop
    n = int(_SAMPLE_RATE * 0.10)
    t = np.linspace(0, 0.10, n, endpoint=False)
    wave = np.sin(2 * math.pi * 180 * t).astype(np.float32)
    env  = np.exp(-t * 40) * 0.4
    return (wave * env * 32767).astype(np.float32)


def _gen_out():
    # Two descending tones
    s1 = _sine(440, 0.15, 0.5)
    s2 = _sine(330, 0.20, 0.5)
    gap = np.zeros(int(_SAMPLE_RATE * 0.05), dtype=np.float32)
    return np.concatenate([s1, gap, s2])


def _gen_walk():
    freqs = [330, 392, 494, 523]
    parts = []
    for f in freqs:
        parts.append(_sine(f, 0.12, 0.45))
        parts.append(np.zeros(int(_SAMPLE_RATE * 0.02), dtype=np.float32))
    return np.concatenate(parts)


def _gen_home_run():
    # Triumphant ascending arpeggio + crowd
    freqs = [261, 329, 392, 523, 659]
    parts = []
    for f in freqs:
        parts.append(_sine(f, 0.14, 0.6))
        parts.append(np.zeros(int(_SAMPLE_RATE * 0.02), dtype=np.float32))
    arp  = np.concatenate(parts)
    crowd = _gen_crowd()
    total = max(len(arp), len(crowd))
    out   = np.zeros(total, dtype=np.float32)
    out[:len(arp)]   += arp
    out[:len(crowd)] += crowd * 0.5
    return out


def _gen_wind_up():
    # Short rising pitch
    n = int(_SAMPLE_RATE * 0.25)
    t = np.linspace(0, 0.25, n, endpoint=False)
    freq = 200 + t * 400
    phase = np.cumsum(2 * math.pi * freq / _SAMPLE_RATE)
    wave  = np.sin(phase).astype(np.float32)
    env   = np.linspace(0, 1, n) * np.linspace(1, 0, n)
    return (wave * env * 0.3 * 32767).astype(np.float32)


def _gen_foul():
    # Quick double-blip
    s1 = _sine(500, 0.07, 0.4)
    s2 = _sine(450, 0.07, 0.4)
    gap = np.zeros(int(_SAMPLE_RATE * 0.04), dtype=np.float32)
    return np.concatenate([s1, gap, s2])
