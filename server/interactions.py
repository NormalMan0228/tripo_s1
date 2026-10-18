"""Player-made interactions for crafted objects (the game's 상호작용 editor).

An owner gives a crafted object new behaviour without a new craft: ready-made presets
(spin, sway, bounce, glow, pulse, colour, slow turn, open/close a part, and for living
objects: clock hands on the player's local time, a ticking step, a sliding drawer, a candle's
flicker, rocking, a rotor), each with a trigger (click/E, near, leave, always) and a level, or a
sentence the studio's designer
turns into a program for the object's existing parts (no Tripo call; the fixture designer
in development). Either way the result is an ordinary VM program that passes the gates of
designed programs (validate_program, exercise_extended). It is kept per object in
object_interactions and replaces the crafted program on every runtime path: the owner's
assembly, event and invoke routes and the visitors' assembly route (apply() below).
'Rest' (sit/lie) is a flag the room's rest system reads; it needs no program.
A new craft of a library type (server/archetypes.py) starts with that type's presets here.
A behaviour the designer made from a sentence is kept in the learned library
(server/behaviour_library.py): the same sentence on an object with the same parts reuses it,
free and without the designer.

The emit target 'whole' is the object itself: rotations about its base centre, a lift,
and glow/colour on every part. One-part crafts already call their only part 'whole'.
Released clients (<= 0.11.2) know only part ids and stop a program that names another
target, so the 'program' they read has those emits reduced to plain expressions
(compat()); newer clients read interaction.program.
"""
import asyncio
import copy
import json
import math
import uuid
from typing import Literal
from fastapi import HTTPException, Request
from pydantic import Field
from .models import Mutation, Strict
from .asset_vm import AssetVM, ProgramError, validate_program, exercise, exercise_extended, legacy, NAME, EVENTS
from .provider import ProviderError
from . import behaviour_library as library
from . import llm_budget

SCHEMA = '''
CREATE TABLE IF NOT EXISTS object_interactions (
 object_id TEXT PRIMARY KEY REFERENCES objects(id), spec TEXT NOT NULL, compiled TEXT,
 draft TEXT, version INTEGER NOT NULL DEFAULT 0, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS interaction_designs (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), object_id TEXT NOT NULL,
 text TEXT NOT NULL, state TEXT NOT NULL, cost INTEGER NOT NULL, program TEXT, provenance TEXT,
 error TEXT, created REAL NOT NULL, updated REAL NOT NULL);
CREATE INDEX IF NOT EXISTS interaction_designs_owner ON interaction_designs(owner_id, created);
'''

WHOLE = 'whole'
KINDS = ('spin', 'sway', 'bounce', 'glow', 'pulse', 'hue', 'turn', 'hinge',
         'clock', 'tick', 'slide', 'flicker', 'rock', 'rotor')
TRIGGERS = ('click', 'near', 'leave', 'always')
# One-shot motions play once per trigger ('always' loops them); toggles switch on and off.
ACTIONS = ('spin', 'sway', 'bounce', 'hue', 'rock')
# Kinds that move one part of the object (the whole object does not open or slide).
PART_KINDS = ('hinge', 'slide')
# A ticking step gets to its next place in this many seconds, a little past it, and settles.
TICK_EASE = .16
# Games that run the living-objects VM say so in this header; others get programs they can run.
VM_HEADER = 'x-villagen-vm'
MAX_PRESETS = 6
# "글로 설명하기": starseeds per description (refunded when the designer fails) and attempts per
# account per UTC day (failed ones count: they used the model).
DESCRIBE_COST = 5
DESCRIBE_DAILY_LIMIT = 10
TEXT_LIMIT = 200
# A description still designing after this long is given up and refunded.
DESIGN_TIMEOUT = 600
TAU = 2 * math.pi


class Preset(Strict):
    kind: Literal[KINDS]
    trigger: Literal[TRIGGERS] = 'click'
    target: str = Field(default=WHOLE, pattern=NAME.pattern)
    level: int = Field(default=2, ge=1, le=3)
    direction: Literal[-1, 1] = 1
    axis: Literal['x', 'y', 'z'] = 'x'
    # Degrees (hinge), degrees per step (tick) or centimetres (slide).
    angle: int = Field(default=90, ge=-180, le=180)
    # Which hand a 'clock' preset turns.
    hand: Literal['hour', 'minute', 'second'] = 'minute'


class Choice(Strict):
    mode: Literal['original', 'presets', 'custom'] = 'presets'
    presets: list[Preset] = Field(default_factory=list, max_length=MAX_PRESETS)
    # Keep the crafted behaviour under the presets (moving crafts).
    keep: bool = True
    rest: Literal['', 'sit', 'lie'] = ''


class SaveInteraction(Mutation, Choice):
    version: int = Field(ge=1)


class Describe(Mutation):
    text: str = Field(min_length=2, max_length=TEXT_LIMIT)


class InteractionError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def fail(code, status=409):
    raise HTTPException(status, code)


# ---------------------------------------------------------------- compiler

DT = ['input', 'dt']


def s(key):
    return ['state', key]


def total(values):
    out = values[0]
    for v in values[1:]:
        out = ['add', out, v]
    return out


