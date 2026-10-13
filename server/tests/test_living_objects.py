"""Living crafted objects: the archetype library, time-driven VM operations, the learned library."""
import asyncio
import json
import math
import sqlite3
import uuid
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server.asset_vm import AssetVM, HOST_LIMITS, V2_OPS, legacy, uses_v2, validate_program, exercise_extended
from server.asset_assembly import demo_design, fixture_glb
from server import archetypes, interactions, admin_cli
from server import behaviour_library as library
from server.archetype_library import ARCHETYPES
from server.interactions import build, check, Preset

VM2 = {'X-Villagen-VM': '2'}


def mutation(**kw):
    return {'request_id': str(uuid.uuid4()), **kw}


def account(c, name):
    r = c.post('/v1/auth/register', json={'username': name, 'password': 'Studio-test-password'})
    assert r.status_code == 200
    return {'Authorization': 'Bearer ' + r.json()['token']}


@pytest.fixture
def world(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, daily_generation_limit=100), worker_enabled=False)
    with TestClient(app) as c:
        yield app, c


def craft(app, c, h, prompt, **kw):
    reply = c.post('/v1/studio/jobs', headers=h, json=mutation(prompt=prompt, **kw))
    assert reply.status_code == 200, reply.text
    job = reply.json()['id']
    asyncio.run(app.state.studio.process(job))
    result = c.get('/v1/studio/jobs/' + job, headers=h).json()
    assert result['state'] == 'ready', result
    return result['object_id'], result


def wrap(angle, op='rotate_z'):
    return angle % 360 if op == 'rotate_y' else (angle + 180) % 360 - 180


def same_angle(a, b, tolerance=1e-6):
    return abs(((a - b) + 180) % 360 - 180) < tolerance


def tick(program, parts, clock, dt=0.0):
    vm = AssetVM(program, interactions.targets_of(parts))
    vm.run('spawn')
    return {(c['op'], c['target']): c['value'] for c in vm.run('tick', {'dt': dt, 'time': 0, 'near': 0, 'clock': clock})}


# ---------------------------------------------------------------- the archetype library

@pytest.mark.parametrize('text,expected', [
    ('벽시계', 'clock'), ('시계를 만들어줘', 'clock'), ('wooden wall clock', 'clock'), ('a clock with a lamp', 'clock'),
    ('시계가 달린 램프', 'lamp'), ('흔들의자를 만들어 주세요', 'rocking_chair'), ('나무 의자', 'seat'), ('rocking chair', 'rocking_chair'),
    ('chest of drawers', 'drawer'), ('나무 서랍장', 'drawer'), ('fancy lamp', 'lamp'), ('보물상자', 'chest'), ('풍차', 'windmill'),
    ('선풍기', 'fan'), ('오르골', 'music_box'), ('촛불', 'candle'), ('침대', 'bed'), ('a light wooden chair', 'seat'),
    ('가습기', None), ('fantasy sword', None), ('table', None)])
def test_requests_are_classified_into_library_types(text, expected):
    found = archetypes.classify(text)
    assert (found['id'] if found else None) == expected


def test_the_designers_category_and_part_ids_bind_roles():
    plan = {'title': 'Old clock', 'category': 'wall_clock', 'parts': [
        {'id': 'clockCase', 'parent': ''}, {'id': 'hourHand', 'parent': 'clockCase'}, {'id': 'minuteHand', 'parent': 'clockCase'}]}
    kind = archetypes.classify('something nice for the wall', plan)
    assert kind['id'] == 'clock'
    roles = archetypes.bind(kind, plan['parts'])
    assert roles == {'body': 'clockCase', 'hour_hand': 'hourHand', 'minute_hand': 'minuteHand'}
    presets, _ = archetypes.presets_for(kind, plan['parts'])
    assert [(p['kind'], p['target'], p['hand']) for p in presets] == [('clock', 'hourHand', 'hour'), ('clock', 'minuteHand', 'minute')]


