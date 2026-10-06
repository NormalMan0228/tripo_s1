# 심사용 온라인 서버 켜기 (Google Cloud VM · 제작: 서버 → Gemini → Tripo)

> 처음 하는 분은 붙여넣기만 하면 되는 [쉬운 안내(텍스트)](SERVER_UPDATE_GUIDE_KO.txt)를 따르세요.

심사위원은 [GitHub Release](https://github.com/NormalMan0228/tripo_s1/releases)에서 `Villagen_<버전>_Windows.zip`만 받아 압축을 풀고 `Villagen.exe`를 실행합니다. 게임은 처음부터 **온라인 월드**(`https://34-28-65-113.sslip.io`)에 접속하고, 초대 코드 없이 가입합니다. 아래는 운영자(계정 주인)가 서버를 최신으로 올리고 제작을 켜는 절차입니다. API 키는 **서버에만** 두고 게임 ZIP·Git·채팅에는 넣지 않습니다.

## 0. 준비할 키 두 개

1. **Gemini API 키** (설계 단계, 무료 등급으로 충분): <https://aistudio.google.com/apikey> → Google 계정 로그인 → **Create API key** → 복사.
   - 무료 등급은 분당·하루 요청 수 제한이 있지만 계정당 3회 제작에는 넉넉합니다. 무료 등급 입력은 Google 서비스 개선에 쓰일 수 있습니다. 결제를 켜면 유료 등급(제작 1회 약 1~2센트)으로 바뀝니다.
2. **Tripo API 키** (3D 생성): 이 PC 바탕화면의 `tripo_key.txt` 내용. 계정이 여러 개면 키를 **한 줄에 하나씩** 모두 넣습니다. 서버는 맨 위 키부터 쓰고, 크레딧이 모자라면 다음 키로 넘어갑니다. 진행 중인 제작은 처음 쓴 키로 끝까지 마무리됩니다.

## 1. VM에 접속

Google Cloud 콘솔 → **Compute Engine → VM 인스턴스** → 데모 VM 줄의 **SSH** 버튼(브라우저 창이 열림).

## 2. 코드 받기

저장소 폴더로 이동합니다(처음 설치할 때 `bootstrap-gcp-free.sh`를 실행한 폴더, 보통 `~/tripo_s1`). 위치를 모르면 `sudo find / -name update_online_server.sh -path '*ops*' 2>/dev/null`로 찾습니다.

```bash
cd ~/tripo_s1
sudo git fetch origin
sudo git checkout main
sudo git pull --ff-only origin main
```


## 3. 키 파일 저장 (각각 한 줄)

```bash
sudo nano ops/secrets/tripo-key
```
키를 붙여넣고(브라우저 SSH는 Ctrl+Shift+V 또는 우클릭) **Ctrl+O → Enter → Ctrl+X**로 저장합니다. 이미 파일이 있으면 건너뜁니다.

```bash
sudo nano ops/secrets/gemini-key
```
Gemini 키를 같은 방법으로 저장합니다.

## 4. 업데이트 + 제작 켜기 + 체험판 규칙

```bash
sudo bash ops/update_online_server.sh main --open-signup --per-account 3 --per-day 1000 --craft-day-limit 30 --max-credits 10 --welcome-stars 150
```

- `--open-signup`: 초대 코드 없이 가입(같은 주소에서 하루 3계정, 하루 전체 200계정까지). 게임에는 초대 코드 칸이 없습니다.
- `--per-account 3`: 계정마다 제작은 **평생 3회**(실패한 제작은 세지 않음).
- `--craft-day-limit 30`: 서버 전체 하루 제작 30회까지.
- `--max-credits 10`: 제작 1회에 Tripo 최대 10크레딧. 직접 색칠·정적인 가구·H3 한 덩어리만 허용되고, 방 공방의 비싼 선택지(질감·움직임·P2·참고 그림)는 잠깁니다.
- `--welcome-stars 150`: 새 계정이 별씨 150개로 시작해 바로 제작해 볼 수 있음.
- 스크립트가 DB를 백업·검증하고, 코드를 받아 API만 다시 빌드한 뒤 `/health`를 출력합니다.

출력 끝의 `/health`에 다음이 보이면 성공입니다.

```
"version":"0.10.0", "studio_tripo_enabled":true, "studio_llm":"gemini", "open_registration":true
```

## 5. 플레이어에게 전달

[Release 링크](https://github.com/NormalMan0228/tripo_s1/releases/tag/v0.10.0) 하나만 보냅니다. 아이디·비밀번호만으로 가입합니다.

## 비용과 한도

- 제작 1회 = Gemini 설계(무료 등급이면 0원) + Tripo 10크레딧.
- 계정당 3회 → 1명당 최대 30크레딧. 서버 전체 하루 최대 30회 → 하루 최대 300크레딧.
- Google Cloud VM은 무료 체험 크레딧 범위에서 동작합니다(결제 계정을 업그레이드하지 않음).

## 문제 해결

- `/health`가 안 뜰 때: `sudo docker compose --env-file ops/production.env -f ops/compose.yaml -f ops/compose.gcp-free.yaml -f ops/compose.tripo.yaml -f ops/compose.gemini.yaml logs api --tail 80`
- 제작이 `llm_rate_limited`로 실패: Gemini 무료 등급의 분당 한도입니다. 잠시 뒤 다시 시도합니다.
- 제작이 `llm_model_unavailable`로 실패: 키로 쓸 수 있는 Gemini 모델 이름을 `ops/production.env`에 `TRIPOTHON_GEMINI_MODELS=모델1,모델2`로 적고 4번을 다시 실행합니다.
- 키를 바꿀 때는 3번 파일만 고친 뒤 4번을 다시 실행합니다.
