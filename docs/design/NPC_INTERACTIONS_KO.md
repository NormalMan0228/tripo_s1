# NPC·특수 건물 상호작용과 상점 서버 계약

## 범위와 데이터 근거

기준 커밋은 `e9ad006`이다. `game/scripts/residents.gd`의 주민 19명,
`day_folk.gd`의 이름·직업, `interiors.gd`와
`game/maps/archipelago/building_placements.json`의 건물 17곳을 대조했다.
서버 기능은 `npc_homes.py`, `story.py`, `quests.py`, `homestead.py`,
`asset_studio.py`, `chat.py`, `friends.py`를 기준으로 구분했다.
클라이언트 대화·일정과 기존 부탁을 새로 구현했다고 표시하지 않는다.

## NPC별 기능

‘대화’는 기존 클라이언트 대화이며, ‘선물’은 서버의 선물·친밀도·답장·집 꾸미기다.
모든 주민에게 기존 부탁 1개씩이 있고, 부탁 보상과 해금 조건은 변경하지 않는다.

| NPC ID / 이름 | 거주 건물 / 역할 | 기존 상호작용 | 이번 추가·연결 |
| --- | --- | --- | --- |
| `naru` 나루 | 02 목조 주택 / 길잡이 | 대화, 선물, 섬 탐방 `naru_islands` | 기존 유지 |
| `sora` 소라 | 11 보라 주택 / 재단사 | 대화, 선물, 옷 갈아입기 `sora_outfit` | 기존 유지 |
| `moru` 모루 | 16 청색 오두막 / 야영 전문가 | 대화, 선물, 버섯 부탁 `moru_soup` | 기존 유지 |
| `haeru` 해루 | 17 등대 / 낚시꾼 | 대화, 선물, 바닷물고기 부탁 `haeru_fish` | 등대 부두의 보람 매입 서비스와 UI 위치 공유 가능 |
| `postman` 다온 | 12 파란 주택 / 우편배달부 | 대화, 선물, 선물 전달 부탁 `daon_gift`, 주민 편지함 | 기존 편지함 유지; 친구 편지 발송은 추가하지 않음 |
| `sweeper` 미소 | 12 파란 주택 / 청소부 | 대화, 선물, 꽃 부탁 `miso_flowers` | 기존 유지 |
| `fisher` 보람 | 06 주황 오두막 / 낚시꾼 | 대화, 선물, 어종 수집 `boram_catch` | `fishing_shack`: 미끼 구매, 생선 매입, `sell_fish` 서비스 |
| `kid` 콩이 | 06 주황 오두막 / 꼬마 | 대화, 선물, 장난감 부탁 `kongi_toy` | 기존 유지 |
| `farmer` 한결 | 03 씨앗 가게 / 농부 | 대화, 씨앗·미끼 거래, 수확물 판매, 일일 식탁 납품, `hangyeol_turnips` | `farm_stall` 공통 상점, `daily_order` 서비스; 기존 API 호환 |
| `regular` 모카 | 01 카페 / 카페 주인 | 대화, 첫 선물 이야기·테라스·답장, 사과 부탁 `moka_pie` | `cafe`의 `herb_tea`: 10분 기분 효과 |
| `miller` 두레 | 04 풍차 / 방앗간지기 | 대화, 당근 부탁 `dure_carrots`, 실내 소품 상호작용 | 기존 유지 |
| `stargazer` 하늘 | 05 천문대 / 별지기 | 대화, 야간 방문 `haneul_stars`, 망원경·별자리 소품 | 기존 유지 |
| `gardener` 초록 | 07 온실 / 정원사 | 대화, 향초 부탁 `chorok_herbs`, 화단·새싹 소품 | 기존 유지 |
| `shopkeeper` 단비 | 13 잡화점 / 상인 | 대화, 집 꾸미기 부탁 `danbi_home`; 거래 전용 서버 API 없음 | `general_store`: 씨앗·소모품·장식 구매, 농작물·생선·채집물 판매; 이주 전 폐점 |
| `scout` 바우 | 02 목조 주택 / 탐험가 | 대화, 선물, 솔방울 부탁 `bau_pinecones` | 기존 유지 |
| `lamplighter` 노을 | 16 청색 오두막 / 등불지기 | 대화, 선물, 조명 배치 `noeul_light`, 부탁 답장 | 기존 유지 |
| `gentleman` 윤재 | 11 보라 주택 / 산책하는 신사 | 대화, 선물, 안부 전달 `yunjae_regards` | 기존 유지 |
| `poet` 가람 | 11 보라 주택 / 시인 | 대화, 선물, 전망대 방문 `garam_lookout` | 기존 유지 |
| `stroller` 새벽 | 17 등대 / 산책자 | 대화, 선물, 야간 부두 산책 `saebyeok_walk` | 기존 유지 |

