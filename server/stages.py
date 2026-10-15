"""Expedition stage clock: one stage is one day (day, then night), each longer than the last.

A staged run (simulation.new_run) records its own rules, so a saved run keeps them:
  stage_base   seconds of stage 1 (settings.day_seconds, 90 on the servers players use)
  stage_count  stages on its map (tutorial 1, forest 3, quarry 5, frost 7)
  boss         species that ends the last night (None: no boss)
  tutorial     the tutorial's rules (cleared by its requirements, the player cannot fall)
Stage n lasts stage_base * (1 + (n-1)/3): 90, 120, 150, ... seconds. Night is the last 35% of a
stage (progress >= .65). On a map with a boss (and on the tutorial) the last night has no time
limit: it holds at OPEN_NIGHT_HOLD progress until the boss falls (or the requirements are met).

Runs saved before stages (no stage_count) keep the old rules: seven days of day_seconds each, won
when the seventh night ends. They read as seven stages of equal length.
"""
NIGHT_FROM = .65
OPEN_NIGHT_HOLD = .82
GROWTH_STEPS = 3      # each stage is stage_base / GROWTH_STEPS longer than the one before
LEGACY_DAYS = 7


def staged(s):
    return 'stage_count' in s


def count(s):
    return int(s['stage_count']) if staged(s) else LEGACY_DAYS


def length(s, stage):
    if not staged(s):
        return float(s['day_seconds'])
    return float(s['stage_base']) * (GROWTH_STEPS + stage - 1) / GROWTH_STEPS


def start(s, stage):
    """Seconds from the run's start to the dawn of `stage` (stage count+1: the end of the last)."""
    n = stage - 1
    if not staged(s):
        return float(s['day_seconds']) * n
    return float(s['stage_base']) * (2 * GROWTH_STEPS * n + n * (n - 1)) / (2 * GROWTH_STEPS)


def open_end(s):
    """The last night has no time limit (a boss map, the tutorial)."""
    return staged(s) and bool(s.get('boss') or s.get('tutorial'))


def final_night_at(s):
    last = count(s)
    return start(s, last) + NIGHT_FROM * length(s, last)


def clock(s, elapsed=None):
    """Where the run is in its stages: stage (1-based), its length and progress, night, the open
    last night (no limit) and the seconds left in the stage (-1 on the open night)."""
    t = s['elapsed'] if elapsed is None else elapsed
    last = count(s)
    if open_end(s) and t >= final_night_at(s):
        seconds = length(s, last)
        progress = min(OPEN_NIGHT_HOLD, (t - start(s, last)) / seconds)
        return {'stage': last, 'count': last, 'seconds': seconds, 'progress': progress, 'night': True,
                'open_night': True, 'remaining': -1., 'phase_remaining': 0.}
    stage = last
    for k in range(1, last + 1):
        if t < start(s, k + 1):
            stage = k
            break
    seconds = length(s, stage)
    into = t - start(s, stage)
    progress = max(0., min(1., into / seconds))
    night = progress >= NIGHT_FROM
    return {'stage': stage, 'count': last, 'seconds': seconds, 'progress': progress, 'night': night,
            'open_night': False, 'remaining': max(0., seconds - into),
            'phase_remaining': max(0., ((1. if night else NIGHT_FROM) - progress) * seconds)}


def time_up(s):
    """Every stage survived (maps without an open last night, and the legacy seven days)."""
    return not open_end(s) and s['elapsed'] >= start(s, count(s) + 1)


def completed(s):
    """Stages behind the player: those whose night ended, the last one once the run is won."""
    if s.get('status') == 'won':
        return count(s)
    return clock(s)['stage'] - 1
