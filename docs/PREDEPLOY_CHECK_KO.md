# 0.11.9 클라이언트 빌드 전 정적 검사

0.11.9 후보 워크트리에서 기존 검사기를 다시 실행한 결과는 **차단 280건, 경고 233건**이다. 기존 `ff066b7`의 **279건/232건**은 별도 과거 기준이다. 현재 280건을 전수 검토한 결과 실제 잘못된 리소스 경로는 **1건**이다. 나머지는 별도로 준비하는 빌드 자산, 테스트·도구 경로, 사운드 계열 접두사였다.

개선 후 기본 검사 결과는 **차단 1건, 경고 83건, 빌드 자산 참조 241건**이다. 자산 상태는 `missing` 206건, `available` 3건, `generated` 8건, `pattern` 24건이다. 수치는 발견 위치별 개수이며 동일 경로가 여러 곳에 있으면 각각 집계한다. 빌드 자산 참조 수도 고유 파일 수가 아니다.

현재 자산이 준비되지 않은 워크트리를 `--assets-root .`로 명시하면 **차단 207건**이다. 이는 필수 복사 자산 누락 206건과 SVG 경로 결함 1건이며 정상적인 엄격 검사 결과다. 소스 검사에서 자산을 별도 분류한 것이 실제 빌드에서 누락을 허용한다는 뜻은 아니다.

- [현재 트리의 개선 전 전체 결과](PREDEPLOY_CHECK_0119_before.json)
- [현재 트리의 개선 후 전체 결과](PREDEPLOY_CHECK_0119_after.json)
- [기존 차단 280건의 개별 분류와 근거](PREDEPLOY_CHECK_0119_classification.json)
- [과거 ff066b7 결과](PREDEPLOY_CHECK_ff066b7.json)

변경 범위는 `tools/predeploy/`, 관련 테스트와 문서다. 아래 게임 수정안은 보고만 하며 적용하지 않았다. 게임 동작·설정 변경, Godot 실행, 외부 호출, 배포, 커밋은 하지 않았다. `CODEX_TASK.md`도 커밋하지 않는다.

검증 결과는 **pytest 97개 통과, 하위 검사 13개 통과**다. 외부 자산의 부분 누락·대소문자·매니페스트 불일치, 실제 Windows 정션과 순환 링크, UID 파일 여부, 생성물과 소스 파일 구분, 요약 30줄 제한 및 종료 코드를 회귀 검사했다. 외부 빌드용 자산 원본을 실제로 공급받아 검사한 결과는 아니며, 자산 보충 동작은 격리된 fixture로 확인했다.

## 0.11.9 빌드 담당자의 실행 순서

PowerShell에서 검사할 후보 체크아웃을 현재 디렉터리로 지정한다. 아래 경로는 이 작업 환경 기준이다. 검사기는 Python 표준 라이브러리만 사용하며 자산을 복사하거나 Godot을 실행하지 않는다.

```powershell
Set-Location -LiteralPath 'D:\lsm26\wt\codex27'
$taskPython = 'C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe'

# 1. 소스만 검토한다. 현재 SVG 경로 결함 때문에 종료 코드 1이 예상된다.
& $taskPython tools/predeploy/check_client.py --summary

# 상세 진단과 별도 build_time_assets 목록을 JSON으로 확인한다.
& $taskPython tools/predeploy/check_client.py --json
```

`--summary`는 최대 30줄이며 차단 위치와 원인을 우선 표시한다. 생략된 항목은 `--json` 또는 기본 전체 출력으로 확인한다. 두 출력 옵션은 함께 사용하지 않는다. 차단이 있으면 종료 코드 **1**, 차단이 없으면 **0**, 사용법 오류는 **2**다.

소스 검사에서 빌드 자산 누락은 별도 목록에 보류한다. 이 결과만으로 빌드 준비가 끝났다고 판단하지 말고 실제 자산 폴더를 명시해 확인한다.

