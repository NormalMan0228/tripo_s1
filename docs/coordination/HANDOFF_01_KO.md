# 01 통합·배포·서버 인수인계 (2026-10-16)

새 세션은 이 문서부터 읽으세요. 0.11.8 배포를 이어서 할 수 있게 적었습니다.

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
