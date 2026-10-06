import math
import pytest
from server import simulation, catalog, navigation
from server.tests.test_api import world, account, mutation


def test_profile_is_owned_versioned_and_persistent(world):
    app,c,clock=world
    alice=account(c,'wardrobe_alice'); bob=account(c,'wardrobe_bob')
    initial=c.get('/v1/me',headers=alice).json()
    assert initial['profile']['version']==0
    avatar=initial['profile']['avatar'] | {'character':'ranger','coat':'#285f83','headwear':'beret','backpack':False}
    body=mutation(version=0,avatar=avatar)
    response=c.post('/v1/profile',headers=alice,json=body)
    assert response.status_code==200 and response.json()['version']==1
    assert c.post('/v1/profile',headers=alice,json=body).json()==response.json()
    assert c.post('/v1/profile',headers=alice,json=mutation(version=0,avatar=avatar)).status_code==409
    assert c.get('/v1/me',headers=bob).json()['profile']['avatar']['character']=='explorer_b'
    assert c.post('/v1/profile',json=body).status_code==401
    assert c.post('/v1/profile',headers=alice,json=mutation(version=1,avatar=avatar|{'owner_id':'bob'})).status_code==422
    assert c.post('/v1/profile',headers=alice,json=mutation(version=1,avatar=avatar|{'character':'res://private.glb'})).status_code==422
    assert c.get('/v1/me',headers=alice).json()['profile']['avatar']==avatar
    assert c.get('/v1/studio',headers=alice).json()['profile']==response.json()
    assert c.get('/v1/studio',headers=bob).json()['profile']['avatar']['character']=='explorer_b'


def test_expedition_choice_cannot_change_active_run_or_supply_reward(world):
    app,c,clock=world; auth=account(c,'expedition_choices')
    request=mutation(map_id='frost',difficulty='veteran')
    rid=c.post('/v1/runs',headers=auth,json=request).json()['id']
    assert c.post('/v1/runs',headers=auth,json=mutation(map_id='forest',difficulty='relaxed')).json()['id']==rid
    state=c.get('/v1/runs/'+rid,headers=auth).json()
    assert (state['map_id'],state['difficulty'],state['reward_multiplier'])==('frost','veteran',2.08)
    assert c.post('/v1/runs',headers=auth,json=mutation(map_id='frost',difficulty='veteran',reward_multiplier=999)).status_code==422
    assert c.post('/v1/runs',headers=auth,json=mutation(map_id='unknown')).status_code==422
    assert c.post('/v1/runs/'+rid+'/input',headers=auth,json={'sequence':1,'difficulty':'veteran'}).status_code==422
    assert c.get('/v1/me',headers=auth).json()['active_run_summary']['map_id']=='frost'


@pytest.mark.parametrize('map_id',catalog.MAPS)
def test_region_resources_avoid_barriers_and_hazards(map_id):
    for seed in range(40):
        s=simulation.new_run(seed,0,60,map_id,'standard')
        assert len(s['nodes'])==60
        assert simulation.clear_position(s,s['x'],s['z'])
        for node in s['nodes']:
            assert all(math.hypot(node['x']-o['x'],node['z']-o['z'])>=o['radius']+1.5 for o in s['obstacles']+s['hazards'])
        for barrier in s['obstacles']:
            assert not simulation.clear_position(s,barrier['x'],barrier['z'])
            limit=simulation.map_bounds(s)
            assert not navigation.segment_open(s,(-limit,barrier['z']),(limit,barrier['z']))


def test_difficulty_changes_danger_and_server_reward():
    states=[]
    for difficulty in catalog.DIFFICULTIES:
        s=simulation.new_run(12,0,60,'forest',difficulty)
        s['elapsed']=40
        simulation.advance(s,.2)
        states.append(s)
    easy,standard,hard=states
    assert easy['hunger']>standard['hunger']>hard['hunger']
    assert len(easy['enemies'])<len(standard['enemies'])<len(hard['enemies'])
    assert easy['enemies'][0]['damage']<standard['enemies'][0]['damage']<hard['enemies'][0]['damage']
    for s in states: s.update(status='won',hp=100,harvested=20,kills=0)
    assert [simulation.reward(s) for s in states]==[35,50,80]
    hard['map_id']='frost'
    assert simulation.reward(hard)==104
    hard['status']='lost'
    assert simulation.reward(hard)==0


def test_hazards_are_local_and_have_distinct_effects():
    s=simulation.new_run(1,0,60,'quarry')
    s['x'],s['z']=-9,-6
    simulation.advance(s,.2)
    assert s['hp']<100 and s['terrain_effect']=='ember'
    s=simulation.new_run(1,0,60,'frost')
    s['x'],s['z']=-9,-7
    simulation.advance(s,.2,dx=1)
    assert s['hp']==100 and s['hunger']<99.8 and s['terrain_effect']=='ice'
    assert 0<s['x']+9<.9


def test_new_creatures_have_distinct_readable_attack_windows():
    for kind in ('brute','wisp'):
        s=simulation.new_run(1,0,60)
        s['nodes']=[];s.update(elapsed=41,x=4.,z=1.5)
        stats=catalog.ENEMIES[kind]
        e=dict(stats,id='test',kind=kind,x=4.,z=0.,phase='chase',phase_until=0.)
        simulation.advance_enemy(s,e,.1,1,False)
        assert e['phase']=='windup'
        assert e['phase_until']-s['elapsed']==pytest.approx(stats['windup'])
        s['x']+=stats['impact']+.5
        s['elapsed']=e['phase_until']+.1
        simulation.advance_enemy(s,e,.1,1,False)
        assert s['hp']==100

@pytest.mark.parametrize('region,difficulty,expected',[
    ('forest','relaxed',70),('forest','standard',100),('forest','veteran',160),
    ('quarry','relaxed',80),('quarry','standard',115),('quarry','veteran',184),
    ('frost','relaxed',91),('frost','standard',130),('frost','veteran',208),
])
def test_exact_reward_rounding(region,difficulty,expected):
    state=simulation.new_run(1,0,60,region,difficulty)
    state.update(status='won',harvested=1000,hp=100)
    assert simulation.reward(state)==expected
