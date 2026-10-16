# 인수인계 · 05 몬스터·바디·주인공 (2026-10-16 10:55 KST, 05 세션 작성)

Codex area 형식(04-05-SOUND-BODY의 바디 부분)으로 썼다. 이 파일이 그 area 파일의 바디 내용보다 새롭다.

## 현재 기준과 확인 방법

- 작업 폴더: `D:\lsm26\wt\body` (branch wt/body). 재개 시 `git log --oneline -12`, `git status --short`, `git log --oneline merge-version-gate..HEAD`로 아직 통합되지 않은 커밋을 확인한다.
- 원본·제작 기록: `C:\lsm26\triphthonS1\art\characters\body_p2_v1\` (ledger.json, mon_v3/anim/*, charsel/*). 본 체크아웃이라 커밋하지 않는다(읽기·가공만).

| 커밋 | 내용 | 통합 |
|---|---|---|
| facb47e~4a8bd4d | P2 18종 교체, attack_speed, manifest, 손 도구 4종 | 01 병합(f460dd6d) |
| ec94769, e570274 | 주인공 m1·f1 / m2·f2·f3·m4 | 01 병합(fe456c2). **달리기 결함 있는 옛 파일** |
| 8dc3218 | 주인공 m3·f4 | 01에 요청(09:21) |
| c2ec5dd | 주인공 8명 수정본(리타깃 클립 대신 원본 클립이 들어가던 결함, run=walk×1.7) | 01에 긴급 요청(10:15). 0.11.9 포함 여부는 01 답 확인 |
| 28104c9 | 2범주 날개 5종(하피·임프·가고일·서리 망령·리치) 스폰 연결 | 다음 패치 |
| 638574b | 3범주 지네·미믹·바실리스크·나가 + 키메라·서리 용 자기 모델, 공격 타이밍 수정 | 다음 패치 |
| 08ee4ff | Godot 검사 tests/monster_motion.gd + 결과 문서 motion_check_godot.md | 다음 패치 |
| (이 커밋) | shadow_beast.gd: 공격 배속 유지, 등장 깜빡임 제거, 큰 몸 쓰러짐 가라앉기 | 다음 패치 |

git 밖 GLB: `game/assets/monsters/<id>_<map>.glb` 29종(원본 `mon_v3/anim/game/<id>.glb`), `game/assets/npc/boni.glb, sol.glb`. 병합 때 복사 + Godot import 필요.

## 지켜야 할 결정 (다시 묻지 않음)

- 몬스터: 원본 메시 변형 금지, 몸 동작만, 종마다 따로 만든 동작(공용 템플릿 금지), 공중형은 떠다님.
- 2/3범주 11종 A안 한도 1,000(사용자 05 세션 직접 "몬스터 11종 A안 1,000 승인." 07:52). **사용 930**.
- 주인공 8명 한도 1,200(05 세션 직접 "캐릭터 8명 모두, 1,200 승인." 07:52). **사용 1,040**(P2 100+텍스처 10+리그 20 ×8). 동작은 리타깃(0크레딧).
- 서리 용 색 B1(진한 빙하 청록). 07 영상도 같은 색.
- 이 승인들은 05 세션 안의 사실이다. 다른 세션·Codex의 추가 지출 권한이 아니다.

## 완료 사실

- 몬스터 29종 게임 GLB 완성: 1범주 18(AI 동작 6개씩) + 보스 키메라·서리 용(절차 동작) + 날개 5(AI+부유) + 지네·미믹·바실리스크·나가(절차 동작). 종별 시트·GIF: `mon_v3/anim/sheets/`.
- 주인공 8명: Tripo P2(내 4방향 그림) → 텍스처 → Mixamo 리그 → `tools/body_gen/retarget_player.py`(게임 뼈 이름, explorer.glb 동작 리타깃) → `part_split.py`(hair/skin/coat/pants/boots/detail__hex 색 바꾸기 재질). 확인 그림 `heroes_pose_check.jpg`, N6 수치 검사로 쪼그림 해결 확인.
- 손 도구 4종(곡괭이·빗자루·우산·등불) `game/assets/tools/`.
- 서버 시험 test_stages + test_monsters 78 통과(638574b).

## Godot 실측 결과 (08ee4ff 기준, 29종 FAIL → 원인과 조치)

1. 공격 배속이 매 프레임 1.0으로 덮어써짐 → shadow_beast.gd에서 attack_rate 유지로 수정(이 커밋). 재검사 결과는 아래 "재검사".
2. 등장 때 '맞음' 처리(last_hp 45 기본값) → -1로 시작하게 수정(이 커밋).
3. 서리 용·트렌트가 다 가라앉기 전에 사라짐 → 가라앉는 깊이를 몸 높이에 비례(이 커밋).
4. **발 미끄러짐(22종)**: 제자리 걷기 클립 + 키 기반 WALK_REF 추정이라 발이 미끄러진다. 걷기 때 발을 거의 안 드는 6종(늑대인간·얼음 조각병·드라우그·서리 기사·왕지네·리자드맨)이 특히 심하다. → 다음 할 일 1.
5. 자세 튐: 공격 중 빠른 손끝(16종), 피격 0.05초 블렌드(21종), 쓰러짐 블렌드 → 다음 할 일 2.
6. 경고: 서리 마녀·나가가 0.3 m 떠 있음(stand_in wisp의 HOVER 0.3) → 다음 할 일 3.

### 재검사 (이 커밋, 8종 175초)

- 공격 배속이 의도대로 적용됨(clip x = meant x). 고블린 타격 −0.05초 통과.
- 등장 깜빡임 사라짐(고블린·하피 실패 목록에서 빠짐). 서리 용 top −0.13 m, 트렌트 −1.24 m로 땅속에서 사라짐.
- 남은 attack_timing 실패는 검사기가 '가장 빠른 뼈의 순간'을 타격으로 본다(팔 드는 순간이 더 빠르면 0.1~0.5초에 잡힘). 빌드의 impact(첫 일격이 멈추는 순간)와 정의가 달라서, 다음 할 일 0에서 기준을 맞춘다. 빙하 거인 −0.13, 서리 용 −0.23처럼 가까운 종도 있다.
- 남은 실패: 발 미끄러짐(대부분), 큰 몸 자세 튐(예티·얼음 골렘·트렌트·빙하 거인).

## 다음 할 일 (순서)

0. **타격 기준 맞추기**: monster_motion.gd의 타격 측정을 build_game_monster의 impact 정의(전방·하방 속도 점수의 첫 일격 끝)와 같게 바꾸거나, 보고서 attack_impact_seconds를 그대로 비교한다.

1. **발 미끄러짐**: 종별로 걷기 클립의 실제 보폭을 재서 WALK_REF/RUN_REF를 맞춘다(발 뼈가 디딘 동안 뒤로 가는 거리 ÷ 시간, build_game_monster의 ground_speed는 제자리 클립에서 0이라 새 측정 필요). 발을 거의 안 드는 6종은 걷기 동작 재생성(유료, 실행 세션 승인 필요) 또는 Blender 발 고정(무료)을 제안.
2. **튐 완화**: 피격 블렌드 0.05→0.12, 쓰러짐 0.08→0.15 적용함(쓰러짐 튐 늑대인간 4→2, 얼음 조각병 3→0, 트롤 대기~멈춤 15→12). 남은 튐은 대부분 공격 중 빠른 손끝(실제로 빠른 동작)이라, 검사기의 큰 몸 POSE_POP 기준과 함께 다시 본다. 빠른 회전 남은 것(리자드맨 idle/death 38°, 임프 attack 38°, 서리 망령 death 32°)은 build의 destep_deg/despike로 다듬기.
3. ~~부유 오검출~~ 해결(e 커밋): 대역 wisp의 0.3 m 부유를 자기 모델에는 적용하지 않음. 서리 마녀 바닥 0.045 m, 나가 0.13 m, 하피는 GLB 부유 0.9 m만.
4. 절차 동작 다듬기: 바실리스크·키메라 쓰러짐 중간 0.17H 뜸, 미믹 쓰러짐 다리가 뚜껑 앞을 가림, 나가 턱 없음, 용 송곳니 일부가 아래턱과 같이 움직임.
5. 주인공: f4 줄무늬 상의는 남색 줄만 색이 바뀜(그림 특성). 모자(f4)·헤어밴드(m3) 같은 장식은 detail로 남는다. 03 카드·프리셋 기본색은 `charsel/game/<id>_parts.json`의 hex.
6. 텍스처 줄이기(codex/texdiet d321dc2, tools/tex_diet/apply_import_limits.py): 새 캐릭터 8명·몬스터 29종 포함해 dry run 뒤 적용.
7. 다시 검사: `tests/monster_motion.gd`(29종 약 10분), stage_smoke, combat_play.

## 실행 예시

```powershell
powershell -ExecutionPolicy Bypass -File D:\lsm26\locks\wait_heavy.ps1 -Owner 05
D:\lsm26\wt\body\.tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://tests/monster_motion.gd -- --fps=144 [--species=goblin,yeti]
# 몬스터 GLB 다시 만들기 (본 체크아웃 tools/body_gen 기준)
blender -b --factory-startup -P tools/body_gen/build_game_monster.py -- <src fbx> <out.glb> <game_build.json|game_build_flyers.json> <id> <report.json>
# 주인공 다시 만들기
blender -b --factory-startup -P tools/body_gen/retarget_player.py -- <tripo rig fbx> <out_rt.glb>
blender -b --factory-startup -P tools/body_gen/part_split.py -- <out_rt.glb> <out.glb> <parts.json> [hair band, f4: 0.05,0.45]
```

## 경계

- Tripo 유료 작업은 실행 세션에서 사용자 직접 승인 필요. 결제 클릭 요령은 메모리 `tripo-studio-flows`.
- .import 줄바꿈 잡음·무관 .uid·artifacts 로그는 커밋하지 않는다. GLB는 git 밖(몬스터) / git 안(주인공 game/assets/m*.glb, 손 도구).
- 다른 세션 소유 파일(main.gd, player.gd 등)은 고치지 않고 요청한다.