선물 가능한 일반 주민은 `npc_homes.NPCS`의 13명이다. 모카의 이야기 선물은 별도이며,
상점 주인에게 일반 선물 API가 새로 생기지는 않는다.

## 건물별 기능

| 건물 ID | 용도·담당 | 기존 기능 | 이번 변경 |
| --- | --- | --- | --- |
| `01_cafe` | 모카 카페 | 대화, 이야기 선물, 테라스 | 허브차 서비스 |
| `02_timber_house` | 나루·바우 주거 | 방문, 선물 자동 배치 | 유지 |
| `03_teal_cottage` | 한결 씨앗 가게 | 씨앗·미끼, 수확물 판매, 납품 | 공통 거래·납품 서비스 |
| `04_windmill` | 두레 풍차 | 대화·부탁·맷돌 소품 | 유지 |
| `05_observatory` | 하늘 천문대 | 대화·야간 부탁·망원경 | 유지 |
| `06_orange_cottage` | 보람·콩이 주거 | 방문, 선물 자동 배치 | 유지; 생선 매입 UI는 부두에서 연결 |
| `07_greenhouse` | 초록 온실 | 대화·부탁·화단 소품 | 유지 |
| `08_gazebo` | 정자 / 가람 활동 장소 | 휴식·대화 | 유지 |
| `09_town_hall` | 플레이어 공방 | 제작·배치·공방 API | 유지; 새 장식은 기존 객체 배치·모델 API 사용 |
| `10_red_house` | 플레이어 집 | 가구 배치·첫 편지 | 유지 |
| `11_purple_house` | 소라·윤재·가람 주거 | 방문, 선물 자동 배치 | 유지 |
| `12_blue_house` | 다온·미소 주거 | 방문, 선물 자동 배치 | 유지 |
| `13_shop` | 단비 잡화점 | 대화·매장·창고 소품 | 이주 플래그와 거래 API |
| `14_stage` | 음악 무대 | 열린 구조물·주변 활동 | 유지 |
| `15_picnic_shelter` | 피크닉 쉼터 | 열린 구조물·휴식 | 유지 |
| `16_blue_cottage` | 모루·노을 주거 | 방문, 선물 자동 배치 | 유지 |
| `17_lighthouse` | 해루·새벽 주거, 보람 부두 활동 | 선물·낚시·부탁 | 보람 생선 매입·미끼 거래 연결 |

현재 지도에는 별도의 번호가 붙은 우체국 또는 낚시 오두막 건물이 없다.
`fishing_shack`은 서비스 ID이고 건물 연결은 실제 존재하는 `17_lighthouse`이다.
우편 UI는 기존 `GET /v1/letters`, `POST /v1/letters/read`를 사용한다.
새 자유 입력·메시지 발송 경로가 없으므로 채팅 필터를 우회하는 통로도 만들지 않는다.

## 상점 데이터와 가격

정의 파일은 `server/shop_catalog.py`, 실행 로직은 `server/shops.py`다.
NPC·건물·구매/판매 목록·가격·일일 제한·장식 순환·서비스가 정의에 있다.
기존 `homestead.SHOP`, `SEED_COSTS`, `PRICES`를 재사용하며 가격을 복제해 바꾸지 않는다.

| 품목 | 구매 잎전 | 지급 방식·제한 |
| --- | ---: | --- |
| `turnip_seed` 순무 씨앗 | 2 | 기존 가방, 기존처럼 일일 제한 없음 |
| `carrot_seed` 당근 씨앗 | 3 | 동일 |
| `pumpkin_seed` 호박 씨앗 | 4 | 동일 |
| `strawberry_seed` 딸기 씨앗 | 5 | 동일 |
| `sunflower_seed` 해바라기 씨앗 | 6 | 동일 |
| `bait` 미끼 | 1 | 소모품, 기존 낚시에서 사용, 일일 제한 없음 |
| `flower_pot` 작은 화분 | 20 | 짝수 계정 일자에 판매, 계정당 하루 1개 |
| `table_lamp` 작은 탁상등 | 20 | 홀수 계정 일자에 판매, 계정당 하루 1개 |

