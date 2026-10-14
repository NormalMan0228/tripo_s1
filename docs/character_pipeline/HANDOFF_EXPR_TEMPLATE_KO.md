# 인계: 외형별 표정 템플릿 작업 (2026-10-14)

이 문서는 표정 템플릿 작업을 새 세션에서 이어 가기 위한 인계 문서다. 이 문서와 메모리(MEMORY.md)를 먼저 읽고 시작한다. 답은 항상 한국어로 한다.

## 1. 목표
- 외형별 표정 템플릿(실사·반실사·카툰·애니)을 만든다. **카툰·애니가 먼저다.**
- 캐릭터마다 AI로 생성한 표정 레퍼런스(이미지·영상)를 보고, Blender에서 52개 표정 키(ARKit)를 자동으로 맞춘다.
- 사람이 촬영하거나 연기하는 방법은 쓰지 않는다.
- 원본 메쉬 모양은 바꾸지 않는다. 자르고 붙이기, 리그, 셰이프 키만 쓴다.

## 2. 지금까지 결정된 것
- **굽는 방식:** 지금 방식(리그 본 → 웨이트 → 셰이프 키)을 유지한다. 삼각형 변화 복사(DT)는 시험했지만 채택하지 않았다(사용자가 지금 방식이 낫다고 판단).
- **MakeHuman:** 실사용 초기값으로 한 번만 쓴다. 그 뒤에는 외형별 포즈 파일을 우리가 직접 쓰고 고친다.
- **레퍼런스 세트 (캐릭터 1명):** 클립 18개, 4초씩, 정면, 첫 프레임과 끝 프레임은 같은 무표정.
  - 감정 7개(미소·활짝 웃음·놀람·화남·슬픔·역겨움·두려움)
  - 눈·눈썹 4개(깜빡임·윙크·시선 8초·눈썹 한쪽)
  - 입·턱 7개(아에이오우 6초·입술 내밀기와 말기·입 왼쪽·볼 부풀리기·턱 왼쪽과 앞·입 최대로 벌리기·혀)
  - 좌우 쌍은 한쪽만 만들고 반전한다.
  - 깊이가 중요한 키 6개는 옆모습을 추가하고, **옆모습이 있을 때와 없을 때를 비교하는 시험**도 한다.
- **영상 모델:** 중간 등급이면 충분하다(720p, 오디오 끔, Lite·Fast·Turbo).
  - 얼굴 후보: MiniMax H3, Seedance 2.0 Fast, Gemini Omni(사용자 구독).
  - 말하기 입 모양: TTS → Audio2Face-3D.
  - 몸: Uthana, QuickMagic. 괴물: Tripo 리그 v2.5.
  - 가격과 평가는 docs/research_hub/INDEX.md 에 있다.
- **정보 수집:** 별도 세션이 담당한다. 조사가 필요하면 INDEX.md를 먼저 보고, 없으면 사용자에게 정보 수집 세션으로 넘겨 달라고 한다.

## 3. 만든 도구 (저장소)
- `tools/face_auto/rigify_bake.py`
  - `--style <styles/x.json>`: 외형 포즈 파일을 읽는다. 값은 머리마다 다른 "반 입 너비" 단위로 쓰고, 기준 'jaw'와 'mpfb'를 지원한다.
  - 환경변수 `BAKE_STYLE_SUFFIX=_s`: 기존 키 옆에 접미사를 붙여 새 키를 굽는다(비교용).
  - 환경변수 `BAKE_ONLY=key,..`: 지정한 키만 굽는다.
- `tools/face_auto/styles/build_styles.py`: 외형별 파라미터(semi·cartoon·anime의 오=mouthFunnel, 우=mouthPucker)로 `styles/<외형>.json`을 만든다. 기준 머리의 컨트롤 위치는 `styles/ctrl_<외형>_<머리>.json`에 있다.
- `tools/face_auto/expr_stills.py`: 뷰 `cut`(얼굴 한가운데 세로 단면)을 추가했고, 잇몸을 분홍색으로 표시한다.

