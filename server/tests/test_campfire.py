"""Campfire mode compatibility, survivor effects, coop rescue, and run payloads."""
import json
import math

import pytest

from server import campfire, coop, simulation as sim
from server.config import Settings
from server.models import Input


@pytest.fixture(autouse=True)
def default_mode(monkeypatch):
    monkeypatch.setenv('TRIPOTHON_CAMPFIRE_MODE', 'barrier')


def run(mode='buff', **changes):
    s = sim.new_run(24, 0., 60.)
    s.update(campfire_mode=mode, elapsed=10., last_wall=10., x=0., z=2.,
             nodes=[], obstacles=[], hazards=[], enemies=[], fire_until=100.,
             hp=50., stamina=50., spawned_night=1)
    s.update(changes)
    return s


def party(mode='buff', fire=True, helpers=1):
    members = [dict(id=str(i), username='player' + str(i), avatar={}) for i in range(helpers + 1)]
    state = coop.new_world(24, 0., 60., members, 'forest', 'standard')
    world = state['world']
    world.update(campfire_mode=mode, nodes=[], obstacles=[], hazards=[], enemies=[],
                 fire_until=100. if fire else 0.)
    x = 0. if fire else 6.
    for index, actor in enumerate(state['players'].values()):
        actor.update(x=x + (index - 1) * .4, z=2., hp=100., stamina=100.)
    state['players']['0']['hp'] = 0.
    return state


def tick_party(state, seconds, online=True):
    steps = round(seconds / .1)
    assert steps * .1 == pytest.approx(seconds)
    for _ in range(steps):
        now = state['world']['last_wall'] + .1
        if online:
            for actor in state['players'].values():
                actor['last_seen'] = now
        coop.advance(state, now)


def test_default_and_invalid_mode_are_checked_on_startup(monkeypatch):
    monkeypatch.delenv('TRIPOTHON_CAMPFIRE_MODE')
    Settings().validate()
    assert sim.new_run(1, 0., 60.)['campfire_mode'] == 'barrier'
    monkeypatch.setenv('TRIPOTHON_CAMPFIRE_MODE', 'BUFF')
    Settings().validate()
    assert sim.new_run(1, 0., 60.)['campfire_mode'] == 'buff'
    monkeypatch.setenv('TRIPOTHON_CAMPFIRE_MODE', 'unsafe')
    with pytest.raises(ValueError, match='TRIPOTHON_CAMPFIRE_MODE'):
        Settings().validate()
    with pytest.raises(ValueError, match='TRIPOTHON_CAMPFIRE_MODE'):
        sim.new_run(1, 0., 60.)


@pytest.mark.parametrize('mode', ['barrier', 'buff'])
def test_opening_message_says_whether_the_fire_stops_monsters(monkeypatch, mode):
    monkeypatch.setenv('TRIPOTHON_CAMPFIRE_MODE', mode)
    s = sim.new_run(1, 0., 60.)
    expected = ('낮에는 채집하고 밤에는 모닥불 곁에서 회복하세요. 불은 몬스터를 막지 못해요.'
                if mode == 'buff' else '낮에는 채집하고 밤에는 모닥불 곁을 지키세요.')
    assert s['message'] == expected
    assert sim.public_state(s)['campfire']['blocks_monsters'] is (mode == 'barrier')
    members = [dict(id='1', username='player1', avatar={})]
    assert coop.new_world(1, 0., 60., members, 'forest', 'standard')['players']['1']['message'] == expected


@pytest.mark.parametrize('saved_mode', ['barrier', 'buff', None])
def test_saved_rules_survive_environment_change_and_json_restart(monkeypatch, saved_mode):
    saved = run(saved_mode or 'barrier')
    if saved_mode is None:
        saved.pop('campfire_mode')
    restored = json.loads(json.dumps(saved))
    monkeypatch.setenv('TRIPOTHON_CAMPFIRE_MODE', 'barrier' if saved_mode == 'buff' else 'buff')
    sim.advance(restored, 10.1)
    expected = saved_mode or 'barrier'
    assert sim.public_state(restored)['campfire']['mode'] == expected
    assert restored['hp'] == pytest.approx(50.06 if expected == 'buff' else 50.)


