# Higgsfield (higgsfield.ai) 조사 노트

- 조사일: 2026-10-14 (KST). 웹 조사만 했음. 가입, 결제, 생성, 로그인은 하지 않음.
- 표기 규칙
  - **[공식]**: Higgsfield 자체 페이지(요금표, 앱 UI, changelog, 블로그, 문서). 벤더 주장.
  - **[독립]**: 제3자 실사용 테스트나 사용자 리뷰.
  - **[제3자]**: 리셀러, 경쟁사, SEO 글. 편향 가능성이 있음.
- 요금표와 모델 선택기는 2026-10-14에 내장 브라우저로 직접 렌더링해 읽음(한국어 로케일, 비로그인). 요금 페이지는 JS로 렌더링되어 WebFetch로는 읽히지 않음.

---

## 1. 한 줄 요약

Higgsfield는 자체 모델 + 타사 모델을 모아 둔 **애그리게이터**다. 핵심 영상 엔진은 타사 모델(Kling, Seedance, Wan, Veo, MiniMax, Grok, Gemini Omni)이다. 자체 모델은 주로 카메라 프리셋(DoP), 이미지(Soul), 립싱크(Speak), 모션 전송(Genjutsu)이다.

장점
- 크레딧 하나로 여러 모델을 비교할 수 있음.
- Kling 3.0 계열은 단가가 매우 싸다(720p 5초에 약 7 크레딧, 약 $0.23~0.49).

단점
- 크레딧 정책과 요금표가 자주 바뀜.
- 무제한(Unlimited) 혜택은 웹 UI 전용이다. API, MCP, 자동화에는 쓸 수 없음.
- 결제·환불 관련 불만이 많음.

---

## 2. 제공 영상 모델 (2026-10-14 기준)

### 2.1 앱 모델 선택기 "추천 모델" 목록 [공식, 앱 UI 직접 확인]
출처: https://higgsfield.ai/ai/video (브라우저 렌더링, 2026-10-14)

| 모델 | 최대 해상도 | 길이 범위 | 비고 |
|---|---|---|---|
| Seedance 2.5 | 1080p | 4–30s | "Top" 표시. 미국에서는 사용 불가(changelog) |
| Seedance 2.5 Draft | 480p | 4–30s | 2026-09 추가된 초안 모드 |
| Seedance 2.5 Edit | 480p–720p | – | 영상 편집과 오디오 |
| Seedance 2.0 / 2.0 Fast / 2.0 Mini | 4K / 720p / 720p | 4–15s | |
| Higgsfield Genjutsu | 1080p | 4–30s | 자체 기능. 모션 전송과 오브젝트 스왑 |
| Kling 3.0 | 4K | 3–15s | |
| **Kling 3.0 Motion Control** | 1080p | **3–30s** | 참조 영상으로 캐릭터 이미지를 구동 |
| MiniMax H3 / H3 Max | 2K / 768p | 5–15s | |
| Gemini Omni Flash 1.1 (+Extend) | 4K | 3–10s | 첫·끝 프레임 제어(changelog) |
| FLUX.3 Video | 1080p | 5–20s | 오디오 동기 생성 |
| Grok Imagine 1.5 / 1.5 Lite (xAI) | 720p / 1080p | 1–15s | 2026-10-01~02 추가 |
| Wan 3.0 (+Prime) | 1080p | 2–30s | |
| HappyHorse | 1080p | 3–15s | |

- "모든 모델" 패밀리: Minimax Hailuo, FLUX.3 Video, Kling, Google Veo, Gemini Omni Flash, Higgsfield(DoP 카메라 프리셋), Wan, Seedance, Genjutsu, Grok Imagine, HappyHorse.
- 상단 탭: 비디오 만들기 / 비디오 편집 / **Motion Control**.
- Sora 2 계열은 요금표에는 남아 있지만 모델 선택기에서는 보이지 않았다. 현재 제공 여부는 **미확인**이다.

### 2.2 최근 추가 이력 [공식, changelog]
출처: https://higgsfield.ai/creator-hub/changelog (요약 도구가 읽은 결과라 날짜가 ±1~3일 다를 수 있음)

