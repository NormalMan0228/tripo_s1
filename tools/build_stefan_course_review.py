"""Build a private, source-grounded course review. No API calls or source edits."""
import html
import json
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'artifacts/stefan-course-audit-20261004'
REPORT = ROOT / 'artifacts/production-lab-20261003/review/stefan-course-review'
REPORT.mkdir(parents=True, exist_ok=True)
(REPORT / 'media').mkdir(exist_ok=True)
INDEX = json.loads((ROOT / 'artifacts/stefan-study/index.json').read_text(encoding='utf-8'))
ASSETS = json.loads((AUDIT / 'assignment-assets.json').read_text(encoding='utf-8'))
BLENDS = json.loads((AUDIT / 'blend-audit.json').read_text(encoding='utf-8'))
FBXS = json.loads((AUDIT / 'fbx-audit.json').read_text(encoding='utf-8'))
COVERAGE = json.loads((AUDIT / 'original-har-caption-coverage.json').read_text(encoding='utf-8')) if (AUDIT / 'original-har-caption-coverage.json').exists() else []
def raw_coverage(entry):
    return next((x for x in COVERAGE if x['course']==entry['group'] and x['file']==Path(entry['source']).name), None)
def coverage_status(entry):
    raw=raw_coverage(entry)
    if raw:
        h,m,s=raw['first'].split(':')
        starts_at_beginning=int(h)*3600+int(m)*60+float(s)<1
        h,m,s=raw['last_cue_end'].split(':')
        end=int(h)*3600+int(m)*60+float(s)
        reaches_playlist_end=any(abs(end-v)<.02 for v in raw['playlist_duration_totals'])
        if starts_at_beginning and reaches_playlist_end:
            return '시작~끝 자막 포함'
        if not starts_at_beginning:
            return '앞부분 텍스트 누락'
        if not reaches_playlist_end:
            return '끝부분 텍스트 미확보'
    return '전체 범위 확인 필요'

