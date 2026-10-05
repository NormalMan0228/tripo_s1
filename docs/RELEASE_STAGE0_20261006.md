# Tripothon S1 — 0단계 기존 구현 검증

검증일: 2026-10-06 KST. **조사·실행 검증만 수행했다. 기존 게임/서버 코드와 실제 계정 DB는 수정하지 않았다. 1단계는 주상 확인 후 시작한다.**

## 기준본과 보존 범위

- 실제 프로젝트: `C:/Users/Administrator/Desktop/iwbtg/공모전/2026_10_5_tripoS1/tripo_s1`.
- 조사 시작: `island-village-rpg`, `be3f1357c96b3250f3f3eaadd1b8df8fa355dc1a`, 미커밋 변경 없음.
- 조사 중 사용자가 최신 main ZIP을 전달했다. 현재 실제 폴더도 `main`, `232797d8808c74eb6a6eec38abe3f1bb01ece461`, 미커밋 변경 없음으로 재확인했다. 이 보고서의 새 문서 추가는 마지막에 별도로 남긴다.
- main은 해당 브랜치를 병합한 PR #3 커밋이며 GitHub 비교의 변경 파일은 0개다. 두 ZIP은 파일 1,984개의 목록·크기·CRC가 일치한다. 로컬 원본과 브랜치 ZIP의 1,984개 추적 파일도 줄바꿈을 정규화해 전수 대조했고 차이·누락은 0개였다.
- 당시 후속 기준으로 지정된 main ZIP의 아카이브 커밋은 `232797d`이고 크기는 802,479,767바이트다. 소스 ZIP이며 EXE/PCK는 없다. **이후 2026-10-06 사용자 지시로 ZIP 기준은 대체되었다. 1단계부터는 실제 `C:/Users/Administrator/Desktop/iwbtg/공모전/2026_10_5_tripoS1/tripo_s1` 폴더를 기준으로 작업·검증한다.**
- 실행 검증은 동일 내용을 복사한 `C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/source`에서 수행했다. Godot 임포트·사용자 설정·검증 계정이 실제 프로젝트나 실사용 데이터와 섞이지 않게 했다.
- 실제 DB의 `polytech1~3`, 관리자 시작 재화, 계정 정리 백업 위치는 **사용자가 공유한 친구의 인계 내용**으로 기록한다. 실제 계정 DB 조회·로그인·초기화·재화 지급은 이번에 수행하지 않았다. 비밀번호와 API 키도 읽지 않았다.
- 친구 인계의 백업 위치: `%LOCALAPPDATA%/TripothonDemo/account-reset-20261005-232302`. 현재 실사용 계정이 3개뿐이라는 설명은 이번 조사에서 독립 확인하지 않았다.

## 기존 구현 검증표

상태를 **코드 존재 / 자동 검사 / 렌더 실행 확인 / 주상 확인**으로 구분한다. 아래 모든 항목의 주상 확인은 아직 대기다.

