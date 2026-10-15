# 마을 생활 서버 통합 계약

`codex/lifesrv`에서 이야기·일일 의뢰 게시판·NPC 편지(`storysrv`), 주민 입주·퇴거와 친분 유지(`movein43`), 상점·건물 서비스(`shops`)를 함께 제공한다. 기준은 0.11.8 후보 `e2edb75`이며, 상점 변경은 제공된 `.codex-shops.patch`를 현재 코드에 수동 통합했다. 게임 코드와 `server/multiplayer.py`는 변경하지 않았다.

이 문서는 세 기능을 함께 사용하는 클라이언트의 기준이다. `NPC_INTERACTIONS_KO.md`는 원본 상점 패치의 계약을 그대로 보존한 자료이며, 그 문서의 “단비 이주 플래그”와 실제 거주 상태의 관계는 아래 설명을 따른다.

## 충돌과 해결

| 충돌 | 통합 결과 |
|---|---|
| `asset_studio.py` 가구 배치에서 건축 규칙과 입주 집터 예약 검사가 충돌 | 기존 건축 규칙을 유지하면서 주민 이사가 켜진 경우 예약 집터를 검사한다. 받침과 함께 이동하는 윗가구도 검사하고, 입주로 집터를 비울 때 쌓인 가구와 부착 정보를 함께 회수해 공중 가구·중복 버전 증가를 막는다. |
| `npc_homes.py`의 편지 발신자 및 편지 조회 준비가 충돌 | 양쪽 발신자 정보와 이사 편지 호환 형식을 유지한다. 편지 조회는 이사 정산과 기념일 편지 생성을 모두 수행한다. 읽음 처리도 같은 트랜잭션에서 도래한 이사를 정산한다. |
| `story.py`의 import, `EVENTS`, `event` 필드와 처리 분기가 중복 | 건축 규칙과 주민 기억 처리를 모두 유지하고 이벤트 분기·필드·상수를 각각 하나로 합쳤다. `forest_told`, `forest_gate` 에필로그에 `danbi_rescued`를 순서대로 연결한다. |
| `story_events` 시각 컬럼이 `at`/`created`로 갈림 | 기존 에필로그의 `at`를 표준으로 유지한다. 이주 브랜치의 `created` 저장은 서버 시작 및 관련 운영자 명령에서 `at`로 한 번만 이름을 바꾼다. 이벤트와 시각은 보존한다. 같은 시각에는 기록 순서를 유지한다. |
| 새 계정의 첫 선물 완료를 기존 완료 계정으로 잘못 분류할 가능성 | 선물 처리에서 이야기 단계를 `done`으로 바꾸기 전에 거주 행을 초기화한다. 새 계정은 구조 전까지 `away`, 기존 완료 저장은 호환용 `home`을 유지한다. |
| 이사 편지가 기존 편지함에 직접 쓰이고 공통 이벤트 훅이 빠짐 | 입주·귀환은 `npc_letters.dispatch(..., 'move_in', ...)`, 퇴거는 `move_out`을 사용한다. 상태·편지·소식이 함께 커밋되며 `village_news.letter_id`가 같은 편지를 가리킨다. 재조회·재시도·롤백에서 중복하지 않는다. |
| 편지 `level`과 메타데이터가 기능별로 겹칠 위험 | 하트 1~4, 이야기 0 이하, 이전 부탁 100, 이전 이사 200대의 읽기 호환성을 보존한다. 새 이벤트 편지는 1,000,000 이상을 할당하고 `npc_letter_events`의 종류·키로 구분한다. 기존 `move`, `quest`, `story` 응답을 유지한다. |
| 일일 게시판은 퇴거 주민의 의뢰를 계속 허용 | 게시판 조회·변경에서 이사를 정산하고 기존 부탁과 같은 부재 검사를 적용한다. `away`/`arriving` 동안 단비 의뢰가 잠기고, 재입주 후 기존 수락·진행·친밀도를 이어 간다. |
| 상점·생활 API가 같은 재고와 잎전 잔액을 변경 | `homesteads.state`를 공유하고 `version`으로 오래된 요청을 거절한다. 기존 생활 API의 구매·판매·납품은 공통 상점 처리로 위임한다. `bag`, `order_day`, 판매 별씨 누적값은 의도적으로 공유하고 `shop_effects`만 새 키로 추가한다. |
| 퀘스트 보상과 상점 거래의 통화·재시도 충돌 | 별씨는 `economy.change_shards`, 잎전은 `economy.change_coins`만 변경한다. 퀘스트·상점·기존 생활 거래가 공통 `mutate`와 요청 저장소를 사용한다. 운영자 테스트 계정 초기 지급도 공통 별씨 함수로 정리했다. |

