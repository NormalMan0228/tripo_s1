import json,shutil,subprocess,re,httpx,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_hair_swap_v11';V=R/'artifacts/production-lab-20261003/review/character-user-hair-v11';L=R/'labs/face_rig_v11';V.mkdir(exist_ok=True,parents=True);L.mkdir(exist_ok=True)
report=json.loads((A/'hair-swap-report.json').read_text());assert report['status']=='passed' and all(report['face_and_all_shape_keys_unchanged'].values())
for n in ['main.tscn','main.gd','face_controller.gd','project.godot','test_face_rig.gd']:
 text=(R/'labs/face_rig_v10'/n).read_text(encoding='utf-8').replace('explorer_b_game_face_v10/godot-verification.json','explorer_b_hair_swap_v11/godot-verification.json').replace('Facial Rig v10','User Hair v11');(L/n).write_text(text,encoding='utf-8')
shutil.copy2(R/'art/characters/explorer_b_game_face_v10/expression-clips.json',L/'expression-clips.json');shutil.copy2(A/'character_user_hair_v11.glb',L/'character_face_clips_v10.glb');shutil.copy2(Path('C:/Users/dd/Downloads/brown hair 3d model.glb'),A/'source_brown_hair.glb')
run=subprocess.run([str(R/'.tools/godot/Godot_v4.7.2-stable_win64_console.exe'),'--headless','--path',str(L),'--script','res://test_face_rig.gd'],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW);(A/'godot-test.log').write_text(run.stdout+run.stderr,encoding='utf-8');engine=json.loads((A/'godot-verification.json').read_text());assert engine['status']=='passed';report['Godot_clips_and_layers_verified']=True;(A/'hair-swap-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
readme='''# 사용자 제공 헤어로 교체 · v11

첨부 brown hair 3d model.glb를 얼굴에 맞춰 배치했습니다. 새 헤어의 기존 색상 텍스처와 UV를 유지하고, 검은 얼룩을 만들던 노멀맵 강도를 0.12로 낮췄습니다. 얼굴과 두피에 들어가는 헤어 정점만 보정했습니다. 얼굴·눈·입·속눈썹·눈썹 메쉬 및 모든 셰이프 키는 v10과 수치상 동일합니다.

기본 상태는 입을 다문 표정입니다. 기존 12개 독립 클립과 Rigify 리그를 유지했습니다. 게임용 GLB에도 모두 포함했습니다. Godot에서 클립별 재생, 미소+깜빡임, 걱정+시선 이동을 다시 검사했습니다.

ZIP의 project.godot을 Godot 4.7.2에서 열면 버튼으로 표정 클립을 확인할 수 있습니다. face_controller.gd의 configure(character), play_expression("Happy"), blink(), look_around(), reset_face()를 사용할 수 있습니다. 기존 v10의 리깅 범위와 눈꺼풀 접힘 제한은 그대로입니다.

이전 모델과 원본 첨부 GLB를 보존했습니다. 추가 Tripo 크레딧은 0입니다.
''';(A/'README.md').write_text(readme,encoding='utf-8');(L/'README.md').write_text(readme,encoding='utf-8')
with zipfile.ZipFile(A/'godot_user_hair_v11.zip','w',zipfile.ZIP_DEFLATED) as z:
 for n in ['main.tscn','main.gd','face_controller.gd','project.godot','expression-clips.json','character_face_clips_v10.glb','README.md']:z.write(L/n,n)
for n in ['front','angle','side','back']:shutil.copy2(A/(n+'.png'),V/(n+'.png'))
shutil.copy2(R/'art/characters/explorer_b_game_face_v10/IdleClosed.png',V/'previous.png')
for n,dst in [('original_face_user_hair_v11.blend','model.blend'),('character_user_hair_v11.glb','model.glb'),('hair-swap-report.json','verification.json'),('godot_user_hair_v11.zip','godot_example.zip'),('README.md','README.md')]:shutil.copy2(A/n,V/dst)
figs=''.join('<figure><img src="'+n+'.png"><figcaption>'+label+'</figcaption></figure>' for n,label in [('front','새 헤어 · 정면'),('angle','사선'),('side','측면'),('back','후면')])
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>첨부 헤어로 교체 v11</title><style>body{font:17px/1.7 system-ui;background:#192631;color:#edf3fb;max-width:1080px;margin:32px auto;padding:0 22px}a{color:#b0d6ff}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0}img{width:100%;border-radius:12px}figcaption{padding:8px}@media(max-width:700px){.grid{grid-template-columns:1fr}}</style><h1>첨부하신 갈색 헤어로 교체했습니다</h1><p>헤어만 교체하고 얼굴과 기존 표정 리그를 유지했습니다. 입을 다문 기본 상태와 12개 독립 표정 클립도 그대로입니다.</p><p><a href="model.blend">Blender 파일</a> · <a href="model.glb">게임용 GLB</a> · <a href="godot_example.zip">Godot 재생 예제</a></p><div class="grid">'''+figs+'''</div><h2>맞춘 부분</h2><p>헤어의 크기와 위치를 맞추고, 뒤쪽 두피와 얼굴 안으로 들어가는 부분을 헤어 쪽에서 보정했습니다. 기존 색상 텍스처와 UV를 유지했고, 일부가 검게 보이던 노멀맵 강도를 낮췄습니다. 새 헤어는 약 2.8만 삼각형입니다.</p><p>얼굴 구성품과 모든 표정 셰이프 키가 v10과 동일한지 검사했습니다. Godot에서 기존 12개 클립과 미소+깜빡임, 걱정+시선 레이어를 다시 확인했습니다.</p><p><a href="previous.png">이전 헤어와 비교</a> · <a href="verification.json">검증 기록</a> · <a href="README.md">조작 방법</a> · <a href="../character-game-face-rig-v10/">이전 표정 클립 안내</a></p></html>''',encoding='utf-8')
state={'date':'2026-10-05','state':'User_brown_hair_swap_v11','blend':(A/'original_face_user_hair_v11.blend').relative_to(R).as_posix(),'glb':(A/'character_user_hair_v11.glb').relative_to(R).as_posix(),'hair_source':'C:/Users/dd/Downloads/brown hair 3d model.glb','face_and_shape_keys_unchanged':True,'clips':report['exported_clips'],'review_url':'http://127.0.0.1:8842/character-user-hair-v11/','credits':0};(A/'workflow-status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
for p in [R/'docs/CHARACTER_GENERATION_POLICY.json',R/'art/characters/explorer_b_pipeline_v3/pipeline.json']:
 d=json.loads(p.read_text(encoding='utf-8-sig'));d['latest_hair_swap_v11']=state
 if p.name=='CHARACTER_GENERATION_POLICY.json':d.update(current_stage=state['state'],current_hybrid_output=A.relative_to(R).as_posix())
 else:d.update(status=state['state'],current_hybrid_bust=state,current_integrated_face=state)
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with httpx.Client(timeout=30) as c:
 response=c.get(state['review_url']);response.raise_for_status();links=set(re.findall(r'(?:src|href)="([^"]+)"',response.text));assert all(c.head(state['review_url']+n).status_code==200 for n in links)
print('V11_PUBLISHED',state['review_url'])
