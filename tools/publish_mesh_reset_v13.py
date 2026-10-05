from pathlib import Path
import json,shutil
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_mesh_reset_v13';V=R/'artifacts/production-lab-20261003/review/character-mesh-reset-v13';V.mkdir(exist_ok=True)
for n,d in [('front.png','front.png'),('original_mesh_with_user_hair_v13.blend','model.blend'),('original_mesh_with_user_hair_v13.glb','model.glb'),('original_source_head.glb','source_head.glb'),('verification.json','verification.json')]:shutil.copy2(A/n,V/d)
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>원본 메쉬 복원 v13</title><style>body{font:17px/1.7 system-ui;background:#192631;color:#edf3fb;max-width:900px;margin:32px auto;padding:0 22px}a{color:#b0d6ff}img{max-width:640px;width:100%}</style><h1>리깅 전 원본 메쉬로 복원</h1><p>원본의 입을 벌린 얼굴 메쉬로 돌아갔습니다. 직접 만든 리그, 표정 셰이프 키, 애니메이션, 보조 입 내부 메쉬를 제거했습니다. 부위별 메쉬 분리, UV와 텍스처, 최근 교체한 갈색 헤어를 유지했습니다.</p><p><a href="model.blend">작업용 Blender 파일</a> · <a href="model.glb">리그 없는 GLB</a> · <a href="source_head.glb">원본 첨부 얼굴 GLB</a></p><img src="front.png"><p>이전 버전은 별도로 보존했습니다. 다음 리깅은 전문 툴에서 새로 진행합니다.</p><a href="verification.json">검증 기록</a></html>''',encoding='utf-8')
state={'state':'Original_mesh_reset_v13','blend':str(A/'original_mesh_with_user_hair_v13.blend'),'glb':str(A/'original_mesh_with_user_hair_v13.glb'),'review_url':'http://127.0.0.1:8842/character-mesh-reset-v13/','rigged':False,'mouth':'original_open','next':'Professional facial rigging tool; not chosen or installed yet'}
(A/'workflow-status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
for p in [R/'docs/CHARACTER_GENERATION_POLICY.json',R/'art/characters/explorer_b_pipeline_v3/pipeline.json']:
 d=json.loads(p.read_text(encoding='utf-8-sig'));d['latest_mesh_reset_v13']=state
 if p.name=='CHARACTER_GENERATION_POLICY.json':d.update(current_stage=state['state'],current_hybrid_output=A.relative_to(R).as_posix())
 else:d.update(status=state['state'],current_hybrid_bust=state,current_integrated_face=state)
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print(state['review_url'])
