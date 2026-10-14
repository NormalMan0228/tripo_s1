# 영상·텍스트 → 3D 애니메이션 도구 조사 (2026-10-14)

범위: 실제 영상 또는 AI 생성 영상, 텍스트를 3D 애니메이션으로 바꾸는 도구.
(a) 얼굴: ARKit 52 곡선과 모음 입모양(아 에 이 오 우), (b) 사람 몸 동작, (c) 몬스터(네발, 다리 많은 것, 날개, 덩어리형).
우리 조건: Tripo 메시, Blender, 얼굴은 Rigify 얼굴 리그를 ARKit 52 셰이프키로 굽는 방식. 로컬 GPU는 RTX 2070 8 GB(Windows). 비용과 결과 품질이 우선이고, 수작업보다 스크립트 자동화를 선호.

표기:
- **[V]** 회사 자기 주장(홈페이지, 문서)
- **[I]** 독립 리뷰 또는 제3자 비교
- **[P]** 논문 자체 보고 수치(재현 안 됨)
- **[C]** 커뮤니티 일화
- **[추정]** 내 판단(출처 없음)
- **[미확인]** 이번 조사에서 직접 확인하지 못함

조사 방식은 웹 검색과 페이지 열람만 했다. 가입, 구매, 다운로드는 하지 않았다. 가격은 자주 바뀌고 출처끼리 충돌하는 경우가 많아서, 충돌하면 모두 적었다.

---

## 0. 한눈에 보기

| 도구 | 용도 | 가격(2026-10 기준, 확인된 것) | 출력 | 자동화/API | 품질 메모 |
|---|---|---|---|---|---|
| MediaPipe Face Landmarker | 얼굴 | 무료(오픈소스) | 52 블렌드셰이프 점수(ARKit 이름) + 478 랜드마크 | 예(Python) | 사람 얼굴 전용. 애니 얼굴은 검출 실패가 많음 [C] |
| MetaHuman Animator (UE 5.6+) | 얼굴 | UE 무료 | MetaHuman 얼굴 리그 애니(UE) | 부분적(UE 안에서) | 모노 영상 품질은 "중간"(3자 평가), 최고 품질은 깊이 카메라 [V][I] |
| Live Link Face (iPhone) | 얼굴 | 앱 무료, TrueDepth iPhone 필요 [미확인] | ARKit 52 CSV | 녹화는 수동 | ARKit 품질이 기준점 |
| Rokoko Face Capture | 얼굴 | Pro 플랜에 포함($50/월 연간, $70/월 월간) | FBX/BVH/CSV(Pro) | 기본 Command API | 별도 판매 없음 |
| Faceit (Blender) | 얼굴 리그 + 모캡 가져오기 | $78~$99 | Blender 셰이프키 | 파이썬 연산자 | 영상 트래커 기능은 문서에서 확인 안 됨 |
| AI Mocap Studio (Blender 애드온) | 얼굴+몸 | $15.99 | ARKit 이름 셰이프키 | Blender 안에서 | MediaPipe 기반. Blender 4.2 LTS 필요 [V] |
| NVIDIA Audio2Face-3D | 얼굴(소리 → 입) | 가중치 공개(NVIDIA Open Model License) | 블렌드셰이프 가중치 | SDK | 소리 기반. 영상 아님 |
| Move One (Move AI) | 몸 | $18/월에 60 크레딧(=1분, Gen1) | FBX 등 [미확인] | 앱 | 어려운 자세에 강함 [I] |
| Rokoko Vision 3.0 | 몸 | 무료 30초/월, Basic $10/월(연간) 600초/월 | FBX, BVH(Basic 이상) | 업로드 방식 | 3.0 이전 버전은 흔들림 [I], 3.0은 "개선" [V] |
| DeepMotion Animate 3D | 몸 | 1 크레딧 = 1초. 무료 60초/월(비상업) | FBX, BVH, GLB | API는 영업 문의 | 떨림과 발 미끄러짐 [I] |
| Plask | 몸 | 무료 15초/일, $18/월 10분, $50/월 60분 | FBX/BVH [미확인] | 아니요 | DeepMotion과 비슷하게 떨림 [I] |
| QuickMagic | 몸+손(+얼굴) | 무료 플랜 있음. 유료 금액은 출처마다 다름 | FBX, BVH, BIP, VMD 등 | 개발자 접근은 상담 | 부드럽고 정확, 손가락 됨 [I] |
| Autodesk Flow Studio | 몸 | Lite $10/월 2,100 크레딧, AI MoCap 10 크레딧/초 | FBX/USD 등 | 아니요 [미확인] | 좋음 [I] |
| Radical | 몸 | **서비스 종료**(데이터 받기 기한 2026-07-06) | - | - | Autodesk가 기술 인수 |
| Meshcapade | 몸 | 2026-02 Epic이 인수, 플랫폼 상태 불확실 | FBX, GLB, SMPL | API 있었음 | 독립 비교에서 최상급 [I] |
| Cascadeur | 몸/키프레임/네발 | Free(상업 불가, FBX 불가), Indie 약 $8~19/월, Pro $33~49/월 | FBX, DAE, USD(Indie 이상) | Python 스크립트 [미확인] | 영상 모캡은 약함 [I]. 네발 AutoPosing 있음 |
| WHAM / GVHMR (오픈소스) | 몸 | 무료. 단, 라이선스 제약 | SMPL 파라미터 | 예(Python) | 연구 수준 최고권. GVHMR은 상업 불가 |
| Uthana | 몸(텍스트·영상) | 무료(비상업), 상업은 월 최소 $100, 영상→모션 $0.05/초 | FBX/GLB | **예(GraphQL API, Python SDK)** | 그럴듯하나 부자연스러운 자세도 있음 [I] |
| SayMotion (DeepMotion) | 텍스트→모션 | 별도 요금(미확인) | FBX 등 | API 페이지 있음 | - |
| HY-Motion 1.0 (Tencent) | 텍스트→모션 | 가중치 공개. **한국은 라이선스 지역에서 제외** | SMPL-H 22관절 | 예 | VRAM 24~26 GB 필요 |
| Tripo 리그·애니 | 몬스터/사람 | 리그 25 크레딧, 애니 하나 10 크레딧 | FBX/GLB | **예(API)** | 프리셋 동작. 7가지 생물 유형 |
| Meshy Animate | 사람/네발 | 크레딧 비용 미확인 | FBX/GLB | 웹앱(API 미확인) | 프리셋 500개 이상 |
| Anything World | 몬스터 전반 | 개인 무료(매출 10만 달러 미만), Micro $50/월, Pro $250/월 | 리그된 모델+애니 | API 있음 | 네발, 곤충, 물고기, 새 지원 [V] |
| SuperAnimal (DeepLabCut) | 동물 2D 키포인트 | 연구용(상업은 EPFL 문의) | 2D 39점 | 예 | 3D 메시 아님 |
| 4D-Animal / WildAni4D | 동물 영상 → 4D 메시 | 연구 코드 | SMAL(개 템플릿) | 연구용 | 논문 수준, 생산용 아님 |

