"""Draws the archetype library's diagrams and writes its type list, from server/archetype_library.py.

Writes:
  docs/objects/img/archetype_code.png      code structure: library -> type -> role/behaviour -> preset -> program -> game
  docs/objects/img/archetype_flow.png      a request becoming a living object
  docs/objects/img/archetype_families.png  the parent classes (families) and what they share
  docs/objects/img/archetype_types_1..3.png  every type under its family, with its parts and motions
  docs/objects/ARCHETYPES_KO.md            the part between the <!-- types:start/end --> markers (full list)

Pages are HTML drawn by headless Chrome (Korean text via the game's Pretendard font), 1200 px wide so
a phone shows them at half size. Run after changing the library:
  .tools\\server-venv\\Scripts\\python.exe tools\\archetype_docs.py
"""
import html
import io
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.archetype_library import ARCHETYPES, FAMILIES, ROOMS, ROLE_NAMES, VERSION  # noqa: E402
from server.interactions import KINDS  # noqa: E402

OUT = ROOT / 'docs' / 'objects'
IMG = OUT / 'img'
FONTS = ROOT / 'game' / 'assets' / 'fonts'
CHROME = [Path('C:/Program Files/Google/Chrome/Application/chrome.exe'),
          Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')]
WIDTH = 1200

# What each preset kind looks like, in a few Korean words.
KIND_KO = {'spin': '빙글 돎', 'sway': '살랑', 'bounce': '통통', 'glow': '켜짐', 'pulse': '은은히 빛남', 'hue': '색 바뀜',
           'turn': '천천히 돎', 'hinge': '열림', 'clock': '실제 시각', 'tick': '째깍', 'slide': '밀림', 'flicker': '일렁임',
           'rock': '흔들림', 'rotor': '돌아감'}
KIND_ABOUT = {'spin': '한 바퀴 빙글 (E마다)', 'sway': '좌우로 살랑 (바람, 스칠 때)', 'bounce': '위아래로 통통 (뛰기, 둥실)',
              'glow': '불 켜기·끄기', 'pulse': '은은하게 밝아졌다 어두워짐', 'hue': '색이 천천히 바뀜',
              'turn': '천천히 계속 돎 (진열대, 회전판)', 'hinge': '한 모서리를 축으로 열고 닫기 (문, 뚜껑)',
              'clock': '시계 바늘이 플레이어의 실제 시각을 가리킴', 'tick': '째깍째깍 한 칸씩 돎 (다이얼)',
              'slide': '빼고 넣기 (서랍, 미닫이, 팝업)', 'flicker': '불꽃처럼 고르지 않게 일렁이는 빛',
              'rock': '추·흔들의자처럼 흔들림 (밀면 흔들리다 멈춤, 또는 계속)', 'rotor': '날개·바퀴·레코드가 제 축으로 돎'}
TRIGGER_KO = {'click': 'E', 'near': '가까이', 'leave': '멀어지면', 'always': '항상'}
REST_KO = {'sit': '앉기', 'lie': '눕기', '': ''}
FAMILY_COLOUR = {'rest': '#f3d9b1', 'rocker': '#f6c7a8', 'hinged': '#cfe0c3', 'sliding': '#d7e6d0', 'light': '#fbe7a1',
                 'flame': '#f9c39a', 'spinner': '#c9dcf0', 'swinging': '#d9d2ef', 'swaying': '#d2ecd9', 'bobbing': '#f6d0de',
                 'appliance': '#dde3e8', 'timekeeper': '#ece2d0', 'still': '#e6e1da'}
GROUPS = [('rest', 'rocker', 'hinged', 'sliding'), ('light', 'flame', 'appliance', 'timekeeper', 'still'),
          ('spinner', 'swinging', 'swaying', 'bobbing')]


def esc(text):
    return html.escape(str(text))


def motions(arch, one_piece=False):
    """'문 열림(E) · 불빛 켜짐(E)' for a type's behaviours (or its one-piece presets)."""
    out = []
    for b in (arch['single'] if one_piece else arch['behaviours']):
        part = '전체' if b['role'] == 'whole' else ROLE_NAMES[b['role']]
        out.append('%s %s(%s)' % (part, KIND_KO[b['kind']], TRIGGER_KO[b.get('trigger', 'click')]))
    return ' · '.join(out)


def summary(arch):
    text = motions(arch)
    rest = REST_KO[arch.get('rest', '')]
    return ' · '.join(x for x in (text, rest) if x) or '움직임 없음 (모양만)'


# ---------------------------------------------------------------- pages

CSS = '''
@font-face{font-family:P;src:url("%(fonts)s/Pretendard-Regular.woff");font-weight:400}
@font-face{font-family:P;src:url("%(fonts)s/Pretendard-SemiBold.woff");font-weight:600}
@font-face{font-family:P;src:url("%(fonts)s/Pretendard-Bold.woff");font-weight:700}
*{box-sizing:border-box}
body{margin:0;background:#fbf8f2;font-family:P,"Malgun Gothic",sans-serif;color:#2d2a26;width:%(width)dpx}
.page{padding:40px 44px 36px}
h1{font-size:48px;margin:0 0 8px;letter-spacing:-1px}
.sub{font-size:25px;color:#6b6258;margin:0 0 26px;line-height:1.45}
.box{border:3px solid #3a342d;border-radius:18px;background:#fff;overflow:hidden}
.hd{padding:12px 20px;font-size:31px;font-weight:700;background:#efe4d2;border-bottom:3px solid #3a342d}
.hd small{font-weight:400;font-size:23px;color:#5d554c;margin-left:10px}
.bd{padding:14px 20px;font-size:25px;line-height:1.5}
.bd b{font-weight:700}
.mono{font-family:Consolas,monospace;font-size:22px;color:#5d554c}
.arrow{font-size:25px;color:#6b6258;text-align:center;margin:10px 0;font-weight:600}
.arrow:before{content:"▼ ";color:#3a342d}
.row{display:flex;gap:20px}
.row>.box{flex:1}
.chip{display:inline-block;border:2px solid #3a342d;border-radius:12px;padding:2px 10px;margin:4px 6px 4px 0;font-size:22px;background:#fffaf0}
.step{display:flex;gap:18px;align-items:flex-start}
.num{flex:none;width:58px;height:58px;border-radius:29px;background:#3a342d;color:#fff;font-size:30px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:6px}
.side{border:3px dashed #8a7f73;border-radius:18px;padding:12px 18px;font-size:23px;line-height:1.45;background:#f6f0e6;margin-top:18px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.member{padding:7px 0;border-bottom:1px solid #e3dccf;font-size:24px;line-height:1.4}
.member:last-child{border-bottom:none}
.member .id{font-family:Consolas,monospace;font-size:20px;color:#7a7065;margin-left:6px}
.member .what{display:block;color:#4a433b;font-size:22px}
.foot{font-size:20px;color:#8a7f73;margin-top:22px}
'''


def page(title, sub, body):
    fonts = FONTS.resolve().as_uri()
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>%s</style></head><body><div class="page">'
            '<h1>%s</h1><div class="sub">%s</div>%s<div class="foot">Villagen · archetype library v%d · %d종 · '
            'tools/archetype_docs.py로 다시 그림</div></div></body></html>') % (
        CSS % {'fonts': fonts, 'width': WIDTH}, esc(title), sub, body, VERSION, len(ARCHETYPES))


