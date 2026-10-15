"""Server-owned expedition definitions. Clients choose IDs, never tuning or rewards."""
from copy import deepcopy
from decimal import Decimal
from . import survival_maps

# Left to right on the expedition window (public_catalog order). One stage is one day (day + night);
# stages grow longer (stages.py). A boss ends the last night of forest, quarry and frost; the tutorial
# ends when its requirements are met and the player cannot fall there.
MAPS = {
    'tutorial': {'creature_variant':'forest','name':'첫 야영지','description':'처음 떠나는 짧은 탐험. 채집하고 도끼를 만들고 불을 피워 첫 밤을 맞아 보세요.',
                 'reward_multiplier':1.,'cold':.5,'stages':1,'boss':None,'tutorial':True,'night_slots':2,'spawn_radius':11.,
                 **survival_maps.layout('tutorial')},
    'forest': {'creature_variant':'forest','name':'솔바람 숲','description':'넉넉한 나무와 열매. 첫 탐험에 어울리는 숲.',
               'reward_multiplier':1.,'cold':1.,'stages':3,'boss':'treant', **survival_maps.layout('forest')},
    'quarry': {'creature_variant':'quarry','name':'노을 채석장','description':'바위 사이를 돌아 탐험하세요. 뜨거운 균열을 조심하세요.',
               'reward_multiplier':1.15,'cold':.7,'stages':5,'boss':'chimera', **survival_maps.layout('quarry')},
    'frost': {'creature_variant':'frost','name':'서리빛 분지','description':'찬 바람과 얼음 웅덩이. 모닥불과 식량을 먼저 준비하세요.',
              'reward_multiplier':1.3,'cold':1.65,'stages':7,'boss':'dragon', **survival_maps.layout('frost')},
}
DIFFICULTIES = {
    'relaxed': {'name':'산책','description':'느린 허기, 약한 적. 지형과 생존을 익히세요.',
                'reward_multiplier':.7,'hunger':.72,'damage':.65,'hp':.8,'speed':.85,'extra_enemies':-1,'cold':.5},
    'standard': {'name':'탐험','description':'기본 생존 규칙. 준비와 전투를 균형 있게.',
                 'reward_multiplier':1.,'hunger':1.,'damage':1.,'hp':1.,'speed':1.,'extra_enemies':0,'cold':1.},
    'veteran': {'name':'개척','description':'더 빠르고 강한 적, 빠른 허기. 보상 1.6배.',
                'reward_multiplier':1.6,'hunger':1.25,'damage':1.4,'hp':1.25,'speed':1.15,'extra_enemies':1,'cold':1.4},
}
# The tutorial always runs on 산책 (simulation.new_run).
TUTORIAL_DIFFICULTY = 'relaxed'
# What clears the tutorial (simulation counters: harvested, fires, kills; crafted tools by name).
TUTORIAL_REQUIREMENTS = (('harvested','자원 채집',6),('axe','도끼 제작',1),('fires','모닥불 피우기',1),('kills','밤의 몬스터 물리치기',2))

