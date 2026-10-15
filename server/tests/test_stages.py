"""Expedition stages: stage lengths, tier schedule, the boss night (no limit, cleared by the boss's
fall), the tutorial (no death, requirements, tutorial_done), catalog fields, rewards, and runs and
party worlds saved before stages (they finish under their old seven-day rules)."""
import json
import math
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from server import campaign, catalog, coop, simulation, stages
from server.app import create_app
from server.config import Settings
from server.tests.legacy_saves import legacy_run, legacy_world, strip

STAGES = {'tutorial': 1, 'forest': 3, 'quarry': 5, 'frost': 7}
ROSTER = {
    'tutorial': {'weak': ('goblin', 'centipede')},
    'forest': {'weak': ('goblin', 'harpy', 'centipede'), 'mid': ('werewolf', 'troll'), 'strong': ('cyclops',)},
    'quarry': {'weak': ('skeleton', 'imp', 'lizardman', 'mimic'), 'mid': ('basilisk', 'naga', 'gargoyle'),
               'strong': ('minotaur', 'mummy_king')},
    'frost': {'weak': ('ghoul', 'frost_wraith', 'ice_shardling', 'draugr'),
              'mid': ('yeti', 'wendigo', 'frost_hag', 'frost_knight'), 'strong': ('ice_golem', 'lich', 'glacier_giant')},
}
BOSSES = {'forest': 'treant', 'quarry': 'chimera', 'frost': 'dragon'}
TIERS_FROM = {'tutorial': {'weak': 1}, 'forest': {'weak': 1, 'mid': 2, 'strong': 3},
              'quarry': {'weak': 1, 'mid': 2, 'strong': 4}, 'frost': {'weak': 1, 'mid': 2, 'strong': 4}}


def mutation(**kw):
    return dict(request_id=str(uuid.uuid4()), **kw)


def account(c, name):
    r = c.post('/v1/auth/register', json={'username': name, 'password': 'Testing-only-12345'})
    assert r.status_code == 200, r.text
    return {'Authorization': 'Bearer ' + r.json()['token']}


@pytest.fixture
def world(tmp_path):
    now = [1000000.]
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings, clock=lambda: now[0], worker_enabled=False)
    with TestClient(app) as client:
        yield app, client, now, settings


def edit_run(app, run_id, edit, table='runs'):
    with app.state.db.transaction() as conn:
        state = json.loads(conn.execute(f'SELECT state FROM {table} WHERE id=?', (run_id,)).fetchone()[0])
        edit(state)
        conn.execute(f'UPDATE {table} SET state=? WHERE id=?', (json.dumps(state), run_id))


def open_field(s):
    s.update(nodes=[], obstacles=[], hazards=[])
    return s


# ------------------------------------------------------------------ stage clock

@pytest.mark.parametrize('map_id', catalog.MAPS)
def test_stage_lengths_are_90_plus_30_per_stage_and_night_is_the_last_35_percent(map_id):
    s = simulation.new_run(1, 0, 90, map_id)
    assert s['stage_count'] == STAGES[map_id] == catalog.MAPS[map_id]['stages']
    elapsed = 0.
    for stage in range(1, s['stage_count'] + 1):
        seconds = 90 + 30 * (stage - 1)
        assert stages.length(s, stage) == seconds and stages.start(s, stage) == elapsed
        for into, night in ((0., False), (seconds * .649, False), (seconds * .651, True), (seconds - .01, True)):
            if stage == s['stage_count'] and night:
                continue  # the open last night: below
            clock = stages.clock(s, elapsed + into)
            assert (clock['stage'], clock['seconds'], clock['night']) == (stage, seconds, night)
            assert clock['progress'] == pytest.approx(into / seconds)
            assert clock['remaining'] == pytest.approx(seconds - into)
        elapsed += seconds
    # Forest 6 min, quarry 12.5 min, frost 21 min of stages (plus the boss night).
    assert stages.start(s, s['stage_count'] + 1) == {'tutorial': 90, 'forest': 360, 'quarry': 750, 'frost': 1260}[map_id]


