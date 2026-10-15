extends SceneTree
## Generated data for the archipelago map (game/maps/archipelago/generated/, git-ignored; what it holds
## and when it counts: game/maps/archipelago/island_bake.gd). Run through tools/bake_archipelago.py, or:
##   .tools/godot/Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://../tools/bake_archipelago.gd
## Builds the map once the way the game does without generated data (render-mesh trimesh colliders),
## then for every collider made from a render mesh writes simplified faces (meshoptimizer through
## SurfaceTool.generate_lod: positions only, at most IslandBake.EPSILON off in world metres, the
## ground GROUND_EPSILON) cut into chunks of at most CHUNK_TRIS triangles, keyed like the build asks
## for them (IslandBake.collider_key), and cuts the levelled ground into chunks (ground.scn,
## ground_chunks.gd: checked bit for bit against the ground it was cut from; a failed check leaves no
## manifest, so nothing of this bake is used). Then builds the map again with that collision and those
## chunks, as the game does, and saves it as the baked island (island.scn; see island_bake.gd). Prints
## BAKE_COLLISION lines per group, BAKE_GROUND, BAKE_ISLAND and BAKE_DONE.
## --no-ground-chunks: no ground.scn (the island then holds the levelled ground as before).
## --check: only says whether the generated data is fresh (exit 0) or not (exit 3).
const Map = preload("res://maps/archipelago/archipelago.gd")
const IslandBake = preload("res://maps/archipelago/island_bake.gd")
const GroundChunks = preload("res://maps/archipelago/ground_chunks.gd")

## Experiments: --epsilon=M, --ground-epsilon=M (0 keeps the faces as they are, only cut in chunks).
var epsilon := IslandBake.EPSILON
var ground_epsilon := IslandBake.GROUND_EPSILON
var zone := IslandBake.WALK_ZONE
var zone_epsilon := IslandBake.WALK_ZONE_EPSILON

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--epsilon="): epsilon = float(arg.trim_prefix("--epsilon="))
		if arg.begins_with("--ground-epsilon="): ground_epsilon = float(arg.trim_prefix("--ground-epsilon="))
		if arg.begins_with("--zone="): zone = float(arg.trim_prefix("--zone="))
		if arg.begins_with("--zone-epsilon="): zone_epsilon = float(arg.trim_prefix("--zone-epsilon="))
	call_deferred("run")

