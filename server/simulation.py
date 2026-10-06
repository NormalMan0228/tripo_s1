"""Server-owned survival state. Clients send intent, never position, time, loot, or score."""
import math
import random
from copy import deepcopy
from decimal import Decimal
from . import navigation, catalog, campaign, survival_maps

ITEMS = {'wood': '목재', 'stone': '돌', 'berry': '열매', 'fiber': '섬유',
         'axe': '돌도끼', 'spear': '창', 'soup': '열매 수프', 'bandage': '붕대'}
RECIPES = {'axe': {'wood': 3, 'stone': 2}, 'spear': {'wood': 4, 'stone': 2},
           'soup': {'berry': 3, 'wood': 1}, 'bandage': {'fiber': 3}}

def clear_position(s, x, z, radius=.85):
    return math.hypot(x,z)>=1.05 and all(math.hypot(x-o['x'],z-o['z'])>=o['radius']+.25 for o in s.get('obstacles',[])) and all(n['kind'] not in ('tree', 'stone') or n['quantity'] <= 0 or
               math.hypot(x-n['x'], z-n['z']) >= radius for n in s['nodes'])


def clear_swing(s, a, b):
    return navigation.segment_open(s,(a['x'],a['z']),(b['x'],b['z']),.55,0)


def map_bounds(s):
    """Half extent of the walkable square (catalog layout; old prototype maps used 18)."""
    return catalog.MAPS.get(s.get('map_id','forest'),catalog.MAPS['forest']).get('bounds',18.)


def push_clear(s, actor):
    """Move an actor that a new map layout left inside a solid to the nearest open spot."""
    if clear_position(s, actor['x'], actor['z']):
        return
    limit=map_bounds(s)
    for step in range(1,400):
        angle,distance=step*2.39996,.3*math.sqrt(step)
        x,z=actor['x']+math.cos(angle)*distance,actor['z']+math.sin(angle)*distance
        if abs(x)<=limit and abs(z)<=limit and clear_position(s,x,z):
            actor['x'],actor['z']=round(x,3),round(z,3)
            return


def ensure_layout(s):
    """Saved runs from an older map layout adopt the current obstacles and hazards."""
    region=catalog.MAPS.get(s.get('map_id','forest'),catalog.MAPS['forest'])
    version=region.get('layout_version')
    if not version or s.get('layout_version')==version:
        return False
    s['obstacles'],s['hazards'],s['layout_version']=deepcopy(region['obstacles']),deepcopy(region['hazards']),version
    blockers=s['obstacles']+s['hazards']
    extent=region.get('node_extent',17.)
    for node in s.get('nodes',[]):
        if all(math.hypot(node['x']-o['x'],node['z']-o['z'])>=o['radius']+1.2 for o in blockers): continue
        for step in range(1,600):
            angle,distance=step*2.39996,.3*math.sqrt(step)
            x,z=node['x']+math.cos(angle)*distance,node['z']+math.sin(angle)*distance
            if (abs(x)<=extent and abs(z)<=extent and math.hypot(x,z)>=4.5
                    and all(math.hypot(x-o['x'],z-o['z'])>=o['radius']+1.6 for o in blockers)
                    and all(m is node or math.hypot(x-m['x'],z-m['z'])>=2.2 for m in s['nodes'])):
                node['x'],node['z']=round(x,2),round(z,2)
                break
    for enemy in s.get('enemies',[]): push_clear(s,enemy)
    if 'x' in s: push_clear(s,s)
    return True


def move_actor(s, actor, dx, dz, speed, dt, radius=.85):
    length = max(1., math.hypot(dx, dz))
    distance_x,distance_z=dx/length*speed*dt,dz/length*speed*dt
    # Bounded substeps stop a lagged sprint from tunneling across a whole trunk.
    steps=max(1,math.ceil(max(abs(distance_x),abs(distance_z))/.25))
    limit=map_bounds(s)
    for _ in range(steps):
        nx = max(-limit, min(limit, actor['x'] + distance_x/steps))
        nz = max(-limit, min(limit, actor['z'] + distance_z/steps))
        if clear_position(s, nx, actor['z'], radius): actor['x'] = nx
        if clear_position(s, actor['x'], nz, radius): actor['z'] = nz


