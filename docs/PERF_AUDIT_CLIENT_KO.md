# 클라이언트 성능 감사 및 적용 순서

2026-10-16 · 기준 커밋 `d28fde54` · 릴리스 0.11.8 · Godot 4.7 클라이언트

일반 PC에서의 프레임 안정성을 목표로 `game/`을 정적으로 조사했다. 안전한 스크립트 수정은 4개 파일에 적용했다. 가장 큰 후속 후보는 고해상도 텍스처, 많은 표면을 가진 모델, 지속 파티클의 메시 설정이다. 실제 군도 지형과 주요 맵 모델은 이 작업트리에 없으므로 전체 맵의 GPU 비용이나 FPS 개선량을 확정할 수 없다.

작업 시작 시 기존 코드 변경은 없었고 `CODEX_TASK.md`만 추적되지 않은 상태였다. `game/project.godot`, 맵·지형·건물 파일, 씬, 자산 및 `.import` 설정을 변경하지 않았다. Godot 실행, 외부 호출, 커밋, 배포도 하지 않았다.

## 조사 범위와 해석

`tools/perf_audit/audit.py`는 표준 라이브러리만 사용한다. PNG/JPEG/WebP/SVG 치수, `.import`의 크기 제한·밉맵·압축 모드, GLB JSON의 삼각형과 표면·재질, GDScript의 프레임 콜백 및 같은 파일의 호출 함수, 씬 구성, 셰이더 ALPHA, 큰 파일의 SHA256 중복을 조사한다. 이미지 픽셀을 디코딩하거나 Godot 임포트를 실행하지 않는다.

| 항목 | 이번 작업트리의 확인 결과 |
|---|---|
| 입력 | `game/` 8,350개 파일, GDScript 342개, `.tscn` 3개 |
| 모델 | GLB 25개: 일반 자산 24개, 테스트 fixture 1개. 내부 메시 143개 |
| 텍스처 | 외부 이미지 302개와 GLB 내장 이미지 25개, 총 327개 기록. 내장·추출 이미지를 중복 합산하면 안 됨 |
| LOD | 일반 GLB 24개 모두 `meshes/generate_lods=true`. 실제 생성 결과와 원거리 품질은 미확인 |
| 투명 재질 | GLB의 `alphaMode=BLEND`는 0건. 스크립트 생성 재질과 ALPHA 셰이더에는 별도 후보가 있음 |
| 큰 중복 | 256 KiB 이상 파일·내장 이미지에서 21개 SHA256 그룹. 배포 용량 후보이며 VRAM 중복의 증거는 아님 |
| 읽지 못하는 형식 | 건물 문 관련 바이너리 `.res` 28개는 목록만 제공. 삼각형·재질·LOD를 추측하지 않음 |
| 누락 자산 | 환경 모델 30종, 건물 18개 배치가 사용하는 모델 17종, 주요 지형 GLB 등이 로컬에 없음 |

텍스처 메모리는 **RGBA8, 전체 mip chain** 기준의 비교용 상한이다. 4096² 한 장은 약 85.33 MiB, 2048²는 21.33 MiB, 1024²는 5.33 MiB이다. JPEG 파일 크기는 VRAM 크기가 아니다. 실제 RGB/RGBA 형식, GPU 압축, 공유, 로드 시점에 따라 값이 달라진다. 도구는 4/8 bpp 블록 압축 후보 크기도 함께 기록하지만 특정 GPU 포맷을 보장하지 않는다.

크기만으로 과대 텍스처를 확정할 수 없다. 표면의 화면 점유율, 얼굴·의상 확대, 한글 가독성을 확인한 뒤 크기 제한을 선택한다. 밉맵이 없는 UI 이미지를 3D 품질 문제로 단정하지 않는다.

## 상위 20개 검토·수정 항목

다음 순위는 잠재 비용, 실제 사용 경로, 반복 빈도와 확신도를 함께 고려한 **수동 검토 순위**다. 관련 파일을 묶었으므로 도구의 원시 후보 20행과 다르다. 기대 효과는 구조적 감소량이며 FPS 실측값이 아니다. 파일별 전체 경로와 변경값은 [자산 인수인계 부록](PERF_AUDIT_CLIENT_ASSETS_KO.md)에 있다.

