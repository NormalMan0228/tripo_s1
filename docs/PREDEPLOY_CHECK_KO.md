# Godot 클라이언트 배포 전 정적 검사

기준 커밋은 `ff066b7`이며, 검사 대상은 이 워크트리의 `game/`이다. **차단 279건, 경고 232건, 종료 코드 1**을 확인했다. 이는 발견 위치별 개수이며, 같은 경로가 여러 곳에 있으면 각각 집계한다. 전체 511건의 위치와 내용은 아래 표에 있으며, 같은 결과를 [JSON 스냅샷](PREDEPLOY_CHECK_ff066b7.json)으로도 제공한다.

이번 작업은 검사기, fixture 테스트, 문서만 추가했다. 게임 파일과 `project.godot`은 수정하지 않았고, Godot 실행·외부 호출·배포·커밋도 하지 않았다. i18n 검사는 별도 작업 범위이므로 포함하지 않는다.

## 실행 방법

저장소 루트에서 PowerShell로 실행한다. Python 표준 라이브러리만 사용하므로 추가 설치가 필요 없다.

```powershell
& 'C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe' tools/predeploy/check_client.py
& 'C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe' tools/predeploy/check_client.py --json
& 'C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe' -m unittest discover -s tools/tests -p 'test_predeploy*.py' -v
```

다른 소형 프로젝트를 검사하려면 `--project-root <project.godot이 있는 폴더>`를 지정한다. 기본 대상은 호출 위치와 무관하게 이 저장소의 `game/`이다. 차단 항목이 하나라도 있으면 종료 코드 **1**, 경고만 있거나 발견 사항이 없으면 **0**이다. JSON의 `file`은 프로젝트 루트 기준 상대 경로이며 `line`은 1부터 시작한다. 검사기 자체는 파일을 쓰거나 Godot을 실행하지 않는다.

테스트 **51개가 모두 통과**했다. 저장된 fixture 프로젝트 10개와 워크트리 안에 생성·정리하는 임시 fixture로 각 규칙, 정상 대조군, 실제 CLI의 JSON 및 종료 코드를 검증했다. 주석, 셰이더 `#include`, 대소문자, UID 자기 선언과 고아 sidecar, 형제 경로 UID, 중첩 동적 표현식, 부모 메서드, 내부 클래스 부모의 범위, 세미콜론 선언, 신호 문법 혼합도 포함한다.

## 검사 규칙

| 범위 | 판정 |
| --- | --- |
| 리소스 | `game/` 아래 `.gd`, `.tscn`, `.tres`, `.gdshader`, `.json`의 `res://`로 시작하는 문자열을 검사한다. 파일·디렉터리 존재 여부와 대소문자를 확인한다. 주석은 제외하며 `.godot`, `.git`, Python 캐시와 심볼릭 링크는 탐색하지 않는다. |
| 고정 경로 | 현재 트리에 없으면 `missing-resource` 차단이다. 코드에서 실제 읽기용인지, 출력용인지, 접두사인지에 따른 예외는 두지 않는다. 기존 `res://../` 형제 경로는 프로젝트 부모 폴더 안에서만 확인한다. |
| 동적 경로 | `+`, `%`, 포맷 자리표시자를 경고로 기록한다. 같은 파일의 최상위 문자열 `const`와 `DIR + name + ".glb"` 형태를 패턴으로 만들어 프로젝트 파일 후보 수와 최대 3개 예시를 출력한다. 후보가 0개여도 경고이며, 후보가 있어도 모든 런타임 값이 유효하다는 뜻은 아니다. 상수끼리의 조합도 경고로 유지한다. |
| UID | `.tscn`·`.tres` 참조가 실제 대상 파일이 존재하는 `.uid` sidecar 또는 같은 문서의 유효한 `ext_resource` 경로로 해결되지 않으면 차단한다. `gd_scene`·`gd_resource` 헤더 자신의 UID 선언은 참조에서 제외한다. |
| GDScript 선언 | 한 파일의 최상위 `func`, `signal`, `var`, `const` 이름이 중복되면 `duplicate-declaration` 차단이다. 종류가 달라도 같은 이름이면 검출한다. 내부 클래스와 지역 변수는 이 규칙에서 제외한다. |
| preload·extends | 없는 파일의 `preload`, 없는 스크립트·등록 클래스의 `extends`는 차단한다. 상대 경로도 확인한다. 스크립트의 `uid://` preload·extends는 `unresolved-preload`·`unresolved-extends` 경고로 남긴다. |
| 메서드 | `class_name` 또는 `const preload`로 식별한 `SomeClass.method()`를 검사한다. 해당 스크립트와 추적 가능한 부모에 없으면 `missing-method` 차단이다. 기본 생성자와 알려진 Script/Resource/Object API는 허용한다. |
| 신호 | 같은 함수에서 같은 신호와 callable을 다시 연결하고 적절한 `is_connected` 가드가 없으면 `duplicate-signal-connect` 경고다. `.bind()` 인자를 구별하며 `Object.connect("signal", cb)`와 `signal.connect(cb)`를 정규화한다. 연결 해제 뒤 재연결은 중복으로 보지 않는다. |
| autoload | `project.godot`의 모든 autoload 대상 파일을 검사하며 누락은 `missing-autoload` 차단이다. |
| 입력 | `Input.is_action_*`와 액션 인자가 있는 `InputMap` 호출을 검사한다. 리터럴 액션이 `[input]`에 없으면 `undefined-input-action` 차단이다. `&"action"`도 지원한다. 변수·계산식은 `dynamic-input-action` 경고다. |
| 검사 불가 | 프로젝트 설정 누락, 대상 폴더 누락, 읽기/디코딩 실패도 차단으로 보고한다. |

입력은 작업 지시대로 **`project.godot`에 명시된 액션**을 기준으로 삼는다. 엔진의 기본 `ui_*` 액션과 런타임 `InputMap.add_action()`도 선언을 대신하지 않는다. 현재 프로젝트에서 이 정책에 따른 리터럴 액션 차단은 0건이다.

이 도구는 완전한 GDScript 파서나 엔진 컴파일 검사가 아니다. 내부 클래스의 메서드, 중복 `class_name`의 모호한 해석, 동적 `load()`와 인스턴스, 특수 네이티브 부모의 전체 API, 프로젝트 바깥 형제 스크립트의 상속은 확정적으로 추적하지 않는다. 네이티브 클래스는 로컬 허용 목록이므로 새로운 엔진 클래스는 목록 보완이 필요할 수 있다. 동적 경로는 파일 간 상수 전달이나 임의 함수의 반환값을 평가하지 않으며, 후보 탐색은 `game/` 안에서만 한다. 신호 검사는 객체 별칭·재할당이나 양성 `is_connected` 뒤 조기 반환 등 모든 제어 흐름을 증명하지 않는다.

## 기준 커밋의 결과와 해석

| 규칙 | 차단 | 경고 |
| --- | ---: | ---: |
| 고정 리소스 경로 누락 | 279 | 0 |
| 동적 리소스 경로 | 0 | 217 |
| 동적 입력 액션 | 0 | 15 |
| UID, 중복 선언, preload, extends, 메서드, 신호, autoload, 리터럴 입력 액션 | 0 | 0 |
| 합계 | **279** | **232** |

GDScript 342개를 포함해 지정된 확장자를 재귀 검사했다. 차단 위치는 `maps/` 144건, `tests/` 90건, `assets/` 39건, `scripts/` 6건이다. JSON 안의 누락 리소스 참조는 175건이다. 이 수치는 현재 체크아웃에 실제로 있는 파일을 기준으로 하므로 로컬 생성 자산을 채우면 결과가 달라진다. 279건을 모두 게임 동작 버그로 해석하면 안 된다.

### 먼저 확인할 항목

1. **저장소에서 제외된 모델·생성 자산**: `game/assets/interior/manifest.json:11`의 `bed.glb`, `game/assets/monsters/manifest.json:20`의 `wolf_forest.glb`, `game/maps/archipelago/building_placements.json:12`의 `cafe.glb` 등이 현재 트리에 없다. `.gitignore`에는 해당 대형 자산과 생성 폴더가 제외되어 있다. 최소 조치는 필요한 자산을 매니페스트의 경로에 복원·생성하고 검사기를 재실행하는 것이다. 이번 작업에서는 다운로드나 생성 작업을 수행하지 않았다.
2. **SVG 대체 경로의 잠재 결함**: `game/scripts/interaction_panel.gd:331`은 없는 `res://assets/ui/starseed.svg`를 전달한다. 다만 `game/scripts/rpg_ui.gd:212`의 `painted()`가 현재 존재하는 `res://assets/ui/icons/starseed.png`로 대체하므로 현재 아이콘이 표시되지 않는다고 단정할 수 없다. PNG가 없을 때 사용하는 SVG 경로의 최소 수정안은 아래와 같다. 게임 파일에는 적용하지 않았다.

   ```diff
   - row.add_child(RpgUi.icon("res://assets/ui/starseed.svg", 24))
   + row.add_child(RpgUi.icon("res://assets/starseed.svg", 24))
   ```

