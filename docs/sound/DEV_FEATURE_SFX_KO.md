# 06:00 뒤 dev 기능 효과음 연결표 (2026-10-16, 04 사운드)

새 기능을 만드는 세션이 소리를 한 줄로 붙일 수 있게 정리했습니다. 새 소리 12종(49개, 약 2.2 MB)은 `tools/sfx/gen_dev_features.py`로 만들었고, 모두 자동 검사를 통과했습니다(거의 같은 테이크 없음, 음량 맞춤). 모든 호출은 섞어 뽑기로 재생되어 같은 테이크가 연달아 나오지 않습니다.

호출 형태:
- 화면 UI: `RpgUi.sfx("<kind>", dB)` → `ui/<kind>`
- 생활: `life.sfx.play("<kind>", pitch, dB)` 또는 `LifeSfx.play` → `life/<kind>`
- 핵심: `sound.effect("<kind>")` → `core/<kind>`
- 위치가 있는 소리: `Fx.sound(app, "<dir>/<kind>", at, pitch, dB)`
- 전투·탐험: `CombatAudio.play(app, "<event>", at)` → `combat/<event>`
- 문: `DoorAudio.play(host, kind, room, at)` (docs/sound/HOOKS_KO.md)

## 1. 농사 (#29, N4 · codex/farm)

| 순간 | 소리 | 새로 만듦 |
|---|---|---|
| 밭 갈기 till | `life/hoe` (이미 연결) | |
| 밭 되돌리기 untill | `life/untill` (흙 토닥 + 고르기) | ✔ |
| 심기 plant | `life/seed` (이미 연결) | |
| 물주기 water | `life/water` (이미 연결) | |
| 이미 물 줌 `life_already_watered` | `RpgUi.sfx("deny",-8)` | |
| 단계 변화 seed→sprout | `life/sprout` (흙 갈라짐 + 잎 펼침), 밭 위치로 `Fx.sound` | ✔ |
| 단계 변화 → ripe(수확 가능) | `life/ripe` (작은 반짝 + 잎 떨림), 화면 밖이면 생략 | ✔ |
| 수확 harvest | `life/pop` 뒤에 `life/collect` (이미 연결). 연속 수확은 `pocket` 음 올림 | |
| 씨앗 구매 / 작물 판매 | `core/buy` / `core/sell` + `RpgUi.sfx("coin_gain")` | |

- 단계 변화는 폴링 응답에서 `stage_index`가 올라갈 때 한 번만 냅니다.
- 여러 칸이 한 번에 바뀌면 0.1~0.2초씩 띄워서 냅니다.

## 2. 상점·특수건물 (#81, 03 UI · 06 스토리 · codex/shops)

| 순간 | 소리 | 새로 만듦 |
|---|---|---|
| 상점 창 열기 / 닫기 | `RpgUi.window`가 open/close를 냄(추가 호출 없음) | |
| 물건 고르기 | `RpgUi.sfx("select",-9)` | |
| 수량 +/- | `RpgUi.sfx("tab",-12)` | |
| 사기 성공 | `core/register` (서랍·종·동전) — 계산대가 있는 상점. 노점은 `core/buy` | ✔ |
| 팔기 성공 | `core/register` 또는 `RpgUi.sfx("coin_gain",-5)` | ✔ |
| 돈 부족·거절 | `RpgUi.sfx("deny",-6)` | |
| 서비스 완료(수리·염색 등) | `RpgUi.sfx("craft_done",-6)` | |
| 문으로 들어가기 | 건물 문 소리(카페·상점 종 포함, 이미 연결) | |

## 3. 주민 이사 (#43, 06 스토리 · codex/movein43)

| 순간 | 소리 | 새로 만듦 |
|---|---|---|
| 이사 소식 편지 도착 | `field/flap`(우편함) + `RpgUi.sfx("notify",-8)` | |
| 게시판 공지 | `field/pin` | ✔ |
| 빈 집터에 집이 생김 | `core/build_appear` (반짝임이 차오르고 나무 쿵쿵, 2~3초), 집터 위치로 | ✔ |
| 입주 환영 | `core/move_in` (따뜻하게 올라가는 짧은 멜로디) | ✔ |
| 떠남 | `core/move_out` (부드럽게 내려가는 멜로디) | ✔ |
| 짐 상자 | `field/box` | |

## 4. 퀘스트 게시판·편지 (#26, 06)

| 순간 | 소리 | 새로 만듦 |
|---|---|---|
| 게시판 열기 | `field/paper` + 창 open | |
| 의뢰 받기 | `RpgUi.sfx("quest_accept",-6)` (이미 있음) | |
| 새 의뢰가 붙음 | `field/pin` | ✔ |
| 완료 보고 | `RpgUi.sfx("quest_complete",-6)` | |
| 편지 쓰기(글자 입력) | `VoiceBabble.speak(app,"letter",…)` 펜 소리 또는 `RpgUi.sfx("brush",-14)` | |
| 편지 보내기 | `RpgUi.sfx("letter_send",-8)` (접기 + 바람) | ✔ |
| 편지 받기 | `field/flap` + `notify` | |

## 5. 탐험 모닥불 버프 (#84, N5 · codex/campfire)

| 순간 | 소리 | 새로 만듦 |
|---|---|---|
| 버프 범위 안으로 들어옴 | `CombatAudio.play(app,"buff_warm")` (따뜻한 확 퍼짐 + 화음) | ✔ |
| 회복 틱 | `CombatAudio.play(app,"buff_heal")` (작게 올라가는 반짝임). 1.5초에 한 번 이하 | ✔ |
| 버프 끝·범위 밖 | `CombatAudio.play(app,"buff_end")` | ✔ |
| 불 지피기 / 불 소리 | `fuel`, `campfire_loop` (이미 연결) | |

- 결계를 없앨 때 main.gd `survival_audio`의 **ward 신호음**(몬스터가 밀려날 때 나던 소리)도 같이 지우거나 `buff_warm`으로 바꿔 주세요.
- `combat_audio.gd`의 EVENTS에 `buff_warm`(-12 dB), `buff_heal`(-21 dB), `buff_end`(-14 dB)를 넣어 두었습니다. 바로 `CombatAudio.play`로 부르면 됩니다.

## 6. 새 몬스터 29종 (N5)

- 연결 끝: 종마다 자기 소리가 납니다(`creature_audio.gd voice_name`).
- 보스는 등장음과 포효를 냅니다(`shadow_beast.gd`).
- 새 종을 추가하면 `tools/sfx/gen_monsters.py`에 한 줄을 넣고 다시 만듭니다.
