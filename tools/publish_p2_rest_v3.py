import json, shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1]
O=R/'art/characters/explorer_b_p2_rest_refined_v3'
OLD=R/'art/characters/explorer_b_p2_rest_refined_v2'
V=R/'artifacts/production-lab-20261003/review/character-p2-friendly-rest-v3'
V.mkdir(parents=True,exist_ok=True)
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state={
 'date':'2026-10-05','state':'P2_friendly_rest_attached_lashes_v3_review',
 'blend':'art/characters/explorer_b_p2_rest_refined_v3/explorer_b_P2_rest_refined_v3.blend',
 'report':'art/characters/explorer_b_p2_rest_refined_v3/refinement-report.json',
 'default_mouth':'closed_gentle_smile','inspection_control':'FACE_CONTROLS["mouth_open"] 0..1',
 'hair_source':'explorer_b_hybrid_bust_v2/HAIR_HD_FITTED',
 'eye_rest':'Gentle opening; continuous tapered strand roots seated above upper rim and below lower rim',
 'lash_geometry':'144 continuous tapered strands, 6336 side quads and 144 tip caps; no alpha fragments',
 'expression_reference':'C:/Users/dd/AppData/Local/Temp/codex-clipboard-d86b1eef-42f9-41c7-85b7-316c7ba2ad35.png',
 'brows':'Contiguous alpha silhouette UV strip, forehead contact and soft tapered ends',
 'source_open_shape_preserved':True,'api_credits':0,'full_face_rig':False,'blink_rig':False,
 'remaining':['Static rest attachment only; lash blink binding pending','Skin is a preview material; final texture painting pending']}
save(O/'workflow-status.json',state)
p=R/'art/characters/explorer_b_pipeline_v3/pipeline.json'
d=json.loads(p.read_text(encoding='utf-8-sig'));d['status']=state['state'];d['current_hybrid_bust']=state;save(p,d)
p=R/'docs/CHARACTER_GENERATION_POLICY.json'
d=json.loads(p.read_text(encoding='utf-8-sig'));d.update(current_stage=state['state'],current_hybrid_output='art/characters/explorer_b_p2_rest_refined_v3',default_face_pose='closed_mouth_gentle_smile_natural_open_eyes');save(p,d)
names=['front','angle','side','face_detail','eye_detail','eye_oblique','brow_detail','mouth_closed','mouth_profile','mouth_open']
for n in names:shutil.copy2(O/(n+'.png'),V/(n+'.png'))
for n in ['front','side','face_detail','mouth_closed']:shutil.copy2(OLD/(n+'.png'),V/('before_'+n+'.png'))
shutil.copy2(O/'verification.json',V/'verification.json')
shutil.copy2(state['expression_reference'],V/'expression-reference.png')
cards=''.join(f'<figure><img src="{n}.png" loading="lazy"><figcaption>{t}</figcaption></figure>' for n,t in [('angle','사선 · 자연스럽게 뜬 눈과 미소'),('eye_detail','눈 확대 · 위·아래 속눈썹'),('eye_oblique','사선 확대 · 속눈썹 뿌리'),('brow_detail','눈썹 확대 · 피부 접촉과 UV'),('mouth_closed','입을 다문 기본 표정'),('mouth_profile','입·턱 측면'),('mouth_open','입 열림 1 · 보존한 구강')])
html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Explorer B · 기본 표정 v3</title><style>body{font:17px/1.7 system-ui;background:#161c25;color:#eef4fb;max-width:1250px;margin:36px auto;padding:0 24px}h1{font-size:30px}.compare,main{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}figure{margin:0}img{width:100%;border-radius:12px}figcaption{padding:9px;color:#c7d2e1}select{padding:9px;font:inherit;background:#283749;color:white;border-radius:7px;margin:12px 0}a{color:#a8d2ff}main{margin-top:25px}.note{background:#27374a;padding:18px;border-radius:12px;margin:20px 0}@media(max-width:700px){.compare,main{grid-template-columns:1fr}}</style><h1>자연스럽게 뜬 눈 · 올라간 입꼬리 · 정돈한 눈썹</h1><p>눈꺼풀을 이전보다 조금 열고 입꼬리 끝을 올렸습니다. 위 속눈썹 뿌리는 위 눈꺼풀의 윗쪽, 아래 속눈썹 뿌리는 아래 눈꺼풀의 아래쪽 피부에 맞췄습니다. 알파 조각이 떨어져 보이던 속눈썹 카드는 뿌리부터 끝까지 이어지는 가는 메쉬 144가닥으로 바꿨습니다. 눈썹은 연속된 텍스처 본체를 UV로 사용하고 피부 접촉을 보정했습니다.</p><label>비교 시점 <select id="view"><option value="front">정면</option><option value="side">측면</option><option value="face_detail">헤어를 숨긴 얼굴</option><option value="mouth_closed">입·턱 확대</option></select></label><div class="compare"><figure><img id="before" src="before_front.png"><figcaption>이전 v2</figcaption></figure><figure><img id="after" src="front.png"><figcaption>수정 v3</figcaption></figure></div><div class="note">입을 다문 상태로 저장했습니다. FACE_CONTROLS의 mouth_open을 0~1로 바꾸면 원본 구강을 확인할 수 있습니다. 속눈썹은 기본 표정에 맞춘 상태이며 깜빡임 리깅은 아직 적용하지 않았습니다. 추가 Tripo 비용은 0크레딧입니다.</div><main>'''+cards+'''</main><p>파일 재열기, 입 열림 0~1, 저장된 속눈썹 뿌리와 중간점의 실제 피부 거리 및 배치 방향, 눈썹 피부 거리, UV를 검사했습니다.</p><p><a href="verification.json">검증 기록</a> · <a href="../character-p2-rest-refined/">이전 v2</a></p><script>document.querySelector('#view').addEventListener('change',e=>{const n=e.target.value;document.querySelector('#before').src='before_'+n+'.png';document.querySelector('#after').src=n+'.png';});</script></html>'''
html=html.replace('<label>비교 시점', '<figure style="max-width:440px;margin:24px 0"><img src="expression-reference.png"><figcaption>사용자가 지정한 표정 참고 이미지</figcaption></figure><label>비교 시점')
(V/'index.html').write_text(html,encoding='utf-8')
print('Published friendly rest v3 comparison page.')
