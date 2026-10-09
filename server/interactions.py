"""Player-made interactions for crafted objects (the game's 상호작용 editor).

An owner gives a crafted object new behaviour without a new craft: ready-made presets
(spin, sway, bounce, glow, pulse, colour, slow turn, open/close a part), each with a
trigger (click/E, near, leave, always) and a level, or a sentence the studio's designer
turns into a program for the object's existing parts (no Tripo call; the fixture designer
in development). Either way the result is an ordinary VM program that passes the gates of
designed programs (validate_program, exercise_extended). It is kept per object in
object_interactions and replaces the crafted program on every runtime path: the owner's
assembly, event and invoke routes and the visitors' assembly route (apply() below).
'Rest' (sit/lie) is a flag the room's rest system reads; it needs no program.

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
from .asset_vm import AssetVM, ProgramError, validate_program, exercise, exercise_extended, NAME, EVENTS
from .provider import ProviderError

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
KINDS = ('spin', 'sway', 'bounce', 'glow', 'pulse', 'hue', 'turn', 'hinge')
TRIGGERS = ('click', 'near', 'leave', 'always')
# One-shot motions play once per trigger ('always' loops them); toggles switch on and off.
ACTIONS = ('spin', 'sway', 'bounce', 'hue')
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
    angle: int = Field(default=90, ge=-180, le=180)


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
        if kind == 'hinge' and target not in ids:
            raise InteractionError('hinge_needs_part')
        if (kind, target) in seen:
            raise InteractionError('duplicate_preset')
        seen.add((kind, target))

        def key(name):
            return f'{prefix}{n}_{name}'
        tick = events['tick']
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
                else:
                    tick.append(advance(ph, math.pi / .6, math.pi))
                    channel('offset_y', target, ['mul', (.12, .24, .4)[level] * .7, ['sin', s(ph)]])
            else:
                t = key('t')
                duration = {'spin': (1.5, 1.0, .6)[level], 'sway': 2.4, 'bounce': .84}[kind]
                state[t] = idle[t] = duration
                # A new trigger waits for the running one to finish, so nothing jumps.
                fire = [['if', ['lt', s(t), duration], [], [['store', t, 0]]]]
                tick.append(timer(t, duration))
                u = ['div', s(t), duration]
                if kind == 'spin':
                    channel('rotate_y', target, ['mul', smooth(u), 360 * direction])
                elif kind == 'sway':
                    channel('rotate_z', target, ['mul', ['mul', (6, 12, 20)[level], ['sin', ['mul', s(t), TAU * 1.6]]], ['sub', 1, u]])
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
            elif kind == 'turn':
                a = key('p')
                state[a] = 0
                speed = (15, 30, 60)[level] * direction
                tick.extend([approach(g, s(on), 1.5), ['store', a, ['mod', ['add', s(a), ['mul', ['mul', DT, speed], s(g)]], 360]]])
                channel('rotate_y', target, s(a))
            else:
                tick.append(approach(g, s(on), (2.5, 5, 9)[level]))
                channel('rotate_' + p.get('axis', 'x'), target, ['mul', s(g), p.get('angle', 90)])
    for (op, target), values in channels.items():
        value = total(values)
        if op == 'rotate_y':
            value = ['mod', value, 360]
        elif op in ('rotate_x', 'rotate_z'):
            value = ['sub', ['mod', ['add', value, 180], 360], 180]
        elif op == 'offset_y':
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
    ('turn', ('천천히 돌', '계속 돌', '빙빙', 'slowly', 'keep turning', 'keep spinning')),
    ('spin', ('돌', '회전', 'spin', 'turn', 'rotate', 'twirl')),
    ('sway', ('흔들', 'sway', 'wobble', 'rock', 'shake')),
    ('bounce', ('튀', '점프', '뛰', '통통', 'bounce', 'jump', 'hop')),
    ('pulse', ('은은', '반짝', '깜빡', 'pulse', 'twinkle', 'shimmer', 'breathe')),
    ('glow', ('빛', '불', '켜', '밝', 'light', 'glow', 'lamp', 'shine')),
    ('hue', ('색', '무지개', 'color', 'colour', 'rainbow')),
]
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
        if kind == 'spin' and any(p['kind'] == 'turn' for p in presets):
            continue
        if kind == 'hinge' and not children:
            continue
        when = trigger or ('always' if kind in ('turn', 'pulse') else 'click')
        if kind == 'hue' and any(w in low for w in ('무지개', 'rainbow')):
            when = 'always'
        presets.append({'kind': kind, 'trigger': when, 'target': children[0] if kind == 'hinge' else WHOLE,
                        'level': level, 'direction': 1, 'axis': 'x', 'angle': -100})
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
                used = conn.execute('SELECT count(*) FROM interaction_designs WHERE owner_id=? AND created>=?', (user['id'], day)).fetchone()[0]
                pending = conn.execute("SELECT id FROM interaction_designs WHERE owner_id=? AND object_id=? AND state='designing'", (user['id'], object_id)).fetchone()
                return {'object_id': object_id, 'listed': obj['state'] == 'listed', 'runtime_version': runtime['version'],
                        'parts': [{'id': p['id'], 'parent': p['parent']} for p in manifest['plan']['parts']],
                        'spec': {**spec, 'version': current['version'] if current else 0},
                        'program': compiled['program'] if compiled else manifest['program'],
                        'original_program': manifest['program'], 'moving': bool(manifest['program']['events']),
                        'draft': {'text': draft['text'], 'program': draft['program'], 'summary': summary(draft['program'])} if draft else None,
                        'describe': {'cost': DESCRIBE_COST, 'limit': DESCRIBE_DAILY_LIMIT, 'left': max(0, DESCRIBE_DAILY_LIMIT - used),
                                     'pending': pending['id'] if pending else None, 'text_limit': TEXT_LIMIT,
                                     'designer': 'fixture' if settings.studio_llm == 'fixture' else 'llm'},
                        'kinds': list(KINDS), 'triggers': list(TRIGGERS), 'max_presets': MAX_PRESETS, 'shards': user['shards']}

        # A private rehearsal: compiles and checks, persists nothing (the 미리보기 button).
        @app.post('/v1/objects/{object_id}/interaction/preview')
        def preview(object_id: str, body: Choice, request: Request):
            with db.read() as conn:
                user = auth(conn, request)
                _, manifest, _, current = load(conn, user['id'], object_id)
                program, idle, _ = compiled_or_fail(body, manifest, current, False)
                return {'program': program if program is not None else manifest['program'], 'idle': idle, 'rest': body.rest}

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
            return mutate(request, body, 'interaction:' + object_id, edit)

        @app.post('/v1/objects/{object_id}/interaction/describe')
        async def describe(object_id: str, body: Describe, request: Request):
            started = {}

            def reserve(conn, user):
                obj, _, _, _ = load(conn, user['id'], object_id)
                if obj['state'] == 'listed':
                    fail('object_is_listed')
                self.expire(conn)
                if conn.execute("SELECT 1 FROM interaction_designs WHERE owner_id=? AND state='designing'", (user['id'],)).fetchone():
                    fail('design_pending')
                day = int(self.clock() // 86400) * 86400
                if conn.execute('SELECT count(*) FROM interaction_designs WHERE owner_id=? AND created>=?', (user['id'], day)).fetchone()[0] >= DESCRIBE_DAILY_LIMIT:
                    fail('interaction_daily_limit', 429)
                design_id = str(uuid.uuid4())
                money(conn, user['id'], -DESCRIBE_COST, 'interaction_charge', design_id)
                conn.execute('INSERT INTO interaction_designs(id,owner_id,object_id,text,state,cost,created,updated) VALUES (?,?,?,?,?,?,?,?)',
                             (design_id, user['id'], object_id, ' '.join(body.text.split()), 'designing', DESCRIBE_COST, self.clock(), self.clock()))
                started['id'] = design_id
                return {'design_id': design_id, 'state': 'designing', 'cost': DESCRIBE_COST}
            reply = mutate(request, body, 'interaction_describe:' + object_id, reserve)
            design_id = reply['design_id']
            if started:
                self.tasks[design_id] = asyncio.ensure_future(self.design(design_id))
            task = self.tasks.get(design_id)
            if task:
                await asyncio.shield(task)
            return self.view(design_id)

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
                result_plan, program, provenance = await self.studio.designer.generate(
                    behaviour_request(row['text'], plan, original), 'gpt-6-luna', 'high', None, None)
                if [p['id'] for p in result_plan['parts']] != [p['id'] for p in parts]:
                    raise InteractionError('design_changed_parts')
                idle = {}
                provenance = {k: provenance.get(k) for k in ('provider', 'model', 'effort', 'usage') if k in provenance} | {'live': live}
            check(program, parts)
            with self.db.transaction() as conn:
                current = conn.execute('SELECT owner_id,state FROM objects WHERE id=?', (row['object_id'],)).fetchone()
                if current['owner_id'] != row['owner_id'] or current['state'] == 'listed':
                    self.give_up(conn, design_id, 'object_unavailable', provenance)
                    return
                still = conn.execute('SELECT state FROM interaction_designs WHERE id=?', (design_id,)).fetchone()
                if still['state'] != 'designing':
                    return
                conn.execute("UPDATE interaction_designs SET state='ready',program=?,provenance=?,updated=? WHERE id=?",
                             (json.dumps(program), json.dumps(provenance), self.clock(), design_id))
                draft = json.dumps({'id': design_id, 'text': row['text'], 'program': program, 'idle': idle})
                conn.execute("INSERT INTO object_interactions(object_id,spec,compiled,draft,version,updated) VALUES (?,?,NULL,?,0,?) "
                             "ON CONFLICT(object_id) DO UPDATE SET draft=excluded.draft,updated=excluded.updated",
                             (row['object_id'], json.dumps({'mode': 'original', 'presets': [], 'keep': True, 'rest': ''}), draft, self.clock()))
        except asyncio.CancelledError:
            with self.db.transaction() as conn:
                self.give_up(conn, design_id, 'design_interrupted', provenance)
            raise
        except Exception as error:
            code = error.code if isinstance(error, (ProviderError, InteractionError)) else 'design_rejected'
            if getattr(error, 'usage', None):
                provenance = {'usage': error.usage}
            with self.db.transaction() as conn:
                self.give_up(conn, design_id, code, provenance)
        finally:
            self.tasks.pop(design_id, None)