---

## 1. 얼굴

### 1.1 MediaPipe Face Landmarker (Google)
- 얼굴 검출, 478점 메시, 표정 점수 순서로 모델 세 개를 연결한다. 마지막 출력이 블렌드셰이프 52개 점수다. [V] https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker · https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker
- 52개 점수는 이름이 ARKit 52와 같고 FACS로 대응된다고 논문에 적혀 있다. 측정한 오차는 아니다. [P] https://pub.dzne.de/record/285257/files/DZNE-2026-00199.pdf
- **정확도 근거**: ARKit 대비 오차를 잰 공개 벤치마크는 찾지 못했다. 웹캠용 회귀기 논문(2026-01, 사전공개)은 자기 방법이 ARKit 6와 비슷하다고 주장하고, MediaPipe는 기준으로 쓰지 않았다. [P] https://arxiv.org/abs/2601.08234v1
- Reallusion 포럼 비교(ARKit, NVIDIA Maxine, MediaPipe 기반 앱)의 결론은 기본 설정으로는 셋 다 썩 좋지 않고 보정이 많이 필요하다는 것이다. [C] https://forum.reallusion.com/PrintTopic550409.aspx
- **애니 얼굴**: 사람 사진용이라 그림이나 애니 얼굴은 검출이 잘 안 된다는 보고가 있고, 원인으로 "사람이 아닌 이미지(일러스트, 애니)"가 꼽힌다. [C] https://huggingface.co/CrucibleAI/ControlNetMediaPipeFace/discussions/2
- 만화 얼굴 랜드마크 연구에서도 과장된 표정(크게 벌린 입 등)에서 실패가 많았다. [P] https://arxiv.org/pdf/1811.03214
- 애니풍 특징(작은 코와 입, 큰 눈)은 적응이 어렵다는 보고도 있다. [P] https://arxiv.org/pdf/2404.12322
- 자동화: Python API가 있고 CPU에서도 돈다. 결과를 CSV로 저장한 뒤 Blender 셰이프키 키프레임으로 옮기는 스크립트를 쉽게 짤 수 있다. [추정]
- **우리 용도 결론** [추정]: 캐릭터가 애니풍이어도 **입력 영상은 사람(실사 또는 실사풍 AI 영상)**으로 만들고, 결과 곡선을 우리 ARKit 52 셰이프키에 꽂는 것이 맞다. 애니풍 AI 영상을 그대로 넣으면 검출 실패 위험이 크다.

### 1.2 Blender용 MediaPipe 애드온
- **AI Mocap Studio**($15.99): 얼굴 468점과 홍채를 블렌드셰이프로 대응한다. 최근 버전은 ARKit 이름 셰이프키에 바로 써서 Faceit 리그와 호환된다. MediaPipe에 Python 3.13 빌드가 없어서 Blender 4.2 LTS가 필요하다(Blender 5.x 불가). [V] https://superhivemarket.com/products/ai-mocap-studio
- **MoCap AI**($9.99, GPL-3.0): 몸 위주. MediaPipe와 OpenCV를 따로 설치해야 한다. [V] https://superhivemarket.com/products/mocap-ai
- [추정] 둘 다 결국 MediaPipe이므로 품질은 1.1과 같다. 우리는 Blender 밖에서 MediaPipe를 돌려 CSV를 만들고 Blender 스크립트로 넣는 편이 버전 문제가 없다.

### 1.3 Faceit
- 가격: ARKit Expressions $78, Unlimited $99, 2~9석 $289. [V] https://superhivemarket.com/products/faceit/ratings · https://bazaar.blendernation.com/listing/faceit-facial-expressions-and-performance-capture/
- 문서에 있는 기능: 녹화된 모캡을 컨트롤 리그나 셰이프키로 가져오기, Audio2Face 가져오기와 리타깃, 뷰포트 실시간 녹화. 영상 트래커나 MediaPipe 내장은 **문서에서 확인되지 않음**. [V] https://faceit-doc.readthedocs.io/en/latest/
- [추정] 우리 파이프라인(Rigify 얼굴을 ARKit 52로 굽기)에서는 "ARKit CSV를 셰이프키로 옮기는 단계"만 쓰면 된다. 직접 스크립트로 해도 충분하다.