# Each item is a paraphrase of the supplied captions/hints, not a quotation or
# an assertion that the entire corresponding online video was watched.
LESSONS = [
('character','1_creating_concept','01 · 콘셉트와 부위별 이미지',
 '전체 콘셉트 → 중립 자세의 전신 → 머리·손·의복·장식의 독립 이미지 → 필요한 추가 시점 순서다. 01:32–01:45는 부위 분리를 제작 단계로 명시한다. 07:04–07:36은 의복과 몸이 융합되는 문제를 피하도록 별도 생성한다. 11:27–12:06은 기존 디자인의 추출과 근접 크롭을 강조한다.',
 'lesson-01-hints: 정면·측면·후면 일관성, 포즈·배경·손가락 분리. 온라인 퀴즈의 실제 질문은 공급 파일에 없다.',
 '우리 캐릭터는 머리·몸·손을 신체 기준으로 삼고, 머리카락·재킷·셔츠·바지·부츠·벨트를 별도 자산으로 유지한다. 재킷과 벨트는 각각 하나, 주머니는 바지에 포함한다. 피부색과 B형 비율을 고정한다.'),
('character','2_3d_generation','02 · 3D 생성과 선별',
 '고해상도 원본은 스컬프와 베이크의 출발점이다. 05:40은 텍스처를 끈 Solid/Normal 검사를 보여준다. 06:13–07:27은 실패한 머리·손을 재생성하고, 10:34–10:37은 전체 생성 모델의 머리·손을 교체한다. 생성 결과를 그대로 최종 모델로 인정하지 않는다.',
 'lesson-02-hints + Generation 3D 예제 2개와 참조 이미지 4개. 예제 캐릭터 메시에는 UV가 없는 모델도 포함된다.',
 '현재 9종 Tripo 원본은 보존한다. 실루엣·손가락·목·의복 두께를 부위별로 검사한 뒤 필요한 부위만 재생성한다. 이 검토에서는 생성 크레딧을 사용하지 않았다.'),
('character','3_sculpting','03 · 스컬프와 실제 접합',
 '캡처는 09:00부터다. 반쪽 정리 후 Mirror/Clipping으로 대칭을 만들고 목을 옷깃에 맞춘다. 20:35–21:04는 Ctrl+J와 표면 접합을 구분하며 Remesh와 Smooth를 사용한다. 23:32–24:35는 기존 손을 제거하고 새 손의 형태·위치를 맞춘 뒤 접합한다. 25:20–25:32는 외투 맞춤을 다룬다.',
 'lesson-03-hints + Sculpt / Sculpt_complete 비교. 전후 모델에 머리·손·부츠의 원본 메시가 별도로 남아 있다. 모든 액세서리를 몸에 용접하는 수업은 아니다.',
 '지난 조립본은 사용자가 품질을 거절했다. 참조 기준의 비율과 위치를 먼저 맞추고, 축별 Scale과 Mirror를 활용한다. 접합은 부위에 따라 시각적 정리 또는 표면 연결을 선택한다. 모든 파츠를 Remesh하지 않는다. 원본 파츠는 별도 컬렉션에 남기고 접합부는 변형 포즈에서도 확인한다.'),
('character','4_retopology_and_optimization','04 · 리토폴로지와 관절 구조',
 '캡처는 16:42부터다. 18:57–19:22에서 팔꿈치·무릎·손가락·얼굴의 변형 루프를 정리한다. Grid Fill / Bridge / Extrude / 고해상도 스냅을 사용한다. 21:35–22:49의 합치기·근접 정점 병합 뒤에도 구멍을 직접 검사한다. 28:41–28:48은 눈을 별도 구체로 만든다.',
 'lesson-04-hints + 도끼·장갑의 고/저해상도 예제. 5개 Blend 엔트리 중 1개는 다른 엔트리와 동일한 SHA-256이다. 자동 리토폴로지 결과를 수작업으로 보정한다.',
 '폴리곤 개수만 줄이지 않는다. 다섯 손가락, 손목·팔꿈치·무릎의 굽힘, 눈꺼풀과 입 주변 루프를 통과시킨다. 의복 교체를 위해 가려진 신체 원본을 보존한다.'),
('character','5_uv_unwrap','05 · UV',
 '캡처는 02:30부터다. 생성 모델의 UV를 정리하고 보이지 않는 위치에 심을 둔다. 체크 패턴으로 왜곡을 보고 얼굴·손에 필요한 해상도를 배분한다. pack margin은 해상도와 베이크 조건에 맞춘다.',
 'lesson-05-hints + Uv / Uv_complete와 검사 이미지. 5개 메시 모두 UV가 있다. Mirror가 남은 편집 메시와 적용 후 엔진 메시의 수치를 혼동하면 안 된다.',
 '피부색 일치, 얼굴·손의 텍셀 밀도, 색칠 영역 마스크를 확인한다. 의도적인 대칭 UV 공유와 잘못 겹친 UV를 구분하고 비대칭 텍스처가 필요할 때 분리한다.'),
('character','6_baking_highpoly_to_lowpoly','06 · 고해상도 → 저해상도 베이킹',
 'Cycles Selected to Active, 고해상도 선택 후 저해상도 활성, 대상 이미지 노드와 cage/ray 거리 설정을 다룬다. Normal은 Non-Color로 읽는다. 한 아틀라스에 이어 굽는 경우 첫 작업 이후 Clear Image를 끈다. 형상과 접합 오류는 베이크 전에 고쳐야 한다.',
 'lesson-06-hints + Blend 4개, FBX 2개, AO/Normal 이미지. FBX 두 파일 모두 장갑·헬멧·총의 고/저해상도 쌍 6개 메시와 UV를 가져올 수 있었으며 액션은 없다.',
 '몸·얼굴·의복의 원본/엔진 메시 쌍을 명확히 이름 붙인다. Normal로 실루엣이나 손목 틈을 숨기지 않는다. cage와 검수 조명을 고정해 오류 영역을 다시 굽는다.'),
('character','7_texturing','07 · 텍스처와 PBR',
 '캡처는 11:18부터다. Modddif의 투영·레이어·부분 수정과 Blender Clone/Smear/브러시를 다룬다. 전체 색만으로 생성한 노멀 효과와 실제 형상 수정은 다르다. 원치 않는 투영 부분은 마스크로 제거하고 손가락처럼 작은 곳을 직접 보정한다.',
 'lesson-07-hints + Texturing Block 예제. 컨테이너·유리·광선의 전후 메시와 Base Color / Normal / Metallic / Roughness / Emission / Alpha, 브러시 이미지가 있다.',
 '하나의 팔레트 기준으로 피부와 의복을 맞춘다. 광원 회전으로 PBR을 확인하고 Godot로 전달할 이미지를 저장한다. 복잡한 질감 작업에서 Substance Painter는 선택 도구로 검토한다.'),
('character','8_rigging_and_weight','08 · 리깅과 웨이트',
 '캡처는 07:48부터다. 옷에 잘못 섞인 손·발의 영향 제거, rigid 부품의 한 본 가중치, 유연한 부위의 점진 가중치, AccuRIG 신체·손 마커와 자세 보정을 다룬다. 꼬리 본은 수동으로 추가한다. 21:43–22:49는 옷 아래 몸을 숨기는 처리를 다룬다.',
 'lesson-08-hints + rig / rig_complete. 실제 예제는 root 리그 62개 본, rootAction 1–120프레임, Shape Key 0개다. 테스트 포즈 예제이며 우리 주인공의 보행·표정 완성본이 아니다.',
 '형태 승인 후에만 손가락과 신체를 바인딩한다. 잘못된 웨이트를 제거한 정점에는 올바른 본을 다시 배분한다. 눈·눈꺼풀·입·턱의 정교한 페이스 리깅은 이 자료만으로 확보되지 않았으므로 별도 검증이 필요하다.'),
('character','9_engine_export','09 · 엔진 이식',
 'Unity/UE의 리타게팅, 본 매핑, 이동 컨트롤러, 의복·꼬리 등의 보조 물리를 설명한다. 06:42–07:01은 영상 밖에서 보조 본을 추가했다고 말한다. Godot에 원리 적용이 가능하다고 언급하지만 Godot 구현 강의는 아니다.',
 '해당 단계의 별도 과제 파일은 공급 ZIP에 없다. 온라인 첨부 목록 확인이 필요하다.',
 'Godot에서는 GLB, AnimationTree, 필요한 Skeleton/BoneMap, 충돌과 이동을 확인한다. 원점·rest pose·스케일·루트 이동 정책을 고정하고 보행 속도와 애니메이션 전환을 실제 플레이로 검증한다.'),
('character','b1_claude_in_blender','보너스 · Blender 자동화',
 'AI가 Python/MCP로 베이크 반복을 돕는다. 첫 배치 베이크는 설정 문제로 실패했다. 03:39 이후는 작업을 이해한 다음 정확한 입력·출력·설정을 알려 자동화하도록 강조한다.',
 '별도 과제 첨부는 공급 ZIP에 없다.',
 '검증된 수작업 절차만 자동화한다. 자동 체크는 파일·UV·본·선택 상태 등을 돕고, 형태·스타일·자연스러움의 사람 검수를 대신하지 않는다.'),
('character','b2_master_tripo_generation','보너스 · Tripo 생성 전략',
 'AI Complete가 필요한 형태를 바꿀 수 있어 준비된 참조를 권한다. 06:54–07:20은 머리카락 덩어리에 Smart Mesh를 쓰는 예를 보여준다. 상세한 옷은 고해상도 생성과 베이크가 적합할 수 있다. 재텍스처 시 UV가 바뀌는지 확인해야 한다.',
 '웹의 당시 Retry/무료 사용 언급은 현재 API 비용 보장을 뜻하지 않는다.',
 '모든 부위에 같은 생성 모드를 강제하지 않는다. 머리카락은 덩어리·실루엣, 얼굴·손은 변형 구조, 옷은 세부와 두께를 각각 우선한다. 유료 재생성은 검토 후 실행한다.'),
('character','b3_tripo_smart_mesh_p2','보너스 · Smart Mesh P2',
 '낮은 폴리곤 한도로 뒤쪽이나 작은 디테일이 사라질 수 있다. quad 출력도 올바른 변형 루프를 보장하지 않는다. 머리카락 분리와 카드 제작은 보완 작업이 필요하고 정교한 의복에는 고해상도→리토폴로지 경로를 비교한다.',
 '수업 당시 모델 버전과 제공 조건에 대한 설명이다. 현재 가격·약관 확인은 별도다.',
 '우리 캐릭터의 근접 카메라에서 머리 뒤·귀·손가락·부츠 안쪽까지 검사한다. 출력 이름보다 실제 실루엣과 변형을 기준으로 선별한다.'),
('character','b4_my_ai_workspace','보너스 · AI 워크스페이스',
 '참조·생성 결과·수정 이력·파일과 작업 메모를 한 프로젝트에 묶어 반복 제작을 돕는다. 사람이 디자인과 배치를 판단한다.',
 '캐릭터/환경 보너스에 같은 작업 내용이 서로 다른 언어로 캡처되어 있다. 강의의 설치·업로드 안내는 실행 권한으로 간주하지 않았다.',
 '승인된 이미지, 파츠, 원본 모델, 수정본, 엔진 출력, 검수 기록을 버전별로 연결한다. 단순 합치기 스크립트가 전체 아트 제작을 대신한다는 전제를 버린다.'),
('environment','3d_environments_tools','도구 · Blender 환경 제작',
 'G/R/S 축 제어, 정사영, 선택물 프레임, 복제, Knife, Shear, 비례 편집, Boolean, Empty를 대칭축으로 쓰는 Mirror 등 실제 조립 도구를 설명한다.',
 '도구 소개의 별도 과제는 공급 ZIP에 없다.',
 '모듈 기준축·원점·단위를 고정한다. 크기·배치 조절은 편집 가능한 오브젝트로 유지하고 카메라 및 보행 규모에 맞춘다.'),
('environment','1_idea_and_concepts','01 · 맵 콘셉트 계층',
 '전체 지도/주요 지점/동선 → 구역 → 근접 장면 → 개별 소품 순서다. 큰 형태를 먼저 정하고 반복 벽·바닥·나무·바위 등을 준비한다. foliage는 줄기 메시와 잎/가지의 알파 평면을 조합한다.',
 'c2-lesson-01-hints와 캠프 콘셉트·개별 소품·자연물 참조, starter 이미지가 있다.',
 '우리 마을과 생존 스테이지는 플레이 동선·구역·카메라를 먼저 승인한다. 전체 맵을 하나의 AI 메시로 만들지 않고 건물·지형·식생·소품으로 제작한다.'),
('environment','2_generate_and_prepare_3d_assets','02 · 모듈과 소품 생성',
 '세밀한 지붕은 고해상도→저해상도 베이크, 작은 단순 부품은 낮은 폴리곤 직접 생성을 비교한다. 문 구멍 등은 Solid/Wireframe으로 확인한다. 수작업 primitive가 유리한 형태도 있다. 잎의 alpha와 tileable PBR을 준비한다.',
 'c2-lesson-02-hints, assets / bridge / swords Blend, 목재·화분·도검·다리·브러시/참조 이미지가 있다. bridge는 57개 메시를 부품과 조립 컬렉션으로 관리한다.',
 'Tripo는 고유 소품 중심으로 쓴다. 벽·바닥·반복 판재·문 규격은 Blender 모듈을 우선한다. 출입구는 실제로 뚫고, 장식 디테일과 충돌 형상을 나눠 관리한다.'),
('environment','3_refine_and_bake_game_assets','03 · 정리·색 통일·베이킹',
 '캡처는 06:54부터다. HSV/RGB 보정으로 팔레트를 맞추고 직접광·간접광이 묻지 않게 색을 굽는다. 자기 메시 색 베이크와 고→저해상도 베이크 설정을 구분한다. 거대한 단일 아틀라스는 작은 UV 섬의 해상도를 떨어뜨릴 수 있다.',
 'c2-lesson-03-hints + lesson3 전후. starter 6메시와 complete 3메시는 비교용 중복과 묶음 구성을 함께 봐야 한다.',
 '캐릭터·지형·건물의 팔레트를 한 장면 조명에서 맞춘다. Blender 전용 노드 효과는 이미지로 굽거나 Godot shader로 구현한다. 맵 전체를 무조건 합치지 않는다.'),
('environment','4_build_pbr_materials','04 · PBR과 부분 마스크',
 '선택/마스크로 금속·거칠기 영역을 칠하고 스크래치 브러시를 활용한다. AI roughness는 반전 여부를 검사한다. 색에서 만든 bump를 노멀로 굽는 방법과 Object/Box 투영을 UV로 굽는 방법을 다룬다.',
 'c2-lesson-04-hints + starter/complete와 PNG/TIF 이미지. complete 42메시는 PBR / Not PBR 비교 복제이며 starter는 21메시다.',
 '자연 재료를 같은 metallic/roughness 값으로 뭉뚱그리지 않는다. 재사용 재질과 색칠 마스크를 분리하고 Godot 조명에서 반복 타일과 경계선을 검사한다.'),
('environment','5_assemble_environments','05 · 환경 조립',
 '캡처는 37:00부터라 앞부분이 크게 빠져 있다. 줄기 변형, 잎 평면의 원점·스냅·표면 정렬, Bezier 밧줄, 지형 패임과 아래쪽 물 평면을 다룬다. 큰 고유 구조는 Blender, 작은 반복 식생은 엔진 배치를 제안한다.',
 'c2-lesson-05-hints + market starter/complete와 참조. 17개 시작 메시를 138개 메시의 가판대·바닥 장면으로 구성한다. 본편 전체 맵이나 UE 프로젝트와 같은 파일은 아니다.',
 '건물과 고유 지형은 모듈 조립 후 승인하고, 나무·풀은 Godot 인스턴싱으로 배치한다. 물·낙엽 등 움직임은 엔진 재질과 파티클로 분리한다.'),
('environment','6_build_interiors_and_optimize_the_scene','06 · 실내와 최적화',
 '캡처는 02:18부터다. 실내 참조에서 큰 구성을 먼저 잡고 필요한 물건을 채운다. 기존 부품을 Knife와 비례 조정으로 재사용한다. 색 통일과 Decimate 후 실루엣 검사를 다룬다.',
 '이 단계의 추가 과제/실내 완성 씬은 공급 ZIP에서 확인되지 않았다.',
 '외부 문과 실내 진입 위치를 규격화한다. 실내는 기능적인 동선과 가구 배치를 먼저 검토한다. Decimate를 캐릭터 관절 토폴로지에 무차별 적용하지 않는다.'),
('environment','7_export_and_scene_setup_UE5','07 · 엔진 씬',
 '캡처는 15:00부터다. UE terrain 레이어·타일 재질·길·식생 페인트·조명·낙엽 Niagara·날씨를 다룬다. 건물 근처 지형과 도로 높이를 조절한다.',
 '영상에서 언급한 전체 UE 프로젝트와 timelapse는 공급 ZIP에 없다. 온라인 첨부 확인이 필요하다.',
 'Godot에서는 지형/모듈 씬, MultiMesh 등 반복 배치, GPUParticles, 충돌·내비게이션·출입 트리거로 목적을 다시 구현한다. UE 플러그인을 그대로 옮기지 않는다.'),
('environment','b1_tripo_smart_mesh_p2','보너스 · Smart Mesh P2',
 '현재 캡처는 00:23.923에서 끝나 비교 내용을 거의 확인할 수 없다. 캐릭터 P2 강의와 같은 전체 영상이라고 단정하지 않는다.',
 '별도 과제 없음. 전체 영상 확인 대기.',
 '모델 선택은 실제 맵 소품의 실루엣·폴리곤·재질 출력으로 시험한다. 이 짧은 자막을 근거로 환경 제작 성능을 확정하지 않는다.'),
('environment','b2_ai_workspace','보너스 · 환경 워크스페이스',
 '참조·생성·검토·구성 반복과 프로젝트 단위 파일 관리 내용이다. 캐릭터 워크스페이스 보너스와 같은 작업 흐름이 확인된다.',
 '추가 온라인 첨부 목록 확인 대기.',
 '동일 모듈의 사용 위치, 원본과 수정본, 변형/재질 인스턴스와 출처를 기록해 맵별 복제 비용을 낮춘다.'),
]

