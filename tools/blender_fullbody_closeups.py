"""Render actual generated head/hands/feet from the saved review scene, no edits."""
import bpy
import json
import argparse
import sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/explorer_b_fullbody_v2/03_generated'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--folder',type=Path)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if args.folder:
    OUT=args.folder.resolve()
    if not OUT.is_relative_to(ROOT): raise RuntimeError('review_folder_outside_project')
bpy.ops.wm.open_mainfile(filepath=str(OUT/'review.blend'),load_ui=False,use_scripts=False)
scene=bpy.context.scene
camera=scene.camera
meshes=[o for o in scene.objects if o.type=='MESH']
points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
low=Vector([min(v[i] for v in points) for i in range(3)])
high=Vector([max(v[i] for v in points) for i in range(3)])
size=high-low
middle=(low+high)/2
scene.render.resolution_x=1000
scene.render.resolution_y=1000
scene.cycles.samples=24
try:
    preferences=bpy.context.preferences.addons['cycles'].preferences
    preferences.compute_device_type='CUDA'
    preferences.get_devices()
    for device in preferences.devices: device.use=device.type=='CUDA'
    scene.cycles.device='GPU' if any(d.type=='CUDA' for d in preferences.devices) else 'CPU'
except Exception: scene.cycles.device='CPU'
original={o.name:list(o.data.materials) for o in meshes}
clay=bpy.data.materials.new('Diagnostic Clay');clay.use_nodes=True
clay.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.46,.48,.51,1)
clay.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.7

def select_region(name):
    if name=='face': return [v for v in points if v.z>low.z+size.z*.77]
    if name=='feet': return [v for v in points if v.z<low.z+size.z*.16]
    sign=1 if name=='hand-positive-y' else -1
    return [v for v in points if sign*(v.y-middle.y)>size.y*.36 and
            low.z+size.z*.30<v.z<low.z+size.z*.63]

records=[]
for name in ('face','hand-positive-y','hand-negative-y','feet'):
    region=select_region(name)
    if not region: raise RuntimeError('empty_closeup_region_'+name)
    rlow=Vector([min(v[i] for v in region) for i in range(3)])
    rhigh=Vector([max(v[i] for v in region) for i in range(3)])
    center=(rlow+rhigh)/2
    for mode in ('material','clay'):
        for o in meshes:
            o.data.materials.clear()
            if mode=='clay': o.data.materials.append(clay)
            else:
                for m in original[o.name]:o.data.materials.append(m)
        offset=Vector((4,-.75,.3)) if name=='face' else Vector((4,-1,.8))
        if name=='feet':offset=Vector((4,-2,2))
        camera.location=center+offset*size.z
        camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        basis=camera.rotation_euler.to_matrix().transposed()
        projected=[basis@(v-center) for v in region]
        width=max(v.x for v in projected)-min(v.x for v in projected)
        height=max(v.y for v in projected)-min(v.y for v in projected)
        camera.data.ortho_scale=max(width,height)*1.22
        filename='detail-'+name+'-'+mode+'.png'
        scene.render.filepath=str(OUT/filename)
        bpy.ops.render.render(write_still=True)
        records.append(dict(region=name,mode=mode,file=filename,bounds=[list(rlow),list(rhigh)]))
        print('CLOSEUP',filename,flush=True)
(OUT/'closeup-record.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print('CLOSEUPS_FINISHED',len(records),flush=True)