3. **엄격한 리터럴 규칙에 걸리는 정상 용도**: `game/scripts/life_sfx.gd:17`·`:18`은 파일명이 아닌 사운드 계열 접두사이며, `:64`의 `SfxBank.pick()`과 `:98`의 `+"_1.wav"`가 실제 존재하는 WAV를 찾는다. `game/scripts/patch_boot.gd:125`의 `project.binary`는 내보낸 패치용이며 소스 체크아웃에는 없다. `game/tests/asset_motion.gd:64` 등의 `artifacts/` 경로는 생성할 테스트 출력이다. 이런 항목은 요구된 리터럴 존재 규칙 때문에 차단으로 유지하며, 게임 코드를 바꿔 해결할 근거는 없다.
4. **동적 경로 검토**: `game/scripts/interiors.gd:1259`의 `res://assets/interior/*.glb`는 후보 0개이며, `:2795`의 `res://assets/ui/day_*.png`는 후보 17개다. 경고는 런타임 값별 존재 여부를 보장하지 못한다는 뜻이다.
5. **동적 입력 액션 검토**: `game/scripts/game_settings.gd:517`의 `InputMap.has_action`·`add_action` 등 총 15건이다. 변수로 전달되는 이름을 `[input]` 선언과 대조해야 한다. 없는 리터럴 액션이나 autoload는 발견되지 않았다.

## 전체 발견 사항

각 행은 진단 1건이다. 같은 파일·행에 서로 다른 경로 또는 호출이 있으면 여러 행으로 표시한다. 아래 표의 경로는 저장소 루트 기준이며, JSON에서는 `game/` 접두사를 제외한다.

<!-- FINDINGS: 아래 내용은 ff066b7 검사 JSON에서 생성한 스냅샷이다. -->

### 차단 279건

