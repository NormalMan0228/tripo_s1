extends SceneTree
## Frame cost of the under-foot effects in the real village (tools/test.ps1 -ClientScript foot_fx_perf
## -Capture; windowed, so the renderer is real). The hero runs back and forth on open grass while
## eight remote walkers' steps are fed to world_audio `stepped` at walking cadence (24 steps/s,
## over FootFx's 12/s budget). Three 8 s phases: effects off, hero only, hero + crowd. Prints the
## mean and 95th-percentile frame time of each phase (same run, so other load on the PC is shared).
const Main := preload("res://scripts/main.gd")
const Fx := preload("res://scripts/fx.gd")
var app: Node3D
var feet: Node

func _initialize() -> void: call_deferred("run_test")

func ground(x: float, z: float) -> Dictionary:
	return app.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(x, 60, z), Vector3(x, -10, z), 1|2))

func open_grass() -> Vector3:
	var Roads = preload("res://scripts/roads.gd")
	for r in range(20, 100, 4):
		for k in 36:
			var a := TAU*k/36.0
			var ok := true
			for s in 9:
				var p := Vector2(cos(a)*r+s, sin(a)*r)
				var hit := ground(p.x, p.y)
				if hit.is_empty() or hit.position.y < 2.2 or hit.position.y > 9.0 or Roads.on_road(p) or (hit.collider is CollisionObject3D and hit.collider.collision_layer&2):
					ok = false; break
			if ok: return ground(cos(a)*r, sin(a)*r).position
	return Vector3.INF

func phase(label: String, seconds: float, crowd: bool, start: Vector3) -> void:
	app.player.global_position = start+Vector3(0, 0.3, 0)
	for i in 10: await physics_frame
	var times: Array[float] = []
	var began := Time.get_ticks_msec()
	var last := Time.get_ticks_usec()
	var flip := 0.0
	var walk_clock := 0.0
	var drawn_before: int = feet.drawn
	Input.action_press("run")
	Input.action_press("move_right")
	while Time.get_ticks_msec()-began < seconds*1000.0:
		await process_frame
		var now := Time.get_ticks_usec()
		var dt := (now-last)/1000.0
		last = now
		times.append(dt)
		flip += dt
		if flip > 1600.0:
			flip = 0.0
			var right := Input.is_action_pressed("move_right")
			Input.action_release("move_right" if right else "move_left")
			Input.action_press("move_left" if right else "move_right")
		if crowd:
			walk_clock += dt/1000.0
			while walk_clock > 1.0/24.0:
				walk_clock -= 1.0/24.0
				var who := randi()%8
				var at: Vector3 = start+Vector3(cos(who)*3.0+randf_range(-0.5, 0.5), 0, sin(who)*3.0+randf_range(-0.5, 0.5))
				app.world_audio.stepped.emit({"kind": "step", "who": "remote", "surface": "grass", "fx": "grass", "at": at,
					"speed": 1.4, "gait": "walk", "foot": -1, "size": 1.0})
	for key in ["run", "move_left", "move_right"]: Input.action_release(key)
	times.sort()
	var mean := 0.0
	for t in times: mean += t
	mean /= maxf(1.0, times.size())
	var p95: float = times[int(times.size()*0.95)] if not times.is_empty() else 0.0
	print("PERF %s frames=%d mean_ms=%.2f p95_ms=%.2f puffs=%d" % [label, times.size(), mean, p95, feet.drawn-drawn_before])

func run_test() -> void:
	app = Main.new()
	root.add_child(app)
	await process_frame
	var username := "footperf_"+str(Time.get_unix_time_from_system()).replace(".", "_")
	await app.authenticate(true, preload("res://tests/qa_server.gd").url(), username, "Qa-footperf-123", "")
	if app.screen != "village":
		print("FOOT_FX_PERF FAIL village did not load")
		quit(1)
		return
	feet = app.get_node("FootFx")
	app.close_village_modal()
	for i in 60: await process_frame
	var start := open_grass()
	if start == Vector3.INF:
		print("FOOT_FX_PERF FAIL no open grass")
		quit(1)
		return
	# Warm up (first-time textures and pools), then the three phases.
	await phase("warmup", 3.0, true, start)
	app.world_audio.stepped.disconnect(feet.on_stepped)
	await phase("off", 8.0, true, start)
	app.world_audio.stepped.connect(feet.on_stepped)
	await phase("hero", 8.0, false, start)
	await phase("crowd", 8.0, true, start)
	print("FOOT_FX_PERF DONE effects=%d" % Fx.played)
	quit(0)
