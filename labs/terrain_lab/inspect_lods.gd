extends SceneTree
func _initialize() -> void:
	for path in ["res://assets/environment/white_flowers.glb","res://assets/environment/shrub.glb","res://assets/environment/round_tree.glb"]:
		var scene := load(path) as PackedScene
		var node := scene.instantiate()
		for mesh: MeshInstance3D in node.find_children("*","MeshInstance3D",true,false):
			for surface in mesh.mesh.get_surface_count():
				var data := RenderingServer.mesh_get_surface(mesh.mesh.get_rid(),surface)
				var sizes := []
				for lod: Dictionary in data.get("lods",[]):
					sizes.append({"threshold":lod.edge_length,"index_bytes":lod.index_data.size()})
				print("LOD_INVENTORY ",path," base_indices=",data.index_count," levels=",sizes)
		node.free()
	quit()
