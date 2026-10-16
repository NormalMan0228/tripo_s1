extends SceneTree
## The baked island (maps/archipelago/island_bake.gd, tools/bake_archipelago.gd) against the map the
## game builds at runtime from the same layouts and generated collision. Headless:
##   Godot --headless --path game --script res://tests/island_bake_check.gd
## Fails when the generated data is stale (layouts, build scripts or map assets changed since the bake:
## run tools/bake_archipelago.py), when the two maps differ in nodes (kind, place, visibility, mesh,
## materials, shadows, LOD bias, lights, collision layers and shapes) or when a probe of their
## collision differs (rays from above on a 1 m grid, the walker's capsule standing there), or when either
## map lacks the chunked ground as the bake made it (ground_chunks.gd: "Ground" the map's third child with
## its chunks and ocean, the model's ground and ocean meshes emptied and hidden), or when the two maps
## do not register the same number of prop LODs (environment_layout.gd restore()).
## Prints ISLAND_BAKE_CHECK {...}.
const Map = preload("res://maps/archipelago/archipelago.gd")
const IslandBake = preload("res://maps/archipelago/island_bake.gd")
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var report := {}
	var why := IslandBake.problem()
	if why.is_empty() and String(IslandBake.manifest().get("content_key", "")) != IslandBake.content_key(): why = "assets changed"
	report["fresh"] = why.is_empty()
	if not why.is_empty():
		failures.append("the bake is stale (%s): run tools/bake_archipelago.py" % why)
		finish(report)
		return
	IslandBake.island_disabled = true
	var runtime := await build("runtime build")
	IslandBake.island_disabled = false
	IslandBake.reset()
	if not IslandBake.island_ready(): failures.append("the baked island is not used")
	var baked := await build("baked island")
	report["runtime_ms"] = runtime.ms
	report["baked_ms"] = baked.ms
	report["nodes"] = [runtime.nodes.size(), baked.nodes.size()]
	var differ := []
	for path: String in runtime.nodes:
		if not baked.nodes.has(path): differ.append("missing in the bake: "+path)
		elif runtime.nodes[path] != baked.nodes[path]: differ.append("%s: %s / %s" % [path, str(runtime.nodes[path]), str(baked.nodes[path])])
	for path: String in baked.nodes:
		if not runtime.nodes.has(path): differ.append("only in the bake: "+path)
	report["node_differences"] = differ.size()
	report["first_differences"] = differ.slice(0, 12).map(func(line): return line.substr(0, 300))
	if not differ.is_empty(): failures.append("%d node differences" % differ.size())
	report["prop_lods"] = [runtime.lods, baked.lods]
	if runtime.lods == 0 or runtime.lods != baked.lods: failures.append("prop LODs: %d in the runtime map, %d on the baked island" % [runtime.lods, baked.lods])
	var probes := 0
	var probe_differences := []
	for index in runtime.probes.size():
		probes += 1
		if runtime.probes[index] != baked.probes[index] and probe_differences.size() < 12: probe_differences.append([runtime.probes[index], baked.probes[index]])
	report["probes"] = probes
	report["probe_differences"] = probe_differences
	if not probe_differences.is_empty(): failures.append("collision probes differ")
	# The chunked ground, in both maps, as the bake made it.
	var made: Dictionary = IslandBake.manifest().get("ground", {})
	report["ground"] = {"made": [made.get("chunks", 0), made.get("tris_after", 0)], "runtime": runtime.ground, "baked": baked.ground}
	for side in ["runtime", "baked"]:
		var ground: Dictionary = report.ground[side]
		if made.is_empty(): failures.append("the bake made no ground chunks")
		elif ground.chunks != int(made.chunks) or ground.tris != int(made.tris_after): failures.append("%s map: %d chunks, %d triangles; the bake made %d, %d" % [side, ground.chunks, ground.tris, made.chunks, made.tris_after])
		if ground.index != 2 or not ground.terrain_first: failures.append("%s map: the ground is child %d (terrain first: %s)" % [side, ground.index, ground.terrain_first])
		if not ground.ocean: failures.append("%s map: no ocean under the ground" % side)
		if ground.model_drawn > 0: failures.append("%s map: %d model ground or ocean meshes still drawn" % [side, ground.model_drawn])
	finish(report)

func finish(report: Dictionary) -> void:
	report["ok"] = failures.is_empty()
	report["failures"] = failures
	print("ISLAND_BAKE_CHECK ", JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)

