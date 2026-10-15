# 클라이언트 성능 감사 — 자산 인수인계 부록

2026-10-16, 0.11.8 기반 worktree의 정적 분석. [주 보고서](PERF_AUDIT_CLIENT_KO.md), [감사 JSON](../artifacts/perf_audit_client.json)을 함께 본다. 이 부록의 자산·맵·셰이더 변경안은 **아직 적용하지 않았다**. Godot 실행, 외부 다운로드, `project.godot` 및 맵·건물 자산 수정도 하지 않았다.

기본 캐릭터의 이미지 공유·메모리, Haeru의 4K 이미지, 작은 파티클 메시, 장착 도구의 표면 수를 우선 검토한다. 맵 원본은 로컬에 없어 별도 인수인계 목록으로 분리했다. 이미지 헤더·삼각형·해시는 확인값이지만 FPS 개선량은 측정하지 않았다. 목표 해상도와 삼각형 수는 후속 비교의 시작점이며, 품질 유지가 검증된 최종값은 아니다.

## 1. 존재하는 텍스처 파일별 변경안

아래 24개 `.import`는 현재 모두 `compress/mode=0`, `mipmaps/generate=true`, `process/size_limit=0`이다. 각 파일의 `process/size_limit`을 표의 값으로 바꾸어 비교하고, PC 대상에서 GPU 블록 압축 `compress/mode=2`도 별도로 비교한다. `mipmaps/generate=true`는 유지한다. 축소와 압축을 하나씩 비교해 얼굴·의상·글씨 손실 및 노멀 채널·방향·밴딩 문제를 구분한다.

RGBA8 전체 mip 근사치는 `가로×세로×4 bytes×4/3`이다. 4K→2K는 이미지당 85.33→21.33 MiB, 2K→1K는 21.33→5.33 MiB다. 실제 RGB/노멀 포맷·압축·mip 제한·공유에 따라 달라지는 상한 비교이며, 압축 절감과 해상도 절감을 같은 기준에서 중복 합산하지 않는다. Haeru 2장을 축소하면 이 기준에서 128 MiB가 줄어든다. B 3개 모델의 이미지 6장을 독립 GPU 리소스로 가정해 더하지 않는다.

