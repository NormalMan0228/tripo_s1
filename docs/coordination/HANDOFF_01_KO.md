# 01 통합·배포·서버 인수인계 (2026-10-16)

최신 배포는 0.11.9.9입니다. 맨 끝 「최신 0.11.9.9」 절부터 읽으세요. 앞의 0.11.8 배포 절차와 당시 상태는 누적 기록입니다.

## 지금 상태

- 통합 브랜치는 `merge-version-gate`이고, 작업 폴더는 `C:\lsm26\triphthonS1\.claude\worktrees\merge-vg`입니다.
- 병합을 미리 해 보는 대기 폴더는 `D:\lsm26\wt\contracts`(브랜치 `wt/contracts`)입니다. 서버 시험은 여기서 돌린 뒤 merge-vg를 fast-forward합니다.
- 메인 서버(옛 학교 서버)는 0.11.7(d6f4328), 최소 버전 0.11.7입니다.
- 0.11.8 내용(마감 06:00): Codex(econ, limits), facing, aigen, ui0118, build, monstersfx, motion, mapinterior-40, mapdoor-1b, home, storyq, vfx, 그리고 서버 계약(집 출입, 재접속, presence held·shards)과 하루 한도 0.
- `game/project.godot`은 0.11.7과 같아야 합니다. 버전 줄 말고 하나라도 바뀌면 패치 대신 설치 파일이 필요해집니다(`tools/game_patch.py` settings).
- 패치 기준판: `D:\lsm26\bases`(0.11.5, 0.11.6, 0.11.7). merge-vg에서 `builds\bases`로 정션되어 있습니다.

## 0.11.8 배포 순서 (merge-vg에서)

1. 무거운 작업 전에는 `powershell -ExecutionPolicy Bypass -File D:\lsm26\locks\wait_heavy.ps1`을 먼저 실행합니다.
2. 버전과 문서:
   - `game/project.godot`의 `config/version="0.11.8"`
   - `docs/releases/school_changes_KO.txt` 맨 위에 `== 0.11.8 (2026-10-16)` 절을 추가합니다(초안: 아래 「도움 파일」의 notes_0118_draft.txt).
   - 로드맵: roadmap.json을 고치고 `tools/build_roadmap.py --note` 실행
   - 커밋합니다. `git add -A`는 쓰지 않습니다.
3. import(실패하면 다시 시도) → `tools/bake_archipelago.py` → `tools/bake_survival.py` → `--script res://../tools/door_leaves.gd`
4. 내보내기: `.tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path game --export-release "Windows School" ../builds/school/Villagen.exe`
5. 설치 파일: `.tools\art-venv\Scripts\python.exe tools\package_release.py --school --installer --game-only`
6. 패치 크기 확인: `python tools\publish_school_build.py patch --dry-run`. 리허설에서 0.11.7→0.11.8은 약 43MB였고, 소리가 늘어 지금은 더 큽니다.
7. 사용자가 "배포해"라고 한 뒤에만 아래를 합니다(총괄을 통해 받음).
   - `python tools\publish_school_build.py upload 0.11.8` → `check --full`
   - `python tools/deploy_school.py --announce 3 --block-older`: school-release로 보냅니다. 그러면 VM 타이머가 5분 안에 3분 공지 → 백업 → 새 서버 → 최소 버전 0.11.8 순서로 반영합니다.
8. 확인:
   - `https://54-117-10-64.sslip.io/health`에서 version 0.11.8, build, tripo_keys, tripo_budget
   - 0.11.7 클라이언트가 패치를 받아 0.11.8로 켜지는지
9. 07:15~08:15 실서버 점검 → DEMO_RUN_KO.md 문구를 고칩니다('0.11.8 배포·점검 뒤에는 다시 돌리지 않기', 한도 숫자).

## 사용자 VM 준비 (총괄이 사용자에게 보냄)

- 새 Tripo 키는 `ops/secrets/tripo-key`에 한 줄로 추가합니다.
- 키 잔액 확인 명령의 출력을 받으면 예산을 계산합니다: `TRIPOTHON_TRIPO_CREDIT_BUDGET = /health tripo_budget.used + 0.9 × 잔액 합계`
- env 값:
  - 계정당 5회, `TRIPO_DAILY_REQUEST_LIMIT=0`(0.11.8 코드부터 가능)
  - WELCOME 150, MAX_STARS 200, MAX_CREDITS_PER_CRAFT 200
  - TESTER 1500, 테스터 예산 10000
- 배포 점검표(배포 전에 사용자가 VM에서 실행해 결과를 붙임):
  - 키 줄 2개
  - `TRIPOTHON_TRIPO_CREDIT_BUDGET=29106` (총괄이 사용자 잔액으로 계산한 값)
  - `TRIPOTHON_ENABLE_LEGACY_GENERATION`이 없거나 false
