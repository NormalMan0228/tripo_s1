# 문 훅 API (집·문·방문 세션용, MAP 제공)

브랜치 `wt/mapdoor-1`. 문 여닫기(32번), 문 열고 들어오기(49번), 자연스럽게 나가기(51번)에 쓰는 훅입니다.
애니메이션은 넣지 않았습니다. 값만 바꾸는 함수이므로 부르는 쪽에서 트윈하거나 노드를 직접 돌립니다.

## 0. 문을 만드는 방식 (사용자 지시 반영)
- 건물 GLB의 원래 메시에서 문이 그려진 면을 그대로 복사해 문짝을 만듭니다. 새 상자는 쓰지 않습니다.
  모양, UV, 텍스처는 원래 문과 같습니다.
- 문짝은 안쪽으로 6 cm 두께를 줍니다. 뒷면은 같은 면을 뒤집은 것이고, 옆면은 문 가장자리 색입니다.
- 문이 열리면 원래 문 자리에 어두운 문간 면(`DoorOpening`)이 보입니다. 닫혀 있을 때는 문짝 뒤에 가려집니다.
- **바깥 문과 실내 문은 같은 메시**입니다. 크기, 경첩 쪽, 여는 방향이 같고, 방 안에서는 같은 문의 뒷면이 보입니다.
- 문 리소스는 건물 모델마다 하나씩 있습니다: `game/maps/archipelago/doors/<모델>.res`(문짝),
  `<모델>_opening.res`(문간). 표는 `door_leaves.json`(문 id → 모델, 리소스, 벽 기준 위치)이고,
  같은 모델을 쓰는 건물은 같은 리소스를 씁니다.
- **0.11.8에는 훅만 들어갑니다. 켜진 문이 없습니다**(`building_doors.gd`의 `ENABLED = []`). 게임 화면은 지금과 같고,
  `door_leaf(id)`·`door_opening(id)`는 `null`, `door_ids()`는 빈 목록, 실내 `FrontDoor`는 지금의 반높이 문(108° 열림)입니다.
  사용자가 문 윤곽을 직접 그리면 그 윤곽대로 잘라 문짝을 만든 뒤 켭니다. 그때 노드 이름, 경첩 축, 각도는 아래 표와 같습니다.

## 1. N3 `register(id, node, hinge_axis, open_angle)`에 넣을 값

| 항목 | 바깥 문 | 실내 문 |
|---|---|---|
| 노드 | `Buildings/<id>/DoorFrame/DoorLeaf` (맵 기준. 예: `Buildings/10_red_house/DoorFrame/DoorLeaf`) | 방 1층 루트 아래 `FrontDoor` |
| 찾는 함수 | `BuildingDoors.door_leaf(id)` | `Interiors.front_door(root)` |
| 경첩 축 | 노드 로컬 **+Y** | 노드 로컬 **+Y** |
| 경첩 위치 | 노드 원점 = 밖에서 볼 때 문의 **오른쪽** 세로 모서리, 문턱 높이. 벽 방향은 부모 `DoorFrame`이 가집니다 | 노드 원점 = 같은 쪽(오른쪽) 모서리, 바닥 |
| 닫힌 상태 회전 | `rotation.y = 0` | `rotation.y = 0` |
| 여는 방향 | **바깥쪽**(+각도) | **바깥쪽**(+각도), 바깥 문과 같습니다 |
| 열린 각도 | `+108°` (`BuildingDoors.OPEN_DEGREES`) | `+108°` (`Interiors.FRONT_DOOR_OPEN_DEGREES`, 기본값은 열림) |

- 노드를 직접 돌려도 되고, `set_door_open(id, 0..1)` / `set_front_door_open(root, 0..1)`을 써도 됩니다.
- 문짝 메시는 노드의 자식 `Mesh`(MeshInstance3D)입니다. 문짝은 경첩에서 로컬 **-X** 방향으로 뻗어 있습니다.
- 집이 바깥 문을 안쪽으로 여는 구조는 아닙니다. 건물 셸 안이 비어 있어서 안쪽으로 열면 문이 벽 속으로 사라지므로 바깥쪽으로 엽니다.

## 2. 마을 건물 바깥 문: `game/maps/archipelago/building_doors.gd`

