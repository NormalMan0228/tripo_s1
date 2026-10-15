# 8종 플레이어 캐릭터·외형 API (최종 계약)

UI 세션(03)용 서버 계약 문서이다. 서버 코드: `server/models.py`(`Avatar`, `AvatarPatch`), `server/appearance.py`, `server/app.py`. 테스트: `server/tests/test_avatar8.py`.

## 0. 한눈에 보기

- 필드 이름은 **기존 이름 그대로**이다: `character`, `hair`, `skin`, `coat`, `pants`, `boots`, `headwear`, `backpack`.
- 바뀐 점과 추가된 점은 다음과 같다.
  - `character` 값이 새 8종 `m1`~`m4`(남성형), `f1`~`f4`(여성형)로 바뀌었다.
  - 색 필드 `accent`가 추가되었다.
  - 모자 `headwear`에 `straw`가 추가되었다.
  - `skin`은 아무 `#RRGGBB` 값이나 받는다. 고정 팔레트는 없어졌다.
- `character_id`, `top`, `bottom`, `shoes`, `accessory`, `hat` 같은 키는 어디에도 없다. 요청에 넣으면 `422`이다.
- `POST /v1/profile`의 `avatar`는 **부분 저장(patch)**이다. 보낸 필드만 바뀌고 생략한 필드는 저장된 값을 유지한다.
- 프로필에 `needs_character_select`가 생겼다. 새 id(`m1`~`f4`)를 `character`에 한 번 저장하기 전까지 `true`이다.
- 새 API `GET /v1/avatar/catalog`가 추가되었다. 로그인 없이 쓸 수 있다.
- `GET /health`에 `avatar_v2: 1`과 `characters` 목록이 추가되었다.
- 0.11.8 게임은 업데이트 없이 그대로 동작한다. 자세한 내용은 10절에 있다.

## 1. 외형 객체 `avatar`

모든 응답(프로필, presence, 방문, 협동 원정, 친구·사람 목록)의 `avatar`는 아래 9개 필드를 **항상 모두** 가진다.

| 필드 | 값 | 기본값(미저장 계정) |
| --- | --- | --- |
| `character` | `m1` `m2` `m3` `m4` `f1` `f2` `f3` `f4` | `f1` |
| `hair` | `#RRGGBB` | `#30595b` |
| `skin` | `#RRGGBB` (팔레트 제한 없음) | `#e4b587` |
| `coat` | `#RRGGBB` | `#dba448` |
| `pants` | `#RRGGBB` | `#526552` |
| `boots` | `#RRGGBB` | `#765744` |
| `accent` | `#RRGGBB` (**신규**) | `#765744` |
| `headwear` | `none` `cap` `beret` `straw` (`straw` **신규**) | `none` |
| `backpack` | JSON 불리언 `true`/`false` | `true` |

색 값의 규칙은 다음과 같다.

- 색은 정규식 `^#[0-9a-fA-F]{6}$`에 맞는 문자열만 받는다.
- 대·소문자 모두 받으며, 보낸 그대로 저장하고 돌려준다.
- `#abc`, `123456`, `#RRGGBBAA`, 앞뒤 공백·개행, 숫자, `null`은 모두 `422`이다.

`backpack`은 진짜 불리언만 받는다. `0`, `1`, `"true"`, `"false"`, `null`은 `422`이다.

`cap`과 `straw`는 서로 다른 모자이다. 서로 바꿔 저장하거나 읽지 않는다.

## 2. 엔드포인트

| 메서드·경로 | 인증 | 외형 관련 내용 |
| --- | --- | --- |
| `POST /v1/auth/register` | 없음 | 응답 `profile` |
| `POST /v1/auth/login` | 없음 | 응답 `profile` |
| `GET /v1/me` | 필요 | 응답 `profile`, `catalog.characters` (8종 `id`·`name`·`description`, `defaults` 없음) |
| `GET /v1/studio` | 필요 | 응답 `profile` |
| `GET /v1/profile` | 필요 | 프로필 객체 그 자체 |
| `POST /v1/profile` | 필요 | 외형 저장(부분 저장). 응답은 프로필 객체 |
| `GET /v1/avatar/catalog` | **없어도 됨** | 8종 카드, 캐릭터별 시작 외형, 모자·색 부위 목록 |
| `GET /health` | 없음 | `avatar_v2: 1`, `characters: [...]` |