@pytest.mark.parametrize('arch', ARCHETYPES, ids=lambda a: a['id'])
def test_every_library_type_compiles_on_its_fixture_and_as_one_piece(arch):
    ids = {r['id'] for r in arch['roles']}
    assert all(b['role'] in ids | {'whole'} for b in arch['behaviours'] + arch['single'])
    for entry in arch['behaviours'] + arch['single']:
        Preset.model_validate({**{k: v for k, v in entry.items() if k not in ('role', 'or_whole')}, 'target': 'whole'})
    one = {'title': 't', 'category': arch['id'], 'parts': [{'id': 'whole', 'parent': ''}]}
    for plan in ([archetypes.fixture_design(arch['words'][0])[0]] if 'fixture' in arch else []) + [one]:
        assert archetypes.classify(arch['words'][0])['id'] == arch['id']
        result = archetypes.assign(arch['id'], plan, {'version': 1, 'state': {}, 'functions': {}, 'events': {}})
        if result is None:
            assert not arch['rest'] and not archetypes.presets_for(arch, plan['parts'])[0]
            continue
        assert result['spec']['rest'] == arch.get('rest', '')
        if result['compiled']:
            check(result['compiled']['program'], plan['parts'])


def test_a_crafted_program_keeps_its_motion_unless_the_type_overrides():
    chest_plan, chest_program = demo_design('chest')
    assert archetypes.assign('chest', chest_plan, chest_program) is None
    clock_plan, _ = demo_design('clock')
    own = {'version': 1, 'state': {}, 'functions': {}, 'events': {'tick': [['emit', 'rotate_z', 'second_hand', ['sub', ['mod', ['mul', ['input', 'time'], -6], 360], 180]]]}}
    result = archetypes.assign('clock', clock_plan, own)
    assert result['spec']['keep'] and len(result['spec']['presets']) == 3
    # Emitted after the crafted motion, the real time wins on the client.
    events = result['compiled']['program']['events']['tick']
    assert events[0] == own['events']['tick'][0] and events[-1][2] in ('hour_hand', 'minute_hand', 'second_hand')


# ---------------------------------------------------------------- time-driven operations

def clock_program():
    plan, _ = demo_design('clock')
    result = archetypes.assign('clock', plan, {'version': 1, 'state': {}, 'functions': {}, 'events': {}})
    return plan['parts'], result['compiled']['program']


def test_clock_hands_follow_the_players_local_time():
    parts, program = clock_program()
    clock = 10 * 3600 + 8 * 60 + 30.5  # 10:08:30.5
    out = tick(program, parts, clock)
    # Clockwise seen from the front is a negative turn about +Z.
    assert same_angle(out[('rotate_z', 'hour_hand')], -((10 % 12) + 8 / 60 + 30.5 / 3600) * 30)
    assert same_angle(out[('rotate_z', 'minute_hand')], -(8 + 30.5 / 60) * 6)
    assert same_angle(out[('rotate_z', 'second_hand')], -30 * 6)
    for (op, _), value in out.items():
        lo, hi = HOST_LIMITS[op]
        assert lo <= value <= hi
    # Midnight and noon: every hand up.
    for clock in (0.5, 43200.5):
        assert all(same_angle(v, 0, .1) for v in tick(program, parts, clock).values())


def test_the_second_hand_ticks_with_a_small_overshoot():
    parts, program = clock_program()
    # Degrees clockwise past 42 seconds (252 degrees).
    past = lambda t: (-tick(program, parts, 3600 + 42 + t)[('rotate_z', 'second_hand')] - 252 + 180) % 360 - 180
    # Settled for most of the second, one step of 6 degrees per second.
    assert all(abs(past(t)) < 1e-6 for t in (.3, .5, .99))
    assert abs(past(1.5) - 6) < 1e-6
    # The jump: starts from the previous second, passes the next a little, then settles.
    path = [past(t / 100) for t in range(0, 20)]
    assert abs(path[0] + 6) < 1e-6 and .3 < max(path) < 1.2
    assert all(b >= a - 1e-9 for a, b in zip(path, path[1:10]))


