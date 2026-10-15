# 사운드 훅 — 발밑 표면, 문 (2026-10-16, 브랜치 wt/soundhooks)

다른 세션이 소리를 직접 고치지 않고 붙여 쓸 수 있는 연결 지점입니다. 시험은 `game/tests/sound_hooks_check.gd`(헤드리스)입니다.

## 1. 발밑 표면 (#30, VFX·생활 세션용)

발소리가 고른 표면을 신호로 그대로 받습니다. 그래서 소리와 이펙트가 같은 판정을 씁니다.

```gdscript
# main.gd(마을·탐험) 또는 studio.gd(방)의 world_audio 노드에 연결
app.world_audio.stepped.connect(func(info: Dictionary):
	match info.fx:
		"dust": Fx.burst(...)      # 모래·흙·자갈·재
		"splash": ...              # 얕은 물
		"snow": ...                # 눈·얼음
		"leaves": ...              # 낙엽
		"grass": ...               # 풀
		"": pass)                  # 돌·나무·마루·타일·러그·계단: 보이는 것 없음
```

`info`에 들어 있는 값은 다음과 같습니다.

| 키 | 값 |
|---|---|
| `kind` | `"step"` · `"land"`(착지) · `"splash"`(물에 들어감) |
| `who` | `"hero"`(내 캐릭터) · `"remote"`(다른 플레이어·그림자 주민·방 주민) |
| `surface` | 소리에 쓴 표면. `WorldAudio.SURFACES` 16종 중 하나이며, 모르는 표면은 `grass` |
| `fx` | `WorldAudio.SURFACE_FX[surface]`: dust · splash · snow · leaves · grass · "" |
| `at` | 발 위치(월드 좌표). 모르면 `Vector3.INF` |
| `speed` | m/s |
| `gait` | `"walk"` · `"run"` |
| `foot` | 0 왼발, 1 오른발. 착지·물·원격은 -1 |
| `size` | 물 첨벙 크기(바다에 빠짐 1.0, 얕은 물 0.5) |

- 연결된 곳이 없으면 신호를 만들지 않으므로 비용이 없습니다.
- 소리를 끄거나 테이크가 없어도 신호는 나갑니다.
- 다른 사람의 발걸음은 들리는 거리(`REMOTE_AUDIBLE` 26 m) 안에서만 나옵니다. 멀리 있는 사람 때문에 이펙트가 쌓이지 않습니다.
- 표면 판정 자체는 그대로 둡니다. 맵·생존은 `main.gd ground_surface()/survival_surface()`, 방은 `studio.gd floor_surface()`입니다.

## 2. 문 (집·문·방문 세션용)

`game/scripts/door_audio.gd`를 씁니다. `transition.gd`는 맵 세션 소유라 고치지 않고 감쌌습니다.

```gdscript
const DoorAudio = preload("res://scripts/door_audio.gd")
DoorAudio.play(self, "open", "home")                         # 내 문(위치 없음 = 평면, play_door와 같음)
DoorAudio.play(self, "open", "01_cafe", door.global_position) # 다른 사람이 여는 문(위치 기반, 거리 감쇠)
DoorAudio.door_open(self, room, at, 1.2)    # 문짝이 1.2초 동안 열리는 애니메이션: 걸쇠+경첩, 느린 삐걱
DoorAudio.door_close(self, room, at, 0.6)   # 0.6초 동안 닫힘: (길면 삐걱) 0.6초 뒤 문틀에 닿는 소리
DoorAudio.play(self, "locked", room, at)    # 잠긴 문 손잡이 덜컹 (#50)
DoorAudio.play(self, "knock", room, at)     # 노크
```

| kind | 소리 | 테이크 |
|---|---|---|
| open / close | 방마다 다른 문 소리(카페 종, 등대 철문…) | 방 14곳 × 4 |
| swing | 문짝이 천천히 움직일 때 경첩 삐걱(1.2~2.4초) | 4 (새로 만듦) |
| locked | 잠긴 손잡이 덜컹 2~4번 | 4 (새로 만듦) |
| knock | 나무문 노크 | 6 |

- 같은 문에서 같은 소리는 90 ms 안에 한 번만 납니다. 같은 폴링에 두 명이 들어와도 겹치지 않습니다.
- 30 m보다 먼 문은 소리를 내지 않습니다.
- 음성 4개짜리 풀이 `host` 아래에 생기고, `host`와 함께 사라집니다.
- 생성기는 `tools/sfx/gen_door_extras.py`이고, `SFX_BASE=merge-version-gate`로 실행합니다.
