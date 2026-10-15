"""Figures for the Korean ISS-1 standard (docs/design/ISS1_KO.md), drawn with Pillow.

    .tools/art-venv/Scripts/python.exe tools/ix_doc_figures.py

Writes docs/design/iss1/fig1..fig6 (PNG). No network, no paid calls.
"""
import math
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'design' / 'iss1'
FONT = 'C:/Windows/Fonts/malgun.ttf'
BOLD = 'C:/Windows/Fonts/malgunbd.ttf'

INK = (38, 44, 52)
SOFT = (110, 118, 128)
PAPER = (250, 248, 243)
GOLD = (226, 170, 40)
BLUE = (70, 140, 225)
GREEN = (80, 170, 95)
ORANGE = (235, 130, 50)
CYAN = (40, 185, 200)
RED = (220, 70, 60)
PURPLE = (150, 110, 220)
GREY = (160, 160, 160)
WOOD = (186, 140, 96)
WOOD_D = (140, 100, 66)
BODY = (96, 120, 150)


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def canvas(w, h, title, subtitle=''):
    img = Image.new('RGB', (w, h), PAPER)
    d = ImageDraw.Draw(img)
    d.text((36, 22), title, fill=INK, font=font(34, True))
    if subtitle:
        d.text((38, 70), subtitle, fill=SOFT, font=font(20))
    return img, d


def arrow(d, a, b, color, width=4, head=14):
    d.line([a, b], fill=color, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for s in (-1, 1):
        p = (b[0] - head * math.cos(ang + s * 0.45), b[1] - head * math.sin(ang + s * 0.45))
        d.line([b, p], fill=color, width=width)


def cross(d, p, color, r=10, width=4):
    d.line([(p[0] - r, p[1]), (p[0] + r, p[1])], fill=color, width=width)
    d.line([(p[0], p[1] - r), (p[0], p[1] + r)], fill=color, width=width)


def dot(d, p, color, r=8):
    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)


def label(d, p, text, color=INK, size=20, bold=False, anchor='la'):
    d.text(p, text, fill=color, font=font(size, bold), anchor=anchor)


def box(d, xy, fill, outline=None, r=10):
    d.rounded_rectangle(xy, r, fill=fill, outline=outline, width=2)


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    img.convert('P', palette=Image.ADAPTIVE, colors=128).save(path, optimize=True)
    print(name, path.stat().st_size)


