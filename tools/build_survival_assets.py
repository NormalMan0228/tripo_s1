"""Turn raw Tripo survival props into the game set (run inside Blender, then post-process in Python).

  blender -b --python tools/build_survival_assets.py -- [--only id ...]
  .tools/art-venv/Scripts/python.exe tools/build_survival_assets.py --post [--only id ...] [--delete-raw]
  Godot --headless --path game --import; then --imports (VRAM compression, size limits, no importer LODs)
  and import again.

Blender pass, per prop (artifacts/survival-assets/jobs/<id>/tripo-original.glb):
  * joins all parts, welds positions (face-corner UVs kept), closes small open boundary loops (cracks the
    survival camera could see through) with attribute-filled faces, and records what was closed;
  * scales to the authored size (height or longest horizontal side), puts the base on y=0 and the pivot at
    the trunk (trees: centroid of the lowest band) or the footprint centre;
  * LOD0: decimated to the game budget below; LOD1: ~35% of that, geometry only (runtime reuses LOD0's
    material) for the zoomed-out camera.
Post pass (plain Python): base colour -> 1024 px JPEG, normal map -> 512 px, ORM dropped (matte constant
roughness), so each prop is ~1 MB and imports as VRAM-compressed textures; writes manifest.json.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / 'artifacts/survival-assets/jobs'
OUT = ROOT / 'game/maps/survival/assets'
REPORT = ROOT / 'artifacts/survival-assets/build_report.json'

# Triangle budget of LOD0 (LOD1 is LOD1_RATIO of it).
BUDGET = {
    'pine_tall': 6000, 'oak_broad': 7000, 'birch_slim': 5000, 'bush_round': 2200, 'berry_bush': 3200,
    'fiber_grass': 2600, 'stone_pile': 2400, 'fern_clump': 2000, 'mushroom_cluster': 1600, 'fallen_log': 2600,
    'tree_stump': 1800, 'mossy_boulder': 3000, 'signpost': 1600, 'log_bench': 1400, 'camp_supplies': 3200,
    'firewood_pile': 2400, 'forest_ruin': 9000, 'sandstone_cliff': 4500, 'sandstone_boulder': 2400,
    'cut_blocks': 2000, 'mine_cart': 3000, 'quarry_crane': 9000, 'dead_tree': 3500, 'dry_shrub': 2200,
    'ember_rock': 2400, 'tool_rack': 3000, 'snow_pine': 6000, 'ice_crystal': 2000, 'snow_boulder': 2400,
    'frost_shrub': 2200, 'snowman': 2000, 'sled': 2600, 'sled_empty': 2600, 'snow_fence': 1800, 'frost_shrine': 8000,
}
LOD1_RATIO = .35
TRUNK_PIVOT = {'pine_tall', 'oak_broad', 'birch_slim', 'dead_tree', 'snow_pine'}
FILL_SIDES = 48  # boundary loops up to this many edges are closed


def items():
    sys.path.insert(0, str(ROOT / 'tools'))
    import importlib.util
    spec = importlib.util.spec_from_file_location('survival_gen', ROOT / 'tools/generate_survival_assets.py')
    # The generator imports the server package and httpx; Blender's Python has neither, so parse ITEMS only.
    source = (ROOT / 'tools/generate_survival_assets.py').read_text(encoding='utf-8')
    start = source.index('ITEMS = [')
    end = source.index('BY_ID = ')
    scope = {'H3': 'H3', 'P2': 'P2'}
    exec(source[start:end], scope)
    return scope['ITEMS']


def blender_pass(only):
    import bpy
    import bmesh
    from mathutils import Vector
    OUT.mkdir(parents=True, exist_ok=True)
    report = json.loads(REPORT.read_text(encoding='utf-8')) if REPORT.exists() else {}
    for item in items():
        ident = item['id']
        if only and ident not in only:
            continue
        raw = JOBS / ident / 'tripo-original.glb'
        if not raw.exists():
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(raw))
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        bpy.ops.object.select_all(action='DESELECT')
        for obj in meshes:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        if len(meshes) > 1:
            bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        # Unparent (keeps transform) and bake every transform into the vertices.
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        for other in [o for o in bpy.context.scene.objects if o != obj]:
            bpy.data.objects.remove(other, do_unlink=True)
        mesh = obj.data
        source_triangles = sum(len(p.vertices) - 2 for p in mesh.polygons)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        boundary = [e for e in bm.edges if e.is_boundary]
        loops_before = _count_loops(boundary)
        filled = bmesh.ops.holes_fill(bm, edges=boundary, sides=FILL_SIDES)
        new_faces = filled.get('faces', [])
        if new_faces:
            bmesh.ops.triangulate(bm, faces=new_faces)
        loops_after = _count_loops([e for e in bm.edges if e.is_boundary])
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        # Size, base and pivot.
        coords = [v.co.copy() for v in mesh.vertices]
        lo = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
        hi = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
        size = hi - lo
        measure, metres = item['measure']
        source = size.z if measure == 'height' else max(size.x, size.y)
        factor = metres / max(source, 1e-6)
        if ident in TRUNK_PIVOT:
            band = lo.z + size.z * .08
            low = [c for c in coords if c.z <= band] or coords
            pivot = Vector((sum(c.x for c in low) / len(low), sum(c.y for c in low) / len(low), lo.z))
        else:
            pivot = Vector(((lo.x + hi.x) * .5, (lo.y + hi.y) * .5, lo.z))
        for v in mesh.vertices:
            v.co = (v.co - pivot) * factor
        mesh.update()
        # Normals: drop imported split normals, smooth by angle after decimation.
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        except RuntimeError:
            pass
        lod0_triangles = _decimate(obj, BUDGET.get(ident, 3000))
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(48))
        obj.name = ident
        mesh.name = ident
        dims = obj.dimensions
        bpy.ops.export_scene.gltf(filepath=str(OUT / (ident + '.glb')), export_format='GLB', use_selection=True,
                                  export_materials='EXPORT', export_yup=True, export_apply=True)
        lod1_triangles = _decimate(obj, int(BUDGET.get(ident, 3000) * LOD1_RATIO))
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(48))
        for mat in obj.data.materials:
            if mat and mat.use_nodes:
                for node in list(mat.node_tree.nodes):
                    if node.type == 'TEX_IMAGE':
                        mat.node_tree.nodes.remove(node)
        bpy.ops.export_scene.gltf(filepath=str(OUT / (ident + '_lod1.glb')), export_format='GLB', use_selection=True,
                                  export_materials='EXPORT', export_yup=True, export_apply=True)
        report[ident] = {'source_triangles': source_triangles, 'lod0_triangles': lod0_triangles,
                         'lod1_triangles': lod1_triangles, 'open_loops_before': loops_before,
                         'open_loops_after': loops_after, 'faces_added_closing_holes': len(new_faces),
                         'scale_factor': round(factor, 5), 'size_m': [round(dims.x, 3), round(dims.z, 3), round(dims.y, 3)],
                         'pivot': 'trunk' if ident in TRUNK_PIVOT else 'footprint_centre'}
        print('SURVIVAL_ASSET_BUILT', ident, json.dumps(report[ident]), flush=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1), encoding='utf-8')


def _count_loops(edges):
    """Open boundary loops of three or more edges (two-edge slits are zero-area weld seams)."""
    edges = set(edges)
    seen, loops = set(), 0
    for edge in edges:
        if edge in seen:
            continue
        size, stack = 0, [edge]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            size += 1
            for vert in current.verts:
                for link in vert.link_edges:
                    if link in edges and link not in seen:
                        stack.append(link)
        loops += size >= 3
    return loops


def _decimate(obj, budget):
    import bpy
    before = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    if before > budget:
        mod = obj.modifiers.new('budget', 'DECIMATE')
        mod.ratio = budget / before
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.validate(clean_customdata=False)
    obj.data.update()
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


# ---------------------------------------------------------------- post pass (no Blender)
def post_pass(only, delete_raw):
    import io
    import hashlib
    from PIL import Image
    sys.path.insert(0, str(ROOT))
    import importlib.util
    spec = importlib.util.spec_from_file_location('interior_tools', ROOT / 'tools/generate_interior_assets.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    from server.provider import validate_glb
    report = json.loads(REPORT.read_text(encoding='utf-8')) if REPORT.exists() else {}
    manifest_items = []
    for item in items():
        ident = item['id']
        path = OUT / (ident + '.glb')
        if not path.exists():
            continue
        if not only or ident in only:
            doc, binary = base.glb_parts(path.read_bytes())
            views = [binary[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']] for v in doc['bufferViews']]
            roles = {}
            for material in doc.get('materials', []):
                pbr = material.get('pbrMetallicRoughness', {})
                if 'baseColorTexture' in pbr:
                    roles[doc['textures'][pbr['baseColorTexture']['index']]['source']] = 'color'
                if 'normalTexture' in material:
                    roles.setdefault(doc['textures'][material['normalTexture']['index']]['source'], 'normal')
                for key in ('metallicRoughnessTexture',):
                    if key in pbr:
                        roles.setdefault(doc['textures'][pbr[key]['index']]['source'], 'orm')
                        del pbr[key]
                if 'occlusionTexture' in material:
                    roles.setdefault(doc['textures'][material['occlusionTexture']['index']]['source'], 'orm')
                    del material['occlusionTexture']
                pbr['metallicFactor'] = 0.0
                pbr['roughnessFactor'] = 0.86
            for index, image in enumerate(doc.get('images', [])):
                role = roles.get(index, 'orm')
                side = {'color': 1024, 'normal': 512, 'orm': 4}[role]
                with Image.open(io.BytesIO(views[image['bufferView']])) as source:
                    already = source.format == 'JPEG' and max(source.size) <= side
                    picture = source.convert('RGB')
                if already:
                    continue  # processed before: no second JPEG generation
                if max(picture.size) > side:
                    picture = picture.resize((side, side), Image.LANCZOS)
                out = io.BytesIO()
                picture.save(out, format='JPEG', quality=90 if role == 'color' else 92, optimize=True)
                views[image['bufferView']] = out.getvalue()
                image['mimeType'] = 'image/jpeg'
            blob = base.build_glb(doc, views)
            stats = {}
            validate_glb(blob, allow_textures=True, stats=stats)
            path.write_bytes(blob)
            report.setdefault(ident, {})['texture_pixels'] = stats.get('texture_pixels')
        result_path = JOBS / ident / 'result.json'
        result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {}
        lod1 = OUT / (ident + '_lod1.glb')
        entry = report.get(ident, {})
        manifest_items.append({
            'id': ident, 'map': item['map'], 'file': 'res://maps/survival/assets/%s.glb' % ident,
            'lod1': 'res://maps/survival/assets/%s_lod1.glb' % ident if lod1.exists() else None,
            'model': 'Tripo P2 textured' if item['model'] == 'P2' else 'Tripo H3 (v3.1) textured',
            'credits_consumed': result.get('credits_consumed'), 'task_id': result.get('task_id'),
            'size_m': entry.get('size_m'), 'lod0_triangles': entry.get('lod0_triangles'),
            'lod1_triangles': entry.get('lod1_triangles'), 'holes_closed_faces': entry.get('faces_added_closing_holes'),
            'open_loops_before': entry.get('open_loops_before'), 'open_loops_after': entry.get('open_loops_after'),
            'bytes': path.stat().st_size + (lod1.stat().st_size if lod1.exists() else 0),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'description': item['text']})
        if delete_raw and (not only or ident in only):
            raw = JOBS / ident / 'tripo-original.glb'
            if raw.exists():
                raw.unlink()
    REPORT.write_text(json.dumps(report, indent=1), encoding='utf-8')
    total = sum(float(i['credits_consumed'] or 0) for i in manifest_items)
    (OUT / 'manifest.json').write_text(json.dumps({
        'version': 1, 'source': 'Tripo text-to-model via tools/generate_survival_assets.py; game set by '
                                'tools/build_survival_assets.py (Blender + post pass)',
        'notes': 'glTF +Y up, metres, base on y=0, pivot at trunk/footprint centre. LOD1 is geometry only; '
                 'the runtime reuses LOD0 materials. Raw downloads are deleted after the build.',
        'total_credits_consumed': total, 'items': manifest_items}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'items': len(manifest_items), 'credits': total,
                      'bytes': sum(i['bytes'] for i in manifest_items)}))


def configure_imports():
    """VRAM-compressed (BPTC/S3TC) textures with mipmaps and size limits; no importer LODs (LOD1 files are ours)."""
    import re
    changed = 0
    for path in OUT.glob('*.import'):
        source = path.read_text(encoding='utf-8')
        edited = source
        if path.name.endswith('.glb.import'):
            edited = re.sub(r'(?m)^meshes/generate_lods=.*$', 'meshes/generate_lods=false', edited)
        else:
            normal = '_NormalGL_' in path.name
            edited = re.sub(r'(?m)^compress/mode=.*$', 'compress/mode=2', edited)
            edited = re.sub(r'(?m)^compress/normal_map=.*$', 'compress/normal_map=1' if normal else 'compress/normal_map=2', edited)
            edited = re.sub(r'(?m)^mipmaps/generate=.*$', 'mipmaps/generate=true', edited)
            edited = re.sub(r'(?m)^process/size_limit=.*$', 'process/size_limit=%d' % (512 if normal else 1024), edited)
        if edited != source:
            path.write_text(edited, encoding='utf-8')
            changed += 1
    print('SURVIVAL_IMPORTS_CONFIGURED', changed)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    only = set()
    if '--only' in argv:
        only = {a for a in argv[argv.index('--only') + 1:] if not a.startswith('--')}
    if '--imports' in argv:
        configure_imports()
    elif '--post' in argv:
        post_pass(only, '--delete-raw' in argv)
    else:
        blender_pass(only)