def test_public_state_carries_the_stage_contract():
    s = simulation.new_run(1, 0, 90, 'forest')
    s['elapsed'] = 90 + 120 * .7  # stage 2, night
    shown = simulation.public_state(s)
    assert (shown['stage'], shown['stage_count'], shown['stage_seconds'], shown['day']) == (2, 3, 120., 2)
    assert shown['night'] and shown['day_progress'] == pytest.approx(.7)
    assert shown['stage_remaining'] == pytest.approx(36.) and shown['phase_remaining'] == pytest.approx(36.)
    assert not shown['boss_night'] and shown['boss'] is None and shown['has_boss'] and not shown['tutorial']
    s['elapsed'] = 30.
    day = simulation.public_state(s)
    assert not day['night'] and day['phase_remaining'] == pytest.approx(58.5 - 30) and day['stage_remaining'] == 60


def test_stage_seconds_shorten_only_on_demo_servers(tmp_path, monkeypatch):
    monkeypatch.setenv('TRIPOTHON_STAGE_SECONDS', '12')
    assert Settings(data_dir=tmp_path).day_seconds == 12
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, mode='live', registration_code='a' * 24).validate()
    monkeypatch.delenv('TRIPOTHON_STAGE_SECONDS')
    assert Settings(data_dir=tmp_path).day_seconds == 90


# ------------------------------------------------------------------ roster and tiers

def test_roster_is_the_confirmed_one_with_todays_art_standing_in():
    assert catalog.ROSTERS == ROSTER
    assert {m: v['boss'] for m, v in catalog.MAPS.items() if v['boss']} == BOSSES
    owners = {}
    for map_id, tiers in ROSTER.items():
        for tier, kinds in tiers.items():
            for kind in kinds:
                stats = catalog.ENEMIES[kind]
                assert stats['tier'] == tier and stats['stand_in'] in catalog.LEGACY_SPECIES
                owners.setdefault(kind, set()).add(map_id)
    # One map each; the tutorial borrows the forest's weak ones.
    for kind, maps in owners.items():
        assert maps == {catalog.ENEMIES[kind]['map']} or maps == {'forest', 'tutorial'}
    assert set(ROSTER['tutorial']['weak']) <= set(ROSTER['forest']['weak'])
    # Maps with more stages have more species.
    sizes = [sum(len(k) for k in ROSTER[m].values()) for m in ('forest', 'quarry', 'frost')]
    assert sizes == sorted(sizes) and len(set(sizes)) == 3
    sizes = {kind: (catalog.ENEMIES[kind]['height'], catalog.ENEMIES[kind].get('length'), catalog.ENEMIES[kind].get('wingspan'))
             for kind in BOSSES.values()}
    assert sizes == {'treant': (5., None, None), 'chimera': (3., 4.5, None), 'dragon': (5., None, 7.)}
    for map_id, kind in BOSSES.items():
        assert catalog.ENEMIES[kind]['tier'] == 'boss' and catalog.ENEMIES[kind]['stand_in'] == 'brute'
        assert catalog.ENEMIES[kind]['hp'] >= 2.5 * max(catalog.ENEMIES[k]['hp'] for v in ROSTER[map_id].values() for k in v)


@pytest.mark.parametrize('map_id', catalog.MAPS)
@pytest.mark.parametrize('difficulty', catalog.DIFFICULTIES)
def test_tiers_come_out_on_their_stage(map_id, difficulty):
    s = simulation.new_run(7, 0, 60, map_id, difficulty)
    first = {}
    for stage in range(1, s['stage_count'] + 1):
        for enemy in simulation.night_enemies(s, stage):
            first.setdefault(catalog.ENEMIES[enemy['species']]['tier'], stage)
    assert first == TIERS_FROM[map_id]


# ------------------------------------------------------------------ the boss night

