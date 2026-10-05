import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
for p in [R/'docs/CHARACTER_GENERATION_POLICY.json',R/'art/characters/explorer_b_pipeline_v3/pipeline.json']:
 d=json.loads(p.read_text(encoding='utf-8-sig'))
 if 'latest_tripo_retopology_v14' in d:d['latest_tripo_retopology_v14'].update(accepted=False,superseded_by='Original_mesh_reset_v13',user_decision='리토폴로지 결과를 사용하지 않고 v13 원본 메쉬로 복귀')
 d['retopology_decision']={'date':'2026-10-05','use_retopology':False,'working_version':'v13','original_mesh_with_user_hair':True}
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=R/'art/characters/explorer_b_tripo_retopo_v14/workflow-status.json';d=json.loads(p.read_text(encoding='utf-8'));d.update(accepted=False,state='Archived_rejected_retopology_trial_v14',current_working_version='v13');p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print('WORKING_VERSION_RESTORED_V13')
