# 04 사운드 인수인계 (2026-10-16 05:35)

## 끝난 것 (merge-version-gate·dev에 들어감)
- 효과음 다양화: 녹음본 323→2,773개, 섞어 뽑기 재생, 소리 없던 동작 약 100곳 연결(docs/sound/README_KO.md). GitHub dev af9598f.
- 발밑 표면 신호 `world_audio.stepped`, 문 소리 `door_audio.gd`(docs/sound/HOOKS_KO.md). N4가 발밑 이펙트에 이미 연결(foot_fx.gd). N3에는 사용법을 보냄.
- 원정 몬스터 29종 고유 소리(717개, 보스 포효·등장음). 01이 병합(edf87cb).
- 트레일러 v3 오디오 8개 → D:\lsm26\trailer_media\audio\ (07에 전달함). 만든 스크립트는 세션 스크래치패드의 trailer\make_trailer_audio.py입니다. 다시 만들려면 이 문서 사본을 보고 재작성합니다.

## 진행 중 (브랜치 wt/sounddev, 작업 폴더 D:\lsm26\wt\monstersfx)
- 7a51859 WIP: dev 기능 효과음 12종 52개(농사 새싹·익음·밭 되돌리기, 상점 계산대, 이사 집 등장·입주·퇴거, 게시판 핀, 편지 보내기, 모닥불 따뜻함·회복·끝) + combat_audio EVENTS에 buff_* 추가 + 연결표 docs/sound/DEV_FEATURE_SFX_KO.md.
- 임포트 완료, sfx_qa 통과.
- **남은 일:**
  1. 06:40 뒤(01 예약 끝) `wait_heavy.ps1` 확인 후 sfx_bank_check·audio_bank_check·life_sound_check·monster_voice_check·compile_all 실행
  2. 통과하면 01에 병합 요청(0.11.8 배포 뒤 dev)
  3. 각 기능이 dev에 들어오면 연결표대로 소리 연결(농사 N4, 상점 03·06, 이사·게시판 06, 모닥불 버프 N5). 모닥불 결계를 없앨 때 main.gd의 ward 신호음도 정리
  4. 몬스터 29종 게임 안 녹화(tests/sound_variety_capture.gd 방식, BenQ 화면)로 보스 포효 음량과 쉭쉭 소리 확인

## 정리할 것
- 작업 폴더 D:\lsm26\wt\soundhooks(병합 끝)는 06:00 뒤 rm_wt.ps1로 지웁니다(정션 먼저 끊기). 세션당 작업 폴더는 1개만 씁니다.

## 규칙 메모
- Godot 무거운 작업은 `wait_heavy.ps1`(heavy-ok일 때만) 뒤에 하고, PC 전체에서 동시에 2개까지입니다.
- project.godot·patch_boot.gd·default_bus_layout.tres는 고치지 않습니다.
- 생성기는 `SFX_BASE=merge-version-gate`로 실행해 원본을 보호합니다.
- Godot import가 가끔 비정상 종료(-1073741819)합니다. 다시 돌리면 됩니다.
