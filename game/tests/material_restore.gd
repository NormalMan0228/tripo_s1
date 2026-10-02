extends SceneTree
var failures: Array[String]=[]
func check(value: bool,label: String) -> void:
	if not value:failures.append(label)
func _initialize() -> void:
	var rows: Array=JSON.parse_string(FileAccess.get_file_as_string("res://../artifacts/material-cases.json"))
	for value in rows:
		var item=load("res://scripts/asset_assembly.gd").new();var blobs := {}
		for id in value.blobs:blobs[id]=Marshalls.base64_to_raw(value.blobs[id])
		check(item.build(value,blobs),"build material case")
		var originals := {}
		for part in value.plan.parts:
			var mesh: MeshInstance3D=item.surfaces[part.id][0];var mat: StandardMaterial3D=mesh.get_surface_override_material(0)
			var expected := Color.WHITE if value.textured else Color(part.color)
			check(mat.albedo_color.is_equal_approx(expected),"initial material keeps provider color for textures")
			originals[part.id]={"color":mat.albedo_color,"texture":mat.albedo_texture}
		item.paint({"body":"#2674ab","lid":"#2674ab"})
		item.paint({"body":"#2674ab"})
		check(item.surfaces.lid[0].get_surface_override_material(0).albedo_color.is_equal_approx(originals.lid.color),"one part restores true original")
		item.paint({})
		for id in originals:
			var mat: StandardMaterial3D=item.surfaces[id][0].get_surface_override_material(0)
			check(mat.albedo_color.is_equal_approx(originals[id].color) and mat.albedo_texture==originals[id].texture,"all colors restore without changing texture resource")
		item.free()
	print("MATERIAL_RESTORE ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}));quit(0 if failures.is_empty() else 1)