def smooth(u):
    return ['mul', ['mul', u, u], ['sub', 3, ['mul', 2, u]]]


def approach(key, goal, rate):
    return ['store', key, ['add', s(key), ['mul', ['sub', goal, s(key)], ['min', 1, ['mul', DT, rate]]]]]


def advance(key, rate, period):
    return ['store', key, ['mod', ['add', s(key), ['mul', DT, rate]], period]]


def timer(key, duration):
    return ['store', key, ['min', duration, ['add', s(key), DT]]]


def jump(u, strength=2.6):
    """0..1 -> a mechanical step: there quickly, a little past (about 9 %), settled at 1."""
    rest = ['sub', 1, u]
    return ['sub', 1, ['mul', ['mul', rest, rest], ['sub', 1, ['mul', strength, u]]]]


def targets_of(parts):
    ids = [p['id'] for p in parts]
    return ids if WHOLE in ids else ids + [WHOLE]


def build(presets, parts, base=None):
    """Presets -> (program, idle). idle names state a settled object returns to between
    events (a finished one-shot timer, a fade that reached its goal): the server stores it
    after each event so reloading never replays the last animation."""
    ids = [p['id'] for p in parts]
    try:
        presets = [(Preset.model_validate(p) if isinstance(p, dict) else p).model_dump() for p in presets]
    except ValueError:
        raise InteractionError('invalid_preset') from None
    if len(presets) > MAX_PRESETS:
        raise InteractionError('too_many_presets')
    taken = set(base['state']) if base else set()
    prefix = next(p for p in ('ix', 'iy', 'iz', 'iq', 'iw') if not any(k.startswith(p) for k in taken))
    state, idle, seen = {}, {}, set()
    events = {e: [] for e in ('spawn', 'click', 'near', 'leave', 'tick')}
    channels, hues = {}, []

    def channel(op, target, value):
        channels.setdefault((op, target), []).append(value)

    for n, p in enumerate(presets):
        kind, trigger, target, level = p['kind'], p['trigger'], p['target'], p['level'] - 1
        direction = p.get('direction', 1)
        if target != WHOLE and target not in ids:
            raise InteractionError('part_not_found')
        if kind in PART_KINDS and target not in ids:
            raise InteractionError('hinge_needs_part')
        if (kind, target) in seen:
            raise InteractionError('duplicate_preset')
        seen.add((kind, target))

        def key(name):
            return f'{prefix}{n}_{name}'
        tick = events['tick']
        axis = p.get('axis', 'x')
        if kind == 'clock':
            # The player's local time: hour and minute hands glide, the second hand ticks (level 1
            # sweeps). Clockwise seen from the axis' + side, the front of a dial facing +Z.
            clock, hand = ['input', 'clock'], p.get('hand', 'minute')
            if hand == 'hour':
                theta = ['div', clock, 120]
            elif hand == 'minute':
                theta = ['div', clock, 10]
            elif level == 0:
                theta = ['mul', ['mod', clock, 60], 6]
            else:
                sec, u = key('s'), key('u')
                tick.append(['set', sec, ['mod', clock, 60]])
                tick.append(['set', u, ['min', 1, ['div', ['mod', ['var', sec], 1], TICK_EASE]]])
                whole_seconds = ['sub', ['var', sec], ['mod', ['var', sec], 1]]
                theta = ['mul', ['add', ['sub', whole_seconds, 1], jump(['var', u], (2.6, 3.4)[level - 1])], 6]
            channel('rotate_' + axis, target, ['mul', ['mod', theta, 360], -direction])
            continue
        if kind == 'tick':
            # Steps of 'angle' degrees (6 by default) with a mechanical jump: every 2 / 1 / 0.5 s
            # (level) while running, or one step per click.
            step = abs(p.get('angle', 6)) or 6
            period = (2.0, 1.0, .5)[level]
            count = 360 // math.gcd(step, 360)
            u = key('u')
            if trigger == 'click':
                n, t = key('n'), key('t')
                state[n], state[t] = 0, TICK_EASE
                idle[t] = TICK_EASE
                events['click'].extend([['store', n, ['mod', ['add', s(n), 1], count]], ['store', t, 0]])
                tick.extend([timer(t, TICK_EASE), ['set', u, ['div', s(t), TICK_EASE]]])
                theta = ['mul', ['add', ['sub', s(n), 1], jump(['var', u])], step]
            else:
                ph, k = key('p'), key('k')
                state[ph] = 0
                rate = DT
                if trigger in ('near', 'leave'):
                    on = key('on')
                    state[on] = float(trigger == 'leave')
                    events['near'].append(['store', on, float(trigger == 'near')])
                    events['leave'].append(['store', on, float(trigger == 'leave')])
                    rate = ['mul', DT, s(on)]
                tick.extend([['store', ph, ['mod', ['add', s(ph), rate], period * count]], ['set', k, ['div', s(ph), period]],
                             ['set', u, ['min', 1, ['div', ['mul', ['mod', ['var', k], 1], period], TICK_EASE]]]])
                theta = ['mul', ['add', ['sub', ['var', k], ['mod', ['var', k], 1]], jump(['var', u])], step]
            channel('rotate_' + axis, target, ['mul', theta, -direction])
            continue
        if kind in ACTIONS:
            looping = trigger == 'always'
            fire = []
            if kind == 'hue':
                c, a = key('c'), key('a')
                state[c], state[a] = .08, float(looping)
                if looping:
                    tick.append(advance(c, (.03, .06, .12)[level], 1))
                else:
                    fire = [['store', c, ['mod', ['add', s(c), (.125, 1 / 6, .25)[level]], 1]], ['store', a, 1]]
                hues.append((target, a, c))
            elif looping:
                ph = key('p')
                state[ph] = 0
                if kind == 'spin':
                    tick.append(advance(ph, (45, 90, 180)[level] * direction, 360))
                    channel('rotate_y', target, s(ph))
                elif kind == 'sway':
                    tick.append(advance(ph, TAU * .5, TAU))
                    channel('rotate_z', target, ['mul', (6, 12, 20)[level], ['sin', s(ph)]])
                elif kind == 'rock':
                    tick.append(advance(ph, TAU * (.45, .6, .8)[level], TAU))
                    channel('rotate_' + axis, target, ['mul', (4, 8, 14)[level], ['sin', s(ph)]])
                else:
                    tick.append(advance(ph, math.pi / .6, math.pi))
                    channel('offset_y', target, ['mul', (.12, .24, .4)[level] * .7, ['sin', s(ph)]])
            else:
                t = key('t')
                duration = {'spin': (1.5, 1.0, .6)[level], 'sway': 2.4, 'bounce': .84, 'rock': 4.0}[kind]
                state[t] = idle[t] = duration
                # A new trigger waits for the running one to finish, so nothing jumps.
                fire = [['if', ['lt', s(t), duration], [], [['store', t, 0]]]]
                tick.append(timer(t, duration))
                u = ['div', s(t), duration]
                if kind == 'spin':
                    channel('rotate_y', target, ['mul', smooth(u), 360 * direction])
                elif kind == 'sway':
                    channel('rotate_z', target, ['mul', ['mul', (6, 12, 20)[level], ['sin', ['mul', s(t), TAU * 1.6]]], ['sub', 1, u]])
                elif kind == 'rock':
                    # A push: rocks a few times and settles.
                    fade = ['sub', 1, u]
                    swing = ['sin', ['mul', s(t), TAU * (.5, .6, .75)[level]]]
                    channel('rotate_' + axis, target, ['mul', ['mul', (5, 9, 14)[level], swing], ['mul', fade, fade]])
                else:
                    hop = ['abs', ['sin', ['mul', s(t), math.pi / .42]]]
                    channel('offset_y', target, ['mul', ['mul', (.12, .24, .4)[level], hop], ['sub', 1, ['mul', .45, u]]])
            if fire:
                events[trigger].extend(fire)
        else:
            on, g = key('on'), key('g')
            state[on] = state[g] = float(trigger in ('always', 'leave'))
            idle[g] = on
            if trigger == 'click':
                events['click'].append(['store', on, ['not', s(on)]])
            elif trigger in ('near', 'leave'):
                events['near'].append(['store', on, float(trigger == 'near')])
                events['leave'].append(['store', on, float(trigger == 'leave')])
            if kind == 'glow':
                tick.append(approach(g, s(on), 6))
                channel('emission', target, ['mul', s(g), (1.0, 2.0, 3.2)[level]])
            elif kind == 'pulse':
                ph = key('p')
                state[ph] = 0
                tick.extend([approach(g, s(on), 3), advance(ph, TAU * .55, TAU)])
                channel('emission', target, ['mul', ['mul', s(g), (.8, 1.6, 2.6)[level]], ['add', .55, ['mul', .45, ['sin', s(ph)]]]])
            elif kind in ('turn', 'rotor'):
                # turn: a slow turntable; rotor: blades, sails or a wheel about the part's own axis.
                a = key('p')
                state[a] = 0
                speed = ((15, 30, 60) if kind == 'turn' else (90, 200, 420))[level] * direction
                tick.extend([approach(g, s(on), 1.5 if kind == 'turn' else 1.1),
                             ['store', a, ['mod', ['add', s(a), ['mul', ['mul', DT, speed], s(g)]], 360]]])
                channel('rotate_y' if kind == 'turn' else 'rotate_' + axis, target, s(a))
            elif kind == 'flicker':
                # A flame: an uneven glow of three waves, fading in and out.
                tick.append(approach(g, s(on), 4))
                waves = [.78]
                for i, (hz, depth) in enumerate(((1.3, .12), (3.1, .07), (7.3, .05))):
                    ph = key('p%d' % i)
                    state[ph] = i * 1.7
                    tick.append(advance(ph, TAU * hz, TAU))
                    waves.append(['mul', depth, ['sin', s(ph)]])
                channel('emission', target, ['mul', ['mul', s(g), (1.2, 2.0, 3.0)[level]], total(waves)])
            elif kind == 'slide':
                tick.append(approach(g, s(on), (2.5, 5, 9)[level]))
                channel('offset_' + axis, target, ['mul', s(g), (p.get('angle', 30) or 30) / 100])
            else:
                tick.append(approach(g, s(on), (2.5, 5, 9)[level]))
                channel('rotate_' + axis, target, ['mul', s(g), p.get('angle', 90)])
    for (op, target), values in channels.items():
        value = total(values)
        if op == 'rotate_y':
            value = ['mod', value, 360]
        elif op in ('rotate_x', 'rotate_z'):
            value = ['sub', ['mod', ['add', value, 180], 360], 180]
        elif op.startswith('offset_'):
            value = ['clamp', value, -2, 2]
        else:
            value = ['clamp', value, 0, 4]
        events['tick'].append(['emit', op, target, value])
    for target, a, c in hues:
        events['tick'].append(['if', ['gt', s(a), 0], [['emit', 'hue', target, ['mod', s(c), 1]]], []])
    program = {'version': 1, 'state': state, 'functions': {}, 'events': {}}
    if base:
        program['state'] = {**base['state'], **state}
        program['functions'] = copy.deepcopy(base['functions'])
    for event in ('spawn', 'click', 'near', 'leave', 'tick'):
        mine = events[event]
        theirs = copy.deepcopy(base['events'].get(event, [])) if base else []
        if theirs and len(theirs) + len(mine) > 128:
            theirs = [['if', 1, theirs, []]]
        if theirs or mine:
            program['events'][event] = theirs + mine
    return program, idle


