# 로컬 실행과 원격 서버 배포

온라인 시범 서버의 실행 가능한 Caddy·Docker Compose 구성과 키/DB/백업 운영 절차는 [`ops/README.md`](../ops/README.md)에 있다. 호스트와 도메인은 아직 제공되지 않아 실제 인터넷 서버는 개설하지 않았다.

## 0.8.1 공방 · 2026-10-02

현재 클라이언트/서버는 **protocol 6**다. `builds/Tripothon_Demo_081/Play.cmd`는 Python/Godot 설치 없이 로컬 시연한다. 패키지에는 계정, API 키, 개발자의 개인 생성물, Codex 로그인 정보가 없다. 기본 공방은 고정 설계와 도형 메시를 사용한다. 이는 실제 AI 생성으로 표시하지 않는다.

개발 프로젝트의 `Open_Studio.cmd`는 별도 8766 서버와 `artifacts/studio-review-data`를 사용한다. 실제 비교용 가구가 있는 개발자 검토 환경이며 배포하지 않는다. 실행기는 유료 Tripo 호출을 끈다. 일반 게임 서버는 8765를 사용한다. 버전이 다른 서버를 자동 강제 종료하지 않는다.

운영 LLM은 `TRIPOTHON_STUDIO_LLM=openai`와 서버 전용 `OPENAI_API_KEY`로 연결한다. `codex` 모드는 이 PC 구독으로 개발 설계를 비교하기 위한 것으로, 플레이어 서비스 운영에 사용하지 않는다. 공급자 모델과 effort, 키를 클라이언트가 임의로 확장할 수 없다. 플레이어 생성 과정에는 Blender가 없다.

Tripo는 기존 비밀 설정 외에 `TRIPO_ENABLE_PAID=true`가 필요하다. 생성 요청은 설계 검증 후 대기하며, 소유자가 최종 견적을 확인해야 유료 요청이 시작된다. 기본 `TRIPOTHON_STARS_PER_CREDIT=1`로 예상 Tripo 비용만큼 별씨를 환산하고 이미 예약한 별씨와의 차이를 원자적으로 차감한다. 도형 미리보기는 추가 과금 없이 동작을 검토하며 실제 메시 외형을 보장하지 않는다. 공급자 가격 변경 시 `server/studio_pricing.py`와 안내를 함께 갱신한다.

`studio_jobs`, `studio_assets`, `studio_runtime`, `generated_apis`, `asset_categories`, `furniture_locations`, `studio_leases`를 자동 추가한다. 기존 계정과 소유권을 유지하며 구형 공방 DB에는 부품 보정 `bindings` 열을 추가한다. 업데이트 전에 서버를 종료하고 DB와 자산 폴더를 함께 백업한다. 파일이 없는 DB 단독 복원은 가구를 복원하지 못한다.

공방 작업의 `unknown` 상태는 재요청하지 않는다. 이미 결제됐을 수 있으므로 알려진 task ID와 공급자 내역을 확인해야 한다. 다운로드 실패 후에도 확인된 크레딧을 기록하며, 공급자가 비용을 보고하지 않으면 0으로 표시하지 않는다. 임대와 heartbeat는 중복 작업 위험을 줄이지만 다중 서버 운영 검증을 대신하지 않는다.

0.8.1 백업은 첫 메시뿐 아니라 모든 조립 부품과 다운로드가 끝난 미완성 작업의 부품도 포함한다. 경로·해시가 충돌하면 실패한다. 복원 시 세션과 작업 임대를 폐기하고, 모든 미완료 공방 작업을 `unknown`으로 보류한다. 스냅샷 시점에 queued였더라도 그 뒤 제공사에 제출됐을 수 있으므로 자동 재요청하지 않는다. 부품 색상, 회전축 보정, 배치 방, 생성 코드와 상태는 DB와 함께 복원된다.

