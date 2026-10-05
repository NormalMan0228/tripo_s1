"""Export a factual local report and reusable sources. Never serves provider keys."""
from pathlib import Path
import json, shutil, subprocess, html, zipfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/detail-map-20261003'
REVIEW=ROOT/'artifacts/production-lab-20261003/review';MEDIA=REVIEW/'art-slice';MEDIA.mkdir(exist_ok=True)
FFMPEG=ROOT/'.tools/art-venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'
budget=json.loads((OUT/'budget.json').read_text());map_data=json.loads((OUT/'map-manifest.json').read_text());play=json.loads((OUT/'playtest/playtest.json').read_text());hand=json.loads((OUT/'character/hand-godot-audit.json').read_text());tools=json.loads((OUT/'installed-tools.json').read_text())
if not all(play[k] for k in ['bridge_crossed','building_entry','building_return','house_wall_blocks','interaction_counters']):raise SystemExit('Map acceptance failed')
if play['max_continuous_step_m']>.11 or play['camera_rotation_delta_rad']>.0001:raise SystemExit('Motion acceptance failed')
def encode(src,out,frames):
 subprocess.run([str(FFMPEG),'-hide_banner','-loglevel','error','-y','-framerate','30','-i',str(src/'frame-%04d.jpg'),'-frames:v',str(frames),'-an','-vf','scale=1280:-2:in_range=auto:out_range=tv,format=yuv420p','-color_range','tv','-c:v','libx264','-profile:v','baseline','-crf','20','-movflags','+faststart',str(out)],check=True)
continuous_frames=play.get('video_continuous_frames',0)
if continuous_frames<1:raise SystemExit('Run --audit --capture --record before exporting the walkthrough')
encode(OUT/'playtest/map-frames',OUT/'playtest/village-walkthrough.mp4',continuous_frames)
for directory in [OUT/'playtest',OUT/'character']:
 for file in directory.iterdir():
  if file.is_file() and file.suffix in ['.png','.mp4','.json']:shutil.copy2(file,MEDIA/file.name)
for file in [OUT/'budget.json',OUT/'map-manifest.json',OUT/'installed-tools.json']:shutil.copy2(file,MEDIA/file.name)
kit=ROOT/'art/village_kit';kit.mkdir(exist_ok=True)
for file in (OUT/'modules').glob('*.glb'):shutil.copy2(file,kit/file.name)
totals={name:{'tripo':sum(t.get('credits_consumed',0) for t in b['tasks'].values()),'scenario':sum(t.get('actual_cu',t.get('quoted_cu',0)) for t in b['scenario'])} for name,b in budget['buckets'].items()}
rows=[]
for bucket,b in budget['buckets'].items():
 for name,t in b['tasks'].items():
  request=json.loads((OUT/f'tripo/{bucket}/{name}/request.json').read_text())
  rows.append(f"<tr><td>{html.escape(bucket)}</td><td>{html.escape(name)}</td><td>{html.escape(request['model'])}</td><td>{request.get('face_limit','—')}</td><td>{t['credits_consumed']:g}</td></tr>")
