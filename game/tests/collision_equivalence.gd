extends SceneTree
## Walkability with the generated (simplified, chunked) colliders against the render-mesh trimeshes the
## map makes without them (maps/archipelago/island_bake.gd, tools/bake_archipelago.gd). Headless:
##   Godot --headless --path game --script res://tests/collision_equivalence.gd [-- --step=0.5 --strict]
## Builds the map twice (generated data off, then on) and probes a grid over the islands each time:
##   ground   a ray from above with the walk mask (1|2|8) and one for the ground alone (1): heights
##   stand    the walker's capsule (r 0.32, h 1.5) lifted by its step height (0.36) above the floor
##            hit there, against everything the walker collides with (1|2|8|32): room to stand?
##   move     between standable neighbours with at most a step between them, the capsule swept
##            from one to the other: can it walk across?
##   reach    cells reachable from the spawn by such moves (doors, bridges, ramps and pads included)
## Fails when a group of more than JITTER_CELLS reachable cells changes (either way), when a door,
## bridge end or pavilion floor is reached from further away, or when a walkable height (floors up to
## 45 degrees, where the walker could reach) moves more than 5 cm. Mismatches are listed with the colliders the walker touches
## there. Prints COLLISION_EQUIVALENCE {...}.
const Map = preload("res://maps/archipelago/archipelago.gd")
const IslandBake = preload("res://maps/archipelago/island_bake.gd")
const Town = preload("res://scripts/town.gd")
const RADIUS := 0.32
const HEIGHT := 1.5
const STEP := 0.36
const WALK := 1|2|8
const BODY := 1|2|8|32
## Reach changes in groups of at most this many cells are a capsule grazing a wall that moved by
## millimetres (cells exactly at the limit flip either way); larger groups fail.
const JITTER_CELLS := 2
var step := 0.5
var origin := Vector2(-104, -82)
var cells := Vector2i(0, 0)
var failures: Array[String] = []

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--step="): step = float(arg.trim_prefix("--step="))
	cells = Vector2i(int(212/step), int(186/step))
	call_deferred("run")

func run() -> void:
	var started := Time.get_ticks_msec()
	IslandBake.disabled = true
	IslandBake.reset()
	var exact := await probe_build("render-mesh trimeshes")
	IslandBake.disabled = false
	IslandBake.reset()
	if not IslandBake.fresh():
		print("COLLISION_EQUIVALENCE ", JSON.stringify({"ok": false, "failures": ["no fresh generated data: run tools/bake_archipelago.py (%s)" % IslandBake.problem()]}))
		quit(1)
		return
	var generated := await probe_build("generated chunks")
	var report := compare(exact, generated)
	report["seconds"] = (Time.get_ticks_msec()-started)/1000.0
	report["ok"] = failures.is_empty()
	report["failures"] = failures
	print("COLLISION_EQUIVALENCE ", JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)

