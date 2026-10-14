# 영상 모델 사용자 평판 조사: 얼굴, 표정, 대사 참조 클립용 (2026-10-14)

목적: 3D 게임 캐릭터 1장(카툰, 애니, 세미리얼, 리얼) → 얼굴/표정/대사 **참조 클립** 생성.
보는 항목: 이미지 1장 정체성 유지, 화풍 유지(애니→실사 드리프트), 표정 범위("o/u/a" 입모양, 웃음, 찡그림), 립싱크(한국어), 정면 카메라 고정, 아티팩트(치아, 입 녹음, 눈), 재시도율, 싸고 쓸 만한 등급.

## 조사 방법과 한계 (먼저 읽기)

- 웹 검색/열람 약 25회. 가입, 구매, 다운로드, 로그인 없음.
- **Reddit은 이 도구로 직접 열람 불가** (reddit.com 차단). X/Discord도 직접 못 봄. 그래서 커뮤니티 의견은 대부분 "블로그가 인용한 Reddit" 같은 2차 인용이다.
- 검색 결과의 대다수가 **API 재판매사 블로그**(Atlas Cloud, Evolink, PixVerse, Pollo, Dreamina 등)다. 이해관계가 있으므로 [3rd-party blog]로 표시하고 가중치를 낮췄다.
- 가장 믿을 만한 독립 근거: **Artificial Analysis 영상 아레나**(블라인드 투표 Elo, 수천~만 표)와 **Curious Refuge 비교 테스트**, **akitaonrails 체험기**. 단, 아레나는 "전체 품질" 순위이지 얼굴/립싱크 전용 순위가 아니다.
- 애니/카툰 캐릭터에 대해 **입모양(o/u/a)을 프레임 단위로 검사한 공개 테스트는 하나도 못 찾았다.** 이 항목은 우리가 직접 시험해야 한다.
- 표기: [community] 사용자 발언, [independent test] 판매 이해관계 없는 실험/아레나, [vendor] 모델 제작사, [3rd-party blog] 재판매사/제휴 블로그.

---

## 0. 공통 근거: Artificial Analysis 이미지→영상 아레나 (오디오 포함)

AA-Video-I2V v1.1, 오디오 포함 보드 (2026-10 열람) [independent test]
출처: https://artificialanalysis.ai/video/leaderboard/image-to-video

| 모델 | Elo | API 가격/분 (1080p) |
|---|---|---|
| MiniMax H3 (768p) | 1130 | $5.40 |
| Vidu Q4 Preview | 1129 | $5.04 |
| Gemini Omni Flash 1.1 | 1126 | $9.12 |
| Seedance 2.5 | 1120 | $24.60 |
| Wan 3.0 | 1119 | $12.00 |
| MiniMax H3 Max | 1116 | $5.76 |
| Seedance 2.0 | 1113 | $22.45 |
| Veo 3.1 | 1029 | $24.00 |
| Veo 3.1 Fast | 1013 | $9.00 |
| Kling 3.0 Omni 1080p Pro | 1003 | $16.80 |
| Kling 3.0 1080p Pro | 1000 (기준점) | $20.16 |

- 신뢰구간은 약 ±11~13. 상위 7개(1113~1130)는 사실상 동률권. Veo/Kling은 그 아래 100점 차로 뚜렷이 낮다. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- v1.0 보드(2026-10-10 스냅샷)에서는 H3 Max 1195 1위, H3 1181, Vidu Q4 Preview 1179, Gemini Omni Flash 1178, Seedance 2.0 720p 1176, Wan 3.0 1164. 상위 6개가 20점 안. 보드 버전마다 Elo 척도가 달라 숫자끼리 비교하면 안 됨. [3rd-party blog] https://www.orcarouter.ai/blog/hidream-o1-video-1-0-leaderboard-debut-api-gap
- 목록에 없음: Veo 3.1 Lite, Seedance 2.0 Fast, H3 Max Turbo, Hailuo 2.3, Kling Avatar 2, Hedra, Higgsfield Speak.

---

## 1. Kling 3.0 (Std / Pro)