def box(head, small, body, colour='#efe4d2'):
    return '<div class="box"><div class="hd" style="background:%s">%s<small>%s</small></div><div class="bd">%s</div></div>' % (
        colour, head, small, body)


def code_page():
    builders = ['body', 'whole', 'part', 'side_door', 'lid', 'drop_door', 'drawer', 'lit', 'flame', 'rotor', 'turntable',
                'hanging', 'tap', 'furniture']
    kinds = ''.join('<span class="chip">%s · %s</span>' % (k, KIND_KO[k]) for k in KINDS)
    body = ''.join([
        box('유형 라이브러리 <span class="mono">ArchetypeLibrary</span>', 'server/archetype_library.py',
            'VERSION %d · <b>ARCHETYPES</b> %d종 · <b>FAMILIES</b> 부모 클래스 %d개 · <b>ROOMS</b> 방 %d곳 · '
            '<b>ROLE_NAMES</b> 부품 이름 %d개<br>빌더(같은 부품을 한 번만 정의): %s' % (
                VERSION, len(ARCHETYPES), len(FAMILIES), len(ROOMS), len(ROLE_NAMES),
                ' '.join('<span class="chip">%s()</span>' % b for b in builders))),
        '<div class="arrow">1 : 108 — 유형 하나하나</div>',
        '<div class="row">' + box('유형 <span class="mono">Archetype</span>', '예: fridge 냉장고',
                                  '<b>id</b>, <b>names</b>{ko, en}<br><b>family</b> → 부모 클래스<br><b>room</b> → 방<br>'
                                  '<b>words</b> 부르는 말<br><b>roles</b>[ ] 부품 역할<br><b>behaviours</b>[ ] 움직임 카드<br>'
                                  '<b>single</b>[ ] 한 덩어리일 때<br><b>rest</b> 앉기·눕기<br><b>fixture</b> 오프라인 설계도') +
        box('부모 클래스 <span class="mono">Family</span>', '13개',
            '공유 부품 + 공유 움직임<br>예: <b>여닫이</b> = 본체 + 문·뚜껑, hinge<br><b>빛나는 것</b> = 받침 + 빛, glow·pulse·hue<br>'
            '<b>도는 것</b> = 본체 + 날개, rotor·turn<br><b>가전</b> = 여닫이 + 빛 + 회전<br>→ 그림 ③') + '</div>',
        '<div class="arrow">유형 1 : N</div>',
        '<div class="row">' + box('부품 역할 <span class="mono">Role</span>', '',
                                  '<b>id</b> (door, lid, flame…)<br><b>words</b> 같은 뜻의 이름<br><b>hint</b> 디자이너에게: 무엇, '
                                  '부모, 회전점<br><b>root</b> · <b>optional</b><br><b>primitive</b> 게임이 직접 만듦(시계 바늘)<br>'
                                  '한국어 이름 = ROLE_NAMES[id]') +
        box('움직임 카드 <span class="mono">Behaviour</span>', '',
            '<b>role</b> 어느 부품<br><b>kind</b> 어떤 움직임<br><b>trigger</b> 언제<br><b>level</b> 세기 1~3<br>'
            '<b>axis</b> · <b>angle</b> · <b>direction</b><br><b>or_whole</b> 부품이 없으면 전체가') + '</div>',
        '<div class="arrow">bind(): 역할 → 실제 부품 id · presets_for()</div>',
        box('상호작용 프리셋 <span class="mono">interactions.Preset</span>', 'server/interactions.py',
            '<b>kind</b> ∈ KINDS %d가지<br>%s<br><b>trigger</b> ∈ click(E) · near(가까이) · leave(멀어지면) · always(항상) · '
            '<b>target</b> 부품 또는 whole(전체) · <b>level</b> 1~3 · 최대 %d장' % (len(KINDS), kinds, 6)),
        '<div class="arrow">build() → check(): 안전 검사</div>',
        box('VM 프로그램 <span class="mono">program</span>', '서버가 저장 (object_interactions)',
            '<b>state</b> 숫자 상태 · <b>events</b> spawn · click · near · leave · tick<br>'
            '<b>emit</b> rotate_x/y/z · offset_x/y/z · emission · hue · <b>idle</b> 멈춘 상태'),
        '<div class="arrow">조립 응답 (assembly) → 게임</div>',
        box('게임 (클라이언트)', 'game/scripts',
            '<b>asset_assembly.gd</b> 부품을 회전점(pivot)에 붙임<br><b>asset_vm.gd</b> 매 프레임 프로그램 실행 → 부품을 돌리고 밀고 빛냄<br>'
            '<b>interaction_panel.gd</b> 편집기: 카드 고치기, 부품 이름(PART_NAMES)'),
        '<div class="side"><b>server/archetypes.py</b> — classify() 말 → 유형 · designer_hint() 디자이너 안내 · bind() · '
        'presets_for() · assign() 새 물건의 첫 동작 · primitive_parts()/seat_parts() 시계 바늘 · fixture_design() 오프라인 설계 · '
        'craft_kind() 제작창 · public() 목록(GET /v1/studio/library)<br><b>server/behaviour_library.py</b> — 배운 설계·동작을 '
        '다시 씀 (열쇠에 VERSION이 들어가서, 유형이 바뀌면 새로 배움)</div>',
    ])
    return page('① 코드 구조', '유형 라이브러리의 데이터가 어떻게 게임 속 움직임이 되는지 (클래스와 함수)', body)


