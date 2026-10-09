"""Player-made interactions (server/interactions.py): presets, the described path, persistence."""
import asyncio
import copy
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.config import Settings
from server.asset_vm import AssetVM, HOST_LIMITS, ProgramError, validate_program
from server.asset_assembly import demo_design
from server import interactions
from server.interactions import build, check, compat, InteractionError, KINDS, TRIGGERS


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


def craft(app, c, h, prompt='flower', **kw):
    reply = c.post('/v1/studio/jobs', headers=h, json=mutation(prompt=prompt, **kw))
    assert reply.status_code == 200, reply.text
    job = reply.json()['id']
    asyncio.run(app.state.studio.process(job))
    result = c.get('/v1/studio/jobs/' + job, headers=h).json()
    assert result['state'] == 'ready', result
    return result['object_id']


def preset(kind, trigger='click', target='whole', **kw):
    return {'kind': kind, 'trigger': trigger, 'target': target, **kw}


def run(program, parts, events, near=0):
    """Commands of the last tick after the given events, as {(op, target): value}."""
    vm = AssetVM(program, interactions.targets_of(parts))
    vm.run('spawn')
    last = {}
    for event in events:
        if event == 'tick':
            for c in vm.run('tick', {'dt': .05, 'time': 0, 'near': near}):
                last[(c['op'], c['target'])] = c['value']
        else:
            vm.run(event, {'near': int(event == 'near')})
    return last, vm


FLOWER = demo_design('flower')
CHEST = demo_design('chest')
ONE = [{'id': 'whole', 'parent': ''}]


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('trigger', TRIGGERS)
def test_every_preset_compiles_through_the_design_gates(kind, trigger):
    parts = CHEST[0]['parts']
    target = 'lid' if kind == 'hinge' else 'whole'
    program, idle = build([preset(kind, trigger, target, level=3, direction=-1, angle=-150, axis='z')], parts)
    check(program, parts)  # validate_program + exercise_extended
    for key, goal in idle.items():
        assert key in program['state'] and (goal in program['state'] if isinstance(goal, str) else True)


def test_presets_move_the_object_on_their_trigger():
    parts = ONE
    spin, _ = build([preset('spin')], parts)
    still, _ = run(spin, parts, ['tick'])
    moved, _ = run(spin, parts, ['click', 'tick', 'tick', 'tick'])
    assert still[('rotate_y', 'whole')] == 0 and 0 < moved[('rotate_y', 'whole')] < 360
    bounce, _ = build([preset('bounce', 'near', level=3)], parts)
    up, _ = run(bounce, parts, ['near', 'tick', 'tick', 'tick', 'tick'])
    assert 0 < up[('offset_y', 'whole')] <= .4
    glow, _ = build([preset('glow', 'click', level=3)], parts)
    lit, vm = run(glow, parts, ['click'] + ['tick'] * 40)
    assert 3 < lit[('emission', 'whole')] <= 3.2
    dark, _ = run(glow, parts, ['click', 'click'] + ['tick'] * 40)
    assert dark[('emission', 'whole')] < .01
    always, _ = build([preset('glow', 'always')], parts)
    assert run(always, parts, ['tick'])[0][('emission', 'whole')] == 2.0
    away, _ = build([preset('glow', 'leave')], parts)
    assert run(away, parts, ['near'] + ['tick'] * 40)[0][('emission', 'whole')] < .01
    hue, _ = build([preset('hue')], parts)
    assert ('hue', 'whole') not in run(hue, parts, ['tick'])[0]
    assert 0 <= run(hue, parts, ['click', 'tick'])[0][('hue', 'whole')] <= 1
    hinge, _ = build([preset('hinge', 'click', 'lid', axis='x', angle=-100)], CHEST[0]['parts'])
    opened, _ = run(hinge, CHEST[0]['parts'], ['click'] + ['tick'] * 60)
    assert -100.5 < opened[('rotate_x', 'lid')] < -99
    turn, _ = build([preset('turn', 'always', level=1)], parts)
    assert run(turn, parts, ['tick'] * 30)[0][('rotate_y', 'whole')] > 0


def test_combined_presets_share_channels_and_keep_the_crafted_motion():
    plan, original = CHEST
    parts = plan['parts']
    program, idle = build([preset('spin', 'click'), preset('turn', 'always'), preset('glow', 'near'),
                           preset('hinge', 'click', 'lid', angle=60)], parts, original)
    check(program, parts)
    # The crafted lid code still runs (its state and click toggle), the presets add to it.
    assert set(original['state']) <= set(program['state'])
    commands, vm = run(program, parts, ['click'] + ['tick'] * 10)
    assert vm.state['open'] == 1
    # One emit per channel: spin and turn add up on rotate_y of the whole object.
    crafted = sum(1 for s in original['events']['tick'] if s[0] == 'emit')
    emits = [s for s in program['events']['tick'] if s[0] == 'emit'][crafted:]
    assert len({(s[1], s[2]) for s in emits}) == len(emits) == 3
    assert ('rotate_y', 'whole') in commands and ('rotate_x', 'lid') in commands
    assert idle  # one-shot timers and fades settle between events


