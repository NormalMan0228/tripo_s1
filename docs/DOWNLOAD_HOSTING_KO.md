# 학교판 설치 파일 배포 (S3)

2026-10-12부터 설치 파일·압축 파일은 GitHub 릴리스에 올리지 않는다. GitHub은 코드와 작업 기록만 둔다.
(큰 exe를 며칠 새 여러 번 올린 직후 계정이 바깥에서 숨겨졌다.)

- 내려받기 페이지(항상 최신): `publish_school_build.py`가 출력하는 `index.html` 주소. **저장소·릴리스·PR에는 이 주소나 exe·zip 링크를 적지 않는다**(2026-10-12 GitHub 계정 제한 사유, 티켓 4850901). 학생에게는 학교 공지로만 알린다.
- 파일 위치: `school/<버전>/Villagen_School_Setup.exe`, `Villagen_School_Windows.zip`, `SHA256SUMS_School.txt`,
  패치는 `school/patches/<베이스>_to_<버전>.pck`와 목록 `school/patches.json` (아래 "패치 업데이트")
- 설정: `tools/download_host.json` (버킷 `villagen-school-dl`, 서울 리전, 키 프로필 `villagen-upload`)
- 비용: 보관 GB당 월 약 0.025달러, 내려받기는 AWS 계정 전체 월 100GB까지 무료.

## 처음 한 번 (사용자)

