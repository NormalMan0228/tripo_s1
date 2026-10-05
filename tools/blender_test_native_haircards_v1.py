"""Small native Blender curve -> ribbon -> UV -> GLB round-trip test. No paid calls."""
import bpy,json,math
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/explorer_b_integrated_face_haircards_v1/haircard_preflight';O.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
data=bpy.data.curves.new('Prepared_groom_guides','CURVE');data.dimensions='3D';data.resolution_u=16
for side in [-1,0,1]:
 s=data.splines.new('BEZIER');s.bezier_points.add(3)
 for i,p in enumerate(s.bezier_points):
  t=i/3;p.co=(side*.055+math.sin(t*math.pi)*.012,.018*math.sin(t*math.pi),.15-.28*t)
  p.handle_left_type=p.handle_right_type='AUTO';p.radius=1-.85*t**4
guides=bpy.data.objects.new('GUIDES_editable_preflight_only',data);bpy.context.collection.objects.link(guides)
ng=bpy.data.node_groups.new('Native_guide_to_UV_ribbon','GeometryNodeTree')
ng.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');ng.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
mod=guides.modifiers.new('Hair_card_ribbons','NODES');mod.node_group=ng
n=ng.nodes;l=ng.links;inp=n.new('NodeGroupInput');out=n.new('NodeGroupOutput')
res=n.new('GeometryNodeResampleCurve');res.mode='COUNT';res.inputs['Count'].default_value=16;l.new(inp.outputs['Geometry'],res.inputs['Curve'])
factor=n.new('GeometryNodeSplineParameter');long=n.new('GeometryNodeStoreNamedAttribute');long.data_type='FLOAT';long.domain='POINT';long.inputs['Name'].default_value='CardV';l.new(res.outputs['Curve'],long.inputs['Geometry']);l.new(factor.outputs['Factor'],long.inputs['Value'])
line=n.new('GeometryNodeCurvePrimitiveLine');line.mode='POINTS';line.inputs['Start'].default_value=(-.012,0,0);line.inputs['End'].default_value=(.012,0,0)
ix=n.new('GeometryNodeInputIndex');cross=n.new('GeometryNodeStoreNamedAttribute');cross.data_type='FLOAT';cross.domain='POINT';cross.inputs['Name'].default_value='CardU';l.new(line.outputs['Curve'],cross.inputs['Geometry']);l.new(ix.outputs['Index'],cross.inputs['Value'])
mesh=n.new('GeometryNodeCurveToMesh');l.new(long.outputs['Geometry'],mesh.inputs['Curve']);l.new(cross.outputs['Geometry'],mesh.inputs['Profile Curve']);l.new(mesh.outputs['Mesh'],out.inputs['Geometry'])
bpy.context.view_layer.update();ev=guides.evaluated_get(bpy.context.evaluated_depsgraph_get());m=bpy.data.meshes.new_from_object(ev)
assert len(m.polygons)==45 and all(len(p.vertices)==4 for p in m.polygons)
u=m.attributes['CardU'];v=m.attributes['CardV'];coords=[(u.data[i].value,v.data[i].value) for i in range(len(m.vertices))]
uv=m.uv_layers.new(name='HairAtlas')
for p in m.polygons:
 for li in p.loop_indices:uv.data[li].uv=coords[m.loops[li].vertex_index]
assert min(c[0] for c in coords)==0 and max(c[0] for c in coords)==1
print('UV_V_RANGE',min(c[1] for c in coords),max(c[1] for c in coords))
assert abs(min(c[1] for c in coords))<1e-5 and abs(max(c[1] for c in coords)-1)<1e-5
cards=bpy.data.objects.new('CARDS_exportable_preflight_only',m);bpy.context.collection.objects.link(cards)
mat=bpy.data.materials.new('Hair_brown_test_only');mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.045,.017,.009,1);m.materials.append(mat)
guides.hide_render=True;guides.hide_set(True)
bpy.ops.object.select_all(action='DESELECT');cards.select_set(True);bpy.context.view_layer.objects.active=cards
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(O/'native_haircard_preflight.blend'))
bpy.ops.export_scene.gltf(filepath=str(O/'native_haircard_preflight.glb'),export_format='GLB',use_selection=True)
before=len(m.loop_triangles) if m.loop_triangles else 90
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(O/'native_haircard_preflight.glb'))
imported=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(imported)==1
m=imported[0].data;assert m.uv_layers
uvcoords=[tuple(x.uv) for x in m.uv_layers.active.data]
assert max(x[0] for x in uvcoords)-min(x[0] for x in uvcoords)>.99
assert max(x[1] for x in uvcoords)-min(x[1] for x in uvcoords)>.99
result={'status':'passed','blender':bpy.app.version_string,'guides':3,'source_quads':45,'export_triangles':len(m.polygons),'uv_preserved':True,'gltf_roundtrip':True,'paid_calls':0,'scope':'Synthetic guide-to-card mechanism test only. Not the new hairstyle and not automatic extraction from arbitrary Tripo solids.','next':['Generate and inspect separate Tripo hair','Create groom guides fitted to that silhouette','Bake or author strand color/alpha atlas','Arrange layered ribbon cards and validate face clearance, silhouette and transparency in Godot']}
(O/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