```powershell
# 2. 실제 자산을 보유한 경로를 직접 지정한다. 아래는 예시이며 자동 선택되지 않는다.
$taskAssetsRoot = 'D:\lsm26\wt\build'
& $taskPython tools/predeploy/check_client.py --assets-root $taskAssetsRoot --summary
& $taskPython tools/predeploy/check_client.py --assets-root $taskAssetsRoot --json

# 같은 자산을 game/ 루트로 지정해도 된다.
& $taskPython tools/predeploy/check_client.py --assets-root (Join-Path $taskAssetsRoot 'game') --summary
```

`--assets-root`는 체크아웃 루트 또는 DevAssets를 푼 루트(`game/` 포함), 혹은 그 안의 `game/`을 받는다. `assets/` 폴더 하나만 지정하는 형식은 지원하지 않는다. 경로가 없거나 구조가 맞지 않으면 차단한다. 외부 폴더는 알려진 자산 파일의 존재를 확인하는 읽기 전용 보충 경로다. 스크립트·설정·매니페스트는 계속 후보 체크아웃의 것을 검사한다. 외부 체크아웃의 소스로 결함을 덮어 통과시키지 않는다.

빌드할 후보의 `game/`에는 다음 6개 폴더의 자산을 팀의 DevAssets 묶음 또는 관리 중인 자산 폴더에서 준비해야 한다. DevAssets 압축은 저장소 상대 경로를 보존한다(`tools/package_release.py:29~31`). 기존 자산 정션을 사용하는 환경도 같은 경로가 필요하다. 외부 경로 검사 옵션 자체는 복원·복사·정션 생성을 수행하지 않는다.

```text
game/maps/archipelago/assets/
game/assets/interior/
game/assets/monsters/
game/maps/survival/assets/
game/assets/npc/
game/assets/portraits/
```

자산 준비와 아래 SVG 결함 수정을 담당 브랜치에서 반영한 다음 실제 빌드할 체크아웃에서 최종 검사를 실행한다. `--assets-root .`는 해당 체크아웃에 준비된 자산과 정션을 명시적으로 검사한다. 외부 폴더를 지정했을 때 성공했어도 이 단계는 필요하다.

```powershell
# 3. 검사기 회귀 테스트. 시스템 임시 폴더를 사용하지 않는다.
& $taskPython -m pytest tools/tests -q --basetemp=.codex-tmppytest -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw '검사기 테스트 실패: 빌드를 중단합니다.' }

# 4. 실제 후보 체크아웃의 자산을 포함한 최종 gate.
& $taskPython tools/predeploy/check_client.py --assets-root . --summary
if ($LASTEXITCODE -ne 0) { throw '배포 전 정적 검사 실패: 차단 항목을 수정합니다.' }

# 5. 위 두 단계가 통과한 뒤 담당자가 실행할 명령. 이번 작업에서는 실행하지 않았다.
powershell -ExecutionPolicy Bypass -File tools/build_game.ps1
if ($LASTEXITCODE -ne 0) { throw '게임 빌드 실패' }
```

`tools/build_game.ps1`은 두 맵의 bake를 먼저 수행한 뒤 Windows Desktop/Developer를 내보낸다. 학교용 내보내기·패치·배포는 해당 릴리스 절차에 따른다. 정적 검사 통과가 bake 성공, Godot import·컴파일 성공, 실행 검증이나 배포 승인을 대신하지 않는다.

다른 프로젝트에는 `--project-root <project.godot이 있는 폴더>`를 사용한다. 기본 대상은 호출 위치와 무관하게 검사기가 있는 저장소의 `game/`이다. JSON의 `file`은 프로젝트 루트 기준 상대 경로이고 `line`은 1부터 시작한다.

## 현재 차단 1건과 최소 수정안

`game/scripts/interaction_panel.gd:331`이 존재하지 않는 `res://assets/ui/starseed.svg`를 전달한다. 실제 SVG는 `game/assets/starseed.svg`에 있다.

```diff
- row.add_child(RpgUi.icon("res://assets/ui/starseed.svg", 24))
+ row.add_child(RpgUi.icon("res://assets/starseed.svg", 24))
```

