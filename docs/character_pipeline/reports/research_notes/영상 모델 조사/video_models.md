# 영상 생성 모델 조사 (Higgsfield·Scenario 제외) — 2026-10-14

목적: 캐릭터별 **애니메이션 참고 영상** 생성 — (a) 얼굴 표정·모음 입모양(아 에 이 오 우), 만화/애니/실사/세미실사, 한 장 이미지→영상, 정체성 유지 (b) 몸 동작(걷기·달리기·공격·대기·이모트) (c) 몬스터(사족·다족·날개·슬라임).

표기:
- **[V]** 회사 자체 주장 · **[I]** 독립 테스트/벤치마크/리뷰 · **[3P]** 제3자 가격표·리셀러·블로그(검증 안 됨) · **[계산]** 내 산수 · **[추정]** 내 판단
- 가격은 2026-08~10 자료 기준이며 출처끼리 자주 어긋남. 결제 전 공식 가격표 재확인 필요.
- 8초 가격 = 초당 가격 × 8 [계산]. 구독 크레딧은 "크레딧당 달러"로 환산.
- 조사 범위 제한: 검색·페치 약 25회로 마감. Reddit 원문은 직접 못 열었고, 몬스터/사족보행 독립 비교는 **찾지 못함**.

---

## 0. 한눈에 (8초 클립 기준 대략 USD)

| 모델 / 도구 | 8초 가격(대략) | 얼굴 | 몸 | 몬스터 | 한 줄 이유 |
|---|---|---|---|---|---|
| LivePortrait (로컬, 무료) | $0 | 4 | – | 2 | 내 얼굴 영상으로 정지 이미지 표정·입 구동, 8GB OK, 동물(고양이·개) 모드 |
| Runway Act-Two | ≈$0.40 | 5 | 2 | 3 | 연기 전이(표정·입), 눈·입 있는 비인간 OK, 허리 위만 |
| Gemini Omni Flash 1.1 (Gemini Pro 구독 포함) | 구독 내 $0 / API ≈$0.80 | 4 | 4 | 3 | AA I2V 공동 1위권, 첫·끝 프레임 고정(루프), 3초 영상 참조 |
| Veo 3.1 / Fast / Lite (Gemini·Flow 포함) | 구독 내 $0 / API $3.20·$0.96·$0.64 | 4 | 3 | 3 | 대사·립싱크 강점, 8초 고정, AA에선 신형보다 하위 |
| Kling 3.0 + Motion Control / Elements | ≈$0.70–1.12 (MC ≈$0.78–1.05) | 4 | 5 | 3 | 참조 영상 동작 전이, 애니·3D 지원 명시, 고개 돌릴 때 얼굴 흔들림 보고 |
| Seedance 2.5 (Dreamina) | ≈$0.78 (연간) ~ $3.3 (API) | 4 | 5 | 3 | 15모델 비교에서 얼굴 가장 안정, 참조영상 동작·타임스탬프, 30초 |
| MiniMax H3 / Hailuo 3 | ≈$0.20–0.72 | 4 | 4 | 3 | AA I2V 1위권 + 최저가급; 오픈가중치는 **한국 사용 불가** 라이선스 |
| Vidu Q4 Preview | ≈$0.36–0.67 | 4 | 3 | 3 | AA 공동 1위권, 참조 15장, 저가; 애니 주장은 자사 자료뿐 |
| Wan 3.0 (API) / Wan-Animate-2 (오픈) | ≈$1.60 / 로컬·클라우드 GPU | 3 | 4 | 2 | Animate-2는 Apache-2.0 동작 전이; 사람 체형 중심 |
| Hedra Character-3 / HeyGen Avatar IV | ≈$0.40 | 4 | 1 | 2 | 오디오→립싱크, 스타일·비인간 얼굴 지원 주장 |
| OmniHuman 1.5 (ByteDance) | ≈$0.96–2.00 | 4 | 1 | 2 | 오디오 구동 아바타, 애니 지원은 리셀러 주장 |
| PixVerse V6 | ≈$0.36–0.92 | 3 | 3 | 3 | 저가, AA 중위권 |
| Grok Imagine Video 1.5 | ≈$1.12 (720p) | 3 | 3 | 3 | AA 9–10위, 참조 이미지 1–7장 |
| Luma Ray3.14 | ≈$0.48 (720p) | 3 | 3 | 3 | 저렴한 개정판, 비교 자료 적음 |
| Runway Gen-4.5 | ≈$0.96 | 3 | 3 | 3 | 범용, AA 상위권 아님 |
| Pika 2.5 / Pikaformance | ≈$0.4–1.6 | 3 | 2 | 2 | 오디오 립싱크 저렴, 720p 상한 |
| Midjourney Video | ≈$0.07–0.22 / 5초 | 3 | 2 | 3 | 가장 쌈, API 없음, 립싱크 없음 |
| LTX-2.5 (오픈가중치 22B) | API ≈$1.04 / 로컬 | 3 | 3 | 2 | 오픈이나 8GB에선 비현실적 |
| Adobe Firefly Video | ≈$2–4 | 2 | 2 | 2 | 상업 안전성 외엔 비쌈 |

