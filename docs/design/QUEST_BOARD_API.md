# 마을 부탁 게시판 API

주민의 기존 부탁(`server/quests.py`의 `QUESTS`)을 매일 게시판에서 골라 수행한다. 일회성 주민 부탁 `/v1/quests`와 진행 기록은 별도이며, 조건·아이템 소비·보상 계산을 공유한다. 모든 API에 `Authorization: Bearer <token>`이 필요하다.

## 운영 규칙

- 서버 기준 **한국 시간(Asia/Seoul) 00:00**에 게시물 5개가 교체된다. 모든 계정에 같은 목록을 제공하며 19일 동안 모든 기존 부탁이 순환한다.
- 계정별 하루 수락 **3개**, 완료 **3개**까지다. 수락 취소나 다른 부탁으로 교체하는 기능은 없다. 이미 수락한 부탁을 다시 수락해도 횟수는 늘지 않는다.
- 미완료 부탁은 자정에 만료된다. 지난 날짜의 새로운 변경 요청은 `409 quest_board_expired`다. 이전 진행 기록은 보존되지만 이월되지 않는다.
- `X-Villagen-UTC-Offset` 헤더나 테스터 시간 재정의로 게시판 날짜·한도를 바꿀 수 없다. 밤 방문 조건은 기존 부탁처럼 실제 서버 시각과 플레이어 시간대 헤더로 판단한다.
- 시작 스토리 잠금과 자기 마을 제한은 기존 부탁과 같다. 다른 사람 마을에서 수락·진행 보고·완료할 수 없다. 조회에는 presence 등록이 필요 없다.
- 보상은 기존 부탁별 기본 3~8 별씨앗과 `TRIPOTHON_QUEST_STARS_SCALE`을 그대로 사용한다. 제작이 필요한 부탁은 기존 20개 상한을 적용한다. 배율 0이면 보상 없이 완료·감사 편지는 가능하다. 새로운 보상 아이템이나 편지 첨부 보상은 없다.
- 완료는 조건 확인, 가져온 아이템 소비, `economy.py`를 통한 별씨앗 지급, 진행 저장, NPC 편지 발송을 한 트랜잭션으로 처리한다. 어느 단계든 실패하면 전부 되돌린다.

## 목록 조회

`GET /v1/quest_board`

응답 예시(목록 중 한 항목만 표시):

```json
{
  "board": {
    "day": "2027-02-01",
    "timezone": "Asia/Seoul",
    "resets_at": 1801494000,
    "unlocked": true,
    "scale": 1.0,
    "limits": {"accept": 3, "complete": 3},
    "accepted": 1,
    "completed": 0,
    "remaining_accepts": 2,
    "remaining_completions": 3,
    "list": [
      {
        "id": "moka_pie",
        "npc": "regular",
        "kind": "bring",
        "day": "2027-02-01",
        "need": 3,
        "have": 3,
        "stars": 8,
        "letter": true,
        "craft": false,
        "night": false,
        "items": ["apple"],
        "state": "ready",
        "accepted": 1801450800
      }
    ]
  }
}
```

`day`와 `id`를 함께 게시물 키로 사용한다. `resets_at`은 다음 교체 시각의 Unix 초다. `state`는 `locked / available / active / ready / done`이다. 잠금이 다시 걸리면 `unlocked`도 확인해야 한다. 기존 부탁과 마찬가지로 완료된 항목에는 `completed`와 실제 지급된 `stars`가 내려온다.

`kind`별 조건과 필드는 기존 `/v1/quests`와 같다.

| kind | 완료 조건 / 추가 필드 |
| --- | --- |
| `bring` | `items` 중 합계 `need`개를 보유. 완료 시 실제로 차감한다. |
| `visit` | 허용 `places` 중 필요한 장소를 방문. `visited`로 진행 표시. 서로 다른 보고 사이 최소 3초. |
| `talk` | `places`의 지정 주민에게 전달했다고 보고. |
| `outfit` | 수락 시점의 프로필 `since` 버전 이후 외모 변경. |
| `catch` | 수락 당시 `since` 어종 기록보다 새로 잡은 종류 수. |
| `gift` | 수락 이후 NPC에게 선물한 기록. 특정 주민은 `to`로 표시하며 장난감 조건도 서버가 확인. |
| `light` | 자신의 마을에 빛나는 가구 배치. |
| `arrange` | 수락 이후 자신의 집 가구를 새로 배치하거나 이동. |

## 수락

`POST /v1/quest_board/{day}/{quest_id}/accept`

```json
{"request_id": "d9db9beb-89b4-4c6a-8ea7-64768fed833b"}
```

방문형 부탁을 해당 장소에서 받았다면 선택 필드 `"place": "observatory"` 등을 함께 보낼 수 있다. 허용된 장소와 밤 조건을 충족하면 즉시 방문으로 계산한다. 응답은 `{"quest": <현재 항목>, "board": <갱신한 전체 게시판>}`이다.