`game/scripts/rpg_ui.gd:212~214`의 `painted()`는 현재 존재하는 `res://assets/ui/icons/starseed.png`로 대체한다. 따라서 지금 항상 아이콘이 보이지 않는다는 의미는 아니다. PNG가 없을 때 잘못된 SVG 대체 경로가 드러나는 결함이며 없는 리터럴을 숨기지 않고 차단으로 유지한다.

## 기존 차단 280건의 전수 분류

| 분류 | 건수 | 처리와 근거 |
| --- | ---: | --- |
| 복사할 빌드 자산 | 181 | archipelago 72, survival 70, interior 24, monsters 15. 별도 빌드 자산 목록으로 이동한다. |
| 테스트 전용 | 90 | `game/tests/`의 테스트 입력·출력·가상 경로. 배포용 소스 검사에서 제외한다. |
| 사운드 계열 접두사 | 3 | `life_sfx.gd:17~18`. 대응 번호 WAV 계열이 있는지 확인하며 없으면 차단한다. |
| 도구 출력·선택적 검증 자료 | 2 | `building_layout.gd:10`, `environment_layout.gd:20`의 한정된 경로. 파일 전체를 제외하지 않는다. |
| bake 생성물 | 2 | archipelago/survival의 `generated/` 참조. 별도 생성 자산으로 표시한다. |
| export 생성물 | 1 | `patch_boot.gd:125`의 `project.binary`. 내보낸 PCK에서 사용하는 설정 파일이다. |
| 실제 누락 리소스 | 1 | 위 SVG 경로 결함. 차단으로 유지한다. |
| 합계 | **280** | **181 + 90 + 3 + 2 + 2 + 1 + 1** |

이 집계는 개선 전 차단 위치를 분류한 값이다. 개선된 검사기는 기존 동적 경고였던 빌드 자산도 별도 목록에 넣고 NPC의 필수 파일을 구체화하므로 새 목록의 총 참조 수는 181 또는 184와 다를 수 있다. 기존 차단의 파일·행·경로별 근거는 [분류 JSON](PREDEPLOY_CHECK_0119_classification.json)에 보관한다.

## 빌드 자산으로 분리하는 근거와 검증 범위

`.gitignore`에 걸린다는 이유만으로 임의 파일을 허용하지 않는다. 검사기는 알려진 자산 폴더, 패키징 목록, 매니페스트와 생성 도구의 산출물 선언을 교차 확인한다. 자산 폴더 안의 참조된 스크립트·설정·매니페스트 누락은 계속 결함이다. 몬스터·인테리어·survival의 GLB와 archipelago 매니페스트가 열거하는 하위 폴더의 GLB는 명단과 대소문자까지 대조한다. archipelago 지형·`v5` 등 명단이 완전하지 않은 영역과 다른 동적 경로는 실제 자산 루트 검사와 빌드 검증이 필요하다.

| 자산 종류 | 저장소 근거 |
| --- | --- |
| archipelago 원본·소품 | `.gitignore:40~41`, `tools/package_release.py:29`, `tools/port_archipelago_map.py:43~59,73~79`, `game/maps/archipelago/building_placements.json`, `environment_layout.json`, `door_leaves.json` |
| interior | `.gitignore:53~56`, `tools/package_release.py:30`, `game/assets/interior/manifest.json`, `tools/generate_interior_assets.py:36~41,400` |
| monsters | `.gitignore:58~62`, `tools/package_release.py:30`, `game/assets/monsters/manifest.json`, `tools/build_monsters.py:25~26,163` |
| survival 원본·LOD | `.gitignore:64~68`, `tools/package_release.py:30`, `game/maps/survival/assets/manifest.json`, `tools/build_survival_assets.py:25,246~247` |
| NPC·portraits | `.gitignore:49~51`, `tools/package_release.py:31`, `game/scripts/main.gd:3604~3608`의 `CAST`, `game/scripts/residents.gd:22~28` |
| bake 생성물 | `.gitignore:42~44`, `tools/build_game.ps1:9,12`, 두 `tools/bake_*.py`의 `FILES`, `tools/game_patch.py:162~166`, `tools/package_release.py:109,112` |
| export 설정 | `tools/build_game.ps1`의 `--export-release`, `tools/game_patch.py:24,118~120,144~146`, `game/scripts/patch_boot.gd:125` |