상점 신규 파일 `shop_catalog.py`, `shops.py`, `test_shops.py`와 `NPC_INTERACTIONS_KO.md`는 패치 본문 그대로 추가했다. `app.py`는 각 기능을 한 번씩 등록하고, 전체 앱의 HTTP 메서드·경로 중복을 회귀 테스트로 검사한다. `story_events`, `story_flags`, 거주·대화 기억·소식, 게시판 진행, 이벤트 편지, 상점 이용량, 잎전 원장은 서로 다른 테이블이며 `CREATE TABLE IF NOT EXISTS`로 초기화한다.

## 이야기·거주·상점의 관계

이야기는 `letter → cafe → craft → done`을 유지한다. `action: "event"`는 이야기 완료 후 자기 마을에서만 허용하며 순서는 `forest_told → forest_gate → danbi_rescued`다. 완료 전에는 `409 story_not_done`, 선행 이벤트 누락은 `409 story_event_order`, 이벤트 누락은 `422 story_event_required`, 미등록 이벤트는 `422 unknown_story_event`다. 이미 기록한 이벤트를 다시 보내도 추가 입주나 편지는 발생하지 않는다.

`danbi_rescued`는 입주 예약과 만남 기억을 같은 트랜잭션에서 기록한다. 입주 기능은 `TRIPOTHON_RESIDENT_MOVES=on`일 때 활성화하며 기본은 `off`다. 거주 전환은 `away → arriving → home → leaving → away`이며 입주·퇴거 대기시간 기본값은 각각 90초다. 퇴거해도 친밀도·선물·대화 기억·편지를 지우지 않는다. 재입주는 운영자 명령으로 시작하며, 구조 이벤트 재전송은 퇴거한 주민을 다시 부르지 않는다.

상점 패치의 `story.flags.danbi_moved_in`은 **모카의 첫 선물 완료로 얻는 상점 개방 권한**이다. 실제 거주 상태와 별도로 저장하며, `general_store.open`은 이 권한을 따른다. 따라서 구조 전·입주 준비 중·퇴거 후에도 이미 얻은 개점 권한은 유지된다. 상점 건물은 `13_shop`, 입주 집은 `danbi_house`로 구분한다. NPC와 집의 노출은 거주 API, 거래 가능 여부는 상점 API를 기준으로 판단한다. 기존 완료 저장에도 개점 권한을 한 번만 보완한다.

운영자의 이야기 `reset`은 에필로그 이벤트와 상점 권한을 지우고 테라스 선물을 가방으로 돌려준다. 거주 행·친밀도·영구 대화 기억·기존 편지는 보존한다. 이후 첫 선물을 다시 완료하면 상점 권한을 다시 얻는다.

## 통합 엔드포인트

모든 아래 API는 기존 Bearer 세션을 사용한다. 게임 상태를 변경하는 POST에는 UUID `request_id`가 필요하다. 표시 시간 설정은 예외로 `time_override`만 전달하며 동일 값 재설정 자체가 멱등이다.

| 메서드 | 경로 | 클라이언트 용도·주요 계약 |
|---|---|---|
| GET | `/v1/me` | 자기 계정의 `story`, `quests`, `residents`, 미읽음 편지 등 통합 상태 |
| GET | `/v1/story` | 이야기 단계·인사·`events`·`flags` |
| POST | `/v1/story/step` | `read_letter`, `accept`, `greet`, `event` |
| POST | `/v1/story/gift` | `object_id`, `version`으로 첫 선물 전달·테라스 배치·감사 편지·상점 해금 |
| GET | `/v1/village/residency` | 현재 방문 마을 또는 자기 마을의 거주·집터·최근 소식 |
| GET | `/v1/residents` | 거주 조회의 동일한 별칭 |
| GET | `/v1/quests` | 기존 주민별 일회성 부탁 |
| POST | `/v1/quests/{quest_id}/accept` | 기존 부탁 수락 |
| POST | `/v1/quests/{quest_id}/progress` | 방문·대화형 부탁 진행 |
| POST | `/v1/quests/{quest_id}/complete` | 기존 부탁 완료·보상·편지 |
| GET | `/v1/quest_board` | 한국 시간 기준 일일 의뢰 5개·수락/완료 한도 각 3개 |
| POST | `/v1/quest_board/{day}/{quest_id}/accept` | 그날 의뢰 수락; `day`는 응답의 `YYYY-MM-DD` |
| POST | `/v1/quest_board/{day}/{quest_id}/progress` | 방문·대화형 일일 의뢰 진행 |
| POST | `/v1/quest_board/{day}/{quest_id}/complete` | 재료 차감·별씨 지급·이벤트 편지를 원자적으로 처리 |
| GET | `/v1/letters` | 자기 계정의 하트·이야기·의뢰·기념일·이사 편지 |
| POST | `/v1/letters/read` | `ids`의 편지 읽음 처리; 빈 목록이면 모두 읽음 |
| GET | `/v1/npcs/{npc_id}/gift` | 기존 선물 가능 주민의 취향·친밀도 |
| POST | `/v1/npcs/{npc_id}/gift` | 기존 선물·친밀도·답장 처리 |
| GET | `/v1/social/npc-homes/{home_id}` | 방문 권한에 따른 주민 집의 배치·보관 상태 |
| GET | `/v1/shops/{shop_id}` | 개점 여부·품목·가격·잔여 한도·공통 생활 버전 |
| POST | `/v1/shops/{shop_id}/buy` | `version`, `item`, `quantity`로 구매 |
| POST | `/v1/shops/{shop_id}/sell` | 같은 형식으로 판매; 기존 판매 별씨 한도 공유 |
| POST | `/v1/shops/{shop_id}/service` | `version`, `service`와 서비스에 필요한 `item`, `quantity` |
| GET | `/v1/homestead` | 상점과 공유하는 잎전·재고·생활 버전 |
| POST | `/v1/homestead` | 기존 생활 액션 유지; `buy`/`sell`/`order`는 공통 상점 처리 |
| GET, POST | `/v1/dev/time_override` | 테스터·관리자의 표시 시간 조회·설정·해제 |

