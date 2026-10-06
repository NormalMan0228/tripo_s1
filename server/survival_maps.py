"""Authored survival map layouts (server-authoritative geometry).

Each map is a flat playable basin (|x|,|z| <= BOUNDS) whose features are listed once here. The server
derives its solid circles (obstacles), terrain effects (hazards) and keep-out trails from them; the client
dresses the same features (game/maps/survival/layouts.json is an exported copy, kept equal by a test).

Feature kinds -> server geometry:
  pond / boulder / outcrop / blocks / crane / cart / oak / deadtree / pine / crystal / shrine / snow_boulder
      one solid circle (x, z, radius)
  ruin   two pillar circles across the arch (walk through the middle)
  log    two circles along its yaw
  ember / ice   hazard circles (walkable, local effect)
Paths are polylines with a width; solid resource nodes (trees, stones) never spawn on them.
"""
import math
from copy import deepcopy

LAYOUT_VERSION = 'survival-v2'
BOUNDS = 22.0          # player/creature centre clamp
NODE_EXTENT = 20.0     # resources spawn within this square
CAMP_CLEAR = 4.5       # no generated resource inside the camp clearing

# Camp kit (solid, so walkers go around it): two log benches north of the fire pit, firewood and
# supplies south-east / south-west, a tent just outside the clearing. Intro resources sit at (+-3, 0),
# (0, +-3); solo and party spawns at z = 1.4-2.0 stay clear.
def _camp(tent, supplies='supplies'):
    return [
        {'kind': 'bench', 'x': 1.8, 'z': -1.9, 'yaw': 45.0, 'radius': 0.55},
        {'kind': 'bench', 'x': -1.8, 'z': -1.9, 'yaw': -45.0, 'radius': 0.55},
        {'kind': 'firewood', 'x': 2.7, 'z': 2.2, 'yaw': -35.0, 'radius': 0.5},
        {'kind': supplies, 'x': -2.6, 'z': 2.5, 'yaw': 30.0, 'radius': 0.6},
        {'kind': 'tent', 'x': tent[0], 'z': tent[1], 'yaw': tent[2], 'radius': 1.2},
        {'kind': 'sign', 'x': -3.6, 'z': -2.2, 'yaw': 35.0, 'radius': 0.35},
    ]


