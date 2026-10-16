# 06 스토리·퀘스트·시연 · 인수인계 메모 (2026-10-16)

다음 세션이 이 파일 하나로 이어서 할 수 있게 적습니다. 작업 폴더 `D:\lsm26\wt\storyq` (브랜치 `wt/storyq`), 병합은 01 통합 세션에 요청합니다.

## 0.11.8에 들어간 것 (merge-version-gate a31d32d)
- 대화 E·Space·Enter 넘기기, 선택지 W/S·↑↓ + E·Space (rpg_ui.gd dialogue_type/skip/pick)
- 판매 → 별씨(3잎전마다 1, 하루 15), 잡화점 단비 '물건 팔기'(shop_sell.gd)
- 보물상자 12개(집 1 + 섬마다 2, 풍차 들판 3), 합 48 (server/treasure.py, game/scripts/treasure.gd)
- 주민 부탁은 의자 주문 뒤 열림(모카 부탁만 이야기 뒤)
- 에필로그: 선물 뒤 다온이 달려와 숲 소식 → "숲의 돌문으로 가기" → 돌문 기록 (story_forest.gd, server story_events)
- 향초 8곳을 덤불 옆으로, 테라스 나무 받침 제거, 다온이 둘 나오던 문제 수정
- 시연 계정 준비 명령 `admin_cli demo prep/list`, 진행표 `docs/demo/DEMO_RUN_KO.md`

## dev에서 진행 중 (06:00 이후)
| # | 작업 | 상태 | 파일 |
|---|---|---|---|
| 83 | 보니(boni, 공방 제작 담당, 하늘색 머리, 초상화 1) · 솔(sol, 초록의 견습 정원사, 초상화 3) | 워크플로 작업 중 | residents.gd, day_folk.gd, shadow_folk.gd |
| 20 | 주민 매일 다른 루틴(휴무일·요일·랜덤 이벤트) | 워크플로 작업 중 | residents.gd |
| 43/44 | 이사 클라이언트 + 다시 온 주민 친분 대사 | 워크플로 작업 중 | move_in.gd (+story.gd 몇 줄) |
| 26/81 | 퀘스트 게시판·NPC 편지 화면, 상점 대화 | 워크플로 작업 중 | quest_board.gd, npc_letters.gd, shop_window.gd |
| 24b | 튜토리얼 탐험에서 단비 구출 → 잡화점 | 대기 | 탐험(N5)·맵 훅 필요 |
| 35 | 테스터 시간대 바꾸기 | 대기 | Codex 테스터 역할(TIME_OVERRIDE_API.md) 뒤 |

## 다른 세션과의 약속
- 단비 집터(02 맵): `game/maps/archipelago/plots.gd` — `Plots.plot_info("danbi_plot")`, `set_plot_built`, `set_sign_text`; 방 id `danbi_house`; 중심 (-23.5, 9.0)
- 집 연출(N2): `game/scripts/house_plots.gd` — `HousePlots.show_house(plot_id, built, fresh, app)`, `set_sign`, `door_at`, `building`. 토스트 문구는 06이 정함("단비 님이 이사 왔어요!")
- 서버(Codex): 게시판·편지 `codex/storysrv`(wt/storyq에 합침), 이사 `codex/movein43`, 상점 `codex/shops` — 서로 충돌해서 Codex가 하나로 합치는 중. 합칠 때 story.py의 'event' 액션과 EVENTS(forest_told, forest_gate)를 남겨야 함
- 결정은 00 총괄에 SendMessage(그림 PNG 경로 포함)

## 시험 돌리는 법
- 한 작업 폴더에서 클라이언트 시험을 동시에 돌리면 로그가 섞입니다. 하나씩 돌리세요.
- 무거운 Godot 작업 전: `powershell -ExecutionPolicy Bypass -File D:\lsm26\locks\wait_heavy.ps1` (PC 전체 2개). `D:\lsm26\locks\reserve.txt`가 있으면 배포 창이니 Godot을 띄우지 않습니다.
- `$env:TRIPOTHON_QA_PORT='8891'; powershell -NoProfile -ExecutionPolicy Bypass -File tools\test.ps1 -SkipServerTests -ClientScript <이름>`
- 주요 시험: story_chapter(62), quest_check(331), quest_e2e(47), demo_keys(28), treasure_check(31), treasure_spots(136), 서버 `server/tests/test_story.py test_treasure.py test_quests.py test_demo.py`
- 새 소리 파일이 들어오면 `.godot/imported` 캐시가 비어 Cannot open file 오류로 exit 1이 납니다 → `robocopy merge-vg\game\.godot → wt\storyq\game\.godot /E /XO`
