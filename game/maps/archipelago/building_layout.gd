extends Node3D
## Reviewed Tripo assets, real metre scale, and local level ground pads.
var manifest: Dictionary
var terrain_root: Node3D
var host: Node3D
var settled_frames := 0
var capture_started := false
var touched_vertices := 0
var placed: Array[Node3D] = []
const OUTPUT := "res://../art/maps/archipelago_placement_v1/"

func install(owner_node: Node3D, terrain: Node3D) -> void:
	host = owner_node
	terrain_root = terrain
	manifest = JSON.parse_string(FileAccess.get_file_as_string("res://maps/archipelago/building_placements.json"))
	_prepare_ground()
	for spec: Dictionary in manifest.buildings:
		var scene := load(String(spec.model)) as PackedScene
		assert(scene != null, "Building model missing: " + String(spec.id))
		var building := scene.instantiate() as Node3D
		building.name = spec.id
		add_child(building)
		building.position = Vector3(spec.position[0], spec.position[1], spec.position[2])
		building.rotation.y = deg_to_rad(float(spec.yaw_degrees))
		building.scale = Vector3.ONE * float(spec.scale)
		placed.append(building)
		# Building collision is separate from ground sampling (layer 2).
		for item in building.find_children("*", "MeshInstance3D", true, false):
			var mesh := item as MeshInstance3D
			mesh.create_trimesh_collision()
			for child in mesh.get_children():
				if child is StaticBody3D:
					child.collision_layer = 2
					child.collision_mask = 0
	print("BUILDING_LAYOUT_READY count=", placed.size(), " level_pad_vertices=", touched_vertices)

func _pad_weight(world: Vector3, spec: Dictionary) -> float:
	var offset := Vector2(world.x - float(spec.position[0]), world.z - float(spec.position[2]))
	var a := deg_to_rad(float(spec.yaw_degrees))
	var local_x := offset.x * cos(a) - offset.y * sin(a)
	var local_z := offset.x * sin(a) + offset.y * cos(a)
	var outside := maxf(absf(local_x) - float(spec.pad_half_extents[0]), absf(local_z) - float(spec.pad_half_extents[1]))
	return 1.0 - smoothstep(0.0, float(spec.pad_blend_m), outside)

func _prepare_ground() -> void:
	for item in terrain_root.find_children("*", "MeshInstance3D", true, false):
		var ground := item as MeshInstance3D
		if "__ground" not in ground.name:
			continue
		var sites: Array[Dictionary] = []
		for spec: Dictionary in manifest.buildings:
			if String(spec.island) in ground.name:
				sites.append(spec)
		var rebuilt := ArrayMesh.new()
		var inverse := ground.global_transform.affine_inverse()
		for surface in ground.mesh.get_surface_count():
			var arrays := ground.mesh.surface_get_arrays(surface)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
			for i in vertices.size():
				var world := ground.global_transform * vertices[i]
				for spec: Dictionary in sites:
					var weight := _pad_weight(world, spec)
					if weight <= 0.0:
						continue
					var normal := (ground.global_basis * normals[i]).normalized()
					var level := float(spec.position[1])
					var gradient_x := (_pad_weight(world + Vector3(.01, 0, 0), spec) - _pad_weight(world - Vector3(.01, 0, 0), spec)) / .02
					var gradient_z := (_pad_weight(world + Vector3(0, 0, .01), spec) - _pad_weight(world - Vector3(0, 0, .01), spec)) / .02
					var slope_x := -normal.x / maxf(normal.y, .001)
					var slope_z := -normal.z / maxf(normal.y, .001)
					var new_normal := Vector3(-((1.0-weight)*slope_x+(level-world.y)*gradient_x), 1, -((1.0-weight)*slope_z+(level-world.y)*gradient_z)).normalized()
					world.y = lerpf(world.y, level, weight)
					vertices[i] = inverse * world
					normals[i] = (ground.global_basis.inverse() * new_normal).normalized()
					touched_vertices += 1
					break
			arrays[Mesh.ARRAY_VERTEX] = vertices
			arrays[Mesh.ARRAY_NORMAL] = normals
			rebuilt.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
			rebuilt.surface_set_material(surface, ground.mesh.surface_get_material(surface))
		ground.mesh = rebuilt

