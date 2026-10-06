# 심사용 온라인 서버 켜기 (Google Cloud VM · 제작: 서버 → Gemini → Tripo)

심사위원은 [GitHub Release](https://github.com/NormalMan0228/tripo_s1/releases)에서 `Tripothon_<버전>_Windows.zip`만 받아 압축을 풀고 `Tripothon.exe`를 실행합니다. 게임은 처음부터 **온라인 월드**(`https://34-28-65-113.sslip.io`)에 접속합니다. 아래는 운영자(계정 주인)가 서버를 최신으로 올리고 제작을 켜는 절차입니다. API 키와 초대 코드는 **서버에만** 두고 게임 ZIP·Git·채팅에는 넣지 않습니다.

## 0. 준비할 키 두 개

1. **Gemini API 키** (설계 단계, 무료 등급으로 충분): <https://aistudio.google.com/apikey> → Google 계정 로그인 → **Create API key** → 복사.
   - 무료 등급은 분당·하루 요청 수 제한이 있지만 계정당 3회 제작에는 넉넉합니다. 무료 등급 입력은 Google 서비스 개선에 쓰일 수 있습니다. 결제를 켜면 유료 등급(제작 1회 약 1~2센트)으로 바뀝니다.
2. **Tripo API 키** (3D 생성): 이 PC 바탕화면의 `tripo_key.txt` 내용(키 한 줄).

## 1. VM에 접속

Google Cloud 콘솔 → **Compute Engine → VM 인스턴스** → 데모 VM 줄의 **SSH** 버튼(브라우저 창이 열림).

## 2. 코드 받기

저장소 폴더로 이동합니다(처음 설치할 때 `bootstrap-gcp-free.sh`를 실행한 폴더, 보통 `~/tripo_s1`). 위치를 모르면 `sudo find / -name update_online_server.sh -path '*ops*' 2>/dev/null`로 찾습니다.

```bash
cd ~/tripo_s1
sudo git fetch origin
sudo git checkout island-village-rpg
sudo git pull --ff-only origin island-village-rpg
```

PR이 `main`에 병합된 뒤에는 `island-village-rpg` 대신 `main`을 써도 됩니다.

## 3. 키 파일 저장 (각각 한 줄)

```bash
sudo nano ops/secrets/tripo-key
```
키를 붙여넣고(브라우저 SSH는 Ctrl+Shift+V 또는 우클릭) **Ctrl+O → Enter → Ctrl+X**로 저장합니다. 이미 파일이 있으면 건너뜁니다.

```bash
sudo nano ops/secrets/gemini-key
```
Gemini 키를 같은 방법으로 저장합니다.

## 4. 업데이트 + 제작 켜기 + 한도

```bash
sudo bash ops/update_online_server.sh island-village-rpg --per-account 3 --per-day 1000 --welcome-stars 150
```

- `--per-account 3`: 계정마다 제작은 **평생 3회**(실패한 제작은 세지 않음).
- `--per-day 1000`: 하루 전체 한도는 사실상 없음.
- `--welcome-stars 150`: 새 계정이 별씨 150개로 시작해 바로 제작해 볼 수 있음(제작 1회 별씨 20~50).
- 스크립트가 DB를 백업·검증하고, 코드를 받아 API만 다시 빌드한 뒤 `/health`를 출력합니다. 작은 VM이라 빌드에 몇 분 걸릴 수 있습니다.

출력 끝의 `/health`에 다음이 보이면 성공입니다.

```
"studio_tripo_enabled":true, "studio_llm":"gemini", "version":"0.10.0"
```

## 5. 초대 코드 전달

```bash
sudo cat ops/secrets/registration-code
```

이 코드와 Release 링크를 심사위원에게 따로 전달합니다. 계정 만들기 화면의 **초대 코드** 칸에 넣습니다.

## 비용과 한도

- 제작 1회 = Gemini 설계(무료 등급이면 0원) + Tripo 생성. Tripo는 설계 부품 수에 따라 대략 10~80 크레딧이며, 게임이 확정 전에 견적을 보여 줍니다.
- 계정당 3회이므로 심사위원 1명당 최대 약 240 크레딧입니다. 공급자 콘솔에서 실제 사용량을 확인하세요.
- Google Cloud VM은 무료 체험 크레딧 범위에서 동작합니다(결제 계정을 업그레이드하지 않음).

## 문제 해결

- `/health`가 안 뜰 때: `sudo docker compose --env-file ops/production.env -f ops/compose.yaml -f ops/compose.gcp-free.yaml -f ops/compose.tripo.yaml -f ops/compose.gemini.yaml logs api --tail 80`
- 제작이 `llm_rate_limited`로 실패: Gemini 무료 등급의 분당 한도입니다. 잠시 뒤 다시 시도합니다.
- 제작이 `llm_model_unavailable`로 실패: 키로 쓸 수 있는 Gemini 모델 이름을 `ops/production.env`에 `TRIPOTHON_GEMINI_MODELS=모델1,모델2`로 적고 4번을 다시 실행합니다.
- 키를 바꿀 때는 3번 파일만 고친 뒤 4번을 다시 실행합니다.
