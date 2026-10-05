import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'art/characters/explorer_b_user_head_v8';bpy.ops.wm.open_mainfile(filepath=str(R/'art/characters/explorer_b_pipeline_v3/01_template_test/mpfb_template_face_test.blend'));o=bpy.data.objects['Template_Face_Body'];b=o.data.shape_keys.key_blocks[0];out={}
for name in ['eyeBlinkLeft','eyeBlinkRight','jawOpen','mouthClose','mouthSmileLeft','mouthSmileRight','browInnerUp','browDownLeft','mouthFrownLeft']:
 k=o.data.shape_keys.key_blocks.get(name)
 if not k:continue
 ids=[i for i,(v,w) in enumerate(zip(k.data,b.data)) if (v.co-w.co).length>.0004];ps=[b.data[i].co for i in ids];out[name]={'count':len(ids),'min':[min(p[j] for p in ps) for j in range(3)],'max':[max(p[j] for p in ps) for j in range(3)],'max_delta':max((k.data[i].co-b.data[i].co).length for i in ids)}
out['objects']=[{'name':x.name,'verts':len(x.data.vertices)} for x in bpy.data.objects if x.type=='MESH' and not x.name.startswith('WGT')];(A/'mpfb-source-probe.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
