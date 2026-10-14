import bpy
o = bpy.data.objects["TemplateHead"]
cnt = {g.name: 0 for g in o.vertex_groups}
for v in o.data.vertices:
    for g in v.groups:
        if g.weight > 0.01: cnt[o.vertex_groups[g.group].name] += 1
print("GROUPS", len(cnt), {k: v for k, v in cnt.items() if v and (k in ('ears','lips','scalp') or 'lid' in k or 'lip' in k or 'jaw' in k or 'brow' in k or 'cheek' in k)})
