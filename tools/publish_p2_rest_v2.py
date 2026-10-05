import json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_p2_rest_refined_v2';OLD=R/'art/characters/explorer_b_p2_closed_assembly_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state={'date':'2026-10-05','state':'P2_relaxed_eyes_subtle_smile_rest_refined_review',
       'blend':'art/characters/explorer_b_p2_rest_refined_v2/explorer_b_P2_rest_refined_v2.blend',
       'report':'art/characters/explorer_b_p2_rest_refined_v2/refinement-report.json',
       'hair_source':'explorer_b_hybrid_bust_v2/HAIR_HD_FITTED',
       'default_mouth':'closed_subtle_smile','inspection_control':'FACE_CONTROLS["mouth_open"] 0..1',
       'eye_rest':'Upper eyelid lowered and lower rim slightly raised; static lashes refitted to connected lid edges',
       'brows':'Thinner, flatter curve with alpha taper at both ends',
       'chin':'Reduced lower-lip projection and smoothed lower-lip-to-chin profile',
       'source_open_shape_preserved':True,'api_credits':0,'full_face_rig':False,'blink_rig':False,
       'remaining':['Local generated seams still need review before final rigging','Lashes are fitted at rest; bind to eyelid deformation for animation','Skin is a preview material; final UV texture painting pending']}
save(O/'workflow-status.json',state)
p=R/'art/characters/explorer_b_pipeline_v3/pipeline.json';d=read(p);d['status']=state['state'];d['current_hybrid_bust']=state;save(p,d)
p=R/'docs/CHARACTER_GENERATION_POLICY.json';d=read(p);d.update(current_stage=state['state'],current_hybrid_output='art/characters/explorer_b_p2_rest_refined_v2',default_face_pose='closed_mouth_subtle_smile_relaxed_open_eyes');save(p,d)
V=R/'artifacts/production-lab-20261003/review/character-p2-rest-refined';V.mkdir(parents=True,exist_ok=True)
for name in ['front','angle','side','face_detail','eye_detail','mouth_closed','mouth_profile','mouth_open']:
 shutil.copy2(O/(name+'.png'),V/(name+'.png'))
for name in ['front','side','face_detail','mouth_closed']:shutil.copy2(OLD/(name+'.png'),V/('before_'+name+'.png'))
shutil.copy2(O/'verification.json',V/'verification.json')
cards=''.join(f'<figure><img src="{name}.png" loading="lazy"><figcaption>{title}</figcaption></figure>' for name,title in [('angle','사선 · 편안한 눈과 약한 미소'),('eye_detail','눈 확대 · 눈꺼풀 가장자리의 속눈썹'),('mouth_profile','측면 확대 · 아랫입술에서 턱으로 이어지는 곡선'),('mouth_closed','입을 다문 기본 표정'),('mouth_open','입 열림 1 · 보존한 구강 확인')])
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Explorer B · 편안한 기본 표정 v2</title><style>body{font:17px/1.7 system-ui;background:#161c25;color:#eef4fb;max-width:1250px;margin:36px auto;padding:0 24px}h1{font-size:30px}.compare,main{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}figure{margin:0}img{width:100%;border-radius:12px}figcaption{padding:9px;color:#c7d2e1}select{padding:9px;font:inherit;background:#283749;color:white;border-radius:7px;margin:12px 0}a{color:#a8d2ff}main{margin-top:25px}.note{background:#27374a;padding:18px;border-radius:12px;margin:20px 0}@media(max-width:700px){.compare,main{grid-template-columns:1fr}}</style><h1>편안한 눈 · 완만한 턱 · 약한 미소</h1><p>속눈썹을 변형된 눈꺼풀 가장자리로 다시 배치했습니다. 위 눈꺼풀은 조금 낮추고 아래 가장자리는 살짝 올렸습니다. 눈썹은 얇고 완만하게 조정하고 끝의 알파를 부드럽게 처리했습니다. 아랫입술 돌출과 턱 사이의 급한 굴곡을 줄였고 입을 다문 약한 미소를 기본 상태로 저장했습니다.</p><label>비교 시점 <select id="view"><option value="front">정면</option><option value="side">측면</option><option value="face_detail">헤어를 숨긴 얼굴</option><option value="mouth_closed">입·턱 확대</option></select></label><div class="compare"><figure><img id="before" src="before_front.png"><figcaption>수정 전</figcaption></figure><figure><img id="after" src="front.png"><figcaption>수정 후 v2</figcaption></figure></div><div class="note">기본은 입 닫힘입니다. Blender에서 FACE_CONTROLS의 mouth_open을 0~1로 바꾸면 원본 구강을 확인할 수 있습니다. 속눈썹은 현재 기본 표정에 맞춘 상태이며, 깜빡임에 따라 움직이는 리깅은 다음 단계입니다. 이번 추가 Tripo 비용은 0크레딧입니다.</div><main>'''+cards+'''</main><p>파일 재열기, 입 열림 0~1 변화, 속눈썹 뿌리 간격, UV 및 원본 보존을 검사했습니다. 생성 메쉬의 일부 미세한 경계는 남아 있으며 최종 리깅 전에 검토합니다.</p><p><a href="verification.json">검증 기록</a> · <a href="../character-p2-closed-assembly/">이전 조립본</a></p><script>document.querySelector('#view').addEventListener('change',e=>{const n=e.target.value;document.querySelector('#before').src='before_'+n+'.png';document.querySelector('#after').src=n+'.png';});</script></html>''',encoding='utf-8')
print('Published refined v2 comparison page.')
