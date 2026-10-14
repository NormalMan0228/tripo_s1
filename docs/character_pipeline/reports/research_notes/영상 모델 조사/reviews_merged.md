# 사용자 평가 통합표 v2: 기존 평가 + 한·일·영·중 커뮤니티 반응 (2026-10-14)

그림: [reviews_merged.png](reviews_merged.png) (휴대폰용). 이 문서는 그림의 근거를 적은 글이다.

합친 자료
- 기존 평가: [reviews_needs.png](reviews_needs.png), [reviews_face.md](reviews_face.md), [reviews_body.md](reviews_body.md)
- 커뮤니티: [community_en_cn.md](community_en_cn.md) (HN·Trustpilot·bilibili 등), [community_kr_jp.md](community_kr_jp.md) (디시·루리웹·아카라이브·note·Zenn·Qiita)
- 각 주장의 원문 URL은 위 문서들에 있다. 여기서는 판단이 바뀐 곳만 대표 URL을 단다.

한계
- Reddit은 여전히 빠져 있다(도구 차단 + 2025-11부터 API 승인제, [INDEX](../../../../research_hub/INDEX.md)의 Reddit 항목 참고).
- 디시 글은 댓글을 못 읽어 글쓴이 1명 의견으로 셌다. note 검증 글 상당수는 유료 강의·제휴 링크가 있는 작성자다 [커뮤니티]/[블로그].
- 애니·카툰 **입 모양**을 프레임 단위로 잰 공개 자료는 이번에도 없다. 우리가 직접 시험해야 한다는 결론은 그대로다.

## 1. 얼굴·표정 (점수: 우리 용도 기준 5점 만점)

| 모델 | 기존 | 새 점수 | 커뮤니티가 더한 것 | 근거 강도 |
|---|---|---|---|---|
| Seedance 2.0 / 2.0 Fast / 2.5 | 4 | **4 (애니 화풍 1위)** | JP: 애니에서 움직여도 3D로 안 바뀌고 얼굴·머리·옷 유지, Kling보다 우세 [블로그] https://note.com/ai_mitsukaru/n/na58654b1f71b · KR: **눈 깜빡임이 없다**, 평균 4~5회 재시도 주장, 한국어가 중국어처럼 들림 [커뮤니티] https://gall.dcinside.com/mgallery/board/view/?id=thesingularity&no=1079232 · EN: "faces look amazing" vs "눈·얼굴이 뻣뻣" [커뮤니티] https://news.ycombinator.com/item?id=49138302 | 많음 (KR·JP 25건+, HN) |
| MiniMax H3 / H3 Max | 4 | **4** | JP: 애니 윤곽·셀 그림자·머리 안정, Kling의 빠른 동작 윤곽 붕괴 없음, Higgsfield 15초 60크레딧으로 쌈 [블로그] https://note.com/creative_edge/n/n5b8795507cdf · 애니 노래 립싱크는 H3가 더 맞는다는 비교 · EN: 화면이 밋밋, 1080p 품질 낮음, 피부 플라스틱 [커뮤니티] | 중간 (JP 10건, HN) |
| Vidu Q4 Preview | 3.5? | **3.5? (변화 없음)** | Q4 자체 사용자 글 0건. Q2·Q3 애니 호평은 공식 파트너 글이 섞임 | 아레나만 |
| Gemini Omni 1.1 Flash | 3.5 | **3 ↓** | JP: 장면을 넘기면 캐릭터 일관성 붕괴, **부분 수정 때 얼굴이 바뀜**, 10초·720p, 물리 어색 [블로그] https://note.com/genel/n/n28bc5a5c0cb3 · EN: Google은 참조 이미지 720p 제한·오디오 싱크 차단 [커뮤니티] https://news.ycombinator.com/item?id=49145728 | 중간 (JP 설명글) |
| Kling 3.0 / Omni 3 | 3 | **3** | KR: 얼굴 유지 좋음, 멀티샷 · JP: 애니에서 발 미끄러짐, 머리카락 굳음, 빠른 동작 윤곽 붕괴, 과한 광택 · Omni 3 단독 평가는 0건 | 중간 |
| Veo 3.1 Fast / Lite | 3 / 2 | **3 / 2** | JP: 실사 립싱크 7개 중 1·2위(2025-12), 단 대사를 바꾸고 한자를 잘못 읽음 [블로그] https://note.com/tanabe_fragments/n/ncb5285b09303 · KR: 한국어 출력 불안정(2025 글) · Lite 단독 평가 0건 | 중간 (실사만) |
| Wan 3.0 · Hailuo 2.3 | 3 | **3** | JP: 가성비 최고(Higgsfield 720p 10초 25크레딧), 애니 순위는 Seedance 2.5 > Wan 3.0 > H3라는 평도 있음 [블로그] https://note.com/creative_edge/n/n2689961726a8 · EN: 눈 흔들림, 밀랍 피부 · KR: 이제 오픈소스 아님 | 중간 |
| Kling Lipsync · HF Speak | 2 | **2** | JP: 립싱크 7개 중 Kling 7위, Higgsfield 6위, 무표정이면 입이 거의 안 열림 · KR(2025 초): 외부 한국어 TTS를 넣으면 체감 80~90% · 공식: 동물 캐릭터 불가 | 중간 |