def flow_page():
    steps = [
        ('플레이어의 말', '"<b>흔들의자</b> 만들어 줘" · "a rocking chair"'),
        ('유형 찾기 <span class="mono">classify()</span>', '단어 끝을 맞춤 (조사 \'를\'은 뗌). 같은 자리면 긴 말이 이김: '
         '흔들의자 &gt; 의자 → <b>rocking_chair</b>. 영어는 with/of 앞의 말.'),
        ('디자이너 안내 <span class="mono">designer_hint()</span>', '"부품 id는 seat, legs… 회전점은 여기" — LLM 디자이너가 '
         '움직일 부품을 따로 나누고 회전점을 바르게 둠. (개발용 오프라인은 fixture 설계도)'),
        ('설계도 plan', '부품 최대 8개: 모양·크기·위치·부모·회전점(pivot)·색. 시계 바늘처럼 게임이 직접 만드는 부품은 크레딧 0.'),
        ('3D 모델', 'Tripo가 부품마다 메쉬를 만듦 (개발 서버는 상자·공 모양 대역).'),
        ('첫 동작 정하기 <span class="mono">assign()</span>', 'bind(): 역할 ↔ 실제 부품 → 움직임 카드(프리셋) → build() → '
         'check() 통과 → 물건의 상호작용으로 저장. 한 덩어리면 single 카드, 앉기·눕기는 rest.'),
        ('게임에서 살아남', 'E·가까이·항상에 맞춰 asset_vm.gd가 프로그램을 돌림: 문이 열리고, 불이 일렁이고, 날개가 돎. '
         '흔들의자는 E로 앉으면 흔들림.'),
        ('주인이 고침', '상호작용 편집기에서 카드를 바꾸거나 \'원래대로\'. 같은 문장의 설계는 behaviour_library가 기억해 다시 씀.'),
    ]
    body = ''
    for n, (head, text) in enumerate(steps, 1):
        body += '<div class="step"><div class="num">%d</div>%s</div>' % (n, box(head, '', text))
        if n < len(steps):
            body += '<div style="height:12px"></div>'
    return page('② 요청에서 살아 있는 물건까지', '플레이어가 말한 한 문장이 움직이는 가구가 되는 순서', body)