### 1.4 MetaHuman Animator / Live Link Face (Epic)
- UE 5.6부터 **모노 카메라(웹캠 포함) 영상**으로 실시간 또는 오프라인 얼굴 애니가 가능하다. 오프라인은 Capture Manager로 가져온 뒤 MetaHuman Performance에서 입력을 Monocular Footage로 두고 Process하는 순서다. 결과는 Animation Sequence나 Level Sequence로 내보낸다. [V] https://dev.epicgames.com/documentation/metahuman/metahuman-animation-from-mono-video-capture-in-unreal-engine · https://metahuman.com/news/metahuman-leaves-early-access-with-a-feature-packed-new-release
- 최고 품질은 깊이 센서가 있는 iPhone이나 스테레오 헤드캠이 필요하다고 Epic이 직접 밝힌다. [V] https://www.metahuman.com/animate
- 한 3자 가이드는 웹캠을 "Mid", iPhone TrueDepth를 "High", 스테레오 HMC를 "Highest"로 분류한다. [I] https://medium.com/@Jamesroha/a-beginners-guide-to-metahumans-in-unreal-engine-5-6-and-5-7-e9b14fadbf3d
- UE 5.8에 실험 기능으로 단일 카메라 몸(+얼굴) 마커리스 캡처 플러그인이 있다는 검색 요약이 있었다. Windows 전용이라고 한다. [V][미확인 원문] https://dev.epicgames.com/documentation/metahuman/animation-from-mono-video
- [추정] 결과는 MetaHuman 얼굴 리그용이라 ARKit 52 셰이프키로 바꾸는 단계가 따로 필요하다. UE를 거쳐야 해서 Blender 자동화 흐름에는 무겁다.

### 1.5 Rokoko Face Capture
- 2024-09부터 따로 팔지 않고 Studio Pro에 포함된다(전에는 연 $480 추가). [V] https://rokoko.com/insights/face-capture-is-now-part-of-our-rokoko-pro-plan
- Pro는 연간 결제 시 $50/월, 월간 결제 시 $70/월이다. Pro만 CSV 내보내기와 Advanced Command API를 준다. [V] https://www.rokoko.com/pricing
- [추정] iPhone ARKit을 쓰는 방식이라 Live Link Face(무료)보다 나은 점이 크지 않다. 얼굴만을 위해 $50/월은 비싸다.

### 1.6 NVIDIA Audio2Face-3D (소리 → 얼굴, 오픈)
- v2.3 "Mark", v3.0 가중치가 Hugging Face에 공개되어 있다. 라이선스는 NVIDIA Open Model License이고 상업과 비상업 모두 가능하다고 적혀 있다. [V] https://huggingface.co/nvidia/Audio2Face-3D-v3.0 · https://huggingface.co/nvidia/Audio2Face-3D-v2.3-Mark
- 논문에 따르면 네트워크, SDK, 학습 프레임워크, 예시 데이터셋까지 공개했다. [P] https://arxiv.org/abs/2508.16401v1
- 짝 모델 Audio2Emotion은 "Audio2Face 프로젝트에서만, 감정 인식 목적 금지"라는 별도 제약이 있다. [V] https://huggingface.co/nvidia/Audio2Emotion-v2.2/blob/refs%2Fpr%2F2/README.md
- 이전 버전 A2F의 46 셰이프를 ARKit 52로 바꾸는 공식 코드는 없고 매핑 스크립트를 직접 짜라는 답변이 있었다. [C] https://forums.developer.nvidia.com/t/46-blendshape-standards-of-audio2face/210504
- [추정] **모음 입모양(아 에 이 오 우) 립싱크는 영상보다 소리 기반이 자동화와 품질 면에서 유리**하다. 한국어 정확도와 RTX 2070에서 돌아가는지는 직접 시험해야 한다.

### 1.7 FLAME 계열 연구 트래커 (DECA, EMOCA, SMIRK, SPECTRE, EMOTE)
- 모두 FLAME 모델(턱, 목, 눈알 관절과 표정 기저) 기반이다. [P] https://flame.is.tue.mpg.de/
- SMIRK(CVPR 2024): 이미지에서 표정이 풍부한 3D 얼굴을 복원한다. [P] https://arxiv.org/abs/2404.04104
- SPECTRE: 말할 때 입 모양 복원에 특화. [P] https://arxiv.org/abs/2207.11094
- EMOCA는 유지보수가 끝났고 inferno 라이브러리로 이관 안내가 있다. [V] https://gitee.com/Junjiagit/emoca
- **FLAME 표정을 ARKit 52로 바꾸는 공개 변환기는 찾지 못했다.** 직접 매핑하거나 회귀 모델을 만들어야 한다. AU(OpenFace)에서 ARKit 가중치로 가는 GRU 연구는 활성 정밀도 90%, 재현율 85%를 보고했다. [P] https://diglib.eg.org/items/d8ceee83-6078-48dd-8290-3b15ae919abd/full
- NVIDIA Maxine 문서에 자기 3DMM 표정을 ARKit 공식으로 바꾸는 예가 있다(참고용). [V] https://docs.nvidia.com/maxine/ar/latest/Appendix/C3DMMVersions.html
- FLAME과 SMPL 계열 모델 파일은 MPI 라이선스로 비상업 제한이 있다(SMPL 라이선스 참고). [V] https://smpl.is.tue.mpg.de/modellicense.html · FLAME은 [미확인]
- EMOTE(소리 → FLAME 감정 립싱크)와 Hallo(소리 → 2D 초상 영상, 3D 아님)는 이번에 조사하지 않았다. [미확인] https://emote.is.tue.mpg.de/ · https://github.com/fudan-generative-vision/hallo
- FaceGood의 오픈소스 Audio2Face도 조사하지 않았다. [미확인] https://github.com/FACEGOOD/FACEGOOD-Audio2Face
- [추정] 연구 트래커는 MediaPipe보다 입과 표정이 세밀할 수 있지만, ARKit 변환과 라이선스 부담이 커서 1순위는 아니다.

