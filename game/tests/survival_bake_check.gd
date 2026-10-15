extends SceneTree
## The survival maps built from their baked data (maps/survival/survival_bake.gd, tools/bake_survival.gd)
## against the maps built without it, from the same run state. Headless:
##   Godot --headless --path game --script res://tests/survival_bake_check.gd
## Fails when a bake is stale (layouts, survival_map.gd, survival_bake.gd or the prop models present
## changed since: run tools/bake_survival.py), when the baked build is not used, or when the two builds
## differ in any node (kind, place, visibility, shadows, materials and their parameters, meshes: the
## generated ones array by array, MultiMesh instance counts), in the instances the build puts into its
## MultiMeshes (prop batches and grass, transforms and custom data exactly, recorded as they go in: a
## headless run cannot read MultiMesh instances back), in the rng state after the build, in the map's
## stats or in its props. Each map is built for the layout with no
## resource nodes and with a fixture of 12 nodes (the inside scatter then differs from the bake tool's
## build), and once with a moved obstacle, which must build without the bake.
## Then as an exported game sees it (SurvivalBake.exported: no script text, so no key()): the fresh bake
## is used whole; another export key is refused; code that changes the ground (height), the rim helpers
## (_sample_rim) or the random numbers drawn before the rim (features) is caught by the fingerprints
## (survival_map.gd bake_probe, rim_probe, rng_before_rim): no bake, or the rim built at runtime.
## Prints SURVIVAL_BAKE_CHECK {...}.
const Map = preload("res://maps/survival/survival_map.gd")
const SurvivalBake = preload("res://maps/survival/survival_bake.gd")
var failures: Array[String] = []
## The map with a record of what goes into its MultiMeshes (test only; the build itself is unchanged).
const RECORDER := """
extends "res://maps/survival/survival_map.gd"
var recorded := []
func _finish_batches() -> void:
	for key in batches: recorded.append("batch %s %d %d" % [key, batches[key].xforms.size(), hash(var_to_bytes(batches[key].xforms))])
	super._finish_batches()
func _grass_chunks() -> Dictionary:
	var chunks: Dictionary = await super._grass_chunks()
	for key in chunks: recorded.append("grass %s %d %d" % [key, chunks[key].size(), hash(var_to_bytes(chunks[key]))])
	return chunks
"""
var recorder: GDScript
## Code changes an exported game must catch without reading the scripts' text.
const TAMPERED := {
	"height":"extends \"res://maps/survival/survival_map.gd\"
func height(x: float, z: float) -> float:
	return super.height(x,z)+0.01
",
	"rim":"extends \"res://maps/survival/survival_map.gd\"
func _sample_rim(min_rim: float, max_rim: float, south_ok: bool) -> Vector2:
	var p := super._sample_rim(min_rim,max_rim,south_ok)
	return p if p.x == INF else p+Vector2(0.5,0.0)
",
	"features":"extends \"res://maps/survival/survival_map.gd\"
func _build_features() -> void:
	rng.randf()
	await super._build_features()
",
}
var name_numbers := RegEx.create_from_string("@(\\w+)@\\d+")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var report := {"maps":{}}
	var stale := []
	for map_id in SurvivalBake.MAPS:
		var why := SurvivalBake.problem(map_id)
		if not why.is_empty(): stale.append("%s: %s" % [map_id, why])
	report["fresh"] = stale.is_empty()
	if not stale.is_empty():
		failures.append("stale (%s): run tools/bake_survival.py" % ", ".join(stale))
		finish(report)
		return
	recorder = GDScript.new()
	recorder.source_code = RECORDER
	recorder.reload()
	var all := Map.layouts()
	var total_differences := 0
	for map_id in SurvivalBake.MAPS:
		var spec: Dictionary = all.maps[map_id]
		var entry := {}
		var reference_nodes := []
		var reference_recorded := []
		# Warm-up: the props are read once, so both timed builds find them in the resource cache.
		var warm := await build(map_id, reference(map_id, spec), false)
		release(warm)
		for fixture in ["layout", "nodes"]:
			var state := reference(map_id, spec)
			if fixture == "nodes": state["nodes"] = fixture_nodes()
			var runtime := await build(map_id, state, false)
			var baked := await build(map_id, state, true)
			if runtime.used_bake: failures.append("%s %s: the runtime build used the bake" % [map_id, fixture])
			if not baked.used_bake: failures.append("%s %s: the baked build did not use the bake" % [map_id, fixture])
			if not baked.rim_replayed: failures.append("%s %s: the baked build did not replay the baked rim" % [map_id, fixture])
			var differ := []
			for i in maxi(runtime.nodes.size(), baked.nodes.size()):
				var a: String = runtime.nodes[i] if i < runtime.nodes.size() else "(none)"
				var b: String = baked.nodes[i] if i < baked.nodes.size() else "(none)"
				if a != b: differ.append("%s / %s" % [a.substr(0, 220), b.substr(0, 220)])
			for key in ["rng", "report", "props", "recorded"]:
				if runtime[key] != baked[key]: differ.append("%s: %s / %s" % [key, str(runtime[key]).substr(0, 220), str(baked[key]).substr(0, 220)])
			total_differences += differ.size()
			if not differ.is_empty(): failures.append("%s %s: %d differences" % [map_id, fixture, differ.size()])
			if fixture == "layout":
				reference_nodes = runtime.nodes
				reference_recorded = runtime.recorded
			else:
				# The comparison sees a change: the fixture's nodes move the inside scatter and the grass.
				var seen := 0
				for i in mini(runtime.nodes.size(), reference_nodes.size()): if runtime.nodes[i] != reference_nodes[i]: seen += 1
				for i in mini(runtime.recorded.size(), reference_recorded.size()): if runtime.recorded[i] != reference_recorded[i]: seen += 1
				entry["fixture_differences"] = seen
				if seen == 0: failures.append("%s: the node description did not see the fixture's nodes" % map_id)
			entry[fixture] = {"runtime_ms":runtime.ms, "baked_ms":baked.ms, "nodes":[runtime.nodes.size(), baked.nodes.size()],
				"node_differences":differ.size(), "first_differences":differ.slice(0, 6)}
			release(runtime)
			release(baked)
		# A run whose obstacles are not the layout's (saved before the server re-synced it): no bake.
		var moved := reference(map_id, spec)
		var obstacles: Array = spec.obstacles.duplicate(true)
		var solid := 0
		for i in obstacles.size():
			if str(obstacles[i].get("kind", "")) != "pond" and float(obstacles[i].radius) > float(obstacles[solid].radius): solid = i
		obstacles[solid]["x"] = float(obstacles[solid]["x"])+1.5
		moved["obstacles"] = obstacles
		var fallback := await build(map_id, moved, true)
		entry["moved_obstacle_uses_bake"] = fallback.used_bake
		if fallback.used_bake: failures.append("%s: a moved obstacle still used the bake" % map_id)
		if not fallback.has_ground: failures.append("%s: the fallback build has no ground" % map_id)
		release(fallback)
		# The fingerprints' cost (the first build of a map in a run of the game computes them once).
		var timed := await build(map_id, reference(map_id, spec), true)
		var t := Time.get_ticks_usec()
		timed.map.bake_probe()
		entry["bake_probe_ms"] = snappedf((Time.get_ticks_usec()-t)/1000.0, 0.01)
		t = Time.get_ticks_usec()
		timed.map.rim_probe()
		entry["rim_probe_ms"] = snappedf((Time.get_ticks_usec()-t)/1000.0, 0.01)
		release(timed)
		report.maps[map_id] = entry
		print("SURVIVAL_BAKE_MAP %s %s" % [map_id, JSON.stringify(entry)])
	report["node_differences"] = total_differences
	report["exported"] = await exported_checks(all)
	finish(report)

