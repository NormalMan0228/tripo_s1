import bpy,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/characters/explorer-b-hand-v4'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer-b-hand.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['Explorer_B_Body_Rig'];body=bpy.data.objects['Explorer_B_SkinnedMesh']
with bpy.data.libraries.load(str(ROOT/'artifacts/characters/explorer-b-v1/explorer-b-custom.blend'),link=False) as (src,dst):dst.objects=['Explorer_B_SkinnedMesh']
original=dst.objects[0]
def head_signature(obj):
    rows=[];uv=obj.data.uv_layers.active.data
    for loop in obj.data.loops:
        v=obj.data.vertices[loop.vertex_index]
        if v.co.z<=.76:continue
        weights=sorted((obj.vertex_groups[g.group].name,round(g.weight,6)) for g in v.groups)
        rows.append((tuple(round(x,6) for x in v.co),tuple(round(x,6) for x in uv[loop.index].uv),tuple(weights)))
    return sorted(rows)
assert head_signature(body)==head_signature(original),'Original head geometry / UV / weights changed'
assert body.data.shape_keys is None
assert not any(b.name.startswith('Face_') for b in rig.data.bones)
assert len([o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)])==1
report={'original_head_geometry_uv_weights_match':True,'facial_additions_removed':True,'bones':len(rig.data.bones),'deform_bones':sum(b.use_deform for b in rig.data.bones),'clips':{}}
totals=[sum(g.weight for g in v.groups) for v in body.data.vertices]
assert max(abs(w-1) for w in totals)<1e-5
for name,seconds in [('Hands_Open_Grasp',4),('Arms_Reach_Grip',4),('Legs_Crouch_Step',6)]:
    rig.animation_data.action=bpy.data.actions[name];low=1e5;high=-1e5
    for frame in range(1,seconds*24+2,6):
        scene.frame_set(frame);ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
        points=[ev.matrix_world@v.co for v in mesh.vertices]
        assert all(math.isfinite(x) for p in points for x in p)
        low=min(low,min(p.z for p in points));high=max(high,max(p.z for p in points));ev.to_mesh_clear()
    report['clips'][name]={'seconds':seconds,'finite':True,'min_z':low,'max_z':high}
    assert low>-.015,'Ground penetration exceeds test tolerance'
(OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
assert len(body.data.vertices)==len(original.data.vertices)
assert all((a.co-b.co).length<1e-7 for a,b in zip(body.data.vertices,original.data.vertices))
hand=[v for v in body.data.vertices if abs(v.co.y)>.305]
assert max(len(v.groups) for v in hand)<=4
report['original_surface_restored']=True
report['vertices']=len(body.data.vertices)
report['hand_max_influences']=max(len(v.groups) for v in hand)
(OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
rig.animation_data.action=bpy.data.actions['Hands_Open_Grasp'];scene.frame_set(1)
for action in list(bpy.data.actions):
    if action.name not in {'Hands_Open_Grasp','Arms_Reach_Grip','Legs_Crouch_Step'}:
        bpy.data.actions.remove(action)
for obj in list(bpy.data.objects):
    if not obj.users_scene:bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'explorer-b-hand.blend'))
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);body.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'explorer-b-hand.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_anim_slide_to_zero=True,export_def_bones=True)
print('HAND_V4_VALIDATED_EXPORTED',json.dumps(report))
