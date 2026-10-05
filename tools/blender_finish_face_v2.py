"""Validate facial closures, export baked morph animation, or render the actual timeline."""
import bpy,json,hashlib,sys,math
import numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'art/characters/explorer_b_face_refined_v2'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer_b_face_refined_v2.blend'))
scene=bpy.context.scene;head=bpy.data.objects['Face_Skin'];controls=bpy.data.objects['FACE_CONTROLS'];hair=bpy.data.objects['Hair_Fitted']
def coords(data):
    v=np.empty(len(data)*3,dtype=np.float32);data.foreach_get('co',v);return v.reshape(-1,3)
def evaluated_mesh(o):
    scene.view_layers[0].update();dep=bpy.context.evaluated_depsgraph_get();eo=o.evaluated_get(dep);return eo,eo.to_mesh()
def head_bvh():
    eo,m=evaluated_mesh(head);m.calc_loop_triangles();v=coords(m.vertices);f=np.empty(len(m.loop_triangles)*3,dtype=np.int32);m.loop_triangles.foreach_get('vertices',f);tree=BVHTree.FromPolygons(v.tolist(),f.reshape(-1,3).tolist(),all_triangles=True);eo.to_mesh_clear();return tree
if '--movie' in sys.argv:
    scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=True
    try:
        pref=bpy.context.preferences.addons['cycles'].preferences;pref.compute_device_type='CUDA';pref.get_devices()
        for d in pref.devices:d.use=d.type=='CUDA'
        if any(d.use for d in pref.devices):scene.cycles.device='GPU'
    except Exception:pass
    bare='--bare' in sys.argv;hair.hide_render=bare
    name='bare' if bare else 'portrait';directory=OUT/('frames-'+name);directory.mkdir(exist_ok=True)
    target=Vector((.01,0,0));camera=scene.camera;camera.location=target+Vector((3,0,0) if bare else (3,-.65,.07));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=.405
    scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    for frame in range(1,145):
        scene.frame_set(frame);scene.render.filepath=str(directory/f'{frame:04d}.png');bpy.ops.render.render(write_still=True)
        if frame%12==0:print('MOVIE_PROGRESS',name,frame,144,flush=True)
    print('MOVIE_READY',name,flush=True);raise SystemExit(0)

