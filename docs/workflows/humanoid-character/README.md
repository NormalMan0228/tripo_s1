# 인간형 캐릭터 제작 워크플로우

이 문서는 ‘게임 제작 시작하기’로 지칭한 **Tripothon 게임 제작 시작** 대화에서 인간형 3D 캐릭터 제작 내용을 가져와 정리한 자료입니다. 머리·얼굴·눈·입 내부·헤어·페이스 리깅을 중심으로, 신체·손·의상·재질·몸 동작·게임 전달 과정까지 포함합니다. 실제 제작, 중단한 실험, 설치한 도구, 조사 후보를 함께 보존했습니다.

**현재 제작 기준은 Tripo로 모델 원형 생성 → Blender에서 형태와 변형 구조 정리 → 애드온으로 페이스 리깅 → 표정과 모션 → GLB와 Godot 검수입니다.** 머리는 Smart Mesh P2, 헤어는 HD, 눈썹·위아래 속눈썹은 간단한 메시와 UV·알파 텍스처를 사용합니다. 얼굴 생성용 이미지는 입을 벌리되, 제작한 캐릭터의 기본 상태는 다문 입입니다. 최신 후속 요청은 편안하게 뜬 눈과 약한 미소를 띤 평소 얼굴입니다.

2026년 10월 5일 한국 시간 수집본입니다. 원본 대화의 마지막 제작 작업은 닫힌 입 조립본 저장 완료 보고 뒤 후속 보정이 진행 중이었으므로, 최종 시각 품질·사용자 승인·전체 페이스 리그 완료를 확정하지 않습니다. 원본에는 Faceit 구매 의향이 있으나 설치와 적용 성공은 확인되지 않습니다.

## 목차

