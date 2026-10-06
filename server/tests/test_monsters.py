"""Survival monsters: roster per map/day, regional art variant, boar charge, shroom spore swarm, balance."""
import math

import pytest

from server import catalog, coop, simulation

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


def test_catalog_has_five_species_with_known_behaviours():
    assert set(catalog.ENEMIES) == SPECIES
    for kind, stats in catalog.ENEMIES.items():
        assert stats['behavior'] in ('melee', 'charge', 'spore')
        assert stats['name'] and stats['hp'] > 0 and stats['damage'] > 0 and stats['windup'] >= .6
    assert catalog.ENEMIES['boar']['behavior'] == 'charge' and catalog.ENEMIES['shroom']['swarm'] == 2


@pytest.mark.parametrize('map_id', catalog.MAPS)
@pytest.mark.parametrize('difficulty', catalog.DIFFICULTIES)
def test_night_roster_sends_the_map_variant_and_valid_unique_enemies(map_id, difficulty):
    s = simulation.new_run(5, 0, 60, map_id, difficulty)
    seen = set()
    for day in range(1, 8):
        enemies = simulation.night_enemies(s, day)
        ids = [e['id'] for e in enemies]
        assert len(ids) == len(set(ids)) and not seen & set(ids)
        seen |= set(ids)
        assert all(e['variant'] == catalog.MAPS[map_id]['creature_variant'] == map_id for e in enemies)
        assert all(e['kind'] in catalog.night_species(map_id, day) for e in enemies)
        assert all(simulation.clear_position(s, e['x'], e['z']) for e in enemies)
        slots = {e['id'].split('_')[0] + '_' + e['id'].split('_')[1] for e in enemies}
        for slot in slots:
            members = [e for e in enemies if e['id'] == slot or e['id'].startswith(slot + '_')]
            assert len(members) == catalog.ENEMIES[members[0]['kind']].get('swarm', 1)


@pytest.mark.parametrize('map_id', catalog.MAPS)
def test_every_species_appears_during_a_standard_week(map_id):
    s = simulation.new_run(5, 0, 60, map_id, 'standard')
    kinds = {e['kind'] for day in range(1, 8) for e in simulation.night_enemies(s, day)}
    assert kinds == SPECIES
    first = {e['kind'] for e in simulation.night_enemies(s, 1)}
    assert 'brute' not in first  # the heavy hitter waits for later nights


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
    """The pre-boar/shroom roster (wolf/wisp/brute cycling): total HP and damage per night."""
    tuning = catalog.DIFFICULTIES[difficulty]
    old = {'wolf': (45., 8.), 'brute': (90., 16.), 'wisp': (30., 6.)}
    hp, nights = 0., []
    for day in range(1, 8):
        damage = 0.
        for i in range(max(1, min(2 + day // 3, 4) + tuning['extra_enemies'])):
            species = ['wolf'] if day == 1 and map_id == 'forest' else ['wolf', 'wisp', 'brute']
            kind = species[(i + day + (1 if map_id == 'quarry' else 0)) % len(species)]
            hp += old[kind][0] * tuning['hp']
            damage += old[kind][1] * tuning['damage']
        nights.append(damage)
    return hp, nights


@pytest.mark.parametrize('map_id', catalog.MAPS)
@pytest.mark.parametrize('difficulty', catalog.DIFFICULTIES)
def test_week_threat_stays_within_the_previous_envelope(map_id, difficulty):
    """Seven nights on 탐험 stay winnable: the new roster stays inside the old roster's threat envelope."""
    s = simulation.new_run(5, 0, 60, map_id, difficulty)
    tuning = catalog.DIFFICULTIES[difficulty]
    old_hp, old_nights = old_roster(map_id, difficulty)
    nights = [simulation.night_enemies(s, day) for day in range(1, 8)]
    assert sum(e['hp'] for night in nights for e in night) <= old_hp * 1.05
    assert max(e['damage'] for night in nights for e in night) <= catalog.ENEMIES['brute']['damage'] * tuning['damage']
    volleys = [sum(e['damage'] for e in night) for night in nights]
    assert sum(volleys) <= sum(old_nights) * 1.1
    assert max(volleys) <= max(old_nights) * 1.2 + 1e-6
