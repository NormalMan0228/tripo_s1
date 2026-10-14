extends SceneTree
## Generated data for the archipelago map (game/maps/archipelago/generated/, git-ignored; what it holds
## and when it counts: game/maps/archipelago/island_bake.gd). Run through tools/bake_archipelago.py, or:
##   .tools/godot/Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://../tools/bake_archipelago.gd
## Builds the map once the way the game does without generated data (render-mesh trimesh colliders),
## then for every collider made from a render mesh writes simplified faces (meshoptimizer through
## SurfaceTool.generate_lod: positions only, at most IslandBake.EPSILON off in world metres, the
## ground GROUND_EPSILON) cut into chunks of at most CHUNK_TRIS triangles, keyed like the build asks
## for them (IslandBake.collider_key). Prints one BAKE_COLLISION line per group and BAKE_DONE.
## --check: only says whether the generated data is fresh (exit 0) or not (exit 3).
const Map = preload("res://maps/archipelago/archipelago.gd")
const IslandBake = preload("res://maps/archipelago/island_bake.gd")

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
	var started := Time.get_ticks_msec()
	IslandBake.disabled = true
	IslandBake.reset()
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
	var library := Resource.new()
	library.set_meta("chunks", chunks)
	var saved := ResourceSaver.save(library, IslandBake.COLLISION, ResourceSaver.FLAG_COMPRESS)
	var manifest := {"format": IslandBake.FORMAT, "engine": Engine.get_version_info().string, "key": IslandBake.key(),
		"stamp": IslandBake.stamp(), "content_key": IslandBake.content_key(), "made": Time.get_datetime_string_from_system(true),
		"epsilon_m": epsilon, "ground_epsilon_m": ground_epsilon, "walk_zone_m": zone, "walk_zone_epsilon_m": zone_epsilon, "chunk_tris": IslandBake.CHUNK_TRIS,
		"collision": groups}
	var file := FileAccess.open(IslandBake.MANIFEST, FileAccess.WRITE)
	file.store_string(JSON.stringify(manifest, " ", true))
	file.close()
	for group in groups: print("BAKE_COLLISION %-12s %s" % [group, JSON.stringify(groups[group])])
	print("BAKE_DONE saved=%d colliders=%d ms=%d" % [saved, chunks.size(), Time.get_ticks_msec()-started])
	quit(0 if saved == OK else 1)

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
