import math
from server import simulation as sim


def night_state():
    s=sim.new_run(24,0,60)
    s.update(elapsed=40,last_wall=40,x=7.,z=0.,spawned_night=1)
    s['nodes']=[]
    s['enemies']=[dict(id='test_enemy',x=8.,z=0.,hp=45.,phase='chase',phase_until=0.)]
    return s


def test_telegraph_can_be_dodged_but_stationary_player_is_hit():
    for dodge in (False,True):
        s=night_state()
        sim.advance(s,40.1)
        e=s['enemies'][0]
        assert e['phase']=='windup' and s['hp']>99
        target=(e['target_x'],e['target_z'])
        for i in range(1,9): sim.advance(s,40.1+i*.1,0,1 if dodge else 0,True)
        assert target==(e['target_x'],e['target_z'])
        assert (s['hp']>99) if dodge else (s['hp']<92)
        assert e['phase']=='recover'


def test_spear_interrupts_windup_and_kills_once():
    s=night_state()
    s['inventory']['spear']=1
    sim.advance(s,40.1)
    assert s['enemies'][0]['phase']=='windup'
    assert sim.action(s,'attack')=='창 공격!'
    assert s['enemies'][0]['phase']=='recover' and s['enemies'][0]['hp']==20
    for i in range(1,9): sim.advance(s,40.1+i*.1)
    sim.action(s,'attack')
    assert not s['enemies'] and s['kills']==1 and s['hp']>99
    s['elapsed']+=1
    sim.action(s,'attack')
    assert s['kills']==1


def test_fire_cancels_pending_attack_and_has_exact_safe_radius():
    s=night_state()
    s.update(x=0.,z=0.)
    s['enemies'][0].update(x=1.,z=0.)
    sim.advance(s,40.1)
    sim.action(s,'fire')
    for i in range(1,10): sim.advance(s,40.1+i*.1)
    assert s['hp']>99 and sim.public_state(s)['warm']
    s['x']=4.
    assert not sim.public_state(s)['warm']


def test_sprint_is_bounded_recovers_and_obeys_obstacles():
    s=sim.new_run(6,0,60)
    s.update(x=1.1,z=0.)
    # Intro tree at (3,0) is a solid obstacle even at sprint speed.
    for i in range(1,11): sim.advance(s,i*.1,1,0,True)
    assert s['x']<=3-.85 and 70<s['stamina']<100
    s['nodes']=[]
    for i in range(11,70): sim.advance(s,i*.1,1,1,True)
    assert max(abs(s['x']),abs(s['z']))<=18 and s['sprint_recover_at']>0
    for i in range(70,160): sim.advance(s,i*.1)
    assert s['stamina']==100
    # A disconnected client's time cannot become sprint distance.
    s.update(x=0,z=2)
    origin=(s['x'],s['z'])
    sim.advance(s,1000,1,1,True)
    assert math.hypot(s['x']-origin[0],s['z']-origin[1])<=6.75*.3+1e-6


def test_consumables_not_wasted_and_solid_regrowth_waits():
    s=sim.new_run(1,0,60)
    s['inventory'].update(bandage=1,wood=10)
    sim.action(s,'eat')
    assert s['inventory']['berry']==4
    s['elapsed']+=1
    sim.action(s,'heal')
    assert s['inventory']['bandage']==1
    s['elapsed']+=1
    s['fire_until']=s['elapsed']+80
    sim.action(s,'fire')
    assert s['inventory']['wood']==10
    tree=s['nodes'][0]
    tree.update(quantity=0,regrow_at=0)
    s.update(x=tree['x'],z=tree['z'])
    sim.advance(s,.1)
    assert tree['quantity']==0
    s.update(x=0,z=0)
    sim.advance(s,.2)
    assert tree['quantity']==4


def test_old_saved_runs_upgrade_without_resetting_progress():
    s=sim.new_run(2,0,60)
    for key in ('stamina','sprinting','sprint_recover_at'): s.pop(key)
    s['elapsed']=123
    sim.advance(s,.1,0,1,True)
    assert s['elapsed']==123.1 and s['stamina']<100


def test_unguarded_player_loses_and_cannot_earn_reward():
    s=sim.new_run(10,0,60)
    for i in range(1,4301):
        sim.advance(s,i*.1)
        if s['status']!='active': break
    assert s['status']=='lost' and sim.reward(s)==0
    inventory=s['inventory'].copy()
    sim.action(s,'harvest','n0')
    assert s['inventory']==inventory


def test_tree_blocks_both_player_and_enemy_attacks():
    s=night_state()
    s['enemies'][0].update(x=8.8,z=0.)
    s['nodes']=[dict(id='obstacle',kind='tree',x=7.9,z=0,quantity=4,regrow_at=0)]
    sim.advance(s,40.1)
    assert s['enemies'][0]['phase']=='chase'
    sim.action(s,'attack')
    assert s['enemies'][0]['hp']==45
    assert s['hp']>99


def test_fire_pit_is_solid_and_legacy_center_spawn_can_escape():
    s=sim.new_run(3,0,60)
    for i in range(1,20): sim.advance(s,i*.1,0,-1)
    assert math.hypot(s['x'],s['z'])>=1.05
    s.update(x=0,z=0)
    sim.advance(s,2,1,0)
    assert math.hypot(s['x'],s['z'])>=1.05


def test_fire_wards_enemies_at_edge_instead_of_freezing_at_spawn():
    s=night_state()
    s.update(x=0,z=2,fire_until=100)
    enemy=s['enemies'][0]
    enemy.update(x=14,z=0)
    for i in range(1,100): sim.advance(s,40+i*.1)
    assert 4.5<math.hypot(enemy['x'],enemy['z'])<5.6
    assert enemy['phase']=='warded' and s['hp']==100


def test_lagged_sprint_cannot_tunnel_through_tree():
    s=sim.new_run(4,0,60)
    s.update(x=1.9,z=0)
    sim.advance(s,10,1,0,True)
    assert s['x']<=2.15


def test_selected_food_and_cooldown_preserve_consumables():
    s=sim.new_run(5,0,60)
    s['hunger']=20
    s['inventory']['soup']=1
    sim.action(s,'eat','berry')
    assert s['hunger']==40 and s['inventory']['soup']==1
    assert sim.public_state(s)['action_cooldown']>.3
    sim.action(s,'eat','soup')
    assert s['inventory']['soup']==1
    sim.advance(s,.3)
    sim.advance(s,.4)
    sim.action(s,'eat','soup')
    assert s['hunger']>89 and s['inventory']['soup']==0


def test_enemy_navigates_around_obstacle_instead_of_oscillating():
    s=night_state()
    s.update(x=6,z=0)
    s['enemies'][0].update(x=1.3,z=0)
    s['nodes']=[dict(id='blocker',kind='tree',x=3,z=0,quantity=6,regrow_at=0)]
    enemy=s['enemies'][0]
    went_around=False
    for i in range(1,101):
        sim.advance(s,40+i*.1)
        went_around|=abs(enemy['z'])>.85
        assert math.hypot(enemy['x']-3,enemy['z'])>=.85
    assert went_around and enemy['x']>4 and s['hp']<95
    assert all(not k.startswith('_') for k in sim.public_state(s)['enemies'][0])
