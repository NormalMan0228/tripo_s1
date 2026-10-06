"""One matching icon set for the HUD, menus and currencies (64x64 SVG).

Shared look: warm two-stop gradient fills, a 3 px walnut outline with round joins,
a soft drop shadow and one white highlight. Existing names (bag, craft, map, chest,
wardrobe, expedition, leaf) are overwritten in place so every caller picks up the
new art; the rest are new. Usage: art-venv python tools/build_ui_icons.py
"""
from pathlib import Path
import re

OUT = Path(__file__).resolve().parents[1] / 'game/assets/ui'
INK = '#3b2414'


def grad(gid, top, bottom):
    return f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>'


def dedupe(svg):
    """Keep the last value of an attribute repeated inside one tag (valid XML)."""
    def fix(match):
        tag = match.group(0)
        attrs = re.findall(r'\s([a-zA-Z:-]+)="([^"]*)"', tag)
        if len({k for k, _ in attrs}) == len(attrs):
            return tag
        head = re.match(r'<[a-zA-Z]+', tag).group(0)
        merged = {}
        for k, v in attrs:
            merged[k] = v
        tail = '/>' if tag.endswith('/>') else '>'
        return head + ''.join(f' {k}="{v}"' for k, v in merged.items()) + tail
    return re.sub(r'<[a-zA-Z][^<>]*>', fix, svg)


def icon(name, defs, shapes, shadow):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><defs>{"".join(defs)}</defs>'
           f'<g transform="translate(0 2.5)" fill="#1a0f06" opacity=".22">{shadow}</g>{shapes}</svg>')
    (OUT / f'{name}.svg').write_text(dedupe(svg), encoding='utf-8')


S = f'stroke="{INK}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"'
HL = 'fill="#fff" opacity=".55"'

icon('bag', [grad('a', '#eaa766', '#b8693a'), grad('b', '#c27843', '#8f4c27')],
     f'<path d="M23 23c0-8 4-12 9-12s9 4 9 12" fill="none" {S} stroke-width="4.5"/>'
     f'<rect x="10" y="21" width="44" height="35" rx="11" fill="url(#a)" {S}/>'
     f'<path d="M11 28q21 15 42 0v5q-21 14-42 0z" fill="url(#b)" {S}/>'
     f'<rect x="27" y="33" width="10" height="9" rx="2.5" fill="#f3cf72" {S} stroke-width="2.5"/>'
     f'<path d="M16 25q4-2 8-2" stroke="#fff" stroke-width="3" opacity=".5" fill="none" stroke-linecap="round"/>',
     '<rect x="10" y="21" width="44" height="35" rx="11"/>')

icon('craft', [grad('h', '#d9dfe3', '#8e9aa3'), grad('w', '#d99a5a', '#9c6233')],
     f'<g transform="rotate(-38 32 32)"><rect x="28.5" y="22" width="7" height="36" rx="3.5" fill="url(#w)" {S}/>'
     f'<path d="M14 11h30q6 0 6 6v4q0 4-4 4H14q-3 0-3-3v-8q0-3 3-3z" fill="url(#h)" {S}/>'
     f'<path d="M15 15h26" stroke="#fff" stroke-width="2.5" opacity=".6" fill="none" stroke-linecap="round"/></g>'
     f'<circle cx="50" cy="48" r="5" fill="#f3cf72" {S} stroke-width="2.5"/>',
     '<g transform="rotate(-38 32 32)"><rect x="28.5" y="22" width="7" height="36" rx="3.5"/><rect x="11" y="11" width="39" height="14" rx="4"/></g>')

icon('map', [grad('p', '#fdf0cc', '#e6cb93'), grad('q', '#efd9a6', '#d4b47a')],
     f'<path d="M8 16l14-5 20 6 14-5v38l-14 5-20-6-14 5z" fill="url(#p)" {S}/>'
     f'<path d="M22 11v38l20 6V17z" fill="url(#q)"/>'
     f'<path d="M8 16l14-5 20 6 14-5v38l-14 5-20-6-14 5zM22 11v38M42 17v38" fill="none" {S}/>'
     f'<path d="M13 41q6-8 13-4t11-6 9-10" fill="none" stroke="#c2523a" stroke-width="2.5" stroke-dasharray="3 3.5" stroke-linecap="round"/>'
     f'<path d="M44 16l6 6m0-6l-6 6" stroke="#c2523a" stroke-width="3.5" stroke-linecap="round"/>',
     '<path d="M8 16l14-5 20 6 14-5v38l-14 5-20-6-14 5z"/>')