func probe_build(label: String) -> Dictionary:
	# Each build in its own world (physics space), so both stay queryable for the comparison.
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
	map.build(camera)
	var build_ms := Time.get_ticks_msec()-t
	for i in 12: await physics_frame
	var roads: Node3D = preload("res://scripts/roads.gd").new()
	roads.name = "Roads"
	map.add_child(roads)
	await roads.build(map.get_world_3d().direct_space_state, map.get_node_or_null("Environment"))
	for i in 4: await physics_frame
	var shapes := 0
	var triangles := 0
	for cs: CollisionShape3D in map.find_children("*", "CollisionShape3D", true, false):
		shapes += 1
		if cs.shape is ConcavePolygonShape3D: triangles += (cs.shape as ConcavePolygonShape3D).get_faces().size()/3
	var space := map.get_world_3d().direct_space_state
	var count := cells.x*cells.y
	var steep := PackedByteArray()
	steep.resize(count)
	var walk := PackedFloat32Array()
	var ground := PackedFloat32Array()
	var stand := PackedByteArray()
	walk.resize(count)
	ground.resize(count)
	stand.resize(count)
	var capsule := CapsuleShape3D.new()
	capsule.radius = RADIUS
	capsule.height = HEIGHT
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.collision_mask = BODY
	t = Time.get_ticks_msec()
	for j in cells.y:
		for i in cells.x:
			var at := origin+Vector2(i, j)*step
			var index := j*cells.x+i
			var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x, 60, at.y), Vector3(at.x, -20, at.y), WALK))
			walk[index] = hit.position.y if not hit.is_empty() else NAN
			# A floor steeper than the walker's 45 degrees: its vertical-ray height jumps with any shift.
			steep[index] = 1 if not hit.is_empty() and hit.normal.y < 0.7 else 0
			var low := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x, 60, at.y), Vector3(at.x, -20, at.y), 1))
			ground[index] = low.position.y if not low.is_empty() else NAN
			if hit.is_empty(): continue
			query.transform = Transform3D(Basis.IDENTITY, Vector3(at.x, walk[index]+STEP+HEIGHT*0.5+0.01, at.y))
			stand[index] = 1 if space.intersect_shape(query, 1).is_empty() else 0
	var stand_ms := Time.get_ticks_msec()-t
	# Moves to the east and south neighbours (both standable, at most a step apart), swept.
	var east := PackedByteArray()
	var south := PackedByteArray()
	east.resize(count)
	south.resize(count)
	t = Time.get_ticks_msec()
	for j in cells.y:
		for i in cells.x:
			var index := j*cells.x+i
			if stand[index] == 0: continue
			for side in 2:
				var other := index+1 if side == 0 else index+cells.x
				if (side == 0 and i+1 >= cells.x) or (side == 1 and j+1 >= cells.y) or stand[other] == 0: continue
				if absf(walk[index]-walk[other]) > STEP: continue
				var from := origin+Vector2(i, j)*step
				var y := maxf(walk[index], walk[other])+STEP+HEIGHT*0.5+0.01
				query.transform = Transform3D(Basis.IDENTITY, Vector3(from.x, y, from.y))
				query.motion = Vector3(step, 0, 0) if side == 0 else Vector3(0, 0, step)
				var free := space.cast_motion(query)
				query.motion = Vector3.ZERO
				if free.size() == 2 and free[0] >= 1.0:
					if side == 0: east[index] = 1
					else: south[index] = 1
	var move_ms := Time.get_ticks_msec()-t
	var reach := reachable(stand, east, south, walk)
	print("PROBED %s: build %d ms, %d shapes, %d triangles, stand %d ms, moves %d ms, reachable %d cells" % [label, build_ms, shapes, triangles, stand_ms, move_ms, reach.count(1)])
	return {"walk": walk, "ground": ground, "stand": stand, "east": east, "south": south, "reach": reach, "shapes": shapes,
		"triangles": triangles, "build_ms": build_ms, "steep": steep, "space": space, "map": map}

## What the walker's capsule touches standing at a cell (lifted by its step), as short collider paths.
func touching(build: Dictionary, index: int) -> Array:
	var at := origin+Vector2(index % cells.x, index/cells.x)*step
	var capsule := CapsuleShape3D.new()
	capsule.radius = RADIUS
	capsule.height = HEIGHT
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.collision_mask = BODY
	var y: float = build.walk[index] if not is_nan(build.walk[index]) else 0.0
	query.transform = Transform3D(Basis.IDENTITY, Vector3(at.x, y+STEP+HEIGHT*0.5+0.01, at.y))
	var names := []
	for hit in (build.space as PhysicsDirectSpaceState3D).intersect_shape(query, 4):
		var path := String((build.map as Node).get_path_to(hit.collider))
		names.append(path.get_slice("/", 0)+"/"+path.get_slice("/", 1))
	return names