- 정체성: Elements 3.0이 3~8초 참조 영상으로 외형과 목소리를 고정. [3rd-party blog] https://www.dzine.ai/blog/kling-3-0-vs-kling-2-6/
- 정체성: r/KlingAI_Videos 스레드에서 "프롬프트 잠그기(같은 묘사 키워드 반복)"가 일관성의 핵심이라는 의견 (2차 인용). [community, 2차] https://www.atlascloud.ai/blog/guides/how-to-use-kling-3.0-for-character-consistency
- 정체성: 한 캐릭터로 5클립 시험 → "완벽하진 않지만 짧은 이야기에 쓸 만큼 일관". [3rd-party blog] https://www.atlascloud.ai/blog/kling-3.0-review-features-pricing-ai-alternatives
- 립싱크: 사용자 인용 "Kling 립싱크는 5초 넘는 클립에선 전혀 좋지 않다" (출처 게시판 불명). [community, 2차] https://soravideo.art/blog/kling-3-ai-video-model
- 립싱크 언어: 한국어 포함 5개 언어, 언어별 음소→비셈 튜닝 주장. [3rd-party blog] https://www.atlascloud.ai/blog/guides/kling-ai-lip-sync
- 아티팩트: 텍스트 깨짐, **정면이 아닌 얼굴의 왜곡**이 흔한 문제. [3rd-party blog] https://www.atlascloud.ai/blog/guides/kling-ai-lip-sync
- 아레나: 오디오 포함 I2V에서 기준점 1000, 상위권보다 약 110~130 낮음, 가격은 $20.16/분으로 비쌈. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- 화풍 유지(애니/카툰): 직접 근거 못 찾음.
- **평점 3/5** — 모션과 참조 고정은 좋다는 평이 많지만 립싱크는 5초 넘으면 약하고 아레나 점수 대비 비쌈.
- 근거 강도: 보통 (재판매사 블로그 다수, 커뮤니티 2차 인용 1~2건, 아레나 1건).

## 2. Kling Omni 3 (3.0 Omni, 첫/끝 프레임)

- 첫/끝 프레임 입력(start_image, end_image) 지원. [3rd-party blog] https://apiframe.ai/guides/kling-3-0-guide , [vendor 워크플로] https://comfy.org/workflows/api_kling_v3_flf2v-351e79d06ae1/
- 정체성: "샷마다 얼굴이 바뀌는 AI 얼굴 드리프트를 Omni가 고친다"는 첫인상 (통제 실험 아님). [community 체험기] https://medium.com/@codeandbird/kling-3-0-omni-first-impressions-best-ai-video-yet-a87d6d6b82e2
- 가장 많이 보고된 문제: **인물 복제, 프롬프트에 없는 사람 추가** 환각. 재생성 때문에 실질 단가가 표면 단가보다 높음. [3rd-party blog] https://soravideo.art/blog/kling-3-omni-guide
- 긴 Omni 클립의 립싱크는 여전히 불안정. [3rd-party blog] https://soravideo.art/blog/kling-3-omni-guide
- 아레나: 1003, $16.80/분. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- 우리 용도 메모: 첫 프레임=중립, 끝 프레임=같은 중립으로 주면 "중립→표정→중립" 루프를 강제할 수 있음 (우리 추론, 출처 없음). 애니↔실사 같은 다른 화풍 끝점 테스트는 공개된 것이 없음.
- **평점 3/5** — 첫/끝 프레임 고정은 우리 용도에 맞지만 환각 재시도와 립싱크 불안정 보고.
- 근거 강도: 적음.

## 3. Kling Lipsync (기존 영상에 입만 맞추기)

- 오래된 기사: **사람 얼굴에서만 동작**, 평평한 사람형 얼굴의 동물/외계인 정도까지만. [3rd-party blog, 구버전] https://getcoai.com/news/ai-video-creation-transformed-by-klings-new-lip-syncing-feature
- 경쟁사 비교: 비인간형 이미지는 **얼굴을 못 찾아 립싱크 시도조차 못 함** (Kling 버전 불명). [3rd-party blog, 경쟁사] https://lemonslice.com/blog/lemonslice-vs-kling
- 정면이 아닌 얼굴 왜곡, 얼굴이 작거나 가려지면 실패. 근접 촬영과 사람형 캐릭터에서 가장 좋음. [3rd-party blog] https://www.atlascloud.ai/blog/guides/kling-ai-lip-sync
- **평점 2/5** — 카툰/애니 얼굴 인식 실패 보고가 있고, 2단계 후처리용으로만 의미.
- 근거 강도: 적음 (경쟁사/구버전 위주).