def fig1():
    img, d = canvas(1500, 820, '그림 1 · 의자 하나에 담긴 소켓 정보', '물체는 "어디에 어떻게 앉는지"를, 캐릭터는 "몸의 어느 점이 닿는지"를 말합니다. 둘이 만나는 점이 소켓입니다.')
    floor_y = 690
    d.line([(60, floor_y), (1440, floor_y)], fill=SOFT, width=3)
    label(d, (70, floor_y + 10), '바닥 (y = 0)', SOFT, 18)
    # Chair, side view: +Z (front) points to the right.
    seat_y = floor_y - 45 * 4.5
    d.rectangle([380, seat_y, 600, seat_y + 22], fill=WOOD)
    d.rectangle([380, seat_y - 230, 400, seat_y], fill=WOOD_D)
    d.rectangle([388, seat_y + 22, 402, floor_y], fill=WOOD_D)
    d.rectangle([580, seat_y + 22, 594, floor_y], fill=WOOD_D)
    # Seat socket.
    sp = (505, seat_y)
    cross(d, sp, GOLD, 14, 5)
    arrow(d, sp, (sp[0] + 110, sp[1]), GOLD, 5)
    d.line([sp, (230, sp[1] - 120)], fill=GOLD, width=2)
    label(d, (90, sp[1] - 160), 'seat_0  (sit)', GOLD, 24, True)
    label(d, (90, sp[1] - 128), '앉는 소켓: 엉덩이가 닿는 점', GOLD, 18)
    label(d, (650, sp[1] + 40), '→ +Z = 앉은 사람의 가슴 방향', GOLD, 18)
    # Height dimension.
    d.line([(350, seat_y), (350, floor_y)], fill=INK, width=2)
    d.line([(342, seat_y), (358, seat_y)], fill=INK, width=2)
    label(d, (240, floor_y - 40), '높이 0.45 m', INK, 18)
    # Approach point.
    ap = (840, floor_y - 4)
    cross(d, ap, CYAN, 16, 5)
    arrow(d, ap, (ap[0] - 120, ap[1]), CYAN, 4)
    label(d, (ap[0] - 70, ap[1] - 60), '다가설 자리 (approach)', CYAN, 22, True)
    label(d, (ap[0] - 70, ap[1] - 34), '발이 서는 점 · 도착 방향', CYAN, 18)
    # Character sitting (simple body): hips on the socket.
    hip = (sp[0] + 4, sp[1] - 12)
    knee = (hip[0] + 110, hip[1] - 4)
    ankle = (knee[0] + 6, floor_y - 18)
    d.line([hip, knee], fill=BODY, width=26)
    d.line([knee, ankle], fill=BODY, width=22)
    d.line([ankle, (ankle[0] + 40, floor_y - 8)], fill=BODY, width=14)
    torso_top = (hip[0] - 20, hip[1] - 190)
    d.line([hip, torso_top], fill=BODY, width=40)
    d.ellipse([torso_top[0] - 34, torso_top[1] - 76, torso_top[0] + 34, torso_top[1] - 8], fill=BODY)
    dot(d, (hip[0], hip[1] + 10), RED, 9)
    d.line([(hip[0], hip[1] + 10), (230, hip[1] + 120)], fill=RED, width=2)
    label(d, (60, hip[1] + 124), 'seat_contact (캐릭터 소켓)', RED, 20, True)
    label(d, (60, hip[1] + 150), '허벅지 관절보다 0.10 m 아래', RED, 18)
    # Right column: what the record says.
    box(d, (1030, 140, 1460, 640), (255, 255, 255), GREY)
    rows = [('id', 'seat_0  (바뀌지 않는 이름)'), ('type', 'sit  (앉기)'), ('variant', 'chair · bench · sofa …'),
            ('at', '[0, 0.5, 0.08]  상자 안 비율'), ('yaw', '0°  물체 앞(+Z) 기준'), ('snap', '실제 메시 위로 높이 맞춤'),
            ('params', 'back, arms, width, depth'), ('approach', '앞 0.35~0.70 m, ±45°, 옆'), ('source', 'authored·server·derived·bbox')]
    label(d, (1052, 156), '소켓 기록 (record)', INK, 24, True)
    for i, (k, v) in enumerate(rows):
        y = 204 + i * 47
        label(d, (1052, y), k, BLUE, 20, True)
        label(d, (1170, y), v, INK, 19)
    save(img, 'fig1_overview.png')


def fig2():
    img, d = canvas(1500, 900, '그림 2 · 소켓 종류 (닫힌 목록, v1)', '종류가 늘면 표준 버전이 올라갑니다. 높이는 바닥에서 접점까지(실제 메시 기준).')
    types = [
        ('sit', '앉기', GOLD, '0.15~0.68 m', 'seat_contact', '의자 · 벤치 · 소파'),
        ('perch', '높은 의자', ORANGE, '0.65~1.10 m', 'seat_contact', '바 의자 · 높은 의자'),
        ('sit_ground', '바닥 앉기', (200, 160, 70), '< 0.15 m', 'seat_contact', '러그 · 방석'),
        ('lie', '눕기', BLUE, '0.10~1.05 m', 'pelvis_lie', '침대 · 선베드 · 해먹'),
        ('stand_use', '서서 쓰기', GREEN, '바닥', 'root', '조리대 · 책상 · 레버'),
        ('reach', '손 뻗기', (90, 150, 90), '바닥', 'root + grip_r', '밭 · 채집'),
        ('grip', '손잡이', ORANGE, '손잡이 중심', 'grip_r / grip_l', '도구 · 손잡이'),
        ('look_at', '바라보기', SOFT, '보는 점', 'eyes', '구경거리'),
        ('passage', '지나가기', PURPLE, '문턱', 'root', '문 · 통로'),
        ('place', '올려놓기', GREEN, '표면', 'hold_front', '선반 · 탁자'),
        ('talk', '대화', SOFT, 'NPC 1.1~1.4 m', 'root + eyes', '말 걸기'),
    ]
    for i, (key, ko, color, height, char, ex) in enumerate(types):
        col = i % 3
        row = i // 3
        x = 40 + col * 485
        y = 120 + row * 190
        box(d, (x, y, x + 465, y + 172), (255, 255, 255), color)
        d.rectangle([x, y, x + 12, y + 172], fill=color)
        label(d, (x + 30, y + 14), key, color, 28, True)
        label(d, (x + 30 + font(28, True).getlength(key) + 14, y + 22), ko, INK, 22, True)
        label(d, (x + 30, y + 66), '높이 ' + height, INK, 19)
        label(d, (x + 30, y + 96), '캐릭터 소켓: ' + char, INK, 19)
        label(d, (x + 30, y + 126), '예: ' + ex, SOFT, 18)
    label(d, (40, 870), 'v1 데모에서 실제로 동작: sit · perch · sit_ground · lie (나머지는 데이터 규격만 정해 두고 WP12~13에서 연결)', RED, 19, True)
    save(img, 'fig2_types.png')


