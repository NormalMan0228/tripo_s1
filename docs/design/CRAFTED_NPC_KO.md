# 플레이어가 만드는 NPC (제작 NPC) 설계 메모

> 사용자 메모(2026-10-16): "움직이는 가구는 제자리에서 움직이게 해야겠죠. 내일 이후부터 시간이 되면 npc도 만들 수 있게 해보고 싶네요."

한 줄 요약: **제작 NPC = 리깅 캐릭터 제작물 + 페르소나(이름·성격·대사·일과)**.
새로 만들 것은 페르소나, 말 걸기, 대사용 LLM 경로(1.5단계)다. 메시·리그·클립은 지금 있는 파이프라인을 그대로 쓴다.

## 0. 먼저: 움직이는 것은 "제자리"에서

- 리그 클립은 이미 제자리 클립이다. `server/rig_rules.py`의 `animation_payload()`가
  `animate_in_place: True`로 요청한다. 뼈만 움직이고 몸 위치는 그대로다.
- 가구 동작(`server/interactions.py` 프리셋: 회전, 흔들기, 통통 튀기 등)도 제자리 동작이다.
- NPC도 같은 원칙을 쓴다. **클립은 제자리, 위치 이동은 게임 코드가 한다.** (루트 모션 안 씀)

## 1. 제작 NPC란

| 구성 | 어디서 오나 |
|---|---|
| 몸 | `animate: true` 제작물. `provenance.rig.moves = true`, 클립 `idle`·`walk` (`docs/design/RIG_ANIM_API.md`) |
| 재생 | `game/scripts/rig_motion.gd` (`start()`가 idle 반복, `play(root, "walk")` 있음. 아직 walk를 부르는 곳은 없음) |
| 페르소나 | 새로 추가. 이름, 성격(`npc_homes.py` NPCS의 cheerful/calm/elegant/dreamy/playful 중 하나), 대사 묶음, 일과 |
| 서버 행 | 새 표 `crafted_npcs(host_id UNIQUE, object_id UNIQUE, name, personality, lines, state, version)`. `routine`은 2단계에 추가한다 |

- 서버가 상태를 가진다. 클라이언트가 보낸 이름·대사·위치를 그대로 믿지 않는다.
- 열 이름이 `host_id`·`object_id`면 delete-accounts가 자동으로 지운다(`admin_cli.py` `USER_COLUMNS`).
- 옛 클라이언트에는 그냥 idle 캐릭터로 보인다. 그래서 안전하게 넘어간다.

### 기존 주민과 다른 점

| 구분 | 기존 주민 | 제작 NPC |
|---|---|---|
| 목록 | `residents.gd` `RESIDENTS` 고정 | 서버 행 |
| 몸 | `res://assets/npc/<id>.glb` | 공방 GLB |
| 대사 | `main.gd` 하드코딩 | DB |
| 선물·부탁·편지·우정 | 있음 | 없음 |
| 집·잠 | 있음 | 없음 |

- id는 `crafted:<object_id>`로 둔다. `NpcGifts.can_receive()`와 `quests.gd` `choice()`에 걸리지 않게 하기 위해서다.
- `village_residents.py`(입주·퇴거)는 다시 쓰지 않는다. 집터 비우기 로직이 섞여 있다.

## 2. 흐름

```
[공방] "친근한 로봇 캐릭터" 제작 (animate=true)
   |   메시 10 + 리그 25 + idle 10 + walk 10 = 55 크레딧
   |   (rig_rules.py 견적값. 실제 Tripo 리그는 아직 한 번도 안 돌림)
   v
[리깅 제작물]  provenance.rig.moves = true, 가방에 있음
   |   "주민으로 만들기": 이름 + 성격 고르기
   v
[서버]  이름 검사(display_names.clean)
   |    -> 대사 묶음: MVP는 성격별 기본 대사, 1.5단계부터 LLM 1회 (llm_budget 예약)
   |    -> 대사 한 줄씩 검사(check_text)
   |    -> crafted_npcs 행 저장, version +1
   v
[게임]  마을에 등장: idle 제자리 재생 -> (2단계) 길 따라 walk
   |    말 걸기 = 저장된 대사에서 고르기 (추가 호출 0)
   v
[방문자] presence 응답의 version 보고 같은 NPC, 같은 대사를 받음
```

