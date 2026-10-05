# Tripothon 제작 도구·세부 파트·테스트 마을 — 2026-10-03

## 완료한 결과

- Godot 4.7.2 테스트 마을: 광장, 생성한 건물 3개 인스턴스, 장터, 우물, 개울, 다리, 과수원, 텃밭, 집 내부. 기존 B형 탐험가와 해루를 사용합니다.
- WASD 이동, Shift 달리기, E 상호작용·집 출입. 건물 전환에는 짧은 페이드를 적용했습니다. F3에서 개발 정보가 열립니다.
- 개발용 독립 손 부품: Scenario 이미지 → Tripo P2 → 로컬 MediaPipe 21점 → Blender 깊이 추정·16본·스킨 가중치 정리 → GLB → Godot 동작 검사.
- 재사용할 수 있는 독립 머리카락, 87개 몸체 분할 결과, 얼굴·손 Rigify 메타리그를 보존했습니다.
- Krita 5.3.4와 Material Maker 1.7 공식 포터블 배포본을 설치했습니다.

## 실행

프로젝트 루트의 `Village_Art_Lab.cmd`를 실행하면 마을이 열립니다. `Detail_Parts_Lab.cmd`는 손 동작·머리카락·분할 결과를 확인하는 개발 도구입니다. `Art_Tools.cmd`에서 Krita·Material Maker·Blender 원본을 열 수 있습니다.

Godot 편집기에서 `labs/village_art_lab/project.godot`를 가져오고 F6/F5로 실행할 수도 있습니다. 자체 검사: `.tools/godot/Godot_v4.7.2-stable_win64_console.exe --path labs/village_art_lab -- --audit --capture`.

## 설치·자동화 검증 범위

| 도구 | 상태 | 검증한 일 |
|---|---|---|
| Blender 4.5.3 LTS | 기존 설치 사용 | 마을·내부·모듈 GLB 제작, 손 리깅과 가중치 수정, Rigify 메타리그 생성 |
| Krita 5.3.4 | 공식 ZIP 설치 | ORA → KRA 변환, KRA 내부 페인트 레이어 2개 확인, PNG 내보내기. 실제 내보낸 목재 텍스처를 Blender·GLB에 사용 |
| Material Maker 1.7 | 공식 ZIP 설치, 공식 릴리스 SHA256 일치 | 실행과 편집용 PBR 그래프 준비. CLI 일괄 내보내기는 결과 파일이 생성되지 않아 미검증으로 남김 |
| Substance 3D Painter | 미설치 | Adobe 라이선스 답변이 아직 없어 구매·체험 구독을 진행하지 않음 |
| Pinokio | 제어 연결 불가 | C:/pinokio는 확인했으나 pterm과 localhost 제어 API가 응답하지 않음. 공식 포터블 배포본으로 진행 |
| MediaPipe Hand Landmarker | 공식 모델 설치 | 가상 손 이미지에서 21점 검출. 모델은 한 손의 좌우를 Right로 판정했으므로 Left 프롬프트만으로 좌우를 확정하지 않음 |

현재 이 세션은 데스크톱 앱의 마우스·붓 제어를 지원하지 않습니다. Blender 스크립트와 Krita 파일 변환을 실행했으며, 직접 붓질했다고 주장하지 않습니다. 수작업을 이어갈 수 있도록 `.blend`, `.kra`, `.ora`, `.ptex`를 남겼습니다. Material Maker는 Substance Painter의 모든 기능을 대체하는 것으로 검증되지 않았습니다.

## 비용 — 서로 분리한 예산

| 분류 | Scenario 사용 / 한도 | Tripo 사용 / 한도 |
|---|---:|---:|
| 캐릭터 세부 실험 | 23 / 1000 CU | 400 / 2000 크레딧 |
| 마을 맵 | 11 / 1000 CU | 360 / 2000 크레딧 |

Tripo 시작 잔액 23110, 이 작업의 확인된 소비 760, 완료된 요청들의 마지막 잔액 22350입니다. 개별 작업의 `credits_consumed`를 합산했으며 동시 요청의 계정 잔액 차이를 각 작업 비용으로 간주하지 않았습니다. Scenario는 UI에서 확인한 개별 결과 비용입니다. 결제·자동 충전·구독 변경은 하지 않았습니다.

