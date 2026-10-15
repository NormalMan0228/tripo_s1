# 0.11.9 병합에서 건너뛰거나 고친 서버 테스트 (01 통합, 2026-10-16)

Codex 브랜치 여러 개가 같은 코드를 서로 다르게 고쳐서, 합친 뒤 일부 테스트가 사라진 내부 구현을 가정하게 됐습니다. 아래는 그 처리 내역입니다. 경제·한도·보안·귓속말·집 출입 테스트 중 건너뛴 것은 없습니다.

## 건너뛴 것 (3개, 성능 캐시 전용)

| 파일 | 테스트 | 이유 | 대신 확인한 것 |
|---|---|---|---|
| server/tests/test_polling_performance.py | test_crop_projection_matches_existing_public_contract | codex/perf의 작물 캐시(`_cached_crop_source`)는 farm의 성장 모델(`advance_plot`)과 합칠 수 없어 빠졌습니다. `public_crops`는 캐시 없는 투영입니다. | `public_crops` = `public()`의 plots·version·server_time(방문자 작물). test_multiplayer의 방문·작물 테스트, test_farming 전체 |
| 같은 파일 | test_crop_cache_is_bounded_and_does_not_retain_large_saves | 위와 같음(캐시가 없음) | 위와 같음 |
| 같은 파일 | test_presence_crop_cache_follows_writes_rollback_clock_and_host | 위와 같음 | presence 응답의 crops는 매번 새로 계산합니다(test_multiplayer) |

같은 파일의 인덱스, 잠금 없는 읽기, 파티 조회 테스트는 그대로 돕니다.

## 고친 것 (건너뛰지 않음)

| 파일 | 바꾼 점 | 이유 |
|---|---|---|
| test_economy_safety.py, test_farming.py | `economy.change_coins(state, n)` → `economy.apply_coins(state, n)` | 잎전 쓰기는 lifesrv의 원장 함수 `change_coins(conn, …)` 하나로 통일했습니다. lifeauth의 메모리 검사 함수는 `apply_coins`로 남겨 같은 거절 규칙(정수, 범위, 부족, 넘침)을 그대로 시험합니다. |
| test_life_bridge.py | 다시 켬 | 상점 거래가 server/shops.py로 옮겨 가서, 시험용 tools/life_bridge.py에도 같은 가격과 `apply_coins` 검사를 쓰는 작은 판매대를 넣었습니다. |
| test_life_reward_boundary.py | `security_events == 0` 확인 한 줄 제거 | 원장 함수는 깨진 잔액을 거절하면서 검토용 경제 플래그와 보안 이벤트를 남깁니다(lifesrv 설계). 거절 코드, 상태 보존, 원장 0건, `ledger_check` 확인은 그대로입니다. |
| test_security_audit.py | 참조 사진 크기 한도 시험값 2049 → 4097 | aigen(#68·75)이 사진을 4096까지 받고 1024로 줄입니다. 작은 쪽 한도(15)와 MIME 위장·잘린 JPEG 거절은 그대로 시험합니다. 서버는 선언한 형식과 실제 형식이 같은지, 픽셀을 끝까지 디코딩할 수 있는지 확인합니다. |
| test_multiplayer.py, test_paint.py, test_home_access.py | 집 가구 모델·칠은 집이 열려 있을 때만 받음(감사 M2) | `visible_object()`에 집 출입 검사를 넣었습니다. 내보낸 손님은 404를 받는다는 시험을 새로 추가했습니다. |