def test_tick_steps_on_click_and_runs_on_its_own():
    parts = [{'id': 'body', 'parent': ''}, {'id': 'dial', 'parent': 'body'}]
    program, idle = build([interactions.Preset(kind='tick', trigger='click', target='dial', axis='z', angle=30).model_dump()], parts)
    check(program, parts)
    vm = AssetVM(program, interactions.targets_of(parts))
    vm.run('spawn')
    rest = lambda: [c['value'] for c in vm.run('tick', {'dt': .1})][-1]
    assert same_angle(rest(), 0)
    vm.run('click')
    for _ in range(5):
        value = rest()
    assert same_angle(value, -30)
    assert list(idle.values()) == [interactions.TICK_EASE]
    running, _ = build([interactions.Preset(kind='tick', trigger='always', target='dial', axis='z', angle=6, level=2).model_dump()], parts)
    vm = AssetVM(running, interactions.targets_of(parts))
    vm.run('spawn')
    values = [[c['value'] for c in vm.run('tick', {'dt': .05})][-1] for _ in range(80)]  # 4 s
    settled = {round(v, 6) for v in values if abs(v / 6 - round(v / 6)) < 1e-9}
    assert len(settled) >= 4  # a step a second


def test_slide_rotor_flicker_and_rock_stay_in_range():
    parts = [{'id': 'body', 'parent': ''}, {'id': 'drawer', 'parent': 'body'}]
    chosen = [interactions.Preset(kind='slide', trigger='click', target='drawer', axis='z', angle=30).model_dump(),
              interactions.Preset(kind='rotor', trigger='always', target='body', axis='x', level=3).model_dump(),
              interactions.Preset(kind='flicker', trigger='always', target='whole', level=3).model_dump(),
              interactions.Preset(kind='rock', trigger='click', target='whole', axis='x').model_dump()]
    program, _ = build(chosen, parts)
    check(program, parts)
    vm = AssetVM(program, interactions.targets_of(parts))
    vm.run('spawn')
    vm.run('click')
    seen = {}
    for i in range(200):
        for c in vm.run('tick', {'dt': .05}):
            seen.setdefault((c['op'], c['target']), []).append(c['value'])
    assert abs(seen[('offset_z', 'drawer')][-1] - .3) < 1e-3
    assert len({round(v) for v in seen[('rotate_x', 'body')]}) > 50
    glow = seen[('emission', 'whole')]
    assert 0 < min(glow) and max(glow) <= 4 and max(glow) - min(glow) > .2
    rock = seen[('rotate_x', 'whole')]
    assert max(rock) > 3 and abs(rock[-1]) < .01  # a push rocks and settles


def test_new_vm_operations_reach_released_games_reduced():
    parts, program = clock_program()
    drawer, _ = build([interactions.Preset(kind='slide', target='drawer', axis='z', angle=30).model_dump()],
                      [{'id': 'body', 'parent': ''}, {'id': 'drawer', 'parent': 'body'}])
    for value, targets in ((program, interactions.targets_of(parts)), (drawer, ['body', 'drawer', 'whole'])):
        assert uses_v2(value)
        old = legacy(value)
        assert not uses_v2(old) and old['state'] == value['state']
        text = json.dumps(old)
        assert '"clock"' not in text and not any('"%s"' % op for op in V2_OPS if '"%s"' % op in text)
        exercise_extended(old, targets)


# ---------------------------------------------------------------- crafting