| 순위 | 근거와 현재 상태 | 권장 조치 / 기대 효과 |
|---|---|---|
| 1 | 군도 주요 자산 누락. `game/maps/archipelago/archipelago.gd:5`, `environment_layout.json`, `building_placements.json`. 환경 593개 인스턴스, 건물 18개 배치 | 맵 원본 작업트리에서 먼저 재감사. 매니페스트의 4K 텍스처를 실제 헤더·임포트와 대조하고 색상 2K/normal·ORM 1K 후보를 검증. 전체 GPU 비용에서 가장 큰 미확인 영역이며 절감 총량 산정 불가 |
| 2 | `haeru_v1` Color·Normal 4096² 두 장, mode=0, mipmaps=true. `game/scripts/player.gd:110`에서 선택 시 사용 | 두 이미지 `.import`의 `process/size_limit=2048`; 3D GPU 압축 검토. 해상도만 낮추면 RGBA8+mip 상한 **170.67→42.67 MiB**, 최대 128 MiB 감소 |
| 3 | 기본 Explorer B wardrobe/reference/motion의 Color·Normal 6개 외부 파일: 모두 2048², mode=0. 이미지 내용은 Color 1종·Normal 1종으로 중복 | 동일 이미지 공유부터 확인. 1K 제한 및 `compress/mode=2` 검토. 고유 두 장의 해상도만 바꾸면 RGBA8 상한 **42.67→10.67 MiB**. 여섯 장을 모두 동시 VRAM으로 계산하지 않음 |
| 4 | brute/ranger/tinker의 Color·Normal·ORM 9장, 각각 2048², mode=0 | 3D 텍스처에 GPU 압축과 1K 후보 적용 후 근접 비교. 1K 전환 시 해당 텍스처당 RGBA8 상한 16 MiB 감소. 선택 아바타가 동시에 몇 명 보이는지에 따라 이득이 달라짐 |
| 5 | `game/scripts/main.gd:934`, `:945`, `:953`: sparks 22개·ambience 45개가 분할 수 미지정 SphereMesh 공유 | `spark_mesh.radial_segments=6`, `rings=3` 후보와 emitter 그림자 OFF를 시각 검증. 지속 파티클당 지오메트리·그림자 패스 감소. 기본 구의 엔진 삼각형 수를 실행 없이 단정하지 않음 |
| 6 | 선택형 `game/assets/explorer.glb`: 40,000 triangles / 7 surfaces. `player.gd:157`의 동적 선택 경로. 자동 LOD는 켜져 있음 | 근거리 원본 20k 목표를 검토하고 생성된 원거리 LOD를 확인. 목표 달성 시 근거리 삼각형 약 50% 감소 가능. 리깅·색 변경 영역 유지 |
| 7 | `authored_axe_v1.glb`: 1,620 triangles / 11 surfaces, spear: 1,640 / 12. 각각 고유 재질 4개 | 정적 도구 부분을 같은 재질끼리 병합. 기본 표면 제출 수 axe 11→최대4, spear 12→최대4 후보. 손잡이 위치·장착 기준·양면 표현 보존 |
| 8 | 기본 `explorer_b_wardrobe.glb`: 16,151 triangles / 4 surfaces | 실제 다중 플레이어 화면에서 확인 후 LOD0 8–12k 검토. 목표 시 삼각형 약 26–50% 감소. 이미 활성화된 자동 LOD를 다시 켜라는 변경은 불필요 |
| 9 | `environment_layout.gd:331`, `:397`: 매니페스트상 lamp28+firepit1로 OmniLight 29개 생성 후보 | 밤에 먼 조명을 거리별로 끄는 후보를 검증. 그림자는 이미 OFF이고 낮 조명 숨김도 존재. 실제 동시 가시 광원 수만큼 셰이딩 비용 감소 가능, 수치 미측정 |
| 10 | `game/maps/archipelago/campfire.gdshader:15`: `ALPHA=1.0`, 불꽃 5겹·총 2,520 triangles | 상수 ALPHA 쓰기를 제거한 불투명 경로를 비교. 불필요 투명 패스·겹침 비용 감소 후보. 가변 alpha를 사용하는 `camp_flame.gdshader`는 유지 |
| 11 | `game/scripts/field_objects.gd:593`: 분수 spray 40개, 6/3 구 메시, alpha 재질. 명시적인 emitter shadow OFF 없음 | `spray.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF` 후보. 불필요 그림자 렌더 비용 감소. 메시 분할은 이미 낮으므로 추가로 낮추라고 권하지 않음 |
| 12 | `life_art.gd:246`, `:430`, `main.gd:935`, `:954`, `survival_map.gd:1454`, `:1478`의 입자 수량은 품질 배율 직접 적용 없음 | 기존 `GameSettings.particle_scale()` 경로와 일관되게 수량을 정하고 설정 변경 시 갱신. 예: 0.5 배율이면 수량 약 절반. 시각 효과가 바뀌므로 담당자 적용 항목 |
| 13 | Explorer B 외부 Color/Normal 복사본과 explorer의 `_0`/`_Image_0`, `_1`/`_Image_1` 복사본이 바이트 동일 | 공용 이미지 참조로 재임포트한 후 미사용 복사본 제거. 확인된 외부 파일 중복분 **6,485,281 B = 6.185 MiB** 감소 후보. 즉시 FPS 개선 근거는 없음 |
| 14 | `title_evening.jpg`, `title_golden.jpg`, `title_morning.jpg`, `ui/loading_cover.jpg`: 2560×1420, mode=1, mipmaps=true | 최대 변 1920/1920×1065 후보를 1080p·고해상도 화면에서 비교. RGBA8 상한 한 장 약 **18.49→10.40 MiB**, 약 44% 감소. UI 선명도 확인 |
| 15 | **수정 완료** `game/scripts/locomotion_pose.gd:3`, `:22`, `:29`, `:111`: 뼈 판별·손가락 목록·보행 clip 목록의 반복 Array 구성 | 상수와 직접 비교로 변경. 두 번의 뼈 순회에서 매 뼈·다리별 임시 배열을 제거하고 `speed>0.12`에서 clip을 판별할 때 임시 배열 1개도 제거. 기존 포즈·관절 결과 유지 |
| 16 | **수정 완료** `game/scripts/world_audio.gd:356`: `walkers.get(key, {})`가 기존 walker에도 빈 기본 Dictionary를 구성 | 새 key일 때만 Dictionary 생성. 기존 walker의 `stride` 호출당 임시 Dictionary 1개와 불필요한 재대입 제거. 상태 참조·발소리 시점 유지 |
| 17 | **수정 완료** `game/scripts/social.gd:117`, `:276`: 원격 인물별 발소리 식별 문자열을 프레임마다 구성 | actor 생성 시 `audio_key` 저장. 유효한 원격 actor의 음향 갱신마다 문자열 형식화 1회 제거. actor를 교체할 때 캐시도 새로 생성 |
| 18 | **수정 완료** `game/scripts/chat_box.gd:151`, `:154`: 숨겨진 채팅창도 `_process` 진입 후 즉시 반환 | `visibility_changed`에서 `set_process(is_visible_in_tree())`. 숨김 동안 빈 프레임 호출 0회, 다시 표시하면 재개. idle/fade 시간 정지 동작 유지 |
| 19 | `game/scripts/main.gd:3073`: 마을 목표 UI가 매 프레임 물건 전체 순회 후 문자열을 다시 작성 | 물건·퀘스트·스토리·언어·미리보기 변화로 무효화하는 캐시를 후속 설계. 변화가 없을 때 O(물건 수) 순회와 형식화 제거 가능. 이벤트 누락 위험 때문에 이번에는 유지 |
| 20 | `game/scripts/npc.gd:111`, `shadow_figure.gd:1005`, `anim_lod.gd:15`: 인물마다 카메라 frustum Array 조회 | 카메라·transform·projection·프레임을 고려한 공유 캐시 검토. 같은 카메라 상태의 N명에서 N회→1회 후보. 카메라 갱신 순서를 검증하기 전 적용하지 않음 |