def seek_enemy(s,enemy,goal,speed,dt):
    here=(enemy['x'],enemy['z'])
    if navigation.segment_open(s,here,goal):
        enemy['_route']=[]
        aim=goal
    else:
        previous=enemy.get('_goal',goal)
        if (not enemy.get('_route') or s['elapsed']>=enemy.get('_route_until',0) or
                math.hypot(previous[0]-goal[0],previous[1]-goal[1])>1.5):
            enemy['_route']=navigation.path_to(s,here,goal)
            enemy['_route_until']=s['elapsed']+1.5
            enemy['_goal']=list(goal)
        while enemy['_route'] and math.hypot(enemy['_route'][0][0]-here[0],enemy['_route'][0][1]-here[1])<.32:
            enemy['_route'].pop(0)
        aim=enemy['_route'][0] if enemy['_route'] else goal
    dx,dz=aim[0]-here[0],aim[1]-here[1]
    length=max(.01,math.hypot(dx,dz))
    move_actor(s,enemy,dx/length,dz/length,min(speed,length/max(dt,.001)),dt)


def advance_enemy(s, enemy, dt, day, warm):
    """A fixed, visible strike target gives the player time to step out of danger."""
    now = s['elapsed']
    enemy.setdefault('phase', 'chase')
    enemy.setdefault('phase_until', 0.)
    if warm:
        enemy['phase'] = 'warded'
        distance = max(.01, math.hypot(enemy['x'], enemy['z']))
        if distance < 4.8:
            move_actor(s, enemy, enemy['x']/distance, enemy['z']/distance, 2.8, dt)
        elif distance>5.2:
            seek_enemy(s,enemy,(enemy['x']/distance*5,enemy['z']/distance*5),1.2+day*.08,dt)
        else:
            seek_enemy(s,enemy,(enemy['x']-enemy['z']/distance,enemy['z']+enemy['x']/distance),.6,dt)
        return
    behavior = enemy.get('behavior', 'melee')
    if enemy['phase'] == 'windup':
        if now >= enemy['phase_until']:
            if behavior == 'charge':
                # The dash is committed to the announced line; it passes the marked spot and overshoots.
                dx, dz = enemy['target_x']-enemy['x'], enemy['target_z']-enemy['z']
                length = max(.01, math.hypot(dx, dz))
                enemy.update(phase='charge', phase_until=now+3., _charge_dx=dx/length, _charge_dz=dz/length,
                             _charge_left=length+enemy.get('charge_overshoot', 2.), _charge_hit=False)
                return
            if math.hypot(s['x']-enemy['target_x'], s['z']-enemy['target_z']) < enemy.get('impact',1.35) and clear_swing(s,enemy,s):
                s['hp'] -= enemy.get('damage',8.)
            enemy['phase'] = 'recover'
            enemy['phase_until'] = now + .85
        return
    if enemy['phase'] == 'charge':
        advance_charge(s, enemy, dt, now)
        return
    if enemy['phase'] == 'recover':
        if now >= enemy['phase_until']: enemy['phase'] = 'chase'
        return
    enemy['phase']='chase'
    vx, vz = s['x']-enemy['x'], s['z']-enemy['z']
    distance = max(.01, math.hypot(vx, vz))
    if distance < enemy.get('reach',1.8) and clear_swing(s,enemy,s):
        if behavior == 'spore':
            # A spore puff is centred on the creature itself: step out of the ring to dodge.
            enemy.update(phase='windup', phase_until=now+enemy.get('windup',1.), target_x=enemy['x'], target_z=enemy['z'])
        else:
            enemy.update(phase='windup', phase_until=now+enemy.get('windup',.65), target_x=s['x'], target_z=s['z'])
        return
    seek_enemy(s,enemy,(s['x'],s['z']),enemy.get('speed',1.2+day*.08),dt)