- Grok Imagine Video 1.5 (xAI): 2026-10-01~02
- Seedance 2.5 Draft Mode: 2026-09-22~24. 미국 제외.
- Genjutsu(Motion Transfer, Object Swap): 2026-09-01
- Genjutsu Restyle(원본 모션 유지): 2026-09-30
- MiniMax H3 Max: 2026-08-31
- Gemini Omni 1.1 Flash: 2026-08-28. 첫·끝 프레임, 360p 드래프트, 최대 4K.
- Wan 3.0 / Wan 3.0 Prime: 2026-08-24. 최대 30초 1080p.
- Seedance 2.5: 2026-08-03~07. 1080p 얼리 액세스는 08-14, Plus 이상.
- Audio 재설계(Qwen 기반): 2026-08-10. TTS, 보이스 체인지, 18개 언어 번역 립싱크.
- Seed Audio 1.0: 2026-06-27. 대사, 효과음, 음악을 한 번에 생성.
- Kling 3.0 Turbo: 2026-06-15~17
- Seedance 2.0 Mini, Seedance 2.0 4K: 2026-06-21~22
- Kling Motion Control MCP 추가: 2026-06-09~10
- **Higgsfield API(종량제) 출시: 2026-09-16**

### 2.3 Lipsync Studio (요금표 "Lipsync Studio" 섹션) [공식]
출처: https://higgsfield.ai/pricing (렌더링)

- Higgsfield Speak 2.0 (자체)
- Kling Speak, Kling Lipsync
- Wan 2.5 Speak / Speak Fast
- Infinite Talk
- Sync Lipsync 3 (4K 30fps)
- Google Veo 3 / Veo 3 Fast with audio

### 2.4 자체 모델과 도구 [공식]
- **DoP** (Lite / Standard / Turbo): image-to-video와 카메라 무빙 프리셋. 앱 안내 문구는 "250개 이상의 프리셋".
- **Soul 2.0 / Soul Cinema**: 이미지 모델.
- **Soul ID**: 인물 아이덴티티 학습.
- **Speak 2.0**: 토킹 헤드.
- **Genjutsu**: 모션 전송, 오브젝트 스왑, 리스타일. API 엔드포인트 `/higgsfield/genjutsu/motion-transfer/v1.0`이 있고, 소스 영상은 4초 이상이어야 한다.
- 기타: Cinema Studio 4.0, Katana(편집), AI Influencer, 3D Jutsu(신규, 미조사).

출처:
- https://higgsfield.ai/
- https://docs.higgsfield.ai/
- https://higgsfield.ai/creator-hub/changelog

---

## 3. 요금

### 3.1 구독 플랜 [공식, 2026-10-14 렌더링]
출처: https://higgsfield.ai/pricing

| 플랜 | 가격 | 월 크레딧 | 크레딧 단가 | 영상 동시 생성 | 비고 |
|---|---|---|---|---|---|
| Free | $0 | 0 (표 기준) | – | 1 | "제한된 사용"으로 표시 |
| $3 일회성 | $3 | 40 | $0.075 | – | 2일 무제한 Soul 2.0 |
| Starter | $19/월 | 270 | **$0.070** | 2 | 일부 모델만 사용 가능(Seedance 2.0 Fast/Mini). Genjutsu 무료 생성 없음 |
| Plus | $47/월(연간) · $59/월(월간) | 1,200 | **$0.039 / $0.049** | 6 | 모든 모델. Kling 3.0과 Nano Banana 2 7일 무제한. Genjutsu 720p 무료 3회 |
| Ultra | $99/월(연간) · $129/월(월간) | 3,000 (6,000·9,000 옵션 있음) | **$0.033 / $0.043** | 8 | |
| Team/Business | $65~/석/월 | 1,000/석 | – | – | 2–15석. 최대 37,500 크레딧 공유. Scale/Team은 30일 무제한 Seedance 2.5 |

**출처 간 충돌**
- [제3자] Creatify는 Free 10크레딧/일, Starter $15/200, Plus $34/1,000, Ultra $84/3,000을 표기했다. 이는 과거 또는 다른 시점의 값이다.
  - https://creatify.ai/blog/higgsfield-pricing-(2026)-plans-and-what-you-ll-actually-pay
- 위 표는 2026-10-14 렌더링 값을 우선한다.