@pytest.mark.parametrize('mode', ['barrier', 'buff'])
@pytest.mark.parametrize('behavior', ['melee', 'spore', 'charge'])
def test_lighting_fire_cancels_pending_attacks_only_in_barrier_mode(mode, behavior):
    s = run(mode, elapsed=40., last_wall=40., hp=100., fire_until=0.)
    enemy = dict(id='pending', x=0., z=3., hp=100., behavior=behavior, damage=12.,
                 phase='windup', phase_until=40., target_x=0., target_z=2., impact=1.4)
    s['enemies'] = [enemy]
    sim.action(s, 'fire')
    sim.advance_enemy(s, enemy, .1, 1, campfire.in_radius(s))
    if behavior == 'charge' and mode == 'buff':
        assert enemy['phase'] == 'charge'
        sim.advance_enemy(s, enemy, .1, 1, campfire.in_radius(s))
    if mode == 'barrier':
        assert s['hp'] == 100. and enemy['phase'] == 'warded'
        assert enemy['z'] > 3.
    else:
        assert s['hp'] == 88. and enemy['phase'] == 'recover'
        recovery = 1.4 if behavior == 'charge' else .85
        assert enemy['phase_until'] == pytest.approx(40. + recovery * 1.5)


@pytest.mark.parametrize('mode', ['barrier', 'buff'])
def test_active_charge_crosses_fire_radius_only_in_buff_mode(mode):
    s = run(mode, elapsed=40., hp=100.)
    enemy = dict(id='charging', x=0., z=3., hp=100., phase='charge', phase_until=43.,
                 _charge_dx=0., _charge_dz=-1., _charge_left=4., _charge_hit=False)
    sim.advance_enemy(s, enemy, .1, 1, True)
    assert s['hp'] == (100. if mode == 'barrier' else 88.)
    assert enemy['phase'] == ('warded' if mode == 'barrier' else 'recover')


@pytest.mark.parametrize('mode', ['barrier', 'buff'])
def test_enemies_approach_the_survivor_or_fire_edge_according_to_mode(mode):
    s = run(mode, elapsed=40., hp=100.)
    enemy = dict(id='approaching', x=0., z=6., hp=100., phase='chase', phase_until=0.)
    for _ in range(35):
        s['elapsed'] += .1
        sim.advance_enemy(s, enemy, .1, 1, True)
    if mode == 'barrier':
        assert math.hypot(enemy['x'], enemy['z']) >= 4.7
        assert enemy['phase'] == 'warded'
    else:
        assert math.hypot(enemy['x'], enemy['z']) < 4.
        assert enemy['phase'] in ('windup', 'recover')


@pytest.mark.parametrize('mode,health,stamina', [('barrier', 50., 53.5), ('buff', 50.15, 54.5)])
def test_regeneration_adds_to_normal_stamina_recovery(mode, health, stamina):
    s = run(mode)
    sim.advance(s, 10.25)
    assert s['hp'] == pytest.approx(health)
    assert s['stamina'] == pytest.approx(stamina)
    capped = run(mode, hp=99.99, stamina=99.99)
    sim.advance(capped, 10.25)
    assert capped['stamina'] == 100.
    assert capped['hp'] == (100. if mode == 'buff' else 99.99)


@pytest.mark.parametrize('position,fire_until', [((4., 0.), 100.), ((4.01, 0.), 100.), ((0., 2.), 10.)])
def test_regeneration_requires_strict_radius_and_burning_fire(position, fire_until):
    s = run(x=position[0], z=position[1], fire_until=fire_until)
    sim.advance(s, 10.1)
    assert s['hp'] == 50.
    assert s['stamina'] == pytest.approx(51.4)
    assert sim.public_state(s)['buffs'] == []
    assert not sim.public_state(s)['warm']


