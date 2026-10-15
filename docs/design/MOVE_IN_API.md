# 주민 입주·퇴거 API (43·44)

단비(`shopkeeper`)가 플레이어별 집터 `danbi_plot`에 입주하고, 떠났다가 돌아와도 친밀도와 만남 기억을 유지하는 서버 계약이다. 구현은 `server/village_residents.py`에 있다. `server/multiplayer.py`와 게임 코드는 변경하지 않는다.

## 설정과 집터

| 환경 변수 | 기본값 | 의미 |
|---|---|---|
| `TRIPOTHON_RESIDENT_MOVES` | `off` | `on`, `1`, `true`일 때 입주 기능 활성화 |
| `TRIPOTHON_RESIDENT_ARRIVE_SECONDS` | `90` | 입주 준비 시간(초) |
| `TRIPOTHON_RESIDENT_LEAVE_SECONDS` | `90` | 퇴거 준비 시간(초) |

시간은 0~2,592,000초의 유한한 값만 허용한다. 0은 같은 트랜잭션에서 즉시 완료한다. 환경 변수는 서버 프로세스에 전달해야 한다. 배포 설정 및 실제 서버 활성화는 이번 작업에 포함하지 않는다.

`MOVERS`에서 주민의 `plot`, `home`, `old_home`을 정의하고 `PLOTS`에서 집터 중심·반경을 정의한다. 맵 세션은 이 두 자료를 함께 맞추면 된다. 현재 계약은 다음과 같다.

- 주민: `shopkeeper` / 단비
- 집터: `danbi_plot`, 집 실내: `danbi_house`, 기능을 끈 경우 기존 집: `13_shop`
- 맵 좌표 중심: `(-23.5, 9.0)`, 반경 5m
- 서버 가구 좌표 중심: `(9.5, -28.0)` — 맵 좌표에서 `Town.SPAWN=(-33,37)`을 뺀 값

활성화 중에는 집터가 비어 있어도 두 가구 배치 API에서 `409 plot_reserved`로 배치를 거절한다. 공방 배치에서 함께 이동하는 윗가구도 집터에 들어갈 수 없다. 입주 시 기존 저장의 집터 안 야외 가구와 그 위에 놓인 가구를 가방으로 돌려주고 배치 좌표·실내 배치 행·받침 연결을 지우며 오브젝트 버전을 한 번씩 올린다. 다른 실내 및 다른 플레이어의 가구는 대상이 아니다. 이미 운영 중인 집터 ID를 바꿀 때는 저장된 `plot`/`home`의 별도 마이그레이션이 필요하다.

## 조회

`GET /v1/village/residency` (동일한 별칭: `GET /v1/residents`)

기존 Bearer 인증이 필요하다. 방문 중이면 `host_for()`가 정한 마을 주인의 상태를 반환한다. 임의의 `host_id` 쿼리로 다른 계정을 읽을 수 없다. 응답은 래퍼 없이 다음 객체다.

```json
{
  "enabled": true,
  "host_id": "village-owner-id",
  "version": 7,
  "residents": [{
    "npc": "shopkeeper",
    "state": "home",
    "home": "danbi_house",
    "plot": "danbi_plot",
    "since": 1800000270.0,
    "due_at": null,
    "moves": 1,
    "legacy": false,
    "back": true,
    "hearts": 2,
    "friendship": {"points": 85, "gifts": 3, "level": 2, "next": 160},
    "memory": {"met": true, "first_met": 1800000000.0, "last_met": 1800000090.0}
  }],
  "plots": {"danbi_plot": "built"},
  "news": [{
    "id": "news-uuid",
    "npc": "shopkeeper",
    "kind": "returned",
    "at": 1800000270.0,
    "letter_id": "letter-uuid",
    "returned_to_bag": []
  }]
}
```

`/v1/me`에도 `residents` 필드로 동일한 구조를 추가한다. 이 필드는 방문 중이어도 **자기 계정의 마을**이다. 방문 마을은 별도 조회 API를 사용한다. presence 및 village payload는 변경하지 않았으므로 방문 화면은 진입 시와 필요한 갱신 시 별도 조회해야 한다.

`residents`는 이번 기능이 관리하는 주민만 담는 덮어쓰기 목록이다. 현재 단비 한 명이며, 나머지 주민의 고정 명단과 집은 기존 클라이언트 자료를 따른다.