Tripo 생성 6회는 P2-20260801, 텍스처·PBR 켜짐, detailed 품질이며 각각 실제 120크레딧이 기록됐습니다. 이 실험은 정가 보장이 아닙니다. 분할은 v2.0-20260430, detailed, split_by_connectivity=true, 실제 40크레딧입니다. 개발자 에셋 생성만 사용했고 플레이어용 생성 서비스는 호출하지 않았습니다. 키는 개발자 로컬 프로세스에서만 읽었으며 게임 클라이언트와 결과물에 포함하지 않았습니다.

Scenario 모델은 GPT Image 2 (`model_openai-gpt-image-2`), Quality Auto, Background Auto, 각 1장입니다. 머리카락 12 CU / 1122×1402, 열린 손 11 CU / 1254×1254, 건물 11 CU / 1380×1140. 이 결과의 생성은 Scenario 이미지 서비스이며 별도 GPT API 호출이나 effort 설정을 사용하지 않았습니다.

## 품질 검증

- 마을 이동, 다리 통과, 건물 충돌, 집 진입·복귀, 수확·사과·낚시 카운터 검사 통과.
- 카메라 방향 변화 0rad. 실제 연속 이동의 최대 물리 프레임 변위 0.075m. 의도된 건물 전환은 별도로 제외. 걷기 2.8m/s, 달리기 4.5m/s, 정지 후 속도 0m/s.
- 독립 손 Godot 리깅 16본, 가져온 동작 길이 2.433초, 반복 시작·끝 최대 회전 차이 0°. Blender 작성 구간은 2.4초이며 가져온 리소스의 길이는 별도로 측정했습니다.
- 손 동작은 Blender에서 만들었습니다. 이 실험에서 Tripo 애니메이션 API는 쓰지 않았습니다.
- 텍스트만으로 만든 첫 손은 형태가 부자연스러워 채택하지 않았습니다. 열린 손은 이미지 입력으로 개선했고, 초기 엄지 변형 문제는 공유 정점 병합과 스무딩·정규화로 줄였습니다.
- 게임의 기존 주인공 메시·얼굴·걷기 동작은 교체하지 않았습니다. 새 손은 몸체 맞춤 전의 독립 실험이며 전체 주인공의 손 애니메이션 완성으로 간주하지 않습니다.
- 분할 87조각은 의미 단위와 다릅니다. 의상 교체 전에 조각 묶음, 단면 완성, 경계·웨이트 검사가 필요합니다.
- Rigify 얼굴 메타리그를 생성했지만 주인공 얼굴에 바인딩하거나 표정 동작을 완성하지 않았습니다. 기존 얼굴은 유지합니다.
- 마을은 별도 아트 테스트 프로젝트입니다. 수확·낚시는 로컬 상호작용 검사이며 완전한 농사/낚시 시스템·서버 보상·경제 저장은 연결하지 않았습니다. 기존 온라인 서버와 본 게임에는 이 맵을 배포하지 않았습니다.

## 재사용 원본과 다음 순서

`art/source/village_art_20261003.blend`, `cottage_interior_20261003.blend`, `open_hand_rigged_20261003.blend`, `explorer_detail_rig_template.blend`가 편집 원본입니다. `art/village_kit/`에는 바닥 중심이 원점인 생성 소품과 직접 만든 집·다리·사과나무·입구 모듈이 있습니다. 각 모듈은 개별 GLB입니다. 한 마을 GLB는 36개 메시로 묶었고 약 314,939삼각형입니다.

다음에는 주인공의 얼굴 토폴로지·눈꺼풀·입 안을 정의하고, 새 머리카락·손의 맞춤 치수를 고정한 뒤 원본 메시를 수정합니다. 표정과 손 동작은 독립 검사 → 몸체 결합 → 걷기/달리기 중 변형 검사 순서로 진행합니다. 맵은 현재 시료를 아트 검토한 뒤 본 게임과 서버의 상호작용/저장 계약에 연결하는 것이 다음 단계입니다.

## 공식 자료

- [Krita 다운로드](https://krita.org/en/download/) · [CLI 파일 변환](https://docs.krita.org/en/reference_manual/linux_command_line.html)
- [Material Maker 공식 릴리스](https://github.com/RodZill4/material-maker/releases/tag/1.7) · [기능 설명](https://rodzilla.itch.io/material-maker)
- [Substance Painter 공식 페이지](https://www.adobe.com/products/substance3d/apps/painter.html)
- [Blender Rigify](https://docs.blender.org/manual/en/latest/addons/rigging/rigify/introduction.html)
- [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python)
- [Tripo 공식 문서](https://platform.tripo3d.ai/docs)