def boss_night(map_id='forest', difficulty='standard'):
    s = open_field(simulation.new_run(3, 0, 60, map_id, difficulty))
    s.update(elapsed=stages.final_night_at(s) - .05, last_wall=0., x=0., z=1.4, fire_until=10. ** 6)
    simulation.advance(s, .1)
    return s


@pytest.mark.parametrize('map_id', ['forest', 'quarry', 'frost'])
def test_boss_arrives_as_the_last_night_begins_and_the_night_has_no_limit(map_id):
    s = simulation.new_run(3, 0, 60, map_id)
    s.update(elapsed=stages.final_night_at(s) - .2, last_wall=0., fire_until=10. ** 6)
    simulation.advance(s, .1)
    assert not any(e.get('boss') for e in s['enemies'])
    simulation.advance(s, .3)
    bosses = [e for e in s['enemies'] if e.get('boss')]
    assert len(bosses) == 1 and bosses[0]['species'] == BOSSES[map_id] and bosses[0]['kind'] == 'brute'
    assert bosses[0]['height'] == catalog.ENEMIES[BOSSES[map_id]]['height']
    assert simulation.clear_position(s, bosses[0]['x'], bosses[0]['z'])
    # The regular wave of the last stage comes with it.
    assert {e['species'] for e in s['enemies'] if not e.get('boss')} <= set(catalog.night_plan(map_id, s['stage_count']))
    shown = simulation.public_state(s)
    assert shown['boss_night'] and shown['stage_remaining'] == -1 and shown['night']
    assert shown['boss'] == {'id': bosses[0]['id'], 'name': catalog.ENEMIES[BOSSES[map_id]]['name'],
                             'hp': bosses[0]['hp'], 'max_hp': bosses[0]['max_hp']}
    # Long past the end of the last stage: still the same night, the boss still out, no win by time.
    for i in range(1, 40):
        s['elapsed'] += 30.
        s['last_wall'] = 0.
        simulation.advance(s, .1)
    shown = simulation.public_state(s)
    assert s['status'] == 'active' and shown['stage'] == s['stage_count'] and shown['night']
    assert shown['day_progress'] == stages.OPEN_NIGHT_HOLD and shown['stage_remaining'] == -1
    assert sum(1 for e in s['enemies'] if e.get('boss')) == 1 and s['enemies']  # nothing cleared by a dawn


def test_the_boss_falling_clears_the_map_with_a_bonus():
    s = boss_night()
    s['enemies'] = [e for e in s['enemies'] if e.get('boss')]
    boss = s['enemies'][0]
    boss.update(x=0., z=4.5, phase='recover', phase_until=10. ** 6)
    s['inventory']['spear'] = 1
    hits = 0
    while s['status'] == 'active':
        s['elapsed'] += 1.
        reply = simulation.action(s, 'attack')
        hits += 1
        assert hits < 40, reply
    # 480 hp / 25 per spear blow; the swing reaches the 5 m treant's body from 3.1 m away.
    assert hits == 20 and reply == '우두머리를 쓰러뜨렸습니다!'
    assert s['status'] == 'won' and s['boss_defeated'] and s['kills'] == 1
    shown = simulation.public_state(s)
    assert shown['boss'] is None and shown['story'] is None
    s.update(harvested=0, hp=100)
    without = dict(s, boss_defeated=False)
    assert simulation.reward(s) - simulation.reward(without) == simulation.BOSS_BASE + simulation.BOSS_PER_STAGE * 3


def test_a_boss_shrugs_off_blows_during_its_wind_up():
    s = boss_night()
    s['enemies'] = [e for e in s['enemies'] if e.get('boss')]
    boss = s['enemies'][0]
    boss.update(x=0., z=4.5, phase='windup', phase_until=s['elapsed'] + 1., target_x=0., target_z=1.4)
    simulation.action(s, 'attack')
    assert boss['phase'] == 'windup' and boss['hp'] == boss['max_hp'] - 10


