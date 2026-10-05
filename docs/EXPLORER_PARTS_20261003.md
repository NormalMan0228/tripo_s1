# B형 탐험가 — 부위별 메시 편집본 (2026-10-03)

최신 부위 편집 원본은 `art/source/explorer_b_parts_20261003.blend`입니다.
**이 파일은 기존 표면 분리 실험본이며, 독립 신체·의상·장식의 제작 완료본은 아닙니다.**
새 제작은 [부위별 제작 기준](CHARACTER_MODULAR_PRODUCTION_STANDARD_20261003.md)에 따라
참조·부품 생성·대칭·접합·토폴로지를 먼저 검수하고 리깅으로 진행합니다.
`Character_Parts_Blender.cmd`를 실행하면 Blender에서 열립니다.
이전 `explorer_video_motions.blend`, `explorer_mesh_review.blend`,
`explorer_mesh_edit.blend`는 통합 메시이므로 부위 편집 원본으로 사용하지 않습니다.

## 분리한 부위

40개의 독립 메시 오브젝트로 구성했습니다. 오른쪽 Outliner에서 이름으로 선택하거나
Object Mode에서 화면의 부위를 클릭할 수 있습니다. Tab은 해당 부위의 Edit Mode,
H는 선택한 부위 숨기기, 숫자패드 /는 해당 부위만 보기입니다.

| 구분 | 오브젝트 |
|---|---|
| 머리·얼굴 | Head_Face_Neck, Nose, Lips, Eye_L/R, Eyebrow_L/R, Eyelid_Upper_L/R, Eyelid_Lower_L/R |
| 머리카락 | Hair_Main, Hair_Sidelock_R |
| 상의 | Jacket_Torso, Jacket_Sleeve_L/R, Jacket_Cuff_L/R, Shirt_Torso |
| 팔·손 | Forearm_L/R, Hand_L/R |
| 하의·벨트 | Pants_Waist, Pants_Leg_L/R, Pants_Cargo_Pocket_L/R, Pants_Cuff_L/R, Belt_Strap, Belt_Buckle |
| 신발 | Boot_Upper_L/R, Boot_Sole_L/R, Boot_Laces_L/R, Boot_Hardware_L/R |

## 제작 방법과 확인한 범위

기존 Tripo detailed 분할의 87조각을 이미지로 검토해 의미 단위로 묶었습니다.
분할 결과와 원본의 모든 41,778삼각형이 대응하는지 확인한 뒤, 애니메이션 원본의
정점·UV·스킨 가중치를 새 오브젝트에 복사했습니다. 팔/손과 좌우 바지 경계는
추가로 분류했으며 기존 표면의 위치는 바꾸지 않았습니다.

- 40개 오브젝트 모두 독립된 Mesh datablock이며, 각각 Edit Mode 진입을 검사했습니다.
- 41본과 기존 6개 동작을 유지했습니다. 각 동작의 시작·끝·중간을 포함한 5시점,
  총 30시점에서 원본과 비교한 최대 정점 위치 차이 0, 공유 경계의 최대 벌어짐 0입니다.
- UV 차이와 스킨 가중치 차이는 0입니다. 원본 삼각형을 누락·중복하지 않았습니다.
- Blender의 custom normal 재인코딩에 따른 최대 벡터 차이는 약 0.00428
  (방향 차이 약 0.245°)입니다. 조립 상태의 렌더도 확인했습니다.
- 재사용 GLB: `artifacts/character-parts-20261003/explorer_b_parts.glb`.
  메시 노드 40개, 스켈레톤 1개/41본, 애니메이션 6개, 텍스처 내장입니다.
- 이번 수정은 유료 생성 API를 호출하지 않았습니다. 기존 통합 원본은 보존했습니다.

## 남은 제작 범위

이 파일은 기존에 보이는 표면을 실제 오브젝트로 나눈 편집본입니다.
상의/바지를 벗었을 때 보일 완전한 몸체, 파츠 안쪽과 단면을 새로 만들지 않았습니다.
따라서 완성된 복장 교체 시스템이나 폐쇄된 독립 의상 모델로 간주하지 않습니다.
분리한 눈·눈꺼풀·입에는 아직 전용 얼굴 본이나 표정 blendshape를 추가하지 않았고,
손가락별 리깅과 별도로 생성한 고밀도 손/헤어도 이 몸체에 통합하지 않았습니다.

이 실험본의 기존 표면을 최종 몸체로 간주하지 않습니다. 별도 신체·의상·장식 생성
→ 좌우 대칭·접합·Sculpt → 변형용 토폴로지 → UV·베이크·재질 → 몸·손·얼굴 리깅
→ 동작 전환·의상 교체·Godot 검사 순서로 새 제작을 진행합니다.

검사 기록: `artifacts/character-parts-20261003/parts-manifest.json`,
`delivery-verification.json`. 재현 스크립트: `tools/build_explorer_semantic_parts.py`.
