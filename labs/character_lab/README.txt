Tripothon Character Atelier — B형 탐험가 V5

실행: 저장소 루트의 Character_Lab.cmd를 더블클릭.
편집: Godot 4.7.2에서 이 폴더의 project.godot를 열기.
명령: powershell -NoProfile -ExecutionPolicy Bypass -File tools/open_character_lab.ps1
기존 실행 게임, 서버 및 온라인 DB와 별개의 로컬 제작 검수 프로젝트.
실행 중 LLM/Tripo 호출이나 로그인/DB 변경을 하지 않는다.

조작
- 전신 / 얼굴 / 손: 관찰용 카메라. 우클릭 드래그 회전, 휠 확대.
- 대기 / 걷기 / 달리기 / 손 동작 / 팔 뻗기: 제자리 동작 검수.
- 맵 이동: WASD, Shift 달리기, Space 점프, Esc 관찰 복귀.
- 재질 / 무채색: 피부·의상·메시 형태 비교.
- 낮 / 저녁: 조명 변화. 재생 / 정지: 포즈 검수. 위치 초기화.
- 테스트 맵에는 1m 바닥 격자, 2.4m 문틀, 벽, 경사로, 계단이 있다.

에셋 출처와 이번 비용
- 기존 B형 디자인을 기준으로 built-in image_gen으로 정면·측면·후면 이미지를 만들었다.
- Tripo P2-20260801: 정면 이미지 기반 새 몸체, 목표 28,000면, 텍스처 detailed/PBR.
- Tripo 리깅 v1.0-20240301: 피부 웨이트·41개 본 공급.
- 새 생성 손은 근접 변형 품질이 부족했다. 기존 hand-v4 손 메시·UV·웨이트를 새 손목에 맞춰 이식했다.
- 손목을 평면으로 절단하고 웨이트가 이어지는 연결 메시를 추가했다. 피부 색·실루엣의 접합 흔적은 추가 검수 대상이다.
- Blender 4.5.3 LTS: 재질 반응 분리·손 보강·71개 본·대기/걷기/달리기/손/팔 뻗기 키프레임.
- 애니메이션은 Blender의 직접 작성 알고리즘으로 이 리그에 맞춰 새 키를 생성했다. 외부 모션 클립을 입힌 것이 아니다.
- 생성 120 + 리깅 25 = 총 145 Tripo 크레딧. rig-check 0.
- image_gen은 내장 도구를 사용했다. OpenAI API 결제 호출이나 별도 토큰 비용 측정은 하지 않았다.
- World Labs / PixVerse는 이번 캐릭터 제작 테스트에 호출하지 않았다.

주요 파일
- assets/explorer_b_v5.glb: 테스트 맵용 모델, 텍스처·리그·동작 포함.
- ../../art/source/explorer_b_v5.blend: 수정 가능한 제작 원본.
- ../../art/references/explorer_b_v5/: 기준 이미지·생성 프롬프트.
- ../../art/explorer-b-v5-manifest.json: 모델·비용·본·메시 출처.
- ../../artifacts/characters/explorer-b-v5/: 원본 생성 GLB, 비용 기록, Godot 검수 화면 및 로그(로컬 전용).

검증 기준과 현재 한계
Godot에서 모델 임포트, 다섯 클립, 손가락 본 30개, 직접 이동/정지,
벽 충돌 시 정지, 경사로 오르기, 무채색 전환을 검사한다.
이 검사가 아트 품질의 최종 승인을 대신하지 않는다.
첫 테스트 버전이며 손목 접합·어깨/팔꿈치 변형·표정 리깅·동작 연기는 추가 아트 검수가 필요하다.
손가락 본이 있다는 사실을 고품질 손 애니메이션의 완성으로 표현하지 않는다.
경사로 이동과 경사면 발바닥 정렬은 별개다. 발바닥 경사 정렬은 아직 구현하지 않았다.
렌더러는 Forward+ (Vulkan), MSAA 8x, SSAO, 4096 그림자. 이 PC의 RTX 2070에서 확인.
낮은 사양은 --rendering-method gl_compatibility로 실행 가능하지만 결과는 따로 검수해야 한다.

재제작 도구
tools/build_explorer_b_v5.py는 운영자가 보관한 원본 생성/이전 hand-v4 작업 파일을 사용하는 제작 도구다.
이 파일들의 로컬 보관 경로는 일반 게임 빌드에 필요하지 않다.
공유된 Blender 원본에서 직접 수정/재내보내기할 수 있다.
유료 생성 작업은 별도 개발자 도구이며 게임 실행 명령에 포함되지 않는다.

변경 파일과 완료 기준
labs/character_lab/: 독립 Godot 테스트 맵·이동·관찰 UI·GLB.
art/source/explorer_b_v5.blend: 모델·재질·리그·다섯 동작을 수정할 원본.
art/references/explorer_b_v5/: 정면·측면·후면 기준과 프롬프트.
tools/build_explorer_b_v5.py: 로컬 제작/내보내기 도구.
tools/open_character_lab.ps1, Character_Lab.cmd: 실행 도구.
완료 기준: 새 캐릭터가 Godot에서 로드되고 관찰/이동/충돌/경사로/다섯 동작을 검수할 수 있다.
다음 기준: 손목과 주요 관절의 근접 변형 승인, 영상 레퍼런스 기반 동작 개선, 표정 리깅.

2026-10-03 실행 검증: Godot 4.7.2 Forward+에서 --acceptance 종료 코드 0.
클립 5개·본 71개·손가락 본 30개·이동 2.24m·정지 idle·벽 충돌 정지·경사로 높이 0.904m·무채색 전환 통과.
최종 테스트 모델은 32,201 정점 / 29,704 삼각형. 실제 화면 4종을 로컬 artifacts 폴더에 저장했다.
근접 화면에는 손목 색/실루엣의 접합 흔적과 일부 손가락 변형이 보인다. 최종 아트 승인 상태는 아니다.