장식은 기존 절차적 모델 생성기를 재사용해 `objects` 인벤토리에 실제 객체로 지급한다.
외부 모델 생성 호출·제작 크레딧 소모는 없다. `object_ids`로 지급 객체를 확인한다.
기존 무료 농사 도구 규칙은 유지하고 소모품 판매에는 미끼를 사용한다.

판매 가격은 모든 경로에서 `homestead.PRICES`와 동일하다. 씨앗·미끼·구매 장식은
NPC에 되팔 수 없다. 보람은 `homestead.FISH`의 생선만 매입한다.
기존 씨앗 가게의 전체 수확물 매입 목록도 유지한다.
가격 필드 `coins`, `shards`는 잎전·별씨이며 현재 모든 상품 별씨 가격은 0이다.
구매 엔진은 두 통화의 동시 차감을 지원하되 새 별씨 발행 경로를 추가하지 않는다.

## 서비스 3개

| 상점 / 서비스 | 입력·비용 | 결과·제한 |
| --- | --- | --- |
| `cafe / herb_tea` | 잎전 3, `quantity=1`, 빈 `item` | `cafe_mood: cozy`, 서버 시각 기준 600초; 하루 3잔. 재구매 시 만료 시각을 현재+600초로 교체하며 누적하지 않음 |
| `farm_stall / daily_order` | 순무 2 + 강농어 1, `quantity=1`, 빈 `item` | 기존대로 잎전 20, 하루 1회. 구형 `action=order`와 같은 `order_day` 사용, 별씨 없음 |
| `fishing_shack / sell_fish` | 생선 `item`, 수량 1~20 | 일반 판매와 같은 재고 검사·가격·별씨 한도. `/sell`과 완전히 같은 거래 로직 |

기분 효과는 표현용이다. 성장 속도·수확량·낚시 확률·별씨 지급량을 올리지 않는다.
서비스와 거래는 로그인한 계정의 소지품·돈·진행을 사용한다. 방문 중에도 호스트 재산을 쓰지 않는다.
위치나 클라이언트의 영업 시간 애니메이션을 서버가 검증한다고 주장하지 않는다.

## 단비 이주 플래그

`story_flags(user_id, flag='danbi_moved_in', created)`가 개점의 유일한 권위다.
새 계정은 플래그가 없으므로 폐점이다. 기존 첫 이야기 `first_gift`의 선물 전달이
서버에서 성공해 `step='done'`으로 전환될 때 같은 트랜잭션에서 이주 플래그를 설정한다.
향후 이야기 확장에서는 승인된 이주 단계에서 `story.move_in_danbi()`를 호출하면 된다.
클라이언트가 임의로 플래그를 설정하는 엔드포인트는 없다.

이미 `first_gift/done`인 저장은 서버 초기화 시 플래그만 보충한다. 잔고·보상을 추가 지급하지 않는다.
운영자 이야기 초기화는 플래그도 제거해 다시 폐점한다. 이야기가 없는 구계정이나
이야기 기능이 꺼진 계정은 자동 이주로 간주하지 않는다. 이 경우 기존 씨앗 가게는
계속 이용 가능하고, 필요할 때 기존 운영자 `story reset USERNAME` 절차로 이야기를 시작한다.
플래그는 `GET /v1/story`와 `/v1/me`의 `story.flags`에도 나온다.

## API 및 클라이언트 연결

모든 API에 기존 Bearer 인증이 필요하다.

- `GET /v1/shops/{shop_id}`: 상점·NPC·건물, `open`, `closed_reason`, `required_flag`,
  계정 잔고와 `version`, `buy`, `sell`, `services`, `sell_stars`, 활성 `effects`를 반환한다.
- `POST /v1/shops/{shop_id}/buy`, `/sell`: 아래 거래 요청을 사용한다.
- `POST /v1/shops/{shop_id}/service`: `item` 대신 `service`를 지정한다.
  `sell_fish`만 추가로 `item`·`quantity`를 받는다.

```json
{
  "request_id": "91c7e1ed-d769-4a4e-bc81-c047077b6ef1",
  "version": 0,
  "item": "turnip_seed",
  "quantity": 2
}
```

```json
{
  "request_id": "196412bd-ac5b-4aa9-a64b-bbaf11bcad29",
  "version": 1,
  "service": "herb_tea"
}
```

거래 성공 응답은 기존 homestead 상태 형태이며 `version`, `coins`, `bag`, `message`,
`sell_stars`, `shards`, `effects`를 포함한다. 구매·판매에는 `stars`, `object_ids`도 있다.
`version`은 가방·농사와 공유한다. 성공마다 증가하므로 최신 값을 적용해야 한다.

