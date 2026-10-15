"""The archetype library: object types the game knows how to bring to life, as plain data.

server/archetypes.py reads it; adding a type is adding one entry here (bump VERSION when an
existing entry changes, so learned designs made with the old wording are not reused).
docs/objects/ARCHETYPES_KO.md explains it for non-programmers, with the class diagrams.

Each archetype:
  id         the type, also what the LLM designer puts in plan.category
  names      ko/en display names
  family     its parent class (FAMILIES): the parts and motions it shares with similar types
  room       where it belongs, for listings (ROOMS)
  words      what players call it (Korean words match the end of a word, after a particle is
             dropped: '흔들의자를' -> '흔들의자'; English words match whole words, plural too).
             A longer word wins at the same place ('흔들의자' over '의자'), so a specific type
             takes its own words from a general one; no word belongs to two types.
  roles      the parts the type is made of, by the id the designer gives them:
               id     the part id the designer is asked to use (and the fixture uses)
               words  other part ids that mean the same role ('hourHand', 'clock_case')
               root   a missing root role takes the first part without a parent
               primitive  a part the game makes itself (no Tripo credits): 'make' names the shape
                      (server/clock_hands.py: hour, minute, second, pendulum)
               hint   what the designer is told the part is
             Its Korean name in the interaction editor is ROLE_NAMES[id] (the game's
             interaction_panel.gd PART_NAMES holds the same names).
  behaviours interaction presets (server/interactions.py Preset) with 'role' instead of
             'target'; or_whole: when that part is missing, the whole object does it
  single     presets for a one-piece craft (static crafts, or the credit-cap fallback)
  rest       '' | 'sit' | 'lie' (rooms seat or lay the walker on it)
  override   the type's behaviours win over a crafted program (a clock must show real time);
             otherwise a craft that already moves keeps its own motion
  always_moving  built with its moving parts even when the player asked for a still piece (a clock
             always gets its hands; they cost nothing), when the craft fits the credit cap
  accent     the role that glows in styles whose palette glows (sci-fi clocks)
  hint       one more sentence for the designer
  fixture    the offline designer's plan (development and tests): title + parts

The first 22 entries are written out; the later ones use the small builders below (one per
shared part: a side door, a lid, a drawer, a glowing part, a flame, a rotor...). The builders
only fill in the same plain data.
"""

VERSION = 2

# Parent classes: what the types of a family share (docs and diagrams read this).
FAMILIES = {
    'rest': {'ko': '앉고 눕는 가구', 'en': 'Rest piece', 'parts': '앉거나 눕는 판 (한 덩어리도 됨)', 'motions': '앉기·눕기 (+ 쿠션·발받침 같은 작은 움직임)'},
    'rocker': {'ko': '흔들 가구', 'en': 'Rocker', 'parts': '받침 + 흔들리는 부분 (또는 전체)', 'motions': 'rock: 밀면 흔들리다 멈춤'},
    'hinged': {'ko': '여닫이', 'en': 'Hinged', 'parts': '본체 + 문·뚜껑·덮개 (한 모서리가 경첩)', 'motions': 'hinge: E로 열고 닫기'},
    'sliding': {'ko': '미닫이·서랍', 'en': 'Sliding', 'parts': '본체 + 서랍·미닫이 판', 'motions': 'slide: E로 빼고 넣기'},
    'light': {'ko': '빛나는 것', 'en': 'Light source', 'parts': '받침 + 빛나는 부분', 'motions': 'glow·pulse·hue: 켜기, 은은한 깜빡임, 색 바뀜'},
    'flame': {'ko': '불꽃', 'en': 'Flame', 'parts': '받침 + 불꽃', 'motions': 'flicker: 일렁이는 불빛 (+ sway)'},
    'spinner': {'ko': '도는 것', 'en': 'Spinner', 'parts': '본체 + 날개·바퀴·회전판', 'motions': 'rotor·turn·spin·tick: 돌기'},
    'swinging': {'ko': '매달린 흔들이', 'en': 'Pendulum', 'parts': '틀 + 한 점에 매달린 부분', 'motions': 'rock: 추처럼 흔들림'},
    'swaying': {'ko': '살랑이는 것', 'en': 'Swayer', 'parts': '받침 + 부드러운 부분', 'motions': 'sway: 바람에 살랑'},
    'bobbing': {'ko': '통통 튀는 것', 'en': 'Bobber', 'parts': '받침 + 떠 있는 부분', 'motions': 'bounce: 둥실·통통'},
    'appliance': {'ko': '가전 (여러 동작)', 'en': 'Appliance', 'parts': '본체 + 문 + 불빛·회전 부분', 'motions': 'hinge + glow + rotor 함께'},
    'timekeeper': {'ko': '시계', 'en': 'Timekeeper', 'parts': '본체 + 바늘 (게임이 직접 만듦)', 'motions': 'clock·tick: 실제 시각'},
    'still': {'ko': '정물', 'en': 'Still piece', 'parts': '한 덩어리', 'motions': '없음 (모양만 정확히)'},
}
ROOMS = {
    'seating': '앉는 가구', 'beds': '눕는 가구', 'tables': '탁자·책상', 'storage': '수납', 'lighting': '조명·불',
    'kitchen': '주방', 'bathroom': '욕실·세탁', 'electronics': '가전·전자', 'music': '악기·소리', 'decor': '장식',
    'outdoor': '마당·놀이터', 'toys': '장난감·취미', 'doors': '문·창',
}


# ---------------------------------------------------------------- builders (plain data out)

def role(id, hint, *words, root=False, optional=False):
    """One part role. hint is what the designer is told; words are other part ids meaning it."""
    out = {'id': id, 'words': list(words), 'hint': hint}
    if root:
        out['root'] = True
    if optional:
        out['optional'] = True
    return out


def act(role_id, kind, trigger='click', **options):
    """One behaviour preset on a role ('whole' for the object)."""
    return {'role': role_id, 'kind': kind, 'trigger': trigger, **options}


def body(hint, id='body', words=('body', 'base', 'case', 'frame', 'housing'), moves=()):
    """The root part every family hangs its moving parts on (moves: presets on it or on 'whole')."""
    return role(id, hint, *words, root=True), list(moves)


def whole(hint, *words, moves=()):
    """A type that moves (or rests) as one piece."""
    return role('whole', hint, *words, root=True), list(moves)


def part(id, hint, *words, optional=False, moves=()):
    """Any other role, with its own behaviours."""
    return role(id, hint, *words, optional=optional), list(moves)


def side_door(id='door', what='the front door', of='body', angle=-100, trigger='click', words=('door', 'leaf', 'panel')):
    """Hinged: a door turning at its left edge, opening toward the viewer."""
    return (role(id, f'{what}, parent {of}, pivot [-.5,0,0] at its hinge edge (left), closed flush with the front (+Z)', *words),
            [act(id, 'hinge', trigger, axis='y', angle=angle)])


def lid(id='lid', what='the lid', of='body', angle=-100, trigger='click', words=('lid', 'cover', 'top')):
    """Hinged: a lid turning up at its back edge."""
    return role(id, f'{what}, parent {of}, pivot [0,0,-.5] at its back edge', *words), [act(id, 'hinge', trigger, axis='x', angle=angle)]


def drop_door(id='door', what='the front door', of='body', angle=85, trigger='click', words=('door', 'hatch', 'flap')):
    """Hinged: a door turning down at its bottom edge (ovens, mailboxes)."""
    return (role(id, f'{what}, parent {of}, pivot [0,-.5,0] at its bottom edge, closed flush with the front (+Z)', *words),
            [act(id, 'hinge', trigger, axis='x', angle=angle)])


def drawer(id='drawer', what='the drawer', of='body', cm=30, axis='z', trigger='click', level=2, words=('drawer',)):
    """Sliding: a drawer or panel sliding out (z), aside (x) or up (y)."""
    way = {'z': 'closed position flush with the front (+Z)', 'x': 'closed in the opening; it slides sideways (+X)',
           'y': 'resting low; it slides up'}[axis]
    return role(id, f'{what}, parent {of}, {way}', *words), [act(id, 'slide', trigger, axis=axis, angle=cm, level=level)]


def lit(id, what, kind='glow', trigger='click', level=2, or_whole=True, words=(), optional=False, more=()):
    """Light: a part that lights (glow), breathes (pulse) or changes colour (hue); more = (kind, trigger, level)."""
    flag = {'or_whole': True} if or_whole else {}
    moves = [act(id, kind, trigger, level=level, **flag)] + [act(id, k, t, level=lv, **flag) for k, t, lv in more]
    return role(id, what, *words, optional=optional), moves


def flame(id='flame', what='the flame', of='body', level=2, sway=False, trigger='always'):
    """Flame: an uneven flickering glow, and for open fires a dancing sway."""
    moves = [act(id, 'flicker', trigger, level=level, or_whole=True)]
    if sway:
        moves.append(act(id, 'sway', 'always', level=1))
    return role(id, f'{what}, parent {of}, pivot [0,-.5,0] at its base', 'flame', 'fire'), moves


def rotor(id, what, axis, trigger='always', level=2, words=(), direction=1, optional=False):
    """Spinner: blades, wheels and records turning about the part's own axis."""
    extra = {'direction': direction} if direction != 1 else {}
    return role(id, what, *words, optional=optional), [act(id, 'rotor', trigger, axis=axis, level=level, **extra)]


def tap(of='body'):
    """Hinged: a tap lever that turns, and the water under it that shimmers while it runs."""
    return [part('handle', f'the tap lever, parent {of} or the tap; it turns to let the water run', 'handle', 'lever', 'tap',
                 moves=[act('handle', 'hinge', 'click', axis='y', angle=60)]),
            lit('water', f'optional: the stream of water under the tap, parent {of} or the tap; it shimmers while running',
                kind='pulse', level=1, or_whole=False, words=('water', 'stream'), optional=True)]


def turntable(id, what, trigger='always', level=1, words=(), more=()):
    """Spinner: a slow turn about the vertical axis (a display stand); more = extra presets on it."""
    return role(id, what, *words), [act(id, 'turn', trigger, level=level)] + list(more)


def hanging(id, what, axis='z', trigger='always', level=1, words=(), of='frame'):
    """Pendulum: a part hanging from its top that swings."""
    return role(id, f'{what}, parent {of}, pivot [0,.5,0] at its top where it hangs', *words), [act(id, 'rock', trigger, axis=axis, level=level)]


def furniture(id, ko, en, family, room, words, *parts, single=(), rest='', hint='', fixture=None):
    """One archetype from its builders' parts: the same plain data as the written-out entries."""
    entry = {'id': id, 'names': {'ko': ko, 'en': en}, 'family': family, 'room': room, 'words': list(words),
             'roles': [r for r, _ in parts], 'behaviours': [m for _, moves in parts for m in moves],
             'single': list(single), 'rest': rest}
    if hint:
        entry['hint'] = hint
    if fixture:
        entry['fixture'] = {'title': fixture[0], 'parts': fixture[1]}
    return entry


def box(id, size, position, color, parent='', pivot=None, rotation=None, shape='box'):
    """A fixture part (offline plan): position is where its pivot sits in its parent's frame
    (the parent's own pivot point), in metres."""
    out = {'id': id, 'shape': shape, 'size': size, 'position': position, 'color': color}
    if parent:
        out['parent'] = parent
    if pivot:
        out['pivot'] = pivot
    if rotation:
        out['rotation'] = rotation
    return out


def ball(id, size, position, color, parent='', pivot=None, rotation=None):
    return box(id, size, position, color, parent, pivot, rotation, 'ellipsoid')


# Fixture colours.
WOOD, LIGHT_WOOD, DARK_WOOD, PALE_WOOD = '#a87c56', '#c79a6b', '#8f6244', '#d6b48a'
WHITE, IVORY, STEEL, IRON, DARK = '#f5f6fa', '#efe6d2', '#b2bec3', '#636e72', '#2d3436'
RED, BLUE, GREEN, YELLOW, PINK, GOLD, BRASS = '#c0392b', '#4a6c8c', '#5d8a5a', '#f6d365', '#f8c8dc', '#d4a72c', '#b08d57'
WATER, FIRE, GLASS = '#7ec8e3', '#ff8c42', '#cfe8f3'