## 3. 대사: 미리 만든 대사 묶음을 추천

**MVP: 성격별 기본 대사 묶음(5종).** LLM 호출 없이 시작한다.

**A안 (추천, 1.5단계): 만들 때 한 번만 LLM 호출.**
- 상황별 대사 30~40줄을 한 번에 만든다. 예: 첫 인사, 아침·낮·저녁·밤(`main.gd` `npc_script` 시간대), 주인에게, 방문자에게.
- 기존 `server/llm_budget.py` 예약을 쓴다 (계정 하루 20회, 서버 하루 1,000회 기본값).
  이 한도는 제작 설계·행동 설계와 같이 쓴다. 실패해도 1회로 센다.
  "그만두기 → 다시 만들기"를 반복하면 한도가 금방 찬다.
  그래서 대사 다시 만들기는 NPC당 하루 1회로 막는다. 같은 `object_id`면 저장된 대사를 다시 쓴다.
- 한 줄씩 `check_text()`로 검사한다. 채팅 욕설 목록도 이 안에서 같이 본다.
  걸린 줄은 버린다. 너무 많이 걸리면 페르소나 전체를 거절한다(`refused_<category>`).
- DB에 저장해 계속 쓴다. **대화 한 줄당 비용 0.** 방문자도 같은 대사를 본다.
- 지금 마을 주민 대사도 이미 스크립트 방식이다 (`main.gd` `npc_script()`, `day_folk.gd` `GREETINGS`, `shadow_folk.gd` `say()`).
- 대사용 LLM 경로는 새로 만든다. `design_provider.py`는 설계 계약(`prompt_for`/`parse_design`)에 묶여 있다.
- 서버 LLM이 fixture(`ops/compose.yaml:18` 기본값)면 호출할 LLM이 없다. 이때는 성격별 기본 대사 묶음(5종)을 쓴다.

**B안 (나중, 선택): 실시간 LLM 대화.**
- 말 걸 때마다 1회 호출. 비용은 한 줄 1원 미만으로 작다(추정, 단가 확인 필요).
- B안은 지금 한도와 맞지 않는다. 말 한 번이 1회라서 50명이 20번씩 말하면 서버 1,000회가 다 찬다.
  그러면 모두의 제작이 멈춘다. 별도 source와 별도 상한이 먼저 필요하다.
- 플레이어 말이 프롬프트에 들어가므로 프롬프트 주입도 막아야 한다.
- 나온 문장마다 검사가 필요하다. 걸리면 A안 대사로 대신한다.
- 캐시: `behaviour_library.py`처럼 (NPC, 상황, 정규화한 플레이어 말) 키로 저장해 재사용.

## 4. 하루 일과와 돌아다니기

- 일과: `game/scripts/residents.gd`의 `plan(id, day)`처럼 (NPC id, 날짜) 시드로 하루 계획을 만든다.
  `plan()`은 `RESIDENTS`의 home·work 항목이 있어야 동작한다. 제작 NPC용 작은 계획 함수를 따로 만든다.
- 길: `game/scripts/shadow_paths.gd`의 도로 그래프를 재사용한다 (그림자 주민이 이미 걷는 길).
  `server/navigation.py`는 생존 숲 전용 격자라서 마을에는 쓰지 않는다.
- 범위: `homestead.village_inside()`는 서버 함수이고 다섯 섬 전체를 덮는 상자다.
  클라이언트 걷기는 도로 그래프(`shadow_paths.gd`)로만 제한한다.
  남의 집 안에는 들어가지 않는다. 문 앞은 `DOOR_CLEARANCE`(`shadow_paths.gd:9`)만큼 비켜 선다.
- 클립: 멈추면 `idle`, 걸으면 `walk`. 속도는 `provenance.rig.seconds.walk` 값으로 맞춘다.
  1.0초는 문서 예시이고 실제 Tripo 값은 아직 모른다.
- 충돌: NPC에는 `craft_collision.gd` 상자 충돌을 붙이지 않는다. 길을 막기 때문이다.
  걷게 하려면 `asset_assembly.gd:191-202`의 `motion_box` 분기가 필요하다(2단계).