def fig3():
    img, d = canvas(1300, 980, '그림 3 · 캐릭터 소켓 (모든 캐릭터 공통 Explorer B 뼈대)', '이름은 뼈 이름과 무관하게 고정. 위치는 뼈대의 기본 자세에서 측정하므로 숫자를 입력하지 않습니다.')
    cx = 520
    ground = 900
    s = 400  # pixels per metre
    def P(x, y):
        return (cx + x * s, ground - y * s)
    # Body.
    d.ellipse([*P(-0.11, 1.62), *P(0.11, 1.36)], outline=BODY, width=6)
    d.line([P(0, 1.36), P(0, 0.88)], fill=BODY, width=10)
    d.line([P(-0.18, 1.22), P(0.18, 1.22)], fill=BODY, width=8)
    for sx in (-1, 1):
        d.line([P(0.18 * sx, 1.22), P(0.24 * sx, 0.98), P(0.27 * sx, 0.78)], fill=BODY, width=8)
        d.line([P(0.08 * sx, 0.88), P(0.10 * sx, 0.49), P(0.12 * sx, 0.07)], fill=BODY, width=9)
        d.line([P(0.12 * sx, 0.07), P(0.12 * sx, 0.03)], fill=BODY, width=9)
    d.line([P(-0.6, 0), P(0.6, 0)], fill=SOFT, width=3)
    pts = [
        ('overhead', (0, 2.05), '이름표 · 말풍선 (서 있을 때 2.05 m)'),
        ('head_top', (0, 1.66), '모자'),
        ('eyes', (0.05, 1.50), '시선의 출발점 · 남이 보는 곳'),
        ('mouth', (0.05, 1.42), '먹기 · 마시기'),
        ('hold_front', (0.0, 1.10), '두 손 들기 · 선물 (가슴 앞 0.25 m)'),
        ('back', (-0.02, 1.16), '가방'),
        ('pelvis_lie', (0.0, 0.874), '엉덩이 중심 → 눕기 소켓에'),
        ('seat_contact', (0.0, 0.774), '허벅지 관절 −0.10 m → 앉기 소켓에'),
        ('grip_r', (0.27, 0.80), '오른손 도구 (player.gd 값 그대로)'),
        ('hip_r', (0.16, 0.84), '허리에 찬 도구'),
        ('sole_l / sole_r', (-0.12, 0.0), '발바닥 (바닥 높이)'),
        ('root', (0.0, 0.0), '발 사이 바닥, +Z = 앞'),
    ]
    for i, (name, (x, y), text) in enumerate(pts):
        p = P(x, y)
        dot(d, p, RED if name in ('seat_contact', 'pelvis_lie') else GOLD, 9)
        ty = 120 + i * 64
        d.line([p, (860, ty + 14)], fill=GREY, width=2)
        label(d, (870, ty), name, RED if name in ('seat_contact', 'pelvis_lie') else INK, 22, True)
        label(d, (870, ty + 28), text, SOFT, 18)
    label(d, (60, 930), '측정값: 엉덩이(허벅지 관절) 높이 0.874 m · 허벅지 0.376 m · 정강이 0.439 m · 발목 0.066 m (CHARACTER_SCALE 1.7 적용 후)', INK, 18)
    save(img, 'fig3_character.png')


