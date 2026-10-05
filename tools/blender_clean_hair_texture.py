"""Bake a continuous reference-brown hair material on original P2 UVs.

The donor hair has different locks: projecting its textures leaves visible
patches. Author subtle continuous object-space color instead; geometry stays.
"""
from pathlib import Path
import json
import bpy
ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'art/characters/explorer_b_fullbody_v2/06_textured_parts/hair'
bpy.ops.wm.open_mainfile(filepath=str(FOLDER/'hair_textured.blend'))
obj = next(o for o in bpy.data.objects if o.type == 'MESH')
mat = obj.data.materials[0]
nodes, links = mat.node_tree.nodes, mat.node_tree.links
bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
base = nodes.get('BaseColor')
rough = nodes.get('Roughness')
texco = nodes.new('ShaderNodeTexCoord')
noise = nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 3.5
noise.inputs['Detail'].default_value = 1
links.new(texco.outputs['Generated'], noise.inputs['Vector'])
ramp = nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (.075,.033,.017,1)
ramp.color_ramp.elements[1].color = (.115,.059,.033,1)
links.new(noise.outputs['Fac'], ramp.inputs[0])
emission = nodes.new('ShaderNodeEmission')
links.new(emission.outputs[0], output.inputs['Surface'])
links.new(ramp.outputs['Color'], emission.inputs['Color'])
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
scene = bpy.context.scene
scene.render.bake.use_selected_to_active = False
scene.render.bake.margin = 24
nodes.active = base
base.image = bpy.data.images.new('hair_BaseColor_Continuous',4096,4096,alpha=False)
base.image.colorspace_settings.name = 'sRGB'
bpy.ops.object.bake(type='EMIT')
base.image.filepath_raw = str(FOLDER/'textures/hair_BaseColor.png')
base.image.file_format = 'PNG'
base.image.save()
links.remove(emission.inputs['Color'].links[0])
emission.inputs['Color'].default_value = (.58,.58,.58,1)
nodes.active = rough
rough.image = bpy.data.images.new('hair_Roughness_Continuous',2048,2048,alpha=False)
rough.image.colorspace_settings.name = 'Non-Color'
bpy.ops.object.bake(type='EMIT')
rough.image.filepath_raw = str(FOLDER/'textures/hair_Roughness.png')
rough.image.file_format = 'PNG'
rough.image.save()
links.new(bsdf.outputs['BSDF'],output.inputs['Surface'])
bsdf.inputs['Specular IOR Level'].default_value = .3
for node in (texco,noise,ramp,emission):
    nodes.remove(node)
for node in nodes:
    if node.type == 'NORMAL_MAP':
        node.inputs['Strength'].default_value = 0
bpy.ops.file.pack_all()
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(FOLDER/'hair_textured.blend'))
path = FOLDER/'texture-transfer.json'
report = json.loads(path.read_text(encoding='utf-8'))
report['color_texture_method'] = 'Blender authored continuous object-space reference-brown material baked to original P2 UV'
report['rejected_projection_reason'] = 'Donor hair-lock geometry differs: projection caused color and roughness patches'
report['normal_strength'] = 0
path.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('CONTINUOUS_HAIR_TEXTURE_BAKED',flush=True)