# Angles: hinge/rock degrees; tick degrees per step; slide centimetres. axis: the part's local axis.
ARCHETYPES = [
    {'id': 'clock', 'names': {'ko': '시계', 'en': 'Clock'}, 'family': 'timekeeper', 'room': 'decor',
     'words': ['시계', '벽시계', '탁상시계', '괘종시계', '뻐꾸기시계', 'clock', 'wall clock', 'grandfather clock', 'cuckoo clock'],
     'roles': [
         {'id': 'body', 'words': ['body', 'case', 'dial', 'face', 'frame', 'housing', 'cabinet'], 'root': True,
          'hint': 'the clock case with a BLANK dial: no hands drawn or modelled on it'},
         {'id': 'hour_hand', 'words': ['hour'], 'primitive': True, 'make': 'hour',
          'hint': 'short thin flat bar, size about [.05,.24,.025], parent body, pivot [0,-.4,0], position at the dial centre just in front of the dial (+Z)'},
         {'id': 'minute_hand', 'words': ['minute'], 'primitive': True, 'make': 'minute',
          'hint': 'longer thin flat bar, size about [.035,.36,.02], parent body, pivot [0,-.4,0], same position as the hour hand but slightly further in front'},
         {'id': 'second_hand', 'words': ['second'], 'primitive': True, 'make': 'second', 'optional': True,
          'hint': 'optional very thin red bar, size about [.02,.4,.02], parent body, pivot [0,-.3,0], in front of the minute hand'},
         {'id': 'pendulum', 'words': ['pendulum', 'bob'], 'primitive': True, 'make': 'pendulum', 'optional': True,
          'hint': 'optional pendulum (tall clocks only): thin bar, parent body, pivot [0,.5,0] at its top, below the dial'},
     ],
     'behaviours': [
         {'role': 'hour_hand', 'kind': 'clock', 'hand': 'hour', 'axis': 'z'},
         {'role': 'minute_hand', 'kind': 'clock', 'hand': 'minute', 'axis': 'z'},
         {'role': 'second_hand', 'kind': 'clock', 'hand': 'second', 'axis': 'z'},
         {'role': 'pendulum', 'kind': 'rock', 'trigger': 'always', 'axis': 'z', 'level': 1},
     ],
     'single': [], 'rest': '', 'override': True, 'always_moving': True, 'accent': 'second_hand',
     'hint': 'The game turns the hands to the player\'s local time, so the program may stay empty.',
     'fixture': {'title': '벽시계', 'parts': [
         {'id': 'body', 'shape': 'box', 'size': [.9, .9, .14], 'position': [0, .62, 0], 'color': '#efe6d2'},
         {'id': 'hour_hand', 'parent': 'body', 'shape': 'box', 'size': [.05, .24, .025], 'position': [0, 0, .085], 'pivot': [0, -.4, 0], 'color': '#2f2a24'},
         {'id': 'minute_hand', 'parent': 'body', 'shape': 'box', 'size': [.035, .36, .02], 'position': [0, 0, .1], 'pivot': [0, -.4, 0], 'color': '#2f2a24'},
         {'id': 'second_hand', 'parent': 'body', 'shape': 'box', 'size': [.02, .4, .02], 'position': [0, 0, .114], 'pivot': [0, -.3, 0], 'color': '#c0392b'}]}},

    {'id': 'door', 'names': {'ko': '문', 'en': 'Door'}, 'family': 'hinged', 'room': 'doors',
     'words': ['문', '대문', '출입문', '현관문', '쪽문', '여닫이문', '문짝', 'door', 'gate', 'doorway'],
     'roles': [
         {'id': 'frame', 'words': ['frame', 'wall', 'post', 'arch', 'jamb', 'body'], 'root': True, 'hint': 'the frame around the opening'},
         {'id': 'door', 'words': ['door', 'gate', 'leaf', 'panel'], 'hint': 'the door leaf, parent frame, pivot [-.5,0,0] at its hinge edge'},
     ],
     'behaviours': [{'role': 'door', 'kind': 'hinge', 'trigger': 'near', 'axis': 'y', 'angle': -100}],
     'single': [], 'rest': '',
     'fixture': {'title': '나무 문', 'parts': [
         {'id': 'frame', 'shape': 'box', 'size': [1.2, 2.2, .1], 'position': [0, 1.1, 0], 'color': '#8f6244'},
         {'id': 'door', 'parent': 'frame', 'shape': 'box', 'size': [.9, 2.0, .06], 'position': [-.45, -.05, .09], 'pivot': [-.5, 0, 0], 'color': '#c79a6b'}]}},

    {'id': 'chest', 'names': {'ko': '상자', 'en': 'Chest'}, 'family': 'hinged', 'room': 'storage',
     'words': ['상자', '보물상자', '궤짝', '함', '보석함', '트렁크', 'chest', 'box', 'crate', 'trunk', 'coffer'],
     'roles': [
         {'id': 'body', 'words': ['body', 'base', 'box', 'case'], 'root': True, 'hint': 'the box'},
         {'id': 'lid', 'words': ['lid', 'cover', 'top'], 'hint': 'the lid, pivot [0,0,-.5] at its back edge'},
     ],
     'behaviours': [{'role': 'lid', 'kind': 'hinge', 'trigger': 'click', 'axis': 'x', 'angle': -100}],
     'single': [], 'rest': ''},

    {'id': 'cabinet', 'names': {'ko': '수납장', 'en': 'Cabinet'}, 'family': 'hinged', 'room': 'storage',
     'words': ['찬장', '장롱', '옷장', '수납장', '캐비닛', '진열장', '사물함', '장식장', 'cabinet', 'wardrobe', 'cupboard', 'closet', 'locker'],
     'roles': [
         {'id': 'body', 'words': ['body', 'case', 'carcass', 'frame'], 'root': True, 'hint': 'the cabinet body'},
         {'id': 'door', 'words': ['door', 'leaf', 'panel'], 'hint': 'the front door, parent body, pivot [-.5,0,0] at its hinge edge'},
     ],
     'behaviours': [{'role': 'door', 'kind': 'hinge', 'trigger': 'click', 'axis': 'y', 'angle': -100}],
     'single': [], 'rest': '',
     'fixture': {'title': '수납장', 'parts': [
         {'id': 'body', 'shape': 'box', 'size': [1.0, 1.7, .5], 'position': [0, .85, 0], 'color': '#a87c56'},
         {'id': 'door', 'parent': 'body', 'shape': 'box', 'size': [.95, 1.6, .04], 'position': [-.475, 0, .27], 'pivot': [-.5, 0, 0], 'color': '#c79a6b'}]}},

    {'id': 'drawer', 'names': {'ko': '서랍장', 'en': 'Drawers'}, 'family': 'sliding', 'room': 'storage',
     'words': ['서랍', '서랍장', '협탁', '화장대', 'drawer', 'drawers', 'dresser', 'nightstand', 'chest of drawers'],
     'roles': [
         {'id': 'body', 'words': ['body', 'case', 'frame', 'cabinet'], 'root': True, 'hint': 'the case'},
         {'id': 'drawer', 'words': ['drawer'], 'hint': 'one drawer, parent body, closed position flush with the front (+Z)'},
     ],
     'behaviours': [{'role': 'drawer', 'kind': 'slide', 'trigger': 'click', 'axis': 'z', 'angle': 30}],
     'single': [], 'rest': '',
     'fixture': {'title': '서랍장', 'parts': [
         {'id': 'body', 'shape': 'box', 'size': [.9, .8, .55], 'position': [0, .4, 0], 'color': '#a87c56'},
         {'id': 'drawer', 'parent': 'body', 'shape': 'box', 'size': [.8, .24, .5], 'position': [0, .17, .05], 'color': '#d6b48a'}]}},

    {'id': 'lamp', 'names': {'ko': '램프', 'en': 'Lamp'}, 'family': 'light', 'room': 'lighting',
     'words': ['램프', '스탠드', '조명', '등', '전등', '무드등', 'lamp', 'light'],
     'roles': [
         {'id': 'base', 'words': ['base', 'stand', 'pole', 'body', 'post'], 'root': True, 'hint': 'the stand'},
         {'id': 'shade', 'words': ['shade', 'bulb', 'light', 'lamp', 'glass', 'globe', 'head'], 'hint': 'the shade or bulb that lights up'},
     ],
     'behaviours': [{'role': 'shade', 'kind': 'glow', 'trigger': 'click', 'level': 2, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'glow', 'trigger': 'click', 'level': 2}], 'rest': ''},

    {'id': 'lantern', 'names': {'ko': '랜턴', 'en': 'Lantern'}, 'family': 'flame', 'room': 'lighting',
     'words': ['랜턴', '등롱', '등불', '초롱', '호롱', '호롱불', '청사초롱', 'lantern'],
     'roles': [
         {'id': 'frame', 'words': ['frame', 'body', 'case', 'base'], 'root': True, 'hint': 'the lantern frame'},
         {'id': 'flame', 'words': ['flame', 'glass', 'light', 'candle', 'fire'], 'hint': 'the glowing glass or flame'},
     ],
     'behaviours': [{'role': 'flame', 'kind': 'flicker', 'trigger': 'click', 'level': 2, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'flicker', 'trigger': 'click', 'level': 2}], 'rest': '',
     'fixture': {'title': '등불', 'parts': [
         {'id': 'whole', 'shape': 'ellipsoid', 'size': [.4, .6, .4], 'position': [0, .3, 0], 'color': '#d9a441'}]}},

    {'id': 'candle', 'names': {'ko': '양초', 'en': 'Candle'}, 'family': 'flame', 'room': 'lighting',
     'words': ['양초', '촛불', '촛대', '캔들', 'candle', 'candles', 'candlestick', 'candelabra'],
     'roles': [
         {'id': 'body', 'words': ['body', 'base', 'holder', 'stick', 'wax'], 'root': True, 'hint': 'the candle and holder'},
         {'id': 'flame', 'words': ['flame', 'fire', 'wick', 'light'], 'hint': 'the flame'},
     ],
     'behaviours': [{'role': 'flame', 'kind': 'flicker', 'trigger': 'always', 'level': 1, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'flicker', 'trigger': 'always', 'level': 1}], 'rest': '',
     'fixture': {'title': '양초', 'parts': [
         {'id': 'whole', 'shape': 'box', 'size': [.14, .4, .14], 'position': [0, .2, 0], 'color': '#f3e6c4'}]}},

    {'id': 'fan', 'names': {'ko': '선풍기', 'en': 'Fan'}, 'family': 'spinner', 'room': 'electronics',
     'words': ['선풍기', '환풍기', '탁상선풍기', 'fan', 'desk fan', 'electric fan', 'ventilator'],
     'roles': [
         {'id': 'body', 'words': ['body', 'base', 'stand', 'pole', 'housing'], 'root': True, 'hint': 'stand and motor'},
         {'id': 'blades', 'words': ['blade', 'rotor', 'propeller', 'fan', 'wing'], 'hint': 'the blade rotor facing front (+Z), parent body'},
     ],
     'behaviours': [{'role': 'blades', 'kind': 'rotor', 'trigger': 'click', 'axis': 'z', 'level': 3}],
     'single': [], 'rest': '',
     'fixture': {'title': '선풍기', 'parts': [
         {'id': 'body', 'shape': 'box', 'size': [.16, 1.0, .16], 'position': [0, .5, 0], 'color': '#dfe6e9'},
         {'id': 'blades', 'parent': 'body', 'shape': 'box', 'size': [.9, .1, .03], 'position': [0, .42, .12], 'color': '#74b9ff'}]}},

    {'id': 'ceiling_fan', 'names': {'ko': '실링팬', 'en': 'Ceiling fan'}, 'family': 'spinner', 'room': 'electronics',
     'words': ['실링팬', '천장선풍기', 'ceiling fan'],
     'roles': [
         {'id': 'body', 'words': ['body', 'base', 'mount', 'motor'], 'root': True, 'hint': 'the mount and motor'},
         {'id': 'blades', 'words': ['blade', 'rotor', 'propeller', 'fan'], 'hint': 'the flat blade rotor, parent body'},
     ],
     'behaviours': [{'role': 'blades', 'kind': 'rotor', 'trigger': 'always', 'axis': 'y', 'level': 2}],
     'single': [], 'rest': ''},

    {'id': 'windmill', 'names': {'ko': '풍차', 'en': 'Windmill'}, 'family': 'spinner', 'room': 'outdoor',
     'words': ['풍차', '바람개비', 'windmill', 'pinwheel', 'wind turbine'],
     'roles': [
         {'id': 'tower', 'words': ['tower', 'body', 'base', 'stick', 'pole', 'house'], 'root': True, 'hint': 'the tower or stick'},
         {'id': 'sails', 'words': ['sail', 'blade', 'rotor', 'wheel', 'wing', 'vane'], 'hint': 'the sail rotor facing front (+Z), parent tower'},
     ],
     'behaviours': [{'role': 'sails', 'kind': 'rotor', 'trigger': 'always', 'axis': 'z', 'level': 1}],
     'single': [], 'rest': '',
     'fixture': {'title': '풍차', 'parts': [
         {'id': 'tower', 'shape': 'box', 'size': [.8, 1.6, .8], 'position': [0, .8, 0], 'color': '#c9a46e'},
         {'id': 'sails', 'parent': 'tower', 'shape': 'box', 'size': [1.6, .18, .04], 'position': [0, .55, .44], 'color': '#f5f0e6'}]}},

    {'id': 'waterwheel', 'names': {'ko': '물레방아', 'en': 'Water wheel'}, 'family': 'spinner', 'room': 'outdoor',
     'words': ['물레방아', '수차', '물레', 'waterwheel', 'water wheel', 'mill wheel', 'spinning wheel'],
     'roles': [
         {'id': 'frame', 'words': ['frame', 'body', 'base', 'stand', 'house'], 'root': True, 'hint': 'the frame'},
         {'id': 'wheel', 'words': ['wheel', 'rotor', 'paddle'], 'hint': 'the wheel turning about the x axis, parent frame'},
     ],
     'behaviours': [{'role': 'wheel', 'kind': 'rotor', 'trigger': 'always', 'axis': 'x', 'level': 1}],
     'single': [], 'rest': '',
     'fixture': {'title': '물레방아', 'parts': [
         {'id': 'frame', 'shape': 'box', 'size': [.2, .9, 1.2], 'position': [-.3, .45, 0], 'color': '#8f6244'},
         {'id': 'wheel', 'parent': 'frame', 'shape': 'box', 'size': [.12, 1.1, .16], 'position': [.25, .1, 0], 'color': '#c79a6b'}]}},

    {'id': 'plant', 'names': {'ko': '화분', 'en': 'Plant'}, 'family': 'swaying', 'room': 'decor',
     'words': ['화분', '식물', '화초', '꽃', '선인장', '분재', '관엽식물', '야자수', 'plant', 'potted plant', 'tree', 'flower', 'flowers', 'bush', 'cactus', 'bonsai', 'palm'],
     'roles': [
         {'id': 'pot', 'words': ['pot', 'base', 'planter', 'vase'], 'root': True, 'hint': 'the pot'},
         {'id': 'leaves', 'words': ['leaf', 'leaves', 'plant', 'foliage', 'crown', 'flower', 'tree'], 'hint': 'the plant, parent pot, pivot [0,-.5,0] at its base'},
     ],
     'behaviours': [{'role': 'leaves', 'kind': 'sway', 'trigger': 'near', 'level': 1, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'sway', 'trigger': 'near', 'level': 1}], 'rest': ''},

    {'id': 'flag', 'names': {'ko': '깃발', 'en': 'Flag'}, 'family': 'swaying', 'room': 'decor',
     'words': ['깃발', '깃대', '현수막', '배너', '휘장', 'flag', 'banner', 'pennant'],
     'roles': [
         {'id': 'pole', 'words': ['pole', 'mast', 'stand', 'base', 'post'], 'root': True, 'hint': 'the pole'},
         {'id': 'cloth', 'words': ['cloth', 'flag', 'banner', 'fabric', 'sheet'], 'hint': 'the cloth, parent pole, pivot [-.5,0,0] at the pole'},
     ],
     'behaviours': [{'role': 'cloth', 'kind': 'rock', 'trigger': 'always', 'axis': 'y', 'level': 2}],
     'single': [{'role': 'whole', 'kind': 'sway', 'trigger': 'always', 'level': 1}], 'rest': '',
     'fixture': {'title': '깃발', 'parts': [
         {'id': 'pole', 'shape': 'box', 'size': [.06, 2.0, .06], 'position': [0, 1.0, 0], 'color': '#8a6a4a'},
         {'id': 'cloth', 'parent': 'pole', 'shape': 'box', 'size': [.75, .48, .03], 'position': [.03, .68, 0], 'pivot': [-.5, 0, 0], 'color': '#c0392b'}]}},

    {'id': 'wind_chime', 'names': {'ko': '풍경', 'en': 'Wind chime'}, 'family': 'swinging', 'room': 'decor',
     'words': ['풍경', '윈드차임', '모빌', 'wind chime', 'windchime', 'mobile'],
     'roles': [
         {'id': 'top', 'words': ['top', 'hanger', 'roof', 'base', 'frame'], 'root': True, 'hint': 'the top it hangs from'},
         {'id': 'chimes', 'words': ['chime', 'bell', 'tube', 'hanging', 'pendant'], 'hint': 'the hanging part, parent top, pivot [0,.5,0] at its top'},
     ],
     'behaviours': [{'role': 'chimes', 'kind': 'rock', 'trigger': 'always', 'axis': 'z', 'level': 1, 'or_whole': True},
                    {'role': 'chimes', 'kind': 'sway', 'trigger': 'near', 'level': 2, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'rock', 'trigger': 'always', 'axis': 'z', 'level': 1}], 'rest': ''},

    {'id': 'rocking_chair', 'names': {'ko': '흔들의자', 'en': 'Rocking chair'}, 'family': 'rocker', 'room': 'seating',
     'words': ['흔들의자', '흔들 의자', 'rocking chair', 'rocker'],
     'roles': [{'id': 'whole', 'words': ['seat', 'chair', 'body'], 'root': True, 'hint': 'the chair'}],
     'behaviours': [{'role': 'whole', 'kind': 'rock', 'trigger': 'click', 'axis': 'x', 'level': 2}],
     'single': [{'role': 'whole', 'kind': 'rock', 'trigger': 'click', 'axis': 'x', 'level': 2}], 'rest': 'sit',
     'fixture': {'title': '흔들의자', 'parts': [
         {'id': 'rockers', 'shape': 'box', 'size': [.6, .06, .8], 'position': [0, .03, 0], 'color': '#8f6244'},
         {'id': 'legs', 'parent': 'rockers', 'shape': 'box', 'size': [.46, .36, .46], 'position': [0, .21, 0], 'color': '#a87c56'},
         {'id': 'seat', 'parent': 'legs', 'shape': 'box', 'size': [.58, .07, .56], 'position': [0, .215, 0], 'color': '#c79a6b'},
         {'id': 'back', 'parent': 'seat', 'shape': 'box', 'size': [.58, .62, .06], 'position': [0, .34, -.25], 'rotation': [-8, 0, 0], 'color': '#c79a6b'}]}},

    {'id': 'music_box', 'names': {'ko': '오르골', 'en': 'Music box'}, 'family': 'spinner', 'room': 'music',
     'words': ['오르골', '뮤직박스', '음악상자', 'music box', 'musicbox'],
     'roles': [
         {'id': 'box', 'words': ['box', 'body', 'base', 'case'], 'root': True, 'hint': 'the box'},
         {'id': 'lid', 'words': ['lid', 'cover', 'top'], 'optional': True, 'hint': 'the lid, parent box, pivot [0,0,-.5] at its back edge'},
         {'id': 'dancer', 'words': ['dancer', 'figure', 'doll', 'ballerina', 'carousel', 'turntable', 'figurine'], 'hint': 'the little figure that turns, parent box'},
     ],
     'behaviours': [{'role': 'lid', 'kind': 'hinge', 'trigger': 'click', 'axis': 'x', 'angle': -100},
                    {'role': 'dancer', 'kind': 'turn', 'trigger': 'click', 'level': 2, 'or_whole': True},
                    {'role': 'whole', 'kind': 'pulse', 'trigger': 'click', 'level': 1}],
     'single': [{'role': 'whole', 'kind': 'turn', 'trigger': 'click', 'level': 1},
                {'role': 'whole', 'kind': 'pulse', 'trigger': 'click', 'level': 1}], 'rest': '',
     'fixture': {'title': '오르골', 'parts': [
         {'id': 'box', 'shape': 'box', 'size': [.6, .32, .42], 'position': [0, .16, 0], 'color': '#8f6244'},
         {'id': 'lid', 'parent': 'box', 'shape': 'box', 'size': [.6, .05, .42], 'position': [0, .185, -.21], 'pivot': [0, 0, -.5], 'color': '#a87c56'},
         {'id': 'dancer', 'parent': 'box', 'shape': 'ellipsoid', 'size': [.1, .24, .1], 'position': [0, .3, .05], 'color': '#f8c8dc'}]}},

    {'id': 'globe', 'names': {'ko': '지구본', 'en': 'Globe'}, 'family': 'spinner', 'room': 'decor',
     'words': ['지구본', '지구의', 'globe'],
     'roles': [
         {'id': 'stand', 'words': ['stand', 'base', 'frame'], 'root': True, 'hint': 'the stand'},
         {'id': 'sphere', 'words': ['sphere', 'globe', 'ball', 'earth', 'world'], 'hint': 'the globe, parent stand'},
     ],
     'behaviours': [{'role': 'sphere', 'kind': 'turn', 'trigger': 'click', 'level': 2}],
     'single': [], 'rest': ''},

    {'id': 'screen', 'names': {'ko': '텔레비전', 'en': 'Screen'}, 'family': 'light', 'room': 'electronics',
     'words': ['텔레비전', '티비', '모니터', '스크린', '컴퓨터', '노트북', 'tv', 'television', 'monitor', 'screen', 'computer', 'laptop'],
     'roles': [
         {'id': 'body', 'words': ['body', 'frame', 'case', 'stand', 'base'], 'root': True, 'hint': 'the set'},
         {'id': 'screen', 'words': ['screen', 'display', 'panel', 'monitor'], 'hint': 'the flat screen on the front (+Z), parent body'},
     ],
     'behaviours': [{'role': 'screen', 'kind': 'glow', 'trigger': 'click', 'level': 2, 'or_whole': True}],
     'single': [{'role': 'whole', 'kind': 'glow', 'trigger': 'click', 'level': 1}], 'rest': '',
     'fixture': {'title': '텔레비전', 'parts': [
         {'id': 'body', 'shape': 'box', 'size': [1.1, .7, .12], 'position': [0, .6, 0], 'color': '#2d3436'},
         {'id': 'screen', 'parent': 'body', 'shape': 'box', 'size': [.95, .55, .02], 'position': [0, 0, .07], 'color': '#4a6c8c'}]}},

    {'id': 'sign', 'names': {'ko': '간판', 'en': 'Sign'}, 'family': 'light', 'room': 'decor',
     'words': ['간판', '표지판', '네온사인', '이정표', 'sign', 'signboard', 'signpost', 'neon sign'],
     'roles': [{'id': 'whole', 'words': ['board', 'sign', 'body'], 'root': True, 'hint': 'the sign'}],
     'behaviours': [{'role': 'whole', 'kind': 'pulse', 'trigger': 'always', 'level': 1}],
     'single': [{'role': 'whole', 'kind': 'pulse', 'trigger': 'always', 'level': 1}], 'rest': ''},

    {'id': 'bed', 'names': {'ko': '침대', 'en': 'Bed'}, 'family': 'rest', 'room': 'beds',
     'words': ['침대', '이층침대', '싱글침대', '더블침대', 'bed', 'bunk bed', 'futon'],
     'roles': [{'id': 'whole', 'words': ['frame', 'bed', 'body'], 'root': True, 'hint': 'the bed'}],
     'behaviours': [], 'single': [], 'rest': 'lie'},

    {'id': 'seat', 'names': {'ko': '의자', 'en': 'Seat'}, 'family': 'rest', 'room': 'seating',
     'words': ['의자', '스툴', '걸상', '좌식의자', 'chair', 'stool', 'seat'],
     'roles': [{'id': 'whole', 'words': ['seat', 'chair', 'body', 'frame'], 'root': True, 'hint': 'the seat'}],
     'behaviours': [], 'single': [], 'rest': 'sit',
     # The offline designer's chair (demo servers and tests: the story chapter's "의자").
     'fixture': {'title': '나무 의자', 'parts': [
         box('seat', [.46, .06, .46], [0, .45, 0], LIGHT_WOOD),
         box('leg_front_left', [.05, .42, .05], [-.19, -.24, .19], WOOD, 'seat'),
         box('leg_front_right', [.05, .42, .05], [.19, -.24, .19], WOOD, 'seat'),
         box('leg_back_left', [.05, .42, .05], [-.19, -.24, -.19], WOOD, 'seat'),
         box('leg_back_right', [.05, .42, .05], [.19, -.24, -.19], WOOD, 'seat'),
         box('back', [.46, .46, .05], [0, .26, -.205], LIGHT_WOOD, 'seat', rotation=[-6, 0, 0])]}},
]