icon('chest', [grad('c', '#d39456', '#94592d'), grad('l', '#e0a866', '#a8683a')],
     f'<rect x="9" y="29" width="46" height="26" rx="4" fill="url(#c)" {S}/>'
     f'<path d="M9 30v-6q0-10 11-10h24q11 0 11 10v6z" fill="url(#l)" {S}/>'
     f'<path d="M17 14.5V55M47 14.5V55" stroke="#e6b552" stroke-width="5"/>'
     f'<path d="M9 30h46" fill="none" {S}/>'
     f'<rect x="27.5" y="25" width="9" height="12" rx="2.5" fill="#f6d77e" {S} stroke-width="2.5"/>'
     f'<path d="M14 21q2-4 7-4" stroke="#fff" stroke-width="2.5" opacity=".5" fill="none" stroke-linecap="round"/>',
     '<rect x="9" y="14" width="46" height="41" rx="6"/>')

icon('wardrobe', [grad('t', '#7cc3b9', '#3f8580')],
     f'<path d="M23 10l-9 4-9 11 8 7 5-4v26h28V28l5 4 8-7-9-11-9-4q-9 8-18 0z" fill="url(#t)" {S}/>'
     f'<path d="M23 10q9 8 18 0" fill="none" {S}/>'
     f'<path d="M32 18v12" stroke="{INK}" stroke-width="2.5" stroke-linecap="round"/>'
     f'<circle cx="32" cy="36" r="2" fill="{INK}"/><circle cx="32" cy="44" r="2" fill="{INK}"/>'
     f'<path d="M14 21l5-4" stroke="#fff" stroke-width="2.5" opacity=".5" stroke-linecap="round"/>',
     '<path d="M23 10l-9 4-9 11 8 7 5-4v26h28V28l5 4 8-7-9-11-9-4q-9 8-18 0z"/>')

icon('expedition', [grad('r', '#f4d184', '#b9822f'), grad('f', '#fffaf0', '#f1e2c0')],
     f'<circle cx="32" cy="32" r="25" fill="url(#r)" {S}/>'
     f'<circle cx="32" cy="32" r="18" fill="url(#f)" {S} stroke-width="2.5"/>'
     f'<path d="M32 15l5 17h-10z" fill="#d4533b" {S} stroke-width="2"/>'
     f'<path d="M32 49l-5-17h10z" fill="#6f8089" {S} stroke-width="2"/>'
     f'<circle cx="32" cy="32" r="3" fill="#f3cf72" {S} stroke-width="2"/>'
     f'<path d="M32 3.5v4M32 56.5v4M3.5 32h4M56.5 32h4" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>'
     f'<path d="M16 20q4-6 10-8" stroke="#fff" stroke-width="2.5" opacity=".6" fill="none" stroke-linecap="round"/>',
     '<circle cx="32" cy="32" r="25"/>')

icon('leaf', [grad('g', '#b4dc8c', '#5f9a45'), grad('g2', '#fffbe6', '#e4f0c8')],
     f'<circle cx="32" cy="32" r="25" fill="url(#g)" {S}/>'
     f'<circle cx="32" cy="32" r="19" fill="none" stroke="#3f6e2c" stroke-width="2" opacity=".55"/>'
     f'<path d="M20 44c0-14 9-23 24-24 0 15-9 24-24 24z" fill="url(#g2)" stroke="#3f6e2c" stroke-width="2.5" stroke-linejoin="round"/>'
     f'<path d="M22 42q8-9 18-18" stroke="#3f6e2c" stroke-width="2" fill="none" stroke-linecap="round"/>'
     f'<path d="M15 22q4-7 11-9" stroke="#fff" stroke-width="2.5" opacity=".6" fill="none" stroke-linecap="round"/>',
     '<circle cx="32" cy="32" r="25"/>')

icon('heart', [grad('h', '#f58f7c', '#c9433d')],
     f'<path d="M32 55C14 42 7 33 7 23 7 14 13 9 20 9c5 0 9 3 12 7 3-4 7-7 12-7 7 0 13 5 13 14 0 10-7 19-25 32z" fill="url(#h)" {S}/>'
     f'<path d="M15 19q2-5 7-5" stroke="#fff" stroke-width="3.5" {HL} fill="none" stroke-linecap="round"/>',
     '<path d="M32 55C14 42 7 33 7 23 7 14 13 9 20 9c5 0 9 3 12 7 3-4 7-7 12-7 7 0 13 5 13 14 0 10-7 19-25 32z"/>')