| 위치 | 규칙 | 누락 경로 |
| --- | --- | --- |
| `game/assets/interior/manifest.json:11` | `missing-resource` | `res://assets/interior/bed.glb` |
| `game/assets/interior/manifest.json:43` | `missing-resource` | `res://assets/interior/wardrobe_closet.glb` |
| `game/assets/interior/manifest.json:75` | `missing-resource` | `res://assets/interior/bookshelf.glb` |
| `game/assets/interior/manifest.json:107` | `missing-resource` | `res://assets/interior/dining_table.glb` |
| `game/assets/interior/manifest.json:139` | `missing-resource` | `res://assets/interior/wooden_chair.glb` |
| `game/assets/interior/manifest.json:171` | `missing-resource` | `res://assets/interior/sofa.glb` |
| `game/assets/interior/manifest.json:203` | `missing-resource` | `res://assets/interior/kitchen_counter.glb` |
| `game/assets/interior/manifest.json:235` | `missing-resource` | `res://assets/interior/cooking_stove.glb` |
| `game/assets/interior/manifest.json:267` | `missing-resource` | `res://assets/interior/potted_plant.glb` |
| `game/assets/interior/manifest.json:299` | `missing-resource` | `res://assets/interior/floor_lamp.glb` |
| `game/assets/interior/manifest.json:331` | `missing-resource` | `res://assets/interior/shop_counter.glb` |
| `game/assets/interior/manifest.json:363` | `missing-resource` | `res://assets/interior/display_shelf.glb` |
| `game/assets/interior/manifest.json:395` | `missing-resource` | `res://assets/interior/crate_stack.glb` |
| `game/assets/interior/manifest.json:427` | `missing-resource` | `res://assets/interior/barrel.glb` |
| `game/assets/interior/manifest.json:459` | `missing-resource` | `res://assets/interior/workbench.glb` |
| `game/assets/interior/manifest.json:491` | `missing-resource` | `res://assets/interior/telescope.glb` |
| `game/assets/interior/manifest.json:523` | `missing-resource` | `res://assets/interior/seedling_bench.glb` |
| `game/assets/interior/manifest.json:555` | `missing-resource` | `res://assets/interior/cafe_counter.glb` |
| `game/assets/interior/manifest.json:587` | `missing-resource` | `res://assets/interior/round_cafe_table.glb` |
| `game/assets/interior/manifest.json:619` | `missing-resource` | `res://assets/interior/piano.glb` |
| `game/assets/interior/manifest.json:651` | `missing-resource` | `res://assets/interior/fireplace.glb` |
| `game/assets/interior/manifest.json:683` | `missing-resource` | `res://assets/interior/lighthouse_lens.glb` |
| `game/assets/interior/manifest.json:715` | `missing-resource` | `res://assets/interior/rug.glb` |
| `game/assets/interior/manifest.json:750` | `missing-resource` | `res://assets/interior/wall_clock.glb` |
| `game/assets/monsters/manifest.json:20` | `missing-resource` | `res://assets/monsters/wolf_forest.glb` |
| `game/assets/monsters/manifest.json:146` | `missing-resource` | `res://assets/monsters/boar_forest.glb` |
| `game/assets/monsters/manifest.json:272` | `missing-resource` | `res://assets/monsters/brute_forest.glb` |
| `game/assets/monsters/manifest.json:433` | `missing-resource` | `res://assets/monsters/wisp_forest.glb` |
| `game/assets/monsters/manifest.json:581` | `missing-resource` | `res://assets/monsters/shroom_forest.glb` |
| `game/assets/monsters/manifest.json:729` | `missing-resource` | `res://assets/monsters/wolf_quarry.glb` |
| `game/assets/monsters/manifest.json:857` | `missing-resource` | `res://assets/monsters/boar_quarry.glb` |
| `game/assets/monsters/manifest.json:985` | `missing-resource` | `res://assets/monsters/brute_quarry.glb` |
| `game/assets/monsters/manifest.json:1143` | `missing-resource` | `res://assets/monsters/wisp_quarry.glb` |
| `game/assets/monsters/manifest.json:1295` | `missing-resource` | `res://assets/monsters/shroom_quarry.glb` |
| `game/assets/monsters/manifest.json:1447` | `missing-resource` | `res://assets/monsters/wolf_frost.glb` |
| `game/assets/monsters/manifest.json:1571` | `missing-resource` | `res://assets/monsters/boar_frost.glb` |
| `game/assets/monsters/manifest.json:1695` | `missing-resource` | `res://assets/monsters/brute_frost.glb` |
| `game/assets/monsters/manifest.json:1849` | `missing-resource` | `res://assets/monsters/wisp_frost.glb` |
| `game/assets/monsters/manifest.json:1997` | `missing-resource` | `res://assets/monsters/shroom_frost.glb` |
| `game/maps/archipelago/building_layout.gd:10` | `missing-resource` | `res://../art/maps/archipelago_placement_v1/` |
| `game/maps/archipelago/building_placements.json:12` | `missing-resource` | `res://maps/archipelago/assets/buildings/cafe.glb` |
| `game/maps/archipelago/building_placements.json:76` | `missing-resource` | `res://maps/archipelago/assets/buildings/timber_house.glb` |
| `game/maps/archipelago/building_placements.json:140` | `missing-resource` | `res://maps/archipelago/assets/buildings/teal_cottage.glb` |
| `game/maps/archipelago/building_placements.json:204` | `missing-resource` | `res://maps/archipelago/assets/buildings/windmill.glb` |
| `game/maps/archipelago/building_placements.json:268` | `missing-resource` | `res://maps/archipelago/assets/buildings/observatory.glb` |
| `game/maps/archipelago/building_placements.json:332` | `missing-resource` | `res://maps/archipelago/assets/buildings/orange_cottage.glb` |
| `game/maps/archipelago/building_placements.json:396` | `missing-resource` | `res://maps/archipelago/assets/buildings/greenhouse.glb` |
| `game/maps/archipelago/building_placements.json:460` | `missing-resource` | `res://maps/archipelago/assets/buildings/gazebo.glb` |
| `game/maps/archipelago/building_placements.json:524` | `missing-resource` | `res://maps/archipelago/assets/buildings/town_hall.glb` |
| `game/maps/archipelago/building_placements.json:588` | `missing-resource` | `res://maps/archipelago/assets/buildings/red_house.glb` |
| `game/maps/archipelago/building_placements.json:652` | `missing-resource` | `res://maps/archipelago/assets/buildings/purple_house.glb` |
| `game/maps/archipelago/building_placements.json:716` | `missing-resource` | `res://maps/archipelago/assets/buildings/blue_house.glb` |
| `game/maps/archipelago/building_placements.json:780` | `missing-resource` | `res://maps/archipelago/assets/buildings/shop.glb` |
| `game/maps/archipelago/building_placements.json:844` | `missing-resource` | `res://maps/archipelago/assets/buildings/stage.glb` |
| `game/maps/archipelago/building_placements.json:897` | `missing-resource` | `res://maps/archipelago/assets/buildings/picnic_shelter.glb` |
| `game/maps/archipelago/building_placements.json:961` | `missing-resource` | `res://maps/archipelago/assets/buildings/blue_cottage.glb` |
| `game/maps/archipelago/building_placements.json:1025` | `missing-resource` | `res://maps/archipelago/assets/buildings/lighthouse.glb` |
| `game/maps/archipelago/building_placements.json:1089` | `missing-resource` | `res://maps/archipelago/assets/buildings/blue_house.glb` |
| `game/maps/archipelago/door_leaves.json:9` | `missing-resource` | `res://maps/archipelago/assets/buildings/cafe.glb` |
| `game/maps/archipelago/door_leaves.json:83` | `missing-resource` | `res://maps/archipelago/assets/buildings/timber_house.glb` |
| `game/maps/archipelago/door_leaves.json:153` | `missing-resource` | `res://maps/archipelago/assets/buildings/teal_cottage.glb` |
| `game/maps/archipelago/door_leaves.json:247` | `missing-resource` | `res://maps/archipelago/assets/buildings/windmill.glb` |
| `game/maps/archipelago/door_leaves.json:341` | `missing-resource` | `res://maps/archipelago/assets/buildings/observatory.glb` |
| `game/maps/archipelago/door_leaves.json:387` | `missing-resource` | `res://maps/archipelago/assets/buildings/orange_cottage.glb` |
| `game/maps/archipelago/door_leaves.json:473` | `missing-resource` | `res://maps/archipelago/assets/buildings/greenhouse.glb` |
| `game/maps/archipelago/door_leaves.json:519` | `missing-resource` | `res://maps/archipelago/assets/buildings/town_hall.glb` |
| `game/maps/archipelago/door_leaves.json:565` | `missing-resource` | `res://maps/archipelago/assets/buildings/red_house.glb` |
| `game/maps/archipelago/door_leaves.json:631` | `missing-resource` | `res://maps/archipelago/assets/buildings/purple_house.glb` |
| `game/maps/archipelago/door_leaves.json:729` | `missing-resource` | `res://maps/archipelago/assets/buildings/blue_house.glb` |
| `game/maps/archipelago/door_leaves.json:819` | `missing-resource` | `res://maps/archipelago/assets/buildings/shop.glb` |
| `game/maps/archipelago/door_leaves.json:865` | `missing-resource` | `res://maps/archipelago/assets/buildings/blue_cottage.glb` |
| `game/maps/archipelago/door_leaves.json:951` | `missing-resource` | `res://maps/archipelago/assets/buildings/lighthouse.glb` |
| `game/maps/archipelago/environment_layout.gd:20` | `missing-resource` | `res://../art/maps/archipelago_environment_v1/` |
| `game/maps/archipelago/environment_layout.json:10` | `missing-resource` | `res://maps/archipelago/assets/environment/bridge_short.glb` |
| `game/maps/archipelago/environment_layout.json:41` | `missing-resource` | `res://maps/archipelago/assets/environment/bridge_long.glb` |
| `game/maps/archipelago/environment_layout.json:72` | `missing-resource` | `res://maps/archipelago/assets/environment/tent_orange.glb` |
| `game/maps/archipelago/environment_layout.json:103` | `missing-resource` | `res://maps/archipelago/assets/environment/tent_green.glb` |
| `game/maps/archipelago/environment_layout.json:134` | `missing-resource` | `res://maps/archipelago/assets/environment/firepit.glb` |
| `game/maps/archipelago/environment_layout.json:165` | `missing-resource` | `res://maps/archipelago/assets/environment/bench.glb` |
| `game/maps/archipelago/environment_layout.json:196` | `missing-resource` | `res://maps/archipelago/assets/environment/lamp.glb` |
| `game/maps/archipelago/environment_layout.json:238` | `missing-resource` | `res://maps/archipelago/assets/environment/round_tree.glb` |
| `game/maps/archipelago/environment_layout.json:269` | `missing-resource` | `res://maps/archipelago/assets/environment/conifer.glb` |
| `game/maps/archipelago/environment_layout.json:300` | `missing-resource` | `res://maps/archipelago/assets/environment/palm.glb` |
| `game/maps/archipelago/environment_layout.json:331` | `missing-resource` | `res://maps/archipelago/assets/environment/shrub.glb` |
| `game/maps/archipelago/environment_layout.json:362` | `missing-resource` | `res://maps/archipelago/assets/environment/white_flowers.glb` |
| `game/maps/archipelago/environment_layout.json:393` | `missing-resource` | `res://maps/archipelago/assets/environment/yellow_flowers.glb` |
| `game/maps/archipelago/environment_layout.json:424` | `missing-resource` | `res://maps/archipelago/assets/environment/bridge_rope.glb` |
| `game/maps/archipelago/environment_layout.json:455` | `missing-resource` | `res://maps/archipelago/assets/environment/bridge_boardwalk.glb` |
| `game/maps/archipelago/environment_layout.json:486` | `missing-resource` | `res://maps/archipelago/assets/environment/pier.glb` |
| `game/maps/archipelago/environment_layout.json:517` | `missing-resource` | `res://maps/archipelago/assets/environment/boat.glb` |
| `game/maps/archipelago/environment_layout.json:548` | `missing-resource` | `res://maps/archipelago/assets/environment/picnic_table.glb` |
| `game/maps/archipelago/environment_layout.json:579` | `missing-resource` | `res://maps/archipelago/assets/environment/beach_umbrella.glb` |
| `game/maps/archipelago/environment_layout.json:610` | `missing-resource` | `res://maps/archipelago/assets/environment/beach_lounger.glb` |
| `game/maps/archipelago/environment_layout.json:641` | `missing-resource` | `res://maps/archipelago/assets/environment/cafe_umbrella.glb` |
| `game/maps/archipelago/environment_layout.json:672` | `missing-resource` | `res://maps/archipelago/assets/environment/cafe_table.glb` |
| `game/maps/archipelago/environment_layout.json:703` | `missing-resource` | `res://maps/archipelago/assets/environment/cafe_chair.glb` |
| `game/maps/archipelago/environment_layout.json:734` | `missing-resource` | `res://maps/archipelago/assets/environment/signboard.glb` |
| `game/maps/archipelago/environment_layout.json:765` | `missing-resource` | `res://maps/archipelago/assets/environment/timber_fence.glb` |
| `game/maps/archipelago/environment_layout.json:796` | `missing-resource` | `res://maps/archipelago/assets/environment/picket_fence.glb` |
| `game/maps/archipelago/environment_layout.json:827` | `missing-resource` | `res://maps/archipelago/assets/environment/speaker.glb` |
| `game/maps/archipelago/environment_layout.json:858` | `missing-resource` | `res://maps/archipelago/assets/environment/planter.glb` |
| `game/maps/archipelago/environment_layout.json:889` | `missing-resource` | `res://maps/archipelago/assets/environment/pink_flowers.glb` |
| `game/maps/archipelago/environment_layout.json:920` | `missing-resource` | `res://maps/archipelago/assets/environment/reeds.glb` |
| `game/maps/archipelago/environment_layout.json:8323` | `missing-resource` | `res://maps/archipelago/assets/fitted_bridges/18_bridge_short.glb` |
| `game/maps/archipelago/environment_layout.json:8567` | `missing-resource` | `res://maps/archipelago/assets/fitted_bridges/49_bridge_boardwalk.glb` |
| `game/maps/archipelago/environment_layout.json:8816` | `missing-resource` | `res://maps/archipelago/assets/fitted_bridges/48_bridge_rope.glb` |
| `game/maps/archipelago/environment_layout.json:9060` | `missing-resource` | `res://maps/archipelago/assets/fitted_bridges/19_bridge_long.glb` |
| `game/maps/archipelago/island_bake.gd:26` | `missing-resource` | `res://maps/archipelago/generated/` |
| `game/maps/archipelago/island_bake.gd:42` | `missing-resource` | `res://maps/archipelago/assets/` |
| `game/maps/archipelago/plots.gd:27` | `missing-resource` | `res://maps/archipelago/assets/buildings/teal_cottage.glb` |
| `game/maps/survival/assets/manifest.json:10` | `missing-resource` | `res://maps/survival/assets/pine_tall.glb` |
| `game/maps/survival/assets/manifest.json:11` | `missing-resource` | `res://maps/survival/assets/pine_tall_lod1.glb` |
| `game/maps/survival/assets/manifest.json:32` | `missing-resource` | `res://maps/survival/assets/oak_broad.glb` |
| `game/maps/survival/assets/manifest.json:33` | `missing-resource` | `res://maps/survival/assets/oak_broad_lod1.glb` |
| `game/maps/survival/assets/manifest.json:54` | `missing-resource` | `res://maps/survival/assets/birch_slim.glb` |
| `game/maps/survival/assets/manifest.json:55` | `missing-resource` | `res://maps/survival/assets/birch_slim_lod1.glb` |
| `game/maps/survival/assets/manifest.json:76` | `missing-resource` | `res://maps/survival/assets/bush_round.glb` |
| `game/maps/survival/assets/manifest.json:77` | `missing-resource` | `res://maps/survival/assets/bush_round_lod1.glb` |
| `game/maps/survival/assets/manifest.json:98` | `missing-resource` | `res://maps/survival/assets/berry_bush.glb` |
| `game/maps/survival/assets/manifest.json:99` | `missing-resource` | `res://maps/survival/assets/berry_bush_lod1.glb` |
| `game/maps/survival/assets/manifest.json:120` | `missing-resource` | `res://maps/survival/assets/fiber_grass.glb` |
| `game/maps/survival/assets/manifest.json:121` | `missing-resource` | `res://maps/survival/assets/fiber_grass_lod1.glb` |
| `game/maps/survival/assets/manifest.json:142` | `missing-resource` | `res://maps/survival/assets/stone_pile.glb` |
| `game/maps/survival/assets/manifest.json:143` | `missing-resource` | `res://maps/survival/assets/stone_pile_lod1.glb` |
| `game/maps/survival/assets/manifest.json:164` | `missing-resource` | `res://maps/survival/assets/fern_clump.glb` |
| `game/maps/survival/assets/manifest.json:165` | `missing-resource` | `res://maps/survival/assets/fern_clump_lod1.glb` |
| `game/maps/survival/assets/manifest.json:186` | `missing-resource` | `res://maps/survival/assets/mushroom_cluster.glb` |
| `game/maps/survival/assets/manifest.json:187` | `missing-resource` | `res://maps/survival/assets/mushroom_cluster_lod1.glb` |
| `game/maps/survival/assets/manifest.json:208` | `missing-resource` | `res://maps/survival/assets/fallen_log.glb` |
| `game/maps/survival/assets/manifest.json:209` | `missing-resource` | `res://maps/survival/assets/fallen_log_lod1.glb` |
| `game/maps/survival/assets/manifest.json:230` | `missing-resource` | `res://maps/survival/assets/tree_stump.glb` |
| `game/maps/survival/assets/manifest.json:231` | `missing-resource` | `res://maps/survival/assets/tree_stump_lod1.glb` |
| `game/maps/survival/assets/manifest.json:252` | `missing-resource` | `res://maps/survival/assets/mossy_boulder.glb` |
| `game/maps/survival/assets/manifest.json:253` | `missing-resource` | `res://maps/survival/assets/mossy_boulder_lod1.glb` |
| `game/maps/survival/assets/manifest.json:274` | `missing-resource` | `res://maps/survival/assets/signpost.glb` |
| `game/maps/survival/assets/manifest.json:275` | `missing-resource` | `res://maps/survival/assets/signpost_lod1.glb` |
| `game/maps/survival/assets/manifest.json:296` | `missing-resource` | `res://maps/survival/assets/log_bench.glb` |
| `game/maps/survival/assets/manifest.json:297` | `missing-resource` | `res://maps/survival/assets/log_bench_lod1.glb` |
| `game/maps/survival/assets/manifest.json:318` | `missing-resource` | `res://maps/survival/assets/camp_supplies.glb` |
| `game/maps/survival/assets/manifest.json:319` | `missing-resource` | `res://maps/survival/assets/camp_supplies_lod1.glb` |
| `game/maps/survival/assets/manifest.json:340` | `missing-resource` | `res://maps/survival/assets/firewood_pile.glb` |
| `game/maps/survival/assets/manifest.json:341` | `missing-resource` | `res://maps/survival/assets/firewood_pile_lod1.glb` |
| `game/maps/survival/assets/manifest.json:362` | `missing-resource` | `res://maps/survival/assets/forest_ruin.glb` |
| `game/maps/survival/assets/manifest.json:363` | `missing-resource` | `res://maps/survival/assets/forest_ruin_lod1.glb` |
| `game/maps/survival/assets/manifest.json:384` | `missing-resource` | `res://maps/survival/assets/sandstone_cliff.glb` |
| `game/maps/survival/assets/manifest.json:385` | `missing-resource` | `res://maps/survival/assets/sandstone_cliff_lod1.glb` |
| `game/maps/survival/assets/manifest.json:406` | `missing-resource` | `res://maps/survival/assets/sandstone_boulder.glb` |
| `game/maps/survival/assets/manifest.json:407` | `missing-resource` | `res://maps/survival/assets/sandstone_boulder_lod1.glb` |
| `game/maps/survival/assets/manifest.json:428` | `missing-resource` | `res://maps/survival/assets/cut_blocks.glb` |
| `game/maps/survival/assets/manifest.json:429` | `missing-resource` | `res://maps/survival/assets/cut_blocks_lod1.glb` |
| `game/maps/survival/assets/manifest.json:450` | `missing-resource` | `res://maps/survival/assets/mine_cart.glb` |
| `game/maps/survival/assets/manifest.json:451` | `missing-resource` | `res://maps/survival/assets/mine_cart_lod1.glb` |
| `game/maps/survival/assets/manifest.json:472` | `missing-resource` | `res://maps/survival/assets/quarry_crane.glb` |
| `game/maps/survival/assets/manifest.json:473` | `missing-resource` | `res://maps/survival/assets/quarry_crane_lod1.glb` |
| `game/maps/survival/assets/manifest.json:494` | `missing-resource` | `res://maps/survival/assets/dead_tree.glb` |
| `game/maps/survival/assets/manifest.json:495` | `missing-resource` | `res://maps/survival/assets/dead_tree_lod1.glb` |
| `game/maps/survival/assets/manifest.json:516` | `missing-resource` | `res://maps/survival/assets/dry_shrub.glb` |
| `game/maps/survival/assets/manifest.json:517` | `missing-resource` | `res://maps/survival/assets/dry_shrub_lod1.glb` |
| `game/maps/survival/assets/manifest.json:538` | `missing-resource` | `res://maps/survival/assets/ember_rock.glb` |
| `game/maps/survival/assets/manifest.json:539` | `missing-resource` | `res://maps/survival/assets/ember_rock_lod1.glb` |
| `game/maps/survival/assets/manifest.json:560` | `missing-resource` | `res://maps/survival/assets/tool_rack.glb` |
| `game/maps/survival/assets/manifest.json:561` | `missing-resource` | `res://maps/survival/assets/tool_rack_lod1.glb` |
| `game/maps/survival/assets/manifest.json:582` | `missing-resource` | `res://maps/survival/assets/snow_pine.glb` |
| `game/maps/survival/assets/manifest.json:583` | `missing-resource` | `res://maps/survival/assets/snow_pine_lod1.glb` |
| `game/maps/survival/assets/manifest.json:604` | `missing-resource` | `res://maps/survival/assets/ice_crystal.glb` |
| `game/maps/survival/assets/manifest.json:605` | `missing-resource` | `res://maps/survival/assets/ice_crystal_lod1.glb` |
| `game/maps/survival/assets/manifest.json:626` | `missing-resource` | `res://maps/survival/assets/snow_boulder.glb` |
| `game/maps/survival/assets/manifest.json:627` | `missing-resource` | `res://maps/survival/assets/snow_boulder_lod1.glb` |
| `game/maps/survival/assets/manifest.json:648` | `missing-resource` | `res://maps/survival/assets/frost_shrub.glb` |
| `game/maps/survival/assets/manifest.json:649` | `missing-resource` | `res://maps/survival/assets/frost_shrub_lod1.glb` |
| `game/maps/survival/assets/manifest.json:670` | `missing-resource` | `res://maps/survival/assets/snowman.glb` |
| `game/maps/survival/assets/manifest.json:671` | `missing-resource` | `res://maps/survival/assets/snowman_lod1.glb` |
| `game/maps/survival/assets/manifest.json:692` | `missing-resource` | `res://maps/survival/assets/sled.glb` |
| `game/maps/survival/assets/manifest.json:693` | `missing-resource` | `res://maps/survival/assets/sled_lod1.glb` |
| `game/maps/survival/assets/manifest.json:714` | `missing-resource` | `res://maps/survival/assets/sled_empty.glb` |
| `game/maps/survival/assets/manifest.json:715` | `missing-resource` | `res://maps/survival/assets/sled_empty_lod1.glb` |
| `game/maps/survival/assets/manifest.json:736` | `missing-resource` | `res://maps/survival/assets/snow_fence.glb` |
| `game/maps/survival/assets/manifest.json:737` | `missing-resource` | `res://maps/survival/assets/snow_fence_lod1.glb` |
| `game/maps/survival/assets/manifest.json:758` | `missing-resource` | `res://maps/survival/assets/frost_shrine.glb` |
| `game/maps/survival/assets/manifest.json:759` | `missing-resource` | `res://maps/survival/assets/frost_shrine_lod1.glb` |
| `game/maps/survival/survival_bake.gd:34` | `missing-resource` | `res://maps/survival/generated/` |
| `game/maps/survival/survival_map.gd:14` | `missing-resource` | `res://maps/archipelago/assets/` |
| `game/maps/survival/survival_map.gd:15` | `missing-resource` | `res://maps/archipelago/assets/v5/` |
| `game/scripts/interaction_panel.gd:331` | `missing-resource` | `res://assets/ui/starseed.svg` |
| `game/scripts/interiors.gd:23` | `missing-resource` | `res://maps/archipelago/assets/environment/` |
| `game/scripts/life_sfx.gd:17` | `missing-resource` | `res://assets/sfx/combat/harvest_fiber` |
| `game/scripts/life_sfx.gd:17` | `missing-resource` | `res://assets/sfx/combat/harvest_stone` |
| `game/scripts/life_sfx.gd:18` | `missing-resource` | `res://assets/sfx/combat/harvest_tree` |
| `game/scripts/patch_boot.gd:125` | `missing-resource` | `res://project.binary` |
| `game/tests/archetype_gallery.gd:241` | `missing-resource` | `res://../artifacts/archetype-gallery.png` |
| `game/tests/asset_motion.gd:64` | `missing-resource` | `res://../artifacts/explorer-walk.png` |
| `game/tests/asset_motion.gd:77` | `missing-resource` | `res://../artifacts/explorer-gather.png` |
| `game/tests/asset_motion.gd:85` | `missing-resource` | `res://../artifacts/explorer-attack.png` |
| `game/tests/audio_bank_check.gd:76` | `missing-resource` | `res://../artifacts/audio-bank-check.txt` |
| `game/tests/audio_bank_check.gd:232` | `missing-resource` | `res://assets/portraits/haeru.png` |
| `game/tests/avatar_everywhere_check.gd:168` | `missing-resource` | `res://../artifacts/avatar-everywhere` |
| `game/tests/character_scale_review.gd:49` | `missing-resource` | `res://../artifacts` |
| `game/tests/content_patch.gd:13` | `missing-resource` | `res://../artifacts` |
| `game/tests/controller_acceptance.gd:18` | `missing-resource` | `res://../artifacts` |
| `game/tests/controller_motion_review.gd:17` | `missing-resource` | `res://../artifacts/controller-motion` |
| `game/tests/craft_badge_check.gd:40` | `missing-resource` | `res://../artifacts/craft-badge.png` |
| `game/tests/craft_one_check.gd:171` | `missing-resource` | `res://../artifacts/craft-one-side-by-side.png` |
| `game/tests/door_sounds_check.gd:75` | `missing-resource` | `res://../artifacts/door-sounds-check.txt` |
| `game/tests/door_test_capture.gd:20` | `missing-resource` | `res://../artifacts/mapdoor/door_test/` |
| `game/tests/explorer_b_integration.gd:12` | `missing-resource` | `res://../artifacts/explorer-b-game.png` |
| `game/tests/explorer_b_integration.gd:24` | `missing-resource` | `res://../artifacts/explorer-b-tool.png` |
| `game/tests/field_objects_check.gd:148` | `missing-resource` | `res://../artifacts/field-objects-check.txt` |
| `game/tests/furniture_stress.gd:16` | `missing-resource` | `res://../artifacts/furniture-stress.json` |
| `game/tests/furniture_stress.gd:39` | `missing-resource` | `res://../artifacts/furniture-stress.png` |
| `game/tests/furniture_stress.gd:41` | `missing-resource` | `res://../artifacts/furniture-stress-results.json` |
| `game/tests/haeru_motion_review.gd:19` | `missing-resource` | `res://../artifacts/haeru-motion` |
| `game/tests/home_visit.gd:61` | `missing-resource` | `res://../artifacts/home-visit-guest.png` |
| `game/tests/home_visit.gd:66` | `missing-resource` | `res://../artifacts/home-visit-host.png` |
| `game/tests/ime_probe.gd:37` | `missing-resource` | `res://../artifacts/ime-probe.txt` |
| `game/tests/interaction_check.gd:108` | `missing-resource` | `res://../artifacts/interaction-editor.png` |
| `game/tests/ix_lab.gd:20` | `missing-resource` | `res://maps/archipelago/assets/environment/bench.glb` |
| `game/tests/ix_lab.gd:20` | `missing-resource` | `res://maps/archipelago/assets/environment/cafe_chair.glb` |
| `game/tests/ix_lab.gd:21` | `missing-resource` | `res://maps/archipelago/assets/environment/beach_lounger.glb` |
| `game/tests/ix_lab.gd:21` | `missing-resource` | `res://maps/archipelago/assets/environment/picnic_table.glb` |
| `game/tests/ix_lab.gd:72` | `missing-resource` | `res://../artifacts/ix` |
| `game/tests/ix_lab.gd:287` | `missing-resource` | `res://../artifacts/ix/ix_sheet.jpg` |
| `game/tests/ix_prop_probe.gd:9` | `missing-resource` | `res://maps/archipelago/assets/environment/bench.glb` |
| `game/tests/ix_prop_probe.gd:9` | `missing-resource` | `res://maps/archipelago/assets/environment/picnic_table.glb` |
| `game/tests/ix_prop_probe.gd:10` | `missing-resource` | `res://maps/archipelago/assets/environment/beach_lounger.glb` |
| `game/tests/ix_prop_probe.gd:10` | `missing-resource` | `res://maps/archipelago/assets/environment/cafe_chair.glb` |
| `game/tests/ix_sources_check.gd:153` | `missing-resource` | `res://maps/archipelago/assets/environment/bench.glb` |
| `game/tests/ix_sources_check.gd:153` | `missing-resource` | `res://maps/archipelago/assets/environment/picnic_table.glb` |
| `game/tests/ix_sources_check.gd:154` | `missing-resource` | `res://maps/archipelago/assets/environment/beach_lounger.glb` |
| `game/tests/ix_sources_check.gd:154` | `missing-resource` | `res://maps/archipelago/assets/environment/cafe_chair.glb` |
| `game/tests/life_loop.gd:26` | `missing-resource` | `res://../.tools/server-venv/Scripts/python.exe` |
| `game/tests/living_objects_check.gd:138` | `missing-resource` | `res://../artifacts/clock-tick-1.png` |
| `game/tests/living_objects_check.gd:140` | `missing-resource` | `res://../artifacts/clock-tick-2.png` |
| `game/tests/locomotion_continuity.gd:51` | `missing-resource` | `res://../artifacts/production-lab-20261003` |
| `game/tests/material_restore.gd:6` | `missing-resource` | `res://../artifacts/material-cases.json` |
| `game/tests/measure_gait.gd:42` | `missing-resource` | `res://../artifacts/production-lab-20261003/source-gait-measurement.json` |
| `game/tests/monster_gallery.gd:27` | `missing-resource` | `res://../artifacts/monsters` |
| `game/tests/monsters.gd:39` | `missing-resource` | `res://../artifacts/monsters.png` |
| `game/tests/monsters.gd:46` | `missing-resource` | `res://../artifacts/monsters-windup.png` |
| `game/tests/patch_update_check.gd:161` | `missing-resource` | `res://qa_patch_probe.txt` |
| `game/tests/patch_update_check.gd:162` | `missing-resource` | `res://qa_patch_filler.bin` |
| `game/tests/patch_update_check.gd:192` | `missing-resource` | `res://../artifacts/qa-patch/client_policy.json` |
| `game/tests/patch_update_check.gd:278` | `missing-resource` | `res://qa_patch_probe.txt` |
| `game/tests/perf_overlay_check.gd:96` | `missing-resource` | `res://../artifacts` |
| `game/tests/perf_overlay_hud.gd:38` | `missing-resource` | `res://../artifacts` |
| `game/tests/picture_furniture.gd:4` | `missing-resource` | `res://../artifacts/picture-furniture-20261002/` |
| `game/tests/plot_views.gd:42` | `missing-resource` | `res://../artifacts/mapinterior` |
| `game/tests/settings_check.gd:498` | `missing-resource` | `res://../artifacts` |
| `game/tests/sfx_bank_check.gd:23` | `missing-resource` | `res://assets/sfx/combat/hit_flesh` |
| `game/tests/sfx_bank_check.gd:24` | `missing-resource` | `res://assets/sfx/ui/hover` |
| `game/tests/sfx_bank_check.gd:25` | `missing-resource` | `res://assets/sfx/combat/hit_stone` |
| `game/tests/sfx_bank_check.gd:26` | `missing-resource` | `res://assets/sfx/ui/__no_such_family__` |
| `game/tests/sfx_bank_check.gd:28` | `missing-resource` | `res://assets/sfx/__test__/single_take` |
| `game/tests/shadow_folk_portraits.gd:21` | `missing-resource` | `res://../artifacts/shadow-folk-portraits/` |
| `game/tests/smoke.gd:83` | `missing-resource` | `res://../artifacts/village-preview.png` |
| `game/tests/story_journal.gd:18` | `missing-resource` | `res://../artifacts/story-journal.png` |
| `game/tests/studio_binding.gd:26` | `missing-resource` | `res://../artifacts/studio-binding.png` |
| `game/tests/studio_e2e.gd:59` | `missing-resource` | `res://../artifacts/studio-e2e.png` |
| `game/tests/studio_e2e.gd:68` | `missing-resource` | `res://../artifacts/studio-e2e.json` |
| `game/tests/studio_flow.gd:40` | `missing-resource` | `res://../artifacts/studio-interaction.png` |
| `game/tests/studio_mode_review.gd:25` | `missing-resource` | `res://../artifacts` |
| `game/tests/studio_review.gd:13` | `missing-resource` | `res://../artifacts/studio-review.png` |
| `game/tests/studio_sync.gd:71` | `missing-resource` | `res://../artifacts/generated-controls.png` |
| `game/tests/terrain_ab_capture.gd:22` | `missing-resource` | `res://../artifacts/terrain_p2/ab/` |
| `game/tests/terrain_probe.gd:190` | `missing-resource` | `res://maps/archipelago/assets/archipelago_terrain_environment_v1.glb` |
| `game/tests/texture_shrink_check.gd:15` | `missing-resource` | `res://assets/interior/barrel.glb` |
| `game/tests/title_art_check.gd:29` | `missing-resource` | `res://assets/title_` |
| `game/tests/transition_frames.gd:114` | `missing-resource` | `res://../artifacts/transition-frames.png` |
| `game/tests/transition_frames.gd:115` | `missing-resource` | `res://../artifacts/transition-frames.txt` |
| `game/tests/treasure_spots.gd:141` | `missing-resource` | `res://../artifacts/treasure-spots.txt` |
| `game/tests/version_gate_check.gd:176` | `missing-resource` | `res://../artifacts/qa-version/client_policy.json` |
| `game/tests/vfx_check.gd:201` | `missing-resource` | `res://../artifacts/vfx_sheet.png` |
| `game/tests/village_furniture.gd:44` | `missing-resource` | `res://../artifacts/village-furniture.png` |
| `game/tests/village_rest_check.gd:133` | `missing-resource` | `res://../artifacts/village-sit.jpg` |
| `game/tests/village_rest_check.gd:134` | `missing-resource` | `res://../artifacts/village-sit.jpg` |
| `game/tests/vm_edges.gd:3` | `missing-resource` | `res://../artifacts/vm-edges.json` |
| `game/tests/vm_edges.gd:13` | `missing-resource` | `res://../artifacts/vm-edges-results.json` |
| `game/tests/vm_parity.gd:4` | `missing-resource` | `res://../artifacts/vm-parity.json` |
| `game/tests/world_navigation.gd:27` | `missing-resource` | `res://../artifacts/harbor-walk.png` |
| `game/tests/world_polish_capture.gd:135` | `missing-resource` | `res://assets/portraits/haeru.png` |