| 파일·줄 | 원본→비교 | 설정 변경안 | 사용 범위 |
| --- | --- | --- | --- |
| `game/assets/haeru_v1_Color_ab7bce27-520e-4bb3-bbaa-d4905b50580a.jpg.import:42` | 4096²→2048² | `process/size_limit=2048`; `compress/mode=2` 비교 | Haeru 선택 시; `player.gd:110` |
| `game/assets/haeru_v1_NormalGL_ab7bce27-520e-4bb3-bbaa-d4905b50580a.png.import:42` | 4096²→2048² | `process/size_limit=2048`; `compress/mode=2` 비교 | Haeru 선택 시; `player.gd:110` |
| `game/assets/explorer_b_motion_Color_c7562c44-0e5c-4eca-8a99-cc67f09222d2.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 기본B·주민·미리보기; 공용 이미지 참조 우선 |
| `game/assets/explorer_b_motion_NormalGL_c7562c44-0e5c-4eca-8a99-cc67f09222d2.png.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 기본B·주민·미리보기; 공용 이미지 참조 우선 |
| `game/assets/explorer_b_reference_Color_c7562c44-0e5c-4eca-8a99-cc67f09222d2.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 기본B·주민·미리보기; 공용 이미지 참조 우선 |
| `game/assets/explorer_b_reference_NormalGL_c7562c44-0e5c-4eca-8a99-cc67f09222d2.png.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 기본B·주민·미리보기; 공용 이미지 참조 우선 |
| `game/assets/explorer_b_wardrobe_Color_c7562c44-0e5c-4eca-8a99-cc67f09222d2.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 기본B·주민·미리보기; 공용 이미지 참조 우선 |
| `game/assets/explorer_b_wardrobe_NormalGL_c7562c44-0e5c-4eca-8a99-cc67f09222d2.png.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 기본B·주민·미리보기; 공용 이미지 참조 우선 |
| `game/assets/explorer_0.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 레거시 explorer; 중복 쌍 참조 정리 먼저 |
| `game/assets/explorer_1.png.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 레거시 explorer; 중복 쌍 참조 정리 먼저 |
| `game/assets/explorer_Image_0.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 레거시 explorer; 중복 쌍 참조 정리 먼저 |
| `game/assets/explorer_Image_1.png.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 레거시 explorer; 중복 쌍 참조 정리 먼저 |
| `game/assets/brute_Color_96a7ca89-ad0f-4798-81d0-5bc337026eb8.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | brute 대체 모델; `shadow_beast.gd:178` |
| `game/assets/brute_NormalGL_96a7ca89-ad0f-4798-81d0-5bc337026eb8.png.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | brute 대체 모델; `shadow_beast.gd:178` |
| `game/assets/brute_ORM_96a7ca89-ad0f-4798-81d0-5bc337026eb8.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | brute 대체 모델; `shadow_beast.gd:178` |
| `game/assets/ranger_Color_aa9528be-a8f3-406a-b977-22d84e7d1e4c.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 선택형 레거시 캐릭터; `player.gd:157` |
| `game/assets/ranger_NormalGL_aa9528be-a8f3-406a-b977-22d84e7d1e4c.png.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 선택형 레거시 캐릭터; `player.gd:157` |
| `game/assets/ranger_ORM_aa9528be-a8f3-406a-b977-22d84e7d1e4c.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 선택형 레거시 캐릭터; `player.gd:157` |
| `game/assets/tinker_Color_f598f6ea-73e6-4439-960c-ae4acdf10e76.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 선택형 레거시 캐릭터; `player.gd:157` |
| `game/assets/tinker_NormalGL_f598f6ea-73e6-4439-960c-ae4acdf10e76.png.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 선택형 레거시 캐릭터; `player.gd:157` |
| `game/assets/tinker_ORM_f598f6ea-73e6-4439-960c-ae4acdf10e76.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 선택형 레거시 캐릭터; `player.gd:157` |
| `game/assets/workshop_0.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 레거시 생성 함수; 실제 호출 확인 |
| `game/assets/workshop_1.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 레거시 생성 함수; 실제 호출 확인 |
| `game/assets/workshop_2.jpg.import:42` | 2048²→1024² | `process/size_limit=1024`; `compress/mode=2` 비교 | 레거시 생성 함수; 실제 호출 확인 |

Haeru는 선택형이고 B는 기본 플레이어·주민에 쓰인다. 해상도만으로 Haeru를 항상 가장 큰 live 병목으로 단정하지 않는다. 생성된 `.scn`/`.ctex`의 실제 참조를 확인해 사용되는 외부 이미지를 찾는다.

다음 2560×1420 UI 이미지는 고해상도 화면의 선명도를 확인하면서 저사양용 최대 변 1920을 비교한다. 현재 `compress/mode=1`, `mipmaps/generate=true`를 유지한다. 기본 캔버스 1280×800만으로 모든 디스플레이에서 과대 해상도라고 단정하거나 위 3D 압축 변경을 일괄 적용하지 않는다.

| 파일·줄 | 비교 변경 | 사용 근거 |
| --- | --- | --- |
| `game/assets/title_morning.jpg.import:39` | `process/size_limit=1920` | `main.gd:569` |
| `game/assets/title_golden.jpg.import:39` | `process/size_limit=1920` | `main.gd:567` |
| `game/assets/title_evening.jpg.import:39` | `process/size_limit=1920` | `main.gd:568` |
| `game/assets/ui/loading_cover.jpg.import:39` | `process/size_limit=1920` | `transition.gd:19` |

## 2. 중복 이미지 — 참조를 공유한 뒤 복사본 정리

SHA256으로 아래 외부 파일의 바이트 동일성을 확인했다. 동일 바이트가 해당 GLB embedded image에도 있다. JSON의 `duplicates.redundant_source_bytes`는 embedded payload까지 포함하므로 그대로 삭제 가능한 파일 용량이나 VRAM 절감량으로 읽으면 안 된다.

파일명은 모두 `game/assets/` 기준이다. canonical은 공유 작업의 제안 기준이며 현재 임포터의 실제 참조를 뜻하지 않는다. 수출·임포트 참조를 공용 파일로 통일하고 재임포트 결과가 그 파일을 쓰는지 확인한 뒤 미참조 복사본을 정리한다. 자동 추출로 복사본이 재생성되지 않도록 수출 경로도 정리해야 한다.

| 권장 canonical | 동일한 다른 외부 파일 | 외부 중복분 |
| --- | --- | --- |
| `explorer_b_wardrobe_NormalGL_c7562c44-0e5c-4eca-8a99-cc67f09222d2.png` | `explorer_b_reference_NormalGL_c7562c44-0e5c-4eca-8a99-cc67f09222d2.png`<br>`explorer_b_motion_NormalGL_c7562c44-0e5c-4eca-8a99-cc67f09222d2.png` | 2,002,122 B |
| `explorer_b_wardrobe_Color_c7562c44-0e5c-4eca-8a99-cc67f09222d2.jpg` | `explorer_b_reference_Color_c7562c44-0e5c-4eca-8a99-cc67f09222d2.jpg`<br>`explorer_b_motion_Color_c7562c44-0e5c-4eca-8a99-cc67f09222d2.jpg` | 1,965,674 B |
| `explorer_Image_0.jpg` | `explorer_0.jpg` | 791,469 B |
| `explorer_Image_1.png` | `explorer_1.png` | 1,726,016 B |

외부 복사본의 중복분 합계는 **6,485,281 B(6.185 MiB)**다. 이 복사본이 현재 임포트 방식에 필수라면 그대로 삭제할 수 없다. `style_character.gd:30`의 motion 모델은 애니메이션을 추출하고 임시 노드를 해제하므로 animation-only 수출도 후속 후보지만, `shadow_figure.gd:64` 등 모든 소비자의 본 경로·트랙을 보존해야 한다.

## 3. 로컬 모델별 삼각형·표면·LOD·사용 여부

삼각형은 GLB accessor/index에서 읽은 원본 메시 합계이며 현재 화면 수가 아니다. 표면은 모델 전체 primitive 수, 재질은 실제 사용한 material slot의 고유 개수다. 표면 수는 기본 draw 제출의 단서이며 인스턴스·가림·그림자 패스에 따른 실제 draw call 수와 다르다.

일반 모델 24개는 대응 `.glb.import:27`에서 모두 `meshes/generate_lods=true`다. `자동 요청`은 설정 확인만 뜻하며 생성된 LOD 결과는 미검증이다. 이 옵션을 유지하고 후속 환경에서 거리/zoom별 LOD와 스킨 변형을 확인한다. 테스트 fixture만 import 근거가 없다. 이번 로컬 자료에서 **고삼각형+LOD 없음으로 확정할 live 모델은 없다**.

literal 검색에 동적 경로 검토를 보완했다. `direct_references=[]`만으로 미사용이라고 단정하지 않는다. 모든 로컬 GLB의 alphaMode는 OPAQUE이며 BLEND 재질은 0개다. 런타임 재질 변경은 별도 항목이다. 아래 기하·재질 목표는 미리보기로 검증할 후보이며 일괄 재수출 명령이 아니다.

| 파일 | 삼각형 / 표면 / 사용재질 | LOD | 사용·근거 | 정확한 후속 변경안 |
| --- | --- | --- | --- | --- |
| `game/assets/authored_axe_v1.glb` | 1,620 / 11 / 4 | 자동 요청 | 장착 도구; `player.gd:266` 동적 경로 | 동일 재질 정적 부분 병합:11→최대 4표면. 그립·실루엣 유지. |
| `game/assets/authored_spear_v1.glb` | 1,640 / 12 / 4 | 자동 요청 | 장착 도구; `player.gd:266` 동적 경로 | 동일 재질 정적 부분 병합:12→최대 4표면. 창날·그립 유지. |
| `game/assets/brute.glb` | 11,974 / 1 / 1 | 자동 요청 | brute 대체 모델; `shadow_beast.gd:178` | 1표면 유지·이미지 축소 우선. 군집 노출 시 6–8k LOD0 비교. |
| `game/assets/cozy_home.glb` | 33,164 / 16 / 16 | 자동 요청 | 현재 game 코드/JSON에서 사용 미확인 | live 우선순위 낮음. 재사용 시 10–16k/최대 8재질 비교. 무조건 삭제 금지. |
| `game/assets/cozy_workshop.glb` | 34,420 / 16 / 16 | 자동 요청 | 현재 game 코드/JSON에서 사용 미확인 | live 우선순위 낮음. 재사용 시 10–16k/최대 8재질 비교. 무조건 삭제 금지. |
| `game/assets/departure_arch.glb` | 6,736 / 8 / 8 | 자동 요청 | 게이트 생성 함수; `world_detail.gd:245` | vertex color/atlas로 최대 4표면 비교. 실제 호출·가림 확인. |
| `game/assets/explorer.glb` | 40,000 / 7 / 7 | 자동 요청 | 선택형 레거시; `player.gd:157` 동적 경로 | 20k LOD0 비교(원본 대비 50%). 7색 영역·스킨 가중치·표정 보존. |
| `game/assets/explorer_b_motion.glb` | 16,151 / 1 / 1 | 자동 요청 | 애니메이션 소스; `style_character.gd:30`, `shadow_figure.gd:64` | 공용 이미지 또는 animation-only 수출 검토. 소비자 본/트랙 확인 전 메시 삭제 금지. |
| `game/assets/explorer_b_reference.glb` | 16,151 / 1 / 1 | 자동 요청 | B 미리보기; `style_character.gd:15`, `studio.gd:800` | wardrobe와 공용 이미지 사용. 손·얼굴 품질 비교 후 8–12k LOD0 검토. |
| `game/assets/explorer_b_wardrobe.glb` | 16,151 / 4 / 4 | 자동 요청 | 기본 플레이어·주민; `player.gd:125`, `shadow_figure.gd:63` | 8–12k LOD0 비교. 4표면의 의상 색 변경 경계 보존. 무조건 1재질 병합 금지. |
| `game/assets/fishing_rod.glb` | 1,488 / 6 / 6 | 자동 요청 | 낚싯대; `player.gd:254` | atlas/vertex color로 최대 2표면 비교. line_tip 위치 유지. |
| `game/assets/fishing_shack.glb` | 20,548 / 12 / 12 | 자동 요청 | 현재 game 코드/JSON에서 사용 미확인 | 재사용 시 8–12k/최대 6표면 비교. live 상위 병목으로 확정하지 않음. |
| `game/assets/haeru_v1.glb` | 12,577 / 6 / 6 | 자동 요청 | Haeru 선택; `player.gd:110` | 4K 이미지 축소 우선. 6표면 영역·애니메이션 유지. 병합은 색 변경 조사 뒤. |
| `game/assets/ranger.glb` | 13,455 / 6 / 6 | 자동 요청 | 선택형 레거시; `player.gd:157` 동적 경로 | 이미지 1K 우선. 6표면 의상 영역 유지하며 8k LOD0 비교. |
| `game/assets/sample_stool.glb` | 12 / 1 / 0 | 자동 요청 | 독립 village/테스트; `village.gd:5` | 12삼각형 유지. 최적화 우선순위 없음. |
| `game/assets/seed_shop.glb` | 19,088 / 13 / 13 | 자동 요청 | 현재 모델 사용 미확인; interiors 테마명과 구분 | 재사용 시 8–12k/최대 6표면 비교. 테마 문자열만으로 사용 판정 금지. |
| `game/assets/shore_rowboat.glb` | 2,028 / 4 / 4 | 자동 요청 | 명시적 참조는 collision 테스트뿐 | 유지. live 배치 확인 전 성능 절감 추정 금지. |
| `game/assets/storybook_camp_v1.glb` | 5,840 / 9 / 9 | 자동 요청 | 탐험 캠프; `survival_map.gd:216` | atlas/vertex color로 최대 4표면 비교. 불·상호작용 구분 유지. |
| `game/assets/storybook_cedar_crown_v1.glb` | 2,864 / 1 / 1 | 자동 요청 | 나무 수관; `art.gd:112` | 1표면 유지. 잎 양면 렌더링을 일괄 back-face로 바꾸지 않음. |
| `game/assets/storybook_frost_outcrop_v1.glb` | 1,026 / 4 / 4 | 자동 요청 | 현재 game 코드/JSON에서 사용 미확인 | 현재 낮은 삼각형 유지. 재사용 시 재질 공유만 검토. |
| `game/assets/storybook_home_v1.glb` | 27,372 / 16 / 16 | 자동 요청 | 현재 game 코드/JSON에서 사용 미확인 | 재사용 시 10–16k/최대 8표면 비교. live 병목으로 확정하지 않음. |
| `game/assets/storybook_quarry_outcrop_v1.glb` | 1,316 / 4 / 4 | 자동 요청 | 현재 game 코드/JSON에서 사용 미확인 | 현재 낮은 삼각형 유지. 재사용 시 재질 공유만 검토. |
| `game/assets/tinker.glb` | 12,899 / 6 / 6 | 자동 요청 | 선택형 레거시; `player.gd:157` 동적 경로 | 이미지 1K 우선. 의상 영역 유지하며 8k LOD0 비교. |
| `game/assets/workshop.glb` | 5,630 / 1 / 1 | 자동 요청 | 레거시 생성 함수; `art.gd:195`, `world_detail.gd:231` | 1표면 유지. 이미지 1K 비교 뒤 실제 live 호출 확인. |
| `game/tests/fixtures/tripo/tripo_pot.glb` | 2,884 / 1 / 1 | 미확인·테스트 | tests/fixtures의 테스트 전용 | import/LOD 미확인. live 순위에서 제외하고 fixture 동작 유지. |

닫힌 도구·몸통에는 해당 GLB material의 `doubleSided=false`를 비교할 수 있지만 잎·머리카락·우산·열린 배의 뒷면은 필요할 수 있다. 모델 전체 culling을 일괄 바꾸지 않는다. 표면 병합 효과는 실제 화면의 인스턴스 수에 따라 확인하며 숨은 장착품까지 합산하지 않는다.

## 4. 누락된 맵 자산: 원본 보유 worktree에서 확인할 명세

환경 매니페스트에는 모델 30종, 건물 매니페스트에는 배치 18개/고유 모델 17종이 있다. 아래 GLB는 전부 현재 worktree에 없다. `18_meadow_house`는 `12_blue_house`의 모델·텍스처를 재사용한다. `archipelago.gd:5`의 `game/maps/archipelago/assets/archipelago_terrain_environment_v1.glb`도 없다. 따라서 로컬 24개 일반 GLB 검사만으로 live 맵 비용 검사가 끝났다고 할 수 없다.

아래는 누락 파일 목록과 **조건부 변경 명세**다. 이미지 이름·현재 크기는 JSON의 `runtime_textures`/`map_texture_copies` 기록이며 헤더 확인값이 아니다. 실제 GLB image→외부 이미지→material slot을 먼저 연결하고 각 이름의 `현재 최대 변→제안 cap`을 실제 `.import`의 `process/size_limit` 또는 수출 크기에 적용해 비교한다. 추출 파일 확장자·경로는 미확인이므로 존재하지 않는 `.import` 경로를 지어내지 않았다. 고해상도 원본은 보존한다.

기본 비교 cap은 Color 2048/Normal 1024/ORM 1024다. 작은 화면에서 이미 LOD를 쓰는 지피물·가로등은 저사양 후보로 Color 1024/Normal 512/ORM 512를 제안한다. 간판·문양·노멀 가독성이 떨어지면 개별 텍스처를 상향 유지한다. cap은 픽셀 피복률 측정 전의 시작점이며 필수값이 아니다. 기존 설정을 확인한 뒤 `compress/mode=2`, `mipmaps/generate=true`도 비교한다.

### 환경 30종

| 배치·근거 | 누락 모델 경로 | 텍스처 이름별 cap(px) |
| --- | --- | --- |
| `18_bridge_short`<br>`environment_layout.json:7` | `game/maps/archipelago/assets/environment/bridge_short.glb` | `NormalGL_cbf6b128-4f5d-4205-bc8c-44844a1bc273`: 2048→1024<br>`Color_cbf6b128-4f5d-4205-bc8c-44844a1bc273`: 4096→2048 |
| `19_bridge_long`<br>`environment_layout.json:38` | `game/maps/archipelago/assets/environment/bridge_long.glb` | `NormalGL_2722401e-db70-44ae-9c4f-f47fb633bb74`: 2048→1024<br>`Color_2722401e-db70-44ae-9c4f-f47fb633bb74`: 4096→2048 |
| `22_tent_orange`<br>`environment_layout.json:69` | `game/maps/archipelago/assets/environment/tent_orange.glb` | `NormalGL_79c70f7f-b3c0-4de8-b76a-029dd14b50d9`: 2048→1024<br>`Color_79c70f7f-b3c0-4de8-b76a-029dd14b50d9`: 4096→2048 |
| `23_tent_green`<br>`environment_layout.json:100` | `game/maps/archipelago/assets/environment/tent_green.glb` | `NormalGL_96579d0e-c00b-411b-9352-579aacd95e6c`: 2048→1024<br>`Color_96579d0e-c00b-411b-9352-579aacd95e6c`: 4096→2048 |
| `24_firepit`<br>`environment_layout.json:131` | `game/maps/archipelago/assets/environment/firepit.glb` | `NormalGL_fbe48e1e-ecc1-4337-bed7-1dd66a8651f3`: 2048→1024<br>`Color_fbe48e1e-ecc1-4337-bed7-1dd66a8651f3`: 4096→2048 |
| `26_bench`<br>`environment_layout.json:162` | `game/maps/archipelago/assets/environment/bench.glb` | `NormalGL_66853057-2b50-4f54-9f63-f53915f05259`: 2048→1024<br>`Color_66853057-2b50-4f54-9f63-f53915f05259`: 4096→2048 |
| `27_lamp`<br>`environment_layout.json:193` | `game/maps/archipelago/assets/environment/lamp.glb` | `NormalGL_b98cb36e-7ff7-4891-96d6-1182256f796d`: 2048→512<br>`Color_b98cb36e-7ff7-4891-96d6-1182256f796d`: 4096→1024<br>`ORM_b98cb36e-7ff7-4891-96d6-1182256f796d`: 2048→512 |
| `37_round_tree`<br>`environment_layout.json:235` | `game/maps/archipelago/assets/environment/round_tree.glb` | `NormalGL_5beb571a-b4f5-42e2-8f06-81a838c5647a`: 2048→1024<br>`Color_5beb571a-b4f5-42e2-8f06-81a838c5647a`: 4096→2048 |
| `38_conifer`<br>`environment_layout.json:266` | `game/maps/archipelago/assets/environment/conifer.glb` | `NormalGL_f13e2b58-d9ac-41fd-846d-5f23b02f2614`: 2048→1024<br>`Color_f13e2b58-d9ac-41fd-846d-5f23b02f2614`: 4096→2048 |
| `39_palm`<br>`environment_layout.json:297` | `game/maps/archipelago/assets/environment/palm.glb` | `NormalGL_f25baf94-a9d0-4674-8749-879e9f0f9316`: 2048→1024<br>`Color_f25baf94-a9d0-4674-8749-879e9f0f9316`: 4096→2048 |
| `40_shrub`<br>`environment_layout.json:328` | `game/maps/archipelago/assets/environment/shrub.glb` | `NormalGL_f1acd4cd-208a-45de-9dde-dbe10f8670b9`: 2048→512<br>`Color_f1acd4cd-208a-45de-9dde-dbe10f8670b9`: 4096→1024 |
| `42_white_flowers`<br>`environment_layout.json:359` | `game/maps/archipelago/assets/environment/white_flowers.glb` | `NormalGL_ba4b5a53-7280-470c-974c-06fdc8a9e587`: 2048→512<br>`Color_ba4b5a53-7280-470c-974c-06fdc8a9e587`: 4096→1024 |
| `43_yellow_flowers`<br>`environment_layout.json:390` | `game/maps/archipelago/assets/environment/yellow_flowers.glb` | `NormalGL_86563262-acbd-40cd-878a-6513f07da3a1`: 2048→512<br>`Color_86563262-acbd-40cd-878a-6513f07da3a1`: 4096→1024 |
| `48_bridge_rope`<br>`environment_layout.json:421` | `game/maps/archipelago/assets/environment/bridge_rope.glb` | `NormalGL_a828fb69-1682-41e4-a65b-c700097bbef9`: 2048→1024<br>`Color_a828fb69-1682-41e4-a65b-c700097bbef9`: 4096→2048 |
| `49_bridge_boardwalk`<br>`environment_layout.json:452` | `game/maps/archipelago/assets/environment/bridge_boardwalk.glb` | `NormalGL_656c0567-f652-443b-baad-01b2cf1f56d7`: 2048→1024<br>`Color_656c0567-f652-443b-baad-01b2cf1f56d7`: 4096→2048 |
| `20_pier`<br>`environment_layout.json:483` | `game/maps/archipelago/assets/environment/pier.glb` | `NormalGL_979c40be-9ebb-433c-a161-a9b0da6e7875`: 2048→1024<br>`Color_979c40be-9ebb-433c-a161-a9b0da6e7875`: 4096→2048 |
| `21_boat`<br>`environment_layout.json:514` | `game/maps/archipelago/assets/environment/boat.glb` | `NormalGL_f6900b28-a7d7-4a99-bcb2-15b996c10c83`: 2048→1024<br>`Color_f6900b28-a7d7-4a99-bcb2-15b996c10c83`: 4096→2048 |
| `25_picnic_table`<br>`environment_layout.json:545` | `game/maps/archipelago/assets/environment/picnic_table.glb` | `NormalGL_3ecd9033-4765-4746-8833-313a3ebec999`: 2048→1024<br>`Color_3ecd9033-4765-4746-8833-313a3ebec999`: 4096→2048 |
| `28_beach_umbrella`<br>`environment_layout.json:576` | `game/maps/archipelago/assets/environment/beach_umbrella.glb` | `NormalGL_fbb30f27-e6dc-448e-b34b-8a6e1eab66ad`: 2048→1024<br>`Color_fbb30f27-e6dc-448e-b34b-8a6e1eab66ad`: 4096→2048 |
| `29_beach_lounger`<br>`environment_layout.json:607` | `game/maps/archipelago/assets/environment/beach_lounger.glb` | `NormalGL_705deb97-2a86-42be-8e8b-a87fcb315059`: 2048→1024<br>`Color_705deb97-2a86-42be-8e8b-a87fcb315059`: 4096→2048 |
| `30_cafe_umbrella`<br>`environment_layout.json:638` | `game/maps/archipelago/assets/environment/cafe_umbrella.glb` | `NormalGL_2c3c2d31-e03d-4b03-8e04-75106e4bfa24`: 2048→1024<br>`Color_2c3c2d31-e03d-4b03-8e04-75106e4bfa24`: 4096→2048 |
| `31_cafe_table`<br>`environment_layout.json:669` | `game/maps/archipelago/assets/environment/cafe_table.glb` | `NormalGL_31aae595-6cee-4d30-92a7-da2288a89607`: 2048→1024<br>`Color_31aae595-6cee-4d30-92a7-da2288a89607`: 4096→2048 |
| `32_cafe_chair`<br>`environment_layout.json:700` | `game/maps/archipelago/assets/environment/cafe_chair.glb` | `NormalGL_3f920afa-43d2-404b-80c5-db06d3c24f57`: 2048→1024<br>`Color_3f920afa-43d2-404b-80c5-db06d3c24f57`: 4096→2048 |
| `33_signboard`<br>`environment_layout.json:731` | `game/maps/archipelago/assets/environment/signboard.glb` | `NormalGL_f480e3f8-6464-43a7-a509-bb4f2f472f0f`: 2048→1024<br>`Color_f480e3f8-6464-43a7-a509-bb4f2f472f0f`: 4096→2048 |
| `34_timber_fence`<br>`environment_layout.json:762` | `game/maps/archipelago/assets/environment/timber_fence.glb` | `NormalGL_f6bc7804-5f9a-4155-922c-d99519634c6f`: 2048→1024<br>`Color_f6bc7804-5f9a-4155-922c-d99519634c6f`: 4096→2048 |
| `35_picket_fence`<br>`environment_layout.json:793` | `game/maps/archipelago/assets/environment/picket_fence.glb` | `NormalGL_88f6e103-8430-4daf-95bb-3ee22a3e258d`: 2048→1024<br>`Color_88f6e103-8430-4daf-95bb-3ee22a3e258d`: 4096→2048 |
| `36_speaker`<br>`environment_layout.json:824` | `game/maps/archipelago/assets/environment/speaker.glb` | `NormalGL_e53f8c86-543f-4b26-9e67-0a2799eb63af`: 2048→1024<br>`Color_e53f8c86-543f-4b26-9e67-0a2799eb63af`: 4096→2048 |
| `41_planter`<br>`environment_layout.json:855` | `game/maps/archipelago/assets/environment/planter.glb` | `NormalGL_887b8829-fc9d-4f7d-85bc-06a08b893ccb`: 2048→512<br>`Color_887b8829-fc9d-4f7d-85bc-06a08b893ccb`: 4096→1024 |
| `44_pink_flowers`<br>`environment_layout.json:886` | `game/maps/archipelago/assets/environment/pink_flowers.glb` | `NormalGL_3ea7acb1-e901-4012-bdec-da5f56e8c51e`: 2048→512<br>`Color_3ea7acb1-e901-4012-bdec-da5f56e8c51e`: 4096→1024 |
| `45_reeds`<br>`environment_layout.json:917` | `game/maps/archipelago/assets/environment/reeds.glb` | `NormalGL_7748e7d8-69c3-45fc-98fa-03fcd4a7f9f2`: 2048→512<br>`Color_7748e7d8-69c3-45fc-98fa-03fcd4a7f9f2`: 4096→1024 |

### 건물 18개 배치 / 고유 모델 17종

| 배치·근거 | 누락 모델 경로 | 텍스처 이름별 cap(px) |
| --- | --- | --- |
| `01_cafe`<br>`building_placements.json:8` | `game/maps/archipelago/assets/buildings/cafe.glb` | `NormalGL_c2073972-34c6-4a03-be6b-57464e493e47`: 2048→1024<br>`Color_c2073972-34c6-4a03-be6b-57464e493e47`: 4096→2048<br>`ORM_c2073972-34c6-4a03-be6b-57464e493e47`: 2048→1024 |
| `02_timber_house`<br>`building_placements.json:72` | `game/maps/archipelago/assets/buildings/timber_house.glb` | `NormalGL_45d7d5bc-ca22-43f2-8df5-c00937bedd74`: 2048→1024<br>`Color_45d7d5bc-ca22-43f2-8df5-c00937bedd74`: 4096→2048<br>`ORM_45d7d5bc-ca22-43f2-8df5-c00937bedd74`: 2048→1024 |
| `03_teal_cottage`<br>`building_placements.json:136` | `game/maps/archipelago/assets/buildings/teal_cottage.glb` | `NormalGL_9b09a799-5702-4121-baa0-27bdbd9e9ea8`: 2048→1024<br>`Color_9b09a799-5702-4121-baa0-27bdbd9e9ea8`: 4096→2048<br>`ORM_9b09a799-5702-4121-baa0-27bdbd9e9ea8`: 2048→1024 |
| `04_windmill`<br>`building_placements.json:200` | `game/maps/archipelago/assets/buildings/windmill.glb` | `NormalGL_8866a17a-62f5-4dc9-ad3b-dcc48aa1042d`: 2048→1024<br>`Color_8866a17a-62f5-4dc9-ad3b-dcc48aa1042d`: 4096→2048<br>`ORM_8866a17a-62f5-4dc9-ad3b-dcc48aa1042d`: 2048→1024 |
| `05_observatory`<br>`building_placements.json:264` | `game/maps/archipelago/assets/buildings/observatory.glb` | `NormalGL_fedcbf96-8921-465d-9516-5f85f459b9a2`: 2048→1024<br>`Color_fedcbf96-8921-465d-9516-5f85f459b9a2`: 4096→2048<br>`ORM_fedcbf96-8921-465d-9516-5f85f459b9a2`: 2048→1024 |
| `06_orange_cottage`<br>`building_placements.json:328` | `game/maps/archipelago/assets/buildings/orange_cottage.glb` | `NormalGL_888dd46a-0a44-45bb-a6c9-b1f6293feb6b`: 2048→1024<br>`Color_888dd46a-0a44-45bb-a6c9-b1f6293feb6b`: 4096→2048<br>`ORM_888dd46a-0a44-45bb-a6c9-b1f6293feb6b`: 2048→1024 |
| `07_greenhouse`<br>`building_placements.json:392` | `game/maps/archipelago/assets/buildings/greenhouse.glb` | `NormalGL_9dcb2f56-7622-4d58-a161-fdca7c83fd52`: 2048→1024<br>`Color_9dcb2f56-7622-4d58-a161-fdca7c83fd52`: 4096→2048<br>`ORM_9dcb2f56-7622-4d58-a161-fdca7c83fd52`: 2048→1024 |
| `08_gazebo`<br>`building_placements.json:456` | `game/maps/archipelago/assets/buildings/gazebo.glb` | `NormalGL_1a379a72-0d36-4601-9e31-93aea64f4a35`: 2048→1024<br>`Color_1a379a72-0d36-4601-9e31-93aea64f4a35`: 4096→2048<br>`ORM_1a379a72-0d36-4601-9e31-93aea64f4a35`: 2048→1024 |
| `09_town_hall`<br>`building_placements.json:520` | `game/maps/archipelago/assets/buildings/town_hall.glb` | `NormalGL_c3a929b7-dc12-4a14-a0ef-6c8fefba6846`: 2048→1024<br>`Color_c3a929b7-dc12-4a14-a0ef-6c8fefba6846`: 4096→2048<br>`ORM_c3a929b7-dc12-4a14-a0ef-6c8fefba6846`: 2048→1024 |
| `10_red_house`<br>`building_placements.json:584` | `game/maps/archipelago/assets/buildings/red_house.glb` | `NormalGL_c70dfb1f-4709-4930-80d1-95488d201cca`: 2048→1024<br>`Color_c70dfb1f-4709-4930-80d1-95488d201cca`: 4096→2048<br>`ORM_c70dfb1f-4709-4930-80d1-95488d201cca`: 2048→1024 |
| `11_purple_house`<br>`building_placements.json:648` | `game/maps/archipelago/assets/buildings/purple_house.glb` | `NormalGL_3028e8cd-45d9-4c6b-97ad-397edd96874a`: 2048→1024<br>`Color_3028e8cd-45d9-4c6b-97ad-397edd96874a`: 4096→2048<br>`ORM_3028e8cd-45d9-4c6b-97ad-397edd96874a`: 2048→1024 |
| `12_blue_house`<br>`building_placements.json:712` | `game/maps/archipelago/assets/buildings/blue_house.glb` | `NormalGL_e93e6ef4-fc89-40d5-a60f-10fc42ac6509`: 2048→1024<br>`Color_e93e6ef4-fc89-40d5-a60f-10fc42ac6509`: 4096→2048<br>`ORM_e93e6ef4-fc89-40d5-a60f-10fc42ac6509`: 2048→1024 |
| `13_shop`<br>`building_placements.json:776` | `game/maps/archipelago/assets/buildings/shop.glb` | `NormalGL_e46bbe9a-e348-4d9d-88eb-c4ab6a5b8feb`: 2048→1024<br>`Color_e46bbe9a-e348-4d9d-88eb-c4ab6a5b8feb`: 4096→2048<br>`ORM_e46bbe9a-e348-4d9d-88eb-c4ab6a5b8feb`: 2048→1024 |
| `14_stage`<br>`building_placements.json:840` | `game/maps/archipelago/assets/buildings/stage.glb` | `NormalGL_17f15b93-12cf-41fb-8a5c-5e574c81f3a9`: 2048→1024<br>`Color_17f15b93-12cf-41fb-8a5c-5e574c81f3a9`: 4096→2048 |
| `15_picnic_shelter`<br>`building_placements.json:893` | `game/maps/archipelago/assets/buildings/picnic_shelter.glb` | `NormalGL_129f79fc-1c9f-4849-8002-911d1e548fe6`: 2048→1024<br>`Color_129f79fc-1c9f-4849-8002-911d1e548fe6`: 4096→2048<br>`ORM_129f79fc-1c9f-4849-8002-911d1e548fe6`: 2048→1024 |
| `16_blue_cottage`<br>`building_placements.json:957` | `game/maps/archipelago/assets/buildings/blue_cottage.glb` | `NormalGL_0733e299-e486-45d7-b552-49432976e95e`: 2048→1024<br>`Color_0733e299-e486-45d7-b552-49432976e95e`: 4096→2048<br>`ORM_0733e299-e486-45d7-b552-49432976e95e`: 2048→1024 |
| `17_lighthouse`<br>`building_placements.json:1021` | `game/maps/archipelago/assets/buildings/lighthouse.glb` | `NormalGL_fd1798fb-c00f-48a1-a11b-3892abf82878`: 2048→1024<br>`Color_fd1798fb-c00f-48a1-a11b-3892abf82878`: 4096→2048<br>`ORM_fd1798fb-c00f-48a1-a11b-3892abf82878`: 2048→1024 |
| `18_meadow_house`<br>`building_placements.json:1085` | `game/maps/archipelago/assets/buildings/blue_house.glb`; 12_blue_house와 공유 | `NormalGL_e93e6ef4-fc89-40d5-a60f-10fc42ac6509`: 2048→1024<br>`Color_e93e6ef4-fc89-40d5-a60f-10fc42ac6509`: 4096→2048<br>`ORM_e93e6ef4-fc89-40d5-a60f-10fc42ac6509`: 2048→1024 |

매니페스트에는 환경 배치 593개와 다리 4개가 있다. 꽃 309개(흰 126/노랑 154/분홍 29), shrub98개, 나무 55개(둥근 38/침엽 13/야자 4), planter28개, reeds22개, lamp28개는 원본 메시 수가 아니라 배치 수다. 같은 이미지의 배치 횟수를 VRAM에 곱하지 않는다. 블록 압축·공유·lazy load·대체 다리·bake 참조가 미확인이므로 JSON 크기를 더한 수치를 실제 GPU 총량으로 쓰지 않는다.

다리는 `bridges[].fitted_model` 및 `authored_at_bank_span`에 따라 원래 모델을 건너뛴다(`environment_layout.gd:37–45`). bridge_short/long/rope/boardwalk 이미지가 현재 모두 올라간다고 단정하지 않는다. 맵 담당자는 이 교체 경로, `assets/prop_lods/<id>.glb`의 존재·실제 전환, 생성된 ground/island 리소스도 함께 검사한다.

## 5. 파티클·그림자·투명·조명 인수인계

다음 조치도 미적용이다. 작은 장식의 그림자 제거, 파티클 수 조절, 셰이더 렌더 경로 변경은 화면 비교가 필요하므로 동일 동작 스크립트 수정과 구분한다.

| 위치 | 확인 상태 | 정확한 후속 조치 |
| --- | --- | --- |
| `game/scripts/main.gd:934–970` | sparks22+ambience45. 같은 SphereMesh(:945)의 분할 수 미지정 | `spark_mesh.radial_segments=6`, `spark_mesh.rings=3`; `sparks.cast_shadow`와 `ambience.cast_shadow`를 OFF로 명시해 비교. 기본 분할값·실제 삼각형 수는 미측정. |
| `game/scripts/field_objects.gd:593–617` | spray40; 이미 radial6/rings3; alpha0.8 | `spray.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF` 비교. 이미 저분할이므로 메시 축소를 중복 권고하지 않음. |
| `game/scripts/life_art.gd:245–263` | sparkles5; quad/additive | `p.cast_shadow=...OFF` 비교. 품질 연동 시 `maxi(1,roundi(5*GameSettings.particle_scale()))`; 설정 변경 때 기존 emitter도 갱신. |
| `game/scripts/life_art.gd:429–461` | burst 기본 14; sphere/facet/petal | `p.cast_shadow=...OFF` 비교. amount의 particle_scale 적용은 시각 변경으로 분리하고 일회성 종료 연결 유지. |
| `game/maps/survival/survival_map.gd:1452–1494` | motes frost150/기타 50, forest fireflies40; 저분할·shadow OFF | 기존 분할/그림자 유지. particle_scale 및 설정 변경 시 재설정 검토. 실제 emitting 상태를 반영해 동시 수량 측정. |
| `game/maps/survival/survival_map.gd:713–730` | ember별 int(10*radius); 이미 저분할·shadow OFF | 위험구역 수·반경별 동시 particles를 집계한 뒤 품질/거리 제한 비교. 게임 단서가 되는 효과는 유지. |
| `game/maps/archipelago/campfire.gdshader:15` | ALPHA=1.0 상수. environment_layout.gd:404에서 5겹; 504tri/겹 | `ALPHA=1.0;` 제거 후 불투명 경로·겹침 비교. 이 조치만으로 삼각형은 감소하지 않음. 5→3겹(2520→1512tri,40% 감소)은 모양 변경 후보로 별도 검토. |
| `game/shaders/camp_flame.gdshader:19` | edge/base/tip에 따라 실제 alpha 변화 | 투명 유지. 상수 alpha 셰이더와 함께 ALPHA 제거 금지. 필요하면 화면 겹침 수를 측정. |
| `game/scripts/occluder_fade.gd:118–127` | 플레이어 가림 해소를 위한 나무 alpha | 의도된 투명 유지. 빌딩 dither는 이미 별도. 일괄 opaque화하지 않고 실제 피복률·전환 비용 측정. |
| `game/maps/archipelago/environment_layout.gd:331–339,397–403` | 매니페스트 lamp28+firepit1=OmniLight29; 모두 shadow=false | 낮 숨김은 daylight.gd:179에 이미 있음. 야간 범위·광원 겹침을 측정한 뒤 카메라 밖 거리별 비활성화 비교. shadow OFF 재권고 금지. |
| `game/scripts/game_settings.gd:411–414`, `main.gd:1014–1018` | 방향광 shadow OFF/2split/4split 설정 | 기존 옵션 유지. project.godot 변경 없이 소품 그림자 제거의 이득을 실제 split·노출 수별로 비교. |

## 6. 기존 최적화와 오탐 방지

- `environment_layout.gd:24–25,94–95`는 ground cover·NO_SHADOW·lod_bias를 이미 적용한다. `:229`의 지피물 260/300px, 나무 150/180px, 기타 72/92px 전환 히스테리시스도 유지한다. 실제 파일 확인 전 LOD 누락으로 보고하지 않는다.
- `survival_map.gd` 외곽 지피물은 chunk MultiMesh와 수동 LOD를 쓴다. 멀리 있는 모든 배치를 full geometry라고 계산하지 않는다.
- `fx.gd:132,144,164,179`, `survival_guide.gd:199`는 이미 particle_scale을 쓰며 `fx.gd:205`는 shadow OFF다. 별도 legacy emitter 경로만 연결 후보다.
- `life_art.gd:95`는 크기 벡터 길이 0.25 미만 소품의 그림자를 끈다. building_dressing/interiors도 작은 장식 shadow OFF가 많아 전부 ON으로 합산하면 안 된다.
- `daylight.gd:170–179`는 낮/밤 gain으로 lamp visibility를 조절한다. 조명 29개가 항상 켜진다는 뜻이 아니다. interiors의 OmniLight 생성 위치 9곳도 동시 인스턴스 수가 아니다.
- `.tscn`3개는 스크립트 bootstrap이다. serialized lights/particles=0은 런타임 0개가 아니다. JSON의 reachable_script_constructor_sites도 생성 위치 목록이며 실시간 개수와 다르다.
- `game/assets/ui/standee/`의 720×960 이미지는 `rpg_ui.gd:2477–2487`의 TextureRect다. mipmaps=false를 3D 원거리 문제로 분류하지 않고 UI 얼굴·문자 가독성을 유지한다.
- GLB embedded image, 추출 PNG/JPG, `.ctex`는 저장 형태가 다르다. 원본 바이트 중복·런타임 VRAM 공유·패키지 중복을 구분하고 이중합산하지 않는다.

## 7. 후속 검증 완료 조건

원본이 있는 작업 공간에서 같은 해상도·카메라·시간대·캐릭터 구성으로 전후를 비교한다. B/Haeru 얼굴·의상·손, 낚싯줄 끝, 도구 실루엣, 건물 간판, 노멀 조명 반응, 불꽃 겹침을 포함한다. 실제 texture memory·draw calls·rendered primitives·frame time을 기록한 뒤 FPS 개선량을 보고한다. LOD는 import 옵션만이 아니라 zoom별 전환과 스킨 변형을 확인한다. 누락 맵 원본이 확보되기 전에는 이 문서의 cap·매니페스트 수치만으로 GPU 전체 비용 결론을 내리지 않는다.
