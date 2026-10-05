extends SceneTree
func _initialize() -> void:
	var scene: Node = load("res://terrain.tscn").instantiate()
	root.add_child(scene)
	inspect.call_deferred(scene)
func inspect(scene: Node) -> void:
	for item in scene.find_children("*", "MeshInstance3D",true,false):
		var mesh := item as MeshInstance3D
		if "spring_pool" in mesh.name or "continuous_sheet" in mesh.name:
			print("INSPECT_WATER ",mesh.name, " transform=",mesh.global_transform)
			print("MATERIAL ",mesh.material_override.shader.resource_path," kind=",mesh.material_override.get_shader_parameter("water_kind"))
			var arrays := mesh.mesh.surface_get_arrays(0)
			var positions: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var uv: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
			for index in [0,24,48,2695,2744,5000,7594]:
				if index<positions.size():print("SAMPLE ",index," position=",positions[index]," uv=",uv[index])
	quit()
