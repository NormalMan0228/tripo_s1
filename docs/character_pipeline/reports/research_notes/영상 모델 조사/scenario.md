# Scenario (scenario.com) 영상 모델 조사 노트

- 조사일: 2026-10-14 (공개 웹만 조사함. 로그인, 가입, 결제, 다운로드는 하지 않음)
- 범위: 캐릭터별 애니메이션 참고 영상. (a) 얼굴 표정과 모음 입모양(아 에 이 오 우), (b) 몸 동작, (c) 몬스터
- 표기 규칙: **[공식]** = Scenario 문서나 마케팅(벤더 주장), **[제3자]** = 외부 사이트(대부분 다른 플랫폼 가격), **[독립 테스트]** = 실제로 써 본 리뷰, **[추정]** = 이 노트의 계산이나 추론(출처 없음)
- 도움말 문서는 대부분 날짜 없이 "N개월 전 업데이트"로만 표시된다. 상대 날짜를 그대로 적었다.

---

## 1. 결론 요약

1. Scenario는 영상 모델을 직접 만들지 않는다. 남의 모델을 묶어 파는 곳이다(Kling, Veo, Seedance, Wan, MiniMax, Runway, Luma, PixVerse, Vidu, LTX, Sora 2, HeyGen, Sync Labs 등). 공식 집계는 "100+ video models"이다. [공식] https://www.scenario.com/features/generate-videos
2. **최신 영상 모델의 CU 단가는 공개 페이지에 없다.** 생성 버튼, Compute Planner, API `?dryRun=true`로만 확인할 수 있다. 공개된 "Pricing from X CU" 값은 구형 모델 몇 개뿐이다. [공식] https://help.scenario.com/articles/8811829644-model-costs-for-asset-generation
3. CU 1개 ≈ **$0.010** (Starter 월결제 기준: $15에 1,500 CU). Pro 이상은 CU가 더 싸고 연간 결제는 33% 할인이다(아래 2장 참고).
4. 우리 용도에 가장 쓸 만한 도구는 셋이다.
   - (a) 얼굴: **Kling AI Avatar V2 Pro**(이미지와 오디오로 립싱크), **Kling Lipsync**(영상에 오디오를 입혀 입만 다시 그림), **Seedance 2.5**(referenceAudio로 입 타이밍 조절)
   - (b) 몸: **Kling V3 Motion Control Std/Pro**(캐릭터 이미지에 참고 영상의 동작을 옮김)
   - (c) 몬스터: 전용 도구가 없다. Kling V3 / Veo 3.1 / Seedance 2.5의 image-to-video에 프롬프트를 쓰고, 처음·끝 프레임을 같은 이미지로 두어 루프를 만드는 방법뿐이다.
5. 큰 위험은 다섯 가지다. 단가가 비공개라는 점, 시드가 없어 같은 결과를 다시 뽑을 수 없다는 점, 애니메·2D 스타일이 약하다는 점, 모션 컨트롤이 사람 형태가 아니면 실패할 수 있다는 점, 립싱크 작업이 "성공"해도 입이 안 움직일 수 있다는 점이다.

---

## 2. 요금제와 CU

### 2.1 요금제 [공식]

| 플랜 | 월 가격 | 월 CU | 메모 |
|---|---|---|---|
| Free | $0 | **50 CU/일** (00:00 UTC 초기화, 이월 없음) | 개인·평가용만 가능, 상업 사용 불가, API 없음, CU 추가 구매 불가 |
| Starter | $15 | 1,500 | 표준 단가, API 사용 가능 |
| Pro | $45 | 5,000 | **연산 할인 10%**, 우선 대기열, CU 소진 후 웹에서 "Relax" 모드 무제한 |
| Max | $75 (추가 좌석 $30/월부터) | 10,000 | **연산 할인 20%**, 최대 25명 |
| Enterprise | 사용자당 월 $125부터 / 별도 협의 | 사용량제 | 연산 할인 30%, 12개월 계약 |

