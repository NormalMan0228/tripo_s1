# 정보 수집 허브 (INDEX)

이 파일은 정보 수집 전용 세션이 관리합니다. 다른 세션은 조사가 필요할 때 먼저 이 파일을 읽고, 여기에 없는 내용만 정보 수집 세션에 요청합니다.

- 최종 갱신: 2026-10-14 12:00 KST (커뮤니티 반응을 평가표에 합침, Reddit 승인제 반영, 주간 수집 계획 초안)
- 관리 세션: "정보 수집" 세션 (프롬프트는 [NEW_SESSION_PROMPT_KO.md](NEW_SESSION_PROMPT_KO.md))
- 경로 줄임: `RN/` = [docs/character_pipeline/reports/research_notes/영상 모델 조사/](../character_pipeline/reports/research_notes/영상%20모델%20조사/)

## 지금 먼저 볼 것 (결론만)

- **애니·카툰 화풍 유지:** Seedance 2.0 > MiniMax H3. 둘 다 4점. Gemini Omni는 시험용(수정 때 얼굴이 바뀜).
- **몸 동작:** Kling 3.0 Motion Control · Seedance 2.x · QuickMagic · Uthana가 4점. 괴물은 근거가 거의 없고 Tripo 4족 리그는 "다리 일자" 위험.
- **재시도는 4~5회**로 잡는다. 음성은 외부 TTS, 입은 따로 맞춘다(오디오 끔).
- **결제:** Scenario CU·Gemini 구독 먼저. Kling 직접 결제·연 결제는 피한다.
- 다음 작은 시험: 카툰 f11·애니 f09 × 표정 3개 × (Seedance 2.0 Fast · H3 · Omni) = 18클립, 약 $5 이하. 생성은 사용자 승인 후.

## 주제별 최신 문서

| 주제 | 최신 문서 | 날짜 | 한 줄 요약 |
|---|---|---|---|
| **사용자 평가 (통합, 최신)** | [reviews_merged.png](../character_pipeline/reports/research_notes/영상%20모델%20조사/reviews_merged.png) · [reviews_merged.md](../character_pipeline/reports/research_notes/영상%20모델%20조사/reviews_merged.md) | 2026-10-14 | 기존 평가 + 한·일·영·중 커뮤니티. Seedance 애니 1위, Omni 3↓, Seedance 몸 4↑, Tripo 괴물·Rokoko ↓, 결제 평판 표 추가 |
| 영상 AI (얼굴·몸·괴물) 종합 | [영상 모델 조사.md](../character_pipeline/reports/영상%20모델%20조사.md) | 2026-10-14 | 용도별 추천·플랫폼 비교. 얼굴 1순위 LivePortrait·Act-Two는 **방향 변경으로 제외됨**(사람 촬영 안 씀) → 통합 평가표를 우선 볼 것 |
| 가격 (Scenario 실측 · Higgsfield 공식표) | [both_real_prices.png](../character_pipeline/reports/research_notes/영상%20모델%20조사/both_real_prices.png) | 2026-10-14 | Kling·Seedance·Wan·Hailuo는 Higgsfield가 1.3~4배 쌈. Veo Lite·Fast(오디오 끔), H3 Max Turbo는 Scenario |
| 가격 (이전 버전) | RN/ cost.png · cost_versions.png · scenario_real_prices.png · scenario_vs_higgsfield.png | 2026-10-14 | both_real_prices.png로 대체됨. 참고용 |
| 플랫폼 노트 | RN/ [higgsfield.md](../character_pipeline/reports/research_notes/영상%20모델%20조사/higgsfield.md) · [scenario.md](../character_pipeline/reports/research_notes/영상%20모델%20조사/scenario.md) · [video_models.md](../character_pipeline/reports/research_notes/영상%20모델%20조사/video_models.md) | 2026-10-14 | 요금제·모델 목록·위험. 영상 모델 전반은 video_models.md |
| 사용자 평가 (이전, 세부 근거) | RN/ [reviews_needs.png](../character_pipeline/reports/research_notes/영상%20모델%20조사/reviews_needs.png) · [reviews_face.md](../character_pipeline/reports/research_notes/영상%20모델%20조사/reviews_face.md) · [reviews_body.md](../character_pipeline/reports/research_notes/영상%20모델%20조사/reviews_body.md) | 2026-10-14 | 통합표의 바탕. 모델별 세부 근거와 아레나 점수 |
| 커뮤니티 반응 (영·중) | RN/ [community_en_cn.md](../character_pipeline/reports/research_notes/영상%20모델%20조사/community_en_cn.md) | 2026-10-14 | 얼굴 드리프트가 가장 흔한 불만. Kling·Higgsfield 결제 불만. 통합표에 반영됨 |
| 커뮤니티 반응 (한·일) | RN/ [community_kr_jp.md](../character_pipeline/reports/research_notes/영상%20모델%20조사/community_kr_jp.md) | 2026-10-14 | 일본은 Seedance·H3 애니 호평, Kling 립싱크 7위. 네이버는 검색 거부. 통합표에 반영됨 |
| 무료 체험 | RN/ [trials.png](../character_pipeline/reports/research_notes/영상%20모델%20조사/trials.png) | 2026-10-14 | 매일 무료: Flow·Kling·Hailuo·Dreamina·Scenario 등 |
| 영상 → 3D 애니메이션 도구 | RN/ [video_to_animation.md](../character_pipeline/reports/research_notes/영상%20모델%20조사/video_to_animation.md) | 2026-10-14 | MediaPipe·Audio2Face·Uthana·Rokoko·QuickMagic·Tripo, RTX 2070 8GB 로컬 가능 목록 |
| 자동 얼굴 표정 도구 | [자동 얼굴 표정 생성 도구 조사.md](../character_pipeline/reports/자동%20얼굴%20표정%20생성%20도구%20조사.md) | 2026-10-13 | 우리 요구를 다 만족하는 도구 없음 |
| 영상 모델 요약 그림 (초기) | RN/ [summary.png](../character_pipeline/reports/research_notes/영상%20모델%20조사/summary.png) | 2026-10-14 | 첫 보고서 요약. 사람 촬영 방식이 들어 있어 일부 낡음 |

## 운영 (정보 수집 세션)

| 항목 | 문서 | 상태 |
|---|---|---|
| 주간 자동 수집 계획 | [figures/weekly_plan.png](figures/weekly_plan.png) | 2026-10-14 초안. **사용자 결정: 아직 켜지 않음** (필요할 때 손으로 실행). 공개 API·RSS 접속 시험 완료: Discourse(Blender·Godot·Unreal)·HN·Bluesky(api.bsky.app)·Mastodon·Civitai·HF·GitHub·note·Zenn·Qiita·80.lv = 200, Unity 포럼 403, Polycount 직접 접속 불가 |
| Reddit | [reddit_api_guide_KO.md](reddit_api_guide_KO.md) | 2025-11부터 API 셀프 발급 종료 → 승인 신청 필요. 사용자 신청 대기 |
| 주간 노트 | weekly/ (아직 없음) | 첫 실행 후 생성 |
| 그림 원본 | [figures_src/](figures_src/) | HTML → 헤드리스 Chrome으로 PNG |