**크레딧 정책** [공식 FAQ, 요금 페이지]
- 미사용 크레딧은 매월 리셋 때 소멸한다.
- 실패한 생성은 자동 환불된다.
- 무제한(Unlimited) 생성은 "일반 대기열"에서 처리되고 피크 시 속도가 조정된다. 크레딧 생성은 우선 대기열이다.
- **무제한과 무료 생성은 higgsfield.ai 웹에서만 쓸 수 있다. MCP/CLI, Canvas, Supercomputer에서는 불가.**
- 무제한 사용 시 자동화·스크립트 사용은 금지되며, 감지되면 이용이 정지된다.

### 3.2 모델별 크레딧 단가 [공식 요금표 "기능 비교" 섹션, 렌더링]
출처: https://higgsfield.ai/pricing

**USD 환산 기준**
- Plus 월간 결제 기준 $0.049/크레딧.
- 괄호 안은 Ultra 연간 $0.033 ~ Starter $0.070 범위.
- 8초 값은 초당 선형 환산이므로 추정치다.

| 모델 | 공식 단가 | 5초 크레딧 | 5초 USD (Plus) | 8초 USD (Plus, 추정) |
|---|---|---|---|---|
| Kling 3.0 720p | ~7 / 5s | 7 | **$0.34** ($0.23–0.49) | ~$0.55 |
| Kling 3.0 1080p | ~8 / 5s | 8 | $0.39 | ~$0.63 |
| Kling 3.0 4K | ~30 / 5s | 30 | $1.47 | ~$2.35 |
| **Kling 3.0 Motion Control 720p** | ~7 / 5s | 7 | **$0.34** | ~$0.55 |
| Kling 3.0 Motion Control 1080p | ~12 / 5s | 12 | $0.59 | ~$0.94 |
| Kling 2.6 Motion Control 720p / 1080p | ~5 / ~7 per 5s | 5 / 7 | $0.25 / $0.34 | |
| Kling Omni 3 FLF(첫·끝 프레임) 720p / 1080p | ~5 / ~6 per 5s | 5 / 6 | $0.25 / $0.29 | |
| Kling Omni 3 Image Ref 720p / 1080p | ~5 / ~7 per 5s | | $0.25 / $0.34 | |
| Kling 2.6 (사운드 포함 / 미포함) | ~10 / ~5 per 5s | | $0.49 / $0.25 | |
| Seedance 2.0 720p / 1080p / 4K | ~22 / ~45 / ~110 per 5s | | $1.08 / $2.21 / $5.39 | $1.73 / $3.53 / – |
| Seedance 2.0 Fast 720p | ~12 / 5s | | $0.59 | |
| Seedance 2.5 | 요금표 행 없음 | 아래 참고 | ~$0.7 ~ $3.9 | |
| Wan 3.0 480p / 720p / 1080p | 5 / 8.75 / 17.5 per 5s | | $0.25 / $0.43 / $0.86 | – / $0.69 / $1.37 |
| Wan 3.0 Prime 720p / 1080p | 15 / 30 per 5s | | $0.74 / $1.47 | |
| Google Veo 3.1 Fast 720p/1080p | ~16 / 4s | (8s ≈ 32) | – | **$1.57** |
| Google Veo 3.1 720p/1080p | ~40 / 4s | (8s ≈ 80) | – | $3.92 |
| Sora 2 720p (선택기에서 미확인) | ~10 / 4s | | | ~$0.98 |
| MiniMax Hailuo 2.3 768p / 1080p | ~6 / ~10 per 6s | | ~$0.25 / ~$0.41 | |
| Grok Video | ~7 / 5s | | $0.34 | |
| Higgsfield DoP Lite / Turbo / Standard 720p | ~3 / ~5 / ~7 per 3s | | | |

**Seedance 2.5 단가**
- 요금표 행이 없다.
- 플랜 카드는 Plus 1,200크레딧 ≈ "~80 Seedance 2.5 동영상"이라고 표기한다. 즉 약 15크레딧/편이며, 기본 저해상도 설정으로 추정된다.
- 앱 UI에서 5s / 1080p / 고비트레이트 설정일 때 생성 버튼에 "80"과 "60"이 함께 표시됐다(할인 전후로 추정, 미확정).
- [공식 블로그]는 8초 720p를 Starter 기준 $2.48로 추정한다.
  - 출처: https://higgsfield.ai/blog/best-affordable-ai-video-generators
