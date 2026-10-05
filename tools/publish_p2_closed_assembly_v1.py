import json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_p2_closed_assembly_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report=read(O/'assembly-report.json');verification=read(O/'verification.json')
state={'date':'2026-10-05','state':'P2_closed_rest_hair_eyes_brows_lashes_assembled_review',
       'blend':'art/characters/explorer_b_p2_closed_assembly_v1/explorer_b_P2_closed_assembly_v1.blend',
       'report':'art/characters/explorer_b_p2_closed_assembly_v1/assembly-report.json',
       'hair_source':'explorer_b_hybrid_bust_v2/HAIR_HD_FITTED',
       'default_mouth':'closed','inspection_control':'FACE_CONTROLS["mouth_open"] 0..1',
       'source_open_shape_preserved':True,'api_credits':0,'full_face_rig':False,'blink_rig':False,
       'materials':'Procedural skin and iris preview; packed eyebrow/lash alpha atlas',
       'remaining':['P2 local seams and eyelid deformation need refinement before final facial rigging','Static lashes must be bound to eyelid deformation at rigging stage','Skin color and material are preview; final UV texture painting remains','HD hair is preserved high-resolution source, not game-optimized']}
save(O/'workflow-status.json',state)
p=R/'art/characters/explorer_b_pipeline_v3/pipeline.json';d=read(p);d['status']=state['state'];d['current_hybrid_bust']=state;save(p,d)
p=R/'docs/CHARACTER_GENERATION_POLICY.json';d=read(p);d.update(current_stage=state['state'],current_hybrid_output='art/characters/explorer_b_p2_closed_assembly_v1',default_face_pose='closed_mouth',preserve_open_mouth_source=True);save(p,d)
V=R/'artifacts/production-lab-20261003/review/character-p2-closed-assembly';V.mkdir(parents=True,exist_ok=True)
for name in ['front','angle','side','face_detail','mouth_closed','mouth_open']:
 shutil.copy2(O/(name+'.png'),V/(name+'.png'))
shutil.copy2(O/'verification.json',V/'verification.json')
cards=''.join(f'<figure><img src="{name}.png" loading="lazy"><figcaption>{title}</figcaption></figure>' for name,title in [('front','정면 · 입을 다문 기본 상태'),('angle','사선 · 최근 수정한 HD 헤어'),('side','측면'),('face_detail','헤어를 숨긴 눈·눈썹·속눈썹 검토'),('mouth_closed','닫힌 입'),('mouth_open','mouth_open = 1 · 원본 개구 형태')])
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Explorer B · P2 머리 조립</title><style>body{font:17px/1.7 system-ui;background:#161c25;color:#edf2f9;max-width:1250px;margin:36px auto;padding:0 24px}h1{font-size:30px}main{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}figure{margin:0}img{width:100%;border-radius:12px}figcaption{padding:10px 0;color:#c1cede}a{color:#a7d0ff}.note{padding:18px;background:#263444;border-radius:12px;margin:20px 0}@media(max-width:750px){main{grid-template-columns:1fr}}</style><h1>P2 머리 + 최근 헤어 · 입을 다문 기본 상태</h1><p>새 P2 머리에 최근 수정한 HD 헤어를 배치했습니다. 별도 갈색 눈알·홍채와 좌우 눈썹·위/아래 속눈썹 UV 메쉬를 추가했습니다. 원본 P2와 입 내부는 보존했습니다.</p><div class="note"><b>Blender 사용법</b><br>기본은 입을 다문 상태입니다. FACE_CONTROLS 선택 → 사용자 정의 속성 → mouth_open: 0은 닫힘, 1은 생성 당시의 입 벌림입니다. 아래 치아와 혀도 함께 움직입니다. 완성된 페이스 리그나 깜빡임 리그는 아직 아닙니다.</div><main>'''+cards+'''</main><p>입 열림 0 / 0.25 / 0.5 / 0.75 / 1 / 0 검사를 완료했습니다. 닫힌 상태에서 입 중앙과 좌우 검사 지점의 구강 노출 높이는 0입니다. 피부는 색상 검토용 재질이며, 최종 UV 텍스처는 추후 작업합니다. P2의 일부 입가·눈꺼풀 접합부도 리깅 전 추가 정리가 필요합니다.</p><p>이번 작업의 추가 Tripo 사용량: 0크레딧. 남은 승인 한도: 40크레딧.</p><p><a href="verification.json">검증 기록</a> · <a href="../character-open-mouth-p2/">이전 P2 구강 원본</a></p></html>''',encoding='utf-8')
print('Published character-p2-closed-assembly; no additional API calls.')
