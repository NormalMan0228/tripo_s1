# Villagen 학과 공유 안내서

> 이 저장소는 누구나 받아 쓸 수 있습니다. 다만 **서버, AI 키, 계정, 비용은 각자 자기 것**을 씁니다.
> 원작자의 서버나 키는 이 안내서의 어떤 단계에도 쓰이지 않습니다.

---

## 한눈에 보기 — 나는 무엇을 하고 싶은가?

| 하고 싶은 것 | 고를 길 | 필요한 것 | 걸리는 시간 |
|---|---|---|---|
| 친구가 연 서버에서 **게임만** 하기 | [A. 게임만 하기](#a-게임만-하기) | Windows PC | 10분 |
| **내 PC**에 서버를 켜서 나 혼자, 또는 친구 몇 명과 하기 | [B. 내 PC 서버](#b-내-pc에-서버-켜기) | Tripo 키, Gemini 키, Godot | 1시간 |
| **학과 전체**가 접속하는 온라인 서버 만들기 | [C. 온라인 서버](#c-학과-온라인-서버-aws-서울) | AWS 계정, Tripo 키, Gemini 키 | 1~2시간 |
| 코드나 아트를 **고쳐서 개발**하기 | [D. 개발하기](#d-개발하기) | B의 준비물 + Git 사용법 | — |

**꼭 지킬 것**

- API 키는 **자기 PC 파일이나 자기 서버에만** 둡니다. Git 커밋, 카톡, 디스코드, 스크린샷, ZIP에 넣지 않습니다.
- 서버 데이터 폴더(`server-data/`, 서버의 `/data`)에는 다른 사람의 계정 정보가 들어 있으니 공유하지 않습니다.
- 물건을 만들 때마다 **Tripo 크레딧(돈)**이 듭니다. 서버를 열기 전에 [비용과 한도](#비용과-한도)를 먼저 정하세요.

---

## 1. 각자 만들 계정과 키

| 무엇 | 어디서 | 비용 | 언제 필요 | 저장 위치 |
|---|---|---|---|---|
| **Tripo API 키** | [platform.tripo3d.ai](https://platform.tripo3d.ai) → API Keys | 유료 크레딧 (제작 1회에 10~35크레딧) | 서버를 직접 켤 때 (B, C) | B: `바탕화면\tripo_key.txt` · C: 서버의 `ops/secrets/tripo-key` |
| **Gemini API 키** | [aistudio.google.com](https://aistudio.google.com) → Get API key | 무료 등급으로 충분 | 서버를 직접 켤 때 (B, C) | B: `바탕화면\gemini_key.txt` · C: 서버의 `ops/secrets/gemini-key` |
| GitHub 계정 | [github.com](https://github.com) | 무료 | 코드를 고쳐 올릴 때 (D) | — |
| AWS 계정 | [aws.amazon.com](https://aws.amazon.com) | 신규 크레딧 $100~200 (카드 인증 필요) | 온라인 서버 (C) | — |
| Tailscale 계정 | [tailscale.com](https://tailscale.com) | 개인 무료 | 내 PC 서버에 친구를 부를 때 (B) | — |

키 파일은 메모장으로 만들고 **키 한 줄만** 넣어 저장합니다. 따옴표나 공백 없이 넣습니다.
다른 위치에 두려면 환경 변수 `TRIPO_API_KEY_FILE`, `GEMINI_API_KEY_FILE`에 그 파일 경로를 넣습니다.

> 게임 속 **계정**(아이디·비밀번호)은 각 서버에 따로 만들어집니다. 서버마다 새로 가입해야 하고, 다른 서버의 계정은 서로 모릅니다.

---

## 2. 사용 프로그램과 버전

### 필수 (B, D)

| 프로그램 | 버전 | 설치 방법 | 비고 |
|---|---|---|---|
| Windows | 10 / 11, 64비트 | — | OpenGL 3.3을 지원하는 그래픽카드면 됩니다 (내장 그래픽 가능) |
| Git | 2.4x 이상 (확인한 버전 2.53) | [git-scm.com](https://git-scm.com/download/win) | 설치 옵션은 기본값 |
| uv | 0.11 이상 | PowerShell에서 `winget install astral-sh.uv` | Python을 대신 설치하고 관리합니다 |
| Python | **3.13** | `tools/setup.ps1`이 uv로 자동 설치 | 따로 설치할 필요 없음 |
| Godot | **4.7.2 stable** (Windows 64bit, 일반판. .NET판 아님) | [godotengine.org](https://godotengine.org) → Download → Archive → **4.7.2-stable** → Windows 64-bit를 받아 `.tools\godot\`에 풀기 (B-1) | 다른 버전으로 열면 파일이 바뀌니 꼭 4.7.2 |
| 디스크 여유 | **10GB 이상** | — | 큰 에셋 약 2GB + Godot 가져오기 캐시 약 2GB + 내려받은 ZIP |

서버 Python 패키지(자동 설치, `server/requirements.txt`): FastAPI 0.142.2, Uvicorn 0.54.0, httpx 0.28.1, Pillow 12.3.0, argon2-cffi 25.1.0, (테스트) pytest 9.1.1

### 선택 (필요한 사람만)

| 프로그램 | 버전 | 언제 | 설치 |
|---|---|---|---|
| Godot 내보내기 템플릿 | 4.7.2 | 게임 exe(배포 ZIP)를 직접 만들 때 | `tools/setup.ps1 -Export` |
| 아트용 Python 환경 | 3.13 + `tools/requirements-art.txt` | UI·아트 도구, 배포 ZIP 만들 때 | `tools/setup.ps1 -Art` |
| Blender | **4.5 LTS** (확인한 버전 4.5.3) | 캐릭터·몬스터·소품을 손볼 때 | [blender.org](https://www.blender.org/download/lts/4-5/) 포터블 ZIP을 `.tools\blender-portable\`에 풀기 |
| Tailscale | 최신 | 내 PC 서버에 친구를 부를 때 | [tailscale.com/download](https://tailscale.com) |
| Inno Setup | 6 | 설치 파일(Setup.exe)을 만들 때 | `.tools\innosetup\`에 설치 |

### 서버 쪽 (C, 자동 설치)

Ubuntu 24.04 LTS (Arm 또는 x86) · Docker와 Docker Compose · Caddy (HTTPS 인증서 자동 발급). 모두 `ops/bootstrap-gcp-free.sh`가 설치합니다.

### 설치 확인

저장소 폴더에서 **`Check_Setup.cmd`를 더블클릭**하면 무엇이 있고 무엇이 없는지 한 번에 보여 줍니다.

```
[OK]   Godot 4.7.2  .tools\godot
[없음] 큰 에셋 폴더 (DevAssets)  없음: game\maps\archipelago\assets → 팀에서 받은 개발용 에셋 묶음을 저장소 최상위에 풀기
[선택] Gemini 키 파일  C:\Users\...\Desktop\gemini_key.txt 에 aistudio.google.com 키 한 줄
```

---

## A. 게임만 하기

1. 게임 설치 파일은 GitHub에 두지 않습니다. 서버를 연 사람(또는 학교 공지)에게 받아 설치합니다.
2. `Villagen`을 실행합니다. Windows가 막으면 **추가 정보 → 실행**을 누릅니다.
3. **게임 시작 → 로그인** 화면의 **월드**에서 **직접 입력**을 고르고, 서버를 연 사람이 알려 준 주소를 넣습니다.
   - 예: `https://3-38-12-34.sslip.io` (온라인 서버), `http://100.101.1.2:8765` (Tailscale 친구 PC)
4. **계정 만들기**를 누릅니다. 비밀번호는 10자 이상이고 대문자와 특수문자가 하나씩 있어야 합니다.

> 기본으로 선택된 월드("온라인 월드" 또는 "학교 월드")는 원작자가 운영하는 서버입니다. 우리 서버를 쓰려면 반드시 **직접 입력**으로 주소를 바꾸세요. 한 번 넣은 주소는 저장됩니다.

### 서버를 연 사람: 주소가 들어간 게임 나눠 주기 (0.11.5 이후 빌드)

`Villagen.exe`와 같은 폴더에 `world.cfg` 파일을 만들면 "온라인 월드"가 우리 서버로 바뀝니다. 그 폴더째 나눠 주면 친구들은 주소를 입력하지 않아도 됩니다. 나눠 줄 때는 학과 드라이브처럼 **GitHub 밖의 공간**을 쓰고, GitHub에는 내려받기 주소를 적지 않습니다.

```ini
[world]
name="우리 학과 월드"
url="https://3-38-12-34.sslip.io"
```

메모장으로 저장할 때 인코딩은 **UTF-8**로 합니다. 0.11.4 이하 빌드는 이 파일을 읽지 않으니 **직접 입력**을 쓰세요.

---

## B. 내 PC에 서버 켜기

내 PC가 서버가 되어 나와 친구 몇 명이 함께 합니다. 물건 제작 비용은 **내 Tripo 키**에서 나갑니다.

### B-1. 처음 한 번: 설치

PowerShell을 열고 한 줄씩 실행합니다.

```powershell
git clone https://github.com/NormalMan0228/tripo_s1.git
cd tripo_s1
git checkout dev
powershell -ExecutionPolicy Bypass -File tools/setup.ps1
```

- `dev`가 최신 개발판입니다. `main`은 공모전 제출판(0.10.2)에서 멈춰 있습니다.
- `setup.ps1`은 Python 3.13 서버 환경을 만듭니다.
- Godot는 [godotengine.org](https://godotengine.org) → Download → Archive → **4.7.2-stable** → Windows 64-bit(.NET 아님)를 받습니다. 압축을 풀어 `Godot_v4.7.2-stable_win64.exe`와 `..._console.exe` 두 파일을 `tripo_s1\.tools\godot\` 바로 아래에 둡니다.
- 팀에서 내려받기 주소 목록 `tools/third_party_downloads.local.json`(Git에 올리지 않는 파일)을 받았다면 `tools/setup.ps1 -Godot`가 대신 받아 줍니다. 체크섬도 확인합니다.

### B-2. 큰 에셋 받기 (지도, 가구, 몬스터, NPC)

용량이 커서 Git에도, GitHub 페이지에도 없습니다. **팀 안에서 따로 전달**합니다(저장소 관리자에게 요청하세요). 묶음은 두 개입니다.

- 지도 묶음 (약 1.7GB, 다섯 섬 지도)
- 아트 묶음 (약 190MB, 실내 가구·몬스터·생존 맵·NPC·초상화)

두 묶음을 **저장소 맨 위 폴더(`tripo_s1`)에 바로** 풉니다. "여기에 풀기"를 쓰고, `tripo_s1\tripo_s1\...`처럼 폴더가 한 번 더 생기지 않게 하세요. 그다음 `Check_Setup.cmd`를 실행해 `큰 에셋 폴더`가 [OK]인지 확인합니다.

> 지도가 없어도 게임은 켜지지만, 평평한 임시 초원으로 나옵니다.

### B-3. 키 파일 두기

- `바탕화면\tripo_key.txt`: Tripo 키 한 줄
- `바탕화면\gemini_key.txt`: Gemini 키 한 줄

Gemini는 "무엇을, 몇 부품으로, 어떤 색으로 만들지"를 정하는 **설계**를 맡고, Tripo가 실제 **3D 모델**을 만듭니다. 키는 서버만 읽고 게임 화면에는 전달되지 않습니다.

### B-4. 첫 실행

1. `.tools\godot\Godot_v4.7.2-stable_win64.exe`를 실행합니다. **가져오기**로 `tripo_s1\game\project.godot`을 엽니다.
   - 처음 열 때 에셋을 가져오느라 **10~30분** 걸립니다. 끝날 때까지 기다립니다.
2. 서버를 켭니다. PowerShell에서 실행합니다.
   ```powershell
   powershell -ExecutionPolicy Bypass -File tools/play_tripo.ps1 -ServerOnly
   ```
   `Tripo-enabled server is ready at http://127.0.0.1:8765 ... design: gemini`가 나오면 준비된 것입니다.
3. Godot 편집기 오른쪽 위의 ▶(F5)를 누릅니다. 로그인 화면의 월드에서 **이 PC 월드**를 고르고 계정을 만듭니다.
4. 끌 때는 `Stop_Tripo_Server.cmd`를 실행합니다.

> exe로 만들어 두면(`tools/setup.ps1 -Export` 후 `tools/build_game.ps1`) 다음부터는 **`Play_Tripo.cmd` 더블클릭 한 번**으로 서버와 게임이 같이 켜집니다.

### B-5. 친구 부르기 (Tailscale)

서버를 인터넷에 공개하지 않고 사설망으로만 엽니다.

1. 나와 친구 모두 [Tailscale](https://tailscale.com)을 설치하고 로그인합니다. Tailscale 관리 화면에서 친구를 내 네트워크에 초대합니다.
2. 내 PC에서 `Host_Friends.cmd`를 실행합니다. 창에 친구가 쓸 주소(`http://100.x.x.x:8765`)가 나옵니다.
3. 친구는 A의 3번처럼 **직접 입력**에 그 주소를 넣고 가입합니다.

내 PC가 꺼지면 서버도 꺼집니다. 늘 켜 둘 서버가 필요하면 C로 가세요.

---

## C. 학과 온라인 서버 (AWS 서울)

언제든 접속할 수 있는 서버입니다. 서버를 만드는 사람이 **비용과 키를 책임집니다**.

### 비용 감각

| 항목 | 월 비용 (대략) |
|---|---|
| EC2 t4g.small (vCPU 2, 메모리 2GB) | 약 $15 |
| 탄력적 IP (고정 주소) | 약 $3.6 |
| 디스크 20GB gp3 | 약 $2 |
| **합계** | **약 $21** (신규 크레딧 $200이면 약 6개월) |
| Tripo 크레딧 | 서버 설정의 `--budget`만큼만 씀 (아래 참고) |

정확한 금액은 AWS 요금 계산기로 확인하세요. 결제 및 비용 관리 → **Budgets**에서 월 $25 알림을 걸어 두면 안전합니다.

### C-1. 서버 만들기 (AWS 콘솔, 명령 없음)

1. 콘솔 오른쪽 위 리전을 **아시아 태평양(서울) ap-northeast-2**로 바꿉니다.
2. EC2 → 인스턴스 → **인스턴스 시작**을 누르고 아래처럼 설정합니다.
   - 이름: `villagen` (자유)
   - 이미지: **Ubuntu Server 24.04 LTS**, 아키텍처 **64비트(Arm)**
   - 유형: **t4g.small** (인원이 많으면 t4g.medium)
   - 키 페어: 없이 계속 (브라우저로 접속합니다)
   - 네트워크: **SSH, HTTPS, HTTP 허용** 세 개 모두 체크
   - 스토리지: **20GiB gp3**
3. **고정 주소**를 붙입니다. 서버를 껐다 켜도 주소가 바뀌지 않게 하는 단계입니다.
   EC2 → 탄력적 IP → **할당** → 만든 주소 선택 → 작업 → **연결** → 방금 만든 인스턴스.

### C-2. 설치 (브라우저 터미널)

인스턴스 선택 → **연결** → **EC2 Instance Connect** → 사용자 이름 `ubuntu` → 연결. 검은 창에 한 줄씩 붙여넣습니다(Ctrl+Shift+V).

```bash
sudo apt-get update && sudo apt-get install -y git
git clone -b dev https://github.com/NormalMan0228/tripo_s1.git ~/tripo_s1
cd ~/tripo_s1
sudo bash ops/bootstrap-gcp-free.sh
```

- 코드를 고쳐 쓰려면 원본 대신 **내 Fork 주소**로 clone합니다(D 참고).
- 마지막 줄이 Docker, 서버, HTTPS 주소를 자동으로 준비합니다. 끝에 나오는 `Demo URL: https://<IP를 -로 이은 주소>.sslip.io/health`에서 `/health`를 뺀 부분이 **우리 서버 주소**입니다. 이 단계에서는 아직 제작(유료)이 꺼져 있고, C-3·C-4에서 켭니다.
- `Could not find the public IP`가 나오면 탄력적 IP를 직접 넣습니다: `sudo PUBLIC_IP=3.38.12.34 bash ops/bootstrap-gcp-free.sh`

### C-3. 키 저장

```bash
sudo nano ops/secrets/tripo-key
```
Tripo 키를 붙여넣고 **Ctrl+O → Enter → Ctrl+X**로 저장합니다. 키가 여러 개면 한 줄에 하나씩 넣습니다. 앞 키의 크레딧이 모자라면 다음 키를 씁니다.

```bash
sudo nano ops/secrets/gemini-key
```
Gemini 키도 같은 방법으로 저장합니다.

### C-4. 우리 규칙으로 켜기

```bash
sudo bash ops/update_online_server.sh dev --open-signup --per-account 0 --per-day 3 --craft-day-limit 60 --max-credits 35 --budget 1000 --welcome-stars 70
```

마지막에 health 결과가 `"ok": true`로 나오면 끝입니다. 숫자의 뜻은 다음 표와 같습니다. **예산(`--budget`)은 꼭 자기 형편에 맞게 정하세요.**

<a id="비용과-한도"></a>

| 옵션 | 뜻 | 예시 값 |
|---|---|---|
| `dev` | 받아 올 브랜치 | `dev` |
| `--open-signup` / `--invite-only` | 초대 코드 없이 가입 허용 / 초대 코드 필요 | `--open-signup` |
| `--signups-per-ip N` | 같은 IP에서 하루에 만들 수 있는 계정 수 | 3 (기본) |
| `--per-account N` | 계정 하나가 평생 맡길 수 있는 제작 수 (0 = 제한 없음) | 0 |
| `--per-day N` | 계정 하나가 하루에 맡길 수 있는 제작 수 | 3 |
| `--craft-day-limit N` | 서버 전체가 하루에 맡길 수 있는 제작 수 → **하루 최대 지출을 정함** | 60 |
| `--max-credits N` | 제작 1회에 쓸 수 있는 Tripo 크레딧. 10 = 직접 색칠하는 단순 가구만, 20 = 색 입힌 가구, 30 = 참고 사진 + 색, 35 = 사진 다듬기 + 색 | 35 |
| `--budget N` | 이 서버가 쓸 수 있는 **Tripo 크레딧 총량**. 다 쓰면 제작이 자동으로 멈춤 (0 = 무제한, 비추천) | 1000 |
| `--welcome-stars N` | 새 계정에 주는 게임 화폐(별씨). 직접 색칠 20, 움직이는 가구 30, 색 입힘 40 | 70 |

**최악의 지출 = `--budget`** 입니다. 예산을 넘는 일은 없습니다. 쓴 양은 브라우저에서 `https://<우리 서버 주소>/health`를 열면 `"tripo_budget": {"used": ..., "total": ...}`로 보입니다.

### C-5. 학과 사람들에게 알리기

서버 주소를 알려 주고 A의 방법으로 접속하게 합니다. `world.cfg`를 넣은 ZIP을 나눠 주면 더 편합니다.

### C-6. 업데이트와 백업

```bash
cd ~/tripo_s1
sudo bash ops/update_online_server.sh dev <C-4와 같은 옵션들>
```
업데이트 스크립트는 매번 데이터(`/data`: 계정 DB와 만든 모델)를 먼저 백업하고 확인한 뒤 새 코드로 바꿉니다. 키 파일과 데이터는 건드리지 않습니다.

> 학기가 끝나면 AWS에서 **인스턴스 종료**와 함께 **탄력적 IP 릴리스**까지 해야 요금이 멈춥니다. 연결되지 않은 고정 IP에도 요금이 붙습니다.

---

## D. 개발하기

1. GitHub에서 원본 저장소를 **Fork**합니다. 내 Fork를 clone하고 `dev`에서 작업 브랜치를 만듭니다.
   ```powershell
   git clone https://github.com/<내 아이디>/tripo_s1.git
   cd tripo_s1
   git checkout dev
   git checkout -b feature/내-작업
   ```
2. B-1~B-4를 똑같이 합니다.
3. 테스트를 돌립니다.
   ```powershell
   .tools\server-venv\Scripts\python.exe -m pytest server/tests -q
   powershell -ExecutionPolicy Bypass -File tools/run_game.ps1 -Check
   ```
4. 게임 exe를 만듭니다.
   ```powershell
   powershell -ExecutionPolicy Bypass -File tools/setup.ps1 -Export -Art
   powershell -ExecutionPolicy Bypass -File tools/build_game.ps1
   .tools\art-venv\Scripts\python.exe tools/package_release.py --game-only
   ```
   결과물은 `builds\release` 폴더에 생깁니다(약 1.3GB). GitHub에는 올리지 않습니다.
   - 내려받기 주소 목록이 없어 `-Export`가 멈추면: Godot 편집기 → 편집기 → **내보내기 템플릿 관리** → 다운로드 및 설치. 그다음 `%APPDATA%\Godot\export_templates\4.7.2.stable\`의 `windows_release_x86_64.exe`, `windows_debug_x86_64.exe`를 `.tools\godot-templates\`에 복사합니다.

### 폴더 지도

| 폴더 | 내용 |
|---|---|
| `game/` | Godot 게임 (`project.godot`, `scripts/`, `tests/`) |
| `server/` | Python 서버 (FastAPI, SQLite, Tripo·Gemini 연결) |
| `ops/` | 온라인 서버용 Docker, Caddy, 설치·업데이트 스크립트 |
| `tools/` | 설치, 빌드, 테스트, 아트 생성 스크립트 |
| `labs/` | 지형·캐릭터·소품 실험용 Godot 프로젝트 |
| `docs/` | 문서, 워크스루, 라이선스 |

### Git에 올리지 않는 것

`.gitignore`가 막아 주지만 한 번 더 확인하세요.
- 키: `tripo_key.txt`, `gemini_key.txt`, `ops/secrets/`, `.env`
- 서버 데이터: `server-data/`, `*.sqlite3`
- 큰 생성물: `game/maps/archipelago/assets/`, `game/assets/interior/` 같은 에셋 폴더, `builds/`, `output/`
- `git add` 뒤에 `.tools\server-venv\Scripts\python.exe tools/audit_public_stage.py`를 돌리면 올리려는 파일에 키나 DB, 너무 큰 파일이 섞였는지 검사합니다.

### 새 에셋을 Tripo로 만들 때

`tools/generate_*.py` 스크립트는 기본으로 `바탕화면\tripo_key.txt`를 읽습니다. 다른 위치면 `--key-file 경로`를 붙입니다. 생성 비용은 실행 전에 스크립트 안의 크레딧 표(manifest)에서 확인하세요.

---

## 문제 해결

| 증상 | 해결 |
|---|---|
| `Tripo key file is missing` | `바탕화면\tripo_key.txt`가 있는지, 확장자가 `.txt.txt`가 되지 않았는지 확인합니다(탐색기 → 보기 → 파일 확장명) |
| `Gemini key file is missing` | `바탕화면\gemini_key.txt`를 만듭니다 (aistudio.google.com 무료 키) |
| `Tripo account check: ...` | 키가 틀렸거나 크레딧이 0입니다. Tripo 사이트에서 확인합니다 |
| `Port 8765 is occupied` | `Stop_Tripo_Server.cmd`를 실행하고 다시 켭니다 |
| 게임이 평평한 초원만 보임 | 지도 묶음을 저장소 맨 위에 풀지 않았습니다 (B-2) |
| Godot가 "다른 버전에서 만든 프로젝트"라고 경고함 | Godot 4.7.2가 아닙니다. 4.7.2-stable을 받아 씁니다 (B-1) |
| PowerShell이 스크립트 실행을 막음 | 명령 앞에 `powershell -ExecutionPolicy Bypass -File`을 붙입니다 (위 예시처럼) |
| 로그인할 때 "멀리 있는 월드는 https:// 주소로 들어가요" | 인터넷 주소는 `https://`만 됩니다. `http://`는 이 PC, 공유기 내부, Tailscale 주소에만 허용됩니다 |
| 온라인 서버 제작이 "예산을 모두 썼어요" | `--budget` 크레딧을 다 쓴 것입니다. 늘리려면 C-4 명령을 더 큰 숫자로 다시 실행합니다 |
| `Check_Setup.cmd` 글자가 깨짐 | PowerShell 창의 글꼴 문제일 뿐 결과는 맞습니다. [OK]/[없음]만 보면 됩니다 |

---

## 더 읽을거리

- [15분 워크스루](WALKTHROUGH_KO.md): 게임 안에서 할 수 있는 것
- [전체 안내서](TRIPOTHON_OVERVIEW_20261004.md): 개발 과정, 클라이언트·서버·AI 생성 흐름
- [보안](SECURITY.md): 서버 보안 설정
- [라이선스](licenses/), [글꼴 라이선스](../game/assets/fonts/LICENSES.md)
