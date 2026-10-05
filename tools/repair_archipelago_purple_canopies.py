"""Use texture colors to repair purple canopy surfaces without changing source images."""
import bpy
import bmesh
import json
import math
import numpy as np
from pathlib import Path
import shutil
import sys
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
asset=sys.argv[sys.argv.index('--')+1]
assert asset in ['08_gazebo','14_stage']
stem=asset.split('_',1)[1]
OUT=ROOT/'art/maps/archipelago_objects_v1'/asset
LAB=ROOT/'labs/archipelago_object_lab'
bpy.ops.wm.open_mainfile(filepath=str(OUT/(stem+'.blend')))
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
colors=np.load(OUT/'texture_color_audit.npy')
uv=obj.data.uv_layers.active.data
purple=[]
for p in obj.data.polygons:
    if p.material_index!=0 or p.center.z<2.8:
        continue
    point=sum((uv[i].uv for i in p.loop_indices),Vector((0,0)))/len(p.loop_indices)
    r,g,b=colors[int((1-point.y)%1*255),int(point.x%1*255)].astype(float)
    is_gold_or_wood = r>b*1.3 and g>b*1.18
    if not is_gold_or_wood:
        purple.append(p.index)
assert len(purple)>100
mat=bpy.data.materials.new('Matte purple canopy')
mat.diffuse_color=(.08,.018,.17,1)
mat.use_nodes=True
p=mat.node_tree.nodes.get('Principled BSDF')
p.inputs['Base Color'].default_value=(.08,.018,.17,1)
p.inputs['Roughness'].default_value=.72
mat.use_backface_culling=False
obj.data.materials.append(mat)
index=len(obj.data.materials)-1
if asset=='08_gazebo':
    for face in purple:
        obj.data.polygons[face].material_index=index
    # Fill the small rim gap left by the defective source deck.
    bpy.ops.mesh.primitive_cylinder_add(vertices=128,radius=2.62,depth=.018,location=(0,0,.588))
    rim=bpy.context.object
    rim.name='Oak deck rim backing'
    rim.data.materials.append(obj.data.materials[2])
    repair={'purple_canopy_matte':True,'deck_rim_closed':True}
else:
    positions=np.array([obj.data.vertices[i].co[:] for face in purple for i in obj.data.polygons[face].vertices])
    lo=positions.min(axis=0)
    hi=positions.max(axis=0)
    center=(lo+hi)/2
    points=np.unique(np.round(positions,3),axis=0)
    rel=points[:,:2]-center[:2]
    angles=np.mod(np.arctan2(rel[:,1],rel[:,0]),2*math.pi)
    radii=np.linalg.norm(rel,axis=1)
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[bm.faces[i] for i in purple],context='FACES')
    bm.to_mesh(obj.data)
    bm.free()
    verts=[]
    faces=[]
    angular=128
    radial=32
    boundary=np.zeros(angular)
    for k in range(angular):
        mask=(np.floor(angles/(2*math.pi)*angular).astype(int)==k)
        if mask.any():
            boundary[k]=radii[mask].max()
    available=np.flatnonzero(boundary)
    boundary=np.interp(np.arange(angular),np.r_[available-angular,available,available+angular],np.tile(boundary[available],3))
    for _ in range(2):
        boundary=(np.roll(boundary,1)+boundary*2+np.roll(boundary,-1))/4
    for j in range(radial+1):
        t=j/radial
        for i in range(angular):
            a=2*math.pi*i/angular
            x=center[0]+boundary[i]*t*math.cos(a)
            y=center[1]+boundary[i]*t*math.sin(a)
            d=(points[:,0]-x)**2+(points[:,1]-y)**2
            weights=np.exp(-(d-d.min())/(2*.23**2))
            z=float(np.dot(weights,points[:,2])/weights.sum())+.006
            verts.append((x,y,z))
    for j in range(radial):
        for i in range(angular):
            a=j*angular+i
            b=j*angular+(i+1)%angular
            faces.append((a,a+angular,b+angular,b))
    mesh=bpy.data.meshes.new('Continuous fabric canopy')
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    cloth=bpy.data.objects.new('Continuous fabric canopy',mesh)
    bpy.context.collection.objects.link(cloth)
    cloth.data.materials.append(mat)
    for p in cloth.data.polygons:
        p.use_smooth=True
    solid=cloth.modifiers.new('Cloth thickness','SOLIDIFY')
    solid.thickness=.012
    bpy.context.view_layer.objects.active=cloth
    bpy.ops.object.modifier_apply(modifier=solid.name)
    # Keep timber and gold but reduce inappropriate full-surface metal response.
    material=obj.data.materials[0]
    principled=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    for key,value in [('Metallic',.08),('Roughness',.62)]:
        sock=principled.inputs[key]
        for link in list(sock.links):
            material.node_tree.links.remove(link)
        sock.default_value=value
    repair={'broken_purple_faces_replaced':len(purple),'continuous_canopy_added':True,'purple_canopy_matte':True}
for o in bpy.context.scene.objects:
    o.select_set(o.type=='MESH')
bpy.context.view_layer.objects.active=obj
bpy.ops.object.join()
obj.data.calc_loop_triangles()
bpy.ops.export_scene.gltf(filepath=str(OUT/(stem+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
shutil.copy2(OUT/(stem+'.glb'),LAB/'assets'/(stem+'.glb'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(stem+'.blend')))
report=json.loads((OUT/'mesh_verification.json').read_text(encoding='utf-8'))
previous=report['local_repairs'] if isinstance(report['local_repairs'],dict) else {}
report.update(vertices=len(obj.data.vertices),triangles=len(obj.data.loop_triangles),materials=len(obj.data.materials),
              local_repairs={**previous,**repair,'original_unchanged':True})
(OUT/'mesh_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('CANOPY_REPAIR_COMPLETE',json.dumps(report['local_repairs']),flush=True)