| 주민 상태 | 집터 값 | 표시 계약 |
|---|---|---|
| `away` | `empty` | 주민 없음, 빈 집터 |
| `arriving` | `building` | 입주 준비, 아직 집 없음 |
| `home` | `built` | 주민과 집 있음 |
| `leaving` | `built` | 퇴거 준비 중이며 집 유지 |

`since`, `due_at`, `news.at`, 만남 시각은 Unix 초다. `due_at`은 준비 중일 때만 있다. 서버는 조회 시 도래한 전환을 처리하며, 완료 시각은 늦게 조회한 시간이 아닌 예약된 `due_at`이다. `/v1/me`, 거주 조회, 우편 조회·읽음 처리, 일회성 퀘스트와 일일 게시판 조회·변경에서도 전환을 반영한다. 백그라운드 타이머는 없다.

`moves`는 완료된 퇴거 횟수다. `back=true`이면 퇴거 후 돌아와 현재 거주 중이다. `memory.met=true`이면 처음 만난 인사를 다시 재생하지 않는다. 귀환 인사는 `back`과 마을/주민/귀환별 상태로 표시한다. `first_met`은 서버가 기록한 최초 만남, `last_met`은 마지막 인사다. 옛 저장에서 만남이 확인되면 기존 이야기의 시작·갱신 시각을 대체 시각으로 옮긴다. 선물/친밀도 이력만 있는 옛 저장은 `met=true`이지만 정확한 만남 시각은 `null`일 수 있다. 대화 전문을 저장하는 기능은 아니다.

`version`은 마을의 이사 상태가 바뀔 때 증가한다. 친밀도 변화, 인사, 소식의 7일 표시 기간 만료까지 나타내는 종합 버전은 아니므로 전체 응답을 버전만으로 생략하지 않는다. 읽을 전환이 없으면 쓰기 트랜잭션을 열지 않는다.

## 스토리 세션 계약

통합 서버는 기존 이야기의 후일담 이벤트 `forest_told`, `forest_gate`를 보존하고 `danbi_rescued`를 연결한다. 저장 형식은 `story_events(user_id,event,at)`이며, 이전 입주 브랜치가 만든 `created` 열은 시작 시 `at`으로 이름을 바꾸어 값을 보존한다. 이벤트는 `first_gift`가 `done`인 뒤에만 기록할 수 있고, 이야기 연습용 `reset`은 이벤트를 지운다. 거주 상태와 영구 친분 기록은 별도 저장되어 초기화되지 않는다.

1. 숲 이야기 안내 완료: `forest_told`
2. 숲 입구 진행: `forest_gate` (`forest_told` 필요)
3. 단비 구출 완료: `danbi_rescued` (`forest_gate` 필요)

각 단계에서 기존 변경 API에 다음 형태를 전송한다. 재시도할 때는 같은 UUID를 사용한다.

```http
POST /v1/story/step
Authorization: Bearer <session>
Content-Type: application/json

{"request_id":"<uuid>","action":"event","event":"danbi_rescued"}
```

응답의 `story.events`와 `GET /v1/story`, `/v1/me`의 `story.events`에 저장된 이벤트 목록이 나온다. 집 상태는 별도 거주 조회나 `/v1/me`로 읽는다. 첫 이야기가 끝나지 않았으면 `409 story_not_done`, 선행 이벤트가 없으면 `409 story_event_order`, 이벤트 누락은 `422 story_event_required`, 알 수 없는 이벤트는 `422 unknown_story_event`다. 방문 중 기록은 `409 story_own_village_only`로 거절한다. 기존 이야기 행이 없는 계정은 원래와 같이 `404 story_not_started`다.

구출 기록과 입주 예약은 같은 트랜잭션이다. 같은 request ID의 재시도는 기존 응답을 돌려주며, 새 request ID로 같은 이벤트를 보내도 플래그·편지·소식은 중복 생성하지 않는다. 이미 나간 단비를 구출 이벤트 재전송으로 다시 입주시키지 않는다. 재입주는 운영자 동작이다. 기능을 끈 동안 기록한 구출은 기능 활성화 후 첫 조회부터 입주 준비를 시작한다.

이 API는 기존 스토리처럼 클라이언트가 완료한 장면을 보고하는 계약이다. 서버는 이벤트 순서·계정·방문 상태를 검사하지만 숲 장면의 위치나 전투 성공을 검증하지 않는다. 스토리 세션에서 실제 구출 장면 완료 시 호출해야 한다.

