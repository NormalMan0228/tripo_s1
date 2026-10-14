# 한국·일본 대형 커뮤니티 반응 조사: AI 영상·모션 도구 (2026-10-14)

목적: 3D 게임 캐릭터(카툰, 애니, 반실사, 실사)와 몬스터의 **표정·몸동작 참고 클립**을 만들 때 쓸 도구에 대해, 한국·일본 사용자들이 실제로 뭐라고 하는지 모은다.

## 0. 조사 방법과 한계 (먼저 읽기)

- 검색·열람 약 30회. 읽기만 했고 가입·로그인·게시·다운로드는 하지 않았다. Reddit은 지시대로 제외(미러·우회 포함).
- **네이버 블로그·카페는 크롤러 차단으로 검색 자체가 막혔다.** 5ch는 검색 결과에 한 번도 잡히지 않았다. 니코니코도 관련 결과가 없었다. 일본 쪽 근거는 거의 전부 note.com, Zenn, Qiita, 유튜브 제목이다.
- 디시인사이드 글은 본문만 읽힌다. 댓글 수는 표시되지만 댓글 내용은 "전체 댓글 0개"로 나와 읽을 수 없었다. 그래서 디시의 반응은 **글쓴이 1명의 의견**으로 센다.
- 표시 규칙
  - [원문확인] 내가 직접 페이지를 열어 확인한 내용
  - [검색요약] 검색 결과의 요약·발췌만 본 내용(원문 미열람, 오독 가능성 있음)
  - 출처 태그: [커뮤니티-KR], [커뮤니티-JP], [블로그], [유튜브]
- note.com의 많은 글은 개인 크리에이터의 홍보성 검증이다(특히 CreativeEdge CL+는 유료 강의·멤버십 운영자). 블로그로 분류했다.
- **질문의 핵심 항목 중 근거가 거의 없는 것:** 몬스터·인외 캐릭터, 한국어 립싱크(최신 버전), Kling Omni 3, Vidu Q4, Seedance 2.0 Fast 단독 평가, Veo 3.1 Lite, Uthana. 이 항목들은 "근거 없음"으로 적었다.
- 글 대부분이 2026년 2~9월 것이다. 하이루오·Veo3 관련 한국 글 일부는 2024~2025년 글이라 현재 버전과 다르다.

## 1. 요약표

| 도구 | KR 분위기 | JP 분위기 | 가장 많이 나온 칭찬 | 가장 많이 나온 불만 | 본 글 수(대략, 독립) |
|---|---|---|---|---|---|
| Seedance 2.0 / 2.5 (Dreamina, 즉몽, CapCut) | 혼합(초기 열광 → 3월 이후 너프·가격 불만) | 긍정(애니는 1위 평가 다수) | 애니 화풍 유지, 격한 동작에서도 덜 무너짐, 프롬프트 이해 | 크레딧 삭감, 재시도 4~5회 주장, 검열·실존 얼굴 차단, 품질 편차, 느린 생성, 한국어가 중국어처럼 들린다는 체감 | KR 약 15, JP 약 12 |
| Kling 3.0 / Omni 3 | 긍정 | 혼합 | 얼굴 유지, 멀티샷, 안정적 출력, 빠름(4초 영상 1분대) | 애니에서 발 미끄러짐·머리카락 굳음·빠른 동작 때 윤곽 붕괴, 매끈한 광택감 | KR 약 8, JP 약 8 (Omni 3 단독 평가는 0) |
| Kling Motion Control 2.6 / 3.0 | 긍정(제한적) | 긍정 | 각도가 바뀌어도 얼굴 유지, 3.0에서 표정 풍부, 애니 캐릭터에도 동작 이식 | 격한 동작·급격한 카메라에 붕괴, 1초짜리 빠른 애니 컷 재현 불가, 한 사람 동작만, 참조 영상에 따라 오류 | KR 약 3, JP 약 8 |
| Kling Lip Sync | 혼합(오래된 글) | 혼합~부정 | 기존 영상의 입만 바꿈, 외부 음성 지원, 가격 쌈(1클립 약 66엔), 동물·원거리 컷에서 무난 | 입술~치아 붕괴(7개 중 7위), 무표정이면 입이 거의 안 벌어짐, 2인 화면에서 왼쪽만 말함 | KR 약 2, JP 약 4 |
| MiniMax H3 / Hailuo 2.3 | 근거 부족(하이루오 구버전 글만) | 긍정 | H3: 애니 윤곽·얼굴·머리 유지, 싸다(15초 60크레딧), 로컬 실행 가능 | 피부가 플라스틱 같음, 실사는 Seedance 2.5에 밀림. 하이루오 구버전은 얼굴 바뀜·AI 질감 | KR 약 3(구버전), JP 약 10 |
| Veo 3.1 (Fast/Lite) | 혼합 | 긍정(립싱크) | 립싱크 자연스러움 1위(실사), 음성 품질 Kling보다 낫다는 평 | 비쌈(1클립 약 430엔), 내 음성 업로드 불가, 대사를 바꿈, 한국어 출력 불안정(2025년 글) | KR 약 8, JP 약 4 (Lite 단독 평가 0) |
| Gemini Omni Flash (1.1) | 근거 없음 | 혼합 | 기존 영상의 대화형 부분 수정 | 일본어 음성 부자연, 물리(공·착지) 어색, 10초·720p, 장면 넘기면 캐릭터 일관성 붕괴, 수정 시 얼굴이 바뀜 | KR 0, JP 약 10 |
| Vidu Q4 | 근거 없음 | 근거 없음(Q2·Q3는 애니 호평) | (Q2·Q3) 애니 작화, 3D 느낌 감소 | Q4 자체 평가 없음 | KR 0, JP 0(Q4), 구버전 약 4 |
| Wan 3.0 | 중립(출시 소식 위주) | 긍정(가성비) | 30초 단일 샷, 싸다(Higgsfield 720p 10초 25크레딧) | 애니는 Seedance 2.5보다 아래, 표정·액션에 AI 티, 오픈소스 아님 | KR 약 3, JP 약 7 |
| Higgsfield (플랫폼) | 혼합~부정 | 혼합 | 여러 모델 한 곳, Seedance에서 얼굴 차단이 덜함 | 비싸다, 크레딧 가챠, 바이럴 마케팅, 검열 강화 | KR 약 7, JP 약 3 |
| Uthana | 근거 없음 | 근거 없음 | - | - | 0 |
| QuickMagic | 혼합 | 긍정 | 발 미끄러짐 거의 없음, 싸고 쉬움, 리그가 깔끔 | 팔·팔꿈치 회전 누락, 애니 품질엔 약 70% 수정 필요, 업데이트로 본 구조 변경 | KR 약 3, JP 약 7 |
| Rokoko Vision | 부정 | 혼합~부정 | 브라우저에서 바로, 짧은 프리비즈용 | 가림에 약함, 복잡한 동작 실패, 15초 제한, 품질 낮음·버그 | KR 약 1, JP 약 3 |
| Tripo 리그·애니메이션 | 근거 없음 | 긍정(제한적) | T포즈면 자동 리깅, 재시도로 개선 | 뼈대를 못 넣는 모델(로봇 등)은 애니 불가, 프리셋 12종뿐 | KR 0, JP 약 5 |
| Meshy 애니메이션 | 근거 없음 | 혼합 | 생성~리깅~애니 한 곳에서, 마커 리깅 쉬움, 라이브러리 많음 | 리그 정밀도 낮음·웨이트 수정 필요, 사람형·개형만, 회전+칼 휘두르기 같은 복합 동작 실패 | KR 0, JP 약 5 |