# behaviour: melee = telegraphed strike at the player's announced spot; charge = telegraphed straight-line
# dash through the announced spot then a stunned recovery; spore = puff centred on itself (swarm: spawns
# `swarm` bodies per night slot). Each map sends its own creature variant id for the client art.
# stand_in: the species whose model the client shows until this species has its own
# (res://assets/monsters/<species>_<variant>.glb); height: metres the stand-in is scaled to;
# body: extra reach the player's swing gets against a large creature.
# The first five are today's art (and the rosters of runs saved before stages); the rest belong to
# one map each (the tutorial borrows the forest's weak ones), by tier: weak, mid, strong, boss.
ENEMIES = {
    'wolf': {'name':'그림자 늑대','hp':45.,'damage':8.,'speed':1.28,'windup':.65,'reach':1.8,'impact':1.35,'behavior':'melee'},
    'boar': {'name':'가시 멧돼지','hp':60.,'damage':12.,'speed':1.05,'windup':.9,'reach':6.,'impact':1.1,'behavior':'charge',
             'charge_speed':7.,'charge_overshoot':2.,'stun':1.4},
    'brute': {'name':'이끼 수호자','hp':90.,'damage':16.,'speed':.85,'windup':1.15,'reach':2.1,'impact':2.,'behavior':'melee'},
    'wisp': {'name':'불씨 도깨비','hp':30.,'damage':6.,'speed':1.65,'windup':.9,'reach':4.8,'impact':1.15,'behavior':'melee'},
    'shroom': {'name':'버섯 망령','hp':22.,'damage':5.,'speed':1.05,'windup':1.,'reach':1.5,'impact':2.,'behavior':'spore','swarm':2},
    # 솔바람 숲
    'goblin': {'name':'고블린','map':'forest','tier':'weak','stand_in':'wolf','behavior':'melee',
               'hp':40.,'damage':7.,'speed':1.3,'windup':.7,'reach':1.8,'impact':1.35},
    'harpy': {'name':'하피','map':'forest','tier':'weak','stand_in':'wisp','behavior':'melee',
              'hp':30.,'damage':6.,'speed':1.6,'windup':.9,'reach':4.4,'impact':1.15},
    'centipede': {'name':'왕지네','map':'forest','tier':'weak','stand_in':'boar','behavior':'charge',
                  'hp':45.,'damage':9.,'speed':1.1,'windup':.85,'reach':5.5,'impact':1.05,'charge_speed':6.5,'charge_overshoot':1.5,'stun':1.3},
    'werewolf': {'name':'늑대인간','map':'forest','tier':'mid','stand_in':'wolf','height':1.9,'behavior':'melee',
                 'hp':80.,'damage':12.,'speed':1.45,'windup':.65,'reach':2.,'impact':1.5},
    'troll': {'name':'트롤','map':'forest','tier':'mid','stand_in':'brute','height':2.8,'behavior':'melee',
              'hp':120.,'damage':16.,'speed':.9,'windup':1.1,'reach':2.2,'impact':2.},
    'cyclops': {'name':'사이클롭스','map':'forest','tier':'strong','stand_in':'brute','height':3.4,'behavior':'melee',
                'hp':170.,'damage':20.,'speed':.85,'windup':1.2,'reach':2.5,'impact':2.3},
    'treant': {'name':'고목 트렌트','map':'forest','tier':'boss','stand_in':'brute','height':5.,'body':1.2,'behavior':'melee',
               'hp':480.,'damage':22.,'speed':.75,'windup':1.3,'reach':2.9,'impact':2.6},
    # 노을 채석장
    'skeleton': {'name':'해골 병사','map':'quarry','tier':'weak','stand_in':'brute','height':1.7,'behavior':'melee',
                 'hp':40.,'damage':8.,'speed':1.15,'windup':.75,'reach':1.9,'impact':1.4},
    'imp': {'name':'임프','map':'quarry','tier':'weak','stand_in':'wisp','behavior':'melee',
            'hp':28.,'damage':6.,'speed':1.7,'windup':.9,'reach':4.8,'impact':1.15},
    'lizardman': {'name':'리자드맨','map':'quarry','tier':'weak','stand_in':'wolf','behavior':'melee',
                  'hp':50.,'damage':9.,'speed':1.25,'windup':.7,'reach':2.1,'impact':1.4},
    'mimic': {'name':'미믹','map':'quarry','tier':'weak','stand_in':'boar','behavior':'charge',
              'hp':55.,'damage':11.,'speed':.9,'windup':.9,'reach':5.,'impact':1.1,'charge_speed':7.5,'charge_overshoot':1.,'stun':1.6},
    'basilisk': {'name':'바실리스크','map':'quarry','tier':'mid','stand_in':'boar','height':1.4,'behavior':'charge',
                 'hp':95.,'damage':14.,'speed':1.,'windup':.9,'reach':6.,'impact':1.2,'charge_speed':7.,'charge_overshoot':2.,'stun':1.5},
    'naga': {'name':'나가','map':'quarry','tier':'mid','stand_in':'wisp','height':1.9,'behavior':'melee',
             'hp':75.,'damage':12.,'speed':1.35,'windup':.85,'reach':3.6,'impact':1.4},
    'gargoyle': {'name':'가고일','map':'quarry','tier':'mid','stand_in':'brute','height':2.2,'behavior':'melee',
                 'hp':110.,'damage':15.,'speed':1.05,'windup':1.,'reach':2.1,'impact':1.8},
    'minotaur': {'name':'미노타우로스','map':'quarry','tier':'strong','stand_in':'brute','height':2.9,'behavior':'charge',
                 'hp':180.,'damage':22.,'speed':1.,'windup':1.,'reach':7.,'impact':1.4,'charge_speed':8.,'charge_overshoot':2.5,'stun':1.8},
    'mummy_king': {'name':'미라 왕','map':'quarry','tier':'strong','stand_in':'brute','height':2.3,'behavior':'spore',
                   'hp':160.,'damage':18.,'speed':.9,'windup':1.1,'reach':2.2,'impact':2.6},
    'chimera': {'name':'키메라','map':'quarry','tier':'boss','stand_in':'brute','height':3.,'length':4.5,'body':1.3,'behavior':'charge',
                'hp':560.,'damage':24.,'speed':.95,'windup':1.1,'reach':8.,'impact':1.8,'charge_speed':8.5,'charge_overshoot':2.5,'stun':2.2},
    # 서리빛 분지
    'ghoul': {'name':'구울','map':'frost','tier':'weak','stand_in':'wolf','behavior':'melee',
              'hp':42.,'damage':8.,'speed':1.35,'windup':.65,'reach':1.8,'impact':1.35},
    'frost_wraith': {'name':'서리 망령','map':'frost','tier':'weak','stand_in':'wisp','behavior':'melee',
                     'hp':28.,'damage':6.,'speed':1.65,'windup':.9,'reach':4.8,'impact':1.15},
    'ice_shardling': {'name':'얼음 조각병','map':'frost','tier':'weak','stand_in':'shroom','behavior':'spore','swarm':2,
                      'hp':22.,'damage':5.,'speed':1.05,'windup':1.,'reach':1.5,'impact':2.},
    'draugr': {'name':'드라우그','map':'frost','tier':'weak','stand_in':'brute','height':1.9,'behavior':'melee',
               'hp':55.,'damage':10.,'speed':1.,'windup':.9,'reach':2.,'impact':1.6},
    'yeti': {'name':'예티','map':'frost','tier':'mid','stand_in':'brute','height':2.6,'behavior':'melee',
             'hp':120.,'damage':16.,'speed':1.,'windup':1.05,'reach':2.2,'impact':2.},
    'wendigo': {'name':'웬디고','map':'frost','tier':'mid','stand_in':'wolf','height':2.2,'behavior':'charge',
                'hp':85.,'damage':14.,'speed':1.3,'windup':.8,'reach':6.,'impact':1.2,'charge_speed':8.,'charge_overshoot':2.,'stun':1.4},
    'frost_hag': {'name':'서리 마녀','map':'frost','tier':'mid','stand_in':'wisp','height':1.8,'behavior':'spore',
                  'hp':70.,'damage':12.,'speed':1.1,'windup':1.,'reach':2.,'impact':2.4},
    'frost_knight': {'name':'서리 기사','map':'frost','tier':'mid','stand_in':'brute','height':2.1,'behavior':'melee',
                     'hp':110.,'damage':15.,'speed':1.,'windup':.85,'reach':2.1,'impact':1.7},
    'ice_golem': {'name':'얼음 골렘','map':'frost','tier':'strong','stand_in':'brute','height':3.2,'behavior':'melee',
                  'hp':190.,'damage':21.,'speed':.8,'windup':1.25,'reach':2.4,'impact':2.4},
    'lich': {'name':'리치','map':'frost','tier':'strong','stand_in':'wisp','height':2.2,'behavior':'melee',
             'hp':140.,'damage':18.,'speed':1.2,'windup':1.,'reach':5.2,'impact':1.6},
    'glacier_giant': {'name':'빙하 거인','map':'frost','tier':'strong','stand_in':'brute','height':3.6,'behavior':'charge',
                      'hp':210.,'damage':24.,'speed':.85,'windup':1.15,'reach':7.,'impact':1.6,'charge_speed':7.,'charge_overshoot':2.,'stun':2.},
    'dragon': {'name':'서리 용','map':'frost','tier':'boss','stand_in':'brute','height':5.,'wingspan':7.,'body':1.5,'behavior':'melee',
               'hp':760.,'damage':28.,'speed':.9,'windup':1.2,'reach':4.8,'impact':2.4},
}
LEGACY_SPECIES = ('wolf', 'boar', 'brute', 'wisp', 'shroom')
for _kind, _stats in ENEMIES.items():
    _stats.setdefault('stand_in', _kind)
    _stats.setdefault('tier', 'legacy')