기존 `action:greet, npc:shopkeeper`도 서버 만남 기억을 기록한다. 구출 자체도 단비와의 만남으로 기록한다. 이야기의 `greeted` 목록, 친밀도, 선물·기존 편지는 이사로 초기화하지 않는다. 이야기 `reset`은 장면용 `greeted`, 후일담 이벤트와 상점 해금 플래그를 초기화하고 카페 테라스 선물을 가방으로 돌려준다. 그 전에 만남 기억을 옮겨 영구 친밀도·만남 기록·거주 상태·기존 편지를 보존한다.

## 우편과 게시판

완료된 입주·퇴거마다 `npc_letters.dispatch`를 통해 기존 `npc_letters`에 편지 한 통, `npc_letter_events`에 이벤트 한 건, `village_news`에 소식 한 건을 같은 트랜잭션으로 기록한다. 준비 시작도 `arriving`/`leaving` 소식을 남기지만 편지는 완료 때만 생성한다. 이벤트 종류와 `residency:<퇴거 횟수>` 키가 중복 전달을 막고, 소식은 동일 편지 ID를 참조한다.

`GET /v1/letters`와 기존 `/v1/letters/read`를 그대로 사용한다. 이사 편지에는 다음 필드를 추가하며, 부탁 편지의 `quest`나 이야기 편지의 `story`는 붙지 않는다.

```json
{
  "npc": "shopkeeper", "name": "단비", "level": 0,
  "move": {"kind": "back", "npc": "shopkeeper"},
  "event": {
    "type": "move_in", "key": "residency:1",
    "payload": {"kind": "back", "home": "danbi_house", "plot": "danbi_plot", "moves": 1}
  }
}
```

`move.kind`: `in`(첫 입주), `out`(퇴거), `back`(귀환). 이벤트 종류는 입주·귀환 `move_in`, 퇴거 `move_out`이다. 기존 편지의 `id`, `created`, `read`, `gift`, `personality`도 유지한다. 신규 이사 편지는 부탁 완료·기념일 편지와 함께 DB 내부 level 1,000,000 이상을 사용하며 주민별 다음 빈 번호를 배정한다. 하트 1~4, 이야기 0 이하, 기존 부탁 100과 충돌하지 않는다. 이전 입주 브랜치의 level 200 이상 편지도 기존 `move` 형식으로 계속 읽는다. 클라이언트는 표시용 `level=0`이 아니라 `move` 필드로 이사 편지를 판별해야 한다.

마을 이사 소식은 `news`로 제공하며, 최근 7일 소식 최대 5개를 최신순으로 반환한다. 같은 시각은 기록 순서의 역순이다. DB의 전체 이력은 삭제하지 않는다. 일일 부탁 게시판은 별도로 `GET /v1/quest_board`와 `POST /v1/quest_board/{day}/{quest_id}/{accept|progress|complete}`를 사용한다. KST 자정에 부탁 5개가 순환하고 계정·날짜별 최대 3개를 수락·완료한다. 일회성 `/v1/quests` 진행과 일일 게시판 진행은 따로 저장된다. 전체 통합 경로는 [생활 서버 통합 문서](LIFE_SERVER_MERGE_KO.md)를 참고한다.

| `news.kind` | 권장 표시 |
|---|---|
| `arriving` | 단비가 곧 이사 와요 |
| `moved_in` | 단비가 이사 왔어요 |
| `leaving` | 단비가 이사를 준비해요 |
| `moved_out` | 단비가 이사를 갔어요 |
| `returned` | 단비가 다시 돌아왔어요 |

`news.id`로 표시 중복을 제거하고, `letter_id`로 해당 편지를 연결한다. `returned_to_bag`는 입주 때 가방으로 돌려준 가구 ID 목록이다. 비어 있지 않으면 가구가 가방으로 돌아갔다는 안내를 덧붙일 수 있다.

## 기존 저장·친분·선물

테이블은 `CREATE TABLE IF NOT EXISTS`로 추가한다. 기존 거주 행은 덮어쓰지 않는다. 처음 기능을 적용할 때 구출 기록이 없고 `first_gift`가 없거나 `done`인 계정은 `home, legacy=true`로 시작한다. 마이그레이션 편지·소식은 만들지 않는다. 집터와 충돌하는 가구는 가방으로 돌려준다. 진행 중인 계정은 `away`에서 시작한다. 이미 구출 플래그가 있으면 첫 입주를 예약한다.