def test_party_boss_is_tougher_and_any_members_blow_clears_the_world():
    members = [dict(id=k, username=k, avatar={}) for k in 'abc']
    state = coop.new_world(5, 0, 60, members, 'quarry', 'standard')
    world = state['world']
    open_field(world)
    world.update(elapsed=stages.final_night_at(world) - .05, last_wall=0., fire_until=10. ** 6)
    for actor in state['players'].values():
        actor['last_seen'] = 0.
    coop.advance(state, .1)
    boss = next(e for e in world['enemies'] if e.get('boss'))
    assert boss['max_hp'] == catalog.ENEMIES['chimera']['hp'] * (1 + catalog.BOSS_PARTY_HP * 2)
    view = coop.public(state, 'b', .1)
    assert view['boss_night'] and view['boss']['max_hp'] == boss['max_hp'] and view['stage_remaining'] == -1
    world['enemies'] = [boss]
    boss.update(x=0., z=4.6, hp=5., phase='recover', phase_until=10. ** 6)
    state['players']['b'].update(x=0., z=2.4, last_attack=-10., last_action=-10.)

    class Body:
        sequence, dx, dz, sprint, action, target = 1, 0., 0., False, 'attack', ''
    coop.apply_input(state, 'b', Body, .2)
    assert world['status'] == 'won' and world['boss_defeated'] and world['reward'] > 0
    assert state['players']['b']['kills'] == 1


# ------------------------------------------------------------------ the tutorial

def test_tutorial_runs_gently_and_nobody_falls():
    s = simulation.new_run(4, 0, 90, 'tutorial', 'veteran')
    assert s['difficulty'] == 'relaxed' and s['tutorial'] and s['boss'] is None and s['stage_count'] == 1
    assert len(s['nodes']) == 36 and all(max(abs(n['x']), abs(n['z'])) <= 12 for n in s['nodes'])
    # Starving in the cold at night with creatures striking: health stops at 1.
    s.update(hunger=0., hp=5., elapsed=70., last_wall=0., fire_until=0.)
    for i in range(1, 200):
        simulation.advance(s, i * .1)
    assert s['status'] == 'active' and s['hp'] == simulation.TUTORIAL_HP_FLOOR
    assert '쓰러지지 않아요' in s['message']
    # Its single night has no limit.
    s['elapsed'] = 5000.
    assert simulation.public_state(s)['stage_remaining'] == -1 and not simulation.public_state(s)['boss_night']


def test_tutorial_night_refills_its_creatures_until_the_kills_are_done():
    s = open_field(simulation.new_run(4, 0, 90, 'tutorial'))
    s.update(elapsed=60., last_wall=0., fire_until=10. ** 6)
    simulation.advance(s, .1)
    assert [e['species'] for e in s['enemies']] == ['goblin', 'centipede']
    assert all(math.hypot(e['x'], e['z']) <= 11.5 for e in s['enemies'])
    s['enemies'] = []
    simulation.advance(s, .2)
    assert not s['enemies']
    s['elapsed'] += simulation.TUTORIAL_REFILL
    simulation.advance(s, .3)
    simulation.advance(s, .4)
    assert len(s['enemies']) == 2 and all('r_' in e['id'] for e in s['enemies'])


def test_tutorial_clears_on_its_requirements_with_a_flat_reward():
    s = simulation.new_run(4, 0, 90, 'tutorial')
    goals = simulation.public_state(s)['story']
    assert goals['id'] == 'tutorial' and [g['target'] for g in goals['goals']] == [6, 1, 1, 2]
    s.update(harvested=6, crafted={'axe': 1}, fires=1, kills=1, last_wall=0.)
    simulation.advance(s, .1)
    assert s['status'] == 'active'
    s['kills'] = 2
    simulation.advance(s, .2)
    assert s['status'] == 'won' and simulation.reward(s) == simulation.TUTORIAL_REWARD
    assert simulation.public_state(s)['story']['objectives_met']