## 방문·대화 보고

`POST /v1/quest_board/{day}/{quest_id}/progress`

```json
{"request_id": "a27d9690-615b-421d-8c6d-f43d8af254a5", "place": "square"}
```

`visit / talk`에만 사용한다. 보유품·낚시·외모·선물·가구 조건은 서버 저장 자료에서 계산하므로 진행량을 보내지 않는다. 응답 형식은 수락과 같다.

## 완료

`POST /v1/quest_board/{day}/{quest_id}/complete`

```json
{"request_id": "00a4d731-9c37-40b6-a822-e69e0f6f1be1"}
```

응답은 다음 필드를 포함한다.

```json
{
  "quest": {"id": "moka_pie", "state": "done"},
  "board": {"completed": 1, "remaining_completions": 2},
  "stars": 8,
  "shards": 108,
  "taken": {"apple": 3},
  "homestead": {},
  "letters": [
    {
      "id": "a225f665-61cb-49d7-a5d5-fd3c4fa954e5",
      "npc": "regular",
      "name": "모카",
      "level": 0,
      "read": false,
      "gift": null,
      "quest": {"npc": "regular"},
      "event": {
        "type": "request_done",
        "key": "2027-02-01:moka_pie",
        "payload": {"quest_id": "moka_pie", "day": "2027-02-01"}
      }
    }
  ]
}
```

위 예시는 일부 필드를 생략했다. 실제 `quest / board / homestead`에는 각각 기존 전체 응답이 들어간다. `taken / homestead`는 `bring`에만 있다. `shards`는 지급 후 전체 별씨앗 잔액이다. 모든 게시판 부탁은 기존 우편함에 감사 편지 한 통을 보낸다.

## 재시도와 오류

변경 요청의 `request_id`는 UUID이며 한 계정의 모든 변경 API에서 공유한다. 응답을 잃었을 때는 **같은 경로·같은 본문·같은 UUID**로 재전송한다. 저장된 응답을 그대로 반환하고 아이템·별씨앗·편지·횟수를 다시 처리하지 않는다. 같은 UUID를 다른 동작·날짜·본문에 쓰면 `409 request_id_reused`다. 실패한 요청은 UUID를 소비하지 않는다.

자정 후에도 이미 성공했던 요청의 정확한 재전송은 과거 응답을 반환한다. 이 응답으로 오늘의 UI를 덮지 말고 `GET /v1/quest_board`로 다시 조회한다. 새로운 UUID로 완료된 부탁을 재완료하면 `409 quest_already_done`이다. 동시 요청에도 한도와 단일 지급이 보장된다.

| HTTP | detail | 클라이언트 처리 |
| --- | --- | --- |
| 401 | `login_required / session_expired` | 재로그인 |
| 404 | `quest_not_found / quest_board_not_offered` | 목록 다시 조회 |
| 409 | `quest_board_expired` | 날짜 교체 후 목록 다시 조회 |
| 409 | `quests_locked / quest_own_village_only` | 스토리 조건 또는 자기 마을로 복귀 안내 |
| 409 | `quest_not_active / quest_not_ready / quest_already_done` | 서버 상태로 UI 갱신 |
| 409 | `quest_not_night / quest_wrong_kind` | 실제 밤 조건 또는 요청 종류 확인 |
| 409 | `request_id_reused` | 새 사용자 동작에 새 UUID 사용 |
| 422 | `invalid_request / quest_bad_place` | 잘못된 UUID·필드·장소 수정 |
| 429 | `quest_board_daily_limit` | 다음 교체 시각 안내 |
| 429 | `quest_too_fast` | 장소 보고 간격 준수 |

## 클라이언트 연결

게시판을 열 때 조회하고, 변경 성공 응답으로 해당 부탁·보유품·잔액·횟수를 갱신한다. `remaining_accepts=0`이면 새 수락 버튼을 비활성화한다. 목록의 `npc / id`에 기존 주민 이름·부탁 번역을 연결하고 `ready`일 때 완료 버튼을 제공한다. 자정(`resets_at`) 또는 앱 복귀 시 목록을 새로 읽는다.

편지는 기존 `GET /v1/letters` 및 `POST /v1/letters/read`로 조회·읽음 처리한다. `event.type`에 맞는 감사/기념일/이사 문구를 연결하고 `level=0`만으로 스토리 편지로 분류하지 않는다. 기념일 일정, 이벤트 중복 방지 및 입주·퇴거 후속 구현 훅은 [NPC_LETTERS_API.md](NPC_LETTERS_API.md)에 명시했다. 플레이어 간 편지 발송 API는 없다.

테스터·운영자용 표시 시각 설정은 [TIME_OVERRIDE_API.md](TIME_OVERRIDE_API.md)의 `GET/POST /v1/dev/time_override`를 사용한다. 이 설정은 하늘·조명에만 적용하며 게시판 날짜나 보상 시각은 바꾸지 않는다.