func ray_collider(build: Dictionary, at: Vector2) -> String:
	var hit := (build.space as PhysicsDirectSpaceState3D).intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x, 60, at.y), Vector3(at.x, -20, at.y), WALK))
	if hit.is_empty(): return ""
	var path := String((build.map as Node).get_path_to(hit.collider))
	return path.get_slice("/", 0)+"/"+path.get_slice("/", 1)

## Mismatched cells in 8-connected groups: [[size, [x, z] of the first, colliders touched], ...].
func clusters(marks: Dictionary, a: Dictionary, b: Dictionary) -> Array:
	var out := []
	var seen := {}
	for start: int in marks:
		if seen.has(start): continue
		var group := [start]
		seen[start] = true
		var head := 0
		while head < group.size():
			var index: int = group[head]
			head += 1
			for dj in [-1, 0, 1]:
				for di in [-1, 0, 1]:
					var other: int = index+dj*cells.x+di
					if marks.has(other) and not seen.has(other):
						seen[other] = true
						group.append(other)
		var at := origin+Vector2(start % cells.x, start/cells.x)*step
		var names := {}
		for index: int in group:
			for name in touching(a, index)+touching(b, index): names[name] = true
		out.append([group.size(), [snappedf(at.x, 0.1), snappedf(at.y, 0.1)], names.keys().slice(0, 4)])
	out.sort_custom(func(x, y): return x[0] > y[0])
	return out

func cell_of(at: Vector2) -> int:
	var c := Vector2i(((at-origin)/step).round())
	return c.y*cells.x+c.x

func reachable(stand: PackedByteArray, east: PackedByteArray, south: PackedByteArray, walk: PackedFloat32Array) -> PackedByteArray:
	var reach := PackedByteArray()
	reach.resize(stand.size())
	# Start at the standable cell nearest the spawn.
	var start := cell_of(Town.SPAWN)
	var best := INF
	for dj in range(-6, 7):
		for di in range(-6, 7):
			var index := start+dj*cells.x+di
			if index >= 0 and index < stand.size() and stand[index] == 1 and Vector2(di, dj).length() < best:
				best = Vector2(di, dj).length()
				start = index
	var queue := PackedInt32Array([start])
	reach[start] = 1
	var head := 0
	while head < queue.size():
		var index := queue[head]
		head += 1
		var links := []
		if east[index] == 1: links.append(index+1)
		if south[index] == 1: links.append(index+cells.x)
		if index % cells.x > 0 and east[index-1] == 1: links.append(index-1)
		if index >= cells.x and south[index-cells.x] == 1: links.append(index-cells.x)
		for other: int in links:
			if reach[other] == 0:
				reach[other] = 1
				queue.append(other)
	return reach