(점수는 [추정]: 아래 근거 종합. 몬스터 점수는 독립 테스트가 없어 전부 추정.)

---

## 1. 독립 벤치마크: Artificial Analysis (AA) Image-to-Video 아레나

출처: https://artificialanalysis.ai/video/leaderboard/image-to-video (AA-Video-I2V v1.1, 블라인드 쌍대 투표 Elo, 오디오 포함 보드로 보임, 2026-10 페치) **[I]**

| 순위(범위) | 모델 | Elo | 1080p 1분 API 가격 |
|---|---|---|---|
| 1 (1–5) | MiniMax H3 (768p) | 1131 | $5.40 |
| 2 (1–5) | Vidu Q4 Preview | 1130 | $5.04 |
| 3 (1–5) | Gemini Omni Flash 1.1 | 1130 | $9.12 |
| 4 (1–7) | Dreamina Seedance 2.5 | 1125 | $24.60 |
| 5 (3–7) | Wan 3.0 | 1118 | $12.00 |
| 6 | MiniMax H3 Max | 1117 | $5.76 |
| 7 | Dreamina Seedance 2.0 | 1114 | $22.45 |
| 8 | FLUX 3 (BFL) | 1084 | $17.40 |
| 9 | Grok Imagine Video 1.5 | 1065 | $15.00 |
| 10 | HappyHorse-1.1 (Alibaba-ATH) | 1060 | $9.90 |
| 11 | MAGI-2 Preview (Sand.ai, 오픈) | 1044 | – |
| 13 | Veo 3.1 | 1034 | $24.00 |
| 15 | Wan 2.7 | 1025 | $9.00 |
| 16 | PixVerse V6 | 1024 | $6.90 |
| 17 | Veo 3.1 Fast | 1017 | $9.00 |
| 19 | Kling 3.0 1080p Pro (기준점) | 1000 | $20.16 |
| 21 | LTX-2.5 Fast | 997 | $7.80 |

