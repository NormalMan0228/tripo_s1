# 영상 기반 B형 탐험가 애니메이션

Seedance 2.0, PixVerse V6, Kling V3의 기존 5초 영상을 각각 추적하여 만든 별도 Godot 검수 프로젝트입니다. Tripo 프리셋 동작을 재사용한 결과가 아닙니다. 제작 중 유료 생성 API를 새로 호출하지 않았습니다.

## 실행

저장소 루트의 `Video_Motion_Lab.cmd`를 실행합니다. 옆면·정면·뒷면, 타임라인, 재생, 전체/반복 전환을 제공합니다. 기존 `game` 프로젝트의 캐릭터를 교체하지 않습니다.

`assets/explorer_video_motions.glb`에 같은 41본 리그·연속된 몸체·텍스처·아래 여섯 클립이 들어 있습니다. Godot의 이름 접미사 자동 해석은 꺼 두었습니다. `_loop` 이름을 자동 제거하지 않도록 유지하십시오. 전방은 +X, 검수 크기는 1.7배입니다.

| 영상 | 전체 클립 | 반복 클립 | 반복 길이 |
| --- | --- | --- | --- |
| Seedance | seedance2_sequence | seedance2_loop | 0.783333초 |
| PixVerse | pixverse6_sequence | pixverse6_loop | 1.500000초 |
| Kling | kling3_sequence | kling3_loop | 1.283333초 |

전체 클립은 각각 5초·60fps이며 일회성 동작입니다. 반복 클립은 원본 구간에서 추출하고 연결점을 보정했습니다. 실제 이동은 캐릭터 컨트롤러가 처리해야 합니다. 단일 옆모습에서 추정한 접지 속도는 제작 명세에 있으며, 그대로 상용 게임 이동 속도의 정답으로 쓰지 마십시오.

## 제작 및 재현

로컬 MediaPipe Heavy → 관절 채널 필터링 → Blender FK·관절 한계·발바닥 보정 → 60fps 키프레임 → GLB → Godot 검수 순서입니다. 손가락 개별 움직임과 얼굴 표정은 추출하지 않았습니다. 가려진 관절과 깊이는 추정·수작업 규칙을 포함합니다.

관련 도구는 `tools/track_reference_motion.py`, `tools/clean_reference_motion.py`, `tools/build_video_reference_animations.py`, `tools/audit_video_animations.py`입니다. Python 의존성은 `tools/video_motion_requirements.txt`에 고정했습니다. 입력 영상·추적 JSON·Blender 제작 원본·검증 기록은 `artifacts/video-motion-20261003`에 저장되며 아티팩트 폴더는 Git에 포함되지 않습니다.

```powershell
.tools/blender-portable/blender-4.5.3-windows-x64/blender.exe --background --python tools/audit_video_animations.py
.tools/godot/Godot_v4.7.2-stable_win64_console.exe --headless --path labs/video_motion_lab --script res://acceptance.gd
```

완료 기준: 여섯 클립 존재, 세 전체 클립의 서로 다른 키프레임, 수평 루트 변위 없음, 루프 연결점 일치, 30·60fps 전환, GLB 재수입 후 실제 스킨 표면 접지 및 Godot 화면 검수. 발 미끄러짐·손/옷 관통·3D 깊이 정확도의 완전한 보장은 이 검사 범위가 아닙니다.