def families_page():
    count = Counter(a['family'] for a in ARCHETYPES)
    builders = {'rest': 'body · whole', 'rocker': 'whole · hanging', 'hinged': 'side_door · lid · drop_door · tap',
                'sliding': 'drawer', 'light': 'lit', 'flame': 'flame', 'spinner': 'rotor · turntable',
                'swinging': 'hanging', 'swaying': 'part(sway)', 'bobbing': 'part(bounce)',
                'appliance': 'side_door + lit + rotor', 'timekeeper': '(직접 작성)', 'still': 'body'}
    cells = ''
    for fid, fam in FAMILIES.items():
        examples = ', '.join(a['names']['ko'] for a in ARCHETYPES if a['family'] == fid)
        if len(examples) > 46:
            examples = examples[:44].rsplit(',', 1)[0] + ' …'
        cells += box('%s' % esc(fam['ko']), '%s · %d종' % (esc(fam['en']), count[fid]),
                     '<b>부품</b> %s<br><b>움직임</b> %s<br><b>빌더</b> <span class="mono">%s</span><br><span style="color:#6b6258">%s</span>' % (
                         esc(fam['parts']), esc(fam['motions']), esc(builders[fid]), esc(examples)), FAMILY_COLOUR[fid])
    body = (box('유형 <span class="mono">Archetype</span>', '모든 유형의 공통',
                'id · 이름 · 부르는 말 · 부품 역할 · 움직임 카드 · 한 덩어리 카드 · 앉기/눕기 · 오프라인 설계도') +
            '<div class="arrow">13개의 부모 클래스가 공통 부품과 움직임을 물려줌</div><div class="grid">%s</div>'
            '<div class="side"><b>가전</b>은 여러 부모를 함께 씀 (여닫이 문 + 빛나는 불빛 + 도는 통). 새 유형은 가장 가까운 '
            '부모의 빌더로 부품을 고르면 됨.</div>') % cells
    return page('③ 가구 분류: 부모 클래스', '같은 부품·같은 움직임을 가진 유형끼리 묶은 13개의 부모 클래스', body)


