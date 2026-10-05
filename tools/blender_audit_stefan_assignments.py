"""Inspect private course examples without saving or executing embedded scripts."""
import bpy
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/stefan-course-audit-20261004'
records = json.loads((out / 'assignment-assets.json').read_text(encoding='utf-8'))
results = []
seen = {}
for rec in records:
    if Path(rec['path']).suffix != '.blend':
        continue
    if rec['sha256'] in seen:
        results.append({'path': rec['path'], 'identical_to': seen[rec['sha256']], 'course':rec['course']})
        continue
    seen[rec['sha256']] = rec['path']
    item = {'path':rec['path'], 'course':rec['course'], 'archive':rec['archive'], 'objects':[], 'images':[]}
    try:
        bpy.ops.wm.open_mainfile(filepath=rec['path'], load_ui=False, use_scripts=False)
        item['collections'] = [{'name':c.name,'objects':[o.name for o in c.objects]} for c in bpy.data.collections]
        for obj in bpy.data.objects:
            r = {'name':obj.name, 'type':obj.type, 'parent':obj.parent.name if obj.parent else None,
                 'collections':[c.name for c in obj.users_collection],
                 'location':list(obj.location), 'scale':list(obj.scale), 'dimensions':list(obj.dimensions),
                 'hidden_viewport':obj.hide_viewport, 'hidden_render':obj.hide_render}
            if obj.type == 'MESH':
                m = obj.data
                r.update(vertices=len(m.vertices), edges=len(m.edges), faces=len(m.polygons),
                         triangles=sum(len(p.vertices)-2 for p in m.polygons),
                         uv_layers=[u.name for u in m.uv_layers],
                         materials=[s.material.name if s.material else None for s in obj.material_slots],
                         vertex_groups=len(obj.vertex_groups),
                         shape_keys=[k.name for k in m.shape_keys.key_blocks] if m.shape_keys else [],
                         modifiers=[{'name':x.name,'type':x.type} for x in obj.modifiers])
            elif obj.type == 'ARMATURE':
                r['bones']=[{'name':b.name,'parent':b.parent.name if b.parent else None,'deform':b.use_deform} for b in obj.data.bones]
            item['objects'].append(r)
        item['materials'] = [{'name':m.name,'nodes':[{'type':n.type,'image':n.image.name if getattr(n,'image',None) else None} for n in m.node_tree.nodes] if m.use_nodes else []} for m in bpy.data.materials]
        item['images'] = [{'name':i.name,'size':list(i.size),'colorspace':i.colorspace_settings.name,'packed':bool(i.packed_file),'path':i.filepath} for i in bpy.data.images]
        item['actions']=[{'name':a.name, 'frame_range':list(a.frame_range)} for a in bpy.data.actions]
        item['scene']={'frames':[bpy.context.scene.frame_start,bpy.context.scene.frame_end],'fps':bpy.context.scene.render.fps}
    except Exception as exc:
        item['error'] = str(exc)
    results.append(item)
    (out / 'blend-audit.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    meshes=[o for o in item['objects'] if o['type']=='MESH']
    print('AUDIT',rec['course'],Path(rec['path']).name,'meshes',len(meshes),'triangles',sum(o.get('triangles',0) for o in meshes),'rigs',sum(o['type']=='ARMATURE' for o in item['objects']),'actions',len(item.get('actions',[])),flush=True)
print('FINISHED',len(results),'files',len(seen),'unique',flush=True)