def fig4():
    img, d = canvas(1500, 820, '그림 4 · 물체 위 위치 규칙 (위에서 본 모습)', '앞은 +Z, 원점은 바닥 면 중심. at = 상자 비율이라 물체를 키우거나 뒤집어도 같은 자리를 가리킵니다.')
    # Left: frame and fractions.
    ox, oy, w, h = 120, 160, 420, 420
    d.rectangle([ox, oy, ox + w, oy + h], outline=INK, width=3)
    for i in range(1, 4):
        d.line([(ox + w * i / 4, oy), (ox + w * i / 4, oy + h)], fill=(225, 222, 214), width=1)
        d.line([(ox, oy + h * i / 4), (ox + w, oy + h * i / 4)], fill=(225, 222, 214), width=1)
    label(d, (ox - 8, oy + h + 8), 'x −0.5', SOFT, 16)
    label(d, (ox + w - 40, oy + h + 8), '+0.5', SOFT, 16)
    label(d, (ox + w + 10, oy - 4), 'z −0.5 (뒤)', SOFT, 16)
    label(d, (ox + w + 10, oy + h - 20), 'z +0.5 (앞)', SOFT, 16)
    arrow(d, (ox + w / 2, oy + h + 40), (ox + w / 2, oy + h + 110), BLUE, 5)
    label(d, (ox + w / 2 + 12, oy + h + 70), '+Z = 앞', BLUE, 20, True)
    d.rectangle([ox, oy, ox + w, oy + 50], fill=WOOD_D)
    label(d, (ox + 12, oy + 12), '등받이', (255, 255, 255), 18)
    sp = (ox + w / 2, oy + h * 0.58)
    cross(d, sp, GOLD, 14, 5)
    arrow(d, sp, (sp[0], sp[1] + 90), GOLD, 5)
    label(d, (sp[0] + 16, sp[1] - 26), 'at = [0, 0.5, 0.08]', GOLD, 19, True)
    # Middle: shape and mirror.
    x2 = 650
    label(d, (x2, 140), '모양 바꾸기 · 좌우 반전', INK, 24, True)
    for i, (sx, mir, t) in enumerate([(1.0, False, '원래 (100%)'), (2.0, False, '가로 200% → 의자 2.0배 폭'), (1.0, True, '좌우 반전 (mirror)')]):
        y = 200 + i * 190
        ww = 150 * sx
        d.rectangle([x2, y, x2 + ww, y + 120], outline=INK, width=2)
        hx = x2 + ww * (0.3 if not mir else 0.7)
        d.rectangle([x2, y, x2 + ww, y + 16], fill=WOOD_D)
        cross(d, (hx, y + 70), GOLD, 10, 4)
        label(d, (hx - 8, y + 84), 'l', BLUE, 18, True)
        label(d, (x2 + ww + 14, y + 40), t, INK, 18)
    label(d, (x2, 770), '반전되면 l/r(손·머리 방향)이 바뀌고, id는 그대로입니다.', SOFT, 18)
    # Right: repeat on a bench.
    x3 = 1110
    label(d, (x3, 140), '반복 (긴 의자)', INK, 24, True)
    for i, (wid, n) in enumerate([(1.5, 2), (3.0, 5)]):
        y = 200 + i * 240
        ww = wid * 110
        d.rectangle([x3, y, x3 + ww, y + 90], outline=INK, width=2)
        for k in range(n):
            px = x3 + ww * (k + 0.5) / n
            cross(d, (px, y + 50), GOLD, 9, 4)
            label(d, (px - 22, y + 62), 'seat_%d' % k, GOLD, 14, True)
        label(d, (x3, y + 100), '폭 %.1f m → %d자리 (간격 0.55 m)' % (wid, n), INK, 18)
    save(img, 'fig4_frames.png')