func run() -> void:
	if "--check" in OS.get_cmdline_user_args():
		var why := IslandBake.problem()
		var stored := String(IslandBake.manifest().get("content_key", ""))
		if why.is_empty() and stored != IslandBake.content_key(): why = "content"
		print("BAKE_CHECK ", "fresh" if why.is_empty() else "stale (%s)" % why)
		quit(0 if why.is_empty() else 3)
		return
	if not Map.available():
		print("BAKE_DONE no map assets (tools/port_archipelago_map.py copies them)")
		quit(2)
		return
	var started := Time.get_ticks_msec()
	IslandBake.disabled = true
	IslandBake.reset()
	# The levelled ground keeps the floats it is built from, for the chunks.
	GroundChunks.keep_arrays = true
	var camera := Camera3D.new()
	root.add_child(camera)
	var map: Node3D = Map.new()
	map.name = "Archipelago"
	root.add_child(map)
	map.build(camera)
	# The deferred finishing steps (rock walls, ramps, roots, prop fitting) wait a few physics steps.
	for i in 12: await physics_frame
	var chunks := {}
	var groups := {}
	var shared := {}
	# Shared prop shapes: the largest placed scale of the prop bounds the error in the world.
	for cs: CollisionShape3D in map.find_children("*", "CollisionShape3D", true, false):
		var mesh := cs.get_parent().get_parent() as MeshInstance3D
		if mesh == null or not cs.shape is ConcavePolygonShape3D: continue
		var ident := prop_id(map, mesh)
		var key := IslandBake.collider_key(map, mesh, ident)
		var scale := mesh.global_basis.get_scale()
		var world_scale := maxf(scale.x, maxf(scale.y, scale.z))
		if not shared.has(key): shared[key] = {"shape": cs.shape, "scale": world_scale, "ground": group_of(key) == "terrain", "group": group_of(key), "mesh": mesh}
		else: shared[key].scale = maxf(shared[key].scale, world_scale)
	var keys := shared.keys()
	keys.sort()
	for key: String in keys:
		var entry: Dictionary = shared[key]
		var faces: PackedVector3Array = (entry.shape as ConcavePolygonShape3D).get_faces()
		var local_epsilon: float = (ground_epsilon if entry.ground else epsilon)/maxf(entry.scale, 0.0001)
		var simple := PackedVector3Array()
		if entry.group == "bridges" or key.begins_with("prop:"+IslandBake.WALKABLE_PROP):
			# Bridges and piers are walked on end to end: all of them within zone_epsilon.
			var walk_epsilon := zone_epsilon/maxf(entry.scale, 0.0001)
			simple = simplify(faces, walk_epsilon) if walk_epsilon > 0.0 else faces
		elif entry.group == "buildings" and zone > 0.0:
			# Where the walker goes (up to `zone` above the building's lowest point: steps, porches,
			# floors, doorways, railings) the faces stay within zone_epsilon; walls and roofs above
			# within epsilon.
			var to_world: Transform3D = (entry.mesh as MeshInstance3D).global_transform
			var bottom := INF
			for point in faces: bottom = minf(bottom, (to_world*point).y)
			var low := PackedVector3Array()
			var high := PackedVector3Array()
			for t in faces.size()/3:
				var y := minf((to_world*faces[t*3]).y, minf((to_world*faces[t*3+1]).y, (to_world*faces[t*3+2]).y))
				if y < bottom+zone: low.append_array(PackedVector3Array([faces[t*3], faces[t*3+1], faces[t*3+2]]))
				else: high.append_array(PackedVector3Array([faces[t*3], faces[t*3+1], faces[t*3+2]]))
			var low_epsilon := zone_epsilon/maxf(entry.scale, 0.0001)
			simple = (simplify(low, low_epsilon) if low_epsilon > 0.0 else low)+(simplify(high, local_epsilon) if local_epsilon > 0.0 else high)
		else:
			simple = simplify(faces, local_epsilon) if local_epsilon > 0.0 else faces
		var pieces := split(simple, IslandBake.CHUNK_TRIS)
		chunks[key] = pieces
		var group: Dictionary = groups.get(entry.group, {"colliders":0, "tris_before":0, "tris_after":0, "chunks":0, "largest_chunk":0})
		group.colliders += 1
		group.tris_before += faces.size()/3
		group.tris_after += simple.size()/3
		group.chunks += pieces.size()
		for piece: PackedVector3Array in pieces: group.largest_chunk = maxi(group.largest_chunk, piece.size()/3)
		groups[entry.group] = group
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(IslandBake.DIR))
	# No island and no chunks yet: the builds below must not load older ones.
	DirAccess.remove_absolute(ProjectSettings.globalize_path(IslandBake.ISLAND))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(IslandBake.GROUND))
	var ground := {}
	if not IslandBake.ground_disabled:
		ground = bake_ground(map)
		print("BAKE_GROUND %s" % JSON.stringify(ground))
		if ground.saved != OK:
			# Nothing of this bake counts: without a manifest the game builds the map as before.
			DirAccess.remove_absolute(ProjectSettings.globalize_path(IslandBake.MANIFEST))
			print("BAKE_DONE the ground chunks failed their check: %s" % str(ground.get("failures", [])))
			quit(1)
			return
	GroundChunks.keep_arrays = false
	var library := Resource.new()
	library.set_meta("chunks", chunks)
	var saved := ResourceSaver.save(library, IslandBake.COLLISION, ResourceSaver.FLAG_COMPRESS)
	var manifest := {"format": IslandBake.FORMAT, "engine": IslandBake.engine(), "key": IslandBake.key(),
		"stamp": IslandBake.stamp(), "content_key": IslandBake.content_key(), "made": Time.get_datetime_string_from_system(true),
		"epsilon_m": epsilon, "ground_epsilon_m": ground_epsilon, "walk_zone_m": zone, "walk_zone_epsilon_m": zone_epsilon, "chunk_tris": IslandBake.CHUNK_TRIS,
		"collision": groups}
	if not ground.is_empty(): manifest["ground"] = ground
	write_manifest(manifest)
	for group in groups: print("BAKE_COLLISION %-12s %s" % [group, JSON.stringify(groups[group])])
	map.queue_free()
	camera.queue_free()
	await process_frame
	if saved != OK:
		print("BAKE_DONE saved=%d" % saved)
		quit(1)
		return
	# The island: built at runtime with the collision just made, then saved as a scene.
	IslandBake.disabled = false
	IslandBake.island_disabled = true
	IslandBake.reset()
	if not IslandBake.fresh():
		print("BAKE_DONE the collision data is not fresh right after writing it (%s)" % IslandBake.problem())
		quit(1)
		return
	var island := await bake_island()
	manifest["island"] = island
	write_manifest(manifest)
	print("BAKE_ISLAND %s" % JSON.stringify(island))
	print("BAKE_DONE saved=%d colliders=%d ms=%d" % [island.saved, chunks.size(), Time.get_ticks_msec()-started])
	quit(0 if island.saved == OK else 1)