### 1.8 애니 얼굴 랜드마크
- hysts/anime-face-detector: 애니 얼굴 검출 후 HRNetV2로 28점을 찍는다. 코드와 가중치 모두 MIT로 표기되어 있다(한 3자 사이트는 라이선스 불명이라고 함). v0.1.0부터 순수 PyTorch로 돈다. [V] https://huggingface.co/hysts/anime-face-detector-hrnetv2 · https://pypi.org/project/anime-face-detector
- [추정] 28점으로는 눈, 눈썹, 입 윤곽 정도만 잡힌다. 52 블렌드셰이프를 직접 뽑을 수 없어서 눈 깜빡임과 입 벌림 정도만 휴리스틱으로 근사할 수 있다. 애니 영상에서 정밀한 표정을 뽑는 상용 도구는 찾지 못했다.

---

## 2. 몸 (사람형)

### 2.1 상용 영상 모캡
**Move One (Move AI)**
- Starter $18/월에 60 크레딧, Standard $48/월에 180, Plus $225/월에 240, Advanced $490/월에 700. Gen1은 1명 1초에 1 크레딧, Gen2는 2 크레딧. 무료 계정은 일회성 30 크레딧. 녹화 길이는 유료 60초, 무료 30초. [V] https://docs.move.ai/knowledge/move-one-pricing
- 다른 Move AI 문서는 $15/월에 180 크레딧 등 다른 숫자를 적고 있어 충돌한다. [V] https://docs.move.ai/knowledge/move-ai-pricing-plans-credits
- [추정] Starter 기준 1분에 약 $18로 가장 비싼 축이다. 앱 기반이라 자동화하기 어렵다.
- 독립 비교: 어려운 자세(땅에 손과 무릎)에 가장 정확하지만 발 미끄러짐이 QuickMagic보다 조금 많다. [I] https://tato.studio/blog/best-ai-video-to-mocap

**Rokoko Vision 3.0**
- 단안 솔버를 새로 만들었다. 웹캠 실시간과 듀얼 카메라는 폐지했고, Rokoko Create에 영상을 올리는 방식만 남았다. 손가락은 출시 시점에 미지원이고, 여러 명 캡처도 미지원이다. [V] https://www.rokoko.com/products/vision
- 요금: Starter 무료 30초/월, Basic $10/월(연간) 또는 $12(월간)에 600초, Plus $20(연간)에 3,000초, Pro $50(연간)에 15,000초. 내보내기는 FBX(전 플랜), BVH(Basic 또는 Plus 이상, 표기 충돌). [V] https://www.rokoko.com/pricing
- 회사는 "분당 $1로 QuickMagic($4/분), Uthana($3/분)보다 싸다"고 주장한다. [V] https://www.rokoko.com/products/vision
- 독립 비교(2025-08, 3.0 이전으로 보임): 흔들리고 튀어서 프로 수준이 아니라고 평가했다. [I] https://tato.studio/blog/best-ai-video-to-mocap

**DeepMotion Animate 3D**
- 1 크레딧 = 1초. 얼굴 추적과 손 추적은 각각 초당 0.5 크레딧씩 추가된다. 무료는 월 60초이고 비상업 전용이다. Studio는 무제한(월 7,200 크레딧까지 우선 처리). 출력은 FBX, BVH, MP4, GLB(커스텀 캐릭터). API는 영업 문의. [V] https://www.deepmotion.com/pricing-animate3d · https://deepmotion.com/article/getting-started
- 플랜별 달러 가격은 출처마다 다르다($9~15/월부터). [I] https://us.fitgap.com/products/009151/deepmotion
- 독립 비교: 떨림과 발 미끄러짐이 보여 복잡한 애니에는 맞지 않는다. [I] https://tato.studio/blog/best-ai-video-to-mocap

**Plask**
- 무료는 하루 15초, Standard $18/월(연간)에 10분, Pro $50/월(연간)에 1시간. [V/3자 스냅샷] https://www.xpay.sh/saas-pricing/plask-motion-ai/ · https://plask.ai/pricing
- 독립 비교: DeepMotion과 비슷하게 떨리고 미끄러진다. [I] https://tato.studio/blog/best-ai-video-to-mocap

**QuickMagic**
- 몸, 손, 얼굴 추정. 휴대폰, 웹캠, 일반 카메라 영상을 받는다. 상체 전용, 여러 명, 움직이는 카메라도 지원한다. 텍스트→모션 초안 기능도 있다. 출력은 FBX, BVH, BIP, C4D, VMD, Mixamo, UE, CC/iClone, Roblox 등. 무료 플랜이 있고 API는 상담. [V] https://www.quickmagic.ai/
- 독립 비교: 부드럽고 정확하며 손가락도 된다. $9.99/월에 150초. 무릎 꿇기 같은 자세에서 조금 미끄러진다. [I] https://tato.studio/blog/best-ai-video-to-mocap
- 가격은 출처마다 다르다($11.90/월부터 등). [I] https://www.itechguides.com/best/ai-motion-capture-software/

**Autodesk Flow Studio (구 Wonder Studio)**
- Free 300 크레딧(30초), Lite 2,100(3분 30초), Standard 6,000(10분), Pro 12,000(20분). AI MoCap은 초당 10 크레딧이고 실사 합성 프로젝트는 초당 20. 달러 가격은 3자 기준으로 Lite $10, Standard $45, Pro $95. [V+I] https://www.autodesk.com/au/products/flow-studio/compare · https://digitalproduction.com/2025/08/13/flow-studio-prices-drop-tiers-multiply-features-shift
- 카메라를 고정하면 발 미끄러짐이 적고, 움직이는 카메라는 3D 정확도가 낮아지고 미끄러짐이 늘어난다. [V] https://help.wonderdynamics.com/create-new-project/ai-motion-capture/
- 독립 비교: 좋음. [I] https://tato.studio/blog/best-ai-video-to-mocap