- 배포 뒤 확인: /health의 `tripo_keys` 2, `tripo_budget.total` 29106
- 테스터 계정 tripo1~5는 배포 뒤 사용자가 VM에서 만듭니다(비밀번호는 숨김 입력). 명령은 `ops/README.md`에 있고 `-f ops/compose.gcp-free.yaml`을 붙입니다.

## 0.11.8 뒤 병합 대기열 (도움 파일 after_0118_queue.txt)

- wt/build 5f4e1c5: 방 벽·천장 배치 클라이언트
- wt/home 031ae19: 문 훅 연결
- codex/farm(N4 클라이언트와 함께), codex/rig67·movein43·secaudit·perf·shops·ja: 총괄이 요청합니다.
- 탐험 로그라이크 a208479: 스위치 기본값을 꺼서 넣습니다.

## 주의

- 공유 에셋 정션이 있는 worktree는 도움 파일 rm_wt.ps1로만 지웁니다(정션을 먼저 끊음).
- strings.json 충돌은 도움 파일 strings_merge.py로 JSON 합집합을 만들어 풉니다. 풀고 나서 중복 키를 검사합니다.

## 도움 파일

- 폴더: `C:\Users\dd\AppData\Local\Temp\claude\C--lsm26-triphthonS1\3d7d7a09-3a2f-44bf-ab93-48415f8d8e6d\scratchpad\`
- `rm_wt.ps1`, `make_wt.ps1`, `strings_merge.py`, `verify_quick.ps1`, `verify_final.ps1`
- `notes_0118_draft.txt`, `after_0118_queue.txt`, `rel0118_runbook.png`
- `.import` 줄바꿈 변화(수천 개)와 추적되지 않는 `.uid`는 커밋하지 않습니다.

## 2026-10-16 11:20 현재

- 메인 서버는 0.11.9(a286f78)이고 최소 버전 0.11.9입니다. S3에는 0.11.9 설치 파일과 0.11.7·0.11.8 → 0.11.9 패치가 있습니다. 기준판은 D:\lsm26ases(0.11.7, 0.11.8, 0.11.9)입니다.
- 서버 설정은 compose.yaml 기본값입니다: 리깅·애니 켜짐, 모닥불 buff, 이사 off, 계정당 하루 5회, 서버 전체 횟수 제한 없음, 예산 29106.
- 내보낸 뒤에는 반드시 pck 안의 project.binary를 검사합니다(ECFG로 시작하고 버전이 맞아야 함). 0.11.9 첫 내보내기에서 0바이트가 나온 적이 있습니다.
- 다음 패치 대기열(도움 파일 after_0118_queue.txt 끝부분): codex/secaudit2 efdc67a(서버 핫픽스 후보), wt/lowspec 64e4650, codex/lownet c59cbd9, wt/vfx3 16c3ae2e(vfx2 + tooluse2 0a083f1 포함, 도구 효과 타이밍), wt/voices a666d589, wt/mapdoor-cut-4 d54b18c4(cut-3 포함, 창문 유리; 문 절단 도구 실행), wt/body 1b893ba(28104c9 포함: 몬스터 11종, GLB 15개 복사 + shadow_beast 결함 수정), wt/ja 495ea9d(두 단계 import), texdiet와 건물 2048 텍스처, wt/uibag 756c5df.

## 2026-10-16 11:45 현재

- 보안 재점검 codex/secaudit2(efdc67a)를 merge-version-gate에 합쳤습니다(ee3dc30). 바뀐 곳은 서버뿐입니다: 표시 이름 우회 차단, 가입 ID 이름 규칙, 로그인 ID 가로채기 차단, 야간 퀘스트 시간대 우회 차단, 예전 리깅·테스터 비용 집계. 서버 전체 테스트는 1,777 통과, 0 실패입니다. Codex 테스트 하나(test_chat 예전 메시지 형식)는 실서버 형식(d07b0795, display_name 포함)에 맞췄습니다.
- 이 커밋은 서버만 다시 빌드하는 핫픽스로 낼 수 있습니다. 게임 버전은 0.11.9 그대로이고 ops/release.json도 같아서, deploy_school.py --announce 3 --block-older를 실행하면 새 배포 커밋 없이 HEAD만 올라갑니다. 3분 공지와 로그아웃이 한 번 생깁니다. 사용자가 이 세션에서 직접 "배포해"라고 해야 진행합니다.
- 11:35 사용자 보고: 0.11.7에서 패치를 누르자 창만 닫히고 다시 켜지지 않았습니다. 보관본 0.11.7로 이 PC에서 재현했더니 179MB 패치를 18초에 받고, 스스로 다시 켜져 v0.11.9 타이틀까지 정상으로 왔습니다. 사용자가 누른 곳은 다른 PC입니다(이 PC에는 0.11.7 설치본도 patches 폴더도 없음). 그 PC에서는 Villagen을 한 번 더 실행하면 패치가 적용됩니다. 다음 패치에서 재시작 안내 문구와 실패 기록을 넣습니다.
- 사용자 데이터의 logs 폴더는 소스 QA 실행과 설치본이 함께 씁니다. ambience .sample 오류는 소스 실행에서 난 것입니다.

## 2026-10-16 14:15 현재

- 메인 서버: 0.11.9.1(13:47) → 0.11.9.2(14:13, build 5100b21, 최소 0.11.9.2). S3에는 0.11.9.2 설치 파일과 0.11.9·0.11.9.1 → 0.11.9.2 패치가 있습니다. 기준판(D:\lsm26\bases)은 0.11.9, 0.11.9.1, 0.11.9.2입니다.
- 0.11.9.1: 옷장 = 8명 고르기·꾸미기(03 31fc61d7), 보니·솔 밤·실내 새 모델(05 b619b25, 02 4d4ced66), 모닥불·몬스터 첫 등장 셰이더 워밍업(N4 8c6fc3a7, N6 ad7090e), 밤 몬스터 한 마리씩(02 b4e96a85), secaudit2 보안.
- 0.11.9.2: 몬스터 11종(05 wt/body 2220a55, GLB 15개는 D:\lsm26\wt\body\game\assets\monsters에서 복사), 첫 처치 연기 워밍업(N4 2ff6c068). monster_motion: 스크립트 오류 0, jumps 0. pose_pop은 9종에 남아 있어 05에 넘겼습니다.
- 0.11.9.3을 빌드하고 있습니다(9da5cf07). 꾸미기 튕김(/v1/me 폴링 실패 1번에 로그아웃 → 401/403 또는 5회 연속일 때만), 색 피커는 닫을 때 반영, 새 캐릭터 detail에 장식색, /v1/me 최상위 needs_character_select. 시험이 통과하면 배포합니다(사용자 승인 "배포 준비 되면 배포해").
- 배포 공지에 패치 메시지가 뜹니다: tools/deploy_school.py --message "…"(사용자 규칙 "버전 오를 때마다 패치 메시지"). 0.11.9.2부터 실제로 표시됩니다.
- 빌드 도움 스크립트: scratchpad\build_01193.ps1(import → 굽기 → compile → 내보내기 → pck ECFG·버전 검사 → 포장 → 패치 dry run → 시험). 내보내기와 import는 0xC0000005로 가끔 실패하므로 3번까지 다시 시도합니다.
- 디스크: 0.11.9 설치 파일과 zip은 C:\lsm26\old_release_0119로 옮겨 두었습니다(지우지 않음). D:에는 큰 파일을 두지 않습니다.
- 다음 패치 대기열(after_0118_queue.txt): vfx3, voices 038b17c2, mapguide-1 f60dbdcc, dress-3 cceac441, ground82-2 299990dc, mapperf-2, maptex-1, uibag bc1887a5(되돌린 커밋 4cca7681을 먼저 되돌린 뒤), craftcol-1 498429e0 + wt/build 8e778284, lowspec, lownet, ja.
- Codex는 10/23 07:47까지 쓸 수 없습니다. 주간 한도는 100%까지 씁니다. 작은 단위가 끝날 때마다 커밋합니다.

## 2026-10-16 15:20 현재

- 메인 서버: 0.11.9.3(14:45 전후, ca2abb5) → 0.11.9.4를 배포했습니다(school-release 18c30d6, 최소 0.11.9.4).
- 0.11.9.3 = 꾸미기 폴링 수정(총괄 패치) + 03 ed2ca13f(장식색·피부·밀짚모자·가죽 배낭) + /v1/me 최상위 needs_character_select.
- 0.11.9.4 = N6 f881ff0(탐험 소리·무기 미리 읽기, 베기 궤적) + 05 268bb60(캐릭터 키) + codex/lownet c59cbd9 + wt/lowspec 64e4650. 합친 브랜치는 wt/all01910입니다.
- N6 d609a47(화면 밖 몬스터 애니 LOD)은 검증 전 WIP라 넣지 않았습니다.
- 사용자는 "11.9.a"로 전부 합쳐 바로 배포하라고 했습니다. 남은 브랜치 병합은 자동 권한 검사가 두 번 막았습니다(vfx3). 이유는 표시되지 않았습니다. 사용자가 "지금 합친 것만 바로 배포"를 골랐습니다. 글자가 든 버전은 패처·서버·도구가 읽지 못해서 숫자 버전만 씁니다.
- 남은 대기열(after_0118_queue.txt 끝부분): vfx3 6af6cdb7(G 들기·보따리), voices 038b17c2, mapdoor-obs-1 38252a78, dress-3 cceac441, ground82-2 299990dc, mapperf-2 7d647e85, maptex-1 0a562ed3, uibag f035517e(4cca7681 되돌리기 먼저), craftcol-4 1a7984b9 + wt/build 3cbe26b9(02 먼저), storyq d5a287d4, ja 495ea9d8, texdiet d321dc20, craftnpc 581b0746(꺼진 상태), mergeplan 26a74434.
- 설치 파일·zip은 S3에 올린 뒤 D:\lsm26\old_release_0119x로 옮겼습니다(지우지 않음). C:\lsm26\old_release_0119에는 0.11.9가 있습니다.

- 사용자 규칙(15:30): 0.11.9.4는 이후 버전(0.11.9.10 등)이 나와도 실행돼야 합니다. 다음 배포부터 `deploy_school.py --announce 3 --min-version 0.11.9.4 --message "…"`를 씁니다. --block-older는 쓰지 않습니다. 서버는 0.11.9.4 클라이언트와 호환을 유지합니다(예전 응답 필드는 그대로 두고 새 필드만 더함).

- 15:50 서버 핫픽스(게임 0.11.9.4 그대로): Tripo 메시 작업이 실패하면 다시 제출합니다(TRIPOTHON_STUDIO_RETRIES 기본 2). 메인 서버의 주소(기기)당 가입 제한을 없앴습니다(compose에서 TRIPOTHON_SIGNUPS_PER_IP_DAY "0" 고정, 하루 전체 200은 그대로). 서버 전체 pytest 1,806 통과.
- 06 호환 규칙: 0.11.9.4 이하 클라이언트(x-villagen-version)에는 기존 주민 부탁 19개 id만 보냅니다. 모르는 id가 오면 BOOK[id]에서 스크립트 오류가 납니다. 게시판 의뢰는 괜찮습니다.

## 2026-10-16 15:50 (주간 98%, 언제든 끊길 수 있음)

- 서버 핫픽스 62dd6af를 배포했습니다(게임 0.11.9.4 그대로, 최소 0.11.9.4). 15:43에는 아직 18c30d6이 돌고 있었습니다. /health build가 62dd6af인지 확인해 주세요.
- 진행 중: 총괄이 탐험 버그 목록과 패치를 만들고 있습니다(docs/coordination/patches/expedition/<id>.patch, 기준 62dd6afe). 서버 패치는 0.11.9.4 그대로 서버만 배포합니다. 클라이언트 패치는 0.11.9.5로 냅니다(git apply → compile_all → docs/coordination/ship_01194.ps1을 0.11.9.5로 고쳐 실행: 빌드·pck 검사·업로드·점검·배포). 배포 명령은 `deploy_school.py --announce 3 --min-version 0.11.9.4 --message "…"`입니다(--block-older 금지).
- 다음 패치 대기열 전체: docs/coordination/NEXT_PATCH_QUEUE_01.txt(맨 아래가 최신). 빌드 스크립트 본: docs/coordination/build_01194.ps1, ship_01194.ps1(경로는 01 scratchpad 기준이라 고쳐 써야 함).
- 디스크: C:\lsm26\old_release_0119, C:\lsm26\old_release_01194, D:\lsm26\old_release_01193(각 2.2GB, 모두 S3에 있음)은 사용자 승인을 받으면 지웁니다.

## 2026-10-16 16:00 (주간 99%)

- 탐험 패치 9개(docs/coordination/patches/expedition)를 merge-vg에 적용했습니다(커밋 eba03e7b, 게임 버전 0.11.9.4 그대로).
- 서버 쪽 탐험 수정: scratchpad의 ship_server_expedition.ps1이 서버 전체 pytest를 돌리고, 통과하면 서버만 배포합니다(--min-version 0.11.9.4). /health build가 이 커밋 이후 것인지 확인해 주세요.
- 클라이언트 쪽(3·4·5의 클라 부분, 6~9)은 0.11.9.5 패치로 내야 합니다. 아직 빌드하지 않았습니다. 할 일:
  1. 사용자가 켜 둔 게임(C:\lsm26\Villagen_0.11.9.4, builds/school에 하드링크)을 닫습니다. 열려 있으면 내보내기가 파일 잠금으로 실패합니다.
  2. project.godot 버전을 0.11.9.5로 바꾸고 school_changes_KO.txt에 항목을 더합니다.
  3. compile_all을 돌립니다. 총괄 패치는 compile 전입니다.
  4. docs/coordination/ship_01194.ps1을 0.11.9.5로 고쳐 실행합니다. deploy 줄은 --block-older 대신 --min-version 0.11.9.4로 바꿉니다.
- monster-anim-quality(9)를 넣었으므로 N6 d609a47은 넣지 않습니다.


## 2026-10-19 · Codex 로컬 시연 중간판 0.11.9.5

- 사용자 요청으로 토큰 최적화 작업은 잠시 중단하고 학교 시연 준비를 진행했습니다.
- 결과와 미완료 범위: `docs/demo/PATCH_01195_KO.md`. 배포·업로드는 아직 하지 않았습니다.
- 실행 파일: `C:\lsm26\Villagen_0.11.9.5`. `Play_Local_Multiplayer.cmd`로 독립된 두 계정이 같은 로컬 마을에 자동 접속합니다. 기존 `.tools` 및 이 체크아웃에 의존합니다.
- 소라의 방 복귀 후 구형 옷장 문제, 채팅 가림, 8명 크기/방향/상체 자세 차이, 일반 몬스터 크기, 사라진 문 조명 참조 오류를 수정했습니다.
- 문·창문/안내 경로의 완료된 `38252a78` 변경을 통합했습니다. 통합 전 백업·목록은 `artifacts/door-integration-before/`. 이 브랜치를 다시 통째로 적용하지 마세요.
- 생성 실패 분류, OpenAI↔Gemini 보조 전환, 호출 예산·비용 귀속 검증 완료. 운영 활성화에는 명시적 보조 목록과 두 제공자의 서버 키가 필요합니다. `ops/compose.llm-fallback.yaml` 준비. 정책 거절·잔액/지출 한도·인증 오류는 자동 전환하지 않습니다.
- 서버 최종 관련 시험 246개 통과. 유료 API 호출 0회. 실제 과거 운영 실패의 원인은 로컬 운영 DB를 찾지 못해 미확정입니다.
- D 작업 사본 NTFS 무손실 압축으로 실제 할당 1.60GiB 절약. 중복 ZIP 3개(3.70GiB)는 자동 승인 검토 차단으로 삭제하지 않았습니다. 우회 삭제하지 않았습니다.
- 캐릭터별 새 걷기/달리기 원본 동작, 건물 전체 재생성, 운영 배포는 남았습니다.


## 2026-10-19 · 설정 Esc 추가 점검

- 사용자: 탐험 수정 상세 보고와 설정 Esc/버튼 먹통 확인 요청.
- 타이틀 설정 Esc의 null viewport 접근을 실제 입력으로 재현하여 수정했습니다. settings_menu.gd에서 창 닫기 전에 입력을 소비합니다. 논리 Esc와 게임패드 B 확인창 취소, 키 변경 취소 클릭도 보완했습니다.
- 실제 게임의 마을/탐험 설정 버튼·탭·버리기·계속하기는 로딩 완료 뒤 정상 동작을 확인했습니다. 영구적인 버튼 먹통 원인은 아직 미확정입니다.
- 회귀 검사: game/tests/settings_input_check.gd. 내부 메서드 호출만 하지 않고 실제 viewport 키/마우스 이벤트를 사용합니다. 외부 스크립트로 출시 PCK에서도 실행할 수 있습니다.
- 기존 settings_check.gd의 낮음 화질 기대값만 80%→현행75%로 수정했고 268개 검사가 통과했습니다. 게임 그래픽 기본값은 바꾸지 않았습니다.
- 같은 로컬 0.11.9.5를 다시 빌드했습니다. docs/demo/PATCH_01195_KO.md에 탐험 9개 기존 패치의 상세와 이번 수정·검증 범위를 추가했습니다.


## 2026-10-19 · 탐험 자동 공격 추가 수정

- 사용자 제보: 특별한 계기 없이 혼자 계속 공격하는 현상.
- 실제 키 입력 없이 전역 attack 눌림 플래그만 남기는 시험에서 반복 공격 재현. 수정 전 13검사 중8실패.
- main.gd: unhandled 새 입력으로만 공격/채집 홀드 시작, 키 해제는 GUI 전 관찰, 반복 시 실제 키 상태도 확인. 채팅·메뉴·입력 잠금·월드 전환·창 포커스 전환에서 홀드 및 미전송 공격/채집 예약 취소.
- pause_menu.gd와 chat_box.gd가 Main의 취소 메서드를 호출합니다. 정상적인 길게 누르기와 짧은 탭, 키 재지정은 유지합니다.
- game/tests/survival_attack_input_check.gd 추가. 새 출시 PCK로 입력·모션19검사 통과, 오류 로그 없음. 설정 입력63개/협동 멀티38개 회귀도 통과했습니다.
- 같은 로컬0.11.9.5를 재빌드했습니다. PCK최신 해시는 artifacts/demo-pack-check.json. 운영 업로드는 하지 않았습니다.
- 처음 키 상태가 남는 하드웨어/엔진 원인까지 확정한 것은 아니며, 그 상태로 자동 공격이 시작·재개되는 경로를 차단한 것입니다.

## 2026-10-20 · 탐험 지역 선택 수정

- 튜토리얼 미완료 계정에서 선택 지역을 첫 야영지로 덮어쓰고 이야기 장을 지우던 `start_run()` 분기를 제거했습니다. 튜토리얼은 기존 카드로 직접 선택하며 완료·보상 조건은 유지합니다.
- 저장 탐험은 실제 지역·난이도로 재개하고 툴팁에도 지역을 표시합니다. 기존 첫 야영지 저장은 그대로 이어갑니다. 다른 지역 선택은 탐험을 마치고 귀환한 뒤 가능합니다.
- `expedition_map_selection.gd`: 새 계정으로 실제 카드 클릭, 서버·렌더 맵 일치, 난이도, 이어하기, 이야기 장 검사. 수정 전 49검사 중18실패 → 수정 후 화면53검사 통과. 서버44검사, 기존 단계·보상·보스16검사 통과. 전체 스크립트 컴파일 실패0.
- 로컬0.11.9.5를 다시 내보냈습니다. 최신 PCK 해시는 `artifacts/demo-pack-check.json`. 서버 파일은 설명 주석만 수정했으며 이 버그 수정에 서버 배포는 필요하지 않습니다. 운영 업로드는 하지 않았습니다.
- 새 출시 PCK로 같은 화면 검사53개 재검증 통과, 실행 오류0. 근거: `artifacts/map-selection-packaged-after.log` 및 `map-selection-packaged-after-error.log`.

## 2026-10-21 · 모든 캐릭터 크기 공통 적용

- `actor_size.gd` 추가. 플레이어 13종·성인 주민은 1.75m, 꼬마·솔은 1.30m 기준. 주요 NPC4명·일반 주민17명의 실내/실외/임시 모델에 적용합니다. `player.gd` 공통 생성 경로를 통해 마을·방·원격 캐릭터·꾸미기 미리보기에 적용됩니다.
- 보니·솔은 스킨 원본 좌표와 리그 내부 배율을 이중 계산해 실물보다 크게 측정했고, 그 때문에 실제 표시가 약1.08m/0.80m로 작아졌습니다. imported scene 경계의 외부 배율과 내부 스킨 좌표를 구분하여 고쳤습니다. 메시의 원본 AABB뿐 아니라 실제 스킨 변형 결과로 크기를 검사합니다.
- 일반 몬스터는 원본 높이 최대1.90m(동작에 따라 순간 높이는 달라짐), 보스는 기존 큰 크기 유지/최소3.50m. 임시 몸체도 같은 기준과 발 위치/체력 표시를 적용하며, 웅크리기 동작은 크기 프레임과 분리했습니다.
- 새 출시 PCK로 `actor_scale_check.gd` 256검사 통과, 오류0. 사람형51경우·몬스터34종/44모델·보스·임시 모델·옷장·외형 재생성 포함. 방/소라17검사와 공격입력19검사 회귀 통과. 전체 컴파일 실패0.
- 로컬 `C:/lsm26/Villagen_0.11.9.5` 재빌드. PCK 해시는 `artifacts/demo-pack-check.json`. 운영 업로드/서버 변경/유료 생성 호출 없음. 비교 이미지는 `artifacts/actor-scale-players.png`, `actor-scale-residents.png`, `actor-scale-monsters.png`.

## 2026-10-21 · 구형 플레이어 제거 및 m2 팔

- 사용자 요청에 따라 플레이 가능한 외형은 신형8명(m1~m4/f1~f4)만 남깁니다. `character_roster.gd`에 목록·프리셋·구형 ID 연결을 모았습니다. 구형 저장/접속 정보는 신형으로 연결하고 색상 등 다른 값은 보존합니다.
- 구형 플레이어 생성 분기, stand-in, 구형 선택 버튼, 구형 초상화를 제거했습니다. 신형 8명 초상화 추가. 게임 자원50파일을 `artifacts/retired-player-assets/`에 복구용 분리했으며 출시 PCK에는 포함되지 않습니다. 현 주민이 사용하는 공용 wardrobe/motion 리그와 NPC 해루는 유지합니다.
- m2는 bind pose가 정상이지만 서로 반대 방향의 원본 동작을 팔다리별로 정렬하면서 쇄골이 안으로 꺾였습니다. `tools/body_gen/retarget_player.py --align-body`로 먼저 몸체 방향을 맞춘 뒤 4개 클립을 다시 옮겼습니다. 현재 기본 동작 참조는 구형 explorer 대신 신형 m1입니다.
- m2 어깨 폭: 수정 전 대기 약0.09m → 수정 후 약0.39m. idle/walk/run/slash 각48시점, 총192시점의 어깨 폭을 검사합니다. 사진: `artifacts/m2-arm-before.png`, `m2-arm-review.png`, `m2-arm-detail.png`.
- 출시 PCK로 roster/구형 자원 제거/저장 연결/8명 미리보기/m2팔59검사 통과, 새8명 기준 전체크기246검사, 마을/방/소라17검사, 서버 외형59시험, 출시 공격입력19검사 통과. 최종 오류0·컴파일 실패0.
- 같은 로컬0.11.9.5 재빌드, 직전 PCK보다 약50.55MiB 감소. 해시 `artifacts/demo-pack-check.json`. 서버 변경/운영 업로드/유료 생성 호출 없음. 주 체크아웃과 무관한 미완료 자산은 건드리지 않았습니다.


## 2026-10-21 — 0.11.9.5 공개 배포 완료

- 사용자 요청으로 설치 파일·ZIP·0.11.9.2/3/4용 패치를 공개하고 운영 서버에 배포했습니다. 운영 커밋 `b2728bf92516f1acbd1c41fa9d48a0b1ce50fb1c`, `/health` 버전0.11.9.5·빌드b2728bf9·정상 응답·점검 해제 확인. 최소 버전0.11.9.4, 최신0.11.9.5입니다.
- 신형8명 전용·구형 외형 이전·m2 팔·전체 크기·탐험 지도 선택/공격 입력·설정 Esc·소라 꾸미기·문/창문 통합 포함. LLM 오류 진단/보조 전환 코드는 포함됐으나 운영 보조 제공자 활성화는 별도 후속 작업입니다.
- 설치 파일 익명 전체 다운로드 SHA256 및 패치3개 다운로드 SHA256 일치. 0.11.9.4 패치14,034,004바이트(약13.4MiB), 실제 기본 PCK에서 패치 후59검사 통과. 서버 전체1,844통과·5건너뜀.
- 상세 보고서 `docs/demo/PATCH_01195_KO.md`; 검증 `artifacts/release-01195-verification.json`. 로드맵의0.11.9.5 배포 항목을 완료로 갱신합니다.
- 배포 후 보고서 커밋은 dev에만 추가하며 school-release는 위 운영 커밋을 유지합니다. 불필요한 추가 점검을 유발하지 않습니다.

## 2026-10-21 · 0.11.9.6 통합 빌드

- 사용자 요청: 상황별 플레이어/NPC 동작·재질·맵 최적화를 빠르게 마치고 한 번에 배포, 최소 검수.
- Tripo 195크레딧 사용, 16종 새 동작을 14모델에 적용. NPC4명 걷기·달리기 보완. 동작·재질·NPC 전환 검사354개 통과.
- 마을/탐험 반복 갱신, 화면 밖 NPC 계산, 재질 공유·키 데이터 최적화. 꽃 묶음은 이득이 작아 출시 제외.
- `docs/demo/PATCH_01195_KO.md`의 0.11.9.6 절 참고. 설치 파일·패치 제작 후 기존 최소 접속0.11.9.4를 유지해 배포합니다.

### 0.11.9.6 공개 배포 완료

- 운영 e9deb12943a57c0aa3c2b5f8d8109f44be45e82d, `/health` 0.11.9.6·정상·점검 해제. 최소0.11.9.4 유지.
- 설치 파일·ZIP·기존0.11.9.2/3/4/5 패치 공개. 실제0.11.9.5→6 패치 로더에서 동작 검사354개 통과, 공개 패치 SHA256 일치.
- 보고서 `docs/demo/PATCH_01195_KO.md` 최신 절, 근거 `artifacts/release-01196-verification.json`.


## 최신 0.11.9.8 · 2026-10-21 배포 확인

- 배포 커밋 `9111963e99dc9db8bc2688c62854a59fc4495020`: 마지막 표시 자세에서 다음 클립으로 보간, 반복 경계·동일 동작 재시작 보간, 플레이어 8명 및 지상 이족 NPC·몬스터 접촉 IK. 네트워크 스냅샷이 멈춰도 계속 걷던 몬스터를 실제 화면 이동 속도로 선택하도록 수정.
- `motion_blend.gd`, `ground_gait.gd` 추가. 플레이어의 기존 `locomotion_pose.gd` 연결 복구, 정지 시 IK 해제 보간. 걷기↔달리기 위상 유지. 비이족 지상 7계열은 측정 속도표 적용.
- 최종 설치파일·ZIP·패치·서버 모두 0.11.9.8. 서버 `/health` build 9111963e, latest 0.11.9.8, min 0.11.9.4, notice null 확인.
- 공개 자동 패치에 0.11.9.7이 먼저 나타난 뒤 동일 동작 반복 보완을 발견했으므로 버전을 재사용하지 않고 0.11.9.8로 마감. 0.11.9.6과 0.11.9.7에서 최종판으로 직접 패치 가능. 이전 기준판을 삭제하지 않았음.
- 예고 대기 0분으로 배포. AWS 업로드 프로필에는 EC2/SSM 직접 명령 권한이 없어서 서버의 기존 자동 감지(최대 5분)는 유지.
- 확인: 최종 동작 93항목을 소스·출시 PCK·두 실제 업그레이드 경로에서 통과. 상황별 기존 354항목 및 플레이어 실제 이동 266샘플 통과. 대표 평지 조건 검사이며 모든 종·지형 전수 검수는 아님.
- 최종 보고서 `docs/demo/PATCH_01195_KO.md`, 증거 `artifacts/release-01198-verification.json`. 추가 Tripo 호출/크레딧 0.


## 최신 0.11.9.9 · 2026-10-21

- 운영 서버 버전 0.11.9.9, 빌드 21727f56, 정상 응답과 점검 공지 해제를 확인했습니다. 최신 클라이언트 0.11.9.9, 최소 접속 0.11.9.4입니다.
- 설치 파일·ZIP·자동 패치 공개 완료. 공개 목록의 버전, 파일 크기 및 SHA-256 메타데이터를 로컬 산출물과 비교했고 0.11.9.8용 공개 패치 전체의 SHA-256도 일치했습니다.
- 0.11.9.8 → 0.11.9.9 패치: 55,288바이트, 변경 5파일, 삭제 0파일. 0.11.9.2~0.11.9.8용 자동 패치를 제공합니다.
- 플레이어 8명 달리기 검사 24개는 소스·출시 PCK·실제 0.11.9.8 설치본에 패치를 적용한 경우 모두 통과했습니다. 기존 전환 검사 93개, 실제 이동 266샘플도 통과했습니다.
- 몬스터 백화는 대표 얼음 몬스터 공격 장면을 수정 전후로 직접 렌더링해 확인했습니다. 전체 몬스터·모든 지형을 전수 검수한 결과는 아닙니다.
- 서버 예고 대기 0분으로 배포했습니다. 기존 서버의 5분 간격 자동 감지 경로를 사용했고 새 빌드의 정상 응답까지 확인했습니다. 추가 유료 생성 호출 0회입니다.
- 새 로컬 빌드: `builds/school-01199/Villagen.exe`. 실행 중인 이전 빌드의 파일은 덮어쓰지 않았습니다. 적용하려면 게임을 재실행해야 합니다.
- 근거: `artifacts/release-01199-verification.json`, `artifacts/release-01199-finalize.log`, `artifacts/release-01199-upgrade-0.11.9.8/result.log`, `artifacts/run-white-comparison.mp4`.


## 공방 제작 긴급 수정 · 2026-10-21

사용자가 제작 1단계 장기 대기와 여러 명 제작 불가를 보고했습니다. 코드에서 다른 사람의 진행 중 제작이 한 건만 있어도 요청·제작 확정을 거절하는 서버 전체 제한과, 한 작업의 설계·이미지 생성을 기다리는 동안 전체 공방 처리가 멈추는 직렬 실행을 확인했습니다. 특정 운영 요청의 로그를 직접 조회한 결과는 아닙니다.

- 기본 동시 처리 4건, 서버 전체 접수 한도 32건으로 변경했습니다. 사용자 한 명당 진행 중 의뢰 1건은 유지합니다. 작업별 임대와 결제 예약은 그대로 적용해 같은 요청의 중복 제출·과금을 막습니다.
- 공방 작업자를 기존 생성 작업자와 분리했습니다. 느린 의뢰가 있어도 다른 작업의 완료 확인과 다음 사용자의 제작을 진행합니다. 일시적인 스케줄러 오류는 다음 주기에 다시 확인합니다.
- LLM 설계 전체에 180초 제한을 적용했습니다. 초과 시 기존 클라이언트의 시간 초과 안내를 표시하고 별씨를 한 번 환불합니다. 작업자가 사라진 설계도 서버 재시작 없이 회수합니다.
- `TRIPOTHON_STUDIO_WORKERS=4`, `TRIPOTHON_STUDIO_QUEUE_LIMIT=32`, `TRIPOTHON_STUDIO_DESIGN_DEADLINE=180` 기본값입니다. Tripo가 이미 접수한 작업의 불명확한 결과와 예산 제한은 기존 방식으로 보존합니다.
- 검증 97개 통과: 느린 설계 중 후속 사용자 완료, 두 사용자 동시 유료 작업 제출·각자 결과물, 대기열 한도, 단일 환불, 중복 과금 방지, 실제 서버 시작·종료 경로. 외부 생성 API는 모의 제공자로 시험해 이번 검증의 유료 호출은 0회입니다.
- 서버만 수정합니다. 0.11.9.9 클라이언트·설치 파일·자동 패치는 재생성하지 않습니다. 배포 후 실제 서버 빌드 확인 결과를 덧붙입니다.
- 시험 기록: `artifacts/craft-final-tests.log`.