공방 복구는 해당 데이터 디렉터리의 서버를 먼저 종료한 운영자 터미널에서만 수행한다. `tools/reconcile_studio.py list-held --data-dir <폴더>`로 보류 작업을 본다. `resume-known`은 `--job-id`, `--key-file`, `--backup-root`, `--evidence-reference`를 요구하며 이미 기록된 3D task만 조회한다. 준비된 파일 또는 확인된 3D 작업이 없는 부품이 하나라도 있으면 거부한다. 이미지 보정 단계가 남은 작업은 이 도구로 자동 재개하지 않는다. live DB는 기존 서버 설정 환경을 사용한다.

제공사 내역에서 **제출되지 않았음을 운영자가 확인한 경우에만** `refund-not-submitted --verified-not-submitted --data-dir <폴더> --job-id <ID> --backup-root <새 백업의 상위 폴더> --evidence-reference <조사 기록 번호>`로 게임 재화 예약을 해제한다. API 키가 필요 없고, 기록된 task/이미지 작업/비용이 있거나 원장이 맞지 않으면 거부한다. 두 변경 명령 모두 먼저 비공개 백업을 만들며 조사 기록을 감사 로그에 남긴다. 제공사 크레딧 환불 기능이 아니다.

기존 0.7 로컬 서버는 `artifacts/backups/before-studio-081`로 백업·검증한 뒤 0.8.1로 갱신했다. 기존 사용자 2명, 물건 2개, 원장 2개, 탐험 1개, 생활 저장 1개의 모든 행이 그대로 유지됨을 비교했다. 실제 비교 가구 DB의 모든 부품 백업은 `artifacts/backups/studio-081-all-parts`에 보관한다. 이 폴더들은 공개 배포 대상이 아니다.

최종 0.8.1 실행 폴더로 전환하기 전 `artifacts/backups/before-final-081`을 생성·검증했다. 전환 후에도 사용자·소유 물건·원장·생존 기록·생활 저장의 전체 행이 동일하다(`artifacts/final-upgrade-check.json`). 일반 게임은 기존 저장 경로를 계속 사용한다.

아래 0.7/0.6과 10월 1일 잔액 0 기록은 이전 배포 기록이다. 10월 2일 실제 유료 생성과 잔액은 프로젝트 `README.md`의 Tripo 실측 비교를 따른다.

## 로컬 시연

현재 0.7의 클라이언트/서버 프로토콜은 **4**다. 새 배포 폴더는 `builds/Tripothon_Demo_07`이며, 기존 패키지의 게임을 닫고 그 패키지의 StopServer.cmd를 실행한 후 새 Play.cmd를 사용한다. `homesteads` 테이블을 자동 추가하며 기존 저장 경로/계정/별씨/물건/탐험을 유지한다. 마을 생활 성장/낚시 시간은 서버 시계에 의존한다. 변경 전 실제 데모 DB 백업은 `artifacts/backups/before-village-07`, 0.6 ZIP은 `artifacts/before-village-07`에 보존했다. 아래 0.6 설명은 이전 마이그레이션 기록이다.

`Play.cmd` 또는 `tools/start.ps1`은 현재 PC의 설치된 Python 가상환경과 Godot 4.7.2를 사용한다. 서버는 127.0.0.1:8765에만 바인딩하며 외부에 공개하지 않는다. 기본 DB와 비공개 생성 파일은 `server-data/`에 저장된다. 데이터 디렉터리는 Git·Docker 이미지·배포 소스에서 제외한다.

서버를 종료하려면 서버를 직접 실행한 터미널에서 Ctrl+C를 누르거나, `tools/stop_server.ps1`을 사용한다. 게임만 종료해도 서버는 계속 실행되므로 이후 다시 접속하면 기록이 남는다.

0.6 클라이언트는 `/health`의 `service=tripothon`, `protocol=3`를 확인한다. 서버도 함께 업데이트해야 한다. 새 이동·기력 필드가 없는 구버전 서버에는 로그인 전에 안내를 표시한다. 실행기는 알 수 없는 프로세스를 자동 종료하지 않는다. 구버전 서버를 기존 종료 스크립트로 종료한 뒤 새 버전을 실행한다. DB를 지우지 않으며, 기존 생존 기록에 없는 기력 필드는 서버가 초기화한다. 예전 캠프 중앙에 저장된 플레이어는 새 모닥불 충돌체 밖으로 옮겨진다. 이번 수정 전 로컬 DB는 `artifacts/backups/before-survival-05`에 백업·검증했다.

