"""Render actual mesh edges for topology review, never edit or save source mesh."""
import argparse
import bpy
import sys
import json
from collections import Counter
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,required=True)
p.add_argument('--kind',choices=['fullbody','head','hand','hair'],default='fullbody')
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.folder.resolve()
if not out.is_relative_to(ROOT): raise RuntimeError('review_folder_outside_project')
bpy.ops.wm.open_mainfile(filepath=str(out/'review.blend'),load_ui=False,use_scripts=False)
scene=bpy.context.scene;camera=scene.camera
meshes=[o for o in scene.objects if o.type=='MESH']
points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
low=Vector([min(v[i] for v in points) for i in range(3)])
high=Vector([max(v[i] for v in points) for i in range(3)])
height=high.z-low.z
topology=[]
for o in meshes:
    m=o.data;parent=list(range(len(m.vertices)))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for edge in m.edges:
        a,b=map(find,edge.vertices);parent[a]=b
    groups={}
    for v in m.vertices: groups.setdefault(find(v.index),[]).append(o.matrix_world@v.co)
    islands=[]
    for vertices in groups.values():
        islands.append({'vertices':len(vertices),'world_min':[min(v[i] for v in vertices) for i in range(3)],
                        'world_max':[max(v[i] for v in vertices) for i in range(3)]})
    uses=Counter(tuple(sorted(e)) for p in m.polygons for e in p.edge_keys)
    bad=[e for e,n in uses.items() if n>2]
    boundary=[e for e,n in uses.items() if n==1]
    topology.append({'object':o.name,'components':sorted(islands,key=lambda x:-x['vertices']),
        'boundary_edges':len(boundary),'nonmanifold_edges':len(bad),
        'nonmanifold_edge_world_midpoints':[list(o.matrix_world@((m.vertices[a].co+m.vertices[b].co)/2)) for a,b in bad],
        'boundary_edge_world_midpoints':[list(o.matrix_world@((m.vertices[a].co+m.vertices[b].co)/2)) for a,b in boundary]})
(out/'topology-detail.json').write_text(json.dumps(topology,indent=2),encoding='utf-8')
def material(name,color):
    m=bpy.data.materials.new(name);m.use_nodes=True
    m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*color,1)
    m.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.8
    return m
base=material('Topology Clay',(.58,.61,.63));wire=material('Actual Mesh Edges',(.018,.055,.066))
for o in meshes:
    o.data.materials.clear();o.data.materials.append(base)
    copy=o.copy();copy.data=o.data.copy();scene.collection.objects.link(copy)
    copy.data.materials.clear();copy.data.materials.append(wire)
    mod=copy.modifiers.new('Render-only polygon edge overlay','WIREFRAME')
    mod.thickness=height*.00035;mod.use_replace=True;mod.use_even_offset=True
    mod.offset=1
scene.render.resolution_x=1100;scene.render.resolution_y=1100
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
    for d in prefs.devices: d.use=d.type=='CUDA'
    scene.cycles.device='GPU' if any(d.type=='CUDA' for d in prefs.devices) else 'CPU'
except Exception: scene.cycles.device='CPU'
regions=[('fullbody',points),('face',[v for v in points if v.z>low.z+height*.77])] if args.kind=='fullbody' else [('overview',points)]
middle=(low+high)/2
for sign,name in ([(1,'hand-positive-y'),(-1,'hand-negative-y')] if args.kind=='fullbody' else []):
    regions.append((name,[v for v in points if sign*(v.y-middle.y)>(high.y-low.y)*.36 and low.z+height*.30<v.z<low.z+height*.63]))
for name,region in regions:
    center=Vector([(min(v[i] for v in region)+max(v[i] for v in region))/2 for i in range(3)])
    offset=Vector((4,-.5,.25))
    if name.startswith('hand-'): offset=Vector((2,4 if name=='hand-positive-y' else -4,1.2))
    camera.location=center+offset*height
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    basis=camera.rotation_euler.to_matrix().transposed();projected=[basis@(v-center) for v in region]
    camera.data.ortho_scale=max(max(v.x for v in projected)-min(v.x for v in projected),max(v.y for v in projected)-min(v.y for v in projected))*1.15
    scene.render.filepath=str(out/('wire-'+name+'.png'))
    bpy.ops.render.render(write_still=True)
    print('TOPOLOGY_RENDER',name,flush=True)
