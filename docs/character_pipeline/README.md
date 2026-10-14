# 캐릭터 제작 파이프라인 문서

2026-10-11 대화에서 만든 설명·매뉴얼·그림을 한곳에 모았습니다. 문서 이름을 누르면 GitHub에서 바로 읽을 수 있습니다(각 폴더의 README.md는 원본 index.html을 `tools/html_doc_to_md.py`로 옮긴 사본). "웹 링크"는 작성자 계정의 claude.ai 페이지라 공유받은 사람만 열립니다. 01 캐릭터 제작 가이드는 눌러 보는 화면이라 HTML을 내려받아 브라우저로 엽니다.

| 번호 | 문서 | 내용 | 웹 링크 |
|---|---|---|---|
| 00 | [테스트 현황](00_테스트_현황.md) | 실패·중단한 테스트와 해야 할 테스트 목록 | - |
| 01 | [캐릭터 제작 가이드](01_캐릭터_제작_가이드.html) | 인간형 캐릭터·인간형 몬스터·비인간형 몬스터별 단계를 눌러 보는 매뉴얼 | https://claude.ai/artifact/8Xcm9YUNWTiABLAamRBQgQ |
| 02 | [얼굴 리그 자동화 보고서](02_얼굴_리그_보고서/) | 공통 실패 원인, 원본 유지 원칙, Faceit·MPFB 분석, 스타일별 통합, 이미지·영상 활용, 실행 결과, 다음 단계 | https://claude.ai/artifact/A5nohTwdZpZGBbWGprKU1g |
| 03 | [그림 모음](03_그림/) | 대화 중에 보낸 설명 그림 | - |
| 05 | [T1 눈꺼풀 부품](05_T1_눈꺼풀_부품/) | 원본 그대로 두고 눈꺼풀 부품 + 뼈 9개로 깜빡임, 머리 3개 | https://claude.ai/artifact/AyMkBzmHmR2Vpj9iQpeVu8 |
| 06 | [T2 입 안](06_T2_입_안/) | 입 안 주머니·이·혀, 입모양, 머리 2개 | https://claude.ai/artifact/PK85fjZfGZ6wQWEATBhDPS |
| 07 | [T3 Godot 실행](07_T3_Godot_실행/) | 원본 유지 리깅을 Godot 4.7에서 실행 (눈꺼풀 뼈·입 표정) | https://claude.ai/artifact/EiWwUGtiBMvy4qPNmQ9BrX |
| 08 | [T4·T5 입력 검사](08_T4T5_입력_검사/) | 리깅 전 8개 항목 자동 판정, 머리 3개 | https://claude.ai/artifact/FNhARZ8Fs5JBtae6KeXym1 |
| 09 | [T6 면 수 줄이기](09_T6_면수_줄이기/) | 25/10/5/2.5% 단계, 모양 차이·대칭·경계·접힘 검사, Godot 확인. 10% 권장 | https://claude.ai/artifact/DNED9Qqci3FsMZi9ZgkRv6 |
| 10 | [T7 표정 스캔](10_T7_표정_스캔/) | Tripo 눈 감은·"아" 머리 → 정렬 → 원본에 표정 키. 입 성공, 눈은 측정용 | https://claude.ai/artifact/SXyThsU3whSC1FVbscveoY |
| 11 | [T13 Rigify 얼굴 자동 리그](11_T13_Rigify_얼굴/) | 기준점 → Rigify 맞춤 → 가중치 → ARKit 42개 굽기 → 10% → Godot, 사람 손 없음 | https://claude.ai/artifact/MTmQNHZK2mpErS3BfxYRva |
| 12 | [T14 리깅 포인트 자동 배치](12_T14_리깅포인트/) | 시험 얼굴 16개 + character1: 조밀 MediaPipe 점(190~370) → 템플릿 관절 92개 옮기기, 눈꺼풀·귀 자동, 위치 오차 2.5 → 0.76mm | https://claude.ai/artifact/E1pYdrzFtc9CqaK4AVzNxe |
| 13 | [T14b 4가지 스타일 전체 흐름](13_T14b_4가지_스타일/) | 실사·반실사·카툰·애니 4개로 자르기→부품→Rigify→ARKit 42개→원본 색, 곡선 자르기·턱 축·정면 1장 색 입히기 수정, 남음: 입 안 | https://claude.ai/artifact/4w2ngRmS7qAY71toPPCpib |
| 14 | [M1 모듈 얼굴 기관](14_M1_모듈_얼굴/) | 최신 전체 흐름(A 원본 자르기 / B 모듈 부품) + 눈·입 지운 머리에 리깅용 눈·입 부품 끼우기, 4가지 스타일, 진행 중 | https://claude.ai/artifact/DWWpNxe949v1GVbwjKaswL |
| 15 | [깨끗한 원본 비교](15_깨끗한_원본_비교/) | 원본을 쿼드로: Blender 리메시, Tripo 리토폴로지(일반·P2), HD·P2 새 생성 6가지를 4개 스타일에서 비교, 추천 P2 새 생성 | https://claude.ai/artifact/Dirx1MBijDwM8xcpcri3uF |
| 16 | [세 방식 최종 비교](16_세_방식_최종_비교/) | 지금 방식 / 리토폴로지+P2 / P2 새 원본을 리그·표정·텍스처까지 같은 체인으로 비교, 판정 P2 새 원본 + 고리 따라 자르기 | https://claude.ai/artifact/4tW7kvRe16y3N2a5vPqosD |
| 17 | [방식 1 다듬기](17_방식1_다듬기/) | P2 눈을 참조 그림에 맞춤, 두 눈 구석 기준 감기·눈물언덕·시선 따라오는 눈꺼풀, 입 리깅 포인트 +12·혀 4본, 포물선 치열+잇몸+혀, 리깅 포인트·본 162/844, ARKit 52+보정 34 (텍스처 보류) | https://claude.ai/artifact/28ifARaPzc6hMJt4LhVaSR |
| 04 | [대안 도구 조사](04_대안_도구_조사.md) | Gemini가 말한 도구들 검증 결과, Rigify 무인 생성 확인 | - |