| 항목 | 근거 파일·변경 | 현재 실행 결과 | 부족한 부분 | 주상이 확인할 행동 | 권장 처리 |
|---|---|---|---|---|---|
| 시작 화면·RPG HUD | `game/scripts/main.gd:345`, `rpg_ui.gd`, `minimap.gd`, `transition.gd`; `85d6ecc` | 3개 언어의 시작·설정·로그인·마을 화면 렌더 확인. 서버 인증 후 마을 진입 통과 | 시작 메뉴의 언어 선택은 설정 안에 있음. 제목 하단 `v0.10`과 프로젝트/내보내기의 `0.9.2` 불일치 | 메뉴 디자인·문구·언어 선택 위치와 HUD가 제출 방향에 맞는지 확인 | 기존 화면 유지, 승인된 부족분과 버전 표기만 보완 |
| 한국어·영어·중국어 | `game/scripts/i18n.gd:13`, `game/i18n/strings.json`, `templates.json` | 번역 816개, EN/ZH 빈 값 0개, 동적 템플릿 9개. 3개 언어 기본 화면과 로그인 통과. 영어 선택은 별도 Godot 프로세스 재시작 후에도 유지 | 영어 이야기 수첩의 인물 이름·본문·목표에 한국어가 남음(`main.gd:1979`). 영어 비밀번호 규칙 placeholder의 끝부분이 잘림. 공방 입력 placeholder는 대비가 낮음. 운영 서버의 영어 생성 전체 동선은 미검증 | 설정에서 English 선택 → 로그인 안내 → 이야기 수첩·제작 의뢰 문구와 읽기 쉬운지 확인 | 번역 시스템 유지, 실제 표시 경로와 잘림·대비만 보완. 중국어는 보존 |
| 첫 플레이 튜토리얼 | `main.gd:482`, `village_life.gd:307`; 현재 목표 HUD·조작·보상 안내 존재 | 신규 검증 계정이 튜토리얼 단계 없이 바로 마을로 진입하는 것을 확인 | 단계 진행·첫 목표 완료 판정·진행 저장·건너뛰기·다시 보기로 연결된 온보딩은 찾지 못함 | 신규 일반 계정으로 들어가 집·목표·재화·제작·배치를 이해할 수 있는지 확인 | 기존 HUD·목표·보상을 재사용하는 짧은 튜토리얼 보완. 새로운 퀘스트 확장은 후순위 |
| BGM·효과음 | `game/scripts/sound.gd:12`, `transition.gd:55`, `game/assets/audio/{village,forest}.wav`; `tools/compose_ambience.py`, `docs/ASSETS.md` | 32초 mono WAV 2곡 존재. BGM 재생 상태, 1.2초 전환 후 이전 스트림 종료, 복귀 시 중복 없음, 게임 프로세스 음소거, 효과음 9종 데이터와 클릭 재생 확인 | 실제 청취 품질·음량·찢어짐·전체 효과음 타이밍은 주상 청취 필요. 승훈의 별도 신규 음악 파일은 전달본에서 확인하지 못함. 음소거 재실행 저장은 없음 | 시작 → 마을 → 탐험 → 실내 → M 음소거를 직접 듣고 유지/교체 범위 판단 | 기존 음악·효과음 보존. 교체할 곡과 장면이 정해지면 해당 연결만 작업 |
| NPC·기존 이야기 | `main.gd:2033`, `village_life.gd`, `server/campaign.py:4` | NPC 5명·해루 41본과 4개 클립·인사 후 낚시 복귀 렌더 검사 통과. 서버의 기존 이야기 목표·첫 보상 검사 통과 | 3장 전체의 실제 7일 플레이는 이번 0단계에서 재실행하지 않음. 영어 이야기 표시 누락 있음 | 해루 대화, 다른 NPC 안내, 이야기 수첩의 기존 목표와 보상을 확인 | 기존 대화·3장 이야기 보존. 신규 NPC/장편 퀘스트 추가는 후순위 |
| 다섯 섬 메인 맵·캐릭터 | `game/scripts/town.gd:76`, `maps/archipelago/archipelago.gd:5`, `tools/port_archipelago_map.py`; `1f137a3` | 다섯 섬 연결 코드·상호작용 좌표·지도 이미지는 존재. 기존 주인공과 NPC는 렌더됨. 실제 실행에는 지도 에셋 누락 경고가 나오며 임시 초원이 표시됨 | `game/maps/archipelago/assets` 및 `labs/terrain_lab/assets` 없음. 섬 GLB·건물·텍스처·다리 등 Git 제외 에셋 인계 필요. 시작 배경·미니맵의 섬 그림은 실제 플레이 맵 검증을 대신하지 못함 | 이 임시 초원이 제출 맵인지 판단. 의도한 섬 맵이라면 원본 에셋 폴더/묶음 제공 | **맵 재제작 없이 기존 에셋 인계·복원 우선. 섬 길·충돌·출입은 자산 복원 후 확인** |
| 제작·배치·상호작용 | `main.gd:2117`, `studio.gd`, `server/asset_studio.py`, `asset_assembly.py`, `homestead.py` | 별도 fixture DB에서 생성·소유 모델·가구 열림·부분 색칠·배치·회전·취소·회수·실내 재입장 저장 복원 통과. 중복·소유권·차감·환불 서버 검사 통과 | 이번에는 실제 유료 Tripo 생성 0회. 마을의 간단 제작 버튼은 현재 무과금 검증 서버에서 비활성으로 표시. 실제 생성→마을 어디든 배치의 운영 동선과 시각 품질은 미검증 | 실제 제출 서버의 제작 가능 여부·견적·완성품·배치를 확인. 샘플/사전 생성물과 실생성을 구분 | 기존 구현 보존. 승인된 계정·횟수·크레딧으로 실생성 검증 필요. 새 물건 상호작용은 후순위 |
| 멀티·서로의 집 방문·Tailscale | `social.gd:21`, `studio.gd`, `tools/serve_multi.py`, `Host_Friends.cmd`; `49c0208`~`86c8227` | 같은 PC의 Godot 클라이언트/계정 2개로 방문 초대·호스트 집 가구 표시·편집 도구 숨김·상호 표시·방문 종료 통과 | 서로 다른 PC·Tailscale 실제 연결·외부 재접속은 미검증. 현재 프로젝트에는 실행기에서 요구하는 `.tools`와 개발 EXE도 없음 | Tailscale 연결 후 실제 친구 1명과 마을 초대 → 집 앞 E → 방문 종료/재접속 확인 | 기존 기능 유지. 네트워크 설치·로그인·방화벽 변경은 이번에 수행하지 않음 |
| 관리자·새 비밀번호 규칙 | `build_mode.gd:7`, `main.gd:2249`, `server/models.py:17`, `app.py:244`, `tools/admin_accounts.py`; `be3f135` | 새 가입 약한 비밀번호 거부·강한 비밀번호 허용·일반 계정 관리자 지급 거부·관리자 지급 원장 기록이 서버 검사에서 통과. 일반 계정의 개발 옵션 비활성 확인 | 실제 `polytech1~3` 로그인·F3/F9 화면·텔레포트와 실제 시작 재화는 친구 인계 내용이며 이번 검사에서는 미확인 | 실제 PC 서버에서 polytech 계정 로그인 → F3/F9 → 관리 창 확인. 일반 플레이어 영상에는 관리자 자원 지급/순간 이동을 일반 기능처럼 넣지 않기 | 기존 관리자 기능 보존, 실사용 계정·백업·비밀번호를 변경하지 않음 |
| 온라인 운영 서버 | `main.gd:17`, `api.gd:3`, `server/config.py`; `286e594` | `https://34-28-65-113.sslip.io/health` HTTPS 응답 성공: live, protocol 6, multiplayer 1, 정원 3 | 현재 health는 `studio_tripo_enabled=false`, `studio_llm=fixture`. 원격 가입·실제 제출 클라이언트·저장 복원·실생성·서버 재시작 지속성 미검증. health만으로 배포 커밋/전체 정상 판정 불가 | 심사용 계정 또는 초대 방식으로 외부 로그인·플레이·저장 확인. 생성 비활성 정책의 제출 체험 판단 | 서버·DB 전면 교체 없이 실제 정책과 접근 경로 확인. API 주소는 브라우저 플레이 링크로 쓰지 않기 |
| Windows ZIP·제출 자료 | `game/export_presets.cfg`, `tools/build_game.ps1`, `package_baseline.py`; 전달 ZIP 전수 목록 | 새 main ZIP은 최신 소스와 일치하지만 EXE/PCK가 없음. 프로젝트에 `builds`·`.tools` 없음 | 현재 배포 ZIP의 최신 일치 여부를 검사할 실행본이 없음. GIF·1~2분 워크스루·커버·에셋 보드·공개 링크 미준비. 필수 섬 자산도 누락 | 실제 제출할 실행본과 맵을 확정. 앞선 검증용/모션 영상은 최종 워크스루로 대체하지 않기 | 0단계 확인 후 단계 5~7에서 제작. 이 소스 ZIP을 최종 실행 ZIP으로 소개하지 않음 |

