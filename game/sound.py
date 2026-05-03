import math
import numpy as np
import pygame

_SR    = 44100
_cache = {}


def init():
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=_SR, size=-16, channels=1, buffer=512)


def play(name: str, volume: float = 1.0):
    if not pygame.mixer.get_init():
        return
    s = _get(name)
    if s:
        s.set_volume(max(0.0, min(1.0, volume)))
        s.play()


def _get(name):
    if name not in _cache:
        _cache[name] = _make(name)
    return _cache[name]


def _make(name):
    fn = {
        "crack":    _crack,
        "crowd":    _crowd,
        "strike":   _strike,
        "ball":     _ball,
        "out":      _out,
        "walk":     _walk,
        "home_run": _homerun,
        "wind_up":  _windup,
        "foul":     _foul,
    }.get(name)
    if not fn:
        return None
    try:
        s = np.clip(fn(), -32767, 32767).astype(np.int16)
        return pygame.sndarray.make_sound(s)
    except Exception:
        return None


# ── helpers ─────────────────────────────────────────────────────────────────

def _t(dur):
    return np.linspace(0, dur, int(_SR * dur), endpoint=False)


def _sine(freq, dur, amp=0.5):
    n = int(_SR * dur)
    t = _t(dur)
    w = np.sin(2 * math.pi * freq * t).astype(np.float32) * amp * 32767
    return w * np.linspace(1.0, 0.0, n)


def _square(freq, dur, amp=0.35):
    t = _t(dur)
    w = np.sign(np.sin(2 * math.pi * freq * t)).astype(np.float32) * amp * 32767
    return w * np.linspace(1.0, 0.0, len(t))


def _chirp(f0, f1, dur, amp=0.4):
    t = _t(dur)
    phase = np.cumsum(2 * math.pi * (f0 + (f1 - f0) * t / max(dur, 1e-6)) / _SR)
    env = np.linspace(1.0, 0.0, len(t))
    return (np.sin(phase) * env * amp * 32767).astype(np.float32)


def _gap(ms):
    return np.zeros(int(_SR * ms / 1000.0), dtype=np.float32)


# ── Google Baseball-style sounds ─────────────────────────────────────────────

def _crack():
    # Bright chiptune "ping" + short noise burst — Google doodle bat crack
    t = _t(0.08)
    ping = np.sin(2 * math.pi * 880 * t).astype(np.float32) * np.exp(-t * 55) * 0.6 * 32767
    noise = np.random.uniform(-1, 1, len(t)).astype(np.float32) * np.exp(-t * 80) * 0.3 * 32767
    return ping + noise


def _crowd():
    # Quick rising cheer swell
    n = int(_SR * 0.9)
    t = np.linspace(0, 0.9, n, endpoint=False)
    env = np.clip(t * 3, 0, 1) * np.exp(-(t - 0.7) ** 2 * 8)
    return np.random.uniform(-1, 1, n).astype(np.float32) * env * 0.4 * 32767


def _strike():
    # Google-style: short descending beep — "bwoop"
    return _chirp(520, 260, 0.18, 0.5)


def _ball():
    # Short soft pop — low tone
    t = _t(0.10)
    return (np.sin(2 * math.pi * 200 * t) * np.exp(-t * 35) * 0.45 * 32767).astype(np.float32)


def _out():
    # Two-note descending chime: G → E
    return np.concatenate([
        _sine(392, 0.14, 0.5), _gap(30),
        _sine(330, 0.18, 0.5),
    ])


def _walk():
    # Four rising bouncy notes — happy chime
    notes = [330, 392, 494, 523]
    parts = []
    for f in notes:
        parts += [_sine(f, 0.10, 0.5), _gap(18)]
    return np.concatenate(parts)


def _homerun():
    # Google doodle ascending fanfare: C-E-G-C octave + crowd swell
    notes = [262, 330, 392, 523, 659, 784]
    parts = []
    for f in notes:
        parts += [_square(f, 0.10, 0.45), _gap(12)]
    arp   = np.concatenate(parts)
    crowd = _crowd() * 0.6
    out   = np.zeros(max(len(arp), len(crowd)), dtype=np.float32)
    out[:len(arp)]   += arp
    out[:len(crowd)] += crowd
    return out


def _windup():
    # Soft rising shimmer while pitcher winds up
    return _chirp(180, 440, 0.22, 0.28)


def _foul():
    # Two-note ping: E → D  (lighter than strike)
    return np.concatenate([
        _sine(500, 0.07, 0.4), _gap(25),
        _sine(420, 0.07, 0.4),
    ])
