# 몸 동작·몬스터 동작용 AI 영상/모션 도구 — 사용자 평판 조사

- 조사일: 2026-10-14 (웹 검색·페이지 읽기 약 27회, 가입·구매·다운로드 없음)
- 목적: 캐릭터 이미지 1장으로 **몸 동작 레퍼런스 클립**(걷기·달리기·공격·대기·이모트)을 만들고, **몬스터/생물**(4족, 다리 많은 것, 날개, 덩어리형) 동작도 만들 수 있는지에 대한 사용자 평판.
- 근거 표시: **[community]** 사용자 글·GitHub 이슈·HN·Product Hunt / **[independent test]** 블라인드 아레나·독립 실측 / **[3rd-party blog]** 리셀러·리뷰 블로그(이해관계 있을 수 있음) / **[vendor]** 제작사 자료.
- **중요한 한계**
  - Reddit은 검색 도구에서 접근이 막혀 있었다(`reddit.com`을 크롤러가 읽을 수 없다는 오류). 그래서 Reddit 의견은 다른 글이 인용한 2차 자료로만 들어 있다. X/Discord 원문도 직접 확인하지 못했다.
  - 검색 결과 대부분이 SEO용 비교글·리셀러 블로그였다. "N번 중 몇 번 성공" 같은 재시도율 데이터는 거의 없다.
  - **비인간형(몬스터) 동작을 직접 시험한 사용자 자료는 영상 모델·3D 도구 모두 거의 없다.** 아래 몬스터 평가는 대부분 간접 근거와 추론이다(추론은 "추론"이라고 표시했다).
  - "(원문 미확인)"은 검색 요약에서만 본 주장이라 정확한 출처 URL이 불확실하다는 뜻이다.

---

## 0. 공통 지표 — 독립 블라인드 아레나 (Artificial Analysis 이미지→영상, 오디오 포함 v1.1)

일반 이미지→영상 선호도 순위다(동작만 따로 잰 점수는 아님). Kling 3.0 Pro = 1000 기준. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video

| 순위 범위 | 모델 | Elo | 표본 | API 가격 (1080p 1분) |
|---|---|---|---|---|
| 1-5 | MiniMax H3 (768p) | 1130 | 3,335 | $5.40 |
| 1-5 | Vidu Q4 Preview | 1129 | 3,894 | $5.04 |
| 1-7 | Dreamina Seedance 2.5 | 1120 | 2,950 | $24.60 |
| 2-7 | Wan 3.0 | 1119 | 5,022 | $12.00 |
| 3-7 | MiniMax H3 Max | 1116 | 3,285 | $5.76 |
| 4-7 | Dreamina Seedance 2.0 | 1113 | 2,670 | $22.45 |
| 12-16 | Veo 3.1 | 1029 | 3,295 | $24.00 |
| 16-18 | Veo 3.1 Fast | 1013 | 5,096 | $9.00 |
| 17-21 | Kling 3.0 Omni Pro | 1003 | 2,816 | $16.80 |
| 20 | Kling 3.0 Pro (기준점) | 1000 | 5,226 | $20.16 |

- 상위 7개는 통계적으로 거의 동률이다. **가격 대비로 보면 MiniMax H3와 Vidu Q4가 압도적으로 싸다.**
- Kling 2.6, Hailuo 2.3, Veo 3.1 Lite는 이 표에 보이지 않는다.
- Hailuo 2.3은 텍스트→영상 표에서 1172.4로 언급된 적이 있다(구 점수 체계라 위 표와 직접 비교할 수 없음). [3rd-party blog] https://artificialanalysis.ai/video/models/kling-3-0-pro

---

## 1. 영상 모델

### 1.1 Kling 3.0 Motion Control / Kling 2.6 Motion Control

**구조**
- 캐릭터 이미지 1장과 레퍼런스 동작 영상을 넣으면, 그 동작을 따라 하는 **영상**이 나온다(뼈대 데이터가 아님). [vendor] https://kling.ai/quickstart/motion-control-user-guide
- Kling 기술보고서는 "구동 영상의 몸과 대상 캐릭터의 몸이 크게 달라도 잘 처리한다"고 주장한다. 경쟁 모델인 Dreamina가 아이 캐릭터의 팔다리 비율을 바꿨다는 비교도 있다. [vendor] https://arxiv.org/html/2603.03160v1

