# B형 탐험가 — 부위별 2D 이미지 검토

기준일 **2026년 10월 3일**. 현재 단계는 **부위별 2D 참조 제작 / 사용자 검토 대기**입니다.

<a id="summary"></a>
## 요약

전신 원안은 사용자의 **“다음 단계로”** 지시로 승인 기록을 남겼습니다.
그 원안을 입력하여 신체·헤어·의상·장식 **19종, 총 27장**을 각각 생성했습니다.
기본 19장에 보조 시점 6장, 손 측면과 몸통 경계 수정 2장을 추가했습니다.
몸통은 **v2를 우선 표시**하고 초기 v1도 보관합니다.

[부품 확대·시점 비교 페이지](http://127.0.0.1:8842/character-parts-2d/)에서 검토할 수 있습니다.
**새 3D 생성·UV·Blender 조립·리깅·애니메이션은 아직 진행하지 않았습니다.**
이번 Tripo·Scenario 호출과 크레딧 소비는 각각 **0**입니다.

![19종 부위별 2D 참조 모음](C:/lsm26/triphthonS1/artifacts/production-lab-20261003/review/character-parts-2d/contact-sheet-v1.jpg)

<a id="contents"></a>
## 목차

1. [19종 참조와 보조 시점](#parts)
2. [현재 확인한 차이·미확정 사항](#review)
3. [60개 제작 단위와의 관계](#coverage)
4. [도구·비용·기록](#accounting)
5. [검토 후 다음 작업](#next)

<a id="parts"></a>
## 19종 참조와 보조 시점

이미지는 기존 전신 그림을 자른 결과가 아니라, 승인한 원안을 참고해 각 부품을 다시
생성한 결과입니다. 다만 몸통 v2는 이번에 독립 생성한 몸통 v1을 수정한 이미지입니다.
옷 아래 가려진 신체는 무채색 마네킹 형상으로 만들었습니다.
이미지마다 프레임을 채우므로 서로의 픽셀 크기는 실제 조립 비율이 아닙니다.

| 분류 | 부품 | 원본·시점 | 검토 사항 |
|---|---|---|---|
| 신체 | 머리 피부 | [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/head-front-v1.png) / [우측면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/head-side-v1.png) / [후면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/head-back-v1.png) | 얼굴 인상·귀·두상과 세 시점의 일관성을 확인합니다. 눈알·눈썹·입 안은 아직 독립 참조가 없습니다. |
| 신체 | 목 | [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/neck-v1.png) | 아래쪽 쇄골 부분이 몸통과 겹칩니다. 목 길이와 최종 분할 경계를 검토해야 합니다. |
| 신체 | 몸통 | [연결 경계 수정안 v2](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/torso-v2.png) / [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/torso-v1.png) | 긴 목과 딱딱한 접합 테두리를 없앤 v2를 기본으로 표시합니다. 초기 v1도 보관했습니다. |
| 신체 | 골반 | [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/pelvis-v1.png) | 허벅지 연결 부분이 긴 편입니다. 골반과 허벅지의 최종 경계는 미확정입니다. |
| 신체 | 오른쪽 위팔 | [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/upper-arm-r-v1.png) | 한쪽 위팔 후보입니다. 접합 원형 표시는 형상 참고이며, 최종 관절이나 접합 치수가 아닙니다. |
| 신체 | 오른쪽 아래팔 | [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/forearm-r-v1.png) | 팔꿈치·손목의 두께와 테이퍼를 검토합니다. 좌우 반사와 신체 연결은 3D에서 검증합니다. |
| 신체 | 오른손 | [손등](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/hand-r-dorsal-v1.png) / [손바닥](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/hand-r-palm-v1.png) / [3/4 시점（초기 측면 요청）](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/hand-r-side-v1.png) / [정확한 엄지 측면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/hand-r-profile-v1.png) | 손등·손바닥에서 다섯 손가락을 확인합니다. 정확한 측면을 추가했고 초기 3/4 시점도 남겼습니다. |
| 신체 | 오른쪽 허벅지 | [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/thigh-r-v1.png) | 옷 아래 허벅지의 기본 형상입니다. 골반·무릎 경계와 전체 길이는 조립 단계에서 맞춥니다. |
| 신체 | 오른쪽 종아리 | [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/calf-r-v1.png) | 무릎 아래 종아리의 기본 형상입니다. 무릎·발목 경계와 좌우 대응은 미검증입니다. |
| 신체 | 오른발 | [앞·안쪽 3/4](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/foot-r-v1.png) | 발가락 다섯 개와 발목·발등 형태를 확인합니다. 파일명의 R만으로 해부학적 좌우가 확정되지는 않습니다. |
| 헤어 | 기본 헤어 | [앞쪽（정면에 가까운 시점）](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/hair-v1.png) / [후면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/hair-back-v1.png) | 머리 피부 없이 헤어만 새로 생성했습니다. 앞·뒤 형태를 비교합니다. 앞머리와 옆머리는 아직 묶음 참조입니다. |
| 의상 | 재킷 몸판 | [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/jacket-body-v1.png) / [후면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/jacket-body-back-v1.png) | 소매와 신체를 제거한 재킷 몸판입니다. 앞·뒤를 비교하고 소매 결합부는 추후 맞춥니다. |
| 의상 | 오른쪽 재킷 소매·소매단 | [정면 3/4](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/jacket-sleeve-r-v1.png) | 말아 올린 소매와 소매단의 묶음 참조입니다. 어깨 개구부·안쪽 두께는 3D에서 확인해야 합니다. |
| 의상 | 안쪽 셔츠 | [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/shirt-v1.png) | 재킷 아래 가려진 소매는 원안으로 확정할 수 없어 민소매 후보로 만들었습니다. 형태 검토가 필요합니다. |
| 의상 | 바지 기본형 | [정면](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/pants-v1.png) | 벨트·부츠·카고 주머니를 제외한 바지 기본형입니다. 허리·다리·밑단은 이후 편집 단위로 나눕니다. |
| 의상 | 오른쪽 부츠 | [앞·바깥 3/4](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/boot-r-v1.png) | 부츠 형상 참조입니다. 끈·금속 부속·밑창은 함께 그려져 있으며 아직 각각의 독립 생성 결과가 아닙니다. |
| 장식 | 벨트 가죽 띠 | [정면 3/4](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/belt-v1.png) | 버클과 분리한 짙은 갈색 벨트입니다. 허리 둘레와 버클 결합 위치는 조립 때 맞춥니다. |
| 장식 | 벨트 버클 | [정면 3/4](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/buckle-v1.png) | 벨트 없이 버클만 새로 생성했습니다. 프레임·핀 형상과 벨트 폭을 검토합니다. |
| 장식 | 카고 주머니 | [정면 3/4](C:/lsm26/triphthonS1/art/references/explorer_b_modular_v1/02_parts/cargo-pocket-v1.png) | 바지에서 독립시킨 주머니 후보입니다. 부착 위치·크기와 좌우 반사는 아직 미확정입니다. |

<a id="review"></a>
## 현재 확인한 차이·미확정 사항

- **목·몸통:** 목의 쇄골 아래와 몸통 영역이 겹칩니다. 몸통 v2는 긴 목과 단단한 테두리를 제거했습니다. 최종 경계·목 길이·치수는 아직 측정하지 않았습니다.
- **골반·허벅지:** 골반의 허벅지 연결 부분이 길어 보입니다. 전체 몸체에서 경계를 정해야 합니다.
- **손:** 손등·손바닥에서 다섯 손가락을 확인했습니다. 첫 측면 요청은 3/4로 생성되어 실제 측면을 추가했습니다. 리깅·가동 범위·좌우 반사는 아직 검증하지 않았습니다.
- **셔츠:** 재킷 아래 소매가 보이지 않아 민소매 후보를 제안했습니다. 원안과 확정된 동일 구조라고 단정하지 않습니다.
- **옷·부츠:** 안쪽 두께·개구부·기본 신체와의 간격·복장 교체는 아직 2D 이미지로 검증할 수 없습니다.
- **좌우:** 한쪽을 후보로 생성했지만 이미지의 R 표기만으로 해부학적 좌우가 검증된 것은 아닙니다. 3D에서 엄지·발 형태와 좌표를 확인한 다음 반사합니다.
- **접합:** 생성 이미지의 원형 연결 끝은 참조 형상입니다. 최종 피부 관절을 기계적인 연결부로 만든다는 뜻이 아닙니다.

<a id="coverage"></a>
## 60개 제작 단위와의 관계

기존 계획의 60개 항목은 최종 편집 단위입니다. 이번 19종은 그 항목을 지원하는
이미지 그룹이며 **60개 독립 메시나 60장 독립 부품 이미지가 완료된 상태가 아닙니다.**

손은 다섯 손가락이 있는 한쪽 손을 기준으로 만들고 이후 손바닥·각 손가락을 편집 단위로
구성합니다. 헤어의 앞머리·옆머리, 소매단, 바지 허리·다리·밑단, 부츠 끈·밑창·부속은
아직 묶음 참조입니다. 필요하면 3D 생성 전에 별도 확대·부품 참조를 추가합니다.

눈알·눈썹은 얼굴 이미지에서 인상을 참고할 수 있지만 개별 참조가 없습니다.
치아·혀 참조도 아직 없습니다. 머리의 정면·측면·후면은 독립 생성 결과이므로
정확하게 동일한 3D 두상의 투영이라고 보장하지 않습니다.

제작 계획의 각 항목에 이미지 대응과 `reference_status`를 기록했습니다.
모든 `mesh_path`는 여전히 null이고 형상 검수·치수·대칭 수치는 미완료입니다.

<a id="accounting"></a>
## 도구·비용·기록

| 항목 | 이번 작업 |
|---|---|
| 이미지 생성 | built-in image_gen, 27번 호출 |
| 실제 모델 ID | 도구가 공개하지 않음. 특정 GPT 이미지 모델명으로 추정하지 않음 |
| 이미지 생성 별도 금액 | 도구가 공개하지 않음. 무료로 단정하지 않음 |
| Tripo API | 신규 호출 0, 크레딧 소비 0 |
| Scenario | 신규 호출 0, 크레딧 소비 0 |
| 별도 GPT API | 신규 호출 없음 |
| 원본 처리 | PNG 원본을 복사·검증. 검토 모음은 별도 문서 레이아웃이며 원본 픽셀을 수정하지 않음 |

- 입력 원안: `art/references/explorer_b_modular_v1/01_design/explorer_b_turnaround_v1.png`
- 원본 27장: `art/references/explorer_b_modular_v1/02_parts/`
- 목록·해시·시점·검토 상태: 같은 폴더의 `generation-manifest-v1.json`
- 전체 프롬프트·입력 경로: 같은 폴더의 이미지별 `*-generation-v1.json`
- 생성 도구가 반환한 실제 파일을 복사하는 도구: `tools/collect_part_reference_images.py`
- 검토 페이지 생성 도구: `tools/build_part_reference_review.py`
- [오프라인 검토 ZIP](C:/lsm26/triphthonS1/artifacts/production-lab-20261003/review/Tripothon_Part_References_2D_v1_20261003.zip): 원본 PNG, 프롬프트, 명세, 이 문서, HTML 포함. 계정 키·DB·유료 강의 원문 미포함.

<a id="next"></a>
## 검토 후 다음 작업

먼저 얼굴·헤어·손 형태, 목/몸통과 골반/허벅지 분할, 셔츠 종류와 의상 실루엣을
검토받습니다. 필요한 수정과 세부 참조가 승인된 뒤 **부위별 3D 생성**을 시작합니다.
소수 부품으로 생성 품질·비용을 확인하고 신체→의상→장식 순으로 확장합니다.
생성 결과의 대칭·치수·접합과 독립 편집 구조를 Blender에서 확인한 뒤 UV·리깅으로 진행합니다.

단계 승인 없이 후속 3D·리깅·애니메이션으로 자동 진행하지 않습니다.

- [부위별 제작 기준](C:/lsm26/triphthonS1/docs/CHARACTER_MODULAR_PRODUCTION_STANDARD_20261003.md)
- [기존 생성·애니메이션 실험 기록](C:/lsm26/triphthonS1/docs/CHARACTER_ANIMATION_WORKFLOW_20261003.md)
- [통합 인계 문서](C:/lsm26/triphthonS1/docs/TRIPOTHON_MASTER_HANDOFF_20261003.md#character)

[요약으로 돌아가기](#summary)