`const BuildingDoors = preload("res://maps/archipelago/building_doors.gd")` 뒤에 정적 함수로 씁니다.

| 함수 | 반환 | 설명 |
|---|---|---|
| `BuildingDoors.door_ids()` | `PackedStringArray` | 지금 맵에 설치된 문 id(테스트 중에는 `10_red_house`만) |
| `BuildingDoors.door_leaf(id)` | `Node3D` | 경첩(`DoorFrame/DoorLeaf`) |
| `BuildingDoors.door_opening(id)` | `MeshInstance3D` | 어두운 문간(`DoorFrame/DoorOpening`). `material_override`에 `inner_light`(0..1)가 있습니다 |
| `BuildingDoors.set_door_open(id, amount)` | - | 0 = 닫힘, 1 = 108° 열림. 즉시 적용됩니다 |
| `BuildingDoors.door_open(id)` | `float` | 지금 열린 정도 |
| `BuildingDoors.leaf_mesh(id)` / `opening_mesh(id)` | `ArrayMesh` | 문 리소스 |
| `BuildingDoors.leaf_size(id)` | `Vector3` | 문 너비, 높이, 두께(m) |

- **문 id**: `Town.DOORS`의 id입니다. room 이름으로 찾을 때는 `Town.door_for(room).id`를 씁니다(예: `"home"` → `"10_red_house"`).
- **충돌 없음**: 문짝과 문간에는 콜리전이 없습니다. 걷는 길, 맵 좌표, 문 앞 지점은 그대로입니다.
- **설치 시점**: 마을 모듈 `building_dressing.gd`의 `dress()`가 건물 재질을 바꾸기 직전에 설치합니다(베이크 섬과 런타임 빌드 모두).
  그래서 문짝도 건물과 같은 외벽 셰이더(밤 창문빛, 가림 페이드)로 그려집니다.

### 트윈 예시
```gdscript
var id := Town.door_for("home").id
var t := create_tween()
t.tween_method(func(v: float): BuildingDoors.set_door_open(id, v), 0.0, 1.0, 0.35).set_trans(Tween.TRANS_SINE)
t.tween_interval(0.6)
t.tween_method(func(v: float): BuildingDoors.set_door_open(id, v), 1.0, 0.0, 0.3)
```

### 안쪽 밝기 그라데이션 (32번)
```gdscript
var opening := BuildingDoors.door_opening(id)
if opening:
    var mat := opening.material_override as ShaderMaterial
    create_tween().tween_property(mat, "shader_parameter/inner_light", clampf(people_inside / 3.0, 0.0, 1.0), 0.5)
```
- `inner_light` 0은 어두운 문간이고, 1은 안쪽 방 불빛입니다. 바닥과 가운데가 가장 밝습니다.
- 색은 `light_color`, `dark_color`로 바꿉니다. 셰이더는 `building_doors.gd`의 `OPENING_SHADER`입니다. 머티리얼은 문마다 따로 있습니다.

## 3. 실내 앞문: `game/scripts/interiors.gd`

| 함수 | 설명 |
|---|---|
| `Interiors.front_door(root)` | `front()`가 만든 `FrontDoor` 경첩을 돌려줍니다. 문이 없는 층이면 `null`입니다 |
| `Interiors.set_front_door_open(root, amount)` | 0 = 닫힘, 1 = 108° 바깥으로 열림 |

- 문이 켜진 건물(지금은 나의 집)은 `FrontDoor` 아래 `Mesh`가 바깥 문과 **같은 문짝 리소스**입니다. 실제 크기 그대로이고, 문간 가운데에 섭니다.
  `FrontDoor`에는 `door_leaf` 메타(건물 id)가 붙습니다. 다른 방은 지금의 반높이 문을 그대로 씁니다.
- 기본 모습은 지금과 같은 **108° 열림**입니다.

