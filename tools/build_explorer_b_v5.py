"""Developer B-v5: clean Tripo mesh, semantic materials, authored motion and fingers.

No player runtime processing, no external animation clips and no facial add-ons.
"""
import bpy, bmesh, math, json
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/characters/explorer-b-v5'
DEST=ROOT/'labs/character_lab/assets'
DEST.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/'body/rig-original.glb'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
body=next(o for o in bpy.context.scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers))
for o in list(bpy.context.scene.objects):
    if o not in [rig,body]:bpy.data.objects.remove(o,do_unlink=True)
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
rig.animation_data_clear();rig.animation_data_create()
rig.name='Explorer_B_V5_Rig';body.name='Explorer_B_V5_Surface'
scene=bpy.context.scene;scene.render.fps=30
for bone in rig.pose.bones:bone.rotation_mode='QUATERNION';bone.matrix_basis=Matrix.Identity(4)
bpy.context.view_layer.update()
source_vertices=len(body.data.vertices)
face_before=[tuple(v.co) for v in body.data.vertices if (body.matrix_world@v.co).z>.77]

# Preserve detailed albedo + normal; separate material response using existing skin groups.
source=body.data.materials[0]
textures=[n.image for n in source.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
color=next((i for i in textures if i.colorspace_settings.name=='sRGB'),None)
pixels=list(color.pixels) if color else []
uv=body.data.uv_layers.active
materials={};counts={}
for name,rough,spec in [('Skin',.60,.28),('Hair',.66,.28),('Jacket',.84,.22),('Pants',.89,.20),('Boots',.73,.28),('Belt',.70,.28)]:
    m=source.copy();m.name='B5_'+name;p=m.node_tree.nodes.get('Principled BSDF')
    for slot,value in [('Metallic',0.0),('Roughness',rough),('Specular IOR Level',spec)]:
        for link in list(p.inputs[slot].links):m.node_tree.links.remove(link)
        p.inputs[slot].default_value=value
    for node in m.node_tree.nodes:
        if node.type=='NORMAL_MAP':node.inputs['Strength'].default_value=.12 if name=='Skin' else .35 if name=='Hair' else .65
    materials[name]=m;counts[name]=0
body.data.materials.clear()
for m in materials.values():body.data.materials.append(m)
names=list(materials)
for poly in body.data.polygons:
    points=[body.matrix_world@body.data.vertices[i].co for i in poly.vertices]
    center=sum(points,Vector())/len(points)
    influence={}
    for index in poly.vertices:
        for g in body.data.vertices[index].groups:
            name=body.vertex_groups[g.group].name
            influence[name]=influence.get(name,0)+g.weight/len(poly.vertices)
    skin_sum=sum(w for n,w in influence.items() if any(k in n for k in ['Hand','Forearm','Head','Neck']))
    rgb=(.5,.5,.5)
    if color and uv:
        xy=sum((uv.data[l].uv for l in poly.loop_indices),Vector((0,0)))/len(poly.loop_indices)
        x=min(color.size[0]-1,max(0,int(xy.x*color.size[0])))
        y=min(color.size[1]-1,max(0,int(xy.y*color.size[1])))
        offset=(y*color.size[0]+x)*4;rgb=pixels[offset:offset+3]
    r,g,b=rgb
    if center.z>.765:
        category='Hair' if max(rgb)<.30 and center.z>.79 else 'Skin'
    elif skin_sum>.65 and (center.z<.62 or abs(center.y)<.07):category='Skin'
    elif center.z<.115:category='Boots'
    elif center.z<.535:category='Pants'
    elif .525<center.z<.575 and abs(center.y)<.115 and max(rgb)<.30:category='Belt'
    else:category='Jacket'
    poly.material_index=names.index(category);poly.use_smooth=True;counts[category]+=1

# Smooth thin fingers with one local subdivision pass, keeping the head/body untouched.
hand_indices=set()
for v in body.data.vertices:
    if sum(g.weight for g in v.groups if body.vertex_groups[g.group].name in ['L_Hand','R_Hand'])>.88:hand_indices.add(v.index)
bm=bmesh.new();bm.from_mesh(body.data);bm.verts.ensure_lookup_table()
deform=bm.verts.layers.deform.active
hand_groups={body.vertex_groups[n].index for n in ['L_Hand','R_Hand']}
def is_hand(vertex):return sum(vertex[deform].get(g,0.0) for g in hand_groups)>.88
bmesh.ops.remove_doubles(bm,verts=[v for v in bm.verts if is_hand(v)],dist=.000001)
edges=[e for e in bm.edges if all(is_hand(v) for v in e.verts)]
for edge in edges:edge.smooth=True
bmesh.ops.subdivide_edges(bm,edges=edges,cuts=1,use_grid_fill=True)
bm.to_mesh(body.data);bm.free();body.data.update()
normals=[tuple(n.vector) for n in body.data.corner_normals]
for i,loop in enumerate(body.data.loops):
    vertex=body.data.vertices[loop.vertex_index]
    if sum(g.weight for g in vertex.groups if g.group in hand_groups)>.88:normals[i]=(0,0,0)
body.data.normals_split_custom_set(normals)

# Place 30 deform bones in each hand's own rest frame, not the old T-pose landmarks.
digits=['Thumb','Index','Middle','Ring','Little'];finger_specs={};hand_regions={}
for side in ['L','R']:
    hand=rig.data.bones[side+'_Hand'];wrist=hand.head_local.copy()
    down=(hand.tail_local-wrist).normalized()
    across=Vector((1,0,0));across=(across-down*across.dot(down)).normalized()
    vertices=[]
    for v in body.data.vertices:
        weight=sum(g.weight for g in v.groups if body.vertex_groups[g.group].name==side+'_Hand')
        if weight>.75:vertices.append(v.index)
    hand_regions[side]=vertices
    positions=[rig.matrix_world.inverted()@body.matrix_world@body.data.vertices[i].co for i in vertices]
    end=max(((p-wrist).dot(down) for p in positions),default=.085)
    start=end*.40;length=end*.55
    span=max(((p-wrist).dot(across) for p in positions),default=.03)-min(((p-wrist).dot(across) for p in positions),default=-.03)
    width=min(.047,max(.028,span*.72))
    for digit,offset,ratio in [('Index',.31,.94),('Middle',.03,1.0),('Ring',-.24,.91),('Little',-.50,.73)]:
        base=wrist+down*start+across*width*offset
        finger_specs[(side,digit)]=([base+down*length*ratio*i/3 for i in range(4)],[])
    thumb=wrist+down*end*.24+across*width*.38
    direction=(down*.62+across*.78).normalized()
    finger_specs[(side,'Thumb')]=([thumb+direction*end*.43*i/3 for i in range(4)],[])
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for (side,digit),(points,names_) in finger_specs.items():
    for i in range(3):
        name=f'{side}_{digit}_{i+1:02d}';b=rig.data.edit_bones.new(name)
        b.head=points[i];b.tail=points[i+1];b.parent=rig.data.edit_bones[side+'_Hand' if i==0 else names_[-1]]
        b.align_roll(Vector((1,0,0)));names_.append(name)
bpy.ops.object.mode_set(mode='OBJECT')
def group(name):return body.vertex_groups.get(name) or body.vertex_groups.new(name=name)
for _,names_ in finger_specs.values():
    for name in names_:group(name)
finger_counts={n:0 for _,nn in finger_specs.values() for n in nn}
for side,indices in hand_regions.items():
    for index in indices:
        vertex=body.data.vertices[index]
        point=rig.matrix_world.inverted()@body.matrix_world@vertex.co
        candidates=[]
        for digit in digits:
            points,nn=finger_specs[(side,digit)];axis=points[-1]-points[0]
            t=(point-points[0]).dot(axis)/axis.length_squared
            distance=(point-(points[0]+axis*max(0,min(1,t)))).length
            candidates.append((distance,digit,t))
        distance,digit,t=min(candidates);points,nn=finger_specs[(side,digit)]
        amount=max(0,min(1,(t+.03)/.35));amount=amount*amount*(3-2*amount)
        if amount<.001:continue
        old={body.vertex_groups[g.group].name:g.weight*(1-amount) for g in vertex.groups}
        along=max(0,min(2,t*3-.5));i=min(1,int(along));fraction=along-i
        old[nn[i]]=old.get(nn[i],0)+amount*(1-fraction)
        old[nn[i+1]]=old.get(nn[i+1],0)+amount*fraction
        for g in list(vertex.groups):body.vertex_groups[g.group].remove([index])
        values=dict(sorted(old.items(),key=lambda kv:kv[1],reverse=True)[:4]);total=sum(values.values())
        for name,value in values.items():
            if value>1e-7:group(name).add([index],value/total,'REPLACE')
            if name in finger_counts and value>.02:finger_counts[name]+=1

# Carry forward the reviewed hand-v4 surface/weights. The generated hand was
# retained in the raw file; it did not meet the close-view deformation standard.
donor_file=ROOT/'artifacts/characters/explorer-b-hand-v4/explorer-b-hand.blend'
with bpy.data.libraries.load(str(donor_file),link=False) as (src,dst):
    dst.objects=['Explorer_B_SkinnedMesh','Explorer_B_Body_Rig']
donor_body,donor_rig=dst.objects
donors=[];donor_matrices={}
for side,indices in hand_regions.items():
    old_hand=donor_rig.data.bones[side+'_Hand'];new_hand=rig.data.bones[side+'_Hand']
    old_indices={v.index for v in donor_body.data.vertices if sum(g.weight for g in v.groups
        if donor_body.vertex_groups[g.group].name==side+'_Hand' or donor_body.vertex_groups[g.group].name.startswith(side+'_')
        and any(d in donor_body.vertex_groups[g.group].name for d in digits))>.85}
    old_axis=(old_hand.tail_local-old_hand.head_local).normalized()
    new_axis=(new_hand.tail_local-new_hand.head_local).normalized()
    old_end=max(((donor_body.matrix_world@donor_body.data.vertices[i].co-old_hand.head_local).dot(old_axis) for i in old_indices))
    new_end=max(((rig.matrix_world.inverted()@body.matrix_world@body.data.vertices[i].co-new_hand.head_local).dot(new_axis) for i in indices))
    factor=new_end/old_end
    rotation=new_hand.matrix_local.to_3x3().normalized()@old_hand.matrix_local.to_3x3().normalized().inverted()
    matrix=Matrix.Translation(new_hand.head_local)@rotation.to_4x4()@Matrix.Scale(factor,4)@Matrix.Translation(-old_hand.head_local)
    donor_matrices[side]=matrix
    polys=[p for p in donor_body.data.polygons if all(i in old_indices for i in p.vertices)]
    used=sorted({i for p in polys for i in p.vertices});mapping={old:new for new,old in enumerate(used)}
    mesh=bpy.data.meshes.new(side+'_Reviewed_Hand_Surface')
    mesh.from_pydata([matrix@donor_body.matrix_world@donor_body.data.vertices[i].co for i in used],[],
        [tuple(mapping[i] for i in p.vertices) for p in polys]);mesh.update()
    obj=bpy.data.objects.new(side+'_Reviewed_Hand_V4',mesh);scene.collection.objects.link(obj)
    obj.parent=rig;obj.matrix_parent_inverse=rig.matrix_world.inverted();obj.matrix_world=Matrix.Identity(4)
    mod=obj.modifiers.new('Original_Skin_Weights','ARMATURE');mod.object=rig
    for material in donor_body.data.materials:
        if not material:continue
        m=material.copy();m.name=side+'_Reviewed_Skin'
        for node in m.node_tree.nodes:
            if node.type=='NORMAL_MAP':node.inputs['Strength'].default_value=.2
        mesh.materials.append(m)
    for old,new in mapping.items():
        for group_data in donor_body.data.vertices[old].groups:
            name=donor_body.vertex_groups[group_data.group].name
            vg=obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
            vg.add([new],group_data.weight,'REPLACE')
    layer=mesh.uv_layers.new(name='Original_Hand_UV')
    original_uv=donor_body.data.uv_layers.active
    for new,old in zip(mesh.polygons,polys):
        new.material_index=old.material_index;new.use_smooth=True
        for loop_a,loop_b in zip(new.loop_indices,old.loop_indices):layer.data[loop_a].uv=original_uv.data[loop_b].uv
    # Imported normals keep the former low-poly hand appearance from returning.
    normal_matrix=rotation
    custom=[]
    for poly in polys:
        custom.extend(normal_matrix@donor_body.data.corner_normals[i].vector for i in poly.loop_indices)
    mesh.normals_split_custom_set(custom);donors.append(obj)
    for digit in digits:
        for i,name in enumerate(finger_specs[(side,digit)][1]):
            if name in donor_rig.data.bones:finger_counts[name]=sum(
                any(donor_body.vertex_groups[g.group].name==name and g.weight>.02 for g in donor_body.data.vertices[v].groups) for v in used)
# Remove only polygons completely inside the replaced hand region.
replace_groups={g.index for g in body.vertex_groups if g.name in ['L_Hand','R_Hand'] or any(d in g.name for d in digits)}
bm=bmesh.new();bm.from_mesh(body.data);deform=bm.verts.layers.deform.active
wrists=[(rig.data.bones[s+'_Hand'].head_local.copy(),
         (rig.data.bones[s+'_Hand'].tail_local-rig.data.bones[s+'_Hand'].head_local).normalized()) for s in ['L','R']]
local_to_rig=rig.matrix_world.inverted()@body.matrix_world
def distal(vertex):
    point=local_to_rig@vertex.co
    wrist,axis=min(wrists,key=lambda pair:(point-pair[0]).length_squared)
    # Keep the original wrist and proximal palm as an overlap under the reviewed
    # surface. Skin weights alone also label forearm vertices as "hand".
    return sum(vertex[deform].get(g,0) for g in replace_groups)>.85 and (point-wrist).dot(axis)>.025
remove=[p for p in bm.faces if all(distal(v) for v in p.verts)]
bmesh.ops.delete(bm,geom=remove,context='FACES');bm.to_mesh(body.data);bm.free();body.data.update()
for vertex in body.data.vertices:
    for side in ['L','R']:
        moved=sum(g.weight for g in vertex.groups if body.vertex_groups[g.group].name.startswith(side+'_')
                  and any(d in body.vertex_groups[g.group].name for d in digits))
        if moved<=0:continue
        for g in list(vertex.groups):
            name=body.vertex_groups[g.group].name
            if name.startswith(side+'_') and any(d in name for d in digits):body.vertex_groups[g.group].remove([vertex.index])
        hand=group(side+'_Hand');existing=next((g.weight for g in vertex.groups if g.group==hand.index),0)
        hand.add([vertex.index],existing+moved,'REPLACE')
assert sorted(face_before)==sorted(tuple(v.co) for v in body.data.vertices if (body.matrix_world@v.co).z>.77), 'Unexpected face geometry edit'
bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for side,matrix in donor_matrices.items():
    for digit in digits:
        for name in finger_specs[(side,digit)][1]:
            old=donor_rig.data.bones[name];new=rig.data.edit_bones[name]
            new.head=matrix@old.head_local;new.tail=matrix@old.tail_local
            new.align_roll(matrix.to_3x3()@old.matrix_local.to_3x3().col[2])
bpy.ops.object.mode_set(mode='OBJECT')
bpy.data.objects.remove(donor_body,do_unlink=True);bpy.data.objects.remove(donor_rig,do_unlink=True)

# Cut both wrist surfaces at clean planes and build a real skinned connecting
# ring. An overlapping shell leaves torn edges when the wrist changes pose.
def ordered_ring(edges,normal):
    vertices=list({v for edge in edges for v in edge.verts})
    center=sum((v.co for v in vertices),Vector())/len(vertices)
    a=normal.cross(Vector((1,0,0)))
    if a.length<.001:a=normal.cross(Vector((0,1,0)))
    a.normalize();b=normal.cross(a).normalized()
    return sorted([v.co.copy() for v in vertices],key=lambda p:math.atan2((p-center).dot(b),(p-center).dot(a)))
def sample_ring(points,count):
    lengths=[(points[(i+1)%len(points)]-p).length for i,p in enumerate(points)]
    perimeter=sum(lengths);result=[]
    for n in range(count):
        distance=perimeter*n/count
        for i,length in enumerate(lengths):
            if distance<=length or i==len(lengths)-1:
                result.append(points[i].lerp(points[(i+1)%len(points)],distance/max(length,.000001)));break
            distance-=length
    return result
for side,hand_obj in zip(['L','R'],donors[:]):
    hand=rig.data.bones[side+'_Hand'];axis=(hand.tail_local-hand.head_local).normalized()
    body_plane=hand.head_local-axis*.006;hand_plane=hand.head_local+axis*.025
    # Restore the complete generated surface just for constructing its wrist.
    # Existing cuts are distal to this plane, so the proximal ring is intact.
    bm=bmesh.new();bm.from_mesh(body.data);deform=bm.verts.layers.deform.active
    ids={g.index for g in body.vertex_groups if g.name==side+'_Hand' or g.name.startswith(side+'_Forearm')}
    selected={v for v in bm.verts if sum(v[deform].get(i,0) for i in ids)>.5}
    geom=list(selected)+[e for e in bm.edges if all(v in selected for v in e.verts)]+[f for f in bm.faces if all(v in selected for v in f.verts)]
    result=bmesh.ops.bisect_plane(bm,geom=geom,dist=.000001,plane_co=body_plane,plane_no=axis,clear_outer=True)
    cut=[e for e in result['geom_cut'] if isinstance(e,bmesh.types.BMEdge)]
    # Weld seam duplicates before reading the boundary.
    if len(cut)<3:raise RuntimeError('Wrist body ring missing: '+side)
    body_ring=ordered_ring(cut,axis)
    body_weights=[(v.co.copy(),{body.vertex_groups[i].name:w for i,w in v[deform].items()}) for e in cut for v in e.verts]
    bm.to_mesh(body.data);bm.free();body.data.update()
    bm=bmesh.new();bm.from_mesh(hand_obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
    result=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.000001,
        plane_co=hand_plane,plane_no=axis,clear_inner=True)
    cut=[e for e in result['geom_cut'] if isinstance(e,bmesh.types.BMEdge)]
    if len(cut)<3:raise RuntimeError('Wrist hand ring missing: '+side)
    hand_ring=ordered_ring(cut,axis)
    bm.to_mesh(hand_obj.data);bm.free();hand_obj.data.update()
    # Bisect/weld invalidates imported corner normals. Recompute smooth normals.
    hand_obj.data.normals_split_custom_set([(0,0,0)]*len(hand_obj.data.loops))
    count=32;a=sample_ring(body_ring,count);b=sample_ring(hand_ring,count)
    # Corresponding circular samples use the same angular origin.
    offset=min(range(count),key=lambda j:sum((a[i]-b[(i+j)%count]).length_squared for i in range(count)))
    b=[b[(i+offset)%count] for i in range(count)]
    verts=[p.lerp(q,t/4) for t in range(5) for p,q in zip(a,b)]
    faces=[]
    for row in range(4):
        for i in range(count):faces.append((row*count+i,row*count+(i+1)%count,(row+1)*count+(i+1)%count,(row+1)*count+i))
    mesh=bpy.data.meshes.new(side+'_Continuous_Wrist');mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(side+'_Wrist_Bridge',mesh);scene.collection.objects.link(obj);obj.parent=rig
    obj.matrix_parent_inverse=rig.matrix_world.inverted();obj.matrix_world=Matrix.Identity(4)
    modifier=obj.modifiers.new('Wrist_Skin','ARMATURE');modifier.object=rig
    for row in range(5):
        for index,point in enumerate(a):
            weights=min(body_weights,key=lambda pair:(pair[0]-point).length_squared)[1]
            values={name:value*(1-row/4) for name,value in weights.items()}
            values[side+'_Hand']=values.get(side+'_Hand',0)+row/4
            for name,value in values.items():
                if value<.000001:continue
                vg=obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
                vg.add([row*count+index],value,'REPLACE')
    skin=bpy.data.materials.new(side+'_Wrist_Skin');skin.use_nodes=True
    principled=skin.node_tree.nodes.get('Principled BSDF');principled.inputs['Base Color'].default_value=(.67,.43,.26,1)
    principled.inputs['Roughness'].default_value=.62;principled.inputs['Specular IOR Level'].default_value=.25
    mesh.materials.append(skin)
    for poly in mesh.polygons:poly.use_smooth=True
    donors.append(obj)

assert sorted(face_before)==sorted(tuple(v.co) for v in body.data.vertices if (body.matrix_world@v.co).z>.77), 'Unexpected face edit after wrist repair'
finger_counts={name:sum(any(o.vertex_groups[g.group].name==name and g.weight>.02 for g in vertex.groups)
    for o in [body]+donors for vertex in o.data.vertices) for _,names_ in finger_specs.values() for name in names_}

# Reuse the algorithm, not animation data: rebuild editable keys for this rig.
TAU=math.tau;source=(ROOT/'tools/blender_explorer_b.py').read_text(encoding='utf-8')
helpers=source[source.index('pb=rig.pose.bones;'):source.index('scene=bpy.context.scene;scene.render.fps=24')]
exec(compile(helpers,'authored_motion_helpers','exec'),globals())
base_pose=pose
def apply_pose(kind,t):
    if kind in ['idle','walk','run']:base_pose('scout' if kind=='idle' else kind,t)
    else:
        base_pose('scout',0)
        amount=envelope(t,.4,1.1,2.1,3.1)
        for side,sign in [('L',1),('R',-1)]:
            wrist=Vector((.035,sign*.16,.50)).lerp(Vector((.18,sign*.095,.67)),amount)
            chain(side+'_Upperarm',side+'_Forearm',side+'_Hand',wrist,(-.6,sign*.7,-.2))
    for (side,digit),(points,nn) in finger_specs.items():
        amount=.10
        if kind in ['hands','reach']:
            amount=envelope(t,.6,1.25,1.95,2.7)*(.35 if kind=='hands' else .25)
        for i,name in enumerate(nn):
            pb[name].rotation_quaternion=Quaternion(Vector((1,0,0)),-math.radians([25,40,25][i])*amount)
    update()
clips=[('idle',6.0),('walk',32/24),('run',20/24),('hands',4.0),('reach',4.0)]
actions={}
for kind,duration in clips:
    rig.animation_data.action=None;previous={}
    frames=round(duration*30)
    for frame in range(frames+1):
        apply_pose(kind,frame/30)
        for bone in pb:
            q=bone.rotation_quaternion
            if bone.name in previous and q.dot(previous[bone.name])<0:q.negate()
            previous[bone.name]=q.copy()
            bone.keyframe_insert('location',frame=frame+1,group=bone.name)
            bone.keyframe_insert('rotation_quaternion',frame=frame+1,group=bone.name)
        if frame==0:rig.animation_data.action.name=kind
    action=rig.animation_data.action;action.use_fake_user=True;actions[kind]=action
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
rig.animation_data.action=actions['idle'];scene.frame_set(1)
for modifier in body.modifiers:
    if modifier.type=='ARMATURE':modifier.use_deform_preserve_volume=False
for poly in body.data.polygons:poly.use_smooth=True
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);body.select_set(True)
for obj in donors:obj.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(DEST/'explorer_b_v5.glb'),export_format='GLB',use_selection=True,
    export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,
    export_anim_slide_to_zero=True,export_def_bones=True,export_materials='EXPORT')
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/source/explorer_b_v5.blend'))
manifest={'generation':'Tripo P2-20260801','generation_credits':120,'rig':'Tripo v1.0-20240301','rig_credits':25,
    'animation':'Blender authored keys rebuilt for this skeleton; no stock animation','source_vertices':source_vertices,
    'vertices':sum(len(o.data.vertices) for o in [body]+donors),'triangles':sum(len(p.vertices)-2 for o in [body]+donors for p in o.data.polygons),
    'bones':len(rig.data.bones),'finger_bones':30,'finger_influenced_vertices':finger_counts,
    'material_faces':counts,'clips':dict(clips),'source_height_m':1.0,'game_height_m':1.7,
    'face':'New generated face, unchanged after import; no added eyeballs, eyelids or mouth mesh',
    'hands':'Reviewed Explorer B hand-v4 geometry, UV and skin weights fitted to the new wrist rest transforms; skinned wrist bridges added; generated hands retained only in raw source',
    'review_status':'First generated version: hand landmarks and joint deformation need visual review; not production approval.'}
(ROOT/'art/explorer-b-v5-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('EXPLORER_B_V5_READY',json.dumps(manifest))