기능을 끄면 `enabled=false`, 단비는 `home/13_shop`, 집터는 `empty`, 소식은 빈 목록이다. 기존 거주·친분 행은 삭제하지 않으며 전환을 처리하지 않는다. 다시 켜면 저장된 예약을 처리한다.

퇴거·귀환은 `npc_friendship`, `npc_gifts`, 기존 편지를 삭제하거나 하트·선물 횟수를 초기화하지 않는다. `npc_conversation_memory`는 `(host_id,npc_id)`로 따로 보관한다. 선물 오브젝트의 소유권과 `gifted` 상태도 보존한다. 퇴거 때 선물을 `stored`로 바꾸고 슬롯을 해제하며, 귀환 때 새 `home_id`와 `fresh=1`을 적용한다.

단비의 새로운 선물 수신 UI와 `danbi_house`의 실내 가구 슬롯 좌표는 맵/클라이언트 후속 계약이다. 이번 변경은 기존 수신 주민 목록을 늘리지 않는다. 새 집의 슬롯이 아직 없으면 기존 선물을 안전하게 보관한다. 슬롯이 정의된 집은 귀환 시 기존 배치 타이머로 다시 배치한다. 슬롯 확정 전 임의 좌표로 가구를 놓지 않는다.

단비가 `away`/`arriving`이면 일회성 부탁과 일일 게시판의 `danbi_home` 부탁은 잠기며, 이미 수락한 부탁도 진행·완료 API를 사용할 수 없다. 기존 진행 데이터는 보존하여 입주 후 이어 간다. 일일 부탁은 해당 KST 날짜가 지나면 만료된다. 완료된 부탁의 보상은 재지급하지 않는다.

## 운영자 동작

플레이어가 임의로 주민을 내보내는 HTTP API는 제공하지 않는다. 아래 명령은 기존 로컬 DB에 적용하는 운영자 도구이며, 이번 작업에서 운영 DB에는 실행하지 않았다.

```text
python -m server.admin_cli residents USERNAME show --data-dir PATH
python -m server.admin_cli residents USERNAME move-in shopkeeper --data-dir PATH
python -m server.admin_cli residents USERNAME move-out shopkeeper --data-dir PATH
```

설정값을 서버와 동일하게 전달해야 한다. 기능이 꺼져 있으면 move 명령은 거절한다. 같은 상태에서 같은 명령을 반복해도 예약·알림은 늘어나지 않는다. 전환은 `away → arriving → home → leaving → away`이고, 시연용 즉시 전환은 두 지연 설정을 0으로 둔다. 전체 거주 이력을 지우는 reset 명령은 제공하지 않는다.

서버 내부 호출은 `arrive(conn, host, npc, now, settings, reason)` / `leave(...)`이다. 호출자는 쓰기 트랜잭션을 소유해야 한다. API의 지연 전환은 SQLite `BEGIN IMMEDIATE` 아래 처리되어 동시 조회에서도 편지·이벤트가 한 번만 생성된다. 트랜잭션 실패 시 상태·가구·알림이 함께 롤백된다.

## 검증

`server/tests/test_village_residents.py`는 기능 끄기, 구출 선행 조건, 90초 경계, 중복 요청, 편지 읽음 처리, 귀환 시 하트·만남·선물 보존, 기존 저장 업그레이드 및 재시작, 집터의 쌓인 가구 반환·배치 금지, 방문자 격리, 부탁 잠금, 동시 조회와 롤백, 운영자 명령, 0초 전환, 설정 검증, 소식 기간, 집터 자료 변경을 검사한다. `test_npc_letters.py`는 이전 이사·하트·이야기·부탁 편지와 신규 귀환·기념일 편지가 한 우편함에서 함께 보존되는 경우 및 읽음 처리의 원자성을 검사한다.

전체 회귀 명령:

```text
C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe -m pytest server/tests -q --basetemp=.codex-tmppytest -p no:cacheprovider
```

현재 통합 서버의 전체 테스트 결과는 [생활 서버 통합 문서](LIFE_SERVER_MERGE_KO.md)에 기록한다. 이전 입주 브랜치의 별도 검증 복사본에서 나온 1,147개 통과 기록은 현재 통합 결과가 아니다. 실제 맵의 집 생성·소멸, 게시판 문구, 귀환 인사 렌더링은 후속 클라이언트 통합에서 확인해야 한다.
