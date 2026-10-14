import bpy
b = bpy.data.objects["Template_Face_Body"]
print("GROUPS", [g.name for g in b.vertex_groups if not g.name.startswith(("joint-", "DEF-", "ORG-", "MCH-"))])
print("NDEF", len([g for g in b.vertex_groups if g.name.startswith("DEF-")]), [g.name for g in b.vertex_groups if "ear" in g.name.lower() or "lid" in g.name.lower() or "lip" in g.name.lower()][:40])