func write_manifest(manifest: Dictionary) -> void:
	var file := FileAccess.open(IslandBake.MANIFEST, FileAccess.WRITE)
	file.store_string(JSON.stringify(manifest, " ", true))
	file.close()

## Builds the map as the game does at runtime (generated collision on, roads as town.gd lays them),
## settles it (props on their full meshes, boats at rest, no spray) and saves it as a scene. The GLB
## models stay instances (referenced, not copied); what the build changed inside them (meshes such as
## the levelled ground, materials, shadow and LOD settings) is listed in the root's "baked_overrides"
## meta, set again after loading. The colliders made from generated chunks ("<mesh>_col" bodies) are
## listed in "baked_colliders" and left out; so are the faces of the other concave shapes (ramps,
## bridge decks: their bodies stay). (A scene file cannot hold nodes added inside a model instance
## without saving the instance as editable, which copies every model mesh into the file.)
const OVERRIDES := ["mesh", "material_override", "cast_shadow", "visible", "lod_bias", "transparency", "layers"]
func bake_island() -> Dictionary:
	var t := Time.get_ticks_msec()
	var camera := Camera3D.new()
	root.add_child(camera)
	var map: Node3D = Map.new()
	map.name = "Archipelago"
	root.add_child(map)
	map.build(camera)
	for i in 12: await physics_frame
	var roads: Node3D = preload("res://scripts/roads.gd").new()
	roads.name = "Roads"
	map.add_child(roads)
	await roads.build(map.get_world_3d().direct_space_state, map.get_node_or_null("Environment"))
	for i in 4: await physics_frame
	var build_ms := Time.get_ticks_msec()-t
	var environment := map.get_node("Environment")
	environment.set_process(false)
	map.set_process(false)
	environment.settle_for_bake()
	for node in [map.spray, map.mist]:
		map.remove_child(node)
		node.free()
	# Engine-made names ("@StaticBody3D@123") do not survive a scene file: readable ones instead.
	for node in map.find_children("*", "", true, false):
		if String(node.name).begins_with("@"): node.name = node.get_class()
	# Colliders from generated chunks: listed and taken out whole (made again after loading).
	var colliders := []
	for body: StaticBody3D in map.find_children("*_col", "StaticBody3D", true, false):
		var mesh := body.get_parent() as MeshInstance3D
		if mesh == null: continue
		var key := IslandBake.collider_key(map, mesh, prop_id(map, mesh))
		if IslandBake.collision_chunks(key).is_empty(): continue
		colliders.append({"mesh": String(map.get_path_to(mesh)), "key": key, "layer": body.collision_layer, "mask": body.collision_mask,
			"shared": key.begins_with("prop:")})
		mesh.remove_child(body)
		body.free()
	# Other concave shapes (ramps, decks): faces listed, the shapes taken out, the bodies kept.
	var stripped := 0
	for cs: CollisionShape3D in map.find_children("*", "CollisionShape3D", true, false):
		if not cs.shape is ConcavePolygonShape3D: continue
		var shape := cs.shape as ConcavePolygonShape3D
		colliders.append({"body": String(map.get_path_to(cs.get_parent())), "faces": shape.get_faces(), "backface": shape.backface_collision})
		cs.get_parent().remove_child(cs)
		cs.free()
		stripped += 1
	# What the build changed inside the model instances.
	var overrides := []
	var instances := 0
	for node in map.find_children("*", "", true, false):
		if node.scene_file_path.is_empty() or node.owner != null: continue
		instances += 1
		var fresh: Node = load(node.scene_file_path).instantiate()
		for inner in node.find_children("*", "", true, false):
			if inner.owner != node: continue
			var original := fresh.get_node_or_null(node.get_path_to(inner))
			if original == null: continue
			var names: Array = OVERRIDES.duplicate()
			if inner is MeshInstance3D and (inner as MeshInstance3D).mesh != null:
				for surface in (inner as MeshInstance3D).get_surface_override_material_count(): names.append("surface_material_override/%d" % surface)
			for property: String in names:
				if not property in inner: continue
				var value = inner.get(property)
				var before = original.get(property)
				var same: bool = is_same(value, before) if (value is Object or before is Object) else value == before
				if not same: overrides.append([String(map.get_path_to(inner)), property, value])
		fresh.free()
	# Every other node the build made belongs to the map (saved); a node it put inside a model
	# instance and not listed above would be lost: there must be none.
	var nodes := 0
	var lost := []
	for node in map.find_children("*", "", true, false):
		nodes += 1
		if node.owner != null: continue
		var parent := node.get_parent()
		if parent != map and parent.owner != map and parent.owner != null and parent.scene_file_path.is_empty():
			lost.append(String(map.get_path_to(node)))
		node.owner = map
	map.set_meta("baked_colliders", colliders)
	map.set_meta("baked_overrides", overrides)
	var packed := PackedScene.new()
	var packed_ok := packed.pack(map)
	var saved := packed_ok
	if packed_ok == OK and not lost.is_empty(): saved = ERR_INVALID_DATA
	if saved == OK: saved = ResourceSaver.save(packed, IslandBake.ISLAND, ResourceSaver.FLAG_COMPRESS)
	var bytes := FileAccess.get_file_as_bytes(IslandBake.ISLAND).size() if saved == OK else 0
	map.queue_free()
	camera.queue_free()
	await process_frame
	return {"saved": saved, "nodes": nodes, "instances": instances, "colliders": colliders.size(), "concave_stripped": stripped,
		"overrides": overrides.size(), "lost": lost.slice(0, 10), "bytes": bytes, "build_ms": build_ms, "ms": Time.get_ticks_msec()-t}