def types_page(n, families):
    body = ''
    for fid in families:
        members = [a for a in ARCHETYPES if a['family'] == fid]
        rows = ''.join('<div class="member"><b>%s</b><span class="id">%s</span><span class="what">%s</span></div>' % (
            esc(a['names']['ko']), esc(a['id']), esc(summary(a))) for a in members)
        body += box(esc(FAMILIES[fid]['ko']), '%s · %d종' % (esc(FAMILIES[fid]['en']), len(members)), rows,
                    FAMILY_COLOUR[fid]) + '<div style="height:18px"></div>'
    return page('④ 유형 목록 %d/%d' % (n, len(GROUPS)), '부모 클래스별 유형과 움직임. (E) = E키·클릭, (가까이) = 다가가면, '
                '(항상) = 늘 움직임', body)


# ---------------------------------------------------------------- drawing

def chrome():
    for path in CHROME:
        if path.exists():
            return path
    raise SystemExit('Chrome or Edge is needed to draw the pages')


def draw(name, markup, work):
    """Draws one page to docs/objects/img/<name>.png: cropped to its content, at most 256 colours."""
    source = work / (name + '.html')
    source.write_text(markup, encoding='utf-8')
    shot = work / (name + '.png')
    subprocess.run([str(chrome()), '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                    '--window-size=%d,6000' % WIDTH, '--default-background-color=fbf8f2ff', '--screenshot=' + str(shot),
                    source.as_uri()], check=True, capture_output=True, timeout=120)
    image = Image.open(shot).convert('RGB')
    # Crop the empty page below the content (the background colour runs to the bottom).
    background = image.getpixel((WIDTH - 2, image.height - 2))
    bottom = image.height
    pixels = image.load()
    while bottom > 10 and all(pixels[x, bottom - 1] == background for x in range(0, WIDTH, 7)):
        bottom -= 1
    image = image.crop((0, 0, WIDTH, min(image.height, bottom + 24)))
    image = image.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    target = IMG / (name + '.png')
    image.save(target, optimize=True)
    print('%s  %dx%d  %d KB' % (target.relative_to(ROOT), image.width, image.height, target.stat().st_size // 1024))


def type_list():
    """The markdown list of every type by room, for ARCHETYPES_KO.md."""
    out = []
    count = Counter(a['room'] for a in ARCHETYPES)
    for room, title in ROOMS.items():
        out.append('### %s (%d종)\n' % (title, count[room]))
        out.append('| 유형 | 부르는 말 | 부품 (역할) | 움직임 | 쉬기 | 부모 클래스 |')
        out.append('|---|---|---|---|---|---|')
        for a in (a for a in ARCHETYPES if a['room'] == room):
            words = ', '.join(a['words'])
            parts = ', '.join('%s%s' % (ROLE_NAMES[r['id']], '(선택)' if r.get('optional') else '') for r in a['roles'])
            moving = motions(a) or '-'
            single = motions(a, True)
            if single:
                moving += '<br>한 덩어리: ' + single
            out.append('| **%s** `%s` | %s | %s | %s | %s | %s |' % (a['names']['ko'], a['id'], words, parts, moving,
                                                                  REST_KO[a.get('rest', '')] or '-', FAMILIES[a['family']]['ko']))
        out.append('')
    return '\n'.join(out)


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        draw('archetype_code', code_page(), work)
        draw('archetype_flow', flow_page(), work)
        draw('archetype_families', families_page(), work)
        for n, families in enumerate(GROUPS, 1):
            draw('archetype_types_%d' % n, types_page(n, families), work)
    doc = OUT / 'ARCHETYPES_KO.md'
    if doc.exists():
        text = doc.read_text(encoding='utf-8')
        start, end = '<!-- types:start -->', '<!-- types:end -->'
        if start in text and end in text:
            head, rest = text.split(start, 1)
            text = head + start + '\n' + type_list() + '\n' + end + rest.split(end, 1)[1]
            doc.write_text(text, encoding='utf-8', newline='\n')
            print('docs/objects/ARCHETYPES_KO.md: type list updated')


if __name__ == '__main__':
    main()
