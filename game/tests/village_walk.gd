extends SceneTree
## Walkability check for the island village without the server: builds the map,
## the town layout (roads, farm, gate) and the building dressing, then drives a real
## Player body (scripts/player.gd) with the movement actions:
##  - every road polyline in roads.gd end to end, forward and backward;
##  - from the nearest road point to every door in TownLayout.DOORS.
##  - across every bridge (environment_layout.json bridges) both ways, and from the
##    nearest road point to every TownLayout.PLACES spot (fishing piers, bell, farm...).
## Reports stuck points (no progress for more than 1.5 s), drops below
## TownLayout.SHORE_MIN_Y (the sea guard putting the walker back), ledges and every
## change between terrain (layer 1) and structures (layer 2: bridges, piers, ramps).
## Simulated time: run with --fixed-fps 60 so a long walk does not take real minutes.
##   Godot --headless --fixed-fps 60 --path game --script res://tests/village_walk.gd
##       -- [--run] [--only=road_name|door_id,...] [--verbose]
const Town = preload("res://scripts/town.gd")
const Roads = preload("res://scripts/roads.gd")
const PlayerBody = preload("res://scripts/player.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const DRESSING := "res://scripts/building_dressing.gd"
const STUCK_FRAMES := 90
const REACH := 0.45
var town: Node3D
var player: CharacterBody3D
var camera: Camera3D
var frame := 0
var verbose := false
var only: PackedStringArray = []
## Per-leg results and a flat list of problems for the summary.
var problems: Array[String] = []
var transitions: Array[String] = []
var legs := 0
var legs_ok := 0
var lowest := INF
var shore_resets := 0
var longest_air := 0
var _floor_layer := -1
var _floor_y := 0.0
var _last_pos := Vector3.ZERO
var _teleported := false

func _initialize() -> void:
	call_deferred("run")
	create_timer(1800).timeout.connect(func():
		push_error("village walk exceeded 30 minutes")
		quit(2))

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg == "--verbose": verbose = true
		if arg.begins_with("--only="): only = arg.trim_prefix("--only=").split(",")
	var started := Time.get_ticks_msec()
	camera = Camera3D.new()
	root.add_child(camera)
	town = Town.new()
	town.camera = camera
	root.add_child(town)
	# Tree roots, open-structure ramps and the road ribbons settle over a few frames.
	for i in 12: await physics_frame
	if ResourceLoader.exists(DRESSING):
		var dressing: Script = load(DRESSING)
		if dressing.has_method("dress"): dressing.dress(town.map)
	for i in 4: await physics_frame
	print("WALK_WORLD_MS ", Time.get_ticks_msec()-started)
	player = PlayerBody.new()
	root.add_child(player)
	player.min_ground_y = Town.SHORE_MIN_Y
	player.sprinting = "--run" in OS.get_cmdline_user_args()
	for road in Roads.ROADS:
		if not only.is_empty() and road[0] not in only: continue
		var pts: Array = road[2]
		await leg("road %s >" % road[0], pts)
		var back := pts.duplicate()
		back.reverse()
		await leg("road %s <" % road[0], back)
	for door in Town.DOORS:
		if not only.is_empty() and door.id not in only: continue
		var from := nearest_road_point(door.at)
		var gap: float = from.distance_to(door.at)
		if gap > 3.0: problems.append("DOOR %s is %.1f m from the nearest road" % [door.id, gap])
		var out: Vector2 = (door.at-door.center).normalized()
		# Up to the door step, then back out the way the walker leaves a room.
		await leg("door %s" % door.id, [from, door.at])
		await leg("door %s out" % door.id, [door.at, door.at+out*1.2, from])
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://maps/archipelago/environment_layout.json"))
	for bridge in layout.get("bridges", []):
		if not only.is_empty() and bridge.id not in only: continue
		var a := Vector2(bridge.a[0], bridge.a[1])
		var b := Vector2(bridge.b[0], bridge.b[1])
		var axis := (b-a).normalized()
		await leg("bridge %s >" % bridge.id, [a-axis*2.0, b+axis*2.0])
		await leg("bridge %s <" % bridge.id, [b+axis*2.0, a-axis*2.0])
	for place in Town.PLACES:
		if not only.is_empty() and place.id not in only: continue
		var from := nearest_road_point(place.at)
		await leg("place %s" % place.id, [from, place.at])
		await leg("place %s back" % place.id, [place.at, from])
	print("")
	for line in transitions:
		if verbose or "LEDGE" in line: print(line)
	print("TRANSITIONS ", transitions.size(), " (terrain <-> bridge/pier/ramp floor changes; --verbose lists all)")
	for line in problems: print("PROBLEM ", line)
	print("VILLAGE_WALK legs=%d ok=%d problems=%d shore_resets=%d lowest_y=%.2f longest_airborne_frames=%d sim_s=%.0f real_ms=%d" % [legs, legs_ok, problems.size(), shore_resets, lowest, longest_air, frame/60.0, Time.get_ticks_msec()-started])
	quit(0 if problems.is_empty() else 1)

static func nearest_road_point(at: Vector2) -> Vector2:
	var best := Vector2.INF
	for road in Roads.ROADS:
		var pts: Array = road[2]
		for i in pts.size()-1:
			var p := Geometry2D.get_closest_point_to_segment(at, pts[i], pts[i+1])
			if p.distance_to(at) < best.distance_to(at): best = p
	return best

func release() -> void:
	for action in ["move_left","move_right","move_forward","move_back"]: Input.action_release(action)

func place(at: Vector2) -> void:
	release()
	player.velocity = Vector3.ZERO
	player.global_position = Town.point(at, 0.15)
	player.has_safe_position = false
	_teleported = true
	_floor_layer = -1
	for i in 3: await physics_frame

## Walks a polyline from its first point. Returns true when every point was reached.
func leg(label: String, points: Array) -> bool:
	legs += 1
	await place(points[0])
	var ok := true
	var travelled := 0.0
	var started := frame
	for n in range(1, points.size()):
		var target: Vector2 = points[n]
		if not await walk_to(target, label):
			ok = false
			# Carry on from the next point so one blocker does not hide the rest.
			await place(target)
		travelled += Vector2(points[n-1]).distance_to(target)
	release()
	var seconds := maxf((frame-started)/60.0, .01)
	var pace := travelled/seconds
	var expected := Profile.VILLAGE_RUN if player.sprinting else Profile.VILLAGE_WALK
	if ok and pace < expected*0.6:
		problems.append("SLOW %s %.1f m/s over %.0f m (walls or props drag the walker)" % [label, pace, travelled])
	if verbose or not ok: print("LEG ", label, " ", "ok" if ok else "FAILED", " %.0f m in %.1f s" % [travelled, seconds])
	if ok: legs_ok += 1
	return ok

func walk_to(target: Vector2, label: String) -> bool:
	var best := INF
	var last_progress := frame
	var limit := frame + int(Vector2(player.position.x, player.position.z).distance_to(target)/2.0*60.0) + 600
	while true:
		var here := Vector2(player.position.x, player.position.z)
		var gap := target-here
		if gap.length() < REACH: return true
		if gap.length() < best-0.05:
			best = gap.length()
			last_progress = frame
		if frame-last_progress > STUCK_FRAMES or frame > limit:
			release()
			problems.append("STUCK %s at (%.1f, %.1f, y %.2f) toward (%.1f, %.1f)%s" % [label, here.x, here.y, player.position.y, target.x, target.y, blocker_near(player.position)])
			return false
		var d := gap.normalized()
		release()
		if d.x > 0.05: Input.action_press("move_right", d.x)
		if d.x < -0.05: Input.action_press("move_left", -d.x)
		if d.y > 0.05: Input.action_press("move_back", d.y)
		if d.y < -0.05: Input.action_press("move_forward", -d.y)
		await physics_frame
		frame += 1
		observe(label)
	return false

## Floor layer changes, shore resets, ledges and air time.
var _air := 0
func observe(label: String) -> void:
	var p := player.global_position
	lowest = minf(lowest, p.y)
	if not _teleported and p.distance_to(_last_pos) > 1.2:
		shore_resets += 1
		problems.append("SHORE_RESET %s: dropped below %.2f near (%.1f, %.1f), put back at (%.1f, %.1f)" % [label, Town.SHORE_MIN_Y, _last_pos.x, _last_pos.z, p.x, p.z])
	_teleported = false
	_last_pos = p
	if player.is_on_floor():
		longest_air = maxi(longest_air, _air)
		if _air > 30: problems.append("AIRBORNE %s for %d frames, landed at (%.1f, %.1f)" % [label, _air, p.x, p.z])
		_air = 0
	else:
		_air += 1
	var space := player.get_world_3d().direct_space_state
	var query := PhysicsRayQueryParameters3D.create(p+Vector3(0, .4, 0), p-Vector3(0, .8, 0), 1|2|8)
	var hit := space.intersect_ray(query)
	if hit.is_empty(): return
	var body := hit.collider as CollisionObject3D
	var layer := body.collision_layer if body else 0
	var y: float = hit.position.y
	if _floor_layer != -1 and layer != _floor_layer:
		var kind := {1:"terrain",2:"structure",8:"prop"}
		var line := "TRANSITION %s %s -> %s at (%.1f, %.1f) dy=%.2f (%s)" % [label, kind.get(_floor_layer, str(_floor_layer)), kind.get(layer, str(layer)), p.x, p.z, y-_floor_y, body.get_parent().name if body and body.get_parent() else "?"]
		if absf(y-_floor_y) > 0.3: line = "LEDGE " + line
		transitions.append(line)
	_floor_layer = layer
	_floor_y = y

## Names what the walker is pressed against, to say where a fix belongs.
func blocker_near(at: Vector3) -> String:
	var shape := SphereShape3D.new()
	shape.radius = Profile.BODY_RADIUS+0.25
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = shape
	query.collision_mask = 2|8|16
	query.transform = Transform3D(Basis.IDENTITY, at+Vector3(0, .7, 0))
	var names: Array[String] = []
	for hit in player.get_world_3d().direct_space_state.intersect_shape(query, 6):
		var node: Node = hit.collider
		var owner_name := ""
		while node and owner_name == "":
			if node.has_meta("placement_spec"): owner_name = str(node.get_meta("placement_spec").get("id", node.name))
			elif node.get_parent() and node.get_parent().name == "Buildings": owner_name = node.name
			node = node.get_parent()
		if owner_name == "": owner_name = str(hit.collider.get_parent().name)
		if owner_name not in names: names.append(owner_name)
	return (" against " + ", ".join(names)) if not names.is_empty() else " (terrain slope or ledge)"