## The levelled ground this build made cut into chunks, with the ocean surface as the LODs it is drawn
## with (ground_chunks.gd), each checked against what it was cut from; saved as ground.scn when both pass.
func bake_ground(map: Node3D) -> Dictionary:
	var t := Time.get_ticks_msec()
	var grounds := map.find_children("*__ground", "MeshInstance3D", true, false)
	var ground := GroundChunks.build(grounds)
	var check := GroundChunks.validate(ground, grounds)
	var oceans := map.find_children("Ocean__central_surface", "MeshInstance3D", true, false)
	var ocean := GroundChunks.add_ocean(ground, oceans[0]) if not oceans.is_empty() else {"ok": true, "failures": []}
	for node in grounds: node.remove_meta(GroundChunks.ARRAYS_META)
	var failures: Array = check.failures+ocean.get("failures", [])
	var saved := ERR_INVALID_DATA
	if failures.is_empty():
		var packed := PackedScene.new()
		saved = packed.pack(ground)
		if saved == OK: saved = ResourceSaver.save(packed, IslandBake.GROUND, ResourceSaver.FLAG_COMPRESS)
	var stats: Dictionary = ground.get_meta("stats", {})
	ground.free()
	var out := stats.duplicate()
	out.merge({"saved": saved, "failures": failures.slice(0, 12), "vertices_checked": check.get("vertices_checked", 0),
		"ocean": ocean, "bytes": FileAccess.get_file_as_bytes(IslandBake.GROUND).size() if saved == OK else 0, "ms": Time.get_ticks_msec()-t})
	return out