**동작 물리 (발 미끄러짐, 무게감, 속도)**
- Kling 3.0을 60회 생성해 본 글: 발 미끄러짐("moonwalk"·"gliding"), 팔 떠다님, 손 뭉개짐이 반복되는 결함이었다. 프롬프트로 "뒤꿈치부터 착지"를 지정하고, 카메라를 캐릭터와 같은 속도로 따라가게 하면 줄어든다고 한다. [3rd-party blog, 리셀러] https://www.atlascloud.ai/blog/mastering-kling-3.0-10-advanced-ai-video-prompts-for-realistic-human-motion
- 단거리 질주 실측(구버전 비교): Veo 3는 발걸음이 깨끗했고, Kling은 몇 초 뒤 팔다리가 변형되기 시작했다. [independent test] https://www.tractionco.com/insights/can-ai-video-keep-up-with-human-movement-a-futureproof-field-test
- 빠른 발동작에는 Pro 등급을 권장하는 가이드가 있다. [3rd-party blog] https://www.eachlabs.ai/blog/kling-motion-control-complete-guide
- Runway 도움말은 "지나치게 빠른 동작은 피하라"고 한다. [3rd-party docs] https://help.runwayml.com/hc/en-us/articles/50280558448147-Creating-with-Kling-3-0-Motion-Control

**레퍼런스 동작 충실도**
- Kling 2.6 Motion Control 시험: 비교 모델 중 실제 몸 역학에 가장 가깝게 따라 했다. 다만 움직이는 동안 배경이 크게 일그러졌다. [independent test] https://www.kapwing.com/resources/seedance-vs-veo-vs-kling-text-to-video-comparison-2026/ (원문 미확인)
- 텍스트만으로 걷기를 설명하면 몸 비율이 흐트러진다. 그래서 레퍼런스 영상 방식을 쓴다. [3rd-party blog] https://www.atlascloud.ai/blog/mastering-kling-3.0-10-advanced-ai-video-prompts-for-realistic-human-motion

**팔다리·손 오류**
- 2.6 애니메이션 캐릭터 360도 회전 테스트: 캐릭터 일관성은 매우 좋았지만, 팔이 몸을 뚫는 결함이 몇 번 나왔다. 실무에 쓰려면 다시 생성해야 한다는 평. [3rd-party blog/독립 리뷰] https://curiousrefuge.com/blog/kling-26-motion-control-review
- Kling 블로그는 "이전 모델은 팔이 사라지고 다리가 떴는데 2.6에서 고쳤다"고 주장한다. [vendor] https://kling.ai/blog/ai-motion-transfer-video-tutorial

**스타일 캐릭터 (치비·큰 머리·애니 비율)**
- Kling 가이드: 실제 사람 영상을 권장하며, 일부 스타일 인간형 비율만 인식된다. 이미지와 영상의 전신/반신 구도가 맞아야 한다. [vendor] https://kling.ai/quickstart/motion-control-user-guide
- 이미지와 영상의 몸 비율을 맞추고, 전신 영상에 반신 이미지를 넣지 말라는 안내. [3rd-party docs] https://replicate.com/kwaivgi/kling-v3-motion-control
- 얼굴 클로즈업 이미지에 춤 영상을 넣으면 실패하거나 심하게 일그러진다. [vendor] https://kling.ai/blog/ai-motion-transfer-video-tutorial
- 치비를 직접 시험한 공개 자료는 찾지 못했다.
- 같은 "뼈대로 끌고 가는" 방식인 Wan Animate 사용자들은 "치비는 뼈대에 맞춰 몸이 늘어난다"고 보고한다(1.3 참조). **추론:** Kling에도 같은 위험이 있다.

**비인간형 (몬스터)**
- 사람 → 인간형 로봇은 비율이 비슷하면 되지만, 사람 → 개는 대개 실패한다. [3rd-party blog] https://www.mindstudio.ai/blog/what-is-kling-2-6-pro-motion-control-video
- Kling 3.0 일반 생성에서 달리는 골든리트리버에 순간적으로 다리가 하나 더 생기고 발이 번졌다. "출시용으로 쓰려면 다시 생성해야 한다"는 평. [3rd-party blog] https://aijustdropped.com/model/kling-v3

**재시도율**
- 수치 자료는 없다. "다시 생성 필요"라는 정성적 언급만 여러 건 있다(위 curiousrefuge, aijustdropped).

