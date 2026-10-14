# 커뮤니티 반응 조사 (영어권 + 중국어권) — 표정·몸동작 참고 영상용 AI 도구

- 조사일: 2026-10-14 (KST)
- 범위: 웹 검색·페이지 읽기 30회. 가입·로그인·다운로드·게시는 하지 않음.
- Reddit은 도구에서 막혀 있어 직접 보지 않았다. 다른 글이 Reddit을 인용한 경우에만 [snippet]으로 표시했다.
- 태그: [HN] Hacker News, [X] X/Twitter, [YouTube], [CN] 중국어권, [ProductHunt], [Trustpilot], [포럼] 포럼·블로그·리셀러 글
- 주의: 검색에 걸린 글의 상당수는 해당 모델을 되파는 리셀러(Atlas Cloud, Tryonr, invideo, Pollo 등)나 경쟁사 블로그다. 이런 글은 [포럼]으로 묶되 "업체 글"이라고 따로 적었다. 실제 사용자 목소리는 HN 댓글, Trustpilot, Reallusion 포럼, bilibili 제목 정도였다.
- 못 찾은 것: YouTube 리뷰 영상 페이지, 공개 Discord 요약, 知乎·小红书·V2EX의 실제 사용자 글, BlenderArtists·Polycount 스레드는 이번 검색에 걸리지 않았다. 해당 항목은 "근거 없음"으로 남겼다.

---

## 1. 한눈에 보기

| 도구 | 전체 분위기 | 가장 많이 나온 칭찬 | 가장 많이 나온 불만 | 본 글 수(대략) |
|---|---|---|---|---|
| Seedance 2.0 / 2.0 Fast / 2.5 (Dreamina·即梦) | 긍정 쪽 혼합 | 얼굴·사실감, 30초 원테이크, 동급 최고라는 평 | 해외 접근, 검열, 저작권 분쟁, 긴 샷에서 누적 오류·뻣뻣한 눈 | 약 35 |
| MiniMax H3 / Hailuo 2.3 | 혼합 | 오픈 웨이트로 집에서 생성, 미세 표정(2.3) | 밋밋한 화면, 1080p 품질, 라이선스, 결제 후 영상 미생성 | 약 30 |
| Kling 3.0 / Omni 3 / Motion Control 2.6·3.0 / Lipsync | 품질은 긍정, 결제는 부정 | 카메라 움직임, 3.0의 무게감 있는 동작, 5개 언어 립싱크 | 모션 컨트롤 얼굴 드리프트, 환불 거부, 크레딧 과다 차감 | 약 25 |
| Google Veo 3.1 (Lite/Fast) / Gemini Omni Flash | 중립~긍정(표본 적음) | 프롬프트 준수율, 글자 렌더링, 3D 애니 스타일 | 참조 720p 제한·오디오 싱크 차단, 풍경 약함 | 약 8 |
| Vidu Q4 | 근거 부족(Q4 전용 글 없음) | 애니 스타일, 다중 참조 일관성 | 드리프트가 "해결되진 않음" | 약 3 |
| Wan 3.0 | 근거 부족 | 오픈 계열 기대 | 오픈 웨이트 여부 불확실, 얼굴 깜빡임 | 약 3 |
| Higgsfield | 갈림(별 5 다수 + 별 1 꼬리) | 여러 모델을 한곳에서 | Unlimited 모드 크레딧 차감, 해지 후 청구 | 약 10 |
| Uthana | 근거 부족(커뮤니티 글 없음) | 프롬프트당 후보 3개, FBX/GLB, Blender 플러그인 | 독립 테스트 없음 | 약 1~2 |
| QuickMagic | 긍정(표본 적음) | 가격 대비 몸 모캡, 발 미끄러짐 적음 | 약간의 떨림, 붙어 있는 두 사람 혼동 | 약 4 |
| Rokoko Vision | 중립(표본 적음) | 무료 단일 카메라 | 빠른 동작 떨림, 발 미끄러짐 | 약 2 |
| Tripo 애니메이션/리그 | 출력은 긍정, 결제·지원은 부정 | Unity로 바로 가져다 씀, 4족 등 리그 종류 | 4족 다리가 일자로 펴짐, 크레딧 리셋, 느린 지원 | 약 6 |
| Meshy Animate | 혼합 | 리깅이 쉽고 빠름 | 리깅이 기본 수준, 얼굴 리그 없음, 결제 불만 | 약 4 |

---

## 2. 얼굴·영상 모델

### 2.1 Seedance 2.0 / 2.0 Fast / 2.5 (ByteDance, Dreamina·即梦·剪映)

**전체: 긍정 쪽 혼합.** 품질 칭찬은 가장 많고, 접근성·검열·저작권 문제가 따라다닌다.