## 이번 실행 결과와 근거

- Godot `4.7.2.stable.official.ed1daf0bf`, Compatibility/OpenGL, Windows/NVIDIA RTX 3060. Python 3.12.14의 기존 검증용 가상환경을 재사용했다. 저장소 권장 Python 3.13 재현은 미실행이다.
- 서버 pytest: **144 passed, 실패 0, 경고 1**, 67.09초. Starlette/httpx deprecation 경고이며 게임 실패가 아니다.
- Godot 임포트와 전체 클라이언트 스크립트 컴파일: 정상 종료, `COMPILE_DONE failed=0`.
- `ui_tour`: PASS 8회, 36.78초. 3개 언어 시작·설정·로그인·마을·제작·지도 18장 확보.
- `content_patch`: PASS 40회, 22.09초. NPC·기존 캐릭터·실내·fixture 가구 동작·부분 색칠·배치·저장 복원.
- `home_visit`: PASS 9회, 7.20초. 같은 PC의 두 계정/두 Godot 클라이언트 객체이며 외부 PC 검증으로 해석하지 않는다.
- `integration`: PASS 24회, 34.97초. 가입·재화·소유 모델·기본 배치·샘플 생성·저장 복원.
- 별도 조사 프로브: PASS 18회, 12.33초. 일반 계정·튜토리얼 미연결·영어 이야기 누락·음향 런타임 상태 확인.
- 언어 설정 재시작 검사: 새 Godot 프로세스에서 영어 선택 유지 PASS 1회.
- 클라이언트 PASS 총 100회(캡처 확인 포함), 런타임 오류 0. **영어 누락·튜토리얼 부재·지도 누락은 별도 품질/인계 문제이며 테스트 통과로 완료 처리하지 않는다.**
- PNG 34장. 실제 유료 생성 0회. 운영 DB 실패 주입·계정 정리·Tailscale 설치·친구 메시지 전송·제출/업로드는 수행하지 않았다.
- 로그·JSON·캡처: `C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006`.
- 검증이 끝난 서버 프로세스는 종료했다. 임시 `qa-data`·`pytest-temp` 폴더 삭제는 자동 승인 검토에서 정책상 차단되어 해당 검증 폴더에 보관 중이다. 실사용 계정 DB와 분리돼 있으며 삭제 완료로 보고하지 않는다.