## 2. 몸 동작 · 괴물 (몸 / 괴물)

| 도구 | 기존 | 새 점수 | 커뮤니티가 더한 것 | 근거 강도 |
|---|---|---|---|---|
| Kling 3.0 Motion Control | 4 / 1 | **4 / 1** | KR·JP: 동작 이식의 사실상 표준, 각도가 바뀌어도 얼굴 유지, 애니 캐릭터 질주도 OK · 약점: 빠른 동작(참조를 느리게 만든 뒤 다시 배속), 1명만, 급한 카메라 · EN: 참조 인물 쪽으로 얼굴이 끌림 | 중간 (JP 8건) |
| Seedance 2.x | 3.5 / 2 | **4 ↑ / 2** | JP: 격한 동작 붕괴가 가장 적음, 피격 로봇이 쓰러지는 동작에 무게감(인외 근거 1건) [블로그] https://note.com/creative_edge/n/nb71d78a940b9 · KR: 10초 액션 10개 중 2~3개만 실패 [커뮤니티] | 중간 |
| MiniMax H3 · Vidu Q4 | 3.5 / 2.5 | **3.5 / 2.5** | H3 애니 액션 어느 정도 버팀(JP 1캐릭터·2회), Vidu Q4는 0건 | 적음 |
| Uthana | 4 / 1 | **4 / 1 (근거 업체뿐)** | 한·일·영 커뮤니티 글 0건. 무료 단계로 직접 시험해야 함 | 업체만 |
| QuickMagic | 4 / 1 | **4 / 1** | EN·JP: 발 미끄러짐 거의 없음, 정리 10분 [커뮤니티] https://discussions.reallusion.com/t/first-full-body-mocap-test-using-quickmagic-and-accuface/15520 · JP: **팔·팔꿈치 회전 누락**, 애니 품질이면 약 70% 수정 · KR: 업데이트로 본 구조가 바뀌어 리타깃 깨짐 | 중간 |
| Rokoko Vision | 3 / 1 | **2.5 ↓ / 1** | JP·KR: 가림에 약함, 복잡한 동작 실패, 15초 제한, 품질 낮음 | 적음 |
| Tripo 리그 v2.5 | 3.5 / 3 | **3.5 / 2.5 ↓** | EN: 여우형 4족에서 자동 리거 4개 모두 다리를 일자로, Tripo는 척추를 팔다리로 인식 [블로그] https://app.cinevva.com/es/blog/2026-08-19-auto-rigged-animals-straight-legs · JP: 뼈대를 못 넣는 형태(로봇)는 애니 불가 [블로그] https://zenn.dev/safubuki/articles/turtle-20240929-tripo2-evo | 적음 |
| Meshy · Anything World | 3 / 2 · 2.5 / 3 | **3 / 2 · 2.5 / 3** | JP: Meshy 리그 베이스는 사람형·개형뿐, 웨이트 수정 필요. Meshy 7 텍스트 모션은 옆돌기·앞구르기 OK, 회전 베기 실패. Anything World는 커뮤니티 글 없음 | 적음 |