@pytest.mark.parametrize('status,hp', [('active', 0.), ('lost', 0.), ('won', 50.), ('abandoned', 50.)])
def test_fire_cannot_revive_solo_dead_or_finished_runs(status, hp):
    s = run(status=status, hp=hp)
    sim.advance(s, 10.1)
    assert s['hp'] == hp
    assert sim.public_state(s)['buffs'] == []


def test_starvation_cannot_be_undone_by_regeneration_after_lethal_damage():
    s = run(hp=.1, hunger=0.)
    sim.advance(s, 10.1)
    assert s['hp'] == 0. and s['status'] == 'lost'


@pytest.mark.parametrize('mode,stamina', [('barrier', 47.8), ('buff', 48.2)])
def test_fire_regeneration_offsets_but_does_not_remove_sprint_cost(mode, stamina):
    s = run(mode)
    sim.advance(s, 10.1, 1., 0., True)
    assert s['sprinting'] and s['stamina'] == pytest.approx(stamina)
    assert s['x'] == pytest.approx(.675)


@pytest.mark.parametrize('mode', ['barrier', 'buff'])
def test_fire_removes_night_cold_without_granting_immunity_after_leaving(mode):
    s = run(mode, elapsed=40., last_wall=40.)
    sim.advance(s, 40.1)
    assert s['hp'] == pytest.approx(50.06 if mode == 'buff' else 50.)
    s.update(x=6., z=2.)
    before = s['hp']
    sim.advance(s, 40.2)
    assert s['hp'] == pytest.approx(before - .028)
    if mode == 'buff':
        assert [b['id'] for b in sim.public_state(s)['buffs']] == ['warmed']


@pytest.mark.parametrize('mode', ['barrier', 'buff'])
def test_warmed_damage_lingers_then_expires_at_five_seconds(mode):
    s = run(mode)
    s['inventory']['spear'] = 1
    sim.advance(s, 10.1)
    s.update(x=6., z=2., fire_until=10.1)
    expires = s.get('warmed_until', 15.1)
    enemy = dict(id='target', x=6., z=3., hp=100., phase='chase', phase_until=0.)
    s['enemies'] = [enemy]
    s['elapsed'] = expires - .01
    sim.action(s, 'attack')
    assert enemy['hp'] == pytest.approx(72.5 if mode == 'buff' else 75.)
    s.update(elapsed=expires, last_action=-10., last_attack=-10.)
    before = enemy['hp']
    sim.action(s, 'attack')
    assert enemy['hp'] == before - 25.
    assert sim.public_state(s)['buffs'] == []


def test_extinguishing_stops_regeneration_but_preserves_only_warmed():
    s = run(fire_until=10.15)
    sim.advance(s, 10.1)
    hp = s['hp']
    sim.advance(s, 10.2)
    assert s['hp'] == hp
    data = sim.public_state(s)
    assert not data['warm'] and not data['campfire']['active']
    assert data['fire_remaining'] == 0.
    assert [b['id'] for b in data['buffs']] == ['warmed']
    assert data['buffs'][0]['remaining'] == pytest.approx(4.9)


@pytest.mark.parametrize('fire,seconds', [(False, 8.), (True, 4.)])
@pytest.mark.parametrize('helpers', [1, 2])
def test_coop_rescue_takes_eight_seconds_or_four_by_fire_without_stacking(fire, seconds, helpers):
    state = party(fire=fire, helpers=helpers)
    downed = state['players']['0']
    tick_party(state, seconds - .1)
    assert downed['hp'] == 0.
    payload = coop.public(state, '0', state['world']['last_wall'])['revive']
    assert payload['active'] and payload['remaining'] == pytest.approx(.1)
    assert payload['speed_multiplier'] == (2. if fire else 1.)
    tick_party(state, .1)
    assert downed['hp'] == 30. and state['world']['status'] == 'active'
    assert downed['revive_progress'] == 0. and downed['revive_rate'] == 0.
    assert not downed['sprinting'] and downed['intent']['dx'] == downed['intent']['dz'] == 0.
    assert coop.public(state, '0', state['world']['last_wall'])['revive'] is None