## "<id>" for a mesh inside a placed prop ("Environment/<id>_<NNN>/..."), "" otherwise.
static func prop_id(map: Node, mesh: Node) -> String:
	var path := String(map.get_path_to(mesh))
	if not path.begins_with("Environment/"): return ""
	var name := path.get_slice("/", 1)
	var tail := name.get_slice("_", name.get_slice_count("_")-1)
	return name.trim_suffix("_"+tail) if tail.length() == 3 and tail.is_valid_int() else ""

static func group_of(key: String) -> String:
	if key.begins_with("prop:"): return "props"
	if key.begins_with("Buildings/"): return "buildings"
	if key.begins_with("Environment/"): return "bridges"
	return "terrain"

## Position-only simplification: corners welded, then meshoptimizer to `epsilon` (mesh units).
static func simplify(faces: PackedVector3Array, epsilon: float) -> PackedVector3Array:
	if faces.size() < 9: return faces
	var tool := SurfaceTool.new()
	tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	for point in faces: tool.add_vertex(point)
	tool.index()
	var arrays := tool.commit_to_arrays()
	var points: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var box := AABB(points[0], Vector3.ZERO)
	for point in points: box = box.expand(point)
	var extent := maxf(box.size.x, maxf(box.size.y, box.size.z))
	var index := tool.generate_lod(epsilon/maxf(extent, 0.0001), 3)
	var out := PackedVector3Array()
	out.resize(index.size())
	for i in index.size(): out[i] = points[index[i]]
	return out

## Cuts the triangles into spatial pieces of at most `limit` (median splits on the longest axis).
static func split(faces: PackedVector3Array, limit: int) -> Array:
	var count := faces.size()/3
	if count <= limit: return [faces]
	var low := Vector3.INF
	var high := -Vector3.INF
	var centres := PackedVector3Array()
	centres.resize(count)
	for t in count:
		var centre := (faces[t*3]+faces[t*3+1]+faces[t*3+2])/3.0
		centres[t] = centre
		low = low.min(centre)
		high = high.max(centre)
	var size := high-low
	var axis := 0 if size.x >= size.y and size.x >= size.z else (1 if size.y >= size.z else 2)
	var values := PackedFloat32Array()
	values.resize(count)
	for t in count: values[t] = centres[t][axis]
	var sorted := values.duplicate()
	sorted.sort()
	var middle := sorted[count/2]
	var a := PackedVector3Array()
	var b := PackedVector3Array()
	# (Packed arrays are values in GDScript: append to each by name.)
	for t in count:
		if values[t] < middle or (values[t] == middle and a.size()/3 < count/2):
			a.append(faces[t*3]); a.append(faces[t*3+1]); a.append(faces[t*3+2])
		else:
			b.append(faces[t*3]); b.append(faces[t*3+1]); b.append(faces[t*3+2])
	if a.is_empty() or b.is_empty(): return [faces]
	return split(a, limit)+split(b, limit)
