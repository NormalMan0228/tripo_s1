# 학술 문헌 조사: 임의/스타일화 3D 머리의 표정 블렌드셰이프·페이스 리그 자동 생성과 이형(異形) 얼굴 간 표정 전이

조사일: 2026-10-13. 범위: 2001–2026 (SIGGRAPH / SIGGRAPH Asia / Eurographics / SCA / CVPR / ICCV / arXiv, Disney·Weta·ILM·Meta·Roblox·Snap 등).
목표 관점: "원본 메시를 유지한 채(neutral = 원본) 사실/카툰/애니/체형 차이/몬스터까지 ARKit-52 식 표정을 자동 생성"하는 파이프라인에 무엇이 쓸 만한가.
표기: [검증] = 이번 세션에서 1차 출처(논문 HTML/초록/저장소)로 확인, [요약] = 검색 결과 요약으로만 확인.

---

## Q1. 주요 방법 계열: 핵심 아이디어 / 필요한 대응(correspondence)·템플릿 / 스타일·비율 차이 처리 / 실패 모드

### Takeaway
방법은 크게 (A) 기하 전이(Deformation Transfer 계열), (B) 예제 기반 개인화(Example-based rigging), (C) 이미 리그가 있는 캐릭터의 가중치 공간 리타게팅, (D) 메시 비의존 신경 리깅(NFR → NFS → RigAnyFace), (E) 2025–2026 "템플릿 패밀리 + 자동 분할 + 희소 DT + 규칙" 파이프라인(OmniFaceRig) 및 생성형(T2Bs, RegHead), (F) 3DMM(FLAME/NPHM), (G) 물리/근육 기반으로 나뉜다. "원본 neutral을 그대로 두고 표정만 생성"한다는 요구에 직접 맞는 것은 A·B·D·E이며, C는 셰이프 생성이 아니라 "구동(가중치 산출)" 문제를 푼다.

### Cited Findings