## 주상이 직접 확인하는 방법

검토용 게임은 **실제 PC 서버와 다른 `127.0.0.1:8767`**에서 현재 켜져 있다. 이는 무료 fixture 검토 환경이며 실시간 Tripo 제작이 비활성화돼 있다. `polytech1~3`은 이 검토 DB에 복사하지 않았다.

다시 열기: `C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/Review_Stage0.cmd`를 실행한다. 이 실행기는 검증용 복사본·기존 Godot/Python 도구·독립 DB/언어 설정만 사용한다. 최종 배포용 실행기가 아니다.

1. 설정 → 한국어/English/中文 선택. 시작 화면과 설정·소리 메뉴가 원하는 구성인지 확인한다.
2. 게임 시작 → 서버가 `직접 입력`, `http://127.0.0.1:8767`인지 확인 → 임시 검토 계정 만들기. 아이디 3~24자의 영문·숫자·밑줄, 비밀번호는 10자 이상·대문자·특수문자 포함. 실제 polytech 비밀번호를 사용하지 않는다.
3. 마을 → WASD/Shift 이동, Tab 지도, I 가방, C 제작. 현재 보이는 초원과 미니맵/시작 그림의 차이를 확인한다.
4. 지도에서 집·공방 목적지를 고르고 가까운 위치의 E 안내로 실내 진입한다. 기존 물건을 놓고 색칠·회수해 본다. 무과금 검토 서버에서 새로운 Tripo 제작 버튼이 잠긴 것은 현재 정책이다.
5. English로 이야기 수첩을 열어 본문·목표에 남은 한국어를 확인한다. 영어 로그인 비밀번호 안내의 잘림도 확인한다.
6. 마을·탐험·실내에서 음악·효과음을 듣고 M으로 음소거를 확인한다. 탐험은 생존 시간이 흐르므로 내용을 보존하려면 기존 메뉴의 저장 귀환을 사용한다.
7. 실제 친구 방문과 polytech 관리자 화면은 실제 PC 서버의 별도 확인 항목이다. 검토 서버에서 관리자 기능을 일반 계정에 부여하지 않았다.

