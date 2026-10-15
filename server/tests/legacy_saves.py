"""Runs and party worlds as the code before stages saved them: seven days of day_seconds each, no
stage fields, creatures with only `kind` (server/stages.py legacy rules)."""
from server import coop, simulation

STAGE_KEYS = ('stage_base', 'stage_count', 'boss', 'tutorial')


def legacy_run(seed, day_seconds=60, map_id='forest', difficulty='standard'):
    s = simulation.new_run(seed, 0, day_seconds, map_id, difficulty)
    for key in STAGE_KEYS:
        s.pop(key)
    return s


def legacy_world(seed, members, day_seconds=60, map_id='forest', difficulty='standard'):
    state = coop.new_world(seed, 0, day_seconds, members, map_id, difficulty)
    for key in STAGE_KEYS:
        state['world'].pop(key)
    return state


def strip(state):
    """A saved run or world (its JSON) taken back to the old fields."""
    for key in STAGE_KEYS:
        state.pop(key, None)
    return state
