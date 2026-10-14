# 학교판 설치 파일 배포 (S3)

2026-10-12부터 설치 파일·압축 파일은 GitHub 릴리스에 올리지 않는다. GitHub은 코드와 작업 기록만 둔다.
(큰 exe를 며칠 새 여러 번 올린 직후 계정이 바깥에서 숨겨졌다.)

- 내려받기 페이지(항상 최신): `publish_school_build.py`가 출력하는 `index.html` 주소. **저장소·릴리스·PR에는 이 주소나 exe·zip 링크를 적지 않는다**(2026-10-12 GitHub 계정 제한 사유, 티켓 4850901). 학생에게는 학교 공지로만 알린다.
- 파일 위치: `school/<버전>/Villagen_School_Setup.exe`, `Villagen_School_Windows.zip`, `SHA256SUMS_School.txt`
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

