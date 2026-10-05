import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v11'
for key in ['sora','moru','naru','haeru']:
 bpy.ops.wm.open_mainfile(filepath=str(O/key/(key+'_rigged_idle.blend')))
 mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
 error=max(abs(sum(g.weight for g in v.groups)-1) for v in mesh.data.vertices);missing=sum(sum(g.weight for g in v.groups)<1e-6 for v in mesh.data.vertices)
 assert error<1e-4 and missing==0
 report=json.loads((O/key/'verification.json').read_text());report['audit']['source_weight_sum_error_max']=error;report['audit']['unweighted_vertices']=missing;(O/key/'verification.json').write_text(json.dumps(report,indent=2));print('SKIN_WEIGHTS_OK',key,error,flush=True)
reports={k:json.loads((O/k/'verification.json').read_text()) for k in ['sora','moru','naru','haeru']};(O/'verification.json').write_text(json.dumps(reports,indent=2))
