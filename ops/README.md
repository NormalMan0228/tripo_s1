# Tripothon 온라인 서버 파일

이 구성은 **초대형 소규모 시범 서비스**를 위한 것이다. 서버를 실제로 공개하려면 별도의 Linux 호스트, 도메인, DNS 설정이 필요하다. 로컬 `demo` DB와 재화는 가져오지 않는다. `ops/compose.yaml`은 가입·게임 플레이를 켜고 AI 과금은 끈 상태로 시작한다. 유료 생성은 운영 점검 후 `ops/compose.paid.yaml`을 추가해 켠다.

## Google Cloud 무료 VM 데모 서버

Google Cloud Always Free는 미국의 지정된 3개 리전에서 월 1대분 `e2-micro`, 표준 영구 디스크 30GB·무료 외부 전송량 1GB를 제공한다. `e2-micro`는 메모리 1GB여서 **AI 생성 과금은 끄고 소수 심사자용 데모**로 시작한다. GLB가 여러 번 다운로드되면 전송량이 무료 한도를 넘을 수 있으므로 과금 알림/예산과 실제 사용량을 확인한다. 이 한도는 서버의 640MB와 프록시의 96MB 메모리 제한을 적용하는 `ops/compose.gcp-free.yaml`에 반영했다. 이는 부하 시험을 통과한 성능 보장이 아니다.

Google Cloud 콘솔에서 2단계 인증과 무료 체험판/결제 계정을 계정 소유자가 활성화한 뒤 `us-west1`, `us-central1`, `us-east1` 중 하나에 `e2-micro` Linux VM과 30GB 이내 표준 영구 디스크를 만든다. 공인 IPv4를 부여하고 SSH 관리 포트는 운영자 IP에서만 허용한다. 방화벽에 80/TCP와 443/TCP만 공개하고 API 8765는 열지 않는다. 별도 도메인이 없다면 공인 IPv4가 `123.45.67.89`일 때 `123-45-67-89.sslip.io`를 `TRIPOTHON_DOMAIN`에 넣는 무료 DNS 방식이 있다. 이는 제3자 DNS에 의존하는 데모용 주소이며 IP가 바뀌면 주소와 게임 설정도 바꿔야 한다.

**자동 결제 방지:** Google Cloud 결제 계정을 `Free trial account` 상태로 유지하고 `업그레이드`/`Activate`를 누르지 않는다. 무료 체험판은 카드로 자동 청구되지 않지만 크레딧 소진 또는 90일 경과 시 서버가 중지되고 나중에 데이터가 삭제될 수 있으므로 백업이 필요하다. `e2-micro`와 표준 디스크의 무료 한도와 별개로 외부 IPv4, 초과 전송량 등은 사용량이 발생할 수 있고 무료 체험 크레딧에서 차감된다. 예산 알림은 지출을 멈추는 하드캡이 아니며 청구 기록은 지연될 수 있다. 이 구성에는 Tripo/OpenAI 키를 넣지 않고 유료 생성도 켜지 않는다.

Debian 12 VM에서 `sudo apt-get update && sudo apt-get install -y git`으로 Git을 설치하고 저장소의 온라인 서버 브랜치를 체크아웃한 다음 `sudo bash ops/bootstrap-gcp-free.sh`를 실행한다. 스크립트는 공식 Docker 저장소에서 Engine/Compose를 설치하고, 기존 부팅 디스크에 스왑 1GB를 만들고, 공인 IP 기반 `sslip.io` 주소·비공개 초대 코드를 생성해 무료 VM용 Compose 구성을 시작한다. 기존 `ops/production.env`와 초대 코드는 덮어쓰지 않는다. 실제 접속 주소를 출력하지만 초대 코드는 출력하지 않으므로 VM에서 별도로 안전하게 확인한다. 먼저 Google Cloud 방화벽에서 80/443을 허용해야 TLS 인증서 발급이 성공한다.

배포 후 VM에서 `sudo python3 ops/smoke_live.py`를 실행하면 HTTPS로 임시 계정을 만들고 API 컨테이너를 재시작한 뒤 같은 계정으로 로그인한다. 이는 SQLite 볼륨의 지속성까지 확인하며 초대 코드·비밀번호·토큰을 출력하지 않는다.

서버 준비 후 아래 **최초 설치**에서 Compose 명령에 `-f ops/compose.gcp-free.yaml`을 추가한다. 유료 AI 생성은 이 소형 VM에서 검증하지 않았으므로 기본적으로 끈다. 별도 호스트 또는 더 큰 유료 VM으로 옮기기 전에는 `ops/compose.paid.yaml`을 적용하지 않는다.

## 구조

```text
플레이어 Godot ── HTTPS :443 ── Caddy ── 사설 Docker 네트워크 ── FastAPI 단일 작업자
                                                               ├─ /data: SQLite + 비공개 GLB
                                                               ├─ /backups: 검증된 스냅샷
                                                               └─ /run/secrets: 초대 코드·API 키
```

API의 8765 포트는 외부에 게시하지 않는다. Caddy IP `172.30.72.2`만 프록시 헤더를 신뢰한다. 이 서브넷이 호스트 네트워크와 겹치면 **Caddy의 고정 IP, API의 고정 IP, 서브넷, `--forwarded-allow-ips`를 함께** 변경한다. Docker 볼륨의 DB와 자산은 컨테이너 재빌드에도 남는다. SQLite 작업자와 과금 작업을 여러 서버로 수평 확장하는 구성은 아니다.

## 최초 설치

