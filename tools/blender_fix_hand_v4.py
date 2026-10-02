"""Rebuild continuous hand skin weights; preserve all non-hand geometry and weights."""
import bpy,math,json,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/characters/explorer-b-hand-v4';OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'artifacts/characters/explorer-b-body-v3/explorer-b-body.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['Explorer_B_Body_Rig'];body=bpy.data.objects['Explorer_B_SkinnedMesh']
digits=['Thumb','Index','Middle','Ring','Little']
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def weights(index):return {body.vertex_groups[g.group].name:g.weight for g in body.data.vertices[index].groups}
def assign(index,values):
    for group_index in [g.group for g in body.data.vertices[index].groups]:body.vertex_groups[group_index].remove([index])
    values=dict(sorted(values.items(),key=lambda kv:kv[1],reverse=True)[:4]);total=sum(values.values())
    for name,value in values.items():
        if value>1e-8:body.vertex_groups[name].add([index],value/total,'REPLACE')
keys={v.index:tuple(round(x,6) for x in v.co) for v in body.data.vertices}
members={}
for v in body.data.vertices:
    if abs(v.co.y)>.305 and .67<v.co.z<.74:members.setdefault(keys[v.index],[]).append(v.index)
adj={k:set() for k in members}
for edge in body.data.edges:
    a,b=[keys[i] for i in edge.vertices]
    if a in members and b in members and a!=b:adj[a].add(b);adj[b].add(a)
original={k:weights(ids[0]) for k,ids in members.items()}
field={}
for key,indices in members.items():
    p=Vector(key);side='L' if p.y>0 else 'R';candidates=[]
    for digit in digits:
        bones=[rig.data.bones[f'{side}_{digit}_{i:02d}'] for i in range(1,4)]
        start=bones[0].head_local;end=bones[-1].tail_local
        axis=(end-start).normalized();along=(p-start).dot(axis)
        closest=start+axis*max(0,min((end-start).length,along));distance=(p-closest).length
        score=math.exp(-distance*distance/(.010**2))
        amount=smooth(-.008,.014,along)
        centers=[((b.head_local+b.tail_local)*.5-start).dot(axis) for b in bones]
        t=0 if along<=centers[0] else 2 if along>=centers[2] else (along-centers[0])/(centers[1]-centers[0]) if along<centers[1] else 1+(along-centers[1])/(centers[2]-centers[1])
        i=min(1,int(t));frac=t-i
        values={f'{side}_Hand':1-amount,bones[i].name:amount*(1-frac),bones[i+1].name:amount*frac}
        candidates.append((score,values))
    total=sum(score for score,values in candidates);combined={}
    for score,values in candidates:
        for name,value in values.items():combined[name]=combined.get(name,0)+score*value/total
    transition=smooth(.305,.322,abs(p.y))
    mixed={name:value*(1-transition) for name,value in original[key].items()}
    for name,value in combined.items():mixed[name]=mixed.get(name,0)+value*transition
    field[key]=mixed
# Geodesic diffusion cannot jump the air gap between neighboring fingers.
for iteration in range(16):
    result={}
    for key,values in field.items():
        strength=.48*smooth(.307,.323,abs(key[1]));neighbors=adj[key]
        if not neighbors:result[key]=values;continue
        mixed={name:v*(1-strength) for name,v in values.items()}
        for other in neighbors:
            for name,v in field[other].items():mixed[name]=mixed.get(name,0)+strength*v/len(neighbors)
        result[key]=mixed
    field=result
for key,indices in members.items():
    for index in indices:assign(index,field[key])
for poly in body.data.polygons:poly.use_smooth=True
rig.animation_data.action=bpy.data.actions['Hands_Open_Grasp'];scene.frame_set(25)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer-b-hand.blend'))
scene.cycles.samples=14;scene.render.resolution_x=720;scene.render.resolution_y=720
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='CUDA'
scene.cycles.device='GPU'
cam=scene.camera;target=Vector((.09,.17,.65));cam.location=target+Vector((2,-3,2));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.23
scene.render.filepath=str(OUT/'after-weights.png');bpy.ops.render.render(write_still=True)
print('WEIGHT_REBUILD_DONE',len(members))