프로필 객체는 모든 곳에서 같은 모양이다.

```json
{
  "avatar": {
    "character": "f1", "hair": "#30595b", "skin": "#e4b587", "coat": "#dba448", "pants": "#526552",
    "boots": "#765744", "accent": "#765744", "headwear": "none", "backpack": true
  },
  "version": 0,
  "needs_character_select": true
}
```

- `version`: 한 번도 저장하지 않은 계정은 `0`이다. 저장이 성공할 때마다 1씩 오른다.
- `needs_character_select`: 서버가 관리하는 읽기 전용 값이다. `avatar` 안에는 없다. 다른 플레이어에게도 보내지 않는다.

## 3. 캐릭터 카탈로그 `GET /v1/avatar/catalog`

로그인 없이 호출할 수 있다. 로그인 상태에서 호출해도 같은 응답이 온다.

```json
{
  "characters": [
    {
      "id": "m1",
      "name": "남성 1",
      "description": "머리, 피부, 옷과 소품의 색을 골라 꾸밀 수 있어요.",
      "defaults": {
        "character": "m1", "hair": "#2b2320", "skin": "#e4b587", "coat": "#3f6fa8", "pants": "#3b4250",
        "boots": "#5a4030", "accent": "#c9a24a", "headwear": "none", "backpack": true
      }
    },
    "... m2, m3, m4, f1, f2, f3, f4 (항상 이 순서, 8개)"
  ],
  "headwear": ["none", "cap", "beret", "straw"],
  "parts": ["hair", "skin", "coat", "pants", "boots", "accent"]
}
```

- `characters`는 8개이며 순서는 `m1 m2 m3 m4 f1 f2 f3 f4`이다.
  - `name`과 `description`은 지금은 임시 문구이다. 서버에서 바뀔 수 있으므로 UI는 하드코딩하지 말고 이 값을 표시한다.
- `defaults`는 **캐릭터마다 다른 시작 외형**이다(`server/appearance.py`의 `DEFAULT_LOOKS`). 형식은 1절의 외형 객체와 같다.
  - 서버가 게임 업데이트 없이 값을 조정할 수 있다.
  - `f1`의 `defaults`는 1절의 계정 기본값과 같다.
- **캐릭터를 저장해도 서버가 그 캐릭터의 `defaults`를 자동으로 적용하지 않는다.** 부분 저장이라 `character`만 바뀐다. 시작 외형으로 바꾸려면 UI가 `defaults`의 필드를 함께 보낸다. `defaults` 전체를 그대로 보내도 유효한 저장이다(테스트로 확인됨).
- `parts`는 색을 고르는 부위의 순서이다. `headwear`는 모자 선택지이다.

## 4. 서버 기능 확인 `GET /health`

```json
{ "ok": true, "...": "...", "avatar_v2": 1, "characters": ["m1","m2","m3","m4","f1","f2","f3","f4"] }
```

새 UI는 `avatar_v2 == 1`이면 8종 선택 화면과 부분 저장을 쓴다. 이 값이 없는 서버는 0.11.8 이전 서버이다.

## 5. 저장 `POST /v1/profile`

요청은 `{ "request_id": UUID, "version": 마지막으로 읽은 version, "avatar": { 바꿀 필드만 } }` 형식이다.

최초 캐릭터 선택(시작 외형 포함)의 요청 예시:

