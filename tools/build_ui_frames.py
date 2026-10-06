"""Procedural 9-slice UI frames for the cozy RPG look, drawn at 2x.

Every PNG lands in game/assets/ui/frames/. RpgUi loads them as StyleBoxTexture with
a size override so they render at 1x on a 1280x800 canvas and stay crisp when the
window is larger. Shapes are signed-distance fields with 1 px analytic AA.
Usage: art-venv python tools/build_ui_frames.py
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageFilter

OUT = Path(__file__).resolve().parents[1] / 'game/assets/ui/frames'
OUT.mkdir(parents=True, exist_ok=True)
META = {}
rng = np.random.default_rng(7)


def hexc(h, a=1.0):
    h = h.lstrip('#')
    return np.array([int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a], dtype=np.float32)


class Canvas:
    def __init__(s, w, h):
        s.w, s.h = w, h
        s.px = np.zeros((h, w, 4), np.float32)
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        s.x, s.y = xs + 0.5, ys + 0.5

    def over(s, color, cov):
        """color: (4,) or (h,w,4) straight alpha; cov: (h,w) coverage."""
        c = np.broadcast_to(color, s.px.shape)
        a = c[..., 3] * np.clip(cov, 0, 1)
        out_a = a + s.px[..., 3] * (1 - a)
        rgb = (c[..., :3] * a[..., None] + s.px[..., :3] * s.px[..., 3:4] * (1 - a[..., None])) / np.maximum(out_a[..., None], 1e-6)
        s.px[..., :3] = rgb
        s.px[..., 3] = out_a

    def save(s, name, margins=None, expand=None, content=None):
        img = Image.fromarray((np.clip(s.px, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA')
        img.save(OUT / (name + '.png'), optimize=True)
        META[name] = {'size': [s.w, s.h], 'margins': margins or [0, 0, 0, 0], 'expand': expand or [0, 0, 0, 0], 'content': content}


def rrect(c, x0, y0, x1, y1, r):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hw, hh = (x1 - x0) / 2, (y1 - y0) / 2
    qx = np.abs(c.x - cx) - (hw - r)
    qy = np.abs(c.y - cy) - (hh - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def fill(d):
    return np.clip(0.5 - d, 0, 1)


def ring(d, width):
    return np.clip(0.5 - (np.abs(d + width / 2) - width / 2), 0, 1)


def vgrad(c, y0, y1, top, bottom):
    t = np.clip((c.y - y0) / max(y1 - y0, 1), 0, 1)[..., None]
    return top * (1 - t) + bottom * t


def shadow(c, x0, y0, x1, y1, r, blur, alpha, dy):
    d = rrect(c, x0, y0 + dy, x1, y1 + dy, r)
    a = np.clip(1 - (d + blur * 0.25) / blur, 0, 1) ** 2 * alpha
    c.over(hexc('#1a1008'), a)


def grain(c, amount):
    n = rng.normal(0, 1, (c.h // 3 + 1, c.w // 3 + 1)).astype(np.float32)
    img = Image.fromarray(((n * 0.2 + 0.5).clip(0, 1) * 255).astype(np.uint8)).resize((c.w, c.h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.2))
    g = (np.asarray(img, np.float32) / 255 - 0.5) * amount
    c.px[..., :3] = np.clip(c.px[..., :3] + g[..., None], 0, 1)


def diamond(c, cx, cy, r):
    return (np.abs(c.x - cx) + np.abs(c.y - cy)) / 1.4142 - r / 1.4142


def circle(c, cx, cy, r):
    return np.hypot(c.x - cx, c.y - cy) - r


def gold_stud(c, cx, cy, r):
    c.over(hexc('#3a2312', .55), fill(diamond(c, cx, cy + 1.5, r + 1.5)))
    c.over(vgrad(c, cy - r, cy + r, hexc('#ffe9a8'), hexc('#b77d2c')), fill(diamond(c, cx, cy, r)))
    c.over(hexc('#fff6d0', .9), fill(circle(c, cx - r * .18, cy - r * .3, r * .22)))


# ------------------------------------------------------------------ panels
def panel(name, base_top, base_bot, border, inner, studs, radius=30, alpha=1.0, glass=False, size=176, pad=(14, 10, 14, 22)):
    W = H = size
    c = Canvas(W, H)
    l, t, r_, b = pad
    x0, y0, x1, y1 = l, t, W - r_, H - b
    shadow(c, x0, y0, x1, y1, radius, 18, .45 if not glass else .55, 6)
    d = rrect(c, x0, y0, x1, y1, radius)
    c.over(hexc(border, alpha), fill(d))
    d2 = rrect(c, x0 + 5, y0 + 5, x1 - 5, y1 - 5, radius - 5)
    body = vgrad(c, y0, y1, hexc(base_top, alpha), hexc(base_bot, alpha))
    c.over(body, fill(d2))
    if not glass:
        grain(c, 0.035)
    else:
        c.over(hexc('#ffffff', .07), fill(d2) * np.clip(1 - (c.y - y0) / 40, 0, 1))
    # inner bevel: light top edge, dark bottom edge
    c.over(hexc('#ffffff', .35 if not glass else .10), ring(d2, 2) * (c.y < (y0 + y1) / 2))
    c.over(hexc('#000000', .10 if not glass else .25), ring(d2, 2) * (c.y >= (y0 + y1) / 2))
    d3 = rrect(c, x0 + 13, y0 + 13, x1 - 13, y1 - 13, radius - 12)
    c.over(hexc(inner, .9), ring(d3, 2))
    if studs:
        for sx, sy in [(x0 + 13, y0 + 13), (x1 - 13, y0 + 13), (x0 + 13, y1 - 13), (x1 - 13, y1 - 13)]:
            gold_stud(c, sx + (4 if sx < W / 2 else -4), sy + (4 if sy < H / 2 else -4), 7)
    m = [l + 40, t + 40, r_ + 40, b + 40]
    c.save(name, margins=m, expand=[l, t, r_, b], content=[26, 22, 26, 22])


panel('panel_paper', '#fbf3e1', '#f0e2c3', '#6e4b2c', '#c9a46a', True)
panel('panel_night', '#26383c', '#152125', '#d2ae66', '#d2ae66', True, alpha=.94, glass=True)
panel('panel_night_plain', '#26383c', '#152125', '#b8975a', '#3f5559', False, radius=24, alpha=.92, glass=True)
panel('panel_paper_plain', '#fbf3e1', '#f2e5c8', '#8a6a45', '#d8bf90', False, radius=24)


# ------------------------------------------------------------------ pill / toast
def pill(name, top, bot, edge, alpha=.94, H=72, W=120):
    c = Canvas(W, H)
    pad = 8
    x0, y0, x1, y1 = pad, pad - 2, W - pad, H - pad - 4
    r = (y1 - y0) / 2
    shadow(c, x0, y0, x1, y1, r, 12, .45, 4)
    d = rrect(c, x0, y0, x1, y1, r)
    c.over(hexc(edge, alpha), fill(d))
    d2 = rrect(c, x0 + 3, y0 + 3, x1 - 3, y1 - 3, r - 3)
    c.over(vgrad(c, y0, y1, hexc(top, alpha), hexc(bot, alpha)), fill(d2))
    c.over(hexc('#ffffff', .10), ring(d2, 2) * (c.y < (y0 + y1) / 2))
    rr = int(r) + pad
    c.save(name, margins=[rr + 2, rr - 2, rr + 2, rr + 2], expand=[pad, pad - 2, pad, pad + 4], content=[22, 9, 22, 9])


pill('pill_night', '#2a3d41', '#172326', '#d2ae66')
pill('pill_paper', '#fdf6e6', '#efe0c0', '#8a6a45')
pill('tooltip', '#2a3d41', '#172326', '#b8975a', H=56, W=96)


# ------------------------------------------------------------------ buttons
def button(name, top, bot, lip, edge, state, text_dark=True, W=112, H=76, radius=18):
    c = Canvas(W, H)
    pad = 6
    press = state == 'pressed'
    lip_h = 2 if press else 6
    off = 4 if press else 0
    x0, y0, x1, y1 = pad, pad + off, W - pad, H - pad
    alpha = .55 if state == 'disabled' else 1
    if state != 'pressed':
        shadow(c, x0, y0, x1, y1, radius, 8, .35 * alpha, 3)
    c.over(hexc(edge, alpha), fill(rrect(c, x0, y0, x1, y1, radius)))
    c.over(hexc(lip, alpha), fill(rrect(c, x0 + 2.5, y0 + 2.5, x1 - 2.5, y1 - 2.5, radius - 2.5)))
    face = rrect(c, x0 + 2.5, y0 + 2.5, x1 - 2.5, y1 - 2.5 - lip_h, radius - 2.5)
    c.over(vgrad(c, y0, y1 - lip_h, hexc(top, alpha), hexc(bot, alpha)), fill(face))
    c.over(hexc('#ffffff', .45 * alpha if text_dark else .22 * alpha), ring(face, 2) * (c.y < y0 + 14))
    if state == 'hover':
        c.over(hexc('#ffe9a8', .9), ring(rrect(c, x0, y0, x1, y1, radius), 2.5))
    m = radius + pad + 4
    c.save(name, margins=[m, m - 2, m, m + 2], expand=[pad, pad, pad, pad], content=[16, 7 + off // 2, 16, 9 + lip_h - off // 2])


def button_set(prefix, top, bot, lip, edge, hover_top, hover_bot, dark):
    button(prefix + '_normal', top, bot, lip, edge, 'normal', dark)
    button(prefix + '_hover', hover_top, hover_bot, lip, edge, 'hover', dark)
    button(prefix + '_pressed', bot, top, lip, edge, 'pressed', dark)
    button(prefix + '_disabled', '#c9c2b2', '#b3ab99', '#8c8576', '#6f6a5f', 'disabled', dark)


button_set('btn_paper', '#fffaf0', '#efe1c4', '#c4a473', '#6e4b2c', '#fffdf6', '#f6e7c4', True)
button_set('btn_green', '#9fcf7c', '#6fa452', '#4a7536', '#2f4d22', '#b5e08f', '#80b862', False)
button_set('btn_gold', '#ffe39a', '#e9b552', '#b07a2a', '#5e3b14', '#fff0b8', '#f2c466', True)
button_set('btn_night', '#33494d', '#1e2d31', '#121b1e', '#c9a861', '#3f585c', '#26393d', False)


def focus_ring(name='focus', W=112, H=76, radius=18):
    c = Canvas(W, H)
    pad = 6
    d = rrect(c, pad - 2, pad - 2, W - pad + 2, H - pad + 2, radius + 2)
    c.over(hexc('#ffd77a', .95), ring(d, 3))
    c.over(hexc('#ffd77a', .25), ring(rrect(c, pad - 5, pad - 5, W - pad + 5, H - pad + 5, radius + 5), 3))
    m = radius + pad + 4
    c.save(name, margins=[m, m, m, m], expand=[pad, pad, pad, pad])


focus_ring()


# ------------------------------------------------------------------ slots
def slot(name, top, bot, edge, inner_shadow, glow=False, W=104, H=104, radius=22, alpha=.92):
    c = Canvas(W, H)
    pad = 6
    x0, y0, x1, y1 = pad, pad, W - pad, H - pad
    shadow(c, x0, y0, x1, y1, radius, 10, .4, 4)
    d = rrect(c, x0, y0, x1, y1, radius)
    c.over(hexc(edge, alpha), fill(d))
    d2 = rrect(c, x0 + 4, y0 + 4, x1 - 4, y1 - 4, radius - 4)
    c.over(vgrad(c, y0, y1, hexc(top, alpha), hexc(bot, alpha)), fill(d2))
    top_fade = np.clip(1 - (c.y - y0) / ((y1 - y0) * .6), 0, 1)
    inset = np.clip(1 - (-d2) / 9, 0, 1) * fill(d2) * top_fade
    c.over(hexc(inner_shadow, .45), inset)
    c.over(hexc('#ffffff', .18), ring(d2, 1.5) * np.clip((c.y - (y0 + y1) * .5) / ((y1 - y0) * .3), 0, 1))
    if glow:
        c.over(hexc('#ffe7a0', .95), ring(d, 3))
        c.over(hexc('#ffe7a0', .18), fill(d2) * np.clip(1 - (-d2) / 14, 0, 1))
    m = radius + pad + 4
    c.save(name, margins=[m, m, m, m], expand=[pad - 2, pad - 2, pad - 2, pad - 2], content=[8, 8, 8, 8])


slot('slot_night', '#2c4044', '#1a272a', '#b8975a', '#000000')
slot('slot_night_hover', '#38525a', '#22343a', '#e7c77d', '#000000', glow=True)
slot('slot_night_pressed', '#4a3d22', '#33291a', '#ffd77a', '#000000', glow=True)
slot('slot_night_primary', '#5a4322', '#3a2b16', '#e7c77d', '#000000')
slot('slot_paper', '#efe2c6', '#e6d5b2', '#a88a5e', '#7a5a33', alpha=1)
slot('slot_paper_hover', '#f8eed8', '#efe0c0', '#c9a25a', '#7a5a33', glow=True, alpha=1)
slot('slot_paper_empty', '#e3d8c0', '#dcd0b5', '#b5a283', '#7a5a33', alpha=.8)


# ------------------------------------------------------------------ fields
def field(name, top, bot, edge, focus, W=96, H=64, radius=12):
    c = Canvas(W, H)
    pad = 4
    x0, y0, x1, y1 = pad, pad, W - pad, H - pad
    d = rrect(c, x0, y0, x1, y1, radius)
    c.over(hexc(edge), fill(d))
    d2 = rrect(c, x0 + 2.5, y0 + 2.5, x1 - 2.5, y1 - 2.5, radius - 2.5)
    c.over(vgrad(c, y0, y1, hexc(top), hexc(bot)), fill(d2))
    c.over(hexc('#000000', .22), np.clip(1 - (-d2) / 7, 0, 1) * fill(d2) * np.clip(1 - (c.y - y0) / ((y1 - y0) * .6), 0, 1))
    if focus:
        c.over(hexc('#ffd77a'), ring(d, 3))
        c.over(hexc('#ffd77a', .3), ring(rrect(c, x0 - 2, y0 - 2, x1 + 2, y1 + 2, radius + 2), 2))
    m = radius + pad + 4
    c.save(name, margins=[m, m, m, m], expand=[pad, pad, pad, pad], content=[14, 9, 14, 9])


field('field_paper', '#f2e7cf', '#fbf4e4', '#a88a5e', False)
field('field_paper_focus', '#f6ecd6', '#fffaf0', '#8a6a45', True)
field('field_night', '#0f191b', '#1c2a2d', '#6f6448', False)
field('field_night_focus', '#122023', '#203236', '#c9a861', True)


# ------------------------------------------------------------------ bars
def bar(name, W=64, H=28, radius=12, kind='bg'):
    c = Canvas(W, H)
    pad = 2
    d = rrect(c, pad, pad, W - pad, H - pad, radius)
    if kind == 'bg':
        c.over(hexc('#0d1416', .9), fill(d))
        d2 = rrect(c, pad + 2, pad + 2, W - pad - 2, H - pad - 2, radius - 2)
        c.over(hexc('#1d2a2d', .95), fill(d2))
        c.over(hexc('#000000', .35), np.clip(1 - (-d2) / 5, 0, 1) * fill(d2) * np.clip(1 - c.y / (H * .6), 0, 1))
        c.over(hexc('#e2c27e', .45), ring(d, 1.5) * (c.y > H * .6))
    else:
        d2 = rrect(c, pad + 2, pad + 2, W - pad - 2, H - pad - 2, radius - 2)
        c.over(vgrad(c, pad, H - pad, hexc('#ffffff'), hexc('#bdbdbd')), fill(d2))
        c.over(hexc('#ffffff', .65), fill(rrect(c, pad + 6, pad + 4, W - pad - 6, H * .45, 4)))
        c.over(hexc('#000000', .25), ring(d2, 1.5) * (c.y > H * .6))
    m = radius + pad + 2
    c.save(name, margins=[m, m, m, m])


bar('bar_bg')
bar('bar_fill', kind='fill')


# ------------------------------------------------------------------ ribbon
def ribbon(name, top, bot, edge, W=260, H=84):
    c = Canvas(W, H)
    tail = 34
    y0, y1 = 14, H - 16
    for side in (0, 1):
        xs = c.x if side == 0 else W - c.x
        tail_shape = np.maximum(np.maximum(xs - (tail + 10), (y0 + 12) - c.y), c.y - (y1 + 10))
        notch = (xs - 6) - np.abs(c.y - (y0 + y1 + 22) / 2) * .55
        tail_d = np.maximum(tail_shape, -notch)
        c.over(hexc('#3c1f12', .4), fill(tail_d - 0.5) * (c.y > y0 + 14))
        c.over(hexc('#7d3a24'), fill(tail_d + 1.5))
    shadow(c, tail - 4, y0, W - tail + 4, y1, 6, 8, .4, 3)
    d = rrect(c, tail - 4, y0, W - tail + 4, y1, 6)
    c.over(hexc(edge), fill(d))
    d2 = rrect(c, tail - 1, y0 + 3, W - tail + 1, y1 - 3, 4)
    c.over(vgrad(c, y0, y1, hexc(top), hexc(bot)), fill(d2))
    c.over(hexc('#ffe7a8', .75), ring(rrect(c, tail + 3, y0 + 7, W - tail - 3, y1 - 7, 2), 1.5))
    c.over(hexc('#ffffff', .22), fill(rrect(c, tail, y0 + 4, W - tail, (y0 + y1) / 2 - 4, 3)))
    c.save(name, margins=[tail + 18, 30, tail + 18, 30], content=[tail + 14, 6, tail + 14, 10])


ribbon('ribbon', '#cc6e47', '#9c4a2f', '#5a2a18')
ribbon('ribbon_teal', '#4f8f8a', '#2f6461', '#183836')


# ------------------------------------------------------------------ keycap
def keycap(name='keycap', W=48, H=48, radius=9):
    c = Canvas(W, H)
    pad = 3
    c.over(hexc('#3a2614'), fill(rrect(c, pad, pad, W - pad, H - pad, radius)))
    c.over(hexc('#c79c52'), fill(rrect(c, pad + 2, pad + 2, W - pad - 2, H - pad - 2, radius - 2)))
    face = rrect(c, pad + 2, pad + 2, W - pad - 2, H - pad - 6, radius - 2)
    c.over(vgrad(c, pad, H - pad, hexc('#fff3cf'), hexc('#ecd29a')), fill(face))
    m = radius + pad + 2
    c.save(name, margins=[m, m, m, m + 2], expand=[1, 1, 1, 1], content=[6, 1, 6, 3])


keycap()


# ------------------------------------------------------------------ portrait ring
def portrait_ring(name='portrait_ring', S=168):
    c = Canvas(S, S)
    cx = cy = S / 2
    R = S / 2 - 8
    outside = circle(c, cx, cy, R - 6) > 0
    c.over(hexc('#1a1008', .45), np.clip(1 - (circle(c, cx, cy + 4, R + 2)) / 8, 0, 1) * outside)
    band = np.maximum(circle(c, cx, cy, R), -circle(c, cx, cy, R - 9))
    c.over(hexc('#4a2f17'), fill(band))
    band2 = np.maximum(circle(c, cx, cy, R - 2), -circle(c, cx, cy, R - 7))
    c.over(vgrad(c, cy - R, cy + R, hexc('#fff0b8'), hexc('#b47b2b')), fill(band2))
    inner = circle(c, cx, cy, R - 9)
    c.over(hexc('#000000', .28), np.clip(1 - (-inner) / 10, 0, 1) * (inner < 0))
    for a in (0, 90, 180, 270):
        rad = np.radians(a - 90)
        gold_stud(c, cx + np.cos(rad) * (R - 4.5), cy + np.sin(rad) * (R - 4.5), 6)
    c.save(name)


portrait_ring()


# ------------------------------------------------------------------ check / radio / slider / arrow / scroll
def check(name, on, radio=False, S=44):
    c = Canvas(S, S)
    pad = 5
    d = circle(c, S / 2, S / 2, S / 2 - pad) if radio else rrect(c, pad, pad, S - pad, S - pad, 9)
    c.over(hexc('#6e4b2c'), fill(d))
    d2 = circle(c, S / 2, S / 2, S / 2 - pad - 2.5) if radio else rrect(c, pad + 2.5, pad + 2.5, S - pad - 2.5, S - pad - 2.5, 7)
    c.over(vgrad(c, pad, S - pad, hexc('#f2e7cf'), hexc('#fffaf0')), fill(d2))
    if on:
        if radio:
            c.over(vgrad(c, 12, S - 12, hexc('#9fcf7c'), hexc('#4a7536')), fill(circle(c, S / 2, S / 2, 8.5)))
        else:
            def seg(ax, ay, bx, by, w):
                px, py = c.x - ax, c.y - ay
                vx, vy = bx - ax, by - ay
                h = np.clip((px * vx + py * vy) / (vx * vx + vy * vy), 0, 1)
                return np.hypot(px - vx * h, py - vy * h) - w
            m = np.minimum(seg(13, 22, 19, 29, 3.2), seg(19, 29, 32, 14, 3.2))
            c.over(hexc('#4a7536'), fill(m))
    c.save(name)


check('check_off', False)
check('check_on', True)
check('radio_off', False, True)
check('radio_on', True, True)


def grabber(name='slider_grabber', S=40, hover=False):
    c = Canvas(S, S)
    cx = cy = S / 2
    c.over(hexc('#1a1008', .4), np.clip(1 - circle(c, cx, cy + 2, 13) / 4, 0, 1))
    c.over(hexc('#5e3b14'), fill(circle(c, cx, cy, 13)))
    c.over(vgrad(c, cy - 12, cy + 12, hexc('#fff7d8' if hover else '#fff0b8'), hexc('#d9a446')), fill(circle(c, cx, cy, 11)))
    c.over(hexc('#ffffff', .7), fill(circle(c, cx - 3, cy - 4, 3.5)))
    c.save(name)


grabber()
grabber('slider_grabber_hover', hover=True)


def arrow(name='arrow_down', S=32, color='#6e4b2c'):
    c = Canvas(S, S)
    d = np.maximum(np.abs(c.x - S / 2) * 0.9 + (c.y - S * .62), -(c.y - S * .34))
    c.over(hexc(color), fill(d))
    c.save(name)


arrow()
arrow('arrow_down_light', color='#f3e2b4')


def scroll(name, W=20, H=40, color='#b89a68', alpha=.85):
    c = Canvas(W, H)
    d = rrect(c, 4, 3, W - 4, H - 3, (W - 8) / 2)
    c.over(hexc(color, alpha), fill(d))
    m = int((W - 8) / 2) + 4
    c.save(name, margins=[m, m, m, m])


scroll('scroll_grabber')
scroll('scroll_grabber_hover', color='#8a6a45', alpha=1)
scroll('scroll_track', color='#000000', alpha=.12)



# ------------------------------------------------------------------ portrait card frame (transparent centre)
def card_frame(name='card_frame', W=208, H=240, r=18):
    c = Canvas(W, H)
    x0, y0, x1, y1 = 12, 8, W - 12, H - 20
    outer = rrect(c, x0, y0, x1, y1, r)
    sh = rrect(c, x0, y0 + 7, x1, y1 + 7, r)
    c.over(hexc('#1a1008'), np.clip(1 - (sh + 4) / 16, 0, 1) ** 2 * .5 * (outer > 0))
    band = np.maximum(outer, -rrect(c, x0 + 9, y0 + 9, x1 - 9, y1 - 9, r - 8))
    c.over(hexc('#4a2f17'), fill(band))
    gold = np.maximum(rrect(c, x0 + 2.5, y0 + 2.5, x1 - 2.5, y1 - 2.5, r - 2), -rrect(c, x0 + 7, y0 + 7, x1 - 7, y1 - 7, r - 6))
    c.over(vgrad(c, y0, y1, hexc('#fff0b8'), hexc('#b47b2b')), fill(gold))
    c.over(hexc('#fff6d0', .8), ring(rrect(c, x0 + 3, y0 + 3, x1 - 3, y1 - 3, r - 2), 1.2) * (c.y < (y0 + y1) / 2))
    inner = rrect(c, x0 + 9, y0 + 9, x1 - 9, y1 - 9, r - 8)
    c.over(hexc('#000000', .4), np.clip(1 - (-inner) / 12, 0, 1) * (inner < 0))
    for sx, sy in [(x0 + 5, y0 + 5), (x1 - 5, y0 + 5), (x0 + 5, y1 - 5), (x1 - 5, y1 - 5)]:
        gold_stud(c, sx, sy, 9)
    m = [x0 + 30, y0 + 30, W - x1 + 30, H - y1 + 30]
    c.save(name, margins=m, expand=[12, 8, 12, 20])


card_frame()

(OUT / 'frames.json').write_text(json.dumps(META, indent=1))
print(len(META), 'frames;', sum(p.stat().st_size for p in OUT.glob('*.png')) // 1024, 'KB')
