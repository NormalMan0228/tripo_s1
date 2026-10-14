"""Make geometry-only distant LODs; runtime reuses original full-resolution PBR."""
import json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/maps/archipelago_objects_v1'
DEST=ROOT/'labs/terrain_lab/assets/prop_lods'
DEST.mkdir(exist_ok=True,parents=True)
targets={'37_round_tree':5000,'38_conifer':4500,'39_palm':3500,'40_shrub':1800,'42_white_flowers':1200,'43_yellow_flowers':1200,'44_pink_flowers':1500,'45_reeds':1600,'41_planter':2200,'27_lamp':2200}
reports=[]
for ident,budget in targets.items():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    path=BASE/ident/(ident.split('_',1)[1]+'.glb')
    bpy.ops.import_scene.gltf(filepath=str(path))
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    for obj in objects:
        bpy.context.view_layer.objects.active=obj
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
        # Weld positions while retaining face-corner UVs from the Tripo atlas.
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.remove_doubles(threshold=.00001);bpy.ops.object.mode_set(mode='OBJECT')
        before=sum(len(p.vertices)-2 for p in obj.data.polygons)
        mod=obj.modifiers.new('Distant_Silhouette_LOD','DECIMATE');mod.ratio=min(1,budget/before);mod.use_collapse_triangulate=True
        bpy.ops.object.modifier_apply(modifier=mod.name)
        obj.data.validate(clean_customdata=True)
        obj.data.update()
        for mat in obj.data.materials:
            if mat and mat.use_nodes:
                for node in list(mat.node_tree.nodes):
                    if node.type=='TEX_IMAGE':mat.node_tree.nodes.remove(node)
        after=sum(len(p.vertices)-2 for p in obj.data.polygons)
        reports.append({'id':ident,'source_triangles':before,'lod_triangles':after,'original_unchanged':True,'original_uv_atlas_retained':True})
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(DEST/(ident+'.glb')),export_format='GLB',use_selection=True,export_materials='EXPORT')
    print('PROP_LOD_READY',ident,before,after,flush=True)
(ROOT/'art/maps/archipelago_performance_v1/prop_lods.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
