"""Craft-time life for crafted objects (the archetype library, server/archetype_library.py).

At planning the request is classified into a library type (classify) and the LLM designer is
told the type's part roles (designer_hint), so a clock comes back as a body with a blank dial and
separate hands pivoting at the dial centre. Role parts such as clock hands are made by the game
itself (primitive_parts, server/clock_hands.py: no Tripo credits), seated just in front of the
dial (seat_parts); a clock is always built with its hands (always_moving). When the craft becomes an object it
starts with the type's behaviours as an ordinary interaction (assign): presets the owner sees and
edits in the interaction editor, '원래대로' still goes back to the crafted motion. A one-piece craft
(static, or the credit-cap fallback) gets the type's whole-object behaviours instead.
"""
import re
import unicodedata
from .archetype_library import ARCHETYPES, VERSION
from .asset_assembly import validate_plan
from . import interactions
from . import clock_hands

BY_ID = {a['id']: a for a in ARCHETYPES}
# Korean particles dropped from the end of a word before matching ('시계를' -> '시계').
PARTICLES = ('으로', '에서', '에게', '처럼', '같은', '모양', '을', '를', '이', '가', '은', '는', '와', '과', '의', '에', '로', '도', '만')
# In English the head noun comes before these ("a clock with a lamp" is a clock).
CUT = re.compile(r'\b(with|for|of|on|in|that|which|featuring|shaped|like|under|over|near|beside|having)\b')
EMPTY = {'version': 1, 'state': {}, 'functions': {}, 'events': {}}


def text_of(value):
    value = unicodedata.normalize('NFKC', str(value or '')).casefold().replace('_', ' ')
    return ' '.join(re.sub(r'[^\w]+', ' ', value).split())


def hangul(word):
    return any('가' <= ch <= '힣' for ch in word)


def stripped(token):
    for particle in PARTICLES:
        if token.endswith(particle) and len(token) > len(particle) + 1:
            return token[:-len(particle)]
    return token


def best_match(text):
    """The library type a phrase names, or None. Korean is head-final (the last noun names the
    object: '시계가 달린 램프' is a lamp); English names it before with/of/for...; a longer word
    beats a shorter one at the same place ('흔들의자' over '의자')."""
    cut = CUT.search(text)
    cut = cut.start() if cut else len(text)
    tokens = [(m.group(), m.start(), m.end()) for m in re.finditer(r'\S+', text)]
    best = None
    for arch in ARCHETYPES:
        for raw in arch['words']:
            word = text_of(raw)
            spans = []
            if hangul(word) and ' ' not in word:
                spans = [(start, end) for token, start, end in tokens if token.endswith(word) or stripped(token).endswith(word)]
            elif hangul(word):
                spans = [(m.start(), m.end()) for m in re.finditer(re.escape(word), text)]
            else:
                spans = [(m.start(), m.end()) for m in re.finditer(r'(?<!\w)' + re.escape(word) + r'(?:s|es)?(?!\w)', text)]
            for start, end in spans:
                score = (start < cut, end, len(word))
                if best is None or score > best[0]:
                    best = (score, arch)
    return best[1] if best else None


def classify(prompt='', plan=None):
    """The library type of a craft: from the player's words first, then the designer's category
    (it was asked to use the type id) and title. None when it is not a known type."""
    plan = plan or {}
    for value in (prompt, plan.get('category', ''), plan.get('title', '')):
        text = text_of(value)
        if not text:
            continue
        if text.replace(' ', '_') in BY_ID:
            return BY_ID[text.replace(' ', '_')]
        found = best_match(text)
        if found:
            return found
    return None


def designer_hint(prompt, motion):
    """The sentence the LLM designer gets for a known type: its category and part roles."""
    arch = classify(prompt)
    if not arch:
        return ''
    head = '\nOBJECT TYPE (from the game\'s library): %s. Set plan.category to "%s".' % (arch['names']['en'], arch['id'])
    if motion == 'static' or len(arch['roles']) < 2:
        return head
    roles = '; '.join('%s%s = %s' % (r['id'], ' (optional)' if r.get('optional') else '', r['hint']) for r in arch['roles'])
    return (head + ' Use exactly these part ids: ' + roles + '. ' + (arch.get('hint') or '') +
            ' The game animates these parts itself: return an empty program unless the player asks for more.')


