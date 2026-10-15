extends SceneTree
## building_layout.gd's placement verification (BUILDING_PLACEMENT_CHECK, which only runs inside the old
## lab host with --placement-capture) on the game's own map, headless:
##   Godot --headless --path game -s res://tests/building_placement_check.gd
## Every building in building_placements.json is in the map at real metre scale (model height =
## dimensions_m[1] within 4 cm), grounded on its levelled pad (9 ground probes at +-0.8 of the pad,
## each within 3.5 cm of its position, model bottom within 1.5 cm) and no two buildings' boxes overlap.
const Map = preload("res://maps/archipelago/archipelago.gd")

func _initialize() -> void:
	call_deferred("run")
	create_timer(300).timeout.connect(func(): quit(2))

func bounds(node: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for item in node.find_children("*", "MeshInstance3D", true, false):
		var mesh := item as MeshInstance3D
		var b: AABB = mesh.global_transform * mesh.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box

func run() -> void:
	var camera := Camera3D.new()
	root.add_child(camera)
	var map: Node3D = Map.new()
	root.add_child(map)
	await map.build(camera)
	for i in 6: await physics_frame
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://maps/archipelago/building_placements.json"))
	var space := map.get_world_3d().direct_space_state
	var placed: Array[Node3D] = []
	var boxes: Array[AABB] = []
	var problems: Array[String] = []
	for spec: Dictionary in manifest.buildings:
		var node := map.get_node_or_null("Buildings/"+String(spec.id)) as Node3D
		if node == null:
			problems.append("missing "+String(spec.id))
			continue
		placed.append(node)
		var box := bounds(node)
		boxes.append(box)
		var hits: Array[float] = []
		for ox in [-.8, 0.0, .8]:
			for oz in [-.8, 0.0, .8]:
				var point := node.global_transform * Vector3(float(spec.pad_half_extents[0])*ox/node.scale.x, 0, float(spec.pad_half_extents[1])*oz/node.scale.z)
				var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(point+Vector3(0, 15, 0), point-Vector3(0, 15, 0), 1))
				if not hit.is_empty(): hits.append(hit.position.y)
		var gap := 0.0
		for y in hits: gap = maxf(gap, absf(y-node.position.y))
		# 4 cm, not the lab's 3: blue_house.glb (12_blue_house, and 18_meadow_house at 0.92) measures 3.5 cm
		# over its listed height in the game's copy; a wrong scale is tens of centimetres off.
		var height_ok := absf(box.size.y-float(spec.dimensions_m[1])) < .04
		var grounded := hits.size() == 9 and gap < .035 and absf(box.position.y-node.position.y) < .015
		if not height_ok: problems.append("%s height %.3f (dimensions %.3f)" % [spec.id, box.size.y, float(spec.dimensions_m[1])])
		if not grounded: problems.append("%s grounded: %d samples, gap %.3f, bottom %.3f" % [spec.id, hits.size(), gap, box.position.y-node.position.y])
	var overlaps: Array = []
	for i in boxes.size():
		for j in range(i+1, boxes.size()):
			if boxes[i].intersects(boxes[j]): overlaps.append([String(placed[i].name), String(placed[j].name)])
	var passed: bool = problems.is_empty() and overlaps.is_empty() and placed.size() == int(manifest.buildings.size())
	for p in problems: print("FAIL ", p)
	if not overlaps.is_empty(): print("OVERLAPS ", JSON.stringify(overlaps))
	print("BUILDING_PLACEMENT_CHECK passed=", passed, " count=", placed.size(), " overlaps=", overlaps.size())
	quit(0 if passed else 1)