# ---------------------------------------------------------------- the library, by room (built with the builders)

ARCHETYPES += [
    # Seating: rest 'sit'; a sofa's cushion hops, an armchair's footrest swings up as you sit.
    furniture('sofa', '소파', 'Sofa', 'rest', 'seating',
              ['소파', '쇼파', '카우치', '러브시트', 'sofa', 'couch', 'loveseat', 'settee'],
              body('the sofa: frame, seat cushions, back and arms', 'base', ('base', 'frame', 'sofa', 'body', 'seat')),
              part('cushion', 'optional: one throw cushion lying on the seat, parent base; it hops when someone sits', 'cushion', 'pillow',
                   optional=True, moves=[act('cushion', 'bounce', 'click', level=1)]),
              rest='sit',
              fixture=('소파', [
                  box('base', [1.6, .45, .8], [0, .225, 0], BLUE),
                  box('back', [1.6, .5, .2], [0, .475, -.3], BLUE, 'base'),
                  box('arm_left', [.2, .25, .8], [-.7, .35, 0], '#3d5a75', 'base'),
                  box('arm_right', [.2, .25, .8], [.7, .35, 0], '#3d5a75', 'base'),
                  ball('cushion', [.4, .32, .14], [-.35, .38, -.12], YELLOW, 'base', rotation=[-15, 0, 0])])),
    furniture('bench', '벤치', 'Bench', 'rest', 'seating',
              ['벤치', '긴의자', '평상', 'bench', 'park bench', 'garden bench', 'pew'],
              whole('the bench', 'bench', 'seat', 'body', 'frame'),
              rest='sit',
              fixture=('공원 벤치', [
                  box('seat', [1.5, .08, .45], [0, .42, 0], LIGHT_WOOD),
                  box('leg_left', [.08, .38, .4], [-.6, -.23, 0], IRON, 'seat'),
                  box('leg_right', [.08, .38, .4], [.6, -.23, 0], IRON, 'seat'),
                  box('back', [1.5, .4, .06], [0, .27, -.2], LIGHT_WOOD, 'seat', rotation=[-10, 0, 0])])),
    furniture('armchair', '안락의자', 'Armchair', 'rest', 'seating',
              ['안락의자', '소파의자', '1인용소파', '리클라이너', '암체어', 'armchair', 'arm chair', 'recliner', 'easy chair',
               'wingback chair', 'lounge chair'],
              body('the armchair: seat, back and arms', 'base', ('base', 'frame', 'chair', 'body', 'seat')),
              part('footrest', 'optional: a footrest folded down under the front of the seat, parent base, pivot [0,.5,0] at its top '
                   'edge; it swings up when someone sits', 'footrest', 'leg_rest', 'ottoman',
                   optional=True, moves=[act('footrest', 'hinge', 'click', axis='x', angle=-80)]),
              rest='sit',
              fixture=('안락의자', [
                  box('base', [.9, .45, .85], [0, .225, 0], '#8e5b4a'),
                  box('back', [.9, .6, .2], [0, .525, -.33], '#8e5b4a', 'base', rotation=[-6, 0, 0]),
                  box('arm_left', [.15, .25, .85], [-.375, .35, 0], '#7a4d3f', 'base'),
                  box('arm_right', [.15, .25, .85], [.375, .35, 0], '#7a4d3f', 'base'),
                  box('footrest', [.6, .3, .06], [0, .2, .455], '#7a4d3f', 'base', pivot=[0, .5, 0])])),
    furniture('throne', '왕좌', 'Throne', 'rest', 'seating',
              ['왕좌', '옥좌', '용상', 'throne'],
              body('the throne: seat and tall back', 'seat', ('seat', 'base', 'throne', 'body', 'chair')),
              lit('gem', 'the jewel set in the top of the back, parent the back or seat; it shimmers', kind='pulse', trigger='always',
                  level=1, or_whole=False, words=('gem', 'jewel', 'crystal')),
              rest='sit',
              fixture=('왕좌', [
                  box('seat', [.9, .5, .8], [0, .25, 0], '#8e2b2b'),
                  box('back', [.9, 1.3, .15], [0, .9, -.33], GOLD, 'seat'),
                  box('arm_left', [.12, .3, .7], [-.45, .4, 0], GOLD, 'seat'),
                  box('arm_right', [.12, .3, .7], [.45, .4, 0], GOLD, 'seat'),
                  ball('gem', [.18, .18, .08], [0, .45, .1], '#e74c3c', 'back')])),
    furniture('beanbag', '빈백', 'Beanbag', 'rocker', 'seating',
              ['빈백', '빈백소파', '빈백의자', 'beanbag', 'bean bag', 'beanbag chair', 'bean bag chair'],
              whole('the soft beanbag', 'bag', 'beanbag', 'seat', 'body', moves=[act('whole', 'rock', 'click', axis='x', level=1)]),
              single=[act('whole', 'rock', 'click', axis='x', level=1)], rest='sit',
              fixture=('빈백', [ball('whole', [.9, .6, .9], [0, .3, 0], '#e17055')])),
    furniture('swing', '그네', 'Swing', 'rocker', 'seating',
              ['그네', '흔들그네', '벤치그네', '해먹의자', 'swing', 'hammock chair', 'swing set', 'swingset', 'porch swing', 'swing chair', 'swing seat', 'tire swing'],
              body('the frame it hangs from: posts and a top beam', 'frame', ('frame', 'beam', 'post', 'stand', 'base')),
              hanging('ropes', 'the ropes or chains with the seat at their foot', axis='x', trigger='click', level=3,
                      words=('rope', 'chain', 'seat', 'swing')),
              rest='sit',
              fixture=('그네', [
                  box('frame', [1.7, .1, .12], [0, 1.85, 0], DARK_WOOD),
                  box('post_left', [.1, 1.85, .1], [-.8, -.925, 0], DARK_WOOD, 'frame'),
                  box('post_right', [.1, 1.85, .1], [.8, -.925, 0], DARK_WOOD, 'frame'),
                  box('ropes', [.03, 1.25, .03], [-.27, -.05, 0], '#d9c9a3', 'frame', pivot=[0, .5, 0]),
                  box('rope_right', [.03, 1.25, .03], [.54, 0, 0], '#d9c9a3', 'ropes', pivot=[0, .5, 0]),
                  box('plank', [.62, .06, .3], [.27, -1.25, 0], LIGHT_WOOD, 'ropes')])),

    # Beds: rest 'lie' (a cradle is a baby's: it rocks, nobody lies in it).
    furniture('hammock', '해먹', 'Hammock', 'rocker', 'beds',
              ['해먹', '그물침대', 'hammock'],
              body('the stand or the two posts it hangs between', 'frame', ('frame', 'stand', 'post', 'base')),
              hanging('net', 'the hammock bed slung between the posts', axis='x', words=('net', 'hammock', 'bed', 'cloth')),
              rest='lie',
              fixture=('해먹', [
                  box('frame', [2.2, .08, .5], [0, .04, 0], DARK_WOOD),
                  box('post_left', [.08, 1.1, .08], [-1.05, .59, 0], DARK_WOOD, 'frame'),
                  box('post_right', [.08, 1.1, .08], [1.05, .59, 0], DARK_WOOD, 'frame'),
                  ball('net', [1.8, .3, .6], [0, 1.0, 0], '#e8d8b0', 'frame', pivot=[0, .5, 0])])),
    furniture('sunbed', '선베드', 'Sun lounger', 'rest', 'beds',
              ['선베드', '썬베드', '비치체어', 'sunbed', 'sun bed', 'sun lounger', 'lounger', 'deck chair', 'beach chair',
               'chaise longue', 'chaise lounge'],
              body('the lounger frame with its flat part', 'frame', ('frame', 'base', 'bed', 'body')),
              part('backrest', 'the raised back, parent frame, pivot [0,-.5,0] at its bottom edge, leaning back; it reclines further '
                   'when someone lies down', 'backrest', 'back', moves=[act('backrest', 'hinge', 'click', axis='x', angle=-35)]),
              rest='lie',
              fixture=('선베드', [
                  box('frame', [.65, .3, 1.5], [0, .15, 0], WHITE),
                  box('pad', [.6, .05, 1.0], [0, .175, .25], '#74b9ff', 'frame'),
                  box('backrest', [.6, .7, .06], [0, .15, -.25], '#74b9ff', 'frame', pivot=[0, -.5, 0], rotation=[-50, 0, 0])])),
    furniture('cradle', '요람', 'Cradle', 'rocker', 'beds',
              ['요람', '아기침대', '흔들침대', 'cradle', 'crib', 'bassinet'],
              whole('the cradle on its rockers', 'cradle', 'basket', 'crib', 'body', moves=[act('whole', 'rock', 'click', axis='x', level=2)]),
              single=[act('whole', 'rock', 'click', axis='x', level=2)],
              fixture=('요람', [
                  box('rockers', [1.0, .08, .6], [0, .04, 0], DARK_WOOD),
                  box('basket', [1.0, .45, .55], [0, .3, 0], '#f5e6ca', 'rockers'),
                  ball('hood', [.35, .4, .58], [-.4, .3, 0], PINK, 'basket')])),

    # Tables and desks.
    furniture('table', '탁자', 'Table', 'still', 'tables',
              ['탁자', '테이블', '식탁', '밥상', '좌탁', '원탁', '티테이블', '교자상', 'table', 'dining table', 'coffee table',
               'side table', 'tea table', 'picnic table', 'round table'],
              body('the table top with its legs', 'tabletop', ('tabletop', 'top', 'table', 'board', 'body')),
              fixture=('탁자', [
                  box('tabletop', [1.2, .06, .8], [0, .72, 0], LIGHT_WOOD),
                  box('leg_1', [.07, .69, .07], [-.53, -.375, -.33], DARK_WOOD, 'tabletop'),
                  box('leg_2', [.07, .69, .07], [.53, -.375, -.33], DARK_WOOD, 'tabletop'),
                  box('leg_3', [.07, .69, .07], [-.53, -.375, .33], DARK_WOOD, 'tabletop'),
                  box('leg_4', [.07, .69, .07], [.53, -.375, .33], DARK_WOOD, 'tabletop')])),
    furniture('desk', '책상', 'Desk', 'sliding', 'tables',
              ['책상', '학생책상', '사무용책상', '작업대', 'desk', 'writing desk', 'school desk', 'office desk', 'workbench', 'work bench'],
              body('the desk top with its legs and drawer case', 'tabletop', ('tabletop', 'top', 'desk', 'body', 'frame')),
              drawer(what='the drawer under the top', of='tabletop'),
              fixture=('책상', [
                  box('tabletop', [1.2, .05, .6], [0, .74, 0], LIGHT_WOOD),
                  box('pedestal', [.45, .69, .58], [.35, -.37, 0], WOOD, 'tabletop'),
                  box('leg_left', [.06, .69, .55], [-.55, -.37, 0], WOOD, 'tabletop'),
                  box('drawer', [.4, .15, .52], [.35, -.115, .04], PALE_WOOD, 'tabletop')])),
    furniture('kotatsu', '코타츠', 'Kotatsu', 'light', 'tables',
              ['코타츠', '고타쓰', '온열테이블', 'kotatsu', 'heated table'],
              body('the low table with its quilt skirt', 'quilt', ('quilt', 'blanket', 'table', 'body', 'base')),
              lit('heater', 'the warm glow along the bottom of the quilt, parent quilt; it lights when switched on', level=1,
                  words=('heater', 'glow', 'warm')),
              single=[act('whole', 'glow', 'click', level=1)],
              fixture=('코타츠', [
                  box('quilt', [1.1, .3, 1.1], [0, .15, 0], '#e17055'),
                  box('tabletop', [1.0, .04, 1.0], [0, .17, 0], LIGHT_WOOD, 'quilt'),
                  box('heater', [1.12, .06, 1.12], [0, -.12, 0], '#ff7f50', 'quilt')])),

    # Storage: hinged (doors, lids) and sliding (drawers).
    furniture('bookshelf', '책장', 'Bookshelf', 'hinged', 'storage',
              ['책장', '책꽂이', '책선반', '선반', 'bookshelf', 'bookcase', 'book shelf', 'shelf', 'shelves', 'bookshelves'],
              body('the shelf case with rows of books', 'body', ('body', 'case', 'shelf', 'frame', 'cabinet')),
              part('book', 'optional: one book standing at the end of a row like a secret lever, parent body, pivot [0,-.5,0] at its '
                   'bottom edge; it tips out when pulled', 'book', 'lever', optional=True,
                   moves=[act('book', 'hinge', 'click', axis='x', angle=25)]),
              fixture=('책장', [
                  box('body', [1.0, 1.8, .35], [0, .9, 0], DARK_WOOD),
                  box('books_top', [.8, .28, .26], [-.04, .55, .07], BLUE, 'body'),
                  box('books_mid', [.88, .28, .26], [0, .05, .07], GREEN, 'body'),
                  box('books_low', [.88, .28, .26], [0, -.45, .07], RED, 'body'),
                  box('book', [.07, .3, .26], [.41, .41, .07], GOLD, 'body', pivot=[0, -.5, 0])])),
    furniture('safe', '금고', 'Safe', 'hinged', 'storage',
              ['금고', '대형금고', 'safe', 'vault', 'strongbox', 'safe box'],
              body('the heavy steel box', 'body'),
              side_door(what='the thick front door'),
              part('dial', 'the combination dial on the door, parent door; it clicks round', 'dial', 'knob', 'lock',
                   moves=[act('dial', 'tick', 'click', axis='z', angle=30)]),
              fixture=('금고', [
                  box('body', [.7, .8, .65], [0, .4, 0], '#4b5563'),
                  box('door', [.62, .72, .05], [-.31, 0, .35], IRON, 'body', pivot=[-.5, 0, 0]),
                  box('dial', [.14, .14, .04], [.41, .05, .045], GOLD, 'door'),
                  box('handle', [.04, .2, .05], [.53, -.12, .05], STEEL, 'door')])),
    furniture('trash_can', '쓰레기통', 'Trash can', 'hinged', 'storage',
              ['쓰레기통', '휴지통', '쓰레기함', '분리수거함', 'trash can', 'garbage can', 'trash bin', 'wastebasket', 'waste bin',
               'dustbin', 'bin', 'rubbish bin', 'recycling bin'],
              body('the bin', 'body', ('body', 'bin', 'can', 'base', 'case')),
              lid(what='the lid; it opens by itself when someone comes near', angle=-80, trigger='near'),
              fixture=('쓰레기통', [
                  box('body', [.45, .6, .45], [0, .3, 0], STEEL),
                  box('lid', [.47, .05, .47], [0, .325, -.235], IRON, 'body', pivot=[0, 0, -.5]),
                  box('pedal', [.2, .03, .08], [0, -.28, .26], DARK, 'body')])),
    furniture('coat_rack', '옷걸이', 'Coat rack', 'swaying', 'storage',
              ['옷걸이', '행거', '모자걸이', '스탠드옷걸이', 'coat rack', 'coat stand', 'hat stand', 'hat rack', 'clothes rack', 'coat tree'],
              body('the stand with its hooks', 'stand', ('stand', 'pole', 'rack', 'base', 'body')),
              part('coat', 'optional: a coat or hat hanging on a hook, parent stand, pivot [0,.5,0] at the hook; it swings a little '
                   'when brushed', 'coat', 'hat', 'jacket', optional=True,
                   moves=[act('coat', 'sway', 'near', level=1, or_whole=True)]),
              single=[act('whole', 'sway', 'near', level=1)],
              fixture=('옷걸이', [
                  box('stand', [.06, 1.7, .06], [0, .85, 0], DARK_WOOD),
                  box('foot', [.5, .05, .5], [0, -.825, 0], DARK_WOOD, 'stand'),
                  box('hooks', [.45, .05, .05], [0, .75, 0], DARK_WOOD, 'stand'),
                  box('coat', [.4, .8, .12], [.15, .75, .07], RED, 'stand', pivot=[0, .5, 0])])),

    # Lighting: glowing parts and flames.
    furniture('chandelier', '샹들리에', 'Chandelier', 'light', 'lighting',
              ['샹들리에', '펜던트조명', '천장조명', '천장등', 'chandelier', 'pendant light', 'pendant lamp', 'ceiling light', 'ceiling lamp'],
              body('the ceiling mount and chain', 'mount', ('mount', 'chain', 'canopy', 'base', 'body')),
              part('lights', 'the arms with candles or bulbs, parent mount, pivot [0,.5,0] at the chain; they light up and sway gently',
                   'lights', 'arms', 'bulb', 'candle',
                   moves=[act('lights', 'glow', 'click', level=2, or_whole=True), act('lights', 'rock', 'always', axis='z', level=1)]),
              single=[act('whole', 'glow', 'click', level=2)],
              fixture=('샹들리에', [
                  box('mount', [.3, .06, .3], [0, 1.6, 0], BRASS),
                  box('chain', [.03, .5, .03], [0, -.28, 0], BRASS, 'mount'),
                  ball('lights', [.9, .25, .9], [0, -.53, 0], YELLOW, 'mount', pivot=[0, .5, 0]),
                  box('candles', [.7, .12, .7], [0, .06, 0], IVORY, 'lights')])),
    furniture('street_lamp', '가로등', 'Street lamp', 'light', 'lighting',
              ['가로등', '외등', '정원등', 'streetlight', 'street light', 'street lamp', 'lamppost', 'lamp post', 'garden lamp',
               'garden light'],
              body('the post', 'post', ('post', 'pole', 'stand', 'base')),
              lit('lamp_head', 'the lamp at the top, parent post; it stays lit', trigger='always', level=2,
                  words=('head', 'lamp', 'lantern', 'light', 'bulb', 'globe')),
              single=[act('whole', 'glow', 'click', level=1)],
              fixture=('가로등', [
                  box('post', [.12, 2.4, .12], [0, 1.2, 0], DARK),
                  box('foot', [.35, .25, .35], [0, -1.075, 0], DARK, 'post'),
                  ball('lamp_head', [.36, .42, .36], [0, 1.36, 0], YELLOW, 'post'),
                  box('cap', [.45, .08, .45], [0, .25, 0], DARK, 'lamp_head')])),
    furniture('fireplace', '벽난로', 'Fireplace', 'flame', 'lighting',
              ['벽난로', '페치카', 'fireplace', 'hearth'],
              body('the stone or brick fireplace with a dark opening', 'body', ('body', 'mantel', 'case', 'frame')),
              flame('fire', 'the fire and logs in the opening', level=2, sway=True),
              fixture=('벽난로', [
                  box('body', [1.4, 1.1, .5], [0, .55, 0], '#9c6b4f'),
                  box('mantel', [1.6, .1, .6], [0, .6, .03], DARK_WOOD, 'body'),
                  box('opening', [.8, .6, .06], [0, -.15, .23], '#2d1f17', 'body'),
                  ball('fire', [.5, .4, .2], [0, -.45, .2], FIRE, 'body', pivot=[0, -.5, 0])])),
    furniture('campfire', '모닥불', 'Campfire', 'flame', 'lighting',
              ['모닥불', '캠프파이어', '화톳불', '장작불', 'campfire', 'camp fire', 'bonfire', 'fire pit', 'firepit'],
              body('the logs and the ring of stones', 'logs', ('logs', 'wood', 'stones', 'base', 'pit')),
              flame('fire', 'the flames on the logs', of='logs', level=3, sway=True),
              single=[act('whole', 'flicker', 'always', level=2)],
              fixture=('모닥불', [
                  box('logs', [.9, .14, .16], [0, .1, 0], '#6d4c41', rotation=[0, 45, 0]),
                  box('log_cross', [.9, .14, .16], [0, 0, 0], '#5d4037', 'logs', rotation=[0, 90, 0]),
                  ball('stones', [1.1, .12, 1.1], [0, -.04, 0], '#8d8d8d', 'logs'),
                  ball('fire', [.45, .7, .45], [0, .05, 0], FIRE, 'logs', pivot=[0, -.5, 0])])),
    furniture('torch', '횃불', 'Torch', 'flame', 'lighting',
              ['횃불', 'torch', 'tiki torch', 'wall torch', 'sconce'],
              body('the handle or pole', 'stick', ('stick', 'pole', 'handle', 'post', 'base', 'body')),
              flame(what='the flame at the top', of='stick', level=2, sway=True),
              single=[act('whole', 'flicker', 'always', level=1)],
              fixture=('횃불', [
                  box('stick', [.08, 1.2, .08], [0, .6, 0], '#6d4c41'),
                  box('cup', [.18, .15, .18], [0, .6, 0], IRON, 'stick'),
                  ball('flame', [.2, .4, .2], [0, .67, 0], '#ffa94d', 'stick', pivot=[0, -.5, 0])])),
    furniture('lava_lamp', '라바램프', 'Lava lamp', 'light', 'lighting',
              ['라바램프', '용암램프', 'lava lamp'],
              body('the base', 'base', ('base', 'stand', 'body')),
              lit('glass', 'the tall glass vessel, parent base; it glows and slowly changes colour', kind='pulse', trigger='always',
                  level=1, words=('glass', 'bottle', 'vessel'), more=[('hue', 'always', 1)]),
              part('blob', 'a blob of wax in the glass, parent glass; it floats up and down', 'blob', 'wax', 'bubble',
                   moves=[act('blob', 'bounce', 'always', level=1)]),
              single=[act('whole', 'pulse', 'always', level=1), act('whole', 'hue', 'always', level=1)],
              fixture=('라바램프', [
                  box('base', [.22, .2, .22], [0, .1, 0], DARK),
                  ball('glass', [.16, .5, .16], [0, .35, 0], '#fd79a8', 'base'),
                  ball('blob', [.2, .13, .2], [0, -.05, 0], '#fdcb6e', 'glass'),
                  box('cap', [.12, .08, .12], [0, .27, 0], DARK, 'glass')])),
    furniture('string_lights', '꼬마전구', 'String lights', 'light', 'lighting',
              ['꼬마전구', '알전구', '줄조명', '전구줄', 'fairy lights', 'string lights', 'christmas lights', 'light string'],
              body('the wire and the posts it is strung between', 'string', ('string', 'wire', 'cord', 'post', 'base')),
              lit('bulbs', 'the little bulbs along the wire, parent string; they twinkle in changing colours', kind='pulse',
                  trigger='always', level=2, words=('bulb', 'lights'), more=[('hue', 'always', 1)]),
              single=[act('whole', 'pulse', 'always', level=1), act('whole', 'hue', 'always', level=1)],
              fixture=('꼬마전구', [
                  box('string', [1.6, .03, .03], [0, 1.0, 0], DARK),
                  box('post_left', [.05, 1.0, .05], [-.8, -.5, 0], DARK_WOOD, 'string'),
                  box('post_right', [.05, 1.0, .05], [.8, -.5, 0], DARK_WOOD, 'string'),
                  box('bulbs', [1.5, .1, .06], [0, -.07, 0], YELLOW, 'string')])),
    furniture('lighthouse', '등대', 'Lighthouse', 'light', 'lighting',
              ['등대', 'lighthouse', 'beacon'],
              body('the tower', 'tower', ('tower', 'body', 'base')),
              part('light', 'the lamp room at the top, parent tower; it shines and its beam turns', 'light', 'lamp', 'lantern', 'beam',
                   moves=[act('light', 'glow', 'always', level=2, or_whole=True), act('light', 'turn', 'always', level=2)]),
              single=[act('whole', 'pulse', 'always', level=1)],
              fixture=('등대', [
                  box('tower', [.6, 2.0, .6], [0, 1.0, 0], WHITE),
                  box('stripe', [.62, .3, .62], [0, .2, 0], RED, 'tower'),
                  box('gallery', [.8, .08, .8], [0, 1.04, 0], DARK, 'tower'),
                  box('light', [.4, .35, .4], [0, 1.255, 0], YELLOW, 'tower'),
                  box('ray', [1.4, .08, .08], [0, 0, 0], '#fff3b0', 'light'),
                  ball('roof', [.5, .25, .5], [0, 1.555, 0], RED, 'tower')])),

    # Kitchen.
    furniture('fridge', '냉장고', 'Fridge', 'appliance', 'kitchen',
              ['냉장고', '김치냉장고', '냉동고', 'refrigerator', 'fridge', 'icebox', 'freezer'],
              body('the tall fridge body', 'body'),
              side_door(what='the fridge door, as tall as the body'),
              lit('light', 'optional: the lit inside behind the door, parent body; it lights while the door is open', level=1,
                  or_whole=False, words=('light', 'inside', 'interior'), optional=True),
              fixture=('냉장고', [
                  box('body', [.8, 1.8, .7], [0, .9, 0], '#ecf0f1'),
                  box('light', [.7, 1.6, .02], [0, 0, .34], '#fff9e0', 'body'),
                  box('door', [.8, 1.78, .06], [-.4, 0, .38], '#dfe6e9', 'body', pivot=[-.5, 0, 0]),
                  box('handle', [.04, .5, .05], [.72, .2, .055], STEEL, 'door')])),
    furniture('stove', '가스레인지', 'Stove', 'flame', 'kitchen',
              ['가스레인지', '가스렌지', '인덕션', '전기레인지', '레인지', '곤로', 'stove', 'cooktop', 'gas stove', 'kitchen stove',
               'gas range', 'hob', 'cooker'],
              body('the stove with its cooktop', 'body'),
              part('burner', 'the burner on top, parent body; its flame flickers when lit', 'burner', 'flame', 'fire', 'ring',
                   moves=[act('burner', 'flicker', 'click', level=2)]),
              part('knob', 'optional: the knob on the front, parent body; it turns when lit', 'knob', 'dial', 'switch', optional=True,
                   moves=[act('knob', 'hinge', 'click', axis='z', angle=-90)]),
              fixture=('가스레인지', [
                  box('body', [.8, .85, .6], [0, .425, 0], '#dfe6e9'),
                  box('cooktop', [.8, .03, .6], [0, .44, 0], DARK, 'body'),
                  ball('burner', [.28, .05, .28], [-.18, .47, .05], '#ff6b35', 'body'),
                  ball('back_burner', [.22, .04, .22], [.2, .46, -.12], IRON, 'body'),
                  box('knob', [.08, .08, .04], [-.18, .3, .32], DARK, 'body')])),
    furniture('oven', '오븐', 'Oven', 'appliance', 'kitchen',
              ['오븐', '화덕', '피자화덕', '전기오븐', 'oven', 'pizza oven', 'bread oven', 'baking oven'],
              body('the oven body', 'body'),
              drop_door(what='the oven door'),
              lit('light', 'optional: the glowing inside behind the door, parent body', level=2, or_whole=False,
                  words=('light', 'inside'), optional=True),
              fixture=('오븐', [
                  box('body', [.8, .8, .65], [0, .4, 0], DARK),
                  box('light', [.6, .45, .02], [0, -.05, .325], '#ff9f43', 'body'),
                  box('door', [.7, .5, .05], [0, -.3, .36], '#57606f', 'body', pivot=[0, -.5, 0]),
                  box('handle', [.5, .04, .05], [0, .42, .04], STEEL, 'door'),
                  box('panel', [.7, .12, .02], [0, .3, .33], '#1e272e', 'body')])),
    furniture('sink', '싱크대', 'Sink', 'hinged', 'kitchen',
              ['싱크대', '개수대', '주방싱크', 'sink', 'kitchen sink'],
              body('the counter with its basin and tap', 'body'),
              *tap(),
              fixture=('싱크대', [
                  box('body', [1.0, .85, .6], [0, .425, 0], '#dfe6e9'),
                  box('basin', [.6, .04, .4], [0, .43, .02], IRON, 'body'),
                  box('faucet', [.05, .3, .05], [0, .575, -.2], STEEL, 'body'),
                  box('spout', [.05, .05, .2], [0, .13, .1], STEEL, 'faucet'),
                  box('handle', [.15, .04, .04], [0, .05, .04], DARK, 'faucet'),
                  box('water', [.04, .25, .04], [0, -.015, .18], WATER, 'faucet')])),
    furniture('kettle', '주전자', 'Kettle', 'rocker', 'kitchen',
              ['주전자', '찻주전자', '티포트', '다관', 'kettle', 'teapot', 'tea pot', 'tea kettle'],
              body('the kettle with its spout and handle', 'body'),
              part('lid', 'the lid on top, parent body; it rattles when the water boils', 'lid', 'cover', 'cap',
                   moves=[act('lid', 'rock', 'click', axis='z', level=2)]),
              single=[act('whole', 'rock', 'click', axis='z', level=1)],
              fixture=('주전자', [
                  ball('body', [.4, .32, .32], [0, .16, 0], STEEL),
                  ball('lid', [.18, .08, .18], [0, .17, 0], IRON, 'body'),
                  box('spout', [.2, .06, .06], [.24, .05, 0], STEEL, 'body', rotation=[0, 0, 30]),
                  box('handle', [.04, .04, .22], [-.2, .08, 0], DARK, 'body')])),
    furniture('coffee_machine', '커피머신', 'Coffee machine', 'appliance', 'kitchen',
              ['커피머신', '커피메이커', '커피기계', '에스프레소머신', 'coffee machine', 'coffee maker', 'coffeemaker', 'espresso machine',
               'espresso maker'],
              body('the machine with its spout', 'body', moves=[act('whole', 'rock', 'click', axis='z', level=1)]),
              lit('light', 'the power light on the front, parent body', level=2, or_whole=False, words=('light', 'lamp', 'led')),
              single=[act('whole', 'rock', 'click', axis='z', level=1), act('whole', 'glow', 'click', level=1)],
              fixture=('커피머신', [
                  box('body', [.35, .45, .38], [0, .225, 0], DARK),
                  box('spout', [.08, .06, .1], [0, .08, .22], IRON, 'body'),
                  box('cup', [.1, .1, .1], [0, -.17, .22], WHITE, 'body'),
                  box('light', [.06, .06, .02], [.1, .15, .2], '#ff7675', 'body')])),
    furniture('toaster', '토스터', 'Toaster', 'sliding', 'kitchen',
              ['토스터', '토스터기', '토스트기', 'toaster'],
              body('the toaster with two slots on top', 'body'),
              drawer('toast', what='the slices of bread in the slots', cm=12, axis='y', level=3, words=('toast', 'bread', 'slice')),
              fixture=('토스터', [
                  box('body', [.4, .25, .25], [0, .125, 0], '#d63031'),
                  box('toast', [.25, .18, .12], [0, .05, 0], '#e0b07a', 'body'),
                  box('lever', [.04, .04, .06], [.15, 0, .15], DARK, 'body')])),
    furniture('microwave', '전자레인지', 'Microwave', 'appliance', 'kitchen',
              ['전자레인지', '전자렌지', 'microwave', 'microwave oven'],
              body('the microwave with its control panel on the right', 'body'),
              side_door(what='the door with its window, left of the panel'),
              lit('light', 'optional: the lit inside behind the door, parent body', level=1, or_whole=False,
                  words=('light', 'inside'), optional=True),
              fixture=('전자레인지', [
                  box('body', [.6, .36, .42], [0, .18, 0], '#dfe6e9'),
                  box('light', [.4, .28, .02], [-.07, 0, .21], '#fff3b0', 'body'),
                  box('door', [.42, .32, .03], [-.28, 0, .235], DARK, 'body', pivot=[-.5, 0, 0]),
                  box('panel', [.12, .3, .02], [.23, 0, .215], IRON, 'body')])),
    furniture('blender', '믹서기', 'Blender', 'spinner', 'kitchen',
              ['믹서기', '믹서', '블렌더', '주서기', '착즙기', 'blender', 'mixer', 'juicer', 'food processor'],
              body('the motor base', 'base', ('base', 'motor', 'body', 'stand')),
              part('jar', 'the jar on the base, parent base; it shakes while blending', 'jar', 'jug', 'cup',
                   moves=[act('jar', 'rock', 'click', axis='z', level=1)]),
              rotor('blade', 'the blades at the bottom of the jar, parent jar, turning flat (about Y)', 'y', trigger='click', level=3,
                    words=('blade', 'rotor', 'knife')),
              single=[act('whole', 'rock', 'click', axis='z', level=1)],
              fixture=('믹서기', [
                  box('base', [.22, .18, .22], [0, .09, 0], DARK),
                  box('jar', [.18, .3, .18], [0, .24, 0], GLASS, 'base'),
                  box('blade', [.24, .02, .05], [0, -.1, 0], STEEL, 'jar'),
                  box('cap', [.19, .04, .19], [0, .17, 0], DARK, 'jar')])),
    furniture('rice_cooker', '밥솥', 'Rice cooker', 'hinged', 'kitchen',
              ['밥솥', '전기밥솥', '압력밥솥', 'rice cooker', 'pressure cooker'],
              body('the cooker body', 'body'),
              lid(what='the domed lid', angle=-80),
              lit('light', 'optional: the little cooking light on the front, parent body', level=1, or_whole=False,
                  words=('light', 'led'), optional=True),
              fixture=('전기밥솥', [
                  ball('body', [.4, .3, .4], [0, .15, 0], '#ecf0f1'),
                  ball('lid', [.38, .12, .38], [0, .12, -.19], '#dfe6e9', 'body', pivot=[0, 0, -.5]),
                  box('light', [.06, .04, .02], [0, 0, .2], '#e17055', 'body')])),
    furniture('cauldron', '가마솥', 'Cauldron', 'light', 'kitchen',
              ['가마솥', '마녀솥', '물약솥', '솥', 'cauldron', 'witch pot'],
              body('the round iron pot', 'cauldron', ('cauldron', 'pot', 'kettle', 'body', 'base')),
              lit('brew', 'the bubbling brew filling the top, parent cauldron; it glows and shifts colour', kind='pulse',
                  trigger='always', level=2, words=('brew', 'potion', 'soup', 'liquid'), more=[('hue', 'always', 1)]),
              single=[act('whole', 'pulse', 'always', level=1)],
              fixture=('가마솥', [
                  ball('cauldron', [.8, .6, .8], [0, .3, 0], DARK),
                  ball('brew', [.62, .1, .62], [0, .27, 0], '#55efc4', 'cauldron')])),

    # Bathroom and laundry.
    furniture('bathtub', '욕조', 'Bathtub', 'rest', 'bathroom',
              ['욕조', '반신욕조', '목욕통', '자쿠지', 'bathtub', 'bath tub', 'tub', 'bath', 'hot tub', 'jacuzzi'],
              body('the tub', 'tub', ('tub', 'bath', 'body', 'base')),
              lit('water', 'the water surface, parent tub; it shimmers', kind='pulse', trigger='always', level=1, or_whole=False,
                  words=('water', 'bubbles', 'foam')),
              rest='lie',
              fixture=('욕조', [
                  box('tub', [1.6, .55, .75], [0, .275, 0], WHITE),
                  box('water', [1.4, .04, .6], [0, .26, 0], WATER, 'tub'),
                  box('faucet', [.06, .2, .06], [-.72, .36, 0], STEEL, 'tub')])),
    furniture('toilet', '변기', 'Toilet', 'hinged', 'bathroom',
              ['변기', '양변기', '좌변기', 'toilet', 'toilet seat', 'loo', 'commode'],
              body('the bowl with its tank at the back', 'body'),
              lid(what='the seat lid; it lifts by itself when someone comes near', trigger='near'),
              rest='sit',
              fixture=('변기', [
                  box('body', [.4, .42, .6], [0, .21, .05], WHITE),
                  box('tank', [.45, .45, .2], [0, .2, -.35], WHITE, 'body'),
                  box('lid', [.4, .04, .5], [0, .23, -.24], '#dfe6e9', 'body', pivot=[0, 0, -.5])])),
    furniture('shower', '샤워기', 'Shower', 'light', 'bathroom',
              ['샤워기', '샤워부스', '샤워실', '샤워', 'shower', 'shower head', 'shower booth', 'shower stall'],
              body('the shower tray and pipe', 'body', ('body', 'tray', 'base', 'frame', 'pipe')),
              lit('water', 'the falling water under the shower head, parent the head or body; it shimmers while running',
                  kind='pulse', level=2, or_whole=False, words=('water', 'stream', 'spray')),
              fixture=('샤워기', [
                  box('body', [.9, .08, .9], [0, .04, 0], '#dfe6e9'),
                  box('pipe', [.05, 2.0, .05], [0, 1.04, -.4], STEEL, 'body'),
                  ball('shower_head', [.25, .06, .25], [0, .95, .15], IRON, 'pipe'),
                  box('water', [.18, 1.6, .18], [0, -.83, 0], '#a8e0ff', 'shower_head')])),
    furniture('washbasin', '세면대', 'Washbasin', 'hinged', 'bathroom',
              ['세면대', '세면기', 'washbasin', 'wash basin', 'basin', 'bathroom sink'],
              body('the pedestal and bowl', 'stand', ('stand', 'pedestal', 'base', 'body')),
              *tap('stand'),
              fixture=('세면대', [
                  box('stand', [.25, .75, .25], [0, .375, 0], WHITE),
                  ball('bowl', [.6, .2, .45], [0, .45, .05], WHITE, 'stand'),
                  box('faucet', [.05, .2, .05], [0, .15, -.15], STEEL, 'bowl'),
                  box('handle', [.14, .04, .04], [0, .08, 0], DARK, 'faucet'),
                  box('water', [.04, .14, .04], [0, -.02, .09], WATER, 'faucet')])),
    furniture('washing_machine', '세탁기', 'Washing machine', 'appliance', 'bathroom',
              ['세탁기', '드럼세탁기', '통돌이', '건조기', '빨래건조기', 'washing machine', 'washer', 'dryer', 'tumble dryer', 'laundry machine'],
              body('the machine body', 'body'),
              rotor('drum', 'the drum seen through the round door on the front, parent body, turning about Z', 'z', trigger='click',
                    level=2, words=('drum', 'tub', 'window')),
              lit('light', 'optional: the power light, parent body', level=1, or_whole=False, words=('light', 'led'), optional=True),
              fixture=('세탁기', [
                  box('body', [.6, .85, .6], [0, .425, 0], WHITE),
                  ball('porthole', [.42, .42, .04], [0, -.02, .3], DARK, 'body'),
                  box('drum', [.3, .3, .03], [0, -.02, .325], '#74b9ff', 'body'),
                  box('light', [.05, .05, .02], [.22, .35, .305], '#55efc4', 'body')])),

    # Electronics and appliances.
    furniture('radio', '라디오', 'Radio', 'light', 'electronics',
              ['라디오', '카세트', '카세트플레이어', '붐박스', '오디오', 'radio', 'boombox', 'cassette player', 'tape player', 'stereo',
               'transistor radio'],
              body('the radio case', 'body'),
              lit('speaker', 'the round speaker grille on the front, parent body; it beats while playing', kind='pulse', level=2,
                  words=('speaker', 'grille', 'grill')),
              part('antenna', 'optional: the antenna, parent body, pivot [0,-.5,0] at its foot; it wobbles when switched', 'antenna',
                   'aerial', optional=True, moves=[act('antenna', 'sway', 'click', level=2)]),
              single=[act('whole', 'sway', 'click', level=1)],
              fixture=('라디오', [
                  box('body', [.6, .35, .2], [0, .175, 0], RED),
                  ball('speaker', [.22, .22, .04], [-.15, -.02, .1], DARK, 'body'),
                  box('tuner', [.18, .08, .03], [.15, .05, .1], YELLOW, 'body'),
                  box('antenna', [.02, .45, .02], [.22, .175, 0], STEEL, 'body', pivot=[0, -.5, 0], rotation=[0, 0, -20]),
                  box('handle', [.4, .04, .04], [0, .2, 0], DARK, 'body')])),
    furniture('record_player', '전축', 'Record player', 'spinner', 'electronics',
              ['전축', '턴테이블', '레코드플레이어', '축음기', '유성기', '엘피플레이어', 'record player', 'turntable', 'gramophone',
               'phonograph', 'vinyl player'],
              body('the player case', 'body'),
              rotor('record', 'the vinyl record on top, parent body, turning flat (about Y)', 'y', trigger='click', level=2,
                    words=('record', 'disc', 'vinyl', 'platter'), direction=-1),
              part('tonearm', 'optional: the tone arm, parent body, pivot [0,0,-.5] at its back end; it swings onto the record',
                   'tonearm', 'arm', 'needle', optional=True, moves=[act('tonearm', 'hinge', 'click', axis='y', angle=-25)]),
              fixture=('전축', [
                  box('body', [.5, .14, .4], [0, .07, 0], DARK_WOOD),
                  ball('record', [.34, .02, .34], [-.05, .08, 0], '#1e1e1e', 'body'),
                  box('label', [.1, .026, .03], [0, 0, 0], RED, 'record'),
                  box('tonearm', [.04, .03, .25], [.19, .09, -.15], STEEL, 'body', pivot=[0, 0, -.5])])),
    furniture('arcade', '오락기', 'Arcade machine', 'light', 'electronics',
              ['오락기', '아케이드', '게임기', '핀볼', 'arcade', 'arcade machine', 'arcade cabinet', 'game machine', 'pinball',
               'pinball machine'],
              body('the tall cabinet', 'body', ('body', 'cabinet', 'case', 'base')),
              lit('screen', 'the screen on the front (+Z), parent body; it flickers with colour', kind='pulse', trigger='always',
                  level=2, words=('screen', 'display', 'monitor'), more=[('hue', 'always', 1)]),
              lit('buttons', 'optional: the control panel buttons, parent body; they light up when played', level=2, or_whole=False,
                  words=('buttons', 'controls', 'joystick'), optional=True),
              single=[act('whole', 'pulse', 'always', level=1)],
              fixture=('오락기', [
                  box('body', [.7, 1.7, .7], [0, .85, 0], '#6c5ce7'),
                  box('screen', [.55, .45, .03], [0, .35, .36], '#00cec9', 'body', rotation=[-10, 0, 0]),
                  box('panel', [.66, .08, .3], [0, -.05, .45], DARK, 'body'),
                  box('buttons', [.3, .04, .1], [0, .06, 0], '#fdcb6e', 'panel'),
                  box('marquee', [.7, .2, .05], [0, .75, .35], '#fd79a8', 'body')])),
    furniture('speaker', '스피커', 'Speaker', 'light', 'electronics',
              ['스피커', '앰프', '우퍼', '사운드바', 'speaker', 'loudspeaker', 'amplifier', 'amp', 'subwoofer', 'soundbar'],
              body('the speaker box', 'body', ('body', 'box', 'cabinet', 'case')),
              lit('cone', 'the big speaker cone on the front, parent body; it beats while playing', kind='pulse', level=2,
                  words=('cone', 'woofer', 'driver')),
              single=[act('whole', 'pulse', 'click', level=1)],
              fixture=('스피커', [
                  box('body', [.4, .7, .35], [0, .35, 0], DARK),
                  ball('cone', [.28, .28, .05], [0, -.12, .18], IRON, 'body'),
                  ball('tweeter', [.1, .1, .04], [0, .2, .18], STEEL, 'body')])),
    furniture('jukebox', '주크박스', 'Jukebox', 'light', 'electronics',
              ['주크박스', 'jukebox'],
              body('the jukebox case', 'body'),
              lit('lights', 'the glowing arch of coloured lights, parent body', kind='hue', trigger='always', level=2,
                  words=('lights', 'arch', 'neon'), more=[('pulse', 'always', 1)]),
              rotor('record', 'optional: the record behind the front window, parent body, facing front (+Z)', 'z', trigger='click',
                    level=1, words=('record', 'disc', 'vinyl'), optional=True),
              single=[act('whole', 'hue', 'always', level=1)],
              fixture=('주크박스', [
                  box('body', [.8, 1.3, .5], [0, .65, 0], DARK_WOOD),
                  ball('lights', [.8, .6, .52], [0, .45, 0], '#fd79a8', 'body'),
                  box('window', [.5, .3, .02], [0, 0, .26], DARK, 'body'),
                  box('record', [.24, .24, .02], [0, 0, .28], '#1e1e1e', 'body')])),
    furniture('telephone', '전화기', 'Telephone', 'bobbing', 'electronics',
              ['전화기', '전화', '유선전화', '공중전화', 'telephone', 'phone', 'rotary phone', 'landline', 'payphone'],
              body('the phone base', 'base', ('base', 'body', 'phone')),
              part('receiver', 'the handset on top, parent base; it jumps when the phone rings', 'receiver', 'handset',
                   moves=[act('receiver', 'bounce', 'click', level=1)]),
              part('dial', 'optional: the rotary dial on the front, parent base', 'dial', 'keypad', optional=True,
                   moves=[act('dial', 'tick', 'click', axis='z', angle=30)]),
              single=[act('whole', 'bounce', 'click', level=1)],
              fixture=('전화기', [
                  box('base', [.3, .15, .25], [0, .075, 0], RED),
                  box('receiver', [.32, .06, .08], [0, .11, -.04], '#a93226', 'base'),
                  box('dial', [.12, .12, .02], [0, 0, .13], WHITE, 'base')])),
    furniture('robot_vacuum', '로봇청소기', 'Robot vacuum', 'spinner', 'electronics',
              ['로봇청소기', '청소기', '진공청소기', 'robot vacuum', 'robot cleaner', 'roomba', 'vacuum', 'vacuum cleaner'],
              body('the round flat robot', 'body', moves=[act('whole', 'spin', 'click', level=2)]),
              lit('light', 'optional: the status light on top, parent body', kind='pulse', trigger='always', level=1, or_whole=False,
                  words=('light', 'led'), optional=True),
              single=[act('whole', 'spin', 'click', level=2)],
              fixture=('로봇청소기', [
                  ball('body', [.4, .1, .4], [0, .05, 0], DARK),
                  ball('lid', [.32, .03, .32], [0, .05, 0], IRON, 'body'),
                  box('light', [.06, .02, .06], [0, .065, .08], '#55efc4', 'body'),
                  box('bumper', [.2, .06, .05], [0, 0, .19], STEEL, 'body')])),
    furniture('heater', '난로', 'Heater', 'light', 'electronics',
              ['난로', '히터', '온풍기', '라디에이터', '전기난로', '석유난로', '장작난로', '난방기', 'heater', 'radiator', 'space heater',
               'wood stove', 'wood burner'],
              body('the heater body', 'body'),
              lit('element', 'the heating element or fire window on the front, parent body; it glows when switched on', level=2,
                  words=('element', 'coil', 'glow', 'grill', 'window')),
              single=[act('whole', 'glow', 'click', level=1)],
              fixture=('난로', [
                  box('body', [.5, .6, .3], [0, .3, 0], '#dfe6e9'),
                  box('element', [.36, .3, .02], [0, .05, .155], '#ff6b35', 'body'),
                  box('handle', [.3, .04, .06], [0, .32, 0], DARK, 'body')])),
    furniture('air_conditioner', '에어컨', 'Air conditioner', 'appliance', 'electronics',
              ['에어컨', '냉방기', '벽걸이에어컨', 'air conditioner', 'aircon', 'air con'],
              body('the indoor unit', 'body'),
              part('louver', 'the air flap along the bottom front, parent body, pivot [0,.5,0] at its top edge; it opens when switched '
                   'on', 'louver', 'louvre', 'flap', 'vent', moves=[act('louver', 'hinge', 'click', axis='x', angle=-40)]),
              lit('light', 'optional: the status light, parent body', level=1, or_whole=False, words=('light', 'led'), optional=True),
              fixture=('에어컨', [
                  box('body', [1.0, .32, .25], [0, 1.6, 0], WHITE),
                  box('louver', [.85, .06, .02], [0, -.1, .135], '#dfe6e9', 'body', pivot=[0, .5, 0]),
                  box('light', [.04, .03, .02], [.4, .05, .13], '#74b9ff', 'body')])),
    furniture('cash_register', '금전등록기', 'Cash register', 'sliding', 'electronics',
              ['금전등록기', '계산대', '포스기', '카운터', 'cash register', 'checkout counter'],
              body('the register with its keys', 'body'),
              drawer(what='the cash drawer at the bottom', cm=25, level=3),
              lit('display', 'optional: the little display on top, parent body', level=1, or_whole=False, words=('display', 'screen'),
                  optional=True),
              fixture=('금전등록기', [
                  box('body', [.5, .25, .45], [0, .125, 0], IRON),
                  box('drawer', [.46, .1, .4], [0, -.07, .03], STEEL, 'body'),
                  box('keys', [.4, .06, .2], [0, .15, .08], DARK, 'body', rotation=[-20, 0, 0]),
                  box('display', [.25, .12, .03], [0, .24, -.12], '#55efc4', 'body')])),

    # Music.
    furniture('piano', '피아노', 'Piano', 'hinged', 'music',
              ['피아노', '그랜드피아노', '업라이트피아노', '전자피아노', '건반', '오르간', 'piano', 'grand piano', 'upright piano',
               'pianoforte', 'organ'],
              body('the piano body with its key bed', 'body'),
              lid(what='the key cover over the keys', of='the key bed or body', angle=-95),
              lit('keys', 'optional: the row of keys under the cover, parent the key bed or body; they shimmer while played',
                  kind='pulse', level=1, or_whole=False, words=('keys', 'keyboard'), optional=True),
              fixture=('피아노', [
                  box('body', [1.4, 1.2, .55], [0, .6, 0], DARK),
                  box('keybed', [1.3, .1, .3], [0, -.15, .4], DARK, 'body'),
                  box('keys', [1.2, .03, .25], [0, .065, 0], WHITE, 'keybed'),
                  box('lid', [1.25, .04, .28], [0, .1, -.14], '#3d3d3d', 'keybed', pivot=[0, 0, -.5])])),
    furniture('drum', '드럼', 'Drum', 'swaying', 'music',
              ['드럼', '드럼세트', '큰북', '작은북', '장구', '소고', '봉고', '젬베', 'drum', 'drum kit', 'drum set', 'snare drum',
               'bongo', 'djembe'],
              body('the drum', 'body', ('body', 'drum', 'shell', 'base'), moves=[act('whole', 'sway', 'click', level=1)]),
              single=[act('whole', 'sway', 'click', level=1)],
              fixture=('드럼', [
                  box('body', [.5, .4, .5], [0, .2, 0], RED),
                  ball('skin', [.5, .04, .5], [0, .2, 0], WHITE, 'body'),
                  box('sticks', [.4, .03, .03], [0, .24, .1], '#e0b07a', 'body', rotation=[0, 30, 0])])),
    furniture('string_instrument', '현악기', 'String instrument', 'swaying', 'music',
              ['기타', '통기타', '전기기타', '일렉기타', '클래식기타', '우쿨렐레', '바이올린', '첼로', '하프', '가야금', '거문고', 'guitar',
               'ukulele', 'violin', 'cello', 'harp', 'lute', 'mandolin', 'banjo'],
              body('the instrument', 'body', ('body', 'guitar', 'violin', 'base'), moves=[act('whole', 'sway', 'click', level=1)]),
              single=[act('whole', 'sway', 'click', level=1)],
              fixture=('통기타', [
                  ball('body', [.4, .5, .12], [0, .25, 0], '#d68910'),
                  box('neck', [.07, .6, .04], [0, .5, 0], '#6d4c41', 'body'),
                  box('head', [.1, .12, .05], [0, .34, 0], '#3e2723', 'neck'),
                  ball('hole', [.12, .12, .02], [0, .05, .06], '#2d1f17', 'body')])),
    furniture('metronome', '메트로놈', 'Metronome', 'swinging', 'music',
              ['메트로놈', 'metronome'],
              body('the pyramid-shaped case', 'body'),
              part('pendulum', 'the pendulum arm on the front, parent body, pivot [0,-.5,0] at its foot; it ticks side to side',
                   'pendulum', 'arm', 'rod', moves=[act('pendulum', 'rock', 'always', axis='z', level=3)]),
              fixture=('메트로놈', [
                  box('body', [.25, .4, .18], [0, .2, 0], DARK_WOOD),
                  box('face', [.15, .3, .02], [0, .02, .09], IVORY, 'body'),
                  box('pendulum', [.02, .32, .02], [0, -.12, .11], DARK, 'body', pivot=[0, -.5, 0]),
                  box('weight', [.06, .04, .03], [0, .2, 0], BRASS, 'pendulum')])),
    furniture('bell', '종', 'Bell', 'swinging', 'music',
              ['종', '종탑', '범종', '교회종', 'bell', 'church bell', 'temple bell', 'bell tower', 'school bell'],
              body('the beam or tower the bell hangs from', 'frame', ('frame', 'beam', 'tower', 'post', 'stand')),
              hanging('bell', 'the bell', trigger='click', level=3, words=('bell',)),
              fixture=('종', [
                  box('frame', [1.0, .12, .15], [0, 1.5, 0], DARK_WOOD),
                  box('post_left', [.12, 1.5, .12], [-.45, -.75, 0], DARK_WOOD, 'frame'),
                  box('post_right', [.12, 1.5, .12], [.45, -.75, 0], DARK_WOOD, 'frame'),
                  box('roof', [1.2, .1, .4], [0, .11, 0], '#6d4c41', 'frame'),
                  ball('bell', [.5, .55, .5], [0, -.06, 0], BRASS, 'frame', pivot=[0, .5, 0])])),

    # Decor.
    furniture('aquarium', '어항', 'Aquarium', 'bobbing', 'decor',
              ['어항', '수족관', '물고기어항', 'aquarium', 'fish tank', 'fishbowl', 'fish bowl'],
              body('the glass tank of water', 'tank', ('tank', 'bowl', 'glass', 'body', 'base'),
                   moves=[act('tank', 'pulse', 'always', level=1)]),
              part('fish', 'a fish swimming at the front of the water, parent tank; it wiggles and bobs', 'fish', 'goldfish',
                   moves=[act('fish', 'sway', 'always', level=2), act('fish', 'bounce', 'always', level=1)]),
              single=[act('whole', 'pulse', 'always', level=1)],
              fixture=('어항', [
                  box('stand', [.9, .5, .4], [0, .25, 0], DARK_WOOD),
                  box('tank', [.85, .55, .38], [0, .525, 0], '#a8dadc', 'stand'),
                  ball('fish', [.2, .1, .06], [.1, 0, .2], '#ff9f43', 'tank'),
                  ball('weed', [.12, .35, .1], [-.28, -.1, .15], GREEN, 'tank')])),
    furniture('painting', '그림', 'Painting', 'swinging', 'decor',
              ['그림', '액자', '명화', '초상화', '풍경화', '유화', '포스터', '사진액자', 'painting', 'picture', 'picture frame',
               'photo frame', 'portrait', 'poster'],
              body('a small nail or hook on the wall it hangs from', 'hook', ('hook', 'nail', 'hanger')),
              hanging('picture', 'the framed picture', trigger='near', words=('picture', 'frame', 'canvas', 'painting'), of='hook'),
              fixture=('그림 액자', [
                  box('hook', [.04, .04, .04], [0, 1.6, 0], DARK),
                  box('picture', [.8, .6, .04], [0, -.02, .03], BRASS, 'hook', pivot=[0, .5, 0]),
                  box('canvas', [.68, .48, .02], [0, -.3, .025], '#74b9ff', 'picture'),
                  box('hill', [.68, .2, .022], [0, -.44, .027], GREEN, 'picture')])),
    furniture('mirror', '거울', 'Mirror', 'light', 'decor',
              ['거울', '전신거울', '손거울', '화장거울', '스탠드거울', 'mirror', 'full length mirror', 'vanity mirror', 'standing mirror',
               'hand mirror'],
              body('the frame', 'frame', ('frame', 'stand', 'body', 'base')),
              lit('glass', 'the mirror glass on the front (+Z), parent frame; it shimmers when someone comes near', kind='pulse',
                  trigger='near', level=1, words=('glass', 'mirror', 'surface')),
              single=[act('whole', 'pulse', 'near', level=1)],
              fixture=('전신거울', [
                  box('frame', [.6, 1.6, .06], [0, .8, 0], BRASS),
                  box('glass', [.5, 1.45, .02], [0, 0, .035], '#d6eaf8', 'frame'),
                  box('foot', [.5, .05, .35], [0, -.775, 0], DARK_WOOD, 'frame')])),
    furniture('curtain', '커튼', 'Curtain', 'sliding', 'decor',
              ['커튼', '블라인드', '암막커튼', '레이스커튼', '가림막', 'curtain', 'drapes', 'drape', 'blinds'],
              body('the curtain rod', 'rod', ('rod', 'rail', 'pole', 'base')),
              part('curtain', 'the curtain cloth hanging from the rod, parent rod, pivot [0,.5,0] at its top; it slides along the rod '
                   'and stirs when someone passes', 'curtain', 'cloth', 'drape', 'fabric',
                   moves=[act('curtain', 'slide', 'click', axis='x', angle=50), act('curtain', 'sway', 'near', level=1)]),
              single=[act('whole', 'sway', 'near', level=1)],
              fixture=('커튼', [
                  box('rod', [1.6, .04, .04], [0, 2.0, 0], DARK_WOOD),
                  box('curtain', [.75, 1.8, .04], [-.38, -.02, .03], '#e17055', 'rod', pivot=[0, .5, 0]),
                  box('pane', [1.2, 1.2, .02], [0, -.8, -.03], GLASS, 'rod')])),
    furniture('rug', '러그', 'Rug', 'rest', 'decor',
              ['러그', '카펫', '양탄자', '깔개', '매트', '발매트', '돗자리', 'rug', 'carpet', 'mat', 'doormat', 'bath mat', 'yoga mat',
               'tatami', 'picnic mat'],
              whole('the flat rug', 'rug', 'carpet', 'mat', 'body'),
              rest='sit',
              fixture=('러그', [
                  box('rug', [1.6, .02, 1.0], [0, .01, 0], RED),
                  ball('pattern', [.9, .02, .5], [0, .004, 0], YELLOW, 'rug')])),
    furniture('vase', '꽃병', 'Vase', 'rocker', 'decor',
              ['꽃병', '화병', '항아리', '도자기', 'vase', 'urn', 'pottery'],
              whole('the vase', 'vase', 'jar', 'body', moves=[act('whole', 'rock', 'near', axis='z', level=1)]),
              single=[act('whole', 'rock', 'near', axis='z', level=1)],
              fixture=('꽃병', [
                  ball('vase', [.35, .5, .35], [0, .25, 0], BLUE),
                  box('neck', [.14, .15, .14], [0, .3, 0], BLUE, 'vase'),
                  ball('flowers', [.3, .25, .3], [0, .18, 0], PINK, 'neck')])),
    furniture('trophy', '트로피', 'Trophy', 'spinner', 'decor',
              ['트로피', '우승컵', '상패', 'trophy', 'trophy cup', 'award'],
              body('the base', 'base', ('base', 'stand', 'plinth', 'body')),
              turntable('cup', 'the cup or figure on top, parent base; it turns slowly and gleams', words=('cup', 'figure', 'trophy'),
                        more=[act('cup', 'pulse', 'always', level=1)]),
              single=[act('whole', 'pulse', 'always', level=1)],
              fixture=('트로피', [
                  box('base', [.3, .12, .3], [0, .06, 0], DARK),
                  box('stem', [.08, .2, .08], [0, .16, 0], GOLD, 'base'),
                  box('cup', [.3, .25, .2], [0, .225, 0], '#f1c40f', 'stem')])),
    furniture('statue', '조각상', 'Statue', 'spinner', 'decor',
              ['동상', '조각상', '석상', '흉상', '조각', '피규어', 'statue', 'sculpture', 'bust', 'figurine', 'monument'],
              body('the pedestal', 'stand', ('stand', 'pedestal', 'plinth', 'base')),
              turntable('sculpture', 'the sculpture on the pedestal, parent stand; it turns slowly to show itself off', trigger='click',
                        words=('sculpture', 'statue', 'figure', 'bust')),
              fixture=('조각상', [
                  box('stand', [.5, .6, .5], [0, .3, 0], '#dfe6e9'),
                  ball('sculpture', [.3, .6, .25], [0, .6, 0], STEEL, 'stand'),
                  ball('head', [.18, .2, .18], [0, .38, 0], STEEL, 'sculpture'),
                  box('arm', [.35, .06, .06], [.1, .1, 0], STEEL, 'sculpture', rotation=[0, 0, 30])])),
    furniture('snow_globe', '스노볼', 'Snow globe', 'spinner', 'decor',
              ['스노볼', '스노우볼', '스노글로브', 'snow globe', 'snowglobe'],
              body('the base', 'base', ('base', 'stand', 'body')),
              turntable('globe', 'the glass globe with its little scene, parent base; it turns and sparkles when shaken', trigger='click',
                        level=2, words=('globe', 'dome', 'glass', 'sphere'), more=[act('globe', 'pulse', 'click', level=2)]),
              fixture=('스노볼', [
                  box('base', [.3, .12, .3], [0, .06, 0], DARK_WOOD),
                  ball('globe', [.32, .32, .32], [0, .2, 0], '#dff3ff', 'base'),
                  box('house', [.1, .1, .1], [0, -.04, .12], RED, 'globe')])),
    furniture('christmas_tree', '크리스마스트리', 'Christmas tree', 'light', 'decor',
              ['크리스마스트리', '성탄트리', '트리', 'christmas tree', 'xmas tree'],
              body('the tree', 'tree', ('tree', 'pine', 'body', 'base')),
              lit('lights', 'the strings of little lights around it, parent tree; they twinkle in changing colours', kind='pulse',
                  trigger='always', level=2, words=('lights', 'garland', 'bulbs'), more=[('hue', 'always', 1)]),
              lit('star', 'optional: the star on top, parent tree', trigger='always', level=2, or_whole=False, words=('star', 'topper'),
                  optional=True),
              single=[act('whole', 'pulse', 'always', level=1)],
              fixture=('크리스마스트리', [
                  box('pot', [.35, .25, .35], [0, .125, 0], RED),
                  ball('tree', [.9, 1.3, .9], [0, .775, 0], '#27ae60', 'pot'),
                  ball('lights', [.94, .25, .94], [0, -.1, 0], YELLOW, 'tree'),
                  box('star', [.18, .18, .06], [0, .7, 0], '#f1c40f', 'tree', rotation=[0, 0, 45])])),
    furniture('balloon', '풍선', 'Balloon', 'bobbing', 'decor',
              ['풍선', '고무풍선', '열기구', 'balloon', 'hot air balloon'],
              body('a little weight on the ground the string is tied to', 'weight', ('weight', 'base', 'anchor', 'stand')),
              part('balloon', 'the balloon with its string, parent weight, pivot [0,-.5,0] at its knot; it floats and sways', 'balloon',
                   moves=[act('balloon', 'bounce', 'always', level=1), act('balloon', 'sway', 'always', level=1)]),
              single=[act('whole', 'bounce', 'always', level=1), act('whole', 'sway', 'always', level=1)],
              fixture=('풍선', [
                  box('weight', [.12, .08, .12], [0, .04, 0], DARK),
                  ball('balloon', [.45, .55, .45], [0, 1.04, 0], '#e74c3c', 'weight', pivot=[0, -.5, 0]),
                  box('string', [.02, 1.0, .02], [0, -.5, 0], WHITE, 'balloon')])),
    furniture('piggy_bank', '저금통', 'Piggy bank', 'bobbing', 'decor',
              ['저금통', '돼지저금통', '저금함', 'piggy bank', 'coin bank', 'money box'],
              whole('the piggy bank', 'pig', 'bank', 'body', moves=[act('whole', 'bounce', 'click', level=1)]),
              single=[act('whole', 'bounce', 'click', level=1)],
              fixture=('돼지저금통', [
                  ball('pig', [.25, .3, .4], [0, .17, 0], '#f8a5c2'),
                  ball('snout', [.1, .08, .06], [0, 0, .2], '#e77f9e', 'pig'),
                  box('ears', [.2, .06, .04], [0, .15, .08], '#e77f9e', 'pig'),
                  box('legs', [.2, .06, .3], [0, -.14, 0], '#e77f9e', 'pig')])),

    # Yard and playground.
    furniture('fountain', '분수', 'Fountain', 'bobbing', 'outdoor',
              ['분수', '분수대', '정원분수', 'fountain', 'water fountain', 'garden fountain', 'bird bath', 'birdbath'],
              body('the basin', 'basin', ('basin', 'pool', 'base', 'body')),
              part('water', 'the spout of water rising from the top, parent the basin or its column, pivot [0,-.5,0] at its foot; it '
                   'bobs and shimmers', 'water', 'spout', 'jet', 'spray',
                   moves=[act('water', 'bounce', 'always', level=1), act('water', 'pulse', 'always', level=1)]),
              single=[act('whole', 'pulse', 'always', level=1)],
              fixture=('분수', [
                  ball('basin', [1.4, .35, 1.4], [0, .175, 0], STEEL),
                  ball('pool', [1.2, .05, 1.2], [0, .15, 0], WATER, 'basin'),
                  box('column', [.15, .6, .15], [0, .4, 0], '#dfe6e9', 'basin'),
                  ball('bowl', [.5, .12, .5], [0, .3, 0], STEEL, 'column'),
                  ball('water', [.25, .4, .25], [0, .05, 0], '#a8e0ff', 'bowl', pivot=[0, -.5, 0])])),
    furniture('slide', '미끄럼틀', 'Slide', 'still', 'outdoor',
              ['미끄럼틀', '미끄럼대', 'slide', 'playground slide'],
              whole('the slide with its ladder and platform', 'slide', 'ladder', 'body', 'frame'),
              fixture=('미끄럼틀', [
                  box('ladder', [.5, 1.2, .1], [0, .6, -.75], RED),
                  box('platform', [.6, .06, .5], [0, .6, .25], YELLOW, 'ladder'),
                  box('chute', [.5, .05, 1.6], [0, -.514, .863], YELLOW, 'platform', rotation=[40, 0, 0])])),
    furniture('seesaw', '시소', 'Seesaw', 'rocker', 'outdoor',
              ['시소', 'seesaw', 'see-saw', 'teeter totter'],
              body('the pivot stand in the middle', 'base', ('base', 'stand', 'pivot', 'post')),
              part('plank', 'the long plank resting on the stand, parent base, turning at its middle; it tips up and down when pushed',
                   'plank', 'board', 'beam', 'seat', moves=[act('plank', 'rock', 'click', axis='z', level=3)]),
              rest='sit',
              fixture=('시소', [
                  box('base', [.3, .4, .3], [0, .2, 0], DARK_WOOD),
                  box('plank', [2.4, .08, .35], [0, .24, 0], '#e17055', 'base'),
                  box('handle_left', [.05, .25, .3], [-.95, .16, 0], DARK, 'plank'),
                  box('handle_right', [.05, .25, .3], [.95, .16, 0], DARK, 'plank')])),
    furniture('carousel', '회전목마', 'Carousel', 'spinner', 'outdoor',
              ['회전목마', '메리고라운드', '뺑뺑이', 'carousel', 'merry-go-round', 'roundabout'],
              body('the round base', 'base', ('base', 'ground', 'body')),
              turntable('platform', 'the turning platform with its pole, roof and horses, parent base', level=2,
                        words=('platform', 'disc', 'deck')),
              part('horse', 'optional: one horse on the platform, parent platform; it rides up and down', 'horse', 'pony',
                   optional=True, moves=[act('horse', 'bounce', 'always', level=1)]),
              single=[act('whole', 'turn', 'always', level=1)],
              fixture=('회전목마', [
                  ball('base', [1.6, .15, 1.6], [0, .075, 0], STEEL),
                  ball('platform', [1.5, .08, 1.5], [0, .11, 0], '#fd79a8', 'base'),
                  box('pole', [.08, 1.4, .08], [0, .74, 0], YELLOW, 'platform'),
                  ball('roof', [1.6, .4, 1.6], [0, .75, 0], '#e84393', 'pole'),
                  box('horse', [.15, .35, .45], [.55, .45, 0], WHITE, 'platform'),
                  box('pony', [.15, .35, .45], [-.55, .45, 0], WHITE, 'platform')])),
    furniture('trampoline', '트램펄린', 'Trampoline', 'bobbing', 'outdoor',
              ['트램펄린', '방방', '봉봉', 'trampoline'],
              body('the round frame on its legs', 'frame', ('frame', 'ring', 'base', 'legs')),
              part('mat', 'the springy mat, parent frame; it bounces when jumped on', 'mat', 'bed', 'surface',
                   moves=[act('mat', 'bounce', 'click', level=1)]),
              single=[act('whole', 'bounce', 'click', level=1)],
              fixture=('트램펄린', [
                  ball('frame', [1.6, .08, 1.6], [0, .45, 0], DARK),
                  box('leg_1', [.05, .45, .05], [.55, -.225, .55], IRON, 'frame'),
                  box('leg_2', [.05, .45, .05], [-.55, -.225, .55], IRON, 'frame'),
                  box('leg_3', [.05, .45, .05], [.55, -.225, -.55], IRON, 'frame'),
                  box('leg_4', [.05, .45, .05], [-.55, -.225, -.55], IRON, 'frame'),
                  ball('mat', [1.4, .04, 1.4], [0, .03, 0], '#0984e3', 'frame')])),
    furniture('mailbox', '우편함', 'Mailbox', 'hinged', 'outdoor',
              ['우편함', '우체통', '편지함', '우편통', 'mailbox', 'letterbox', 'letter box', 'postbox', 'post box', 'mail box'],
              body('the post', 'post', ('post', 'pole', 'stand', 'base')),
              part('box', 'the box on the post, parent post', 'box', 'case'),
              drop_door(what='the front door of the box', of='box'),
              part('flag', 'the little flag on the side, parent box, pivot [0,-.5,0] at its foot, lying forward; it goes up when there '
                   'is post', 'flag', 'signal', moves=[act('flag', 'hinge', 'click', axis='x', angle=-90)]),
              fixture=('우편함', [
                  box('post', [.1, 1.0, .1], [0, .5, 0], DARK_WOOD),
                  box('box', [.3, .3, .5], [0, .65, 0], RED, 'post'),
                  box('door', [.28, .28, .03], [0, -.14, .265], '#a93226', 'box', pivot=[0, -.5, 0]),
                  box('flag', [.03, .25, .05], [.17, -.05, .1], YELLOW, 'box', pivot=[0, -.5, 0], rotation=[90, 0, 0])])),
    furniture('birdhouse', '새집', 'Birdhouse', 'bobbing', 'outdoor',
              ['새집', '새둥지', '둥지', '새장', 'birdhouse', 'bird house', 'nest box', 'bird feeder', 'birdcage', 'bird cage', 'nest'],
              body('the post', 'post', ('post', 'pole', 'stand', 'base')),
              part('house', 'the little house on the post, parent post', 'house', 'cage'),
              part('bird', 'optional: a little bird on the perch, parent house; it hops when someone comes near and bobs its head',
                   'bird', 'robin', 'sparrow', optional=True,
                   moves=[act('bird', 'bounce', 'near', level=1), act('bird', 'sway', 'always', level=1)]),
              fixture=('새집', [
                  box('post', [.08, 1.2, .08], [0, .6, 0], DARK_WOOD),
                  box('house', [.35, .35, .3], [0, .775, 0], '#e17055', 'post'),
                  box('roof', [.45, .06, .4], [0, .2, 0], DARK_WOOD, 'house'),
                  ball('hole', [.1, .1, .02], [0, .04, .15], '#2d1f17', 'house'),
                  box('perch', [.03, .03, .1], [0, -.07, .2], DARK_WOOD, 'house'),
                  ball('bird', [.1, .08, .12], [0, -.015, .23], '#74b9ff', 'house')])),
    furniture('weathervane', '풍향계', 'Weathervane', 'swinging', 'outdoor',
              ['풍향계', '풍향기', 'weathervane', 'weather vane', 'weathercock', 'wind vane'],
              body('the post with its compass arms', 'post', ('post', 'pole', 'stand', 'base')),
              part('vane', 'the arrow or rooster on top, parent post; it swings round with the wind', 'vane', 'arrow', 'rooster',
                   moves=[act('vane', 'rock', 'always', axis='y', level=2)]),
              fixture=('풍향계', [
                  box('post', [.06, 1.6, .06], [0, .8, 0], DARK),
                  box('cross_x', [.6, .03, .03], [0, .6, 0], DARK, 'post'),
                  box('cross_z', [.03, .03, .6], [0, .6, 0], DARK, 'post'),
                  box('vane', [.7, .15, .03], [0, .82, 0], BRASS, 'post')])),
    furniture('well', '우물', 'Well', 'spinner', 'outdoor',
              ['우물', '두레박', 'well', 'wishing well', 'water well'],
              body('the round stone wall', 'wall', ('wall', 'stone', 'base', 'body')),
              rotor('crank', 'the crank handle at the side of the beam, parent wall, turning about X', 'x', trigger='click', level=1,
                    words=('crank', 'winch', 'handle')),
              drawer('bucket', what='the bucket on its rope under the beam', of='wall', cm=40, axis='y', level=1, words=('bucket', 'pail')),
              part('roof', 'optional: the little roof on two posts, parent wall', 'roof', 'beam', optional=True),
              fixture=('우물', [
                  box('wall', [1.0, .6, 1.0], [0, .3, 0], '#95a5a6'),
                  ball('water', [.8, .02, .8], [0, .3, 0], '#2e86de', 'wall'),
                  box('post_left', [.08, 1.0, .08], [-.45, .8, 0], DARK_WOOD, 'wall'),
                  box('post_right', [.08, 1.0, .08], [.45, .8, 0], DARK_WOOD, 'wall'),
                  box('roof', [1.1, .1, .6], [0, 1.35, 0], '#6d4c41', 'wall'),
                  box('crank', [.05, .3, .05], [.55, 1.0, 0], DARK, 'wall'),
                  box('bucket', [.2, .2, .2], [0, .55, 0], DARK_WOOD, 'wall')])),
    furniture('scarecrow', '허수아비', 'Scarecrow', 'swaying', 'outdoor',
              ['허수아비', 'scarecrow'],
              body('the post in the ground', 'post', ('post', 'pole', 'stake', 'base')),
              part('scarecrow', 'the straw figure with arms, head and hat, parent post, pivot [0,-.5,0] at its foot; it sways in the wind',
                   'scarecrow', 'figure', 'straw', moves=[act('scarecrow', 'sway', 'always', level=1)]),
              single=[act('whole', 'sway', 'always', level=1)],
              fixture=('허수아비', [
                  box('post', [.08, 1.6, .08], [0, .8, 0], DARK_WOOD),
                  box('scarecrow', [.35, .6, .25], [0, .1, 0], GOLD, 'post', pivot=[0, -.5, 0]),
                  box('arms', [1.2, .08, .08], [0, .45, 0], DARK_WOOD, 'scarecrow'),
                  ball('head', [.3, .3, .3], [0, .75, 0], '#f5deb3', 'scarecrow'),
                  box('hat', [.4, .12, .4], [0, .2, 0], '#6d4c41', 'head')])),

    # Toys and hobbies.
    furniture('rocking_horse', '흔들목마', 'Rocking horse', 'rocker', 'toys',
              ['흔들목마', '목마', '장난감말', 'rocking horse', 'hobby horse'],
              whole('the horse on its rockers', 'horse', 'rocker', 'body', moves=[act('whole', 'rock', 'click', axis='x', level=2)]),
              single=[act('whole', 'rock', 'click', axis='x', level=2)], rest='sit',
              fixture=('흔들목마', [
                  box('rockers', [.3, .06, 1.1], [0, .03, 0], DARK_WOOD),
                  box('legs', [.25, .35, .7], [0, .2, 0], LIGHT_WOOD, 'rockers'),
                  box('horse', [.25, .3, .8], [0, .3, 0], '#f5deb3', 'legs'),
                  box('head', [.2, .45, .25], [0, .3, .38], '#f5deb3', 'horse', rotation=[20, 0, 0]),
                  box('saddle', [.3, .05, .3], [0, .17, -.05], RED, 'horse')])),
    furniture('spinning_top', '팽이', 'Spinning top', 'spinner', 'toys',
              ['팽이', '팽이장난감', 'spinning top', 'whirligig'],
              whole('the top', 'top', 'body', moves=[act('whole', 'spin', 'always', level=3), act('whole', 'sway', 'always', level=1)]),
              single=[act('whole', 'spin', 'always', level=3), act('whole', 'sway', 'always', level=1)],
              fixture=('팽이', [
                  ball('top', [.4, .25, .4], [0, .2, 0], '#e84393'),
                  box('tip', [.06, .12, .06], [0, -.15, 0], DARK, 'top'),
                  box('handle', [.06, .15, .06], [0, .18, 0], DARK, 'top'),
                  box('stripe', [.41, .05, .1], [0, .02, 0], YELLOW, 'top')])),
    furniture('telescope', '망원경', 'Telescope', 'hinged', 'toys',
              ['망원경', '천체망원경', '쌍안경', 'telescope', 'spyglass'],
              body('the tripod or stand', 'tripod', ('tripod', 'stand', 'base', 'mount', 'legs')),
              part('tube', 'the telescope tube, parent tripod, turning at its middle; it tilts up to the sky and scans slowly', 'tube',
                   'scope', 'barrel', moves=[act('tube', 'hinge', 'click', axis='x', angle=-25),
                                             act('tube', 'rock', 'always', axis='y', level=1)]),
              fixture=('망원경', [
                  box('tripod', [.06, 1.0, .06], [0, .5, 0], DARK),
                  box('feet', [.6, .04, .6], [0, -.48, 0], DARK, 'tripod'),
                  box('tube', [.14, .14, .9], [0, .55, 0], '#2d3436', 'tripod', rotation=[-15, 0, 0]),
                  box('eyepiece', [.06, .06, .12], [0, 0, -.5], BRASS, 'tube'),
                  ball('lens', [.16, .16, .04], [0, 0, .45], '#74b9ff', 'tube')])),
    furniture('easel', '이젤', 'Easel', 'light', 'toys',
              ['이젤', '화판', 'easel', 'painting easel'],
              body('the easel stand', 'stand', ('stand', 'frame', 'legs', 'base')),
              lit('canvas', 'the canvas on the easel, parent stand; its colours change as it is painted', kind='hue', level=2,
                  or_whole=False, words=('canvas', 'board', 'painting', 'picture')),
              fixture=('이젤', [
                  box('stand', [.06, 1.6, .06], [0, .8, -.1], DARK_WOOD, rotation=[-8, 0, 0]),
                  box('leg_left', [.05, 1.6, .05], [-.35, 0, .12], DARK_WOOD, 'stand', rotation=[0, 0, -12]),
                  box('leg_right', [.05, 1.6, .05], [.35, 0, .12], DARK_WOOD, 'stand', rotation=[0, 0, 12]),
                  box('shelf', [.7, .05, .1], [0, -.1, .1], DARK_WOOD, 'stand'),
                  box('canvas', [.7, .55, .03], [0, .22, .1], '#81ecec', 'stand')])),
    furniture('sewing_machine', '재봉틀', 'Sewing machine', 'spinner', 'toys',
              ['재봉틀', '미싱', '재봉기', 'sewing machine'],
              body('the machine body', 'body'),
              rotor('wheel', 'the hand wheel on the right side, parent body, turning about X', 'x', trigger='click', level=2,
                    words=('wheel', 'handwheel', 'flywheel')),
              lit('light', 'optional: the little sewing light under the arm, parent body', level=1, or_whole=False,
                  words=('light', 'lamp'), optional=True),
              fixture=('재봉틀', [
                  box('body', [.6, .12, .25], [0, .06, 0], DARK),
                  box('pillar', [.12, .3, .2], [.22, .21, 0], DARK, 'body'),
                  box('arm', [.55, .1, .18], [-.04, .31, 0], DARK, 'body'),
                  box('head', [.1, .18, .18], [-.27, .2, 0], DARK, 'body'),
                  box('wheel', [.04, .2, .06], [.3, .27, 0], STEEL, 'body'),
                  box('light', [.05, .03, .05], [-.2, .245, .07], YELLOW, 'body')])),
    furniture('jack_in_the_box', '깜짝상자', 'Jack-in-the-box', 'hinged', 'toys',
              ['깜짝상자', 'jack in the box'],
              body('the box', 'box', ('box', 'body', 'case')),
              lid(of='box', angle=-110),
              part('clown', 'the clown on its spring, parent box, pivot [0,-.5,0] at its foot, hidden inside; it pops up', 'clown',
                   'jack', 'figure', moves=[act('clown', 'slide', 'click', axis='y', angle=30, level=3),
                                            act('clown', 'sway', 'click', level=2)]),
              single=[act('whole', 'bounce', 'click', level=2)],
              fixture=('깜짝상자', [
                  box('box', [.4, .4, .4], [0, .2, 0], '#e74c3c'),
                  box('lid', [.42, .04, .42], [0, .22, -.21], '#f1c40f', 'box', pivot=[0, 0, -.5]),
                  ball('clown', [.2, .25, .2], [0, -.2, 0], '#fdcb6e', 'box', pivot=[0, -.5, 0]),
                  ball('hat', [.12, .15, .12], [0, .3, 0], '#6c5ce7', 'clown')])),
    furniture('teddy_bear', '곰인형', 'Teddy bear', 'bobbing', 'toys',
              ['곰인형', '인형', '테디베어', '봉제인형', '애착인형', 'teddy bear', 'teddy', 'plush', 'plushie', 'stuffed animal',
               'stuffed toy', 'doll'],
              whole('the plush toy', 'bear', 'teddy', 'doll', 'body',
                    moves=[act('whole', 'bounce', 'click', level=1), act('whole', 'sway', 'near', level=1)]),
              single=[act('whole', 'bounce', 'click', level=1), act('whole', 'sway', 'near', level=1)],
              fixture=('곰인형', [
                  ball('bear', [.35, .4, .3], [0, .2, 0], '#c68e5a'),
                  ball('head', [.3, .28, .26], [0, .3, 0], '#c68e5a', 'bear'),
                  ball('ear_left', [.1, .1, .06], [-.12, .14, 0], '#a0704a', 'head'),
                  ball('ear_right', [.1, .1, .06], [.12, .14, 0], '#a0704a', 'head'),
                  ball('muzzle', [.12, .08, .06], [0, -.03, .13], '#f5deb3', 'head')])),

    # Doors and windows.
    furniture('window', '창문', 'Window', 'hinged', 'doors',
              ['창문', '창호', '들창', '여닫이창', '창틀', 'window', 'windowpane', 'casement'],
              body('the window frame', 'frame', ('frame', 'wall', 'sill', 'body')),
              side_door('pane', what='the glass window leaf', of='frame', angle=-80, words=('pane', 'sash', 'glass', 'leaf')),
              fixture=('창문', [
                  box('frame', [1.0, 1.1, .12], [0, 1.2, 0], IVORY),
                  box('pane', [.9, 1.0, .04], [-.45, 0, .08], GLASS, 'frame', pivot=[-.5, 0, 0]),
                  box('bar', [.9, .03, .045], [.45, 0, 0], IVORY, 'pane'),
                  box('sill', [1.1, .05, .2], [0, -.57, .04], LIGHT_WOOD, 'frame')])),
    furniture('sliding_door', '미닫이문', 'Sliding door', 'sliding', 'doors',
              ['미닫이문', '미닫이', '장지문', '미세기문', '슬라이딩도어', 'sliding door', 'shoji', 'barn door', 'pocket door'],
              body('the door frame', 'frame', ('frame', 'wall', 'track', 'rail', 'body')),
              drawer('panel', what='the sliding door panel', of='frame', cm=85, axis='x', words=('panel', 'door', 'leaf', 'slider')),
              fixture=('미닫이문', [
                  box('frame', [1.3, 2.2, .12], [0, 1.1, 0], DARK_WOOD),
                  box('panel', [.95, 2.0, .05], [0, -.05, .09], IVORY, 'frame'),
                  box('grid_x', [.95, .03, .052], [0, .3, 0], DARK_WOOD, 'panel'),
                  box('grid_y', [.03, 2.0, .052], [0, 0, 0], DARK_WOOD, 'panel')])),
]

