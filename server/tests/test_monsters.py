"""Survival monsters: roster per map/stage and tier, stand-in art, regional art variant, boar charge,
shroom spore swarm, balance; runs saved before stages keep their old rosters."""
import math

import pytest

from server import catalog, coop, simulation, stages
from server.tests.legacy_saves import legacy_run

SPECIES = {'wolf', 'boar', 'brute', 'wisp', 'shroom'}


def open_field(map_id='forest', difficulty='standard'):
    s = simulation.new_run(3, 0, 60, map_id, difficulty)
    s.update(nodes=[], obstacles=[], hazards=[], elapsed=41., x=8., z=4.)
    return s


def spawn(kind, s, x, z):
    stats = catalog.ENEMIES[kind]
    enemy = dict(stats, id='t_' + kind, kind=kind, x=x, z=z, max_hp=stats['hp'], phase='chase', phase_until=0.)
    return enemy


def run(s, enemy, seconds, dt=.05, move=None):
    for _ in range(int(round(seconds / dt))):
        if move:
            s['x'] += move[0] * dt
            s['z'] += move[1] * dt
        s['elapsed'] += dt
        simulation.advance_enemy(s, enemy, dt, 1, False)


def test_catalog_species_have_known_behaviours_and_todays_art_as_stand_ins():
    assert set(catalog.LEGACY_SPECIES) == SPECIES
    for kind, stats in catalog.ENEMIES.items():
        assert stats['behavior'] in ('melee', 'charge', 'spore')
        assert stats['name'] and stats['hp'] > 0 and stats['damage'] > 0 and stats['windup'] >= .6
        assert stats['stand_in'] in SPECIES and catalog.ENEMIES[stats['stand_in']]['stand_in'] == stats['stand_in']
        if stats['behavior'] == 'charge':
            assert {'charge_speed', 'charge_overshoot', 'stun'} <= set(stats)
    assert catalog.ENEMIES['boar']['behavior'] == 'charge' and catalog.ENEMIES['shroom']['swarm'] == 2


@pytest.mark.parametrize('map_id', catalog.MAPS)
@pytest.mark.parametrize('difficulty', catalog.DIFFICULTIES)
def test_night_roster_sends_species_stand_in_variant_and_valid_unique_enemies(map_id, difficulty):
    s = simulation.new_run(5, 0, 60, map_id, difficulty)
    seen = set()
    for day in range(1, s['stage_count'] + 1):
        enemies = simulation.night_enemies(s, day)
        ids = [e['id'] for e in enemies]
        assert len(ids) == len(set(ids)) and not seen & set(ids)
        seen |= set(ids)
        assert all(e['variant'] == catalog.MAPS[map_id]['creature_variant'] for e in enemies)
        tonight = catalog.night_species(map_id, day, s['difficulty'])
        for e in enemies:
            assert e['species'] in tonight and e['species'] in catalog.ROSTERS[map_id][catalog.ENEMIES[e['species']]['tier']]
            assert e['kind'] == e['stand_in'] == catalog.ENEMIES[e['species']]['stand_in']
            assert e.get('height') == catalog.ENEMIES[e['species']].get('height')
        assert all(simulation.clear_position(s, e['x'], e['z']) for e in enemies)
        slots = {e['id'].split('_')[0] + '_' + e['id'].split('_')[1] for e in enemies}
        for slot in slots:
            members = [e for e in enemies if e['id'] == slot or e['id'].startswith(slot + '_')]
            assert len(members) == catalog.ENEMIES[members[0]['species']].get('swarm', 1)


@pytest.mark.parametrize('map_id', catalog.MAPS)
def test_every_species_of_the_map_appears_during_a_standard_run(map_id):
    s = simulation.new_run(5, 0, 60, map_id, 'standard')
    kinds = {e['species'] for day in range(1, s['stage_count'] + 1) for e in simulation.night_enemies(s, day)}
    assert kinds == {k for tier in catalog.ROSTERS[map_id].values() for k in tier}
    first = {catalog.ENEMIES[e['species']]['tier'] for e in simulation.night_enemies(s, 1)}
    assert first == {'weak'}  # the heavy hitters wait for later nights


