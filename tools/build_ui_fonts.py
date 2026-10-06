"""Subset the bundled UI fonts to the characters the game shows.

Sources (all SIL Open Font License 1.1, see game/assets/fonts/LICENSES.md):
  Pretendard  https://github.com/orioncactus/pretendard  (body / UI, ko + Latin)
  Jua         https://github.com/google/fonts/tree/main/ofl/jua  (display titles)
  Noto Sans SC https://github.com/google/fonts/tree/main/ofl/notosanssc (zh fallback)

Pretendard and Jua keep every KS X 1001 Hangul syllable (2,350) so player-typed
Korean renders; Noto Sans SC keeps only the Han characters found in the game's
text, with the OS CJK font as the runtime fallback for anything else.
Usage: art-venv python tools/build_ui_fonts.py <download dir>
"""
import sys, re
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1])
OUT = ROOT / 'game/assets/fonts'

text = ''
for pattern in ['game/i18n/*.json', 'game/scripts/*.gd', 'game/tests/fixtures/*.json', 'server/*.py']:
    for path in ROOT.glob(pattern):
        text += path.read_text(encoding='utf-8', errors='ignore')
used = set(text)

def span(a, b): return {chr(c) for c in range(a, b + 1)}
common = span(0x20, 0x7E) | span(0xA0, 0x17F) | span(0x2010, 0x205E) | span(0x2190, 0x21FF) | span(0x2200, 0x22FF) \
    | span(0x2460, 0x24FF) | span(0x25A0, 0x25FF) | span(0x2600, 0x27BF) | span(0x3000, 0x303F) | span(0x3131, 0x318E) | span(0xFF01, 0xFF5E)
ksx = set()
for hi in range(0xB0, 0xC9):
    for lo in range(0xA1, 0xFF):
        try: ksx.add(bytes([hi, lo]).decode('cp949'))
        except UnicodeDecodeError: pass
hangul = {c for c in used if 0xAC00 <= ord(c) <= 0xD7A3} | ksx
han = {c for c in used if 0x3400 <= ord(c) <= 0x9FFF or 0xF900 <= ord(c) <= 0xFAFF}
print('hangul', len(hangul), 'han', len(han))

def cut(font, chars, out):
    opts = subset.Options()
    opts.layout_features = ['*']
    opts.name_IDs = ['*']
    opts.notdef_outline = True
    opts.glyph_names = False
    opts.hinting = False
    opts.flavor = 'woff'
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=[ord(c) for c in chars])
    sub.subset(font)
    font.flavor = 'woff'
    font.save(OUT / out)
    print(out, (OUT / out).stat().st_size // 1024, 'KB')

for weight in ['Regular', 'SemiBold', 'Bold']:
    cut(TTFont(SRC / f'Pretendard-{weight}.otf'), common | hangul | used - han, f'Pretendard-{weight}.woff')
cut(TTFont(SRC / 'Jua-Regular.ttf'), common | hangul | used - han, 'Jua-Regular.woff')
for weight, name in [(400, 'Regular'), (700, 'Bold')]:
    vf = TTFont(SRC / 'NotoSansSC-VF.ttf')
    static = instancer.instantiateVariableFont(vf, {'wght': weight})
    cut(static, han | span(0x3000, 0x303F) | span(0xFF01, 0xFF5E) | span(0x20, 0x7E), f'NotoSansSC-{name}.woff')