- 말 걸기: 제작 NPC는 `npc.gd`가 아니라 `asset_assembly` 노드다. `main.gd` `nearest_npc()`의 npcs 목록에 넣는다.
  돌아보기는 화면에서만 한다. 초상화가 없으니 `open_dialogue()`에 기본 그림을 쓴다.
- 성능: 지금 제작 캐릭터는 `rig_motion.start()`의 autoplay라서 `anim_lod`가 걸리지 않는다.
  `npc.gd`처럼 MANUAL 모드로 바꾸고 `AnimLod.stride()`에 맞춰 `advance()`해야 한다.

## 5. 소유와 한도

- **처음엔 계정당 1명.** 서버 표의 `host_id UNIQUE`로 막는다.
- 제작물 행은 주인 것 그대로 둔다. 상태는 `placed`(마을)로 두어 방문자용 `visible_object()`
  (`multiplayer.py`)가 그대로 보이게 한다.
- **잠금 코드는 넣지 않는다.** 물건 상태를 바꾸는 길이 10곳쯤 된다
  (`app.py` 613·629·768, `asset_studio` 846, `build_rules` 188·394, `npc_homes` 713, `story` 275, `village_residents` 109).
  - NPC는 그 물건이 마을에 `placed`일 때만 보인다.
  - 치우거나 팔거나 선물하면 NPC는 숨고 행은 남는다. 다시 놓으면 돌아온다.
  - 특히 단비 입주(`village_residents` 109)는 집터의 물건을 가방으로 돌려보낸다.
- **비용**
  - 이미 만든 리깅 캐릭터를 NPC로 바꾸면: Tripo 크레딧 0. LLM은 1.5단계부터 1회.
  - 공방에서 새로 만들면: 55 크레딧(v3.1 무색 메시, `rig_rules.py` 견적), 텍스처 P2면 155.
  - 별씨 = 크레딧 x `TRIPOTHON_STARS_PER_CREDIT`.
  - 지금 1회 상한은 심사 서버 10, 학교 서버 35라서 55짜리 리깅 제작이 막힌다.
    `TRIPOTHON_RIG_ANIM_ENABLED`도 기본 false다. 그래서 실서버에는 리깅 캐릭터가 하나도 없다.
    상한을 올리려면 사용자 크레딧 승인이 먼저다.
- **환불**: 지금 규칙 그대로. 리그·클립 실패면 별씨 전액 환불(`rig_failed`/`animation_failed`).
  새로 만들 때는 **페르소나 검사를 메시 전에** 해서, 거절돼도 돈이 들지 않게 한다.
- 해제: "주민 그만두기"를 하면 NPC 행만 지우고 물건은 가방으로 돌아간다.

## 6. 방문자에게 보이기

- 서버가 NPC 행과 version을 가진다. presence 응답에 `npc_homes` 버전처럼
  `crafted_npcs` 버전을 같이 싣는다 (`multiplayer.py`, 349줄 근처).
  349줄은 쓰기 구간이다(초당 240회 폴링이 쓰기 자리 하나를 같이 씀). 새 조회는 `phase.commit()` 뒤에 넣는다.
- 몸(GLB)은 기존 방문자 조립 경로로 받는다. idle은 `asset_assembly.gd`가 이미 자동 재생한다.
- 위치는 동기화하지 않는다. 일과는 (id, 날짜) 시드라 같다.
  하지만 시계는 기기 시계이고, 길 위 걷기는 기기마다 무작위다. 그래서 서 있는 자리는 기기마다 다를 수 있다.
  장식 NPC라 괜찮다.
- 말 걸기는 각자 화면에서만 열린다. 대사는 같다.

## 7. 안전

- **실존 인물 닮게 만들기 금지**: `check_text()`는 단어 목록(sexual·violence·hate·drugs + 욕설)만 본다.
  person은 LLM 설계 호출 안의 SAFETY 규칙으로만 걸린다.
  그래서 대사 생성 프롬프트에 같은 거절 규칙(`{"refused": 분류}`)을 새로 넣어야 한다.
- 대사는 LLM 거절 규칙으로 막는다. 이름에 든 실존 인물은 지금 코드로 못 잡는다. 신고와 운영자 끄기로 대응한다.
- **이름**: `display_names.clean()` 규칙을 그대로 쓴다 (2~12자, 금칙어, 운영자 사칭 금지).
- **대사**: 한 줄씩 검사.
- **신고·끄기 (MVP에 넣음)**: 신고는 기존 `/v1/social/report`를 그대로 쓴다(`to_id`=주인, `context="npc:<object_id>"`).
  `admin_cli`에 NPC 끄기 명령을 하나 추가한다. 방문자에게 보이는 순간부터 필요하다.