def test_party_tutorial_counts_everyone_together_and_nobody_falls():
    members = [dict(id=k, username=k, avatar={}) for k in 'ab']
    state = coop.new_world(2, 0, 90, members, 'tutorial', 'standard')
    a, b = state['players']['a'], state['players']['b']
    for actor in (a, b):
        actor['last_seen'] = 0.
    a.update(hp=3., hunger=0.)
    state['world'].update(elapsed=70., last_wall=0.)
    for i in range(1, 30):
        coop.advance(state, i * .1)
    assert a['hp'] == simulation.TUTORIAL_HP_FLOOR and state['world']['status'] == 'active'
    a.update(harvested=4, crafted={'axe': 1}, kills=1)
    b.update(harvested=2, fires=1, kills=1)
    coop.advance(state, 3.1)
    assert state['world']['status'] == 'won' and state['world']['reward'] == simulation.TUTORIAL_REWARD


def finish_tutorial(app, run_id):
    edit_run(app, run_id, lambda s: s.update(harvested=6, crafted={'axe': 1}, fires=1, kills=2))


def test_tutorial_done_is_set_once_the_tutorial_is_cleared(world):
    app, c, now, _ = world
    a = account(c, 'tutorial_alice')
    assert c.get('/v1/me', headers=a).json()['tutorial_done'] is False
    # Leaving it does not count.
    rid = c.post('/v1/runs', headers=a, json=mutation(map_id='tutorial', difficulty='veteran')).json()['id']
    run = c.get('/v1/runs/' + rid, headers=a).json()
    assert run['map_id'] == 'tutorial' and run['difficulty'] == 'relaxed' and run['tutorial']
    assert c.post('/v1/runs/' + rid + '/abandon', headers=a, json=mutation()).status_code == 200
    assert c.get('/v1/me', headers=a).json()['tutorial_done'] is False
    rid = c.post('/v1/runs', headers=a, json=mutation(map_id='tutorial')).json()['id']
    finish_tutorial(app, rid)
    now[0] += .1
    state = c.post('/v1/runs/' + rid + '/input', headers=a, json={'sequence': 1}).json()
    assert state['status'] == 'won' and state['reward'] == simulation.TUTORIAL_REWARD
    me = c.get('/v1/me', headers=a).json()
    assert me['tutorial_done'] is True and me['pending_reward']['reward'] == simulation.TUTORIAL_REWARD
    assert c.post('/v1/runs/' + rid + '/claim', headers=a, json=mutation()).json()['story_bonus'] == 0
    # Selectable afterwards; it stays done.
    rid = c.post('/v1/runs', headers=a, json=mutation(map_id='tutorial')).json()['id']
    assert c.get('/v1/runs/' + rid, headers=a).json()['map_id'] == 'tutorial'
    assert c.get('/v1/me', headers=a).json()['tutorial_done'] is True


def test_party_tutorial_clear_marks_the_members_still_on_it(world):
    app, c, now, _ = world
    hs = [account(c, name) for name in ('party_alice', 'party_bravo', 'party_charlie')]
    c.post('/v1/party', headers=hs[0], json=mutation())
    for h, name in zip(hs[1:], ('party_bravo', 'party_charlie')):
        invite = c.post('/v1/social/invites', headers=hs[0], json=mutation(username=name, kind='party')).json()
        assert c.post('/v1/social/invites/' + invite['id'] + '/accept', headers=h, json=mutation()).status_code == 200
    for h in hs:
        c.post('/v1/social/presence', headers=h, json={})
    rid = c.post('/v1/party/runs', headers=hs[0], json=mutation(map_id='tutorial')).json()['id']
    route = '/v1/coop/runs/' + rid
    ids = [c.get(route, headers=h).json()['self_id'] for h in hs]
    assert c.post(route + '/abandon', headers=hs[2], json=mutation()).status_code == 200

    def done(state):
        state['players'][ids[0]].update(harvested=6, crafted={'axe': 1}, fires=1)
        state['players'][ids[1]].update(kills=2)
        for actor in state['players'].values():
            actor['last_seen'] = now[0]
    edit_run(app, rid, done, 'coop_runs')
    now[0] += .2
    assert c.get(route, headers=hs[0]).json()['status'] == 'won'
    assert [c.get('/v1/me', headers=h).json()['tutorial_done'] for h in hs] == [True, True, False]