FEATURES = {
    'forest': _camp((4.6, -4.2, -130.0)) + [
        {'kind': 'pond', 'x': 11.5, 'z': 10.0, 'radius': 3.2},
        {'kind': 'pond', 'x': 14.6, 'z': 7.4, 'radius': 2.3},
        {'kind': 'pond', 'x': 9.0, 'z': 12.9, 'radius': 2.0},
        {'kind': 'boulder', 'x': 8.0, 'z': -11.2, 'radius': 2.0},
        {'kind': 'boulder', 'x': 10.8, 'z': -13.2, 'radius': 1.5},
        {'kind': 'boulder', 'x': -18.2, 'z': -8.6, 'radius': 1.6},
        {'kind': 'ruin', 'x': -11.0, 'z': -14.0, 'yaw': 38.0, 'span': 3.2, 'radius': 0.7},
        {'kind': 'oak', 'x': -15.2, 'z': -2.6, 'radius': 0.9},
        {'kind': 'oak', 'x': 16.4, 'z': -6.8, 'radius': 0.9},
        {'kind': 'oak', 'x': -6.4, 'z': 15.6, 'radius': 0.9},
        {'kind': 'log', 'x': -16.0, 'z': 7.0, 'yaw': 20.0, 'length': 2.6, 'radius': 0.6},
        {'kind': 'log', 'x': 4.6, 'z': -17.6, 'yaw': -64.0, 'length': 2.6, 'radius': 0.6},
    ],
    'quarry': _camp((-4.4, -4.4, 135.0), 'tools') + [
        {'kind': 'ember', 'x': -10.0, 'z': -6.0, 'radius': 2.3},
        {'kind': 'ember', 'x': 10.0, 'z': 8.0, 'radius': 2.4},
        {'kind': 'ember', 'x': -3.0, 'z': 14.5, 'radius': 1.8},
        {'kind': 'outcrop', 'x': -7.0, 'z': 5.0, 'radius': 2.2},
        {'kind': 'outcrop', 'x': 7.0, 'z': -7.0, 'radius': 2.5},
        {'kind': 'outcrop', 'x': -13.0, 'z': -12.0, 'radius': 1.8},
        {'kind': 'outcrop', 'x': 15.5, 'z': -1.5, 'radius': 2.0},
        {'kind': 'outcrop', 'x': -16.5, 'z': 9.5, 'radius': 2.0},
        {'kind': 'blocks', 'x': 5.0, 'z': 12.5, 'radius': 1.2},
        {'kind': 'blocks', 'x': -4.0, 'z': -12.5, 'radius': 1.1},
        {'kind': 'crane', 'x': 12.5, 'z': -13.5, 'radius': 1.3},
        {'kind': 'cart', 'x': 19.0, 'z': 4.0, 'radius': 1.0},
        {'kind': 'deadtree', 'x': -18.5, 'z': -2.0, 'radius': 0.6},
        {'kind': 'deadtree', 'x': 3.0, 'z': 18.5, 'radius': 0.6},
    ],
    'frost': _camp((4.6, -4.2, -130.0), 'sled') + [
        {'kind': 'ice', 'x': -10.0, 'z': -6.0, 'radius': 3.4},
        {'kind': 'ice', 'x': -12.6, 'z': -2.4, 'radius': 2.5},
        {'kind': 'ice', 'x': -7.0, 'z': -8.9, 'radius': 2.2},
        {'kind': 'ice', 'x': 10.0, 'z': 7.0, 'radius': 3.0},
        {'kind': 'snow_boulder', 'x': -8.0, 'z': 7.0, 'radius': 2.0},
        {'kind': 'snow_boulder', 'x': 8.0, 'z': -9.0, 'radius': 2.1},
        {'kind': 'snow_boulder', 'x': 13.0, 'z': -1.0, 'radius': 1.7},
        {'kind': 'snow_boulder', 'x': -17.0, 'z': 12.0, 'radius': 1.8},
        {'kind': 'snow_boulder', 'x': 16.0, 'z': 14.5, 'radius': 1.6},
        {'kind': 'shrine', 'x': 0.0, 'z': -16.5, 'radius': 1.0},
        {'kind': 'crystal', 'x': 5.0, 'z': -14.5, 'radius': 0.9},
        {'kind': 'crystal', 'x': -15.0, 'z': -14.0, 'radius': 1.0},
        {'kind': 'crystal', 'x': 17.5, 'z': -12.0, 'radius': 0.9},
        {'kind': 'pine', 'x': -18.5, 'z': -7.5, 'radius': 0.9},
        {'kind': 'pine', 'x': 18.5, 'z': 5.5, 'radius': 0.9},
        {'kind': 'snowman', 'x': -5.5, 'z': -5.2, 'radius': 0.45},
        {'kind': 'snowman', 'x': 14.0, 'z': 9.6, 'radius': 0.45},
    ],
}

# Trails start at the edge of the camp clearing (r ~3.6) and lead to each landmark.
PATHS = {
    'forest': [
        {'width': 1.5, 'points': [[-2.4, -2.9], [-6.0, -8.0], [-10.2, -12.9], [-12.4, -15.6], [-14.0, -21.5]]},
        {'width': 1.4, 'points': [[3.6, 0.9], [9.0, 1.6], [15.0, 0.4], [21.5, 1.4]]},
        {'width': 1.4, 'points': [[-3.4, 3.6], [-7.0, 8.0], [-11.0, 13.5], [-13.5, 21.5]]},
        {'width': 1.2, 'points': [[3.2, 3.4], [5.4, 5.6], [7.2, 7.0]]},
        {'width': 1.3, 'points': [[0.8, -3.6], [2.6, -8.0], [1.2, -14.0], [1.8, -21.5]]},
    ],
    'quarry': [
        {'width': 2.2, 'points': [[0.4, 3.9], [1.0, 9.0], [0.0, 15.0], [1.0, 21.5]]},
        {'width': 1.8, 'points': [[3.4, -3.4], [3.8, -9.5], [10.0, -14.6]]},
        {'width': 1.6, 'points': [[-3.8, 0.8], [-10.0, 0.5], [-21.5, -0.5]]},
        {'width': 1.4, 'points': [[3.8, 0.9], [8.0, 2.4], [19.0, 1.8]]},
    ],
    'frost': [
        {'width': 1.5, 'points': [[-0.8, -3.8], [-0.6, -8.0], [0.0, -15.0]]},
        {'width': 1.4, 'points': [[3.8, 0.9], [8.0, 2.8], [15.0, 3.6], [21.5, 2.4]]},
        {'width': 1.4, 'points': [[-0.6, 3.9], [-1.5, 9.0], [-2.5, 21.5]]},
        {'width': 1.2, 'points': [[-3.9, -0.9], [-8.5, 1.8], [-15.0, 4.5]]},
    ],
}

