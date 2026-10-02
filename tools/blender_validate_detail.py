import bpy,json,math
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/characters/explorer-b-detailed-v2'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'explorer-b-detailed.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['Explorer_B_Detailed_Rig'];body=bpy.data.objects['Explorer_B_SkinnedMesh']
character=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)]
report={'bones':len(rig.data.bones),'deform_bones':sum(b.use_deform for b in rig.data.bones),'meshes':len(character),'weight_checks':{},'ik_checks':{}}
for obj in character:
    totals=[sum(g.weight for g in v.groups) for v in obj.data.vertices]
    report['weight_checks'][obj.name]={'vertices':len(totals),'max_sum_error':max(abs(v-1) for v in totals),'unweighted':sum(v<.99 for v in totals)}
    assert report['weight_checks'][obj.name]['unweighted']==0
    assert report['weight_checks'][obj.name]['max_sum_error']<1e-5
    for v in obj.data.vertices:assert all(math.isfinite(x) for x in v.co)
mins=[];maxs=[]
for frame in [1,13,25,49,61,97,121,145]:
    scene.frame_set(frame);graph=bpy.context.evaluated_depsgraph_get()
    for obj in character:
        evaluated=obj.evaluated_get(graph);mesh=evaluated.to_mesh();points=[evaluated.matrix_world@v.co for v in mesh.vertices]
        assert all(math.isfinite(x) for p in points for x in p)
        mins.append(min(p.z for p in points));maxs.append(max(p.z for p in points));evaluated.to_mesh_clear()
report['evaluated_meshes_finite']=True;report['height_range_m']=[min(mins),max(maxs)]
rig.animation_data_clear()
for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
bpy.context.view_layer.update()
for side,sign in [('L',1),('R',-1)]:
    for part,lower in [('Hand','Forearm'),('Foot','Calf')]:
        ctrl=rig.pose.bones[f'CTRL_{side}_{part}_IK'];old=ctrl.matrix.copy();m=old.copy()
        m.translation+=Vector((0,-sign*.025,.025) if part=='Hand' else (.025,0,.035));ctrl.matrix=m
        constraint=rig.pose.bones[f'{side}_{lower}'].constraints['Optional_IK_'+part];constraint.influence=1;bpy.context.view_layer.update()
        error=(rig.pose.bones[f'{side}_{lower}'].tail-ctrl.head).length
        report['ik_checks'][side+'_'+part]={'endpoint_error_m':error,'passed':error<.003}
        assert error<.003,(side,part,error)
        constraint.influence=0;ctrl.matrix=old;bpy.context.view_layer.update()
report['finger_bones_with_weights']=sum(1 for g in body.vertex_groups if any(d in g.name for d in ['Thumb_','Index_','Middle_','Ring_','Little_']) and any(any(w.group==g.index and w.weight>.01 for w in v.groups) for v in body.data.vertices))
assert report['finger_bones_with_weights']==30
(OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('DETAIL_VALIDATION_PASS',json.dumps(report))