```json
{
  "request_id": "9d889795-e9ae-47bc-8df7-047a5b0c43f1",
  "version": 0,
  "avatar": {
    "character": "f3", "hair": "#1c1a1a", "skin": "#bc865c", "coat": "#3d8a7d", "pants": "#3a3f3a",
    "boots": "#4a3528", "accent": "#e6a25a", "headwear": "straw", "backpack": false
  }
}
```

응답(항상 9개 필드가 모두 채워진 외형):

```json
{
  "avatar": {
    "character": "f3", "hair": "#1c1a1a", "skin": "#bc865c", "coat": "#3d8a7d", "pants": "#3a3f3a",
    "boots": "#4a3528", "accent": "#e6a25a", "headwear": "straw", "backpack": false
  },
  "version": 1,
  "needs_character_select": false
}
```

이후 소품색만 바꾸는 요청:

```json
{ "request_id": "2d74069c-d650-479e-b4aa-27bc029ba056", "version": 1, "avatar": { "accent": "#A0B1C2" } }
```

이 요청의 응답은 다음과 같다.

- `character` `f3`와 나머지 값은 그대로 유지된다.
- `accent`만 `#A0B1C2`로 바뀐다.
- `version`은 `2`, `needs_character_select`는 `false`이다.

저장 규칙은 다음과 같다.

- **생략과 `null`은 다르다.** 필드를 생략하면 저장값이 유지되고, `null`을 보내면 `422`이다.
- 빈 `avatar: {}`도 정상 저장이다. 버전이 오르고 속도 제한 횟수에도 포함된다.
- **옛 id도 받는다.** 옛 id는 다음처럼 매핑해서 저장한다.
  - `explorer`, `tinker` → `m1`
  - `explorer_b`, `ranger` → `f1`
  - 응답과 저장값에는 매핑된 새 id만 나온다.
- 그 밖의 값은 모두 `422 {"detail":"invalid_request"}`이다.
  - 모르는 id: `m5`, `F1`, `""`, 경로 문자열 등
  - 모르는 모자: `crown`, `Straw` 등
  - 정의되지 않은 필드: `character_id`, `top`, `owner_id`, `colors`, `needs_character_select` 등
- 요청 최상위에 `needs_character_select`를 넣어도 `422`이다.
- 실패한 요청(`422`/`409`/`429`)은 외형, 버전, `needs_character_select`를 바꾸지 않는다.

## 6. 최초 캐릭터 선택 `needs_character_select`

- 모든 계정은 `true`로 시작한다. 새 계정과 마이그레이션된 기존 계정 모두 해당한다.
- `avatar.character`에 **새 id(`m1`~`f4`)를 명시해서 저장에 성공하면** `false`가 된다.
  - 기본값과 같은 `f1`을 명시해도 선택 완료이다.
  - 한 번 `false`가 되면 이후 어떤 저장이나 재전송으로도 `true`로 돌아가지 않는다.
- 다음 경우는 선택 완료가 **아니다**. 값이 `true`로 유지된다.
  - `character`를 생략한 저장(색, 모자, 가방만 바꾼 경우)
  - **옛 id**(`explorer`, `explorer_b`, `ranger`, `tinker`)를 보낸 저장. id는 매핑되어 저장되지만 선택은 완료되지 않는다.

새 UI의 흐름은 다음과 같다.

1. 로그인·회원가입 응답(또는 `GET /v1/me`)의 `profile`로 캐릭터를 만든다.
2. `needs_character_select == true`이면 8종 선택 화면을 연다.
   - 카드와 시작 외형은 `GET /v1/avatar/catalog`에서 가져온다.
   - 기존 계정은 마이그레이션된 외형(`profile.avatar`)을 미리보기 시작값으로 쓸 수 있다.
3. 확정할 때 `character`를 **명시해서** 저장한다. 시작 외형을 쓰려면 `defaults` 필드도 함께 보낸다.
4. 성공 응답의 `needs_character_select: false`를 확인한 뒤 다음 화면으로 넘어간다. 저장에 실패하면 선택 완료로 처리하지 않는다.
5. 일반 옷장에서 색만 바꿀 때는 `character`를 빼고 바뀐 필드만 보낸다.

