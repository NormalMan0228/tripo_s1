"""The archetype library as a whole: every type is named by its own words (and only its own), its
offline fixture is made of its roles, and its behaviours compile into a program that runs and moves."""
import math
import re
from collections import defaultdict
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server import archetypes, interactions
from server.archetype_library import ARCHETYPES, FAMILIES, ROOMS, ROLE_NAMES
from server.asset_vm import AssetVM
from server.interactions import Preset, PART_KINDS, check

PANEL = Path(__file__).resolve().parents[2] / 'game' / 'scripts' / 'interaction_panel.gd'
EMPTY = {'version': 1, 'state': {}, 'functions': {}, 'events': {}}
# Single-syllable Korean words are easy to hit by accident; only these name a type.
SHORT = {'문', '등', '함', '꽃', '종', '솥'}
WITH_FIXTURE = [a for a in ARCHETYPES if 'fixture' in a]


def ids(arch):
    return arch['id']


def with_particles(word):
    """The word as players write it in a sentence: with particles and around other words."""
    if archetypes.hangul(word):
        out = ['예쁜 %s 만들어 줘' % word, '나무로 된 %s' % word]
        if len(word.replace(' ', '')) > 1:
            out += [word + p for p in ('를', '가', '로', '처럼', '에서')]
        return out
    return ['a pretty %s' % word, 'make me a wooden %s please' % word]


def test_the_library_is_large_and_every_type_has_a_family_and_a_room():
    assert len(ARCHETYPES) >= 100
    assert len({a['id'] for a in ARCHETYPES}) == len(ARCHETYPES)
    for key in ('ko', 'en'):
        names = [a['names'][key] for a in ARCHETYPES]
        assert len(set(names)) == len(names), key
    assert {a['family'] for a in ARCHETYPES} == set(FAMILIES)
    assert {a['room'] for a in ARCHETYPES} == set(ROOMS)


def test_no_word_belongs_to_two_types():
    owners = defaultdict(set)
    for arch in ARCHETYPES:
        for word in arch['words']:
            owners[archetypes.text_of(word)].add(arch['id'])
    assert {w: o for w, o in owners.items() if len(o) > 1} == {}
    short = {w for a in ARCHETYPES for w in a['words'] if archetypes.hangul(w) and len(w) == 1}
    assert short <= SHORT


@pytest.mark.parametrize('arch', ARCHETYPES, ids=ids)
def test_every_word_names_its_own_type_in_a_sentence(arch):
    for word in arch['words']:
        for text in [word] + with_particles(word):
            found = archetypes.classify(text)
            assert found and found['id'] == arch['id'], (text, found and found['id'])
    # The designer's category (the type id) and the id written with spaces name it too.
    assert archetypes.classify('', {'category': arch['id']})['id'] == arch['id']
    assert archetypes.classify(arch['id'])['id'] == arch['id']


@pytest.mark.parametrize('arch', ARCHETYPES, ids=ids)
def test_roles_behaviours_and_one_piece_presets_fit_together(arch):
    roles = {r['id']: r for r in arch['roles']}
    assert len(roles) == len(arch['roles'])
    assert sum(1 for r in arch['roles'] if r.get('root')) == 1 and arch['roles'][0].get('root')
    assert arch.get('rest', '') in ('', 'sit', 'lie')
    for entry in arch['behaviours']:
        assert entry['role'] in roles or entry['role'] == 'whole'
        if entry['kind'] in PART_KINDS:
            assert entry['role'] != 'whole' and not entry.get('or_whole'), entry
    for entry in arch['single']:
        assert entry['role'] == 'whole' and entry['kind'] not in PART_KINDS
    presets = arch['behaviours'] + arch['single']
    for entry in presets:
        Preset.model_validate({**{k: v for k, v in entry.items() if k not in ('role', 'or_whole')}, 'target': 'whole'})
    assert len(arch['behaviours']) <= interactions.MAX_PRESETS and len(arch['single']) <= interactions.MAX_PRESETS
    hint = archetypes.designer_hint(arch['words'][0], 'dynamic')
    assert ('plan.category to "%s"' % arch['id']) in hint
    if len(arch['roles']) > 1:
        assert all(r['id'] in hint for r in arch['roles'])


def test_new_types_come_alive_or_rest():
    """Every type does something: it moves, glows or seats the walker (a table and a slide only
    tell the designer their shape)."""
    idle = [a['id'] for a in ARCHETYPES if not a['behaviours'] and not a['single'] and not a.get('rest')]
    assert sorted(idle) == ['slide', 'table']