## 4. 전체 적용과 다시 만들기
- **문 리소스 다시 만들기**: 저장소 루트 폴더(예: `D:\lsm26\wt\map`, 병합한 작업 폴더의 루트)에서 실행합니다.
  ```
  powershell -ExecutionPolicy Bypass -File D:\lsm26\locks\wait_heavy.ps1
  .tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://../tools/door_leaves.gd
  ```
  - 끝에 `DOOR_LEAVES doors=<문 개수> ms=<걸린 시간>`이 찍히면 성공입니다(14개 기준 약 14초). 문마다 `DOOR_LEAF <id> ...` 줄이 나옵니다.
  - 결과물은 **git에 커밋하는 파일**입니다(베이크의 git-ignored `generated/`가 아닙니다). 베이크(`tools/bake_archipelago.py`)나
    패키징이 다시 만들지 않으므로, 실행한 뒤 아래 파일을 커밋합니다.
    - `game/maps/archipelago/door_leaves.json` (문 id → 모델, 리소스, 벽 기준 위치)
    - `game/maps/archipelago/doors/<모델>.res`, `<모델>_opening.res` (문짝, 문간)
  - `Town.DOORS`의 모든 항목을 자동으로 처리합니다. 건물 GLB, 배치(`building_placements.json`), `Town.DOORS`가 바뀌면 다시 실행합니다.
    **wt/mapinterior(`18_meadow_house`)를 병합한 뒤 한 번 실행해야 `building_doors_check`가 통과합니다.**
  - 확인: `.tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://tests/building_doors_check.gd`
    → `BUILDING_DOORS_CHECK {... "passed":true}`.
  - 맵 베이크(`island.scn`)에는 영향이 없습니다. 문은 마을 모듈이 실행 중에 붙이므로 다시 베이크할 필요가 없습니다.
- 모든 문에 적용: `building_doors.gd`의 `ALL_DOORS := true`(지금은 `ENABLED = ["10_red_house"]`만).
- 칠한 색으로 문을 못 찾는 문은 `RECT_OVERRIDES`에 직접 적습니다(카페, 천문대, 온실, 공방, 잡화점). 새 건물도 칠한 문을 못 찾으면
  1.0 x 2.1 m 기본 문간으로 만들고 `no door paint found` 줄을 찍습니다. 그때는 `RECT_OVERRIDES`에 윤곽을 적습니다.

## 4-1. 사용자 외곽선으로 자르기 (`tools/door_cutter.gd`, 사용자가 그린 윤곽용)
- 입력: `artifacts/outline_tool/renders/<모델>__<면>.json`(렌더 정보: `origin_tl`, `u`, `v`, `view_dir`, `mpp`, 모델 좌표)과
  `artifacts/outline_tool/outlines/<render_id>.json`(`polys: [{kind: door|window, hinge: left|right, pts: [[px,py],...]}]`).
- 실행(저장소 루트):
  ```
  powershell -ExecutionPolicy Bypass -File D:\lsm26\locks\wait_heavy.ps1
  .tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://../tools/door_cutter.gd
  ```
  (`-- --only=red_house__front`로 한 렌더만, `-- --renders=DIR --outlines=DIR`로 다른 폴더를 씁니다.)
  `artifacts/outline_tool/merged`가 있으면 그것을 기본으로 씁니다(사용자 문·창 윤곽 + 자동 창 + 뚫린 구멍,
  `tools/window_panes.py`가 만듦). 윤곽을 새로 그렸으면 먼저 `.tools\art-venv\Scripts\python.exe tools/window_panes.py`를 실행합니다.
  merged 없이 사용자 윤곽만으로 자르면 창 유리(`windows/*_glass.res`)가 사용자가 그린 창만으로 줄어듭니다.
- 문(`door`): 윤곽 안에서 카메라가 보는 모든 면을 윤곽선을 따라 삼각형째 잘라 문짝으로 가져갑니다. 윤곽 밖 조각은 건물에 남습니다.
  결과는 `doors/<모델>.res`(6 cm 두께 문짝), `<모델>_opening.res`(문간), `<모델>_cut.res`(건물에 남는 조각)이고,
  `door_leaves.json`에 `frame`, `hinge`, `drop`(건물에서 뺄 삼각형)이 들어갑니다. 실행하면 `DOOR_CUT <render_id> door {...}` 줄의
  `left_m2`(잘린 뒤 윤곽 안에 남아 보이는 건물 면적)가 **0**이어야 합니다.