- 오픈가중치 보드: MiniMax H3 > MAGI-2 Preview > LTX-2.5 Fast > LTX-2.5 Pro > LTX-2.3 (https://artificialanalysis.ai/video/leaderboard/image-to-video/open-weights) **[I]**
- 주의: 일반 선호도(화질·움직임)이지 **정체성 유지·해부학·고정 카메라·애니 스타일**을 따로 재지 않음. 상위 1–7위는 신뢰구간이 겹쳐 사실상 동률. 스냅샷 시점마다 순위가 바뀜(7월 스냅샷엔 Omni Flash 1위·Seedance 2.0 2위: https://benchmarklist.com/benchmarks/artificial_analysis_image_to_video/ **[3P]**).

---

## 2. 플랫폼별 노트

### 2.1 Google — Veo 3.1 / Gemini Omni Flash (Gemini 앱·Flow·API)
- **API 공식 가격** (https://ai.google.dev/gemini-api/docs/pricing, 오디오 포함, 무료 티어 없음) **[V, 공식가]**
  - Veo 3.1 Standard $0.40/s (720p·1080p), 4K $0.60 → 8초 **$3.20**
  - Veo 3.1 Fast $0.10 (720p) / $0.12 (1080p) → 8초 **$0.80–0.96**
  - Veo 3.1 Lite $0.05 (720p) / $0.08 (1080p) → 8초 **$0.40–0.64**; Lite는 4K·비디오입력·연장 불가, 1080p는 8초 고정 (https://benchlm.ai/md/media-pricing/veo.md **[3P]**)
  - Gemini Omni Flash(gemini-omni-1.1-flash): 영상 출력 $17.50/1M 토큰, 720p 1초=5,792토큰 ≈ **$0.10/s** → 8초 ≈ $0.80 **[V]**
- **구독(사용자 보유 Gemini Pro)**:
  - Gemini 앱 Veo 3.1 영상은 8초, Pro/Ultra 필요, 한도 존재 (https://support.google.com/gemini/answer/16126339 **[V]**)
  - 2026-05-17부터 Gemini 앱은 "5시간마다 갱신 + 주간 한도"의 연산량 기반 한도로 변경 (https://support.google.com/gemini/answer/17004136 **[V]**)
  - Omni 10초 영상 1개가 한도의 ~22% 소모, 실패한 1건이 5시간 한도를 다 썼다는 사용자 보고 (https://mezha.ua/en/news/koristuvach-gemini-vicherpav-5-godinniy-limit-pislya-odnogo-zapitu-311650/ **[I, 일화]**)
  - Flow: AI Pro 월 1,000 크레딧(Lite 약 100개 / Quality 약 10개) 추정, 무료계정 하루 50 크레딧(유료 가입 시 대체됨) (https://www.atlascloud.ai/blog/guides/veo-3.1-ai-video-generator-free-or-paid , https://aivideosensei.com/guides/google-veo-access-and-free-tier **[3P]**)
- **Omni Flash 기능**: 2026-05 I/O 출시, 대화형 편집, 최대 10초 + 1.1(2026-08-27)에서 10초 단위 연장 최대 40초, **첫·끝 프레임 고정**(루프·전환), **3초 영상 참조로 캐릭터 유지**, 360p 초안 (https://mezha.ua/en/news/gemini-omni-1-1-flash-upd-314609/ , https://www.etvbharat.com/en/technology/google-gemini-omni-1-dot-1-flash-google-flow-enn26082900548 **[V 보도]**)
- 품질: AA I2V에서 Omni Flash 1.1은 공동 1위권, Veo 3.1은 13위·Fast 17위 **[I]**. Veo 3.1은 대사·립싱크 용도로 추천 (https://pixo.video/blog/seedance-vs-veo-vs-kling **[3P]**), 극단적 표정 변화에도 얼굴 유지 5/5 (https://www.vidguru.ai/blog/seedance-2-vs-veo-3-1-comparison.html **[3P 단일 테스터]**), 움직임은 적은 편 (https://vidlux.ai/blog/veo-vs-kling-vs-seedance **[3P]**).
- 동작 전이(참조 영상→캐릭터): Omni의 3초 영상 참조는 "캐릭터 일관성" 용도로 보도됨, 동작 전이 기능으로 확인된 자료 없음 [추정: 미확인].
- 한국어 모음 발화: Veo/Omni 네이티브 오디오의 한국어 정확도는 확인 못함 [미확인].

### 2.2 Kling (Kuaishou) — 3.0 / Omni / Motion Control / Elements / 4.0
- **구독** (https://kling.ai/blog/kling-video-3-0-credit-cost-guide, 2026-07-28 **[V]**): Standard $10(첫 달 $6.99) 660cr, Pro $37 3,000cr, Premier $92 8,000cr, Ultra $180 26,000cr. 100cr당 $1.33(Std)~$0.62(Ultra). 무료(Basic)는 **상업 이용 불가**.
- 크레딧 소모: 3.0 1080p 무음 8cr/s, 720p 6cr/s, 1080p+오디오 5초 60cr, 4K 30cr/s **[V]**. Motion Control Std 9cr/s, Pro 12cr/s (https://www.aiarty.com/ai-video-generator/kling-ai-pricing.htm **[3P]**).
  - [계산] Pro 플랜($1.09/100cr) 기준 8초: 1080p 무음 64cr ≈ **$0.70**, Motion Control Pro 96cr ≈ **$1.05**, Std 72cr ≈ **$0.78**.
- API: fal Kling v3 Pro I2V **$0.14/s → 8초 $1.12** (https://fal.ai/pricing **[3P 공식 재판매가]**). AA 기준 1080p 오디오 $20.16/분 ≈ $2.69/8초 **[I]**.
- 무료: 로그인 시 일 66cr(24시간 만료)이라는 자료와 월 66cr이라는 자료가 충돌 (https://www.eesel.ai/en/blog/kling-ai-pricing **[3P]**). Kling은 소유권이 아닌 사용권 부여 (https://www.layer3labs.io/guides/best-ai-video-generators **[3P]**).
- **Motion Control**: 참조 영상 + 캐릭터 이미지 → 동작 전이. 공식 페이지 "사람·애니·3D 캐릭터 지원" (https://kling.ai/feature/ko/ai-motion-control **[V]**). 참조 인물과 캐릭터는 닮을 필요 없고 체형 비율·프레이밍만 비슷하면 됨 (https://www.atlascloud.ai/blog/guides/kling-ai-motion-control **[3P]**).
  - 실패 양상: **얼굴 흔들림이 가장 많이 보고됨**, 큰 고개 회전 시 얼굴이 참조 인물 쪽으로 끌려감; 3.0 웹UI에서 여러 각도 이미지(Element Binding)로 완화, API는 캐릭터 이미지 1장만 (같은 출처, r/generativeAI 2차 인용 **[I 2차]**). 3.0은 발이 덜 미끄러진다는 사용자 소감 (r/klingO1 2차 인용 **[I 일화]**). 참조 영상 길이 권장 2–5초 vs 최대 30초 등 상충.
- **Elements**: 여러 이미지/참조 영상으로 재사용 캐릭터 구성, 애니 스토리텔링 최고로 추천 (https://www.elser.ai/blog/kling-vs-seedance-vs-veo-for-anime-videos-which-ai-model-wins-in-2026 **[3P]**), Kling 3.0 Pro를 애니·스타일 최고로 꼽음 (https://tryinfer.com/best/ai-models-for-anime-video **[3P]**). 반면 15모델 캐릭터 비교에선 Kling 3.0 8위 (https://note.com/shirono_aru/n/n1f9fa1cd2838 **[I 단일 테스터]**).
- 동작·물리: 블라인드 프롬프트 테스트에서 Kling 3.0이 motion physics 1위 (https://clipia.ai/en/blog/seedance-2-vs-kling-3-vs-veo-3 **[3P]**).
- **Kling 4.0**: 2026-09-30 발표, 9-28부터 제한 공개, 10월 정식 예정, 공식가 없음, 립싱크 정확도 개선 주장 (https://kling.ai/blog/kling40-kling-visual-realism-creative-control-introducing-storytelling **[V]**, https://www.gradually.ai/en/ai-models/kling-4-0/ **[3P]**).

### 2.3 Runway — Gen-4.5 / Act-Two / Aleph 2.0
- 플랜: Free 125cr(1회), Standard $15(625cr), Pro $35(2,250cr), Max $95(9,500cr, Unlimited는 2026-06-01 판매 중단), 연간 할인; API 1cr=$0.01 (https://www.atlascloud.ai/blog/tips/runway-aleph , https://runway.com/pricing **[3P/V]**)
- Gen-4.5 12cr/s → 8초 **$0.96** (API) (https://creatify.ai/blog/runway-pricing-(2026)-plans-credits-and-what-you-ll-actually-pay **[3P]**). AA 순위표에는 없음.
- **Act-Two**: 5cr/s, 최소 3초 → 8초 **$0.40** **[3P]**. 운전 영상(내가 연기한 영상)의 표정·입·타이밍을 캐릭터 이미지/영상에 전이.
  - 공식: 다양한 각도·**비인간 캐릭터**·스타일에서 잘 동작 (https://help.runwayml.com/hc/en-us/articles/42311337895827-Performance-Capture-with-Act-Two **[V]**)
  - 조건: 눈과 입이 분명해야 함, 말할 때 보일 송곳니 등은 입력 이미지에 이미 보여야 함, 운전 영상은 1인·컷 없음·**허리 위 프레이밍**, 옆얼굴/전신 불가, 혀 내밀기 등 일부 표정 미전이, 영상 참조 시 제스처 제어 불가, 해상도 저하·결과 예측 어려움 (https://fuser.studio/articles/runway-act-two-guide , https://filmora.wondershare.com/trending-topic/runway-act-two-review.html **[3P]**)
- Aleph 2.0: 기존 영상 편집, 28cr/s(API $0.28/s) → 8초 $2.24 **[3P]**.

### 2.4 ByteDance — Seedance 2.0 / 2.5, Dreamina, CapCut, OmniHuman
- Seedance 2.5: Dreamina 전 세계 출시 2026-07-31, 30초 I2V(720p), 180초 베타 (https://tirto.id/dreamina-launches-seedance-25-the-tool-of-ai-video-generation-that-reduces-clip-stitching-visual-drift-and-rework-hAFX **[V 보도]**)
- 가격: Dreamina 연간 플랜 환산 **$0.097/s → 8초 ≈ $0.78**, 2.0 프로모 $0.046/s (https://dreamina.capcut.com/seedance/seedance-price **[V]**); Volcano Engine API $0.09–0.21/s (https://www.atlascloud.ai/blog/guides/seedance-2.5-pricing-guide **[3P]**); AA 측정 $24.60/분(≈$3.28/8초) **[I]**; fal Seedance 2.0 토큰 과금 $0.014/1k토큰 (https://fal.ai/pricing).
- **참조 영상 동작**: 참조 영상이 동작·카메라 경로·페이싱·립싱크 타이밍, 참조 이미지가 정체성 담당 (https://runware.ai/docs/models/bytedance-seedance-2-5/guides/motion-control **[3P 문서]**); 그린스크린/흰 모델 참조로 캐릭터 움직임 지정 (https://pixverse.ai/en/blog/seedance-2-5-ai-video-generator-review **[3P]**); 초 단위 타임스탬프 명령 (runtimewire **[보도]**).
- 품질: 15모델 I2V 캐릭터 비교에서 **Seedance 2.5 1위, 얼굴 가장 안정** (https://note.com/shirono_aru/n/n1f9fa1cd2838 **[I 단일 테스터, 2026-09]**). 캐릭터 안정성 9/10 (Kling 8, Veo 7) (https://www.elser.ai/blog/best-ai-video-model-character-consistency-2026 **[3P]**). AA 4위 **[I]**.
- 실패/위험: **알아볼 수 있는 얼굴·저작권 캐릭터 필터링** (https://morphed.app/blog/ai-video-generator-for-anime **[3P]**); 1.5 Pro 시절 복잡한 동작·다인 상호작용 아티팩트 (https://www.atlascloud.ai/blog/guides/seedance-vs-kling-vs-sora-vs-veo **[3P]**).
- OmniHuman 1.5 (오디오 구동 아바타): API $0.12–0.25/s → 8초 $0.96–2.00, 셀프서브 구독 없음 (https://www.byteplus.com/en/product/OmniHuman **[V]**, https://www.heygen.com/blog/ai-video-generator-pricing **[3P 경쟁사]**). 애니·2D 최적화 주장은 리셀러 주장 **[3P]**.

### 2.5 MiniMax — H3 (Hailuo 3.0)
- 2026-07-31 출시, 최대 15초, 2K+스테레오 오디오, 텍스트·이미지·영상·오디오 참조 (https://rits.shanghai.nyu.edu/ai/minimax-releases-h3-2k-video-with-native-audio-open-weights-promised/ **[보도]**)
- 가격: fal H3 Max I2V **$0.05/s (8초 $0.40)**, H3 Max Turbo $0.025/s (8초 $0.20) (https://fal.ai/pricing); AA $5.40/분 → 8초 $0.72 **[I]**; OpenRouter $0.13/s~ **[3P]**; Hailuo 앱 $7.99–199.99/월(H3 이전 스냅샷) (https://www.aiarty.com/ai-video-generator/hailuo-ai-pricing.htm **[3P]**).
- 품질: AA I2V **1위**(Elo 1131) **[I]**.
- **오픈가중치 함정**: 2026-08 HF에 768p 체크포인트 2종(FL2VA, Ref2VA) 공개, 2K 업스케일러·프롬프트 단계는 비공개, 최소 42.5GB(오프로딩 시 12GB 카드) — 그러나 **라이선스가 EU·UK·한국·미국을 적용 지역에서 제외** (https://rits.shanghai.nyu.edu/ai/minimax-ships-h3-weights-with-the-us-and-eu-excluded/ , https://aiweekly.co/fr/alerts/minimax-ouvre-les-poids-de-h3-mais-exclut-us-ue-uk-et-core **[보도]**). → 한국 스튜디오는 **API만** 사용.

### 2.6 Vidu (Shengshu) — Q3 / Q4 Preview
- Q4 Preview(2026-10): $0.045/s(540p) ~ $0.39/s(4K), 11-30까지 I2V·참조영상 30% 할인, 참조 이미지 최대 15장, "생생한 연기"를 내세움 (https://technologymagazine.com/globenewswire/3376813 **[V]**). → 8초 540p ≈ **$0.36**, AA 1080p $5.04/분 → ≈$0.67 **[I]**.
- AA I2V 2위 **[I]**. 애니 강점 주장은 Vidu 자사 페이지 (https://www.vidu.com/vidu-q3-vs-seedance-2-0-vs-kling-3-0 **[V]**); 광고형 테스트에서 "Vidu가 캐릭터를 더 단단히 고정" (https://www.atlascloud.ai/blog/tips/kling-vs-vidu-vs-seedance-which-video-model-is-best-for-social-media-ad-creative **[3P]**); 반면 15모델 비교에서 Q3 Pro 10–11위 **[I 단일]**.

### 2.7 Alibaba — Wan 3.0 / Wan 2.x / Wan-Animate
- Wan 3.0: 2026-08-06 공개 베타, **클로즈드(API 전용)**, 최대 30초 (https://morphic.com/kr/resources/models/wan-3-0 , https://www.atlascloud.ai/blog/tips/is-wan-3.0-open-source **[3P]**). AA 5위, $12/분 → 8초 ≈$1.60 **[I]**. 오픈 라인은 Wan 2.2가 마지막.
- **Wan-Animate-2** (2026-08-07, **Apache 2.0**): 포즈 추출 없이 운전 영상 latent를 DiT에 직접 입력, 텍스트 시점 LoRA, 다인·다양한 체형, Lite판 400×720 24fps 실시간, INT8/BF16, ComfyUI 노드. 블라인드 사용자 연구에서 Dreamina·Kling MotionControl과 동급 이상이라는 주장 (https://www.opensourceforu.com/2026/08/alibaba-open-sources-wan-animate-2-real-time-ai-character-animation/ **[V 보도]**). VRAM·모델 크기 미공개. 비인간 언급 없음.
- Wan2.2-Animate-14B(2025-09): 공식 80GB급; 커뮤니티 GGUF Q2_K로 6GB, 480p 클립 10–15분(RTX 4050) (https://www.patreon.com/TheLocalLab/posts/wan-2-2-animate-139973446 **[3P 유료 패키지, 일화]**).

### 2.8 Tencent — HunyuanVideo 1.5 / Avatar
- HunyuanVideo 1.5(8.3B, 2025-11) 최신 공식, "HunyuanVideo 2"는 미확인 (https://github.com/Tencent-Hunyuan/HunyuanVideo **[V]**). 8GB 불가(로드에 ~14GB) (https://localaimaster.com/blog/local-ai-video-generation **[3P]**).
- HunyuanVideo-Avatar(2025-05): 사진+오디오→말/노래, 감정 제어·다인·다양한 스타일 (https://huggingface.co/tencent/HunyuanVideo-Avatar **[V]**); 감정 제어 주장은 과장이라는 자동 리뷰 (https://pith.science/paper/2505.20156 **[I 약함]**).

### 2.9 기타 상용
- **PixVerse V6**: 720p 9cr/s, 1080p 18cr/s(오디오 23); 리셀러 720p $0.045/s → 8초 ≈$0.36, AA $6.90/분 → ≈$0.92 (https://www.atlascloud.ai/blog/tips/pixverse-ai-pricing **[3P]**). AA 16위 **[I]**. 애니 생성기 순위에서 자사 1위(자사 블로그, 신뢰 낮음) (https://pixverse.ai/en/blog/best-ai-anime-video-generators-2026 **[V]**).
- **Grok Imagine Video 1.5 (xAI)**: 480p $0.08, 720p $0.14, 1080p $0.25 /s, 참조 이미지 1–7장($0.01/장) (https://docs.x.ai/developers/models/grok-imagine-video-1.5 **[V]**) → 8초 720p **$1.12**. AA 9위 **[I]**.
- **Luma Ray3.14**: 720p 20cr/s, 1080p 80cr/s; Plus $30/10,000cr → 8초 720p ≈**$0.48**; API ≈$0.06/s; Ray3.2 가격 상충 (https://www.therundown.ai/tools/ray-3-14 , https://wavespeed.ai/blog/cost-and-billing/luma-ai-pricing/ **[3P]**). 독립 순위 자료 없음.
- **Pika 2.5 / Pikaformance**: 5초 480p 12cr / 720p 20cr / 1080p 40cr; Pikaformance(이미지+오디오 립싱크) 3cr/오디오초, 720p 상한, 유료 최대 30초; 무료 80cr/월·상업 불가; 크레딧 단가는 사이트마다 상충 (https://www.therundown.ai/tools/pika **[3P]**).
- **Midjourney Video**: 이미지→5초 클립, SD 480p 4개 배치 8분 / HD 720p 26분 GPU시간; Standard 기준 ≈$0.033/분 → 클립당 SD ≈$0.07, HD ≈$0.22; 구독 $10–120; **API 없음** (https://www.eesel.ai/blog/midjourney-pricing **[3P]**).
- **Adobe Firefly Video**: 540p 20cr/s, 720p 50, 1080p 100; Standard $9.99/2,000cr → 8초 720p ≈$2.00, 1080p ≈$4.00 (https://www.krea.ai/blog/is-adobe-firefly-free-what-it-is-and-how-it-compares-in-2026 **[3P 경쟁사]**). 상업적으로 안전한 학습 데이터가 장점이나 비용·품질 열세 [추정].
- **LTX-2.5 (Lightricks)**: 2026-08-11, 22B 오픈가중치(dev + distilled), ARR $10M 미만 무료 상업 이용 (https://venturebeat.com/technology/ltx-2-5-can-generate-a-10-second-ai-video-from-an-image-in-just-6-8-seconds-on-nvidia-superchips-and-its-open-weights **[보도]**). VRAM: 공식 32GB+/80GB 권장, 양자화 16GB, 8GB int8은 미검증 (https://ltx.io/blog/deploying-ltx-on-premise **[V]**, https://ltx23.app/blog/ltx-2-5-system-requirements **[3P]**). AA LTX-2.5 Fast 21위, $7.80/분 **[I]**.
- **Meta Vibes / Movie Gen**: Vibes는 Meta AI 내 AI 영상 피드(2025-09), 2026-02 브라질·멕시코 단독 앱 테스트, Movie Gen급 생성기의 일반 공개는 미확정 (https://techcrunch.com/?p=3065702 , https://www.nemovideo.com/blog/meta-ai-video-generator **[보도/3P]**). → 제작용 부적합.
- **OpenAI**: Sora 앱 2026-04-26 종료, API 2026-09-24 종료 예정, ChatGPT 내 영상 기능도 정리된다는 보도 다수 (https://en.wikipedia.org/wiki/Sora_(text-to-video_model) **[3P]**). → ChatGPT 구독은 영상에 쓸 수 없음 [추정, 반대 주장 1건 존재].
- **HeyGen Avatar IV**: API $0.05/s → 8초 $0.40, 스타일·2D·3D·**비인간 얼굴** 지원 (HeyGen 자사 블로그 https://www.heygen.com/blog/ai-video-generator-pricing **[V]**).
- **Hedra Character-3**: 540p 2.5¢, 720p 5¢, 1080p 6.25¢ /s → 8초 720p $0.40; 이미지 한 장 말/노래 캐릭터로 리뷰어 호평, Trustpilot·환불 분쟁 보고 (https://magichour.ai/blog/guide-to-hedra-ai , https://www.elser.ai/blog/best-ai-video-generators-with-lip-sync-in-2026-7-tools-for-talking-and-singing-characters **[3P]**).
- Synthesia / D-ID: 실사 프레젠터 아바타 중심이라 이번 용도(스타일 캐릭터 참고 영상)엔 부적합 [추정, 이번 조사에서 가격 미검증].

### 2.10 애그리게이터
- **fal.ai**: Kling v3 Pro I2V $0.14/s, Kling 2.5 Turbo Pro $0.07/s, MiniMax H3 Max $0.05/s, Turbo $0.025/s, Seedance 2.0 토큰 과금 (https://fal.ai/pricing **[3P 공식 재판매가]**). Grok 1.5 I2V도 제공 (https://fal.ai/models/xai/grok-imagine-video/v1.5/image-to-video).
- **Freepik**(2026-04 Magnific로 리브랜드 주장 1건): Premium+ 등에서 일부 이미지 모델만 무제한, **영상은 항상 크레딧** (https://www.eesel.ai/blog/freepik-ai-pricing **[3P]**).
- **Krea**: 무료 100유닛/일, Basic $9(5,000), Pro $35(20,000, 전 영상모델) — 상충 자료 있음; **OpenArt**: $14/4,000cr, 무료는 워터마크, 상업은 $29~; **Leonardo**: 무료 150토큰/일, Kling/Veo/Seedance 제공 증거 없음 (https://higgsfield.ai/blog/best-affordable-ai-video-generators **[3P 경쟁사]**, https://imaginode.ai/en/alternatives/openart **[3P]**).
- Replicate: 이번 조사에서 가격 미확인.
- 결론[추정]: 여러 모델을 짧게 비교 테스트할 땐 fal(종량제)이 가장 투명; 구독형 애그리게이터는 크레딧 환산이 불투명.

---

## 3. 얼굴 표정·모음 입모양 (a)

### 3.1 거의 무료 경로: 표정 재연(reenactment)
- **LivePortrait** (Kuaishou/KlingTeam, 오픈): 운전 영상(내가 "아 에 이 오 우" + 표정 연기)으로 정지 캐릭터 이미지의 표정·입을 구동. stitching + 눈/입 리타게팅 모듈(눈 뜸·입 벌림 스칼라), 동물 데이터 파인튜닝으로 고양이·개·판다 구동 (https://liveportrait.github.io/ , https://arxiv.org/html/2407.03168v2 **[V 논문]**). 만화·예술 이미지 입력 가능, 정면 얼굴 권장 (https://gaga.art/blog/liveportrait/ **[3P]**). RTX 3060에서 피크 VRAM ≈4.5GB (https://sadtalker.ai/sadtalker-vs-liveportrait **[3P 단일]**), 3060 12GB에서 입력 1초당 4–5초 렌더 (https://huggingface.co/spaces/KlingTeam/LivePortrait/discussions/22 **[I 사용자]**). → **RTX 2070 8GB에서 현실적** [추정].
  - **FasterLivePortrait**: TensorRT 가속, Python 3.10·CUDA 12.4, GPU별 엔진 빌드 (https://note.com/tori29umai/n/n7f56e9a170c5 **[3P]**).
  - ComfyUI 노드(LivePortraitKJ)에 눈·입 배율 리타게팅 (https://www.runcomfy.com/comfyui-nodes/ComfyUI-LivePortraitKJ/LivePortraitProcess **[3P]**). FaceFusion 3.0이 LivePortrait를 expression_restorer로 내장.
  - PersonaLive(CVPR 2026): 실시간 스트리밍 포트레이트, 12GB 필요 → 8GB 불가 (https://github.com/GVCLab/PersonaLive **[V]**).
  - 실패 양상[추정+일반 보고]: 큰 고개 회전·옆얼굴 약함, 애니 큰 눈/단순 입 구조에서 키포인트 오검출 가능, 몸·머리카락 움직임 거의 없음. 애니 전용 벤치마크는 못 찾음.
- **유료 연기 전이**: Runway Act-Two(8초 $0.40, 비인간 OK, 허리 위) — 위 2.3 참조.

### 3.2 오디오 구동 립싱크 (모음 발음 → 입모양)
- Hedra Character-3, HeyGen Avatar IV, OmniHuman 1.5, Pikaformance, HunyuanVideo-Avatar(오픈, 고VRAM). 모두 "한 장 이미지 + 음성". 스타일/비인간 얼굴은 "눈·입이 분명해야" 성공 (https://zoice.com/blog/best-ai-drawing-lip-sync-generator/ **[3P]**).
- 한국어 모음 정확도 독립 검증 자료 없음 [미확인] → 직접 녹음한 "아 에 이 오 우" 음성으로 1회씩 테스트 권장.

### 3.3 이미지→영상 범용 모델로 표정
- Gemini Omni Flash / Veo 3.1 (구독 내), Kling 3.0(+Elements, 립싱크), Seedance 2.5, MiniMax H3, Vidu Q4. 프롬프트만으로 "정확히 '오' 모양을 2초 유지" 같은 통제는 약함 [추정]. 정체성 유지는 Seedance 2.5 > Kling/Veo (단일 테스터) **[I]**.

### 3.4 파이프라인 메모 (ARKit 52 연결)
- 생성된 참고 영상(또는 운전용 사람 영상)에서 MediaPipe Face Landmarker로 **52개 블렌드셰이프 계수**를 바로 뽑을 수 있음 (https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker **[V, 기존 지식으로 인용·이번 세션 미재확인]**). 사람 얼굴에선 잘 되나 애니/카툰 얼굴에선 검출 실패 가능 [추정]. → 얼굴은 "사람 운전 영상 → 블렌드셰이프 곡선" 직행이 AI 영상보다 싸고 정확할 수 있음.

---

## 4. 몸 동작 (b)
- **참조 영상 동작 전이가 핵심**: Kling 3.0 Motion Control(애니·3D 지원 명시), Seedance 2.5 참조 영상(흰 모델/그린스크린 참조, 타임스탬프), Wan-Animate-2(오픈), Runway Act-Two(상반신만). 참조 영상은 직접 촬영하거나 Mixamo 등 기존 모션을 렌더한 영상 사용 가능 [추정].
- 텍스트/이미지만으로 걷기·달리기: AA 상위(MiniMax H3, Vidu Q4, Omni Flash, Seedance) 중 저가 모델로 반복 생성. Omni 1.1 첫·끝 프레임 고정으로 루프 사이클 만들기 가능성 [추정].
- 알려진 실패: 발 미끄러짐(Kling 2.6에서 보고, 3.0 개선 소감) **[I 일화]**, 복잡한 동작·다인 상호작용 아티팩트(Seedance 1.5 Pro) **[3P]**, 카메라가 고정되지 않고 따라 움직임(일반적, 모델별 고정카메라 옵션은 이번 조사에서 체계적 확인 못함) [추정], 참조 인물 얼굴로의 정체성 드리프트(Kling MC) **[I 2차]**.

## 5. 몬스터·크리처 (c)
- **Veo/Kling/Seedance 간 몬스터·사족보행 독립 비교는 찾지 못함** (검색 결과는 사람·물리 중심 비교뿐) (https://www.atlascloud.ai/blog/guides/seedance-vs-kling-vs-sora-vs-veo **[3P]**).
- 동물 모션 데이터는 본질적으로 부족(포획이 비현실적) → 일반 영상 모델이 비인간 보행에 약할 가능성 (https://arxiv.org/html/2609.01823v1 **[I 논문, 영상모델 직접 테스트 아님]**).
- 쓸 만한 경로 [추정]:
  - 사족보행: Kling Motion Control에 **실제 동물 영상**(말·개·고양이)을 참조로 + 몬스터 이미지 (체형 비율이 비슷해야 함, 위 Kling 조건).
  - 다족·날개·슬라임: 참조 동작이 없으므로 순수 I2V를 저가 모델(MiniMax H3 Turbo $0.20/8초, Vidu Q4 540p $0.36)로 여러 번 뽑아 고르기. 다리 개수 변화·관절 녹아내림 체크.
  - 크리처 얼굴(으르렁·포효): Runway Act-Two(눈·입 분명, 이빨은 입력에 보여야 함), LivePortrait 동물 모드.
- Maya MotionMaker는 말·늑대형 개 모션 생성(영상 아님, 3D 툴) — 참고 (https://www.sehatdiri.com/2026/08/motionmaker-ai-biped-quadruped-maya.html **[3P]**).

## 6. 로컬/무료 (RTX 2070 8GB, Turing)
- Turing은 bf16 미지원 → 최신 bf16/fp8 모델은 fp16 경로 필요·느림 [추정].
- **LivePortrait / FasterLivePortrait**: 가능성 높음(피크 ~4.5GB) — 얼굴용 1순위.
- **FramePack** (HunyuanVideo 기반 13B, 6GB): 공식 지원은 RTX 30/40/50, **20xx 미검증**; 초기 설정 미흡 시 5초에 5시간, 가속 설치 후 개선 (https://github.com/lllyasviel/FramePack/issues/523 **[I 사용자]**).
- **Wan 2.2 TI2V-5B**: ComfyUI 문서 "8GB 네이티브 오프로딩으로 적합" vs 공식 24GB (https://computingforgeeks.com/run-wan-video-generation-locally/ **[3P]**); 양자화 Wan 2.2 I2V 8GB에서 5초 480p 181초 (벤더 블로그, https://blog.segmind.com/wan-comfyui-setup-gguf-workflow-tutorial/ **[3P]**).
- **Wan2.2-Animate GGUF Q2–Q4**: 6–8GB, 480p, 수십 분 [3P 일화]. **Wan-Animate-2 INT8**: VRAM 미공개.
- LTX-2.5(8GB int8 미검증), HunyuanVideo 1.5(8GB 불가), MiniMax H3 오픈(한국 라이선스 제외) → 사실상 불가.
- 무료 티어: Kling 일 66cr(상업 불가), Pika 80cr/월(상업 불가), Krea 100/일, Leonardo 150/일, Flow 무료계정 50/일(유료 가입 시 대체), Gemini Pro 구독 내 Veo/Omni(사용량 한도).

## 7. 주요 위험
1. **라이선스**: MiniMax H3 오픈가중치는 한국 제외; Kling·Pika 무료 출력 상업 불가; Kling은 사용권 부여; OpenArt 무료 워터마크.
2. **가격 변동·자료 신뢰도**: 대부분 제3자 자료, 같은 모델도 출처별 2–10배 차이. Kling 4.0·Wan 3.0·Vidu Q4는 프리뷰/베타.
3. **정체성 드리프트**: 고개 회전 시(Kling MC), 참조 인물로 끌림; Seedance는 실존 얼굴·저작권 캐릭터 필터.
4. **Gemini 구독 한도**: 연산량 기반, 영상 1개가 큰 비중, 실패 생성도 소모.
5. **몬스터 품질 근거 없음**: 독립 테스트 부재 → 소규모 직접 테스트 필수.
6. **AA 순위 ≠ 우리 용도**: 고정 카메라·정확한 입모양·루프·해부학은 따로 검증 필요.
7. 참고 영상은 2D → 리그 적용엔 영상→모캡/블렌드셰이프 추출 단계가 별도로 필요(이번 범위 밖).

## 8. 추천 테스트 순서 [추정]
1. 얼굴: 직접 촬영 "아 에 이 오 우 + 기본 감정" 10초 → LivePortrait 로컬(4 스타일 이미지) → 같은 운전 영상으로 Act-Two 1회씩($0.40×4) 비교.
2. 몸: 같은 참조 동작(걷기·공격) → Kling 3.0 Motion Control vs Seedance 2.5 참조영상 vs Wan-Animate-2(클라우드) 각 1회.
3. 몬스터: MiniMax H3 Turbo/Vidu Q4로 I2V 3–5회 + Kling MC에 실제 동물 영상 1회 + Omni(구독) 첫·끝 프레임 루프 1회.
