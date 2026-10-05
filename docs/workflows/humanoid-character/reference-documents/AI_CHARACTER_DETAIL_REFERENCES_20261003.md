# AI 캐릭터 세부 제작 자료집

확인일 2026년 10월 3일. 대상은 Tripothon의 B형 탐험가와 마을 NPC이며, Tripo로 모델을 다시 세부 제작한 뒤 Blender에서 리깅하고 Godot에 전달하는 개발용 작업입니다.

우리에게 가장 가까운 조합은 **Stefan의 파츠별 생성 → 얼굴 메시 정리 → Faceit으로 표정 구조 준비 → MediaPipe나 Audio2Face로 얼굴 모션 생성 → 몸·손 동작과 결합**입니다. 이 조합은 자료를 바탕으로 한 제안이며, 전체를 우리 캐릭터에서 검증한 구현 결과는 아닙니다.

## AI가 맡는 일을 먼저 구분하기

| 작업 | 자료와 도구 | 얻는 결과 | 별도로 해야 하는 일 |
| --- | --- | --- | --- |
| 부품 만들기 | Stefan, Tripo P2·Segmentation | 파츠 메시 | 크기·연결부·변형용 토폴로지 검수 |
| 표정을 만들 얼굴 준비 | CGDive·Csaba Kiss의 Faceit | shape key·얼굴 제어 구조 | 눈꺼풀·입·턱의 변형 수정 |
| 얼굴 움직임 얻기 | Audio2Face, AccuFACE, MediaPipe | 시간별 표정 값·얼굴 모션 | 대상 리그로 전이·보정·베이크 |
| 손 움직임 얻기 | cg tinker·MediaPipe | 손 랜드마크·관절 구동 | 손가락 메시·웨이트·가려짐 보정 |
| 반복 작업 자동화 | Stefan의 Claude in Blender | 스크립트·베이크·검사 자동화 | 기준 설정과 결과 검수 |