- 정리하면 5초 기준 약 15~80크레딧, 즉 **$0.7~3.9(Plus)**다. 해상도에 따라 차이가 크다.

**립싱크(Lipsync Studio)**

| 모델 | 공식 단가 | 5초 USD (Plus, 환산) |
|---|---|---|
| Higgsfield Speak 2.0 720p | ~14 / 5s | **$0.69** |
| Kling Lipsync 720p (기존 영상에 입 맞춤) | ~2 / 5s | **$0.10** |
| Kling Speak 720p / 1080p | ~2 / ~4 per 2s | 5s ≈ $0.25 / $0.49 |
| Wan 2.5 Speak 480p / 720p / 1080p | ~6 / ~12 / ~20 per 5s | $0.29 / $0.59 / $0.98 |
| Infinite Talk 480p / 720p | ~18 per 5s / ~12 per 2s | $0.88 / 5s ≈ $1.47 |
| Sync Lipsync 3 4K 30fps | ~18 / 2s | 5s ≈ $2.2 |
| Veo 3 Fast w/audio 720p | ~22 / 8s | 8s ≈ $1.08 |

**독립 실측과의 대조** [독립]
- saascrmreview(2026-10-01~02, Ultra 계정, 720p)의 실측값이다.
  - Kling 3.0 5초: 10크레딧(오디오 포함), 무음 7.5크레딧.
  - Seedance 2.0 5초: 22.5크레딧.
  - Veo 3.1 Fast 8초: 32크레딧.
  - Cinema Studio 4.0 5초: 35크레딧(1080p는 60).
- 공식 표와 거의 일치한다.
- 출처: https://saascrmreview.com/?p=13747

**재시도 비용**
- [공식 블로그 인용, 제3자 경유] "사용 가능한 클립 1개에 3~5회 생성"이라는 내용이 Novoads 글에 인용돼 있다.
  - 출처: https://novoads.ai/blog/higgsfield-pricing
- **실제 예산은 위 단가의 3~5배로 잡아야 한다.**

### 3.3 API (종량제) [공식 블로그와 문서]
출처: https://higgsfield.ai/blog/higgsfield-api, https://docs.higgsfield.ai/

