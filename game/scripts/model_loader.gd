extends RefCounted

static func load_sample(path: String) -> Node3D:
	var bytes := FileAccess.get_file_as_bytes(path)
	return load_bytes(bytes)

# Downloaded models stay in memory. The server validates GLB before publishing it.
static func load_bytes(bytes: PackedByteArray) -> Node3D:
	if bytes.is_empty() or bytes.size() > 20 * 1024 * 1024:
		return null
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	if document.append_from_buffer(bytes, "", state) != OK:
		return null
	var imported := document.generate_scene(state) as Node3D
	if imported == null:
		return null
	var meshes: Array[MeshInstance3D] = []
	_collect_meshes(imported, meshes)
	if meshes.is_empty():
		imported.free()
		return null
	var bounds := AABB()
	var first := true
	for instance in meshes:
		var transform := _local_transform(instance, imported)
		var mesh_bounds: AABB = transform * instance.get_aabb()
		bounds = mesh_bounds if first else bounds.merge(mesh_bounds)
		first = false
	var longest: float = maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z))
	if not is_finite(longest) or longest < 0.001:
		imported.free()
		return null
	var root := Node3D.new()
	root.name = "SampleDecoration"
	var pivot := Node3D.new()
	root.add_child(pivot)
	pivot.add_child(imported)
	var factor := 1.6 / longest
	pivot.scale = Vector3.ONE * factor
	pivot.position = -Vector3(bounds.get_center().x, bounds.position.y, bounds.get_center().z) * factor
	root.set_meta("size", bounds.size * factor)
	root.set_meta("paint", Color.WHITE)
	paint(root, Color.WHITE)
	return root

static func _local_transform(node: Node3D, imported: Node3D) -> Transform3D:
	var result := node.transform
	var current := node
	while current != imported:
		current = current.get_parent() as Node3D
		if current == null:
			break
		result = current.transform * result
	return result

static func _collect_meshes(node: Node, result: Array[MeshInstance3D]) -> void:
	if node is MeshInstance3D and node.mesh != null:
		result.append(node)
	for child in node.get_children():
		_collect_meshes(child, result)

static func paint(root: Node3D, color: Color) -> void:
	var meshes: Array[MeshInstance3D] = []
	_collect_meshes(root, meshes)
	for instance in meshes:
		var material := StandardMaterial3D.new()
		material.albedo_color = color
		material.roughness = 0.9
		instance.material_override = material
	root.set_meta("paint", color)

static func add_collision(root: Node3D) -> void:
	var size: Vector3 = root.get_meta("size")
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	shape.position.y = size.y / 2.0
	body.add_child(shape)
	root.add_child(body)
