import json, shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_open_mouth_hd_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
result=read(O/'generation-result.json');report=read(O/'inspection-report.json')
state={'source':'art/characters/explorer_b_open_mouth_hd_v1/model.glb',
       'blend':'art/characters/explorer_b_open_mouth_hd_v1/explorer_b_open_mouth_HD_workbench.blend',
       'state':'HD_generated_initial_cleanup_ready_for_form_review',
       'workflow':['HD generation','shape refinement','retopology','UV/bake/textures','facial rigging'],
       'retopology_complete':False,'rigged':False,'generation_credits':result['credits_consumed'],
       'remaining_budget':result['budget_remaining'],
       'oral_geometry_review':'Lips separated and recessed surface present, but cavity is shallow with fused tooth/tongue relief. Needs reconstruction and separation during form refinement.',
       'eye_geometry_review':'Generated iris and catchlight are relief in the head mesh; replace with separate eyeballs during form refinement.'}
p=R/'art/characters/explorer_b_pipeline_v3/pipeline.json';d=read(p);d['status']=state['state'];d['current_head_hd']=state
d['next_head_generation'].update(status='HD_generation_complete',next_model='Tripo v3.1 HD Ultra',tripo_submitted=True,tripo_credits_spent=result['credits_consumed'])
save(p,d)
p=R/'docs/CHARACTER_GENERATION_POLICY.json';d=read(p)
d.update(current_stage=state['state'],current_head_output='art/characters/explorer_b_open_mouth_hd_v1',current_batch_actual_credits=1000-result['budget_remaining'])
d['mode_by_part']['head']='HD source -> form refinement -> retopology -> UV/bake/textures -> facial rigging'
save(p,d)
p=R/'art/references/explorer_b_open_mouth_v1/manifest.json';d=read(p);d.update(status='HD_generation_complete',tripo_submitted=True,tripo_credits_spent=result['credits_consumed'],task_id=result['task_id']);save(p,d)
save(O/'workflow-status.json',state)
V=R/'artifacts/production-lab-20261003/review/character-open-mouth-hd';V.mkdir(parents=True,exist_ok=True)
for name in ['front','angle','side','prepared_front','prepared_angle','prepared_side','mouth_detail']:
    shutil.copy2(O/(name+'.png'),V/(name+'.png'))
shutil.copy2(R/'art/references/explorer_b_open_mouth_v1/01_head_open_mouth_front.png',V/'reference.png')
shutil.copy2(O/'inspection-report.json',V/'inspection-report.json')
cards=''.join(f'<figure><img src="{name}.png" loading="lazy"><figcaption>{title}</figcaption></figure>' for name,title in [
    ('reference','승인한 입 벌린 이미지'),('prepared_front','작업용 HD · 정면'),('prepared_angle','작업용 HD · 사선'),('prepared_side','작업용 HD · 측면'),('mouth_detail','입 확대 · 얕은 내부와 붙어 있는 치아 형태'),('front','보존한 Tripo 원본 · 하단 불필요 면 포함')])
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Explorer B · 입 벌린 HD 머리</title><style>body{font:17px/1.65 system-ui;background:#151b24;color:#eff4fa;max-width:1250px;margin:36px auto;padding:0 24px}h1{font-size:30px}main{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}figure{margin:0}img{width:100%;border-radius:12px}figcaption{padding:9px 0;color:#c6d0df}a{color:#9ac9ff}.note{background:#263344;padding:18px;border-radius:12px;margin:22px 0}@media(max-width:750px){main{grid-template-columns:1fr}}</style><h1>입을 벌린 HD 머리 · 형태 수정 준비</h1><p>Tripo v3.1 Ultra 원본 471,138 삼각형 / 235,571 정점. 이번 생성 40크레딧, 승인 한도 잔여 140크레딧.</p><p>HD 원본 → 형태 다듬기 → 리토폴로지 → UV·베이크·텍스처 → 페이스 리깅 순서입니다. 현재 리토폴로지·페이스 리깅은 진행 전입니다.</p><div class="note">원본 GLB와 숨긴 원본 메쉬를 보존했습니다. 별도 작업용 복사본에서 쇄골 아래의 불필요한 면을 잘랐습니다. 입술은 떨어져 있지만 입안은 얕고 치아·혀가 붙어 있는 부조 형태입니다. 눈의 반사광도 돌기로 생성됐습니다. 이 부분들은 형태 수정 단계에서 구강과 독립 파츠로 정리해야 합니다.</div><main>'''+cards+'''</main><p>Blender 파일: art/characters/explorer_b_open_mouth_hd_v1/explorer_b_open_mouth_HD_workbench.blend</p><p><a href="inspection-report.json">재열기·메쉬 검사 기록</a> · <a href="https://developers.tripo3d.ai/en/docs/generation-image-to-model/standard">사용한 HD 생성 설정 문서</a> · <a href="../character-hybrid-refined/">이전 조립 모델</a></p></html>''',encoding='utf-8')
print(json.dumps(state,ensure_ascii=False))