# Species per map and tier (each species belongs to one map; the tutorial borrows the forest's weak).
ROSTERS = {
    'tutorial': {'weak':('goblin','centipede')},
    'forest': {'weak':('goblin','harpy','centipede'),'mid':('werewolf','troll'),'strong':('cyclops',)},
    'quarry': {'weak':('skeleton','imp','lizardman','mimic'),'mid':('basilisk','naga','gargoyle'),'strong':('minotaur','mummy_king')},
    'frost': {'weak':('ghoul','frost_wraith','ice_shardling','draugr'),'mid':('yeti','wendigo','frost_hag','frost_knight'),
              'strong':('ice_golem','lich','glacier_giant')},
}
# The first stage each tier comes out at night.
TIER_FROM = {
    'tutorial': {'weak':1},
    'forest': {'weak':1,'mid':2,'strong':3},
    'quarry': {'weak':1,'mid':2,'strong':4},
    'frost': {'weak':1,'mid':2,'strong':4},
}
# A boss night on a party expedition: the boss's health grows by this much per member past the first.
BOSS_PARTY_HP = .5

# Runs saved before stages keep their nights: pools widen as the week goes on; slot i of day d takes
# pool[(i+d-1) % len(pool)].
LEGACY_POOLS = {
    'forest': ((1,('wolf','shroom')), (2,('wolf','shroom','boar')), (4,('wolf','boar','brute','shroom')),
               (6,('brute','wolf','boar','wisp','shroom'))),
    'quarry': ((1,('wisp','wolf')), (2,('wisp','boar','wolf')), (4,('boar','wisp','brute','wolf','shroom'))),
    'frost': ((1,('wolf','boar')), (2,('wolf','boar','shroom')), (4,('boar','wolf','brute','wisp','shroom'))),
}

