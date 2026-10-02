"""Server-owned expedition definitions. Clients choose IDs, never tuning or rewards."""
from copy import deepcopy
from decimal import Decimal

MAPS = {
    'forest': {'name':'솔바람 숲','description':'넉넉한 나무와 열매. 첫 탐험에 어울리는 숲.',
               'reward_multiplier':1.,'cold':1.,'hazards':[], 'obstacles':[]},
    'quarry': {'name':'노을 채석장','description':'바위 사이를 돌아 탐험하세요. 뜨거운 균열을 조심하세요.',
               'reward_multiplier':1.15,'cold':.7,
               'hazards':[{'x':-9.,'z':-6.,'radius':2.3,'kind':'ember'}, {'x':10.,'z':7.,'radius':2.4,'kind':'ember'}],
               'obstacles':[{'x':-7.,'z':5.,'radius':2.2},{'x':7.,'z':-7.,'radius':2.5},{'x':-12.,'z':-11.,'radius':1.8}]},
    'frost': {'name':'서리빛 분지','description':'찬 바람과 얼음 웅덩이. 모닥불과 식량을 먼저 준비하세요.',
              'reward_multiplier':1.3,'cold':1.65,
              'hazards':[{'x':-9.,'z':-7.,'radius':3.1,'kind':'ice'}, {'x':10.,'z':6.,'radius':3.,'kind':'ice'}],
              'obstacles':[{'x':-8.,'z':6.,'radius':2.},{'x':8.,'z':-8.,'radius':2.1},{'x':12.,'z':-1.,'radius':1.7}]},
}
DIFFICULTIES = {
    'relaxed': {'name':'산책','description':'느린 허기, 약한 적. 지형과 생존을 익히세요.',
                'reward_multiplier':.7,'hunger':.72,'damage':.65,'hp':.8,'speed':.85,'extra_enemies':-1,'cold':.5},
    'standard': {'name':'탐험','description':'기본 생존 규칙. 준비와 전투를 균형 있게.',
                 'reward_multiplier':1.,'hunger':1.,'damage':1.,'hp':1.,'speed':1.,'extra_enemies':0,'cold':1.},
    'veteran': {'name':'개척','description':'더 빠르고 강한 적, 빠른 허기. 보상 1.6배.',
                'reward_multiplier':1.6,'hunger':1.25,'damage':1.4,'hp':1.25,'speed':1.15,'extra_enemies':1,'cold':1.4},
}
ENEMIES = {
    'wolf': {'name':'그림자 짐승','hp':45.,'damage':8.,'speed':1.28,'windup':.65,'reach':1.8,'impact':1.35},
    'brute': {'name':'이끼 수호자','hp':90.,'damage':16.,'speed':.85,'windup':1.15,'reach':2.1,'impact':2.},
    'wisp': {'name':'불씨 도깨비','hp':30.,'damage':6.,'speed':1.65,'windup':.9,'reach':4.8,'impact':1.15},
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

def rules(state):
    return MAPS[state.get('map_id','forest')],DIFFICULTIES[state.get('difficulty','standard')]

def combined_multiplier(state):
    region,difficulty=rules(state)
    return float(Decimal(str(region['reward_multiplier']))*Decimal(str(difficulty['reward_multiplier'])))