## 4. 작업 폴더 (이전 세션 scratchpad, 디스크에 그대로 있음)
- S = `C:/Users/dd/AppData/Local/Temp/claude/C--lsm26-triphthonS1/6b19c4bc-69c2-44b3-bb2c-0698c04d3525/scratchpad`
- P = `C:/Users/dd/AppData/Local/Temp/claude/C--lsm26-triphthonS1/3dd79e48-f532-4100-b2d5-3a2f54980063/scratchpad` (MPFB 템플릿 `P/mpfb/tpl`, s4 정합 결과)
- 머리 4개: f02_european_woman(실사), f06_game_heroine(반실사), f11_pixar_boy(카툰), f09_anime_girl(애니)
  - 기준 메쉬: `S/m1/clean/P2/<머리>` (base.blend, landmarks.json, eyes_meta.json)
  - 결과: `S/m1/v4/P2/<머리>` (rfit/rigify_sym.blend = 굽기 입력, bake/arkit_bp.blend = 최종, eyes_mouth.json 'rings')
  - 전체 체인: `S/m1/chain_v4.sh <머리>`
- 템플릿 시험: `bash S/m1/style/try_style.sh <머리> <styles/x.json> mouthFunnel,mouthPucker`
  - 지정한 키를 `_s` 접미사로 굽고, arkit_bp에 합쳐서 mouth·34·cut 정지 이미지를 만든다.
  - 비교표 스크립트: `S/m1/style/sheet4.py`
- 최근 결과 그림:
  - `S/m1/style/s4_34.jpg`: 반실사 템플릿을 4개 머리에 적용
  - `S/m1/style/cart_anim_v1.jpg`: 카툰·애니 v1
- Blender: `C:/lsm26/triphthonS1/.tools/blender-portable/blender-4.5.3-windows-x64/blender.exe`
- 파이썬: `.tools/art-venv/Scripts/python.exe` (scipy·PIL 있음)

## 5. 작업 순서 (사용자에게 보고한 그림: S/m1/diag/order/work_order.png)
1. **레퍼런스 준비:** 18클립의 외형별 지시문을 쓰고, 무표정 정면·옆모습 그림을 준비한다(무료 이미지 도구). 비용 0. ← **다음 할 일**
2. **작은 시험:** f11·f09 × 오·웃음·놀람 × H3·Seedance 2.0 Fast·Omni, 18클립. **$5 이하, 사용자 승인 대기.**
3. **측정 도구:** 클립에서 입 윤곽, 눈꺼풀 선, 눈썹 선, 볼 실루엣과 짓기·유지·풀기 속도를 잰다. 애니에서는 사람 얼굴 인식이 실패하므로 분할 방식을 쓴다.
4. **자동 맞춤 도구:** 렌더 윤곽이 레퍼런스 윤곽에 맞도록 포즈 파일 값을 자동 조정한 뒤, 지금 방식으로 굽고 비교표를 만든다.
5. **카툰·애니 전체 세트:** 18클립과 옆모습. 약 $10~25, 승인 필요.
6. **옆모습 있음/없음 비교:** 5에 포함.
7. **이·턱·입술 맞물림:** 애니·카툰용 흰 띠 이를 만들고, f09 뒤집힘과 입꼬리 계단도 함께 고친다.
8. **새 머리 12개로 일반화 시험:** Tripo 3,000크레딧까지 승인돼 있다(미사용).
9. **실사·반실사 템플릿.**
10. **말하기:** TTS → Audio2Face. 모델 다운로드는 승인이 필요하다.
11. **몸 동작·괴물.**
12. **매 단계 문서화:** 그림을 넣은 한국어 테스트 문서, 로드맵 갱신.

## 6. 남은 문제
- 카툰 '우'에서 가운데 입술이 벌어진다.
- 실사 f02의 '오'에서 윗니가 너무 많이 보인다.
- f09는 일부 키에서 면이 뒤집힌다.
- f11·f09의 입꼬리가 계단처럼 보인다.
- 보정 키의 런타임 드라이버가 아직 없다.
- 승인 대기 중인 정리: `.tools/toporig` 6.6GB 삭제, scratch의 full·fixtest·v3 약 11GB 정리.

## 7. 사용자 규칙 (메모리에도 있음)
- 한국어로 답한다. **계획을 알릴 때는 반드시 그림(PNG)을 넣는다.** HTML을 헤드리스 Chrome으로 렌더하고 SendUserFile로 보낸다.
- 자동화를 우선한다. 사람이 직접 하는 단계를 두지 않는다.
- 비용이 드는 생성, 가입, 다운로드는 승인을 받는다. 사용자 Chrome은 로그인이 필요한 화면에서만 쓰고, 다 쓴 탭은 닫는다.
- 주간 사용량이 99%가 되면 멈춘다(get_usage로 확인).
- 내가 띄우지 않은 Blender 프로세스는 건드리지 않는다.
- 테스트마다 그림이 들어간 한국어 문서를 만든다(docs/character_pipeline/).
