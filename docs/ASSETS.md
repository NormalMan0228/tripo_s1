# 에셋 기록 · 2026-10-01

Scenario 프로젝트: `Tripothon Seven Nights`

- 탐험가 원화: `asset_GMk13nSmyBDeh968kQKrTtrk`, GPT Image 2, 11 CU. 생성 완료 및 JPG 다운로드 확인. 게임 로그인 화면과 디자인 참고에 사용.
- 탐험가 3D: `asset_8xB8NQ8Jr4egQRMfTjoYvJS2`, Hunyuan 3D 2.1, 46 CU. 40,000 삼각형. 묶음 ZIP 내보내기로 다운로드하여 `game/assets/explorer.glb`에 적용. 키/개인 물건과 무관한 공용 게임 아트다.
- 공방 3D: `asset_Wc2ewBfctaEvm4jGJE8E4nMG`, Meshy 7.1 Text-to-3D, 120 CU. 6,000면 목표, 실제 5,630 삼각형, 2K PBR 설정. 흰 벽·기와지붕·청록색 문으로 요청했고 `game/assets/workshop.glb`에 적용. 생성 결과에는 작은 바닥 받침이 포함되어 있다.
- 탐험가 리깅·동작: Scenario의 Tripo Rigging 1.0 Biped. 걷기 `asset_ss853o1pgJDKHGJmoCRAUD2d`, 대기 `asset_2jK74GPGLGSpb9myyxXvyEUb`, 리깅 기본 모델 `asset_R8PkbZso9fQAfAoAqY4FLwLN`. `tripothon-animated-explorer.zip`으로 실제 다운로드했다. 동일한 노드·스킨임을 검사한 뒤 `tools/merge_explorer_animations.py`로 걷기·대기를 한 GLB에 병합했다. 걷기 Hip의 순수 수평 이동량만 제거하고 뼈대 동작·상하 움직임·텍스처는 보존한다.
- 검토용 오디오: ElevenLabs Music v2.5, 각 30초. 숲 `asset_cai6G1rBXctrrxwLhUzLeLPv`, 마을 `asset_76Bm2g66LTiXz5tLJVprnAun`. 숲 상세 화면에서 30 CU 확인. 두 결과의 자동 설명이 각각 낭독·개 짖는 소리로 표시되어 프롬프트와 일치하지 않았다. 실제 청취 품질을 확인하지 못했으므로 게임에 적용하지 않았다. 원본은 사용자 Downloads의 `tripothon-audio.zip`에 보관하며 배포 ZIP에는 포함하지 않는다.
- 에셋별 확인 비용만 기록했다. 계정의 전체 사용량과 결제 설정은 공개 저장소에 포함하지 않는다.

원화 프롬프트 요약: 청록 머리와 목도리, 호박색 우비, 작은 배낭과 갈색 부츠를 착용한 숲 탐험가. 정면 A 포즈, 단순 파스텔 3D 형태, 흰 배경. 다른 게임의 캐릭터를 복제하도록 요청하지 않음.

나무·자원·그림자 적·도구·의자 GLB·별씨 SVG와 캐릭터/집의 대체 도형은 직접 만들었다. 클릭·채집·제작·식사·불·타격·피해·오류·보상 효과음 9종도 코드로 직접 합성한다. Blender는 사용하지 않았다.

0.4 개선에서 해안 지형·산책길·돌 광장·정원 소품·등불·돌문·외곽 수목·야영지와 4개 셰이더를 직접 작성했다. `tools/compose_ambience.py`는 외부 음원 없이 마을/숲용 32초 반복 곡을 PCM WAV로 합성한다. 두 파일은 mono 22,050 Hz, 16-bit이며 파형 최대값을 검사해 클리핑이 없음을 확인했다. 맵 이동 시 1.2초 크로스페이드, M 음소거를 제공한다. Scenario 생성 오디오와는 별도 자산이며 이 개선에는 Scenario 크레딧을 추가 사용하지 않았다.

단일 모델 다운로드는 파일 저장에 실패했지만, Select All → More → Download → Export로 만든 ZIP의 Download 링크는 정상 저장됐다. 탐험가 GLB에는 JPEG 바이트가 PNG MIME의 data URI로 기록되어 있었다. `tools/import_scenario_glb.py`가 내장 데이터만 허용하고 실제 이미지 형식에 맞춰 binary bufferView로 정리한다. 픽셀을 수정하거나 외부 URL에서 텍스처를 받지는 않는다.

Godot가 공용 GLB를 PackedScene으로 가져와 배포 PCK에 포함한다. 개인 생성 GLB는 별도 HTTP 바이트 로더를 사용한다. 두 경로를 혼동하면 안 된다. 탐험가 높이 1.7, 공방 최대 폭/깊이 4.8로 정규화했다. 캐릭터는 걷기/대기 애니메이션을 부드럽게 전환하며 BoneAttachment3D로 제작한 도구를 손에 연결한다. 0.4에서는 실제 렌더링 및 10개 동작 검사를 통과했고 공격·채집 전용 동작은 없었다. 아래 0.5에서 절차적인 행동 동작을 더하고 검사를 13개로 늘렸다.
# 0.5 생존 플레이 아트 추가 (2026-10-01)

