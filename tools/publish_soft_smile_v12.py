from pathlib import Path
import shutil,json,subprocess,zipfile
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_soft_smile_v12';L=R/'labs/face_rig_v12';V=R/'artifacts/production-lab-20261003/review/character-soft-smile-v12'
L.mkdir(exist_ok=True);V.mkdir(exist_ok=True)
for n in ['main.tscn','main.gd','face_controller.gd','project.godot','test_face_rig.gd','expression-clips.json']:
 t=(R/'labs/face_rig_v11'/n).read_text(encoding='utf-8').replace('explorer_b_hair_swap_v11/godot-verification.json','explorer_b_soft_smile_v12/godot-verification.json').replace('User Hair v11','Soft Smile v12');(L/n).write_text(t,encoding='utf-8')
shutil.copy2(A/'character_soft_smile_v12.glb',L/'character_face_clips_v10.glb')
p=subprocess.run([str(R/'.tools/godot/Godot_v4.7.2-stable_win64_console.exe'),'--headless','--path',str(L),'--script','res://test_face_rig.gd'],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
(A/'godot-test.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0
assert json.loads((A/'godot-verification.json').read_text())['status']=='passed'
with zipfile.ZipFile(A/'godot_soft_smile_v12.zip','w',zipfile.ZIP_DEFLATED) as z:
 for n in ['main.tscn','main.gd','face_controller.gd','project.godot','expression-clips.json','character_face_clips_v10.glb']:z.write(L/n,n)
for n in ['front','angle','side','back']:shutil.copy2(A/(n+'.png'),V/(n+'.png'))
shutil.copy2(R/'art/characters/explorer_b_hair_swap_v11/front.png',V/'previous.png')
for n,d in [('original_face_soft_smile_v12.blend','model.blend'),('character_soft_smile_v12.glb','model.glb'),('godot_soft_smile_v12.zip','godot_example.zip'),('verification.json','verification.json')]:shutil.copy2(A/n,V/d)
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>입꼬리 완화 v12</title><style>body{font:17px/1.7 system-ui;background:#192631;color:#edf3fb;max-width:1080px;margin:32px auto;padding:0 22px}a{color:#b0d6ff}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}img{width:100%;border-radius:12px}</style><h1>입꼬리를 낮춘 기본 표정</h1><p>기존 얼굴 원본은 보존하고, 입을 다문 기본 표정의 양쪽 입꼬리만 부드럽게 낮췄습니다. 새 헤어와 12개 독립 표정 클립을 유지했습니다.</p><p><a href="model.blend">Blender 파일</a> · <a href="model.glb">게임용 GLB</a> · <a href="godot_example.zip">Godot 재생 예제</a></p><div class="grid"><div><img src="previous.png">이전 입꼬리</div><div><img src="front.png">완화한 입꼬리</div><img src="angle.png"><img src="side.png"></div><p><a href="verification.json">검증 기록</a></p></html>''',encoding='utf-8')
state={'state':'Soft_closed_smile_v12','blend':str(A/'original_face_soft_smile_v12.blend'),'glb':str(A/'character_soft_smile_v12.glb'),'review_url':'http://127.0.0.1:8842/character-soft-smile-v12/','original_author_basis_unchanged':True,'clips':12}
(A/'workflow-status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
for p in [R/'docs/CHARACTER_GENERATION_POLICY.json',R/'art/characters/explorer_b_pipeline_v3/pipeline.json']:
 d=json.loads(p.read_text(encoding='utf-8-sig'));d['latest_soft_smile_v12']=state
 if p.name=='CHARACTER_GENERATION_POLICY.json':d.update(current_stage=state['state'],current_hybrid_output=A.relative_to(R).as_posix())
 else:d.update(status=state['state'],current_hybrid_bust=state,current_integrated_face=state)
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print('V12_PUBLISHED',state['review_url'])
