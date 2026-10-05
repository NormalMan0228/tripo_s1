import bpy, numpy as np, json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
out={}
for n in ['sora','moru','naru','haeru']:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.gltf(filepath=str(R/'art/characters/npc_cast_closed_v2'/n/(n+'_static.glb')))
 o=next(o for o in bpy.context.scene.objects if o.type=='MESH')
 p=np.array([o.matrix_world@v.co for v in o.data.vertices]);h=p[:,2].max()
 d={'bounds':[p.min(axis=0).tolist(),p.max(axis=0).tolist()],'slices':{}}
 for z in [.1,.2,.3,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85]:
  slab=p[np.abs(p[:,2]/h-z)<.01];d['slices'][str(z)]={'x':np.quantile(slab[:,0],[.1,.5,.9]).tolist(),'abs_y':np.quantile(abs(slab[:,1]),[.25,.5,.75,.9,.99]).tolist()} if len(slab) else {}
 out[n]=d
(R/'art/characters/npc_cast_closed_v2/landmarks.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