def advance_charge(s, enemy, dt, now):
    """Straight committed dash; hits the player once, stops at obstacles, then a long stunned recovery."""
    step = min(enemy['_charge_left'], enemy.get('charge_speed', 7.)*dt)
    before = (enemy['x'], enemy['z'])
    move_actor(s, enemy, enemy['_charge_dx'], enemy['_charge_dz'], enemy.get('charge_speed', 7.), step/max(enemy.get('charge_speed', 7.),.01))
    moved = math.hypot(enemy['x']-before[0], enemy['z']-before[1])
    enemy['_charge_left'] -= step
    if not enemy['_charge_hit'] and math.hypot(s['x']-enemy['x'], s['z']-enemy['z']) < enemy.get('impact', 1.1):
        enemy['_charge_hit'] = True
        s['hp'] -= enemy.get('damage', 12.)
    if enemy['_charge_left'] <= 1e-6 or moved < step*.35 or enemy['_charge_hit'] or now >= enemy['phase_until']:
        enemy.update(phase='recover', phase_until=now+enemy.get('stun', 1.4))


def night_enemies(s, day):
    """Server-chosen roster for one night: species per map/day, count per difficulty, swarms, variant art id."""
    region, tuning = catalog.rules(s)
    map_id = s.get('map_id', 'forest')
    pool = catalog.night_species(map_id, day)
    variant = catalog.creature_variant(map_id)
    enemies = []
    for i in range(max(1, min(2+day//3, 4)+tuning['extra_enemies'])):
        angle = i*2.4+day
        kind = pool[(i+day-1) % len(pool)]
        stats = catalog.ENEMIES[kind]
        for member in range(stats.get('swarm', 1)):
            spread = angle+member*.22
            enemy = {'id': f'e{day}_{i}' + (f'_{member}' if member else ''), 'x': math.cos(spread)*14,
                     'z': math.sin(spread)*14, 'kind': kind, 'variant': variant, 'behavior': stats['behavior'],
                     'hp': stats['hp']*tuning['hp'], 'max_hp': stats['hp']*tuning['hp'],
                     'damage': stats['damage']*tuning['damage'],
                     'speed': (stats['speed']+(day-1)*.08)*tuning['speed'],
                     'windup': stats['windup'], 'reach': stats['reach'], 'impact': stats['impact'],
                     'phase': 'chase', 'phase_until': 0.}
            if stats['behavior'] == 'charge':
                enemy.update(charge_speed=stats['charge_speed']*tuning['speed'],
                             charge_overshoot=stats['charge_overshoot'], stun=stats['stun'])
            for offset in range(16):
                if clear_position(s, enemy['x'], enemy['z']):
                    break
                enemy['x'], enemy['z'] = math.cos(spread+offset*.25)*14, math.sin(spread+offset*.25)*14
            enemies.append(enemy)
    return enemies

def new_run(seed, now, day_seconds, map_id='forest', difficulty='standard'):
    rng = random.Random(seed)
    region=catalog.MAPS[map_id]
    tuning=catalog.DIFFICULTIES[difficulty]
    # Reserve camp and the four introductory resources before placing the forest.
    nodes = [dict(id=f'n{i}', kind=k, x=x, z=z, quantity=6, regrow_at=0)
             for i,(k,x,z) in enumerate([('tree', 3, 0), ('berry', -3, 0), ('stone', 0, -3), ('fiber', 0, 3)])]
    extent=region.get('node_extent',17.)
    cycle=survival_maps.RESOURCE_CYCLE[map_id]
    for i in range(4,60):
        kind = cycle[i % len(cycle)]
        for attempt in range(5000):
            x, z = round(rng.uniform(-extent,extent),2), round(rng.uniform(-extent,extent),2)
            # Trails stay open: trunks and rock piles never grow on a path.
            if (math.hypot(x,z)>=survival_maps.CAMP_CLEAR and all(math.hypot(x-n['x'],z-n['z'])>=2.2 for n in nodes)
                and all(math.hypot(x-o['x'],z-o['z'])>=o['radius']+1.6 for o in region['obstacles']+region['hazards'])
                and (kind not in ('tree','stone') or not survival_maps.on_path(map_id,x,z,.9))):
                break
        else:
            raise RuntimeError('forest_layout_exhausted')
        nodes.append({'id': f'n{i}', 'kind': kind, 'x': round(x, 2), 'z': round(z, 2),
                      'quantity': 6 if kind == 'tree' else 4, 'regrow_at': 0})
    return {'map_id':map_id,'difficulty':difficulty,'obstacles':deepcopy(region['obstacles']),
            'hazards':deepcopy(region['hazards']), 'layout_version':region.get('layout_version'), 'x': 0., 'z': 1.4, 'hp': 100., 'hunger': 100., 'stamina': 100., 'sprinting': False,
            'sprint_recover_at': 0., 'elapsed': 0., 'last_wall': now,
            'day_seconds': day_seconds, 'inventory': {'wood': 5 if difficulty=='relaxed' else 3, 'stone': 0, 'berry': 6 if difficulty=='relaxed' else 4, 'fiber': 0,
            'axe': 0, 'spear': 0, 'soup': 0, 'bandage': 0}, 'nodes': nodes, 'enemies': [],
            'fire_until': 0., 'harvested': 0, 'kills': 0, 'last_action': -10., 'last_attack': -10.,
            'spawned_night': 0, 'sequence': 0, 'message': '낮에는 채집하고 밤에는 모닥불 곁을 지키세요.', 'status': 'active'}

def advance(s, now, dx=0., dz=0., sprint=False):
    # Disconnection pauses the prototype simulation; missed time cannot be banked for movement.
    dt = max(0., min(now - s['last_wall'], 0.3))
    s['last_wall'] = now
    if s['status'] != 'active':
        return
    ensure_layout(s)
    # Old saved prototypes started inside the now-solid fire pit.
    if math.hypot(s['x'],s['z'])<1.05:
        length=math.hypot(s['x'],s['z'])
        if length<.001: s['x'],s['z']=0.,1.06
        else: s['x'],s['z']=s['x']/length*1.06,s['z']/length*1.06
    s['elapsed'] += dt
    region,tuning=catalog.rules(s)
    on_ice=any(h['kind']=='ice' and math.hypot(s['x']-h['x'],s['z']-h['z'])<h['radius'] for h in s.get('hazards',[]))
    s.setdefault('stamina', 100.)
    s.setdefault('sprint_recover_at', 0.)
    s['sprinting'] = bool(sprint and math.hypot(dx,dz)>.1 and s['stamina']>1 and s['elapsed']>=s['sprint_recover_at'])
    if s['sprinting']:
        s['stamina'] = max(0.,s['stamina']-22*dt)
        if s['stamina']<=1: s['sprint_recover_at']=s['elapsed']+1.5
    else:
        s['stamina'] = min(100.,s['stamina']+14*dt)
    move_actor(s,s,dx,dz,(6.75 if s['sprinting'] else 4.5)*(.65 if on_ice else 1.),dt)
    s['hunger'] = max(0., s['hunger'] - dt * (0.54 if s['sprinting'] else 0.42)*tuning['hunger'])
    if s['hunger'] == 0:
        s['hp'] -= dt * 3
    day = min(7, int(s['elapsed'] / s['day_seconds']) + 1)
    night = (s['elapsed'] % s['day_seconds']) / s['day_seconds'] >= 0.65
    warm = s['fire_until'] > s['elapsed'] and math.hypot(s['x'], s['z']) < 4.0
    if night:
        if s['spawned_night'] < day:
            s['spawned_night'] = day
            s['enemies'].extend(night_enemies(s, day))
        if not warm:
            s['hp'] -= dt * 0.28*region['cold']*tuning['cold']
        for enemy in s['enemies']:
            advance_enemy(s,enemy,dt,day,warm)
    else:
        s['enemies'] = []
    s['terrain_effect']=''
    for hazard in s.get('hazards',[]):
        if math.hypot(s['x']-hazard['x'],s['z']-hazard['z'])<hazard['radius']:
            s['terrain_effect']=hazard['kind']
            if hazard['kind']=='ember': s['hp']-=dt*2.5*tuning['damage']
            elif hazard['kind']=='ice': s['hunger']=max(0.,s['hunger']-dt*.8)
    for node in s['nodes']:
        if node['quantity'] <= 0 and node['regrow_at'] <= s['elapsed']:
            # Never grow a solid obstacle inside the player or a creature.
            occupied = any(math.hypot(a['x']-node['x'],a['z']-node['z'])<1.1 for a in [s,*s['enemies']])
            if node['kind'] not in ('tree','stone') or not occupied: node['quantity'] = 4
    if s['hp'] <= 0:
        s['hp'], s['status'] = 0., 'lost'
        s['message'] = '탐험이 끝났습니다. 마을에서 다시 준비해 보세요.'
    elif s['elapsed'] >= s['day_seconds'] * 7:
        s['status'] = 'won'
        s['message'] = '일곱 번의 밤을 버텼습니다! 별씨를 받고 마을로 돌아가세요.'

def action(s, kind, target=''):
    if s['status'] != 'active':
        return '탐험이 이미 종료되었습니다.'
    now, inv = s['elapsed'], s['inventory']
    if now-s['last_action'] < 0.35:
        return '잠시 후 다시 시도해 주세요.'
    s['last_action'] = now
    if kind == 'harvest':
        node = next((n for n in s['nodes'] if n['id'] == target), None)
        if node is None or node['quantity'] <= 0:
            return '채집할 자원이 없습니다.'
        if math.hypot(s['x']-node['x'], s['z']-node['z']) > 2.3:
            return '조금 더 가까이 다가가세요.'
        item = {'tree': 'wood', 'stone': 'stone', 'berry': 'berry', 'fiber': 'fiber'}[node['kind']]
        amount = min(node['quantity'], 2 if item == 'wood' and inv['axe'] else 1)
        if sum(inv.values()) + amount > 80:
            return '탐험 가방이 가득 찼습니다.'
        node['quantity'] -= amount
        node['regrow_at'] = now + s['day_seconds'] * 2
        inv[item] += amount
        s['harvested'] += amount
        return f'{ITEMS[item]} +{amount}'
    if kind == 'eat':
        if s['hunger']>=99 and s['hp']>=99: return '이미 배가 부르고 건강합니다.'
        if target and target not in ('soup','berry'): return '먹을 수 없는 물건입니다.'
        item = target or ('soup' if inv['soup'] > 0 else 'berry')
        if inv[item] <= 0:
            return '먹을 것이 없습니다. 열매를 채집하세요.'
        inv[item] -= 1
        s['hunger'] = min(100., s['hunger'] + (50 if item == 'soup' else 20))
        s['hp'] = min(100., s['hp'] + (8 if item == 'soup' else 2))
        return f'{ITEMS[item]}를 먹었습니다.'
    if kind == 'heal':
        if s['hp']>=99: return '체력이 충분합니다. 붕대를 아껴 두세요.'
        if inv['bandage'] < 1:
            return '섬유 세 개로 붕대를 만들어 보세요.'
        inv['bandage'] -= 1
        s['hp'] = min(100., s['hp'] + 30)
        return '붕대로 체력을 회복했습니다.'
    if kind == 'craft':
        recipe = RECIPES.get(target)
        if not recipe:
            return '알 수 없는 제작법입니다.'
        if target in ('axe','spear') and inv[target]:
            return '이미 이 도구를 갖고 있습니다.'
        if any(inv[k] < v for k,v in recipe.items()):
            return '제작 재료가 부족합니다.'
        for k,v in recipe.items():
            inv[k] -= v
        inv[target] += 1
        s.setdefault('crafted',{})[target]=s.get('crafted',{}).get(target,0)+1
        return f'{ITEMS[target]} 제작 완료'
    if kind == 'fire':
        if math.hypot(s['x'], s['z']) > 3:
            return '중앙 야영지로 돌아가세요.'
        if inv['wood'] < 2:
            return '목재 두 개가 필요합니다.'
        if s['fire_until']-now>60:
            return '불이 충분히 타고 있습니다. 목재를 아껴 두세요.'
        inv['wood'] -= 2
        s['fire_until'] = min(max(now, s['fire_until']) + 30, now + 90)
        s['fires']=s.get('fires',0)+1
        return '모닥불을 피웠습니다. 주변에서는 밤의 위협을 피할 수 있어요.'
    if kind == 'attack':
        if now-s['last_attack'] < 0.7:
            return '다음 공격을 준비 중입니다.'
        s['last_attack'] = now
        enemy = min((e for e in s['enemies'] if clear_swing(s,s,e)), key=lambda e: math.hypot(e['x']-s['x'],e['z']-s['z']), default=None)
        if enemy is None or math.hypot(enemy['x']-s['x'],enemy['z']-s['z']) > 2.6:
            return '가까운 적이 없습니다.'
        enemy['hp'] -= 25 if inv['spear'] else 10
        # Successful hits interrupt a telegraphed strike briefly.
        enemy.update(phase='recover',phase_until=now+.4)
        if enemy['hp'] <= 0:
            s['enemies'].remove(enemy)
            s['kills'] += 1
        return '창 공격!' if inv['spear'] else '맨손 공격!'
    return '허용되지 않은 행동입니다.'

def public_state(s):
    data = {k:v for k,v in s.items() if k not in ('last_wall','last_action','last_attack')}
    data['enemies']=[{k:v for k,v in e.items() if not k.startswith('_')} for e in s['enemies']]
    data['map_id']=s.get('map_id','forest')
    data['difficulty']=s.get('difficulty','standard')
    data['reward_multiplier']=catalog.combined_multiplier(s)
    data['obstacles']=s.get('obstacles',[])
    data['hazards']=s.get('hazards',[])
    data['day'] = min(7, int(s['elapsed']/s['day_seconds'])+1)
    data['night'] = s['elapsed'] % s['day_seconds'] / s['day_seconds'] >= 0.65
    data['day_progress'] = s['elapsed'] % s['day_seconds'] / s['day_seconds']
    data['fire_remaining'] = max(0., s['fire_until']-s['elapsed'])
    data['stamina'] = s.get('stamina',100.)
    data['sprinting'] = s.get('sprinting',False)
    data['warm'] = data['fire_remaining']>0 and math.hypot(s['x'],s['z'])<4
    data['phase_remaining'] = max(0.,((1 if data['night'] else .65)-data['day_progress'])*s['day_seconds'])
    data['action_cooldown'] = max(0.,.35-(s['elapsed']-s['last_action']))
    data['attack_cooldown'] = max(0.,.7-(s['elapsed']-s['last_attack']))
    data['story']=campaign.progress(s)
    return data

def reward(s):
    if s['status'] != 'won':
        return 0
    base=min(100, 35 + s['harvested']//4 + s['kills']*2 + int(s['hp']//10))
    return math.floor(Decimal(base)*Decimal(str(catalog.combined_multiplier(s))))
