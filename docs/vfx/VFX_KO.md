# VFX 사용 안내 (N4)

다른 세션이 효과를 붙일 때 보는 짧은 안내입니다. 효과는 모두 **CPU 입자 + 짧은 트윈**으로 만듭니다. 조명(Light)은 새로 만들지 않고, 입자에는 그림자를 그리지 않습니다. 설정의 '움직임 줄이기'를 켜면 입자 수가 35%로 줄어듭니다.

## 1. 기본 효과: `game/scripts/fx.gd`

```gdscript
const Fx := preload("res://scripts/fx.gd")
Fx.burst(world, at, "sparkle", 12)        # 한 번 터지는 입자
Fx.kick(world, at, "scuff", 3, back)      # 발밑처럼 낮게 튀는 입자(back 방향으로 기욺)
Fx.stream(world, at, "spark", 1.5, 12.0)  # 몇 초 동안 계속 나오는 입자
Fx.ring(world, at, 1.2)                   # 바닥에서 넓어지며 사라지는 고리
Fx.glow(world, at, Color("ffd27a"), 1.6)  # 부풀었다 사라지는 빛(가산 합성)
Fx.bubble(world, at, "heart")             # 말풍선 아이콘
Fx.arrive(world, item, app)               # 가구를 놓을 때의 묶음 효과
```

- **입자 종류**: leaf, petal, sparkle, drop, splash, note, heart, smoke, steam, dust, spark, seed, fluff, zz
- **발밑 전용 종류**: scuff(작은 먼지), snow, blade(풀 조각), litter(마른 잎)
- 마지막 인자 `tint`의 알파가 0보다 크면, 그 종류의 기본 색 대신 tint 색을 씁니다.
- 첫 인자에는 효과가 속한 세계의 Node3D를 넘깁니다(app.world 등). 효과는 그 아래에 붙고, 끝나면 스스로 정리됩니다.

## 2. 발밑 이펙트: `game/scripts/foot_fx.gd`

- main.gd에서 `FootFx.attach(self, world_audio)`로 한 번 연결합니다. 사운드 세션의 `stepped` 신호를 받습니다.
- 소리와 같은 표면 판정(WorldAudio.SURFACE_FX)을 씁니다.
  - 흙·모래·자갈·재: 먼지
  - 얕은 물: 물방울과 물결
  - 눈·얼음: 눈가루
  - 낙엽: 마른 잎
  - 풀: 풀 조각
  - 딱딱한 바닥: 효과 없음
- 착지할 때와 물에 빠질 때는 더 크게 나옵니다.
- 전체 상한은 초당 12개입니다. 26 m 밖의 다른 사람 발걸음은 신호가 나오지 않습니다.
- 색은 낮/밤(daylight.current.night)에 맞춰 어두워집니다.

## 3. 탐험 효과: `game/scripts/combat_fx.gd`

| 함수 | 쓰는 곳 |
|---|---|
| `slash(app, heavy)` | 휘두르기 궤적. 프레임마다 갱신하고 한 프레임은 최대 1/30초로 계산해, 프레임이 길어져도 궤적이 건너뛰지 않습니다. |
| `strike(app, at, kill, parried)` | 타격 불꽃·섬광·고리. 처치하면 연기와 큰 고리, 받아치기면 흰 고리가 더해집니다. |
| `hurt(app)` | 피격 시 빨간 불꽃. 섬광 설정이 켜져 있으면 화면 가장자리도 붉어집니다. |
| `harvest(app, kind, at)` | 채집 파편. tree / stone / fiber / berry |
| `crafted(app)` | 제작 완료 빛 |
| `fuel(app)` | 모닥불에 연료를 넣을 때 불꽃과 연기 |
| `heal(app)` / `eat(app)` | 붕대 / 식사 |
| `ended(app, won)` | 탐험 성공(금빛 기둥) / 쓰러짐(회색 연기) |

## 4. 낚시

`fishing.gd`의 미터는 물고기 난이도에 따라 달라집니다.
- 1: 가로 레인
- 2: 세로 게이지
- 3~5: 원형

낚은 순간에는 물결 고리가 나옵니다. 희귀한 물고기(별 3개)이거나 새로 발견했거나 기록을 깼으면 금빛 빛과 반짝임이 더해집니다.

## 5. 시험

- `game/tests/vfx_check.gd`: 모든 종류와 상한을 확인합니다. `--capture`를 붙이면 `artifacts/vfx_sheet.png`를 만듭니다.
- `game/tests/foot_fx_village.gd`: 실제 마을의 모래·물가·풀을 걸어 봅니다. 창 모드에서 실행합니다. headless에서는 첫 HTTP 요청이 실패하는 기존 문제가 있습니다.
- `game/tests/fishing_shapes_check.gd`: 미터 3종을 확인합니다.
- `game/tests/foot_fx_perf.gd`: 마을의 프레임 시간을 잽니다. 발밑 효과 끔 / 내 캐릭터만 / 다른 사람 8명, 세 경우를 비교합니다.