상점 ID는 `general_store`(단비), `farm_stall`(씨앗·납품), `cafe`(허브차), `fishing_shack`(미끼·생선 매입)다. 서비스 ID는 `farm_stall/daily_order`, `cafe/herb_tea`, `fishing_shack/sell_fish`로 대응한다. 재고·일일 한도는 계정 단위이며 상점 방문 중에도 인증된 계정의 돈과 재고를 사용한다. 주민 강제 퇴거·입주나 이야기 플래그 직접 설정용 공개 HTTP 경로는 추가하지 않는다.

`/v1/me.residents`는 방문 중에도 자기 계정 상태이고 별도 거주 GET은 방문 마을 상태다. 편지와 의뢰는 자기 계정 기준이며 부탁 변경은 자기 마을에서만 허용한다. 기념일·게시판 날짜는 서버 한국 시간, 상점과 기존 판매 보상은 기존 생활 시스템의 날짜 규칙을 따른다. 표시 시간 override는 어느 쪽의 보상·이사 시각도 바꾸지 않는다.

## 저장·멱등성과 검증

공통 요청 저장소는 `(user_id, request_id)`를 키로 사용한다. 같은 요청의 재시도는 저장된 응답을 돌려주며, 다른 경로나 내용으로 재사용하면 `409 request_id_reused`다. 별씨 원장의 퀘스트 참조는 의뢰 ID 또는 날짜·의뢰 ID이고, 상점 참조는 요청 UUID다. 잎전 원장은 최초 변경 시 기존 잔액을 `opening_balance`로 한 번 기록한 뒤 증감만 기록한다. 동일 거래의 재고·버전·원장·편지 변경은 하나의 트랜잭션으로 처리한다.

`test_life_server_merge.py`는 퇴거·재입주 후 친밀도와 수락한 게시판 의뢰 보존, 이사 편지와 소식의 1:1 연결, 의뢰 보상 뒤 상점 구매의 양쪽 원장 합계 및 재시도, 전체 라우트 중복을 검사한다. 이야기 회귀에는 에필로그 세 단계의 순서·완료 조건·재시도, 신규 계정의 실제 입주, 이전 `created` 스키마의 서버/운영자 업그레이드를 추가했다.

전체 회귀 명령은 사용자 지정 임시 경로와 캐시 비활성화를 적용한다.

```powershell
& 'C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe' -m pytest server/tests -q --basetemp=.codex-tmppytest -p no:cacheprovider
```

2026-10-16 현재 작업 트리에서 위 명령으로 **1,257 passed, 1 warning**을 확인했다. 실행 시간은 1,072.34초(17분 52초)다. 경고는 기존 Starlette TestClient의 httpx 사용 중단 예정 안내 한 건이다. 별도 검증 복사본 없이 실제 작업 파일 전체를 검증했다.

상점 신규 파일 4개와 원본 패치 본문의 일치, 충돌 표시 없음, `git diff --check` 통과 및 `game/`·`server/multiplayer.py` 변경 없음도 확인했다. Git 쓰기 명령은 실행하지 않았으므로 병합 인덱스 정리와 커밋은 조정자가 수행한다. `CODEX_TASK.md`와 `.codex-shops.patch`는 그대로 보존했다.
