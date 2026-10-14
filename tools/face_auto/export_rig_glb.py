"""Export the rigged head (face + eyes + lid parts/bones + mouth parts) to glTF for Godot, with plain colours.
Also writes <out>.lids.json: per lid bone the closing angle and sign (blink = rotate about the bone's own Y axis).
Usage: blender -b <rig_mouth.blend> -P export_rig_glb.py -- <lid_pose.json> <out.glb>
"""
import bpy, sys, json
a = sys.argv[sys.argv.index('--') + 1:]
POSE, OUT = a[0], a[1]
cols = {'skin': (0.86, 0.72, 0.64, 1), 'mouth_inner': (0.35, 0.08, 0.1, 1), 'eye': (0.95, 0.95, 0.95, 1),
        'teeth': (0.97, 0.96, 0.9, 1), 'tongue': (0.78, 0.35, 0.4, 1)}
def pbr(name, rgba):
    m = bpy.data.materials.get(name + '_pbr') or bpy.data.materials.new(name + '_pbr'); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF'); b.inputs['Base Color'].default_value = rgba; b.inputs['Roughness'].default_value = 0.6
    return m
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    if o.name == 'face':
        for i, m in enumerate(o.data.materials):
            o.data.materials[i] = pbr('mouth_inner' if (m and m.name == 'mouth_inner') else 'skin', cols['mouth_inner' if (m and m.name == 'mouth_inner') else 'skin'])
        if not o.data.materials: o.data.materials.append(pbr('skin', cols['skin']))
    else:
        key = 'eye' if o.name == 'eyes' else 'teeth' if o.name.startswith('teeth') else 'tongue' if o.name == 'tongue' else 'skin'
        o.data.materials.clear(); o.data.materials.append(pbr(key, cols[key]))
for o in bpy.data.objects:
    if o.type == 'MESH' and o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value = 0.0
for o in bpy.context.view_layer.objects: o.select_set(o.type in ('MESH', 'ARMATURE') and o.name != 'target' and not o.name.startswith('WGT-'))
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_morph=True, export_morph_normal=False,
                          export_skins=True, export_animations=False, export_apply=False)
pose = json.load(open(POSE))
json.dump({'bones': {f'lid_{s}_{k}': {'angle': -al * p['sign']} for s, p in pose.items() for k, al in enumerate(p['alpha_b'])}},
          open(OUT + '.lids.json', 'w'), indent=1)
print('EXPORTED', OUT)