def check(program, parts, extended=True):
    """The gates of designed programs. Raises InteractionError with a public code."""
    targets = targets_of(parts)
    try:
        validate_program(program, set(targets))
        (exercise_extended if extended else exercise)(program, targets)
    except ProgramError as error:
        raise InteractionError('interaction_too_complex' if str(error) in ('program_complexity', 'program_too_large') else 'interaction_rejected') from None
    return program


def compile_choice(choice, manifest, current=None, extended=True):
    """(program or None for the crafted one, idle, text) for a Choice on this object."""
    parts, original = manifest['plan']['parts'], manifest['program']
    if choice.mode == 'presets':
        moving = bool(original['events'])
        program, idle = build(choice.presets, parts, original if choice.keep and moving else None)
        return check(program, parts, extended), idle, ''
    if choice.mode == 'custom':
        draft = json.loads(current['draft']) if current is not None and current['draft'] else None
        if draft:
            return check(draft['program'], parts, extended), draft.get('idle', {}), draft['text']
        spec = json.loads(current['spec']) if current is not None else {}
        compiled = json.loads(current['compiled']) if current is not None and current['compiled'] else None
        if spec.get('mode') == 'custom' and compiled:
            return compiled['program'], compiled['idle'], spec.get('text', '')
        raise InteractionError('no_custom_design')
    return None, {}, ''