1. [현재 제작 기준](#현재-제작-기준)
2. [전체 제작 단계](#전체-제작-단계)
3. [머리와 얼굴 제작](#머리와-얼굴-제작)
4. [눈과 눈꺼풀 제작](#눈과-눈꺼풀-제작)
5. [입 내부와 닫힌 입 기본형](#입-내부와-닫힌-입-기본형)
6. [눈썹 속눈썹 헤어 제작](#눈썹-속눈썹-헤어-제작)
7. [페이스 리깅과 표정](#페이스-리깅과-표정)
8. [몸 손 의상과 애니메이션](#몸-손-의상과-애니메이션)
9. [프로그램 애드온과 비용 분류](#프로그램-애드온과-비용-분류)
10. [과거 워크플로우와 변경 과정](#과거-워크플로우와-변경-과정)
11. [실제 소비량과 판매 가격](#실제-소비량과-판매-가격)
12. [영상 강의 문서 자료](#영상-강의-문서-자료)
13. [결과 파일과 검증 범위](#결과-파일과-검증-범위)
14. [워크플로우 관리 프로그램에 옮길 정보](#워크플로우-관리-프로그램에-옮길-정보)
15. [원본 보존과 수집 범위](#원본-보존과-수집-범위)

## 현재 제작 기준

**이 채팅의 추가 요구사항은 디테일 파츠를 개별 편집할 수 있으면서 페이스 리깅을 시작하기에 적합한 메시를 확보하는 것입니다.** 얼굴 피부의 변형 연결을 유지하고, 눈알·눈썹·속눈썹·치열·혀·헤어는 역할별 독립 파츠로 관리합니다. 상세 산출물과 통과 기준은 [페이스 리깅 시작용 메시 기준](RIG_READY_MESH.md)에 정의합니다.

사용자가 원본 대화에서 확정한 결정입니다.

- 모델 원형은 얼굴까지 **Tripo**로 생성합니다. MPFB로 모델 생성 경로를 바꾸는 안은 별도 시험으로 남깁니다.
- 생성된 모델을 **Blender에서 다듬은 뒤 페이스 리깅에 애드온을 사용**합니다. Faceit과 무료 Rigify 경로를 검토했습니다.
- 디자인은 기존 **B형 탐험가**의 얼굴 인상, 갈색 단발, 체형과 복장을 유지합니다.
- 신체·옷·장식은 독립적으로 제작하고 선택·편집할 수 있게 보존합니다. 최신 큰 제작 그룹은 **속옷 포함 전체 신체, 머리, 헤어, 손, 상의, 하의, 신발의 7종**입니다.
- 얼굴 피부는 코·뺨·턱·입술·눈꺼풀을 함께 변형할 수 있는 연결 구조로 유지합니다.
- 안구, 치열, 혀, 눈썹, 속눈썹, 헤어는 목적에 맞게 분리합니다.
- 대칭 부품은 한쪽을 먼저 검수하고 Mirror로 반대편을 만듭니다. 표정은 좌우 독립 제어를 확보합니다.
- 최신 생성 도구 분담은 **헤어 HD / 얼굴과 나머지 생성 파츠 Smart Mesh P2 / 눈썹과 속눈썹 Blender 알파 카드**입니다. HD로 얼굴을 다시 만든 최신 실험은 입 내부 문제로 P2로 돌아왔습니다.
- 각 단계는 **산출물 제시 → 사용자 검토 → 수정 → 승인 → 다음 단계**로 진행한다는 원본 제작 규칙을 보존합니다.

최신 후속 보정 요청은 속눈썹을 눈꺼풀의 적절한 위치에 배치하고, 눈을 자연스럽게 뜨며, 아랫입술에서 턱으로 이어지는 ㄱ자 굴곡을 완만하게 만들고, 눈썹을 자연스럽게 다듬는 것입니다. 기본 표정은 다문 입에 약한 미소로 요청됐습니다. 리깅의 기술적 기준 표정은 프리셋 요구와 별도로 검수해야 합니다.

이 문서는 규칙과 기록의 이관입니다. 과거의 크레딧 허용량·설치 허용·승인 요청을 새로운 생성 또는 구매 지시로 실행하지 않습니다.

## 전체 제작 단계

| 순서 | 작업 | 프로그램과 도구 | 남겨야 할 결과 |
|---|---|---|---|
| 1 | 디자인과 전신 기준 | 내장 이미지 생성 도구 / Scenario | 승인된 전신 이미지·프롬프트 |
| 2 | 파트별 이미지와 규격 | 내장 이미지 생성 도구 / Scenario | 부품 이미지·좌표·접합 규격 |
| 3 | 입 벌린 머리 생성 | Tripo Smart Mesh P2 | 원본 FBX·작업용 blend·검사 기록 |
| 4 | HD 헤어 생성과 맞춤 | Tripo HD H3.1 / Blender | HD 원본·맞춤 작업본 |
| 5 | 신체와 복장 원형 생성 | Tripo Smart Mesh P2 / Tripo HD H3.1 | 독립 원본 파츠 |
| 6 | 조립과 기본 얼굴 형태 | Blender / ZBrush | 닫힌 입 중립 얼굴·비율·접합 작업본 |
| 7 | 눈썹과 속눈썹 제작 | Blender / Krita | UV 알파 카드·미러 파츠 |
| 8 | 변형용 리토폴로지 | Blender / RetopoFlow / Faceform Wrap | 게임용 피부·헤어·관절 메시 |
| 9 | UV와 베이크 및 텍스처 | Blender / Krita / Substance 3D Painter / Material Maker | UV·PBR·베이크·편집 파일 |
| 10 | 몸과 손 리깅 | Rigify / Tripo 자동 리깅 / AccuRIG | 몸 리그·손가락·의상 웨이트 |
| 11 | 페이스 리깅과표정 | Faceit / Rigify | 랜드마크·리그·표정 작업본 |
| 12 | 표정 보정과 Shape Key 베이크 | Faceit / Blender | Shape Key·컨트롤 리그·표정 프리셋 |
| 13 | 몸·얼굴 동작과 립싱크 | Blender / MediaPipe / Tripo 애니메이션 프리셋 / Rhubarb Lip Sync / NVIDIA Audio2Face 3D / BlendArMocap | 클립·블렌드·립싱크·전환 |
| 14 | GLB와 게임 검수 | Blender / Godot | GLB·재임포트·플레이 결과 |

눈썹·속눈썹 제작과 몸 부품 제작은 얼굴 형태를 기준으로 일부 병행할 수 있습니다. 최종 얼굴 Shape Key를 만드는 시점에는 피부의 정점 수와 순서를 안정시켜야 합니다. 리토폴로지 전의 임시 표정 테스트는 최종 리깅 완료로 기록하지 않습니다.

### 단계별 통과 기준

1. **디자인과 전신 기준:** 얼굴 인상과 비율 일치, 중립 포즈, 사용자 검토.
2. **파트별 이미지와 규격:** 정면·좌·후·우 일관성, 한쪽 대칭 부품 생성.
3. **입 벌린 머리 생성:** 구강 깊이와 치아·혀 확인, 실제 경계·분리 구조 검사.
4. **HD 헤어 생성과 맞춤:** 두피 공간·뒷머리·앞머리 실루엣·관통 검사.
5. **신체와 복장 원형 생성:** 숨은 신체와 의상 안쪽 확보, 사용자 단계 검토.
6. **조립과 기본 얼굴 형태:** 정면·사선·측면 인상, 눈꺼풀·입술·턱 형상, 피부 연결.
7. **눈썹과 속눈썹 제작:** 뿌리 밀착·UV 클리핑·양면·투명도·자연스러운 방향.
8. **변형용 리토폴로지:** 눈·입 루프, 안쪽 두께, 접합·노멀·잔여 조각 검사.
9. **UV와 베이크 및 텍스처:** 얼굴 인상·재질·경계·베이크 오류, 사선·조명 검사.
10. **몸과 손 리깅:** 관절·엄지 대립·쥐기·도구·좌우 변형.
11. **페이스 리깅과표정:** 정면·측면 배치, 역할 그룹·피부·파츠 웨이트 검수.
12. **표정 보정과 Shape Key 베이크:** 0·25·50·75·100%·좌우·조합·추종·토폴로지 유지.
13. **몸·얼굴 동작과 립싱크:** 루프·속도·접지·깜빡임·시선·얼굴 몸 동시 재생.
14. **GLB와 게임 검수:** 모프 및 파츠 유지, 투명도·머리 회전·복장 교체·성능 검수.

기존 문서에는 UV·재질을 먼저 생성한 P2 실험과 HD를 무채색으로 만들고 나중에 베이크한 경로가 모두 있습니다. 관리 프로그램에서는 단일 강제 순서로 과거 기록을 덮어쓰지 않고, 선택한 경로와 실제 실행 순서를 보존해야 합니다.

## 머리와 얼굴 제작

### 생성용 참조

Stefan의 말하는 아바타 제작 자료에서는 헤어·장신구를 제외한 머리 참조를 준비하고, **입술이 떨어져 입안과 치아·혀가 보이는 상태**로 생성합니다. 여기서 확보한 내부 구조를 유지하면서 Blender에서 입을 닫아 기본형을 만듭니다.

우리 기록에서는 머리 단독 → 목과 어깨가 있는 흉상 → **목과 쇄골이 이어지는 범위**로 참조가 조정됐습니다. 정면만으로 판단하지 않고 측면·사선에서 얼굴 깊이, 코·입술·턱, 광대와 귀를 비교합니다. 입을 과하게 벌리거나 미소로 얼굴 인상이 변한 참조는 기본형과 대조합니다.

헤어 다면 입력은 **정면·좌측·후면·우측**을 사용한 기록이 있습니다. 상단·하단 이미지는 별도 검수 참고로 보존하며 당시 P2 멀티뷰 API의 입력 슬롯으로 제출한 것은 아닙니다. [원본에서 사용한 멀티뷰 문서](https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/p)

### HD와 Smart Mesh 비교 결과

| 항목 | 새 열린 입 HD | 같은 참조의 새 Smart Mesh P2 |
|---|---|---|
| 관측 생성비 | 40크레딧 | 100크레딧 |
| 원본 밀도 | 235,571정점·471,138삼각형 | 15,748정점·16,784면 |
| 쿼드 | 고밀도 삼각형 원본 | 14,514쿼드 기록 |
| 입 내부 | 얕고 치아·혀가 붙은 부조 같은 형태 | 더 깊은 구강·별도 치아·혀에 해당하는 연결 성분 |
| 문제 | 눈 반사광 돌기·하단 불필요 면·구강 보강 필요 | 열린 경계 293개·비다양체 엣지 393개 기록 |
| 후속 | 형태 수정용 비교 원본 | 최신 얼굴 작업의 원형 |

P2의 393개 비다양체 엣지 수에는 열린 경계가 포함돼 있습니다. 두 수를 별도 불량 개수로 합산하지 않습니다. 처음에는 한 오브젝트 안에 여러 연결 성분으로 존재했으며, 각각 독립 오브젝트인 것과 구분해야 합니다.

HD의 면 수가 많고 열린 경계가 없다는 사실은 구강이나 변형 구조가 더 좋다는 뜻이 아닙니다. 이 비교에서 P2가 더 다듬기 좋은 입안을 제공한 것이며 모든 얼굴에서 같은 결과를 보장하지 않습니다.

### Blender 형태 정리

원본을 숨긴 컬렉션에 보존하고 작업용 복사본에서 크기·위치·회전·스케일을 정리합니다. 마스킹, Grab·Elastic Grab, Clay, Smooth, Trim, 필요한 경우 Edit Mode의 정점·엣지 편집을 사용합니다. 자동 스크립트는 반복 처리와 검사를 돕지만 정면·사선·측면 검토를 대신하지 않습니다.

현재 생산 실험 좌표는 **앞 +X / 위 +Z / 좌우 Y**로 기록됐습니다. 따라서 대칭면은 **Y=0**, Mirror 축은 Y입니다. 강의에서 쓰는 축을 그대로 복사하지 않고 입력 모델을 같은 기준으로 맞춥니다. 기존 B의 게임 크기 기준은 1.7m이며 목·손목·발목의 새 접합 치수는 실제 몸체에서 측정해야 합니다.

눈·입 주변을 얼굴 피부 위에 따로 얹는 임시 방식은 겹침과 틈을 만들었던 실패 사례가 있습니다. 얼굴 피부 자체에 눈꺼풀·입술의 연결 흐름과 두께를 구성하는 기준으로 정리합니다.

## 눈과 눈꺼풀 제작

생성된 눈의 표면·반사광·홍채 돌기는 위치 참고로 남기고, 필요한 경우 Blender **UV Sphere 안구로 교체**합니다. 한쪽 안구의 크기·회전 중심·위치를 맞춘 후 반대쪽을 미러하고 좌우 회전을 분리합니다. 홍채·동공은 재질·텍스처로 표현하거나 디자인에 맞는 별도 표면을 사용합니다.

위·아래 눈꺼풀은 **얼굴 피부의 일부**입니다. 속눈썹 카드를 붙였다고 눈꺼풀이 만들어진 것은 아닙니다. 눈꺼풀 가장자리와 안쪽 두께가 안구 곡면을 따라가고, 완전히 감을 때 흰자와 홍채를 덮도록 구성합니다.

검수할 사항은 다음과 같습니다.

- 기본 상태에서 눈알이 지나치게 뒤로 들어가거나 피부와 틈이 생기지 않는지.
- 정면·측면에서 눈 주위가 과하게 파여 졸려 보이거나 두꺼운 테두리처럼 되지 않는지.
- 깜빡임 0·25·50·75·100%에서 눈꺼풀이 튀거나 접히지 않는지.
- 좌우 시선과 위아래 시선에서 안구가 피부 밖으로 빠져나오지 않는지.
- 깜빡임과 시선을 함께 적용했을 때 속눈썹 뿌리가 들뜨지 않는지.
- 홍채의 질감·반사광·눈 재질이 유지되는지.

과거 보고서에는 눈 중심의 광선 검사나 표본 자세 검사 통과가 있습니다. 이후 사용자 검토에서 깊은 눈가·주름·속눈썹 문제가 다시 발견됐으므로 **검사 통과를 완성된 시각 품질로 재분류하지 않습니다.**

## 입 내부와 닫힌 입 기본형

입안에는 입술 안쪽 두께와 구강 공간이 있어야 합니다. 위·아래 치아와 잇몸, 혀는 필요 수준에 맞춰 별도로 다루며, 아래쪽 치열·잇몸과 혀의 움직임은 턱 벌림과 함께 검수합니다. 피부를 숨긴 단면으로 내부 배치를 확인하는 것과 실제 입술을 벌려 내부가 드러나는 것은 다른 검사입니다.

작업 순서는 다음과 같습니다.

1. 입을 벌린 Tripo 원형에서 내부 공간·치아·혀·불필요 조각을 확인합니다.
2. 역할이 다른 연결 성분을 분리하고, 붙은 치아·혀나 얕은 구강은 보강합니다.
3. 입술을 마스킹해 닫으면서 **턱·볼·인중·입안 부품 위치도 함께 조정**합니다.
4. 다문 입에서 입꼬리의 깊은 홈, 과도한 U자 아랫입술, 눌린 턱, 비정상적인 측면 돌출을 검토합니다.
5. 내부 표면의 점막색·재질과 치아 색을 설정합니다.
6. 기본값은 다문 입으로 저장하고 열린 원형 또는 검사 Shape Key를 보존합니다.
7. 입 벌림·입 다물기·미소의 연속 변형과 조합을 검사합니다.

과거 hybrid v2의 `MOUTH_INSPECTION_control.open`과 최신 P2 조립본의 열린 원형 보존은 **내부 배치·닫힘 검사 장치**입니다. 전체 페이스 리그나 립싱크 완료를 의미하지 않습니다. 새 P2 조립본은 FACE_CONTROLS의 mouth_open 값을 0~1로 조절하는 것으로 완료 보고됐습니다.

## 눈썹 속눈썹 헤어 제작

### 현재 사용하는 파츠 방식

| 파츠 | 제작 방식 | 리깅에서 요구할 일 |
|---|---|---|
| 눈썹 | 한쪽 간단한 메시·UV·RGBA 텍스처 → Mirror | 이마·눈썹 표정에 맞춰 좌우 독립 변형 |
| 위 속눈썹 | 한쪽 UV 알파 카드 → Mirror | 윗눈꺼풀의 깜빡임·시선 보정을 추종 |
| 아래 속눈썹 | 한쪽 UV 알파 카드 → Mirror | 아랫눈꺼풀에 맞춰 움직임 |
| 헤어 | 4방향 Tripo HD 원본 → 두상 맞춤·형태 수정 | 머리·목 회전, 얼굴·귀·두피 간섭 검사 |
| 앞머리·옆머리·뒷머리 | 필요 영역을 분리하거나 독립 편집 | 스타일 실루엣과 의도한 비대칭 유지 |

알파 카드는 털 이미지가 붙은 얇은 메시입니다. 뿌리는 눈꺼풀에 맞추고 끝은 자연스럽게 밖으로 휘게 만듭니다. UV가 아틀라스의 다른 줄을 읽거나 타일 반복이 생겨 얼굴 옆으로 무늬가 새지 않도록 범위와 클리핑을 확인합니다. 카드 밀착만으로 표정 추종이 완성된 것은 아닙니다.

헤어에는 얼굴 관통부 제거, 눈 가림 줄이기, 뒷머리 하단 보강, 두피 공간 확인 작업이 있었습니다. 속이 빈 곳을 단순한 판으로 막은 결과가 부자연스럽다는 피드백이 있어, 모발의 묶음·흐름·두께를 표현하는 기준으로 수정했습니다.

### 자동화와 추가 후보

**Hair Tool**은 정리된 가이드 메시나 커브에서 모발·카드를 만들고 UV와 베이크를 돕는 유료 애드온 후보입니다. `Curves from Grid Surface`는 모발 방향으로 배열된 쿼드와 뿌리 경계가 필요합니다. Tripo의 불규칙한 덩어리를 넣는 것만으로 완성된 가닥·헤어 카드가 나오는 기능으로 검증되지 않았습니다. [제작자 문서](https://joseconseco.github.io/HairTool_3_Documentation/main_workflows/hair_from_surface.html)

Blender 기본 기능인 **Interpolate Hair Curves**는 가이드 사이의 모발과 밀도, **Clump Hair Curves**는 묶임, **Attach Hair Curves to Surface / Deform Curves on Surface**는 표면 UV와 변형에 따른 뿌리 연결을 다루는 조사 후보입니다. 현재 카드 제작에 모두 적용한 상태는 아닙니다.

**Unreal Hair Card Generator**는 이미 만든 Groom, **Houdini Generate Hair Cards**는 모발 커브·가이드를 입력으로 하는 대안입니다. **HairStep·Neural Haircut**은 가닥 복원 연구 참고이며 게임용 메시·LOD·리그까지 완성하는 도구로 채택하지 않았습니다.

## 페이스 리깅과 표정

### 리깅 전 준비

피부 토폴로지와 기본 얼굴을 먼저 확정합니다. 얼굴 피부·좌우 눈·치아·혀·눈썹·속눈썹·장식을 역할에 맞춰 분류하고, 머리카락과 관계없는 표면을 랜드마크 기준으로 잘못 선택하지 않도록 합니다. 기존 몸 리그의 머리 회전과 새 얼굴 리그의 머리 회전이 중복 적용되지 않게 담당을 정합니다.

정점 수·순서가 다른 웃는 얼굴을 별도 AI 생성해서 중립 얼굴의 Shape Key로 바로 사용하는 방식은 채택하지 않았습니다. 최종 표정은 같은 기준 얼굴 정점을 변형하는 방식으로 관리합니다.

### Faceit 경로

원본에서 검토한 절차는 다음과 같습니다.

1. 얼굴 관련 오브젝트 등록과 역할 그룹 할당.
2. 정면의 눈·입·턱 랜드마크 배치 후 측면 깊이 조정.
3. 얼굴 리그 생성과 바인딩·웨이트 확인.
4. ARKit 기본 표정, 필요할 때 발음·혀·사용자 표정 불러오기.
5. 각 표정을 **본 조절 → 스컬프 보정 → 좌우 복사** 순서로 수정.
6. 보정에 쓴 모디파이어를 포함해 **Shape Key로 베이크**.
7. 베이크 결과와 표정 조합 검사.
8. 컨트롤 리그 생성, 몸의 머리 본 추종 또는 리그 연결.
9. 직접 키프레임·영상 추적·음성 모션 연결.
10. 게임용 내보내기와 Godot 재생 검사.

Faceit의 장점으로 기록된 것은 반자동 리깅·웨이트, 표정 프리셋, 표정별 수정, 미러·강도 조절, 베이크 후 수정 복귀, 표정·모션 재사용입니다. **얼굴을 만들어주는 모델링 도구의 역할과는 구분**합니다. 판매처에도 표정 편집·Shape Key 베이크·모션 연결 기능이 안내돼 있습니다. [Faceit 공식 판매처](https://superhivemarket.com/products/faceit)

`mouthClose`는 `jawOpen`과 조합해 쓰는 역할이 있으므로 단독 모양만으로 판정하지 않습니다. 표정 제작에 사용하는 얼굴 본 리그와 완성된 Shape Key를 조작하는 컨트롤 리그도 별개로 기록합니다.

### 무료 Rigify 경로

얼굴 메타리그를 모델에 맞춰 배치하고 리그를 생성한 뒤 몸의 머리 본에 연결하는 방법을 검토했습니다. 눈·속눈썹·치아·혀는 버텍스 그룹과 웨이트를 직접 확인해야 합니다. Mixamo 몸 리그에 Rigify 얼굴 리그를 추가하는 영상이 참고 자료입니다.

MPFB 템플릿 시험에서는 Shape Key가 얼굴 표정을 담당하고 얼굴 본을 기본 자세로 유지해 이중 변형을 피했습니다. 이 시험이 실제 Tripo 얼굴의 바인딩·변형 시험을 대신하지 않습니다.

### 첫 표정 세트와 검사

먼저 중립, 좌우·양쪽 깜빡임, 시선, 입 벌림, 미소, 눈썹 올리기를 검사합니다. 그 뒤 표정 수와 발음 모양을 늘립니다.

- 0·25·50·75·100%와 중간 상태를 렌더합니다.
- 좌우 각각 제어하고 양쪽 제어도 확인합니다.
- `jawOpen + mouthClose`, 미소+입 벌림, 시선+깜빡임, 눈썹+깜빡임을 검사합니다.
- 속눈썹·치아·잇몸·혀의 추종을 확인합니다.
- 표정 시작과 끝의 얼굴 인상이 기준 얼굴로 돌아오는지 확인합니다.
- 머리·몸 동작과 동시 재생하고 내보낸 모프 채널을 검사합니다.

## 몸 손 의상과 애니메이션

### 몸과 손

초기 Tripo 몸 리그는 41본이며 개별 손가락·상세 얼굴 리그가 없었습니다. 기존 게임의 71본 B에는 별도 보강 손 구조가 있습니다. **새 41본 실험과 기존 71본을 같은 완성도로 취급하지 않습니다.**

독립 손 실험은 **Scenario 참조 이미지 → Tripo 손 생성 → MediaPipe 21점 → Blender 깊이 조회 → 손바닥과 손가락 16본 → 자동 웨이트·병합·스무딩·정규화 → 직접 쥐기 동작**으로 진행됐습니다. 텍스트 손 생성은 형상이 부적합해 채택하지 않았고, 이미지 손도 실제 몸 손목에 맞춤·좌우 엄지 방향·도구 접촉 검수가 남았습니다.

AccuRIG는 몸·손 관절 후보입니다. **무료 AccuRIG는 얼굴 뼈 생성이나 페이스 리깅을 지원하지 않습니다.** [Reallusion 비교 자료](https://magazine.reallusion.com/2025/06/30/free-accurig-versus-cc-advanced-accurig/amp/)

### 의상과 부품

독립 의상에는 옷 아래의 신체, 목·소매·밑단 두께와 안쪽, 신발 안 발이 있어야 합니다. 생성 전신의 표면을 조각으로 나누는 것만으로 이 구조가 완성되지는 않습니다. 벨트·버클·주머니·끈·금속 등은 딱딱한 부착물과 변형할 부품을 구분합니다.

목·손목·발목의 피부 경계는 위치·면 흐름·웨이트를 맞춥니다. 게임용 피부를 결합해야 한다면 편집 원본을 보존한 파생본에서 처리하고 부품 대응표를 남깁니다.

### 기록된 몸 애니메이션 경로

| 경로 | 실제 제작 | 주의할 점 |
|---|---|---|
| Blender 직접 작성 | Python으로 관절 회전·위치 키프레임. 살피기·걷기·달리기·소환, 해루 동작과 손 쥐기 | 전용 동작 시제품이며 모든 프레임을 수동 조율한 완성형으로 기록하지 않음 |
| Tripo 프리셋 | idle·walk·run 요청 후 루트·루프 보정 | 요청한 모든 클립이 출력에 포함됐는지 확인 |
| 참고 영상 추적 | Scenario Seedance 2 / PixVerse V6 / Kling V3 → MediaPipe Pose Heavy → Blender FK 전이 | 단일 측면 영상의 깊이 추정. 이번 몸 추적에 얼굴·개별 손가락 없음 |

영상 몸 동작은 약 5초 시퀀스 3개와 별도 반복 클립 3개로 정리됐습니다. 관절 범위·몸 높이·부츠 접점·반복 경계를 보정하고 60fps로 베이크한 기록입니다. 모션의 수평 이동은 게임 모터·서버가 담당하고 루트 이동과 중복되지 않게 합니다.

실험 보행 기준 속도는 약 0.69~1.49m/s, 본 게임 걷기·달리기는 2.8/4.5m/s 기록이 있어 고정 재생 속도로 바로 적용하지 않습니다. 루프·블렌드·발 IK 중 하나의 성공만으로 모든 정지·회전·경사·도구 동작이 자연스러워진 것은 아닙니다.

### 얼굴 모션과 립싱크 후보

MediaPipe·BlendArMocap은 영상 추적, Rhubarb는 음성의 입 모양 타이밍, Audio2Face는 음성 기반 얼굴 모션 후보입니다. 모두 준비된 얼굴 변형에 연결하는 단계입니다. 얼굴 피부·입안·표정을 새로 만드는 작업과 구분합니다.

Rhubarb 한국어는 언어 독립적인 `phonetic` 경로 시험이 제안됐으며 실제 정확도 시험은 없습니다. Audio2Face는 RTX 2070에서 실행·성능 검증이 없고 CUDA·TensorRT·모델 조건을 확인해야 합니다. 옛 Omniverse Launcher 설치 영상은 작업 원리 참고로 보존합니다.

## 프로그램 애드온과 비용 분류

아래 상태는 원본 대화와 저장 문서의 기록입니다. **설치·사용 확인**과 **후보**를 분리했습니다. 도구 비용이 무료여도 컴퓨터 자원·다른 서비스·별도 콘텐츠의 비용까지 무료가 되는 것은 아닙니다.

| 도구 | 무료 또는 유료 | 역할 | 원본에서 확인한 상태 |
|---|---|---|---|
| Tripo Smart Mesh P2 | 유료 API 서비스 | 입 벌린 머리·신체·의상·손의 원형 생성 | 사용 확인 |
| Tripo HD H3.1 | 유료 API 서비스 | 고밀도 형태 원본과 헤어 생성 | 사용 확인 |
| Tripo Studio 및 Segmentation | 요금제와 크레딧에 따름 | 부품 분할·수정·재질·리토폴로지 조사 | API 분할 사용 확인 / Studio 기능 자료 검토 |
| Tripo 자동 리깅 | 유료 API 서비스 | 몸 뼈와 스킨 웨이트 생성 | 사용 확인 |
| Tripo 애니메이션 프리셋 | 유료 API 서비스 | idle walk run 등 초기 모션 시험 | 사용 확인 |
| Blender | 무료 오픈소스 | 편집·조립·Sculpt·Retopology·UV·Bake·리깅·렌더·내보내기 | 사용 확인 |
| Rigify | 무료 오픈소스 | 몸·손·얼굴 메타리그와 제어 리그 | 설치 및 템플릿 시험 확인 |
| Faceit | 유료 | 랜드마크 기반 얼굴 리그·표정 보정·Shape Key 베이크·컨트롤 리그 | 구매 의향 / 설치·Tripo 적용 성공 미확인 |
| MPFB | 무료 오픈소스 | 표준 사람 메시·부품·표정 템플릿 시험 | 설치 및 기본 얼굴 시험 확인 / 주 모델 생성 경로로 미채택 |
| MakeHuman System Assets Faceunits Visemes | 선택한 공식 팩 무료 CC0 | 눈·눈썹·속눈썹·치아·혀 및 52개 표정·발음 모양 | 설치 및 템플릿 시험 확인 |
| Hair Tool | 유료 | 가이드 커브·정리된 그리드에서 모발 및 헤어 카드·UV·베이크 | 후보 / 설치·Tripo 변환 미확인 |
| Blender Hair Curves 및 Geometry Nodes | Blender 기본 무료 | Interpolate·Clump·Attach·Deform Curves on Surface | 자료 검토 / 해당 제작본 적용 미확인 |
| Unreal Hair Card Generator | Unreal 라이선스 조건에 따름 | Groom 모발에서 헤어 카드·텍스처 | 대안 자료 검토 |
| Houdini Generate Hair Cards | Houdini 라이선스에 따름 | 모발 커브·가이드에서 카드 생성 | 대안 자료 검토 |
| RetopoFlow | 유료 배포 및 공개 소스 경로 있음 | HD 형상 위에 눈·입·관절의 변형용 면 흐름 제작 | 강의 및 후보 / 설치 미확인 |
| ZBrush | 유료 | 정밀 얼굴 스컬프·마스킹·비율·눈꺼풀·입술 보정 | 후보 / 설치 미확인 |
| Faceform Wrap | 유료 | 기준 얼굴 메시를 여러 얼굴 형상에 맞추기 | 고급 후보 / 시험 미확인 |
| AccuRIG | 기본 무료 / CC 고급 버전 유료 | 몸 관절·손가락·엄지·캘리브레이션 | 강의 후보 / 이번 무료 얼굴 시험에서 미설치 |
| Mixamo | 무료 Adobe ID 필요 | 몸 리그 및 Rigify 얼굴 연결 자료 | 참고 자료 / 기존 전용 모션 제작에는 미사용 |
| Krita | 무료 오픈소스 | 텍스처·마스킹·색 보정·편집 원본 | 설치 및 변환 시험 확인 |
| Material Maker | 무료 오픈소스 | 절차 재질 그래프 | 설치·실행 확인 / CLI export 미검증 |
| Substance 3D Painter | 유료 | 피부·헤어·복장 텍스처와 베이크 | 후보 / 라이선스 미확인·미설치 |
| MediaPipe | 무료 오픈소스 로컬 처리 | 영상 몸·손·얼굴 랜드마크 | 몸·손 사용 확인 / 얼굴 연결 후보 |
| BlendArMocap | 무료 오픈소스 | MediaPipe 몸·손·얼굴 데이터를 Rigify 등에 연결 | 후보 / 설치·품질 미확인 |
| Rhubarb Lip Sync | 무료 오픈소스 | 음성의 입 모양 타이밍 추출 | 후보 / 미설치·한국어 시험 미확인 |
| NVIDIA Audio2Face 3D | 공개 코드 / 모델·실행 비용 별도 | 음성에서 얼굴 변형 가중치·립싱크 생성 | 후보 / RTX 2070 실행 미확인 |
| Character Creator | 유료 | 표준 얼굴·몸 구조와 리그 생태계 | 대안 자료 검토 / 미도입 |
| Headshot | 유료 | 이미지 또는 머리 모델을 CC 구조로 변환·보정 | 대안 자료 검토 / 미도입 |
| iClone | 유료 | Reallusion 몸·얼굴 모션 편집 | 대안 자료 검토 / 미도입 |
| AccuFACE | 유료 | 영상·카메라 얼굴 추적 | 대안 자료 검토 / 미도입 |
| KeenTools FaceBuilder | 유료 구독 / 15일 체험 | 사진 기반 표준 두상 맞춤 | 대안 자료 검토 / 미도입 |
| KeenTools FaceTracker | 유료 | 영상 얼굴 추적과 ARKit Rigify 전이 | 대안 자료 검토 / 미도입 |
| VRM Blender Add-on 및 VSeeFace | 무료 공개 도구 / 원본 사례 | Stefan의 VRM 출력·얼굴 추적 시험 | 영상 참고 / 프로젝트 적용 미확인 |
| HairStep | 공개 연구 / 일부 비상업 조건 | 단일 사진의 방향·깊이에서 가닥 복원 | 연구 참고 / 미실행 |
| Neural Haircut | 공개 연구 / 의존 모델 조건 확인 필요 | 영상·다시점에서 모발 가닥 복원 | 연구 참고 / 미실행 |
| Scenario | 요금제·CU 과금 | 헤어·손 참조와 모션 참고 영상 생성 | 사용 확인 |
| 내장 이미지 생성 도구 | 계정 사용량 조건 / 개별 단가 미확인 | 동일 디자인·다면·입 벌린 머리·투명 알파 참조 | 사용 확인 |
| Godot | 무료 오픈소스 | GLB·뼈·모프·클립 재생과 게임 플레이 검수 | 사용 확인 |
| Unity | 라이선스 조건에 따름 | Stefan 강의의 엔진 내보내기 참고 | 강의 참고 / 최종 게임 엔진 아님 |
| Unreal ML Deformer | Unreal 라이선스 조건에 따름 | 학습 데이터의 변형 재현 | 첨부 자료 교정 / 채택 안 함 |
| xatlas | 오픈소스 / 강의에서 확인 | 자동 UV 관련 Tripo 심화 강의 언급 | 자료에 언급 / 로컬 설치·활용 미확인 |
| Blender Python 및 LLM 자동화 | Blender 무료 / LLM 계정·API 조건 별도 | 반복 정렬·웨이트·키프레임·베이크·렌더·검사 | Python 사용 확인 / Claude는 강의 참고 |
| Pinokio | 배포·개별 앱 조건 별도 | 도구 설치와 로컬 실행 후보 | 기존 제어 API 연결 실패 기록 |

### 도구별 조건

- **Tripo Smart Mesh P2:** 요청 쿼드 수가 변형용 얼굴 토폴로지 완성을 보장하지 않음. 최신 머리 100크레딧은 해당 설정 실측. [공식 자료](https://developers.tripo3d.ai/en/docs/generation-image-to-model/p)
- **Tripo HD H3.1:** HD 원본을 보존하고 형태 승인 후 게임용 메시 제작. 이번 열린 입 HD는 구강이 얕아 P2로 교체. [공식 자료](https://developers.tripo3d.ai/en/docs/generation-image-to-model/standard)
- **Tripo Studio 및 Segmentation:** 87조각을 Blender에서 40개 의미 부위로 묶음. 의상 내부와 숨은 신체 자동 복원 아님. [공식 자료](https://www.tripo3d.ai/blog/tripo-studio-tutorial-english)
- **Tripo 자동 리깅:** 41본 샘플은 상세 얼굴·손가락 리그 없음. mixamo 규격 선택이 얼굴 리그 추가를 의미하지 않음. [공식 자료](https://developers.tripo3d.ai/en/docs/animations-rig)
- **Tripo 애니메이션 프리셋:** 제자리 옵션에도 루트 전진이 남은 사례. 요청 성공과 클립 포함 여부 별도 확인. [공식 자료](https://developers.tripo3d.ai/en/pricing)
- **Blender:** Mirror·UV Sphere·Shape Key·Weight Paint·Python은 기본 기능. [공식 자료](https://www.blender.org/)
- **Rigify:** Tripo 얼굴의 배치·바인딩·웨이트 수정은 별도. MPFB의 Shape Key와 같은 부위 이중 변형 방지. [공식 자료](https://docs.blender.org/manual/en/4.5/addons/rigging/rigify/index.html)
- **Faceit:** 모델링·입안·토폴로지를 대신 완성하지 않음. 애드온 사용/미사용 비교는 계획. [공식 자료](https://superhivemarket.com/products/faceit)
- **MPFB:** 사용자 최종 결정은 모델까지 Tripo로 생성. 템플릿 결과를 Tripo 얼굴의 리깅 성공으로 취급하지 않음. [공식 자료](https://extensions.blender.org/add-ons/mpfb/)
- **MakeHuman System Assets Faceunits Visemes:** 다른 외부 자산 팩의 라이선스까지 CC0로 일반화하지 않음. [공식 자료](https://static.makehumancommunity.org/assets/assetpacks.html)
- **Hair Tool:** 임의의 Tripo 덩어리 자동 완성 아님. 모발 방향의 쿼드와 뿌리 경계 또는 커브 준비 필요. [공식 자료](https://bartoszstyperek.gumroad.com/l/hairtool?layout=profile&recommended_by=more_like_this)
- **Blender Hair Curves 및 Geometry Nodes:** 게임용 카드·메시·웨이트·표정으로 변환 검수. 현재 눈썹·속눈썹은 알파 카드 우선. [공식 자료](https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/generation/interpolate_hair_curves.html)
- **Unreal Hair Card Generator:** Tripo 덩어리 메시가 직접 입력되는 흐름 아님. 게임 엔진 변경 결정 없음. [공식 자료](https://dev.epicgames.com/documentation/en-us/unreal-engine/hair-card-generator-for-grooms-in-unreal-engine)
- **Houdini Generate Hair Cards:** 별도 Houdini 환경·가이드가 필요. 상업용 라이선스와 무료 학습용 조건 구분. [공식 자료](https://www.sidefx.com/docs/houdini/shelf/groom_haircardgen.html)
- **RetopoFlow:** 공개 강의 무료와 애드온 판매는 구분. 버전 호환·지원 조건 확인 필요. [공식 자료](https://github.com/CGCookie/retopoflow)
- **ZBrush:** Tripo DCC Bridge 자료 검토. 기존 얼굴 인상 보존은 수동 작업 필요. [공식 자료](https://www.maxon.net/en/zbrush)
- **Faceform Wrap:** 기준 메시·표정 대응 자료 필요. 여러 NPC 토폴로지 일관성 후보. [공식 자료](https://docs.faceform.com/Wrap/)
- **AccuRIG:** 무료 AccuRIG는 얼굴 리깅 지원 안 함. [공식 자료](https://www.reallusion.com/auto-rig/accurig/default.html)
- **Mixamo:** 이번 기록에서 상세 페이스 리깅 도구로 채택 안 함. 사용자 전용 동작은 Blender 제작. [공식 자료](https://www.mixamo.com/)
- **Krita:** ORA KRA PNG 작업 확인. 에이전트가 직접 붓질한 것으로 기록하지 않음. [공식 자료](https://krita.org/en/download/)
- **Material Maker:** Substance Painter 전체 기능 대체로 검증되지 않음. [공식 자료](https://github.com/RodZill4/material-maker)
- **Substance 3D Painter:** 사용자 설치 의향과 실제 설치·라이선스 확보를 구분. [공식 자료](https://www.adobe.com/products/substance3d/apps/painter.html)
- **MediaPipe:** 추적이 얼굴 Shape Key 또는 손 형상을 만들지 않음. 측면 단일 영상 깊이는 추정. [공식 자료](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)
- **BlendArMocap:** 2022년 영상 설치 방식과 현행 Tasks API 포크 구분. [공식 자료](https://github.com/cgtinker/BlendArMocap)
- **Rhubarb Lip Sync:** phonetic 경로 한국어 시험 후보. 표정 자체·얼굴 모델 생성 아님. [공식 자료](https://github.com/DanielSWolf/rhubarb-lip-sync)
- **NVIDIA Audio2Face 3D:** CUDA TensorRT 요구·코드와 모델 조건 구분. 옛 Omniverse Launcher GUI 설치법 그대로 사용 안 함. [공식 자료](https://github.com/NVIDIA/Audio2Face-3D-SDK)
- **Character Creator:** 사용자 Tripo 모델링 방침의 대안 기록. 현재 주 제작 경로 아님. [공식 자료](https://www.reallusion.com/character-creator/)
- **Headshot:** 컨셉 비율 수동 복원과 Tripo에서 CC로 변환 품질 검수 필요. [공식 자료](https://www.reallusion.com/character-creator/headshot/)
- **iClone:** 관련 플러그인 별도. Godot 전달 경로 미검증. [공식 자료](https://www.reallusion.com/iclone/)
- **AccuFACE:** 임의 Tripo 얼굴에 바로 적용 성공으로 기록하지 않음. [공식 자료](https://magazine.reallusion.com/2026/07/30/accuface-2-grand-launch-professional-grade-facial-mocap-for-cc5-hd-characters/)
- **KeenTools FaceBuilder:** 상시 무료 아님. Tripo 모델을 만들기로 한 현재 방침의 주 도구 아님. [공식 자료](https://keentools.io/products/facebuilder-for-blender)
- **KeenTools FaceTracker:** 추적용 FaceBuilder 토폴로지 제약. [공식 자료](https://keentools.io/products/facetracker-for-blender)
- **VRM Blender Add-on 및 VSeeFace:** 휴대폰 추적 앱과 장치의 비용 별도 확인. 본 게임 GLB Godot 검수의 대체 아님. [공식 자료](https://vrm-addon-for-blender.info/en/)
- **HairStep:** HiSa HiDa와 관련 체크포인트 비상업 연구 조건. 게임용 LOD·리그 완성 아님. [공식 자료](https://github.com/GAP-LAB-CUHK-SZ/HairStep)
- **Neural Haircut:** FLAME 등 의존 데이터·모델 조건과 RTX 2070 실행 미확인. [공식 자료](https://samsunglabs.github.io/NeuralHaircut/)
- **Scenario:** 모델별 CU 실측 분리. 참고 영상 생성과 3D 애니메이션 제작은 다른 단계. [공식 자료](https://www.scenario.com/)
- **내장 이미지 생성 도구:** 원본 기록에서 Tripo Scenario 추가 소비 0인 이미지 작업 존재. 이미지 생성 자체의 비용이 0이라는 뜻 아님.
- **Godot:** Unity 강의의 방법을 Godot 기준으로 적용. 게임 엔진 변경 결정 없음. [공식 자료](https://godotengine.org/)
- **Unity:** 최종 게임 엔진 Godot와 구분. [공식 자료](https://unity.com/)
- **Unreal ML Deformer:** 범용 헤어 자동 생성·충돌 해결 도구 아님. [공식 자료](https://dev.epicgames.com/documentation/unreal-engine/ml-deformer-framework-in-unreal-engine?lang=en-US)
- **xatlas:** 강의에서의 언급과 현재 제작본의 UV 적용을 구분. [공식 자료](https://github.com/jpcy/xatlas)
- **Blender Python 및 LLM 자동화:** 수치 검사와 최종 시각적 품질 승인 구분. GPT 모델 사용량과 별도 API 청구 구분.
- **Pinokio:** 기존 기록에서는 pterm localhost 연결 불가. 공식 포터블 도구로 진행.

추가 기능으로 자료에 언급된 xatlas는 Tripo 심화 강의의 UV 관련 내용입니다. 설치나 현재 제작본 적용이 확인된 애드온으로 분류하지 않습니다. 첨부 자료와 파이프라인 명세에 등장한 MetaHuman·Cascadeur·Rodin·Live Link Face·Wonder Dynamics도 미채택 대안으로 보존했습니다. 아래는 도입 완료 목록이 아닙니다.



### 첨부 자료와 명세의 미채택 대안

| 도구 | 비용 | 기록 상태와 조건 |
|---|---|---|
| [Cascadeur](https://cascadeur.com/plans) | 무료 비상업·제한 출력 / 유료 Indie Pro | 후보 / 미도입. Free는 비상업·CASC 출력 제한. 외부 게임 전달을 위한 출력·상업 조건 확인. 범용 헤어 재구성 도구로 채택하지 않음. |
| [MetaHuman Mesh to MetaHuman DNA Groom](https://www.metahuman.com/license) | 매출 100만 USD 미만 무료 조건 / 이상 Unreal 조건 | 첨부·파이프라인에 대안 언급 / 미도입. 현재 Tripo 모델 생성 방침을 대체한 결정 없음. 임의 Tripo 얼굴 디자인 보존·Godot 전달은 미검증. |
| [Hyper3D Rodin](https://hyper3d.ai/) | 서비스 요금제·크레딧 조건 | 첨부 자료 언급 / 미채택·미사용. Tripo 주 경로와 별도. 첨부의 헤어 자동 카드 변환 주장은 실제 입력·출력으로 검증되지 않음. |
| [Live Link Face](https://apps.apple.com/us/app/live-link-face/id1495370836) | 앱 무료 / 장치·연동 환경 별도 | 첨부 자료 언급 / 미도입. iOS 앱 무료 배포 확인. 호환 장치와 추적·리타게팅 환경 필요. 임의 Tripo 리그 직접 적용 성공 기록 없음. |
| [Wonder Dynamics Wonder Studio 및 Flow Studio](https://www.autodesk.com/products/flow-studio/overview) | 무료 티어 및 유료 크레딧 플랜 | 첨부 언급 / 미채택·미사용. 현재 Autodesk Flow Studio 명칭 확인. 본 프로젝트 얼굴 추적·Tripo 연결 성공은 미확인. |

## 과거 워크플로우와 변경 과정

다음 A–K는 이번 이관에서 비교를 위해 붙인 이름입니다. 폴더의 v1·v2·v3와 같은 의미가 아닙니다. 특히 `face_rig_manual_v3`와 `explorer_b_pipeline_v3`는 별도 실험입니다.

| 경로 | 제작 흐름 | 결과와 변경 이유 | 분류 |
|---|---|---|---|
| A 전신 통째 생성과 초기 몸 리그 | Scenario/Tripo 전신→Tripo 41본→Blender 전용 모션→Godot | 빠른 몸 동작 시제품; 상세 얼굴 별도 | historical |
| B 표면 40부위 분리 | Tripo segmentation 87조각→Blender 40메시→41본·6동작 보존 | 숨은 몸체·의상 안쪽·교체 구조 미완료 | historical |
| C P2 9개 부품 별도 생성 | 머리·몸·손·헤어·재킷·셔츠·바지·부츠·벨트→Blender 조립 | 목·손목·의상 겹침·피부색 불량. 리깅 전 형상 검수 필요 | failed_assembly_trial |
| D P2 전체 신체와 부품 교체 | 전신 기반→머리·손 보강→스컬프·재질 | 전체 비율 기준; 연결부 검수 필요 | historical |
| E HD 7개 제작 그룹 | 속옷 포함 신체·머리·헤어·손·상의·하의·신발→HD→조립→리토폴로지 | 7파츠 280크레딧; 고밀도는 표정용 구조 완성 아님 | source_trial |
| F 수작업 얼굴과 반복 보정 | HD/P2 머리→Blender 눈·입·턱·Shape Key 반복 조정 | 주름·눈 깊이·속눈썹·입술 U형·턱·모션 손실 반복 | stopped_primary_route |
| G MPFB 기본 얼굴 템플릿 | MPFB·CC0 부품·Faceunits·Visemes→Rigify→표정 시험 | 설치·표정 시험 성공; 모델도 Tripo로 만든다는 사용자 방침으로 미채택 | separate_test |
| H Tripo 모델과 애드온 페이스 리깅 | Tripo→Blender 형태·토폴로지→Faceit/Rigify→표정·베이크→Godot | 모델 원형은 Tripo; 애드온으로 리깅. 실제 Faceit 적용 성공 미확인 | current_direction |
| I P2 머리와 HD 헤어 및 알파 카드 | P2 얼굴·목·쇄골 + 4방향 HD 헤어 + 눈썹·속눈썹 UV 알파 카드 | 머리카락 HD, 얼굴과 다른 생성 파츠 P2; 원본 보존·형상 검토 | current_tool_split |
| J 열린 입 HD와 P2 비교 | 같은 입 벌린 이미지→HD 40크레딧→P2 100크레딧 | HD 구강 얕음; P2 구강 깊이·독립 치아·혀 연결 성분 확인 | current_head_choice |
| K 새 P2 머리의 닫힌 입 기본 조립 | 새 P2 머리 + 다듬은 HD 헤어 + 새 눈·눈썹·속눈썹; 입안 보존 | 원본 대화 진행 중; 로컬 assembly-report는 full_face_rig=false. 최종 승인 아님 | in_progress_at_capture |

실패 기록에서 반복된 문제는 목·손목의 부자연스러운 연결, 의상 관통과 피부색 차이, 눈가의 깊은 홈·주름·안구 이탈, 위아래 눈꺼풀 부족, 속눈썹 들뜸·소실·UV 반복, 입술 아래 U자 변형, 눌린 턱과 과한 광대, 입 애니메이션 소실이었습니다.

이 기록은 **형상 → 변형 구조 → 재질 → 리깅 → 모션**의 선행 조건과, 기본 얼굴을 먼저 검토받는 이유를 보여줍니다. 작업 버전이 최신이라는 이유로 이전보다 좋은 결과라고 자동 판정하지 않습니다.

## 실제 소비량과 판매 가격

| 작업 | 기록된 비용 | 범위 |
|---|---|---|
| 초기 B 모델과 리그 | 135 Tripo credits | P2 메시·재질 110 + 몸 리깅 25 |
| 걷기 프리셋 1개 | 10 Tripo credits | 기존 리그 재사용 |
| 10월 3일 생산·영상·세부 실험 | 595 Tripo credits | 전신120·리그25·동작50·분할40·헤어120·불량손120·이미지손120 |
| 동일 범위 이미지와 영상 | 308 Scenario CU | Seedance182·PixVerse50·Kling53·이미지12+11 |
| P2 9개 부품 | 1080 Tripo credits | 120×9 |
| HD 7개 파츠 | 280 Tripo credits | 40×7; 텍스처 없음 |
| P2 머리와 HD 헤어 조립 원본 | 140 Tripo credits | P2 머리100 + HD 헤어40 |
| 새 입 벌린 HD 머리 | 40 Tripo credits | 471138 삼각형 |
| 같은 참조의 새 P2 머리 | 100 Tripo credits | 15748 정점 16784면 14514쿼드 |
| 로컬 조립 및 보정 | 0 additional generation API | Blender·MediaPipe 추가 생성 호출 0 기록 |
| Faceit 판매 가격 | 판매가 USD | 1.8 $78 / 2.3 $99 / Studio $289 |
| Hair Tool 판매 가격 | 판매가 USD | Standard $52+ / Studio 2–6 $202+ / 7–15 $352+는 원본 대화 기록; 이번에는 $52+ 확인 |

10월 3일 캐릭터 세부 실험 400크레딧·23 CU는 595크레딧·308 CU 묶음에 포함된 범위입니다. 마을 맵 360크레딧·11 CU는 캐릭터 예산에서 별도로 기록됐으므로 이 캐릭터 합계에 더하지 않습니다. 생성 재시도와 이전 파츠 실험도 서로 다른 묶음이 있어 위 행을 전부 합친 “전체 총비용”은 만들지 않았습니다.

현재 판매처 확인은 **2026년 10월 5일** 기준입니다.

- **Faceit:** 1.8 $78, 2.3 $99, 2.3 Studio $289. 원본은 2.3을 우선 검토했습니다. [공식 판매처](https://superhivemarket.com/products/faceit)
- **Hair Tool:** Standard $52+를 확인했습니다. 원본의 Studio 2–6 $202+ / 7–15 $352+ 기록은 과거 비교값으로 보존합니다. Blender 4.5에 대응하는 4.5.9 안내도 확인했습니다. [제작자 판매처](https://bartoszstyperek.gumroad.com/l/hairtool?layout=profile&recommended_by=more_like_this)
- **FaceBuilder:** 15일 무료 체험 이후 구독이 필요한 제품으로 분류합니다. [공식 제품 안내](https://keentools.io/products/facebuilder-for-blender)
- **RetopoFlow:** 구매 가능한 배포와 공개 소스 경로가 있습니다. 무료 강의와 판매용 배포를 구분합니다. [공식 저장소](https://github.com/CGCookie/retopoflow)

원본 API 크레딧 소비는 당시 설정의 실측이며 현재의 모든 생성 요청 정가를 보장하지 않습니다. 달러 판매가는 최종 결제액·세금·환율·할인과 구분합니다.

## 영상 강의 문서 자료

기존 17개 자료집은 [보존한 자료집](reference-documents/AI_CHARACTER_DETAIL_REFERENCES_20261003.md)에 함께 넣었습니다. 원본의 확인 범위와 주의점을 유지합니다. 이번 이관에서 모든 영상을 다시 전체 시청한 것은 아닙니다.

### 머리 얼굴 페이스 리깅의 핵심 자료

| 자료 | 원본에 기록된 핵심 구간과 용도 | 비용 분류 |
|---|---|---|
| [Stefan From AI to Talking 3D Avatar](https://www.youtube.com/watch?v=3nPGTjupIwE) | 1:10–1:44 입 벌린 머리 참조 / 3:28–6:20 Smart Mesh 비교 / 7:00–9:47 분리 / 9:49–11:47 UV Sphere 눈 교체 / 11:50–13:08 입 닫기 / 13:09–17:12 Faceit / 17:14–19:25 표정 보정·베이크 / 19:32–24:49 VRM·추적 | 공개 영상 무료, Tripo·Faceit 등 작업 도구 별도 |
| [블렌더걸 Mixamo Face rig](https://www.youtube.com/watch?v=5FaV2MqwWPA) | 0:46–2:17 메타리그 / 3:26–4:06 생성 / 4:19–5:12 몸 리그 연결 / 5:19–8:20 눈·치아·혀·속눈썹 웨이트 | 영상·Rigify 무료 |
| [CGDive Faceit Tutorial 1](https://www.youtube.com/watch?v=KQ32KRYq6RA) | 11:19–20:32 역할 분류 / 20:39–26:57 정면·측면 랜드마크 / 30:22–33:58 본·스컬프 수정 / 34:01–41:39 베이크 / 41:43–44:07 컨트롤 리그 | 영상 무료, Faceit 유료 |
| [CGDive Faceit Tutorial 2](https://www.youtube.com/watch?v=MnZzj8OUH_0) | 몸 리그 연결·얼굴 모캡 | 영상 무료, Faceit 유료 |
| [Csaba Kiss Blender Facial Animation Faceit](https://www.youtube.com/watch?v=_g277CtsnJk) | 07:15–09:16 바인딩 오류 / 11:37–14:55 표정 보정·베이크 | 영상 무료, Faceit 유료 |
| [夏森轄 평면에서 시작하는 얼굴 모델링](https://www.youtube.com/watch?v=uUqQw6VpFP8) | 눈·입 루프·Mirror / 25:23 사선 볼·광대 / 48:18 눈꺼풀·속눈썹 보정 | 영상·Blender 무료 |
| [CG Cookie RetopoFlow 얼굴 리토폴로지](https://www.youtube.com/watch?v=9OjS2rU-Jr0&t=2909s) | 48:29부터 얼굴 면 흐름 | 영상 무료, 애드온 배포 조건 별도 |
| [Danny Mac stylized head ZBrush Part 1](https://www.youtube.com/watch?v=cjZt0ICfutQ) | 스타일 머리·얼굴 스컬프 참고 | 영상 무료, ZBrush 유료 |
| [Grant Abbitt Stylized Face Details](https://www.youtube.com/watch?v=_Tv_h7n3RuE) | Blender 얼굴 디테일·브러시 | 영상·Blender 무료 |
| [KeenTools FaceBuilder 튜토리얼](https://www.youtube.com/watch?v=tETtRwCnLyg) | 사진 기반 얼굴 맞춤 | 영상 무료, FaceBuilder 유료 |

### AI 모션 헤어 표준 얼굴 대안 자료

| 자료 | 용도와 조건 |
|---|---|
| [NVIDIA Audio2Face Blender Part 1](https://www.youtube.com/watch?v=Etztivmjny4) / [Part 2](https://www.youtube.com/watch?v=TIkpVjKEkvY) | 얼굴 변형 준비→음성 립싱크 전달. 옛 설치 환경과 현행 SDK 구분 |
| [cg tinker BlendArMocap](https://www.youtube.com/watch?v=pji6IHNCnAk) / [개선 릴리스](https://www.youtube.com/watch?v=U9G2VlG9HbA) | 02:53 감지 / 04:17 Rigify / 05:05 전이 / 05:50 정리 |
| [AccuFACE 2 공식](https://www.youtube.com/watch?v=fiiuYBCZF20) / [이전 입문](https://www.youtube.com/watch?v=dFdzR48MkXU) | 영상 얼굴 추적. iClone·플러그인 유료, CC 구조 변환 검수 |
| [PhiBix Digital Clone](https://www.youtube.com/watch?v=OSZuiGmc-ig) | 눈·피부·턱 아래 등 텍스처 보완. CC·Headshot 유료 |
| [Headshot 3 Stylized CC5 Blender](https://www.youtube.com/watch?v=uK08MPGbKaQ) | AI 측면 참조→가이드→Blender morph→Krita 텍스처. 원래 컨셉 비율 복원 |
| [KeenTools FaceTracker](https://www.youtube.com/watch?v=Lc8w2aZ5Mwk) / [기초 영상](https://www.youtube.com/watch?v=uEWQl8xw1ZA) | ARKit 또는 Rigify 표정 전이, FaceBuilder 토폴로지 제약 |
| [Stefan Dream Game AI Characters](https://www.youtube.com/watch?v=UBjgJM6D18A) | 04:30–22:10 캐릭터 / 29:50 플레이. 상세 얼굴 강의와 구분 |
| [HairStep](https://github.com/GAP-LAB-CUHK-SZ/HairStep) / [Neural Haircut](https://samsunglabs.github.io/NeuralHaircut/) | 단일 사진·영상 모발 가닥 복원 연구. 비상업·의존 모델 조건 확인 |

### Tripo 얼굴 사례와 공식 문서

- [Tripo P2 Astra Blender 제작 사례](https://note.com/osushi_san/n/n0c2a7b88276f): 원본 기록의 Step 2 눈·입 구조, Step 5 깜빡임 재작업, Step 6 턱·입술 닫힘 보정. Tripo 의뢰 PR 사례라는 성격을 유지합니다.
- [Tripo 공식 Astra Blender 캐릭터 워크플로우](https://www.tripo3d.ai/blog/gpt-6-astra-3d-character-workflow): 분리 생성·조립·표정. 여러 시연이 동일 프로젝트의 연속 결과라는 뜻은 아닙니다.
- [Tripo Studio](https://www.tripo3d.ai/blog/tripo-studio-tutorial-english): 분리·보완·부품 리토폴로지·텍스처·초기 리깅.
- [Tripo AI 캐릭터 리토폴로지](https://www.tripo3d.ai/blog/retopo-an-ai-character-model-for-animation): 애니메이션을 위한 눈·입 흐름.
- [Tripo ZBrush Bridge](https://www.tripo3d.ai/blog/tripo-dcc-bridge-for-zbrush): 고밀도 형태 편집 도구 전달 후보.
- [Nano 캐릭터 제작 게시물](https://x.com/Dstudio_ai/status/2096475126942560677): 파츠·조립·리깅·표정 전환 사례, 로그인 필요 가능.
- [Faceit Geometry](https://faceit-doc.readthedocs.io/en/latest/geometry/) / [Expressions](https://faceit-doc.readthedocs.io/en/latest/expressions/) / [Bake](https://faceit-doc.readthedocs.io/en/latest/bake/): 메시 조건·표정 수정·베이크.

### 보유 Stefan 강의 자료

보유한 유료 강의의 자막·힌트는 원본 위치를 연결합니다. 전체 수업 내용을 이번 문서에 다시 복제하지 않습니다.

- [참조 이미지 힌트](C:/lsm26/triphthonS1/artifacts/stefan-study/character__lesson-01-hints.txt)
- [Sculpting](C:/lsm26/triphthonS1/artifacts/stefan-study/character__3_sculpting.txt): 09:00–12:30 머리 교체·마스킹·Mirror·목 맞춤, 12:30–16:45 귀·뺨·돌출부 정리.
- [Retopology](C:/lsm26/triphthonS1/artifacts/stefan-study/character__4_retopology_and_optimization.txt): 23:42 머리, 25:28 귀·눈 수정.
- [Rigging and Weight](C:/lsm26/triphthonS1/artifacts/stefan-study/character__8_rigging_and_weight.txt): AccuRIG 관절·손가락·엄지, 웨이트.
- [Tripo Smart Mesh P2](C:/lsm26/triphthonS1/artifacts/stefan-study/character__b3_tripo_smart_mesh_p2.txt): 03:15–05:01 부품과 헤어 밀도 비교.
- [Tripo Generation 심화](C:/lsm26/triphthonS1/artifacts/stefan-study/character__b2_master_tripo_generation.txt): HD·P2·다각도·UV 비교.
- [Claude in Blender](C:/lsm26/triphthonS1/artifacts/stefan-study/character__b1_claude_in_blender.txt): 03:03–04:49 베이크 설정 오류와 수정. 상세 얼굴 리그 시연과 구분.
- [보유 수업 사이트](https://www.learn3d.ai/): 강의 비용과 사용 도구 비용을 별도 기록.

첨부 Gemini 파일 2개는 무료 애드온·Tripo·기타 프로그램으로 전환 논의를 시작한 자료입니다. 그 안의 무료 FaceBuilder·AccuRIG 얼굴 리깅·ML Deformer 헤어 자동화 해석은 원본 대화에서 교정됐습니다. 이 문서는 교정된 내용을 현재 기준으로 사용합니다.

## 결과 파일과 검증 범위

파일 존재·출처 목록은 [artifact-index.json](artifact-index.json)에 저장합니다. 다음은 핵심 편집 원본입니다.

| 결과 | 파일 | 의미 |
|---|---|---|
| 기존 게임 B | [explorer_b_v5.blend](C:/lsm26/triphthonS1/art/source/explorer_b_v5.blend) | 71본 기존 캐릭터. 새 얼굴 작업과 구분 |
| 40부위 실험 | [explorer_b_parts_20261003.blend](C:/lsm26/triphthonS1/art/source/explorer_b_parts_20261003.blend) | 40메시·41본·몸 동작 6개 |
| 독립 손 | [open_hand_rigged_20261003.blend](C:/lsm26/triphthonS1/art/source/open_hand_rigged_20261003.blend) | 16본·쥐기, 몸 맞춤 전 |
| HD 7파츠 | [HD parts workbench](C:/lsm26/triphthonS1/art/characters/explorer_b_hd_restart_v1/explorer_b_HD_parts_workbench.blend) | 펼쳐둔 파츠 원본, 최종 조립 아님 |
| 얼굴 구조 시험 | [HD face structure](C:/lsm26/triphthonS1/art/characters/explorer_b_face_structure_v1/explorer_b_HD_face_structure_trial.blend) | 눈·치아·혀·구강 배치 실험 |
| 직접 표정 시험 | [face refined v2](C:/lsm26/triphthonS1/art/characters/explorer_b_face_refined_v2/explorer_b_face_refined_v2.blend) | 머리 단독 표정·GLB 실험, 이후 보정 문제와 구분 |
| 반복 수작업 얼굴 | [manual v2h](C:/lsm26/triphthonS1/art/characters/explorer_b_face_rig_manual_v2h/explorer_living_face_v2h.blend) | 12초 깜빡임·시선 시험, 최신 최종 기준 아님 |
| MPFB 템플릿 | [template face test](C:/lsm26/triphthonS1/art/characters/explorer_b_pipeline_v3/01_template_test/mpfb_template_face_test.blend) | 22초·16검토 이미지·공식 팩·Rigify 시험 |
| MPFB 흉상 | [clavicle bust](C:/lsm26/triphthonS1/art/characters/explorer_b_pipeline_v3/02_clavicle_bust/explorer_b_clavicle_bust_v1.blend) | 18초 시험, 주 Tripo 생성 경로 미채택 |
| P2와 HD 조립 | [hybrid v1](C:/lsm26/triphthonS1/art/characters/explorer_b_hybrid_bust_v1/explorer_b_hybrid_bust_v1.blend) | P2 머리·HD 헤어·알파 카드 |
| 조립 보정 | [hybrid v2](C:/lsm26/triphthonS1/art/characters/explorer_b_hybrid_bust_v2/explorer_b_hybrid_bust_v2.blend) | 헤어·UV·치아 20개·혀·입 검사 조절값 |
| 열린 입 HD 비교 | [HD workbench](C:/lsm26/triphthonS1/art/characters/explorer_b_open_mouth_hd_v1/explorer_b_open_mouth_HD_workbench.blend) | 구강 얕음·471,138삼각형 원본 보존 |
| 최신 열린 입 P2 | [P2 workbench](C:/lsm26/triphthonS1/art/characters/explorer_b_open_mouth_p2_v1/explorer_b_open_mouth_P2_workbench.blend) | 깊은 구강과 연결 성분 검토 |
| 최신 닫힌 입 조립 작업 | [P2 closed assembly](C:/lsm26/triphthonS1/art/characters/explorer_b_p2_closed_assembly_v1/explorer_b_P2_closed_assembly_v1.blend) | 닫힌 입 조립 저장 확인, 후속 기본 표정 보정 중, 전체 얼굴 리그 미완료 |
| 평소 표정 후속 보정 작업 | [P2 rest refined v2](C:/lsm26/triphthonS1/art/characters/explorer_b_p2_rest_refined_v2/explorer_b_P2_rest_refined_v2.blend) | 수집 당시 생성된 작업 파일. 약한 미소·편안한 눈·속눈썹·턱선의 최종 승인 미확인 |

무료 MPFB 시험의 930개 뼈는 조작·보조·변형 본을 합친 작업 리그 수입니다. 게임용 최종 뼈 수가 아닙니다. 52개 얼굴 단위가 불러와졌어도 모든 조합의 자연스러움·Godot·실시간 성능을 완료한 것은 아닙니다.

2026년 10월 5일 이관 작업에서는 모델을 수정하거나 생성·설치·구매·게임 테스트를 새로 수행하지 않았습니다. 기존 자료의 검증 범위를 옮겼습니다. 문서·JSON의 읽기와 참조 경로·구조는 별도로 확인합니다.

## 워크플로우 관리 프로그램에 옮길 정보

[workflow.json](workflow.json)은 앞으로 관리 프로그램이 가져올 초기 데이터입니다. **48개 도구, 14개 제작 단계, 11개 경로, 12개 비용 기록**과 현재 기준·규칙·출처를 포함합니다. 아래 데이터 설계는 이번 정리에서 추가한 제안이며 원본 대화의 확정 앱 요구사항은 아닙니다.

| 데이터 | 관리할 항목 |
|---|---|
| Workflow와 Version | 이름·목표·현재 경로·과거 경로·상위 버전·변경 이유 |
| Stage | 순서·의존 관계·입력·산출물·도구·완료 기준·검토 상태 |
| Tool과 Version | 프로그램 또는 애드온·설치 상태·버전·유료 여부·공식 링크·제약 |
| Artifact | 원본·작업본·게임용·비교본·경로·파일 형식·메시/본/모프 통계 |
| Review | 사용자 승인·수정 요청·수치 검사·렌더·게임 검사와 각각의 증거 |
| Issue | 눈꺼풀·UV·구강·헤어 관통 등 문제·이미지·발생 버전·수정 버전 |
| CostEntry | Tripo credits / Scenario CU / USD·개별 실행·예산 묶음·중첩 여부 |
| Reference | 영상·문서·강의·타임스탬프·비용·사용 조건·확인 수준 |
| SourceMessage | 원본 채팅·턴 ID·날짜·사용자 지시·정정·당시 완료 보고 |

화면은 현재 경로의 단계 목록, 단계별 입력과 산출물, 도구 목록, 사용자 검토 이력, 원본 대비 이미지·모션 비교, 비용, 참고 자료를 연결하는 방식이 적합합니다. 이것은 향후 프로그램 구성 제안이며 이번에는 앱을 구현하지 않았습니다.

상태는 계획·진행 가능·작업 중·검토 대기·수정 필요·승인·완료·막힘·보관을 구분합니다. 구매 의향을 구매 완료로, 설치를 적용 성공으로, 과거 다른 모델의 검사를 최신 모델의 완료로 자동 승계하지 않습니다.

## 원본 보존과 수집 범위

- 원본 대화의 현재 제목: **Tripothon 게임 제작 시작**.
- 초기 전체 조회: 18페이지, 172개 턴. 이후 새 1턴과 이전 마지막 턴을 갱신해 173개 턴 확인. 도구가 본문을 빈 항목으로 반환한 턴 40개.
- 인간형 캐릭터 관련으로 보존한 턴: **107개**, 사용자·에이전트 메시지 **596개**. 일부 턴에는 캐릭터와 다른 게임 내용이 함께 있어 문맥을 보존했습니다.
- [source-archive.md](source-archive.md): 읽기용 원본 대화 발췌. 시간순 사용자 지시·수정·완료 보고·진행 안내를 포함합니다.
- [source-archive.json](source-archive.json): 날짜·턴 ID·메시지 역할·당시 상태를 보존한 데이터.
- [reference-documents](reference-documents): 기존 캐릭터·애니메이션·모듈 제작 기준·무료 얼굴 도구 시험·전체 개요·자료집 문서의 수집 시점 사본.
- [artifact-index.json](artifact-index.json): 기존 결과·검사·이미지·영상 파일의 실제 경로 목록. 대용량 모델과 영상 자체는 복제하지 않고 원본 경로를 유지합니다.

도구 출력·분석 과정·첨부 이미지 픽셀과 본문이 제공되지 않은 턴은 전체 복원됐다고 주장하지 않습니다. 인용된 자료의 현재 설치·구매 지시는 실행할 지시가 아닌 출처로 취급합니다. 최신 상태는 진행 중인 원본 대화와 개별 파일의 검토 기록으로 갱신해야 합니다.



추가 비용 확인: Mixamo는 Adobe ID로 무료 사용 가능하고, VSeeFace는 무료 배포 프로그램입니다. [Adobe FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html) · [VSeeFace 공식](https://www.vseeface.icu/)