"본 글 수"는 이번 조사에서 제목이나 본문으로 확인한 서로 다른 글의 수다. 표본이 작으니 근거 강도로만 쓰자.

## 2. 도구별 상세

### 2.1 Seedance 2.0 / 2.0 Fast / 2.5 (Dreamina, 즉몽, CapCut, Higgsfield 경유)

**한국**
- 2026년 2월 출시 직후 디시 특이점 갤러리에서 한국어·검열 테스트 글이 조회 1.5만, 추천 28을 받았다. 글쓴이는 프롬프트가 거부되고 모델이 임의의 다른 영상을 만들었다고 썼다. 욕설 장면의 샤우팅은 Sora 2보다 낫다고 평가했다. 도로 위 차량 움직임은 비현실적이라고 지적했다. [원문확인][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=978617
- 2월 후기 글은 모든 언어를 중국어처럼 발음하는 것을 가장 큰 단점으로 꼽았다(한국어 대사 품질 관련, 1인 체감). [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=964621
- 루리웹 후기: 10초 액션 영상 10개 중 2~3개만 실패했고, 명령 이해력이 높다고 평가. [검색요약][커뮤니티-KR] https://bbs.ruliweb.com/userboard/board/700315/read/9250
- 3월 30일 문제 정리 글(디시): 공식 데모의 팔 3개, 손가락 오류, 박수 치는 손 뭉개짐, 지나치게 매끈한 피부("플라스틱"), **눈 깜빡임이 없다**는 지적, 출시 초기보다 프롬프트를 덜 따른다는 주장. 실패해도 크레딧이 돌아오지 않고 **평균 4~5회 재시도**가 필요하다는 주장, 15초 1편 약 $2.10 추정, 대기 2~10시간. 글쓴이가 해외 반응을 모은 정리글이라 독립 검증은 아니다. [원문확인][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=1079232
- 4월 8일 "크레딧 너프 사건" 글: Dreamina가 플랜 크레딧을 크게 깎았다. 일본 Advanced 플랜은 월 55,550 → 12,235(약 78% 감소)라고 정리했다. [원문확인][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=aicreate&no=62350
- 한국 정식 출시 후 가격 분석, 요금제별 포인트 정리 글이 여러 개 있다(가격 관심이 매우 높음). [검색요약][커뮤니티-KR] https://m.dcinside.com/board/thesingularity/1077503 , https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=1078650 , https://m.dcinside.com/board/thesingularity/1075647
- Higgsfield 경유 Seedance가 Dreamina보다 비싸지만 얼굴 감지 차단이 없다는 글. [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=aicreate&no=65019
- 립싱크 방법: 음원만 든 mp4를 참조 영상으로 넣으면 그 음원을 따라 부른다. 다만 과정이 수동적이라 번거롭다는 평. [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=aicreate&no=62780
- 아카라이브 AI 그림 채널: 만화 원작 장면을 넣으면 성우 목소리 대사까지 붙은 애니로 만든다는 초기 소개. 공식 발표 번역에서 **다인원 립싱크는 아직 과제**라고 밝혔다고 정리. v2v가 대단하다는 글도 있다. [검색요약][커뮤니티-KR] https://arca.live/b/aiart/162007977 , https://arca.live/b/aiart/162263130 , https://arca.live/b/aiart/162504993 , https://arca.live/b/aiart/172854969
- 애니 오프닝처럼 만든 사례 글, 루리웹의 "시댄스 2.0과 완 3.0으로 단편 애니" 글(빌리빌리에서 시댄스 2.0 애니가 많다는 언급). [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=981670 , https://bbs.ruliweb.com/community/board/300143/read/76991077
- 유튜브 한국어: "국내최초! 시댄스2.0 공식홈 사용후기", "시댄스2.0 완전히 이해하세요. 클링비교 무한테스트"(댓글은 프롬프트 이해가 필수라는 평과 차이가 크지 않다는 평으로 갈림), "시댄스 2.0 AI 캐릭터 영상 테스트"(Midjourney 키 이미지 → Flow 얼굴 안정화 → Dreamina). [검색요약][유튜브] https://www.youtube.com/watch?v=lvvWH08I4H4 , https://www.youtube.com/watch?v=NGGwayKllEQ , https://www.youtube.com/watch?v=O38yyvlnLok

**일본**
- 미츠카루 비교(2026-06-24): 애니에서 Seedance 2.0이 화풍 유지와 동작 자연스러움 모두 우세. 움직이자마자 3D처럼 변하는 현상이 없었고, 얼굴·머리·옷 디테일이 유지됐다. 반면 출력 편차가 크고 실패작이 섞이며, 4초 영상 생성에 2분 반~3분이 걸린다. 립싱크와 애니 실패율은 다루지 않았다. [원문확인][블로그] https://note.com/ai_mitsukaru/n/na58654b1f71b
- 애니 제작자 澤村徹: Kling 3.0으로 만든 애니 MV에서 원거리 샷·격한 액션이 무너진 부분 약 절반을 Seedance 2.0으로 다시 만들었다. 다만 Seedance는 데포르메·액션에 모방 티가 난다고 느꼈다. [검색요약][블로그] https://note.com/metalmickey/n/n66a8772512b0
- CreativeEdge: Seedance 2.0이 Kling 3.0보다 고성능이지만 가드레일이 엄격하다. 실존 인물 참조를 자주 거부해서 생성 횟수가 늘었다. 이후 Higgsfield·Freepik 경유로는 실존 인물 참조가 가능해졌다는 글도 올렸다. [검색요약][블로그] https://note.com/creative_edge/n/nd14f62e9e4df , https://note.com/creative_edge/n/n91b776e20b9d
- 격한 동작 중 붕괴가 Seedance 2.0에서 크게 억제되고 Kling 3.0은 녹아내리는 듯한 열화가 보인다는 검증. 피격된 로봇이 앞으로 쓰러지는 동작에 무게감이 있다는 평(인외 캐릭터 관련 몇 안 되는 근거). [검색요약][블로그] https://note.com/creative_edge/n/nb71d78a940b9
- 립싱크(821R, 2026-07-04): Higgsfield의 Seedance 2.0으로 일본어 노래 립싱크를 시도했다. 레퍼런스 음원의 가사를 지키지 않고 멋대로 가사를 부르는 경우가 있었다. 5~10초 짧은 컷과 시작 프레임 정지 이미지를 함께 쓰니 만족에 가까워졌다. 두 캐릭터에게 가볍게 춤추라고 하자 타이밍 좋은 동작이 나왔다. [원문확인][블로그] https://note.com/821r/n/n23c0507d0d7e
- Seedance 2.5 vs MiniMax H3 노래 립싱크: 2.5는 몸 움직임이 좋고 멜로디를 따르지만 가사를 미묘하게 바꾸고, 리듬이 조금 늦게 느껴진다는 평. [검색요약][블로그] https://note.com/dreamy_quail9288/n/nac14cd0b3b66 , https://note.com/highdrama/n/n33b22ba185f0
- Seedance 2.5는 2.0보다 빠르지만 비용이 2배 이상이고, 어느 쪽이 낫다고 단정하기 어렵다는 체험기. [검색요약][블로그] https://note.com/highdrama/n/nae5153980e2e
- 유튜브 일본어 "【徹底比較】Seedance 2.0 vs Kling 3.0｜10本作ってわかった違い"의 댓글은 Kling이 지나치게 매끈하고 광택이 강하며 Seedance가 자연스럽다는 반응. [검색요약][유튜브] https://www.youtube.com/watch?v=SpyWj2klOJ0

**Seedance 2.0 Fast:** 단독 평가는 찾지 못했다. 가격 정리 글(디시)과 Standard·Fast·Kling 3.0 격투 장면을 비교한 쇼츠 1개만 있다. [검색요약][커뮤니티-KR][유튜브] https://m.dcinside.com/board/thesingularity/1075647 , https://www.youtube.com/shorts/nIpKFmPDrZE

### 2.2 Kling 3.0 / Kling Omni 3

**한국**
- 디시 AI 창작 갤러리(2026-02-18): Veo·Runway·Luma를 써 보고 Kling으로 돌아왔다. 3.0 멀티샷 덕에 노가다가 줄었지만, 가성비는 아직 2.5가 낫다는 평. 애니 스타일 유지나 표정에 대한 언급은 없다. [원문확인][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=aicreate&no=59886
- 같은 프롬프트로 Kling 3.0과 Veo 3.1을 비교한 글: 음성은 Veo가 낫고 전체 성능은 Kling이 낫다는 의견. [검색요약][커뮤니티-KR] https://m.dcinside.com/board/aicreate/59219
- "클링 3.0 진짜 미쳤네", Higgsfield 유료로 Kling 3 첫 영상을 만든 글(생성 약 1시간, 품질과 표정 칭찬). [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=959275 , https://m.dcinside.com/board/thesingularity/956433
- 클리앙(2026-02): Kling 3.0 영상에 놀라면서도 아직 평가는 어렵다는 반응. [검색요약][커뮤니티-KR] https://www.clien.net/service/board/park/19138571
- 구버전 비교(하이루오 vs 클링, 2024~2025): Kling이 화질이 낫고 원본 얼굴을 거의 그대로 유지한다. 두 사람이 나오면 팔이 몸을 뚫는 문제가 심하다. 검열이 엄격하다. [검색요약][커뮤니티-KR] https://m.dcinside.com/board/aicreate/42962 , https://gall.dcinside.com/mgallery/board/view/?id=aicreate&no=45589 , https://gall.dcinside.com/mgallery/board/view/?id=aicreate&no=43188
- 유튜브 한국어: "일주일간의 클링 3.0 사용 리뷰"(멀티샷·주체 바인딩으로 캐릭터 일관성 유지), "클링 3.0으로 캐릭터와 목소리 일관성 유지하는 방법(립싱크 필요 없음)", "씨댄스2.0 vs 클링3.0 vs Veo3.1 누가 최강자인가?", "AI 영상생성 완벽 비교". [검색요약][유튜브] https://www.youtube.com/watch?v=-K3_tZcQ1BE , https://www.youtube.com/watch?v=YIHN5rvvIqE , https://www.youtube.com/watch?v=7zVp4upK5IU , https://www.youtube.com/watch?v=przt9kV9x9s

**일본**
- 미츠카루(2026-06): 애니에서 Kling 3.0은 작화는 유지하지만, 걸어오는 장면에서 발을 움직이지 않고 옆으로 미끄러지며 머리카락이 굳어 보였다. 남자는 왼손·여자는 오른손으로 악수하라는 지시도 반대로 했다. 실사·광고와 출력 안정성은 Kling이 위. [원문확인][블로그] https://note.com/ai_mitsukaru/n/na58654b1f71b
- CreativeEdge(H3 검증 글 안에서): 빠른 동작 때 Kling 3.0의 윤곽선 붕괴가 문제였다고 언급. [원문확인][블로그] https://note.com/creative_edge/n/n5b8795507cdf
- 10초를 넘기면 쓸데없는 요소가 섞이는 빈도가 조금 늘지만, 다른 모델보다 안정감이 있다는 평. [검색요약][블로그] https://note.com/creative_edge/n/nb71d78a940b9
- Veo 3.1과 Kling 3.0은 일본어 프롬프트로도 의도를 잘 잡는다는 비교. [검색요약][블로그] https://note.com/mashtake/n/nbc5c7808e789
- R2V(참조 기반) 비교: Seedance 2.0 / Veo 3.1 / Vidu Q2 / Kling 3.0을 실제 출력으로 비교한 글이 있다(내용 미열람). [검색요약][블로그] https://note.com/smoothiestudio/n/n7fcb658fa8f7

**Kling Omni 3 단독:** 커뮤니티 평가를 찾지 못했다. 공식·판매처 페이지만 있다(립싱크 3~15초, 720p/1080p, 측면·강한 그림자·가림에서 정확도 하락이라는 판매처 설명). [검색요약][블로그·판매처] https://renoise.ai/ja/blog/kling-3-omni-lip-sync-explained

### 2.3 Kling Motion Control 2.6 / 3.0

**한국**
- 디시 특이점(2026-02): Kling은 모션컨트롤 빼고는 잘 모르겠고, 순수 생성 성능은 Seedance 1.5 Pro나 다른 모델이 나을 수도 있다는 의견. 즉 **모션컨트롤이 Kling의 대표 강점**으로 인식된다. [검색요약][커뮤니티-KR] https://m.dcinside.com/board/thesingularity/991711?page=2
- 루리웹 질문: 특정 안무 영상은 잘 되는데, 유튜브에서 받은 안무 영상을 넣으면 계속 오류가 난다. [검색요약][커뮤니티-KR] https://bbs.ruliweb.com/userboard/board/700315/read/9714
- 디시 AI 매터스 갤러리의 기사 전재: 애니 캐릭터·동물·어린이로 동작 이식, 표정·손가락을 몸 전체와 따로 다루는 설계. Runway Act-Two 대비 평가자 78.5%가 선호했다는 **개발사 자체 평가**. [검색요약][커뮤니티-KR(기사 전재)] https://m.dcinside.com/board/aimatters/2158

**일본**
- 3.0은 2.6보다 어느 각도에서도 얼굴이 거의 흔들리지 않고 표정이 풍부해졌다는 설명. 격한 동작에서 화면이 무너지는 것이 최대 과제이며, 참조 영상을 AI로 느리게 만든 뒤 생성하고 다시 배속을 올리는 우회법이 소개됨. 급격한 줌·극단적 앵글 변화가 있으면 캐릭터 동작과 카메라 중 하나를 우선해 출력이 일그러진다. [검색요약][블로그] https://note.com/hiroto141225/n/nbf07d639227c , https://note.com/creative_edge/n/n512915518c30
- 애니 캐릭터로 질주 장면을 만들어도 얼굴이 다른 사람으로 바뀌지 않았다는 체험. [검색요약][블로그] https://note.com/yomikakisan/n/nee40a8ffa2f1
- 애니 밈("나오야") 재현 검증: 약 1초의 빠른 컷은 재현하지 못했다. 한 사람의 동작만 흉내 낼 수 있다는 제약. [검색요약][블로그] https://note.com/ai_douga/n/nef3a0bdcd2d9
- element(얼굴 고정) 기능은 사전 준비가 많아 단순 참조보다 다루기 어렵다는 감상. [검색요약][블로그] https://note.com/creative_edge/n/n512915518c30
- 변신 영상 검증: 머리카락이 서서히 사라지고 얼굴이 녹는 실패(주로 시작·끝 프레임 방식 검증). [검색요약][블로그] https://note.com/aru_ka3/n/n890b077d22de
- 2.6 댄스 영상 열광 글 다수. 참조 영상은 사람 동작이 뚜렷하고 속도가 중간인 것이 좋다는 권고. [검색요약][블로그] https://note.com/re_76enree4/n/nc7dc8ed3dea0 , https://note.com/tsunagu_story/n/n5b00c07c970b , https://note.com/komugi_dolko/n/nc41fc9d5b5a1

### 2.4 Kling Lip Sync

- 7개 도구 립싱크 비교(タナベ, **2025-12-05**, 실사 영상, 일본어 글): 1위 Veo 3.1, 2위 Veo 3.1 Fast, 3위 HeyGen, 4위 DomoAI, 5위 Hedra, 6위 Higgsfield, **7위 Kling**. Kling은 입술에서 치아로 이어지는 붕괴가 뚜렷했고, 12월 5일 업데이트도 큰 개선은 아니었다. 1클립 비용 Kling 약 66엔, Veo 3.1 약 430엔, Veo 3.1 Fast 약 164엔, Higgsfield 약 270엔. DomoAI는 애니에 강하다고 평가. [원문확인][블로그] https://note.com/tanabe_fragments/n/ncb5285b09303
- MV 제작 검증: Kling 립싱크 정확도가 매우 높아 음원에 입을 맞추는 데 썼다. 다만 노래가 아니라 대화용이고, 표정을 보고 입 벌림을 정하므로 무표정이면 입이 거의 열리지 않으며 프롬프트로 입 움직임을 지정할 수 없다. [검색요약][블로그] https://note.com/akiyoshisanbass/n/n482f0f95ea42
- 반려동물(고양이·개) 일본어 립싱크 검증: Kling과 DomoAI가 가장 좋았고, 근거리가 아닌 컷에서는 Kling이 낫다. [검색요약][블로그] https://note.com/tanabe_fragments/n/n7617f31ae323
- 한국(아카라이브, 약 600일 전 = 2025년 초 글): 내장 음성은 영어·중국어만이지만 외부 음성 파일을 넣을 수 있고, 깨끗한 한국어 TTS를 넣으면 체감 80~90% 비슷하게 나온다. 화면에 2명 이상이면 왼쪽 사람만 말해서 좌우 반전으로 우회했다. [검색요약][커뮤니티-KR] https://arca.live/b/aiartreal/127023616
- 참고(공식): 립싱크는 사람(실사·3D·2D)용이고 동물 캐릭터는 대상 아님(Kling 1.x 기준 안내). → 몬스터에 쓰기 어렵다. [검색요약][공식] https://kling.ai/quickstart/ai-lip-sync-guide

### 2.5 MiniMax H3 / Hailuo 2.3

**한국:** H3나 2.3에 대한 커뮤니티 글은 찾지 못했다. 하이루오 구버전(2024~2025) 글만 있다. 무제한 요금제로 물량을 뽑기 좋고, 손가락과 2D 애니 같은 움직임은 하이루오가 낫다. 반면 특유의 AI 질감, 얼굴이 자주 바뀜, 멀리 있는 인물의 팔이 길어짐, 약한 물리. [검색요약][커뮤니티-KR] https://m.dcinside.com/board/aicreate/42962 , https://gall.dcinside.com/mgallery/board/view/?id=aicreate&no=45589 , https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=618242

**일본**
- CreativeEdge(2026-08-18): Seedance용 캐릭터 참조와 프롬프트를 그대로 써서 H3(2K, Higgsfield)로 16초 애니 클립을 2번 생성했다. 윤곽·얼굴·머리·배색·셀 그림자가 안정적이고, Kling 3.0의 빠른 동작 윤곽 붕괴가 거의 없어 액션도 어느 정도 버틴다. 걱정하는 표정·박수·스킵·달리기 지시가 들어갔다. 표정 뉘앙스, 립싱크, 몬스터, 재시도율은 다루지 않았다. Higgsfield 15초 기준: H3 2K 60크레딧, Seedance 2.0 1080p 180(할인 135), Seedance 2.5 1080p 240(할인 135). 표본 1캐릭터·2회. [원문확인][블로그] https://note.com/creative_edge/n/n5b8795507cdf
- 같은 저자의 후속: 실사 콘텐츠는 Seedance 2.5가 최고이며 H3와 Wan 3.0은 따라오지 못했다. H3로 AI 드라마 제작이 가능한지 Seedance 2.0과 비교한 글도 있다. [검색요약][블로그] https://note.com/creative_edge/n/n93ff40c702f9 , https://note.com/creative_edge/n/ndef338606b31
- H3는 로컬에서도 돌린다(MacBook Pro M4 Max 4bit/8bit 실측, ComfyUI, 집의 DGX Spark로 실사→애니 변환). 8bit가 4bit보다 선과 음영이 깨끗하고 머리·표정 디테일이 선명하다. 실사→애니 변환에서 입 모양 변화와 눈 깜빡임도 생성된다. 사람 피부가 플라스틱처럼 보일 때가 있다. [검색요약][블로그] https://zenn.dev/acntechjp/articles/zenn-minimax-h3-m4max , https://note.com/cadmi/n/n3200167febec , https://note.com/mayu_hiraizumi/n/nd66cfebfe5d0 , https://zenn.dev/kun432/scraps/105eef7bf15e43
- 4면 캐릭터 시트를 넣어도 효과가 없었고, 구조화된 프롬프트가 효과가 있었다는 A/B(약 5초 회전 샷, 시드 3개로 범위 한정). [검색요약][블로그] https://zenn.dev/toki_mwc/articles/minimax-h3-structured-prompt-ab
- Hailuo 2.3 소개 글: 애니·특수 화풍 안정성과 실사 미세 표정이 향상됐다고 한다. 다만 검증은 대부분 Fast로 했고, 브레이크댄스는 Fast가 무너져서 Standard를 썼다. [검색요약][블로그] https://note.com/kind_llama1215/n/n176fce520761
- 애니 노래 립싱크는 H3가 더 맞는다는 비교가 있다. [검색요약][블로그] https://note.com/dreamy_quail9288/n/nac14cd0b3b66

### 2.6 Google Veo 3.1 (Fast / Lite)

**한국** (대부분 2025년 Veo 3 ~ 3.1 초기 글)
- 한국어로 말하라고 여러 번 써도 10번 중 1번꼴로만 한국어가 나오고 나머지는 영어이거나 무음이었다. [검색요약][커뮤니티-KR] https://m.dcinside.com/board/thesingularity/736982
- Flow에서는 한국어 음성이 안 돼서 일반 채팅 화면에서 만들었다는 글들(2025). [검색요약][커뮤니티-KR] https://www.clien.net/service/board/park/18984389 , https://m.dcinside.com/board/thesingularity/738258
- 3.1 후기: 확장 기능에서 소리가 나게 됐지만 생성 성능 자체는 같다. 일관성과 확장성은 좋아졌다. [검색요약][커뮤니티-KR] https://m.dcinside.com/board/thesingularity/861179 , https://arca.live/b/aiartreal/150702847
- 비교 영상 글: Veo3는 대사, 특히 한국어 처리가 부족하다. [검색요약][커뮤니티-KR] https://m.dcinside.com/board/aicreate/55413
- 2026년: Kling 3.0 대비 음성은 Veo가 낫다는 비교. [검색요약][커뮤니티-KR] https://m.dcinside.com/board/aicreate/59219

**일본**
- 립싱크 1위(Veo 3.1)·2위(Fast). 팔과 몸도 자연스럽게 움직인다. 단점은 내 음성을 올릴 수 없고, 생성 길이에 맞춰 대사를 바꾸고, 쉬운 한자도 잘못 읽는다는 것. Fast는 클로즈업에서 치아가 무너지고 대사를 자주 잘못 읽는다. [원문확인][블로그] https://note.com/tanabe_fragments/n/ncb5285b09303
- Veo 3.1로 기초를 만들고 Omni Flash로 마무리하라는 워크플로 제안. [검색요약][블로그] https://note.com/sasukebrain/n/nf64a5325d4b6
- **Veo 3.1 Lite 단독 평가는 찾지 못했다.**

### 2.7 Gemini Omni Flash (5월판, 8월 27일 1.1판)

- 한국 커뮤니티 글은 찾지 못했다.
- 일본: 처음부터 만드는 능력은 Seedance 2.0이 훨씬 위지만, 기존 영상을 대화로 부분 수정하는 데 강하다. 공 궤적이 무중력처럼 뜨고 점프 착지가 어색하다. 일본어 대사가 부자연스럽고 긴 내레이션일수록 심하다. 한 번에 최대 10초, 720p. 장면을 넘기면 캐릭터 일관성이 무너진다. 스마트폰 지우기 수정은 성공했지만 얼굴까지 바뀌었다. API 초당 $0.10, 무료 티어 없음, Flow에서 편집 1회 116엔. [검색요약][블로그] https://note.com/genel/n/n28bc5a5c0cb3 , https://note.com/kudo_notes/n/nfc39d028f15c , https://note.com/moral_coyote7965/n/n91212f63c3ad , https://note.com/keitaro_aigc/n/n89b14a48fda8 , https://qiita.com/Takuya__/items/91e7225dd422e158821c , https://note.com/tanabe_fragments/n/n16d99e872fa2
- 1.1판은 직전 영상 최대 약 10초를 참조해 이어 붙이는 장면 연장 기능이 추가됐다. [검색요약][블로그] https://note.com/ai__worker/n/ne02d3b29cd70
- 표정 참고 클립 관점: 얼굴이 수정 중에 바뀌는 사례가 있으므로 **캐릭터 동일성 유지용으로는 위험**, 이미 만든 클립의 소품·배경 정리에만 쓸 만하다(종합 판단).

### 2.8 Vidu Q4

- 한국·일본 모두 Q4 실사용 평가를 찾지 못했다. 일본 Qiita 워크플로 글에 제품 페이지 설명(최대 4K, 16초, 참조 영상 워크플로)만 인용됐다. [검색요약][블로그] https://qiita.com/wendyxyz733/items/e669c6dc6d5997d3ab11
- 구버전 평가(참고): Q2 R2V 이후 캐릭터의 3D 느낌이 꽤 사라지고 칼 묘사가 안정됐다. Q3는 애니 전용이라 생각했는데 실사 쪽으로도 넘어왔다. 애니 콘텐츠면 Vidu가 최선이라는 글은 Vidu 공식 파트너가 쓴 것이라 할인해서 봐야 한다. [검색요약][블로그] https://note.com/kongo_jun/n/n7e4724768207 , https://note.com/genel/n/n5a48cba444ad , https://note.com/fujin_metaverse/n/n2ed9162e4e5a , https://note.com/noz_tanaka/n/ne13af76f9855
- Vidu Q1이 "얼굴이 바뀌는 문제"를 해결했다는 글(구버전). [검색요약][블로그] https://note.com/akiyoshisanbass/n/na0b798a633a4

### 2.9 Wan 3.0

**한국**
- 아카라이브 AI 그림 채널: 2026-08-24 출시 소식 글. 댓글에서 Wan은 이제 오픈소스가 아니라는 지적, 2.2 이후 공개 가중치가 멈췄다는 불만. [검색요약][커뮤니티-KR] https://arca.live/b/aiart/180891745 , https://arca.live/b/aiart/179175914
- 루리웹: 시댄스 2.0과 완 3.0으로 만든 단편 애니 공유. [검색요약][커뮤니티-KR] https://bbs.ruliweb.com/community/board/300143/read/76991077
- (참고) Wan 2.2 시절 아카라이브에서 얼굴 디테일 워크플로·음성→영상(S2V) 실험 글이 많았다. 오픈 가중치였기 때문. [검색요약][커뮤니티-KR] https://arca.live/b/aiart/146571859 , https://arca.live/b/aiart/146799983

**일본**
- CreativeEdge: 실사 표정 AI 드라마는 Wan 3.0으로 비용을 크게 줄일 수 있겠다고 했다. 애니 표현 순위는 Seedance 2.5 > Wan 3.0 > MiniMax H3지만 실사만큼 차이가 크지 않다. Higgsfield 크레딧: Wan 3.0 720p 10초 25, Seedance 2.5 1080p 10초 160. [검색요약][블로그] https://note.com/creative_edge/n/n2689961726a8
- 30초 단일 컷 서사 재현은 되지만, 사람→물고기 변신 순간은 이펙트처럼 처리되고 중간 프레임이 빠졌다. 우키요에 스타일은 판화 질감이 부족했다. [검색요약][블로그] https://note.com/ai_driven/n/nf820636b7b91 , https://qiita.com/a01093972190/items/120c69158c783226f95c
- Seedance 2.5와 비교: 표정·움직임·카메라에 AI 티가 남고 격한 액션의 긴장감이 약하다. [검색요약][블로그] https://note.com/genel/n/n5ffc64657467
- Wan 3.0 vs H3, 30초 비교 전 맞춰야 할 조건 7가지 같은 글도 있다(비교 조건 통제의 중요성). [검색요약][블로그] https://note.com/fluxproweb/n/nee630fddf99f , https://note.com/dora5/n/ncd9f5e55bc13

### 2.10 Higgsfield (여러 모델을 모은 플랫폼)

**한국**
- 장점: 연출이 좋고 이미지→영상 흐름이 만족스럽다. 자체 모델과 Hailuo·Sora2·Veo·Wan·Kling·Seedance를 한 곳에서 쓴다. 단점: 이미지가 물 빠진 듯하고 질감 디테일이 약하다. Kling 2.1 Master 생성 오류, Sora2·Veo는 상위 구독 필요. [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=898195
- 2026년 7월 "너무 비싸다" 글. 생성이 크레딧을 태우는 가챠 같아서 상위 요금제로 끌어올린다는 댓글 요지. [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=1305454
- 바이럴 광고와 AI 드라마로 사람을 끌지만 실제로는 모델마다 별도 구독이 필요하다는 비판. 2만 달러짜리 쇼케이스 영상이 사실 Seedance 4K로 보인다는 글. 전에는 되던 생성이 저작권·성인물 사유로 거부되기 시작했다는 자문 요청. [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=ai_utilize&no=87559 , https://gall.dcinside.com/mgallery/board/view/?id=aicreate&no=67071 , https://gall.dcinside.com/mgallery/board/view/?id=aicreate&no=66221

**일본**
- 립싱크 6위/7: 전반적으로 좋지만 중거리에서 품질이 떨어지고 클로즈업은 아주 좋다. 1클립 약 270엔, 할인 캠페인이 잦다. [원문확인][블로그] https://note.com/tanabe_fragments/n/ncb5285b09303
- Higgsfield·Freepik 경유 Seedance 2.0은 실존 인물 참조가 막히지 않는다는 속보. [검색요약][블로그] https://note.com/creative_edge/n/n91b776e20b9d

### 2.11 Uthana

- 한국어·일본어 모두 후기, 리뷰, 사용기를 찾지 못했다(검색 2회). 일본에서는 비슷한 텍스트→모션 도구로 Mootion, MotionGPT(Blender 적용), Maya용 Text2Motion 서버 실험 글이 나온다. [검색요약][블로그] https://note.com/kawamou/n/ncf9baa85e620 , https://cgworld.jp/regular/202308-aicg-03.html
- 결론: 한·일 커뮤니티 근거 0. 영어권 자료로 판단해야 한다.

### 2.12 QuickMagic

**한국 (디시 AI 모션캡처 마이너 갤러리)**
- 업데이트 후 센터 본이 사라지고 하반신 본만 나오게 바뀌어 VMD로 바꿀 때 모델이 깨졌다(MMD 기준). 본 구조가 바뀌면 리타겟이 깨질 수 있다는 경고. [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=aimocap&no=219
- 진입장벽이 낮고 싸며 가격 대비 품질이 좋지만, 취미를 만족시키기에는 부족하다는 엇갈린 평. 결제 수단이 페이팔뿐이라는 언급(오래된 글). [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=aimocap&no=80
- "퀵매직 때려잡는 GVHMR(+AGI Mocap)": 연구 모델 GVHMR이 매우 좋고, 특정 상황에서 포즈 일치율이 떨어진다는 비교. 글은 현재 404(삭제됨). [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=aimocap&no=374

**일본**
- 2024 검증: 발이 거의 미끄러지지 않는다. 상체·팔이 약하고, 팔 회전이 거의 빠지거나 팔꿈치 회전이 사라진 부분이 있다. [검색요약][블로그] https://note.com/mmder16/n/n18de7fef7cbe
- 라이브 느낌 작품이면 조금만 고쳐 써도 되지만, 애니 품질의 완벽한 동작이면 약 70% 수정이 필요하다는 판단(2024년 말). [검색요약][블로그] https://note.com/mirecat/n/ncb76c29d5994
- 2026년 2월경 무료판 검증: 정확도에 놀랐고, CINEMA 4D에 가져와도 미리보기와 같은 품질에 리그도 깔끔했다. [검색요약][블로그] https://note.com/shuntachibana_ie/n/n5754457f62f4
- 손가락·표정도 잡고 브라우저에서 관절을 끌어 미세 조정(IK/FK 필터, 물리 최적화)할 수 있다는 소개(홍보성). [검색요약][블로그] https://note.com/ai_hakase/n/nc077e2b7b4b0
- 2024년 기준: 다운로드는 FBX만, 처리에 몇 시간, VMD는 유료이며 120초 제한. 현재 사양은 다를 수 있다. [검색요약][블로그] https://note.com/mirecat/n/n2f7504fd3dbf , https://note.com/tomohiro_hiyama/n/n02defd570616

### 2.13 Rokoko Vision

- 일본: 카메라 1~2대로 쉽지만 가림(오클루전)에 약하다. 브라우저에서 끝나고 짧은 프리비즈에는 좋지만, 길거나 정밀한 작업은 유료가 필요하다. [검색요약][블로그] https://note.com/humble_bobcat51/n/n75a14d62c79f
- 2026년 1월경 검증: 15초 이내 영상이 필요하고, 복잡한 동작은 깨끗하게 잡히지 않았다. [검색요약][블로그] https://note.com/shuntachibana_ie/n/n1735495a9025
- 2024년 초 비교: 공중제비 불가, 평범한 걷기도 쓸 수 없었다. 이후 카메라 2대 지원으로 바뀌었지만 개선은 미확인. 2023년(구 Rokoko Video)은 걷기는 부드럽지만 발 방향이 틀어지는 경향. [검색요약][블로그] https://note.com/tomohiro_hiyama/n/n02defd570616 , https://note.com/nakashun_t/n/n8a029a7dc5f2
- 한국: 캡처 품질이 많이 낮고 버그가 있다는 불만, 광학식보다 덜 정밀해 수정이 훨씬 어렵다. [검색요약][커뮤니티-KR] https://gall.dcinside.com/mgallery/board/view/?id=aimocap&no=80

### 2.14 Tripo 리그·애니메이션

- 한국 커뮤니티 근거 없음.
- 일본: T포즈 사진을 넣으면 자동 리깅해 준다. 달리기·점프 등 프리셋 12종. 형태에 따라 리그가 부정확할 때도 있다. 리깅 실패 때 재시도로 나아진 사례가 있고, 안 되면 이미지 준비나 3D 생성부터 다시 해야 한다. [검색요약][블로그] https://note.com/docp3/n/ne961c3b7a550 , https://note.com/teruemon/n/nd04461ec91dc
- 뼈대를 적용할 수 없다고 판단된 3D 데이터(로봇 예시)는 애니메이션을 볼 수 없다. → **몬스터·비인간형은 막힐 수 있다.** [검색요약][블로그] https://zenn.dev/safubuki/articles/turtle-20240929-tripo2-evo
- Blender: GLB보다 FBX로 내보내야 사각면 유지가 쉽다. Auto-Rig Pro로 바인드·변형까지 확인했지만, 비다양체 형상은 0이 되지 않고 모델마다 결과 확인·설정 변경이 남는다. [검색요약][블로그] https://note.com/snapreplica/n/n3aacec2d7457
- 스케치 1장에서 게임 캐릭터까지 만드는 2026년 검증: 리깅 이후에는 손작업이 생겼다. [검색요약][블로그] https://zenn.dev/hibari_inc/articles/sketch_to_3d
- Tripo 개발사의 자동 리깅 AI UniRig 시험기도 있다. [검색요약][블로그] https://zenn.dev/vlntr_telco_rd/articles/6ac4810ad35647

### 2.15 Meshy 애니메이션

- 한국 커뮤니티 근거 없음.
- 일본: 머리·어깨·팔꿈치·손목·사타구니·무릎·발목에 마커를 맞추면 자동 리깅된다. 쉽지만 정확도는 아직 발전 중이다. 라이브러리가 많고 카테고리로 거를 수 있다. [검색요약][블로그] https://note.com/windspeaks/n/n0053f1e9c6cb
- 리그 베이스가 사람형과 개형(사족)뿐이라 특수 체형은 동작이 부자연스러울 수 있다. 자동 리깅은 웨이트 맵 조정이 필요하고 리그 정밀도가 꽤 느슨하다. [검색요약][블로그] https://note.com/osushi_san/n/n257fc3c94aff , https://note.com/th1980/n/n59f46e1ced96
- Meshy 7(2026년 9월경): 걷기·달리기·복싱 프리셋은 문제없고, 텍스트 생성 모션 중 옆돌기·벽 오르기·앞구르기는 자연스러웠다. 회전 점프하며 칼을 내려치기, 물건 던지기는 실패했다. [검색요약][블로그] https://note.com/miya19/n/n3f9ecbcf2c65
- 비인간형 캐릭터와 도구 간 본 호환에서 작업이 멈췄다는 사례. [검색요약][블로그] https://note.com/upfrontier/n/n338b878e01aa

## 3. 질문 항목별 교차 정리

### 3.1 애니·카툰 화풍 유지
- **Seedance 2.0/2.5가 일본 블로그에서 가장 높은 평가**를 받았다(움직여도 3D·실사로 바뀌지 않음). 다만 출력 편차가 크고 재시도가 많다. https://note.com/ai_mitsukaru/n/na58654b1f71b
- MiniMax H3는 애니 윤곽·셀 그림자 유지가 좋고 싸다는 평이 있다(표본 작음). https://note.com/creative_edge/n/n5b8795507cdf
- Kling 3.0은 작화는 유지하지만 발 미끄러짐, 굳은 머리카락, 빠른 동작 윤곽 붕괴, 과한 광택이 지적됐다.
- 2D 평면 애니가 실사보다 동작 붕괴가 많고, AI에 맡기면 3DCG 느낌으로 끌려간다는 관찰이 검색 요약에 있었다. 다만 어느 글의 내용인지 특정하지 못해 근거로 세지 않았다.

### 3.2 얼굴·표정·입 정확도
- 얼굴 동일성: Kling(구버전부터)과 Kling Motion Control 3.0이 강하다는 평. Seedance는 매끈한 피부와 **눈 깜빡임 부재**가 지적됐다(디시 3월 정리글). https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=1079232
- 표정: 표정 자체를 따로 채점한 한·일 커뮤니티 검증은 사실상 없다. H3 검증에 걱정하는 표정 지시가 들어간 정도다. Kling Motion Control 3.0이 2.6보다 표정이 풍부하다는 설명이 있다.
- 입: 실사 립싱크는 Veo 3.1 1위, Kling 꼴찌(2025-12 기준). Kling 립싱크는 무표정이면 입이 거의 안 열린다. "말하라"고만 하면 입만 움직이는 무표정이 되기 쉬워 감정을 함께 써야 한다는 팁. https://note.com/tanabe_fragments/n/ncb5285b09303 , https://note.com/akiyoshisanbass/n/n482f0f95ea42

### 3.3 한국어·일본어 립싱크
- 한국어: 최신 버전 검증은 거의 없다. Seedance 2.0은 한국어도 중국어처럼 들린다는 체감(2026-02). Veo3는 한국어 출력이 10번에 1번(2025). Kling은 외부 한국어 TTS를 넣으면 80~90%(2025년 초).
- 일본어: Veo 3.1은 자연스럽지만 대사를 바꾸고 한자를 잘못 읽는다. Gemini Omni Flash는 일본어 음성이 부자연스럽다. Seedance 2.0/2.5는 노래 가사를 멋대로 바꾸는 문제가 있다.
- 실무 결론: **대사 음성은 외부 TTS/성우로 만들고, 입은 립싱크 단계에서 맞추는** 쪽이 한·일 사용자들의 공통 우회법이다.

### 3.4 몸동작 품질
- 영상 모델: Seedance가 격한 동작 붕괴에 가장 강하다. Kling은 미끄러짐, Gemini Omni는 물리(무중력 공, 착지)가 약하다.
- 동작 이식: Kling Motion Control이 사실상 표준으로 인식된다. 약점은 빠른 동작(느리게 만든 참조로 우회), 1인 한정, 급격한 카메라.
- 영상→3D 모캡: QuickMagic이 발 고정이 좋고 팔 회전이 약하다. Rokoko Vision은 가림·복잡 동작에 약하다. 한국 갤러리에서는 GVHMR(오픈 연구 모델)이 더 낫다는 의견이 있었다.

### 3.5 몬스터·인외
- **한·일 모두 직접 검증 글이 거의 없다.** 근거는 단편적이다.
  - Seedance 2.0: 피격된 로봇이 쓰러지는 동작에 무게감이 있다. https://note.com/creative_edge/n/nb71d78a940b9
  - Kling Lip Sync: 동물 캐릭터는 대상 아님(공식, 구버전). 반면 실사 반려동물 일본어 립싱크는 Kling이 상위(블로그). 서로 다른 기능·버전이라 확인 필요.
  - Meshy 리그는 사람형과 개형만. Tripo는 뼈대를 못 넣는 형태(로봇)는 애니 불가.
  - Wan 3.0: 사람→물고기 변신 중간 프레임 누락.
- 판단: 몬스터 참고 클립은 내부 테스트로 직접 확인해야 한다(구조→동일성→연출 3단계 점검법이 Qiita에 소개됨). https://qiita.com/neuhausbarsuhn106/items/2d863dac7376fa0294ad

### 3.6 가격·가치·재시도
- Seedance: 성능은 최고 평가지만 Dreamina 크레딧 대폭 삭감(4월), 실패해도 크레딧 차감, 평균 4~5회 재시도 주장, 15초 약 $2.10 추정. 한국 갤러리에 가격 계산 글이 매우 많다.
- Higgsfield 크레딧(15초): H3 60 < Seedance 2.0 720p 90 < Seedance 2.0 1080p 180 < Seedance 2.5 1080p 240. Wan 3.0은 720p 10초 25. → 가성비는 Wan 3.0과 H3가 앞선다.
- Kling: 2.5가 3.0보다 가성비가 낫다는 한국 의견. 립싱크 1클립 약 66엔으로 쌈.
- Veo 3.1: 립싱크 1클립 약 430엔으로 가장 비쌈.
- Gemini Omni Flash: 초당 $0.10, 무료 없음.
- 한·일 모두 "한 번에 완성되지 않는다"는 전제가 공통이다. 같은 설정이라도 여러 번 뽑아 고르는 방식.

## 4. 근거 강도와 주의
- 가장 근거가 많은 것: Seedance 2.0 계열(KR·JP 합쳐 25건 이상), Kling 3.0·Motion Control(합쳐 25건 정도).
- 중간: MiniMax H3(JP 위주 10건 정도), Wan 3.0, Gemini Omni Flash(JP 설명글 위주), QuickMagic.
- 거의 없음: Vidu Q4, Kling Omni 3 단독, Seedance 2.0 Fast 단독, Veo 3.1 Lite, Uthana, Tripo·Meshy의 한국 반응, 몬스터 전반, 한국어 립싱크 최신 검증.
- 디시 글은 댓글을 읽지 못해 반대 의견 규모를 모른다. note 검증 글 상당수는 유료 강의·제휴 링크가 있는 작성자다.
- 일본 Seedance는 중국 국내판과 성능이 다른 글로벌판일 수 있다는 지적이 있다. 제공 경로(Dreamina, CapCut, API, Higgsfield)에 따라 결과가 다르다는 보고도 있다. https://note.com/creative_edge/n/nb71d78a940b9 , https://note.com/ai_mitsukaru/n/na58654b1f71b