icon('hunger', [grad('a', '#f6c46a', '#d08a2e'), grad('lf', '#9fd27a', '#4f8a3a')],
     f'<path d="M32 18c-6-4-22-4-23 12-1 14 9 26 17 26 3 0 4-1 6-1s3 1 6 1c8 0 18-12 17-26-1-16-17-16-23-12z" fill="url(#a)" {S}/>'
     f'<path d="M32 18q-1-8 4-12" fill="none" {S}/>'
     f'<path d="M35 12q8-7 15-2-6 7-15 2z" fill="url(#lf)" {S} stroke-width="2.5"/>'
     f'<path d="M15 28q1-6 7-7" stroke="#fff" stroke-width="3.5" opacity=".55" fill="none" stroke-linecap="round"/>',
     '<path d="M32 18c-6-4-22-4-23 12-1 14 9 26 17 26 3 0 4-1 6-1s3 1 6 1c8 0 18-12 17-26-1-16-17-16-23-12z"/>')

icon('stamina', [grad('s', '#a6ecd6', '#3fa58e')],
     f'<path d="M37 5L13 36h15l-5 23 26-33H33z" fill="url(#s)" {S}/>'
     f'<path d="M33 12l-12 17" stroke="#fff" stroke-width="3" opacity=".55" stroke-linecap="round"/>',
     '<path d="M37 5L13 36h15l-5 23 26-33H33z"/>')

icon('cold', [grad('i', '#e4f6ff', '#8cc4e2')],
     f'<g {S} stroke-width="0" fill="none">'
     + ''.join(f'<g transform="rotate({a} 32 32)"><path d="M32 6v52M32 14l-6-6M32 14l6-6M32 50l-6 6M32 50l6 6" stroke="{INK}" stroke-width="8" stroke-linecap="round"/></g>' for a in (0, 60, 120))
     + ''.join(f'<g transform="rotate({a} 32 32)"><path d="M32 6v52M32 14l-6-6M32 14l6-6M32 50l-6 6M32 50l6 6" stroke="url(#i)" stroke-width="4" stroke-linecap="round"/></g>' for a in (0, 60, 120))
     + '</g>',
     '<circle cx="32" cy="32" r="22"/>')

icon('gear', [grad('g', '#e7d5ae', '#a88a5e')],
     f'<path d="M28 6h8l1.5 6.5 5 2 5.5-3.5 5.5 5.5-3.5 5.5 2 5L58 28v8l-6.5 1.5-2 5 3.5 5.5-5.5 5.5-5.5-3.5-5 2L36 58h-8l-1.5-6.5-5-2-5.5 3.5-5.5-5.5 3.5-5.5-2-5L6 36v-8l6.5-1.5 2-5-3.5-5.5 5.5-5.5 5.5 3.5 5-2z" fill="url(#g)" {S}/>'
     f'<circle cx="32" cy="32" r="8.5" fill="#fff6e0" {S}/>',
     '<circle cx="32" cy="32" r="26"/>')

icon('mail', [grad('m', '#fffaf0', '#ecd9b0'), grad('m2', '#f2e2be', '#d9bd86')],
     f'<rect x="7" y="15" width="50" height="36" rx="5" fill="url(#m)" {S}/>'
     f'<path d="M8 17l24 19 24-19" fill="url(#m2)" {S}/>'
     f'<circle cx="32" cy="35" r="5" fill="#d4533b" {S} stroke-width="2.2"/>',
     '<rect x="7" y="15" width="50" height="36" rx="5"/>')

icon('people', [grad('a', '#8fc6e8', '#4a86b0'), grad('b', '#f2b37e', '#c4774a')],
     f'<circle cx="42" cy="21" r="8" fill="#f6dcc0" {S}/><path d="M28 52q0-17 14-17t14 17z" fill="url(#a)" {S}/>'
     f'<circle cx="23" cy="24" r="9" fill="#f6dcc0" {S}/><path d="M7 55q0-19 16-19t16 19z" fill="url(#b)" {S}/>',
     '<circle cx="23" cy="24" r="9"/><circle cx="42" cy="21" r="8"/><path d="M7 55q0-19 16-19t16 19zM28 52q0-17 14-17t14 17z"/>')

