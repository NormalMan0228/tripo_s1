"""Write the per-appearance expression templates (pose files for rigify_bake --style).

A template is written once on the style's representative head (control rest positions in ctrl_<style>_<head>.json,
dumped from its Rigify face rig; origin = lip slit centre, unit = half mouth width w). Every move is in w, so the same
file fits thin / round heads of that style: the bake multiplies by each head's own w.
Head space: +x = character's left, -y = forward, +z = up. jaw_deg > 0 opens the jaw.

Mouth shapes are built from a few readable numbers per style (PARAMS) instead of control-by-control values:
  lip edge controls (lip.T*, lip.B*, lip_end*) at |x| = xr (0 centre .. 1 corner):
      dx = -inward * x                     corners (and the whole lip line) pulled toward the centre
      dz = +-open * sqrt(1 - xr^2)          upper edge up / lower edge down on an ellipse -> a round opening
      dy = forward + push * (1 - xr^2)      whole mouth forward, the middle more (protrusion)
  other controls round the mouth follow by a falloff over the mouth ellipse (1 at its rim, 0 at twice its size).
Usage: python build_styles.py   (writes styles/<style>.json next to this file)
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))

PARAMS = {
    'semi': {
        'head': 'ctrl_semi_f06.json',
        'keys': {
            # 오 (ARKit mouthFunnel): round opening, corners in, lips forward and flared
            'mouthFunnel': {'jaw_deg': 3.0, 'inward': 0.30, 'open_up': 0.17, 'open_lo': 0.10, 'forward': -0.10, 'push': -0.14,
                            'flare': -0.04, 'surround': 0.55},
            # 우 (ARKit mouthPucker): lips closed, corners well in, lips pushed far forward
            'mouthPucker': {'jaw_deg': 0.5, 'inward': 0.42, 'open_up': 0.0, 'open_lo': 0.0, 'forward': -0.18, 'push': -0.20,
                            'flare': 0.0, 'surround': 0.65},
        },
    },
    # 카툰 (Pixar 계열): 크고 과장된 입 모양, 볼까지 크게 따라옴
    'cartoon': {
        'head': 'ctrl_cartoon_f11.json',
        'keys': {
            'mouthFunnel': {'jaw_deg': 6.0, 'inward': 0.36, 'open_up': 0.22, 'open_lo': 0.22, 'forward': -0.12, 'push': -0.18,
                            'flare': -0.05, 'surround': 0.75},
            'mouthPucker': {'jaw_deg': 1.0, 'inward': 0.50, 'open_up': 0.0, 'open_lo': 0.0, 'forward': -0.22, 'push': -0.28,
                            'flare': 0.0, 'surround': 0.8},
        },
    },
    # 애니: 입술 내밈은 거의 없고, 작고 둥근 입이 아래쪽으로 열림 (2D 애니의 단순한 입 모양)
    'anime': {
        'head': 'ctrl_anime_f09.json',
        'keys': {
            'mouthFunnel': {'jaw_deg': 5.0, 'inward': 0.42, 'open_up': 0.10, 'open_lo': 0.20, 'forward': -0.03, 'push': -0.04,
                            'flare': 0.0, 'surround': 0.4},
            'mouthPucker': {'jaw_deg': 1.0, 'inward': 0.55, 'open_up': 0.03, 'open_lo': 0.05, 'forward': -0.04, 'push': -0.06,
                            'flare': 0.0, 'surround': 0.4},
        },
    },
}
MOUTH_RX, MOUTH_RZ = 1.0, 0.6          # mouth ellipse (in w) for the falloff of the controls round the lips


def smooth(t):
    t = min(max(t, 0.0), 1.0); return t * t * (3 - 2 * t)


def mouth_key(ctrl, p):
    d = {}
    for n, (x, y, z) in ctrl.items():
        xr = min(abs(x), 1.0); prof = math.sqrt(max(0.0, 1.0 - xr * xr))
        if n.startswith(('lip.T', 'lip.B', 'lip_end')):
            s = 0 if n.startswith('lip_end') else (1 if n.startswith('lip.T') else -1)
            h = p['open_up'] if s > 0 else p['open_lo']
            dx = -p['inward'] * x
            dz = s * h * prof
            dy = p['forward'] + p['push'] * (1 - xr * xr) + p['flare'] * prof * (s != 0)
        else:
            rho = math.hypot(x / MOUTH_RX, z / MOUTH_RZ); f = smooth(2.0 - rho) * p['surround']
            if f < 1e-3: continue
            dx = -p['inward'] * x * f
            dy = (p['forward'] + 0.5 * p['push']) * f
            dz = (0.3 * p['open_up'] if z > 0 else -0.3 * p['open_lo']) * f
        if abs(dx) + abs(dy) + abs(dz) > 1e-4: d[n] = [round(dx, 4), round(dy, 4), round(dz, 4)]
    return d


def build(style):
    P = PARAMS[style]; head = json.load(open(os.path.join(HERE, P['head'])))
    out = {'style': style, 'unit': 'half mouth width of each head (lip slit centre to corner)', 'source_head': P['head'],
           'params': P['keys'], 'keys': {}}
    for key, p in P['keys'].items():
        out['keys'][key] = {'base': 'jaw', 'jaw_deg': p['jaw_deg'], 'd': mouth_key(head['ctrl'], p)}
    json.dump(out, open(os.path.join(HERE, style + '.json'), 'w'), indent=1)
    print(style, {k: len(v['d']) for k, v in out['keys'].items()})


if __name__ == '__main__':
    for st in PARAMS: build(st)
