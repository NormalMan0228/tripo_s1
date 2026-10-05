"""Inventory the reference assets; generation advances only after human review."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/maps/archipelago_objects_v1'
OUT.mkdir(parents=True, exist_ok=True)
items = [
 ('01_cafe', '빨간 곡면 지붕 카페', '북서 섬', 'building', 8.0),
 ('02_timber_house', '청색 지붕 목조 주택', '북서 섬 뒤쪽', 'building', 8.0),
 ('03_teal_cottage', '청록 지붕 크림색 주택', '북서 섬 앞쪽', 'building', 6.2),
 ('04_windmill', '풍차', '북서 섬 오른쪽', 'building', 12.0),
 ('05_observatory', '망원경과 청색 돔 천문대', '북동 섬 뒤쪽', 'building', 11.0),
 ('06_orange_cottage', '주황 지붕 청록색 주택', '북동 섬 왼쪽', 'building', 6.2),
 ('07_greenhouse', '유리 온실', '북동 섬 앞쪽', 'building', 6.5),
 ('08_gazebo', '보라색 원형 지붕 정자', '북동 섬 오른쪽', 'building', 5.0),
 ('09_town_hall', '시계탑이 있는 마을 회관', '남서 섬 중앙', 'building', 10.0),
 ('10_red_house', '빨간 지붕 붉은 벽돌 주택', '남서 섬 뒤쪽', 'building', 8.0),
 ('11_purple_house', '보라색 지붕 주택', '남서 섬 왼쪽', 'building', 8.0),
 ('12_blue_house', '노란 지붕 파란 주택', '남서 섬 호수 옆', 'building', 6.8),
 ('13_shop', '녹백색 줄무늬 차양 상점', '남서 섬 오른쪽', 'building', 5.5),
 ('14_stage', '보라색 천막 음악 무대', '남동 섬 뒤쪽 왼편', 'building', 5.5),
 ('15_picnic_shelter', '빨간 지붕 피크닉 쉼터', '남동 섬 뒤쪽 오른편', 'building', 4.5),
 ('16_blue_cottage', '청색 지붕 크림색 주택', '남동 섬 앞쪽', 'building', 6.8),
 ('17_lighthouse', '빨간 등실 등대', '작은 등대 섬', 'building', 9.0),
 ('18_bridge_short', '짧은 아치형 목조 다리', '북쪽 및 중앙 수로', 'bridge', None),
 ('19_bridge_long', '긴 아치형 목조 다리', '남서 섬과 등대 섬 사이', 'bridge', None),
 ('20_pier', '기둥이 있는 목조 부두', '카페 앞·호수·등대 앞', 'prop', None),
 ('21_boat', '갈색 소형 목조 보트', '등대 부두 옆', 'prop', None),
 ('22_tent_orange', '주황색 삼각 텐트', '남동 섬 캠프', 'prop', None),
 ('23_tent_green', '연두색 삼각 텐트', '남동 섬 캠프', 'prop', None),
 ('24_firepit', '돌로 둘러싼 모닥불 받침과 장작', '남동 섬 캠프', 'prop', None),
 ('25_picnic_table', '목조 피크닉 테이블과 긴 의자', '남동 섬 캠프와 쉼터', 'prop', None),
 ('26_bench', '갈색 공원 벤치', '각 섬 정원', 'prop', None),
 ('27_lamp', '검정색 정원 가로등', '각 섬·다리·부두', 'prop', None),
 ('28_beach_umbrella', '청백색 줄무늬 해변 파라솔', '북동 및 남동 섬 모래 해변', 'prop', None),
 ('29_beach_lounger', '목조 해변 긴 의자', '파라솔 아래', 'prop', None),
 ('30_cafe_umbrella', '밝은 크림색 카페 파라솔', '카페 테라스', 'prop', None),
 ('31_cafe_table', '작은 원형 카페 테이블', '카페 테라스', 'prop', None),
 ('32_cafe_chair', '목조 카페 의자', '카페 테라스', 'prop', None),
 ('33_signboard', 'A형 칠판 입간판', '카페와 상점 입구', 'prop', None),
 ('34_timber_fence', '낮은 목조 가로 울타리', '카페 정원과 수로 옆', 'prop', None),
 ('35_picket_fence', '흰색 정원 울타리', '남서 섬 보라색 집', 'prop', None),
 ('36_speaker', '검정색 무대 스피커', '음악 무대 양쪽', 'prop', None),
 ('37_round_tree', '둥근 수관 활엽수', '각 섬', 'vegetation', None),
 ('38_conifer', '층이 있는 짙은 청록색 침엽수', '각 섬', 'vegetation', None),
 ('39_palm', '작은 야자수', '온실과 북동 섬', 'vegetation', None),
 ('40_shrub', '둥근 잎 관목', '건물과 바위 주변', 'vegetation', None),
 ('41_planter', '테라코타 화분', '카페와 상점', 'prop', None),
 ('42_white_flowers', '흰색 작은 꽃 무리', '정원', 'vegetation', None),
 ('43_yellow_flowers', '노란색 작은 꽃 무리', '정원', 'vegetation', None),
 ('44_pink_flowers', '분홍색 작은 꽃 무리', '정원', 'vegetation', None),
 ('45_reeds', '호숫가 갈대', '안쪽 호수', 'vegetation', None),
 ('46_water_lily', '수련 잎과 노란 꽃', '안쪽 호수', 'vegetation', None),
 ('47_starfish', '붉은 불가사리', '남서 섬 해변', 'prop', None),
]
path = OUT / 'queue.json'
if not path.exists():
    data = {'reference':'art/maps/archipelago_terrain_v1/map_reference.png',
            'workflow':'one asset at a time; explicit user approval required before the next generation',
            'scale_reference':'1.70 metre adult', 'roads':'omitted by prior user request',
            'existing_assets':'approved terrain, lakes, ocean, waterfall and rocks remain in use',
            'items':[{'id':id, 'name':name, 'reference_location':place, 'category':category,
                      'target_height_m':height, 'review_status':'planned'}
                     for id,name,place,category,height in items]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'OBJECT_QUEUE_CREATED unique_assets={len(items)} first=01_cafe')
else:
    print('Existing review queue preserved')
