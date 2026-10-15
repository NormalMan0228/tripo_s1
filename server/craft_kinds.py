"""The kinds a player may pick in the craft window ('기능' row) instead of letting the server guess.

Each is a library type (server/archetype_library.py) whose finished object really does something:
the type's interaction presets (open a lid, light up, turn, sway...) or its rest (rooms seat or lay
the walker on it). A picked kind replaces archetypes.classify() for that craft: the designer is told
the type and its part roles plus the size rule below, the fixture designer builds the type's parts,
and the object starts with the type's behaviours. '' (the default) keeps the guess from the words.

  id     the library type
  icon   a short id the game maps to one of its icons (craft_kinds_row.gd ICONS)
  zh     the Chinese name (the library has ko/en)
  does   what the finished object does, as the window words it
  hint   the size/shape rule the window shows and the designer is told

Adding a kind is one line here; the type must have presets or a rest (checked at import).
"""
from .archetypes import BY_ID, least_meshes

KINDS = [
    ('seat', 'chair', '椅子',
     {'ko': '앉기', 'en': 'Sit on it', 'zh': '可以坐'},
     {'ko': '앉는 높이 약 0.45 m · 등받이는 뒤쪽', 'en': 'Seat height about 0.45 m, backrest at the back', 'zh': '座高约0.45米，靠背在后侧'}),
    ('sofa', 'sofa', '沙发',
     {'ko': '앉기 · 쿠션 통통', 'en': 'Sit on it, cushions bounce', 'zh': '可以坐，坐垫会弹'},
     {'ko': '앉는 높이 약 0.42 m · 폭 1.6~2 m', 'en': 'Seat about 0.42 m high, 1.6-2 m wide', 'zh': '座高约0.42米，宽1.6~2米'}),
    ('rocking_chair', 'rocker', '摇椅',
     {'ko': '앉기 · 흔들흔들', 'en': 'Sit on it, it rocks', 'zh': '可以坐，会摇晃'},
     {'ko': '아래에 둥근 흔들 다리 · 앉는 높이 약 0.45 m', 'en': 'Curved rockers underneath, seat about 0.45 m high', 'zh': '底部弧形摇脚，座高约0.45米'}),
    ('bed', 'bed', '床',
     {'ko': '눕기', 'en': 'Lie on it', 'zh': '可以躺'},
     {'ko': '눕는 면 높이 약 0.5 m · 길이 약 2 m', 'en': 'Mattress top about 0.5 m high, about 2 m long', 'zh': '床面高约0.5米，长约2米'}),
    ('lamp', 'lamp', '台灯',
     {'ko': '눌러서 켜고 끄기', 'en': 'Click to switch the light', 'zh': '点击开关灯'},
     {'ko': '받침 위에 빛나는 갓·전구 · 높이 0.4~1.6 m', 'en': 'A stand with a glowing shade or bulb on top, 0.4-1.6 m tall', 'zh': '底座上有发光的灯罩或灯泡，高0.4~1.6米'}),
    ('lantern', 'lantern', '灯笼',
     {'ko': '불꽃이 일렁여요', 'en': 'A flickering flame', 'zh': '火光摇曳'},
     {'ko': '틀 안에 불빛 · 높이 약 0.3~0.6 m', 'en': 'A frame around a light, about 0.3-0.6 m tall', 'zh': '框架里有火光，高约0.3~0.6米'}),
    ('chest', 'chest', '箱子',
     {'ko': '뚜껑 열고 닫기', 'en': 'Open and close the lid', 'zh': '打开和关上盖子'},
     {'ko': '몸통 + 뒤쪽이 경첩인 뚜껑', 'en': 'A box with a lid hinged at the back', 'zh': '箱体加后侧铰链的盖子'}),
    ('cabinet', 'cabinet', '柜子',
     {'ko': '문 열고 닫기', 'en': 'Open and close the door', 'zh': '打开和关上柜门'},
     {'ko': '몸통 + 옆 모서리가 경첩인 앞문 · 높이 약 1~1.8 m', 'en': 'A body with a front door hinged at one side, about 1-1.8 m tall', 'zh': '柜体加侧边铰链的前门，高约1~1.8米'}),
    ('drawer', 'drawer', '抽屉柜',
     {'ko': '서랍 빼고 넣기', 'en': 'Pull the drawer out and in', 'zh': '拉出和推回抽屉'},
     {'ko': '몸통 + 앞으로 빠지는 서랍 · 높이 약 0.8 m', 'en': 'A case with a drawer sliding out the front, about 0.8 m tall', 'zh': '柜体加向前拉出的抽屉，高约0.8米'}),
    ('door', 'door', '门',
     {'ko': '다가가면 열려요', 'en': 'Opens when you come near', 'zh': '靠近时打开'},
     {'ko': '문틀 + 옆이 경첩인 문짝 · 높이 약 2.1 m', 'en': 'A frame with a leaf hinged at one side, about 2.1 m tall', 'zh': '门框加侧边铰链的门扇，高约2.1米'}),
    ('clock', 'clock', '时钟',
     {'ko': '실제 시각을 가리켜요', 'en': 'Shows the real time', 'zh': '显示真实时间'},
     {'ko': '몸통 + 빈 문자판 · 바늘은 공방이 무료로 달아요', 'en': 'A body with a blank dial; the workshop adds the hands for free', 'zh': '钟体加空白表盘，指针由工坊免费安装'}),
    ('fan', 'fan', '风扇',
     {'ko': '눌러서 날개 돌리기', 'en': 'Click to spin the blades', 'zh': '点击转动扇叶'},
     {'ko': '받침 + 앞을 보는 날개 · 높이 약 1 m', 'en': 'A stand with blades facing front, about 1 m tall', 'zh': '底座加朝前的扇叶，高约1米'}),
    ('music_box', 'music', '音乐盒',
     {'ko': '뚜껑이 열리고 인형이 돌아요', 'en': 'The lid opens and the dancer turns', 'zh': '盖子打开，小人旋转'},
     {'ko': '작은 상자 + 뚜껑 + 위에서 도는 장식', 'en': 'A small box, a lid and a figure that turns on top', 'zh': '小盒子加盖子和顶部旋转的装饰'}),
    ('plant', 'plant', '盆栽',
     {'ko': '다가가면 잎이 살랑', 'en': 'Leaves sway when you come near', 'zh': '靠近时叶子摇曳'},
     {'ko': '화분 + 잎·꽃 (뿌리 쪽이 화분에 닿게)', 'en': 'A pot with leaves or flowers rooted in it', 'zh': '花盆加扎根其中的叶子或花'}),
]

