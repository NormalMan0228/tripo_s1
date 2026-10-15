extends SceneTree
## Frame time in a crowded village (every resident out, on screen around the walker), drawn in a
## window with no frame cap: the on-screen animation LOD (anim_lod.gd) against the old camera-distance
## rule, alternating in 6 s rounds. Prints MOTION_FPS lines (avg / worst 1 % ms, walker CPU).
##   Godot --position X,Y --path game --script res://tests/motion_fps.gd
const Stub = preload("res://tests/shadow_folk_stub.gd")
const Folk = preload("res://scripts/shadow_folk.gd")
const Figure = preload("res://scripts/shadow_figure.gd")
const Town = preload("res://scripts/town.gd")
const PlayerBody = preload("res://scripts/player.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const AnimLod = preload("res://scripts/anim_lod.gd")

func _initialize() -> void: call_deferred("run")

func run() -> void:
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = Profile.VILLAGE_CAMERA_DEFAULT
	camera.far = 400.0
	root.add_child(camera)
	var app = Stub.new()
	root.add_child(app)
	app.build(camera)
	for i in 8: await physics_frame
	app.spawn_villagers()
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	sun.shadow_enabled = true
	app.add_child(sun)
	var stub_body: Node = app.player
	app.remove_child(stub_body)
	stub_body.queue_free()
	var player = PlayerBody.new()
	app.player = player
	app.add_child(player)
	var start := Vector2(-36.5, 30.5)
	player.global_position = Town.point(start, 0.15)
	var folk = Folk.new()
	folk.persist = false
	app.add_child(folk)
	folk.setup(app)
	var near: Array = []
	for i in folk.paths.points.size():
		if Vector2(folk.paths.points[i]).distance_to(start) < 12.0 and not folk.paths.links[i].is_empty(): near.append(i)
	var k := 0
	for walker in folk.walkers:
		walker.set_present(true)
		var node: int = near[(k*5) % near.size()]
		walker.place_at(node, folk.paths.links[node][0])
		k += 1
	var focus: Vector3 = player.global_position+Profile.CAMERA_FOCUS_OFFSET
	camera.position = focus+Profile.CAMERA_OFFSET*Profile.CAMERA_PULLBACK
	camera.look_at(focus)
	camera.current = true
	AnimLod.legacy_eye = camera.global_position
	await create_timer(2.0).timeout
	var results := {"lod": [], "legacy": []}
	for round_index in 4:
		var mode := "lod" if round_index % 2 == 0 else "legacy"
		AnimLod.legacy = mode == "legacy"
		await create_timer(0.5).timeout
		Figure.profile = true
		Figure.profile_us = 0
		var times := PackedFloat32Array()
		var started := Time.get_ticks_usec()
		var ticks0 := Engine.get_physics_frames()
		while Time.get_ticks_usec()-started < 6000000:
			await process_frame
			times.append(root.get_process_delta_time())
		Figure.profile = false
		var ticks := maxi(1, Engine.get_physics_frames()-ticks0)
		times.sort()
		var total := 0.0
		for t in times: total += t
		var worst := 0.0
		var n := maxi(1, times.size()/100)
		for i in n: worst += times[times.size()-1-i]
		var visible := 0
		for walker in folk.walkers: if walker.visible and walker.anim_stride == 1: visible += 1
		var line := {"mode":mode, "fps":snappedf(times.size()/6.0, 0.1), "avg_ms":snappedf(total/times.size()*1000.0, 0.01), "worst1_ms":snappedf(worst/n*1000.0, 0.01), "walker_ms_per_tick":snappedf(Figure.profile_us/1000.0/ticks, 0.001), "walkers":folk.walkers.size(), "every_tick":visible}
		results[mode].append(line)
		print("MOTION_FPS ", JSON.stringify(line))
	AnimLod.legacy = false
	quit(0)