## 적용한 스크립트 변경과 동작 보존 근거

| 파일:줄 | 변경 | 검토한 수명·동작 |
|---|---|---|
| `game/scripts/locomotion_pose.gd:3` | `FINGER_PARTS` 상수 추가 | 문자열 목록이 바뀌지 않음. 런타임에서 이 배열을 수정하지 않음 |
| `game/scripts/locomotion_pose.gd:22` | `[leg.hip, leg.knee, leg.foot]`의 membership을 OR 비교로 교체하고 일치 시 break | 비교에 부작용이 없고 기존 `is_leg` 결과와 같음 |
| `game/scripts/locomotion_pose.gd:29` | 손가락 문자열 상수 목록 순회, 일치 시 break | 기존 substring 판별 결과 유지 |
| `game/scripts/locomotion_pose.gd:111` | `current_clip in ["walk","run"]`을 두 직접 비교로 교체 | speed 조건과 허용 clip 집합 유지 |
| `game/scripts/world_audio.gd:356` | walker key 부재일 때만 `{}` 생성하고 기존 Dictionary 참조 재사용 | position/seen/stride 상태 갱신과 5초 정리 로직 유지 |
| `game/scripts/social.gd:117`, `:276` | actor 생성 시 발소리 문자열 캐시, 반복 경로에서 재사용 | `peers` entry 생성은 이 경로 한 곳. 외형 변경은 actor 내부 visual을 교체하므로 key가 계속 유효 |
| `game/scripts/chat_box.gd:151`, `:154` | 실제 tree visibility에 맞춰 process 활성화 | 기존 `_process`도 숨겨졌으면 시간 누적 전에 return. 표시 복구 신호 연결 확인 |