def test_accounts_with_expeditions_before_the_tutorial_count_as_done(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings, worker_enabled=False)
    with TestClient(app) as c:
        veteran, newcomer = account(c, 'old_hand'), account(c, 'new_face')
        c.post('/v1/runs', headers=veteran, json=mutation(map_id='forest'))
    # As a database from before the tutorial: no tutorial table yet.
    with sqlite3.connect(tmp_path / 'world.sqlite3') as db:
        db.execute('DROP TABLE tutorial_progress')
    app = create_app(settings, worker_enabled=False)
    with TestClient(app) as c:
        assert c.get('/v1/me', headers=veteran).json()['tutorial_done'] is True
        assert c.get('/v1/me', headers=newcomer).json()['tutorial_done'] is False
    # Made once: later starts leave the table alone.
    app = create_app(settings, worker_enabled=False)
    with TestClient(app) as c:
        assert c.get('/v1/me', headers=newcomer).json()['tutorial_done'] is False


# ------------------------------------------------------------------ catalog and story

def test_catalog_lists_the_maps_in_order_with_stages_boss_and_tutorial(world):
    app, c, now, _ = world
    maps = c.get('/v1/me', headers=account(c, 'catalog_reader')).json()['catalog']['maps']
    assert [(m['id'], m['order'], m['stages'], m['has_boss'], m['tutorial']) for m in maps] == [
        ('tutorial', 0, 1, False, True), ('forest', 1, 3, True, False),
        ('quarry', 2, 5, True, False), ('frost', 3, 7, True, False)]
    assert next(m for m in maps if m['id'] == 'quarry')['name'] == '노을 채석장'
    assert all({'name', 'description', 'reward_multiplier'} <= set(m) for m in maps)


def test_story_chapters_read_stages_and_the_boss():
    chapter = campaign.CHAPTERS[1]
    s = simulation.new_run(1, 0, 60, chapter['map_id'])
    s['chapter_id'] = chapter['id']
    s['elapsed'] = stages.start(s, 3) + 1
    goals = campaign.progress(s)['goals']
    assert goals[:2] == [{'label': '5스테이지 돌파', 'current': 2, 'target': 5},
                         {'label': '키메라 처치', 'current': 0, 'target': 1}]
    s.update(status='won', boss_defeated=True)
    assert campaign.progress(s)['goals'][:2] == [{'label': '5스테이지 돌파', 'current': 5, 'target': 5},
                                                 {'label': '키메라 처치', 'current': 1, 'target': 1}]
    assert campaign.map_objective('frost') == '7스테이지 · 서리 용 처치'
    assert not any('일곱 번의 아침' in c['intro'] for c in campaign.CHAPTERS)


# ------------------------------------------------------------------ saved before stages