doc=f'''# Tripothon 제작 도구·세부 파트·테스트 마을 — 2026-10-03

## 완료한 결과

- Godot 4.7.2 테스트 마을: 광장, 생성한 건물 3개 인스턴스, 장터, 우물, 개울, 다리, 과수원, 텃밭, 집 내부. 기존 B형 탐험가와 해루를 사용합니다.
- WASD 이동, Shift 달리기, E 상호작용·집 출입. 건물 전환에는 짧은 페이드를 적용했습니다. F3에서 개발 정보가 열립니다.
- 개발용 독립 손 부품: Scenario 이미지 → Tripo P2 → 로컬 MediaPipe 21점 → Blender 깊이 추정·16본·스킨 가중치 정리 → GLB → Godot 동작 검사.
- 재사용할 수 있는 독립 머리카락, 87개 몸체 분할 결과, 얼굴·손 Rigify 메타리그를 보존했습니다.
- Krita 5.3.4와 Material Maker 1.7 공식 포터블 배포본을 설치했습니다.

## 실행

프로젝트 루트의 `Village_Art_Lab.cmd`를 실행하면 마을이 열립니다. `Detail_Parts_Lab.cmd`는 손 동작·머리카락·분할 결과를 확인하는 개발 도구입니다. `Art_Tools.cmd`에서 Krita·Material Maker·Blender 원본을 열 수 있습니다.

Godot 편집기에서 `labs/village_art_lab/project.godot`를 가져오고 F6/F5로 실행할 수도 있습니다. 자체 검사: `.tools/godot/Godot_v4.7.2-stable_win64_console.exe --path labs/village_art_lab -- --audit --capture`.

## 설치·자동화 검증 범위

| 도구 | 상태 | 검증한 일 |
|---|---|---|
| Blender 4.5.3 LTS | 기존 설치 사용 | 마을·내부·모듈 GLB 제작, 손 리깅과 가중치 수정, Rigify 메타리그 생성 |
| Krita 5.3.4 | 공식 ZIP 설치 | ORA → KRA 변환, KRA 내부 페인트 레이어 2개 확인, PNG 내보내기. 실제 내보낸 목재 텍스처를 Blender·GLB에 사용 |
| Material Maker 1.7 | 공식 ZIP 설치, 공식 릴리스 SHA256 일치 | 실행과 편집용 PBR 그래프 준비. CLI 일괄 내보내기는 결과 파일이 생성되지 않아 미검증으로 남김 |
| Substance 3D Painter | 미설치 | Adobe 라이선스 답변이 아직 없어 구매·체험 구독을 진행하지 않음 |
| Pinokio | 제어 연결 불가 | C:/pinokio는 확인했으나 pterm과 localhost 제어 API가 응답하지 않음. 공식 포터블 배포본으로 진행 |
| MediaPipe Hand Landmarker | 공식 모델 설치 | 가상 손 이미지에서 21점 검출. 모델은 한 손의 좌우를 Right로 판정했으므로 Left 프롬프트만으로 좌우를 확정하지 않음 |

현재 이 세션은 데스크톱 앱의 마우스·붓 제어를 지원하지 않습니다. Blender 스크립트와 Krita 파일 변환을 실행했으며, 직접 붓질했다고 주장하지 않습니다. 수작업을 이어갈 수 있도록 `.blend`, `.kra`, `.ora`, `.ptex`를 남겼습니다. Material Maker는 Substance Painter의 모든 기능을 대체하는 것으로 검증되지 않았습니다.

## 비용 — 서로 분리한 예산

| 분류 | Scenario 사용 / 한도 | Tripo 사용 / 한도 |
|---|---:|---:|
| 캐릭터 세부 실험 | {totals['character_detail']['scenario']:g} / 1000 CU | {totals['character_detail']['tripo']:g} / 2000 크레딧 |
| 마을 맵 | {totals['village_map']['scenario']:g} / 1000 CU | {totals['village_map']['tripo']:g} / 2000 크레딧 |

Tripo 시작 잔액 23110, 이 작업의 확인된 소비 760, 완료된 요청들의 마지막 잔액 22350입니다. 개별 작업의 `credits_consumed`를 합산했으며 동시 요청의 계정 잔액 차이를 각 작업 비용으로 간주하지 않았습니다. Scenario는 UI에서 확인한 개별 결과 비용입니다. 결제·자동 충전·구독 변경은 하지 않았습니다.

Tripo 생성 6회는 P2-20260801, 텍스처·PBR 켜짐, detailed 품질이며 각각 실제 120크레딧이 기록됐습니다. 이 실험은 정가 보장이 아닙니다. 분할은 v2.0-20260430, detailed, split_by_connectivity=true, 실제 40크레딧입니다. 개발자 에셋 생성만 사용했고 플레이어용 생성 서비스는 호출하지 않았습니다. 키는 읽기 전용으로 서버 환경에서만 사용했으며 결과물에 포함하지 않았습니다.

Scenario 모델은 GPT Image 2 (`model_openai-gpt-image-2`), Quality Auto, Background Auto, 각 1장입니다. 머리카락 12 CU / 1122×1402, 열린 손 11 CU / 1254×1254, 건물 11 CU / 1380×1140. 이 결과의 생성은 Scenario 이미지 서비스이며 별도 GPT API 호출이나 effort 설정을 사용하지 않았습니다.

## 품질 검증

- 마을 이동, 다리 통과, 건물 충돌, 집 진입·복귀, 수확·사과·낚시 카운터 검사 통과.
- 카메라 방향 변화 {play['camera_rotation_delta_rad']:g}rad. 실제 연속 이동의 최대 물리 프레임 변위 {play['max_continuous_step_m']:.3f}m. 의도된 건물 전환은 별도로 제외. 걷기 2.8m/s, 달리기 4.5m/s, 정지 후 속도 {play['stop_speed_m_s']:g}m/s.
- 독립 손 Godot 리깅 {hand['bones']}본, 가져온 동작 길이 {hand['clip_seconds']:.3f}초, 반복 시작·끝 최대 회전 차이 {hand['loop_endpoint_max_gap_deg']:g}°. Blender 작성 구간은 2.4초이며 가져온 리소스의 길이는 별도로 측정했습니다.
- 손 동작은 Blender에서 만들었습니다. 이 실험에서 Tripo 애니메이션 API는 쓰지 않았습니다.
- 텍스트만으로 만든 첫 손은 형태가 부자연스러워 채택하지 않았습니다. 열린 손은 이미지 입력으로 개선했고, 초기 엄지 변형 문제는 공유 정점 병합과 스무딩·정규화로 줄였습니다.
- 게임의 기존 주인공 메시·얼굴·걷기 동작은 교체하지 않았습니다. 새 손은 몸체 맞춤 전의 독립 실험이며 전체 주인공의 손 애니메이션 완성으로 간주하지 않습니다.
- 분할 87조각은 의미 단위와 다릅니다. 의상 교체 전에 조각 묶음, 단면 완성, 경계·웨이트 검사가 필요합니다.
- Rigify 얼굴 메타리그를 생성했지만 주인공 얼굴에 바인딩하거나 표정 동작을 완성하지 않았습니다. 기존 얼굴은 유지합니다.
- 마을은 별도 아트 테스트 프로젝트입니다. 수확·낚시는 로컬 상호작용 검사이며 완전한 농사/낚시 시스템·서버 보상·경제 저장은 연결하지 않았습니다. 기존 온라인 서버와 본 게임에는 이 맵을 배포하지 않았습니다.

## 재사용 원본과 다음 순서

`art/source/village_art_20261003.blend`, `cottage_interior_20261003.blend`, `open_hand_rigged_20261003.blend`, `explorer_detail_rig_template.blend`가 편집 원본입니다. `art/village_kit/`에는 바닥 중심이 원점인 생성 소품과 직접 만든 집·다리·사과나무·입구 모듈이 있습니다. 각 모듈은 개별 GLB입니다. 한 마을 GLB는 {map_data['batched_meshes']}개 메시로 묶었고 약 {map_data['triangles']:,}삼각형입니다.

다음에는 주인공의 얼굴 토폴로지·눈꺼풀·입 안을 정의하고, 새 머리카락·손의 맞춤 치수를 고정한 뒤 원본 메시를 수정합니다. 표정과 손 동작은 독립 검사 → 몸체 결합 → 걷기/달리기 중 변형 검사 순서로 진행합니다. 맵은 현재 시료를 아트 검토한 뒤 본 게임과 서버의 상호작용/저장 계약에 연결하는 것이 다음 단계입니다.

## 공식 자료

- [Krita 다운로드](https://krita.org/en/download/) · [CLI 파일 변환](https://docs.krita.org/en/reference_manual/linux_command_line.html)
- [Material Maker 공식 릴리스](https://github.com/RodZill4/material-maker/releases/tag/1.7) · [기능 설명](https://rodzilla.itch.io/material-maker)
- [Substance Painter 공식 페이지](https://www.adobe.com/products/substance3d/apps/painter.html)
- [Blender Rigify](https://docs.blender.org/manual/en/latest/addons/rigging/rigify/introduction.html)
- [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python)
- [Tripo 공식 문서](https://platform.tripo3d.ai/docs)
'''
doc=doc.replace('키는 읽기 전용으로 서버 환경에서만 사용했으며 결과물에 포함하지 않았습니다.', '키는 개발자 로컬 프로세스에서만 읽었으며 게임 클라이언트와 결과물에 포함하지 않았습니다.')
(ROOT/'docs/ART_TOOLS_AND_VILLAGE_20261003.md').write_text(doc,encoding='utf-8');(MEDIA/'ART_TOOLS_AND_VILLAGE_20261003.md').write_text(doc,encoding='utf-8')
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tripothon · 제작 도구와 실제 아트 시료</title><style>
:root{color-scheme:light;--ink:#26473c;--muted:#64756a;--paper:#f6f1e7;--line:#dedfd3}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Malgun Gothic",system-ui,sans-serif;line-height:1.7}main{max-width:1200px;margin:auto;padding:40px 28px 90px}nav{display:flex;gap:22px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:20px}a{color:#2e6b55}header{padding:40px 0 28px}h1{font-size:42px;line-height:1.25;letter-spacing:-1.4px;margin:10px 0}h2{font-size:27px;margin-top:58px}h3{font-size:20px;margin:0 0 10px}p{color:var(--muted)}.tag{font-size:13px;letter-spacing:2px;color:#a77b38}.hero{width:100%;border-radius:22px;background:#dde8df}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.card{background:#fffcf5;border:1px solid var(--line);padding:22px;border-radius:18px}.card img,.card video{width:100%;border-radius:12px;background:#dce6df}.full{margin:20px 0;width:100%;border-radius:16px}table{border-collapse:collapse;width:100%;background:#fffaf0}th,td{padding:12px 15px;text-align:left;border-bottom:1px solid var(--line)}th{background:#e7ecdf}code{background:#e6ecdf;padding:3px 7px;border-radius:5px}.note{border-left:4px solid #b59456;padding:14px 20px;background:#efe8d8;border-radius:8px;margin:20px 0}.ok{color:#287350}.scroll{overflow-x:auto}.flow{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.flow span{background:#e4eadb;padding:12px 16px;border-radius:12px}small{color:var(--muted)}@media(max-width:800px){.grid{grid-template-columns:1fr}h1{font-size:32px}main{padding:24px 16px}.card{padding:16px}}</style><main><nav><a href="#map">실제 마을</a><a href="#hand">세부 파트 실험</a><a href="#tools">설치 도구</a><a href="#cost">비용·명세</a><a href="art-slice/ART_TOOLS_AND_VILLAGE_20261003.md">문서 저장본</a></nav><header><div class="tag">TRIPOTHON · ART SLICE · 2026.10.03</div><h1>편집할 수 있는 원본,<br>걸어 다닐 수 있는 마을.</h1><p>공식 도구 설치 → 생성 파트 검사 → 편집 원본 보존 → Godot 플레이 검증까지.<br>아래 이미지는 이번에 제작한 실제 에셋과 게임 렌더링입니다.</p></header><img class="hero" src="art-slice/village-overview.png" alt="실제 Godot 테스트 마을 전체 구조"><h2 id="map">01 · 실제 Godot 테스트 마을</h2><p>광장·장터·개울과 다리·과수원·텃밭·집 내부. B형 탐험가와 해루 NPC를 적용했습니다.</p><video class="full" controls playsinline muted preload="metadata" poster="art-slice/village-start.png" src="art-slice/village-walkthrough.mp4"></video><div class="grid"><article class="card"><h3>광장과 장터</h3><img src="art-slice/village-start.png" alt="마을 광장 플레이 화면"><p>고정된 카메라 방향, 이동 속도에 맞춘 걷기·달리기, 가까운 물건에 맞춰 바뀌는 E 안내.</p></article><article class="card"><h3>강 너머로 이어지는 공간</h3><img src="art-slice/village-square.png" alt="개울·다리·해루"><p>다리 통과와 강변 충돌을 검사했습니다. 기존 해루 모델의 낚시 동작과 대화를 적용했습니다.</p></article><article class="card"><h3>집 안으로 들어가기</h3><img src="art-slice/cottage-interior.png" alt="집 내부"><p>짧은 페이드로 공간을 전환합니다. 별도 내부와 출구, 마을로 돌아오는 동작을 검사했습니다.</p></article><article class="card"><h3>검증한 범위</h3><p class="ok">이동 · 다리 · 벽 충돌 · 집 출입·복귀 · 로컬 상호작용 통과</p><p>카메라 방향 변화 0rad<br>연속 이동 최대 물리 프레임 변위 0.075m<br>걷기 2.8m/s · 달리기 4.5m/s</p><p><code>Village_Art_Lab.cmd</code>로 실행합니다. WASD·Shift·E, F3은 개발 정보입니다.</p><small>본 게임과 온라인 서버에 배포하기 전의 별도 아트 시료입니다. 농사·낚시는 로컬 상호작용 시험이며 서버 경제에 반영하지 않습니다.</small></article></div><h2 id="hand">02 · 생성 부품에서 실제 손 동작까지</h2><div class="flow"><span>Scenario 정면 이미지</span>→<span>Tripo P2 메시·PBR</span>→<span>로컬 21점 추적</span>→<span>Blender 깊이·16본·웨이트</span>→<span>Godot GLB 동작</span></div><p>텍스트만으로 만든 첫 손은 형태가 부자연스러워 제외했습니다. 다섯 손가락이 선명한 이미지로 다시 생성했고, 엄지 주변의 초기 웨이트 문제를 보정했습니다.</p><div class="grid"><article class="card"><h3>실제 Godot 손 동작</h3><video controls playsinline muted preload="metadata" poster="art-slice/hand-godot.png" src="art-slice/hand-godot-motion.mp4"></video><p>16본 · 가져온 길이 2.433초 · 반복 시작/끝 자세 차이 0°.<br>동작은 Blender에서 만들었습니다.</p><a href="art-slice/open_hand_rigged.glb" download>리깅·동작 포함 GLB</a></article><article class="card"><h3>웨이트 보정 후 쥐는 자세</h3><img src="art-slice/open-hand-rig-grasp.png" alt="보정한 독립 손 쥐기"><p>공유 정점 병합, 스무딩 18회, 가중치 정규화를 적용했습니다. 주인공 몸체와의 연결 및 엄지 대립 동작은 추가 맞춤이 필요합니다.</p></article><article class="card"><h3>독립 머리카락</h3><img src="art-slice/bob-hair.png" alt="새로 생성한 머리카락"><p>13,420정점·21,319삼각형. 머리카락만 따로 생성했습니다. 머리 치수와 내부 맞춤은 다음 검사입니다.</p></article><article class="card"><h3>몸체 세부 분할</h3><img src="art-slice/body-detailed-segment.png" alt="세부 분할 검사"><p>87개 조각으로 분리됐습니다. 조각 개수와 의미 있는 교체 부위는 다르므로 묶음·경계·단면 검사가 필요합니다.</p></article></div><div class="note">기존 주인공의 메시·얼굴·걷기는 유지했습니다. 새 손은 독립 실험이며 전체 캐릭터 완성으로 간주하지 않습니다. 얼굴 Rigify 템플릿은 보존했지만 얼굴 바인딩·표정은 아직 완성하지 않았습니다.</div><h2 id="tools">03 · 설치한 도구와 수작업 원본</h2><div class="grid"><article class="card"><h3>Krita 5.3.4</h3><p>공식 포터블 설치, ORA→KRA 및 PNG 내보내기 검사 완료. 2개 페인트 레이어를 확인했습니다. 이 목재 텍스처를 실제 마을 GLB에 적용했습니다.</p><code>art/source/village_materials/timber_touchup.kra</code><p><a href="https://docs.krita.org/en/reference_manual/linux_command_line.html">공식 CLI 문서</a></p></article><article class="card"><h3>Material Maker 1.7</h3><p>공식 설치·실행, 편집용 PBR 그래프 준비. 릴리스 SHA256 일치. 자동 내보내기에서 결과 파일이 생성되지 않아 해당 단계는 미검증입니다.</p><code>village_timber.ptex</code><p><a href="https://github.com/RodZill4/material-maker/releases/tag/1.7">공식 릴리스</a></p></article><article class="card"><h3>Blender 4.5.3 · Rigify</h3><p>마을·내부·개별 모듈과 손 리깅을 제작했습니다. 얼굴·손 메타리그도 저장했습니다. Blender 원본에서 메시와 웨이트를 계속 수정할 수 있습니다.</p><a href="https://docs.blender.org/manual/en/latest/addons/rigging/rigify/introduction.html">Rigify 공식 안내</a></article><article class="card"><h3>Substance Painter</h3><p>Adobe 라이선스 답변을 받기 전이어서 미설치입니다. 구매나 체험 구독은 진행하지 않았습니다.</p><a href="https://www.adobe.com/products/substance3d/apps/painter.html">공식 페이지</a></article></div><p>현재 세션은 데스크톱 앱의 직접 마우스·붓 제어를 지원하지 않습니다. 파일 변환과 Blender 스크립트를 실행했으며 직접 붓질했다고 주장하지 않습니다. <code>Art_Tools.cmd</code>에서 편집 원본을 열 수 있습니다.</p><h2 id="cost">04 · 분리한 예산과 실제 지출</h2>'''
page+=f'''<table><tr><th>작업</th><th>Scenario</th><th>Tripo</th></tr><tr><td>캐릭터 세부 실험</td><td>{totals['character_detail']['scenario']:g} / 1000 CU</td><td>{totals['character_detail']['tripo']:g} / 2000</td></tr><tr><td>마을 맵</td><td>{totals['village_map']['scenario']:g} / 1000 CU</td><td>{totals['village_map']['tripo']:g} / 2000</td></tr></table><p>Tripo 총 760크레딧. 시작 잔액 23110 → 마지막 확인 22350. 비용은 각 작업의 기록을 합산했습니다.</p><details><summary>생성 모델·요청 명세</summary><div class="scroll"><table><tr><th>분류</th><th>에셋/작업</th><th>모델</th><th>면 제한 요청</th><th>실제 크레딧</th></tr>{''.join(rows)}</table></div><p>생성은 texture·PBR=true, texture_quality=detailed입니다. 요청한 면 제한과 최종 삼각형 수가 같다고 보장하지 않습니다. Scenario: GPT Image 2, Auto 품질, 각 1장. 머리카락 12 CU, 열린 손 11 CU, 건물 11 CU. 별도 GPT API 호출·effort 설정은 쓰지 않았습니다.</p></details><h2>05 · 저장과 다음 작업</h2><p>개별 모듈은 <code>art/village_kit/</code>, 편집 원본은 <code>art/source/</code>, 실제 실행 프로젝트는 <code>labs/</code>에 있습니다. 생성 소품의 원점은 바닥 중심으로 정리했습니다.</p><p>다음 순서: 얼굴 토폴로지·눈꺼풀·입 안 정의 → 머리카락·손 치수 맞춤 → 독립 변형 검사 → 몸체 결합 → 걷기·달리기 중 검사. 마을은 아트 검토 후 본 게임의 서버 상호작용·저장에 연결합니다.</p><p><a href="art-slice/ART_TOOLS_AND_VILLAGE_20261003.md" download>상세 문서 저장본</a> · <a href="art-slice/budget.json">지출 기록</a> · <a href="art-slice/playtest.json">마을 검사 결과</a> · <a href="art-slice/hand-godot-audit.json">손 동작 검사 결과</a></p></main></html>'''
page=page.replace('code{background:#e6ecdf;padding:3px 7px;border-radius:5px}', 'code{background:#e6ecdf;padding:3px 7px;border-radius:5px;overflow-wrap:anywhere}')
if (REVIEW/'closeup-play.html').exists():page=page.replace('<nav>', '<nav><a href="closeup-play.html">근접 플레이 영상</a>',1)
(REVIEW/'art-slice.html').write_text(page,encoding='utf-8')
shutil.copy2(ROOT/'labs/detail_parts_lab/assets/open_hand_rigged.glb',MEDIA/'open_hand_rigged.glb')
bundle=OUT/'Tripothon_Art_Slice_20261003.zip'
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
 for folder in [ROOT/'labs/village_art_lab',ROOT/'labs/detail_parts_lab',ROOT/'art/village_kit']:
  for file in folder.rglob('*'):
   if file.is_file() and '.godot' not in file.parts:z.write(file,file.relative_to(ROOT))
 for file in [ROOT/'Village_Art_Lab.cmd',ROOT/'Detail_Parts_Lab.cmd',ROOT/'Art_Tools.cmd',ROOT/'docs/ART_TOOLS_AND_VILLAGE_20261003.md']:z.write(file,file.relative_to(ROOT))
 for file in [ROOT/'art/source/village_art_20261003.blend',ROOT/'art/source/cottage_interior_20261003.blend',ROOT/'art/source/open_hand_rigged_20261003.blend',ROOT/'art/source/explorer_detail_rig_template.blend',ROOT/'art/source/bob-hair_20261003.blend']:
  z.write(file,file.relative_to(ROOT))
 for file in (ROOT/'art/source/village_materials').rglob('*'):
  if file.is_file():z.write(file,file.relative_to(ROOT))
 z.writestr('README.txt','Tripothon editable art slice — 2026-10-03\n\nRequires Godot 4.7.2 or compatible Godot 4.x. Import labs/village_art_lab/project.godot or labs/detail_parts_lab/project.godot in Godot and run.\nThe .cmd launchers use the original workspace .tools layout. Engine executables are not bundled.\nBlender 4.5.3, Krita 5.3.4 and Material Maker 1.7 can open the editable sources in art/source.\nThis is an isolated local art lab, not a deployed server build. No provider keys are included.\n')
print('ART_SLICE_REPORT',REVIEW/'art-slice.html');print('TOTALS',totals);print('BUNDLE',bundle)
