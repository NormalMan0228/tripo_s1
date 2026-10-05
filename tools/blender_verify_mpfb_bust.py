"""Reopen and exercise the styled bust; no changes to the saved review file."""
import bpy,json,math
from collections import Counter,defaultdict
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/mpfb-clavicle-bust-20261004'
scene=bpy.context.scene;scene.frame_set(1)
face=bpy.data.objects['Face_Neck_Clavicle'];keys=face.data.shape_keys.key_blocks
edges=Counter(tuple(sorted((a,b))) for p in face.data.polygons for a,b in zip(list(p.vertices),list(p.vertices)[1:]+list(p.vertices)[:1]))
adj=defaultdict(set)
for a,b in edges:adj[a].add(b);adj[b].add(a)
unseen=set(range(len(face.data.vertices)));components=[]
while unseen:
 stack=[unseen.pop()];n=0
 while stack:
  i=stack.pop();n+=1
  for j in adj[i]&unseen:unseen.remove(j);stack.append(j)
 components.append(n)
assert len(components)==1,components
assert all(n==2 for n in edges.values()),Counter(edges.values())
report={'reopened':bpy.data.filepath,'skin_components':components,'skin_edge_face_counts':dict(Counter(edges.values())),'shape_keys':len(keys),'driver_tests':[],'renders':[],'all_passed':False}
assert len(keys)==90
assert 'mouthSmileLeft' in keys and 'jawOpen' in keys
assert all(math.isfinite(v) for k in keys for p in k.data for v in p.co)
for name in ['Eyes','Eyebrows','Eyelashes','Teeth','Tongue']:
 o=bpy.data.objects[name];assert o.data.shape_keys
 if name=='Eyelashes':assert all(k in o.data.shape_keys.key_blocks for k in ['eyeBlinkLeft','eyeBlinkRight'])
face.data.shape_keys.animation_data.action=None
def pose(values):
 for k in keys[1:]:k.value=values.get(k.name,0)
 bpy.context.view_layer.update()
 for name in ['Eyes','Eyebrows','Eyelashes','Teeth','Tongue']:
  for k in bpy.data.objects[name].data.shape_keys.key_blocks[1:]:
   assert abs(k.value-keys[k.name].value)<1e-5,(name,k.name,k.value,keys[k.name].value)
def render(label,values,angle=0):
 pose(values)
 target=Vector((0,-.015,.147));a=math.radians(angle)
 scene.camera.location=target+Vector((math.sin(a)*1.3,-math.cos(a)*1.3,.012))
 scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
 scene.render.filepath=str(OUT/(label+'.png'));bpy.ops.render.render(write_still=True)
 report['driver_tests'].append({'pose':label,'values':values,'accessory_drivers_match':True})
 report['renders'].append(label+'.png')
scene.cycles.samples=32
for amount in [.25,.5,.75]:render('blink_'+str(int(amount*100)),{'eyeBlinkLeft':amount,'eyeBlinkRight':amount})
render('gaze_blink',{'eyeBlinkLeft':.5,'eyeBlinkRight':.5,'eyeLookOutLeft':.4,'eyeLookInRight':.4},35)
render('gaze_side',{'eyeLookOutLeft':.4,'eyeLookInRight':.4},65)
report['all_passed']=True
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('BUST_VERIFIED',json.dumps(report))
