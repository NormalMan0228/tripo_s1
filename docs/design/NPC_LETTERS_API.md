# NPC 이벤트 편지 API

마을 주민이 부탁 완료·기념일 등의 사건에 맞춰 기존 우편함으로 편지를 보낸다. 플레이어 간 편지 전송 API는 없다. 이벤트 편지는 별씨앗, 물건, 친밀도 보상을 추가하지 않는다.

## 조회 및 읽음 처리

기존 인증 방식과 엔드포인트를 그대로 사용한다.

- `GET /v1/letters`: 본인의 최근 편지 최대 50통과 전체 미확인 수를 반환한다. 최신 편지가 먼저 나온다.
- `POST /v1/letters/read`: `{"request_id":"UUID","ids":["편지 UUID"]}`로 해당 편지만 읽음 처리한다. `ids`를 비우거나 생략하면 본인의 모든 편지를 읽음 처리한다. 다른 사람의 편지 ID는 무시된다. 동일 `request_id` 재시도는 기존 응답을 재사용한다.
- `GET /v1/me`: 기존 `npc_letters_unread` 필드로 우편함 알림을 표시한다. 방문 presence 없이도 조회할 수 있다.

`GET /v1/letters`, `GET /v1/me`의 미확인 수 조회, `POST /v1/letters/read`가 해당 날짜의 주민 기념일 편지 발송을 확인한다. 전체 읽음 요청은 그 시점에 도착하는 기념일 편지도 포함한다.

```json
{
  "letters": [
    {
      "id": "11111111-2222-4333-8444-555555555555",
      "npc": "naru",
      "name": "나루",
      "personality": "cheerful",
      "level": 0,
      "created": 1801450800.0,
      "read": false,
      "gift": null,
      "quest": {"npc": "naru"},
      "event": {
        "type": "request_done",
        "key": "2027-02-01:naru_islands",
        "payload": {"quest_id": "naru_islands", "day": "2027-02-01"}
      }
    }
  ],
  "unread": 1
}
```

`event`가 있는 편지는 `event.type`으로 문안을 선택한다. 새 이벤트의 `level`은 항상 0이며 `gift`는 `null`이다. `request_done`은 기존 부탁 편지 클라이언트를 위해 `quest.npc`도 제공한다. `event.payload`를 별도 객체로 유지하므로 본문 데이터가 `type`이나 `key`를 덮어쓰지 않는다.

기존 하트 편지(`level` 1~4), 스토리 편지(`story`), 기존 일회성 부탁 편지(`quest`)에는 `event`를 추가하지 않는다. 저장된 선물과 읽음 상태도 유지한다. 클라이언트는 `event`가 없으면 기존 표시 규칙을 사용한다.

## 이벤트 종류

| `event.type` | 발송 시점 | 중복 방지 `key` | `payload` |
| --- | --- | --- | --- |
| `request_done` | 마을 게시판 부탁 완료 트랜잭션 | `YYYY-MM-DD:quest_id` | `quest_id`, `day` |
| `resident_day` | 해당 주민의 기념일에 우편함/미확인 수 확인 | `YYYY-MM-DD` | `date`, `occasion: "village_anniversary"` |
| `move_in` | 향후 입주 확정 작업에서 연결할 훅 | 영속 입주 사건 ID | 입주 구현에서 정하는 표시용 정보 |
| `move_out` | 향후 퇴거 확정 작업에서 연결할 훅 | 영속 퇴거 사건 ID | 퇴거 구현에서 정하는 표시용 정보 |

기념일은 캐릭터의 실제 생일 설정이 아니라 이번 서버 기능의 마을 기념일 일정이다. 매일 서버의 **KST(UTC+09:00) 자정** 기준으로 해당 여부를 확인한다. 계정의 시간대 헤더, 계정 일일 기준, 데모 시간대 override는 영향을 주지 않는다. 해당 날짜에 주민별 1통을 보낸다. 지나간 날짜를 소급 발송하지 않으며, 다음 해의 같은 날짜에는 새 편지를 보낸다.

| 주민 | 기념일 | 주민 | 기념일 |
| --- | --- | --- | --- |
| 나루 `naru` | 01-09 | 바우 `scout` | 02-06 |
| 소라 `sora` | 03-12 | 윤재 `gentleman` | 04-08 |
| 가람 `poet` | 05-14 | 모루 `moru` | 06-10 |
| 노을 `lamplighter` | 07-07 | 해루 `haeru` | 08-11 |
| 새벽 `stroller` | 09-16 | 다온 `postman` | 10-09 |
| 미소 `sweeper` | 10-25 | 보람 `fisher` | 11-13 |
| 콩이 `kid` | 12-18 | | |

## 서버 내부 훅과 입주 작업 인계

`server.npc_letters.dispatch(conn, user_id, npc, event, event_key, now, payload=None)`는 생성되거나 기존에 존재하는 편지 UUID 문자열을 반환한다. 등록된 주민만 허용한다. 호출자는 반드시 쓰기 트랜잭션을 열어야 한다. 스키마는 `NpcHomes` 초기화 시 기존 우편함 다음에 생성되므로 모든 조회와 게시판 완료 전에 준비된다.

입주·퇴거 구현에서는 실제 거주 상태 변경이 성공하는 **동일 트랜잭션 안에서** 이 함수를 호출한다. 재시도할 때 새 HTTP `request_id` 대신 동일한 영속 사건 ID를 `event_key`로 전달한다. 한 거주 회차 ID를 입주·퇴거 양쪽에 써도 이벤트 종류가 달라 각각 한 통씩 생성된다. 같은 주민의 재입주는 새 거주 회차 ID가 필요하다. 주민 삭제보다 먼저 퇴거 편지를 생성하고, 우편함의 주민 ID와 발신자 표시 정보를 계속 해석할 수 있게 유지해야 한다. 현재 입주 상태 변경 API나 자동 입주/퇴거 동작은 추가하지 않는다.

```python
with db.transaction() as conn:
    # 실제 입주 상태 변경과 거주 회차 저장을 먼저 수행한다.
    letter_id = npc_letters.dispatch(
        conn, user_id, npc_id, "move_in", residency_id, now,
        {"home_id": home_id},
    )
```

동일 `(계정, 주민, event, event_key)`는 편지 ID·발송 시각·첫 payload·읽음 상태를 재사용한다. 요청 완료가 롤백되면 편지도 함께 롤백된다. 동시 요청은 기존 SQLite 쓰기 트랜잭션 직렬화와 유일 제약으로 중복을 막는다.

편지 본문과 읽음 상태는 기존 `npc_letters`에 저장하고, 이벤트 구분만 `npc_letter_events`에 연결한다. 기존 `UNIQUE(host_id,npc_id,level)`을 보존하기 위해 새 이벤트의 내부 level은 1,000,000 이상에서 주민별로 증가한다. 이 내부 수치는 클라이언트에 노출하지 않는다. 신규 보상 지급 경로는 없다.