def test_barrier_keeps_downed_survivors_spectating():
    state = party('barrier')
    tick_party(state, 8.)
    assert state['players']['0']['hp'] == 0.
    assert coop.public(state, '0', 8.)['revive'] is None


@pytest.mark.parametrize('interruption', ['moving', 'far', 'wall', 'withdrawn', 'offline', 'downed_offline'])
def test_rescue_progress_resets_when_help_is_interrupted(interruption):
    state = party(helpers=2)
    state['players']['2']['x'] = 10.
    tick_party(state, 1.)
    downed, helper = state['players']['0'], state['players']['1']
    assert downed['revive_progress'] == pytest.approx(2.)
    now = state['world']['last_wall'] + .1
    if interruption == 'moving':
        helper['intent'] = dict(dx=1., dz=0., sprint=False, at=now)
    elif interruption == 'far':
        helper['x'] = 8.
    elif interruption == 'wall':
        state['world']['obstacles'] = [dict(x=-.2, z=2., radius=.1)]
    elif interruption == 'withdrawn':
        helper['withdrawn'] = True
    elif interruption == 'offline':
        helper['last_seen'] = now - coop.PRESENCE_SECONDS
    else:
        downed['last_seen'] = now - coop.PRESENCE_SECONDS
    coop.advance(state, now)
    assert downed['hp'] == 0. and downed['revive_progress'] == 0.
    assert downed['revive_rate'] == 0.
    public = coop.public(state, '0', now)['revive']
    assert public['progress'] == 0. and not public['active'] and public['remaining'] is None


def test_fire_rescue_boost_requires_both_helper_and_downed_inside_radius():
    state = party()
    downed, helper = state['players']['0'], state['players']['1']
    downed.update(x=3.9, z=0.)
    helper.update(x=4.1, z=0.)
    tick_party(state, 1.)
    assert downed['revive_progress'] == pytest.approx(1.)
    assert downed['revive_rate'] == 1.


def test_a_teammate_downed_against_a_bench_can_still_be_revived():
    state = party()
    downed = state['players']['0']
    state['world']['obstacles'] = [dict(kind='bench', x=downed['x'] - .82, z=downed['z'], radius=.55)]
    assert sim.clear_position(state['world'], downed['x'], downed['z'])
    tick_party(state, 1.)
    assert downed['revive_rate'] == 2. and downed['revive_progress'] == pytest.approx(2.)


def test_leaving_fire_slows_an_ongoing_rescue_without_erasing_progress():
    state = party()
    tick_party(state, 1.)
    state['world']['fire_until'] = state['world']['elapsed']
    tick_party(state, 1.)
    assert state['players']['0']['revive_progress'] == pytest.approx(3.)
    assert state['players']['0']['revive_rate'] == 1.


def test_offline_pause_clears_rescue_and_never_banks_time():
    state = party()
    tick_party(state, 1.)
    elapsed = state['world']['elapsed']
    coop.advance(state, 100.)
    assert state['world']['elapsed'] == elapsed
    downed = state['players']['0']
    assert downed['revive_progress'] == 0. and downed['revive_rate'] == 0.
    # An online request at the same wall-clock time cannot add a simulation tick.
    for actor in state['players'].values():
        actor['last_seen'] = 100.
    coop.advance(state, 100.)
    assert downed['revive_progress'] == 0.
    coop.advance(state, 100.1)
    assert downed['revive_progress'] == pytest.approx(.2)


def test_withdrawal_and_party_wipe_cannot_rescue_players():
    withdrawn = party()
    withdrawn['players']['0']['withdrawn'] = True
    tick_party(withdrawn, 4.)
    assert withdrawn['players']['0']['hp'] == 0.
    data = coop.public(withdrawn, '0', 4.)
    assert data['status'] == 'abandoned' and data['revive'] is None and data['buffs'] == []
    assert next(p for p in data['players'] if p['id'] == '0')['revive'] is None
    wiped = party()
    wiped['players']['1']['hp'] = 0.
    tick_party(wiped, .1)
    assert wiped['world']['status'] == 'lost'
    assert all(p['hp'] == 0. for p in wiped['players'].values())
    assert coop.public(wiped, '0', .1)['revive'] is None