Faceit과 AccuRIG은 이 목록에서 **리깅 자동화 도구**로 다룹니다. 생성형 AI 모델과 같은 것으로 설명하지 않습니다. MediaPipe는 머신러닝으로 동작을 추정하지만, 우리 캐릭터의 얼굴 메시나 손 모델을 새로 만드는 것은 아닙니다. [Faceit 공식 문서](https://faceit-doc.readthedocs.io/en/latest/), [MediaPipe 공식 가이드](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker).

## 가장 먼저 볼 자료

1. Stefan의 Tripo Smart Mesh P2 강의 03:15–05:01: 몸 전체를 더 복잡하게 만드는 대신 파츠 단위 생성과 헤어 결과를 판단하는 기준을 봅니다.
2. CGDive의 Faceit 첫 강의: 새 얼굴에 어떤 표정 구조가 필요한지 파악합니다.
3. Csaba Kiss의 07:15–14:55 구간: 자동 바인딩·표정 오류·게임용 베이크를 봅니다.
4. cg tinker의 손·얼굴 추적과 최신 MediaPipe 문서: 기존 몸 영상 파이프라인을 확장할 무료 후보를 검토합니다.
5. NVIDIA의 Audio2Face Part 1과 Part 2: 얼굴 구조와 음성 기반 모션을 연결하는 방식을 봅니다. 예전 설치법은 현행 SDK 안내와 구분합니다.

## 자료별 정리

### 01 Stefan 3D AI Tripo Smart Mesh P2 강의

[Tripo Smart Mesh P2 강의](https://www.learn3d.ai/)

먼저 보기 · AI 메시 생성 · 보유한 유료 강의 자료

**볼 구간:** 03:15–05:01 · 파츠별 생성과 머리카락 실험

**배울 내용:** 파츠를 따로 생성하는 접근과 P2 머리카락 테스트. 같은 예제에서 1,500 quad보다 3,000 quad 결과가 나았지만, 이것을 모든 헤어의 공통 기준으로 삼을 수는 없습니다.

**남는 결과:** 부품별 메시. 헤어 카드나 리그의 완성을 보장하는 결과는 아닙니다.

**우리 게임에 적용:** B형 탐험가의 머리카락·재킷·부츠를 별도 생성하고 실루엣을 먼저 비교하는 데 가장 직접적입니다.

**한계:** 강사도 머리카락 생성의 어려움과 후속 수정을 설명합니다. 목·손목·옷 경계의 연결은 별도로 검수해야 합니다.

**확인 범위:** 사용자가 제공한 강의 자막의 해당 구간 확인

보유 자료: [character__b3_tripo_smart_mesh_p2.txt](C:/lsm26/triphthonS1/artifacts/stefan-study/character__b3_tripo_smart_mesh_p2.txt)


### 02 Tripo 공식 Tripo Studio Tutorial과 Segmentation

[Tripo Studio Tutorial과 Segmentation](https://www.tripo3d.ai/blog/tripo-studio-tutorial-english)

먼저 보기 · AI 파츠 분리와 보완 · 공개 가이드 · 생성 서비스 이용료 별도

**볼 구간:** Segmentation · Brush · Add Part · Merge · Part Completion

**배울 내용:** 생성한 모델에서 부품을 분리하고 브러시로 영역을 수정하며, 누락된 부품 형상을 보완하는 흐름입니다.

**남는 결과:** 편집 가능한 파츠 메시. 표정용 토폴로지나 손가락 관절을 자동으로 확보하는 기능과는 구분해야 합니다.

**우리 게임에 적용:** 처음부터 개별 생성한 부품과, 통합 모델을 분리한 부품을 비교할 기준으로 씁니다.

**한계:** Studio 기능·요금과 API 지원 범위를 동일하게 가정하지 않습니다. 분리만으로 관절 주변의 변형 품질이 좋아지지는 않습니다.

**확인 범위:** 공식 가이드와 API 기능 문서 확인

함께 볼 자료: [Mesh Segment API](https://developers.tripo3d.ai/en/docs/mesh-segment) · [Mesh Complete API](https://developers.tripo3d.ai/en/docs/mesh-complete)


### 03 Stefan 3D AI Rigging and Weight 강의

[Rigging and Weight 강의](https://www.learn3d.ai/)

먼저 보기 · 자동 리깅과 수동 보정 · 보유한 유료 강의 · AccuRIG 기본 도구 무료

**볼 구간:** 12:15–15:17 · 특히 14:05–14:33 손 리깅

**배울 내용:** AccuRIG에서 관절 위치를 정면과 깊이 방향으로 확인하고, 손가락 수·마디 위치를 맞춘 뒤 캘리브레이션하는 과정입니다.

**남는 결과:** 몸과 손가락의 뼈·스킨 웨이트. 전용 손 동작이나 얼굴 리그까지 만들어 주는 수업은 아닙니다.

**우리 게임에 적용:** 손가락이 붙어 있거나 손만 각지는 문제를 메시 단계부터 확인하고, 마디 위치를 검수하는 기준으로 씁니다.

**한계:** 관절 생성과 모션 생성은 별도 작업입니다. 손가락 형상과 웨이트를 고친 뒤 쥐기·펴기·엄지 맞닿기를 시험해야 합니다.

**확인 범위:** 사용자 강의 자막과 공식 손 리깅 매뉴얼 확인

보유 자료: [character__8_rigging_and_weight.txt](C:/lsm26/triphthonS1/artifacts/stefan-study/character__8_rigging_and_weight.txt)

함께 볼 자료: [AccuRIG 손가락 관절과 엄지 방향](https://manual.reallusion.com/actorcore-accurig-1/content/enu/1.1/07-Hand-Rig/Setting-and-Mirroring-Joints.htm) · [AccuRIG 2 공식 매뉴얼](https://manual.reallusion.com/AccuRig-2/2.0/01-welcome/welcome.htm)


### 04 CGDive This addon automates Facial Animation FACEIT Tut 1

[This addon automates Facial Animation FACEIT Tut 1](https://www.youtube.com/watch?v=KQ32KRYq6RA)

먼저 보기 · 얼굴 리깅 자동화 · 영상 무료 · Faceit 애드온 유료

**볼 구간:** 영상 전체 · 랜드마크와 표정용 변형 준비

**배울 내용:** Faceit으로 얼굴의 기준점을 맞추고 표정용 shape key와 컨트롤 리그를 준비하는 접근입니다. Faceit 자체를 생성형 AI라고 분류하지 않습니다.

**남는 결과:** 표정용 변형과 얼굴 제어 구조. 여기에 다른 AI가 추출한 표정 수치를 연결할 수 있습니다.

**우리 게임에 적용:** Tripo로 만든 얼굴을 움직이게 만들 때 필요한 구조를 이해하는 첫 자료입니다.

**한계:** 모든 얼굴에서 자동 결과가 자연스럽다는 보장은 없습니다. 입·눈꺼풀·턱의 메시와 생성된 표정을 확인해야 합니다.

**확인 범위:** 제작자 자료 페이지·YouTube 제목과 채널·Faceit 공식 문서 확인

함께 볼 자료: [CGDive의 Faceit 자료 모음](https://addons.cgdive.com/tools/faceit) · [Faceit 공식 문서](https://faceit-doc.readthedocs.io/en/latest/)


### 05 CGDive FaceIt Tutorial 2 Body rigs and FaceIt mocap Blender

[FaceIt Tutorial 2 Body rigs and FaceIt mocap Blender](https://www.youtube.com/watch?v=MnZzj8OUH_0)

다음 보기 · 몸과 얼굴 리그 통합 · 영상 무료 · Faceit 애드온 유료

**볼 구간:** 영상 전체 · 몸 리그와 얼굴 모션의 결합

**배울 내용:** 이미 준비된 몸 리그에 얼굴 모션을 결합하는 작업을 다룹니다.

**남는 결과:** 몸·머리·얼굴의 제어 관계를 정리한 캐릭터 리그.

**우리 게임에 적용:** 우리 영상 기반 몸 애니메이션에 얼굴 움직임을 추가할 때 머리 회전이 두 번 적용되지 않도록 설계하는 참고입니다.

**한계:** 영상 속 리그와 우리 리그의 뼈 이름·기준 자세가 다를 수 있습니다. 적용 완료 사례로 제시하는 것은 아닙니다.

**확인 범위:** CGDive 공식 자료 페이지와 YouTube 제목·채널 확인


### 06 Csaba Kiss Blender Facial Animation Faceit

[Blender Facial Animation Faceit](https://www.youtube.com/watch?v=_g277CtsnJk)

먼저 보기 · 얼굴 리깅과 오류 수정 · 영상 무료 · Faceit 애드온 유료

**볼 구간:** 07:15–09:16 바인딩 오류 · 11:37–13:07 표정 수정 · 13:08–14:55 게임용 베이크

**배울 내용:** 자동 바인딩이 실패하거나 표정이 깨질 때 수정하고, 게임에 전달할 shape key를 베이크하는 과정을 챕터로 나눠 보여줍니다.

**남는 결과:** 수정한 표정용 shape key와 베이크 결과.

**우리 게임에 적용:** 우리 얼굴이 과하게 일그러지거나 눈·입이 어색해지는 문제를 해결하는 데 우선순위가 높습니다.

**한계:** 자동 리깅의 한계를 확인하는 자료입니다. 영상의 Game Ready Bake 이후에도 Godot GLB 검증은 별도로 필요합니다.

**확인 범위:** 2024-12-26 공개 영상의 제작자 설명과 챕터 확인


### 07 NVIDIA Omniverse Audio2Face and Blender Part 1 Generating Facial Shape Keys

[Audio2Face and Blender Part 1 Generating Facial Shape Keys](https://www.youtube.com/watch?v=Etztivmjny4)

원리 참고 · AI 얼굴 변형 전이 · 영상 무료 · 과거 Omniverse 앱 워크플로우

**볼 구간:** Part 1 · 사용자 캐릭터의 얼굴 변형 준비

**배울 내용:** AI 얼굴 움직임을 사용자 캐릭터에 적용하기 위한 shape key 생성·전이 흐름입니다.

**남는 결과:** Blender에서 사용할 얼굴 shape key.

**우리 게임에 적용:** 얼굴 구조를 준비하는 단계와 음성에서 모션을 만드는 단계가 어떻게 이어지는지 이해하는 자료입니다.

**한계:** 예전 설치법은 그대로 따라 하지 않습니다. Omniverse Launcher의 설치 파일 배포와 Exchange 설치 경로는 종료됐습니다. 기존 설치의 실행과 새 SDK 도입은 구분해야 합니다.

**확인 범위:** 공식 채널 제목·공식 포럼의 연결 링크·현행 NVIDIA 안내 확인

함께 볼 자료: [현재 Audio2Face 3D 저장소](https://github.com/NVIDIA/Audio2Face-3D) · [Launcher 변경 안내](https://developer.nvidia.com/omniverse/legacy-tools)


### 08 NVIDIA Omniverse Audio2Face and Blender Part 2 Loading AI Generated Lip Sync Clips

[Audio2Face and Blender Part 2 Loading AI Generated Lip Sync Clips](https://www.youtube.com/watch?v=TIkpVjKEkvY)

다음 보기 · 음성에서 얼굴 모션 생성 · 영상 무료 · 현행 실행 환경 구축 별도

**볼 구간:** Part 2 · AI 립싱크 모션을 Blender로 전달

**배울 내용:** 음성에서 얻은 얼굴 애니메이션을 준비된 캐릭터에 전달하는 과정입니다.

**남는 결과:** 얼굴 변형의 시간별 가중치와 립싱크 클립.

**우리 게임에 적용:** NPC 대사를 음성 기반 얼굴 애니메이션으로 만드는 후보입니다. 모델링 문제를 대신 해결하는 도구로 쓰지는 않습니다.

**한계:** 현행 SDK는 CUDA·TensorRT 환경이 필요합니다. SDK 코드의 MIT 라이선스와 모델의 이용 조건은 별개이며, 우리 PC에서 실행 검증한 상태가 아닙니다.

**확인 범위:** 공식 채널 제목·공식 연결 링크·Audio2Face 3D SDK README 확인

함께 볼 자료: [Audio2Face 3D SDK](https://github.com/NVIDIA/Audio2Face-3D-SDK)


### 09 Reallusion 공식 Getting Started with AccuFACE 2 iClone 8 Tutorial

[Getting Started with AccuFACE 2 iClone 8 Tutorial](https://www.youtube.com/watch?v=fiiuYBCZF20)

유료 후보 · AI 영상 얼굴 추적 · 영상 무료 · iClone와 관련 플러그인 유료

**볼 구간:** 현행 AccuFACE 2 입문 · 아래 이전 영상은 설정별 챕터 제공

**배울 내용:** 영상·카메라에서 얼굴 연기를 추적하는 방식입니다. AccuFACE 2는 CC5 HD 캐릭터에 맞춘 AI 추적을 강조합니다.

**남는 결과:** 편집 가능한 얼굴 연기 데이터.

**우리 게임에 적용:** 얼굴 클로즈업 영상에서 표정을 얻는 대안입니다. Reallusion 제작 도구를 도입할 경우 비교합니다.

**한계:** 임의의 Tripo 메시가 바로 얼굴 추적 대상이 된다고 가정하지 않습니다. CC 얼굴 구조로의 변환과 Godot 전달 경로를 시험해야 합니다.

**확인 범위:** 공식 영상 설명과 2026-07-30 제품 발표 확인

함께 볼 자료: [이전 입문 영상 · 03:44 영상 입력 · 07:44 스무딩 · 08:13 노이즈 제거](https://www.youtube.com/watch?v=dFdzR48MkXU) · [AccuFACE 2 공식 발표](https://magazine.reallusion.com/2026/07/30/accuface-2-grand-launch-professional-grade-facial-mocap-for-cc5-hd-characters/)


### 10 cg tinker BlendArMocap AR Pose Hand Face Detection in Blender Beta Release

[BlendArMocap AR Pose Hand Face Detection in Blender Beta Release](https://www.youtube.com/watch?v=pji6IHNCnAk)

무료 후보 · ML 얼굴과 손 동작 추적 · 영상과 오픈소스 도구 무료

**볼 구간:** 02:53 손·얼굴·몸 감지 · 04:17 Rigify · 05:05 동작 전이 · 05:50 결과 정리

**배울 내용:** Google MediaPipe로 얼굴과 손을 추적하고 리그에 전달합니다. 뒤의 릴리스 영상도 함께 보면 좋습니다.

**남는 결과:** 랜드마크와 리그 구동 데이터. 손 모델이나 얼굴 shape key를 생성하는 기능은 아닙니다.

**우리 게임에 적용:** 이미 사용 중인 영상 기반 MediaPipe 몸 애니메이션을 얼굴·손 클로즈업으로 확장하는 데 가장 가까운 무료 참고입니다.

**한계:** 2022년 영상의 설치 방식은 오래됐습니다. 현행 Tasks API 포크는 Blender 4.5 LTS 테스트를 주장하지만 여기서는 설치·품질을 검증하지 않았습니다. 가려진 손가락도 자동으로 정확해지지는 않습니다.

**확인 범위:** 제작자 영상 챕터·공식 사이트·포크 README·Google 문서 확인

함께 볼 자료: [개선 릴리스 영상](https://www.youtube.com/watch?v=U9G2VlG9HbA) · [원 제작자 코드](https://github.com/cgtinker/BlendArMocap) · [현행 API 포크 · 미검증 후보](https://github.com/Ivangeraldo/BlendArMocap-UpdatedAPIPort-2026) · [MediaPipe 얼굴 추적 공식 가이드](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker)


### 11 PhiBix Building a Realistic 3D Digital Clone

[Building a Realistic 3D Digital Clone](https://www.youtube.com/watch?v=OSZuiGmc-ig)

세부 품질 참고 · AI 참조 이미지와 표면 보완 · 영상 무료 · CC5와 Headshot 등 유료 도구

**볼 구간:** 공식 사례의 Steps 7–11 · 텍스처 누락과 눈·피부·복장 검수

**배울 내용:** 다각도 얼굴 자료를 맞추고, 턱 아래의 누락된 참조를 AI로 보완한 뒤 투영·수정하는 사례입니다.

**남는 결과:** 보완한 얼굴 텍스처와 디테일을 갖춘 캐릭터.

**우리 게임에 적용:** 귀 뒤·턱 아래·두피처럼 생성 결과가 약한 부분을 찾아 국소적으로 고치는 방법을 참고합니다.

**한계:** 실사 디지털 더블 사례입니다. 우리 탐험가의 그림체를 실사화하는 기준으로 쓰지 않습니다. 머리카락도 통째로 AI가 완성하는 시연으로 보지 않습니다.

**확인 범위:** 제작자 채널·영상 제목과 2026-08-11 공식 사례 본문 확인

함께 볼 자료: [AI 보완 단계가 정리된 공식 사례](https://magazine.reallusion.com/2026/08/11/digital-double-from-photos-phibixs-photorealistic-workflow-with-cc5-and-headshot-3-1/)


### 12 Reallusion 공식 · Mythcons 사례 Headshot 3 Stylized Image to 3D CC5 and Blender

[Headshot 3 Stylized Image to 3D CC5 and Blender](https://www.youtube.com/watch?v=uK08MPGbKaQ)

유료 후보 · AI 참조와 표준 얼굴 메시 변형 · 영상 무료 · CC5와 Headshot 등 유료 도구

**볼 구간:** AI 측면 생성 → 가이드 곡선 수정 → Blender morph → Krita 텍스처 정렬

**배울 내용:** 과장된 캐릭터도 자동 평균 얼굴에 맞추지 않고, 컨셉 실루엣을 수동으로 되살리는 접근입니다.

**남는 결과:** 기존 리그를 유지하며 수정한 스타일 캐릭터.

**우리 게임에 적용:** B형 탐험가의 얼굴 비율을 유지하면서 표준 얼굴 구조를 활용할 수 있는지 비교할 자료입니다.

**한계:** 근육질 캐리커처가 예제입니다. AI가 머리카락까지 새로 생성한 사례가 아니며, 우리 캐릭터에서 변형이 자연스러운지는 별도 확인해야 합니다.

**확인 범위:** 공식 채널·영상 제목과 2026-06-26 공식 사례 본문 확인

함께 볼 자료: [제작 과정과 수동 보정 설명](https://magazine.reallusion.com/2026/06/26/headshot-3-stylized-image-to-3d-building-a-bodybuilder-caricature-in-cc5-and-blender/)


### 13 KeenTools 공식 Facial Mocap and 3D Facial Animation in One FaceTracker for Blender Tutorial

[Facial Mocap and 3D Facial Animation in One FaceTracker for Blender Tutorial](https://www.youtube.com/watch?v=Lc8w2aZ5Mwk)

대안 비교 · 영상 얼굴 추적과 리타게팅 · 영상 무료 · FaceTracker와 FaceBuilder 유료

**볼 구간:** 얼굴 모션을 ARKit blendshape 또는 Rigify로 전달하는 흐름

**배울 내용:** 사진으로 만든 얼굴의 영상 추적과 다른 캐릭터로의 표정 전이를 Blender 안에서 다루는 후보입니다.

**남는 결과:** 얼굴 추적과 전이한 표정 애니메이션.

**우리 게임에 적용:** 얼굴 영상 기반 파이프라인을 비교할 때 사용합니다.

**한계:** 추적에 사용하는 얼굴은 FaceBuilder 토폴로지가 필요합니다. 임의의 Tripo 얼굴을 곧바로 추적할 수 있다고 보면 안 됩니다.

**확인 범위:** 현재 공식 제품 페이지의 영상 링크·요구 조건과 YouTube 채널 확인

함께 볼 자료: [기초 영상 · 02:09 얼굴 메시 · 07:20 추적 개선 · 09:52 내보내기](https://www.youtube.com/watch?v=uEWQl8xw1ZA) · [FaceTracker 현재 제품 안내](https://keentools.io/products/facetracker-for-blender)


### 14 Stefan 3D AI Claude in Blender 강의

[Claude in Blender 강의](https://www.learn3d.ai/)

자동화 참고 · LLM Blender 작업 자동화 · 보유한 유료 강의 자료

**볼 구간:** 03:03–04:49 · 베이크 실패와 설정 수정

**배울 내용:** Claude가 Blender 베이크를 자동화하다 설정 오류로 실패한 뒤, 사람이 작업 조건을 명확히 지정하는 사례입니다.

**남는 결과:** 작업 스크립트와 베이크한 텍스처. 얼굴 리그 생성 시연은 아닙니다.

**우리 게임에 적용:** 파츠 정렬·이름 규칙·텍스처 베이크·내보내기 검사를 자동화하는 방식을 참고합니다.

**한계:** 강의의 ray distance 같은 수치를 우리 모델에 그대로 복사하지 않습니다. 메시 크기와 주변 부품에 맞춘 설정이 필요합니다.

**확인 범위:** 사용자 강의 자막의 해당 구간 확인

보유 자료: [character__b1_claude_in_blender.txt](C:/lsm26/triphthonS1/artifacts/stefan-study/character__b1_claude_in_blender.txt)


### 15 Stefan 3D AI Building My Dream Game With AI Characters and Animations

[Building My Dream Game With AI Characters and Animations](https://www.youtube.com/watch?v=UBjgJM6D18A)

전체 흐름 참고 · AI 캐릭터 제작과 게임 통합 · 공개 영상 무료

**볼 구간:** 04:30–22:10 캐릭터 예제 · 29:50 플레이 테스트

**배울 내용:** P2 캐릭터 생성에서 애니메이션과 게임 테스트까지 이어지는 전체 흐름입니다.

**남는 결과:** 게임에 통합하는 캐릭터와 동작 사례.

**우리 게임에 적용:** 파츠·얼굴·손의 개별 작업을 전체 제작 순서 안에 놓는 참고 자료입니다.

**한계:** 얼굴 shape key와 손가락의 상세 제작 강의로 보지는 않습니다. Unity 예제의 엔진 통합 부분은 Godot 방식으로 바꿔야 합니다.

**확인 범위:** 공개 영상 설명·챕터와 로컬 자막 확인

보유 자료: [UBjgJM6D18A-transcript.txt](C:/lsm26/triphthonS1/artifacts/stefan-study/youtube/UBjgJM6D18A-transcript.txt)


### 16 GAP LAB 연구팀 HairStep CVPR 2023

[HairStep CVPR 2023](https://github.com/GAP-LAB-CUHK-SZ/HairStep)

연구 참고 · AI 모발 가닥 복원 · 공개 연구 코드 · 데이터와 체크포인트 비상업 연구용

**볼 구간:** 프로젝트 데모와 README의 Single view 3D Hair Reconstruction

**배울 내용:** 한 장의 사진에서 모발 방향·깊이를 추정하여 3D 가닥을 복원하는 연구입니다.

**남는 결과:** 가닥 기반 모발 복원. 게임용 헤어 메시·LOD·리그까지 완성하는 결과는 아닙니다.

**우리 게임에 적용:** AI가 머리카락을 어디까지 복원할 수 있는지 이해하는 참고로만 둡니다.

**한계:** HiSa·HiDa 데이터와 관련 체크포인트는 비상업 연구용입니다. 상용 게임에 도입할 후보로 추천하지 않습니다.

**확인 범위:** 공식 저장소의 연구 설명·환경·이용 제한 확인


### 17 Neural Haircut 연구팀 Neural Haircut ICCV 2023

[Neural Haircut ICCV 2023](https://samsunglabs.github.io/NeuralHaircut/)

연구 참고 · AI 영상 모발 가닥 복원 · 공개 연구 · 의존 데이터와 모델 조건 별도 확인

**볼 구간:** 프로젝트 데모와 공식 추론 코드

**배울 내용:** 단안 영상이나 여러 시점의 이미지에서 가닥 단위 모발을 복원하는 연구입니다.

**남는 결과:** 가닥 기반 헤어 형상.

**우리 게임에 적용:** 여러 각도의 참조가 헤어 형상에 어떤 정보를 더 주는지 비교할 참고입니다.

**한계:** 우리 RTX 2070 환경에서 실행하거나 게임용 변환을 검증하지 않았습니다. FLAME 등 의존 모델까지 상업 이용 가능하다고 판정하지 않습니다.

**확인 범위:** 연구 논문과 공식 추론 코드의 입력·출력 설명 확인

함께 볼 자료: [공식 추론 코드](https://github.com/Vanessik/NeuralHaircut)


## 머리카락과 얼굴을 새로 만들 때의 적용안

아래는 자료에 근거한 **Tripothon 작업 제안**입니다.

머리카락은 우리 컨셉에 맞는 덩어리형 메시를 먼저 시험합니다. 정면 실루엣뿐 아니라 옆·뒤 모양, 두피와의 접점, 목 회전 때의 간섭을 봅니다. 가닥 복원 연구가 더 세밀한 결과를 보여도, 그대로 게임용 헤어·LOD·흔들림으로 이어지는 것은 아닙니다. Stefan의 헤어 실험과 HairStep의 결과는 서로 다른 목표로 비교해야 합니다.

얼굴 피부는 눈꺼풀·입 주변이 변형될 수 있는 일관된 메시로 준비합니다. 눈알·치아·혀·머리카락·장신구는 목적에 따라 별도 파츠로 두되, 피부 자체를 잘게 쪼개는 것을 품질 향상의 기준으로 삼지 않습니다. Tripo에서 웃는 얼굴과 화난 얼굴을 각각 새로 생성한 결과는 정점 수와 순서가 달라질 수 있어, 곧바로 shape key로 사용할 수 있다고 가정하지 않습니다. 표정은 기준 얼굴의 정점을 유지하며 만들어야 합니다. [Faceit 시작 문서](https://faceit-doc.readthedocs.io/en/latest/getting_started/).

첫 얼굴 시험은 중립·깜빡임·미소·입 벌리기·눈썹 올리기로 시작하는 것이 좋겠습니다. 얼굴 실루엣을 유지하며 눈꺼풀이 눈알을 뚫지 않고, 입 안이 찢어지지 않는지를 먼저 확인합니다. 그 다음 표정 채널을 늘리고 음성·영상 기반 얼굴 모션을 연결합니다. 기존의 걷기·달리기 몸 동작에 얼굴 모션을 더할 때는 머리 회전을 어느 쪽에서 담당할지도 정합니다.

손은 AI 생성 결과에서 손가락이 실제로 분리됐는지부터 확인합니다. 관절이 있어도 메시가 붙어 있으면 자연스럽게 움직이지 않습니다. 마디 주변의 형상·웨이트를 확보한 뒤 손 클로즈업 영상에서 동작을 추출하고, 쥐기·펴기·엄지 맞닿기·도구 잡기를 시험합니다. cg tinker의 방식은 이 동작 추출을 참고하는 자료이며, 손 모델 생성의 대체 수단은 아닙니다.

## 도구 도입 우선순위

| 선택 | 추천하는 경우 | 현재 판단 |
| --- | --- | --- |
| Tripo와 Blender 유지 | 파츠·헤어·복장 제작 | 기존 도구로 먼저 모델 품질을 높이기 |
| Faceit 검토 | 같은 얼굴에서 여러 표정과 NPC 재사용 | 상세 얼굴 리그를 위한 우선 유료 후보. 현재 Blender 버전 호환과 샘플 얼굴 결과부터 확인 |
| MediaPipe 얼굴·손 확장 | 추가 서비스 과금 없이 영상 기반 동작 실험 | 우리 기존 파이프라인과 가장 가까움. cg tinker의 구조를 참고하고 현행 Tasks API 사용 |
| Audio2Face 3D 검토 | NPC 대사에 음성 기반 얼굴 모션 추가 | 현행 SDK와 모델 조건·실행 환경 확인이 필요. 옛 GUI 설치 영상만 따라 시작하지 않기 |
| CC5·Headshot·AccuFACE 검토 | 표준 얼굴 구조와 유료 제작 생태계 도입 | AI 모델과 스타일 얼굴 변형 사례는 유용하나, Tripo 얼굴 변환·Godot 전달을 먼저 시험 |
| KeenTools 검토 | 영상 기반 얼굴 추적 비교 | FaceBuilder 토폴로지 제약이 있어 첫 도입 순위는 낮음 |
| HairStep·Neural Haircut | AI 모발 복원 원리 조사 | 연구 참고로 유지. 상용 게임용 제작 경로로 아직 채택하지 않음 |

## 버전과 이용 조건에서 확인할 부분

- NVIDIA Omniverse Launcher는 2025년 10월 1일부터 deprecated 상태이며, 설치 파일 배포와 Exchange의 앱 설치 경로가 종료됐습니다. 기존 설치는 계속 실행될 수 있습니다. 기존 Audio2Face 영상은 작업 원리를 보는 자료로 쓰고, 새 설치는 현재 저장소를 기준으로 검토해야 합니다. [NVIDIA 현행 안내](https://developer.nvidia.com/omniverse/legacy-tools).
- Audio2Face 3D SDK는 Windows·Linux와 CUDA·TensorRT 실행 환경을 요구합니다. SDK의 MIT 코드 라이선스가 모든 모델·데이터의 이용 조건을 대신하지 않습니다. RTX 2070에서의 실제 실행 속도와 품질은 이번 조사에서 측정하지 않았습니다. [공식 SDK](https://github.com/NVIDIA/Audio2Face-3D-SDK).
- BlendArMocap의 원 영상은 2022년 자료입니다. 현대 Tasks API 포크의 Blender 4.5 LTS 테스트는 유지관리자의 설명이며, 우리 환경에서의 실행 확인은 아닙니다. 오래된 영상의 관리자 권한 설치 절차를 그대로 재현할 필요가 있다고 판단하지 않습니다. [포크 README](https://github.com/Ivangeraldo/BlendArMocap-UpdatedAPIPort-2026).
- HairStep의 HiSa·HiDa 데이터와 관련 체크포인트는 비상업 연구용입니다. 무료 공개 저장소라는 이유로 상업 이용 가능하다고 분류하면 안 됩니다. Neural Haircut도 의존 모델·데이터의 조건까지 확인하기 전에는 상용 후보로 확정하지 않습니다. [HairStep 공식 저장소](https://github.com/GAP-LAB-CUHK-SZ/HairStep), [Neural Haircut 공식 코드](https://github.com/Vanessik/NeuralHaircut).
- 유료 도구를 검토할 때는 소프트웨어 사용권과 구매한 헤어·복장 등 콘텐츠의 게임 내 배포권을 구분해 확인해야 합니다. 이 자료집은 특정 콘텐츠의 상업 배포권을 판정한 문서가 아닙니다.

## 조사 범위와 확인 수준

국내외 자료를 검색했으며, 이번 목록은 얼굴·손·머리카락의 **실제 3D 데이터 제작 또는 전이 과정**을 확인할 수 있는 자료를 우선했습니다. 2D 영상에서 얼굴만 움직이는 예제, 이미지 속 헤어 변경, 출력 메시·리그가 확인되지 않는 홍보 영상은 주 추천에서 제외했습니다. 국내 채널 수를 맞추기 위해 직접 관련 없는 프리비즈 자료를 넣지는 않았습니다.

Stefan 자료는 사용자가 제공한 강의 자막과 공개 영상 자막을 읽었습니다. 다른 영상은 제작자의 설명·챕터·YouTube 제목과 채널·공식 매뉴얼·사례 글을 확인했습니다. 모든 영상을 처음부터 끝까지 프레임별로 시청했다는 뜻은 아니며, 도구를 설치해 동일 결과를 재현했다는 뜻도 아닙니다. 각 자료에 확인 범위를 표시했습니다.

강의·문서 안의 설치 지시나 도구 추천은 제3자 자료로 취급했습니다. 이번에는 자료 조사와 정리만 수행했으며, 유료 생성·도구 구매·프로젝트 모델 변경은 수행하지 않았습니다.