### 경고 232건

| 위치 | 규칙 | 내용 |
| --- | --- | --- |
| `game/maps/archipelago/archipelago.gd:5` | `dynamic-resource` | `res://maps/archipelago/assets/archipelago_terrain_environment_v1.glb` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:26` | `dynamic-resource` | `res://maps/archipelago/building_placements.json` / 후보 1개 |
| `game/maps/archipelago/archipelago.gd:29` | `dynamic-resource` | `res://maps/archipelago/environment_layout.json` / 후보 1개 |
| `game/maps/archipelago/archipelago.gd:33` | `dynamic-resource` | `res://maps/archipelago/assets/prop_lods/*.glb` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:46` | `dynamic-resource` | `res://maps/archipelago/assets/v3/*_surface_normal.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:49` | `dynamic-resource` | `res://maps/archipelago/assets/v5/*.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:153` | `dynamic-resource` | `res://maps/archipelago/building_layout.gd` / 후보 1개 |
| `game/maps/archipelago/archipelago.gd:174` | `dynamic-resource` | `res://maps/archipelago/*` / 후보 65개 |
| `game/maps/archipelago/archipelago.gd:176` | `dynamic-resource` | `res://maps/archipelago/assets/v3/*_surface_normal.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:177` | `dynamic-resource` | `res://maps/archipelago/assets/v5/current_field.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:178` | `dynamic-resource` | `res://maps/archipelago/assets/v5/coast_field.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:179` | `dynamic-resource` | `res://maps/archipelago/assets/v5/shore_distance.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:180` | `dynamic-resource` | `res://maps/archipelago/assets/v5/organic_foam.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:187` | `dynamic-resource` | `res://maps/archipelago/*` / 후보 65개 |
| `game/maps/archipelago/archipelago.gd:189` | `dynamic-resource` | `res://maps/archipelago/assets/v3/pond_surface_normal.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:190` | `dynamic-resource` | `res://maps/archipelago/assets/v5/organic_foam.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:197` | `dynamic-resource` | `res://maps/archipelago/waterfall_splash.gdshader` / 후보 1개 |
| `game/maps/archipelago/archipelago.gd:199` | `dynamic-resource` | `res://maps/archipelago/assets/v5/organic_foam.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:208` | `dynamic-resource` | `res://maps/archipelago/ground_surface.gdshader` / 후보 1개 |
| `game/maps/archipelago/archipelago.gd:212` | `dynamic-resource` | `res://maps/archipelago/assets/v5/*.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:213` | `dynamic-resource` | `res://maps/archipelago/assets/v5/grass_detail_normal.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:214` | `dynamic-resource` | `res://maps/archipelago/assets/v5/sand_detail_normal.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:215` | `dynamic-resource` | `res://maps/archipelago/assets/v5/headland_normals.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:219` | `dynamic-resource` | `res://maps/archipelago/rock_surface.gdshader` / 후보 1개 |
| `game/maps/archipelago/archipelago.gd:220` | `dynamic-resource` | `res://maps/archipelago/assets/v5/rock_detail.png` / 후보 0개 |
| `game/maps/archipelago/archipelago.gd:225` | `dynamic-resource` | `res://maps/archipelago/environment_layout.gd` / 후보 1개 |
| `game/maps/archipelago/building_layout.gd:237` | `dynamic-resource` | `res://../art/maps/archipelago_placement_v1/placement_verification.json` / 후보 0개 |
| `game/maps/archipelago/building_layout.gd:265` | `dynamic-resource` | `res://../art/maps/archipelago_placement_v1/*.png` / 후보 0개 |
| `game/maps/archipelago/environment_layout.gd:30` | `dynamic-resource` | `res://../*/` / 후보 0개 |
| `game/maps/archipelago/environment_layout.gd:77` | `dynamic-resource` | `res://maps/archipelago/assets/prop_lods/*.glb` / 후보 0개 |
| `game/maps/archipelago/environment_layout.gd:132` | `dynamic-resource` | `res://../*/` / 후보 0개 |
| `game/maps/archipelago/environment_layout.gd:216` | `dynamic-resource` | `res://maps/archipelago/assets/prop_lods/*.glb` / 후보 0개 |
| `game/maps/archipelago/island_bake.gd:27` | `dynamic-resource` | `res://maps/archipelago/generated/manifest.json` / 후보 0개 |
| `game/maps/archipelago/island_bake.gd:28` | `dynamic-resource` | `res://maps/archipelago/generated/collision.res` / 후보 0개 |
| `game/maps/archipelago/island_bake.gd:29` | `dynamic-resource` | `res://maps/archipelago/generated/island.scn` / 후보 0개 |
| `game/maps/archipelago/island_bake.gd:30` | `dynamic-resource` | `res://maps/archipelago/generated/ground.scn` / 후보 0개 |
| `game/maps/archipelago/island_bake.gd:108` | `dynamic-resource` | `res://maps/archipelago/assets/*` / 후보 0개 |
| `game/maps/survival/survival_bake.gd:56` | `dynamic-resource` | `res://maps/survival/generated/survival_*.res` / 후보 0개 |
| `game/maps/survival/survival_map.gd:159` | `dynamic-resource` | `res://maps/survival/layouts.json` / 후보 1개 |
| `game/maps/survival/survival_map.gd:221` | `dynamic-resource` | `res://maps/archipelago/assets/*` / 후보 0개 |
| `game/maps/survival/survival_map.gd:222` | `dynamic-resource` | `res://maps/survival/assets/*.glb` / 후보 0개 |
| `game/maps/survival/survival_map.gd:222` | `dynamic-resource` | `res://maps/survival/assets/*_lod1.glb` / 후보 0개 |
| `game/maps/survival/survival_map.gd:514` | `dynamic-resource` | `res://maps/archipelago/assets/v5/*.png` / 후보 0개 |
| `game/maps/survival/survival_map.gd:515` | `dynamic-resource` | `res://maps/archipelago/assets/v5/grass_detail_normal.png` / 후보 0개 |
| `game/maps/survival/survival_map.gd:516` | `dynamic-resource` | `res://maps/archipelago/assets/v5/sand_detail_normal.png` / 후보 0개 |
| `game/maps/survival/survival_map.gd:517` | `dynamic-resource` | `res://maps/archipelago/assets/v5/rock_detail_normal.png` / 후보 0개 |
| `game/maps/survival/survival_map.gd:595` | `dynamic-resource` | `res://maps/archipelago/assets/v3/pond_surface_normal.png` / 후보 0개 |
| `game/maps/survival/survival_map.gd:986` | `dynamic-resource` | `res://maps/survival/assets/sled_empty.glb` / 후보 0개 |
| `game/scripts/build/placed_menu.gd:83` | `dynamic-resource` | `res://assets/ui/*.svg` / 후보 52개 |
| `game/scripts/chat_box.gd:226` | `dynamic-input-action` | `InputMap.has_action` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/chat_box.gd:295` | `dynamic-resource` | `res://assets/ui/icons/crown.png*` / 후보 2개 |
| `game/scripts/combat_audio.gd:128` | `dynamic-resource` | `res://assets/sfx/combat/*` / 후보 596개 |
| `game/scripts/combat_audio.gd:178` | `dynamic-resource` | `res://assets/sfx/combat/*` / 후보 596개 |
| `game/scripts/combat_audio.gd:273` | `dynamic-resource` | `res://assets/sfx/combat/heartbeat_loop.wav` / 후보 1개 |
| `game/scripts/combat_audio.gd:319` | `dynamic-resource` | `res://assets/sfx/combat/campfire_loop.wav` / 후보 1개 |
| `game/scripts/controller_profile.gd:30` | `dynamic-input-action` | `InputMap.has_action` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/controller_profile.gd:31` | `dynamic-input-action` | `InputMap.add_action` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/controller_profile.gd:34` | `dynamic-input-action` | `InputMap.action_add_event` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/creature_audio.gd:199` | `dynamic-resource` | `res://assets/sfx/creatures/layer_*_*` / 후보 60개 |
| `game/scripts/creature_audio.gd:219` | `dynamic-resource` | `res://assets/sfx/creatures/step_*` / 후보 76개 |
| `game/scripts/creature_audio.gd:241` | `dynamic-resource` | `res://assets/sfx/creatures/*_*` / 후보 2374개 |
| `game/scripts/creature_audio.gd:273` | `dynamic-resource` | `res://assets/sfx/creatures/*_*` / 후보 2374개 |
| `game/scripts/creature_audio.gd:274` | `dynamic-resource` | `res://assets/sfx/creatures/*` / 후보 2374개 |
| `game/scripts/creature_audio.gd:275` | `dynamic-resource` | `res://assets/sfx/creatures/*_*_forest` / 후보 0개 |
| `game/scripts/creature_audio.gd:297` | `dynamic-resource` | `res://assets/sfx/creatures/step_*` / 후보 76개 |
| `game/scripts/creature_audio.gd:299` | `dynamic-resource` | `res://assets/sfx/creatures/layer_*_*` / 후보 60개 |
| `game/scripts/field_objects.gd:24` | `dynamic-resource` | `res://assets/sfx/field/*.wav` / 후보 174개 |
| `game/scripts/field_objects.gd:321` | `dynamic-resource` | `res://assets/sfx/field/*.wav` / 후보 174개 |
| `game/scripts/field_objects.gd:1456` | `dynamic-resource` | `res://assets/sfx/field/*.wav` / 후보 174개 |
| `game/scripts/game_settings.gd:517` | `dynamic-input-action` | `InputMap.add_action` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/game_settings.gd:517` | `dynamic-input-action` | `InputMap.has_action` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/game_settings.gd:518` | `dynamic-input-action` | `InputMap.action_get_events` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/game_settings.gd:519` | `dynamic-input-action` | `InputMap.action_erase_event` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/game_settings.gd:524` | `dynamic-input-action` | `InputMap.action_add_event` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/hero_voice.gd:65` | `dynamic-resource` | `res://assets/sfx/hero/*` / 후보 168개 |
| `game/scripts/hero_voice.gd:93` | `dynamic-resource` | `res://assets/sfx/hero/*` / 후보 168개 |
| `game/scripts/interiors.gd:1259` | `dynamic-resource` | `res://assets/interior/*.glb` / 후보 0개 |
| `game/scripts/interiors.gd:1260` | `dynamic-resource` | `res://assets/interior/*` / 후보 1개 |
| `game/scripts/interiors.gd:1276` | `dynamic-resource` | `res://assets/interior/*.glb` / 후보 0개 |
| `game/scripts/interiors.gd:1278` | `dynamic-resource` | `res://assets/interior/*.glb` / 후보 0개 |
| `game/scripts/interiors.gd:1279` | `dynamic-resource` | `res://maps/archipelago/assets/environment/*.glb` / 후보 0개 |
| `game/scripts/interiors.gd:1280` | `dynamic-resource` | `res://maps/archipelago/assets/environment/*.glb` / 후보 0개 |
| `game/scripts/interiors.gd:2794` | `dynamic-resource` | `res://assets/portraits/*.png` / 후보 0개 |
| `game/scripts/interiors.gd:2795` | `dynamic-resource` | `res://assets/ui/day_*.png` / 후보 17개 |
| `game/scripts/interiors.gd:2796` | `dynamic-resource` | `res://assets/ui/shadow_*.png` / 후보 15개 |
| `game/scripts/main.gd:1265` | `dynamic-resource` | `res://assets/ui/*` / 후보 508개 |
| `game/scripts/main.gd:1335` | `dynamic-resource` | `res://assets/ui/icons/*.png` / 후보 43개 |
| `game/scripts/main.gd:2104` | `dynamic-resource` | `res://assets/items/*.svg` / 후보 15개 |
| `game/scripts/main.gd:2148` | `dynamic-resource` | `res://assets/items/*.svg` / 후보 15개 |
| `game/scripts/main.gd:2971` | `dynamic-resource` | `res://assets/ui/portrait_*.png` / 후보 4개 |
| `game/scripts/main.gd:3802` | `dynamic-resource` | `res://assets/portraits/*.png` / 후보 0개 |
| `game/scripts/monster.gd:45` | `dynamic-resource` | `res://assets/monsters/*_*.glb` / 후보 0개 |
| `game/scripts/npc.gd:44` | `dynamic-resource` | `res://assets/npc/*.glb` / 후보 0개 |
| `game/scripts/npc.gd:48` | `dynamic-resource` | `res://assets/npc/*.glb` / 후보 0개 |
| `game/scripts/npc.gd:51` | `dynamic-resource` | `res://assets/npc/*.glb` / 후보 0개 |
| `game/scripts/npc_gifts.gd:170` | `dynamic-resource` | `res://assets/items/*.svg` / 후보 15개 |
| `game/scripts/painter/paint_widgets.gd:12` | `dynamic-resource` | `res://assets/ui/painter/*.svg` / 후보 29개 |
| `game/scripts/painter/paint_widgets.gd:27` | `dynamic-resource` | `res://assets/ui/painter/*.svg` / 후보 29개 |
| `game/scripts/painter/paint_widgets.gd:351` | `dynamic-resource` | `res://assets/ui/painter/*.svg` / 후보 29개 |
| `game/scripts/painter/paint_widgets.gd:360` | `dynamic-resource` | `res://assets/ui/painter/*.svg` / 후보 29개 |
| `game/scripts/player.gd:157` | `dynamic-resource` | `res://assets/*.glb` / 후보 24개 |
| `game/scripts/player.gd:266` | `dynamic-resource` | `res://assets/authored_*_v1.glb` / 후보 2개 |
| `game/scripts/rpg_ui.gd:174` | `dynamic-resource` | `res://assets/ui/frames/*.png` / 후보 81개 |
| `game/scripts/rpg_ui.gd:207` | `dynamic-resource` | `res://assets/ui/*.svg` / 후보 52개 |
| `game/scripts/rpg_ui.gd:213` | `dynamic-resource` | `res://assets/ui/icons/*.png` / 후보 43개 |
| `game/scripts/rpg_ui.gd:1059` | `dynamic-resource` | `res://assets/ui/portrait_*.png` / 후보 4개 |
| `game/scripts/sfx_bank.gd:137` | `dynamic-resource` | `res://assets/sfx/*` / 후보 6996개 |
| `game/scripts/shadow_folk.gd:603` | `dynamic-resource` | `res://assets/ui/day_*.png` / 후보 17개 |
| `game/scripts/shadow_folk.gd:603` | `dynamic-resource` | `res://assets/ui/shadow_*.png` / 후보 15개 |
| `game/scripts/sound.gd:117` | `dynamic-resource` | `res://assets/audio/*.*` / 후보 10개 |
| `game/scripts/story.gd:474` | `dynamic-resource` | `res://assets/ui/day_*.png` / 후보 17개 |
| `game/scripts/story.gd:474` | `dynamic-resource` | `res://assets/ui/shadow_*.png` / 후보 15개 |
| `game/scripts/story.gd:850` | `dynamic-resource` | `res://assets/ui/day_*.png` / 후보 17개 |
| `game/scripts/story.gd:850` | `dynamic-resource` | `res://assets/ui/shadow_*.png` / 후보 15개 |
| `game/scripts/story_forest.gd:138` | `dynamic-resource` | `res://assets/ui/day_*.png` / 후보 17개 |
| `game/scripts/story_forest.gd:138` | `dynamic-resource` | `res://assets/ui/shadow_*.png` / 후보 15개 |
| `game/scripts/studio.gd:454` | `dynamic-resource` | `res://assets/ui/portrait_*.png` / 후보 4개 |
| `game/scripts/studio.gd:1102` | `dynamic-resource` | `res://assets/items/*.svg` / 후보 15개 |
| `game/scripts/transition.gd:418` | `dynamic-resource` | `res://assets/sfx/doors/*_*.wav` / 후보 120개 |
| `game/scripts/transition.gd:440` | `dynamic-resource` | `res://assets/sfx/doors/*_*.wav` / 후보 120개 |
| `game/scripts/village.gd:28` | `dynamic-input-action` | `InputMap.has_action` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/village.gd:29` | `dynamic-input-action` | `InputMap.add_action` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/village.gd:33` | `dynamic-input-action` | `InputMap.action_add_event` / 동적 액션 이름을 [input]과 대조 |
| `game/scripts/voice_babble.gd:244` | `dynamic-resource` | `res://assets/sfx/voice/*.wav` / 후보 217개 |
| `game/scripts/voice_babble.gd:255` | `dynamic-resource` | `res://assets/sfx/voice/*` / 후보 434개 |
| `game/scripts/voice_babble.gd:256` | `dynamic-resource` | `res://assets/sfx/voice/*.wav` / 후보 217개 |
| `game/scripts/voice_babble.gd:331` | `dynamic-resource` | `res://assets/sfx/voice/quill` / 후보 0개 |
| `game/scripts/voice_babble.gd:488` | `dynamic-resource` | `res://assets/sfx/voice/quill` / 후보 0개 |
| `game/scripts/voice_babble.gd:502` | `dynamic-resource` | `res://assets/sfx/voice/greet_*` / 후보 48개 |
| `game/scripts/voice_babble.gd:532` | `dynamic-resource` | `res://assets/sfx/voice/emote_*_*` / 후보 240개 |
| `game/scripts/world_audio.gd:159` | `dynamic-resource` | `res://assets/sfx/ambience/birds.wav` / 후보 1개 |
| `game/scripts/world_audio.gd:550` | `dynamic-resource` | `res://assets/sfx/ambience/*.wav` / 후보 103개 |
| `game/scripts/world_audio.gd:577` | `dynamic-resource` | `res://assets/sfx/ambience/*.wav` / 후보 103개 |
| `game/tests/admin_tour.gd:10` | `dynamic-resource` | `res://../artifacts/admin-*.png` / 후보 0개 |
| `game/tests/archipelago_probe.gd:92` | `dynamic-resource` | `res://../artifacts/island-shot-*.png` / 후보 0개 |
| `game/tests/archipelago_probe.gd:116` | `dynamic-resource` | `res://../artifacts/island-top-*.png` / 후보 0개 |
| `game/tests/archipelago_probe.gd:149` | `dynamic-resource` | `res://../artifacts/island-view-*.png` / 후보 0개 |
| `game/tests/audio_bank_check.gd:83` | `dynamic-resource` | `res://assets/sfx/*/` / 후보 6996개 |
| `game/tests/audio_check.gd:114` | `dynamic-resource` | `res://assets/sfx/steps/*_*_` / 후보 0개 |
| `game/tests/avatar_rooms_check.gd:19` | `dynamic-resource` | `res://../artifacts/avatar-*.png` / 후보 0개 |
| `game/tests/bed_wake_check.gd:12` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/build_mode_room.gd:20` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/build_mode_village.gd:22` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/building_holes.gd:117` | `dynamic-resource` | `res://../artifacts/holes-*-*.png` / 후보 0개 |
| `game/tests/chat_box_check.gd:49` | `dynamic-resource` | `res://../artifacts/chat-*.png` / 후보 0개 |
| `game/tests/craft_live.gd:24` | `dynamic-resource` | `res://../artifacts/craft-live-*.png` / 후보 0개 |
| `game/tests/craft_panel_check.gd:24` | `dynamic-resource` | `res://../artifacts/craft-panel-*.png` / 후보 0개 |
| `game/tests/daylight_check.gd:34` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/demo_keys.gd:41` | `dynamic-resource` | `res://../artifacts/demo-keys-*-*.png` / 후보 0개 |
| `game/tests/design_preview.gd:35` | `dynamic-resource` | `res://../artifacts/design-preview-*.png` / 후보 0개 |
| `game/tests/expanded_motion.gd:13` | `dynamic-resource` | `res://../artifacts/*.png` / 후보 0개 |
| `game/tests/expansion.gd:13` | `dynamic-resource` | `res://../artifacts/*.png` / 후보 0개 |
| `game/tests/expedition_ui_check.gd:27` | `dynamic-resource` | `res://../artifacts/exp-*.png` / 후보 0개 |
| `game/tests/exterior_views.gd:105` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/field_objects_check.gd:314` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/fishing_shapes_check.gd:177` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/font_shots.gd:57` | `dynamic-resource` | `res://../artifacts/font-*.png` / 후보 0개 |
| `game/tests/foot_fx_village.gd:89` | `dynamic-resource` | `res://../artifacts/foot_fx_*.png` / 후보 0개 |
| `game/tests/furniture_showcase.gd:49` | `dynamic-resource` | `res://../artifacts/*-review-frames` / 후보 0개 |
| `game/tests/furniture_showcase.gd:61` | `dynamic-resource` | `res://../artifacts/*-showcase.png` / 후보 0개 |
| `game/tests/guide_tour.gd:29` | `dynamic-resource` | `res://../artifacts/guide-**.png` / 후보 0개 |
| `game/tests/home_access_ui.gd:48` | `dynamic-resource` | `res://../artifacts/home_access_*.png` / 후보 0개 |
| `game/tests/home_roundtrip.gd:9` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/hud_fold_tour.gd:26` | `dynamic-resource` | `res://../artifacts/hud-fold-*.png` / 후보 0개 |
| `game/tests/inspect_placed.gd:27` | `dynamic-resource` | `res://../artifacts/placed-*.png` / 후보 0개 |
| `game/tests/integration.gd:19` | `dynamic-resource` | `res://../artifacts/*.png` / 후보 0개 |
| `game/tests/island_walk.gd:27` | `dynamic-resource` | `res://../artifacts/island-walk-*.png` / 후보 0개 |
| `game/tests/landmark_review.gd:10` | `dynamic-resource` | `res://../artifacts/*.png` / 후보 0개 |
| `game/tests/life_loop.gd:105` | `dynamic-resource` | `res://../artifacts/life-*.png` / 후보 0개 |
| `game/tests/life_sound_check.gd:78` | `dynamic-resource` | `res://assets/sfx/life/*_` / 후보 0개 |
| `game/tests/life_sound_check.gd:121` | `dynamic-resource` | `res://assets/sfx/core/*_` / 후보 0개 |
| `game/tests/living_objects_check.gd:160` | `dynamic-resource` | `res://../artifacts/clock-hands-*.jpg` / 후보 0개 |
| `game/tests/model_gallery.gd:18` | `dynamic-resource` | `res://../artifacts/*.json` / 후보 0개 |
| `game/tests/model_gallery.gd:34` | `dynamic-resource` | `res://../artifacts/*-frames` / 후보 0개 |
| `game/tests/model_gallery.gd:53` | `dynamic-resource` | `res://../artifacts/*.png` / 후보 0개 |
| `game/tests/multiplayer.gd:30` | `dynamic-resource` | `res://../artifacts/multiplayer-*.png` / 후보 0개 |
| `game/tests/npc_dialogue.gd:13` | `dynamic-resource` | `res://../artifacts/npc-*.png` / 후보 0개 |
| `game/tests/npc_gift_check.gd:75` | `dynamic-resource` | `res://../artifacts/npc-gift-*.png` / 후보 0개 |
| `game/tests/object_transform_check.gd:23` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/occluder_check.gd:72` | `dynamic-resource` | `res://../artifacts/occluder-*.png` / 후보 0개 |
| `game/tests/open_structures.gd:48` | `dynamic-resource` | `res://../artifacts/open-*.png` / 후보 0개 |
| `game/tests/peer_door_check.gd:21` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/picture_furniture.gd:38` | `dynamic-resource` | `res://../artifacts/picture-furniture-20261002/render-input.json` / 후보 0개 |
| `game/tests/picture_furniture.gd:49` | `dynamic-resource` | `res://../artifacts/picture-furniture-20261002/public/*.png` / 후보 0개 |
| `game/tests/picture_furniture.gd:54` | `dynamic-resource` | `res://../artifacts/picture-furniture-20261002/reference.jpg` / 후보 0개 |
| `game/tests/picture_furniture.gd:64` | `dynamic-resource` | `res://../artifacts/picture-furniture-20261002/frames` / 후보 0개 |
| `game/tests/picture_furniture.gd:71` | `dynamic-resource` | `res://../artifacts/picture-furniture-20261002/frames/frame_*.jpg` / 후보 0개 |
| `game/tests/picture_furniture.gd:72` | `dynamic-resource` | `res://../artifacts/picture-furniture-20261002/public/*.png` / 후보 0개 |
| `game/tests/presentation.gd:11` | `dynamic-resource` | `res://../artifacts/*.png` / 후보 0개 |
| `game/tests/quest_e2e.gd:46` | `dynamic-resource` | `res://../artifacts/quest-shot-*-*.png` / 후보 0개 |
| `game/tests/render_portraits.gd:55` | `dynamic-resource` | `res://assets/ui/portrait_*.png` / 후보 4개 |
| `game/tests/residents_walk.gd:258` | `dynamic-resource` | `res://../artifacts/residents-*.png` / 후보 0개 |
| `game/tests/room_door_check.gd:12` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/settings_check.gd:93` | `dynamic-input-action` | `InputMap.has_action` / 동적 액션 이름을 [input]과 대조 |
| `game/tests/settings_check.gd:95` | `dynamic-input-action` | `InputMap.action_get_events` / 동적 액션 이름을 [input]과 대조 |
| `game/tests/settings_check.gd:284` | `dynamic-input-action` | `InputMap.action_get_events` / 동적 액션 이름을 [input]과 대조 |
| `game/tests/seven_days.gd:19` | `dynamic-resource` | `res://../artifacts/*.png` / 후보 0개 |
| `game/tests/sfx_bank_check.gd:123` | `dynamic-resource` | `res://assets/sfx/combat/hit_flesh_1.wav` / 후보 1개 |
| `game/tests/sfx_bank_check.gd:126` | `dynamic-resource` | `res://assets/sfx/combat/hit_flesh_*.wav` / 후보 13개 |
| `game/tests/sfx_bank_check.gd:130` | `dynamic-resource` | `res://assets/sfx/combat/hit_flesh.wav` / 후보 0개 |
| `game/tests/sfx_bank_check.gd:134` | `dynamic-resource` | `res://assets/sfx/ui/hover.wav` / 후보 1개 |
| `game/tests/sfx_bank_check.gd:134` | `dynamic-resource` | `res://assets/sfx/ui/hover_1.wav` / 후보 1개 |
| `game/tests/sfx_bank_check.gd:137` | `dynamic-resource` | `res://assets/sfx/*` / 후보 6996개 |
| `game/tests/sfx_bank_check.gd:144` | `dynamic-resource` | `res://assets/sfx/` / 후보 0개 |
| `game/tests/sfx_bank_check.gd:168` | `dynamic-resource` | `res://assets/sfx/` / 후보 0개 |
| `game/tests/sfx_bank_check.gd:234` | `dynamic-resource` | `res://assets/sfx/ui/__no_such_family__.wav` / 후보 0개 |
| `game/tests/shadow_folk_capture.gd:26` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/shadow_probe.gd:57` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/shadow_still_check.gd:124` | `dynamic-resource` | `res://../artifacts/shadow-still-*.png` / 후보 0개 |
| `game/tests/story_chapter.gd:49` | `dynamic-resource` | `res://../artifacts/story-shot-*-*.png` / 후보 0개 |
| `game/tests/survival_maps.gd:38` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/title_art_check.gd:33` | `dynamic-resource` | `res://../artifacts/title-*.png` / 후보 0개 |
| `game/tests/tooltip_tour.gd:25` | `dynamic-resource` | `res://../artifacts/tooltip-*.png` / 후보 0개 |
| `game/tests/town_review.gd:7` | `dynamic-resource` | `res://../artifacts/*.png` / 후보 0개 |
| `game/tests/treasure_check.gd:42` | `dynamic-resource` | `res://../artifacts/treasure-shot-*-*.png` / 후보 0개 |
| `game/tests/treasure_spots.gd:349` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/tree_drops.gd:30` | `dynamic-resource` | `res://../artifacts/*.png` / 후보 0개 |
| `game/tests/ui0118_shots.gd:27` | `dynamic-resource` | `res://../artifacts/ui0118-*.png` / 후보 0개 |
| `game/tests/ui_bubble_shot.gd:25` | `dynamic-resource` | `res://../artifacts/bubble-*.png` / 후보 0개 |
| `game/tests/ui_consistency_check.gd:153` | `dynamic-resource` | `res://scripts/*` / 후보 215개 |
| `game/tests/ui_gallery.gd:35` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
| `game/tests/ui_sfx_check.gd:46` | `dynamic-resource` | `res://assets/sfx/ui/*.wav` / 후보 355개 |
| `game/tests/ui_tour.gd:24` | `dynamic-resource` | `res://../artifacts/ui-*.png` / 후보 0개 |
| `game/tests/version_gate_check.gd:51` | `dynamic-resource` | `res://../artifacts/version-gate-*.png` / 후보 0개 |
| `game/tests/village_doors_check.gd:27` | `dynamic-resource` | `res://../artifacts/village_doors_*.png` / 후보 0개 |
| `game/tests/village_life.gd:14` | `dynamic-resource` | `res://../artifacts/*.png` / 후보 0개 |
| `game/tests/voice_variety_check.gd:62` | `dynamic-resource` | `res://assets/sfx/voice/*` / 후보 434개 |
| `game/tests/voice_variety_check.gd:91` | `dynamic-resource` | `res://assets/sfx/voice/emote_*_*` / 후보 240개 |
| `game/tests/voice_variety_check.gd:94` | `dynamic-resource` | `res://assets/sfx/voice/greet_*` / 후보 48개 |
| `game/tests/voice_variety_check.gd:97` | `dynamic-resource` | `res://assets/sfx/voice/quill` / 후보 0개 |
| `game/tests/wardrobe_check.gd:13` | `dynamic-resource` | `res://../artifacts/wardrobe-*.png` / 후보 0개 |
| `game/tests/world_polish_capture.gd:41` | `dynamic-resource` | `res://../artifacts/*` / 후보 0개 |
