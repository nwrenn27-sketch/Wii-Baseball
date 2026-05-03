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
    fn = {"crack":_crack,"crowd":_crowd,"strike":_strike,"ball":_ball,
          "out":_out,"walk":_walk,"home_run":_homerun,"wind_up":_windup,"foul":_foul}.get(name)
    if not fn:
        return None
    try:
        s = np.clip(fn(), -32767, 32767).astype(np.int16)
        return pygame.sndarray.make_sound(s)
    except Exception:
        return None


def _sine(freq, dur, amp=0.5):
    n = int(_SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    w = (np.sin(2 * math.pi * freq * t) * amp * 32767).astype(np.float32)
    return w * np.linspace(1.0, 0.0, n)


def _crack():
    n = int(_SR * 0.12)
    t = np.linspace(0, 0.12, n, endpoint=False)
    w = (np.random.uniform(-1,1,n).astype(np.float32)*0.6 + np.sin(2*math.pi*220*t).astype(np.float32)*0.4)
    return w * np.exp(-t * 60) * 0.8 * 32767

def _crowd():
    n = int(_SR * 1.2)
    t = np.linspace(0, 1.2, n, endpoint=False)
    return np.random.uniform(-1,1,n).astype(np.float32) * np.clip(t*2,0,1) * np.exp(-(t-1.0)**2*5) * 0.35 * 32767

def _strike():
    n = int(_SR * 0.18)
    t = np.linspace(0, 0.18, n, endpoint=False)
    phase = np.cumsum(2 * math.pi * 600 * np.exp(-t*15) / _SR)
    return (np.sin(phase) * np.exp(-t*10) * 0.5 * 32767).astype(np.float32)

def _ball():
    n = int(_SR * 0.10)
    t = np.linspace(0, 0.10, n, endpoint=False)
    return (np.sin(2*math.pi*180*t) * np.exp(-t*40) * 0.4 * 32767).astype(np.float32)

def _out():
    gap = np.zeros(int(_SR * 0.05), dtype=np.float32)
    return np.concatenate([_sine(440,0.15,0.5), gap, _sine(330,0.20,0.5)])

def _walk():
    parts = []
    for f in [330, 392, 494, 523]:
        parts += [_sine(f, 0.12, 0.45), np.zeros(int(_SR*0.02), dtype=np.float32)]
    return np.concatenate(parts)

def _homerun():
    parts = []
    for f in [261, 329, 392, 523, 659]:
        parts += [_sine(f, 0.14, 0.6), np.zeros(int(_SR*0.02), dtype=np.float32)]
    arp = np.concatenate(parts)
    crowd = _crowd()
    out = np.zeros(max(len(arp), len(crowd)), dtype=np.float32)
    out[:len(arp)]   += arp
    out[:len(crowd)] += crowd * 0.5
    return out

def _windup():
    n = int(_SR * 0.25)
    t = np.linspace(0, 0.25, n, endpoint=False)
    phase = np.cumsum(2 * math.pi * (200 + t*400) / _SR)
    env   = np.linspace(0,1,n) * np.linspace(1,0,n)
    return (np.sin(phase) * env * 0.3 * 32767).astype(np.float32)

def _foul():
    gap = np.zeros(int(_SR * 0.04), dtype=np.float32)
    return np.concatenate([_sine(500,0.07,0.4), gap, _sine(450,0.07,0.4)])