# The interaction editor's Korean name for each role id (the game's interaction_panel.gd
# PART_NAMES holds the same names; server/tests check they agree).
ROLE_NAMES = {
    'whole': '전체', 'body': '본체', 'lid': '뚜껑', 'base': '받침', 'hour_hand': '시침', 'minute_hand': '분침',
    'second_hand': '초침', 'door': '문', 'pendulum': '추', 'blades': '날개', 'sails': '날개', 'wheel': '바퀴',
    'drawer': '서랍', 'screen': '화면', 'shade': '갓', 'flame': '불꽃', 'cloth': '깃발 천', 'pole': '깃대', 'frame': '틀',
    'tower': '탑', 'dancer': '인형', 'sphere': '지구', 'stand': '받침대', 'chimes': '방울', 'top': '윗부분', 'box': '상자',
    'pot': '화분', 'leaves': '잎',
    'cushion': '쿠션', 'footrest': '발받침', 'seat': '앉는 자리', 'gem': '보석', 'ropes': '그넷줄', 'net': '그물',
    'backrest': '등받이', 'tabletop': '상판', 'quilt': '이불', 'heater': '히터', 'book': '책', 'dial': '다이얼', 'coat': '외투',
    'mount': '고정대', 'lights': '조명', 'post': '기둥', 'lamp_head': '전등', 'fire': '불', 'logs': '장작', 'stick': '자루',
    'glass': '유리', 'blob': '왁스 방울', 'string': '전선', 'bulbs': '꼬마전구', 'light': '불빛', 'burner': '화구', 'knob': '손잡이',
    'handle': '레버', 'water': '물', 'toast': '식빵', 'jar': '용기', 'blade': '칼날', 'cauldron': '솥', 'tub': '욕조',
    'drum': '세탁통', 'speaker': '스피커', 'antenna': '안테나', 'record': '레코드판', 'tonearm': '톤암', 'buttons': '버튼',
    'cone': '울림판', 'receiver': '수화기', 'element': '발열판', 'louver': '바람날개', 'display': '표시창', 'keys': '건반',
    'bell': '종', 'tank': '수조', 'fish': '물고기', 'basin': '수반', 'hook': '고리', 'picture': '그림', 'rod': '커튼봉',
    'curtain': '커튼', 'cup': '컵', 'sculpture': '조각', 'globe': '유리구슬', 'tree': '나무', 'star': '별', 'weight': '무게추',
    'balloon': '풍선', 'plank': '판자', 'platform': '회전판', 'horse': '목마', 'mat': '매트', 'flag': '깃발', 'house': '새집',
    'bird': '새', 'vane': '풍향판', 'wall': '벽', 'crank': '도르래 손잡이', 'bucket': '두레박', 'roof': '지붕',
    'brew': '물약', 'scarecrow': '허수아비', 'tripod': '삼각대', 'tube': '경통', 'canvas': '캔버스', 'clown': '광대', 'pane': '창짝', 'panel': '판',
}