- 게임에서는 `building_doors.gd`가 켜진 문의 건물 렌더 메시에서 `drop` 삼각형을 빼고 `_cut.res` 조각을 붙입니다(콜리전은 그대로).
  그래서 문을 열면 벽에 문 자국이 남지 않고 문간만 보입니다.
- 경첩: 윤곽의 `hinge`가 `right`(기본)든 `left`든 **약속은 같습니다**: `DoorFrame/DoorLeaf`는 닫힘 0, 로컬 +Y 축,
  바깥쪽 열림이 **양수**(+108°)입니다. 왼쪽 경첩 문은 `DoorFrame`이 뒤집혀(로컬 +Y가 아래) 있어서 같은 값으로 바깥쪽으로 열립니다.
  실내도 같아서, 왼쪽 경첩 방은 `FrontDoorMount`(z축으로 뒤집힌 받침) 아래에 `FrontDoor`가 있고 `rotation.y` 0↔108°로 바깥쪽으로 열립니다.
  `BuildingDoors.hinge_side(id)`가 `"right"`/`"left"`를 돌려줍니다.
- 창문(`window`): 윤곽 안에서 카메라를 향한 앞 표면(60° 이내)만 `windows/<모델>_glass.res`로 모읍니다. 뚫린 구멍(`hole`)은
  둘레 벽 깊이에 벽 재질 판(`hole` 표면)으로 막습니다. 게임에서는 `scripts/window_glass.gd`가 켜져 있습니다(9번 창문).
- 적용: 결과를 커밋하고 `building_doors.gd`의 `ENABLED`에 건물 id를 넣거나 `ALL_DOORS := true`로 켭니다.

## 4-2. 사용자 윤곽 문: 경첩·양문·여는 방향 (2026-10-16 새벽 사용자 지시)
- 사용자가 그린 문 윤곽(현재 정면 10개: 카페, 온실, 천문대, 주황 지붕 오두막, 나의 집, 잡화점, 씨앗 가게, 목조 주택, 공방, 풍차)을
  `tools/door_cutter.gd`가 그대로 잘라 씁니다. 윤곽에 적힌 hinge 값은 쓰지 않고 자동으로 정합니다.
  - 겹치거나 맞닿은 윤곽은 한 문간으로 합칩니다. 윤곽이 두 개면 그 경계로 나눈 양문, 하나인데 폭이 1.6 m 이상이거나
    폭/높이가 0.9 이상이면 가운데를 나눈 양문입니다. 양문의 경첩은 바깥 양끝입니다.
  - 한 장짜리 문은 렌더에서 손잡이(어두운 쇠, 회색 금속, 놋쇠)가 보이는 쪽의 반대편에 경첩을 답니다. 손잡이가 안 보이면
    건물 끝(벽)이 더 가까운 쪽에 답니다.
  - **문은 안쪽으로 열립니다.** 바깥에서는 문간 뒤 어두운 공간(`DoorOpening`, 문짝 폭만큼 깊은 상자) 안으로 문짝이 들어가는 모습이 보입니다.
  - 결정은 `game/maps/archipelago/door_hinges.json`에 남습니다:
    `{건물 id: {leaves: [{hinge: "left"|"right", reason: "double"|"handle"|"wall"|"user"}], opens: "in"|"out"}}`.
    사용자가 바꾸려면 그 항목에 `"override": true`를 넣고 `hinge`/`opens`를 고친 뒤 커터를 다시 실행합니다.
- **N3 쪽 사용법(변경 없음)**: `BuildingDoors.set_door_open(id, 0..1)`과 `Interiors.set_front_door_open(root, 0..1)`만 부르면 됩니다.
  두 함수가 경첩 쪽, 양문(두 장 모두), 여는 방향(0..1 → 0..108°를 맞는 방향으로)을 모두 처리합니다.
  `door_leaf(id)`는 첫 문짝(`DoorFrame/DoorLeaf`)을 돌려주므로 켜진 문이면 null이 아닙니다.
- 노드 이름: 바깥 `Buildings/<id>/DoorFrame`(벽 기준 프레임) 아래 `DoorLeaf`, 양문이면 `DoorLeaf2`(각 경첩 위치, 자식 `Mesh`),
  `DoorOpening`(어두운 문간 상자, `inner_light`). 실내는 `FrontDoor`, 양문이면 `FrontDoor2`(원점=경첩, 같은 문짝 리소스).
  각 문짝 노드의 `sign` 메타(+1/-1)가 여는 방향입니다.
