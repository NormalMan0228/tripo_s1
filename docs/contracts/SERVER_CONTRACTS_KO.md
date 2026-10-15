# 서버 계약 (Handoff 담당, 2026-10-16)

여러 세션이 함께 쓰는 서버 약속입니다. 바꿀 때는 Handoff 세션에 먼저 알려 주세요. 코드가 정답이고, 이 문서는 그 요약입니다.

## 1. 집 출입 `home_access` — `server/home_access.py`

결정 사항(사용자): 주인이 없으면 아무도 못 들어오고, 잠금 기본은 꺼짐, 나가기는 자유입니다.

| 규칙 | 서버 동작 |
|---|---|
| 주인 | 언제나 자기 집에 들어갑니다. |
| 손님 들어가기 | 주인이 지금 집 안에 있을 때만 됩니다(주인의 마지막 presence가 `scene:'home'`, 20초 이내). |
| 손님 머무르기 | 주인이 나간 뒤 10초(`OWNER_GRACE`) 안에 따라 나가야 합니다. 그 뒤에는 `owner_away`로 거절됩니다. |
| 잠금 | 주인만 켜고 끕니다. 새로 들어오는 손님만 막고, 이미 안에 있는 손님은 그대로 둡니다. 기본은 꺼짐입니다. |
| 내쫓기 | 주인만 할 수 있습니다. 그 손님은 바로 집 밖(`village`)으로 나가고, 10분(`EJECT_SECONDS`) 동안 다시 못 들어옵니다. 마을 방문은 계속됩니다. |
| 거절 | 손님의 presence가 `scene:'home'`으로 와도 서버는 `away`로 저장합니다. 그러면 아무에게도 그려지지 않고 `space`도 `null`이 됩니다. 클라이언트만 막는 방식이 아니라 서버가 막습니다. |

**API**
- `GET /v1/home/access` → `{host_id, open, owner, locked, owner_in?, reason?, until?}`: 지금 방문 중인 마을의 집에 대한 상태입니다. 문을 열기 전에 확인합니다.
- `POST /v1/home/lock {request_id, locked: bool}` → `{locked}`: 내 집 잠금
- `POST /v1/home/eject {request_id, user_id}` → `{ok, was_inside, until}`: 내 집에서만 내보냅니다. 자기 자신을 지정하면 409 `cannot_eject_self`입니다.
- presence 응답의 `home` 블록도 `GET /v1/home/access`와 같은 모양입니다(매 폴링마다 옵니다).
- `reason`은 `owner_away`, `locked`, `ejected` 중 하나입니다. 클라이언트는 이 값에 맞는 효과나 문구를 보여 주고 문을 닫아 둡니다.
- `/health`의 `home_access: 1`을 보고 기능이 있는지 확인합니다.

## 2. presence 필드 — `server/multiplayer.py` `/v1/social/presence`

**보내는 쪽(요청)**: 옛 클라이언트도 계속 돌도록, 새 필드는 `/health`에 광고될 때만 보냅니다.

| 필드 | 형식 | 광고 | 뜻 |
|---|---|---|---|
| `ix` | `{k,p,c,t0,o,s,h}` | `interaction_sync: 1` | 몸이 물체와 하는 일(소켓 종류, 단계). 그대로 다른 사람에게 전달됩니다. |
| `held` | `^[a-z0-9_]{0,32}$` | `presence_held: 1` | 손에 든 물건 id입니다. `''`이나 생략은 빈손입니다. 서버는 해석하지 않고 전달만 합니다. |

**받는 쪽(응답)**
- `shards` (정수): 내 별씨 잔액입니다. 폴링마다 와서 화면 지갑이 바로 따라갑니다. 숫자 표시는 꾸밈이고, 실제 검증은 서버 장부(`app.py money`)가 합니다.
- `home` (객체): 위 1번의 집 출입 상태입니다.
- `space.players[]`: 사람마다 `ix`가 있을 때만 `ix`를, `held`가 있을 때만 `held`를 붙입니다.

**held id 목록**: 들고 다니기 세션(N4)이 클라이언트 쪽 목록을 정합니다. 예: `umbrella`, `lantern`, `bouquet`, `rod`, `axe`. 서버는 형식만 검사하니, 새 물건을 추가할 때 서버를 고칠 필요가 없습니다. 모르는 id를 받은 클라이언트는 빈손으로 그립니다.

## 3. 상호작용 소켓 정의 (ISS-1) — `game/scripts/ix/ix_schema.gd`

소켓의 단일 정의는 `ix_schema.gd`입니다. 자세한 설명은 `docs/design/INTERACTION_SOCKETS.md`와 `docs/design/ISS1_KO.md`에 있습니다. 새 종류를 추가하려면 스키마 버전을 올려야 하니 Handoff에 먼저 알려 주세요.

- **좌표 규칙**: 미터, 초, 라디안 단위입니다. +Y가 위입니다. 물체의 앞은 +Z이고, 원점은 바닥 발자국의 가운데입니다.
- **물체 소켓 종류(`TYPES`)**: `sit` `perch` `sit_ground` `lie` `stand_use` `reach` `grip` `look_at` `passage` `place` `talk`
  - 앉기·눕기 높이 범위는 `HEIGHT_RANGE`, 누울 자리의 최소 크기는 1.3 × 0.45 m입니다.
  - 변형: 앉기는 `SIT_VARIANTS`(chair, bench, swing, rocker 등), 눕기는 `LIE_VARIANTS`(bed, hammock, bathtub 등)
- **캐릭터 소켓(`CHARACTER_SOCKETS`)**: `root` `seat_contact` `pelvis_lie` `sole_l/r` `grip_r/l` `pinch_r/l` `hold_front` `back` `hip_r/l` `eyes` `mouth` `head_top` `overhead`. 어느 뼈인지는 `ix_rig.gd SOCKETS`에 있습니다.
  - 물체 소켓과 캐릭터 소켓의 짝은 `ALIGNS`가 정합니다(예: sit → seat_contact, lie → pelvis_lie, grip → grip_r, place → hold_front).
- **소켓 기록**(`normalize()`가 모든 필드를 채움): `{id, type, variant, carrier, at, off, yaw, snap, params, approach[], exit, cap, group, repeat, source, follow}`
  - `source`는 `authored`, `server`, `derived`, `bbox` 중 하나입니다. 게임 안에서 만든 Tripo 물체는 설계 부품 → 충돌 상자 → 테두리 상자(bbox) 순서로 소켓을 얻습니다.
  - 문제 검사는 `problems()`가 합니다.
- **애니메이션 클립 이름**: `family_variant_phase[_qualifier]` 형식입니다. 패밀리, 단계, 한정어, 마커는 각각 `FAMILIES`, `PHASES`, `QUALIFIERS`, `MARKERS` 목록에 있는 것만 씁니다. 외부에서 만든 클립도 이 이름을 따라야 합니다.
- **들고 다니기(N4, 64번)**: 손에 드는 물건은 캐릭터 소켓 `grip_r`(한 손), `hold_front`(양손), `pinch_r`(꼬집기), `back`(등)에 붙입니다. 무엇을 들었는지는 위 presence `held`로 다른 사람에게 알립니다. 잡는 자세의 클립은 `carry_*`, `tool_*` 패밀리를 씁니다.

## 4. 요청을 받으면 넣을 것

- 문 열고 들어오기·나가기 이벤트(N3, 49·51번): presence에 `door: 'in' | 'out'`과 시각을 넣어 다른 사람에게 전달하는 방식을 생각하고 있습니다. 필요하면 Handoff에 요청해 주세요.
