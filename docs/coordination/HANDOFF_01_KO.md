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
   - `docs/releases/school_changes_KO.txt` 맨 위에 `== 0.11.8 (2026-10-16)` 절을 추가합니다(초안: C:\Users\dd\AppData\Local\Temp\claude\C--lsm26-triphthonS1\3d7d7a09-3a2f-44bf-ab93-48415f8d8e6d\scratchpad
otes_0118_draft.txt).
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
- 배포 점검표: env에 `TRIPOTHON_ENABLE_LEGACY_GENERATION`이 없거나 false인지 확인합니다.
- 테스터 계정 tripo1~5는 배포 뒤 사용자가 VM에서 만듭니다(비밀번호는 숨김 입력). 명령은 `ops/README.md`에 있고 `-f ops/compose.gcp-free.yaml`을 붙입니다.

## 0.11.8 뒤 병합 대기열 (C:\Users\dd\AppData\Local\Temp\claude\C--lsm26-triphthonS1\3d7d7a09-3a2f-44bf-ab93-48415f8d8e6d\scratchpadfter_0118_queue.txt)

- wt/build 5f4e1c5: 방 벽·천장 배치 클라이언트
- wt/home 031ae19: 문 훅 연결
- codex/farm(N4 클라이언트와 함께), codex/rig67·movein43·secaudit·perf·shops·ja: 총괄이 요청합니다.
- 탐험 로그라이크 a208479: 스위치 기본값을 꺼서 넣습니다.

## 주의

- 공유 에셋 정션이 있는 worktree는 C:\Users\dd\AppData\Local\Temp\claude\C--lsm26-triphthonS1\3d7d7a09-3a2f-44bf-ab93-48415f8d8e6d\scratchpadm_wt.ps1로만 지웁니다(정션을 먼저 끊음).
- strings.json 충돌은 C:\Users\dd\AppData\Local\Temp\claude\C--lsm26-triphthonS1\3d7d7a09-3a2f-44bf-ab93-48415f8d8e6d\scratchpad\strings_merge.py로 JSON 합집합을 만들어 풉니다. 풀고 나서 중복 키를 검사합니다.
- `.import` 줄바꿈 변화(수천 개)와 추적되지 않는 `.uid`는 커밋하지 않습니다.