GATES = [
 ('01 이미지', '전신과 승인된 부위별 2D 이미지', 'B형 비율, 같은 디자인·피부색, 개별 이미지, 재킷/벨트 통합, 바지 주머니 포함', '사용자 이미지 승인 전 새 3D 생성 진행 금지'),
 ('02 부위별 3D', '머리·몸·손·머리카락·의복·장식의 원본과 선별 기록', 'Solid와 재질 보기 모두 검사; 다섯 손가락, 대칭, 의복 두께, 추가 시점 일치', '사용자 3D 파츠 승인 후 형태 조립'),
 ('03 Blender 형태', 'unrigged 조립 검수본 + 보존된 원본 컬렉션', '목/손목의 외관과 접합 방식, 몸과 의복 간격, Mirror 대칭, 머리/손 비율, 옷 교체 가능 구조', '리그·애니메이션 없이 정면/후면/측면/근접 승인'),
 ('04 리토폴로지', '변형 가능한 엔진 메시 + 원본 쌍', '손가락/팔꿈치/무릎/눈/입의 루프, 열린 경계와 중복면, 실루엣 유지', '큰 굽힘 포즈와 근접 와이어 검수'),
 ('05 UV·베이크·텍스처', 'UV / PBR 텍스처 / 색칠 마스크 / bake 설정', '의도하지 않은 겹침·왜곡·ray 오류 없음, 피부색 일치, 얼굴/손 해상도, Godot 재질 비교', '사용자 UV·텍스처 승인'),
 ('06 리깅·페이스', '신체·손·보조 본 + 표정 베이스 + 포즈 검사', '웨이트 정규화, 옷 관통, 손가락 접힘, 눈꺼풀 닫힘, 입/턱 변형, head/hair 분리 유지', '페이스 고급 기능은 별도 참고 자료 확보 후 범위 확정'),
 ('07 애니메이션', '클립·전환·이동 속도 표 + 실제 플레이 영상', 'rest pose·원점·스케일 일치, 루트 이동 정책, 발 접지·속도 일치, idle/walk/run 방향전환의 튐·순간이동 검사', '최종 Godot 카메라와 실제 이동에서 사용자 승인'),
]
e = html.escape
sections = []
for group, anchor, title, lesson, attachment, application in LESSONS:
    entry = next(x for x in INDEX if x['group'] == group and Path(x['source']).stem == anchor)
    capture = entry['first_available_cue'] + ' → ' + entry['last_available_cue']
    sections.append(f'''<article id="{group}-{anchor}"><h3>{e(title)}</h3>
      <p class="source">출처: {e(entry['source'])} · 캡처 {capture} · 전체 영상 검토 미완료</p>
      <div class="lesson-grid"><div><h4>수업에서 확인</h4><p>{e(lesson)}</p><h4>과제·힌트 대조</h4><p>{e(attachment)}</p></div>
      <div class="proposal"><h4>Tripothon 적용 제안</h4><p>{e(application)}</p></div></div></article>''')