**Radical**: Autodesk가 핵심 기술을 인수했고 웹 포털은 종료됐다. 데이터 받기 기한은 2026-07-06. [I] https://www.cgchannel.com/?p=175200

**Meshcapade (MoCapade)**: 독립 비교에서 "역동적이고 발 고정이 정확함"으로 최상급 평가. [I] https://tato.studio/blog/best-ai-video-to-mocap 다만 2026-02 Epic Games가 인수했다. [V] https://www.mpg.de/26082348/max-planck-spin-off-draws-epic-games-to-tuebingen 플랫폼 지속 여부는 불확실하다(종료됐다는 미확인 3자 주장도 있음). 출력은 FBX, GLB, MP4, SMPL. [I] https://dataconomy.com/tools/meshcapade/

**Cascadeur 영상 모캡**: 2023.1에 들어왔고 오픈소스 라이브러리에 후처리를 더한 방식. [V] https://cascadeur.com/blog/general/cascadeur-20231-introduces-finger-autoposing-video-mocap-and-macos-version 독립 비교: 동작의 힘이 빠지고 뒤틀림과 떠오름이 있으며 손가락이 없다. [I] https://tato.studio/blog/best-ai-video-to-mocap

**Kinetix**: 이번 조사에서 확인하지 못했다. [미확인]

### 2.2 오픈소스 (로컬)
- **GVHMR**(SIGGRAPH Asia 2024): 라이선스는 저장소 자체 라이선스로 **교육, 연구, 비영리 전용**이고 상업은 저자 이메일로 문의해야 한다. 파생물도 비상업이어야 한다. [V] https://raw.githubusercontent.com/zju3dv/GVHMR/main/LICENSE · https://github.com/zju3dv/GVHMR
- **WHAM**: 코드는 MIT. [V] https://raw.githubusercontent.com/yohanshin/WHAM/main/LICENSE 하지만 SMPL 모델 파일이 필요하다.
- **SMPL 모델 라이선스**: 학술 연구 전용이고 상업 목적은 금지된다. 상업 라이선스는 Meshcapade 또는 Max Planck Innovation(smpl@max-planck-innovation.de)에 문의해야 한다. "상업 목적의 다른 산출물 생성"도 금지 문구에 들어 있다. [V] https://smpl.is.tue.mpg.de/modellicense.html
  - [추정] 따라서 WHAM 코드가 MIT여도, SMPL을 거쳐 만든 동작을 상업 게임에 넣는 것은 법적으로 회색이다. 연구나 시험, 프로토타입에는 쓸 수 있고 출시용 데이터는 상용 도구나 별도 라이선스가 안전하다.
- **Blender 경로**: GVHMR를 Blender에서 돌리는 CEB Studios의 임베디드 Python 패키지가 있다($5 이상). 시험 환경은 RTX 3090 24 GB였고 최소 사양은 모른다고 한다. 판매자도 상업 사용은 권하지 않는다. [V] https://carlosedubarreto.gumroad.com/l/py_embed_gvhmr
- GVHMR 결과를 Mixamo 리그에 리타깃하는 MCP 스킬이 있다. [C] https://skillsllm.com/skill/mixamo-llm-mocap
- 리타깃 도구: Retarget(Expy Kit 포크, 5.0부터 "Bind to Active Metarig"로 Rigify 변환, Blender 5.0 이상). [V] https://extensions.blender.org/add-ons/retarget/
  - Mixaify(Mixamo → Rigify, 무료, Blender 5 전용). [V] https://github.com/netherby/mixaify-retarget
  - Diffeomorphic BVH/FBX Retargeter(스크립트 인터페이스 문서 있음). [V] https://bitbucket.org/Diffeomorphic/retarget_bvh.git/wiki
- 주의: 리타깃 실패의 주원인은 레스트 포즈 불일치다. [C] https://extensions.blender.org/add-ons/retarget/versions/
- 4DHumans, TRAM, SMPLer-X는 이번에 라이선스와 VRAM을 확인하지 못했다. [미확인] https://github.com/shubham-goel/4D-Humans · https://github.com/yufu-wang/tram · https://github.com/caizhongang/SMPLer-X
- [추정] RTX 2070 8 GB에서 WHAM이나 GVHMR 추론은 짧은 클립이면 될 가능성이 있지만 확인되지 않았다. 직접 시험해야 한다.

### 2.3 텍스트 → 모션
- **HY-Motion 1.0**(Tencent, 2025-12): DiT 플로 매칭 모델로 10억 파라미터. 학습 데이터는 모션 3,000시간 이상이고 출력은 SMPL-H 22관절. [P] https://arxiv.org/abs/2512.23464v1
  - VRAM은 1.0B가 26 GB, Lite가 24 GB 필요하다(3자). [I] https://www.sourcepulse.org/projects/21729235
  - **라이선스가 EU, 영국, 한국을 지역에서 제외**한다는 GitHub 이슈가 있다. [C/V 인용] https://github.com/Tencent-Hunyuan/HY-Motion-1.0/issues/49
  - 결론: 우리(한국, 8 GB)는 사용 불가로 본다.
- **Uthana**: 모든 플랜에서 API 키를 발급하고 GraphQL 단일 엔드포인트에 Python, TS SDK를 준다. 영상→모션은 고정 카메라와 한 명이 조건이다. 자동 리깅은 FBX/GLB를 받는다. [V] https://uthana.com/blog/how-uthanas-api-speeds-up-text-to-motion-animation · https://uthana.com/product/video-to-motion
  - 요금: 무료는 비상업. 상업은 텍스트→모션 초당 $0.02~0.10, 영상→모션 초당 $0.05, 리그 하나 $0.15, 월 최소 $100. [I(3자 요약)] https://aisotools.com/pricing/uthana · 공식 https://uthana.com/pricing
  - 독립 비교: 괜찮지만 자세가 부자연스러울 때가 있다. [I] https://tato.studio/blog/best-ai-video-to-mocap