## 4. Kling AI Avatar 2 (Std / Pro) 및 "Kling Speak"

- 제작사 계열 논문: 애니, 카툰, 스타일 캐릭터로 일반화된다고 보고 (2025 원 논문, Avatar 2 전용 평가 아님). [vendor] https://arxiv.org/pdf/2509.09595
- v2는 카툰/일러스트 캐릭터 지원, v1보다 립싱크 크게 향상 주장. [3rd-party blog] https://fal.ai/learn/devs/kling-avatar-v2-vs-v1-evolution-ai-powered-avatar-generation
- Standard 티어: 사람 또는 카툰 캐릭터. [3rd-party blog] https://runware.ai/models/klingai-avatar-2-0-standard
- 손 안정성 향상, 최대 5분, 립싱크 정확도 향상. [3rd-party blog] https://www.hedra.com/models/video/kling/ai-avatar-v2-standard
- 모션 자유도가 커서 **제스처와 정체성 변동**이 생길 수 있음. 손을 입에서 떨어뜨리고 치아, 입술, 눈, 배경을 프레임 단위로 확인하라고 권장. [3rd-party blog] https://www.media.io/comparison/kling-ai-avatar.html
- (Kling v3 아바타 립싱크) 영어/중국어 매우 좋음, 성조 언어와 노래에서 정확도 하락. **눈 깜빡임이 오디오와 무관하게 고정 간격**이라 로봇 같아 보일 수 있음. 머리와 몸은 정적(= 카메라 고정에는 유리). 30초 넘으면 정체성 드리프트 증가. [3rd-party blog, 판매사 대표 작성] https://blog.picassoia.com/kling-v3-18-avatar-lipsync-what-you-actually-get
- "Kling Speak"는 Higgsfield에서 쓰는 이름. 밝은 정면 얼굴, 눈 뜨고, 손/마이크/선글라스 가림 금지 권장, 1회 최대 약 1분. 공식 매핑 미확인. [3rd-party blog] https://higgsfield.ai/blog/Meet-KlingAI-Avatar-2.0-AI-Talking-Avatars
- **평점 3/5** — 오디오 구동, 정면 고정, 머리 정적이라 "입모양 참조"에 구조적으로 맞지만, 카툰/애니 얼굴 인식 실패 보고와 고정 깜빡임, 독립 테스트 부재.
- 근거 강도: 적음 (대부분 vendor/재판매사).

## 5. Google Veo 3.1 (Lite / Fast / Standard)

