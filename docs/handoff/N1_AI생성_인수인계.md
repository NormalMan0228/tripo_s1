# N1 · AI 생성 파이프라인 인수인계 (2026-10-16 04:50)

브랜치 `wt/aigen`, 작업 폴더 `D:\lsm26\wt\aigen`. 01(통합)이 7a3aad6과 caad43d를 merge-version-gate에 합쳤고, 898c946과 c15e192는 병합을 요청해 둔 상태입니다.

## 끝난 일
| # | 내용 | 주요 파일 |
|---|---|---|
| 60 | 부적절 요청은 순화하지 않고 거절하며 이유를 보여 줌. 세 단계: ① 설명 금지어(과금 전) ② LLM 설계 SAFETY 판정(추가 비용 없음) ③ Tripo 내용 정책(2008)과 banned는 거절로 처리하고 환불 | `server/craft_moderation.py`, `server/data/craft_words.txt`, `server/asset_contract.py` |
| 16 | 실패 이유를 10가지로 분류해 제작 창 맨 위 카드로 보여 줌 | `craft_moderation.failure_reason`, `game/scripts/craft_words.gd failure()` |
| 68·75 | 사진은 게임에서 20MB까지 받아 1600px·1MB로 줄이고 EXIF 회전을 적용함. 서버는 6MB·4096px까지 받아 2048px·1MB로 다시 저장함(메타데이터 제거, sRGB 변환). 너무 크거나 작거나 읽을 수 없으면 이유를 알림 | `asset_studio.py check_image / reference_image`, `craft_panel.gd read_photo` |
| 69 | "AI 그림을 먼저 보고 만들기"를 끄면 그림 단계 없이 바로 만듦(5크레딧 절약) | `craft_panel.gd picture_first` |
| 53 | 크기 '직접 정하기': 바닥을 드래그해 넓이, 위아래로 드래그해 높이를 정함. 치수는 LLM에 넘김 | `game/scripts/craft_size_box.gd`, `StudioRequest.dims` |
| 17 | 사용자 결정은 B안. 확인할 때까지 HUD 제작(C) 슬롯에 반짝이는 '!'를 붙임 | `game/scripts/craft_badge.gd`, `craft_tracker.badge()` |
| 73 | 대책 2개: 미리보기 카메라가 물건 전체를 비춤, 컨셉 그림 프롬프트에 넓은 여백 요구 | `game/scripts/preview_frame.gd`, `asset_studio.draw_concept` |

## 남은 일
- **73 원인 확정**: 실제로 잘린 job으로 아직 확인하지 못함. 사용자가 VM에서 신고된 job의 `studio_jobs.provenance`(image_path, concept)와 `<job>-concept.jpg`, `<job>-whole.glb`를 확인해야 함(크레딧 없음).
- **71 '로컬까지 연동'**: 뜻을 사용자에게 확인해야 함.
- **67 캐릭터 리깅·애니**: XL 규모이고 크레딧 승인이 필요함.
- 창 모드 craft_panel_check 실패: 배지를 넣기 전 코드로 A/B 해 봐도 같았음. main.gd refresh_inventory의 HUD 재생성 타이밍 문제로, 01이 is_instance_valid 확인을 넣음(23ddaa0). 06:00 무렵 다시 확인할 예정.

## 배포 주의
- 0.11.7 클라이언트(버전 헤더 0.11.8 미만)는 거절 사유를 한국어 문장으로 받음.
- 학습 설계 캐시 키에 `DESIGN_RULES='safety1'`이 붙어, 처음에는 같은 문장이라도 LLM 설계를 다시 함.
- 금지어는 `server/data/craft_words.txt`만 고치면 됨. 한글은 단어 첫머리에서만 찾고, `*단어`로 쓰면 단어 안에서도 찾음. 자세한 문법은 파일 머리말에 있음.

## 테스트
- 서버: `server/tests/test_craft_moderation.py`, `test_craft_dims.py`(전체 1087 통과).
- Godot(헤드리스): `craft_panel_check`(QA 서버 필요), `craft_size_box_check`, `preview_frame_check`, `craft_badge_check`.