def test_withdrawn_living_actor_has_no_self_or_peer_buffs():
    state = party()
    actor = state['players']['1']
    actor.update(withdrawn=True, warmed_until=5.)
    data = coop.public(state, '1', 0.)
    assert data['status'] == 'abandoned' and data['buffs'] == [] and data['revive'] is None
    assert next(p for p in data['players'] if p['id'] == '1')['buffs'] == []


def test_coop_warmed_is_private_to_each_actor_and_survives_json_restart(monkeypatch):
    state = party(helpers=2)
    state['players']['0'].update(hp=50., x=0., z=2.)
    state['players']['1'].update(hp=50., x=6., z=2.)
    state['players']['2'].update(hp=50., x=0., z=3.)
    tick_party(state, .1)
    assert state['players']['0']['hp'] == pytest.approx(50.06)
    assert state['players']['1']['hp'] == 50.
    state['players']['0'].update(x=6., z=3.)
    restored = json.loads(json.dumps(state))
    monkeypatch.setenv('TRIPOTHON_CAMPFIRE_MODE', 'barrier')
    tick_party(restored, .1)
    payload = coop.public(restored, '0', .2)
    actors = {p['id']: p for p in payload['players']}
    assert payload['campfire']['mode'] == 'buff'
    assert [b['id'] for b in actors['0']['buffs']] == ['warmed']
    assert actors['0']['buffs'][0]['remaining'] == pytest.approx(4.9)
    assert actors['1']['buffs'] == []
    assert [b['id'] for b in actors['2']['buffs']] == ['campfire_regeneration', 'warmed']
    assert restored['players']['0']['hp'] == pytest.approx(50.06)
    assert restored['players']['2']['hp'] == pytest.approx(50.12)
    assert 'warmed_until' not in payload and 'revive_progress' not in payload


@pytest.mark.parametrize('warm', [True, False])
@pytest.mark.parametrize('mode', ['barrier', 'buff'])
def test_night_recovery_tuning_only_applies_near_a_lit_fire(mode, warm):
    s = run(mode, elapsed=40., fire_until=100. if warm else 0.)
    enemy = dict(id='strike', x=0., z=3., hp=100., phase='windup', phase_until=40.,
                 target_x=0., target_z=2.)
    if mode == 'barrier' and warm:
        sim.advance_enemy(s, enemy, .1, 1, True)
        assert enemy['phase'] == 'warded'
    else:
        sim.advance_enemy(s, enemy, .1, 1, warm)
        assert enemy['phase_until'] - 40. == pytest.approx(1.275 if mode == 'buff' and warm else .85)


@pytest.mark.parametrize('dx', [.1, .001])
def test_even_small_movement_intents_interrupt_rescue(dx):
    state = party()
    tick_party(state, 1.)
    helper = state['players']['1']
    helper['intent'] = dict(dx=dx, dz=0., sprint=False, at=1.1)
    coop.advance(state, 1.1)
    assert state['players']['0']['revive_progress'] == 0.
    assert state['players']['0']['revive_rate'] == 0.


def test_another_members_new_fire_grants_warmed_before_first_exit_tick():
    state = party(fire=False)
    state['players']['0'].update(hp=100., x=3.9, z=0.)
    state['players']['1'].update(x=0., z=2.)
    coop.apply_input(state, '1', Input(sequence=1, action='fire'), 0.)
    assert state['world']['fire_until'] == 30.
    assert 'warmed_until' not in state['players']['0']
    coop.apply_input(state, '0', Input(sequence=1, dx=1.), 0.)
    coop.advance(state, .1)
    actor = state['players']['0']
    assert actor['x'] > 4.
    assert actor['warmed_until'] == 5.
    assert [b['id'] for b in coop.public(state, '0', .1)['buffs']] == ['warmed']