**어느 등급이면 충분한가**
- 빠른 발동작은 Pro(위 eachlabs). 그 외에는 Standard로도 된다는 언급이 많다(대부분 리셀러 글).

**Kling 3.0 이미지→영상(일반)**
- 아레나 기준점 1000으로 상위권 모델보다 약 110~130점 낮다. 가격은 $20/분으로 비싼 편이다. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- 한 블로그의 고양이 프롬프트 테스트에서는 움직임 매끄러움 9/10을 받았다. [3rd-party blog, Seedance 판매사] https://www.noviai.ai/video-tips/seedance-2-reivew/

### 1.2 Seedance 2.0 / 2.5 (레퍼런스 영상으로 동작 복사)

**동작 물리**
- 걷기·회전·팔 들기는 15초 내내 매끄러웠고, 끊김이나 팔다리 분리가 없었다. [3rd-party blog, 판매사 작성자 실측] https://www.noviai.ai/video-tips/seedance-2-reivew/
- 반면 달리기·빠른 전투·극단적 회전에서는 가끔 팔다리가 늘어나고, 약간 몸을 뚫고, 프레임 사이 잔상이 생겼다. 고속 동작에는 수작업 정리를 권장한다. [3rd-party blog] 같은 URL

**손·팔다리**
- 손가락이 가끔 뭉개지고, 3명 이상 장면은 혼란스럽다. [3rd-party blog] https://www.noviai.ai/video-tips/seedance-2-reivew/

**레퍼런스 충실도**
- 같은 레퍼런스 영상을 쓰면 프롬프트 3개 모두 카메라 움직임이 동일했다. 즉 레퍼런스가 동작 경로와 타이밍을 강하게 고정한다. [3rd-party blog] https://www.technology.org/2026/02/23/how-i-used-reference-videos-to-replicate-complex-camera-movements-in-seedance-2-0/
- 각 파일의 역할을 구체적으로 지시하면 12회 중 11회 성공, 모호하게 지시하면 12회 중 4회 성공했다. 레퍼런스가 결과물보다 짧으면 끝부분 동작을 지어낸다. [3rd-party blog] https://magichour.ai/blog/seedance-20-reference-guide (원문 미확인)
- Seedance 2.0 논문은 복합 지시에서 Kling 3.0보다 동작 품질 점수가 1점 이상 높다고 한다. [vendor] https://arxiv.org/pdf/2604.14148

**스타일 캐릭터·몬스터**
- 직접 시험한 자료를 찾지 못했다.

**비용·접근성**
- $22~25/분으로 상위권 중 가장 비싸다. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- "공개 API가 없고 실제 사람 얼굴 레퍼런스를 막는다"는 글이 있다. 다만 fal 등 여러 API 리셀러가 이미 있어 오래된 정보일 수 있다. https://fal.ai/learn/tools/seedance-2-0-vs-kling-3-0 (원문 미확인)

### 1.3 Wan 3.0 / Wan-Animate (2.2 Animate 기준. "Wan-Animate-2" 사용자 자료는 찾지 못함)

**Wan 3.0**
- 아레나 1119점으로 상위권이고 $12/분이다. 몸 동작에 특화된 사용자 리뷰는 찾지 못했다. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video

**Wan Animate — 치비 등 다른 비율의 캐릭터**
- 몸 비율이 사람과 크게 다른 캐릭터(치비 등)에는 배우 연기를 정확히 옮길 수 없다. 모델이 캐릭터 몸을 뼈대에 맞춰 늘린다. [community] https://github.com/kijai/ComfyUI-WanVideoWrapper/issues/1262
- 우회책:
  - 몸/얼굴/손 뼈대 안내를 끄면 된다(대신 동작 정확도가 떨어진다).
  - 구동 영상 첫 프레임으로 캐릭터 그림을 새로 만든다.
  - 출처는 같은 GitHub 이슈. [community]
- 같은 이슈에서 "예제 워크플로 결과가 데모 영상과 전혀 다르다"는 보고도 있다. 데모가 과장됐을 수 있다. [community] 같은 URL