HN에서 가장 큰 스레드는 "Seedance 2.5" (442점, 댓글 255개, 2026-08-01).
- 출처: [HN] https://news.ycombinator.com/item?id=49138302 (댓글 원문 API: https://hn.algolia.com/api/v1/items/49138302)
- 보이는 상위 댓글 기준으로 긍정 약 10, 부정 약 5, 중립·혼합 8~10. 부정 댓글은 주로 "AI 영상 자체가 싫다"는 쪽이었다.

**얼굴·표정**
- 칭찬: nbardy는 "The faces look amazing"이라고 했고, 정체성 유지는 후학습으로 쉽게 될 거라고 봤다. [HN] https://news.ycombinator.com/item?id=49145692
- 불만: efficax는 눈에 띄는 오류는 적지만 눈과 얼굴이 이상하게 움직여 "뻣뻣하고 부자연스럽다"고 했다. [HN] https://news.ycombinator.com/item?id=49146263

**몸동작·일관성**
- orbital-decay: 데모에 빠른 컷 편집이 많고, 덜하긴 해도 여전히 "애니메이션처럼 보이는" 부자연스러운 동작이 있다. [HN] https://news.ycombinator.com/item?id=49140033
- pavlov: 액션 장면은 결함을 숨기지만, 길고 안정된 샷에서는 프레임마다 쌓이는 환각이 드러난다. [HN] https://news.ycombinator.com/item?id=49142898
- globular-toast: 선물이 상자에 안 맞는 등 연속성 오류가 많다고 했다. [HN] https://news.ycombinator.com/item?id=49142041
- zmmmmm: 30초~1분 정도의 일관성은 이제 가능하다고 봤다(광고용으로 충분). [HN] https://news.ycombinator.com/item?id=49139610

**애니·만화 스타일**
- konart: AI 숏드라마에 퍼진 "신카이 마코토풍" 화면을 언급했다. 반응은 반반이었다. [HN] https://news.ycombinator.com/item?id=49142077
- bilibili 영상 페이지의 추천 제목에 "seedance2.0의 애니가 너무 강하다"는 제목과 "기본적인 인물 일관성도 못 지킨다"는 제목이 함께 있었다. 본문은 확인하지 못했고 제목만 봤다. [CN] https://www.bilibili.com/video/BV14WZLBNE8D/
- 업체 글(Atlas Cloud): 선화와 평면 채색에서 프레임 간 떨림(line-boil, color crawl)이 가장 잘 드러나고, 앱의 재압축이 평면 색 경계를 망가뜨린다고 했다. 한 번 생성의 상한은 15초다. [포럼] https://www.atlascloud.ai/blog/guides/seedance-2.0-animation-2d

**립싱크**
- 업체 글(Crepal): 짧고 또렷한 대사는 입 모양·턱·타이밍이 10번 중 7번 정도 자연스러웠고, 실패도 일정한 패턴으로 반복된다고 했다. [포럼] https://crepal.ai/blog/aivideo/blog-seedance-2-0-lip-sync-voiceover-fix/

**가격·접근·신뢰성**
- iamleppert: "Seedance 2 접근"을 내세운 사이트들이 사기였다며 정식 경로를 물었다. [HN] https://news.ycombinator.com/item?id=49139775
- thelucent: 공식 경로는 Dreamina이고, BytePlus API는 아직 2.5를 제공하지 않을 수 있다고 했다. [HN] https://news.ycombinator.com/item?id=49140084
- JimsonYang: 미국에는 아직 풀리지 않았다고 했다. [HN] https://news.ycombinator.com/item?id=49141046
- scamdrill: 30초 클립 한 개에 약 7달러로 추정했다. [HN] https://news.ycombinator.com/item?id=49139814
- "Tell HN: Seedance 2.5 API Pricing" 글도 따로 있었다. [HN] https://news.ycombinator.com/item?id=49170050
- 경쟁사·업체 리뷰들도 중국 밖 접근, 강한 검열, 진입 장벽을 흔한 불만으로 꼽았다. [포럼] https://pixverse.ai/en/blog/seedance-2-0-review-prompts-and-use-cases , https://wavespeed.ai/blog/zh-CN/posts/seedance-2-0-review-issues-and-alternatives/
- 중국 내 즉梦은 처음에 일부 그레이 테스트 사용자에게만 열렸다(bilibili 작가 칼럼, 2026-02). [CN] https://www.bilibili.com/opus/1166551484549038086

