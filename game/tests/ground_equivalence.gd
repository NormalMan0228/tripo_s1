extends SceneTree
## The chunked ground (generated/ground.scn, maps/archipelago/ground_chunks.gd) against the levelled
## ground the map builds without it (--no-ground-chunks: one mesh per island, as drawn before). Headless:
##   Godot --headless --path game --script res://tests/ground_equivalence.gd
## Checks:
##   chunks     every triangle of the levelled ground that reaches DROP_BELOW is in exactly one chunk
##              (the cell of its centroid) with every vertex the same, as floats and as GPU bytes; every
##              triangle left out lies wholly below DROP_BELOW (under the opaque sea)
##   ocean      the ocean surface's LODs are the model's, triangle by triangle, vertex bytes included
##   heights    on a 0.5 m grid over the islands and at every map point (doors, bridge ends, piers, pavilion
##              floors, places, the cafe terrace slot, every placed prop and building): where the levelled
##              ground is at or above DROP_BELOW the chunks have ground there at the same height and
##              with the same normal (no holes, no cracks, no steps)
## Prints GROUND_EQUIVALENCE {...}; exits 1 on any failure (or a stale bake).
const Map = preload("res://maps/archipelago/archipelago.gd")
const IslandBake = preload("res://maps/archipelago/island_bake.gd")
const GroundChunks = preload("res://maps/archipelago/ground_chunks.gd")
const Town = preload("res://scripts/town.gd")
const BUCKET := 2.0
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var started := Time.get_ticks_msec()
	var report := {}
	var why := IslandBake.problem()
	if not why.is_empty() or not ResourceLoader.exists(IslandBake.GROUND):
		finish({"fresh": false}, "no fresh ground chunks: run tools/bake_archipelago.py (%s)" % why)
		return
	# The ground as drawn before: built at runtime without the chunks.
	IslandBake.ground_disabled = true
	IslandBake.reset()
	var viewport := SubViewport.new()
	viewport.own_world_3d = true
	viewport.size = Vector2i(64, 64)
	root.add_child(viewport)
	var camera := Camera3D.new()
	viewport.add_child(camera)
	var map: Node3D = Map.new()
	map.name = "Archipelago"
	viewport.add_child(map)
	await map.build(camera)
	var grounds := map.find_children("*__ground", "MeshInstance3D", true, false).filter(func(g): return (g as MeshInstance3D).mesh != null)
	if grounds.size() != 5 or map.has_node("Ground"): failures.append("the build without chunks has %d ground meshes%s" % [grounds.size(), " and chunks" if map.has_node("Ground") else ""])
	var chunks: Node3D = (load(IslandBake.GROUND) as PackedScene).instantiate()
	var check := GroundChunks.validate(chunks, grounds)
	report["chunks"] = check
	for line in check.failures: failures.append(line)
	var stats: Dictionary = chunks.get_meta("stats", {})
	report["stats"] = {"tris_before": stats.get("tris_before"), "tris_after": stats.get("tris_after"), "chunks": stats.get("chunks"), "cells": stats.get("cells")}
	var oceans := map.find_children("Ocean__central_surface", "MeshInstance3D", true, false)
	if chunks.has_node("Ocean") and not oceans.is_empty():
		var ocean := GroundChunks.validate_ocean((chunks.get_node("Ocean") as MeshInstance3D).mesh, (oceans[0] as MeshInstance3D).mesh)
		report["ocean"] = ocean
		for line in ocean.failures: failures.append(line)
		var node := chunks.get_node("Ocean") as MeshInstance3D
		for property in ["cast_shadow", "layers", "lod_bias", "transparency", "gi_mode"]:
			if node.get(property) != oceans[0].get(property): failures.append("ocean %s differs" % property)
		if node.material_override == null or (node.material_override as ShaderMaterial).shader != (oceans[0].material_override as ShaderMaterial).shader: failures.append("ocean material differs")
	elif not oceans.is_empty(): failures.append("the chunks carry no ocean")
	# Heights: the top ground surface under each point, before and after.
	var before := Surface.new(grounds)
	var after := Surface.new(chunks.get_children().filter(func(c): return String(c.name).begins_with("Chunk_")))
	var points := map_points()
	var grid := 0
	for z in range(-224, 225):
		for x in range(-256, 193):
			points.append(["grid", Vector2(x*0.5, z*0.5)])
			grid += 1
	var compared := 0
	var largest := 0.0
	var largest_normal := 0.0
	var holes := []
	var steps := []
	var map_point_moves := 0
	for entry: Array in points:
		var at: Vector2 = entry[1]
		var a := before.sample(at)
		if a.is_empty() or a.y < GroundChunks.DROP_BELOW: continue
		var b := after.sample(at)
		compared += 1
		if b.is_empty():
			if holes.size() < 12: holes.append([entry[0], at, snappedf(a.y, 0.001)])
			continue
		var dy := absf(float(a.y)-float(b.y))
		largest = maxf(largest, dy)
		largest_normal = maxf(largest_normal, rad_to_deg((a.normal as Vector3).angle_to(b.normal)))
		if dy > 0.0:
			if entry[0] != "grid": map_point_moves += 1
			if steps.size() < 12: steps.append([entry[0], at, snappedf(a.y, 0.0001), snappedf(b.y, 0.0001)])
	report["heights"] = {"points": points.size(), "grid": grid, "map_points": points.size()-grid, "compared": compared,
		"holes": holes, "moved": steps, "largest_m": largest, "largest_normal_deg": snappedf(largest_normal, 0.001), "map_points_moved": map_point_moves}
	if not holes.is_empty(): failures.append("%d+ points have ground before and none in the chunks" % holes.size())
	if not steps.is_empty(): failures.append("ground heights differ (largest %.4f m)" % largest)
	if largest_normal > 0.0: failures.append("ground normals differ (largest %.3f deg)" % largest_normal)
	chunks.free()
	report["seconds"] = (Time.get_ticks_msec()-started)/1000.0
	finish(report)