def strip_whole(body):
    out = []
    for statement in body:
        if statement[0] == 'emit' and statement[2] == WHOLE:
            out.append(['do', statement[3]])
        elif statement[0] == 'if':
            out.append(['if', statement[1], strip_whole(statement[2]), strip_whole(statement[3])])
        elif statement[0] == 'repeat':
            out.append(['repeat', statement[1], statement[2], strip_whole(statement[3])])
        else:
            out.append(statement)
    return out


def compat(value):
    """The program released clients run: emits to the virtual 'whole' target become plain
    expressions (same state, nothing they cannot show)."""
    program = value['program']
    if 'interaction' not in value or WHOLE in [p['id'] for p in value['plan']['parts']]:
        return program
    return {**program, 'events': {k: strip_whole(v) for k, v in program['events'].items()},
            'functions': {k: {**f, 'body': strip_whole(f['body'])} for k, f in program['functions'].items()}}


def targets(value):
    return targets_of(value['plan']['parts'])


def settle(value, state):
    """State to store after an event: one-shot timers finished, fades at their goal."""
    for key, goal in value.get('interaction', {}).get('idle', {}).items():
        if key in state:
            state[key] = state[goal] if isinstance(goal, str) else goal
    return state


def apply(conn, object_id, value):
    """The object's effective runtime, in place: value['program'] becomes the player's
    interaction program and value['interaction'] its public description (with the full
    program for new clients). Objects without an interaction are returned unchanged."""
    row = conn.execute('SELECT spec,compiled,version FROM object_interactions WHERE object_id=?', (object_id,)).fetchone()
    if not row:
        return value
    spec = json.loads(row['spec'])
    compiled = json.loads(row['compiled']) if row['compiled'] else None
    if not compiled and not spec.get('rest'):
        return value
    if compiled:
        value['program'] = compiled['program']
    value['interaction'] = {'mode': spec.get('mode', 'original'), 'rest': spec.get('rest', ''), 'version': row['version'],
                            'idle': compiled['idle'] if compiled else {}, 'program': value['program']}
    return value


def downgrade(value):
    if isinstance(value, dict):
        if set(value) == {'version', 'state', 'functions', 'events'}:
            return legacy(value)
        return {k: downgrade(v) for k, v in value.items()}
    if isinstance(value, list):
        return [downgrade(v) for v in value]
    return value


def for_client(request, value):
    """A reply for this game. Games that do not run the living-objects VM (no X-Villagen-VM: 2;
    released games up to 0.11.3) get every program in it reduced to what they can run
    (asset_vm.legacy): the same state, new operations as plain expressions, clocks on the time
    since the object loaded."""
    try:
        level = int(request.headers.get(VM_HEADER, '1'))
    except ValueError:
        level = 1
    return value if level >= 2 else downgrade(value)