func _process(_delta: float) -> void:
	if not OS.get_cmdline_user_args().has("--placement-capture"):
		return
	settled_frames += 1
	if settled_frames >= 100 and not capture_started:
		capture_started = true
		_verify_and_capture.call_deferred()

func _bounds(node: Node3D) -> AABB:
	var bounds := AABB()
	var first := true
	for item in node.find_children("*", "MeshInstance3D", true, false):
		var mesh := item as MeshInstance3D
		var box: AABB = mesh.global_transform * mesh.get_aabb()
		bounds = box if first else bounds.merge(box)
		first = false
	return bounds

func _verify_and_capture() -> void:
	var report := {"count": placed.size(), "metre_scale": true, "level_pad_vertices": touched_vertices, "buildings": [], "overlaps": []}
	var bounds: Array[AABB] = []
	var valid := placed.size() == 17
	for i in placed.size():
		var node := placed[i]
		var box := _bounds(node)
		bounds.append(box)
		var spec: Dictionary = manifest.buildings[i]
		var ground_hits: Array[float] = []
		# Probe rotated footprint corners, edges and centre after terrain collision
		# has entered physics. Layer 1 excludes the new buildings and character.
		for ox in [-.8, 0.0, .8]:
			for oz in [-.8, 0.0, .8]:
				var point := node.global_transform * Vector3(float(spec.pad_half_extents[0])*ox, 0, float(spec.pad_half_extents[1])*oz)
				var query := PhysicsRayQueryParameters3D.create(point + Vector3(0, 15, 0), point - Vector3(0, 15, 0), 1, [host.actor.get_rid()])
				var hit := get_world_3d().direct_space_state.intersect_ray(query)
				if not hit.is_empty():
					ground_hits.append(hit.position.y)
		var max_gap := 0.0
		for y in ground_hits:
			max_gap = maxf(max_gap, absf(y-node.position.y))
		var height_ok := absf(box.size.y - float(spec.dimensions_m[1])) < .03
		var grounded := ground_hits.size() == 9 and max_gap < .035 and absf(box.position.y-node.position.y) < .015
		valid = valid and height_ok and grounded
		report.buildings.append({"id": node.name, "position_m": [node.position.x,node.position.y,node.position.z], "height_m": box.size.y, "footprint_ground_samples":ground_hits.size(), "max_ground_gap_m":max_gap, "grounded":grounded, "scale_correct":height_ok})
	for i in bounds.size():
		for j in range(i+1, bounds.size()):
			if bounds[i].intersects(bounds[j]):
				report.overlaps.append([placed[i].name, placed[j].name])
	valid = valid and report.overlaps.is_empty()
	report["passed"] = valid
	var file := FileAccess.open(OUTPUT + "placement_verification.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  "))
	print("BUILDING_PLACEMENT_CHECK passed=", valid, " count=", placed.size(), " overlaps=", report.overlaps.size())
	host.free_camera = false
	host.map_tour = false
	var layer := host.get_node_or_null("CanvasLayer")
	if layer:
		layer.visible = false
	host.camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	var views := [
		["overview", Vector3(0,2,3), 138.0, .92, -.08],
		["northwest", Vector3(-42,4,-39), 60.0, .73, -.15],
		["northeast", Vector3(46,4,-32), 67.0, .76, -.12],
		["southwest", Vector3(-43,5,31), 65.0, .74, -.1],
		["southeast", Vector3(49,3,38), 57.0, .75, -.12],
		["lighthouse", Vector3(7,5,78), 22.0, .63, -.15],
	]
	for view in views:
		var target: Vector3 = view[1]
		var elevation: float = view[3]
		var azimuth: float = view[4]
		host.camera.size = view[2]
		host.camera.position = target + Vector3(sin(azimuth)*cos(elevation),sin(elevation),cos(azimuth)*cos(elevation))*180.0
		host.camera.look_at(target)
		# Freeze normal orbit updates until every image has been drawn.
		host.free_camera = true
		await get_tree().create_timer(.7).timeout
		await RenderingServer.frame_post_draw
		var path := ProjectSettings.globalize_path(OUTPUT + String(view[0]) + ".png")
		get_viewport().get_texture().get_image().save_png(path)
		print("PLACEMENT_CAPTURE ", path)
	get_tree().quit(0 if valid else 1)