**저작권·사건 (참고 영상 용도에는 직접 영향 적음)**
- 할리우드 반발 기사 스레드: [HN] https://news.ycombinator.com/item?id=47022952
- Disney 경고장: [HN] https://news.ycombinator.com/item?id=47009132
- Reuters "저작권 분쟁으로 출시 중단": [HN] https://news.ycombinator.com/item?id=47381489
- "Seedance 데모는 과장됐다" 반박 글: [HN] https://news.ycombinator.com/item?id=47068708
- No Film School: 결과는 인상적이지만 생성형 영상 특유의 엉성함이 여전하다고 평가. [포럼] https://nofilmschool.com/seedance-2-0-ai-video-model

**X 게시물 (HN에 링크된 것만)**
- "SeeDance 2.5 Is Stunning" [X] https://twitter.com/Long4AI/status/2069262125776920582 (HN: https://news.ycombinator.com/item?id=48640441)
- "30초 영상을 한 번에 생성" [X] https://twitter.com/xiaohu/status/2069236441964818508 (HN: https://news.ycombinator.com/item?id=48639900)

**재시도율:** 직접 수치는 없음. Crepal 글의 "10번 중 7번 자연스러움"이 립싱크 쪽 유일한 수치.
**괴물·비인간:** 근거 없음.

---

### 2.2 MiniMax H3 (Hailuo 3.0) / Hailuo 2.3

**전체: 혼합.** H3는 오픈 웨이트라 HN에서 반응이 컸다. 품질 평가는 갈렸다.

HN 큰 스레드 두 개:
- "MiniMax H3 Day-0 Support in ComfyUI" (334점, 댓글 94개, 2026-08-03) [HN] https://news.ycombinator.com/item?id=49155629
- "H3-metal – Apple Silicon용 H3 추론" (440점, 댓글 98개, 2026-08-11) [HN] https://news.ycombinator.com/item?id=49252179 (댓글은 읽지 않음)
- ComfyUI 스레드에서 의미 있는 댓글 약 30개 중 긍정 약 10, 부정 약 12, 나머지 혼합.

**얼굴·표정·화면**
- fodkodrasz: 기술은 인상적이지만 화면이 "고통스러울 정도로 밋밋하고 흔하다". [HN] https://news.ycombinator.com/item?id=49156052
- _diyar: 얼굴 일관성은 참조 이미지에 달려 있을 거라고 추측. [HN] https://news.ycombinator.com/item?id=49156469
- 얼굴·립싱크·애니 스타일을 직접 다룬 댓글은 거의 없었다.

**몸동작**
- jareklupinski: 입김이 호흡과 맞지 않았다. [HN] https://news.ycombinator.com/item?id=49159645
- fwip: 프롬프트로 지시한 휩팬 전환을 무시하고 그냥 컷으로 넘어갔다. [HN] https://news.ycombinator.com/item?id=49156863

**괴물·비인간**
- sheesdev: 쥐 렌더링이 "놀랍도록 좋다"고 했다(음료 장면은 너무 매끈). [HN] https://news.ycombinator.com/item?id=49155964

**로컬 실행·속도 (참고 영상을 대량으로 뽑을 때 의미 있음)**
- vblanco: 4070 Ti Super에서 480p 10초에 약 10분, "결과가 대단하다". [HN] https://news.ycombinator.com/item?id=49155969
- Maxious: 5080에서 같은 클립 약 3분. [HN] https://news.ycombinator.com/item?id=49156168
- wincy: 전체 구성 약 83GB, 양자화하면 5090에 들어갈 수도. [HN] https://news.ycombinator.com/item?id=49160981
- chrsw: 큰 장비에서 1080p는 "아무 데도 못 쓸" 수준이었다. [HN] https://news.ycombinator.com/item?id=49156786

