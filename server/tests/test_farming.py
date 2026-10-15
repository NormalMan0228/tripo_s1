"""Farming rules with injected clocks; HTTP tests use the real transaction/replay path."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from server import economy, homestead
from server.models import LifeAction
from server.tests.test_api import world, account, mutation
from server.tests.test_homestead import get, do


def action(state, name, now, **kwargs):
    return homestead.act(state, LifeAction(**mutation(version=state['version'], action=name, **kwargs)), now)


@pytest.mark.parametrize('crop', homestead.CROPS)
@pytest.mark.parametrize('water', [False, True])
def test_every_crop_stages_and_exact_ripe_boundary(crop, water):
    state = homestead.initial()
    state['bag'][crop+'_seed'] = 1
    start = 1_000_000.
    action(state, 'plant', start, item=crop)
    if water: action(state, 'water', start)
    original = copy.deepcopy(state)
    rule = homestead.CROPS[crop]
    assert sum(rule['stage_seconds'].values()) == rule['seconds']
    rate = 1 if water else .5
    elapsed = 0
    for stage, seconds in rule['stage_seconds'].items():
        plot = homestead.public(state, start+elapsed/rate)['plots'][0]
        assert plot['stage'] == stage
        assert not plot['ready']
        elapsed += seconds
    deadline = start+rule['seconds']/rate
    assert homestead.public(state, deadline-.01)['plots'][0]['stage'] == 'growing'
    ripe = homestead.public(state, deadline)['plots'][0]
    assert ripe['stage'] == 'ripe' and ripe['stage_index'] == 3
    assert ripe['ready'] and ripe['progress'] == 1 and ripe['remaining'] == 0
    assert state == original  # Polling frequency cannot award or consume growth.
    with pytest.raises(homestead.Rejected, match='life_not_ready'):
        action(state, 'harvest', deadline-.01)
    reward = action(state, 'harvest', deadline)['reward']
    assert reward['items'] == {crop: rule['yield']}
    with pytest.raises(homestead.Rejected, match='life_not_ready'):
        action(state, 'harvest', deadline)


def test_watering_preserves_dry_progress_and_polls_do_not_accelerate(world):
    _, c, clock = world
    a = account(c, 'water_progress')
    planted = do(c, a, 'plant', item='turnip').json()
    assert planted['plots'][0]['remaining'] == 180
    clock[0] += 40
    before = get(c, a)
    assert before['plots'][0]['stage'] == 'sprout'
    assert get(c, a) == before
    wet = do(c, a, 'water').json()['plots'][0]
    assert wet['growth_seconds'] == 20 and wet['remaining'] == 70
    assert do(c, a, 'water').json()['detail'] == 'life_already_watered'
    clock[0] += 69.99
    assert do(c, a, 'harvest').status_code == 409
    clock[0] += .01
    assert do(c, a, 'harvest').json()['reward']['items'] == {'turnip': 2}


@pytest.mark.parametrize('offset', [-720, 0, 330, 540, 840])
def test_water_expires_at_pinned_midnight_and_can_be_renewed(world, offset):
    _, c, clock = world
    midnight = 12*86400-offset*60
    clock[0] = midnight-10
    a = account(c, 'midnight_farmer')
    # Registration does not authenticate; this first authenticated request pins the offset.
    a['X-Villagen-UTC-Offset'] = str(offset)
    do(c, a, 'plant', item='pumpkin')
    wet = do(c, a, 'water').json()['plots'][0]
    assert wet['watered_until'] == midnight
    assert wet['remaining'] == 290  # 10 wet seconds + 140/.5 dry seconds.
    a['X-Villagen-UTC-Offset'] = str(840 if offset != 840 else -720)
    clock[0] = midnight
    dry = get(c, a)['plots'][0]
    assert not dry['watered'] and dry['growth_seconds'] == 10
    clock[0] += 20
    dry = get(c, a)['plots'][0]
    assert dry['growth_seconds'] == 20 and dry['remaining'] == 260
    renewed = do(c, a, 'water').json()['plots'][0]
    assert renewed['growth_seconds'] == 20 and renewed['remaining'] == 130
    assert renewed['watered_until'] == midnight+86400
    clock[0] += 130
    assert do(c, a, 'harvest').status_code == 200


def test_offline_growth_crosses_multiple_days_without_extra_wet_credit():
    state = homestead.initial()
    start = homestead.day_end(1_000_000)-10
    action(state, 'plant', start, item='pumpkin')
    action(state, 'water', start)
    dry = homestead.public(state, start+100)['plots'][0]
    assert dry['growth_seconds'] == 55 and not dry['watered']
    ripe = homestead.public(state, start+3*86400)['plots'][0]
    assert ripe['ready'] and ripe['growth_seconds'] == 150


def test_backwards_clock_does_not_duplicate_growth():
    state = homestead.initial()
    action(state, 'plant', 1000, item='turnip')
    action(state, 'water', 1040)
    assert homestead.public(state, 1020)['plots'][0]['growth_seconds'] == 20
    assert homestead.public(state, 1040)['plots'][0]['growth_seconds'] == 20
    assert homestead.public(state, 1050)['plots'][0]['growth_seconds'] == 30


@pytest.mark.parametrize('crop', ['radish', 'potato', 'tomato', 'corn'])
def test_new_seeds_use_existing_shop_and_sale_economy(world, crop):
    _, c, clock = world
    a = account(c, 'new_crop_farmer')
    rule = homestead.CROPS[crop]
    bought = do(c, a, 'buy', item=crop+'_seed').json()
    assert bought['coins'] == 12-rule['seed_cost']
    assert bought['catalog']['shop'][crop+'_seed'] == rule['seed_cost']
    do(c, a, 'plant', item=crop)
    clock[0] += rule['seconds']*2
    do(c, a, 'harvest')
    sold = do(c, a, 'sell', item=crop, quantity=rule['yield']).json()
    income = rule['yield']*rule['price']
    assert sold['coins'] == 12-rule['seed_cost']+income
    assert sold['stars'] == income//3
    assert sold['sell_stars']['cap'] == 15


def test_replay_conflicts_races_and_ownership(world):
    _, c, clock = world
    a = account(c, 'farm_owner')
    b = account(c, 'farm_guest')
    plant = mutation(version=0, action='plant', plot=0, item='turnip')
    first = c.post('/v1/homestead', headers=a, json=plant).json()
    for change in ({'plot':1}, {'action':'water'}, {'item':'carrot'}):
        response = c.post('/v1/homestead', headers=a, json=plant|change)
        assert response.status_code == 409 and response.json()['detail'] == 'request_id_reused'
    assert get(c, b)['plots'][0].get('crop') is None
    clock[0] += 180
    harvest = mutation(version=first['version'], action='harvest', plot=0)
    def send(_): return c.post('/v1/homestead', headers=a, json=harvest).json()
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(send, range(2)))
    assert results[0] == results[1] and results[0]['reward']['items'] == {'turnip':2}
    do(c, a, 'plant', item='carrot')
    assert c.post('/v1/homestead', headers=a, json=harvest).json() == results[0]
    assert c.post('/v1/homestead', headers=a, json=plant).json() == first
    current = get(c, a)
    assert current['bag']['turnip'] == 2 and current['plots'][0]['crop'] == 'carrot'
    assert current['bag']['turnip_seed'] == 2


@pytest.mark.parametrize('name', ['plant', 'water', 'harvest', 'untill'])
def test_all_plot_actions_reject_outside_zone_and_negative_indices(name):
    state = homestead.initial()
    state['plots'][0].update(x=0, z=0)
    with pytest.raises(homestead.Rejected, match='life_not_farmland'):
        action(state, name, 1000, item='turnip')
    body = LifeAction(**mutation(version=0, action=name)).model_copy(update={'plot':-1})
    with pytest.raises(homestead.Rejected, match='life_no_plot'):
        homestead.plot_action(state, body, 1000)


def test_legacy_dry_and_watered_migration_is_repeatable_and_persists(world):
    app, c, clock = world
    a = account(c, 'legacy_farmer')
    get(c, a)
    now = clock[0]
    state = homestead.initial()
    state['plots'] = [
        {'crop':'turnip', 'planted_at':now-60, 'watered':False, 'ready_at':None},
        {'crop':'carrot', 'planted_at':now-200, 'watered':True, 'watered_at':now-40, 'ready_at':now+80},
        {'crop':'pumpkin', 'planted_at':now-400, 'watered':True, 'ready_at':now-1},
        {}, {}, {},
    ]
    with app.state.db.transaction() as conn:
        user_id = conn.execute('SELECT id FROM users WHERE username=?', ('legacy_farmer',)).fetchone()[0]
        conn.execute('INSERT INTO homesteads VALUES (?,?)', (user_id, json.dumps(state)))
    first = get(c, a)
    assert first['plots'][0]['growth_seconds'] == 30
    assert first['plots'][1]['remaining'] == 80
    assert first['plots'][2]['ready']
    assert first['plots'][3] == dict(zip(('x','z'), homestead.STARTER_PLOTS[3]))
    assert get(c, a) == first
    do(c, a, 'water', plot=0)
    clock[0] += 60
    assert do(c, a, 'harvest', plot=0).json()['bag']['turnip'] == 2
    clock[0] += 20
    assert do(c, a, 'harvest', plot=1).json()['bag']['carrot'] == 2
    assert do(c, a, 'harvest', plot=2).json()['bag']['pumpkin'] == 2
    assert get(c, a)['coins'] == state['coins']


def test_legacy_watered_crop_keeps_deadline_across_midnight():
    state = homestead.initial()
    midnight = homestead.day_end(1_000_000)
    state['plots'][0].update(crop='turnip', planted_at=midnight-20,
                            watered=True, watered_at=midnight-10, ready_at=midnight+80)
    assert homestead.public(state, midnight+40)['plots'][0]['remaining'] == 40
    assert homestead.public(state, midnight+80)['plots'][0]['ready']


@pytest.mark.parametrize('amount', [-13, 1.5, True])
def test_leaf_coin_helper_rejects_invalid_changes_atomically(amount):
    state = {'coins':12}
    with pytest.raises(ValueError): economy.change_coins(state, amount)
    assert state['coins'] == 12