**Wan Animate — 손·팔다리**
- 일부 구성에서는 얼굴만 움직이고 손은 안 움직였다. [community] 같은 이슈
- 얼굴 애니메이션이 너무 강해서 몸 포즈와 얼굴 강도를 따로 조절하게 해 달라는 요청이 있다. [community] https://github.com/Comfy-Org/ComfyUI/issues/10401
- "Wan Animate의 뒤틀린 팔다리" 대안으로 SCAIL을 소개하는 유튜브 영상(제목·설명만 확인). [community] https://www.youtube.com/watch?v=tFtpztVqnHs

**Wan Animate — 비인간형**
- 논문 구조상 사람 뼈대 신호로 몸 동작을 옮긴다. [vendor 논문] https://arxiv.org/html/2509.14055v1
- **추론:** 생물·몬스터에는 맞지 않는다.

**Wan Animate — 비용**
- 오픈 웨이트라서 로컬 GPU로 무료 실행할 수 있다.

### 1.4 MiniMax H3 / Hailuo 2.3

**H3 vs 2.3**
- 같은 6초 시험에서 H3가 연기를 더 알아보기 쉬웠고 리듬도 더 자연스러웠다. 크레딧은 2.3이 27, H3가 84로 약 3배다. [3rd-party blog, 실측] https://astorie.ai/blog/minimax-h3-review

**동작 물리**
- H3는 공간 역학을 직접 지시하지 않으면 떠다니거나 뭉개지는 쪽으로 간다. [3rd-party blog] https://digitalzoomstudio.net/2026/09/unrealistic-movement-in-ai-video-models-like-minimax-hailuo-h3-fix/
- 레퍼런스 영상을 넣으면 연기는 분명해지지만 물리가 좋아진다는 보장은 없다. 손이 물건을 잡는 순간, 발이 땅에 닿는 순간으로 판단하라는 조언. [3rd-party blog] https://www.imagine.art/blogs/minimax-h3-vs-hailuo-2-3
- 움직이면서 형태가 무너지는 실패 사례(종이배 등). [3rd-party blog] https://trilogyai.substack.com/p/minimax-h3-ai-video

**싸움 동작**
- 커뮤니티 모션 어댑터 비교: 어댑터 없이는 "전진-멈칫" 반복 끊김, 어댑터를 쓰면 계속 움직인다. [community] https://huggingface.co/MATLOWAI/MiniMax-H3-Motion-Adapter

**춤 동작**
- 일본 사용자가 H3, WAN DANCER, LTX2.3을 비교했다. H3의 움직임이 LTX보다 훨씬 자연스러웠다. 480x864 5초 생성에 약 9분 걸렸다(로컬 워크플로로 보임). [community] https://note.com/ai_0049/n/n6ca05d44959d

**Hailuo 2.3**
- 솔로 발레는 설득력이 있었다.
- 여러 명이 추는 스트리트 댄스에서는 가운데 댄서의 두 다리가 하나로 합쳐졌다(3.5/10). [3rd-party blog] https://www.atlascloud.ai/blog/tips/hailuo-ai-video-generator-review

**가격**
- 6초 클립 기준 2K H3 $0.78, 768p Hailuo 2.3 $0.28. [3rd-party blog] https://huggingface.co/blog/ResterChed/minimax-h3-hailuo-3-0
- 아레나 표 기준 H3 768p는 $5.40/분. [independent test]

**몬스터**
- 직접 시험 자료는 없다.

### 1.5 Veo 3.1 Fast / Lite