**비교**
- echelon: Seedance 2.0보다 1년 반 뒤처졌다. [HN] https://news.ycombinator.com/item?id=49156651 / 반박: coder543은 선호도 리더보드에서 H3가 Seedance 2.0보다 위라고 했다. [HN] https://news.ycombinator.com/item?id=49161228
- ilaksh: Seedance 2.5가 많은 경우 훨씬 낫다. [HN] https://news.ycombinator.com/item?id=49157433
- Seedance 2.5 스레드에서 ronsor는 약간의 품질 손실보다 통제권·비용이 낫다고 했고([HN] https://news.ycombinator.com/item?id=49139802), Genego는 LTX 2.3보다 못하다고([HN] https://news.ycombinator.com/item?id=49140548), dagaci는 API판 H3가 프롬프트를 더 잘 따른다고 했다([HN] https://news.ycombinator.com/item?id=49142667).

**라이선스·검열**
- razster: 라이선스 때문에 미국에서 쓸 수 없다. [HN] https://news.ycombinator.com/item?id=49156610
- CamperBob2: 대형 연구소 모델 중 검열이 가장 적다. [HN] https://news.ycombinator.com/item?id=49178266

**Hailuo 2.3 (H3 이전 버전)**
- 리셀러 글(Artlist): 미세 표정과 얼굴 연기, 특히 애니 스타일에서 Kling보다 낫다고 했다. [포럼] https://artlist.io/blog/new-hailuo-2-3/
- Scenario 도움말: 미세 표정 모델링이 개선됐지만, 2.0과 달리 마지막 프레임 지정이 안 된다. [포럼] https://help.scenario.com/articles/8094765856-minimax-hailuo-video-the-essentials
- 2026-07-31에 H3로 대체됐다는 제3자 페이지. [포럼] https://www.seeddance.io/zh/models/hailuo-2-3
- 중국 매체 비교: 하이뤄는 "가성비, 단일 샷 사실 스타일"로 평가됨(구버전 기준). [CN] https://www.woshipm.com/?p=6094052 , https://m.sohu.com/a/1015578849_122004016/ (검색 요약 기준, 어느 문장이 어느 페이지인지는 확인 못 함)

**결제·신뢰성**
- MiniMax 회사 Trustpilot: 최고 요금제 80달러를 냈는데 결과가 약했고 환불 메일에 답이 없었다는 리뷰(하이뤄라고 명시하진 않음). [Trustpilot] https://www.trustpilot.com/review/minimax.io?page=1
- 불만 사이트: 2026-09-19 영상이 안 만들어졌는데 60크레딧 차감, Google Play 자동 갱신 불만(2026-10-01). [포럼] https://www.sikayetvar.com/en/hailuo-ai-us
- 공식 약관은 실패·심사 거절 시 크레딧 자동 반환이라고 함(결과가 마음에 안 드는 건 해당 없음). https://hailuoai.video/doc/payment-policy.html
- 쇼케이스: H3와 터보 LoRA로 끝없는 시트콤([HN] https://news.ycombinator.com/item?id=49504884), 집 PC로 만든 단편([HN] https://news.ycombinator.com/item?id=49879513).

---

### 2.3 Kling 3.0 / Kling Omni 3 / Motion Control 2.6·3.0 / Kling Lipsync

**전체: 품질은 대체로 긍정, 결제·지원은 강한 부정.** HN에서는 리셀러 Show HN 글만 있고(7개, 모두 4점 이하) 실제 토론은 없었다. [HN] https://hn.algolia.com/api/v1/search?query=Kling%203.0&tags=story

**모션 컨트롤 (참고 영상 → 캐릭터)**
- 가장 흔한 불만은 얼굴 드리프트: 참조 영상 속 사람과 캐릭터 이미지의 얼굴 각도·조명이 다르면 얼굴이 참조 인물 쪽으로 끌려간다. 업체 글이고, 근거로 든 것이 댓글 8개짜리 Reddit 글 하나다 [snippet]. [포럼] https://www.atlascloud.ai/blog/guides/kling-ai-motion-control
- 해결책으로 각도·조명이 다른 캐릭터 이미지 3장 이상(웹 UI만, API는 1장), 2~5초 클립을 권함. 같은 글.
- 2.6은 머리 회전이 크면 얼굴 일관성이 무너지고, 3.0은 측면·가림에서도 얼굴을 유지하도록 설계됐다는 설명. [포럼] https://tryonr.com/kling-3-motion-control
- 2.6 동작은 "둥둥 떠 보이고", 3.0은 걷기·뛰기·춤에 무게감이 생겼다(리셀러 주장). [포럼] https://invideo.io/blog/kling-motion-control/
- 가격 차이: 720p 기준 2.6은 초당 9크레딧, 3.0은 초당 25크레딧(1080p 13 / 35). "초안은 2.6, 최종은 3.0" 권장. 같은 Tryonr 글.
- 중국 매체: 모션 컨트롤 3.0이 동작·표정·입모양·손짓 일관성에서 "혁명적"이라고 보도(공식 발표 전달, 독립 테스트 아님). [CN] https://m.jiemian.com/article/14074435.html , https://www.stdaily.com/web/gdxw/2026-02/05/content_470802.html
- 애니·카툰 캐릭터로 모션 컨트롤을 직접 시험한 사용자 글은 이번 검색에서 하나도 못 찾았다.

**립싱크**
- 3.0은 중·영·일·한·스페인어 5개 언어 립싱크. 웹 앱 클립 상한 60초. 정면이 아닌 얼굴에서 왜곡이 흔한 문제로 꼽힘. [포럼] https://www.atlascloud.ai/blog/guides/kling-ai-lip-sync
- 2024년 출시 당시 공식 설명: 실사·3D·2D 인물은 되고 동물 캐릭터는 립싱크 불가. [CN] https://www.cs.com.cn/cj2020/202409/t20240930_6443554.html → 괴물·동물 입모양에는 약점일 가능성.
- 2025년 해외 테스터: 기술은 영리하지만 결과가 여전히 "묘하게 섬뜩하다". 오히려 스타일화된 표현이 낫다고 함. [포럼] https://www.pootlepress.com/2025/03/testing-the-most-recommended-ai-video-tools-are-they-ready-for-promotional-content/

**결제·지원 (Trustpilot)**
- SaaSWorthy 집계 1.3/5 (70개). [Trustpilot] https://www.saasworthy.com/product/kling-ai/reviews
- 아래 리뷰들은 Trustpilot 나라별 페이지(kling.ai / klingai.com) 검색 요약에서 나온 것이다. 어느 리뷰가 어느 나라 페이지에 있는지는 하나씩 확인하지 못했다. [Trustpilot] https://es.trustpilot.com/review/kling.ai , https://it.trustpilot.com/review/kling.ai , https://se.trustpilot.com/review/kling.ai , https://ca.trustpilot.com/review/klingai.com , https://jp.trustpilot.com/review/klingai.com
  - 해지 후 2026-05-09에 8.80달러 청구, 메일 무응답, 카드 분쟁 예정.
  - 한 번도 안 쓴 크레딧도 환불 불가, "가상 상품" 정책을 이유로 거절.
  - 자동 갱신 30분 안에 연락했는데 환불 거부.
  - 25크레딧일 작업이 125크레딧 차감.
  - 300크레딧을 샀지만 월 구독이 아니어서 무료 대기열에서 몇 시간 대기. 월 크레딧은 이월 안 됨.
  - 5달러 크레딧을 샀는데 피크 시간 안내만 뜨고 사용 불가, 환불 방법 없음.
  - 긍정: 프롬프트를 잘 이해하고 카메라 움직임이 가장 좋다(이미지 생성은 약함).
- 같은 리뷰가 나라별 페이지에 반복돼 실제 작성자 수는 더 적다(고유 리뷰 약 8개로 봄).
- 중국 비교 기사(구버전 2.x): 화면 디테일·물리 표현은 가장 좋지만 대기 30분 이상. [CN] https://www.woshipm.com/?p=6094052 (검색 요약 기준)

---

### 2.4 Google Veo 3.1 (Lite / Fast) / Gemini Omni Flash

**전체: 중립~긍정, 표본이 매우 적음.** HN의 Veo 3.1 글은 대부분 반응이 작다(출시 글 18점/댓글 3개).
- [HN] https://news.ycombinator.com/item?id=45594616 (Veo 3.1 출시), https://news.ycombinator.com/item?id=47589686 (Veo 3.1 Lite), https://news.ycombinator.com/item?id=47497002 (Gemini 앱에 Veo 3.1 Fast)
- 제약: Seedance 2.5 스레드에서 jarjoura는 Google과 xAI가 참조 이미지를 720p로 제한하고 오디오 싱크를 막는다고 했다(딥페이크 우려 때문이라고 봄). 실제 캐릭터 참조 영상을 만들 때 직접 걸리는 제약. [HN] https://news.ycombinator.com/item?id=49145728
- Gemini Omni Flash: Design Arena에서 프롬프트 준수 81%(평균 63%), 사실 영상부터 스타일화된 3D 애니까지 잘 처리, 풍경은 승률이 14.5%p 떨어짐. [포럼] https://notes.designarena.ai/gemini-omni-flash-a-video-model-for-directors/
- Omni 1.1 Flash가 LMArena 텍스트→영상 1위지만 표가 아직 적다는 글. [포럼] https://www.mindstudio.ai/blog/gemini-omni-1-1-flash-video-model
- 빠르고 싼 모델이라는 리뷰. [포럼] https://www.eesel.ai/blog/gemini-omni-flash-review
- PeerPush 평점 5.0이지만 리뷰 1개. [ProductHunt 유사] https://peerpush.com/p/gemini-omni-flash
- 얼굴 표정·립싱크·애니 유지·괴물에 대한 사용자 글: 근거 없음.

---

### 2.5 Vidu Q4

**전체: 근거 부족.** Q4만 다룬 사용자 글은 찾지 못했다(Q 시리즈 일반 리뷰만).
- Creator Economy Tools 3.8/5: 일관성은 경쟁작보다 낫지만 드리프트가 남아 "해결된 건 아니다". [포럼] https://creatoreconomytools.com/tool/vidu
- Dupple: 애니 스타일 결과가 특히 좋다, 참조 3~7장. [포럼] https://dupple.com/reviews/vidu-ai
- Unite.ai: 프롬프트 복잡도에 따라 결과 편차가 크다(제휴 수익 고지 있음). [포럼] https://www.unite.ai/vidu-ai-review/

---

### 2.6 Wan 3.0 (Alibaba)

**전체: 근거 부족.** 2026-08-24 출시, 2~30초, 480p~1080p, 하나의 엔드포인트로 통합. [포럼] https://www.mindstudio.ai/models/wan-3-0
- Reddit 반응을 정리한 제3자 블로그 [snippet]: 관심은 있지만 "오픈 웨이트가 정말 나오나"가 최대 질문이고, 직접 비교는 아직 적다. [포럼] https://wan27.org/blog/wan-3-0-reddit
- 업체 글: 사실적 얼굴에서 눈 흔들림, 밀랍 같은 피부, 입 깜빡임, 얼굴 구조 변화가 문제. [포럼] https://www.plushcap.com/content/atlas-cloud/blog/atlas-cloud-wan-30-realistic-faces-3-prompts-that-look-human
- HN H3 스레드에서 SV_BubbleTime은 H3 샘플을 보고 LTX2·Wan 폴더를 지웠다고 했다(Wan 2.x 기준). [HN] https://news.ycombinator.com/item?id=49155791
- Civitai: Wan 3.0 관련 글·LoRA는 못 찾았다. 학습 레시피는 Wan 2.1/2.2까지만. [포럼] https://developer.civitai.com/orchestration/recipes/training-wan

---

### 2.7 Higgsfield

**전체: 갈림.** 여러 회사 모델(Kling, Seedance, Veo 등)을 묶어 파는 서비스라 화질은 밑에 깔린 모델을 따른다. 불만은 거의 결제 쪽이다.
- Trustpilot 1,200개 이상, 별 5 약 63%, 별 1 약 20%(제3자 집계). 다른 블로그는 4.0점에 별 1 꼬리가 길다고 함. [Trustpilot] https://trustpilot.com/review/higgsfield.ai , 집계 출처 https://fluxnote.io/guides/higgsfield-ai-questions-answered , https://creatify.ai/blog/higgsfield-ai-review-(2026)-is-it-worth-it
- 아래 리뷰들은 Trustpilot 나라별 페이지 검색 요약에서 나온 것이다(리뷰별 페이지는 하나씩 확인 못 함). [Trustpilot] https://uk.trustpilot.com/review/higgsfield.ai?page=4 , https://ie.trustpilot.com/review/higgsfield.ai?page=3 , https://uk.trustpilot.com/review/higgsfield.ai?page=9 , https://ca.trustpilot.com/review/higgsfield.ai?page=4 , https://ie.trustpilot.com/review/higgsfield.ai?page=7
  - Unlimited 토글을 켰는데 Ultra 계정에서 3,000크레딧 이상 사라짐(2026-07). 지원팀은 로그상 토글이 꺼져 있었다며 복구 거부.
  - 해지 후 150달러 청구(2026-03). 환불은 첫 결제만 된다는 리뷰도 있음.
  - Ultra + 추가 크레딧을 샀는데 5분 영상 하나에 6,000크레딧 전부 소진.
  - 무제한 Nano Banana 2K 모드가 너무 느려 사실상 유료 크레딧으로 밀어낸다. "사기"라는 표현까지 나옴.
- 브랜드 작업에 1,000달러 넘게 쓴 사용자가 있다는 가격 분석. [포럼] https://dailyaifixs.com/blog/higgsfield-ai-pricing-2026-the-credit-catch
- 회사 답변은 support@higgsfield.ai에 "Manual Review" 제목으로 보내라는 안내가 반복됨. 같은 Trustpilot 페이지.
- Product Hunt 리뷰 페이지는 "아직 리뷰 없음". [ProductHunt] https://www.producthunt.com/products/higgsfield-ai/reviews
- 얼굴·애니·립싱크 품질에 대한 Higgsfield 고유의 평가는 없음(밑의 모델 평가를 따름).

---

## 3. 몸동작 도구

### 3.1 Uthana (텍스트/영상 → 스켈레톤 애니메이션)

**전체: 근거 부족.** HN 검색 0건, BlenderArtists·80.lv·Polycount에서 리뷰 못 찾음, Product Hunt 리뷰 URL은 404.
- HN Algolia 검색 결과 0건: https://hn.algolia.com/api/v1/search?query=Uthana%20OR%20QuickMagic%20OR%20%22Rokoko%20Vision%22
- 가벼운 리뷰 8.5/10: "AAA 애니메이터를 대체하진 않지만 대부분 창작자에게 10%의 노력으로 90%의 가치". 실제 테스트 내용은 적음. [포럼] https://aiindigo.com/blog/uthana-review-2026-text-to-animation-that-actually-works
- 제품 설명: 프롬프트 하나에 서로 다른 모델로 후보 3개, FBX/GLB 내보내기, Blender 플러그인, GraphQL API. https://uthana.com/product/text-to-motion , https://replicate.com/uthana/text-to-motion-diffusion-v2
- Scenario 도움말: 이야기보다 팔다리 동작을 묘사해야 잘 된다. [포럼] https://help.scenario.com/articles/5065632876-uthana-the-essentials
- 2025-03 투자 430만 달러 + 공개 베타. https://pulse2.com/uthana-4-3-million-raised-to-transform-3d-character-animation-with-genai
- 괴물·비인간, 카툰 과장 동작: 근거 없음.

### 3.2 QuickMagic (영상 → 모캡)

**전체: 긍정(표본 적음).**
- Reallusion 포럼, 첫 전신 모캡 테스트(댓글 5개): 원작성자는 몸 모캡 가성비 최고라고 함. 약간의 떨림을 커브 에디터에서 스무딩(약 20)으로 정리했고, 모캡 특성상 올라간 어깨를 내려야 했으며 정리에 약 10분. 연간 Pro 200달러 = 12,000 vcoin = 약 200분. Move.ai가 품질은 조금 낫지만 훨씬 비싸고, 다른 서비스는 "꽤 엉성"했다고 함. 다른 사용자는 "깨끗하고 부드럽다"고 했다. 얼굴은 AccuFace + AccuLIPS 따로 사용. 손가락·발 미끄러짐 언급은 없음. [포럼] https://discussions.reallusion.com/t/first-full-body-mocap-test-using-quickmagic-and-accuface/15520
- Product Hunt 댓글(hunted.space 미러): 바닥 접지 감지가 좋아 발 미끄러짐 정리가 훨씬 적다, 단일 영상에서 여러 명 캡처 가능하지만 두 사람이 붙어 있으면 헷갈린다, 2D 보정 타임라인으로 프레임별 수정 가능. [ProductHunt] https://www.hunted.space/product/quickmagic-2
- FutureTools 디렉터리에 "추천 조작·나쁜 리뷰·수상한 관행으로 검토 중" 경고가 붙어 있음(시점 불명). [포럼] https://futuretools.io/tools/quickmagic
- HN 0건.

### 3.3 Rokoko Vision (Rokoko Video)

**전체: 중립, 독립 사용자 글 거의 없음.**
- 무료 Starter: 단일 카메라 Vision, 정리 필터, FBX 내보내기. Plus(연 결제 월 20달러): 듀얼 카메라 + Blender 실시간 스트리밍. https://www.rokoko.com/pricing
- 80.lv 출시 소개: 영상 업로드 → FBX/BVH → Blender, 정리는 무료 Rokoko Studio에서. [포럼] https://cdn.80.lv/articles/rokoko-video-new-free-ai-motion-capture-tool
- 체조·레슬링처럼 빠르고 겹치는 동작은 떨림이 남아 손으로 다듬어야 하고, 2D에서 깊이를 추정하므로 발 미끄러짐이 생긴다(가벼운 리뷰 글). [포럼] https://aiindigo.com/blog/rokoko-video-review-2026-high-fidelity-motion-capture-without-the-suit
- 경쟁사(Viggle) 비교: 단일 카메라 무료, 녹화 15초까지. [포럼] https://viggle.ai/blog/pinoc-vs-rokoko-vision
- HN 0건, BlenderArtists 스레드 못 찾음.

### 3.4 Tripo 애니메이션 / 자동 리그

**전체: 모델 출력은 긍정, 결제·지원은 부정, 리그 품질은 독립 근거 적음.**
- Trustpilot 약 600개, TrustScore 4.5(스냅샷마다 4.5~4.7). AI 요약은 쓰기 쉽고 품질 좋다는 평이 다수, 가끔 형태 왜곡. [Trustpilot] https://uk.trustpilot.com/review/tripo3d.ai?page=5
- 불만: 산 크레딧이 매월 리셋돼 못 쓰면 사라짐, 월 결제 없이 연 결제만, 결제했는데 비구독자로 처리돼 내보내기 불가(2026-03-12), 지원팀이 같은 정보를 반복 요구하고 7일 지연 자동 답변, 이후 일부 보상. 별 5 리뷰를 쓰면 300크레딧을 준다는 주장도 있었음(확인 못 함). 리뷰별 나라 페이지는 하나씩 확인 못 함. [Trustpilot] https://ie.trustpilot.com/review/tripo3d.ai?page=6 , https://ca.trustpilot.com/review/tripo3d.ai?page=5 , https://au.trustpilot.com/review/tripo3d.ai?page=6
- 괴물·4족: Tripo Rigging 2.5는 4족·6족·8족·조류·뱀형·수중형을 지원한다는 설명. [포럼] https://help.scenario.com/articles/4692888910-tripo-family-the-complete-guide
- 독립(에 가까운) 테스트: 여우 같은 4족 동물에서 Tripo 포함 4개 자동 리거가 모두 다리 관절을 거의 일자로 놓았고, Tripo는 척추를 팔다리 사슬로 인식했다. 이족 위주 학습 데이터 탓이라고 봄. 글쓴 회사가 Tripo 리깅을 유료 상품에 넣고 있어 완전 중립은 아님. [포럼] https://app.cinevva.com/es/blog/2026-08-19-auto-rigged-animals-straight-legs
- 50개 이상 생성한 리뷰어: Blender 정리 없이 Unity에 바로 넣어 썼다(리그 전용 평가는 아님). [포럼] https://levelup.gitconnected.com/building-game-ready-3d-assets-fast-the-best-ai-generators-for-production-workflows-in-2026-f1f725ff5df0

### 3.5 Meshy Animate / 자동 리그

**전체: 혼합.**
- Trustpilot 점수가 출처마다 다름: 2.0/5(13개, 2026-05 확인) vs 4.8/5(2026-08). 월 결제인 줄 알았는데 연 결제가 청구됐다는 환불 불만이 반복. [Trustpilot 집계] https://stacksheriff.com/ai-tools/meshy-ai-review/ , https://knowara.com/ai-tools/image/meshy-ai-review/
- 리깅은 "매우 기본적", 얼굴 리그 미지원, 표준 이족·4족에 최적화돼 특이한 괴물은 수동 리깅 필요. [포럼] https://knowara.com/ai-tools/image/meshy-ai-review/
- Product Hunt 댓글: "쉬운 리깅과 애니메이션이 좋다". [ProductHunt] (StackSheriff 글이 인용) https://stacksheriff.com/ai-tools/meshy-ai-review/
- Meshy 6에서는 자동 리깅이 크레딧 무료라는 설명. 같은 StackSheriff 글.

---

## 4. 우리 용도(게임 캐릭터 표정·몸동작 참고 영상)에 비춘 정리

1. **애니·카툰 얼굴을 다룬 실제 사용자 글이 거의 없다.** 애니 관련 의견은 bilibili 제목 두 개, HN "신카이풍" 댓글, 리셀러 글뿐이다. 애니/카툰 유지력은 결국 직접 테스트해야 판단할 수 있다.
2. **얼굴 드리프트가 모델을 가리지 않고 가장 흔한 불만이다.** Kling 모션 컨트롤(참조 인물 쪽으로 얼굴이 끌림), Seedance(긴 샷 누적 오류, 뻣뻣한 눈), Vidu(드리프트가 해결되진 않음), Wan(눈 흔들림·입 깜빡임).
3. **괴물·비인간:** 영상 쪽은 H3 쥐 렌더 칭찬 하나, Kling 립싱크는 동물 불가(2024 기준). 리그 쪽은 Tripo·Meshy 모두 4족은 되지만 다리·척추 오류나 "표준 체형만"이라는 지적.
4. **결제 리스크:** Kling과 Higgsfield는 Trustpilot에 환불 거부·해지 후 청구·크레딧 과다 차감 불만이 쌓여 있다. Tripo·Meshy는 연 결제·크레딧 리셋 불만. 소액·단기 결제로 시험하는 게 안전하다.
5. **재시도율 수치는 사실상 없다.** Seedance 립싱크 "10번 중 7번"(업체 글)과 중국 기사의 "抽卡率(뽑기 횟수)을 같이 봐야 한다"는 언급 정도. [CN] https://www.woshipm.com/?p=6335625 (검색 요약 기준)
6. **몸동작:** QuickMagic이 사용자 평가가 가장 구체적이고 좋다(정리 10분, 연 200달러로 약 200분). Rokoko·Uthana는 독립 평가가 거의 없어 무료 단계에서 직접 시험해야 한다.

## 5. 이번 조사에서 다루지 못한 것

- YouTube 리뷰 영상(제목·고정 댓글), 공개 Discord 요약, 知乎·小红书·V2EX 실사용 글, BlenderArtists·Polycount 스레드: 검색에 걸리지 않았다.
- HN "H3-metal"(댓글 98개)와 Seedance 2.5 스레드 뒷부분(약 3만 자)은 읽지 않았다.
- G2/Capterra 점수는 확인하지 못했다(QuickMagic의 Software Advice 등록 페이지만 확인: https://www.softwareadvice.com.au/software/528112/QuickMagic).
