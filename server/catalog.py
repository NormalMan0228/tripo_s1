"""Server-owned expedition definitions. Clients choose IDs, never tuning or rewards."""
from copy import deepcopy
from decimal import Decimal
from . import survival_maps

MAPS = {
    'forest': {'creature_variant':'forest','name':'솔바람 숲','description':'넉넉한 나무와 열매. 첫 탐험에 어울리는 숲.',
               'reward_multiplier':1.,'cold':1., **survival_maps.layout('forest')},
    'quarry': {'creature_variant':'quarry','name':'노을 채석장','description':'바위 사이를 돌아 탐험하세요. 뜨거운 균열을 조심하세요.',
               'reward_multiplier':1.15,'cold':.7, **survival_maps.layout('quarry')},
    'frost': {'creature_variant':'frost','name':'서리빛 분지','description':'찬 바람과 얼음 웅덩이. 모닥불과 식량을 먼저 준비하세요.',
              'reward_multiplier':1.3,'cold':1.65, **survival_maps.layout('frost')},
}
DIFFICULTIES = {
    'relaxed': {'name':'산책','description':'느린 허기, 약한 적. 지형과 생존을 익히세요.',
                'reward_multiplier':.7,'hunger':.72,'damage':.65,'hp':.8,'speed':.85,'extra_enemies':-1,'cold':.5},
    'standard': {'name':'탐험','description':'기본 생존 규칙. 준비와 전투를 균형 있게.',
                 'reward_multiplier':1.,'hunger':1.,'damage':1.,'hp':1.,'speed':1.,'extra_enemies':0,'cold':1.},
    'veteran': {'name':'개척','description':'더 빠르고 강한 적, 빠른 허기. 보상 1.6배.',
                'reward_multiplier':1.6,'hunger':1.25,'damage':1.4,'hp':1.25,'speed':1.15,'extra_enemies':1,'cold':1.4},
}
# behaviour: melee = telegraphed strike at the player's announced spot; charge = telegraphed straight-line
# dash through the announced spot then a stunned recovery; spore = puff centred on itself (swarm: spawns
# `swarm` bodies per night slot). Each map sends its own creature variant id for the client art.
ENEMIES = {
    'wolf': {'name':'그림자 늑대','hp':45.,'damage':8.,'speed':1.28,'windup':.65,'reach':1.8,'impact':1.35,'behavior':'melee'},
    'boar': {'name':'가시 멧돼지','hp':60.,'damage':12.,'speed':1.05,'windup':.9,'reach':6.,'impact':1.1,'behavior':'charge',
             'charge_speed':7.,'charge_overshoot':2.,'stun':1.4},
    'brute': {'name':'이끼 수호자','hp':90.,'damage':16.,'speed':.85,'windup':1.15,'reach':2.1,'impact':2.,'behavior':'melee'},
    'wisp': {'name':'불씨 도깨비','hp':30.,'damage':6.,'speed':1.65,'windup':.9,'reach':4.8,'impact':1.15,'behavior':'melee'},
    'shroom': {'name':'버섯 망령','hp':22.,'damage':5.,'speed':1.05,'windup':1.,'reach':1.5,'impact':2.,'behavior':'spore','swarm':2},
}
# Night roster per map: pools widen as the week goes on; slot i of day d takes pool[(i+d-1) % len(pool)].
NIGHT_POOLS = {
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
    return {'maps':[dict(id=k,**{f:v[f] for f in ('name','description','reward_multiplier')}) for k,v in MAPS.items()],
            'difficulties':[dict(id=k,**{f:v[f] for f in ('name','description','reward_multiplier')}) for k,v in DIFFICULTIES.items()],
            'characters':deepcopy(CHARACTERS)}

def night_species(map_id, day):
    pool=NIGHT_POOLS['forest'][0][1]
    for first_day,kinds in NIGHT_POOLS.get(map_id,NIGHT_POOLS['forest']):
        if day>=first_day: pool=kinds
    return pool

def creature_variant(map_id):
    return MAPS.get(map_id,MAPS['forest'])['creature_variant']

def rules(state):
    return MAPS[state.get('map_id','forest')],DIFFICULTIES[state.get('difficulty','standard')]

def combined_multiplier(state):
    region,difficulty=rules(state)
    return float(Decimal(str(region['reward_multiplier']))*Decimal(str(difficulty['reward_multiplier'])))