def test_preset_limits():
    parts = CHEST[0]['parts']
    for presets, code in [([preset('spin'), preset('spin', 'near')], 'duplicate_preset'),
                          ([preset('hinge', 'click', 'whole')], 'hinge_needs_part'),
                          ([preset('glow', 'click', 'nothing')], 'part_not_found'),
                          ([preset('glow', 'click', p) for p in ('whole', 'body', 'lid')] * 3, 'too_many_presets')]:
        with pytest.raises(InteractionError) as caught:
            program, _ = build(presets, parts)
        assert caught.value.code == code
    # A crafted program at the size limit leaves no room: rejected by the same gate.
    heavy = copy.deepcopy(CHEST[1])
    heavy['functions']['big'] = {'params': [], 'body': [], 'return': 0}
    expression = 0
    for _ in range(20):
        expression = ['add', expression, ['mul', 1, 1]]
    for count in range(1, 60):
        heavy['events']['spawn'] = [['do', expression]] * count
        try:
            validate_program(heavy, {'body', 'lid'})
        except ProgramError:
            break
    heavy['events']['spawn'] = [['do', expression]] * (count - 1)
    validate_program(heavy, {'body', 'lid'})
    with pytest.raises(InteractionError) as caught:
        check(build([preset('glow'), preset('spin'), preset('pulse', 'always', 'lid'), preset('bounce'),
                     preset('sway', 'near', 'lid'), preset('hue', 'always')], parts, heavy)[0], parts)
    assert caught.value.code == 'interaction_too_complex'


def test_compat_program_runs_on_released_clients():
    plan, _ = FLOWER
    program, _ = build([preset('spin', 'always'), preset('glow', 'click', 'center')], plan['parts'])
    value = {'plan': plan, 'program': program, 'interaction': {}}
    old = compat(value)
    ids = {p['id'] for p in plan['parts']}
    validate_program(old, ids)  # no 'whole' target left
    vm = AssetVM(old, ids)
    vm.run('click')
    assert all(c['target'] in ids for c in vm.run('tick', {'dt': .1}))
    # One-part crafts name their part 'whole': nothing to strip.
    one = {'plan': {'parts': [{'id': 'whole'}]}, 'program': program, 'interaction': {}}
    assert compat(one) is program