def test_a_crafted_clock_starts_with_its_hands_on_local_time(world):
    app, c = world
    a = account(c, 'alice')
    oid, job = craft(app, c, a, '벽시계')
    assert job['provenance']['archetype'] == 'clock' and job['provenance']['behaviour']['presets'] == 3
    value = c.get('/v1/objects/' + oid + '/assembly', headers={**a, **VM2}).json()
    program = value['interaction']['program']
    assert value['interaction']['mode'] == 'presets' and '["input", "clock"]' in json.dumps(program)
    assert set(value['runtime']['state']) == set(program['state'])
    out = tick(program, value['plan']['parts'], 15 * 3600 + 45 * 60)
    assert same_angle(out[('rotate_z', 'hour_hand')], -(3 + .75) * 30)
    # The owner sees them as presets in the editor and may change them.
    info = c.get('/v1/objects/' + oid + '/interaction', headers={**a, **VM2}).json()
    assert [p['hand'] for p in info['spec']['presets']] == ['hour', 'minute', 'second'] and info['spec']['archetype'] == 'clock'
    # A released game (no X-Villagen-VM) gets programs it can run.
    old = c.get('/v1/objects/' + oid + '/assembly', headers=a).json()
    assert not uses_v2(old['program']) and not uses_v2(old['interaction']['program'])
    validate_program(old['interaction']['program'], set(interactions.targets_of(old['plan']['parts'])))


def test_static_crafts_get_whole_object_behaviour_and_rest(world):
    app, c = world
    a = account(c, 'alice')
    lamp, _ = craft(app, c, a, 'a reading lamp', motion='static')
    value = c.get('/v1/objects/' + lamp + '/assembly', headers={**a, **VM2}).json()
    assert [p['id'] for p in value['plan']['parts']] == ['whole']
    assert value['interaction']['mode'] == 'presets' and 'click' in value['interaction']['program']['events']
    chair, _ = craft(app, c, a, '흔들의자')
    value = c.get('/v1/objects/' + chair + '/assembly', headers={**a, **VM2}).json()
    assert value['interaction']['rest'] == 'sit' and 'rotate_x' in json.dumps(value['interaction']['program'])
    event = c.post('/v1/objects/' + chair + '/event', headers=a, json=mutation(version=value['runtime']['version'], event='click'))
    # E pushes it: the rock's timer starts again (the rocking itself plays on every tick).
    assert event.status_code == 200 and 0 in event.json()['patch'].values()
    stool, _ = craft(app, c, a, 'wooden stool', motion='static')
    value = c.get('/v1/objects/' + stool + '/assembly', headers={**a, **VM2}).json()
    assert value['interaction']['rest'] == 'sit' and value['interaction']['mode'] == 'original'


class FurnitureProvider:
    def __init__(self):
        self.calls = []

    async def balance(self):
        return 10000

    async def request(self, method, path, payload):
        self.calls.append(payload)
        return {'task_id': 'task-' + str(len(self.calls))}

    async def task(self, task):
        return {'status': 'success', 'credits_consumed': 10, 'output': {'model_url': 'private-test-model'}}

    async def download(self, url, allow_textures=False):
        return fixture_glb('ellipsoid', allow_textures)


def test_clock_hands_cost_no_tripo_credits(tmp_path):
    provider = FurnitureProvider()
    app = create_app(Settings(data_dir=tmp_path, paid_enabled=True, tripo_key='private-test-key', daily_generation_limit=100),
                     provider=provider, worker_enabled=False)
    with TestClient(app) as c:
        a = account(c, 'alice')
        job = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='clock', geometry='tripo', mesh_model='v3.1-20260211')).json()['id']
        asyncio.run(app.state.studio.process(job))
        quote = c.get('/v1/studio/jobs/' + job, headers=a).json()
        # Four parts, one Tripo mesh: the hands are the game's own bars.
        assert len(quote['design']['parts']) == 4 and quote['provenance']['estimated_tripo_credits'] == 10
        # The preview before confirming already turns the hands.
        preview = c.get('/v1/studio/jobs/' + job + '/preview', headers={**a, **VM2}).json()
        assert '["input", "clock"]' in json.dumps(preview['program'])
        c.post('/v1/studio/jobs/' + job + '/confirm', headers=a, json=mutation())
        for _ in range(4):
            asyncio.run(app.state.studio.process(job))
        done = c.get('/v1/studio/jobs/' + job, headers=a).json()
        assert done['state'] == 'ready' and len(provider.calls) == 1 and done['provenance']['tripo_credits_consumed'] == 10
        value = c.get('/v1/objects/' + done['object_id'] + '/assembly', headers={**a, **VM2}).json()
        assert value['interaction']['mode'] == 'presets'