1. AWS 콘솔 → IAM → 사용자 → **사용자 생성**: 이름 `villagen-upload`, 콘솔 접근 없음.
2. 그 사용자 → 권한 추가 → **인라인 정책 생성** → JSON에 아래를 붙여 넣고 이름 `villagen-school-dl-upload`로 저장.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ManageDownloadBucket",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket", "s3:ListBucket",
        "s3:PutBucketPolicy", "s3:GetBucketPolicy",
        "s3:PutBucketPublicAccessBlock", "s3:GetBucketPublicAccessBlock"
      ],
      "Resource": "arn:aws:s3:::villagen-school-dl"
    },
    {
      "Sid": "ManageDownloadFiles",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:AbortMultipartUpload"],
      "Resource": [
        "arn:aws:s3:::villagen-school-dl/school/*",
        "arn:aws:s3:::villagen-school-dl/private/*"
      ]
    }
  ]
}
```

3. 그 사용자 → 보안 자격 증명 → **액세스 키 만들기** → 용도 "로컬 코드" 선택.
4. 이 PC 터미널에서 직접 실행하고 키 두 개를 붙여 넣는다(비밀 키는 화면에 안 보임):

```
powershell -ExecutionPolicy Bypass -File tools\aws_upload_login.ps1
```

키는 `%USERPROFILE%\.aws\credentials`에만 저장된다. 저장소에는 들어가지 않는다.

## 버킷 준비 (한 번, Claude)

```
.tools\art-venv\Scripts\python.exe tools\publish_school_build.py setup
```

"Public read was refused"가 나오면: S3 콘솔 → 왼쪽 **이 계정에 대한 퍼블릭 액세스 차단 설정** → 편집 →
"버킷 정책을 통해 부여된…" 두 항목만 끄고 다시 실행한다. 공개되는 것은 `school/` 아래 파일 읽기뿐이다.

## 배포할 때마다

0. `docs/releases/school_changes_KO.txt` 맨 위에 `== 버전 (날짜)`와 `- 바뀐 점` 줄들을 적는다. 로드맵(`roadmap.json` → `build_roadmap.py`)도 갱신.
1. 깨끗한 사본에서 빌드 → `package_release.py --school --game-only` → `--installer`
2. `publish_school_build.py upload` → 설치 파일과 함께 `CHANGES_KO.txt`(바뀐 점·고친 점), `ROADMAP_KO.txt`(계획·진행), `roadmap.png`도 올라가고 페이지에 링크된다.
   기록만 고칠 때는 `publish_school_build.py docs`.
3. `publish_school_build.py check --full` → `download check: PASS`
4. `python tools/update_download_links.py` → README 첫 화면의 설치 안내(버전·방법만, 링크 없음) 갱신
5. VM: `sudo bash ops/notice.sh release <버전> <내려받기 페이지 주소>` (게임 안 알림은 서버가 주소를 전하므로 저장소에 주소가 없어도 된다)
6. 오래된 버전 정리: `publish_school_build.py prune 2` (최신 2개만 남김)

## 패치 업데이트 (0.11.5 설치본부터)

설치한 게임(`Villagen.exe` + `Villagen.pck`, 약 1.8GB)을 매번 새로 받지 않고, 바뀐 파일만 담은 작은
패치(`.pck`)를 게임이 스스로 받는다.

- **게임 동작**
  - 켜면 타이틀 메뉴보다 먼저 서버에 버전을 묻는다("최신 버전인지 확인하고 있어요…").
  - 서버가 더 새 버전을 알리면 바로 업데이트 화면: 패치 목록 확인 → 내려받기(진행 막대, 끊기면 이어 받기)
    → SHA-256 확인 → "업데이트 완료! 게임을 다시 시작해요." → 게임이 스스로 다시 켜지고 새 버전으로 실행된다.
    선택이 아니라 필수다.
  - 플레이 중에 새 버전이 나오면 위쪽에 "새 버전이 있어요 · 타이틀로 돌아가면 업데이트해요" 안내만 뜨고,
    타이틀로 돌아가는 순간 업데이트한다. 서버가 최소 버전(`min`)을 올리면 플레이 중이어도 바로 업데이트한다.
  - 패치로 안 되는 릴리스(아래)면 "새로 설치해야 해요" 창과 내려받기 페이지 버튼이 뜬다.
  - 패치 목록이 아직 안 올라왔으면 "새 버전을 준비하고 있어요" 창에서 45초마다 다시 확인한다.
- **구조**
  - 베이스: 전체 설치판으로 낸 버전의 pck. `builds/bases/<버전>/Villagen.pck` + `base.json`(엔진·템플릿 기록).
    `upload` 할 때마다 자동 보관, 최근 3개만 남는다(각 약 1.8GB, git에 안 들어감). 지워진 베이스의 설치본은 설치 파일로 업데이트.
  - 패치: 베이스마다 하나, 최신 버전까지 한 번에 가는 누적 패치 `patches/<베이스>_to_<최신>.pck`
    (Godot `--export-patch`, 바뀐 파일 + 지워진 파일 표시만). 0.11.3→0.11.4 실측: 1.8GB 대신 17MB, 내보내기 39초.
  - 목록: 내려받기 페이지 옆 `patches.json` (최신 버전, 베이스별 파일·크기·SHA-256 또는 `requires_reinstall`).
    게임은 서버(`/v1/client`)가 알려 주는 주소로 읽는다. 기본은 페이지(`index.html`) 옆 `patches.json`이라
    서버 설정을 따로 할 필요가 없다(`notice.sh patches <주소>|auto|off`로 바꿀 수 있음).
  - 게임 쪽: 받은 패치는 `%APPDATA%\Godot\app_userdata\Tripothon — Seven Nights\patches\`에 저장된다.
    다음 실행 때 첫 번째 autoload `scripts/patch_boot.gd`가 다른 스크립트보다 먼저 패치를 불러온다.
    패치를 받은 뒤 세 번 연속 타이틀까지 못 가면 그 패치를 끄고 설치 파일을 안내한다.
    지원용: `Villagen.exe --no-patch`는 패치 없이 설치된 버전으로 켠다.
- **설치 파일이 필요한 릴리스** (`patch`가 자동으로 판단해 `requires_reinstall`로 적는다)
  - `engine`: Godot 버전이 바뀜 / `template`: 내보내기 템플릿(exe)이 바뀜
  - `boot`: `game/scripts/patch_boot.gd`가 바뀜(설치본의 것이 항상 먼저 실행되므로)
  - `settings`: `project.godot`에서 버전 말고 다른 설정이 바뀜(입력 키, autoload, 창 설정 등)
  - 0.11.4 이하 설치본에는 패치 기능이 없으므로, 패치를 쓰는 첫 버전(0.11.5)은 한 번 설치 파일로 배포한다.

### 패치로 배포할 때 (보통)

0. `docs/releases/school_changes_KO.txt`·로드맵 갱신(위와 같음).
1. 깨끗한 사본(무시된 에셋까지 있는 본 저장소)에서 `game/project.godot`의 `config/version`을 올리고 커밋.
2. `.tools\art-venv\Scripts\python.exe tools\publish_school_build.py patch --dry-run`
   → 베이스마다 "N files changed, M removed, X MB"와 설치 필요 여부를 확인한다.
   지워지는 파일이 많으면 에셋이 빠진 사본으로 보고 멈춘다(의도했으면 `--allow-removals`).
3. `publish_school_build.py patch` → 패치 파일을 먼저, `patches.json`을 마지막에 올린다.
4. `publish_school_build.py check` → `patch list: latest <버전>`과 각 패치 `OK`, `download check: PASS`.
5. `git push origin <커밋>:school-release` → 서버 자동 업데이트(점검 공지 → 모두 로그아웃 → 새 코드 →
   `notice.sh release <버전>`) → 게임들이 타이틀에서 패치를 받는다. 3번을 먼저 하면 바로 받고,
   늦어도 게임은 "준비하고 있어요"에서 기다렸다가 받는다.

### 설치 파일로 배포할 때 (엔진 변경 등, 위 "설치 파일이 필요한 릴리스")

위 "배포할 때마다" 1~6을 그대로 한다. `upload`가 이 버전을 새 베이스로 보관하고, 보관 중인 예전 베이스에서
이 버전으로 가는 패치(가능한 경우)와 `patches.json`도 같이 올린다(`--no-patches`로 끔).

### 점검과 로그아웃

- 점검이 **시작되는 순간** 서버는 그 전에 로그인한 모든 세션을 끝낸다(`sessions.created` < 점검 시작 → 401 `session_reset`).
  게임은 계정 설정을 보내 두고 타이틀로 돌아가 "서버 점검이 시작되어 로그아웃했어요" 화면과 남은 시간·예상 끝 시각을 보여 준다.
  점검이 끝나면 다시 로그인한다. 탐험은 서버에 남아 "이어하기"로 돌아갈 수 있다.
- `update_online_server.sh --announce`와 자동 업데이트도 같은 점검 공지를 쓰므로, 재시작 전에 모두 로그아웃된다.
- 점검 없이 모두 로그아웃시키기: `sudo bash ops/notice.sh logout-all`.

### 이 PC에서 시험

`game/tests/patch_update_check.gd`(QA 서버 + 테스트가 직접 띄우는 작은 패치 서버)와
`game/tests/version_gate_check.gd`(점검·강제 로그아웃). 실제 버킷이나 학교 서버는 쓰지 않는다.
QA 서버만 `notice.sh patches`/정책 파일에 `http://127.0.0.1:<포트>/...` 주소를 받을 수 있다.