- **SayMotion**(DeepMotion): 텍스트나 영상 프롬프트로 3D 애니를 만든다. 요금은 별도이고 미확인. [V] https://cgpress.org/archives/deepmotion-releases-saymotion-a-new-generative-ai-for-text-to-animation.html
- **Tripo 애니메이션 API**: 리그된 모델만 입력으로 받는다. 걷기, 뛰기, 대기, 전투, 생물별 동작 프리셋이 있고 하나에 10 크레딧(배치는 최대 5개). [V] https://developers.tripo3d.com/en/models/animation
- **Meshy Animate**: 사람형과 네발 자동 리그, 프리셋 500개 이상, FBX/GLB. 텍스트→모션과 크레딧 비용은 문서에 없다. [V] https://docs.meshy.ai/en/webapp/guides/animate
- **MDM / MoMask**: 이번에 조사하지 않았다. 학습 데이터(HumanML3D/AMASS)에 비상업 제약이 있을 가능성이 있다. [미확인] https://github.com/GuyTevet/motion-diffusion-model · https://github.com/EricGuo5513/momask-codes
- **Mixamo**: 이번 조사에서 확인하지 않았다(무료, 사람형만으로 알려짐). [미확인] https://www.mixamo.com

---

## 3. 몬스터 / 비인간형

현실적인 결론부터 [추정]: **임의 생물체 영상을 그대로 3D 리그 애니로 바꾸는 생산용 도구는 없다.** 실제로 쓸 수 있는 길은 세 가지다.
1. 자동 리그와 프리셋 동작(Tripo, Meshy, Anything World)
2. 키프레임 보조(Cascadeur 네발 AutoPosing)
3. 연구 코드(개 SMAL 등 특정 종만)

### 3.1 Tripo 자동 리그 + 애니
- 7가지 생물 유형(네발 포함)을 자동 리깅한다. Rig Check는 무료다. 리그는 25 크레딧이고 애니는 하나에 10 크레딧. [V] https://developers.tripo3d.com/en/models/rig · https://developers.tripo3d.com/en/models/animation
- 네발 리그와 애니 하나를 합치면 약 35 크레딧이다. Tripo는 "Mixamo와 AccuRig는 네발을 못 한다"고 주장한다(벤더 주장). [V] https://www.tripo3d.ai/blog/ai-tools-for-rigging-and-animating-quadruped-or-non-humanoid-3d
- 무료 플랜 산출물 라이선스(CC BY 4.0 표기와 약관 문구)가 애매하다는 지적이 있다. [I] https://ludo.ai/compare/meshy-alternatives
- 우리 규칙: Tripo 유료 생성은 사용자가 정한 크레딧 상한 안에서만 한다(메모리 규칙).

### 3.2 Meshy
- 사람형과 네발 자동 리그, 프리셋 500개 이상, FBX/GLB. [V] https://docs.meshy.ai/en/webapp/guides/animate
- 리그와 애니 크레딧 비용은 미확인. [미확인] https://docs.meshy.ai/en/webapp/pricing

### 3.3 Anything World (Animate Anything)
- 네발, 곤충, 물고기, 새를 지원한다. 20,000 버텍스가 넘으면 축소 처리하고, 리그에는 뼈와 웨이트가 있다. [I] https://www.cgchannel.com/2023/10/animate-anything-uses-ai-to-rig-your-3d-characters
- 요금(공식): 개인 $0(최근 12개월 매출이나 투자가 10만 달러 미만), Micro $50/월, Pro $250/월. [V] https://anything.world/pricing
- 크레딧과 API 호출 수는 3자 사이트마다 다르다. [I] https://toolquestor.com/vs/anything-world-vs-avatar-sdk
- [추정] 다리가 많거나 날개가 있는 생물에 가장 넓게 대응하지만, 품질은 프리셋 수준이다. 덩어리형(블롭)은 뼈 구조가 정해지지 않아 셰이프키나 물리 기반으로 직접 만드는 편이 낫다.

### 3.4 Cascadeur
- 2025.3에서 AutoPosing과 Quick Rigging에 네발 지원을 넣었고(알파), 2026.1에서 네발 AutoPosing이 더 자연스러워졌다고 한다. 2026.1에는 Root Motion AI도 들어갔다. [V] https://cascadeur.com/blog/view/cascadeur-2025-3-new-inbetweening-quadrupeds · https://cascadeur.com/blog/view/cascadeur-2026-1-new-renderer-ue-live-link
- 라이선스: Free는 상업 사용 불가에 자체 포맷만 내보낸다. Indie는 FBX, DAE, USD를 내보내고 매출이나 투자가 10만 달러 미만이어야 한다. Pro는 제한 없음. [V] https://cascadeur.com/agreement · https://cascadeur.com/blog/general/cascadeurs-new-licensing-structure-comprehensive-faq
- 가격은 출처마다 다르다. Indie 약 $8/월(연간)~$19/월, Pro $33~49/월. [I] https://bityclips.com/tool/cascadeur/pricing

