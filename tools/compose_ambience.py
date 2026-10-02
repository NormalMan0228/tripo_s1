"""Original loopable game music, synthesized without external samples or services."""
from array import array
from math import exp, sin, cos, pi
from pathlib import Path
import wave

RATE = 22050
SECONDS = 32
COUNT = RATE * SECONDS
ROOT = Path(__file__).resolve().parents[1]

def frequency(midi):
    return 440 * 2 ** ((midi - 69) / 12)

def note(track, start, length, midi, gain, pad=False):
    """Wrapping tails across sample zero makes the arrangement a genuine loop."""
    hz = frequency(midi)
    begin = round(start * RATE)
    frames = round(length * RATE)
    for i in range(frames):
        t = i / RATE
        if pad:
            envelope = sin(pi * i / frames) ** 2
            tone = sin(2*pi*hz*t)*0.8 + sin(2*pi*hz*1.0015*t)*0.2
        else:
            envelope = min(1, t/0.014) * exp(-t*2.3) * min(1,(length-t)/0.07)
            tone = sin(2*pi*hz*t) + sin(2*pi*hz*2*t)*0.17 + sin(2*pi*hz*3*t)*0.035
        value = tone * envelope * gain
        track[(begin+i) % COUNT] += value
        if not pad:
            track[(begin+i+round(RATE*0.27)) % COUNT] += value*0.16
            track[(begin+i+round(RATE*0.51)) % COUNT] += value*0.075

def compose(mode):
    track = array('f', [0]) * COUNT
    chords = ([48,55,60,64], [45,52,57,60], [41,48,53,57], [43,50,55,59]) if mode=='village' else ([48,55,60,63], [44,51,56,60], [46,53,58,62], [43,50,55,58])
    melodies = ([72,76,79,76], [72,69,76,72], [69,72,77,76], [74,71,67,71]) if mode=='village' else ([72,67,75,72], [72,68,67,72], [70,65,74,70], [67,70,74,67])
    for bar,chord in enumerate(chords):
        for pitch in chord:
            note(track,bar*8-1,9,pitch,0.032,True)
        note(track,bar*8,6,chord[0]-12,0.045,True)
        for step in range(8):
            note(track,bar*8+step,3,chord[step%4]+12,0.058 if mode=='village' else 0.026)
        for step,pitch in enumerate(melodies[bar]):
            note(track,bar*8+0.5+step*2,3.5,pitch,0.105 if mode=='village' else 0.044)
    peak=max(abs(v) for v in track)
    assert 0 < peak < 1, 'Unexpected clipping or silence'
    pcm=array('h',(round(v*29000) for v in track))
    destination=ROOT/'game'/'assets'/'audio'/f'{mode}.wav'
    destination.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(destination),'wb') as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(RATE)
        target.writeframes(pcm.tobytes())
    print(f'{mode}: {SECONDS}s / {RATE}Hz / mono / peak={peak:.3f}')

if __name__=='__main__':
    for mode in ['village','forest']: compose(mode)
