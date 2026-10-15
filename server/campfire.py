"""Opt-in campfire survivor buffs; saved runs own their mode and simulation clock."""
import math
import os


RADIUS = 4.0
HP_PER_SECOND = .6
STAMINA_PER_SECOND = 4.0
WARMED_SECONDS = 5.0
WARMED_ATTACK_MULTIPLIER = 1.1
NIGHT_RECOVERY_MULTIPLIER = 1.5
REVIVE_SECONDS = 8.0
REVIVE_FIRE_MULTIPLIER = 2.0
REVIVE_RADIUS = 2.3
REVIVE_HP = 30.0


def configured_mode():
    value = os.getenv('TRIPOTHON_CAMPFIRE_MODE', 'barrier').strip().lower()
    if value not in ('barrier', 'buff'):
        raise ValueError('TRIPOTHON_CAMPFIRE_MODE must be barrier or buff')
    return value


def mode(world):
    # Runs saved before the feature keep their original rules, even after a restart.
    return world.get('campfire_mode', 'barrier')


def in_radius(world, actor=None):
    actor = world if actor is None else actor
    return world['fire_until'] > world['elapsed'] and math.hypot(actor['x'], actor['z']) < RADIUS


def living(world, actor):
    return world['status'] == 'active' and actor['hp'] > 0 and not actor.get('withdrawn', False)


def advance(s, dt):
    if mode(s) != 'buff' or not living(s, s):
        return
    if in_radius(s):
        s['warmed_until'] = s['elapsed'] + WARMED_SECONDS
        s['hp'] = min(100., s['hp'] + HP_PER_SECOND * dt)
        s['stamina'] = min(100., s.get('stamina', 100.) + STAMINA_PER_SECOND * dt)


def warmed_remaining(world, actor=None):
    actor = world if actor is None else actor
    if mode(world) != 'buff' or not living(world, actor):
        return 0.
    return max(WARMED_SECONDS if in_radius(world, actor) else 0.,
               actor.get('warmed_until', 0.) - world['elapsed'])


def attack_multiplier(s):
    return WARMED_ATTACK_MULTIPLIER if warmed_remaining(s) > 0 else 1.


def recovery_seconds(s, seconds):
    # Called only by the night enemy loop, after a strike or charge. No spawn/AI changes.
    return seconds * (NIGHT_RECOVERY_MULTIPLIER if mode(s) == 'buff' and in_radius(s) else 1.)


def advance_revives(state, now, dt, presence_seconds, intent_seconds, clear_swing):
    """Stationary nearby teammates help automatically; multiple helpers do not stack."""
    world, players = state['world'], state['players']
    if mode(world) != 'buff' or world['status'] != 'active':
        return
    helpers = [(key, p) for key, p in players.items()
               if living(world, p) and now - p['last_seen'] < presence_seconds
               and not (now - p['intent']['at'] <= intent_seconds
                        and math.hypot(p['intent']['dx'], p['intent']['dz']) > 0.)]
    for key, actor in players.items():
        actor['revive_rate'] = 0.
        if actor['hp'] > 0 or actor['withdrawn'] or now - actor['last_seen'] >= presence_seconds:
            actor['revive_progress'] = 0.
            continue
        rates = [REVIVE_FIRE_MULTIPLIER if in_radius(world, actor) and in_radius(world, helper) else 1.
                 for helper_id, helper in helpers if helper_id != key
                 and math.hypot(actor['x'] - helper['x'], actor['z'] - helper['z']) <= REVIVE_RADIUS
                 and clear_swing(world, helper, actor)]
        rate = max(rates, default=0.)
        actor['revive_rate'] = rate
        actor['revive_progress'] = actor.get('revive_progress', 0.) + dt * rate if rate else 0.
        if actor['revive_progress'] >= REVIVE_SECONDS - 1e-9:
            actor.update(hp=REVIVE_HP, revive_progress=0., revive_rate=0., warmed_until=0.,
                         sprinting=False, intent={'dx': 0., 'dz': 0., 'sprint': False, 'at': now},
                         message='동료의 도움으로 다시 일어났습니다.')


def public_actor(world, actor=None):
    actor = world if actor is None else actor
    warm = in_radius(world, actor)
    buffs = []
    if mode(world) == 'buff' and living(world, actor) and warm:
        buffs.append(dict(id='campfire_regeneration', remaining=max(0., world['fire_until'] - world['elapsed']),
                          hp_per_second=HP_PER_SECOND, stamina_per_second=STAMINA_PER_SECOND,
                          cold_immune=True))
    remaining = warmed_remaining(world, actor)
    if remaining > 0:
        buffs.append(dict(id='warmed', remaining=remaining, attack_multiplier=WARMED_ATTACK_MULTIPLIER))
    revive = None
    if mode(world) == 'buff' and world['status'] == 'active' and actor['hp'] <= 0 and not actor.get('withdrawn'):
        progress, rate = actor.get('revive_progress', 0.), actor.get('revive_rate', 0.)
        revive = dict(progress=min(1., progress / REVIVE_SECONDS), active=rate > 0,
                      remaining=max(0., REVIVE_SECONDS - progress) / rate if rate else None,
                      speed_multiplier=rate)
    return dict(warm=warm, buffs=buffs, revive=revive)


def public_fire(world):
    remaining = max(0., world['fire_until'] - world['elapsed'])
    return dict(mode=mode(world), x=0., z=0., radius=RADIUS, remaining=remaining,
                active=remaining > 0, blocks_monsters=mode(world) == 'barrier')