이번 변경은 기존 캐릭터·공방 자산을 재사용했다. Scenario 유료 생성을 추가로 제출하지 않았다. 숲길·방향 표식·선착장 난간과 충돌, 그루터기·채집 조각, 그림자 짐승과 보행/공격 준비 자세는 코드로 만들었다. `game/assets/items/*.svg`의 자원·도구·음식 아이콘 8개는 `tools/create_item_icons.py`로 직접 작성한 벡터 아트다.

`action_pose.gd`는 기존 리깅에 채집·창 공격·피격·먹기 상체 자세를 겹친다. 별도의 생성 모션이나 추가 Tripo 호출이 아니다. 구현 시 [Godot SkeletonModifier3D 공식 문서](https://docs.godotengine.org/en/4.6/classes/class_skeletonmodifier3d.html)의 수정자 처리 순서를 참고했고, 설치된 Godot 4.7.2에서 실제 손/도구 위치와 포즈 적용을 검사했다.

## 0.6 Scenario Tripo 확장 (2026-10-01)

아래는 에셋별 생성 비용이다. Scenario CU와 게임 서버의 Tripo API 크레딧은 별개다.

| 용도 | Tripo 모델 | 비용 | 생성 원본 ID |
|---|---|---:|---|
| 미라 | P2 Text to 3D | 220 CU | `asset_jahwUGLY12LTpZqhcemqVhMJ` |
| 테오 | P2 Text to 3D | 220 CU | `asset_fDyyKQCqNBDcJB6tngQSd27U` |
| 이끼 수호자 | P2 Text to 3D | 220 CU | `asset_s1FsXdYe2LyJMHNQpMVTcWhJ` |
| 루·미라·테오 각각 idle/walk/run/slash, 수호자 idle/walk/slash | Rigging 1.0 Biped | 15 × 70 CU | `ASSETS_06.json`의 부모/결과 ID |
| 루·미라·테오 세부 부위 | Segmentation v2 Detailed | 3 × 80 CU | 아래 참조 |

- 루 분리: `asset_cgnnjV4rKCMhxaCR5kKsjQM3`, 45개 메시.
- 미라 분리: `asset_HqqCnqJ1G86hCK7i1Vbf5gRr`, 58개 메시.
- 테오 분리: `asset_wqZCSR1cueNgPXZosZGMoyyi`, 42개 메시.
- Rigging 2.5의 실제 UI에는 이족보행 선택이 없어 1.0 Biped를 사용했다. 루는 기존 idle GLB를 입력으로 4동작을 재생성했다. 라이브러리 선택 후 입력 ID를 확인해 다른 모델에 적용하는 일을 방지했다.
- 원본 묶음: 사용자 Downloads의 `tripothon-expansion-06.zip`. 검토·작업본: `artifacts/scenario-06/`. ZIP metadata의 부모 ID와 GLB animation 이름으로 동작을 식별했다. 수호자 원본은 묶음에 없지만 수호자의 3개 리깅 결과는 포함되어 있다.
- `tools/merge_character_clips.py`는 노드·스킨이 같은지 확인하고 idle/walk/run/slash를 병합한다. walk/run의 수평 root drift만 제거하며 상하 동작은 유지한다.
- `tools/partition_avatar.py`는 Tripo 분리 메시의 검토된 부위 번호(`tools/avatar_parts.json`)를 원래 리깅 메시로 옮긴다. 정규화한 표면의 최근접 거리 95백분위는 세 캐릭터 모두 0.000002 미만이었다. 원래 POSITION/NORMAL/UV/JOINTS/WEIGHTS를 보존하고 삼각형 인덱스를 재분배한다. 분리 결과를 다시 리깅하거나 관절마다 독립 객체로 붙이지 않는다.
- 최종 루 40,000 / 미라 13,455 / 테오 12,899 삼각형을 모두 보존했다. 머리·피부·상의·하의·신발·세부 장식, 루의 배낭을 별도 표면으로 관리한다. 텍스처 픽셀을 수정하지 않고 부위별 셰이더로 색을 바꾼다. 눈·입 등 얼굴의 명암은 원본 비율을 유지한다.
- 6.6초 slash 클립의 대기 구간을 제외하여 플레이어는 1.1~3.34초 부분을 0.7초에 재생한다. 수호자는 공격 예고/회복 시간에 맞춰 1.05초부터 재생한다. 도끼 손잡이 방향도 타격 시 도끼날이 지면을 향하도록 검토했다. 창·맨손·식사·피격은 기존 절차적 상체 동작을 사용한다.
- 모자 2종과 신규 캐릭터 배낭은 코드로 제작해 Head/Spine02 뼈에 연결했다. 루의 생성 배낭을 숨길 때 드러나는 등판은 별도 옷 도형으로 메운다. 이는 자유로운 의상 메시 교체 기능이 아니다.
- 불씨 도깨비, 추가 지역의 바위·균열·얼음·눈과 NPC 기능은 직접 작성했다. 수호자만 새 Tripo 몬스터 메시이며 나머지 적은 코드 기반 모델이다. Blender는 사용하지 않았다.

아트 전처리는 별도 `.tools/art-venv`에서 numpy 2.5.3, Pillow 12.3.0, scipy 1.18.1을 사용했다. 이 환경은 게임 서버 런타임이나 배포 ZIP에 넣지 않는다. 원본과 결과는 공용 게임 아트이며 개인 소유 GLB 전달 경로와 분리되어 있다.
# 0.8 아트 기준과 생성물 구분 · 2026-10-02

도끼/창은 `tools/build_authored_tools.py`에서 만든 개발자 공용 메시로 바꿨다. 단순 박스 날 대신 굽은 도끼날, 창날과 손잡이 감개를 만들고 기존 손 뼈대 부착과 손가락 파지를 유지한다. `artifacts/authored-environment/*-v1.blend` 원본과 `game/assets/authored_*_v1.glb`를 남겼다. 로그인 초상도 실제 Explorer B 렌더로 통일했다.

기본 주인공은 기존 컨셉 이미지와 Explorer B를 기준으로 한다. 손가락을 보강한 hand-v4의 원래 얼굴·메시를 유지하고 전용 TrailWalk/Dash 등 기존 제작 동작을 연결했다. 옷 색칠용 파생 파일은 삼각형의 재질 배정만 바꾸며 정점/UV/노멀/스킨 웨이트를 보존한다. 증거는 `artifacts/wardrobe-validation` 관련 결과와 `tools/prepare_explorer_b_avatar.py`에 있다. 얼굴 리깅을 새로 완성했다고 주장하지 않는다.

`game/assets/storybook_home_v1.glb`는 개발자가 Blender로 제작한 공용 건물이다. 소스는 `tools/build_authored_home.py`, 작업 파일은 `artifacts/authored-environment/storybook-home-v1.blend`다. 이는 플레이어의 런타임 생성에 Blender가 필요하다는 뜻이 아니다.

개인 가구의 실제 Tripo 결과는 `artifacts/furniture/runtime-comparison`, `artifacts/furniture/h3-comparison`, `artifacts/reference-chain`, `artifacts/chest-body-refinement`에 원본과 응답·비용 기록을 보존한다. 개인 DB와 함께 공개 패키지에서 제외한다. 검토용 웹 폴더에는 선택한 영상/스크린샷과 비밀 없는 모델 실험 결과만 복사한다.

정적 가구는 하나의 메시, 동적 가구는 별도 정적 부품을 제한된 숫자 프로그램으로 조립·동작시킨다. 이번 가구 동작은 Tripo 리타깃 애니메이션이 아니다. Tripo의 뼈대 애니메이션 기능과 가구의 힌지/회전/접근 반응은 다른 경로다. 손가락·얼굴이나 연성 물체를 이 가구 파이프라인이 자동 리깅하지 않는다.

0.8.1의 화덕·조리 냄비·장작(`build_authored_camp.py`), 채석장 층암과 눈 덮인 얼음 기둥(`build_authored_region_props.py`), 부드러운 층형 수관(`build_authored_cedar.py`)은 개발자가 Blender에서 만든 공용 환경 메시다. `.blend`는 `artifacts/authored-environment`, 실행용 GLB는 `game/assets/storybook_*_v1.glb`에 있다. 생성 API나 Scenario 크레딧을 쓰지 않았다. 수관은 하나의 재질 표면을 공유하고 나무마다 색·방향·높이와 캐릭터 가림 투명도를 별도로 적용한다. 장애물 중심·서버 반경은 유지한다. 불꽃은 `camp_flame.gdshader`의 절차적 효과다.

## 해루 낚시꾼 디자인 기준 · 2026-10-02

사용자가 제공한 해루 디자인 시트를 `game/assets/npc_haeru_design.png`로 보존한다. 핵심 특징은 자연스럽게 흐르는 짙은 남색 머리, 황갈색 낚시 조끼와 밝은 이너, 진청 바지, 갈색 장화, 밝고 느긋한 인상이다. 기존 마을 NPC `tinker.glb`의 부위 색을 이에 맞추고, Godot 대화창은 원본 시트의 초상 영역을 `AtlasTexture`로 표시한다. 이는 **기존 3D 모델의 색 조정과 2D 초상 적용**이며, 시트의 정면·측면·후면을 재현한 신규 3D 모델이나 얼굴 표정 애니메이션을 완성했다는 뜻이 아니다. 새 Tripo·Scenario 생성 비용은 사용하지 않았다.