- 실내 문간은 문 폭에 맞춰 넓어집니다(`doorway_half`). 안쪽으로 열린 실내 문이 가구와 부딪히는지는 아직 검사하지 않습니다.
- 아직 안 그린 4채(보라 지붕 집, 파란 집, 파란 지붕 오두막, 등대)는 예전 자동 윤곽 데이터라 `ALL_DOORS`를 켜면 덧댄 문짝이 됩니다.
  다 그린 뒤 커터를 다시 실행하면 같은 방식이 됩니다.

## 4-3. 문 v2/v3 (2026-10-16 오전, 사용자 지시)
- 문짝은 잘라낸 면이 아니라 **새 판**입니다: 윤곽 모양의 5 cm 판이고, 앞면은 건물 문 그림을 평평하게 붙였습니다.
  뒷면과 옆면은 문 색, 양면에 쇠 손잡이가 있습니다. 구멍 둘레에는 벽색 리빌(`DoorReveal`, 22 cm)이 있고, 뒤는 어두운 문간(`DoorOpening`)입니다.
- 구멍: 윤곽 안의 면을 문 앞면에서 2 m 깊이까지 모두 지웁니다(여러 겹, 옆면, 문간 바닥과 인방 밑면 포함). 문 앞쪽은 건드리지 않습니다.
- 떠 있는 조각: 윤곽 둘레 0.5 m, 문 앞면에서 2 m 깊이 안에 완전히 들어 있고 건물 본체와 이어지지 않은(꼭짓점 1 mm 용접 기준)
  면적 1.5 m² 미만 조각도 지웁니다. 기록: `artifacts/mapdoor/floaters.json`.
- 천문대 양문: 두 윤곽 사이 경계가 비스듬하면(기울기 0.05 이상) 그 선을 따라 두 장으로 나눕니다. 천문대 문은 둥근 탑에 있어
  벽이 렌더 정면과 약 27° 돌아 있으므로 문짝 판을 그 벽면을 따라 세웁니다(`tilt_degrees`, 10° 이상일 때만). 실내 `FrontDoor`는
  `BuildingDoors.flat_basis(leaf)`로 평평하게 되돌려 씁니다.
- 어두운 문간(`DoorOpening`)은 사각 상자가 아니라 **윤곽 모양을 벽 안쪽으로 민 통**입니다(벽 기울기를 따름). 그래서 아치 위 모서리나
  비스듬한 벽 앞으로 검은 면이 튀어나오지 않습니다(16 파란 지붕 오두막 문 위 검은 막대 수정, 2026-10-16).
- 경첩 바꾸기: `door_hinges.json`의 항목에 `"override": true`를 넣고 `hinge`를 고친 뒤 커터를 다시 실행합니다
  (02 목조 주택, 17 등대가 사용자 지시로 왼쪽 경첩).
- 켜진 문: `ENABLED`에 14채 모두와 `18_meadow_house`가 있습니다.
- **18_meadow_house**: 문 데이터는 모델(blue_house)마다 하나라서, 같은 모델을 쓰는 건물은 `BuildingDoors.entry(id)`가 자동으로 찾아 씁니다.
  `Town.DOORS`에 아직 없으면 그냥 무시됩니다. **wt/mapinterior를 병합한 뒤에는 `tools/door_cutter.gd`를 한 번 실행해서**
  18_meadow_house 항목이 `door_leaves.json`에 생기게 합니다(실행 방법은 4-1 참고).

## 5. 검증
- `game/tests/building_doors_check.gd`(헤드리스): 모든 `Town.DOORS`에 문 리소스가 있는지, 켜진 문의 노드 이름과 위치,
  두께, 바깥쪽 열림, 콜리전 없음, 베이크 섬과 런타임 빌드의 위치가 같은지, 실내 `FrontDoor`가 같은 문짝인지 확인합니다.
- `game/tests/door_test_capture.gd`(창 모드): 닫힘, 반쯤 열림, 열림, 두께 근접 사진을 찍고, 닫힌 문을 원래 건물과 픽셀 단위로 비교합니다.
