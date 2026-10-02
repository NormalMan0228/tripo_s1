"""Rounded, scalloped cedar branch tiers; public developer art only."""
import bpy,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/authored-environment';OUT.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
vertices=[];faces=[];shades=[];segments=40
profile=[(.1,-.08),(.76,-.08),(.97,-.02),(1,.08),(.91,.24),(.64,.52),(.34,.82),(.09,1.1),(.012,1.16)]
for tier in range(4):
    radius=1.2-tier*.245;base=1.08+tier*.64;offset=len(vertices)
    for ring,(r,z) in enumerate(profile):
        for index in range(segments):
            a=index*math.tau/segments+tier*.73
            wave=1+.07*math.cos(a*5+tier*.7)+.025*math.sin(a*9)
            droop=-.05*math.cos(a*5+tier*.7)*r
            vertices.append((math.cos(a)*r*radius*wave+tier*.028,math.sin(a)*r*radius*wave,base+z+droop))
            shade=.78+.15*tier/3+.06*max(0,min(1,z));shades.append(shade)
    for ring in range(len(profile)-1):
        for index in range(segments):
            a=offset+ring*segments+index;b=offset+ring*segments+(index+1)%segments
            faces.append((a,b,b+segments,a+segments))
    faces.append(tuple(offset+i for i in reversed(range(segments))))
    faces.append(tuple(offset+(len(profile)-1)*segments+i for i in range(segments)))
mesh=bpy.data.meshes.new('Scalloped cedar tiers');mesh.from_pydata(vertices,[],faces);mesh.update()
ob=bpy.data.objects.new('Cedar crown',mesh);bpy.context.collection.objects.link(ob)
colors=mesh.color_attributes.new(name='Tint',type='FLOAT_COLOR',domain='POINT')
for color,shade in zip(colors.data,shades):color.color=(shade,shade,shade,1)
for polygon in mesh.polygons:polygon.use_smooth=True
m=bpy.data.materials.new('Cedar');m.diffuse_color=(.13,.28,.19,1);m.use_nodes=True
m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=m.diffuse_color
m.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.96
mesh.materials.append(m)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'storybook-cedar-v1.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'game/assets/storybook_cedar_crown_v1.glb'),export_format='GLB',export_yup=True,export_animations=False,export_vertex_color='ACTIVE')
print('CEDAR vertices',len(mesh.vertices),'surfaces',len(mesh.materials))