- 출처: https://www.scenario.com/pricing , https://help.scenario.com/articles/4276871610-pricing-plans (7일 전 업데이트), https://help.scenario.com/articles/8811829644-model-costs-for-asset-generation (할인율)
- 연간 결제는 33% 저렴하다. 연간 금액은 페이지에 나와 있지 않다. [공식] https://help.scenario.com/articles/4276871610-pricing-plans
- 무료 크레딧 표기가 페이지마다 다르다. 가격 페이지 배너는 "50 free daily credits", FAQ는 "50 credits"라고 쓴다. 도움말은 "50 CU per day"이다. [공식] https://www.scenario.com/pricing
- 월 CU는 이월되지 않는다. 추가 구매한 CU는 "90일에서 1년" 동안 유효하고, 월 CU를 다 쓴 다음에 차감된다. 추가 CU 가격은 공개되지 않았고 결제 화면에서만 보인다. [공식] https://help.scenario.com/articles/8811829644-model-costs-for-asset-generation , https://help.scenario.com/articles/7157036624-usage-limits-and-compute-units-cu
- 상업 이용: "All paid plans include a full commercial license." 무료 플랜 결과물은 개인·평가용이다. [공식] https://www.scenario.com/pricing
- 한도를 넘으면 Free와 Starter는 생성이 멈춘다. Pro 이상은 웹에서 Relax 모드로 넘어간다. **API는 어느 플랜이든 한도에서 멈춘다.** [공식] https://help.scenario.com/articles/7157036624-usage-limits-and-compute-units-cu

### 2.2 CU를 달러로 바꾸기 [추정, 공식 환율은 없음]

Scenario는 CU의 달러 환율을 공개하지 않는다. "One CU does not equal one image"라는 문구만 있다. [공식] https://help.scenario.com/articles/8811829644-model-costs-for-asset-generation

아래는 정가로 직접 나눈 값이다.

| 플랜 | 정가 기준 $/CU | 할인 반영 (모델 CU 가격에 할인이 적용된다고 가정) |
|---|---|---|
| Starter 월결제 | $0.0100 | $0.0100 |
| Pro 월결제 | $0.0090 | 약 $0.0081 |
| Max 월결제 | $0.0075 | 약 $0.0060 |
| Starter 연간 (-33%) | 약 $0.0067 | 약 $0.0067 |

아래 표에서는 계산을 쉽게 하려고 **1 CU ≈ $0.01** 로 잡는다(보수적인 값).

### 2.3 영상 한 편당 CU

**공개된 실제 값 [공식, 각 모델 페이지의 "Pricing from"]**: 최저 설정 기준의 시작가다.

| 모델 | 시작가 | 약 USD | 상태 | 출처 |
|---|---|---|---|---|
| Seedance 1.5 Pro (1080p, 최대 12초, 오디오와 다국어 립싱크) | 40 CU부터 | $0.40 | **사용 중단(deprecated)**, 후속은 Seedance 2.5 | https://www.scenario.com/models/seedance-15-pro |
| Kling 1.6 Pro (처음·끝 프레임, 1080p) | 75 CU부터 | $0.75 | 구형 | https://www.scenario.com/models/kling-16-pro |
| Kling O1 Reference Images (참고 이미지 최대 7장으로 캐릭터 고정) | 90 CU부터 | $0.90 | 현역 | https://www.scenario.com/models/kling-o1-reference-images |
| Seedance 1 Pro (1080p, 2–12초) | 114 CU부터 | $1.14 | 구형 | https://www.scenario.com/models/seedance-1-pro |

**최신 모델(Veo 3.1, Kling V3, Seedance 2.5, Motion Control, AI Avatar)**: 공개 페이지에 CU 값이 없다. 구조화 데이터에는 가격이 "0"으로 들어 있는데, 자리 표시값으로 보인다. 확인한 페이지:
- https://www.scenario.com/models/veo-31
- https://www.scenario.com/models/kling-v3-i2v-standard
- https://www.scenario.com/models/kling-v3-std-motion-control
- https://www.scenario.com/models/kling-v3-pro-motion-control

공식 문서가 밝힌 상대적인 비용 정보는 다음과 같다.
- Veo 3.1 Fast는 Standard의 "약 절반" 가격이고, Lite는 Fast보다 싸다. [공식] https://help.scenario.com/articles/1049410120-veo-3-1-the-essentials
- Kling 4K는 Standard의 몇 배이고 초 단위로 과금된다. AI Avatar 비용은 설정에 따라 **최대 100배까지** 차이 난다. 반드시 dry run을 먼저 돌려야 한다. [공식, Scenario의 에이전트 스킬 문서] https://raw.githubusercontent.com/scenario-labs/skills/main/skills/scenario-kling/SKILL.md
- 해상도, 길이, 오디오, 참고 영상 입력이 비용을 올린다. image-to-video와 multi-shot은 같은 해상도의 text-to-video보다 비쌀 수 있다. [공식] https://help.scenario.com/articles/8811829644-model-costs-for-asset-generation