## GitHub이 막혔을 때 서버에 코드 넘기기 (비상용)

VM은 평소 GitHub에서 코드를 받는다(`update_online_server.sh`의 `git pull`). GitHub이 막히면:

1. PC(사용자가 직접): `.tools\art-venv\Scripts\python.exe tools\send_code_to_vm.py`
   → 빠진 커밋만 묶어 `private/villagen-dev.bundle`에 올리고 VM 명령을 출력한다.
2. VM(EC2 Instance Connect 브라우저 창, PC PowerShell 아님): 출력된 줄을 차례로 붙여 넣는다.
   받는 곳을 묶음으로 잠시 바꿔 업데이트한 뒤 GitHub 주소로 되돌린다.

`private/`는 버킷 정책 `SchoolServerPrivateRead`로 **학교 서버 IP(54.117.10.64)만** 읽을 수 있다.
서버 IP가 바뀌면 그 정책의 IP도 바꾼다. 채팅에서 서명 주소를 복사하면 키 부분이 가려져 403이 나므로 서명 주소는 쓰지 않는다.

## 학교 서버 자동 업데이트 (2026-10-14부터)

VM에서 한 번만: `cd ~/tripo_s1` → `sudo git pull --ff-only origin dev` → `sudo bash ops/install_auto_update.sh`.
그 뒤로는 VM에 들어갈 필요가 없다.

- 배포: 위 1~4가 끝나면 `git push origin <커밋>:school-release`. dev에 올리는 것만으로는 배포되지 않는다.
- 서버가 5분마다 확인 → 새 커밋이면 10분 점검 공지(게임 안 카운트다운) → 백업 → 새 코드 → 재시작 →
  `notice.sh release <버전>`(저장된 내려받기 주소 유지). 대략 push 후 15~20분이면 끝난다.
- 실패하면 그 커밋은 다시 시도하지 않는다(브랜치가 다시 바뀔 때 재시도). 백업은 업데이트 스크립트가 먼저 만든다.
- 상태: `sudo bash ops/install_auto_update.sh --status` (로그 /var/log/villagen-autoupdate.log), 끄기: `--remove`.
- 점검 공지 시간·브랜치는 `/etc/systemd/system/villagen-autoupdate.service`의 Environment 줄.

