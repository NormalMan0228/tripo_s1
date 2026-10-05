import json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_tripo_retopo_v14';V=R/'artifacts/production-lab-20261003/review/character-tripo-retopo-v14';V.mkdir(exist_ok=True)
report=json.loads((A/'inspection.json').read_text(encoding='utf-8'));result=json.loads((A/'result.json').read_text(encoding='utf-8'));assert result['status']=='success'
for n,d in [('face_retopology_assembly_v14.blend','model.blend'),('face_retopology_assembly_v14.glb','model.glb'),('front.png','front.png'),('wire.png','wire.png'),('mouth.png','mouth.png'),('eyes.png','eyes.png'),('inspection.json','inspection.json')]:shutil.copy2(A/n,V/d)
shutil.copy2(R/'art/characters/explorer_b_mesh_reset_v13/front.png',V/'previous.png')
shutil.copy2(A/Path(result['file']).name,V/Path(result['file']).name)
summary=f"얼굴 본체: 원본 {report['source']['vertices']:,}정점 / {report['source']['faces']:,}면 → Tripo 결과 {report['result']['vertices']:,}정점 / {report['result']['faces']:,}면. 사각형 {report['result']['quads']:,}면. 사용 {result['credits_consumed']:g}크레딧. 목표 8,000면과 실제 출력은 다릅니다."
(V/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>Tripo Smart 리토폴로지 v14</title><style>body{font:17px/1.7 system-ui;background:#192631;color:#edf3fb;max-width:1080px;margin:32px auto;padding:0 22px}a{color:#b0d6ff}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}img{width:100%;border-radius:12px}</style><h1>Tripo Smart Retopology · 검토본</h1><p>'''+summary+'''</p><p>얼굴 본체만 Tripo에서 처리했습니다. 새 헤어와 분리된 눈알·치아·혀·눈썹·속눈썹·귀·쇄골은 원본대로 유지했습니다. 원본 v13은 보존했습니다.</p><p>코·입술 표면 거칠어짐, 목 연결부 흔적, 비정상 연결 모서리 16개가 남아 있습니다. 표정용 최종본으로 확정하지 않았습니다. Tripo가 정규화한 크기·위치를 복원하고 가져온 면의 방향을 보정했습니다.</p><p><a href="model.blend">Blender 작업 파일</a> · <a href="model.glb">GLB 검토본</a> · <a href="'''+Path(result['file']).name+'''">Tripo 원본 출력</a></p><div class="grid"><div><img src="previous.png">원본</div><div><img src="front.png">리토폴로지 결과</div><img src="wire.png"><img src="mouth.png"><img src="eyes.png"></div><p>GLB는 삼각형으로 저장됩니다. 작업용 Blender 파일의 면 구성은 위 수치를 기준으로 확인하세요. 자동 리토폴로지 결과이며, 표정 변형 및 중립 입 닫기 검증은 아직 진행하지 않았습니다.</p><a href="inspection.json">메쉬 검사 기록</a> · <a href="https://developers.tripo3d.ai/en/docs/mesh-decimate">Tripo 공식 문서</a></html>''',encoding='utf-8')
state={'state':'Tripo_smart_retopology_v14','blend':str(A/'face_retopology_assembly_v14.blend'),'glb':str(A/'face_retopology_assembly_v14.glb'),'review_url':'http://127.0.0.1:8842/character-tripo-retopo-v14/','credits_consumed':result['credits_consumed'],'rigged':False,'facial_deformation_verified':False}
(A/'workflow-status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
for p in [R/'docs/CHARACTER_GENERATION_POLICY.json',R/'art/characters/explorer_b_pipeline_v3/pipeline.json']:
 d=json.loads(p.read_text(encoding='utf-8-sig'));d['latest_tripo_retopology_v14']=state
 if p.name=='CHARACTER_GENERATION_POLICY.json':d.update(current_stage='Tripo_retopology_review_v14_original_v13_preserved')
 else:d.update(status='Tripo_retopology_review_v14_original_v13_preserved')
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print(state['review_url'])