icon('admin', [grad('k', '#ffe39a', '#c8902f')],
     f'<path d="M9 46l7-24 11 11 5-17 5 17 11-11 7 24z" fill="url(#k)" {S}/>'
     f'<rect x="9" y="46" width="46" height="8" rx="2" fill="#d9a446" {S}/>'
     f'<circle cx="32" cy="38" r="3.5" fill="#d4533b" {S} stroke-width="2"/>',
     '<path d="M9 54V46l7-24 11 11 5-17 5 17 11-11 7 24v8z"/>')

icon('close', [grad('x', '#f2e7cf', '#d9c49a')],
     f'<circle cx="32" cy="32" r="24" fill="url(#x)" {S}/>'
     f'<path d="M23 23l18 18M41 23L23 41" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>',
     '<circle cx="32" cy="32" r="24"/>')

icon('fire', [grad('f', '#ffd36b', '#e0612f'), grad('f2', '#fff4c0', '#ffc24a')],
     f'<path d="M32 58c-13 0-20-8-20-18 0-12 11-16 12-28 6 4 9 9 9 15 3-2 4-5 4-9 7 6 15 13 15 22 0 10-7 18-20 18z" fill="url(#f)" {S}/>'
     f'<path d="M32 56c-6 0-9-4-9-8 0-6 5-8 7-14 4 4 11 8 11 14 0 4-3 8-9 8z" fill="url(#f2)"/>',
     '<path d="M32 58c-13 0-20-8-20-18 0-12 11-16 12-28 6 4 9 9 9 15 3-2 4-5 4-9 7 6 15 13 15 22 0 10-7 18-20 18z"/>')

icon('home', [grad('w', '#fff3dc', '#e8d2a6'), grad('r', '#e07a5a', '#a8452f')],
     f'<path d="M14 30v24h36V30" fill="url(#w)" {S}/>'
     f'<path d="M6 33L32 10l26 23" fill="none" {S} stroke-width="6" stroke="{INK}"/>'
     f'<path d="M6 33L32 10l26 23" fill="none" stroke="url(#r)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
     f'<rect x="27" y="38" width="10" height="16" rx="2" fill="#a8683a" {S} stroke-width="2.5"/>',
     '<path d="M14 30v24h36V30L32 12z"/>')

icon('book', [grad('b', '#7fae8f', '#3f6e5a'), grad('p', '#fffaf0', '#ecdcb8')],
     f'<path d="M8 14q12-4 24 2 12-6 24-2v38q-12-4-24 2-12-6-24-2z" fill="url(#b)" {S}/>'
     f'<path d="M12 16q10-3 18 2v32q-8-4-18-2zM52 16q-10-3-18 2v32q8-4 18-2z" fill="url(#p)" stroke="{INK}" stroke-width="2" stroke-linejoin="round"/>'
     f'<path d="M16 25h9M16 31h9M39 25h9M39 31h9" stroke="#b39468" stroke-width="2" stroke-linecap="round"/>',
     '<path d="M8 14q12-4 24 2 12-6 24-2v38q-12-4-24 2-12-6-24-2z"/>')

icon('sound', [grad('s', '#e7d5ae', '#a88a5e')],
     f'<path d="M8 25h10l13-11v36L18 39H8z" fill="url(#s)" {S}/>'
     f'<path d="M40 24q5 8 0 16M47 18q10 14 0 28" fill="none" stroke="{INK}" stroke-width="3.5" stroke-linecap="round"/>',
     '<path d="M8 25h10l13-11v36L18 39H8z"/>')

icon('clock', [grad('c', '#f4d184', '#b9822f'), grad('f', '#fffaf0', '#f1e2c0')],
     f'<circle cx="32" cy="32" r="24" fill="url(#c)" {S}/><circle cx="32" cy="32" r="18" fill="url(#f)" {S} stroke-width="2.5"/>'
     f'<path d="M32 20v12l8 5" fill="none" stroke="{INK}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>',
     '<circle cx="32" cy="32" r="24"/>')

icon('chat', [grad('c', '#fffaf0', '#ecd9b0')],
     f'<path d="M12 12h40q6 0 6 6v20q0 6-6 6H30l-12 10v-10h-6q-6 0-6-6V18q0-6 6-6z" fill="url(#c)" {S}/>'
     f'<circle cx="22" cy="28" r="3.5" fill="#d4533b"/><circle cx="32" cy="28" r="3.5" fill="#e9a24c"/><circle cx="42" cy="28" r="3.5" fill="#4a86b0"/>',
     '<path d="M12 12h40q6 0 6 6v20q0 6-6 6H30l-12 10v-10h-6q-6 0-6-6V18q0-6 6-6z"/>')

print('icons written to', OUT)