CHARACTERS = [
    {'id':'explorer_b','name':'B · 여행자','description':'원래 얼굴과 손을 보존한 노란 재킷 여행자.'},
    {'id':'explorer','name':'루 · 탐험가','description':'노란 우비를 입은 섬의 첫 탐험가.'},
    {'id':'ranger','name':'미라 · 숲지기','description':'숲길을 좋아하는 구리빛 머리의 숲지기.'},
    {'id':'tinker','name':'테오 · 정비사','description':'작은 물건을 고치는 붉은 재킷의 정비사.'},
]

def public_catalog():
    return {'maps':[dict(id=k,**{f:v[f] for f in ('name','description','reward_multiplier')},order=i,stages=v['stages'],
                         has_boss=bool(v['boss']),tutorial=bool(v.get('tutorial'))) for i,(k,v) in enumerate(MAPS.items())],
            'difficulties':[dict(id=k,**{f:v[f] for f in ('name','description','reward_multiplier')}) for k,v in DIFFICULTIES.items()],
            'characters':deepcopy(CHARACTERS)}

def night_count(map_id, stage, extra=0):
    """Night slots (a swarm species fills one slot with several bodies)."""
    fixed = MAPS.get(map_id, MAPS['forest']).get('night_slots')
    return fixed if fixed else max(1, min(2+stage//2, 5)+extra)

def night_plan(map_id, stage, extra=0):
    """Species per night slot: the strongest tier out leads, a mid follows once strong ones are out
    (and fills the fifth slot), the rest are weak; each tier rotates through its species by stage."""
    roster = ROSTERS.get(map_id, ROSTERS['forest'])
    first = TIER_FROM.get(map_id, TIER_FROM['forest'])
    out = [t for t in ('strong','mid','weak') if t in roster and stage >= first[t]]
    taken = {}
    plan = []
    for i in range(night_count(map_id, stage, extra)):
        if i == 0: tier = out[0]
        elif (i == 1 and out[0] == 'strong') or (i == 4 and 'mid' in out): tier = 'mid'
        else: tier = 'weak'
        pool = roster[tier]
        plan.append(pool[(taken.get(tier, 0)+stage-1) % len(pool)])
        taken[tier] = taken.get(tier, 0)+1
    return plan

def night_species(map_id, stage, difficulty=None, boss=True):
    """The species a stage's night can bring (every difficulty's when none is given), the map's boss
    last on its final stage: the client reads their models ahead of the night."""
    extras = [DIFFICULTIES[difficulty]['extra_enemies']] if difficulty else sorted({d['extra_enemies'] for d in DIFFICULTIES.values()})
    kinds = []
    for extra in extras:
        for kind in night_plan(map_id, stage, extra):
            if kind not in kinds: kinds.append(kind)
    region = MAPS.get(map_id, MAPS['forest'])
    if boss and region['boss'] and stage >= region['stages']: kinds.append(region['boss'])
    return kinds

def legacy_night_species(map_id, day):
    pool=LEGACY_POOLS['forest'][0][1]
    for first_day,kinds in LEGACY_POOLS.get(map_id,LEGACY_POOLS['forest']):
        if day>=first_day: pool=kinds
    return pool

def stand_in(kind):
    return ENEMIES.get(kind, {}).get('stand_in', kind)

def creature_variant(map_id):
    return MAPS.get(map_id,MAPS['forest'])['creature_variant']

def rules(state):
    return MAPS[state.get('map_id','forest')],DIFFICULTIES[state.get('difficulty','standard')]

def combined_multiplier(state):
    region,difficulty=rules(state)
    return float(Decimal(str(region['reward_multiplier']))*Decimal(str(difficulty['reward_multiplier'])))
