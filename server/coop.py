"""Three-player survival: one world clock, shared resources/enemies, private actors.

Requests advance one persisted world under the database transaction. Input is an
intent with a short lease, never a client-supplied position or elapsed time.
"""
import math
from copy import deepcopy
from . import simulation, catalog

PLAYER_FIELDS = (
    'x', 'z', 'hp', 'hunger', 'stamina', 'sprinting', 'sprint_recover_at',
    'inventory', 'last_action', 'last_attack', 'sequence', 'message',
    'harvested', 'kills', 'crafted', 'fires', 'terrain_effect',
)
PRESENCE_SECONDS = 10
INTENT_SECONDS = .6


def new_world(seed, now, day_seconds, members, map_id, difficulty):
    world = simulation.new_run(seed, now, day_seconds, map_id, difficulty)
    players = {}
    for index, member in enumerate(members):
        actor = {key: deepcopy(world[key]) for key in PLAYER_FIELDS if key in world}
        actor.update(x=(index-1)*1.3, z=2.0, username=member['username'],
                     avatar=member['avatar'], last_seen=now, withdrawn=False,
                     intent={'dx': 0, 'dz': 0, 'sprint': False, 'at': now})
        players[member['id']] = actor
    return {'world': world, 'players': players}


def actor_view(state, user_id):
    world, actor = state['world'], state['players'][user_id]
    return {**world, **{k: v for k, v in actor.items() if k in PLAYER_FIELDS}}


def spawn_enemies(world, day):
    world['spawned_night'] = day
    world['enemies'].extend(simulation.night_enemies(world, day))


def advance(state, now):
    world, players = state['world'], state['players']
    previous = world['last_wall']
    world['last_wall'] = now
    if world['status'] != 'active':
        return
    if simulation.ensure_layout(world):
        for actor in players.values():
            simulation.push_clear(world, actor)
    # No offline catch-up. A remaining connected member keeps the party running.
    online = any(not p['withdrawn'] and now-p['last_seen'] < PRESENCE_SECONDS for p in players.values())
    dt = max(0., min(now-previous, .3)) if online else 0.
    if dt == 0:
        return
    for user_id, actor in players.items():
        if actor['withdrawn'] or actor['hp'] <= 0:
            actor['sprinting'] = False
            continue
        view = actor_view(state, user_id)
        # Reuse single-player movement, stamina, hunger and terrain rules, but
        # advance enemies and resource respawns exactly once below.
        view.update(last_wall=now-dt, spawned_night=7, enemies=[], nodes=deepcopy(world['nodes']))
        intent = actor['intent'] if now-actor['intent']['at'] <= INTENT_SECONDS else {}
        simulation.advance(view, now, intent.get('dx', 0), intent.get('dz', 0), intent.get('sprint', False))
        actor.update({key: view[key] for key in PLAYER_FIELDS if key in view})
    world['elapsed'] += dt
    day = min(7, int(world['elapsed']/world['day_seconds'])+1)
    night = world['elapsed'] % world['day_seconds']/world['day_seconds'] >= .65
    alive = {key: p for key, p in players.items() if not p['withdrawn'] and p['hp'] > 0}
    if night and alive:
        if world['spawned_night'] < day:
            spawn_enemies(world, day)
        for enemy in world['enemies']:
            target_id = enemy.get('target_user')
            if enemy.get('phase') not in ('windup', 'charge') or target_id not in alive:
                target_id = min(alive, key=lambda key: math.hypot(alive[key]['x']-enemy['x'], alive[key]['z']-enemy['z']))
            enemy['target_user'] = target_id
            actor = alive[target_id]
            view = actor_view(state, target_id)
            warm = world['fire_until'] > world['elapsed'] and math.hypot(actor['x'], actor['z']) < 4
            simulation.advance_enemy(view, enemy, dt, day, warm)
            actor['hp'] = max(0., view['hp'])
    elif not night:
        world['enemies'] = []
    for node in world['nodes']:
        if node['quantity'] <= 0 and node['regrow_at'] <= world['elapsed']:
            occupied = any(math.hypot(a['x']-node['x'], a['z']-node['z']) < 1.1
                           for a in [*players.values(), *world['enemies']] if not a.get('withdrawn'))
            if node['kind'] not in ('tree', 'stone') or not occupied:
                node['quantity'] = 4
    finish(state)


def finish(state):
    world, players = state['world'], state['players']
    if world['status'] != 'active':
        return
    if not any(not p['withdrawn'] and p['hp'] > 0 for p in players.values()):
        world['status'] = 'lost'
    elif world['elapsed'] >= world['day_seconds']*7:
        world['status'] = 'won'
    if world['status'] != 'active':
        world['harvested'] = sum(p['harvested'] for p in players.values())
        world['kills'] = sum(p['kills'] for p in players.values())
        world['hp'] = max((p['hp'] for p in players.values() if not p['withdrawn']), default=0)
        world['reward'] = simulation.reward(world)


def apply_input(state, user_id, body, now):
    actor = state['players'][user_id]
    # Advance using previously accepted intents before recording the new input.
    advance(state, now)
    actor['last_seen'] = now
    actor['sequence'] = body.sequence
    actor['intent'] = dict(dx=body.dx, dz=body.dz, sprint=body.sprint, at=now)
    if body.action and actor['hp'] > 0 and not actor['withdrawn']:
        view = actor_view(state, user_id)
        actor['message'] = simulation.action(view, body.action, body.target)
        actor.update({key: view[key] for key in PLAYER_FIELDS if key in view and key != 'message'})
        state['world']['fire_until'] = view['fire_until']
    finish(state)


def public(state, user_id, now):
    actor = state['players'][user_id]
    data = simulation.public_state(actor_view(state, user_id))
    data.update(coop=True, self_id=user_id,
                status='abandoned' if actor['withdrawn'] else state['world']['status'],
                reward=0 if actor['withdrawn'] else state['world'].get('reward', 0),
                players=[dict(id=key, username=p['username'], avatar=p['avatar'], x=p['x'], z=p['z'],
                              hp=p['hp'], sprinting=p['sprinting'], online=now-p['last_seen'] < PRESENCE_SECONDS,
                              withdrawn=p['withdrawn']) for key, p in state['players'].items()])
    if actor['hp'] <= 0 and data['status'] == 'active':
        data['message'] = '쓰러졌습니다. 동료가 생존하는 동안 관전합니다.'
    return data