func compare(a: Dictionary, b: Dictionary) -> Dictionary:
	var count := cells.x*cells.y
	var walk_moved := 0
	var walk_missing := 0
	var ground_moved := 0
	var largest := 0.0
	var largest_ground := 0.0
	var deltas: Array[float] = []
	var walk_where := []
	var stand_changed := 0
	var moves_changed := 0
	var lost := {}
	var gained := {}
	for index in count:
		var wa: float = a.walk[index]
		var wb: float = b.walk[index]
		if is_nan(wa) != is_nan(wb): walk_missing += 1
		elif not is_nan(wa) and a.steep[index] == 0 and b.steep[index] == 0:
			var d := absf(wa-wb)
			deltas.append(d)
			largest = maxf(largest, d)
			# Only where the walker can be (reachable before): roofs and the tops of props do not count.
			if d > 0.05 and a.reach[index] == 1:
				walk_moved += 1
				if walk_where.size() < 12:
					var at := origin+Vector2(index % cells.x, index/cells.x)*step
					walk_where.append([snappedf(at.x, 0.1), snappedf(at.y, 0.1), snappedf(wa, 0.01), snappedf(wb, 0.01), ray_collider(a, at), ray_collider(b, at)])
		var ga: float = a.ground[index]
		var gb: float = b.ground[index]
		if not is_nan(ga) and not is_nan(gb) and a.steep[index] == 0:
			largest_ground = maxf(largest_ground, absf(ga-gb))
			if absf(ga-gb) > 0.02: ground_moved += 1
		if a.stand[index] != b.stand[index]: stand_changed += 1
		if a.east[index] != b.east[index] or a.south[index] != b.south[index]: moves_changed += 1
		if a.reach[index] == 1 and b.reach[index] == 0: lost[index] = true
		if a.reach[index] == 0 and b.reach[index] == 1: gained[index] = true
	deltas.sort()
	var p99: float = deltas[int(deltas.size()*0.99)] if not deltas.is_empty() else 0.0
	# Places that must stay reachable: every door, both ends of every bridge, the pavilion floors.
	var places := {}
	for door: Dictionary in Town.DOORS: places["door "+String(door.id)] = Vector2(door.at)
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://maps/archipelago/environment_layout.json"))
	for bridge: Dictionary in layout.bridges:
		places["bridge %s a" % bridge.id] = Vector2(bridge.a[0], bridge.a[1])
		places["bridge %s b" % bridge.id] = Vector2(bridge.b[0], bridge.b[1])
	for id in Map.OPEN_STRUCTURES: places["floor "+id] = Map.OPEN_STRUCTURES[id][0]
	var place_report := {}
	for name: String in places:
		var near := nearest_reached(a.reach, places[name])
		var near_b := nearest_reached(b.reach, places[name])
		place_report[name] = [snappedf(near, 0.01), snappedf(near_b, 0.01)]
		if near_b > near+step*1.5: failures.append("%s: nearest reachable cell %.2f m away, was %.2f m" % [name, near_b, near])
	# A change of reach larger than a cell or two at the edge of a wall is a change of walkability.
	var lost_groups := clusters(lost, a, b)
	var gained_groups := clusters(gained, a, b)
	for group in lost_groups: if group[0] > JITTER_CELLS: failures.append("%d cells around %s no longer reachable (%s)" % group)
	for group in gained_groups: if group[0] > JITTER_CELLS: failures.append("%d cells around %s newly reachable (%s)" % group)
	if walk_moved > 0: failures.append("%d walk heights moved more than 5 cm (largest %.3f m)" % [walk_moved, largest])
	var report := {"grid": [cells.x, cells.y, step], "cells": count,
		"exact": {"shapes": a.shapes, "triangles": a.triangles, "build_ms": a.build_ms, "reachable": a.reach.count(1), "standable": a.stand.count(1)},
		"generated": {"shapes": b.shapes, "triangles": b.triangles, "build_ms": b.build_ms, "reachable": b.reach.count(1), "standable": b.stand.count(1)},
		"walk_height": {"largest_m": snappedf(largest, 0.0001), "p99_m": snappedf(p99, 0.0001), "moved_over_5cm": walk_moved, "hit_changed": walk_missing, "where": walk_where},
		"ground_height": {"largest_m": snappedf(largest_ground, 0.0001), "moved_over_2cm": ground_moved},
		"stand_changed": stand_changed, "moves_changed": moves_changed,
		"reach_lost_count": lost.size(), "reach_gained_count": gained.size(),
		"reach_lost_groups": lost_groups.slice(0, 12), "reach_gained_groups": gained_groups.slice(0, 12),
		"places": place_report}
	return report

func nearest_reached(reach: PackedByteArray, at: Vector2) -> float:
	var centre := Vector2i(((at-origin)/step).round())
	var best := INF
	for dj in range(-8, 9):
		for di in range(-8, 9):
			var c := centre+Vector2i(di, dj)
			if c.x < 0 or c.y < 0 or c.x >= cells.x or c.y >= cells.y: continue
			if reach[c.y*cells.x+c.x] == 1: best = minf(best, (origin+Vector2(c)*step).distance_to(at))
	return best