@pytest.mark.parametrize('map_id', catalog.MAPS)
def test_public_state_names_the_species_tonight_can_bring(map_id):
    s = simulation.new_run(5, 0, 60, map_id, 'veteran')
    for day in range(1, s['stage_count'] + 1):
        s['elapsed'] = stages.start(s, day) + 10.
        shown = simulation.public_state(s)
        assert shown['day'] == shown['stage'] == day
        assert shown['night_species'] == catalog.night_species(map_id, day, s['difficulty'])
        assert {e['species'] for e in simulation.night_enemies(s, day)} <= set(shown['night_species'])
        assert shown['night_stand_ins'] == {k: catalog.ENEMIES[k]['stand_in'] for k in shown['night_species']}
        # The boss's model is read ahead on its stage, from its dawn.
        assert (catalog.MAPS[map_id]['boss'] in shown['night_species']) == bool(s['boss'] and day == s['stage_count'])


@pytest.mark.parametrize('map_id', [m for m in catalog.MAPS if m != 'tutorial'])
def test_runs_saved_before_stages_keep_their_old_rosters(map_id):
    s = legacy_run(5, 60, map_id, 'veteran')
    for day in range(1, 8):
        enemies = simulation.night_enemies(s, day)
        assert {e['kind'] for e in enemies} <= set(catalog.legacy_night_species(map_id, day))
        assert not any('species' in e or 'stand_in' in e for e in enemies)  # the old saved fields
        s['elapsed'] = (day - 1) * 60 + 10.
        shown = simulation.public_state(s)
        assert shown['day'] == shown['stage'] == day and shown['stage_count'] == 7
        assert shown['night_species'] == list(catalog.legacy_night_species(map_id, day))
        assert not shown['boss_night'] and shown['boss'] is None


def test_public_state_shows_variant_but_hides_charge_internals():
    s = open_field('quarry')
    boar = spawn('boar', s, 8., 0.)
    boar['variant'] = 'quarry'
    s['enemies'] = [boar]
    run(s, boar, 1.)
    assert boar['phase'] == 'charge' and '_charge_dx' in boar
    public = simulation.public_state(s)['enemies'][0]
    assert public['variant'] == 'quarry' and public['phase'] == 'charge'
    assert not any(key.startswith('_') for key in public)


@pytest.mark.parametrize('dodge', [False, True])
def test_boar_charge_is_telegraphed_dodgeable_and_ends_stunned(dodge):
    s = open_field()
    boar = spawn('boar', s, 8., -1.)
    run(s, boar, .05)
    assert boar['phase'] == 'windup' and (boar['target_x'], boar['target_z']) == (8., 4.)
    # Wind-up: the line is fixed; a sidestep of ~2 m clears the 1.1 m impact radius.
    run(s, boar, catalog.ENEMIES['boar']['windup'] + .05, move=(2.4, 0) if dodge else None)
    assert boar['phase'] == 'charge'
    run(s, boar, 1.2)
    assert boar['phase'] == 'recover'
    assert s['hp'] == (100 if dodge else 100 - catalog.ENEMIES['boar']['damage'])
    stunned_until = boar['phase_until']
    assert stunned_until - s['elapsed'] > .8  # a long, punishable recovery
    hp = s['hp']
    run(s, boar, .3)
    assert s['hp'] == hp  # one hit per charge, nothing while stunned


def test_punishing_a_stunned_charger_keeps_its_stun():
    s = open_field()
    boar = spawn('boar', s, 8., 3.)
    s['enemies'] = [boar]
    stun_end = s['elapsed'] + catalog.ENEMIES['boar']['stun']
    boar.update(phase='recover', phase_until=stun_end)
    assert simulation.action(s, 'attack') == '맨손 공격!'
    assert boar['phase'] == 'recover' and boar['phase_until'] == stun_end
    # A hit still pauses a creature whose own recovery is shorter (here: already over).
    boar['phase_until'] = s['elapsed'] - 1.
    s['elapsed'] += .8
    simulation.action(s, 'attack')
    assert boar['phase'] == 'recover' and boar['phase_until'] == pytest.approx(s['elapsed'] + .4)