- **보상 없음**: 그림자 주민처럼 NPC는 아이템·돈을 주지 않는다. 악용 여지를 없앤다.

## 8. 단계

- **MVP (하루)**: 개발 서버의 가짜 Tripo(`fixture_rigged_glb`)로 만든 시험용 리깅 캐릭터에 이름·성격을 붙인다.
  대사는 성격별 기본 대사 묶음. 놓은 자리에서 idle, 말 걸면 대사. 계정당 1명. 방문자도 보인다.
  신고(`/v1/social/report`)와 `admin_cli` NPC 끄기도 넣는다. 서성이기는 2단계로 미룬다.
- **1.5단계**: LLM 대사 묶음 1회. 새 프롬프트·파서·거절 규칙·fixture. 다시 만들기는 NPC당 하루 1회.
- **2단계**: 서성이기, 도로 그래프 따라 걷기(`motion_box` 분기), 하루 일과(`routine` 열 추가), 잠자기(집 안으로 사라짐).
- **3단계**: 공방에서 "NPC로 만들기"를 한 번에 (페르소나 검사 → 메시 → 리그). 1회 상한 승인이 먼저다.
- **4단계**: 계정당 인원 늘리기, 선물·우정(`npc_homes.py` 재사용).
- **5단계 (선택)**: 실시간 LLM 대화. 별도 source·상한과 프롬프트 주입 방어가 먼저다.

## 9. 사용자에게 물어볼 것

1. 대사는 MVP에 성격별 기본 대사, 다음에 A안(LLM 대사 묶음 1회)으로 가도 될까요? 실시간 대화는 나중에?
2. 처음엔 계정당 1명으로 할까요?
3. 이미 만든 리깅 캐릭터를 NPC로 바꾸는 것도 허용할까요?
   (지금 실서버에는 리깅 캐릭터가 없습니다. 시험은 개발 서버의 가짜 Tripo 캐릭터로 합니다.)
4. NPC는 어디 살까요? 플레이어 집 / 놓은 자리 / 마을 광장?
   - 추천: **놓은 자리.** 빈 집터(`house_plots.gd`)는 맵 세션이 맡은 영역이고 `danbi_plot`이 예약돼 있어 후보에서 뺍니다.
5. NPC 이름이 다른 플레이어 이름과 같아도 될까요?
   - 추천: **막습니다.** 다른 플레이어 표시 이름(`display_key`)과 같은 이름은 거절하고, 이름표에 "주민"을 표시합니다. 플레이어 사칭을 막기 위해서입니다.
6. 실제 유료 리그 시험은 별도 크레딧 승인이 필요합니다. 1회 상한(심사 10, 학교 35)을 55 이상으로 올려야 합니다.
   MVP는 개발 서버의 가짜 Tripo 캐릭터로 0 크레딧 시험을 제안합니다.

## 10. 단계별 정리

| 단계 | 내용 | 예상 작업량 | NPC 1명당 크레딧 |
|---|---|---|---|
| MVP | 시험용 리깅 캐릭터 + 이름·성격 + 성격별 기본 대사 + idle 제자리 + 말 걸기 + 방문자 표시 + 신고 | 1일 | 0 (가짜 Tripo 시험) |
| 1.5단계 | LLM 대사 묶음 1회(새 프롬프트·파서·거절 규칙·fixture) | 1일 | LLM 1회 |
| 2단계 | 서성이기, 도로 따라 walk, 시드 일과, 집에 들어가 자기 | 1~2일 | 추가 0 |
| 3단계 | 공방에서 바로 NPC 제작 (페르소나 먼저 검사) | 1일 | 55 (P2 텍스처면 155), 상한 승인 필요 |
| 4단계 | 인원 확대, 선물·우정 연결 | 1~2일 | 추가 0 |
| 5단계 (선택) | 실시간 LLM 대화 + 캐시 + 매 줄 검사 + 별도 상한 | 2~3일 | Tripo 0, LLM 대화당 1회 (별도 상한 안에서) |