def test_a_solo_run_saved_before_stages_finishes_on_its_seven_days(world):
    app, c, now, settings = world
    a = account(c, 'legacy_alice')
    rid = c.post('/v1/runs', headers=a, json=mutation()).json()['id']
    # Saved by the old code on its third night, one of its creatures out (kind only).
    def old(state):
        strip(state)
        state['day_seconds'] = 60.
        state.update(elapsed=3 * 60 - 15., spawned_night=3, fire_until=10. ** 6, x=0., z=1.4, hunger=100., hp=100.)
        state['enemies'] = [dict(id='e3_0', kind='boar', variant='forest', behavior='charge', x=9., z=0., hp=60., max_hp=60.,
                                 damage=12., speed=1.2, windup=.9, reach=6., impact=1.1, charge_speed=7., charge_overshoot=2.,
                                 stun=1.4, phase='chase', phase_until=0.)]
    edit_run(app, rid, old)
    now[0] += .2
    state = c.post('/v1/runs/' + rid + '/input', headers=a, json={'sequence': 1}).json()
    assert (state['stage'], state['stage_count'], state['stage_seconds'], state['day']) == (3, 7, 60., 3)
    assert state['night'] and not state['boss_night'] and state['boss'] is None and not state['has_boss']
    assert [e['id'] for e in state['enemies']] == ['e3_0'] and state['enemies'][0]['species'] == 'boar'
    assert state['night_species'] == list(catalog.legacy_night_species('forest', 3))
    # Its seventh night ends it, as before: won by time, the old reward.
    edit_run(app, rid, lambda s: s.update(elapsed=7 * 60 - .1))
    now[0] += .2
    state = c.post('/v1/runs/' + rid + '/input', headers=a, json={'sequence': 2}).json()
    assert state['status'] == 'won' and '일곱 번의 밤' in state['message']
    assert state['reward'] == min(100, 35 + state['harvested'] // 4 + state['kills'] * 2 + int(state['hp'] // 10))
    with app.state.db.read() as conn:
        saved = json.loads(conn.execute('SELECT state FROM runs WHERE id=?', (rid,)).fetchone()[0])
    assert 'stage_count' not in saved  # never migrated


def test_legacy_runs_spawn_their_old_nights():
    s = open_field(legacy_run(5))
    s.update(elapsed=6 * 60 + 40., last_wall=0., spawned_night=5, fire_until=10. ** 6)
    simulation.advance(s, .1)
    assert {e['kind'] for e in s['enemies']} <= set(catalog.legacy_night_species('forest', 7))
    assert s['spawned_night'] == 7 and not any(e.get('boss') for e in s['enemies'])


def test_a_party_world_saved_before_stages_finishes_on_its_seven_days():
    members = [dict(id=k, username=k, avatar={}) for k in 'ab']
    state = legacy_world(3, members)
    state['world'].update(elapsed=7 * 60 - .1, last_wall=0., fire_until=10. ** 6)
    for actor in state['players'].values():
        actor['last_seen'] = 0.
    coop.advance(state, .05)
    assert state['world']['status'] == 'active'
    view = coop.public(state, 'a', .05)
    assert (view['stage'], view['stage_count'], view['boss']) == (7, 7, None)
    coop.advance(state, .2)
    assert state['world']['status'] == 'won' and state['world']['reward'] > 0
    assert 'stage_count' not in state['world']


def test_a_forest_run_played_by_intents_reaches_the_boss_night_alive():
    """Only valid movement/harvest/eat/fire intents (the seven-day bot of test_api.py on stages of
    60, 80 and 100 s): the camp fire holds every night off, then the boss night does not end."""
    s = simulation.new_run(42, 0, 60)
    now, target = 0., None
    while now < stages.final_night_at(s) + 40:
        now += .1
        inv = s['inventory']
        if s['status'] != 'active':
            break
        clock = stages.clock(s)
        if s['hunger'] < 65 and (inv['berry'] or inv['soup']):
            simulation.action(s, 'eat')
        if (clock['night'] or clock['progress'] > .6) and s['fire_until'] - s['elapsed'] < 2 and inv['wood'] >= 2 and abs(s['x']) < 2:
            simulation.action(s, 'fire')
        if inv['wood'] < 8 and s['nodes'][0]['quantity'] > 0: target = (1.2, 0, 'n0')
        elif inv['berry'] < 5 and s['nodes'][1]['quantity'] > 0: target = (-1.2, 0, 'n1')
        else: target = (0, 0, '')
        dx = max(-1, min(1, (target[0] - s['x']) * 2))
        dz = max(-1, min(1, (target[1] - s['z']) * 2))
        simulation.advance(s, now, dx, dz)
        if target[2] and abs(target[0] - s['x']) < .1:
            simulation.action(s, 'harvest', target[2])
    shown = simulation.public_state(s)
    assert s['status'] == 'active' and s['hp'] > 50, dict(hp=s['hp'], hunger=s['hunger'], elapsed=s['elapsed'])
    assert shown['boss_night'] and shown['boss']['name'] == '고목 트렌트' and shown['stage'] == 3
    assert s['elapsed'] > stages.start(s, 4)  # past the last stage's end: no win by time
