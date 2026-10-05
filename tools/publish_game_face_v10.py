import json,shutil,subprocess,re,httpx,zipfile,hashlib,struct
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_game_face_v10';L=R/'labs/face_rig_v10';V=R/'artifacts/production-lab-20261003/review/character-game-face-rig-v10';V.mkdir(parents=True,exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report=read(A/'rig-verification.json');engine=read(A/'godot-verification.json');assert engine['status']=='passed';assert report['source_sha256_unchanged'] and all(report['author_original_geometry_UV_topology_material_checks'].values());assert all(x['visible']==0 for x in report['oral_occlusion'].values());assert (R/'artifacts/godot-face-v10-capture-errors.log').read_text().strip()==''
clips=read(A/'expression-clips.json');assert (R/'artifacts/godot-face-v10-capture.log').read_text().count('GAME_CLIP_CAPTURED')==len(clips)
buf=(A/'character_face_clips_v10.glb').read_bytes();n,_=struct.unpack_from('<II',buf,12);g=json.loads(buf[20:20+n]);bag=next(x for x in g['nodes'] if x.get('name')=='MOUTH_interior_bag');report['mouth_interior_triangles']=sum(g['accessors'][p['indices']]['count']//3 for p in g['meshes'][bag['mesh']]['primitives'])
ff=R/'.tools/krita-5.3.4/krita-x64-5.3.4/bin/ffmpeg.exe';fp=ff.with_name('ffprobe.exe');videos=[]
for c in clips:
 name=c['name'];frames=A/'game_frames'/name;assert len(list(frames.glob('frame_*.png')))==c['frames'];video=A/(name+'.mp4')
 subprocess.run([str(ff),'-hide_banner','-loglevel','error','-y','-framerate','30','-i',str(frames/'frame_%04d.png'),'-c:v','libopenh264','-b:v','2400k','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
 meta=json.loads(subprocess.check_output([str(fp),'-v','error','-count_frames','-show_entries','stream=nb_read_frames,avg_frame_rate','-of','json',str(video)],creationflags=subprocess.CREATE_NO_WINDOW));assert int(meta['streams'][0]['nb_read_frames'])==c['frames'];assert meta['streams'][0]['avg_frame_rate']=='30/1';videos.append({'name':name,'frames':c['frames'],'fps':30});shutil.copy2(video,V/video.name);shutil.copy2(A/('game_'+name+'.png'),V/('game_'+name+'.png'))
report.update(status='passed',actual_Godot_4_7_2_verified=True,engine_layers={'happy_plus_blink':True,'concern_plus_gaze':True,'crossfade_seconds':.25},game_video_validation=videos,blink_coverage_note='One boundary sample remains visible per eye out of 1620; full blink closes the pupil. Original topology retained.');save(A/'rig-verification.json',report)
readme='''# 원본 얼굴을 보존한 페이스 리그 v10

첨부한 `3d cartoon girl head.glb`의 얼굴 본체를 깎거나 리토폴로지하지 않았습니다. Blender 편집 파일의 Basis, UV, 폴리곤, 재질은 v9 원본과 일치합니다. 원본 파일의 SHA256도 일치합니다. 입을 닫는 기본 상태는 별도 RestClosed 셰이프 키입니다. 입 안의 보조 메쉬를 따로 추가해 틈으로 치아나 혀가 보이지 않게 했습니다.

## 파일

- original_preserved_face_rig_v10.blend: 원본 Basis를 보존한 편집용 파일입니다.
- character_face_clips_v10.glb: 입을 다문 포즈를 기본 상태로 적용한 별도 게임용 복사본입니다. 얼굴 UV와 폴리곤은 유지하고 헤어만 약 3만 삼각형으로 줄였습니다. 12개 애니메이션과 모프 타깃, 스킨, 텍스처를 포함합니다.
- game_export_scene_v10.blend: 게임용 복사본을 내보내는 작업 파일입니다.
- labs/face_rig_v10: Godot 4.7.2에서 실행한 재생 예제입니다. ZIP 안의 project.godot을 열면 됩니다.

## Blender 조작

Rigify head 조작 본에 얼굴 표정 36개와 시선 2개 속성이 있습니다. 아래 Action Editor에서 액션을 선택하고 Space로 재생합니다. 재생 범위는 각 액션에 맞춰 1–90 또는 1–120입니다. Blink는 1–15, WinkLeft/Right는 1–45, TalkOpen은 1–60입니다. 각 액션은 기본 표정에서 시작해 목표 표정을 거친 뒤 기본 표정으로 돌아옵니다.

원래 열린 입 형상을 검사하려면 재생을 멈추고 리그의 활성 Action을 해제한 뒤, head 본의 표정/시선 값을 모두 0으로 하고 jawOpen만 1로 설정합니다. jawOpen=0이면 입을 다문 기본 상태입니다. 원본 얼굴 메쉬는 항상 Basis_original_unchanged에 있습니다.

MPFB의 눈썹 표정 단위를 가져와 이 얼굴에 맞춘 보정을 더했습니다. 눈꺼풀·속눈썹과 입은 원본 형태에 맞춘 개별 타깃으로 피팅했습니다. Rigify가 머리와 눈의 조작 리그를 담당하고, 드라이버가 셰이프 키를 연결합니다. 완전한 ARKit 52개 세트나 발음별 음성 립싱크는 아닙니다.

## 게임 클립

IdleClosed, Smile, Happy, Concern, Determined, Surprise, Pucker, TalkOpen, Blink, WinkLeft, WinkRight, LookAround가 각각 독립된 애니메이션입니다. 하나의 긴 애니메이션에서 프레임 구간을 잘라 쓸 필요가 없습니다. 원본 키프레임 속도는 30fps입니다.

## Godot 사용

GLB를 불러온 캐릭터 아래에 face_controller.gd를 붙인 Node를 추가하고 configure(character)를 호출합니다. 이후 play_expression("Happy"), blink(), blink("WinkLeft"), look_around(), reset_face()를 사용할 수 있습니다.

AnimationTree의 Face 전환은 0.25초 동안 섞입니다. 눈꺼풀과 시선은 필터가 적용된 OneShot 레이어이므로 미소를 유지한 채 깜빡이거나 걱정 표정 위에서 시선을 움직일 수 있습니다. 예제 화면의 버튼으로 각 클립을 선택할 수 있고 자연스러운 간격으로 4초마다 깜빡입니다.

## 검증과 범위

Blender에서 원본 Basis·UV·폴리곤·재질과 원본 열린 입 복구를 검사했습니다. 모든 클립의 시작/끝 기본 표정, 중간 프레임의 유한 좌표, 기본 포즈에서 치아·혀 1318개 표면 표본의 가림을 확인했습니다. Godot에서 12개 클립과 미소+깜빡임, 걱정+시선 이동을 확인했습니다. 개별 MP4는 Blender의 오프라인 렌더가 아니라 Godot OpenGL Compatibility 렌더러로 캡처했습니다.

원본 토폴로지를 보존했기 때문에 완전히 눈을 감을 때 눈꺼풀의 일부 접힘/각진 부분은 남아 있습니다. 눈 표면 표본 1620개 중 각 눈의 경계 1개가 보이며 홍채는 가려집니다. 원본을 보존한 첫 게임용 표정 세트이며, 기존 게임의 캐릭터 장면을 교체한 상태는 아닙니다.
'''
(A/'README.md').write_text(readme,encoding='utf-8');(L/'README.md').write_text(readme,encoding='utf-8');shutil.copy2(A/'godot-verification.json',L/'godot-verification.json');shutil.copy2(A/'expression-clips.json',L/'expression-clips.json');shutil.copy2(A/'character_face_clips_v10.glb',L/'character_face_clips_v10.glb')
with zipfile.ZipFile(A/'godot_face_rig_v10.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name in ['project.godot','main.tscn','main.gd','face_controller.gd','character_face_clips_v10.glb','expression-clips.json','godot-verification.json','README.md']:z.write(L/name,name)
for source,name in [('original_preserved_face_rig_v10.blend','model.blend'),('character_face_clips_v10.glb','model.glb'),('godot_face_rig_v10.zip','godot_face_rig_v10.zip'),('rig-verification.json','rig-verification.json'),('godot-verification.json','godot-verification.json'),('README.md','README.md')]:shutil.copy2(A/source,V/name)
labels={'IdleClosed':'기본 · 입 다문 상태','Smile':'살짝 미소','Happy':'기쁨','Concern':'걱정','Determined':'결의','Surprise':'놀람','Pucker':'입술 오므리기','TalkOpen':'입 열기와 닫기','Blink':'깜빡임','WinkLeft':'왼쪽 윙크','WinkRight':'오른쪽 윙크','LookAround':'시선 이동'}
cards=''.join('<button data-clip="'+c['name']+'"><img src="game_'+c['name']+'.png" alt="'+labels[c['name']]+'"><span>'+labels[c['name']]+' · '+str(round(c['frames']/30,1))+'초</span></button>' for c in clips)
video_data={c['name']:{'label':labels[c['name']],'layer':c['layer'],'frames':c['frames']} for c in clips}
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>원본 보존 · 게임용 페이스 리그 v10</title><style>body{font:17px/1.7 system-ui;background:#17232f;color:#edf4fa;max-width:1180px;margin:32px auto;padding:0 24px}a{color:#abd7ff}.hero{display:grid;grid-template-columns:1.1fr 1fr;gap:26px}.hero video{width:100%;max-height:690px;background:#434950;border-radius:16px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:24px}button{background:#293b4d;color:#fff;border:2px solid transparent;border-radius:12px;cursor:pointer;padding:0;overflow:hidden;text-align:left;font:inherit}button.selected{border-color:#73c3ff}button img{width:100%;display:block}button span{display:block;padding:8px;font-size:15px}.note{background:#283b50;padding:16px;border-radius:12px}code{color:#abd7ff}li{margin:8px 0}@media(max-width:850px){.hero{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,1fr)}}</style><h1>원본 얼굴을 보존한 게임용 페이스 리그</h1><p>입을 다문 상태를 기본 표정으로 만들고, 눈·눈썹·볼·코·입의 조작을 연결했습니다. 얼굴의 원본 Basis·UV·폴리곤·재질을 유지했습니다.</p><div class="hero"><div><video id="player" controls playsinline preload="metadata" src="IdleClosed.mp4" poster="game_IdleClosed.png"></video><p id="caption">기본 · 입 다문 상태</p></div><div><h2>12개의 독립 클립</h2><p>아래에서 표정을 선택하면 그 클립만 재생됩니다. 게임용 GLB에도 각각 다른 이름의 애니메이션으로 들어 있습니다.</p><div class="note">기본 상태는 별도 셰이프 키로 닫은 입입니다. 편집용 Blender 파일에 원래 열린 입 형상을 보존했고, 게임용 복사본에는 닫힌 기본 포즈를 적용했습니다.</div><h2>게임에서 표정을 섞는 방식</h2><p>Godot 예제는 표정 사이를 0.25초 동안 부드럽게 전환합니다. 깜빡임과 시선은 별도 레이어라서 <b>미소 + 깜빡임</b>, <b>걱정 + 시선 이동</b>을 함께 재생할 수 있습니다.</p><p><a href="model.blend">Blender 편집 파일</a><br><a href="model.glb">게임용 GLB · 12개 클립</a><br><a href="godot_face_rig_v10.zip">Godot 재생 예제 ZIP</a><br><a href="README.md">조작 방법과 검증 범위</a></p></div></div><div class="grid">'''+cards+'''</div><h2>사용한 도구와 확인한 내용</h2><p>MPFB 눈썹 표정 단위에 얼굴별 보정을 더하고, Blender 셰이프 키로 눈꺼풀·속눈썹·입을 피팅했습니다. Rigify 조작 본과 드라이버를 연결했습니다. 얼굴 표정 36개와 시선 2개를 조절할 수 있습니다.</p><p>원본 형상·UV·폴리곤·재질, 열린 입 복구, 클립의 시작·중간·끝 프레임을 검사했습니다. 기본 포즈에서 치아·혀 표면 표본 1318개가 가려지는 것도 확인했습니다. <b>여기 있는 영상은 실제 Godot 렌더러 캡처</b>입니다.</p><p>원본 토폴로지를 유지해 완전히 눈을 감을 때 일부 접힘과 각진 부분이 남아 있습니다. 홍채는 가려지며 눈당 1620개 표본 중 경계 1개가 보입니다. 발음별 음성 립싱크는 포함하지 않았고, 기존 게임의 캐릭터 장면 교체는 하지 않았습니다.</p><p>추가 Tripo 크레딧: 0 · <a href="rig-verification.json">Blender 검증</a> · <a href="godot-verification.json">Godot 검증</a></p><script>const clips='''+json.dumps(video_data,ensure_ascii=False)+''';const player=document.getElementById('player');document.querySelectorAll('[data-clip]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-clip]').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');const name=b.dataset.clip;player.src=name+'.mp4';player.poster='game_'+name+'.png';document.getElementById('caption').textContent=clips[name].label+' · '+clips[name].frames+'프레임 · 30fps';player.play().catch(()=>{});}));document.querySelector('[data-clip="IdleClosed"]').classList.add('selected');</script></html>''',encoding='utf-8')
state={'date':'2026-10-05','state':'Original_preserved_closed_rest_independent_game_clips_v10','blend':(A/'original_preserved_face_rig_v10.blend').relative_to(R).as_posix(),'glb':(A/'character_face_clips_v10.glb').relative_to(R).as_posix(),'game_demo':L.relative_to(R).as_posix(),'source_basis_preserved':True,'neutral':'reversible closed-mouth pose','original_open_pose_recoverable':True,'facial_controls':36,'gaze_controls':2,'clips':[c['name'] for c in clips],'game_engine_verified':'Godot 4.7.2 OpenGL Compatibility','hair_triangles':report['runtime_hair_triangles'],'review_url':'http://127.0.0.1:8842/character-game-face-rig-v10/','credits':0};save(A/'workflow-status.json',state)
for p in [R/'docs/CHARACTER_GENERATION_POLICY.json',R/'art/characters/explorer_b_pipeline_v3/pipeline.json']:
 d=read(p);d['latest_game_face_rig_v10']=state
 if p.name=='CHARACTER_GENERATION_POLICY.json':d.update(current_stage=state['state'],current_hybrid_output=A.relative_to(R).as_posix())
 else:d.update(status=state['state'],current_hybrid_bust=state,current_integrated_face=state,current_head_source={'type':'original user supplied GLB','source':'art/characters/explorer_b_user_head_v8/source_user_head.glb','author_blend':state['blend'],'source_basis_preserved':True,'default_closed_is_pose':True})
 save(p,d)
with httpx.Client(timeout=30) as c:
 r=c.get(state['review_url']);r.raise_for_status();links=set(re.findall(r'(?:src|href|poster)="([^"]+)"',r.text));links.update(x['name']+'.mp4' for x in clips);codes={x:c.head(state['review_url']+x).status_code for x in links};assert all(v==200 for v in codes.values());print(state['review_url'],'HTTP_ASSETS_OK',len(codes))
print('V10_GAME_FACE_PUBLISHED',report['runtime_hair_triangles'],len(clips))