func finish(report: Dictionary, failure := "") -> void:
	if not failure.is_empty(): failures.append(failure)
	report["ok"] = failures.is_empty()
	report["failures"] = failures
	print("GROUND_EQUIVALENCE ", JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)

## Points other sessions' quests and story stand on, and every placed thing.
func map_points() -> Array:
	var out := []
	for door: Dictionary in Town.DOORS: out.append(["door "+String(door.id), Vector2(door.at)])
	for place: Dictionary in Town.PLACES: out.append(["place "+String(place.id), Vector2(place.at)])
	out.append_array([["spawn", Town.SPAWN], ["home door", Town.HOME_DOOR], ["workshop door", Town.WORKSHOP_DOOR], ["gate", Town.GATE]])
	out.append(["cafe terrace slot", Vector2(-60.2, -27.6)])
	for id in Map.OPEN_STRUCTURES: out.append(["floor "+id, Map.OPEN_STRUCTURES[id][0]])
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://maps/archipelago/environment_layout.json"))
	for bridge: Dictionary in layout.bridges:
		out.append(["bridge %s a" % bridge.id, Vector2(bridge.a[0], bridge.a[1])])
		out.append(["bridge %s b" % bridge.id, Vector2(bridge.b[0], bridge.b[1])])
	for pier: Dictionary in layout.piers:
		out.append(["pier landing", Vector2(pier.landing[0], pier.landing[1])])
		out.append(["pier tip", Vector2(pier.tip[0], pier.tip[1])])
	for spec: Dictionary in layout.instances: out.append(["prop "+String(spec.id), Vector2(spec.position[0], spec.position[2])])
	var placements: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://maps/archipelago/building_placements.json"))
	for spec: Dictionary in placements.buildings: out.append(["building "+String(spec.id), Vector2(spec.position[0], spec.position[2])])
	return out

## The top surface of some ground meshes: height and interpolated normal under a point.
class Surface:
	var tris := []
	var buckets := {}

	func _init(nodes: Array) -> void:
		for node: MeshInstance3D in nodes:
			var to_world := node.global_transform if node.is_inside_tree() else node.transform
			for surface in node.mesh.get_surface_count():
				var arrays := node.mesh.surface_get_arrays(surface)
				var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
				var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
				var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
				for t in range(0, index.size(), 3):
					var a := to_world*verts[index[t]]
					var b := to_world*verts[index[t+1]]
					var c := to_world*verts[index[t+2]]
					var id := tris.size()
					tris.append([a, b, c, normals[index[t]], normals[index[t+1]], normals[index[t+2]]])
					var low := Vector2i(floori(minf(a.x, minf(b.x, c.x))/BUCKET), floori(minf(a.z, minf(b.z, c.z))/BUCKET))
					var high := Vector2i(floori(maxf(a.x, maxf(b.x, c.x))/BUCKET), floori(maxf(a.z, maxf(b.z, c.z))/BUCKET))
					for bz in range(low.y, high.y+1):
						for bx in range(low.x, high.x+1):
							var key := Vector2i(bx, bz)
							if not buckets.has(key): buckets[key] = PackedInt32Array()
							buckets[key].append(id)

	## {"y", "normal"} of the highest triangle over `at`, or {} for none.
	func sample(at: Vector2) -> Dictionary:
		var key := Vector2i(floori(at.x/BUCKET), floori(at.y/BUCKET))
		if not buckets.has(key): return {}
		var best := {}
		for id in buckets[key]:
			var t: Array = tris[id]
			var a: Vector3 = t[0]
			var b: Vector3 = t[1]
			var c: Vector3 = t[2]
			var v0 := Vector2(b.x-a.x, b.z-a.z)
			var v1 := Vector2(c.x-a.x, c.z-a.z)
			var v2 := Vector2(at.x-a.x, at.y-a.z)
			var den := v0.x*v1.y-v1.x*v0.y
			if absf(den) < 1e-12: continue
			var u := (v2.x*v1.y-v1.x*v2.y)/den
			var v := (v0.x*v2.y-v2.x*v0.y)/den
			if u < -1e-6 or v < -1e-6 or u+v > 1.0+1e-6: continue
			var y := a.y+u*(b.y-a.y)+v*(c.y-a.y)
			if best.is_empty() or y > float(best.y):
				best = {"y": y, "normal": ((t[3] as Vector3)*(1.0-u-v)+(t[4] as Vector3)*u+(t[5] as Vector3)*v).normalized()}
		return best