0.6은 `profiles` 테이블을 추가하며 기존 계정·원장·소유 물건을 유지한다. 구버전 생존 기록은 숲/탐험 난이도로 읽는다. 0.6 변경 전 실제 데모 DB의 백업은 `artifacts/backups/before-expansion-06`이다. 새 설치 없는 패키지는 `builds/Tripothon_Demo_06`에 있고, 기존 0.5 실행 폴더를 덮어쓰지 않는다. 두 버전은 같은 기본 포트를 사용하므로 함께 실행하지 않는다. 기존 서버를 자체 StopServer.cmd로 종료한 뒤 새 Play.cmd를 실행한다. 저장 위치는 동일한 `%LOCALAPPDATA%/TripothonDemo/server-data`다.

## 원격 구성

호스팅 계정/도메인이 아직 지정되지 않았으므로 실제 서버를 공개하지 않았다. `server/Dockerfile`은 배포 준비 파일이며 이 환경에서 Docker 빌드를 검증한 것은 아니다.

작은 시연은 HTTPS reverse proxy → 단일 Uvicorn 프로세스 → SQLite/비공개 자산 디렉터리 구조로 시작할 수 있다. 다음 조건을 모두 구성한다.

1. `TRIPOTHON_MODE=live`, demo와 다른 `TRIPOTHON_DATA_DIR`, 영구 데이터 볼륨.
2. 서버 비밀 저장소에 `TRIPO_API_KEY` 또는 서버 전용 파일을 가리키는 `TRIPO_API_KEY_FILE`, 24자 이상의 `TRIPOTHON_REGISTRATION_CODE` 설정. 코드/이미지/클라이언트에 넣지 않는다.
3. 유효한 HTTPS 인증서. 외부 사용자는 reverse proxy로만 접근한다. Uvicorn 포트의 외부 직접 접속은 네트워크에서 막는다.
4. Uvicorn의 `--forwarded-allow-ips`에는 실제 프록시 IP만 지정한다. Docker 기본값 127.0.0.1은 같은 네트워크 네임스페이스의 프록시만 신뢰한다. 별도 컨테이너 프록시를 사용할 때는 그 IP/신뢰 경계를 명시적으로 구성해야 한다. `*`로 넓히지 않는다.
5. `--workers 1`을 유지한다. SQLite와 단일 생성 작업자는 다중 프로세스 분산 스케줄링을 구현하지 않았다.
6. 읽기 전용 잔액 점검 성공 후 `TRIPO_ENABLE_PAID=true`를 설정한다. 요청 한도와 실제 모델 가격을 공급자 문서에서 확인한다.
7. 게임의 서버 주소를 HTTPS 주소로 바꾸고 별도 계정으로 가입한다. 0 별씨에서 시작하므로 생존 완주로 게임 재화를 획득한다.

## 검증할 실제 연동

- 잔액 점검: 키를 가린 상태에서 JSON 성공 또는 정리된 오류 코드 확인.
- 실제 1회 생성: 텍스트 → Tripo task ID → success → 검증된 GLB → 생성자의 보관함.
- 게임에서 다운로드·색칠·배치 후 재접속 복원.
- 다른 계정에서 모델 ID를 알아도 접근 불가, 판매 후 이전 소유자 접근 불가.
- 지급/구매/생성 원장, DB·자산 백업 및 복원 확인.

`unknown` 생성 상태는 Tripo에 제출되었을 수 있으나 결과를 기록하지 못했다는 뜻이다. 공급자 작업 내역을 확인하기 전에는 자동 재시도·환불·잠금 해제를 하지 않는다. 서버 운영자는 아래 CLI로 검토 결과를 반영한다. 클라이언트용 우회 API는 없다.

## 보류된 생성 복구