def attach(conn, object_id, assigned, now):
    """A new object's starting interaction (server/archetypes.py assign), as if its owner saved it."""
    conn.execute('INSERT INTO object_interactions(object_id,spec,compiled,draft,version,updated) VALUES (?,?,?,NULL,1,?) '
                 'ON CONFLICT(object_id) DO NOTHING',
                 (object_id, json.dumps(assigned['spec']), json.dumps(assigned['compiled']) if assigned['compiled'] else None, now))


def put_draft(conn, object_id, design_id, text, program, idle, now):
    """A described behaviour waiting in the editor (미리보기 / 저장)."""
    draft = json.dumps({'id': design_id, 'text': text, 'program': program, 'idle': idle})
    conn.execute("INSERT INTO object_interactions(object_id,spec,compiled,draft,version,updated) VALUES (?,?,NULL,?,0,?) "
                 "ON CONFLICT(object_id) DO UPDATE SET draft=excluded.draft,updated=excluded.updated",
                 (object_id, json.dumps({'mode': 'original', 'presets': [], 'keep': True, 'rest': ''}), draft, now))


def describe_key(text, parts):
    return library.make_key('describe', library.normalize(text), library.signature(parts))


def summary(program):
    """What a program reacts to and moves, for the editor's icons."""
    ops = set()

    def walk(body):
        for statement in body:
            if statement[0] == 'emit':
                ops.add(statement[1])
            elif statement[0] == 'if':
                walk(statement[2]); walk(statement[3])
            elif statement[0] == 'repeat':
                walk(statement[3])
    for body in program['events'].values():
        walk(body)
    for function in program['functions'].values():
        walk(function['body'])
    return {'events': sorted(e for e in program['events'] if e in EVENTS), 'ops': sorted(ops)}


# ---------------------------------------------------------------- fixture designer

WORDS = [
    ('hinge', ('열', '닫', '뚜껑', 'open', 'close', 'lid', 'door')),
    ('slide', ('서랍', '밀어', '당겨', '미끄러', 'slide', 'drawer', 'pull out')),
    ('clock', ('시계', '시각', '현재 시간', 'clock', 'tell the time', 'real time')),
    ('tick', ('째깍', '똑딱', 'tick')),
    ('rotor', ('프로펠러', '바람개비', '풍차', '날개', 'propeller', 'windmill', 'blade', 'rotor')),
    ('turn', ('천천히 돌', '계속 돌', '빙빙', 'slowly', 'keep turning', 'keep spinning')),
    ('spin', ('돌', '회전', 'spin', 'turn', 'rotate', 'twirl')),
    ('rock', ('흔들의자', '앞뒤로', '흔들거', 'rocking', 'rock back')),
    ('sway', ('흔들', 'sway', 'wobble', 'rock', 'shake')),
    ('bounce', ('튀', '점프', '뛰', '통통', 'bounce', 'jump', 'hop')),
    ('flicker', ('촛불', '일렁', '아른', 'flicker', 'candle', 'flame')),
    ('pulse', ('은은', '반짝', '깜빡', 'pulse', 'twinkle', 'shimmer', 'breathe')),
    ('glow', ('빛', '불', '켜', '밝', 'light', 'glow', 'lamp', 'shine')),
    ('hue', ('색', '무지개', 'color', 'colour', 'rainbow')),
]
# A kind that says the same thing more precisely replaces the plainer one.
PRECISE = {'spin': ('turn', 'rotor'), 'sway': ('rock',), 'pulse': ('flicker',), 'glow': ('flicker',)}
HANDS = (('hour', 'hour'), ('minute', 'minute'), ('second', 'second'))
ROTOR_WORDS = ('blade', 'sail', 'rotor', 'propeller', 'wheel', 'fan')
TRIGGER_WORDS = [
    ('near', ('다가', '가까이', '근처', 'near', 'approach')),
    ('leave', ('멀어', '떠나', 'leave', 'away')),
    ('always', ('항상', '계속', '언제나', '늘', 'always', 'forever')),
    ('click', ('클릭', '누르', '눌', '만지', 'click', 'press', 'tap', 'touch')),
]


def fixture_presets(text, parts):
    """Offline stand-in for the designer (development/QA): words -> presets. Not an LLM."""
    low = text.lower()
    trigger = next((t for t, words in TRIGGER_WORDS if any(w in low for w in words)), '')
    level = 3 if any(w in low for w in ('세게', '크게', '빠르게', '많이', 'strong', 'fast', 'big')) else \
        1 if any(w in low for w in ('살짝', '약하게', '조금', '천천히', 'gentle', 'slow', 'soft')) else 2
    children = [p['id'] for p in parts if p['parent']] or [p['id'] for p in parts[1:]]
    presets = []
    for kind, words in WORDS:
        if not any(w in low for w in words) or len(presets) >= MAX_PRESETS:
            continue
        if any(p['kind'] in PRECISE.get(kind, ()) for p in presets):
            continue
        if kind in PART_KINDS and not children:
            continue
        when = trigger or ('always' if kind in ('turn', 'pulse', 'rotor', 'tick', 'flicker') else 'click')
        if kind == 'hue' and any(w in low for w in ('무지개', 'rainbow')):
            when = 'always'
        base = {'kind': kind, 'trigger': when, 'target': WHOLE, 'level': level, 'direction': 1, 'axis': 'x', 'angle': -100}
        if kind == 'clock':
            hands = [(p['id'], hand) for p in parts for word, hand in HANDS if word in p['id'].lower()]
            presets.extend({**base, 'trigger': 'always', 'target': part, 'axis': 'z', 'hand': hand} for part, hand in hands)
            del presets[MAX_PRESETS:]
            continue
        if kind == 'hinge':
            base['target'] = children[0]
        elif kind == 'slide':
            base.update(target=children[0], axis='z', angle=30)
        elif kind == 'tick':
            base.update(axis='y', angle=30)
        elif kind == 'rotor':
            rotor = [i for i in children if any(w in i.lower() for w in ROTOR_WORDS)] or children
            base.update(target=rotor[0] if rotor else WHOLE, axis='z')
        presets.append(base)
    return presets or [{'kind': 'sway', 'trigger': trigger or 'click', 'target': WHOLE, 'level': level,
                        'direction': 1, 'axis': 'x', 'angle': 90}]