def test_boar_charge_stops_at_an_obstacle():
    s = open_field()
    s['obstacles'] = [{'x': 8., 'z': 2., 'radius': 1.}]
    s.update(x=8., z=4.6)
    boar = spawn('boar', s, 8., -1.)
    boar.update(phase='windup', phase_until=s['elapsed'], target_x=8., target_z=4.6)
    run(s, boar, 1.2)
    assert boar['phase'] == 'recover' and boar['z'] < 1. and s['hp'] == 100


@pytest.mark.parametrize('step_out', [False, True])
def test_shroom_spore_puff_is_centred_on_itself(step_out):
    s = open_field()
    s.update(x=8., z=1.2)
    shroom = spawn('shroom', s, 8., 0.)
    run(s, shroom, .05)
    assert shroom['phase'] == 'windup'
    assert (shroom['target_x'], shroom['target_z']) == (shroom['x'], shroom['z'])
    run(s, shroom, catalog.ENEMIES['shroom']['windup'] + .05, move=(0, 1.3) if step_out else None)
    assert shroom['phase'] == 'recover'
    assert s['hp'] == (100 if step_out else 100 - catalog.ENEMIES['shroom']['damage'])


def test_coop_charging_boar_keeps_its_announced_target():
    members = [dict(id='a', username='a', avatar={}), dict(id='b', username='b', avatar={})]
    state = coop.new_world(9, 0, 60, members, 'forest', 'standard')
    world = state['world']
    world.update(nodes=[], obstacles=[], hazards=[], elapsed=40., spawned_night=1, fire_until=0., last_wall=0.)
    state['players']['a'].update(x=8., z=5.5, last_seen=0.)
    state['players']['b'].update(x=9.6, z=1.6, last_seen=0.)
    boar = spawn('boar', world, 8., 0.)
    boar.update(phase='windup', phase_until=40.05, target_x=8., target_z=5.5, target_user='a')
    world['enemies'] = [boar]
    for i in range(1, 6):
        coop.advance(state, i * .05)
        if boar['phase'] == 'charge':
            assert boar['target_user'] == 'a'  # b is nearer, but the dash is committed
    assert boar['phase'] in ('charge', 'recover')


def old_roster(map_id, difficulty):
    """The roster before stages (wolf/shroom/boar/brute/wisp pools): HP and damage per night."""
    s = legacy_run(5, 60, map_id, difficulty)
    nights = [simulation.night_enemies(s, day) for day in range(1, 8)]
    return [sum(e['hp'] for e in night) for night in nights], [sum(e['damage'] for e in night) for night in nights]


@pytest.mark.parametrize('map_id', [m for m in catalog.MAPS if m != 'tutorial'])
@pytest.mark.parametrize('difficulty', catalog.DIFFICULTIES)
def test_stage_threat_starts_like_the_old_first_nights_and_grows(map_id, difficulty):
    """Stage 1 is about as hard as the old first night (one slot, a little more health); later
    nights are tougher than the first; one hit (bosses aside) stays within 1.5x the old heaviest blow."""
    s = simulation.new_run(5, 0, 60, map_id, difficulty)
    tuning = catalog.DIFFICULTIES[difficulty]
    old_hp, old_volleys = old_roster(map_id, difficulty)
    nights = [simulation.night_enemies(s, day) for day in range(1, s['stage_count'] + 1)]
    hp = [sum(e['hp'] for e in night) for night in nights]
    volleys = [sum(e['damage'] for e in night) for night in nights]
    assert hp[0] <= old_hp[0] * 1.4 and volleys[0] <= old_volleys[0] * 1.4
    assert all(later > hp[0] for later in hp[1:]) and hp[-1] >= 2 * hp[0]
    assert max(e['damage'] for night in nights for e in night) <= catalog.ENEMIES['brute']['damage'] * 1.5 * tuning['damage']