def fig5():
    img, d = canvas(1600, 900, '그림 5 · 앉기와 일어나기의 흐름 (순간이동 없음)', '모든 이동은 물리 틱 안에서 한 틱에 0.08 m · 0.35 rad 이하. 이동 키는 다가가기를 바로 취소하고, E/Esc는 언제나 일어납니다.')
    states = [('CLAIM', '자리 고르기', '빈 자리·다가설\n자리를 고름', SOFT),
              ('APPROACH', '다가가기', '걷기 속도로\n마지막 0.5 m 감속', CYAN),
              ('ALIGN', '돌아서기', '남은 거리 미끄러짐\n초당 10 rad 회전', (60, 160, 170)),
              ('ENTER', '앉기', '0.55 s: 뒤·아래로\n자세 0→1', GOLD),
              ('HOLD', '앉아 있기', '흔들의자면\n엉덩이가 따라감', (200, 150, 30)),
              ('EXIT', '일어나기', '0.5 s: 위로 먼저\n그다음 앞으로', ORANGE),
              ('RECOVER', '되돌려주기', '빈 자리 위,\n의자 밖을 봄', GREEN)]
    for i, (key, ko, note, color) in enumerate(states):
        x = 40 + i * 222
        box(d, (x, 130, x + 200, 330), (255, 255, 255), color)
        d.rectangle([x, 130, x + 200, 140], fill=color)
        label(d, (x + 100, 160), key, color, 22, True, 'ma')
        label(d, (x + 100, 196), ko, INK, 24, True, 'ma')
        for j, line in enumerate(note.split('\n')):
            label(d, (x + 100, 246 + j * 28), line, SOFT, 17, False, 'ma')
        if i < len(states) - 1:
            arrow(d, (x + 202, 230), (x + 220, 230), INK, 3, 8)
    label(d, (40, 350), 'ABORT: 다른 것이 몸을 옮기면(문·순간이동) 그 자리에서 놓아주고 0.15 s에 자세를 풉니다. 시간이 넘치면 감시 타이머가 놓아줍니다.', RED, 18)
    # Curves: body height and pose weight over ENTER/EXIT.
    gx, gy, gw, gh = 120, 420, 1360, 380
    d.rectangle([gx, gy, gx + gw, gy + gh], outline=GREY, width=2)
    label(d, (gx, gy - 34), '몸의 높이와 자세 무게 (ENTER 0.55 s → HOLD → EXIT 0.5 s)', INK, 21, True)
    def ss(e0, e1, x):
        t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
        return t * t * (3 - 2 * t)
    pts_y, pts_w, pts_xz = [], [], []
    total = 0.55 + 0.4 + 0.5
    for k in range(301):
        tt = total * k / 300
        if tt <= 0.55:
            u = tt / 0.55
            y = ss(0.25, 1.0, u)
            w = ss(0.0, 0.9, u)
            xz = ss(0.10, 0.85, u)
        elif tt <= 0.95:
            y = w = xz = 1.0
        else:
            u = (tt - 0.95) / 0.5
            y = ss(0.25, 1.0, 1 - u)
            w = ss(0.0, 0.9, 1 - u)
            xz = ss(0.10, 0.85, 1 - u)
        px = gx + gw * k / 300
        pts_y.append((px, gy + 20 + (gh - 40) * y))
        pts_w.append((px, gy + gh - 20 - (gh - 40) * w))
        pts_xz.append((px, gy + gh - 20 - (gh - 40) * xz))
    d.line(pts_xz, fill=CYAN, width=4)
    d.line(pts_w, fill=GOLD, width=5)
    d.line(pts_y, fill=BLUE, width=5)
    label(d, (gx + 20, gy + gh + 14), '— 몸 내려가기 (0.25~1.0 구간, 무릎이 먼저 굽음)', BLUE, 18, True)
    label(d, (gx + 560, gy + gh + 14), '— 자세 무게 (0~0.9)', GOLD, 18, True)
    label(d, (gx + 860, gy + gh + 14), '— 앞뒤 이동 (0.10~0.85)', CYAN, 18, True)
    for t, name in [(0.0, 'E'), (0.55, '앉음'), (0.95, 'E 다시'), (1.45, '섬')]:
        px = gx + gw * t / total
        d.line([(px, gy), (px, gy + gh)], fill=(210, 205, 196), width=2)
        label(d, (px + 6, gy + 6), name, SOFT, 16)
    save(img, 'fig5_flow.png')