func build(label: String) -> Dictionary:
	var viewport := SubViewport.new()
	viewport.own_world_3d = true
	viewport.size = Vector2i(64, 64)
	root.add_child(viewport)
	var camera := Camera3D.new()
	viewport.add_child(camera)
	var map: Node3D = Map.new()
	map.name = "Archipelago"
	viewport.add_child(map)
	var t := Time.get_ticks_msec()
	await map.build(camera)
	var ms := Time.get_ticks_msec()-t
	for i in 12: await physics_frame
	if not map.has_node("Roads"):
		var roads: Node3D = preload("res://scripts/roads.gd").new()
		roads.name = "Roads"
		map.add_child(roads)
		await roads.build(map.get_world_3d().direct_space_state, map.get_node_or_null("Environment"))
		for i in 4: await physics_frame
	var environment := map.get_node("Environment")
	# The props' LODs (environment_layout.gd), registered in both maps alike (the baked island once had none).
	var lods: int = environment.lod_entries.size()
	environment.set_process(false)
	environment.settle_for_bake()
	# The settled boats reach the physics server at the next steps.
	for i in 3: await physics_frame
	var nodes := {}
	describe(map, map, "", nodes)
	var probes := []
	var space := map.get_world_3d().direct_space_state
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.32
	capsule.height = 1.5
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.collision_mask = 1|2|8|32
	for z in range(-82, 104):
		for x in range(-104, 108):
			var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(x, 60, z), Vector3(x, -20, z), 1|2|8|16|32))
			if hit.is_empty():
				probes.append(null)
				continue
			query.transform = Transform3D(Basis.IDENTITY, Vector3(x, hit.position.y+0.36+0.76, z))
			probes.append([x, z, snappedf(hit.position.y, 0.0001), space.intersect_shape(query, 1).is_empty(), String(map.get_path_to(hit.collider)).get_slice("/", 1)])
	var ground := {"index": -1, "chunks": 0, "tris": 0, "ocean": false, "model_drawn": 0, "terrain_first": String(map.get_child(0).name).begins_with("archipelago_terrain")}
	var chunks := map.get_node_or_null("Ground")
	if chunks:
		ground.index = chunks.get_index()
		ground.ocean = chunks.has_node("Ocean")
		for chunk in chunks.get_children():
			if not String(chunk.name).begins_with("Chunk_"): continue
			ground.chunks += 1
			ground.tris += (chunk as MeshInstance3D).mesh.surface_get_arrays(0)[Mesh.ARRAY_INDEX].size()/3
	for m: MeshInstance3D in map.find_children("*__ground", "MeshInstance3D", true, false)+map.find_children("Ocean__central_surface", "MeshInstance3D", true, false):
		if m.mesh != null or m.visible: ground.model_drawn += 1
	print("BUILT %s in %d ms: %d nodes" % [label, ms, nodes.size()])
	viewport.queue_free()
	await process_frame
	return {"ms": ms, "nodes": nodes, "probes": probes, "ground": ground, "lods": lods}

## Names the engine makes ("@Node@12") and their readable stand-ins in the bake ("StaticBody3D2")
## compare as the node's class; same names under one parent are told apart by their order.
func describe(map: Node, node: Node, path: String, out: Dictionary) -> void:
	var counts := {}
	for child in node.get_children():
		var name := String(child.name)
		if name.begins_with("@") or (name.begins_with(child.get_class()) and name.trim_prefix(child.get_class()).is_valid_int()) or name == child.get_class():
			name = child.get_class()
		counts[name] = counts.get(name, 0)+1
		var key := path+"/"+name+("#%d" % counts[name] if counts[name] > 1 else "")
		out[key] = summary(child)
		describe(map, child, key, out)

func summary(node: Node) -> Array:
	var out: Array = [node.get_class()]
	if node is Node3D:
		var xf := (node as Node3D).global_transform
		out.append([snappedf(xf.origin.x, 0.001), snappedf(xf.origin.y, 0.001), snappedf(xf.origin.z, 0.001),
			snappedf(xf.basis.x.x, 0.001), snappedf(xf.basis.y.y, 0.001), snappedf(xf.basis.z.z, 0.001), snappedf(xf.basis.x.z, 0.001)])
		out.append((node as Node3D).visible)
	if node is GeometryInstance3D:
		var geometry := node as GeometryInstance3D
		out.append_array([geometry.cast_shadow, snappedf(geometry.lod_bias, 0.001), material_name(geometry.material_override)])
	if node is MeshInstance3D:
		var instance := node as MeshInstance3D
		out.append(mesh_name(instance.mesh))
		for surface in instance.get_surface_override_material_count(): out.append(material_name(instance.get_surface_override_material(surface)))
	if node is MultiMeshInstance3D and (node as MultiMeshInstance3D).multimesh:
		out.append([(node as MultiMeshInstance3D).multimesh.instance_count, mesh_name((node as MultiMeshInstance3D).multimesh.mesh)])
	if node is CollisionObject3D:
		out.append_array([(node as CollisionObject3D).collision_layer, (node as CollisionObject3D).collision_mask])
	if node is CollisionShape3D and (node as CollisionShape3D).shape:
		var shape := (node as CollisionShape3D).shape
		out.append(shape.get_class())
		if shape is ConcavePolygonShape3D: out.append([(shape as ConcavePolygonShape3D).get_faces().size(), (shape as ConcavePolygonShape3D).backface_collision])
		elif shape is ConvexPolygonShape3D: out.append((shape as ConvexPolygonShape3D).points.size())
		elif shape is CapsuleShape3D: out.append([(shape as CapsuleShape3D).radius, (shape as CapsuleShape3D).height])
	if node is Light3D:
		out.append_array([snappedf((node as Light3D).light_energy, 0.001), (node as Light3D).light_color.to_html()])
	return out

## A mesh as its file, or (made by the build) its kind, surfaces and bounds.
func mesh_name(mesh: Mesh) -> String:
	if mesh == null: return ""
	if mesh.resource_path.begins_with("res://") and not mesh.resource_path.contains("generated/"): return mesh.resource_path
	var box := mesh.get_aabb()
	return "%s %d %s %s" % [mesh.get_class(), mesh.get_surface_count(), str(box.position.snapped(Vector3.ONE*0.001)), str(box.size.snapped(Vector3.ONE*0.001))]

func material_name(material: Material) -> String:
	if material == null: return ""
	if material is ShaderMaterial:
		return "shader "+((material as ShaderMaterial).shader.resource_path if (material as ShaderMaterial).shader else "")
	if material is BaseMaterial3D: return "%s %s" % [material.get_class(), (material as BaseMaterial3D).albedo_color.to_html()]
	return material.get_class()