def test_credit_cap_fallback_keeps_the_types_whole_object_behaviour(tmp_path):
    class ThreeParts:
        async def generate(self, prompt, model, effort, image=None, style=None):
            plan = archetypes.fixture_design('music box')[0]
            return plan, {'version': 1, 'state': {}, 'functions': {}, 'events': {}}, {'provider': 'gemini', 'model': 'test'}

    settings = Settings(data_dir=tmp_path, mode='live', paid_enabled=True, tripo_key='test-only-key',
                        studio_llm='gemini', gemini_key='test-only-key', registration_code='test-only-invitation-123456',
                        daily_generation_limit=100, user_daily_generation_limit=100, max_credits_per_craft=25)
    provider = FurnitureProvider()
    app = create_app(settings, worker_enabled=False, designer=ThreeParts(), provider=provider)
    with TestClient(app, base_url='https://testserver') as client:
        token = client.post('/v1/auth/register', json={'username': 'cap_fall', 'password': 'Test-password-123',
                                                        'invitation': settings.registration_code}).json()['token']
        h = {'Authorization': 'Bearer ' + token}
        with app.state.db.transaction() as db:
            db.execute('UPDATE users SET shards=500')
        job = client.post('/v1/studio/jobs', headers=h, json=mutation(prompt='오르골', designer='llm', geometry='tripo',
                                                                     material='mesh', motion='dynamic', mesh_model='v3.1-20260211')).json()['id']
        asyncio.run(app.state.studio.process(job))
        status = client.get('/v1/studio/jobs/' + job, headers=h).json()
        assert status['provenance']['fallback'] == 'single_piece_credit_cap' and status['provenance']['estimated_tripo_credits'] == 10
        client.post('/v1/studio/jobs/' + job + '/confirm', headers=h, json=mutation())
        for _ in range(4):
            asyncio.run(app.state.studio.process(job))
        done = client.get('/v1/studio/jobs/' + job, headers=h).json()
        assert done['state'] == 'ready'
        value = client.get('/v1/objects/' + done['object_id'] + '/interaction', headers=h).json()
        assert [p['kind'] for p in value['spec']['presets']] == ['turn', 'pulse']


# ---------------------------------------------------------------- the learned library

class CountingDesigner:
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, model, effort, image=None, style=None):
        self.calls.append(prompt)
        if 'PLAN TO RETURN UNCHANGED: ' in prompt:
            plan = json.loads(prompt.split('PLAN TO RETURN UNCHANGED: ', 1)[1].split('\n', 1)[0])
            program = {'version': 1, 'state': {'lit': 0}, 'functions': {}, 'events': {
                'click': [['store', 'lit', ['not', ['state', 'lit']]]],
                'tick': [['emit', 'emission', 'body', ['mul', ['state', 'lit'], 2]]]}}
            return plan, program, {'provider': 'openai', 'model': model, 'usage': {'input_tokens': 10}}
        plan, program = demo_design('chest')
        plan['title'], plan['category'] = 'Hourglass', 'hourglass'
        return plan, program, {'provider': 'openai', 'model': model, 'usage': {'input_tokens': 10}}