`tools/reconcile_job.py --data-dir (live 데이터 경로) list-held`로 보류 기록을 확인한다. API 키/원문 응답/프롬프트는 출력하지 않는다. 운영자가 공급자 작업 내역에서 해당 계정·프롬프트·제출 시점을 대조한 뒤:

- 작업 ID를 찾은 경우 `--data-dir`, `--backup-root`, `--job-id`, `--evidence-reference`, `--key-file`을 지정하고 `attach-task --task-id (확인한 ID)`를 실행한다. 작업 조회에 성공해야 기존 task만 재조회하도록 연결한다. 이미 기록된 다른 ID로 바꾸거나 다른 게임 작업에 붙은 ID를 재사용할 수 없다. 새 유료 제출을 하지 않는다.
- **제출되지 않았다는 사실을 공급자 기록으로 확인한 경우에만** 같은 운영 인자와 `refund-not-submitted --verified-not-submitted`를 사용한다. `--key-file`은 이 동작에는 필요 없다. API가 부재를 자동 증명하는 기능은 없으므로 이 플래그는 운영자의 확인 선언이다. 작업 ID가 이미 있으면 이 환불 경로를 거부한다.

두 동작 모두 변경 전에 새 백업을 만들고, 트랜잭션과 원장·감사 기록을 남긴다. 근거 식별자에는 비밀키나 응답 본문 대신 운영 티켓 번호 같은 짧은 참조를 쓴다. 반복 실행해도 환불이 중복 지급되지 않는다. 이 CLI는 운영자만 서버 터미널에서 사용하며 웹 관리자 API로 노출하지 않는다.

2026-10-01 실제 Tripo 계정의 인증/잔액 조회는 성공했고 가용 잔액은 0.0이다. 유료 요청은 하지 않았다. 실제 생성 경로는 모의 Tripo HTTP 응답으로 검증했다. DNS/TLS·실제 생성·외부 네트워크·Docker 빌드·공개 서버 부하와 보안은 배포 시 별도 검증 대상이다.

## 백업과 복원

운영자 전용 위치를 사용한다. 아래 destination은 기존에 없는 새 디렉터리여야 한다. 백업 시 서버를 끌 필요는 없지만, 복구한 데이터로 전환할 때는 기존 서버를 중단하고 공급자 작업/백업 이후 거래를 대조한다.

```powershell
.\.tools\server-venv\Scripts\python.exe tools/backup_server.py create --data-dir server-data --destination artifacts/backups/new-snapshot
.\.tools\server-venv\Scripts\python.exe tools/backup_server.py verify --snapshot artifacts/backups/new-snapshot
.\.tools\server-venv\Scripts\python.exe tools/backup_server.py restore --snapshot artifacts/backups/new-snapshot --destination artifacts/restored-demo --mode demo
```

복원은 새 디렉터리를 만들고 모든 세션을 폐기한다. 모든 진행 중 생성은 unknown으로 보류되므로 작업 내역 확인 없이 잠금을 해제하지 않는다. 원본 DB에는 영향을 주지 않는다. 실제 로컬 DB의 백업/검증도 `artifacts/backups/local-20261001-01`에서 실행했다.

## Windows 패키지 재빌드

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_game.ps1
powershell -ExecutionPolicy Bypass -File tools/build_demo_server.ps1
powershell -ExecutionPolicy Bypass -File tools/test.ps1 -Packaged -PortableServer -Capture -Night
powershell -ExecutionPolicy Bypass -File tools/test.ps1 -Packaged -PortableServer -Capture -FullRun
.\.tools\server-venv\Scripts\python.exe tools/package_demo.py
```

서버 빌드는 PyInstaller 6.22.3을 사용한다. 휴대용 서버는 loopback demo 전용이며 키를 읽지 않는다. 실제 live 서버는 서버 소스/Docker 경로로 배포한다. 고객에게 live 운영 데이터/서버 비밀을 넣어 배포하면 안 된다. Windows release EXE는 경로 덮어쓰기를 차단하므로 테스트 스크립트를 직접 주입할 수 없다. 따라서 EXE의 독립 시작을 확인하고, 내보낸 동일 PCK의 통합 검사는 Godot 실행기로 수행했다.
