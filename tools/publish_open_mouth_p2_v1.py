import json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_open_mouth_p2_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
res=read(O/'generation-result.json');report=read(O/'inspection-report.json');notes=read(O/'visual-review.json')
state={'source':'art/characters/explorer_b_open_mouth_p2_v1/model.fbx',
       'blend':'art/characters/explorer_b_open_mouth_p2_v1/explorer_b_open_mouth_P2_workbench.blend',
       'state':'P2_open_mouth_geometry_review','generated':True,'rigged':False,
       'credits':res['credits_consumed'],'remaining_credits':res['budget_remaining'],
       'hd_comparison_preserved':'art/characters/explorer_b_open_mouth_hd_v1',
       'visual_review':notes}
save(O/'workflow-status.json',state)
p=R/'art/characters/explorer_b_pipeline_v3/pipeline.json';d=read(p);d['status']=state['state'];d['current_head_p2']=state
d['next_head_generation'].update(status='P2_generation_complete',next_model='Tripo Smart Mesh P2',tripo_submitted=True,tripo_credits_spent=res['credits_consumed'])
save(p,d)
p=R/'docs/CHARACTER_GENERATION_POLICY.json';d=read(p);d.update(current_stage=state['state'],current_head_output='art/characters/explorer_b_open_mouth_p2_v1',current_batch_actual_credits=1000-res['budget_remaining'])
d['mode_by_part']['head']='Smart Mesh P2 -> oral/topology review -> targeted cleanup -> texture -> facial rigging; HD trial retained'
save(p,d)
p=R/'art/references/explorer_b_open_mouth_v1/manifest.json';d=read(p)
d['HD_generation_preserved']={'task_id':d.get('task_id'),'output':'art/characters/explorer_b_open_mouth_hd_v1'}
d.update(status='P2_generation_complete',next_model='Tripo Smart Mesh P2',task_id=res['task_id'],tripo_credits_spent=res['credits_consumed']);save(p,d)
V=R/'artifacts/production-lab-20261003/review/character-open-mouth-p2';V.mkdir(parents=True,exist_ok=True)
for name in ['front','angle','side','mouth_detail','mouth_section']:
    shutil.copy2(O/(name+'.png'),V/(name+'.png'))
shutil.copy2(R/'art/characters/explorer_b_open_mouth_hd_v1/mouth_detail.png',V/'hd_mouth.png')
shutil.copy2(O/'inspection-report.json',V/'inspection-report.json')
cards=''.join(f'<figure><img src="{name}.png" loading="lazy"><figcaption>{title}</figcaption></figure>' for name,title in [('front','P2 원본 정면'),('angle','P2 사선'),('side','P2 측면'),('mouth_detail','P2 입 확대'),('mouth_section','P2 단면 · 별도 검사용 복사본'),('hd_mouth','이전 HD 입 확대')])
from html import escape
details=''.join('<li>'+escape(t)+'</li>' for t in notes['findings_ko'])
(V/'index.html').write_text(f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Explorer B · Smart Mesh P2 입 내부 비교</title><style>body{{font:17px/1.7 system-ui;background:#161c25;color:#edf2f9;max-width:1250px;margin:36px auto;padding:0 24px}}h1{{font-size:30px}}main{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}figure{{margin:0}}img{{width:100%;border-radius:12px}}figcaption{{padding:10px 0;color:#c1cede}}a{{color:#a7d0ff}}@media(max-width:750px){{main{{grid-template-columns:1fr}}}}</style><h1>입을 벌린 머리 · Smart Mesh P2</h1><p>동일한 승인 이미지로 머리만 재생성했습니다. {report['vertices']:,} 정점 / {report['faces']:,} 면. 이번 사용 {res['credits_consumed']:g}크레딧 / 잔여 {res['budget_remaining']:g}크레딧.</p><ul>{details}</ul><main>{cards}</main><p>Blender는 입 확대 시점으로 저장했습니다. 원본, 작업용 복사본, 숨긴 단면 검사용 복사본을 구분했습니다. 페이스 리깅은 아직 적용하지 않았습니다.</p><p><a href="inspection-report.json">메쉬 검사 기록</a> · <a href="../character-open-mouth-hd/">HD 비교 결과</a> · <a href="https://developers.tripo3d.ai/en/docs/generation-image-to-model/p">P2 설정 문서</a></p></html>''',encoding='utf-8')
print(json.dumps(state,ensure_ascii=False))