**기본 조건**
- 2026-09-16 출시. 구독과 완전히 별개다(구독이 API 요금이나 권한에 영향을 주지 않음).
- USD 선불 충전 방식. 최소 충전은 $5다(제3자 경유: https://www.mindstudio.ai/blog/higgsfield-api-pricing-pay-per-use/).
- 충전금은 1년 뒤 소멸한다.
- 실패한 요청은 과금하지 않는다. 결과물은 최소 7일 보관된다.
- 키 하나로 동시 요청 20개. 상업적 사용 가능.
- 카탈로그: 67개 영상 엔트리, 17개 이미지 엔트리(https://docs.higgsfield.ai/docs/models.md).
- 가격은 콘솔(https://console.higgsfield.ai)에서 확인한다.

**시작가("from")**

| 모델 | 단가 | 5초 | 8초 |
|---|---|---|---|
| Kling 2.5 | $0.042/s | $0.21 | |
| Kling 2.6 | $0.07/s | $0.35 | |
| **Seedance 2.5** | $0.0738/s | **$0.37** | $0.59 |
| **Kling 3.0** | $0.112/s | **$0.56** | $0.90 |
| PixVerse 6 | $0.115/s | | |
| MiniMax H3 | $0.13/s | $0.65 | |
| LTX 2.5 Pro | $0.17/s | | |
| Wan 3.0 | $0.20/s | $1.00 | $1.60 |
| Seedance 2.0 | $0.9332/s | | |
| DoP | $0.125/생성 | | |
| Grok Imagine Video 1.5 | $0.25/s (검색 요약 경유, 원문 미확인) | | |

- Seedance 2.0의 $0.9332/s는 오기이거나 4K 단가일 가능성이 있다. 확인이 필요하다.
- 표의 값은 최저가다. 해상도나 오디오를 올리면 비싸진다.
- [제3자] Seedance 2.5 720p는 약 $0.46/s로 추정된다. 5초면 약 $2.3이다.
  - 출처: https://www.seedance.tv/blog/higgsfield-api-pricing-per-video
- **결론: Kling 3.0은 구독 크레딧 쪽이 API보다 싸다**(구독 $0.23–0.49/5s, API $0.56/5s~).

---

## 4. 우리 용도 관련 기능

| 필요 기능 | Higgsfield 지원 | 근거 |
|---|---|---|
| 단일 이미지 → 영상(I2V) | 거의 모든 모델 | 앱 UI |
| 아이덴티티 유지 | 모델 자체 기능에 의존. Kling 3.0 Element Binding과 멀티 레퍼런스, Seedance 레퍼런스. Soul ID는 이미지용이다 | [제3자] https://www.atlascloud.ai/blog/guides/kling-ai-motion-control |
| 립싱크와 토킹헤드 | Lipsync Studio(Speak 2.0, Kling Speak/Lipsync, Wan Speak, InfiniteTalk, Sync 3). 요금표상 Speak는 Starter 이상 기능 행으로 표시된다. 독립 리뷰는 Plus 이상이라고 한다 | 요금표; https://saascrmreview.com/?p=13747 |
| 음성 생성 | Higgsfield Audio(Qwen 기반 TTS, 18개 언어). 한국어 포함 여부는 미확인. Seed Audio 1.0 | changelog |
| 표정 제어 | **명시적 표정·블렌드셰이프 제어는 없다.** 프롬프트와 참조 영상(Motion Control, Genjutsu)으로 간접 제어한다 | 앱 UI 확인 |
| 고정 정면 카메라 | 프롬프트("static camera")로 지정한다. DoP와 Cinema Studio는 카메라 프리셋 중심이라 오히려 움직이는 쪽에 특화돼 있다. 고정 보장 옵션은 확인하지 못했다 | 앱 UI |
| 모션 전송(참조 영상 → 캐릭터) | **Kling 3.0/2.6 Motion Control**(3–30s, 1080p). **Genjutsu Motion Transfer**(4–30s, 1080p, API 있음) | 앱 UI, docs |
| 첫·끝 프레임 | Kling Omni 3 FLF, Gemini Omni 1.1 Flash. 요금표 기능 행에 "시작 및 종료 프레임 제어"가 있다 | 요금표, changelog |
| 최대 길이 | Seedance 2.5, Wan 3.0, Kling MC, Genjutsu는 최대 30초 | 앱 UI |
| 해상도·fps | Kling 3.0과 Seedance 2.0은 최대 4K. ByteDance Upscale은 4K 업스케일과 60fps 보간 | 앱 UI, changelog |
| 여러 클립 간 일관성 | 동일 시작 프레임 재사용과 Kling 멀티 레퍼런스로 확보. Cinema Studio 멀티샷은 독립 테스트에서 샷 간 오브젝트 디자인이 바뀌었다 | [독립] saascrmreview |

**Kling 3.0 Motion Control 입력 조건**
- [제3자] Runway(같은 Kling 모델을 호스팅)는 다음 조건을 권장한다.
  - 캐릭터 이미지에 전신(또는 상반신), 모든 팔다리, 머리가 가림 없이 보여야 한다.
  - 실제 사람의 동작 영상을 참조로 쓴다.
  - 인간형 비율의 스타일라이즈 캐릭터는 될 수도 있다.
  - 출처: https://help.runwayml.com/hc/en-us/articles/50280558448147-Creating-with-Kling-3-0-Motion-Control
- [제3자] Atlas Cloud는 API 호출 시 캐릭터 이미지를 1장만 받는다고 한다(웹 UI는 여러 장).
  - 출처: https://www.atlascloud.ai/blog/guides/kling-ai-motion-control

---

## 5. 기대 결과 (용도별)

### (a) 얼굴 표정과 모음 입모양(아 에 이 오 우)

**선택지**
1. Kling Lipsync(약 $0.10/5s)이나 Speak 2.0($0.69/5s)에 "아-에-이-오-우" 음성을 넣는다.
2. 또는 Kling 3.0이나 Seedance에 정면 고정 프롬프트를 주고, 첫·끝 프레임을 모두 같은 중립 이미지로 지정해 원위치 복귀를 강제한다.

**품질 근거**
- **독립 테스트에서 립싱크, 애니메, 카툰 결과는 찾지 못했다.** saascrmreview는 립싱크를 범위 밖으로 뒀다.
- [공식] 토킹 비디오 가이드는 일러스트 캐릭터가 사실적인 방향으로 드리프트하는지 확인하라고 직접 언급한다.
  - 즉 애니·카툰 스타일 붕괴가 알려진 리스크다.
  - 출처: https://higgsfield.ai/blog/still-image-to-talking-video
- [공식] Soul ID는 픽셀 단위 아이덴티티 고정이 아니라고 인정한다. 낯선 각도, 조명, 스타일 변화에서 드리프트가 생긴다.
  - 출처: https://higgsfield.ai/blog/sould-id-best-character-consistency
- [독립] Soul ID 학습 테스트에서 실존 인물 아이덴티티 일치는 **5개 중 0개**였다(25크레딧, 약 4.4분).
  - 출처: https://saascrmreview.com/?p=13747
- [독립] Kling 3.0은 여성 얼굴을 안정적으로 유지했다. Veo 3.1 Fast는 클립 중간에 고개를 완전히 돌려 버렸다(동일 출처).
  - 즉 Veo는 정면 고정 측정용으로는 부적합할 수 있다.

**예상**
- 사실적, 반실사 스타일: Kling 계열 립싱크로 "참고용 입모양"은 충분할 가능성이 높다.
- 애니메와 카툰: 입 모양이 사실적 입술로 바뀌거나 치아·혀가 생성되는 아티팩트가 날 리스크가 있다. 테스트가 필요하다.
- 모음 5개 개별 포즈 측정: 프레임 단위 정확도는 보장되지 않는다. 블렌드셰이프 참고용으로만 쓴다.

### (b) 바디 모션 (걷기, 달리기, 공격, 대기, 이모트)

- **최적 경로: Kling 3.0 Motion Control.** 사람 참조 영상(직접 촬영하거나 모캡 렌더) 위에 캐릭터 이미지를 얹는다.
  - 720p 5초 약 7크레딧(약 $0.34). 최대 30초.
- [제3자/크리에이터 보고] 3.0은 발이 지면에 고정되고 체중 이동이 자연스럽다. 2.6은 "얼음 위 미끄러짐"이 있었다.
  - 조명이 고르지 않으면 아티팩트가 생긴다. 정면, 밝은 조명, 전신, 중립 시작 포즈가 성공률을 높인다.
  - 2.6은 큰 머리 회전에서 얼굴 일관성이 떨어졌다.
  - 출처: https://www.atlascloud.ai/blog/guides/kling-ai-motion-control (리셀러 글. 약 40회 생성 보고는 자가 보고)
- 대안: Genjutsu Motion Transfer(1080p, 4–30s, API 엔드포인트 있음). 독립 품질 리뷰는 찾지 못했다.
- [독립] 개 달리기 프롬프트 비교(동일 출처 saascrmreview)
  - Seedance 2.0은 끝까지 전력 질주를 유지했다.
  - Kling 3.0은 끝에서 걷기로 느려졌다.
  - 따라서 프롬프트만으로 만드는 고강도 동작(달리기, 공격)은 Seedance 계열이 유리할 수 있다.

### (c) 몬스터와 비인간형 크리처 (사족, 다족, 날개, 블롭)

- **Motion Control은 인간형 전제다.** Runway 가이드는 사람 동작 참조와 인간형 비율을 권장한다. 사족, 다족, 날개 구조에는 매핑 근거가 없다.
- 비인간형은 일반 I2V(Seedance 2.x, Kling 3.0, Veo)에 프롬프트를 주는 방식에 의존하게 된다.
- **크리처 전용 독립 테스트는 찾지 못했다.** 개(사족) 1건만 있다. 다리 개수 변화, 신체 모핑, 날갯짓 주기 불안정은 업계 공통으로 예상되는 실패 유형이다(추론).
- 블롭이나 단순 형태는 상대적으로 무난할 것으로 보인다(추론, 근거 없음).

---

## 6. 주요 리스크

1. **정책과 가격 변동이 잦다.** 요금표, 플랜 이름, 크레딧 수가 몇 달 사이에도 서로 다르게 보고된다(Creatify와 공식 요금표 비교). 매 구매 직전에 다시 확인해야 한다.
2. **무제한 혜택은 웹 UI 전용이고 자동화가 금지된다.**
   - API, MCP, Supercomputer에서는 쓸 수 없다.
   - 피크 시 느려진다.
   - 스크립트 사용이 감지되면 정지된다.
   - 우리의 자동화 우선 원칙과 충돌한다. 자동화하려면 API 종량제를 써야 한다.
   - 출처: https://higgsfield.ai/pricing
3. **결제·환불 불만이 있다** [독립, Trustpilot 개별 리뷰].
   - 무제한을 켰는데 크레딧 약 3,000이 차감됐다는 주장.
   - 해지 후 청구, 환불 거절.
   - 환불은 7일 이내이면서 크레딧 0 사용일 때만 가능하다.
   - 출처: https://uk.trustpilot.com/review/higgsfield.ai?page=8, https://www.mindstudio.ai/blog/higgsfield-subscription-cancellation-complaints
4. **학습 데이터 사용.** 입력과 출력이 모델 학습에 쓰일 수 있다. 예외는 Enterprise 계약뿐이다. 캐릭터 원화 유출 리스크가 있다.
   - 출처: https://saascrmreview.com/?p=13747 (약관 인용)
5. **오탐 차단.** 실존 인물이 아닌데 "Protected content detected"가 뜨거나 제공사 측 "IP check" 오류로 실패하는 사례가 있다(크레딧은 환불됨).
6. **재시도 비용.** 사용 가능한 클립 1개에 3~5회 생성이 필요하다고 보고된다.
7. **Seedance 2.5는 미국에서 사용 불가**(한국은 해당 없음). Sora 2는 모델 선택기에서 사라진 것으로 보인다.
8. **월 크레딧은 이월되지 않는다.**

---

## 7. 권장 (Higgsfield 한정)

- 테스트는 **Plus 월간($59, 1,200크레딧)으로 1개월**이 적당하다.
  - Kling 3.0 / Motion Control 720p 5초 기준 이론상 약 170클립이다. 재시도 3~5배를 감안하면 약 35~55개의 사용 가능한 클립이다.
  - Plus는 Kling 3.0 7일 무제한도 포함한다(웹 UI 수동 사용만 해당).
- 자동화가 필요하면 **API $5~20 충전으로 소량 검증**한다. Kling 3.0은 $0.112/s~, Seedance 2.5는 $0.0738/s~, Genjutsu는 API로 쓸 수 있다.
- 먼저 테스트할 것
  - (a) 애니 캐릭터 1장 + 한국어 모음 음성 → Kling Lipsync와 Speak 2.0을 비교해 스타일 드리프트를 본다.
  - (b) Kling 3.0 MC로 걷기와 공격을 해 본다.
  - (c) 사족 크리처 1장으로 Seedance 2.0과 Kling 3.0 I2V를 비교한다.

---

## 8. 출처 목록

**[공식]**
- https://higgsfield.ai/pricing (2026-10-14 브라우저 렌더링)
- https://higgsfield.ai/ai/video (2026-10-14 렌더링)
- https://higgsfield.ai/creator-hub/changelog
- https://higgsfield.ai/blog/higgsfield-api
- https://docs.higgsfield.ai/ , https://docs.higgsfield.ai/docs/models.md
- https://higgsfield.ai/blog/still-image-to-talking-video
- https://higgsfield.ai/blog/sould-id-best-character-consistency
- https://higgsfield.ai/blog/best-affordable-ai-video-generators

**[독립]**
- https://saascrmreview.com/?p=13747 (2026-10-02 실측)
- Trustpilot: https://uk.trustpilot.com/review/higgsfield.ai?page=8

**[제3자/리셀러/경쟁사]**
- https://creatify.ai/blog/higgsfield-pricing-(2026)-plans-and-what-you-ll-actually-pay (경쟁사)
- https://novoads.ai/blog/higgsfield-pricing (경쟁사)
- https://www.mindstudio.ai/blog/higgsfield-api-pricing-pay-per-use/
- https://www.mindstudio.ai/blog/higgsfield-subscription-cancellation-complaints
- https://www.seedance.tv/blog/higgsfield-api-pricing-per-video
- https://www.atlascloud.ai/blog/guides/kling-ai-motion-control (리셀러)
- https://help.runwayml.com/hc/en-us/articles/50280558448147-Creating-with-Kling-3-0-Motion-Control (경쟁 플랫폼의 같은 모델 가이드)