coverage_rows = ''.join(f'<tr><td>{"캐릭터" if x["group"]=="character" else "환경"}</td><td><a href="#{x["group"]}-{Path(x["source"]).stem}">{e(Path(x["source"]).stem)}</a></td><td>{(raw_coverage(x) or {}).get("first",x["first_available_cue"])} – {(raw_coverage(x) or {}).get("last_cue_end",x["last_available_cue"])}</td><td>{coverage_status(x)}</td></tr>' for x in INDEX)
gates = ''.join(f'<tr><th>{e(a)}</th><td>{e(b)}</td><td>{e(c)}</td><td>{e(d)}</td></tr>' for a,b,c,d in GATES)
archives = json.loads((AUDIT / 'nested-archive-inventory.json').read_text(encoding='utf-8'))
archive_rows = ''.join(f'<tr><td>{e(group)}</td><td>{e(Path(x["path"]).name)}</td><td>{len(x["files"])}</td><td>{e(", ".join(f"{k}: {v}" for k,v in x["types"].items()))}</td></tr>' for group, items in archives.items() for x in items if 'files' in x)
audit_rows = ''
for x in BLENDS:
    if 'identical_to' in x:
        status = '동일 SHA-256의 다른 파일 참조'
    elif 'error' in x:
        status = '열기 실패: ' + x['error']
    else:
        meshes=[o for o in x['objects'] if o['type']=='MESH']
        rigs=[o for o in x['objects'] if o['type']=='ARMATURE']
        status=f'메시 {len(meshes)} / 리그 {len(rigs)} / 액션 {len(x["actions"])} / Shape Key 있는 메시 {sum(bool(o["shape_keys"]) for o in meshes)}'
    relative=Path(x['path']).relative_to(AUDIT / 'assignment-assets')
    audit_rows += f'<tr><td>{e(str(relative))}</td><td>{e(status)}</td></tr>'

figures=[
 ('character-Sculpt-1.png','스컬프 시작 예제: 몸과 따로 놓인 부위'),
 ('character-Sculpt_complete-1.png','스컬프 완료 예제: 비율과 접합을 수정한 형태'),
 ('character-Uv_complete-1.png','UV 단계의 저해상도 캐릭터 예제'),
 ('environment-lesson5-1.png','환경 조립 시작: 재사용할 부품'),
 ('environment-lesson5(complete)-1.png','환경 조립 완료: 시장 가판대와 바닥'),
 ('character-rig_complete-1.png','리깅 예제의 1프레임'),
 ('character-rig_complete-30.png','리깅 예제의 30프레임'),
 ('character-rig_complete-60.png','리깅 예제의 60프레임'),
]
gallery=''
for filename,caption in figures:
    shutil.copy2(AUDIT/'previews'/filename,REPORT/'media'/filename)
    gallery+=f'<figure><a href="media/{e(filename)}" target="_blank"><img src="media/{e(filename)}" loading="lazy" alt="{e(caption)}"></a><figcaption>{e(caption)}</figcaption></figure>'