def bind(arch, parts):
    """{role: part id} for the parts this design has: the role's own id, a part id containing one
    of the role's words, or for a root role the first part without a parent."""
    ids = [p['id'] for p in parts]
    taken, roles = set(), {}
    for role in arch['roles']:
        pick = role['id'] if role['id'] in ids else None
        if pick is None:
            words = [role['id']] + role.get('words', [])
            pick = next((i for i in ids if i not in taken and any(w in i.lower() for w in words)), None)
        if pick is None and role.get('root'):
            pick = next((p['id'] for p in parts if not p.get('parent') and p['id'] not in taken), None)
        if pick and pick not in taken:
            roles[role['id']] = pick
            taken.add(pick)
    return roles


def presets_for(arch, parts):
    """The type's presets on this object's parts, as full Preset dicts."""
    single = len(parts) == 1
    roles = bind(arch, parts)
    out, seen = [], set()
    for entry in (arch['single'] if single else arch['behaviours']):
        role = entry['role']
        target = 'whole' if role == 'whole' or single else roles.get(role)
        if target is None and entry.get('or_whole'):
            target = 'whole'
        if target is None or (entry['kind'], target) in seen:
            continue
        seen.add((entry['kind'], target))
        preset = {k: v for k, v in entry.items() if k not in ('role', 'or_whole')}
        out.append(interactions.Preset.model_validate({**preset, 'target': target}).model_dump())
    return out[:interactions.MAX_PRESETS], roles


def primitive_parts(arch_id, plan):
    """{part id: shape} for role parts the game makes itself (no Tripo credits): box-shaped parts
    with a parent, never every part."""
    arch = BY_ID.get(arch_id)
    if not arch or len(plan['parts']) < 2:
        return {}
    roles = bind(arch, plan['parts'])
    by_id = {p['id']: p for p in plan['parts']}
    out = {roles[r['id']]: r.get('make', 'minute') for r in arch['roles'] if r.get('primitive') and r['id'] in roles
           and by_id[roles[r['id']]]['shape'] == 'box' and by_id[roles[r['id']]]['parent']}
    return out if len(out) < len(plan['parts']) else {}


def least_meshes(arch, motion):
    """Tripo meshes a craft of this type needs at least: one when still, or when every moving role
    is a part the game makes (a clock: body only), else two (a body and a moving part)."""
    if motion != 'dynamic':
        return 1
    moving = {b['role'] for b in (arch or {}).get('behaviours', [])} - {'whole'}
    roles = {r['id']: r for r in (arch or {}).get('roles', [])}
    return 1 if moving and all(roles.get(m, {}).get('primitive') for m in moving) else 2


def craft_kind(prompt):
    """What the craft window needs before a request: the type, whether it is always built moving,
    and the Tripo meshes a moving craft of it needs."""
    arch = classify(prompt)
    if not arch:
        return {'archetype': None, 'names': {}, 'always_moving': False, 'moving_meshes': 2, 'rest': ''}
    return {'archetype': arch['id'], 'names': arch['names'], 'always_moving': bool(arch.get('always_moving')),
            'moving_meshes': least_meshes(arch, 'dynamic'), 'rest': arch.get('rest', '')}


# Hands and pendulum: the turning point the shapes are drawn around, back to front.
PIVOTS = {'pendulum': [0, .5, 0], 'hour': [0, -.4, 0], 'minute': [0, -.4, 0], 'second': [0, -.3, 0]}
LAYERS = ('pendulum', 'hour', 'minute', 'second')
# The longest a hand may be, as a share of the dial (the body's smaller face side).
REACH = {'hour': .34, 'minute': .5, 'second': .52}
GAP = .003