## 03_그림
- `01_전체_워크플로우.png`: 레퍼런스부터 애니메이션까지 전체 단계(초기안, CC5 기준)
- `02_얼굴과_몸_세_갈래.png`: 인간형 캐릭터·인간형 몬스터·비인간형 몬스터 세 갈래
- `03_파츠_잘라_붙이기.png`: 파츠를 잘라 붙여 리메시하고 이음새를 다듬는 과정
- `04_합친_메쉬의_두_경로.png`: 합친 메쉬를 표정 리그 쪽과 몸 위주 쪽으로 나누는 두 경로
- `05_메쉬에_없는_정보.png`: 원본만으로 눈이 안 감기는 이유와 해결 방법 A·B
- `06_CC5_대_애니템플릿_비교.png`: CC5 Headshot과 애니메이션 템플릿 랩핑 비교 (지금은 원본 유지 원칙으로 랩핑을 쓰지 않음)
- `07_CC5_눈_수정전후.png`: CC5 Headshot 눈꺼풀 점 수정 전후와 깜빡임

## 지금 원칙 (2026-10-11 사용자 결정)
- 원본 메쉬의 모양은 바꾸지 않는다. 자르기, 부품 추가, 리깅, 표정만 한다.
- 면 수 줄이기는 허용한다. 대칭이 필요한 캐릭터는 대칭 검증을 통과해야 한다.
- 자동화를 먼저 시도하고 수동 절차는 최소로 줄인다.

## 관련 위치
- 스크립트: `tools/face_auto/` (원본 유지 리깅 `rig_original.py`, MediaPipe 기준점, MPFB 템플릿)
- 정책: `docs/CHARACTER_GENERATION_POLICY.json` (다른 도구가 읽을 수 있어 제자리에 둠)
- 이전 캐릭터 문서 (2026-10-03~04, 제자리 유지):
  - [AI_CHARACTER_DETAIL_REFERENCES_20261003.md](../AI_CHARACTER_DETAIL_REFERENCES_20261003.md)
  - [CHARACTER_ANIMATION_WORKFLOW_20261003.md](../CHARACTER_ANIMATION_WORKFLOW_20261003.md)
  - [CHARACTER_MODULAR_PRODUCTION_STANDARD_20261003.md](../CHARACTER_MODULAR_PRODUCTION_STANDARD_20261003.md)
  - [CHARACTER_PART_REFERENCES_20261003.md](../CHARACTER_PART_REFERENCES_20261003.md)
- 결과 이미지:
  - `art/characters/character1_face_v3/anime_wrap/`
  - Seed-san 템플릿과 라이선스: `art/templates/seedsan/`