#### A. 기하 전이 (Deformation Transfer 계열)
- **Deformation Transfer (Sumner & Popović, SIGGRAPH 2004, TOG 23(3))** [검증]: 소스 메시가 보이는 변형(삼각형별 affine 변환)을 서로 다른 타깃 메시에 다시 적용. 사용자가 소수의 vertex marker를 찍어 삼각형 대응 맵을 만들고, 정점 수·연결성이 달라도 됨. 선형 시스템을 한 번 분해(factor)해 두면 새 변형 전이는 back-substitution만 필요. — [Project page](https://people.csail.mit.edu/sumner/research/deftransfer)
- DT 공식 페이지는 논문·영상·메시 데이터(.obj)를 제공하며, 검색된 자료에서 공식 소스코드 링크는 확인되지 않음(데이터는 사용 시 출처 표기 요청). — [Data page](https://people.csail.mit.edu/sumner/research/deftransfer/data.html)
- 한계: 원 DT는 단일 컴포넌트 manifold 삼각 메시에만 적용 가능하다는 지적이 있고, Ben-Chen·Weber·Gotsman의 Spatial Deformation Transfer가 다중 컴포넌트/사면체 등으로 확장. — [Spatial Deformation Transfer (EG/SCA)](https://diglib.eg.org/handle/10.2312/14962)
- 2026년 비교 연구(OmniFaceRig)는 DT의 약점을 "수동 대응 주석 필요"로 정리하고, 동시에 자기 파이프라인 내부의 실제 블렌드셰이프 전이 엔진으로 **sparse deformation transfer(Sumner & Popović 2004, 삼각형별 affine)** 를 그대로 사용, 후처리로 Point Deform + Delta Mush 스무딩, 눈꺼풀 닫힘·시선·턱·치아-얼굴 충돌 규칙을 붙임. — [OmniFaceRig HTML](https://arxiv.org/html/2606.08043)
- Disney(Chandran et al. 2022)는 "직접 DT는 개별 기하 요소 단위로 작동해 아티팩트가 생기기 쉽고, 블렌드셰이프 리그 방식은 대형 리그 제작비가 크다"고 기존 두 접근을 비판. — [Disney Research Studios page](https://studios.disneyresearch.com/2022/07/24/local-anatomically-constrained-facial-performance-retargeting)
- **Expression Cloning (Noh & Neumann, SIGGRAPH 2001)**: 이 계열의 초기작(정점 모션 벡터 전이). 세부 내용은 이번 세션에서 미확인. — [SIGGRAPH history](https://history.siggraph.org/learning/expression-cloning-by-noh-and-neumann/)
- **Semantic Deformation Transfer (Baran, Vlasic, Grinspun, Popović, SIGGRAPH 2009, TOG 28(3))** [검증]: 기하를 그대로 복사하지 않고 "의미"를 전이. 보간·투영이 선형대수로 되는 shape space를 두고, **양 캐릭터의 짝지어진 예제 포즈 몇 개**로 두 shape space 간 대응을 추정. 예: 사람 걷기를 홍학에 옮길 때 무릎이 반대로 굽어야 함; 그림 1은 대응 포즈 5쌍으로 다른 캐릭터 포즈를 생성. — [Paper PDF](https://homes.cs.washington.edu/~jovan/papers/baran-2009-sdt.pdf); [Adobe Research](https://research.adobe.com/publication/semantic-deformation-transfer)

#### B. 예제 기반 개인화 (Example-based facial rigging)
- **Example-Based Facial Rigging (Li, Weise, Pauly, SIGGRAPH 2010)** [요약]: 일반 템플릿 블렌드셰이프의 "컨트롤 의미와 표정 동역학"을 타깃으로 옮기고, 타깃 캐릭터의 예제 포즈를 최대한 재현하도록 블렌드셰이프를 최적화. 포즈를 추가할수록 점진적으로 개선, **훈련 포즈 1개로도 그럴듯한 애니메이션**, 정점 공간보다 **gradient 공간 최적화가 우수**. 수작업 캐릭터와 실제 배우 스캔 모두 시연. — [EPFL Infoscience](https://infoscience.epfl.ch/record/149375); [SIGGRAPH history](https://history.siggraph.org/?p=105425)
- 오픈 재구현(MIT 라이선스)은 ARKit 블렌드셰이프를 템플릿으로 쓰며, **모든 입력(템플릿 셰이프·타깃·예제 포즈)이 동일 토폴로지**여야 함; 타깃이 다르면 별도 DT 저장소로 먼저 타깃 토폴로지의 블렌드셰이프를 만들라고 안내. — [vasiliskatr/example_based_facial_rigging_ARkit_blendshapes](https://github.com/vasiliskatr/example_based_facial_rigging_ARkit_blendshapes)
- **Expression Packing (Carrigan, Zell, Guiard, McDonnell, Eurographics 2020, CGF 39(2))** [요약]: 템플릿 기반 블렌드셰이프 전이를 개인화할 때 필요한 "훈련 표정"을 정수 최적화로 최소화(활성 블렌드셰이프 겹침 최소), 스캔 수가 제한되면 일반 전이 대비 개선폭이 큰 셰이프를 우선. CGF 메타데이터상 CC BY 4.0. — [EG Digital Library](https://diglib.eg.org/handle/10.1111/cgf13925)
- **Orvalho, Zacur, Susin, "Transferring the Rig and Animations from a Character to Different Face Models" (CGF 27(8), 2008)** [요약]: 소스 리그를 한 번 만들고, 얼굴 특징 **랜드마크**로 리그를 해부학적 비율에 맞게(anthropometric) 변형해 다른 얼굴 모델에 적용. NURBS/폴리곤/래티스/스켈레톤까지 적응, 기존 애니 스크립트 재사용. 저자들의 2007 SIGGRAPH 토크는 수작업 대비 90–99% 빠르다고 주장(개발자 자체 추정). — [EG Digital Library](https://diglib.eg.org/handle/10.2312/CGF.v27i8pp1997-2012); [SIGGRAPH talk](https://history.siggraph.org/?p=141592)

#### C. 이미 리그가 있는 스타일화 캐릭터로의 리타게팅(가중치 공간)
- **Facial Retargeting with Automatic Range of Motion Alignment (Blanco i Ribera, Zell, Lewis, Noh, Botsch; SIGGRAPH 2017, TOG 36(4):154)** [요약]: 기존 방법이 수작업 배우-캐릭터 포즈 쌍을 요구하거나 비율이 비슷할 때만 된다는 한계를 지적. 캐릭터 블렌드셰이프 리그의 모션 공간과 배우의 표현적 훈련 시퀀스 모션 공간을 **manifold alignment**로 정렬; 이산 미분 기반 smoothness prior; **두 캐릭터 간 희소 대응만** 필요, 스타일화 캐릭터로 전이 가능. 저자 소속 KAIST/Bielefeld/TU Dortmund 등(Disney 논문 아님). — [Paper PDF](https://cg.cs.tu-dortmund.de/publications/2017-faces.pdf); [KAIST record](https://koasas.kaist.ac.kr/handle/10203/224590)
- **Spacetime Expression Cloning for Blendshapes (Seol, Lewis, Seo, Choi, Anjyo, Noh; TOG 31(2), 2012)** [요약]: 모션을 위치의 시간미분으로 보고 Poisson 방정식으로 리타게팅; 타깃 얼굴의 그럴듯한 표정 공간 prior + 베이지안 정식화; 시간 지터 없이 소스 리듬 유지. — [KAIST DSpace](https://dspace.kaist.ac.kr/handle/10203/102030)
- "Artist friendly facial animation retargeting" (Seol, Seo, Kim, Lewis, Noh) — 존재만 확인. — [SIGGRAPH history](https://history.siggraph.org/?p=197627)
- **DeepExpr (Aneja et al., ACCV 2016)** [요약]: 사람 표정 CNN과 스타일화 캐릭터 표정 CNN을 따로 학습 후 transfer learning으로 공통 특징공간에 연결, 사람 표정에 대응하는 캐릭터 표정을 검색. FERG-DB(스타일화 캐릭터 표정 데이터셋) 제시. — [Adobe Research](https://research.adobe.com/publication/modeling-stylized-character-expressions-via-deep-learning); [arXiv 1911.08591](https://arxiv.org/pdf/1911.08591)
- **ExprGen: Learning to Generate 3D Stylized Character Expressions from Humans (Aneja et al., WACV 2018)** [요약]: 사람/캐릭터 표정 인식 CNN의 잠재변수로 3D 캐릭터 **리그 파라미터**를 산출; 여러 캐릭터로 일반화, 한 캐릭터 리그로 다른 리그를 반지도식 구동; "순수 기하가 아니라 지각적 타당성"을 기준으로 함. MTurk 평가. — [Paper PDF](https://grail.cs.washington.edu/wp-content/uploads/2018/03/aneja2018ltg.pdf); [Adobe Research](https://research.adobe.com/publication/learning-to-generate-3d-stylized-character-expressions-from-humans)
- **Facial Expression Retargeting from Human to Avatar Made Easy (Zhang et al., arXiv 2008.05110, 2020)** [요약]: 표정이 과장되면 블렌드셰이프(선형 공간) 저차원 근사가 나빠질 수 있다고 지적, 사람/아바타 표정을 각각 VAE로 비선형 표현하고 잠재공간 간 번역 네트워크 학습. — [ar5iv](https://ar5iv.labs.arxiv.org/html/2008.05110)
- **Kim et al., Pacific Graphics 2021 (CGF 40(7)), KAIST + Gulliver Studios** [요약]: 비지도 딥러닝 리타게팅으로 소스 블렌드셰이프 가중치를 **비율·토폴로지·블렌드셰이프 구성이 다른** 타깃 모델로 전이; 수작업 쌍 데이터 불필요. — [Paper PDF](https://diglib7.eg.org/bitstream/handle/10.1111/cgf14400/v40i7pp045-055.pdf)
- **Deep-Learning-Based Facial Retargeting Using Local Patches (Choi et al., CGF 2024; arXiv 2601.08429, 2026)** [요약]: KAIST + Netmarble F&C·Anigma. "인간 얼굴 구조에서 크게 벗어난 스타일화/과장 캐릭터"를 대상으로, 소스 영상 프레임에서 로컬 패치 자동 추출 → 타깃 패치 재연(reenactment) → 프레임별 리그 가중치 추정. 전역 이미지 기반 방법보다 정점 오차가 낮다고 보고. — [EG Digital Library](https://diglib.eg.org/handle/10.1111/cgf15263); [arXiv](https://arxiv.org/abs/2601.08429)
- **Semi-Supervised Video-Driven Facial Animation Transfer for Production (Moser et al., Digital Domain, TOG 40(6), 2021)** [요약]: 비지도 image-to-image translation으로 이미지 도메인 간 공유 잠재표현을 학습해 영상→3D 캐릭터, 캐릭터↔캐릭터(렌더 경유) 전이. 스타일화 대상 여부는 미확인. — [dblp (Lucio Moser)](https://dblp.org/pid/186/0119)
- **FreeAvatar (NetEase Fuxi, SIGGRAPH Asia 2024)** [요약]: 대규모 무라벨 얼굴 이미지로 표정 foundation model을 학습하고, 신경 렌더러로 미분 가능하게 만든 "Expression-driven Multi-avatar Animator"가 아바타별 컨트롤 파라미터를 산출(여러 아바타 동시 학습). 랜드마크 기반 기하 제약은 미묘한 감정을 못 잡는다고 주장. — [arXiv 2409.13180](https://arxiv.org/abs/2409.13180v2)
- **Local Anatomically-Constrained Facial Performance Retargeting (Chandran, Ciccone, Gross, Bradley; Disney Research|Studios, SIGGRAPH 2022)** [요약]: 2단계 — 로컬 표정 디테일을 타깃에 전이 → 해부학적 제약을 쓴 전역 얼굴 표면 예측으로 타깃의 그럴듯한 형상 범위 안에 유지. 아티스트용 블렌드셰이프식 미세조정 컨트롤 제공. 기존 DT보다 우수, 프로덕션 블렌드셰이프 기법과 동급 품질을 **훨씬 적은 입력 셰이프**로 달성. 주 대상은 사람→사람이나 **사람→크리처도 동작**한다고 기술. — [Disney Research Studios](https://studios.disneyresearch.com/2022/07/24/local-anatomically-constrained-facial-performance-retargeting); [PDF](https://studios.disneyresearch.com/app/uploads/2022/07/Local-Anatomically-Constrained-Facial-Performance-Retargeting-1.pdf)
- 후속 **Anatomically Constrained Implicit Face Models (Chandran & Zoss, Disney, CVPR 2024)**: 2022 방법의 해부학 solve가 프레임당 수 분 걸린다고 지적, 자기 방법은 프레임당 약 2–3초. — [arXiv 2312.07538](https://arxiv.org/pdf/2312.07538)
- **Production-Level Facial Performance Capture Using Deep CNNs (Laine et al., NVIDIA/Remedy/Pinscreen/USC/Aalto, SCA 2017)** [요약]: 고급 멀티뷰 스테레오 + 아티스트 보정 애니로 배우 1명을 캡처하고, **5–10분 분량**으로 CNN을 학습해 단안 영상에서 그 배우 얼굴의 조밀 3D 추적(가려진 부위 포함)을 실시간 추론. 즉 배우별(per-subject) 캡처 자동화이며 스타일화 리타게팅·블렌드셰이프 생성 방법은 아님. — [NVIDIA Research](https://research.nvidia.com/publication/2017-07_production-level-facial-performance-capture-using-deep-convolutional-neural); [arXiv 1609.06536](https://arxiv.org/pdf/1609.06536)
- Larey et al. (arXiv 2306.12188, 2023): 영상 프레임을 랜드마크로 바꾸고 기관(organ)별로 묶어 블렌드셰이프 가중치로 매핑, 합성 데이터 **캐릭터 1개**만으로 학습; 눈 표정 별도 처리. (추적→가중치 문제) — [arXiv](https://arxiv.org/abs/2306.12188)

#### D. 메시 비의존 신경 리깅 (Neural face rigging)
- **Neural Face Rigging (NFR; Qin, Saito, Aigerman, Groueix, Komura; HKU + Adobe; SIGGRAPH 2023 conf., DOI 10.1145/3588432.3591556)** [검증]: 정체성 인코더 + 표정 인코더 → 디코더가 neutral 메시를 표정으로 변형하는 deformation autoencoder. 인코더는 정면 RGBD 렌더(256²)용 2D CNN + 정점 좌표/법선용 DiffusionNet; 정체성 코드 100-D, 표정 코드 128-D 중 **앞 53차원을 ICT FaceKit의 53개 FACS(ARKit 호환) 파라미터로 정규화**, 나머지는 데이터에서 학습(Multiface 4D 스캔의 세밀 변형). 디코더는 **Neural Jacobian Fields**(삼각형별 3×3 Jacobian을 MLP로 예측). 연결성이 다른 임의 얼굴 메시에 수동 블렌드셰이프·대응 없이 적용. — [arXiv HTML](https://arxiv.org/html/2305.08296v1); [arXiv abs](https://arxiv.org/abs/2305.08296)
- NFR 한계(저자): 눈·입 주변 내부 구조 제거 "standardization" 단계가 여전히 필요; MetaHuman 등 다른 파라미터화는 데이터 접근 문제로 미검증; 나이·성별·인종 편향 연구 필요. 시험 메시는 FaceWarehouse, Triplegangers, MetaHuman, 아티스트 메시 등 **사람**만. — [arXiv HTML](https://arxiv.org/html/2305.08296v1)
- NFR 저장소 README: 커스텀 타깃은 `align.blend`로 대략 정렬, "얼굴 안에 입/눈/코 소켓과 안구가 없어야" 하고, "전역 solve가 맞도록 입과 눈을 잘라야(cut)" 함. — [NFR_pytorch](https://github.com/dafei-qin/NFR_pytorch)
- 후속 논문들이 지적한 NFR 실패 모드: 미묘한 부피 변화(얇아짐/두꺼워짐)와 shifting 아티팩트, 역리깅 시 표정 얽힘(소스에 없는 눈감김), **스타일화 메시에서 눈썹 이동·메시 스케일 변화 아티팩트** — [Neural Face Skinning HTML](https://arxiv.org/html/2505.22416v1); 단일 연결 외피 컴포넌트에만 작동하고 분리된 서브메시 미지원, 사람 데이터로만 학습 — [OmniFaceRig HTML](https://arxiv.org/html/2606.08043); 비인간형 in-the-wild 머리를 거의 변형하지 못함, 최대 컴포넌트만 남기고 안쪽 입술/눈꺼풀을 다듬는 전처리 필요 — [RigAnyFace HTML](https://arxiv.org/html/2511.18601v1)
- **Neural Face Skinning for Mesh-agnostic Facial Expression Cloning (NFS; Cha, Yoon, Seo, Noh; KAIST + Flawless AI; Eurographics 2025, CGF)** [검증]: NFR 구조(CNN + DiffusionNet) 위에 **skinning encoder**를 추가 — 타깃 정점별 skinning weight를 예측(사전 정의 분할 라벨로 간접 감독)해 전역 표정 코드가 작용하는 영역을 제한, 로컬 디테일 보존. 출력은 원본 정점에 더하는 정점별 변위(=원본 neutral 보존). 표정 코드 128-D 중 ICT 53개 FACS로 감독. 학습: ICT(100명) + Multiface(13명); **스타일화 데이터 미사용**. 미학습 스타일화 얼굴(Mery, Malcolm, Bonnie, Morphy)에 정성 평가만, NFR은 눈썹 이동·스케일 변화, ZPT는 전부 실패했다고 보고. ICT MSE 0.3514(NFR) → 0.2480. — [arXiv HTML](https://arxiv.org/html/2505.22416v1); [EG DL](https://diglib.eg.org/handle/10.1111/cgf70009)
- NFS 한계(저자): 편집성이 ICT 블렌드셰이프에 한정(머리 자세·목 불가), **타깃 스케일이 학습 데이터와 다르면 skinning weight 부정확** → 표정 품질 저하, 학습에 GT 분할 필요, 프레임별 처리로 지터. — [arXiv HTML](https://arxiv.org/html/2505.22416v1)
- **RigAnyFace (RAF; Ma, Kneubuehler, Chu, Sachs, Jiang, Huang; Penn State + Roblox; arXiv 2511.18601, 2025-11)** [검증]: 정적 neutral 메시 + FACS 벡터 → 정점별 3D 변위. DiffusionNet 기반에 FACS 조건 diffusion block과 **분리 컴포넌트(안구 등)용 전역 인코더** 추가(5.4M 파라미터). 리그 정의: **FACS 48 + corrective 48 = 96 포즈**. 데이터: 리그 있는 머리 161 + 리그 없는 머리 175; 리그 없는 머리는 MegActor 기반 2D 얼굴 애니로 포즈 이미지를 만들고 분할 마스크 + RAFT optical flow로 **2D 감독**(1단계), 이후 리그 데이터로 3D 손실 미세조정(2단계). 2D 생성/flow 모델은 소수 리그 머리 렌더로 **스타일화 얼굴에 미세조정**. 테스트 시 템플릿·대응점·랜드마크 불필요, T4 GPU 약 3.1초. 정량 평가는 인간형 머리만, 비인간형은 정성. — [arXiv HTML](https://arxiv.org/html/2511.18601v1)
- RAF 한계(저자): 세부 기하가 없는 껍데기형(shell-like) 메시에서 성능 저하, 얼굴이 여러 조각으로 쪼개진 부실한 메시에서 변형 후 공간 일관성 상실. — [arXiv HTML](https://arxiv.org/html/2511.18601v1)

#### E. 2025–2026 전 자동 파이프라인 및 생성형
- **OmniFaceRig (Wang, Ma, …, Ranjan; Meta Reality Labs; arXiv 2606.08043, 2026-06)** [검증]: 표면만 있는(구강 없음) 정적 캐릭터 메시 → **FACS 블렌드셰이프 최대 155개**(Core 13 / Additional 46 / Full 155) + 절차적 치아·잇몸·혀 + UV 재패킹. 단계: VLM+CV 혼합 riggability 검사 → 다중 모델 얼굴 파싱(41클래스 stylized Sapiens 파서, 38클래스 humanoid 파서, SAM 3 폴백, 영역별 적응 선택; 약 1만 장 주석 2D 이미지로 미세조정) → **조밀 키포인트 기반 템플릿 정합**(전역 강체 정렬 + 정점별 비강체 변형, 코는 키포인트에서 제외) → 절차적 구강 생성(RBF로 치아 템플릿 워프, ARAP+SDF로 치아 배치) → 충돌 인지 블렌드셰이프 전이(sparse DT). **템플릿 3종(human / long-muzzle: 개·늑대·여우·말 / short-muzzle: 고양이·곰·토끼·호랑이)을 VLM이 자산별로 선택**. 300개 인간·인간형 부분집합에서 최종 성공률 99.0%, 20–30초/자산. ARKit 언급 없음. — [arXiv HTML](https://arxiv.org/html/2606.08043); [arXiv abs](https://arxiv.org/abs/2606.08043)
- OmniFaceRig 한계(저자): 세 템플릿 패밀리 안의 "얼굴이 보이는" 캐릭터만 대상, **모든 동물·스타일화 캐릭터를 덮는 일반 파라미터화가 아님** — 새 토폴로지 패밀리는 템플릿·분할 라벨·riggability 기준을 추가해야 함. 실패 예: 새(뾰족한 부리), 물고기형(넓고 긴 입이 얼굴 경계 근처), 곤충(거대 겹눈), 해마형(길고 납작한 주둥이·가려진 입). riggability 검사는 필터일 뿐 분할 오류·템플릿 피팅 불안정·입 위치 오류로 실패 가능. — [arXiv HTML](https://arxiv.org/html/2606.08043)
- **RegHead: Non-Humanoid Head Blendshapes via Feed-Forward Registration (Luo et al.; UCSC, UIUC, KAUST, Snap; arXiv 2607.12206, 2026-07)** [검증]: 공유 표정 어휘(**7개 표정**, ARKit 52 아님)를 가진 비인간형 정체성 데이터셋을, 소수 아티스트 리그 라이브러리로부터 **미세조정 이미지 편집 모델(Qwen-Image)로 표정 이미지 생성 → 이미지 조건 3D/4D 생성으로 표정 메시 재구성 → 사람 검수**로 약 2만 개까지 확장. 피드포워드 정합 모델이 neutral을 voxelize하고 앵커별 변환을 예측, 비정합 표정 메시를 neutral 기반 대응 블렌드셰이프 기저로 변환(LBS로 neutral의 조밀 점을 변형 → neutral 기하가 베이스). 약 5초. 한계: 곤충형·긴 꼬리 종 등 일반 머리 해부와 먼 경우 underfit, 눈/입이 모호하면 의미 대응 약함, 상류 메시의 아티팩트·정체성 드리프트에 민감, 국소 미소/찡그림 재현 어려움. — [arXiv HTML](https://arxiv.org/html/2607.12206); [arXiv abs](https://arxiv.org/abs/2607.12206)
- **T2Bs: Text-to-Character Blendshapes via Video Generation (Luo et al.; UCSC + Snap 등)** [검증]: text-to-3D로 정적 캐릭터 메시 생성 → 20개 표정 프롬프트로 비디오 확산 모델이 표정 영상 생성 → 메시 정점에서 초기화한 deformable 3D Gaussian(약 2,000 제어점 LBS)으로 정렬 → 프레임별 메시를 PCA로 직교 블렌드셰이프화(실험은 100-블렌드셰이프). ARKit/FACS 어휘·FLAME 미사용(생성 캐릭터 자신의 메시가 템플릿). 동물·카툰 머리 대상이며, 사람 랜드마크 검출기가 안 맞아 VLM으로 눈·입을 분할해 20개 정규 랜드마크 선택; MagicArticulate·UniRig 스켈레톤은 얼굴 모션에 부적합 판정. 한계: 머리만, 초기 자산의 구강 내부 커버리지 필요, 비디오 모델의 부자연스러운 변형·시간 불일치, 약 1800초/정체성(RegHead 측 비교). — [arXiv HTML v2](https://arxiv.org/html/2509.10678v2); [RegHead HTML](https://arxiv.org/html/2607.12206)
- T2Bs 게재처: arXiv v2 본문에는 학회명이 없으나 CVF Open Access에 ICCV 2025 논문으로 등재(출처 간 표기 차이). — [CVF ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/html/Luo_T2Bs_Text-to-Character_Blendshapes_via_Video_Generation_ICCV_2025_paper.html)
- **ToonifyGB (arXiv 2505.10072, IEEE VR 2026 포스터)** [요약]: 개선 StyleGAN으로 실사 영상을 스타일화 영상(Arcane, Pixar 스타일)으로 바꾼 뒤 3D Gaussian 블렌드셰이프(neutral + 표정 블렌드셰이프)를 재구성, 얼굴 추적 파라미터로 구동. 입력은 실제 얼굴 영상이며 메시가 아닌 Gaussian. — [arXiv HTML](https://arxiv.org/html/2505.10072v3)
- **DreamFace (Zhang et al.; ShanghaiTech + Deemos; TOG 42(4), 2023)** [요약]: 텍스트 → CLIP 공간으로 거친 형상 선택 → SDS로 변위·법선 정제; neutral 자산이 **통일 토폴로지**라 블렌드셰이프 기반 애니메이션을 자연스럽게 지원(즉 고정 템플릿 토폴로지 위의 생성). 상용 서비스(hyperhuman)로 이어짐. — [arXiv 2304.03117](https://arxiv.org/abs/2304.03117); [SIGGRAPH blog](https://blog.siggraph.org/?p=17443)
- **Towards Native Generative Model for 3D Head Avatar (arXiv 2410.01226, 2024)** [요약]: 생성 머리 메시가 ARKit와 같은 52채널 체계를 따르므로 정체성을 고정하고 블렌드셰이프 파라미터로 구동 가능 — 임의 스타일 메시에 ARKit을 붙이는 방법이 아니라 템플릿 공간 내 생성. — [arXiv PDF](https://arxiv.org/pdf/2410.01226)

#### F. 3DMM / 파라메트릭 머리 모델
- **FLAME 라이선스**: FLAME 2017/2019/2020/2023 및 Blender 애드온은 **비상업 과학연구·교육·비상업 예술**용 소프트웨어 라이선스; 상용 제품 포함·상용 서비스·상업 목적 산출물 생성 금지, 제3자 배포는 MPI 서면 허가 필요, 신경망 학습 사용 제한 조항 존재(스니펫 절단). — [FLAME model license](https://flame.is.tue.mpg.de/modellicense.html)
- FLAME 상업 사용에 관해 상충 신호: 2020 기관 발표는 "연구자·기업에 무료 제공", Hugging Face 코멘트는 "FLAME 2023 Open 상업 무료"라 주장하나 공식 페이지는 학술 라이선스로 표기 — 서면 확인 전 상업 사용 불가로 간주해야 함. — [MPI news](https://ps.is.tuebingen.mpg.de/news/scientists-in-tubingen-develop-3d-head-model-that-can-be-used-to-design-better-fitting-protective-gear); contradicted by [FLAME license](https://flame.is.tue.mpg.de/modellicense.html); [HF discussion](https://huggingface.co/3DAIGC/LAM-20K/discussions/2)
- **NPHM (Giebenhain et al., 2022/2023)**: 신경(implicit) 파라메트릭 머리 모델. 저자 명시 한계 — 기하만 다루고 외관 정보 없음, 느슨한 머리카락 미표현. — [arXiv 2212.02761](https://arxiv.org/pdf/2212.02761)
- **FaceTalk (Aneja, Thies, Dai, Nießner)**: 오디오 기반 모션 diffusion을 NPHM 표정 공간에서 수행 — 즉 NPHM이 표현하는 사람 머리 공간에 묶임. — [arXiv 2312.08459](https://arxiv.org/pdf/2312.08459)
- **GNM Head (Google, 2026)**: Apache 2.0으로 공개된 파라메트릭 사람 머리 모델(상업 통합 가능). 스타일화 대응 여부 미확인. — [HF papers](https://huggingface.co/papers/2607.23687); [arXiv](https://arxiv.org/pdf/2607.23687)
- NVIDIA Maxine AR SDK의 기본 얼굴 피팅 모델은 ICT-FaceKit ICT Face Model의 수정본(시선 블렌드셰이프 추가). — [NVIDIA Maxine docs](https://docs.nvidia.com/maxine/ar/latest/Appendix/C3DMMVersions.html)

#### G. 물리/근육 기반
- **Phace (Ichim, Kadlecek, Kavan, Pauly; SIGGRAPH 2017, TOG 36(4))** [요약]: 블렌드셰이프 대신 연조직·능동 근육·뼈 상호작용의 비선형 퍼텐셜 에너지 최소화로 표정 계산; 충돌·접촉 처리로 블렌드셰이프의 비현실 포즈 감소; 새로운 근육 활성화 정식화; **개인별 모델을 소수 표정 스캔으로 거의 자동 생성**; 연조직 부피 스케일로 얼굴을 마르게/통통하게 변경, 좀비 변환 데모. 비인간 얼굴 일반화는 출처에 없음. — [Project page](https://users.cs.utah.edu/~ladislav/ichim17phace/ichim17phace.html)
- Ichim et al. 2016(SCA)은 "블렌드셰이프는 빠르고 직접 제어되지만 동역학·충돌·비압축성 통합이 어렵고, 물리 기반은 이를 자동 제공하나 근육·뼈 등 해부 모델링이 어렵다"고 정리. — [Phace project page / EPFL](https://infoscience.epfl.ch/record/231436)
- **Learning Active Quasistatic Physics-based Models from Data (Srinivasan, Wang, Rojas, Klár, Kavan, Sifakis; SIGGRAPH 2021, TOG 40(4):129)** [요약]: 미분 가능 준정적 물리 시뮬 층 + 디코더 신경망; **근육 구조를 가정하지 않고** 예제 포즈로부터 작동(actuation) 구조와 제어를 학습; 최대 25만 요소 볼륨 모델; 희소 모캡 입력·직접 조작 스컬프팅 지원. (Ziva 계열 연구진) — [Project page](https://pages.cs.wisc.edu/~qisiw/SIG.html)
- **Learning a Generalized Physical Face Model From Data (Yang, Zoss, Chandran, Gross, Solenthaler, Sifakis, Bradley; Disney; SIGGRAPH 2024)** [요약]: 대규모 3D 얼굴로 학습한 일반 물리 얼굴 모델을 **단일 3D 스캔 또는 단일 이미지**로 새 정체성에 빠르게 피팅; 애니 컨트롤·캐릭터 간 리타게팅, 충돌 회피·중력·마비·뼈 리셰이핑 효과. 기존엔 캐릭터마다 변형 모델 학습(숙련 아티스트 + 긴 학습)이 필요했다고 지적. 스타일화/비인간 지원 여부는 페이지에 없음. — [Disney Research Studios](https://studios.disneyresearch.com/?p=43021)
- "An Implicit Physical Face Model Driven by Expression and Style" (arXiv 2401.15414) — 제목만 확인. — [arXiv](https://arxiv.org/pdf/2401.15414)
- **Art-Directed Muscle Simulation for High-End Facial Animation (Cong, Bhat, Fedkiw; Stanford + ILM; SCA 2016)** [요약]: 근육에 블렌드셰이프 시스템을 만들어 생체역학 시뮬을 구동(아티스트 제어 + 물리), 선택적 snap으로 스컬프트 주름과 물리 입 모양 혼합, **단일 neutral 포즈로부터 새 크리처 얼굴로 애니메이션 전이** 가능. — [EG Digital Library](https://diglib.eg.org/handle/10.2312/sca20161229)
- ILM은 *Kong: Skull Island*에서 두개골·근육 포함 해부학적 얼굴 시뮬 모델을 만들고 목표 셰이프를 맞추며 "on-model"을 유지(SIGGRAPH 2017 talk). Cong & Fedkiw "Muscle-Based Facial Retargeting with Anatomical Constraints" 토크도 존재. — [Kong talk](https://history.siggraph.org/?p=84135); [Retargeting talk](https://history.siggraph.org/?p=79478)
- **Animatomy (Choi, Eom, …, Letteri, Singh; Wētā + U. Toronto; SIGGRAPH Asia 2022)** [요약]: FACS 셰이프 세트 대신 **근섬유 곡선(muscle fiber curves)** 의 수축/이완 strain을 해부학적 기저로 사용, strain이 피부 변형을 구동해 배우→캐릭터(나비족) 전이. FACS 시스템은 근육 분리·커버리지·대립·중복 문제가 있다고 주장; Letteri는 FACS 퍼펫 리그가 최대 약 900개 셰이프까지 늘어난다고 언급. *Avatar: The Way of Water*에 사용, Gollum 이래의 FACS 파이프라인 대체. — [Project page](https://dgp.toronto.edu/projects/animatomy); [fxguide](https://www.fxguide.com/?p=287134)

#### H. 기타(리그 역변환·바디)
- **Rig Inversion by Training a Differentiable Rig Function (EA SEED, SIGGRAPH Asia 2022)** [요약]: MLP로 리그 함수를 근사해 미분 가능 대리 모델을 만들고, 이를 이용해 메시→리그 파라미터 역변환 모델 학습. 토이 리그 예제 코드 공개. — [EA SEED](https://ea.com/seed/news/seed-rig-inversion-differentiable-rig-function); [GitHub](https://github.com/electronicarts/rig-inversion)
- Holden, Saito, Komura (SCA 2015) "Learning an Inverse Rig Mapping for Character Animation": 애니메이터가 만든 희소 예제로 스켈레톤→리그 공간 비선형 회귀 + 도함수 학습, Old Man 얼굴 리그 예. — [EG DL](https://diglib.eg.org/items/3282c733-71cb-4095-8be0-c2daae4b4072)
- Racković et al. (3Lateral/Epic 공저): 2차/4차 보정항이 있는 블렌드셰이프 모델의 정확·희소 역리그 해. — [ar5iv 2302.04820](https://ar5iv.org/html/2302.04820)
- **Neural Blend Shapes (Li, Aberman, Hanocka, Liu, Sorkine-Hornung, Chen; SIGGRAPH 2021)**: 이족(biped) 바디 자동 리깅·스키닝·blend shape 생성 라이브러리, 정렬된 삼각 메시 입력; 얼굴 리깅은 다루지 않음. — [GitHub](https://github.com/PeizhuoLi/neural-blend-shapes); [ar5iv](https://ar5iv.labs.arxiv.org/html/2105.02451)

### Inferences
- "원본 메시 유지" 요구에 부합하는 출력 형태는 (i) DT/Example-based처럼 타깃 메시 자체의 정점 해를 구하는 것, (ii) NFS·RAF처럼 원본 정점에 변위를 더하는 것, (iii) RegHead처럼 neutral을 베이스로 LBS 변형하는 것이다. 반대로 DreamFace·"Native Generative Head"·FLAME/NPHM 피팅은 고정 템플릿 토폴로지/공간으로 메시를 **대체**하므로 이 요구와 충돌한다(앞서 사용자가 거부한 template wrap과 같은 문제).
- C 계열(Ribera, Seol, ExprGen, Kim 2021, Choi 2024, FreeAvatar, Moser)은 "타깃 리그가 이미 있다"는 전제 하의 구동 문제다. 52개 셰이프 자체를 만드는 단계 이후, 사람 추적 → 스타일화 캐릭터 가중치 변환(특히 과장 캐릭터의 range-of-motion 정렬) 단계에서 쓸모가 있다.
- 2026년 산업 연구(OmniFaceRig)가 결국 "자동 분할/키포인트 + 템플릿 패밀리 정합 + 고전 sparse DT + 눈꺼풀·턱·충돌 규칙"으로 돌아왔다는 점은, 현 프로젝트의 tools/face_auto 방향(원본 보존 + 영역 컷 + 규칙)이 학계 최신 실무 해법과 같은 축에 있음을 시사한다. 신경 방법(NFR/NFS/RAF)은 정량적으로는 사람 얼굴에서만 검증되었다.

### Gaps
- "Real-time facial animation on stylized characters"라는 정확한 제목의 논문은 찾지 못함(유사 주제는 Choi 2024, ExprGen, FreeAvatar).
- StyleRig, HeadSculpt, Text2Avatar, AnimeHead, Toonify3D, "Diffusion-based facial rig generation", "Learning Compositional Radiance Fields of Dynamic Human Heads"는 이번 세션에서 1차 출처 확인을 못 함(대부분 2D/NeRF·3DMM 기반으로 원본 메시 리깅과는 거리가 있을 것으로 보이나 미검증).
- Sifakis et al. 2005(근육 활성 추정), Bouaziz 2013/Li 2013(실시간 추적용 DT·온라인 보정) 등 고전 문헌은 이번에 출처를 확보하지 못함.
- Li 2010의 상세 실패 모드(예제 포즈가 템플릿 의미와 크게 다를 때 등)는 초록·재구현 README 수준에서만 확인.

---

## Q2. 하나의 템플릿 vs 스타일별 템플릿 vs 절차적·랜드마크·영역 상대 규칙 — 문헌은 무엇을 말하나

### Takeaway
"단일 사람 템플릿/3DMM 하나로 모든 스타일"은 문헌상 일관되게 실패 요인으로 지적되고(사람 데이터 편향, 스케일·비율 차이, 과장 표정의 선형 공간 한계), 최신 실무형 시스템은 **소수의 템플릿 패밀리 + 자동 분할·키포인트 + 규칙 후처리**(OmniFaceRig: 3종), 또는 **템플릿 + 대상별 예제 포즈로 개인화**(Li 2010, Expression Packing, Semantic DT, Chandran 2022)로 수렴한다. 그 어떤 방식도 새·물고기·곤충형 같은 "패밀리 밖" 얼굴은 아직 못 다룬다.

### Cited Findings
- **단일 템플릿의 한계 증거**
  - NFR은 사람 데이터(ICT + Multiface)로만 학습, 사람 메시로만 시험; 후속 연구에서 스타일화 메시에 눈썹 이동·스케일 변화 아티팩트, 비인간형 머리는 거의 변형 못 함. — [NFR HTML](https://arxiv.org/html/2305.08296v1); [NFS HTML](https://arxiv.org/html/2505.22416v1); [RigAnyFace HTML](https://arxiv.org/html/2511.18601v1)
  - NFS: 타깃 스케일이 학습 분포와 다르면 skinning weight가 부정확해짐(=비율 차이에 취약). — [NFS HTML](https://arxiv.org/html/2505.22416v1)
  - 과장 표정은 블렌드셰이프(선형 공간) 저차원 근사가 나쁠 수 있음. — [Zhang 2020](https://ar5iv.labs.arxiv.org/html/2008.05110)
  - 기존 리타게팅은 배우와 캐릭터 비율이 비슷할 때만 작동하거나 수작업 포즈 쌍을 요구. — [Ribera 2017](https://cg.cs.tu-dortmund.de/publications/2017-faces.pdf)
  - 의미 보존이 기하 보존보다 중요할 수 있음(사람→홍학 무릎 방향). — [Semantic DT](https://homes.cs.washington.edu/~jovan/papers/baran-2009-sdt.pdf)
  - FLAME/NPHM은 사람 머리 스캔 기반 모델이며, NPHM은 기하만·머리카락 미표현 등 한계를 명시; FLAME은 상업 사용 제한. — [NPHM](https://arxiv.org/pdf/2212.02761); [FLAME license](https://flame.is.tue.mpg.de/modellicense.html)
- **스타일/종(種)별 템플릿 패밀리**
  - OmniFaceRig: human / long-muzzle / short-muzzle 3종 템플릿을 VLM이 선택; 새 토폴로지 패밀리는 템플릿·분할 라벨·riggability 기준을 추가해야 한다고 명시; 부리·물고기 입·겹눈·해마 주둥이에서 실패. — [OmniFaceRig HTML](https://arxiv.org/html/2606.08043)
  - 얼굴 파싱도 스타일별로 분리: 스타일화 인간용 41클래스 Sapiens 파서, 카툰 동물·비인간용 38클래스 humanoid 파서, SAM 3 폴백. — [OmniFaceRig HTML](https://arxiv.org/html/2606.08043)
- **템플릿 + 대상별 예제(개인화)**
  - Li 2010: 일반 템플릿 → 타깃 예제 포즈로 개인화, 포즈 1개로도 그럴듯. — [EPFL](https://infoscience.epfl.ch/record/149375)
  - Expression Packing: 최소 훈련 표정 집합 자동 선택. — [EG DL](https://diglib.eg.org/handle/10.1111/cgf13925)
  - Chandran 2022: 프로덕션 블렌드셰이프 대비 훨씬 적은 입력 셰이프로 동급 품질, 크리처에도 동작. — [Disney](https://studios.disneyresearch.com/2022/07/24/local-anatomically-constrained-facial-performance-retargeting)
  - Semantic DT: 대응 예제 포즈 몇 쌍(그림 1은 5쌍). — [Paper](https://homes.cs.washington.edu/~jovan/papers/baran-2009-sdt.pdf)
- **랜드마크·영역 상대(로컬) 방식**
  - Orvalho 2008: 랜드마크로 리그를 해부학적 비율에 맞춰 변형 — 형태·외관과 무관하게 리그 재사용 목표. — [EG DL](https://diglib.eg.org/handle/10.2312/CGF.v27i8pp1997-2012)
  - NFS: 전역 코드는 유지하되 예측된 skinning(영역) 가중치로 작용 범위를 제한해 로컬 디테일 보존. — [NFS HTML](https://arxiv.org/html/2505.22416v1)
  - Choi 2024: 로컬 패치 단위 재연이 전역 이미지 기반보다 스타일화 타깃에서 우수. — [EG DL](https://diglib.eg.org/handle/10.1111/cgf15263)
  - Chandran 2022: 로컬 전이 → 해부 제약 전역 해. — [Disney PDF](https://studios.disneyresearch.com/app/uploads/2022/07/Local-Anatomically-Constrained-Facial-Performance-Retargeting-1.pdf)
  - T2Bs: 비인간 얼굴엔 사람 랜드마크 검출기가 부적합 → VLM으로 눈·입 분할 후 20개 정규 랜드마크를 3D 자산에 선택. — [T2Bs HTML](https://arxiv.org/html/2509.10678v2)
  - RegHead: "고정 표정 어휘(공유 vocabulary)"가 정체성 간 가중치 의미를 일정하게 해 캐릭터별 새 대응 없이 리타게팅 가능 — 다만 어휘는 7개. — [RegHead HTML](https://arxiv.org/html/2607.12206)
- **어휘(blendshape 세트) 자체의 문제**
  - Wētā: FACS 기반은 근육 분리·커버리지·대립·중복 문제가 있어 근섬유 strain 기저로 교체; FACS 퍼펫은 최대 약 900 셰이프. — [Animatomy](https://dgp.toronto.edu/projects/animatomy); [fxguide](https://www.fxguide.com/?p=287134)
  - 리그 크기는 연구마다 다름: NFR/NFS = ICT 53(ARKit 호환), RAF = FACS 48 + 보정 48, OmniFaceRig = 13/46/155, RegHead = 7, T2Bs = PCA(실험 100). — 각 HTML: [NFR](https://arxiv.org/html/2305.08296v1), [RAF](https://arxiv.org/html/2511.18601v1), [OmniFaceRig](https://arxiv.org/html/2606.08043), [RegHead](https://arxiv.org/html/2607.12206), [T2Bs](https://arxiv.org/html/2509.10678v2)

### Inferences
- 문헌 근거로 보면 현실적 최적점은 "**의미(어휘)는 하나(ARKit 52)로 고정**, 기하적 템플릿은 **소수 패밀리**(예: 사람형 사실/세미/카툰/애니 공통 1개 + 주둥이형 동물 1–2개), 패밀리 내부 차이는 **영역 상대 규칙(눈꼬리·입꼬리·턱 피벗 등 랜드마크 앵커)** 과 **원본 위 DT/변위**로 흡수"이다. OmniFaceRig가 정확히 이 구조이며 후처리 규칙(눈꺼풀 닫힘, 시선, 턱, 충돌)을 명시적으로 둔다.
- 애니 스타일(큰 눈, 작은 코/입, 평면적 얼굴)은 어떤 논문에서도 정량 검증된 적이 없다. OmniFaceRig도 "모든 스타일화 캐릭터를 덮지 않는다"고 명시하므로, 애니는 눈꺼풀·입 규칙을 스타일별로 따로 두는 편이 안전해 보인다(추론).
- "체형(마름/뚱뚱)" 차이는 얼굴 리깅 문헌에서 별도 축으로 다뤄지지 않는다. NFS의 스케일 민감성 보고를 보면, 학습형 방법을 쓴다면 입력 정규화(스케일·정렬)가 필수다(추론). DT/규칙 방식은 타깃 자체의 국소 프레임에서 계산하므로 이 문제에 상대적으로 강하다(추론).

### Gaps
- 단일 템플릿 vs 다중 템플릿을 같은 데이터셋에서 직접 비교한 통제 실험(ablation)은 찾지 못함. OmniFaceRig의 ablation 세부(템플릿 1종으로 했을 때 수치)는 이번에 확인 못 함.
- 애니메이션 스타일(일본 애니) 전용 블렌드셰이프 자동 생성 학술 논문은 이번 검색에서 발견되지 않음.

---

## Q3. 스타일화·과장 캐릭터와 크리처를 명시적으로 다루는 방법, 그리고 각각 요구하는 것

### Takeaway
명시적으로 다루는 방법은 많지만, **아무 입력 없이 임의 스타일 메시에 셰이프를 생성**하는 것은 2025–2026년의 RigAnyFace·OmniFaceRig·RegHead·T2Bs뿐이고, 그 외(Ribera, ExprGen, Kim 2021, Choi 2024, Chandran 2022, Semantic DT, Li 2010, Cong 2016)는 **타깃의 기존 블렌드셰이프 리그, 아티스트 예제 포즈, 또는 해부(근육·두개골) 설정**을 요구한다.

### Cited Findings
| 방법 (연도, 게재) | 스타일/크리처 대상 | 타깃 측 요구사항 | 출처 |
|---|---|---|---|
| Semantic DT (SIGGRAPH 2009) | 형태·의미가 다른 캐릭터(사람→홍학) | 양쪽 짝지어진 예제 포즈 몇 쌍 | [PDF](https://homes.cs.washington.edu/~jovan/papers/baran-2009-sdt.pdf) |
| Example-based rigging (SIGGRAPH 2010) | 수작업 캐릭터 | 템플릿 블렌드셰이프(동일 토폴로지로 사전 전이) + 타깃 예제 포즈 ≥1 | [EPFL](https://infoscience.epfl.ch/record/149375); [repo](https://github.com/vasiliskatr/example_based_facial_rigging_ARkit_blendshapes) |
| Orvalho et al. (CGF 2008) | 형태·외관 무관 리그 재사용 | 소스 리그 + 랜드마크 | [EG DL](https://diglib.eg.org/handle/10.2312/CGF.v27i8pp1997-2012) |
| Ribera et al. (SIGGRAPH 2017) | 스타일화 캐릭터 | 캐릭터 블렌드셰이프 리그 + 배우 표현 훈련 시퀀스 + 희소 대응 | [PDF](https://cg.cs.tu-dortmund.de/publications/2017-faces.pdf) |
| DeepExpr (ACCV 2016) / ExprGen (WACV 2018) | 스타일화 카툰 캐릭터 | 캐릭터 리그 + 캐릭터 표정 이미지 데이터(FERG-DB 류) | [Adobe](https://research.adobe.com/publication/modeling-stylized-character-expressions-via-deep-learning); [PDF](https://grail.cs.washington.edu/wp-content/uploads/2018/03/aneja2018ltg.pdf) |
| Kim et al. (PG 2021) | 비율·토폴로지·블렌드셰이프 구성 상이 | 타깃 블렌드셰이프 모델(쌍 데이터 불필요) | [PDF](https://diglib7.eg.org/bitstream/handle/10.1111/cgf14400/v40i7pp045-055.pdf) |
| Choi et al. (CGF 2024) | 인간 구조에서 크게 벗어난 스타일화/과장 | 타깃 캐릭터 리그(가중치 추정) | [EG DL](https://diglib.eg.org/handle/10.1111/cgf15263) |
| Chandran et al. Disney (SIGGRAPH 2022) | 사람→사람 주력, 크리처도 가능 | 소수 타깃 셰이프 + 해부 제약 | [Disney](https://studios.disneyresearch.com/2022/07/24/local-anatomically-constrained-facial-performance-retargeting) |
| Cong, Bhat, Fedkiw ILM (SCA 2016) | 크리처 | 근육 모델 + 단일 neutral 포즈로 전이 | [EG DL](https://diglib.eg.org/handle/10.2312/sca20161229) |
| Animatomy Wētā (SIGGRAPH Asia 2022) | 배우→나비족 | 근섬유 곡선 기저, 고품질 동적 스캔으로 최적화 | [Project](https://dgp.toronto.edu/projects/animatomy) |
| NFS (EG 2025) | 스타일화 얼굴(정성) | neutral만(학습엔 분할 라벨) | [HTML](https://arxiv.org/html/2505.22416v1) |
| RigAnyFace (arXiv 2025) | 스타일화·비인간형(정성) | neutral + FACS 벡터, 분리 컴포넌트 허용 | [HTML](https://arxiv.org/html/2511.18601v1) |
| OmniFaceRig Meta (arXiv 2026) | 인간·인간형·주둥이 긴/짧은 동물 | 표면 메시만(자동 템플릿 선택) | [HTML](https://arxiv.org/html/2606.08043) |
| RegHead Snap (arXiv 2026) | 비인간형 크리처 머리 | neutral + 비정합 표정 메시(생성 파이프라인 산출) | [HTML](https://arxiv.org/html/2607.12206) |
| T2Bs Snap (ICCV 2025) | 동물·카툰 머리 | 텍스트(메시도 생성) | [HTML](https://arxiv.org/html/2509.10678v2) |

- 크리처 리타게팅의 별도 고전 축으로, Seol, O'Sullivan, Lee의 "Creature Features" (SCA 2013)는 사람 모션으로 비인간 캐릭터를 실시간 퍼핏팅하지만 **바디** 모션 대상이다. — [EG DL](https://diglib.eg.org/handle/10.2312/15006)
- RegHead는 표정 데이터 부족 문제를 "아티스트 리그 소수 라이브러리 → 미세조정 이미지 편집으로 표정 이미지 → 이미지 기반 3D/4D 재구성 → 사람 검수"로 해결. — [RegHead HTML](https://arxiv.org/html/2607.12206)
- RigAnyFace는 소수 리그 머리 렌더로 2D 애니메이션/flow 모델을 스타일화 얼굴에 미세조정해, 리그 없는 스타일화 메시도 2D 감독으로 학습에 사용. — [RAF HTML](https://arxiv.org/html/2511.18601v1)

### Inferences
- 사용자의 현재 흐름(Tripo로 open-mouth 등 표정 레퍼런스 생성 → 원본 neutral에 정합)은 RegHead의 데이터 생성 아이디어(이미지 편집으로 표정 이미지 → 3D 재구성 → neutral에 정합)와 구조적으로 같다. 차이는 RegHead가 7개 표정과 학습된 피드포워드 정합기를 쓴다는 것. 52개 전부를 이 방식으로 만들기는 비용상 어렵고, **소수 핵심 표정(예: jawOpen, eyeBlink, mouthSmile, mouthFunnel/Pucker 등)만 생성·정합해 Example-based rigging(Li 2010)의 예제 포즈로 쓰고 나머지는 템플릿 DT + 개인화**로 채우는 조합이 문헌상 자연스럽다(추론). Expression Packing은 어떤 소수 표정을 고를지에 대한 근거를 준다.
- 크리처(주둥이형)는 사람 템플릿에서 DT로 직접 옮기면 실패 위험이 크고(OmniFaceRig가 별도 템플릿을 둔 이유), Ribera/Chandran류는 이미 리그가 있어야 하므로, "주둥이형 전용 ARKit-호환 템플릿 1–2개"를 수작업으로 한 번 만드는 비용이 가장 현실적이다(추론).

### Gaps
- Weta/ILM/Disney의 크리처용 얼굴 리타게팅의 내부 알고리즘 세부(예: Gollum~Avatar 사이 FACS 기반 크리처 솔브)는 공개 논문 수준에서는 Animatomy, Cong 2016, Kong 토크 이상으로 확인하지 못함.
- RigAnyFace·OmniFaceRig·RegHead의 애니(일본 애니 풍) 결과는 정량 보고 없음.

---

## Q4. 쓸 수 있는 코드·데이터와 라이선스

### Takeaway
실제로 내려받아 쓸 수 있는 것은 **NFR(MIT, 단 학습 데이터는 ICT/Multiface 조건 승계)**, **Li 2010 ARKit 재구현(MIT)**, **DT 원 논문 데이터(코드 없음)**, **EA rig-inversion(라이선스 미확인)**, **Neural Blend Shapes(바디, 라이선스 미확인)** 정도다. 2025–2026 최신작(NFS, RigAnyFace, OmniFaceRig, RegHead, T2Bs)은 코드 공개가 확인되지 않았고, OmniFaceRig는 벤치마크 데이터(Omni-Bench)만 공개를 명시했다. FLAME은 비상업 라이선스다.

### Cited Findings
- **NFR**: 코드 MIT 라이선스(LICENSE 파일 포함); 사전학습 모델·전처리 테스트 데이터는 Google Drive, 라이선스 표기 없음; 학습 데이터는 ICT-FaceKit·Multiface 유래 — 상류 라이선스 확인 필요. — [NFR_pytorch](https://github.com/dafei-qin/NFR_pytorch)
- NFR 샘플 학습 데이터(HKU-CGVU/NFR-sample-data, ICT 40명, 약 3GB; 전체는 약 800GB)는 ICT-FaceKit 유래이며 그 라이선스를 따르라고 명시. — [Hugging Face](https://huggingface.co/datasets/HKU-CGVU/NFR-sample-data)
- **Example-based facial rigging ARKit 재구현**: MIT; 동일 토폴로지 필수; 포함 메시는 데모용(타 오픈소스 유래, ICT-FaceKit 타깃 얼굴 포함). — [GitHub](https://github.com/vasiliskatr/example_based_facial_rigging_ARkit_blendshapes)
- **Deformation Transfer**: 공식 페이지는 논문·영상·메시 데이터 제공, 공식 코드 링크는 미확인(사용 시 출처 표기 요청). — [Project](https://people.csail.mit.edu/sumner/research/deftransfer); [Data](https://people.csail.mit.edu/sumner/research/deftransfer/data.html)
- **Neural Face Skinning**: 코드 저장소 언급 없음; arXiv 논문만 CC BY 4.0. — [arXiv HTML](https://arxiv.org/html/2505.22416v1)
- **RigAnyFace**: 코드/데이터 공개 여부 미기재(논문 CC BY 4.0, 프로젝트 페이지 wenchao-m.github.io/RigAnyFace.github.io); OmniFaceRig 저자도 "RAF 코드가 공개되지 않아 재실행 불가"라고 기술. — [RAF HTML](https://arxiv.org/html/2511.18601v1); [OmniFaceRig HTML](https://arxiv.org/html/2606.08043)
- **OmniFaceRig**: Omni-Bench(1,000개 이족 캐릭터, FACS 블렌드셰이프 + 구강 기하; 인간·인간형·고양이·개 등) "자유 이용 가능" 공개, omnifacerig.github.io; 코드 공개·데이터 라이선스는 명시되지 않음. — [arXiv abs](https://arxiv.org/abs/2606.08043); [arXiv HTML](https://arxiv.org/html/2606.08043)
- **RegHead / T2Bs**: 프로젝트 페이지·GitHub 링크는 있으나 코드/데이터 공개와 라이선스를 본문에서 확인하지 못함(논문 자체는 CC BY 4.0). — [RegHead HTML](https://arxiv.org/html/2607.12206); [T2Bs HTML](https://arxiv.org/html/2509.10678v2)
- **EA SEED rig-inversion**: 토이 리그 예제(데이터 생성·리그 근사 학습·역변환 스크립트) 공개. 라이선스는 이번에 미확인. — [GitHub](https://github.com/electronicarts/rig-inversion)
- **Neural Blend Shapes**: 바디 자동 리깅·스키닝·blend shape 라이브러리 공개, 이족 사전학습 모델, LICENSE 파일 존재하나 종류 미확인; 얼굴 미지원. — [GitHub](https://github.com/PeizhuoLi/neural-blend-shapes)
- **FLAME**: 비상업 연구/교육/비상업 예술 전용, 상업 제품·서비스 불가. — [FLAME license](https://flame.is.tue.mpg.de/modellicense.html)
- **GNM Head (Google)**: Apache 2.0(상업 통합 가능). — [HF papers](https://huggingface.co/papers/2607.23687)
- **Expression Packing 논문**: CC BY 4.0(논문). 코드 공개 여부 미확인. — [EG DL](https://diglib.eg.org/handle/10.1111/cgf13925)
- **Cong 학위논문** "Art-directed muscle simulation…": CC BY-NC 3.0. — [Stanford PURL](https://purl.stanford.edu/dk455yp8085)
- NFR 저장소의 테스트 메시 템플릿 출처: COMA, FLAME, MeshTalk(각자 라이선스 적용). — [NFR_pytorch](https://github.com/dafei-qin/NFR_pytorch)

### Inferences
- 상업 게임 파이프라인에 바로 넣을 수 있는 "임의 스타일 → ARKit 52" 공개 코드는 사실상 없다. 공개·허용 라이선스인 것은 NFR(MIT, 사람 얼굴 전용·전처리 필수)과 Li 2010 재구현(MIT)뿐이며, 둘 다 ICT/ARKit류 사람 템플릿에 의존한다. ICT-FaceKit 데이터·사전학습 가중치의 상업 사용 가능 여부는 별도 확인이 필요하다.
- 따라서 현 프로젝트는 (1) 자체 DT/규칙 엔진(tools/face_auto)을 주력으로 유지하고, (2) NFR을 사람형 얼굴의 비교 기준선 또는 초기값 생성기로 시험하며, (3) Omni-Bench를 스타일화·동물 회귀 테스트 세트 후보로 검토하는 것이 문헌·라이선스 측면에서 타당하다(추론; Omni-Bench 라이선스 확인 전 상업 학습 사용은 보류).

### Gaps
- ICT-FaceKit의 정확한 라이선스 조문, NPHM 코드/모델 라이선스, EA rig-inversion·Neural Blend Shapes 저장소 라이선스 종류는 이번 세션에서 확인하지 못함.
- OmniFaceRig·RegHead·T2Bs의 향후 코드 공개 여부는 프로젝트 페이지를 직접 확인해야 함(이번에는 arXiv 본문만 확인).
- DreamFace, FaceTalk, ToonifyGB의 코드/라이선스 미확인.