report={'stage':'face v2 validation','api_credits_spent':0,'method':'Blender mesh editing and authored shape keys, no Tripo rigging API'}
build=json.loads((OUT/'build-report.json').read_text())
report['source_files_unchanged']={part:hashlib.sha256((ROOT/f'art/characters/explorer_b_hd_restart_v1/{part}/{part}_HD.blend').read_bytes()).hexdigest()==build[part+'_source_sha256'] for part in ['head','hair']}
assert all(report['source_files_unchanged'].values())
scene.frame_set(1);base=coords(head.data.shape_keys.key_blocks['Basis'].data)
edges=np.empty(len(head.data.edges)*2,dtype=np.int32);head.data.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
parent=np.arange(len(base),dtype=np.int32)
def root(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for a,b in edges:
    a,b=root(a),root(b)
    if a!=b:parent[b]=a
_,counts=np.unique([root(i) for i in range(len(base))],return_counts=True)
report['skin_component_vertex_counts']=sorted(counts.tolist(),reverse=True)
report['shape_keys']=[k.name for k in head.data.shape_keys.key_blocks]
report['blink_core_visibility']={}
for frame,label in [(1,'open'),(19,'closed')]:
    scene.frame_set(frame);tree=head_bvh();result={}
    for sign,side in [(1,'L'),(-1,'R')]:
        visible=0;total=0
        for y in np.linspace(sign*.169-.060,sign*.169+.060,25):
            for z in np.linspace(-.047,.025,17):
                dy=y-sign*.169;dz=z+.005;front=.170+.100*math.sqrt(max(0,1-(dy/.130)**2-(dz/.112)**2))-.40*sign*dy
                hit=tree.ray_cast(Vector((1,float(y),float(z))),Vector((-1,0,0)))
                visible+=int(not hit[0] or hit[0].x<front-.0001);total+=1
        result[side]={'visible_eye_rays':visible,'tested_rays':total}
    report['blink_core_visibility'][label]=result
for side in ['L','R']:assert report['blink_core_visibility']['closed'][side]['visible_eye_rays']==0
report['eyelid_clearance_native_units']={}
for sign,side in [(1,'L'),(-1,'R')]:
    full=coords(head.data.shape_keys.key_blocks['Blink_'+side].data)-base;arc=coords(head.data.shape_keys.key_blocks['BlinkArc_'+side].data)-base
    mask=np.linalg.norm(full,axis=1)>1e-7
    results=[]
    for b in [0,.25,.5,.75,1]:
        p=base+full*b+arc*(4*b*(1-b));p=p[mask];dy=p[:,1]-sign*.169;dz=p[:,2]+.005;q=1-(dy/.130)**2-(dz/.112)**2;inside=q>0
        surface=.170+.100*np.sqrt(np.maximum(0,q))-.40*sign*dy
        results.append({'blink':b,'minimum_front_clearance':float(np.min((p[:,0]-surface)[inside]))})
    report['eyelid_clearance_native_units'][side]=results
first=None;last=None;values=[]
for frame in range(1,145):
    scene.frame_set(frame);scene.view_layers[0].update();values.append([float(controls[n]) for n in ['Blink_L','Blink_R','Jaw_Open','Smile','Brow_Raise']])
    if frame in [1,144]:
        eo,m=evaluated_mesh(head);p=coords(m.vertices);eo.to_mesh_clear()
        if frame==1:first=p
        else:last=p
report['loop_max_vertex_delta']=float(np.max(abs(first-last)))
report['control_range']=[float(np.min(values)),float(np.max(values))]
assert report['loop_max_vertex_delta']<1e-6
assert report['control_range'][0]>=-1e-6 and report['control_range'][1]<=1.000001
report['mesh_objects']=[o.name for o in scene.objects if o.type=='MESH']
report['limits']=['No phoneme/viseme library or ARKit expression set.','Outside new eyelid/lip bands, the reduced HD skin remains triangulated.','No body rig integration or Godot play test performed in this face task.','Skin and iris use vertex pigment; production UV maps are not authored.']
(OUT/'validation-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('VALIDATED',json.dumps(report),flush=True)

text=bpy.data.texts.get('READ_ME_FACE_V2') or bpy.data.texts.new('READ_ME_FACE_V2')
text.clear();text.write('FACE STUDY V2\nSpace: play frames 1-144 (24 fps).\nControls: FACE_CONTROLS > Object properties > Custom Properties.\nBlink_L/R, Jaw_Open, Smile, Brow_Raise use 0..1.\nAnimation drives these properties; change values at an unkeyed frame or mute the action to pose manually.\nFace skin is connected; eyes, lashes, hair and dental parts remain separate.\nOriginal HD source files are untouched.\nThis is authored Blender deformation, not Tripo auto-animation or Faceit.\nWorking skin remains triangulated outside the reconstructed feature loops.\n')
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer_b_face_refined_v2.blend'))

# Export a sampled animation from evaluated driver values. The editable blend above
# keeps its original controls and drivers; these temporary export changes aren't saved.
shapeobjects=[o for o in scene.objects if o.type=='MESH' and o.data.shape_keys]
samples={o.name:[] for o in shapeobjects}
for frame in range(1,145):
    scene.frame_set(frame);scene.view_layers[0].update()
    for o in shapeobjects:samples[o.name].append([float(k.value) for k in o.data.shape_keys.key_blocks][1:])
for o in shapeobjects:
    keys=o.data.shape_keys;keys.animation_data_clear()
    for frame,values in enumerate(samples[o.name],1):
        for key,value in zip(list(keys.key_blocks)[1:],values):
            key.value=value;key.keyframe_insert(data_path='value',frame=frame)
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT')
for o in scene.objects:
    if o.type=='MESH':o.select_set(True)
bpy.context.view_layer.objects.active=head
bpy.ops.export_scene.gltf(filepath=str(OUT/'explorer_b_face_refined_v2.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='SCENE',export_anim_scene_split_object=False,export_frame_range=True,export_force_sampling=True,export_morph=True,export_morph_normal=True,export_morph_animation=True,export_vertex_color='MATERIAL',export_all_vertex_colors=False)
print('GLB_EXPORTED',flush=True)