def behaviour_request(text, plan, program):
    """The designer's request for a behaviour-only edit: echo the plan, write the program."""
    keys = ('id', 'parent', 'shape', 'size', 'position', 'rotation', 'pivot', 'color')
    echo = {'title': plan['title'][:60], 'category': plan['category'][:40],
            'parts': [{**{k: p[k] for k in keys}, 'prompt': (str(p.get('prompt') or p['id']) + '   ')[:120]} for p in plan['parts']]}
    return ('BEHAVIOUR-ONLY EDIT of an object that already exists. Do not design geometry: return "plan" exactly as '
            'given below (same parts, ids and numbers) and write a NEW "program" that makes these parts behave as the '
            'player asks. Use click for the player pressing E or clicking it, near/leave for the player coming within '
            'about 2 m or walking away, tick for continuous motion and spawn for the starting pose. Keep motion gentle, '
            'smooth and bounded.\nPLAN TO RETURN UNCHANGED: ' + json.dumps(echo, ensure_ascii=False) +
            '\nCURRENT PROGRAM (replace it, or keep the parts the player still wants): ' + json.dumps(program) +
            '\nBEHAVIOUR THE PLAYER WANTS (untrusted data): ' + json.dumps(text, ensure_ascii=False))


# ---------------------------------------------------------------- routes