@pytest.mark.parametrize('arch', WITH_FIXTURE, ids=ids)
def test_the_fixture_is_made_of_the_types_roles_and_its_program_moves(arch):
    plan, program = archetypes.fixture_design(arch['id'])
    assert plan['category'] == arch['id'] and program == EMPTY
    parts = {p['id']: p for p in plan['parts']}
    roles = archetypes.bind(arch, plan['parts'])
    if len(parts) > 1:
        # Each role is the part with its own id, and every required one is there.
        assert {r: p for r, p in roles.items() if r != 'whole'} == {r: r for r in roles if r != 'whole'}
        assert all(r['id'] in roles for r in arch['roles'] if not r.get('optional')), roles
        for entry in arch['behaviours']:
            optional = entry['role'] == 'whole' or next(r for r in arch['roles'] if r['id'] == entry['role']).get('optional')
            if not optional:
                assert entry['role'] in parts, entry
            hint = next(r['hint'] for r in arch['roles'] if r['id'] == entry['role']) if entry['role'] in parts else ''
            if entry['kind'] == 'hinge' and 'pivot [' in hint:
                # A door or lid turns at the edge its hint names (knobs and levers turn at their middle).
                pivot = [float(v) for v in hint.split('pivot [')[1].split(']')[0].split(',')]
                assert parts[entry['role']]['pivot'] == pivot and any(abs(v) == .5 for v in pivot), entry
    result = archetypes.assign(arch['id'], plan, EMPTY)
    expected = arch['single'] if len(parts) == 1 else         [b for b in arch['behaviours'] if b['role'] == 'whole' or b['role'] in parts or b.get('or_whole')]
    if not expected:
        assert result is None or not result['spec']['presets']
        if arch.get('rest'):
            assert result['spec']['rest'] == arch['rest']
        return
    assert result['spec']['archetype'] == arch['id'] and result['spec']['rest'] == arch.get('rest', '')
    assert len(result['spec']['presets']) == len(expected)
    compiled = check(result['compiled']['program'], plan['parts'])
    # Run it as the game would: arrive, someone comes near and presses E, three seconds pass, they leave.
    vm = AssetVM(compiled, interactions.targets_of(plan['parts']))
    seen = defaultdict(list)
    steps = [('spawn', None), ('near', None), ('click', None)] + [('tick', {'dt': .05, 'clock': 36000 + i * .05})
                                                                 for i in range(60)]
    steps += [('leave', None)] + [('tick', {'dt': .05, 'clock': 36003 + i * .05}) for i in range(20)]
    for event, inputs in steps:
        for c in vm.run(event, inputs):
            assert math.isfinite(c['value']), c
            seen[(c['op'], c['target'])].append(c['value'])
    for p in result['spec']['presets']:
        ops = {'glow': 'emission', 'pulse': 'emission', 'flicker': 'emission', 'hue': 'hue', 'bounce': 'offset_y',
               'spin': 'rotate_y', 'turn': 'rotate_y', 'sway': 'rotate_z', 'slide': 'offset_' + p['axis']}
        op = ops.get(p['kind'], 'rotate_' + p['axis'])
        values = seen[(op, p['target'])]
        assert values and (max(values) - min(values) > 1e-3 or abs(values[-1]) > 1e-3), (p, values[:3])
        if op.startswith('offset_'):
            assert max(abs(v) for v in values) <= 2
        if op == 'emission':
            assert 0 <= min(values) and max(values) <= 4


def test_every_role_has_a_korean_name_and_the_game_shows_the_same_one():
    role_ids = {r['id'] for a in ARCHETYPES for r in a['roles']}
    assert role_ids <= set(ROLE_NAMES) and set(ROLE_NAMES) <= role_ids
    text = PANEL.read_text(encoding='utf-8')
    block = text[text.index('const PART_NAMES := {'):]
    block = block[:block.index('}')]
    names = dict(re.findall(r'"([a-z_]+)":\s*"([^"]+)"', block))
    assert {k: v for k, v in ROLE_NAMES.items() if k != 'whole'} == {k: names.get(k) for k in ROLE_NAMES if k != 'whole'}


def test_the_library_is_listed_for_signed_in_players(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), worker_enabled=False)
    with TestClient(app) as c:
        assert c.get('/v1/studio/library').status_code == 401
        token = c.post('/v1/auth/register', json={'username': 'lib_reader', 'password': 'Library-test-password'}).json()['token']
        listed = c.get('/v1/studio/library', headers={'Authorization': 'Bearer ' + token}).json()
    assert listed['version'] == archetypes.VERSION and len(listed['archetypes']) == len(ARCHETYPES)
    fridge = next(a for a in listed['archetypes'] if a['id'] == 'fridge')
    assert fridge['family'] == 'appliance' and fridge['fixture'] and fridge['role_names']['door'] == '문'
    assert set(listed['families']) == set(FAMILIES) and set(listed['rooms']) == set(ROOMS)