def test_immediate_exit_after_fire_rescue_preserves_warmed():
    state = party()
    state['players']['0'].update(x=3.9, z=0.)
    state['players']['1'].update(x=3.5, z=0.)
    tick_party(state, 4.)
    assert state['players']['0']['hp'] == 30.
    now = state['world']['last_wall']
    coop.apply_input(state, '0', Input(sequence=1, dx=1.), now)
    coop.advance(state, now + .1)
    assert state['players']['0']['x'] > 4.
    assert [b['id'] for b in coop.public(state, '0', now + .1)['buffs']] == ['warmed']


@pytest.mark.parametrize('mode', ['barrier', 'buff'])
def test_solo_and_coop_api_expose_authoritative_fire_buff_and_rescue_contract(tmp_path, monkeypatch, mode):
    from fastapi.testclient import TestClient
    from server.app import create_app
    from server.tests.social_world import World

    monkeypatch.setenv('TRIPOTHON_CAMPFIRE_MODE', mode)
    w = World(tmp_path)
    try:
        alice, bravo = w.players('alice', 'bravo')
        solo = w.call(alice, '/v1/runs')['id']
        route = '/v1/runs/' + solo
        reply = w.client.post(route + '/input', headers=alice.headers,
                              json=dict(sequence=1, action='fire'))
        assert reply.status_code == 200, reply.text
        data = reply.json()
        assert data['campfire'] == dict(mode=mode, x=0., z=0., radius=4.,
                                       remaining=30., active=True, blocks_monsters=mode == 'barrier')
        assert data['warm'] and data['fire_remaining'] == 30.
        assert data['revive'] is None
        assert [b['id'] for b in data['buffs']] == (['campfire_regeneration', 'warmed'] if mode == 'buff' else [])
        assert not {'warmed_until', 'revive_progress', 'revive_rate'} & data.keys()
        if mode == 'buff':
            assert data['buffs'][0]['cold_immune'] is True
            assert data['buffs'][1]['attack_multiplier'] == 1.1
        w.call(alice, route + '/abandon')
        w.call(alice, '/v1/party')
        invitation = w.call(alice, '/v1/social/invites', username=bravo.name, kind='party')
        w.call(bravo, '/v1/social/invites/' + invitation['id'] + '/accept')
        for actor in (alice, bravo):
            w.presence(actor)
        shared = w.call(alice, '/v1/party/runs')['id']
        route = '/v1/coop/runs/' + shared
        reply = w.client.post(route + '/input', headers=alice.headers,
                              json=dict(sequence=1, action='fire'))
        assert reply.status_code == 200, reply.text
        with w.app.state.db.transaction() as conn:
            saved = json.loads(conn.execute('SELECT state FROM coop_runs WHERE id=?', (shared,)).fetchone()[0])
            saved['players'][alice.id].update(x=0., z=2.)
            saved['players'][bravo.id].update(x=.5, z=2., hp=0.)
            conn.execute('UPDATE coop_runs SET state=? WHERE id=?', (json.dumps(saved), shared))
        w.tick(.2)
        data = w.get(bravo, route)
        players = {p['id']: p for p in data['players']}
        assert data['campfire']['mode'] == mode and data['warm']
        assert players[bravo.id]['buffs'] == data['buffs'] == []
        assert players[bravo.id]['revive'] == data['revive']
        assert bool(players[alice.id]['buffs']) == (mode == 'buff')
        if mode == 'buff':
            assert data['revive']['progress'] == pytest.approx(.05)
            assert data['revive']['remaining'] == pytest.approx(3.8)
            assert data['revive']['active'] and data['revive']['speed_multiplier'] == 2.
        else:
            assert data['revive'] is None
        # A real app restart with a different environment preserves the persisted rules.
        monkeypatch.setenv('TRIPOTHON_CAMPFIRE_MODE', 'buff' if mode == 'barrier' else 'barrier')
        restarted = create_app(w.settings, clock=lambda: w.now[0], worker_enabled=False)
        with TestClient(restarted) as second:
            reply = second.get(route, headers=bravo.headers)
            assert reply.status_code == 200, reply.text
            assert reply.json()['campfire']['mode'] == mode
            assert reply.json()['revive'] == data['revive']
    finally:
        w.close()
