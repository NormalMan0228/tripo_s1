extends SceneTree
## Automatic stutter / teleport check (tests/motion_watch.gd) on the real walkers, drawn at a
## faster screen rate than the 60 Hz physics (as on a 144 Hz monitor), in real time:
##  village  the real Player walks the island village (a road, onto the lighthouse pier ledge and
##           back, a door with steps) under the follow camera while residents walk around it;
##  room     the walker in a room (studio.tscn, WASD path at screen rate) and up a staircase
##           (the scripted climb; frames under the black fade are not judged);
##  multi    another player drawn from an irregular presence feed (remote_motion.gd on a
##           visual_only player.gd, as social.gd draws it), with a 12 m door jump (allowed: the
##           feed flags it and an effect plays).
## Prints MOTION_WATCH lines and MOTION_CONTINUITY PASS/FAIL. Headless, no server, no credits:
##   Godot --headless --path game --script res://tests/motion_continuity.gd -- [--scene=village,room,multi] [--fps=144]
## Do not pass --fixed-fps: drawn frames must come between physics ticks.
const MotionWatch = preload("res://tests/motion_watch.gd")
const Stub = preload("res://tests/shadow_folk_stub.gd")
const Folk = preload("res://scripts/shadow_folk.gd")
const Town = preload("res://scripts/town.gd")
const Roads = preload("res://scripts/roads.gd")
const PlayerBody = preload("res://scripts/player.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const RemoteMotion = preload("res://scripts/remote_motion.gd")

var watch: MotionWatch
var camera: Camera3D
var player: CharacterBody3D
var focus := Vector3.ZERO
var focus_ready := false
var follow_camera := true
var results := {}
var failed := false

func _initialize() -> void:
	call_deferred("run")
	create_timer(600).timeout.connect(func():
		push_error("motion continuity exceeded 10 minutes")
		quit(2))

func arg(name: String, fallback: String) -> String:
	for item in OS.get_cmdline_user_args():
		if item.begins_with("--"+name+"="): return item.trim_prefix("--"+name+"=")
	return fallback

func run() -> void:
	Engine.max_fps = int(arg("fps", "144"))
	seed(20261016)
	var scenes := arg("scene", "village,room,multi").split(",")
	for scene in scenes:
		_last_ticks = Engine.get_physics_frames()
		match scene:
			"village": await village()
			"room": await room()
			"multi": await multi()
			_: push_error("unknown scene "+scene)
	print("MOTION_CONTINUITY ", "FAIL" if failed else "PASS", " ", JSON.stringify(results))
	quit(1 if failed else 0)

func finish(name: String) -> void:
	var result := watch.report()
	MotionWatch.print_report(name, result)
	results[name] = "PASS" if result.pass else "FAIL"
	if not result.pass: failed = true

## main.gd follow_camera(): the drawn walker, smoothed, at the fixed orthographic offset.
func follow(delta: float) -> void:
	if not is_instance_valid(player) or not follow_camera: return
	var target: Vector3 = player.render_position()+Profile.CAMERA_FOCUS_OFFSET
	if not focus_ready:
		focus = target
		focus_ready = true
	else: focus = focus.lerp(target, Profile.damping(Profile.CAMERA_RESPONSE, delta))
	camera.position = focus+Profile.CAMERA_OFFSET*Profile.CAMERA_PULLBACK
	camera.look_at(focus)

## Runs `frames_or_until` drawn frames, sampling every frame and tick.
func frames(count: int) -> void:
	for i in count: await one_frame()

var _last_ticks := 0
func one_frame() -> void:
	await process_frame
	var delta := get_process_delta()
	follow(delta)
	var now := Engine.get_physics_frames()
	if now != _last_ticks:
		_last_ticks = now
		watch.tick()
	watch.frame(delta)

func get_process_delta() -> float:
	return root.get_process_delta_time()

func release() -> void:
	for action in ["move_left", "move_right", "move_forward", "move_back"]: Input.action_release(action)

func steer(d: Vector2) -> void:
	release()
	if d.x > 0.05: Input.action_press("move_right", d.x)
	if d.x < -0.05: Input.action_press("move_left", -d.x)
	if d.y > 0.05: Input.action_press("move_back", d.y)
	if d.y < -0.05: Input.action_press("move_forward", -d.y)

## Walks the player through `points` (x, z) with the movement actions; false when stuck.
func walk(points: Array, run := false) -> bool:
	player.sprinting = run
	for target in points:
		var best := INF
		var since := 0
		while true:
			var here := Vector2(player.position.x, player.position.z)
			var gap: Vector2 = target-here
			if gap.length() < 0.45: break
			if gap.length() < best-0.05:
				best = gap.length()
				since = 0
			since += 1
			if since > 240:
				release()
				print("  STUCK walking to ", target, " at ", here)
				return false
			steer(gap.normalized())
			await one_frame()
	release()
	return true

static func nearest_road_point(at: Vector2) -> Vector2:
	var best := Vector2.INF
	for road in Roads.ROADS:
		var pts: Array = road[2]
		for i in pts.size()-1:
			var p := Geometry2D.get_closest_point_to_segment(at, pts[i], pts[i+1])
			if p.distance_to(at) < best.distance_to(at): best = p
	return best

## ------------------------------------------------------------------ village
func village() -> void:
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = Profile.VILLAGE_CAMERA_DEFAULT
	camera.far = 400.0
	root.add_child(camera)
	camera.current = true
	var app = Stub.new()
	root.add_child(app)
	app.build(camera)
	for i in 8: await physics_frame
	app.spawn_villagers()
	app.daylight.override_hour = 10.0
	# The real walker in place of the stub body.
	var stub_body: Node = app.player
	app.remove_child(stub_body)
	stub_body.queue_free()
	player = PlayerBody.new()
	player.min_ground_y = Town.SHORE_MIN_Y
	app.player = player
	app.add_child(player)
	var start := Vector2(-36.5, 30.5)
	player.global_position = Town.point(start, 0.15)
	var folk = Folk.new()
	folk.persist = false
	app.add_child(folk)
	folk.setup(app)
	for i in 30: await physics_frame
	# Residents on the paths around the walker's route, so they walk on screen.
	var near: Array = []
	for i in folk.paths.points.size():
		if Vector2(folk.paths.points[i]).distance_to(start) < 22.0 and not folk.paths.links[i].is_empty(): near.append(i)
	var placed := 0
	for walker in folk.walkers:
		if near.is_empty() or placed >= 8: break
		var node: int = near[placed*7 % near.size()]
		walker.set_present(true)
		walker.place_at(node, folk.paths.links[node][0])
		placed += 1
	watch = MotionWatch.new(camera)
	watch.add("player", player, {"speed": Profile.VILLAGE_RUN, "draw": player.visual,
		"skeleton": func(): return player.hand_skeleton})
	for walker in folk.walkers:
		var w = walker
		watch.add("resident_"+str(w.spec.id), w, {"speed": maxf(2.5, w.pace*2.0), "draw": w.visual,
			"skeleton": func(): return w.skeleton, "shown": func(): return w.present and w.fade > 0.9 and w.state != "hidden"})
	await frames(30)
	# A road walk, a run, onto the lighthouse pier (a 0.46 m ledge) and back, a door with steps.
	var road: Array = Roads.ROADS[0][2]
	await walk([nearest_road_point(start)])
	await walk(road.slice(0, mini(4, road.size())))
	await walk(road.slice(0, mini(4, road.size())).duplicate().slice(0, 1), true)
	var sea: Vector2 = Vector2(-4, 82.6)
	var shore := nearest_road_point(sea)
	player.global_position = Town.point(shore, 0.15)
	player.velocity = Vector3.ZERO
	focus_ready = false
	watch.excuse("player", 3)
	await frames(10)
	await walk([sea])
	await frames(20)
	await walk([shore], true)
	var door: Dictionary = Town.DOORS[0]
	var outside := nearest_road_point(door.at)
	player.global_position = Town.point(outside, 0.15)
	player.velocity = Vector3.ZERO
	focus_ready = false
	watch.excuse("player", 3)
	await frames(10)
	await walk([door.at])
	await walk([outside])
	await frames(30)
	finish("village")
	release()
	app.queue_free()
	camera.queue_free()
	player = null
	await process_frame

## ------------------------------------------------------------------ room
func room() -> void:
	follow_camera = false
	Engine.set_meta("interior_hour", 13.0)
	Engine.set_meta("studio_session", {"token":"", "url":"http://127.0.0.1:9", "room":arg("room", "01_cafe")})
	var app: Control = load("res://scenes/studio.tscn").instantiate()
	root.add_child(app)
	await create_timer(0.5).timeout
	player = app.hero
	var veil_dark := func() -> bool:
		var veil = root.get_node_or_null("Transition")
		return veil != null and veil.get("veil") != null and veil.veil.modulate.a > 0.6
	watch = MotionWatch.new(app.camera)
	watch.add("room_walker", player, {"speed": Profile.ROOM_WALK, "draw": player.visual,
		"skeleton": func(): return player.hand_skeleton, "shown": func(): return not veil_dark.call()})
	await frames(20)
	# Around the room: four directions and diagonals, starts and stops.
	for d in [Vector2(1, 0), Vector2(0, -1), Vector2(-1, 0), Vector2(0.7, 0.7), Vector2(-0.7, -0.7), Vector2(0, 1)]:
		steer(d)
		await frames(70)
		release()
		await frames(12)
	# Up the first staircase, ladder or hatch on this floor.
	var stair: Dictionary = {}
	for record in app.decor:
		if record.has("link"):
			stair = record
			break
	if not stair.is_empty():
		app.travel_enabled = true
		app.travel(stair)
		for i in 900:
			await one_frame()
			if not app.travelling: break
		await frames(40)
	else: print("  ROOM no staircase in ", arg("room", "01_cafe"))
	finish("room")
	release()
	app.queue_free()
	player = null
	Engine.remove_meta("interior_hour")
	Engine.remove_meta("studio_session")
	follow_camera = true
	await process_frame

## ------------------------------------------------------------------ multi
func multi() -> void:
	follow_camera = false
	var stage := Node3D.new()
	root.add_child(stage)
	var floor := StaticBody3D.new()
	stage.add_child(floor)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(200, 0.2, 200)
	shape.shape = box
	floor.add_child(shape)
	floor.position.y = -0.1
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 26.0
	stage.add_child(camera)
	camera.position = Vector3(0, 8.8, 16.5)*2.5
	camera.look_at(Vector3.ZERO)
	camera.current = true
	var other = PlayerBody.new()
	other.controls_enabled = false
	other.visual_only = true
	stage.add_child(other)
	var motion = RemoteMotion.new()
	watch = MotionWatch.new(camera)
	watch.add("other_player", other, {"speed": Profile.VILLAGE_RUN, "draw": other.visual,
		"skeleton": func(): return other.hand_skeleton})
	var rng := RandomNumberGenerator.new()
	rng.seed = 77
	# The sender: a loop at walking pace, a run, stops and a door jump of 12 m at 9 s.
	var sender := Vector3(-6, 0, 0)
	var heading := Vector2(1, 0)
	var started := RemoteMotion.now()
	var next_post := started
	var last_t := started
	while RemoteMotion.now()-started < 14.0:
		await process_frame
		var t: float = RemoteMotion.now()-started
		var dt: float = RemoteMotion.now()-last_t
		last_t = RemoteMotion.now()
		var speed := 0.0 if fmod(t, 5.0) > 4.2 else (4.5 if t > 6.0 and t < 8.5 else 2.8)
		heading = heading.rotated(0.35*dt)
		sender += Vector3(heading.x, 0, heading.y)*speed*dt
		if t > 9.0 and t-dt <= 9.0: sender += Vector3(12, 0, 0)
		if RemoteMotion.now() >= next_post:
			next_post = RemoteMotion.now()+0.25+rng.randf_range(-0.12, 0.12)
			motion.push(RemoteMotion.now(), sender, RemoteMotion.now(), atan2(-heading.x, -heading.y), Vector3(heading.x, 0, heading.y)*speed)
		var delta := root.get_process_delta_time()
		var was: bool = motion.teleported
		motion.update(delta)
		if motion.teleported and not was: watch.excuse("other_player", 4)
		motion.apply_to(other)
		var now_ticks := Engine.get_physics_frames()
		if now_ticks != _last_ticks:
			_last_ticks = now_ticks
			watch.tick()
		watch.frame(delta)
	finish("multi")
	stage.queue_free()
	follow_camera = true
	await process_frame