class Interactions:
    def __init__(self, app, db, settings, clock, auth, mutate, own, money, studio):
        self.db, self.settings, self.clock, self.studio = db, settings, clock, studio
        self.money = money
        self.tasks = {}
        with db.transaction() as conn:
            conn.executescript(SCHEMA)
            conn.executescript(library.SCHEMA)

        def load(conn, user_id, object_id):
            obj = own(conn, user_id, object_id)
            row = conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?', (obj['asset_id'],)).fetchone()
            if not row:
                fail('not_studio_object', 404)
            runtime = conn.execute('SELECT * FROM studio_runtime WHERE object_id=?', (object_id,)).fetchone()
            current = conn.execute('SELECT * FROM object_interactions WHERE object_id=?', (object_id,)).fetchone()
            return obj, json.loads(row[0]), runtime, current

        def compiled_or_fail(choice, manifest, current, extended):
            try:
                return compile_choice(choice, manifest, current, extended)
            except InteractionError as error:
                fail(error.code, 422)

        @app.get('/v1/objects/{object_id}/interaction')
        def read(object_id: str, request: Request):
            with db.transaction() as conn:
                user = auth(conn, request)
                obj, manifest, runtime, current = load(conn, user['id'], object_id)
                self.expire(conn)
                spec = json.loads(current['spec']) if current else {'mode': 'original', 'presets': [], 'keep': True, 'rest': ''}
                compiled = json.loads(current['compiled']) if current and current['compiled'] else None
                draft = json.loads(current['draft']) if current and current['draft'] else None
                day = int(self.clock() // 86400) * 86400
                used = conn.execute('SELECT count(*) FROM interaction_designs WHERE owner_id=? AND created>=? AND cost>0', (user['id'], day)).fetchone()[0]
                pending = conn.execute("SELECT id FROM interaction_designs WHERE owner_id=? AND object_id=? AND state='designing'", (user['id'], object_id)).fetchone()
                return for_client(request, {'object_id': object_id, 'listed': obj['state'] == 'listed', 'runtime_version': runtime['version'],
                        'parts': [{'id': p['id'], 'parent': p['parent']} for p in manifest['plan']['parts']],
                        'spec': {**spec, 'version': current['version'] if current else 0},
                        'program': compiled['program'] if compiled else manifest['program'],
                        'original_program': manifest['program'], 'moving': bool(manifest['program']['events']),
                        'draft': {'text': draft['text'], 'program': draft['program'], 'summary': summary(draft['program'])} if draft else None,
                        'describe': {'cost': DESCRIBE_COST, 'limit': DESCRIBE_DAILY_LIMIT, 'left': max(0, DESCRIBE_DAILY_LIMIT - used),
                                     'pending': pending['id'] if pending else None, 'text_limit': TEXT_LIMIT,
                                     'designer': 'fixture' if settings.studio_llm == 'fixture' else 'llm'},
                        'kinds': list(KINDS), 'triggers': list(TRIGGERS), 'max_presets': MAX_PRESETS, 'shards': user['shards']})

        # A private rehearsal: compiles and checks, persists nothing (the 미리보기 button).
        @app.post('/v1/objects/{object_id}/interaction/preview')
        def preview(object_id: str, body: Choice, request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                _, manifest, _, current = load(conn, user['id'], object_id)
                program, idle, _ = compiled_or_fail(body, manifest, current, False)
                return for_client(request, {'program': program if program is not None else manifest['program'], 'idle': idle, 'rest': body.rest})

        @app.post('/v1/objects/{object_id}/interaction')
        def save(object_id: str, body: SaveInteraction, request: Request):
            def edit(conn, user):
                obj, manifest, runtime, current = load(conn, user['id'], object_id)
                if obj['state'] == 'listed':
                    fail('object_is_listed')
                if body.version != runtime['version']:
                    fail('stale_runtime_version')
                program, idle, text = compiled_or_fail(body, manifest, current, True)
                spec = {'mode': body.mode, 'presets': [p.model_dump() for p in body.presets] if body.mode == 'presets' else [],
                        'keep': body.keep, 'rest': body.rest, 'text': text}
                compiled = json.dumps({'program': program, 'idle': idle}) if program is not None else None
                version = (current['version'] if current else 0) + 1
                conn.execute('INSERT INTO object_interactions(object_id,spec,compiled,draft,version,updated) VALUES (?,?,?,NULL,?,?) '
                             'ON CONFLICT(object_id) DO UPDATE SET spec=excluded.spec,compiled=excluded.compiled,version=excluded.version,updated=excluded.updated',
                             (object_id, json.dumps(spec), compiled, version, self.clock()))
                # The new program starts from its own state; the crafted program's keys keep their values.
                effective = program if program is not None else manifest['program']
                vm = AssetVM(effective, targets_of(manifest['plan']['parts']))
                vm.run('spawn')
                old = json.loads(runtime['state'])
                for key in manifest['program']['state']:
                    if key in vm.state and key in old:
                        vm.state[key] = old[key]
                conn.execute('UPDATE studio_runtime SET state=?,version=version+1 WHERE object_id=?', (json.dumps(vm.state), object_id))
                value = apply(conn, object_id, {'plan': manifest['plan'], 'program': manifest['program']})
                return {'spec': {**spec, 'version': version}, 'interaction': value.get('interaction'), 'program': effective,
                        'runtime': {'state': vm.state, 'version': runtime['version'] + 1}}
            return for_client(request, mutate(request, body, 'interaction:' + object_id, edit))

        @app.post('/v1/objects/{object_id}/interaction/describe')
        async def describe(object_id: str, body: Describe, request: Request):
            started = {}

            def reserve(conn, user):
                obj, manifest, _, _ = load(conn, user['id'], object_id)
                if obj['state'] == 'listed':
                    fail('object_is_listed')
                self.expire(conn)
                text = ' '.join(body.text.split())
                # Said before about an object with the same parts: the learned behaviour, free.
                learned = self.learned(conn, text, manifest['plan']['parts'])
                if learned:
                    design_id, now = str(uuid.uuid4()), self.clock()
                    program, idle = learned['value']['program'], learned['value'].get('idle', {})
                    conn.execute('INSERT INTO interaction_designs(id,owner_id,object_id,text,state,cost,program,provenance,created,updated) '
                                 'VALUES (?,?,?,?,?,?,?,?,?,?)',
                                 (design_id, user['id'], object_id, text, 'ready', 0, json.dumps(program),
                                  json.dumps({'provider': 'library', 'entry': learned['key'], 'made_by': learned['provider']}), now, now))
                    put_draft(conn, object_id, design_id, text, program, idle, now)
                    library.used(conn, learned['key'], now)
                    return {'design_id': design_id, 'state': 'ready', 'cost': 0}
                if conn.execute("SELECT 1 FROM interaction_designs WHERE owner_id=? AND state='designing'", (user['id'],)).fetchone():
                    fail('design_pending')
                day = int(self.clock() // 86400) * 86400
                if conn.execute('SELECT count(*) FROM interaction_designs WHERE owner_id=? AND created>=? AND cost>0', (user['id'], day)).fetchone()[0] >= DESCRIBE_DAILY_LIMIT:
                    fail('interaction_daily_limit', 429)
                design_id = str(uuid.uuid4())
                money(conn, user['id'], -DESCRIBE_COST, 'interaction_charge', design_id)
                conn.execute('INSERT INTO interaction_designs(id,owner_id,object_id,text,state,cost,created,updated) VALUES (?,?,?,?,?,?,?,?)',
                             (design_id, user['id'], object_id, text, 'designing', DESCRIBE_COST, self.clock(), self.clock()))
                started['id'] = design_id
                return {'design_id': design_id, 'state': 'designing', 'cost': DESCRIBE_COST}
            reply = mutate(request, body, 'interaction_describe:' + object_id, reserve)
            design_id = reply['design_id']
            if started:
                self.tasks[design_id] = asyncio.ensure_future(self.design(design_id))
            task = self.tasks.get(design_id)
            if task:
                await asyncio.shield(task)
            return for_client(request, self.view(design_id))

    def learned(self, conn, text, parts):
        """The learned library's behaviour for this sentence on these parts, re-checked, or None."""
        entry = library.find(conn, describe_key(text, parts))
        if not entry:
            return None
        try:
            check(entry['value']['program'], parts)
        except InteractionError:
            return None
        return entry

    def expire(self, conn):
        for row in conn.execute("SELECT id FROM interaction_designs WHERE state='designing' AND created<?", (self.clock() - DESIGN_TIMEOUT,)).fetchall():
            if row['id'] not in self.tasks:
                self.give_up(conn, row['id'], 'design_interrupted')

    def give_up(self, conn, design_id, code, provenance=None):
        row = conn.execute('SELECT * FROM interaction_designs WHERE id=?', (design_id,)).fetchone()
        if not row or row['state'] != 'designing':
            return
        conn.execute("UPDATE interaction_designs SET state='failed',error=?,provenance=?,updated=? WHERE id=?",
                     (code, json.dumps(provenance or {}), self.clock(), design_id))
        self.money(conn, row['owner_id'], row['cost'], 'interaction_refund', design_id)

    def view(self, design_id):
        with self.db.read() as conn:
            row = conn.execute('SELECT * FROM interaction_designs WHERE id=?', (design_id,)).fetchone()
            shards = conn.execute('SELECT shards FROM users WHERE id=?', (row['owner_id'],)).fetchone()[0]
        value = {'design_id': design_id, 'state': row['state'], 'cost': row['cost'], 'text': row['text'], 'shards': shards}
        if row['state'] == 'ready':
            program = json.loads(row['program'])
            value.update(program=program, summary=summary(program))
        elif row['state'] == 'failed':
            value.update(error=row['error'])
        return value

    async def design(self, design_id):
        provenance = {}
        try:
            with self.db.read() as conn:
                row = conn.execute('SELECT * FROM interaction_designs WHERE id=?', (design_id,)).fetchone()
                obj = conn.execute('SELECT asset_id FROM objects WHERE id=?', (row['object_id'],)).fetchone()
                manifest = json.loads(conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?', (obj['asset_id'],)).fetchone()[0])
            plan, original = manifest['plan'], manifest['program']
            parts = plan['parts']
            if self.settings.studio_llm == 'fixture':
                presets = fixture_presets(row['text'], parts)
                program, idle = build(presets, parts, original if original['events'] else None)
                provenance = {'provider': 'authored_fixture', 'presets': presets}
            else:
                # The studio's designer and its validation/repair loop; the plan comes back unchanged.
                live = self.settings.mode == 'live'
                result_plan, program, provenance = await llm_budget.generate(
                    self.db, self.settings, self.clock, row['owner_id'], 'interaction_describe', design_id, self.studio.designer,
                    behaviour_request(row['text'], plan, original), 'gpt-6-luna', 'high', None, None)
                if [p['id'] for p in result_plan['parts']] != [p['id'] for p in parts]:
                    raise InteractionError('design_changed_parts')
                idle = {}
                provenance = {k: provenance.get(k) for k in ('provider', 'model', 'effort', 'usage', 'attempts', 'usage_complete', 'fallback_used') if k in provenance} | {'live': live}
            check(program, parts)
            with self.db.transaction() as conn:
                current = conn.execute('SELECT owner_id,state FROM objects WHERE id=?', (row['object_id'],)).fetchone()
                if current['owner_id'] != row['owner_id'] or current['state'] in ('listed', 'gifted'):
                    self.give_up(conn, design_id, 'object_unavailable', provenance)
                    return
                still = conn.execute('SELECT state FROM interaction_designs WHERE id=?', (design_id,)).fetchone()
                if still['state'] != 'designing':
                    return
                conn.execute("UPDATE interaction_designs SET state='ready',program=?,provenance=?,updated=? WHERE id=?",
                             (json.dumps(program), json.dumps(provenance), self.clock(), design_id))
                put_draft(conn, row['object_id'], design_id, row['text'], program, idle, self.clock())
                # What the designer made is kept: the next player saying this about the same parts gets it free.
                if self.settings.studio_llm != 'fixture':
                    library.remember(conn, describe_key(row['text'], parts), 'describe', library.normalize(row['text']),
                                     library.signature(parts), {'program': program, 'idle': idle}, self.clock(),
                                     provider=str(provenance.get('provider') or ''), origin=design_id, category=plan.get('category', ''))
        except asyncio.CancelledError:
            with self.db.transaction() as conn:
                self.give_up(conn, design_id, 'design_interrupted', provenance)
            raise
        except Exception as error:
            code = error.code if isinstance(error, (ProviderError, InteractionError)) else 'design_rejected'
            if hasattr(error, 'usage'):
                provenance = {'usage': error.usage}
                if hasattr(error, 'attempts'):
                    provenance.update(attempts=error.attempts, usage_complete=error.usage_complete)
                    if error.attempts:
                        provenance.update({k: error.attempts[-1][k] for k in ('provider', 'model') if k in error.attempts[-1]})
            with self.db.transaction() as conn:
                self.give_up(conn, design_id, code, provenance)
        finally:
            self.tasks.pop(design_id, None)
