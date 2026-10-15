# 04 사운드 인수인계 (2026-10-16 05:35)

## 끝난 것 (merge-version-gate·dev에 들어감)
- 효과음 다양화: 녹음본 323→2,773개, 섞어 뽑기 재생, 소리 없던 동작 약 100곳 연결(docs/sound/README_KO.md). GitHub dev af9598f.
- 발밑 표면 신호 `world_audio.stepped`, 문 소리 `door_audio.gd`(docs/sound/HOOKS_KO.md). N4가 발밑 이펙트에 이미 연결(foot_fx.gd). N3에는 사용법을 보냄.
- 원정 몬스터 29종 고유 소리(717개, 보스 포효·등장음). 01이 병합(edf87cb).
- 트레일러 v3 오디오 8개 → D:\lsm26\trailer_media\audio\ (07에 전달함). 다시 만들 때는 `tools/sfx/make_trailer_audio.py [파일이름]`을 씁니다.

## 병합 요청함 (09:00, 01에, 브랜치 wt/sounddev beadd6ff, 작업 폴더 D:\lsm26\wt\monstersfx)
- dev 기능 효과음 12종 52개 + combat_audio EVENTS buff_* + 연결표 docs/sound/DEV_FEATURE_SFX_KO.md (a0238913까지 테스트 통과: compile_all, sfx_bank·audio_bank·life_sound·monster_voice·sound_hooks).
- beadd6ff: 방에서 만든 물건 클릭 소리(studio.gd use_cue). interaction_check의 "placed in the village" 실패는 변경 전에도 똑같이 남(기존 문제).

## 남은 일
1. 기능 쪽 소리 호출: N4(농사·모닥불 버프), 06(상점·이사·게시판·편지)에 호출 목록을 보냈습니다. 그쪽 브랜치가 dev에 들어온 뒤 실제로 소리가 나는지 확인합니다.
2. 모닥불 결계를 없애면 main.gd survival_audio의 ward 신호음을 정리합니다(N4에 알림).
3. 몬스터 교체본(wt/body)이 병합되면 탐험 녹화로 보스 포효 음량과 리자드맨·바실리스크의 쉭쉭 소리를 확인합니다.
4. 병합이 끝나면 D:\lsm26\wt\monstersfx를 rm_wt.ps1로 지웁니다(정션 먼저 끊기). soundhooks는 이미 지웠습니다.

## 규칙 메모
- Godot 무거운 작업은 `wait_heavy.ps1`(heavy-ok일 때만) 뒤에 하고, PC 전체에서 동시에 2개까지입니다.
- project.godot·patch_boot.gd·default_bus_layout.tres는 고치지 않습니다.
- 생성기는 `SFX_BASE=merge-version-gate`로 실행해 원본을 보호합니다.
- Godot import가 가끔 비정상 종료(-1073741819)합니다. 다시 돌리면 됩니다.
