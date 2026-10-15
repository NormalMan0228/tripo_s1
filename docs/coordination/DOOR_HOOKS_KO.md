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
- **지금은 테스트로 `10_red_house`(나의 집) 하나만 켜져 있습니다**(`building_doors.gd`의 `ENABLED`).
  사용자가 승인하면 `ALL_DOORS := true`로 바꿔 모든 문에 적용합니다.

## 1. N3 `register(id, node, hinge_axis, open_angle)`에 넣을 값

| 항목 | 바깥 문 | 실내 문 |
|---|---|---|
| 노드 | `Buildings/<id>/DoorLeaf` (맵 기준. 예: `Buildings/10_red_house/DoorLeaf`) | 방 1층 루트 아래 `FrontDoor` |
| 찾는 함수 | `BuildingDoors.door_leaf(id)` | `Interiors.front_door(root)` |
| 경첩 축 | 노드 로컬 **+Y** | 노드 로컬 **+Y** |
| 경첩 위치 | 노드 원점 = 밖에서 볼 때 문의 **오른쪽** 세로 모서리, 문턱 높이 | 노드 원점 = 같은 쪽(오른쪽) 모서리, 바닥 |
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
| `BuildingDoors.door_leaf(id)` | `Node3D` | 경첩(`DoorLeaf`) |
| `BuildingDoors.door_opening(id)` | `MeshInstance3D` | 어두운 문간(`DoorOpening`). `material_override`에 `inner_light`(0..1)가 있습니다 |
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
- 문 리소스 만들기(14개 전부 약 10초):
  ```
  .tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://../tools/door_leaves.gd
  ```
  `Town.DOORS`의 모든 항목을 자동으로 처리합니다. 건물 GLB, 배치, `Town.DOORS`가 바뀌면 다시 실행합니다
  (예: wt/mapinterior의 `18_meadow_house`를 병합한 뒤 한 번 다시 실행해야 합니다).
- 모든 문에 적용: `building_doors.gd`의 `ALL_DOORS := true`.
- 칠한 색으로 문을 못 찾는 문은 `RECT_OVERRIDES`에 직접 적습니다(카페, 천문대, 온실, 공방, 잡화점).

## 5. 검증
- `game/tests/building_doors_check.gd`(헤드리스): 모든 `Town.DOORS`에 문 리소스가 있는지, 켜진 문의 노드 이름과 위치,
  두께, 바깥쪽 열림, 콜리전 없음, 베이크 섬과 런타임 빌드의 위치가 같은지, 실내 `FrontDoor`가 같은 문짝인지 확인합니다.
- `game/tests/door_test_capture.gd`(창 모드): 닫힘, 반쯤 열림, 열림, 두께 근접 사진을 찍고, 닫힌 문을 원래 건물과 픽셀 단위로 비교합니다.