## 7. 재전송·버전 충돌·속도 제한

- **재전송**: 응답을 못 받았으면 같은 `request_id`와 **완전히 같은 본문**으로 다시 보낸다.
  - 서버는 처음 성공했을 때의 `avatar`와 `version`을 돌려준다. 버전을 다시 올리지 않고, 속도 제한 횟수도 쓰지 않는다.
  - `needs_character_select`는 재전송이어도 **현재 계정 값**을 돌려준다. 선택 전 요청을 선택 후에 재전송해도 선택 화면이 다시 열리지 않는다.
  - 그 사이 다른 저장이 있었다면 재전송 응답은 최신 상태가 아니다. 최신 값은 `GET /v1/profile`로 읽는다.
- **본문 동일성**: 필드 생략과 명시는 다른 요청이다. 예를 들어 `{}`와 `{"character":"f1"}`은 같은 UUID로 보낼 수 없다.
  - 성공한 UUID를 다른 본문에 다시 쓰면 `409 request_id_reused`이다.
- **버전 충돌**: 서버 `version`과 다르면 `409 stale_profile_version`이다. `GET /v1/profile`로 다시 읽고 사용자 변경을 다시 적용한 뒤 새 UUID로 저장한다.
- **속도 제한**: 계정마다 최근 60초 동안 **성공한 저장 10회**까지 허용한다.
  - 11번째 저장은 `429 {"detail":"avatar_rate_limited"}`이다. `Retry-After` 헤더에 정수 초(1~60)가 온다.
  - 재전송, `422`, `409`는 횟수에 포함되지 않는다.
  - 제한 기록은 서버를 재시작해도 유지된다.
  - 색 미리보기는 클라이언트에서만 처리하고, 확정할 때 한 번 저장한다.
- **업그레이드 전 요청의 재전송**: 0.11.8 서버가 이미 성공 처리한 외형 요청을 업그레이드 후에 같은 UUID와 본문으로 재전송해도 된다. 서버는 옛 방식의 fingerprint(`appearance.legacy_request_json`)로 대조한다. 당시 결과를 새 형식(옛 id 매핑, `accent` 기본값)으로 돌려주며, 새로 기록하는 것은 없다.

## 8. 다른 플레이어에게 보이는 외형

아래 플레이어 항목은 모두 1절 형식의 `avatar`(9개 필드)와 `avatar_version`(그 플레이어 프로필의 `version`)을 가진다.

| API | 위치 |
| --- | --- |
| `POST /v1/social/presence` | `space.players`, `village.players` (마을, 방문, 집 안) |
| `GET /v1/coop/runs/{id}`, `POST /v1/coop/runs/{id}/input` | `players` (원정 시작 이후 저장한 최신 외형) |
| `GET /v1/social/people` | `online`, `friends` |

- `avatar_version`이 바뀌면 모델과 색을 다시 적용한다.
- presence는 매번 최신 프로필을 읽는다.
- `GET /v1/social/people`의 `online` 목록은 기존 캐시를 써서 최대 약 3초 늦게 반영된다. 이 지연을 저장 실패로 처리하지 않는다.
- presence나 방문 요청 자체의 형식은 바뀌지 않았다. 외형은 `POST /v1/profile`로만 저장한다.

## 9. 기존 DB 마이그레이션

서버가 시작할 때 한 번만 자동으로 변환한다. 클라이언트가 할 일은 없다.

- `profiles.needs_character_select` 열이 기본값 `1`로 추가된다. **모든 기존 계정은 `true`**가 된다.
- 바꾸기 전 원본 JSON과 버전은 `profile_avatar8_backup(user_id, avatar, version)`에 그대로 보존된다.
- 변환 규칙:
  - 옛 id는 매핑한다: `explorer`·`tinker` → `m1`, `explorer_b`·`ranger` → `f1`.
  - `accent`가 없으면 기본값 `#765744`를 넣는다.
  - `cap`과 `beret`은 그대로 둔다.
  - 깨진 필드는 그 필드만 기본값으로 바꾼다. JSON 전체가 깨졌으면 기본 외형을 쓴다.