숨김 상태에서도 진행해야 하는 네트워크·게임 시간 타이머는 중단하지 않았다. `world_audio.gd`와 `perf_overlay.gd`에는 이미 유휴/숨김 process 중단이 있다. 안정적으로 고정된 노드 조회를 찾았다는 이유만으로 동적 노드를 무조건 캐시하지 않았다. `main.gd`의 PlacementDisc는 미리보기 모델 교체 시 무효화 검증이 필요하다.

## 자동 후보에서 제외하거나 우선순위를 낮춘 항목

- `cozy_workshop.glb` 34,420 / 16 surfaces, `cozy_home.glb` 33,164 / 16, `storybook_home_v1.glb` 27,372 / 16은 크지만 직접 사용 참조가 확인되지 않는다. 배포·사용 경로를 확인하기 전 live 병목으로 단정하지 않는다. 동적 경로 때문에 완전한 미사용 판정도 하지 않는다.
- GLB fixture의 import 부재는 게임 전체의 LOD 누락이 아니다. 생성 옵션이 켜져 있어도 `.godot` 캐시가 없으므로 유효한 LOD 생성 여부는 이번 작업에서 검증하지 못했다.
- `environment_layout.gd:94`, `:95`, `:229`에는 이미 지피물 LOD bias·전환 기준과 소품 그림자 OFF가 있다. 전체 소품에 같은 조치를 반복하지 않는다.
- `studio.gd:1054`의 `find_children`는 프레임 콜백에서 도달할 수 있지만 daylight 호출은 `:2317` 부근에서 20/25초 단위로 제한된다. 도달 가능하다는 사실은 매 프레임 실행된다는 뜻이 아니다.
- `quests.gd:978`의 loop 안 await에는 `reporting`과 재시도 시간 방어가 있다. 매 프레임 중복 요청으로 판정하지 않았다. `main.gd:4192`와 `studio.gd:2260`의 근접 이벤트 await도 기존 시간 간격·진행 상태를 확인한 뒤 수정해야 한다.
- `occluder_fade.gd:74`의 ray query는 `CHECK_EVERY`로 제한된다. 가리는 물체를 투명화하는 alpha는 기능이며 제거 대상이 아니다.
- 720×960 standee PNG는 UI TextureRect 용도다. mipmaps=false를 오류로 취급하지 않는다. `preload()` 역시 매 프레임의 동기 파일 로드로 분류하지 않는다.

## 도구의 순위·데이터 형식

JSON의 `findings`는 점수 내림차순, 경로·줄·분류 순으로 정렬한다. 동점 정렬과 파일 순회가 고정되어 재실행 결과를 비교할 수 있다. `category`, `path`, `line`, `score`, `evidence`, `recommendation`, `rank`가 공통 필드다. 바이너리 GLB의 `line=1`은 파일 위치 표기이며 실제 텍스트 줄이 아니다. `mesh` 인덱스 또는 `#image[index]`로 대상을 구분한다.

점수는 서로 다른 비용을 검토하기 위한 휴리스틱이며 시간 단위가 아니다. 대표 규칙은 다음과 같다.

