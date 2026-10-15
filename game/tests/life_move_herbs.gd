extends "res://tests/life_place_nodes.gd"
## Authoring tool (2026-10-16, STORY #18): moves the eight herb gather spots off the road edges
## into the shrubs. For each herb in forage.gd it looks for the nearest spot (within 9 m) that the
## gather-node sampler accepts (life_place_nodes.gd ok()) and that sits beside a shrub (40_shrub,
## 0.8-1.8 m away), at least 3 m from a road edge, 3 m from every other gather spot and every
## treasure chest, and clear of the café terrace and 모카's place. Prints the rows for forage.gd.
##   godot --headless --path game --script res://tests/life_move_herbs.gd
const Forage = preload("res://scripts/forage.gd")
const Treasure = preload("res://scripts/treasure.gd")

func run() -> void:
	var camera := Camera3D.new(); root.add_child(camera)
	var map: Node3D = Map.new(); root.add_child(map); map.build(camera)
	for i in 6: await physics_frame
	space = map.get_world_3d().direct_space_state
	var roads: Node3D = Roads.new(); map.add_child(roads); roads.build(space, map.get_node("Environment"))
	for i in 3: await physics_frame
	var shrubs: Array = []
	for node in map.get_node("Environment").prop_nodes:
		if not is_instance_valid(node): continue
		var id := str(node.get_meta("placement_spec", {}).get("id", ""))
		if id in ["37_round_tree", "38_conifer"]: trees.append(Vector2(node.global_position.x, node.global_position.z))
		if id == "40_shrub": shrubs.append(Vector2(node.global_position.x, node.global_position.z))
	print("SHRUBS ", shrubs.size())
	var keep: Array = []
	for row in Forage.NODES:
		if str(row[1]) != "herb": keep.append([str(row[1]), Vector2(float(row[2]), float(row[3]))])
	for chest in Treasure.FIELD: keep.append(["chest", Vector2(chest.at)])
	var moved: Array = []
	for row in Forage.NODES:
		if str(row[1]) != "herb": continue
		var from := Vector2(float(row[2]), float(row[3]))
		var best := Vector2.INF
		var best_gap := INF
		for r10 in range(0, 91, 3):
			var radius := float(r10)/10.0
			for k in (1 if radius == 0.0 else 24):
				var p := (from+Vector2.from_angle(TAU*k/24.0)*radius).snapped(Vector2(0.1, 0.1))
				if road_gap(p) < 3.0: continue
				var shrub := INF
				for s in shrubs: shrub = minf(shrub, p.distance_to(s))
				if shrub < 0.8 or shrub > 1.8: continue
				var crowded := false
				for other in keep+moved:
					if p.distance_to(other[1]) < 3.0: crowded = true
				for zone in Treasure.KEEP_CLEAR:
					if p.distance_to(zone[0]) < float(zone[1]): crowded = true
				if crowded or not ok("herb", p, []): continue
				if radius < best_gap:
					best_gap = radius
					best = p
			if best != Vector2.INF: break
		if best == Vector2.INF:
			print("KEEP ", row[0], " (no shrub spot within 9 m)")
			moved.append(["herb", from])
			print("NODE [\"%s\",\"herb\",%.1f,%.1f]," % [row[0], from.x, from.y])
		else:
			moved.append(["herb", best])
			print("NODE [\"%s\",\"herb\",%.1f,%.1f],  # moved %.1f m, road gap %.1f" % [row[0], best.x, best.y, best_gap, road_gap(best)])
	quit()