## 3. 결제·지원 평판 (새 항목)

| 곳 | 위험 | 내용 | 출처 |
|---|---|---|---|
| Kling 직접 결제 | **높음** | SaaSWorthy 집계 1.3/5. 해지 후 청구, 안 쓴 크레딧 환불 거부, 25크레딧 작업에 125 차감 | [커뮤니티] community_en_cn.md 2.3절 |
| Higgsfield | **중~높음** | Trustpilot 4.0이지만 별 1이 약 20%. Unlimited 토글 크레딧 소실, 해지 후 150달러 청구. KR: "크레딧 가챠", 비쌈 | [커뮤니티] community_en_cn.md 2.7절, community_kr_jp.md 2.10절 |
| Dreamina (Seedance) | 중 | 2026-04 플랜 크레딧 대폭 삭감(JP Advanced 약 78% 감소 정리글), 실패해도 크레딧 차감 | [커뮤니티] https://gall.dcinside.com/mgallery/board/view/?id=aicreate&no=62350 |
| MiniMax / Hailuo | 중 | 생성 실패에 크레딧 차감 불만. 공식 약관은 실패 시 자동 반환 | [커뮤니티]·[공식] community_en_cn.md 2.2절 |
| Tripo · Meshy | 중 | 크레딧 매월 소멸, 연 결제만(또는 연 결제 오청구), 느린 지원 | [커뮤니티] community_en_cn.md 3.4·3.5절 |
| Scenario · Google(Gemini 구독) | 자료 없음 | 이미 쓰는 곳이라 추가 결제 위험이 가장 적다 | [추정] |

## 4. 결론이 바뀐 점

1. **애니·카툰 화풍 유지 1순위는 Seedance 2.0**, 2순위 H3 (일본 블로그 비교 여러 건). 기존 표의 "H3 = 애니 그림체" 판단은 유지하되 순서를 바꾼다.
2. **Gemini Omni는 3.5 → 3.** 무료라 시험용으로는 계속 쓰지만, 수정 중 얼굴이 바뀐다는 보고가 있어 최종 레퍼런스용으로는 위험하다.
3. **재시도는 3~5회가 아니라 4~5회로 잡는다** (KR 주장 + Seedance 립싱크 "10번 중 7번" 업체 글).
4. **Seedance는 눈 깜빡임이 없다는 지적** → 깜빡임은 영상에서 가져오지 말고 우리 규칙(눈꼬리 기준 블링크)으로 만든다.
5. **대사 음성은 외부 TTS로 만들고 입은 따로 맞추는 것**이 한·일 사용자의 공통 우회법이다. 우리 계획(오디오 끔 + TTS + Audio2Face)과 같다.
6. **괴물은 여전히 근거가 거의 없다.** Tripo 4족 리그는 "다리 일자" 위험이 새로 보고됐다. 괴물은 직접 시험 전까지 점수를 믿지 말 것.
7. **결제는 이미 있는 Scenario CU·Gemini 구독을 먼저 쓴다.** Kling 직접 결제와 연 결제는 피하고, Higgsfield는 필요할 때 최소 월 요금제로 짧게.

## 5. 다음 작은 시험 (변경)

기존 제안(카툰 f11·애니 f09 × 표정 3개 × 모델 3개 = 18클립, 약 $5 이하)을 유지하되 모델 순서를 바꾼다.
- 1순위 Seedance 2.0 Fast, 2순위 H3 (Scenario Turbo 40 CU), 3순위 Gemini Omni(구독, 무료).
- 각 클립에서 볼 것: 화풍 유지, 정면 고정, 입 모양 o·u·a 프레임 수, 눈 깜빡임 유무, 재시도 횟수.
- 실제 생성(크레딧 사용)은 사용자 승인 후 다른 세션에서 한다.
