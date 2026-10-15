# 인수인계 · 05 몬스터·바디 애니 (2026-10-16)

## 어디에 무엇이 있나

| 무엇 | 위치 |
|---|---|
| 작업 브랜치 | `wt/body` (`D:\lsm26\wt\body`, merge-version-gate 3526ae5 기준). 0.11.8 뒤 dev 병합 대기열(01) |
| 게임 GLB 20개 (git 제외) | `C:\lsm26\triphthonS1\art\characters\body_p2_v1\mon_v3\anim\game\<id>.glb` → 게임 이름 `game/assets/monsters/<id>_<map>.glb` |
| NPC GLB (git 제외) | `...\anim\game\boni.glb`, `sol.glb` → `game/assets/npc/boni.glb`, `sol.glb` (첫 클립 idle) |
| 원본 FBX(동작 포함) | `...\anim\src\<id>\mon_<id>_anim.fbx` + `.fbm` 텍스처 폴더 |
| 확인 그림 | `...\anim\sheets\<id>_clips.png / .gif` |
| 빌드 설정 | `art/characters/body_p2_v1/mon_v3/anim/game_build.json` (키, 클립 이름 매칭 54자 이하, 반복, 정리, 발광, 부유) |
| 동작 프롬프트 | `.../anim/motion_prompts.json`, `npc_motion_prompts.json` |
| 크레딧 기록 | `art/characters/body_p2_v1/ledger.json` → `monsters_v3_anim` |

## 다시 만들기

- zip 하나 → GLB·시트·GIF: `python tools/body_gen/process_anim_zip.py <id> <export.zip>` (BODY_SCRATCH에 임시 폴더)
- 빠진 동작 확인: `python tools/body_gen/check_anim_zip.py <id> <zip>`
- 빌드만: `blender -b --factory-startup -P tools/body_gen/build_game_monster.py -- <fbx> <out.glb> <game_build.json> <id> [report.json]`
- 전체 그림·표: `roster_sheet.py`, `report_table.py`, manifest 기록: `write_manifest_v3.py <manifest.json> <glb 폴더>`

## 게임에 넣기 (dev, 0.11.8 뒤)

1. wt/body 병합: `server/catalog.py`(ROSTERS), `server/tests/test_stages.py`, `game/scripts/monster.gd`(WALK_REF/RUN_REF), `game/tests/stage_smoke.gd`
2. 빌드 체크아웃의 `game/assets/monsters/`에 GLB 20개 복사, `game/assets/npc/`에 boni·sol 복사, Godot 가져오기
3. 시험: server tests, stage_smoke, combat_play

## 사용자 결정 대기 (총괄 목록)

- 남은 11종 크레딧: `cat23_credit_plan.png` (A 한도 1,000 추천 / B 350 / C 보류)
- 서리 용 서리색 정면: `frost_dragon_front_candidates.png` (B1 추천), 원본 `mon_v3/fronts/frost_dragon/`
- 승인 뒤 준비된 것: 날개·떠다님 5종 AI 동작 프롬프트(워크플로 결과, `anim/flyer_motion_prompts.json`), 빌드 `hover` 옵션, 네 발 절차 동작은 `tools/blender_build_monster.py`(예전 네 발 몬스터용) 재사용

## 주의

- Tripo AI 동작 목록은 계정 전체 공유입니다. animate 페이지를 여러 개 열면 끝난 동작이 모든 페이지 모델에 붙고, 자기 동작이 빠질 수 있습니다.
  - 내보낸 뒤 반드시 `check_anim_zip`으로 확인하고, 빠진 것은 카드를 눌러 다시 적용합니다(무료).
- 숨은 탭에서는 페이지 타이머가 느려집니다. 대기열은 확인할 때마다 한 단계씩(`__step`) 진행합니다.
- Blender 동작 이름은 63바이트까지라, 클립 매칭 문구는 프롬프트 앞 54자 이하여야 합니다.