## As an exported game: SurvivalBake cannot compare key() there, only export_key() and the fingerprints.
func exported_checks(all: Dictionary) -> Dictionary:
	var out := {}
	SurvivalBake.exported = true
	SurvivalBake.reset()
	for map_id in SurvivalBake.MAPS:
		var spec: Dictionary = all.maps[map_id]
		var seen := {}
		var fresh := await build(map_id, reference(map_id, spec), true)
		seen["fresh"] = [fresh.used_bake, fresh.rim_replayed]
		if not (fresh.used_bake and fresh.rim_replayed): failures.append("exported %s: the fresh bake was not used whole" % map_id)
		release(fresh)
		for change in TAMPERED:
			var script := GDScript.new()
			script.source_code = TAMPERED[change]
			script.reload()
			var result := await build(map_id, reference(map_id, spec), true, script)
			seen[change] = [result.used_bake, result.rim_replayed]
			# A changed ground: no bake at all. A changed rim or random state before it: the baked ground
			# and water, the rim built here.
			var want := [false, false] if change == "height" else [true, false]
			if seen[change] != want: failures.append("exported %s: %s change gave bake/rim %s, expected %s" % [map_id, change, seen[change], want])
			release(result)
		# Another export key (a constant or layouts.json changed since the bake): refused.
		var data: Resource = load(SurvivalBake.path(map_id))
		var kept: String = data.get_meta("export_key")
		data.set_meta("export_key", "changed")
		SurvivalBake.reset()
		seen["export_key"] = SurvivalBake.problem(map_id)
		data.set_meta("export_key", kept)
		SurvivalBake.reset()
		if seen.export_key != "export key": failures.append("exported %s: another export key gave '%s'" % [map_id, seen.export_key])
		out[map_id] = seen
	SurvivalBake.exported = false
	SurvivalBake.reset()
	print("SURVIVAL_BAKE_EXPORTED %s" % JSON.stringify(out))
	return out

func finish(report: Dictionary) -> void:
	report["ok"] = failures.is_empty()
	report["failures"] = failures
	print("SURVIVAL_BAKE_CHECK ", JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)

func reference(map_id: String, spec: Dictionary) -> Dictionary:
	return {"map_id":map_id, "obstacles":spec.obstacles.duplicate(true), "hazards":spec.hazards.duplicate(true), "nodes":[]}

