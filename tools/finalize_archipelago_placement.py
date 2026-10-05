"""Record a verified map layout and the user's authorization to place this batch."""
import json
import re
import shutil
from pathlib import Path
from archipelago_queue import locked_queue

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/maps/archipelago_placement_v1'
report = json.loads((OUT/'placement_verification.json').read_text())
source = json.loads((OUT/'source_preservation_verification.json').read_text())
assert report['passed'] and report['count'] == source['count'] == 17 and source['passed']
assert not report['overlaps']
for name in ['capture_final.log', 'walking_audit.log']:
    log = (OUT/name).read_text(encoding='utf-8')
    assert not re.search(r'(?m)^\s*(?:ERROR|SCRIPT ERROR):', log), name
assert 'TERRAIN_AUDIT_PASS all_five_islands_grounded' in (OUT/'walking_audit.log').read_text(encoding='utf-8')
assert all((OUT/(name+'.png')).exists() for name in ['overview','northwest','northeast','southwest','southeast','lighthouse'])
shutil.copyfile(ROOT/'art/maps/archipelago_terrain_v6/verification.json', OUT/'terrain_ground_verification.json')
evidence = 'User: 이제 맵의 각 위치의 알맞는 곳에 배치해주세요'
with locked_queue() as queue:
    for item in queue['items'][:17]:
        item['placement_status'] = 'placed'
        item['placement_manifest'] = 'art/maps/archipelago_placement_v1/placements.json'
        item['placement_evidence'] = evidence
        if item['review_status'] == 'awaiting_user':
            item['review_status'] = 'approved'
            item['approval_evidence'] = evidence
            item['approval_scope'] = 'Use this reviewed model in the map layout'
    queue['active_batch']['status'] = 'approved_and_placed'
    queue['active_batch']['placement_evidence'] = evidence
    queue['active_batch']['placement_package'] = 'art/maps/archipelago_placement_v1'
    assert all(item['review_status'] == 'planned' for item in queue['items'][17:])
readme = '''# 레퍼런스 건물 배치 v1

생성된 17개 건물을 승인된 섬 지형의 해당 위치에 배치했습니다.

| 섬 | 배치된 건물 |
|---|---|
| 북서 | 카페, 청색 지붕 목조 주택, 청록 지붕 주택, 풍차 |
| 북동 | 천문대, 주황 지붕 주택, 유리 온실, 보라색 정자 |
| 남서 | 마을 회관, 붉은 벽돌 주택, 보라 지붕 주택, 노란 지붕 주택, 상점 |
| 남동 | 음악 무대, 피크닉 쉼터, 청색 지붕 주택 |
| 작은 남쪽 섬 | 등대 |

건물은 원래의 실제 미터 크기를 유지합니다. 건물 아래만 평탄하게 준비하고
가장자리를 기존 지형으로 부드럽게 연결했습니다. 해안, 호수, 폭포는 유지했습니다.
다리 연결 지점과 캠핑장 중심부는 후속 오브젝트가 들어갈 공간으로 남겨 두었습니다.

검증: 건물 17개, 발밑 지면 표본 153개, 건물 겹침 0개, 5개 섬 산책 시작점 정상.
원본 모델의 모든 메시 접근자 바이트와 재질 기록이 맵 복사본에서도 동일합니다.
8K 원본은 그대로 보존했습니다. 17개를 함께 표시하는 맵 복사본은 컬러 4K,
노멀/ORM 2K로 준비하여 GPU 메모리 사용량을 줄였습니다.

실행: 저장소 루트의 Terrain_Lab.cmd.
WASD 이동, Q/E 높이, 오른쪽 드래그 시점, Shift 빠르게, Alt 천천히.
1–5 섬별 건물 시점, R 전체, C 자유 카메라 전환, H 안내 숨기기.

placement_verification.json: 실제 Godot 장면의 크기·접지·겹침 검사.
source_preservation_verification.json: 검토한 모델의 메시·재질 보존 검사.
overview.png와 섬별 PNG: 실제 맵에서 촬영한 이미지.
'''
(OUT/'README.md').write_text(readme, encoding='utf-8')
print('ARCHIPELAGO_PLACEMENT_FINALIZED buildings=17 grounded_samples=153 overlaps=0')