def test_save_is_owner_only_idempotent_versioned_and_reversible(world):
    app, c = world
    a, b = account(c, 'alice'), account(c, 'bobby')
    oid = craft(app, c, a, 'chest')
    route = '/v1/objects/' + oid
    before = c.get(route + '/assembly', headers=a).json()
    assert 'interaction' not in before
    info = c.get(route + '/interaction', headers=a).json()
    assert info['spec']['mode'] == 'original' and info['moving'] and [p['id'] for p in info['parts']] == ['body', 'lid']
    assert c.get(route + '/interaction', headers=b).status_code == 404
    assert c.get(route + '/interaction').status_code == 401
    choice = dict(mode='presets', presets=[preset('spin', 'click'), preset('hinge', 'near', 'lid', angle=-70)], keep=False, rest='sit')
    assert c.post(route + '/interaction/preview', headers=b, json=choice).status_code == 404
    rehearsal = c.post(route + '/interaction/preview', headers=a, json=choice)
    assert rehearsal.status_code == 200 and 'click' in rehearsal.json()['program']['events']
    assert c.get(route + '/assembly', headers=a).json()['runtime']['version'] == before['runtime']['version']
    assert c.post(route + '/interaction', headers=b, json=mutation(version=1, **choice)).status_code == 404
    stale = c.post(route + '/interaction', headers=a, json=mutation(version=9, **choice))
    assert stale.status_code == 409 and stale.json()['detail'] == 'stale_runtime_version'
    payload = mutation(version=before['runtime']['version'], **choice)
    saved = c.post(route + '/interaction', headers=a, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()['runtime']['version'] == before['runtime']['version'] + 1
    assert c.post(route + '/interaction', headers=a, json=payload).json() == saved.json()
    reused = c.post(route + '/interaction', headers=a, json={**payload, 'rest': 'lie'})
    assert reused.status_code == 409 and reused.json()['detail'] == 'request_id_reused'
    after = c.get(route + '/assembly', headers=a).json()
    assert after['runtime']['version'] == before['runtime']['version'] + 1
    assert after['interaction']['rest'] == 'sit' and after['interaction']['mode'] == 'presets'
    assert after['interaction']['program'] == saved.json()['program'] != before['program']
    # The crafted lid toggle is gone (keep=False); the server VM runs the new program.
    assert 'open' not in after['runtime']['state']
    event = c.post(route + '/event', headers=a, json=mutation(version=after['runtime']['version'], event='click'))
    assert event.status_code == 200, event.text
    timer = next(k for k in event.json()['patch'])
    assert event.json()['patch'][timer] == 0
    # Stored settled: a reload does not replay the spin.
    stored = c.get(route + '/assembly', headers=a).json()['runtime']['state']
    assert stored[timer] == after['interaction']['idle'][timer]
    near = c.post(route + '/event', headers=a, json=mutation(version=event.json()['version'], event='near')).json()
    assert any(v == 1 for k, v in near['patch'].items() if k.endswith('_on'))
    listing = c.get(route + '/interaction', headers=a).json()
    assert listing['spec']['presets'][1]['target'] == 'lid' and listing['spec']['version'] == 1
    # 원래대로: the crafted program and an unchanged reply shape come back.
    reset = c.post(route + '/interaction', headers=a, json=mutation(version=near['version'], mode='original'))
    assert reset.status_code == 200
    restored = c.get(route + '/assembly', headers=a).json()
    assert 'interaction' not in restored and restored['program'] == before['program']
    assert restored['runtime']['state'] == before['runtime']['state']


def test_rest_only_keeps_the_crafted_program_and_invoke_uses_the_override(world):
    app, c = world
    a = account(c, 'alice')
    oid = craft(app, c, a, 'chest', motion='static')
    route = '/v1/objects/' + oid
    value = c.get(route + '/assembly', headers=a).json()
    assert [p['id'] for p in value['plan']['parts']] == ['whole'] and not value['program']['events']
    saved = c.post(route + '/interaction', headers=a, json=mutation(version=1, mode='original', rest='lie'))
    assert saved.status_code == 200
    value = c.get(route + '/assembly', headers=a).json()
    assert value['interaction']['rest'] == 'lie' and value['program'] == value['interaction']['program']
    saved = c.post(route + '/interaction', headers=a, json=mutation(version=2, presets=[preset('sway', 'always', level=3)]))
    value = c.get(route + '/assembly', headers=a).json()
    # A one-part craft: 'whole' is its part, so released clients run the same program.
    assert value['program'] == value['interaction']['program'] and value['interaction']['rest'] == ''
    assert c.post(route + '/invoke', headers=a, json=mutation(version=3, function='open_flower', args=[1])).status_code == 409


def test_market_listing_locks_interactions(world):
    app, c = world
    a = account(c, 'alice')
    oid = craft(app, c, a, 'chest')
    route = '/v1/objects/' + oid
    assert c.post('/v1/market', headers=a, json=mutation(object_id=oid, version=1, price=10)).status_code == 200
    saved = c.post(route + '/interaction', headers=a, json=mutation(version=1, presets=[preset('glow')]))
    assert saved.status_code == 409 and saved.json()['detail'] == 'object_is_listed'
    described = c.post(route + '/interaction/describe', headers=a, json=mutation(text='빛나게'))
    assert described.status_code == 409 and described.json()['detail'] == 'object_is_listed'
    assert c.get(route + '/interaction', headers=a).json()['listed'] is True


def test_described_interaction_with_the_fixture_designer(world):
    app, c = world
    a = account(c, 'alice')
    oid = craft(app, c, a, 'chest')
    route = '/v1/objects/' + oid
    shards = c.get('/v1/me', headers=a).json()['shards']
    assert c.post(route + '/interaction', headers=a, json=mutation(version=1, mode='custom')).json()['detail'] == 'no_custom_design'
    payload = mutation(text='다가가면 뚜껑이 열리고 은은하게 빛나요')
    first = c.post(route + '/interaction/describe', headers=a, json=payload)
    assert first.status_code == 200, first.text
    draft = first.json()
    assert draft['state'] == 'ready' and draft['shards'] == shards - interactions.DESCRIBE_COST
    assert 'near' in draft['summary']['events'] and {'rotate_x', 'emission'} <= set(draft['summary']['ops'])
    # The same request is not charged twice.
    assert c.post(route + '/interaction/describe', headers=a, json=payload).json()['design_id'] == draft['design_id']
    assert c.get('/v1/me', headers=a).json()['shards'] == shards - interactions.DESCRIBE_COST
    info = c.get(route + '/interaction', headers=a).json()
    assert info['draft']['program'] == draft['program'] and info['describe']['left'] == interactions.DESCRIBE_DAILY_LIMIT - 1
    saved = c.post(route + '/interaction', headers=a, json=mutation(version=1, mode='custom'))
    assert saved.status_code == 200 and saved.json()['spec']['text'] == draft['text']
    assert c.get(route + '/assembly', headers=a).json()['interaction']['program'] == draft['program']


def test_described_interaction_uses_the_studio_designer_and_refunds_failures(world):
    from server.design_provider import DesignFailure
    app, c = world
    a = account(c, 'alice')
    oid = craft(app, c, a, 'chest')
    route = '/v1/objects/' + oid
    calls = []

    class Designer:
        async def generate(self, prompt, model, effort, image, style):
            calls.append(prompt)
            plan = json.loads(prompt.split('PLAN TO RETURN UNCHANGED: ', 1)[1].split('\n', 1)[0])
            program = {'version': 1, 'state': {'lit': 0}, 'functions': {}, 'events': {
                'click': [['store', 'lit', ['not', ['state', 'lit']]]],
                'tick': [['emit', 'emission', 'body', ['mul', ['state', 'lit'], 2]]]}}
            return plan, program, {'provider': 'openai', 'model': model, 'effort': effort, 'usage': {'input_tokens': 10}}

    class Broken:
        async def generate(self, *args):
            raise DesignFailure([{'usage': {'input_tokens': 5}, 'validation_error': 'ProgramError: invalid_expression'}])

    class Shifty(Designer):
        async def generate(self, *args):
            plan, program, provenance = await super().generate(*args)
            plan['parts'] = plan['parts'][:1]
            return plan, program, provenance

    app.state.settings.studio_llm = 'openai'
    app.state.studio.designer = Designer()
    shards = c.get('/v1/me', headers=a).json()['shards']
    reply = c.post(route + '/interaction/describe', headers=a, json=mutation(text='make the body glow on click'))
    assert reply.status_code == 200 and reply.json()['state'] == 'ready', reply.text
    assert '"lid"' in calls[0] and 'make the body glow on click' in calls[0]
    for designer, code in [(Broken(), 'llm_invalid_design'), (Shifty(), 'design_changed_parts')]:
        app.state.studio.designer = designer
        failed = c.post(route + '/interaction/describe', headers=a, json=mutation(text='spin it'))
        assert failed.status_code == 200 and failed.json()['state'] == 'failed' and failed.json()['error'] == code
    # Failures are refunded; only the successful description is paid.
    assert c.get('/v1/me', headers=a).json()['shards'] == shards - interactions.DESCRIBE_COST
    # The last good draft stays and can be saved; the server VM runs it.
    saved = c.post(route + '/interaction', headers=a, json=mutation(version=1, mode='custom'))
    assert saved.status_code == 200
    event = c.post(route + '/event', headers=a, json=mutation(version=2, event='click')).json()
    assert event['patch'] == {'lit': 1}
    # Daily limit per account (failed attempts count: they used the model).
    left = c.get(route + '/interaction', headers=a).json()['describe']['left']
    app.state.studio.designer = Designer()
    for _ in range(left):
        assert c.post(route + '/interaction/describe', headers=a, json=mutation(text='glow')).status_code == 200
    limited = c.post(route + '/interaction/describe', headers=a, json=mutation(text='glow'))
    assert limited.status_code == 429 and limited.json()['detail'] == 'interaction_daily_limit'


def test_visitors_see_the_interaction(world):
    app, c = world
    a, b = account(c, 'alice'), account(c, 'bobby')
    oid = craft(app, c, a, 'flower')
    route, guest = '/v1/objects/' + oid, '/v1/social/village/objects/' + oid
    assert c.post(route + '/placement', headers=a, json=mutation(version=1, room='village', x=5, z=4)).status_code == 200
    invite = c.post('/v1/social/invites', headers=a, json=mutation(username='bobby', kind='village')).json()
    assert c.post('/v1/social/invites/' + invite['id'] + '/accept', headers=b, json=mutation()).status_code == 200
    plain = c.get(guest + '/assembly', headers=b).json()
    assert 'interaction' not in plain
    saved = c.post(route + '/interaction', headers=a, json=mutation(version=1, presets=[preset('spin', 'always'), preset('glow', 'near', 'center')], keep=True))
    assert saved.status_code == 200, saved.text
    seen = c.get(guest + '/assembly', headers=b).json()
    assert seen['interaction']['program'] == saved.json()['program'] and seen['runtime']['version'] == 2
    # Released clients get the same state with the whole-object emits reduced.
    ids = {p['id'] for p in seen['plan']['parts']}
    validate_program(seen['program'], ids)
    assert seen['program']['state'] == seen['interaction']['program']['state']
    # Visitors cannot change it.
    assert c.post(route + '/interaction', headers=b, json=mutation(version=2, presets=[])).status_code == 404
    assert c.post(route + '/interaction/describe', headers=b, json=mutation(text='spin')).status_code == 404