조회 항목의 `daily_limit`과 `remaining`이 `null`이면 일일 제한이 없다.
유한 재고는 계정별 구매 한도와 같으며 `stock_scope='account'`다.
`day`와 `resets_at`은 인증 시 고정된 계정 UTC 오프셋으로 계산한다.
요청 헤더를 바꿔 재고·납품·별씨 제한을 초기화할 수 없다.
장식 목록은 해당 날짜의 상품만 반환한다. 재시작 후에도 한도는 유지된다.

클라이언트는 NPC 대화/건물 메뉴에 상점 ID를 연결하고 서버 가격·잔여량을 표시한다.
폐점이면 구매·판매를 비활성화하고 `danbi_not_moved_in` 안내를 보여준다.
네트워크 재시도는 **동일한 경로·본문·request_id**로 해야 한다.
서버는 원래 영수증을 반환한다. 새로운 행동은 새 UUID를 사용한다.
`stale_life_version`이면 상점/가방을 다시 조회하고 새 요청을 만든다.
장식 구매 후 `/v1/me` 객체 목록을 갱신하며 기존 모델·배치 API를 사용한다.
기분 효과는 `effects.cafe_mood.expires_at`과 `server_time` 기준으로 표현한다.
클라이언트 파일의 기능 변경은 이번 범위에 포함하지 않았다.

대표 오류: 인증 없음 401, 없는 상점/서비스 404, 유효하지 않은 본문 422,
폐점 `shop_closed`, 잔고 부족 `life_not_enough_coins`/`insufficient_shards`,
소지품 부족 `life_missing_items`, 미취급 품목 `life_invalid_item`,
다른 날 상품 `shop_item_unavailable`, 일일 한도 `shop_daily_limit`,
완료된 납품 `life_order_completed`, 버전 충돌 `stale_life_version`,
멱등 키 재사용 `request_id_reused`는 409다.

## 호환성·원장·검증

`POST /v1/homestead`의 `buy`, `sell`은 `farm_stall`의 같은 거래 함수로 위임한다.
`order`도 같은 납품 함수로 위임한다. 기존 요청 operation인 `homestead`를 유지해
업그레이드 전 저장된 요청 영수증도 그대로 재생한다. 가방·씨앗·동전·농사 버전과
판매 보상의 당일 누계·이월 잎전은 기존 저장에서 이어 사용한다.

잎전 변경은 `economy.change_coins()`와 `leaf_ledger`, 별씨 변경은 기존
`economy.change_shards()`와 `ledger`를 거친다. 최초 잎전 변경 시 기존 잔고를
`opening_balance`로 한 번 기록할 뿐 추가 지급하지 않는다. 구매 `shop_buy`,
판매 `shop_sell`, 카페 `shop_service`, 납품 `daily_order`, 관리자 `admin_grant`가
잎전 원장의 사유다. 동전 변경 함수 자체에도 savepoint가 있어 원장/잔고 쓰기 실패가
부분 반영되지 않는다. 가방·재고·두 통화·요청 영수증은 바깥 SQLite 트랜잭션에서 묶인다.

기존 판매 별씨 공식(기본 잎전 매출 3당 별씨 1)과 일일 한도(기본 15), 설정값,
계정 일자 고정, 원장 재검증은 그대로다. 상점 수나 서비스 호출 수만큼 한도가 늘어나지 않는다.

`server/tests/test_shops.py`는 거래·잔고 부족·인벤토리 부족·폐점·이주 전환,
단일/동시 재시도·변조된 키·버전 경합·원장 기록과 실패 롤백·장식 실물 지급,
순환/일일 재고·계정 격리·재시작·시간대 변경·서비스 만료·구형 요청 및 가격 이관을 검사한다.
전체 검증 명령은 다음과 같다. 샌드박스에서 기본 임시 폴더에 접근할 수 없으면
`PYTEST_ADDOPTS`의 `--basetemp`를 작업 폴더 내부의 새 테스트 디렉터리로 지정한다.

```powershell
& 'C:\lsm26\triphthonS1\.tools\server-venv\Scripts\python.exe' -m pytest server/tests -q
```


?? ??(2026-10-16): **1,150? ??**, ?? 1?, ?? 0?.
? ?? ???? 24???, ??? ?? Starlette TestClient? httpx ?? ?? ???.
`git diff --check`? ????. ????????? ???? ???.