1. Linux 서버에 Docker Engine/Compose를 설치하고, 도메인의 A/AAAA 레코드를 서버 IP로 연결한다. 방화벽에서는 80/TCP, 443/TCP, 필요하면 443/UDP만 공개한다. 8765는 공개하지 않는다.
2. 저장소를 배포 서버에 체크아웃한다. `ops/production.env.example`을 `ops/production.env`로 복사해 실제 도메인을 적는다. 이 파일에는 비밀을 넣지 않는다.
3. `ops/secrets`를 호스트에서 접근 제한된 디렉터리로 만들고 `registration-code` 파일을 만든다. 24자 이상의 무작위 ASCII 한 줄이어야 한다. 예: `python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > ops/secrets/registration-code`. 디렉터리는 0700, 파일은 `root:10001` 소유·0640 권한으로 설정한다. Compose 파일 기반 secret이 호스트 권한 그대로 마운트되고 API 프로세스가 gid 10001로 실행되기 때문이다. 초대 코드는 채팅, 이슈, Git, 클라이언트 빌드에 넣지 않는다.
4. 저장소 루트에서 `docker compose --env-file ops/production.env -f ops/compose.yaml config`로 구성을 확인하고 `docker compose --env-file ops/production.env -f ops/compose.yaml up -d --build`로 시작한다. `https://실제도메인/health`에서 `mode=live`, `protocol=6`, `studio_tripo_enabled=false`를 확인한다. 게임의 서버 입력란에 같은 HTTPS 주소를 넣고 새 계정을 만든다.

`ops/secrets`, `ops/production.env`, `ops/backups`는 Git과 Docker 빌드 컨텍스트에서 제외된다. Docker Compose의 파일 기반 secrets는 **API 컨테이너에만** 마운트된다. 운영 호스트 관리자와 Docker 접근 권한자는 이 비밀 및 데이터에 접근할 수 있으므로 그 계정을 제한한다. 도메인 TLS 인증서와 갱신 상태는 Caddy 로그로 확인한다.

## 유료 AI 생성 켜기

1. 별도의 OpenAI API 과금 계정과 Tripo API 계정을 준비한다. 키를 서버의 `ops/secrets/openai-key`, `ops/secrets/tripo-key`에 각각 ASCII 한 줄로 저장하고 0600으로 제한한다. 값은 터미널 명령 인수, 로그, Git, 게임에 남기지 않는다. `OPENAI_API_KEY`·`TRIPO_API_KEY` 환경변수와 파일 변수를 동시에 쓰면 서버가 시작을 거부한다.
2. 사용 가능한 OpenAI API 모델 이름과 Tripo 모델/요금을 운영 계정에서 확인한다. 현재 플레이어 공개 정책은 LLM `gpt-6-luna/high`와 제한된 Tripo 선택지에 고정되어 있다. **모델의 실제 API 사용 가능성·가격과 실제 생성은 아직 검증하지 않았다.** 필요한 경우 모델 매핑과 견적을 검증·수정한 뒤 켠다.
3. 서버 데이터 백업을 만들고 확인한다. `docker compose --env-file ops/production.env -f ops/compose.yaml -f ops/compose.paid.yaml config`로 비밀 파일 경로와 외부 포트가 맞는지 살핀 뒤 같은 인자에 `up -d --build`를 실행한다. `/health`의 `studio_tripo_enabled=true`를 확인한다.
4. 별도의 시험 계정으로 생성 요청 → 설계 및 견적 → 플레이어 확인 → Tripo 작업 → 비공개 GLB 다운로드 → 색칠·배치 → 재로그인을 끝까지 점검한다. 소액 예산으로 시작하고 공급자 콘솔에서 실제 청구액을 확인한다. 예상치가 실제 크레딧 비용을 보장하지 않는다.

기본 전역 한도는 하루 5회, 계정당 2회, 동시에 유료 작업 1개다. `ops/production.env`의 한도 값은 운영 규모에 맞춰 변경할 수 있다. 유료 모드에서는 두 API 키 또는 OpenAI 설계 제공자가 없으면 시작을 거부한다. 구형 `/v1/generations`는 기본 live 서버에서 차단되어 최종 견적 확인을 건너뛸 수 없다. 동적 스크립트는 제한된 수치 AST로 검증되며 서버의 Python 코드로 실행하지 않는다.

## 데이터와 사고 대응

백업은 단일 DB 파일 복사가 아니라 SQLite 온라인 백업과 자산 해시 검사를 함께 수행한다. 아래 이름을 매번 새로 지정한다.

```bash
docker compose --env-file ops/production.env -f ops/compose.yaml exec api python /app/tools/backup_server.py create --data-dir /data --destination /backups/snap-YYYYMMDD-HHMM
docker compose --env-file ops/production.env -f ops/compose.yaml exec api python /app/tools/backup_server.py verify --snapshot /backups/snap-YYYYMMDD-HHMM
```

백업 볼륨은 같은 호스트에 있으므로 암호화된 별도 저장소로 주기적으로 옮기고 복구를 연습해야 한다. 백업에는 비밀번호 해시와 사용자 자산이 포함된다. 복원 절차와 미확정 유료 작업의 수동 정합성 처리는 [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md)를 따른다. 과금 작업이 `unknown`이면 공급자 내역 확인 전 재제출하거나 임의 환불하지 않는다. 비밀 유출이 의심되면 공급자 키와 초대 코드를 교체하고 서버를 재시작하며, 해당 계정의 실제 사용 내역을 조사한다.

운영 전에는 호스트 패치, 로그 보존/개인정보 정책, 백업 자동화, 부하 시험, 침투 시험이 남아 있다. 이 코드는 공개 대규모 서비스 보안 인증을 받은 상태가 아니다.