NPC는 `npc.gd:44,48,51`에서 `%s.glb`로 조합된다. `main.gd`의 `CAST`에 있는 `naru`, `sora`, `moru`, `haeru`를 근거로 GLB 4개와 portrait PNG 4개를 확인한다. portrait의 사용 근거는 `main.gd:3802`, `interiors.gd:2794`다.

JSON의 `build_time_assets`에는 `resource`, `status`, `evidence`를 기록한다. 소스만 검사할 때 누락된 복사 자산은 `missing`으로 보류한다. `--assets-root`를 지정하면 현재 트리와 지정 루트 어디에도 없는 필수 복사 자산은 `missing-build-asset` 차단이다. 존재하는 자산은 `available`, 미확정 동적 패턴은 `pattern`이다. 후보가 있다는 사실만으로 모든 런타임 값을 증명하지 않는다.

생성물은 자산 루트를 지정해도 `generated`로 별도 기록한다. 이미 파일이 있어도 최신 소스와 일치하는지 정적 검사기는 확인하지 않는다. **bake/export 산출물의 최신성은 미검증**이며 빌드·패키징 단계에서 재생성·검증해야 한다.

기본 소스 인덱스는 심볼릭 링크와 Windows 정션을 따라가지 않는다. `--assets-root`로 명시한 루트 안에서는 알려진 자산 폴더의 정션을 따라 검사하며 순환·읽기 실패는 차단한다. `D:\lsm26` 등 특정 경로를 자동 탐색하지 않는다. 외부 자산의 스크립트나 JSON을 가져와 분석하는 방식도 아니다.

## 제외를 좁게 적용한 정상 용도

`life_sfx.gd:17~18`의 `harvest_stone`, `harvest_fiber`, `harvest_tree`는 파일명이 아닌 계열 이름이다. `:64`의 `SfxBank.pick()`과 `:98`의 `+"_1.wav"`가 실제 WAV를 찾는다. `sfx_bank.gd:3,11,37`에도 계열 형식이 명시되어 있다. 대응 WAV 없이 이름만 있는 경우는 허용하지 않는다.

`building_layout.gd:10`의 `OUTPUT`은 `:237`의 WRITE, `:265`의 PNG 저장에 사용하며 `:188`에서 `--placement-capture`로 제한한다. `environment_layout.gd:20`의 `output_path`도 `:503`의 WRITE, `:540`의 PNG 저장 및 `:450`의 캡처 가드가 있다. `:31~32`의 로컬 검증 JSON 읽기는 `file_exists`로 보호한다. 해당 경로만 제외하고 두 파일의 실제 GLB·매니페스트 참조는 검사한다. `game/tests/`, `game/tools/`는 배포 검사 대상에서 제외한다.

## 남아 있는 정적 검사의 한계

기존 UID, 선언 중복, preload·extends, 식별 가능한 정적 메서드, 신호 중복 연결, autoload, 입력 액션 검사는 유지한다. 주석은 검사하지 않으며 파일명 대소문자를 구별한다. 입력 액션은 `project.godot`의 선언이 기준이고 런타임 등록이나 엔진 기본 액션을 자동으로 가정하지 않는다.

이 도구는 완전한 GDScript 파서나 Godot 컴파일러가 아니다. 임의 함수의 반환값, 파일 간 동적 경로 전달, 모든 네이티브 API, 객체 별칭과 모든 제어 흐름을 증명하지 못한다. 동적 경로·입력 경고는 별도 검토가 필요하다. GLB 내부 무결성, import 결과, UID 캐시의 엔진 동작, bake 최신성, 실제 게임 화면·실행은 확인하지 않는다. 검사 통과 후에도 기존 빌드·실행 검증 절차를 수행한다.