# Generated (non-intro) resource kinds cycle through these per map.
RESOURCE_CYCLE = {
    'forest': ['tree', 'berry', 'stone', 'fiber'],
    'quarry': ['stone', 'tree', 'berry', 'stone', 'fiber'],
    'frost': ['tree', 'fiber', 'stone', 'tree', 'berry'],
}

SOLID_KINDS = ('pond', 'boulder', 'outcrop', 'blocks', 'crane', 'cart', 'oak', 'deadtree', 'pine', 'crystal',
               'shrine', 'snow_boulder', 'bench', 'firewood', 'supplies', 'tools', 'sled', 'tent', 'sign', 'snowman')
HAZARD_KINDS = ('ember', 'ice')


def circles(feature):
    """Server solid circles of one feature."""
    kind = feature['kind']
    if kind in SOLID_KINDS:
        return [{'x': feature['x'], 'z': feature['z'], 'radius': feature['radius'], 'kind': kind}]
    if kind in ('ruin', 'log'):
        half = (feature['span'] if kind == 'ruin' else feature['length']) * .5
        if kind == 'log':
            half -= feature['radius'] * .6
        yaw = math.radians(feature['yaw'])
        dx, dz = math.cos(yaw) * half, -math.sin(yaw) * half
        return [{'x': round(feature['x'] + sx * dx, 3), 'z': round(feature['z'] + sx * dz, 3),
                 'radius': feature['radius'], 'kind': kind} for sx in (-1, 1)]
    return []


def obstacles(map_id):
    return [circle for feature in FEATURES[map_id] for circle in circles(feature)]


def hazards(map_id):
    return [{'x': f['x'], 'z': f['z'], 'radius': f['radius'], 'kind': f['kind']}
            for f in FEATURES[map_id] if f['kind'] in HAZARD_KINDS]


def segment_distance(x, z, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    length_sq = max(1e-9, dx * dx + dz * dz)
    t = max(0., min(1., ((x - a[0]) * dx + (z - a[1]) * dz) / length_sq))
    return math.hypot(x - a[0] - t * dx, z - a[1] - t * dz)


def on_path(map_id, x, z, margin=0.):
    for path in PATHS.get(map_id, []):
        points = path['points']
        for a, b in zip(points, points[1:]):
            if segment_distance(x, z, a, b) < path['width'] * .5 + margin:
                return True
    return False


def layout(map_id):
    """Fields merged into catalog.MAPS[map_id]."""
    return {'bounds': BOUNDS, 'node_extent': NODE_EXTENT, 'obstacles': obstacles(map_id),
            'hazards': hazards(map_id), 'paths': deepcopy(PATHS[map_id]), 'layout_version': LAYOUT_VERSION}


def client_export():
    """The copy the Godot client reads (game/maps/survival/layouts.json)."""
    return {'version': LAYOUT_VERSION, 'bounds': BOUNDS, 'node_extent': NODE_EXTENT, 'camp_clear': CAMP_CLEAR,
            'maps': {map_id: {'features': deepcopy(FEATURES[map_id]), 'paths': deepcopy(PATHS[map_id]),
                              'obstacles': obstacles(map_id), 'hazards': hazards(map_id)} for map_id in FEATURES}}