| 종류 | 점수·검출 기준 |
|---|---|
| 텍스처 | 최대 축 >2048, RGBA8 추정 ≥4 MiB인데 GPU 비압축, 또는 큰 이미지의 mip 비활성. 기본 `min(95, 25 + MiB)`, 내장 이미지 후보는 0.5배 |
| 메시·모델 | 메시 ≥20k triangles, 표면 ≥4, 모델 전체 ≥20k 또는 ≥6 surfaces. 삼각형·표면 수로 가중; 명시적 LOD 비활성 메시에는 추가 20점 |
| 프레임 스크립트 | tree 탐색 65, await 60, heavy call 55, node lookup 40, 배열·사전 35, 문자열 25. 로컬 loop +15, 같은 파일 helper 호출 깊이마다 -10(최대 -30), 최소 1점. `game/tests/` 스크립트는 0.25배 |
| 중복 | ≥256 KiB 바이트 동일 데이터만. `min(80, 15 + 중복 source MiB × 3)`. source 용량이며 동시 메모리 사용량 아님 |
| 조명·입자·그림자 | 명시적 씬 노드와 스크립트 생성 위치를 별도로 기록. 크기를 모르는 소품 그림자 후보는 낮은 확신도·12점 |

전체 인벤토리는 `textures`, `meshes`, `models`, `materials`, `scenes`, `scripts`, `duplicates`, `coverage`, `warnings`, `limitations`에 있다. 압축 모드 0/1을 GPU 압축으로 취급하지 않는다. mip limit은 원문을 기록하되 메모리 비교는 전체 mip chain으로 한다.

이 도구는 완전한 GDScript 파서나 프로파일러가 아니다. 다른 파일의 호출, 동적 호출, 클래스 이름 기반 참조, 동일 이름의 내부 클래스 메서드, 호출자 loop의 배수, 조건·타이머의 실행 빈도를 정확히 계산하지 않는다. 익명 함수 본문은 이벤트 콜백 오탐을 줄이기 위해 제외하므로 동기 map/filter lambda 내부 작업도 누락될 수 있다. 문자열로 조립하는 경로와 다운로드 자산은 별도로 확인한다. 그림자 대입 탐색도 모든 분기의 최종 상태를 증명하지 않는다.

세 `.tscn`은 스크립트가 실제 장면을 만드는 진입 파일이다. 모두 직렬화된 light/particle 노드는 0개다. JSON에는 연결된 파일에서 찾은 생성 위치를 함께 제공하지만, 생성 위치 수는 활성 인스턴스 수가 아니다. 환경 매니페스트의 lamp28+firepit1처럼 호출 횟수까지 확인한 수만 인스턴스 후보로 해석한다.

## 재현 및 검증

작업트리 루트에서 실행한다. 의존성 설치나 네트워크 접근은 필요하지 않다.

```powershell
& 'C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe' tools/perf_audit/audit.py --root game --json artifacts/perf_audit_client.json --top 20
& 'C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe' -m pytest tools/perf_audit/test_audit.py --basetemp=.codex-tmppytest -p no:cacheprovider -q
git diff --check
```

감사 도구는 게임 입력을 수정하지 않는다. `--json` 지정 위치에만 결과를 쓴다. `artifacts/perf_audit_client.json`은 재생성 가능한 로컬 결과이며 기존 `.gitignore` 적용 대상이다. 원시 결과 전체가 필요하면 위 명령으로 생성한다.

검증 결과: **pytest 35개 통과**, 실제 `game/` 전체 감사 실행 완료, 최종 후보 1,464건, 파싱 경고 0건. 테스트는 이미지 헤더·NPOT mip 계산, import 크기 제한, GLB indexed/nonindexed/strip 삼각형과 LOD, 텍스트 ArrayMesh 표면·LOD, 재질, SHA256 중복, 프레임 helper와 loop, 주석·문자열·이벤트 callback 오탐, 중첩 씬 인스턴스, 손상 자산 경고, 결정적 정렬, CLI 저장을 검증한다. GDScript 수정은 수명주기·호출부와 diff를 정적으로 검토했다. Godot 문법 검사, 화면 비교, GPU 메모리·FPS 측정은 실행하지 않았다.

후속 담당자는 [자산 부록](PERF_AUDIT_CLIENT_ASSETS_KO.md)의 조건부 변경을 실제 자산이 있는 작업트리에 적용하고, 기존 `game/scripts/perf_overlay.gd`의 F2 표시로 동일 장면·카메라·해상도·품질·인원 조건의 평균/최악 1% 프레임 시간, draw calls, triangles, VRAM을 비교하면 된다. 기본 캐릭터와 Haeru, 마을 낮/밤, 생존 맵, 장비 표시, 채팅 숨김/복원을 포함한다. 측정 결과를 이 문서에 추가하기 전에는 FPS 향상률을 수치로 주장하지 않는다.