**등급 비교**
- 동작 사실감 점수: Lite 7.2, Fast 7.7. 시간 일관성: Lite 6.7, Fast 7.0. 집계 사이트 한 곳의 점수다. [3rd-party blog] https://maxvideoai.com/ai-video-engines/veo-3-1-fast-vs-veo-3-1-lite
- Lite는 복잡한 장면에서 깜빡임과 동작 아티팩트가 있다는 언급(위 URL, 그리고 https://ltx.io/blog/veo-3-1-lite [경쟁사]).
- "Lite와 Quality 차이를 거의 못 느꼈다"는 유튜브 비교(제목·설명만 확인). [community] https://www.youtube.com/watch?v=qWTkXpQwDrc

**동작 물리**
- (구 Veo 3) 질주 발걸음이 깨끗했다. [independent test] https://www.tractionco.com/insights/can-ai-video-keep-up-with-human-movement-a-futureproof-field-test
- 고양이 프롬프트 테스트에서는 움직임 7/10. [3rd-party blog] https://www.noviai.ai/video-tips/seedance-2-reivew/

**아레나**
- Veo 3.1 Fast 1013점, $9/분. [independent test]

**몬스터**
- 초기 Veo(구 모델)에서 "다리 6개 말"이 나온 사례가 있다. 현행 모델과는 무관하다. [3rd-party] https://www.artnews.com/art-news/reviews/1234801925-1234801925/

### 1.6 Vidu Q4 (2026-10-07 출시, 1주일 됨)

- 아레나 1129점(1~5위 동률권), $5.04/분으로 최저가권이다. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- 초기 평가: 얼굴은 어색할 때가 있지만, 애니·스타일 애니메이션·모션그래픽은 꽤 유망하다. [3rd-party blog] https://mykreatool.com/en/news/vidu-ai-video-generator-4k-10bit
- 애니·시네마틱 액션 쪽 성향이라는 리뷰어 인상. [3rd-party news] https://pandaily.com/shengshu-vidu-q4-preview-4k-video-model-reference-audio-0-09-yuan-per-second
- "크고 빠른 동작도 번지지 않는다"는 주장. [vendor] https://www.perfectcorp.com/consumer/blog/video-editing/vidu-q4-youcam-apps
- 텍스트→영상은 아직 지원하지 않는다. [3rd-party] https://www.orcarouter.ai/blog/vidu-q4-preview-aa-video-i2v-debut
- 몸 동작 실측과 몬스터 자료는 아직 없다.

### 1.7 Higgsfield Genjutsu

- 동작을 새로 만드는 도구가 아니라 **기존 영상을 편집(영상→영상)하는 도구**다. 예: 옷 색 바꾸기, 차만 교체하기. [3rd-party blog, 제휴 링크] https://www.cachephoto.com/en/cineblog/higgsfield-genjutsu-video-a-video/
- Reddit 스레드에서 렌더 대기가 2~4일이라는 보고가 여럿 있다(2차 인용). 무료 플랜에는 크레딧이 없고, Plus는 월 €59. [3rd-party, Reddit 인용] https://www.kavel.ai/blog/higgsfield-genjutsu-price-guide
- "아직 논의가 부족하다"는 정리. [community roundup] https://digg.com/tech/627fi5zb
- **추론:** 사람 모션 영상 속 배우를 우리 캐릭터로 바꾸는 용도로는 쓸 수 있다. 하지만 비용과 대기 시간 때문에 우리 용도에는 비효율적이다.

---

## 2. 3D 쪽 (뼈대 데이터 직접 출력)

### 2.1 Uthana (텍스트→모션 1.0/2.0/3.0, 영상→모션, Locomotion)

**출력 형식**
- 영상이 아니라 FBX/GLB/BVH 키프레임 **뼈대 데이터**가 나온다. [vendor] https://uthana.com/models/video-to-motion
- 2족 캐릭터로 리타깃한다. 비인간형은 지원 범위 밖이다. [vendor] 같은 URL

**텍스트→모션 3.0**
- 2026-06-15부터 제한 공개 중이며, 사용하려면 지원팀에 요청해야 한다. [vendor] https://uthana.com/docs/api/changelog
- 3.0에서는 Foot IK 같은 수동 옵션이 빠졌다. [3rd-party docs] https://help.scenario.com/articles/6720109441-uthana-motion-the-essentials
- **추론:** 발 접지는 엔진에서 직접 확인해야 한다.

**Locomotion**
- 마지막 프레임이 첫 프레임과 같아서 깔끔하게 반복 재생된다. 보폭 수, 속도, 방향을 조절할 수 있고 2초 안에 나온다. [vendor] https://uthana.com/product/locomotion
- Uthana 자체도 "정확한 방향·속도·보폭이 중요하면 텍스트가 아니라 Locomotion을 쓰라"고 한다. [vendor] https://uthana.com/blog/text-to-motion-30-sets-a-new-bar-for-ai-animation

**사용자 평**
- 사용자 리뷰: "달리기, 점프, 칼 들기" 같은 복합 프롬프트를 요청한 대로 수행해 인상적이었다고 한다. 발 미끄러짐은 다루지 않았다. [3rd-party blog] https://aiixx.ai/blog/uthana-review-the-ai-tool-that-makes-3d-animation-as-easy-as-texting
- Uthana 스스로 "같은 입력으로 통제된 품질 비교는 하지 않았다"고 밝힌다. [vendor] https://uthana.com/resources/best-ai-motion-capture-tools
- 독립 실측이나 커뮤니티 평가는 찾지 못했다(Reddit 접근 불가).

### 2.2 Rokoko Vision 3.0 + 텍스트→모션 (Rokoko Create)

- Vision 3.0은 해석기를 처음부터 다시 만들어 데이터가 훨씬 깨끗해졌다고 한다. [vendor] https://www.rokoko.com/insights/introducing-rokoko-vision-3-0
- 몸이 가려지면 약하다. 전신이 보여야 한다. [vendor] https://www.rokoko.com/products/vision
- 3.0 출시 시점에 손가락 추적이 없고, 웹캠·듀얼카메라 모드가 빠졌다. [3rd-party] https://aitools.fyi/rokoko-vision
- 구버전 Vision은 "떨리고 튄다"는 평이었다(약 14개월 전 비교라 3.0 이전). [3rd-party blog/비교 실측] https://tato.studio/blog/best-ai-video-to-mocap
- 텍스트→모션은 "실험적"이다. 스무딩 필터를 쓰면 아티팩트가 생기고, 반복 재생 시 "제자리 미끄러짐·회전"이 생긴다(구 Preview 릴리스 노트). [vendor] https://support.rokoko.com/hc/en-us/articles/40253275317265-Rokoko-Studio-Preview-1-1-0-Text-to-Motion
- 가격: Basic 월 $10(연간 결제)에 Vision 600초. [vendor] https://www.rokoko.com/pricing
- 비인간형은 해당 없다(사람 뼈대 전용).

### 2.3 QuickMagic

- CGDive(블렌더 유튜버) 실사용 리뷰:
  - 동작이 땅에 붙어 있고 안정적이며, 발 고정 감지가 탁월하다.
  - 땅을 짚은 손은 약하고, 슬로모션 영상은 어렵다.
  - 무료 50코인/월(1초 = 1코인).
  - 이미지 날짜는 2024-02.
  - [independent test] https://cgdive.com/quickmagic-review-high-quality-ai-motion-capture/
- 비교 리뷰: 부드럽고 정확하며 손가락 추적도 된다. 다만 무릎 꿇기 같은 복잡한 포즈에서는 발이 미끄러진다. [3rd-party blog] https://tato.studio/blog/best-ai-video-to-mocap
- Reallusion(iClone)이 QuickMagic 엔진을 통합했고, AI 모캡의 발 미끄러짐은 iClone 도구로 고친다고 한다. [vendor 측] https://magazine.reallusion.com/2026/04/13/video-mocap-for-beginners/
- 비인간형은 해당 없다.

### 2.4 Tripo 애니메이션/리깅 프리셋 (생물 포함)

- 리깅 모델 버전 `v1.0`은 2족 전용이고 프리셋이 90개 이상이다. `v2.5-20260210`은 4족·6족·8족·뱀형·수중형·조류를 지원한다. [vendor] https://developers.tripo3d.ai/en/docs/animations-rig
- **v2.5 생물용 프리셋 목록은 문서에 없다(확인 불가).** 예시 리깅 작업은 30크레딧이었다.
- StraySpark 실측 비교 (2026-05):
  - 처음부터 애니메이션 완성까지 가장 빨랐다(약 3분).
  - UE5 리타깃이 가장 깔끔했고, Mover 2.0에서 발 미끄러짐이나 떨림 보고가 없었다.
  - 어깨·가슴 웨이트가 과하게 부드러워 팔을 들면 처지고, 턱 웨이트가 지저분했다.
  - 스타일 로봇은 최고였다.
  - (당시) 2족 전용이었다.
  - [independent test/3rd-party blog] https://www.strayspark.studio/blog/ai-auto-rigging-showdown-2026-tripo-meshy-cascadeur-mixamo
- Tripo 블로그도 AI 도구의 4족 애니메이션은 "발 타이밍이 실제 걸음걸이에서 벗어나고, 발밑 접지가 미끄러진다"고 인정한다. [vendor] https://www.tripo3d.ai/blog/animal-animation-gait-foot-contact

### 2.5 Meshy 애니메이트

- 프리셋은 500~600개 이상으로 Tripo보다 많다. [vendor] https://www.meshy.ai/tutorials/character-auto-rigging-workflow
- 4족은 "개(Dog)" 템플릿과 Smart Rig(베타)로 지원하지만, 애니메이션 종류가 적다. [vendor] 같은 URL
- StraySpark 실측:
  - 엉덩이 회전축이 5~15cm 어긋나 Mover 2.0에서 발이 땅을 뚫고 미끄러졌다.
  - 척추·쇄골 이름이 표준과 달라 캐릭터당 약 8분의 수동 매핑이 필요했다.
  - 프로토타입용으로는 좋다는 평.
  - (Meshy 7 이전 버전 기준)
  - [independent test/3rd-party blog] https://www.strayspark.studio/blog/ai-auto-rigging-showdown-2026-tripo-meshy-cascadeur-mixamo
- 경쟁사 Tripo는 "Meshy는 2족만 지원한다"고 주장한다(현재 Meshy 문서와 충돌). [vendor 경쟁사] https://www.tripo3d.ai/blog/quadruped-rigging-tools-compared

### 2.6 Anything World (Animate Anything)

- 인간형 외에 4족·곤충·물고기·새를 지원하고, 뼈대와 웨이트를 자동으로 만든다(2023 기사, 당시 무료 월 3모델). [3rd-party news] https://www.cgchannel.com/2023/10/animate-anything-uses-ai-to-rig-your-3d-characters/
- HN 사용자(3D 경험자): "숙련 아티스트만큼은 아니지만 꽤 괜찮다. 이 수준을 꾸준히 내려면 1년쯤 경험이 필요하다." [community] https://news.ycombinator.com/item?id=37741575
- 걷기·달리기·대기·점프 애니메이션이 나오지만, 생성된 뼈대를 메쉬에 맞게 손으로 조정해야 한다. [3rd-party blog] https://www.top3d.ai/learn/ai-rigging-animals-animate-anything
- 대칭 모델이 결과가 좋고, 하위 분류는 직접 고쳐야 할 수 있다. [vendor] https://anything-world.gitbook.io/anything-world/quickstart/animate-anything-quickstart
- Product Hunt 리뷰는 5건, 평균 5.0으로 표본이 매우 적다. [community] https://www.producthunt.com/products/anything-world/reviews

### 2.7 공통 사항: 영상→모캡은 사람 전용

- 인디 실사용 비교 글: 검토한 영상 모캡 도구 중 **4족·생물을 직접 처리하는 도구는 없다.** [3rd-party blog] https://www.strayspark.studio/blog/ai-mocap-indie-developers-2026-comparison
- AI가 만든 영상(고정 카메라)을 GVHMR로 Mixamo 리그에 옮기는 오픈소스 예제가 있다. 자동화 파이프라인 참고용이다. [community] https://github.com/dongxiansuixin/mixamo-llm-mocap
- 비슷한 프로젝트로, 발 고정을 포함해 BVH/FBX로 내보내는 것도 있다. [community] https://github.com/freddysae0/video2mocap

---

## 3. 평점 (우리 용도: 이미지 1장 → 게임 캐릭터 몸 동작 레퍼런스, + 몬스터)

| 도구 | 몸 | 몬스터 | 한 줄 이유 | 근거 강도 |
|---|---|---|---|---|
| Kling 3.0 Motion Control | 4 | 1 | 사람 레퍼런스 동작을 가장 잘 따르는 전용 도구다. 치비 비율은 위험하고, 사람→개 변환은 실패한다는 평 | 적음(독립) + vendor 다수 |
| Kling 2.6 Motion Control | 3 | 1 | 역학 충실도는 좋지만 배경 왜곡과 팔 관통이 있다. 3.0이 나왔으니 쓸 이유가 적다 | 적음 |
| Kling 3.0 이미지→영상 | 3 | 2 | 아레나 기준점으로 상위권보다 낮고 비싸다. 발 미끄러짐과 다리 추가 사례가 있다 | 적음 + 아레나 |
| Seedance 2.0 / 2.5 | 3.5 | 2 | 레퍼런스 복사와 걷기는 좋지만 빠른 전투에서 팔다리가 늘어난다. 가장 비싸다($22~25/분) | 적음(판매사 리뷰) + 아레나 |
| Wan 3.0 | 3 | 2 | 아레나 상위권인데 동작 관련 사용자 자료가 없다 | 아레나만 |
| Wan-Animate (2.2) | 2 | 1 | 무료·로컬이 장점이지만 치비는 뼈대에 맞춰 늘어나고 팔다리가 뒤틀린다는 커뮤니티 보고 | 적음(community) |
| MiniMax H3 / Hailuo 2.3 | 3.5 | 2.5 | 아레나 1위권이면서 최저가. 다만 물리를 지시하지 않으면 떠다니고, 다인원에서 다리가 합쳐진다 | 적음 + 아레나 |
| Veo 3.1 Fast / Lite | 3 | 2 | 걸음은 깔끔하다는 평. Lite는 Fast보다 동작 점수가 낮다. 아레나 중위권 | 적음 |
| Vidu Q4 | 3.5 (잠정) | 2.5 (잠정) | 아레나 1위권에 $5/분. 애니·액션이 유망하다는 초기 평. 출시 1주라 실측이 없다 | 매우 적음 + 아레나 |
| Higgsfield Genjutsu | 1 | 1 | 동작 생성이 아니라 영상 편집 도구다. 2~4일 대기, 월 €59 | 적음(Reddit 2차 인용) |
| Uthana (텍스트→모션 3.0 / Locomotion / 영상→모션) | 4 | 1 | 뼈대 데이터가 바로 나오고 반복용 걸음 사이클이 된다. 2족 전용, 3.0은 제한 공개 | vendor 위주 |
| Rokoko Vision 3.0 + 텍스트→모션 | 3 | 1 | 싸고(월 $10) Studio 정리 도구가 있다. 손가락 없음, 텍스트→모션은 실험 단계 | 적음 + vendor |
| QuickMagic | 4 | 1 | 독립 리뷰에서 발 접지가 우수했다. 무료 50초/월. 영상→모캡 변환 단계로 최적 | 적음(독립 리뷰 2) |
| Tripo 리깅/애니메이션 | 3.5 | 3 | 실측에서 리타깃이 가장 깔끔했다. v2.5는 6족·8족·조류 리깅. 생물 프리셋 품질은 미확인 | 적음 + vendor |
| Meshy 애니메이트 | 3 | 2 | 프리셋이 가장 많다. 엉덩이 축 오차로 발 미끄러짐. 4족은 개 템플릿뿐 | 적음 |
| Anything World | 2.5 | 3 | 4족·곤충·새 자동 리그와 걷기·달리기 프리셋. 뼈대 수동 조정 필요, 자료가 오래됨 | 적음(2023) |

## 4. 저비용 추천 조합

**몸 동작 (인간형·스타일 캐릭터)**
1. **Uthana Locomotion / 텍스트→모션.** 영상을 거치지 않고 반복용 걷기·달리기 뼈대가 바로 나온다(초 단위 과금).
2. **QuickMagic 무료/저가 + 사람 레퍼런스 영상.** 직접 찍은 영상이나 저가 생성 영상을 모캡으로 바꾼다. 발 접지 평가가 가장 좋다.
3. **MiniMax H3 또는 Vidu Q4 이미지→영상.** 시각 레퍼런스가 필요할 때 쓴다(약 $5/분으로 Kling Pro의 1/4). 레퍼런스 동작을 정확히 복제해야 하면 Kling 3.0 Motion Control Standard를 쓴다.
- 치비·큰 머리 캐릭터 주의: 뼈대 기반 영상 전이(Kling Motion Control, Wan Animate)는 몸을 늘린다는 커뮤니티 보고가 있다. 그래서 **뼈대 데이터 → 우리 리그로 리타깃**하는 경로(1, 2)가 비율을 지키기에 더 안전하다. (추론 + community)

**몬스터 (비인간형)**
1. **Tripo 리깅 v2.5 (4족·6족·8족·조류·뱀형)과 그 프리셋.** 이미 쓰는 파이프라인이다. 생물 프리셋 목록과 품질은 소액으로 직접 확인해야 한다.
2. **Anything World.** 4족·곤충·새 자동 리그와 기본 이동 프리셋. 무료 등급으로 시험.
3. **MiniMax H3 / Vidu Q4 이미지→영상**을 "눈으로 참고하는 용도"로만 쓴다. 다리 개수 오류가 흔하므로 여러 개 생성해서 고르고, 키 포즈는 Blender나 Cascadeur에서 직접 잡는다. 영상→모캡 도구는 비인간형을 처리하지 못한다.
