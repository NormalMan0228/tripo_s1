import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/characters/explorer-b-hand-v4';OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'artifacts/characters/explorer-b-body-v3/explorer-b-body.blend'))
rig=bpy.data.objects['Explorer_B_Body_Rig'];body=bpy.data.objects['Explorer_B_SkinnedMesh'];scene=bpy.context.scene
rig.animation_data.action=bpy.data.actions['Hands_Open_Grasp'];scene.frame_set(25)
report={'custom_normals':body.data.has_custom_normals,'vertices':len(body.data.vertices),'faces':len(body.data.polygons),'flat_faces':sum(not p.use_smooth for p in body.data.polygons)}
keys={v.index:tuple(round(x,6) for x in v.co) for v in body.data.vertices}
hands=[p for p in body.data.polygons if all(abs(body.data.vertices[i].co.y)>.305 for i in p.vertices)]
pk=[tuple(sorted(keys[i] for i in p.vertices)) for p in hands]
report['hand_faces']=len(hands);report['duplicate_hand_faces']=len(pk)-len(set(pk));report['flat_hand_faces']=sum(not p.use_smooth for p in hands)
report['hand_duplicate_vertices']=len([v for v in body.data.vertices if abs(v.co.y)>.305])-len({keys[v.index] for v in body.data.vertices if abs(v.co.y)>.305})
bm=bmesh.new();bm.from_mesh(body.data);vs=[v for v in bm.verts if abs(v.co.y)>.305];bmesh.ops.remove_doubles(bm,verts=vs,dist=.000001)
report['hand_nonmanifold_after_weld']=sum(not e.is_manifold for e in bm.edges if all(abs(v.co.y)>.31 for v in e.verts));bm.free()
(OUT/'diagnosis.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
cam=scene.camera;target=Vector((.09,.17,.65));cam.location=target+Vector((2,-3,2));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.23
scene.render.resolution_x=720;scene.render.resolution_y=720;scene.cycles.samples=12
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
scene.cycles.device='GPU'
for name in ['before','no-normal-map','auto-normals','clay']:
    if name=='no-normal-map':
        for m in body.data.materials:
            for node in m.node_tree.nodes:
                if node.type=='BSDF_PRINCIPLED':
                    for link in list(node.inputs['Normal'].links):m.node_tree.links.remove(link)
    if name=='auto-normals':
        for p in body.data.polygons:p.use_smooth=True
        if body.data.has_custom_normals:body.data.normals_split_custom_set([(0,0,0)]*len(body.data.loops))
    if name=='clay':
        m=bpy.data.materials.new('DiagnosisClay');m.diffuse_color=(.45,.45,.45,1);body.data.materials.clear();body.data.materials.append(m)
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
