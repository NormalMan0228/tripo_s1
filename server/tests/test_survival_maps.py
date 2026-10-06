"""Authored survival layouts: client copy, walkability, bounds, migration of older runs."""
import json
import math
from collections import deque
from pathlib import Path

import pytest

from server import catalog, coop, navigation, simulation, survival_maps

ROOT = Path(__file__).resolve().parents[2]
STEP = .4


def test_client_layout_copy_is_current():
    exported = json.loads((ROOT / 'game/maps/survival/layouts.json').read_text(encoding='utf-8'))
    assert exported == survival_maps.client_export(), 'run tools/export_survival_layouts.py'


def reachable_cells(s):
    """Walk the server's own collision (clear_position) on a fine grid from the spawn point."""
    limit = simulation.map_bounds(s)
    size = int(limit * 2 / STEP) + 1
    def point(i, j): return -limit + i * STEP, -limit + j * STEP
    start = (round((s['x'] + limit) / STEP), round((s['z'] + limit) / STEP))
    seen, queue = {start}, deque([start])
    while queue:
        i, j = queue.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (i + di, j + dj)
            if n in seen or not (0 <= n[0] < size and 0 <= n[1] < size):
                continue
            if simulation.clear_position(s, *point(*n)):
                seen.add(n)
                queue.append(n)
    return [point(i, j) for i, j in seen]


@pytest.mark.parametrize('map_id', catalog.MAPS)
def test_every_resource_and_hazard_is_reachable_from_camp(map_id):
    for seed in (0, 7, 19, 33):
        s = simulation.new_run(seed, 0, 60, map_id)
        cells = reachable_cells(s)
        assert len(cells) > 4000
        for node in s['nodes']:
            # Harvest range is 2.3 m; demand a walkable spot within 2 m of every node.
            assert any(math.hypot(x - node['x'], z - node['z']) <= 2.0 for x, z in cells), (map_id, seed, node)
        for hazard in s['hazards']:
            assert any(math.hypot(x - hazard['x'], z - hazard['z']) < hazard['radius'] for x, z in cells)
        assert any(math.hypot(x, z) < 2.5 for x, z in cells)  # the fire can be lit


@pytest.mark.parametrize('map_id', catalog.MAPS)
def test_trails_are_open_and_obstacles_solid(map_id):
    s = simulation.new_run(4, 0, 60, map_id)
    limit = simulation.map_bounds(s)
    for path in survival_maps.PATHS[map_id]:
        for a, b in zip(path['points'], path['points'][1:]):
            for k in range(21):
                x, z = a[0] + (b[0] - a[0]) * k / 20, a[1] + (b[1] - a[1]) * k / 20
                if max(abs(x), abs(z)) <= limit:
                    assert simulation.clear_position(s, x, z), (map_id, x, z)
    for node in s['nodes'][4:]:
        if node['kind'] in ('tree', 'stone'):
            assert not survival_maps.on_path(map_id, node['x'], node['z'], .9)
    for barrier in s['obstacles']:
        assert not simulation.clear_position(s, barrier['x'], barrier['z'])
        assert not navigation.segment_open(s, (-limit, barrier['z']), (limit, barrier['z']))


def test_larger_bounds_hold_walkers_and_creatures():
    s = simulation.new_run(6, 0, 60, 'forest')
    s.update(nodes=[], x=-6., z=6.)
    for i in range(1, 90):
        simulation.advance(s, i * .1, -1, 1, False)
    assert 18 < max(abs(s['x']), abs(s['z'])) <= survival_maps.BOUNDS
    route = navigation.path_to(s, (0, 6), (20, 20))
    assert route and max(abs(c) for cell in route for c in cell) <= survival_maps.BOUNDS


@pytest.mark.parametrize('map_id', catalog.MAPS)
def test_night_spawns_land_on_open_ground(map_id):
    s = simulation.new_run(2, 0, 60, map_id)
    for day in range(1, 8):
        for enemy in simulation.night_enemies(s, day):
            assert simulation.clear_position(s, enemy['x'], enemy['z']), (map_id, day, enemy['id'])


def test_saved_runs_adopt_the_new_layout():
    s = simulation.new_run(9, 0, 60, 'quarry')
    # A run saved before survival-v2: old obstacle set, no version, walker inside a new outcrop.
    s.pop('layout_version')
    s['obstacles'] = [{'x': -7., 'z': 5., 'radius': 2.2}]
    s['hazards'] = []
    s['nodes'][10].update(x=15.5, z=-1.5)
    s.update(x=15.5, z=-1.0)
    simulation.advance(s, .1)
    assert s['layout_version'] == survival_maps.LAYOUT_VERSION
    assert s['obstacles'] == catalog.MAPS['quarry']['obstacles']
    assert simulation.clear_position(s, s['x'], s['z'])
    for node in s['nodes']:
        assert all(math.hypot(node['x'] - o['x'], node['z'] - o['z']) >= o['radius'] + 1.2
                   for o in s['obstacles'] + s['hazards'])
    # Party worlds migrate once for everybody.
    state = coop.new_world(3, 0, 60, [{'id': 'a', 'username': 'a', 'avatar': {}}], 'frost', 'standard')
    state['world'].pop('layout_version')
    state['world']['obstacles'] = []
    state['players']['a'].update(x=8., z=-9.)
    coop.advance(state, .1)
    assert state['world']['layout_version'] == survival_maps.LAYOUT_VERSION
    assert simulation.clear_position(state['world'], state['players']['a']['x'], state['players']['a']['z'])


def test_camp_kit_leaves_spawns_and_intro_resources_open():
    for map_id in catalog.MAPS:
        s = simulation.new_run(1, 0, 60, map_id)
        assert simulation.clear_position(s, 0, 1.4)
        for i in range(3):
            assert simulation.clear_position(s, (i - 1) * 1.3, 2.)
        kit = [o for o in s['obstacles'] if o['kind'] in ('bench', 'firewood', 'supplies', 'tools', 'sled', 'tent', 'sign')]
        assert len(kit) == 6
        for node in s['nodes'][:4]:
            assert all(math.hypot(node['x'] - o['x'], node['z'] - o['z']) > o['radius'] + .85 for o in kit)