### 3.5 영상 → 동물 포즈와 4D (연구)
- **SuperAnimal-Quadruped**(DeepLabCut): 네발 동물 이미지 4만 장 이상으로 학습한 2D 키포인트 39점 모델. 라이선스 표기가 충돌한다(Apache-2.0 태그 / "연구 전용, 비상업" / 상업은 EPFL TTO 문의). [V] https://huggingface.co/mwmathis/DeepLabCutModelZoo-SuperAnimal-Quadruped/blob/d69a44904d67dabc806af97f490acd8006129b8b/README.md · https://github.com/DeepLabCut/deeplabcut
- **4D-Animal**(2025-07 사전공개): 개 SMAL 템플릿 기반. 수작업 키포인트 없이 실루엣, 부위, 시간 단서로 영상에서 애니 가능한 3D 동물을 만든다. 코드 공개. [P] https://arxiv.org/abs/2507.10437
- **WildAni4D**(CVPR 2026 Findings): 합성 영상으로 학습해 프레임 간 떨림을 줄였다. [P] https://openaccess.thecvf.com/content/CVPR2026F/html/Cho_WildAni4D_Towards_4D_Animal_Mesh_Reconstruction_CVPRF_2026_paper.html
- **Animal-in-Motion** 벤치마크: 모델 기반 방법은 2D 지표는 좋지만 3D 형태가 비현실적이고, 모델 없는 방법은 자연스럽지만 점수가 낮다. [P] https://par.nsf.gov//servlets/purl/10650464
- AI4Animation(Unity, 학습에 모캡 데이터 필요)과 Animal3D는 이번에 조사하지 않았다. [미확인] https://github.com/sebastianstarke/AI4Animation
- [추정] 이 연구들은 SMAL(실제 동물 형태) 템플릿에 묶여 있어 우리 몬스터 메시로 옮기려면 별도 리타깃이 필요하다. 생산 파이프라인으로는 아직 이르다. 단, 실제 개나 고양이 영상을 SMAL 동작으로 뽑아 네발 몬스터에 리타깃하는 실험은 해볼 만하다(라이선스는 따로 확인 필요).

---

## 4. AI 생성 영상과 스타일 영상을 입력으로 쓸 때

- **공개된 직접 시험은 없다.** Veo, Kling, Sora 영상을 모캡 솔버에 넣어 발 미끄러짐을 잰 공개 테스트는 찾지 못했다. [검색 결과 없음]
- 관련 연구:
  - PhyMotion(2026): 생성 영상에서 GVHMR로 SMPL-X 궤적을 뽑아 운동학, 접촉, 동역학 타당성을 채점한다. 즉 "AI 영상 → GVHMR"은 이미 평가 도구로 쓰이는 경로다. [P] https://arxiv.org/pdf/2605.14269
  - HumanScore(Stanford): 생성 영상 13개 모델의 사람 동작을 6개 지표로 평가했고, 보기에 그럴듯한 것과 생체역학적 정확도 사이에 일관된 차이를 발견했다. [P] https://cs.stanford.edu/~xtiange/projects/humanscore/
- 발 미끄러짐, 떠오름, 관통, 가짜 접촉은 고급 상용 파이프라인에도 남는 결함이다. [P] https://arxiv.org/html/2601.19036v1
- 가림(팔다리가 화면 밖으로 나감)이 생기면 결과가 이상해진다. [V] https://www.rokoko.com/insights/tutorial-start-animating-with-our-free-ai-mocap-tool-rokoko-video
- 고정 카메라, 평평한 바닥, 한 명이 조건이다. [V] https://help.wonderdynamics.com/create-new-project/ai-motion-capture/ · https://uthana.com/product/video-to-motion
- [추정] AI 영상에서 예상되는 실패:
  1. 프레임마다 손가락 개수나 팔다리 길이가 바뀜(형태 붕괴) → 뼈 길이 흔들림, 손 추적 실패
  2. 물리 불일치(발이 땅에서 미끄러짐) → 영상 자체에 미끄러짐이 있으면 솔버가 그대로 옮김
  3. 카메라 흔들림이나 줌 → 전역 궤적 오류
  4. 클립이 짧음(5~10초) → 긴 동작은 이어 붙여야 함
  5. 애니풍이나 카툰풍 영상 → 사람 포즈 추정기의 검출률이 떨어짐(얼굴은 1.1 참고)
- [추정] 대응: AI 영상 프롬프트에 "고정 카메라, 전신, 단색 배경, 한 명, 실사풍 사람"을 넣는다. 실제로 찍은 같은 동작 영상을 대조군으로 두고 발 속도와 뼈 길이 흔들림을 수치로 비교한다. 몸 동작은 실사풍 사람 영상에서 뽑아 스타일 캐릭터로 리타깃한다.

---

## 5. RTX 2070 8 GB에서 무료로 로컬 실행 가능한 것

| 항목 | 가능 여부 | 비고 |
|---|---|---|
| MediaPipe Face Landmarker → ARKit 52 CSV → Blender | 가능(CPU로도 됨) | 무료, 상업 가능(Apache-2.0으로 알려짐 [미확인 원문]) |
| anime-face-detector(28점) | 가능 | MIT 표기 |
| Audio2Face-3D(소리 → 얼굴) | 가능성 높음 | 8 GB에서 동작은 [미확인] |
| WHAM / GVHMR(영상 → SMPL) | 짧은 클립은 가능성 있음 | [미확인]. SMPL과 GVHMR 라이선스 때문에 상업 출시용으로는 부적합 |
| HY-Motion | 불가 | VRAM 24~26 GB, 한국 제외 라이선스 |
| Cascadeur Free | 가능 | 상업 불가, FBX 내보내기 불가 |
| SuperAnimal / 4D-Animal | 가능성 있음 | 연구용 |

---

## 6. 저비용 추천(우리 파이프라인 기준) [추정, 근거는 위 각 항목]

**얼굴**
1. 기본: 실사 사람 참고 영상(직접 촬영 또는 실사풍 AI 영상)을 MediaPipe로 돌려 ARKit 52 CSV를 만들고, Blender 스크립트로 우리 셰이프키에 키프레임을 넣는다. 비용 0원, 완전 자동화.
2. 립싱크(아 에 이 오 우): Audio2Face-3D로 소리에서 곡선을 만들고 ARKit 52로 매핑한다. 비용 0원.
3. 품질을 더 올리려면 TrueDepth iPhone과 Live Link Face(무료) CSV를 쓴다.
4. 하지 말 것: 애니풍 AI 영상을 직접 트래킹하는 것.