**최신 모델 추정값 [추정]**

계산 방법: 아래 업스트림 API 초당 가격에 Scenario 마진을 곱하고 1 CU = $0.01로 환산했다.
- 업스트림 가격 출처 [제3자]: Kling 3.0 무음 720p $0.084/s, 오디오 포함 $0.126/s. Veo 3.1 Standard $0.40/s, Fast 720p $0.10/s, Lite 720p $0.05/s(Teamday, 2026-09-23 확인, https://www.teamday.ai/blog/best-ai-video-models-2026). Kling v3 Std $0.071/s, Pro $0.095/s, Seedance 2.0 약 $0.112/s(Atlas Cloud, https://www.atlascloud.ai/blog/guides/kling-ai-pricing). 이 값들은 Scenario 가격이 아니다.
- 마진: 구형 모델의 공개가와 업스트림 가격을 비교하면 Scenario 마진은 대략 1.0–1.8배로 보인다(추정). 아래 범위는 1.0배와 1.8배를 적용한 값이다.

| 클립 | 5초 CU (≈USD) | 8초 CU (≈USD) |
|---|---|---|
| Kling V3 Std I2V (무음 720p) | 35–65 CU ($0.35–0.65) | 57–100 CU ($0.57–1.00) |
| Kling V3 Pro I2V (1080p, 오디오 끔) | 48–85 CU ($0.48–0.85) | 76–140 CU ($0.76–1.40) |
| Kling V3 + 오디오 | 63–115 CU | 100–180 CU |
| Kling V3 Motion Control Std/Pro | Kling V3 I2V와 비슷할 것으로 추정 (비공개) | 동일 |
| Veo 3.1 Lite (720p) | 25–45 CU ($0.25–0.45) | 40–72 CU ($0.40–0.72) |
| Veo 3.1 Fast (720p) | 50–90 CU ($0.50–0.90) | 80–145 CU ($0.80–1.45) |
| Veo 3.1 Standard (1080p, 오디오) | 200–360 CU ($2–3.6) | **320–575 CU ($3.2–5.8)** |
| Seedance 2.x (720p) | 56–100 CU ($0.56–1.00) | 90–160 CU ($0.90–1.60) |
| Kling AI Avatar V2 Pro | **비공개, 설정에 따라 100배 차이 → dry run 필수** | 동일 |

- **실패와 재시도 비용을 따로 잡아야 한다.** 쓸 만한 컷 하나에 보통 3–4번 생성한다고 보면, 실제 비용은 위 값의 3–4배다. (Seedance 블로그의 가상 예시: 40 크레딧짜리 컷이 재시도 3번으로 160 크레딧. [제3자, 예시] https://www.seedance.tv/blog/kling-ai-credits-per-video)
- **정확한 값을 확인하는 법 (CU 소모 없음)**: 웹 생성 버튼에 표시되는 CU를 본다. 또는 Organization Settings > Compute Planner를 쓰거나, API에 `POST https://api.cloud.scenario.com/v1/generate/custom/{modelId}?dryRun=true`를 보낸다. [공식] https://help.scenario.com/articles/7934059476-api-usage-and-credits-compute-units

---

## 3. Scenario의 영상 모델 목록 (2026-10 기준)

### 3.1 도움말 "Video Generation" 모음, 39개 문서 [공식]
https://help.scenario.com/collections/8732525598-video_generation

- Google: Veo 3 / 3.1(Standard, Fast, Lite, Extend), Gemini Omni 계열
- Kuaishou Kling: V1.6, V2.1, V2.5, V2.6, V3(Std/Pro/4K, T2V/I2V), V3 Omni Video, O1(I2V / Reference Images / Reference Video / Video Edit), Motion Control(V2.6, V3 Std, V3 Pro), AI Avatar V2 Pro, Lipsync, Video to Audio
- ByteDance Seedance: 1 Pro / Lite, 1.5 Pro(사용 중단), 2, **2.5**
- Alibaba: Wan 2.2 / 2.5 / 2.6 / 2.7 / **3.0**, Happy Horse 1.0 / 1.1
- MiniMax: Hailuo 2.3(Fast), **H3**
- OpenAI: Sora 2 / Sora 2 Pro
- Runway: Gen-4.5, Aleph(편집)
- Luma: Ray 3.2, Reframe
- PixVerse: V5 / V6, VibeMV
- Shengshu Vidu: Q2 Reference / Q3 Pro / **Q4**
- Lightricks LTX: LTX-2 / 2.3(Fast, Retake)
- 기타: xAI Grok Imagine Video 1.5, BFL FLUX.3 Video, Kandinsky 6.0, Pruna P-Video, Ovi, HeyGen Video Agent / Avatar 4, SAM3(분할)

### 3.2 API 문서의 제공사별 모델 수 [공식]
https://docs.scenario.com/get-started/generation/video-generation

| 제공사 | 모델 수 | 제공사 | 모델 수 |
|---|---|---|---|
| Kuaishou | 27 | Lightricks | 26 |
| Scenario(자체 도구) | 30 | Alibaba | 18 |
| Shengshu | 16 | Google | 11 |
| MiniMax | 11 | Bytedance | 8 |
| Luma | 7 | PixVerse | 6 |
| Pruna | 6 | Sync Labs(립싱크) | 5 |
| xAI | 5 | HeyGen | 4 |
| Runway | 4 | Cartwheel | **1** |

- Cartwheel은 텍스트로 3D 모션을 만드는 회사로 알려져 있다. 리깅된 3D 애니메이션을 바로 받을 수 있다면 (b)에 영상보다 나을 수 있다. 이 모델의 상세 페이지는 이번에 확인하지 못했다. 다음 URL로 확인해야 한다: https://docs.scenario.com/get-started/generation/video-generation/video-generation-cartwheel
- "Scenario"가 제공사인 30개는 자체 영상 도구다. 문서와 스킬에서 보이는 것은 영상 자르기, 오디오 추출 같은 후처리와 업스케일이다. [공식] https://raw.githubusercontent.com/scenario-labs/skills/main/skills/scenario-video/SKILL.md

### 3.3 Kling 27종 세부 (API 문서) [공식]
https://docs.scenario.com/get-started/generation/video-generation/video-generation-kuaishou-technology

| 모델 | 우리 용도 | 길이 | 입력 / 비고 |
|---|---|---|---|
| Kling AI Avatar V2 Pro (`model_kling-video-ai-avatar-v2-pro`) | (a) 립싱크·표정 | 오디오 길이를 따름 | 이미지와 오디오 파일 필수 |
| Kling Lipsync (`model_kling-lip-sync`) | (a) 기존 영상의 입만 교체 | 입력 영상 2–10초, 720–1080p | 오디오 파일, 또는 텍스트와 voiceId |
| Kling V3 I2V Std / Pro / 4K | (a)(b)(c) 일반 I2V | 3–15초 | 시작 이미지 필수, 끝 프레임 선택, 오디오 기본 켜짐 |
| Kling V3 Omni Video | 참고 이미지·영상 혼합 | 3–15초 | 참고 이미지 최대 7장(영상을 쓰면 4장), 720p/1080p/4K. 4K에서는 참고 영상 불가 |
| Kling O1 Reference Images | 캐릭터 고정 | 3–10초 | 참고 이미지 최대 7장, 끝 프레임 없음 |
| Kling V3 Std / Pro Motion Control | (b) 동작 전이 | 공개 안 됨 | 캐릭터 이미지와 구동 영상(mp4/mov/webm/m4v/gif) |
| Kling V2.6 Motion Control | (b) | 구동 영상 최대 10초(image 방향) 또는 30초(video 방향) | 캐릭터 이미지 340–3850px, pro/std 모드 |

- fps는 어느 모델에도 표기되어 있지 않다. [공식] 같은 출처
- **어떤 Kling 모델에도 시드(seed)가 없다.** 마음에 드는 결과를 다시 똑같이 뽑을 수 없다. 클립 연장 기능도 없어서, 앞 클립의 마지막 프레임으로 새 I2V를 돌려 이어 붙여야 한다. [공식] https://raw.githubusercontent.com/scenario-labs/skills/main/skills/scenario-kling/SKILL.md
- Kling이 생성하는 음성은 중국어와 영어만 된다. 다른 언어는 영어로 번역된다. **한국어 음성은 직접 생성할 수 없으니 오디오 파일을 따로 넣어야 한다.** [공식] 같은 출처

### 3.4 기타 주요 모델 [공식]

**Veo 3.1** (https://help.scenario.com/articles/1049410120-veo-3-1-the-essentials , https://www.scenario.com/models/veo-31)
- 1080p, 오디오 생성.
- 처음·끝 프레임을 지원한다. 참고 이미지는 1–3장이다.
- **처음 프레임과 참고 이미지는 같이 쓸 수 없다.**
- Extend는 한 번에 7–8초씩 늘리고 최대 148초까지 간다.
- Standard, Fast, Extend는 **Pro 플랜 이상**에서만 쓸 수 있다. Lite(4/6/8초, 720p/1080p)는 모든 플랜에서 된다.

**Seedance 2.5** (https://help.scenario.com/articles/1651934064-seedance-2-5-the-essentials, 8일 전 업데이트)
- 4–30초, 480p/720p/1080p. 4K는 없다.
- 참고 이미지 최대 30장, 참고 영상 최대 10개, 참고 오디오 최대 10개.
- `referenceAudio`는 타이밍과 립싱크를 조절하지만 **결과물에는 소리가 들어가지 않는다.**
- 처음 프레임과 참고 이미지는 같이 쓸 수 없다.
- 시드, 마스크, 3D 참고 입력이 없다.
- 네이티브 오디오는 생성 후 검열되어 완성된 클립이 막힐 수 있다.
- 공식 예시로 애니메풍 장면 연장이 있다.

**Kling V3 일반** (https://help.scenario.com/articles/7001313393-kling-v3-the-essentials)
- 사실적인 사람, 시네마틱 장면, **3D풍 애니메이션은 "exceptionally strong"**이라고 한다.
- **평면 2D 전통 애니메이션은 "more challenging"**이라고 인정한다.
- 멀티샷은 최대 5샷이다. 끝 프레임은 단일 샷일 때만 된다.

**모델 고르기 가이드** (https://help.scenario.com/articles/6618023406-how-to-choose-the-right-video-model-2026-edition, 6개월 전 업데이트)
- 캐릭터 고정: Kling O1 Reference ("Character Locking" 1위)
- 원본 이미지에 충실한 I2V: Wan 2.6 I2V ("least hallucination")
- 립싱크: HeyGen Avatar 4, Kling AI Avatar 2 ("perfect phonetic lip-sync", 벤더 주장). 기존 영상 더빙: Sync Lipsync React-1
- 빠른 초안: LTX-2 Fast, Hailuo 2.3 Fast

**공통 기능** [공식]
- I2V, T2V, V2V를 지원한다.
- 처음·끝 프레임으로 루프를 만들 수 있다.
- 영상 길이, 해상도, 모션 강도, 카메라 이동을 조절할 수 있다.
- 출처: https://www.scenario.com/features/generate-videos , https://help.scenario.com/articles/4919258867-introduction-to-video-generation

**고정 카메라** [공식]
- 프롬프트를 고정 카메라 문구로 시작한다.
- 카메라 제어 UI의 Pan, Tilt, Zoom을 0으로 둔다.
- 출처: https://help.scenario.com/articles/1755388979-troubleshooting-video-generations

**API** [공식]
- Starter 이상 모든 유료 플랜에서 쓸 수 있고, 웹과 같은 CU 잔액을 공유한다.
- 비동기 작업이다: `POST /v1/generate/custom/{modelId}`로 jobId를 받고 `GET /v1/jobs/{jobId}`로 상태를 확인한다.
- dryRun 파라미터로 비용을 미리 볼 수 있다.
- MCP 서버와 에이전트 스킬(scenario-labs/skills)이 있다. Blender, Unity, Unreal, Godot용 스킬 폴더도 있다.
- 출처: https://help.scenario.com/articles/7934059476-api-usage-and-credits-compute-units , https://docs.scenario.com/get-started/generation/video-generation , https://github.com/scenario-labs/skills
- 대량 생성은 API로 작업을 여러 개 동시에 보내는 방식이다. 웹 UI의 배치 기능은 이번에 확인하지 못했다.

**LoRA** [공식]
- 학습한 LoRA는 영상 모델에 적용되지 않는다.
- LoRA로 스틸 이미지를 먼저 만들고, 그 이미지를 처음 프레임이나 참고 이미지로 쓴다.
- 출처: https://raw.githubusercontent.com/scenario-labs/skills/main/skills/scenario-video/SKILL.md

---

## 4. 용도별 예상 결과

### (a) 얼굴 표정과 입모양(아 에 이 오 우)

**추천 흐름 [추정, 공식 기능을 조합한 것]**
1. 캐릭터 정면 얼굴 이미지를 크게 크롭한다.
2. 한국어 모음 "아-에-이-오-우" 오디오를 준비한다. 직접 녹음하거나 TTS를 쓴다. Scenario에도 ElevenLabs TTS가 있다(https://docs.scenario.com/get-started/generation/video-generation).
3. Kling AI Avatar V2 Pro에 이미지와 오디오를 넣어 말하는 영상을 만든다.
4. 표정(기쁨, 슬픔, 화남 등)은 Kling V3 I2V나 Seedance 2.5에 고정 카메라 프롬프트를 쓰고, 처음 프레임과 끝 프레임을 같은 이미지로 넣어 중립 → 표정 → 중립 루프로 만든다.

**예상 품질**
- 사실풍·반실사: 좋을 것으로 예상한다. 벤더가 "lifelike facial animation and accurate lipsync"라고 주장한다. [공식] https://help.scenario.com/articles/8534375995-kling-video-models-the-essentials
- 3D 카툰풍: Kling V3가 3D풍에 강하다고 명시한다. [공식] https://help.scenario.com/articles/7001313393-kling-v3-the-essentials
- 2D 애니메풍: 약하다. "flat 2D traditional animation"이 어렵다고 공식 문서가 인정한다. 애니메 얼굴은 입이 작고 단순해서 립싱크 모델이 사람 입처럼 다시 그릴 위험이 있다. 이 부분은 [추정]이고, 실제 테스트 자료는 찾지 못했다.

**실패 패턴 [공식, 스킬 문서]** (https://raw.githubusercontent.com/scenario-labs/skills/main/skills/scenario-video/SKILL.md)
- 작업은 "완료"로 끝났는데 입이 그대로인 경우가 있다. 같은 시점의 원본과 결과 프레임을 비교해야 한다.
- 얼굴이 작거나, 돌아가 있거나, 흐리면 립싱크가 실패한다. 얼굴을 크게 크롭해서 넣어야 한다.
- AI Avatar는 얼굴 전체 움직임을 새로 만들어 낸다. 결과가 원본 메시의 표정과 1:1로 대응하지 않는다.

**우리 파이프라인에서의 의미 [추정]**
- 결과 영상은 ARKit 52 셰이프키를 손으로 맞출 때 보는 참고 자료로만 쓸 수 있다.
- 영상에서 블렌드셰이프 값을 자동으로 뽑는 기능은 Scenario에 없다.

### (b) 몸 동작(걷기, 달리기, 공격, 대기, 이모트)

**최선의 도구는 Kling V3 Motion Control Std/Pro다.**
- 캐릭터 이미지 1장과 동작 참고 영상(직접 찍은 영상이나 스톡 영상)을 넣으면 동작이 그대로 옮겨진다.
- Pro는 손동작과 복잡한 제스처용이고, Std는 싼 프로토타입용이다.
- "Character Orientation"을 video로 두면 시작 자세가 달라도 참고 영상 쪽 방향을 따른다.
- [공식] https://help.scenario.com/articles/2242372122-kling-v3-motion-control-the-essentials , https://www.scenario.com/models/kling-v3-pro-motion-control

**대기·이모트**
- Kling V3 I2V나 Veo 3.1에 처음과 끝 프레임을 같은 이미지로 넣어 루프를 만든다. [공식] https://www.scenario.com/features/generate-videos

**예상 품질 [독립 테스트/제3자]**
- 동작이 뚜렷하고 연속적일 때 가장 안정적이다. 손, 소품, 아주 빠른 동작은 예측하기 어렵다. [독립 테스트] https://aiimagetovideo.pro/blog/kling-motion-control/
- 보이지 않던 팔다리를 지어낸다. 예: 주머니에 넣은 손이 손을 흔드는 동작에서 새로 생긴다.
- 회전이 있으면 3D풍이나 사실풍 캐릭터가 낫다. 평면 2D는 뒷모습에서 무너질 수 있다. [제3자 문서] https://docs.comfy.org/tutorials/partner-nodes/kling/kling-motion-control
- 캐릭터와 참고 영상의 비율이 맞아야 한다. 상반신 캐릭터에 전신 동작을 넣으면 안 된다. 참고 영상에는 한 명만 있어야 한다. [제3자] https://help.runwayml.com/hc/en-us/articles/50280558448147-Creating-with-Kling-3-0-Motion-Control , https://kling.ai/blog/ai-motion-transfer-video-tutorial

**한계 [추정]**
- 출력이 영상이어서 리타깃할 수 있는 모션 데이터가 아니다. 카메라와 원근이 섞여 있어서 Rigify 키프레임을 찍을 때 눈으로 보는 참고 자료로만 쓸 수 있다.
- 3D 모션 데이터가 필요하면 Cartwheel(위 3.2)을 따로 확인해야 한다.

### (c) 몬스터(네발, 다리가 많은 것, 날개, 젤리형)

**Scenario에 전용 도구는 없다.**

**모션 컨트롤**
- 문서끼리 말이 다르다. Artlist는 "사람 같은 대상이 감지되지 않으면 실패할 가능성이 높다"고 쓴다(https://help.artlist.io/hc/en-us/articles/34809730954269-Kling-3-0-Motion-Control). Runway는 "일부 순수 동물"이 된다고 쓴다(https://help.runwayml.com/hc/en-us/articles/50280558448147-Creating-with-Kling-3-0-Motion-Control). 둘 다 [제3자]다.
- 사람 동작 참고 영상으로 네발 몬스터를 움직이는 것은 사실상 무리다 [추정].

**현실적인 방법 [추정]**
- I2V(Kling V3 Pro, Veo 3.1, Seedance 2.5)에 걸음새를 구체적으로 묘사한 프롬프트를 쓴다. 예: "네 다리 대각선 보행, 좌전–우후 동시". 고정 카메라에 측면 시점으로 둔다.
- 생성 텍스트로 "running horse"처럼만 쓰면 일반적인 동작이 나온다는 지적이 있다. [제3자] https://kling.ai/blog/ai-motion-transfer-video-tutorial

**예상 실패 [추정, 독립 테스트를 찾지 못함]**
- 다리 개수가 바뀌거나 다리가 합쳐진다.
- 날개 관절이 무너진다.
- 젤리형은 형태가 계속 바뀐다.
- 그래서 몬스터 쪽이 재시도 횟수가 가장 많을 것으로 예상한다.

---

## 5. 위험 요약

1. **최신 모델 단가가 비공개다.** 예산 계산 전에 웹 버튼 표시값이나 dryRun으로 확인해야 한다. 위 추정표 오차는 ±80%다.
2. **시드가 없다**(Kling 전 모델, Seedance 2.5). 좋은 결과를 똑같이 다시 만들 수 없다. 같은 캐릭터로 동작 세트를 만들면 컷마다 얼굴과 비율이 조금씩 달라질 수 있다.
3. **Veo 3.1 Standard, Fast, Extend는 Pro 이상에서만 쓸 수 있다.** 사용자 플랜을 확인해야 한다.
4. 애니메·2D 스타일은 공식적으로도 약하다고 인정한다. 2D 캐릭터는 회전과 뒷모습이 무너진다.
5. 모션 컨트롤은 사람 형태가 전제다. 몬스터는 I2V 운에 기대야 한다.
6. 오디오 검열 때문에 완성된 클립이 막힐 수 있다(Seedance 2.5). 한국어 음성은 Kling이 직접 만들 수 없다.
7. 월 CU는 이월되지 않는다. 추가 CU는 Free 플랜에서 살 수 없다.
8. 결과물은 영상일 뿐이다. 블렌드셰이프 값이나 본 애니메이션을 자동으로 뽑아 주지 않는다.

## 6. 다음에 확인할 것 (CU 소모 없음)

- 웹에서 Kling AI Avatar V2 Pro, Kling V3 Std/Pro Motion Control, Kling V3 I2V Std, Veo 3.1 Lite/Fast, Seedance 2.5를 차례로 고르고, 5초 720p와 8초 설정에서 버튼에 표시되는 CU를 적는다.
- Cartwheel 모델이 3D 모션(FBX/GLB)을 내보내는지 확인한다.
- 추가 CU 구매 단가를 결제 화면에서 확인한다.