- 대사 위주 작업에 깔끔한 립싱크, 단 비용이 높음. [community, 크리에이터 커뮤니티] https://www.skool.com/mk-ads-1846/veo-31-video-generation-review-when-to-use-it
- 실사 이미지 TTS 립싱크 1회 시험에서 다른 플랫폼보다 못해 보였음, 매 실행 결과가 달라 운일 수 있음. [community 체험기] https://ndurner.substack.com/p/google-veo-31
- 클립마다 **목소리가 바뀜**, 이어 붙이면 배경음 끊김. [3rd-party blog] https://www.glbgpt.com/hub/jp/how-to-make-characters-speak-in-veo-3-1-the-ultimate-guide-to-dialogue-audio-lip-sync/
- 화풍: 지브리풍 시험에서 빛과 카메라는 좋으나 붓터치가 과하게 매끈, **"애니 충실도보다 애니메이션된 실사"** 쪽으로 기움. [3rd-party blog] https://www.goenhance.ai/de/blog/veo-3-1-vs-sora-2-review
- 화풍: 애니 키프레임 1장 시험에서 배경이 끝으로 갈수록 **사진 같은 경기장으로 드리프트**(3D/실사 금지 네거티브 프롬프트에도), 캐릭터는 "모델은 맞지만 다른 그림"으로 다시 그려짐. 8초 $3.20. [3rd-party blog, 직접 생성] https://www.atlascloud.ai/blog/guides/minimax-h3-vs-veo-31-anime
- 프롬프트가 구체적이지 않으면 결과 폭이 넓고 일부 맥락에서 품질 후퇴. [community 체험기] https://theaifilmmaker.substack.com/p/testing-the-limits-of-ai-video-with
- Fast: 대부분 시청자가 Standard와 구분 못 했다는 주장(방법 불명). [3rd-party blog] https://www.mindstudio.ai/blog/what-is-google-veo-3-1-fast-video
- Lite: 약 4~6초, 단순한 오디오에서 안정적, 립싱크는 "기본" 수준, 대사 적은 콘텐츠용. [3rd-party blog] https://www.elser.ai/m/veo/veo-3-1-lite
- Lite 가격 약 $0.05/초(720p), Fast $0.15/초. [3rd-party blog] https://www.cometapi.com/what-is-google-veo-3-1-lite/ , https://theplanettools.ai/tools/veo-3-1
- 아레나: Veo 3.1 1029, Fast 1013 (상위권보다 약 90~100 낮음). [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- **평점: Standard 3/5, Fast 3/5, Lite 2/5** — 실사/세미리얼 대사에는 강하지만 애니/카툰은 실사로 끌려간다는 보고가 2건, 아레나 하위, Standard는 비쌈. Lite는 초안용.
- 근거 강도: 보통 (체험기 몇 건 + 아레나), Lite는 적음.

## 6. Gemini Omni 1.1 Flash

- 아레나: 오디오 포함 I2V 3위 1126, $9.12/분. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- 30개 이상 출력 시험: **단일 화자 립싱크는 약 6~7초까지 정확**, 그 뒤 드리프트. 2인 장면에서 대사를 섞음 (1.1 전용 여부 불명). [3rd-party blog] https://invideo.io/faq/how-long-can-ai-lip-sync-stay-accurate-before-it-breaks/
- 모델 카드도 "편집 전반의 완전한 일관성 유지"는 미해결이라고 인정. [3rd-party blog, 모델 카드 인용] https://promptslove.com/blog/gemini-omni-1-1-flash-review/
- 3초 이하 참조 클립 입력, 장면 확장 시 이전 10초 참조. [3rd-party blog] https://www.mindstudio.ai/blog/gemini-omni-1-1-flash-video-model
- AI Studio 경로에서 내부 서버 오류 반복, Flow(Ultra 요금제)에선 원활. [community 체험기] https://promptslove.com/blog/gemini-omni-1-1-flash-review/
- 화풍 유지, 입모양: 근거 없음.
- **평점 3.5/5** — 아레나 상위이고 6초짜리 참조 클립엔 충분하지만 얼굴/애니 전용 근거가 없고 접근성 문제.
- 근거 강도: 적음 (아레나 + 판매사 블로그).

## 7. Seedance 2.0 / 2.0 Fast / 2.5 (ByteDance)

- **독립 3자 비교(Wan 3.0, MiniMax H3, Seedance 2.0) 립싱크 시험에서 Seedance 2.0이 "가장 강한 립싱크"**. [independent test] https://curiousrefuge.com/blog/wan3-review
- 체험기: **애니 아바타 정지 이미지 1장으로 립싱크 시험 시 외형 유지**, 표정에 "생기가 있음", 립싱크는 "말을 꽤 잘 따라감". 단 모션/카메라는 참조에서 눈에 띄게 드리프트, **쓸 만한 장면 1개당 3~5회 재생성** 추정. [community 체험기] https://akitaonrails.com/en/2026/04/15/seedance-2-0-public-launch-first-impressions/
- 같은 체험기: **실존 인물 얼굴 참조 차단**, 대형 IP 캐릭터 필터. (리얼 스타일 캐릭터가 "실존 얼굴"로 오인될 위험, 우리 추론) [community 체험기] https://akitaonrails.com/en/2026/04/15/seedance-2-0-public-launch-first-impressions/ , 사람 얼굴 참조 제한 언급 [3rd-party docs] https://docs.pletor.ai/models/video-models/seedance-2.0
- 립싱크 조건: **미디엄 클로즈업 + 고정 카메라**가 최선, 옆얼굴 불안정, 한 줄 5~10단어, "고개 끄덕/돌리기" 지시는 립싱크와 충돌하니 빼라. 중국어 가장 안정, 영어 근소 2위, **일본어/한국어는 긴 문장에서 드리프트** (자체 시험 + 더우인 크리에이터 보고). [3rd-party blog] https://www.cutout.pro/learn/?p=2903
- 다인 립싱크와 가끔의 오디오 왜곡은 공식 기술평가에서도 미해결로 인정. [3rd-party blog, 기술보고 인용] https://www.cutout.pro/learn/?p=2903 , 기술보고서 [vendor] https://arxiv.org/pdf/2604.14148
- 2D 평면 애니는 선과 단색에 깜빡임이 숨을 곳이 없어 스타일라이즈드 3D보다 어려움. 9장 참조로 캐릭터 고정. [3rd-party blog] https://www.atlascloud.ai/blog/guides/seedance-2.0-animation-2d
- 영어/중국어 립싱크 자연스러움 (Jimeng 웹 UI 시험). [3rd-party blog] https://evolink.ai/blog/seedance-2-review-best-ai-video-generator-2026
- **2.0 Fast**: Standard는 조명/질감 디테일, Fast는 저가·고처리량. [3rd-party blog] https://www.atlascloud.ai/ko/models/bytedance/seedance-2.0-fast/image-to-video , "대부분 용도에 충분" [3rd-party docs] https://docs.pletor.ai/models/video-models/seedance-2.0 . Fast vs Standard 얼굴/립싱크 직접 비교 테스트는 못 찾음. Mini vs Fast 비교에서 사람 중심 클립의 캐릭터 안정성은 Fast가 낫다고 평가. [3rd-party blog] https://kinovi.ai/blogs/seedance-2-0-mini-vs-seedance-2-0-fast-which-one-should-you-use
- **2.5**: Wan 3.0보다 "전반적 감정 연기가 더 강함", 다만 한 시험에선 아티팩트가 더 많았고 가격이 약 4배. [independent test] https://curiousrefuge.com/blog/wan3-review
- **2.5 한국어**: 한국어 장면 4개 API 실생성, 대사/환경음/입 움직임 한 번에 생성, 한글로 쓰라고 권장(로마자는 억양 손실, 추론). 720p 약 $0.238/초. 립싱크 품질 평가는 없음. [3rd-party blog, 직접 생성] https://blog.segmind.com/seedance-2-5-for-korean-developers-native-korean-audio-local-context-and-what-it-actually-costs/
- 구독 경로: Standard 요금제 2,500크레딧, 10초당 6크레딧, 재시도 포함 월 80~140개 클립 추정. [community 체험기] https://akitaonrails.com/en/2026/04/15/seedance-2-0-public-launch-first-impressions/
- 아레나: 2.5 1120 ($24.60/분), 2.0 1113 ($22.45/분). [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- **평점: 2.0 4/5, 2.0 Fast 3.5/5, 2.5 4/5(비쌈)** — 독립 비교에서 립싱크 1위, 애니 아바타 1장 유지 보고, 고정 카메라 권장 조건이 우리 용도와 일치. 단점은 실존얼굴 필터, 3~5회 재시도, 한국어 긴 문장 드리프트, API 단가.
- 근거 강도: **많음** (독립 테스트 1, 체험기 1, 블로그 다수, 아레나). Fast는 적음.

## 8. MiniMax H3 / H3 Max / H3 Max Turbo, Hailuo 2.3

- 아레나: H3 768p **1130 (오디오 포함 I2V 1위권)** $5.40/분, H3 Max 1116 $5.76/분. v1.0 보드에선 H3 Max 1195 1위. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video , https://www.orcarouter.ai/blog/hidream-o1-video-1-0-leaderboard-debut-api-gap
- 애니 키프레임 1장 직접 시험(1테이크): **H3는 평면 셀 셰이딩 유지, 3D 드리프트 없음**, 8초 내내 같은 얼굴/머리/의상. 가타카나 정확. 8초 약 $1.12 (Veo $3.20). 단 생성 447초 (Veo 152초). [3rd-party blog, 직접 생성] https://www.atlascloud.ai/blog/guides/minimax-h3-vs-veo-31-anime
- 독립 립싱크 시험: **H3가 원본 오디오에 없는 노래 구간을 만들어냄** (오디오 환각). [independent test] https://curiousrefuge.com/blog/wan3-review
- 자사 모델 중 **H3 Max의 reference-to-video만 립싱크 대사에 버팀** → "고정된 캐릭터가 카메라 앞에서 대사" 용도. [3rd-party docs] https://help.scenario.com/articles/8094765856-minimax-hailuo-video-the-essentials
- 5초 클립에 약 4분, 결과는 일관되지만 워터마크, 그대로 쓰기엔 부족. 최대 9개 혼합 참조. 오픈 웨이트. [3rd-party blog] https://dreamina.capcut.com/resource/minimax-h3-review
- **H3 Max Turbo**: 사용자/독립 평가 못 찾음.
- **Hailuo 2.3**: 미세 표정, 자연스러운 실사 얼굴 연기, 애니/일러스트/게임 CG 지원 강화 (제작사 주장). [vendor] https://www.minimax.io/news/minimax-hailuo-23 . 긴 샷에서도 얼굴 안정 [3rd-party blog, 재판매] https://tokenmix.ai/blog/hailuo-2-3-video-review-2026 . **카메라가 도는 동작에서 얼굴이 변함** [3rd-party blog] https://yespress.io/hailuo-ai . 비교 가이드는 Hailuo를 시네마틱 인물용으로, 애니는 다른 도구로 배정 [3rd-party blog] https://magichour.ai/blog/hailuo-02-cinematic-video-model-guide-minimax-flux-ai . (Hailuo 2.3은 무음 영상 모델로 알고 있으나 이번 조사에서 출처 확인 못 함 → 표정 전용 클립 후보로만.)
- **평점: H3 4/5, H3 Max 4/5, H3 Max Turbo 미평가(근거 없음), Hailuo 2.3 3/5** — H3는 아레나 최상위 + 최저가권 + 애니 셀 셰이딩 유지 보고. 단점은 느림, 노래 오디오 환각, 입모양 전용 시험 없음.
- 근거 강도: H3/H3 Max 보통 (아레나 대량 표 + 직접생성 블로그 1 + 독립 시험 1), Hailuo 2.3 적음(대부분 vendor).

## 9. Wan 3.0 (Alibaba)

- 독립 비교: 카페 대화 장면에서 **단일 생성으로도 얼굴 연기에 "놀라운 감정 울림"**. 단 배경 연속성 문제, **피부 질감 과다 디테일**. [independent test] https://curiousrefuge.com/blog/wan3-review
- 같은 시험: **립싱크가 가장 큰 약점 중 하나**, 캐릭터 이미지+노래에서 입을 오디오에 못 맞춤. 추격 장면에선 캐릭터 일관성 붕괴. Seedance 2.5보다 약 4배 쌈, "실용적 작업마" 평가. [independent test] https://curiousrefuge.com/blog/wan3-review
- 반대 의견: 뮤직비디오 시험에서 립싱크 "정확해 보임" (판매사). [3rd-party blog] https://pollo.ai/de/hub/wan-3-0-review
- 대사 립싱크는 Veo 3.1이 앞선다는 비교. [3rd-party blog] https://www.glbgpt.com/hub/jp/wan-3-0-vs-kling-3-0/
- 2~30초, 1080p, 첫/끝 프레임, 참조 이미지 10장. 프롬프트 따옴표 대사만으로 음성+입 생성, 얼굴 근접 유지 권장. [3rd-party docs] https://help.scenario.com/articles/4856166365-wan-3-0-the-essentials
- 애니: 워크플로 글은 실제 생성 없이 작성, 12샷째에 의상 디테일과 눈이 드리프트한다고 경고. [3rd-party blog] https://wavespeed.ai/blog/ai-workflows/wan-3-0-anime-video-workflow/
- 아레나: 1119, $12.00/분. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- **평점 3/5** — 표정 감정은 좋지만 독립 시험에서 립싱크가 약하고 과다 피부 디테일은 카툰/애니에 불리.
- 근거 강도: 보통 (독립 시험 1 + 블로그).

## 10. Vidu Q4 (Preview)

- 2026-10-07 공개된 Preview. [vendor 보도자료] https://technologymagazine.com/globenewswire/3376813
- 아레나: 오디오 포함 I2V **2위 1129, $5.04/분 (조사 대상 중 최저가)**. [independent test] https://artificialanalysis.ai/video/leaderboard/image-to-video
- 최대 12개 캐릭터/제품/장소 일관 유지, 얼굴/의상/목소리 유지 주장. [3rd-party blog] https://morphic.com/resources/models/vidu-q4 . 참조 음성으로 캐릭터 목소리 일관. [vendor] https://technologymagazine.com/globenewswire/3376813
- 사용자 리뷰 한 줄: "움직일 때 얼굴 일관성이 조금 더 필요" (Pollo 플랫폼 일반 리뷰, Q4 전용 아님). [community, 약함] https://pollo.ai/ko/m/vidu-q4
- 애니 데모는 Q3 것. [vendor/재판매] https://www.media.io/ai/jp/image-to-video/vidu-q4
- **평점 3.5/5 (잠정)** — 아레나 2위에 최저가라 시험 가치가 크지만 얼굴/립싱크/애니 독립 근거가 전혀 없음.
- 근거 강도: 아레나만 (얼굴 전용 근거 없음).

## 11. Higgsfield Speak 2.0

- 영화인 실사용 비교(vs HeyGen Avatar 4): 표현력 있고 시네마틱하나 모션이 느슨, **입 정렬이 약점**, 정적 프레이밍과 배경 무움직임. **외계인/비인간에서 더 잘됨**. (본문 유료, 검색 요약 기준, 2025-06) [community 체험기] https://creativepossible.substack.com/p/which-ai-lip-sync-tool-should-you
- 유튜브 비교 요약(기계 생성 노트): 주 피사체만 싱크, **입술과 치아가 흐려지거나 모양이 변함**, 최대 15초. [community, 낮은 신뢰] https://lilys.ai/ms/notes/nano-banana-pro-20260203/higgsfield-ai-lip-sync-comparison (본문 재열람 실패, 검색 스니펫 기준)
- 제작사 주장 "픽셀 단위 싱크". [vendor] https://higgsfield.ai/blog/19fPMcKM5T0c8o8HQGdgyW
- **평점 2/5** — 고정 프레이밍은 맞지만 입/치아 흐림 보고가 반복되어 입모양 참조용으로 부적합.
- 근거 강도: 적음.

## 12. Hedra Character-3

- 정지 초상 1장 + 오디오 → 말하는 아바타, 예시에 일러스트와 클레이 캐릭터. [vendor] https://www.hedra.com/models/video/hedra/character-3
- 비사진 화풍을 비즈니스 아바타보다 잘 처리. 단 **립싱크 품질이 오디오에 좌우**(잡음/억양 약함), **클로즈업과 미묘한 표정이 덜 설득력**. (제휴 수수료 고지) [3rd-party blog] https://neuronfeed.com/reviews/hedra-review
- 2026-02 후속 Omnia 출시, Character-3는 고정 카메라 아바타용으로 유지. [3rd-party docs] https://docs.pletor.ai/ai-model-library/video-models/hedra-character-3
- 사실감보다 표정 애니메이션 우선인 앉은 캐릭터 대화 영상에 추천. [3rd-party, 보도자료형] https://www.barchart.com/story/news/37179827/best-ai-lip-sync-tools-for-2026-how-to-choose-the-right
- **평점 3/5** — 고정 카메라 + 스타일 캐릭터 지원은 맞지만 클로즈업/미세 표정 약하다는 평, 구세대 모델.
- 근거 강도: 적음.

---

## 요약 표

| 모델 | 평점 | 칭찬 | 불만 | 근거 |
|---|---|---|---|---|
| Kling 3.0 Std/Pro | 3 | 참조 고정, 모션 | 5초 넘으면 립싱크 약함, 옆얼굴 왜곡, 비쌈 | 보통 |
| Kling Omni 3 | 3 | 첫/끝 프레임, 정체성 | 인물 환각, 재시도 | 적음 |
| Kling Lipsync | 2 | 2단계 후처리 | 카툰 얼굴 인식 실패 | 적음 |
| Kling Avatar 2 / Speak | 3 | 오디오 구동, 머리 정적 | 고정 깜빡임, 카툰 인식 불확실 | 적음(vendor) |
| Veo 3.1 Std / Fast | 3 / 3 | 실사 대사 립싱크 | 애니가 실사로 드리프트, 아레나 하위 | 보통 |
| Veo 3.1 Lite | 2 | 매우 쌈 | 기본 립싱크, 4~6초 | 적음 |
| Gemini Omni 1.1 Flash | 3.5 | 아레나 3위 | 6~7초 후 립싱크 드리프트 | 적음 |
| Seedance 2.0 | 4 | 독립 시험 립싱크 1위, 애니 1장 유지 | 실존얼굴 필터, 3~5회 재시도, 한국어 긴 문장 | 많음 |
| Seedance 2.0 Fast | 3.5 | 쌈, "대부분 충분" | 직접 비교 없음 | 적음 |
| Seedance 2.5 | 4 | 감정 연기 최강, 한국어 오디오 | 비쌈, 아티팩트 보고 | 보통 |
| MiniMax H3 | 4 | 아레나 1위권, 최저가권, 셀 셰이딩 유지 | 느림, 노래 오디오 환각 | 보통 |
| MiniMax H3 Max | 4 | ref-to-video 대사 유지 | 느림 | 보통 |
| H3 Max Turbo | - | - | 근거 없음 | 없음 |
| Hailuo 2.3 | 3 | 미세 표정(vendor) | 카메라 회전 시 얼굴 변화 | 적음 |
| Wan 3.0 | 3 | 감정 표현 | 립싱크 약함, 피부 과다 디테일 | 보통 |
| Vidu Q4 Preview | 3.5 | 아레나 2위, 최저가 | 얼굴 독립 근거 없음 | 아레나만 |
| Higgsfield Speak 2.0 | 2 | 비인간 캐릭터 | 입/치아 흐림, 입 정렬 약함 | 적음 |
| Hedra Character-3 | 3 | 스타일 캐릭터, 고정 카메라 | 클로즈업/미세표정 약함 | 적음 |

## 우리 용도 저가 추천 3개

1. **MiniMax H3 (768p)** — 아레나 오디오 I2V 1위권에 $5.40/분, 애니 셀 셰이딩 유지 시험 보고. 오디오는 우리가 준 것만 쓰는지 확인 필요.
2. **Seedance 2.0 (초안은 Fast)** — 독립 시험 립싱크 1위, 애니 아바타 1장 정체성 유지 보고, "고정 카메라 미디엄 클로즈업" 권장 조건이 우리 촬영 조건과 같음. 리얼 스타일은 실존얼굴 필터에 걸리는지 먼저 확인.
3. **Kling AI Avatar 2 Standard** — 오디오 구동, 머리 정적이라 정면 고정 입모양(o/u/a) 클립에 구조적으로 맞음. 카툰/애니 얼굴 인식 실패 여부를 1장씩 먼저 확인. (와일드카드: Vidu Q4 Preview, 최저가 + 아레나 2위지만 얼굴 근거 없음)

## 우리가 직접 확인해야 할 것 (공개 근거 없음)

- 4가지 화풍별 "o/u/a" 모음 유지 프레임 수, 웃음/찡그림 분리 표현.
- 한국어 짧은 대사(5~10단어) 입모양 정확도.
- 정면 고정 카메라 지시 준수율, 재시도율(모델당 같은 입력 3~5회).
- 치아/혀 깜빡임, 눈 깜빡임 패턴.