## Twelve resource nodes inside the play square (fixed positions): the inside scatter keeps clear of them.
func fixture_nodes() -> Array:
	var r := RandomNumberGenerator.new()
	r.seed = 4242
	var nodes := []
	for i in 12:
		nodes.append({"id":"fixture_%d" % i, "kind":["tree","stone","berry","fiber"][i % 4], "x":r.randf_range(-18.0, 18.0), "z":r.randf_range(-18.0, 18.0), "quantity":3})
	return nodes

## One build in its own world; `use_bake` false builds as if there were no baked data.
func build(map_id: String, state: Dictionary, use_bake: bool, script: GDScript = null) -> Dictionary:
	SurvivalBake.disabled = not use_bake
	var viewport := SubViewport.new()
	viewport.own_world_3d = true
	viewport.size = Vector2i(64, 64)
	root.add_child(viewport)
	var map: Node3D = (script if script else recorder).new()
	viewport.add_child(map)
	var started := Time.get_ticks_usec()
	await map.build(state)
	var ms := (Time.get_ticks_usec()-started)/1000.0
	map.set_process(false)
	SurvivalBake.disabled = false
	var props := []
	for id in map.props: if map.props[id].ok: props.append(id)
	props.sort()
	var nodes := []
	describe(map, map, nodes)
	return {"viewport":viewport, "map":map, "ms":snappedf(ms, 0.1), "used_bake":map.baked != null, "rng":str(map.rng.state),
		"report":JSON.stringify(map.report(), "", true), "props":props, "nodes":nodes, "has_ground":map.has_node("Ground"),
		"recorded":map.get("recorded"), "rim_replayed":map.rim_replayed}

func release(result: Dictionary) -> void:
	(result.viewport as Node).queue_free()

func describe(map: Node, node: Node, out: Array) -> void:
	for child in node.get_children():
		var path := name_numbers.sub(String(map.get_path_to(child)), "@$1@", true)
		var line := [path, child.get_class()]
		if child is Node3D:
			var xf: Transform3D = (child as Node3D).global_transform
			line.append(floats([xf.basis.x, xf.basis.y, xf.basis.z, xf.origin], 0.001))
			line.append((child as Node3D).visible)
		if child is GeometryInstance3D:
			line.append((child as GeometryInstance3D).cast_shadow)
			line.append(material((child as GeometryInstance3D).material_override))
		if child is MeshInstance3D: line.append(mesh((child as MeshInstance3D).mesh))
		if child is MultiMeshInstance3D: line.append(multimesh((child as MultiMeshInstance3D).multimesh))
		if child is Label3D: line.append([(child as Label3D).text, (child as Label3D).modulate, child.is_in_group("place_nameplates")])
		if child is CPUParticles3D: line.append([(child as CPUParticles3D).amount, (child as CPUParticles3D).emitting, mesh((child as CPUParticles3D).mesh)])
		for meta in child.get_meta_list(): line.append("%s=%s" % [meta, str(child.get_meta(meta))])
		out.append(str(line))
		describe(map, child, out)

func floats(vectors: Array, step: float) -> Array:
	var out := []
	for v: Vector3 in vectors: out.append_array([snappedf(v.x, step), snappedf(v.y, step), snappedf(v.z, step)])
	return out

func material(value: Material) -> String:
	if value == null: return "none"
	if value is ShaderMaterial:
		var shader_material := value as ShaderMaterial
		var parts := [shader_material.shader.resource_path if shader_material.shader else "", shader_material.render_priority]
		if shader_material.shader:
			for uniform in shader_material.shader.get_shader_uniform_list():
				var parameter = shader_material.get_shader_parameter(uniform.name)
				parts.append("%s=%s" % [uniform.name, parameter.resource_path if parameter is Resource else str(parameter)])
		for meta in shader_material.get_meta_list(): parts.append("%s=%s" % [meta, str(shader_material.get_meta(meta))])
		return str(parts)
	if value is BaseMaterial3D:
		var base := value as BaseMaterial3D
		return str([value.get_class(), base.albedo_color, base.shading_mode, base.roughness, base.metallic])
	return value.get_class()

## Meshes from files by their path; meshes made by the build by their arrays (exactly).
func mesh(value: Mesh) -> String:
	if value == null: return "none"
	if not value.resource_path.is_empty() and not value.resource_path.begins_with(SurvivalBake.DIR): return value.resource_path
	var parts := [value.get_class(), value.get_surface_count(), str(value.get_aabb())]
	if value is ArrayMesh:
		for surface in value.get_surface_count():
			var arrays := value.surface_get_arrays(surface)
			for index in [Mesh.ARRAY_VERTEX, Mesh.ARRAY_NORMAL, Mesh.ARRAY_COLOR, Mesh.ARRAY_TEX_UV, Mesh.ARRAY_INDEX]:
				parts.append(hash(arrays[index]) if arrays[index] != null else 0)
			parts.append(material(value.surface_get_material(surface)))
	return str(parts)

## (Instance transforms are compared from the build's record: headless they read back as identity.)
func multimesh(value: MultiMesh) -> String:
	if value == null: return "none"
	return str([value.instance_count, value.use_custom_data, value.transform_format, mesh(value.mesh)])