def seat_parts(arch_id, plan):
    """Puts the game's own parts where they look made: each hand turns at its hub, no longer than
    the dial allows, and they stand in layers just in front of the body's face (a few millimetres
    apart, so nothing flickers). Turning points (positions) stay where the designer put them."""
    makes = primitive_parts(arch_id, plan)
    if not makes:
        return plan
    by_id = {p['id']: p for p in plan['parts']}
    front = {}
    for part_id in sorted(makes, key=lambda i: LAYERS.index(makes[i]) if makes[i] in LAYERS else 9):
        part, make = by_id[part_id], makes[part_id]
        body = by_id.get(part['parent'])
        if not body or make not in PIVOTS:
            continue
        part['pivot'] = list(PIVOTS[make])
        dial = min(body['size'][0], body['size'][1])
        if make in REACH and part['size'][1] > dial * REACH[make]:
            part['size'][1] = round(max(.02, dial * REACH[make]), 4)
        # Flat: as thin as a part may be, and thinner than wide so the game never takes the face for
        # the edge.
        part['size'][2] = .02
        if part['size'][2] >= part['size'][0] * .8:
            part['size'][0] = round(min(3, part['size'][2] / .7), 4)
        depth = part['size'][2]
        face = front.get(body['id'], body['size'][2] * (.5 - body['pivot'][2]))
        part['position'][2] = round(min(3, face + GAP + depth / 2), 4)
        front[body['id']] = part['position'][2] + depth / 2
    return validate_plan(plan)


def assign(arch_id, plan, program, style=''):
    """The interaction a new object of this type starts with: {'spec', 'compiled', 'roles'} or None.
    A craft that already moves keeps its own motion unless the type overrides it (a clock must
    show real time); the type's rest (sit/lie) applies either way. Raises InteractionError when
    the presets do not pass the gates."""
    arch = BY_ID.get(arch_id)
    if not arch:
        return None
    parts = plan['parts']
    moving = bool(program['events'])
    chosen, roles = presets_for(arch, parts)
    if moving and not arch.get('override'):
        chosen = []
    # A style whose palette glows lights the type's accent part (a sci-fi clock's second hand).
    accent = roles.get(arch.get('accent', ''))
    if chosen and accent and clock_hands.palette(style).get('glow') and len(chosen) < interactions.MAX_PRESETS:
        chosen.append(interactions.Preset(kind='glow', trigger='always', target=accent, level=1).model_dump())
    rest = arch.get('rest', '')
    if not chosen and not rest:
        return None
    spec = {'mode': 'presets' if chosen else 'original', 'presets': chosen, 'keep': True, 'rest': rest, 'text': '',
            'archetype': arch['id']}
    compiled = None
    if chosen:
        built, idle = interactions.build(chosen, parts, program if moving else None)
        compiled = {'program': interactions.check(built, parts), 'idle': idle}
    return {'spec': spec, 'compiled': compiled, 'roles': roles}


def fixture_design(prompt):
    """The offline designer's plan for a library type that has one (development and tests)."""
    arch = classify(prompt)
    if not arch or 'fixture' not in arch:
        return None
    parts = [{'id': p['id'], 'parent': p.get('parent', ''), 'prompt': p.get('prompt') or 'A standalone ' + p['id'].replace('_', ' '),
              'shape': p['shape'], 'size': p['size'], 'position': p['position'], 'rotation': p.get('rotation', [0, 0, 0]),
              'pivot': p.get('pivot', [0, 0, 0]), 'color': p['color']} for p in arch['fixture']['parts']]
    plan = validate_plan({'title': arch['fixture']['title'] + ' · 오프라인 시연', 'category': arch['id'], 'parts': parts})
    return plan, {'version': 1, 'state': {}, 'functions': {}, 'events': {}}


def public():
    """The library for listings: id, names, roles, rest and what it does."""
    return {'version': VERSION, 'archetypes': [
        {'id': a['id'], 'names': a['names'], 'rest': a.get('rest', ''), 'roles': [r['id'] for r in a['roles']],
         'behaviours': [{k: v for k, v in b.items()} for b in a['behaviours']], 'single': a['single']} for a in ARCHETYPES]}