for _id, *_ in KINDS:
    assert _id in BY_ID and (BY_ID[_id]['behaviours'] or BY_ID[_id]['single'] or BY_ID[_id].get('rest')), _id

IDS = tuple(k[0] for k in KINDS)
BY_KIND = {k[0]: k for k in KINDS}


def public():
    """The kinds for GET /v1/studio: id, names, icon, does, hint and what the form needs (as
    POST /v1/studio/kind answers for a guessed type, plus needs_moving)."""
    out = []
    for kind_id, icon, zh, does, hint in KINDS:
        arch = BY_ID[kind_id]
        out.append({'id': kind_id, 'names': {**arch['names'], 'zh': zh}, 'icon': icon, 'does': does, 'hint': hint,
                    'rest': arch.get('rest', ''), 'moving_meshes': least_meshes(arch, 'dynamic'),
                    'always_moving': bool(arch.get('always_moving')), 'needs_moving': needs_moving(arch)})
    return out


def needs_moving(arch):
    """True when the type does its thing only with separate moving parts (a chest's lid, a fan's
    blades): a still one-piece craft of it would do nothing, so the window builds it moving."""
    return not (arch['single'] or arch.get('rest') or arch.get('always_moving'))


def size_rule(kind_id):
    """The English size rule the designer is told for a picked kind ('' for none)."""
    entry = BY_KIND.get(kind_id)
    return entry[4]['en'] if entry else ''