- 프로필 `version`은 올리지 않는다. 의상 퀘스트 같은 버전 기반 진행이 마이그레이션만으로 완료되지 않게 하기 위해서이다.
- 외형 이외의 데이터(계정, 재화, 물건, 집, 원장)는 바꾸지 않는다.
- 프로필을 한 번도 저장하지 않은 계정은 행이 새로 생기지 않는다. 그대로 `version: 0`, 기본 외형, `true`이다.
- 완료 표시는 `metadata.avatar8_schema = 1`이다. 재시작해도 다시 변환하지 않고, 백업도 덮어쓰지 않는다.

## 10. 0.11.8 게임(옛 클라이언트)과의 호환

0.11.8 게임은 업데이트 없이 계속 접속하고 저장할 수 있다.

- **읽기**: 필드 이름이 같아서 옛 게임은 `character`, 색 필드, `headwear`, `backpack`을 그대로 읽는다.
  - 옛 게임은 `character` 값과 관계없이 **항상 같은 옷장 모델**을 불러온다. 그래서 새 id(`m3` 등)는 그 모델로 보이고, 색은 반영된다.
  - 옛 게임은 `accent`를 모르므로 무시한다(`avatar_look.gd`의 `normalize`가 버림).
  - `straw`는 옛 게임에 따로 모양이 없어 cap이 아닌 둥근 모자 모양으로 보인다(`player.gd`의 headwear 분기).
- **저장**: 옛 옷장은 8개 필드 전체를 보내고 `accent`는 보내지 않는다. 부분 저장이므로 `accent`는 저장값이 유지된다.
  - 옛 캐릭터 버튼(여행자, 루, 미라, 테오)을 누르면 옛 id가 가고, 서버는 `m1`/`f1`로 매핑한다. 이것은 선택 완료로 치지 않는다.
  - 새 UI에서 고른 캐릭터(예: `m3`)도 옛 옷장에서 옛 버튼을 누르면 `m1`/`f1`로 바뀐다. 계약대로의 동작이다.
- **선택 완료 조건**: 옛 옷장은 받은 `character` 값을 그대로 다시 보낸다. 그래서 색만 바꿔 저장해도 마이그레이션된 계정에서는 `f1`이 간다.
  - 서버는 새 id(`m1`~`f4`)가 **`accent`와 함께 오거나**, 게임 버전 헤더 `x-villagen-version`이 **0.11.9 이상**일 때만 선택 완료로 친다.
  - 옛 옷장은 `accent`를 모르고 버전도 0.11.8 이하라서, 옛 게임에서 저장해도 새 게임의 선택 화면은 그대로 기다린다.
  - **새 선택 화면은 저장할 때 `accent`를 꼭 함께 보낸다**(0.11.9 게임은 버전 헤더로도 충족된다).
- `GET /v1/me`의 `catalog.characters`도 8종(`m1`~`f4`)이다. 옛 옷장은 이 목록이 아니라 자체 버튼 4개를 쓰므로 영향이 없다.

## 11. 오류

오류 본문은 `{"detail": "코드"}`이다.

| HTTP | `detail` | UI 처리 |
| --- | --- | --- |
| `401` | `login_required` 등 | 기존 로그인·세션 만료 흐름 |
| `422` | `invalid_request` | 값, 필드 이름, UUID, 버전 형식 확인. 재시도하지 않는다 |
| `409` | `stale_profile_version` | 최신 프로필을 다시 읽고 새 UUID로 저장 |
| `409` | `request_id_reused` | 성공한 UUID를 다른 본문에 다시 쓴 것. 새 UUID 사용 |
| `429` | `avatar_rate_limited` | `Retry-After`초 기다린 뒤 저장 |