**몸**
1. 시험·프로토타입: WHAM이나 GVHMR 로컬(무료)을 SMPL로 뽑아 Rigify에 리타깃한다(연구 라이선스 범위).
2. 출시용 저가: Rokoko Vision Basic($10/월에 600초)과 QuickMagic(독립 평가 양호, 손가락 됨)을 같은 클립으로 비교한 뒤 하나를 고른다. 대량으로 자동화하려면 Uthana API(영상→모션 초당 $0.05, 월 최소 $100)를 쓴다.
3. 자세가 어려운 동작만 Move One이나 Flow Studio를 건별로 쓴다.
4. 텍스트→모션: Tripo 프리셋(10 크레딧)이나 Uthana. HY-Motion은 제외.

**몬스터**
1. 네발: Tripo 리그(25) + 프리셋 애니(10)를 쓰거나 Meshy 프리셋을 쓰고, 부족한 부분은 Cascadeur Indie 네발 AutoPosing으로 키프레임한다.
2. 곤충, 새, 물고기: Anything World(개인 무료 조건 확인).
3. 덩어리형: 리그 대신 셰이프키나 래티스, 물리 기반 절차 애니(Blender 스크립트).
4. 실제 동물 영상 → SMAL(4D-Animal) → 몬스터 리타깃은 연구 실험으로만.

---

## 7. 주요 위험

1. **라이선스**
   - GVHMR(비상업), SMPL·SMPL-X(비상업, 상업은 별도 라이선스), SuperAnimal(연구용 표기)
   - HY-Motion(한국 지역 제외)
   - DeepMotion 무료와 Cascadeur Free는 상업 불가
   - Tripo 무료 산출물 라이선스가 애매함
2. **서비스 지속성**
   - Radical 종료(2026-07)
   - Meshcapade는 Epic 인수(2026-02) 뒤 플랫폼 상태가 불확실
   - Rokoko는 듀얼 카메라와 웹캠 실시간을 폐지
   - 가격이 자주 바뀜(Move AI 문서끼리도 충돌)
3. **AI 영상 품질**: 공개 벤치마크가 없다. 형태 붕괴, 물리 불일치, 짧은 클립 문제가 있다.
4. **애니 얼굴**: 사람 얼굴 트래커의 검출률이 떨어진다. 애니 전용 검출기는 28점뿐이다.
5. **ARKit 변환**
   - MetaHuman과 FLAME 결과에는 ARKit 52 변환 단계가 따로 필요하다.
   - 눈동자와 턱처럼 관절로 움직이는 부분은 셰이프키로 바꿀 때 손실된다. [C] https://forum.reallusion.com/PrintTopic556386.aspx
6. **독립 평가 부족**: 몸 모캡 비교는 사실상 tato.studio 한 곳(2025-08, 정성 평가)뿐이다. 우리 클립으로 직접 비교해야 한다.

---

## 8. 출처 (본문에 쓴 주요 URL)
- MediaPipe Face Landmarker: https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
- MetaHuman 모노 영상: https://dev.epicgames.com/documentation/metahuman/metahuman-animation-from-mono-video-capture-in-unreal-engine
- Audio2Face-3D: https://huggingface.co/nvidia/Audio2Face-3D-v3.0 · https://arxiv.org/abs/2508.16401v1
- Rokoko 가격·Vision: https://www.rokoko.com/pricing · https://www.rokoko.com/products/vision
- Move One 가격: https://docs.move.ai/knowledge/move-one-pricing
- DeepMotion: https://www.deepmotion.com/pricing-animate3d
- 독립 비교: https://tato.studio/blog/best-ai-video-to-mocap
- Flow Studio: https://www.autodesk.com/au/products/flow-studio/compare
- Radical 종료: https://www.cgchannel.com/?p=175200
- Meshcapade 인수: https://www.mpg.de/26082348/max-planck-spin-off-draws-epic-games-to-tuebingen
- GVHMR 라이선스: https://raw.githubusercontent.com/zju3dv/GVHMR/main/LICENSE
- WHAM 라이선스: https://raw.githubusercontent.com/yohanshin/WHAM/main/LICENSE
- SMPL 라이선스: https://smpl.is.tue.mpg.de/modellicense.html
- HY-Motion: https://arxiv.org/abs/2512.23464v1 · https://github.com/Tencent-Hunyuan/HY-Motion-1.0/issues/49
- Uthana: https://uthana.com/pricing · https://uthana.com/blog/how-uthanas-api-speeds-up-text-to-motion-animation
- Tripo 리그·애니: https://developers.tripo3d.com/en/models/rig · https://developers.tripo3d.com/en/models/animation
- Meshy: https://docs.meshy.ai/en/webapp/guides/animate
- Anything World: https://anything.world/pricing
- Cascadeur: https://cascadeur.com/blog/view/cascadeur-2026-1-new-renderer-ue-live-link · https://cascadeur.com/agreement
- SuperAnimal: https://huggingface.co/mwmathis/DeepLabCutModelZoo-SuperAnimal-Quadruped/blob/d69a44904d67dabc806af97f490acd8006129b8b/README.md
- 4D-Animal: https://arxiv.org/abs/2507.10437
- AI 영상 동작 평가: https://arxiv.org/pdf/2605.14269 · https://cs.stanford.edu/~xtiange/projects/humanscore/
- anime-face-detector: https://huggingface.co/hysts/anime-face-detector-hrnetv2
- AI Mocap Studio: https://superhivemarket.com/products/ai-mocap-studio
