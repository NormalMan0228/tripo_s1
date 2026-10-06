"""Soft UI sounds (hover, click, open, close, toast, confirm) synthesised offline.

Wooden ticks and small bell tones that sit under the cozy music. 22.05 kHz mono
16-bit WAV, a few KB each, written to game/assets/sfx/ui/.
Usage: art-venv python tools/build_ui_sounds.py
"""
from pathlib import Path
import wave
import numpy as np

OUT = Path(__file__).resolve().parents[1] / 'game/assets/sfx/ui'
OUT.mkdir(parents=True, exist_ok=True)
SR = 22050
rng = np.random.default_rng(3)


def t(seconds):
    return np.arange(int(SR * seconds)) / SR


def env(x, attack, decay):
    return np.minimum(1, x / max(attack, 1e-4)) * np.exp(-x / decay)


def bell(freq, seconds, decay, partials=((1, 1), (2.01, .35), (3.02, .12))):
    x = t(seconds)
    return sum(a * np.sin(2 * np.pi * freq * m * x) for m, a in partials) * env(x, .002, decay)


def tick(freq, seconds, decay, noise=.5):
    x = t(seconds)
    body = np.sin(2 * np.pi * freq * x) * env(x, .0008, decay)
    n = rng.normal(0, 1, len(x)) * env(x, .0005, decay * .35) * noise
    return body + n


def lowpass(sig, k):
    kernel = np.ones(k) / k
    return np.convolve(sig, kernel, mode='same')


def mix(*parts):
    n = max(len(a) for a in parts)
    return sum(np.pad(a, (0, n - len(a))) for a in parts)


def later(seconds, sig):
    return np.concatenate([np.zeros(int(SR * seconds)), sig])


def save(name, sig, gain=.6):
    sig = sig / max(np.abs(sig).max(), 1e-6) * gain
    fade = np.linspace(1, 0, min(200, len(sig)))
    sig[-len(fade):] *= fade
    data = (sig * 32767).astype(np.int16)
    with wave.open(str(OUT / f'{name}.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(data.tobytes())


save('hover', lowpass(tick(1900, .06, .012, .25), 3), .28)
save('click', mix(lowpass(tick(950, .09, .02, .6), 2), .4 * lowpass(tick(1500, .09, .012, .2), 2)), .55)
x = t(.28)
swish = lowpass(rng.normal(0, 1, len(x)), 9) * np.sin(np.pi * np.clip(x / .28, 0, 1)) ** 2
save('open', mix(swish * .6, later(.05, bell(1175, .23, .09)) * .5), .45)
save('close', mix(swish[::-1] * .6, bell(784, .28, .07) * .35), .38)
save('toast', mix(bell(1319, .45, .16), later(.07, bell(1760, .38, .14)) * .7), .32)
save('confirm', mix(bell(988, .5, .14), later(.08, bell(1319, .42, .15)), later(.16, bell(1976, .34, .12)) * .6), .42)
print(sorted(p.name for p in OUT.glob('*.wav')), sum(p.stat().st_size for p in OUT.glob('*.wav')) // 1024, 'KB')