def test_a_described_behaviour_is_reused_without_the_designer(world):
    app, c = world
    a, b = account(c, 'alice'), account(c, 'bobby')
    first, _ = craft(app, c, a, 'chest')
    second, _ = craft(app, c, b, 'wooden chest')
    designer = CountingDesigner()
    app.state.settings.studio_llm = 'openai'
    app.state.studio.designer = designer
    reply = c.post('/v1/objects/' + first + '/interaction/describe', headers=a, json=mutation(text='Make the body glow on click!'))
    assert reply.json()['state'] == 'ready' and reply.json()['cost'] == interactions.DESCRIBE_COST and len(designer.calls) == 1
    shards = c.get('/v1/me', headers=b).json()['shards']
    # Another player, another chest, the same words (case, punctuation and "please" aside).
    again = c.post('/v1/objects/' + second + '/interaction/describe', headers=b, json=mutation(text='please make the body glow on click'))
    assert again.status_code == 200 and again.json()['state'] == 'ready' and again.json()['cost'] == 0
    assert len(designer.calls) == 1 and again.json()['program'] == reply.json()['program']
    assert c.get('/v1/me', headers=b).json()['shards'] == shards
    saved = c.post('/v1/objects/' + second + '/interaction', headers=b, json=mutation(version=1, mode='custom'))
    assert saved.status_code == 200
    # Free reuses do not use up the day's descriptions.
    assert c.get('/v1/objects/' + second + '/interaction', headers=b).json()['describe']['left'] == interactions.DESCRIBE_DAILY_LIMIT
    # Different parts: not the same behaviour.
    clock, _ = craft(app, c, b, 'clock')
    other = c.post('/v1/objects/' + clock + '/interaction/describe', headers=b, json=mutation(text='make the body glow on click'))
    assert other.json()['cost'] == interactions.DESCRIBE_COST and len(designer.calls) == 2
    with app.state.db.read() as conn:
        entries = library.listing(conn, 'describe')
    assert len(entries) == 2 and sorted(e['uses'] for e in entries) == [0, 1]


def test_a_crafted_design_is_reused_without_the_designer(world):
    app, c = world
    a, b = account(c, 'alice'), account(c, 'bobby')
    designer = CountingDesigner()
    app.state.settings.studio_llm = 'openai'
    app.state.studio.designer = designer
    oid, first = craft(app, c, a, 'A small hourglass', designer='llm')
    assert len(designer.calls) == 1 and first['provenance']['provider'] == 'openai'
    _, second = craft(app, c, b, 'a small hourglass.', designer='llm')
    assert len(designer.calls) == 1 and second['provenance']['provider'] == 'library'
    assert second['design'] == first['design']
    # Another style or motion is another request.
    craft(app, c, b, 'a small hourglass', designer='llm', motion='static')
    assert len(designer.calls) == 2


def test_a_design_is_not_served_before_its_craft_finished(world):
    app, c = world
    a = account(c, 'alice')
    designer = CountingDesigner()
    app.state.settings.studio_llm = 'openai'
    app.state.studio.designer = designer
    job = c.post('/v1/studio/jobs', headers=a, json=mutation(prompt='hourglass', designer='llm', concept=True, motion='static')).json()['id']
    asyncio.run(app.state.studio.process(job))
    assert c.get('/v1/studio/jobs/' + job, headers=a).json()['state'] == 'awaiting_confirmation'
    with app.state.db.read() as conn:
        (entry,) = library.listing(conn, 'design')
        assert not entry['ready'] and library.find(conn, entry['key']) is None


def test_operators_list_show_and_disable_learned_entries(world, tmp_path, capsys):
    app, c = world
    a = account(c, 'alice')
    designer = CountingDesigner()
    app.state.settings.studio_llm = 'openai'
    app.state.studio.designer = designer
    craft(app, c, a, 'hourglass', designer='llm')
    data = app.state.settings.data_dir
    assert admin_cli.main(['library', 'list', '--data-dir', str(data)]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed[0]['kind'] == 'design' and listed[0]['label'] == 'hourglass' and listed[0]['ready'] == 1
    key = listed[0]['key']
    assert admin_cli.main(['library', 'show', key[:8], '--data-dir', str(data)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown['value']['plan']['category'] == 'hourglass'
    assert admin_cli.main(['library', 'disable', key[:8], '--data-dir', str(data)]) == 0
    capsys.readouterr()
    craft(app, c, a, 'hourglass', designer='llm')
    assert len(designer.calls) == 2