def fig6():
    img, d = canvas(1600, 960, '그림 6 · 외부 애니메이션 계약 (클립을 밖에서 만들 때)', '이름은 사람이 읽기 위한 것, 진짜 정보는 메타데이터. 숫자는 키트가 재므로 애니메이터는 입력하지 않습니다.')
    # Name breakdown.
    parts = [('sit', '가족', GOLD), ('chair', '변형', BLUE), ('enter', '단계', GREEN), ('l90', '수식어', ORANGE)]
    x = 60
    for i, (t, ko, c) in enumerate(parts):
        wpx = font(44, True).getlength(t)
        box(d, (x, 120, x + wpx + 30, 190), (255, 255, 255), c)
        label(d, (x + 15, 130), t, c, 44, True)
        label(d, (x + 15, 198), ko, INK, 18, True)
        x += wpx + 30
        if i < 3:
            label(d, (x + 4, 130), '_', INK, 44, True)
            x += 30
    rules = ['소문자·숫자와 _ 만, 최대 48자, 단어 6개까지',
             '끝 단어 금지: loop, cycle, col, navmesh, rigid … (가져오기 이름 규칙과 충돌)',
             '숫자로 끝나는 말은 l90 · r90 · b180 만 허용',
             '가족: sit perch sitg lie use reach crouch door talk give take carry tool act emote',
             '단계: enter hold exit act fidget react  ·  반복은 이름이 아니라 메타의 loop']
    for i, r in enumerate(rules):
        label(d, (60, 240 + i * 32), '· ' + r, INK, 19)
    # Marker timeline.
    tx, ty, tw = 60, 470, 900
    label(d, (tx, ty - 50), '마커 (Animation.add_marker) — ENTER 클립 예', INK, 22, True)
    d.line([(tx, ty), (tx + tw, ty)], fill=INK, width=4)
    for t, name, c in [(0.0, '0: 발 위의 Root', SOFT), (0.12, 'warp_begin', CYAN), (0.7, 'contact', RED), (0.85, 'settled', GOLD), (1.0, '끝 = HOLD 첫 프레임', SOFT)]:
        px = tx + tw * t
        d.line([(px, ty - 14), (px, ty + 14)], fill=c, width=4)
        label(d, (px, ty + 22), name, c, 17, True, 'ma')
    label(d, (tx, ty + 70), 'warp_begin~contact 사이에서 실제 의자 위치로 부드럽게 휘어짐(최대 0.35 m · 45°, 높이 ±0.18 m).', SOFT, 17)
    label(d, (tx, ty + 96), 'EXIT 클립: release (손 떼기) → exit_ok (이 뒤로 이동 키가 걷기로 이어짐).', SOFT, 17)
    # Reference dims.
    box(d, (1010, 400, 1560, 900), (255, 255, 255), GREY)
    label(d, (1030, 414), '기준 소품 높이 (키트 · m)', INK, 22, True)
    dims = [('의자 / 벤치', '0.45'), ('소파', '0.42'), ('낮은 의자', '0.30'), ('바 의자 (perch)', '0.72'), ('바닥', '0'),
            ('침대', '윗면 0.50 · 길이 2.0 · 폭 0.9'), ('해먹', '1.0'), ('선베드', '0.35 · 등받이 35°'), ('조리대', '0.90'),
            ('책상 · 탁자', '0.75'), ('대화 상대', '1.1 m 떨어짐')]
    for i, (k, v) in enumerate(dims):
        label(d, (1030, 456 + i * 39), k, INK, 19)
        label(d, (1260, 456 + i * 39), v, BLUE, 19, True)
    # Pipeline.
    label(d, (60, 640), '넣는 방법 (코드 수정 없음)', INK, 22, True)
    steps = ['art/anim_inbox/<가족>/ 에 원본 + .ix.json', 'tools/ix_intake.py (Blender) → VRS 뼈대로 리타깃, 30 fps',
             'tests/ix_clip_bake.gd → 검사 후 assets/anim/interact/<세트>.res', 'PCK 패치로 배포 · 없으면 절차적 자세로 자동 대체']
    for i, s in enumerate(steps):
        y = 690 + i * 56
        box(d, (60, y, 940, y + 44), (255, 255, 255), GREEN)
        label(d, (80, y + 10), '%d. %s' % (i + 1, s), INK, 19)
    label(d, (60, 920), '리타깃: Explorer B 기준 뼈대(71개, 몸 41개 필수). Mixamo/Rigify/VRM 등은 뼈 이름표로 맞춤. 앞 방향 화살표 = GLB +X.', SOFT, 17)
    save(img, 'fig6_clip_contract.png')


if __name__ == '__main__':
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()
    fig6()