## 캡처로 바로 확인

[한국어 시작](C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/source/artifacts/ui-ko-title.png) · [영어 설정](C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/source/artifacts/ui-en-settings.png) · [영어 로그인](C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/source/artifacts/ui-en-login.png) · [중국어 시작](C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/source/artifacts/ui-zh-title.png)

[실제 임시 초원 HUD](C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/source/artifacts/ui-en-village.png) · [영어 이야기 누락](C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/source/artifacts/stage0-en-story.png) · [제작 제한 안내](C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/source/artifacts/ui-en-craft.png) · [집 방문](C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/source/artifacts/home-visit-guest.png) · [가구 상호작용](C:/Users/Administrator/Documents/ChatGPT/공모전/qa/tripo_stage0_20261006/source/artifacts/content-home-furniture.png)

## 주상 확인과 다음 단계

### 이후 단계의 보고·검사 기준 — 사용자 추가 지시

- 단계가 끝날 때마다 완료 작업, 핵심 검사 결과, 주상이 확인할 행동, **다음 단계 목록**을 함께 표시한다.
- 검사량은 이번 0단계의 약 **1/3**로 줄인다. 이번의 서버 144개·클라이언트 PASS 100회를 기준으로 하면 서버 약 48개·클라이언트 약 33회 규모이며, 매 단계마다 이 수를 채우는 할당량은 아니다.
- 변경한 부분과 로그인·저장·재화/생성 중복 방지 등 실제 위험이 있는 핵심 흐름만 선정한다. 이미 통과했고 변경하지 않은 영역의 전체 검사를 반복하지 않는다.
- 문제가 발견되면 해당 원인과 수정 범위에 필요한 검사만 추가한다. 전체 서버/클라이언트 검사로 자동 확대하지 않는다.
- 위 기준은 앞으로의 단계에 적용한다. 이미 수행한 0단계 검사 기록은 사실대로 보존한다.

- **제출 준비 완료:** 아직 아니다. 0단계 조사·검증 자료와 확인용 환경만 준비됐다.
- **주상 확인 필요:** 시작 화면/HUD 유지 범위, 영어 부족분 보완 범위, 기존 음악 유지·교체, NPC·이야기 유지, 실제 제출 맵과 자산 인계, 운영 생성 제한과 심사 체험 방침.
- **제출을 막는 문제:** 다섯 섬 필수 자산 미전달, 실행 가능한 최신 제출 ZIP·영상·커버·에셋 보드 없음, 운영 서버의 실제 제출 동선 미검증. 짧은 온보딩과 영어 누락 보완도 요구사항에 남는다.
- 위 표는 0단계 종료 당시의 상태다. 이후 사용자가 실제 프로젝트 폴더를 기준으로 1단계 진행을 승인했다. 후속 변경·검증 결과는 `RELEASE_STAGE1_20261006.md`에 기록한다.

이번에 새로 만든 프로젝트 파일은 이 검증 문서뿐이다. 조사 프로브·실행기·로그·임포트 캐시·검토 DB는 프로젝트 밖의 QA 경로에 있다.