document=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stefan 강의 검토 · Tripothon 제작 기준</title>
<style>
:root{{--ink:#22322e;--muted:#64746e;--line:#d9e2dc;--paper:#f6f7f2;--accent:#225f50}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth;scroll-padding-top:30px}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.8 'Segoe UI','Malgun Gothic',sans-serif}}main{{max-width:1240px;margin:auto;padding:42px 28px 90px}}h1{{font-size:38px;line-height:1.3;margin:16px 0}}h2{{font-size:27px;margin-top:55px}}h3{{font-size:22px;margin:0 0 14px}}h4{{font-size:15px;color:var(--accent);margin:12px 0 4px}}p{{margin:8px 0 16px}}a{{color:var(--accent)}}.eyebrow,.source,.small{{font-size:13px;color:var(--muted)}}.notice{{background:#fff4d8;border-left:5px solid #c38b28;padding:18px 24px;border-radius:8px}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}}.stat{{background:white;border:1px solid var(--line);padding:18px;border-radius:12px}}.stat b{{display:block;font-size:31px}}nav{{background:#e9efea;padding:20px 26px;border-radius:12px}}nav ol{{columns:2;padding-left:24px;margin:0}}article{{background:white;border:1px solid var(--line);border-radius:14px;padding:24px;margin:18px 0}}.lesson-grid{{display:grid;grid-template-columns:1.4fr 1fr;gap:25px}}.proposal{{background:#edf4ef;padding:12px 20px;border-radius:9px}}.table-scroll{{overflow:auto;border:1px solid var(--line);border-radius:10px}}table{{border-collapse:collapse;width:100%;background:white;font-size:14px}}th,td{{text-align:left;padding:14px 16px;border-bottom:1px solid var(--line);vertical-align:top}}th{{background:#eaf0eb}}td{{overflow-wrap:anywhere}}.gallery{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}}figure{{margin:0;background:white;border:1px solid var(--line);border-radius:12px;overflow:hidden}}figure img{{display:block;width:100%;height:auto}}figcaption{{padding:12px 18px;font-size:14px}}li{{margin:8px 0}}.flow{{display:flex;gap:8px;flex-wrap:wrap}}.flow span{{border:1px solid var(--line);padding:8px 14px;background:white;border-radius:8px}}.flow span:not(:last-child)::after{{content:' →';color:#6c9486}}@media(max-width:800px){{main{{padding:22px 16px}}h1{{font-size:29px}}.stats{{grid-template-columns:repeat(2,1fr)}}.lesson-grid,.gallery{{grid-template-columns:1fr}}nav ol{{columns:1}}}}@media print{{body{{background:white}}main{{padding:0}}article,figure{{break-inside:avoid}}nav{{display:none}}}}
</style></head><body><main>
<div class="eyebrow">TRIPOTHON · 2026-10-04 · 강의 근거와 제작 제안 구분</div>
<h1>Stefan 강의 검토와<br>캐릭터·맵 제작 기준</h1>
<div class="notice"><b>검토 상태: 제공 자료 분석 완료 / 스컬프팅 본문·과제 온라인 확인</b><p>2026-10-04에는 로그인된 스컬프팅 강의 본문과 과제를 정상적으로 읽었다. 제공 ZIP의 해당 자막·힌트와 대조했으며, 온라인 전체 과목의 과제·퀴즈·추가 첨부 및 영상 전체 시청은 아직 완료하지 않았다.</p><p><a href="https://learn3dai.teachable.com/courses/ai-x-3d/lectures/65393569">스컬프팅 강의</a> · <a href="https://learn3dai.teachable.com/courses/ai-x-3d/lectures/65393574">스컬프팅 과제</a>: 참조 비율과 위치 조정 → 좌우 대칭 → 기존 부위 제거와 교체 → 필요한 곳의 브러시 수정 순서다. 모든 부품의 Remesh는 요구하지 않는다. 우리 P2 메쉬에는 국소 연결 수정을 우선하고, 교체 가능한 머리카락·의복은 독립 유지한다. 전신 Remesh가 필요하다면 별도 스컬프 복사본에서 검토한다. 이것은 P2 토폴로지를 보존하기 위한 우리 프로젝트의 적용 방침이다. 정면·측면·후면·사선의 Solid 화면을 검토한 뒤 UV·리깅으로 넘어간다.</p></div>
<div class="stats"><div class="stat"><b>23</b>제공 자막 파일 검토</div><div class="stat"><b>13</b>힌트 문서 검토</div><div class="stat"><b>27</b>Blend 엔트리 구조 확인<br><span class="small">고유 파일 26개</span></div><div class="stat"><b>2 + 88</b>FBX 가져오기 + 이미지 확인<br><span class="small">원본 중복 포함</span></div></div>
<p><b>핵심:</b> 부위별 이미지를 새로 준비하고 독립 3D 파츠를 만든 뒤, Blender에서 형상·대칭·연속 표면을 다듬는다. 변형 가능한 저해상도 메시와 UV·베이크를 거쳐 리깅한다. 맵은 전체 콘셉트와 동선을 먼저 정하고 모듈·소품·식생·실내를 조립한다.</p>
<p>지난 캐릭터 조립본은 사용자가 품질을 거절한 실험본이다. 본 개수나 생성된 파일의 존재를 완료 기준으로 삼지 않는다. 다음 제작은 <b>리깅 없는 형태 검수</b>부터 다시 진행해야 한다. 사용자 요청에 따라 각 단계를 하나씩 승인받는다.</p>
<nav aria-label="목차"><ol><li><a href="#sculpt-brush-mask">브러시·마스킹 적용 기준</a></li><li><a href="#coverage">검토 범위와 누락 구간</a></li><li><a href="#character">캐릭터 전체 제공 강의</a></li><li><a href="#environment">맵 전체 제공 강의</a></li><li><a href="#examples">과제 예제의 실제 모습</a></li><li><a href="#gates">Tripothon 캐릭터 적용 순서</a></li><li><a href="#map">Tripothon 맵 적용 순서</a></li><li><a href="#corrections">기술 설명의 정정과 Godot 전환</a></li><li><a href="#supplement">추가 과제 기준 9장</a></li><li><a href="#next">다음 작업과 온라인 확인 항목</a></li><li><a href="#inventory">자료 목록과 재현 방법</a></li></ol></nav>
<section id="sculpt-brush-mask"><h2>브러시·마스킹 · 필수 작업과 검토 기준</h2>
<p>사용자의 2026-10-04 보완 요구: 위치·크기 조정과 부품 교체만으로 스컬프팅 완료라고 판단하지 않는다. 마스킹과 목적에 맞는 브러시 수정이 핵심 제작 단계다. 작업 전 원본을 보존하고 수정 복사본에서 수행하며, 현재 이 문서는 적용 계획이고 실제 브러시 작업 완료 기록은 아니다.</p>
<div class="table-scroll"><table><thead><tr><th>영역</th><th>마스킹과 작업</th><th>완료 기준</th></tr></thead><tbody>
<tr><td>기존 머리·손 제거</td><td>제거 영역을 Mask로 지정하고 보호 영역과 마스크 방향을 확인한 뒤 Mask Slice를 사용한다. 목·손목 접합 경계는 별도 관리한다.</td><td>몸통·팔의 보존할 형상이 손상되지 않고, 절단 후 중복 면과 불필요한 내부 면이 없다. 자동 Fill 결과도 따로 검사한다.</td></tr>
<tr><td>목·손목과 신체 실루엣</td><td>인접한 얼굴·손가락·의복은 마스크 또는 별도 객체로 보호한다. Grab / Elastic Grab으로 접합 단면과 실루엣을 조정한다. 필요한 볼륨만 Inflate / Clay로 보강한다.</td><td>참조 비율이 유지되고 목·손목이 꺾이거나 비정상적으로 얇아지지 않는다. Inflate로 외관이 닿았다는 이유만으로 연결됐다고 판단하지 않는다.</td></tr>
<tr><td>얼굴의 입꼬리·콧방울 핀칭</td><td>승인된 눈·입 실루엣과 주변 얼굴을 보호하고 작은 영역에 낮은 강도의 Smooth를 적용한다. 부족한 볼륨은 필요한 경우만 보강한다.</td><td>핀칭이 줄고 승인된 얼굴 인상이 유지된다. 눈·눈썹·속눈썹을 한꺼번에 리메시하지 않는다.</td></tr>
<tr><td>손·머리카락의 디테일</td><td>손톱·손가락 사이 간격·머리카락 가닥 경계를 보호한다. 생성 노이즈와 접합부에 한정해 Smooth / Grab을 사용한다. 의도된 비대칭 머리 가르마는 유지한다.</td><td>손가락이 붙거나 가닥이 뭉개지지 않는다. 손목 위의 작은 열린 경계는 면 연결 작업으로 별도 수리한다.</td></tr>
</tbody></table></div>
<p>강의의 브러시·마스크 원리를 우리 P2 자산에 적용한 계획이다. 실제 접합은 경계와 면 구조를 검사하고 Bridge/Weld 등으로 처리하며, Remesh가 필요하면 별도 스컬프 복사본에서 평가한다. 브러시 변형과 위상 연결은 서로 다른 작업으로 기록한다.</p>
<p><b>검토 자료:</b> 작업 전후 동일 각도 비교, 마스크가 표시된 화면, 사용 브러시와 수정 부위 기록, 정면·측면·후면·사선 Solid 화면, 접합부 Wireframe. 사용자 검토 후 UV·리깅으로 진행한다. 출처: 온라인 스컬프팅 본문·과제 및 제공된 <code>character__lesson-03-hints.txt</code>.</p></section>
<section id="coverage"><h2>1. 무엇을 실제로 검토했는가</h2>
<p>원본은 Desktop의 stefan_character_files.zip / stefan_environment_files.zip이다. 두 ZIP의 내부 ZIP 25개를 목록화하고, 실습 파일 130개를 별도 사본으로 풀었다. 자막 파일 23개와 힌트 13개를 읽었으며, 27개 Blend 엔트리와 FBX 2개를 Blender 4.5.3 LTS에서 검사했다. 참조·UV·베이크·PBR 이미지 88개는 컨택트 시트로 확인했다. 숫자는 중복 파일을 포함한다.</p>
<p>자막은 HAR에 캡처된 응답의 일부다. 시작/종료 시각이 영상 전체 길이 또는 중간 구간의 연속성을 보증하지 않는다. 특히 Sculpt·Retopology·Texturing·Rigging, 환경 조립 강의의 앞부분을 보완해야 한다. 일부 예제를 실제로 렌더한 것은 영상 속 클릭·선택·브러시 동작을 모두 확인한 것과 다르다.</p>
<p><b>원본 재확인:</b> 23개 중 11개는 자막 시작이 0초 근처이고 마지막 종료가 파일 안의 재생 목록 길이와 일치한다. 따라서 모든 파일의 자막이 일부뿐인 것은 아니다. 나머지에는 앞/끝 텍스트 누락이 확인된다. 예를 들어 Sculpt는 자막 응답 284건 중 115건, 환경 Assemble은 472건 중 370건에 실제 텍스트 본문이 없다. 요청 기록 또는 HTTP 200 성공 기록의 존재만으로 자막 내용이 저장됐다고 볼 수 없다. 10초 이상의 자막 간격은 무음 구간일 수도 있어 그 자체로 누락으로 단정하지 않았다.</p>
<div class="table-scroll"><table><thead><tr><th>과정</th><th>파일 / 상세로 이동</th><th>가용 자막 시각</th><th>상태</th></tr></thead><tbody>{coverage_rows}</tbody></table></div></section>
<section id="character"><h2>2. 캐릭터 강의 · 제공된 본편 9개 + 보너스 4개</h2>{''.join(s for s in sections if 'id="character-' in s)}</section>
<section id="environment"><h2>3. 맵 강의 · 도구 + 본편 7개 + 보너스 2개</h2>{''.join(s for s in sections if 'id="environment-' in s)}</section>
<section id="examples"><h2>4. 과제 파일에서 직접 확인한 모습</h2><p>아래는 강의의 실습 파일을 직접 연 회색 형상 검토 렌더다. 우리 게임 모델이 아니며, 재질·노멀·엔진 성능이나 자연스러운 전체 애니메이션을 검증한 화면도 아니다. 시작/완료 쌍을 비교해 작업 구조를 파악하기 위한 자료다. 이미지를 누르면 크게 볼 수 있다.</p><div class="gallery">{gallery}</div>
<p>스컬프 과제, UV 과제, 리깅 과제는 모두 같은 시연 캐릭터의 연속 파일이라고 볼 수 없다. 리깅 예제에는 Shape Key가 없고, 1·30·60·90 프레임의 포즈 비교만 확인했다. 이를 정교한 페이스 리깅이나 보행 제작의 완성된 참고로 사용하면 안 된다.</p></section>
<section id="gates"><h2>5. 우리 캐릭터 제작 순서와 승인 기준</h2><div class="flow">{''.join(f'<span>{e(g[0])}</span>' for g in GATES)}</div>
<p><b>개발용 캐릭터 제작에 대한 제안</b>이다. 플레이어의 가구 생성 서비스에 이 전체 공정을 요구하지 않는다. 원본 이미지·파츠는 그대로 보존하고, 새 버전의 작업물만 분리해 제작한다.</p>
<div class="table-scroll"><table><thead><tr><th>단계</th><th>결과물</th><th>검수</th><th>진행 조건</th></tr></thead><tbody>{gates}</tbody></table></div>
<p><b>부위 분리와 신체 접합의 관계:</b> 원본 머리·몸·손은 각각 편집 가능하게 남긴다. 이번 추가 이미지 3은 모든 파츠를 Remesh로 꿰맬 필요가 없고 상황에 따라 부품을 배치하고 접합부 외관을 정리하는 것으로 충분하다고 명시한다. 따라서 연속 표면 또는 용접을 모든 부위의 필수 기준으로 강제하지 않는다. 우리 캐릭터에서는 노출 경계와 움직일 때의 틈·겹침을 기준으로 연결 방식을 정한다. 재킷·바지·머리카락·장식을 몸과 함께 Remesh하지 않으며, 컬렉션 분류나 Ctrl+J만으로 품질이 확보됐다고 판단하지 않는다.</p>
<p><b>애니메이션 검수:</b> 이동 거리/클립 주기와 보행 속도를 맞추고 발 미끄러짐을 본다. idle↔walk↔run, 시작/정지, 급회전, 경사, 충돌 중 전환을 최종 카메라와 근접 카메라에서 비교한다. in-place 또는 root motion 중 이동 책임을 하나로 정해 중복 이동을 막는다. 전환 시간·위상·루트 좌표 검사를 기록하며 이것은 아직 수행된 게임 검증이 아니다.</p></section>
<section id="map"><h2>6. 우리 맵 제작 순서</h2><ol>
<li><b>공간 계획:</b> 기존 승인된 맵 콘셉트를 기준으로 전체 동선, 구역, 주요 지점, 실내 진입과 생존 활동 공간을 블록아웃한다. Godot의 실제 캐릭터 크기·카메라로 검토한다.</li>
<li><b>모듈 규격:</b> 건물 벽/지붕/문, 길/바닥, 지형과 난간의 스케일·원점·접합 규칙을 정한다. 구조가 단순하고 규격적인 것은 Blender에서 만든다.</li>
<li><b>참조와 고유 소품:</b> 영역별 팔레트와 개별 참조를 승인한다. 독특한 소품에 Tripo를 쓰고 실패한 문·구멍·얇은 판은 직접 수정한다.</li>
<li><b>재질·식생:</b> tileable PBR, 알파 잎/가지, 줄기·바위 변형을 준비한다. UV 크기와 Godot의 alpha/culling/shadow를 확인한다.</li>
<li><b>Blender 조립:</b> 고유 건물·큰 구조물을 편집 가능한 모듈로 조립한다. 실내는 큰 가구와 사용 동선부터 만들고 작은 장식을 더한다.</li>
<li><b>Godot 검증:</b> 반복 식생은 엔진에서 배치하고 충돌·내비게이션·출입·가구 배치·카메라 가림을 확인한다. 조명·물·바람·낙엽은 엔진 효과로 만든다.</li>
<li><b>최적화:</b> 실루엣과 플레이 시야를 지키면서 필요에 따라 LOD·인스턴싱·텍스처 아틀라스·불필요한 면 제거를 사용한다. 수업 예제의 숫자를 전체 게임 예산으로 복사하지 않는다.</li></ol></section>
<section id="corrections"><h2>7. 강의 설명을 그대로 복사하면 안 되는 부분</h2><ul>
<li><b>Face Orientation:</b> 공급 힌트에 앞/뒤 색을 뒤집어 설명한 부분이 있다. 기본 Blender 오버레이는 앞면 파랑·뒷면 빨강이다. 테마 색 변경 가능성도 있으므로 실제 노멀 방향을 검사한다. <a href="https://docs.blender.org/manual/id/4.2/editors/3dview/display/overlays.html">Blender 공식 오버레이 설명</a></li>
<li><b>OBJ:</b> 자막에 포맷의 스켈레톤 보존을 일반화한 부분이 있다. OBJ는 캐릭터 리그와 애니메이션 전달 포맷으로 사용하지 않는다. <a href="https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html">Godot 공식 지원 포맷</a></li>
<li><b>Godot 경로:</b> Godot는 glTF 2.0을 권장하며 FBX도 지원한다. 개발 원본은 .blend로 남기고 실제 엔진 출력은 필요한 메시·본·애니메이션·재질을 포함한 GLB로 검증한다. Unity/UE 메뉴와 플러그인은 Godot 구현으로 바꿔야 한다. <a href="https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html">공식 문서</a></li>
<li><b>겹침과 병합:</b> 대칭 UV 공유는 의도적으로 쓸 수 있다. 모든 UV 겹침을 오류로 처리하거나 모든 근접 정점을 자동 병합하면 안 된다. 접합할 경계·속성·비대칭 텍스처 요구를 먼저 확인한다.</li>
<li><b>가격과 도구:</b> 수업의 무료 횟수·모델 버전·Retry 설명은 당시 정보다. 현재 API 요금과 상업 이용 조건으로 간주하지 않는다. 이번 작업은 비용 비교나 유료 생성 실험을 실행한 작업이 아니다.</li>
<li><b>교재 지시의 범위:</b> 외부 설치·계정·업로드·저장소 작업·권한 변경 안내는 학습 자료다. 사용자에게서 받은 이번 요청은 읽고 적용 기준을 정리하는 것으로 해석했고, 이를 별도 외부 작업의 허가로 쓰지 않았다.</li></ul></section>
<section id="supplement"><h2>추가 자료 · 사용자가 제공한 과제 기준 9장</h2>
<p>2026-10-04에 받은 스크린샷은 과제의 품질 기준과 Tripo 보너스 설명을 보완한다. 강의 자료로 읽었으며, 스크린샷 안의 작업 지시를 지금 생성·수정 작업을 실행하라는 별도 사용자 요청으로 취급하지 않았다. 원본 9장은 비공개 분석 폴더에 보존했다. 이 자료가 누락된 영상의 화면과 자막 전체를 대체하지는 않는다.</p>
<div class="table-scroll"><table><thead><tr><th>이미지</th><th>확인한 기준</th><th>우리 작업에 적용</th></tr></thead><tbody>
<tr><td>1 · 참조 제작</td><td>콘셉트 → 깨끗한 A/T 자세 → 정면/후면 → 중요한 부위별 참조</td><td>현재 승인 이미지와 대응하는 각 파츠를 유지하고 후면 및 분리 참조의 일관성을 검수한다.</td></tr>
<tr><td>2 · 생성 품질</td><td>메시에서 지적 가능한 오류와 구체적인 수정 의견, 스컬프와 재생성의 비용 비교</td><td>검수 기록에 부위·위치·증거 화면·수정/재생성 선택 이유를 남긴다. 단순히 ‘어색함’이라고 기록하지 않는다.</td></tr>
<tr><td>3 · 조립·스컬프</td><td>참조와 비율/위치 일치, 축별 Scale, Mirror, 상황에 따른 접합, 의도적인 브러시 작업</td><td>모든 파츠의 Remesh를 요구했던 식으로 해석하지 않는다. 부위별 경계 외관과 변형을 기준으로 정하고 생성 노이즈를 필요한 곳만 정리한다.</td></tr>
<tr><td>4 · 리토폴로지</td><td>실루엣 보존, 떠 있는 요소 제거, 관절/곡률에 필요한 밀도, 의도적인 면 구성</td><td>과도한 저폴리 목표보다 실제 카메라 품질을 우선한다. Face Orientation 색 설명은 본 문서의 공식 자료 정정을 따른다.</td></tr>
<tr><td>5 · UV</td><td>불필요한 심·왜곡·겹침을 줄이고 Stretch로 검사, 대칭에는 Mirror 활용</td><td>실습의 3개 재질 배분은 그 예제의 규칙이다. 우리 의복 교체와 색칠 요구에 맞춰 재질/마스크를 설계하며 의도된 대칭 공유를 따로 기록한다.</td></tr>
<tr><td>6 · 베이크</td><td>고/저해상도 실루엣 일치, 미세 디테일의 적절한 생략, Scale/Rotation 적용, 아티팩트 보정</td><td>리깅 전 일관된 변환을 확정하고 bake 설정을 기록한다. 작은 베이크 오류 보정과 형상 오류 수정을 구분한다.</td></tr>
<tr><td>7 · 웨이트</td><td>팔을 움직일 때 무관한 다리/발이 끌려오지 않도록 잘못된 본 영향을 제거</td><td>부위별 극단 포즈로 영향 범위를 검수하고 웨이트 정규화와 실제 재배분까지 확인한다.</td></tr>
<tr><td>8 · HD / Smart Mesh</td><td>HD는 고해상도 원본→리토폴로지→베이크, Smart Mesh는 직접 저해상도 생성. 머리카락·단순 부품과 상세 의복은 다른 경로가 적합할 수 있다.</td><td>HD가 항상 고폴리 출력이라는 단순 분류를 피하고 생성 설정과 출력 구조를 기록한다. 깨끗한 직접 참조·추가 시점·Solid/Unlit 검수 후 부위별 경로를 선택한다.</td></tr>
<tr><td>9 · P2</td><td>부품별 생성, 여러 폴리곤 목표 비교, 뒤쪽 표면과 연결 구조 확인, 상세 의복은 고해상도 경로, 형상 검토 후 텍스처</td><td>숫자를 모든 부위에 복사하지 않는다. Quad 모드도 관절 루프나 깨끗한 연결을 보장하지 않으므로 직접 검사한다.</td></tr>
</tbody></table></div>
<p>Tripo 버전·무료 Retry·모델 순위·폴리곤 상한·Ultra 권장 등은 수업 촬영 당시 설명이다. 현재 API 제공 기능과 비용으로 단정하지 않는다. 이번 자료 반영에서는 생성 API를 호출하지 않았다.</p></section>
<section id="next"><h2>8. 다음에 할 일과 아직 남은 수강 확인</h2><p><b>다음 제작 단위:</b> 캐릭터의 리깅 없는 형태 검수본 1개. 원본 파츠를 보존하며 목·손목의 경계 외관과 연결 방식, 좌우 대칭, 몸과 재킷/셔츠/바지의 간격, 손가락 형태를 검토한다. 정면·측면·후면·근접 렌더를 사용자가 확인한 뒤 UV·리깅으로 넘어간다. 현재 거절된 조립본을 완료 상태로 재사용하지 않는다.</p>
<p><b>온라인 확인이 선행되어야 할 항목:</b></p><ul>
<li>두 과정의 실제 최신 섹션/강의/영상 목록과 lesson page 본문 전체.</li>
<li>assignment / quiz의 실제 문항·제출 기준, 모든 다운로드·starter·solution·hint 목록.</li>
<li>자막 앞부분이 누락된 Sculpt·Retopology·UV·Texturing·Rigging, 환경 Refine·Assemble·Interior·UE 설정의 영상 화면.</li>
<li>환경 Smart Mesh P2 전체, 조립 timelapse, 전체 UE 프로젝트, 실내 완성 파일, 캐릭터 엔진 이식 자료.</li>
<li>페이스·머리카락·보조 본 관련 추가/보너스 자료가 실제로 있는지. 현재 공급 자료에 없는 상세 페이스 과정을 수업에 있다고 추정하지 않는다.</li></ul>
<p class="notice">스컬프팅 강의와 과제는 로그인된 탭에서 접근을 확인했다. 나머지 온라인 과목과 전체 영상 시청의 완료 여부는 별도로 기록한다. 스컬프팅 자막의 로컬 제공 범위는 약 09:00–25:51이며, 앞부분은 해당 자막 파일에 없다.</p></section>
<section id="inventory"><h2>9. 첨부 자료 목록과 재현</h2><details><summary>25개 내부 ZIP의 구성 보기</summary><div class="table-scroll"><table><thead><tr><th>과정</th><th>압축 파일</th><th>파일 수</th><th>종류</th></tr></thead><tbody>{archive_rows}</tbody></table></div></details>
<details><summary>27개 Blend 엔트리의 구조 확인 보기</summary><div class="table-scroll"><table><thead><tr><th>상대 경로</th><th>검사 결과</th></tr></thead><tbody>{audit_rows}</tbody></table></div></details>
<p>원본 ZIP과 프로젝트 캐릭터 파일은 수정하지 않았다. Blender 파일은 자동 스크립트 실행을 끈 상태로 읽고, 구조 검사와 일부 형상 렌더만 수행했다. 구버전 색공간 이름에 대한 경고가 있어 실제 재질 이식은 후속 검증이 필요하다. FBX 2개도 별도 빈 씬에 가져와 검사했고 원본에 저장하지 않았다.</p>
<p>비공개 원자료/메타데이터: <code>artifacts/stefan-course-audit-20261004/</code> · 자막: <code>artifacts/stefan-study/</code> · 실행 도구: <code>tools/inventory_stefan_course_materials.py</code>, <code>extract_stefan_assignment_assets.py</code>, <code>blender_audit_stefan_assignments.py</code>, <code>blender_audit_stefan_fbx.py</code>, <code>blender_preview_stefan_assignments.py</code>, <code>build_stefan_course_review.py</code>.</p>
<p>보고서 재생성: <code>.tools/server-venv/Scripts/python.exe tools/build_stefan_course_review.py</code><br>표시 서버: <code>.tools/server-venv/Scripts/python.exe tools/serve_production_review.py --port 8842</code> (동일 포트 서버가 이미 실행 중이면 추가 실행하지 않는다.)</p>
<p>공개 소개: <a href="https://learn3d.ai/ai-x-3d">캐릭터 과정</a> · <a href="https://learn3d.ai/ai-x-3d-environments">환경 과정</a> · <a href="https://learn3dai.teachable.com/l/dashboard">수강 대시보드</a>. 이 로컬 검토 문서는 인터넷에 게시하지 않았고 유료 강의 원본이나 HAR 인증 정보를 웹 루트에 넣지 않았다.</p></section>
</main></body></html>'''
(REPORT/'index.html').write_text(document,encoding='utf-8')
# Store the review in docs too, with relative media for an offline copy.
offline=ROOT/'docs/stefan-course-review-20261004'
offline.mkdir(parents=True,exist_ok=True)
shutil.copytree(REPORT/'media',offline/'media',dirs_exist_ok=True)
(offline/'index.html').write_text(document,encoding='utf-8')
(AUDIT/'review-status.json').write_text(json.dumps({
 'date':'2026-10-04','status':'supplied_materials_reviewed_sculpting_online_text_verified',
 'online_text_reviewed':[{'lesson':'Sculpting','lecture_url':'https://learn3dai.teachable.com/courses/ai-x-3d/lectures/65393569','assignment_url':'https://learn3dai.teachable.com/courses/ai-x-3d/lectures/65393574','full_video_watched':False}],
 'online_complete':False,'full_videos_watched':False,'project_assets_modified':False,
 'caption_files':len(INDEX),'assignment_members':len(ASSETS),
 'types':dict(Counter(Path(x['path']).suffix for x in ASSETS)),
 'blend_entries':len(BLENDS),'blend_open_errors':[x for x in BLENDS if 'error' in x],
 'fbx_import_errors':[x for x in FBXS if 'error' in x],
 'review':str(offline/'index.html')},ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved',offline/'index.html')
print('URL http://127.0.0.1:8842/stefan-course-review/')
