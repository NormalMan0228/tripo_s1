extends SceneTree
## Under-foot effects in the real village (tools/test.ps1 -ClientScript foot_fx_village [-Capture]):
## finds a sand, a shallow-water and a grass spot by raycast, walks the hero across each with the
## move keys, and checks the footstep `stepped` events drew the matching puffs (FootFx.drawn) for
## the same surface the sound picked. With --capture it saves one frame per surface mid-walk:
## artifacts/foot_fx_<surface>.png.
const Main := preload("res://scripts/main.gd")
const Fx := preload("res://scripts/fx.gd")
var app: Node3D
var failures: Array[String] = []
var seen := {}

func _initialize() -> void: call_deferred("run_test")

func check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ")+what)
	if not ok: failures.append(what)

func release() -> void:
	for key in ["move_left","move_right","move_forward","move_back","run"]: Input.action_release(key)

func ground(x: float, z: float) -> Dictionary:
	var space := app.get_world_3d().direct_space_state
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(x, 60, z), Vector3(x, -10, z), 1|2))
	return hit

## A spot whose ground height lies in [low, high] for a 6 m run along +-x or +-z, off roads and decks;
## wet: the sea (ground under 0.3 m) lies within 3 m to one side of the run's middle, so the run
## follows the water's edge (the village puts the hero back on the shore below 0.45 m).
func find_spot(low: float, high: float, wet := false) -> Dictionary:
	var Roads = preload("res://scripts/roads.gd")
	for r in range(20, 110, 3):
		for k in 48:
			var a := TAU*k/48.0
			var x := cos(a)*r
			var z := sin(a)*r
			for dir in [Vector2(1, 0), Vector2(0, 1), Vector2(-1, 0), Vector2(0, -1)]:
				var ok := true
				for s in 7:
					var p: Vector2 = Vector2(x, z)+dir*s
					var hit := ground(p.x, p.y)
					if hit.is_empty() or hit.collider is CollisionObject3D and hit.collider.collision_layer&2:
						ok = false; break
					var y: float = hit.position.y
					if y < low or y > high or Roads.on_road(p):
						ok = false; break
				if ok and wet:
					var mid: Vector2 = Vector2(x, z)+dir*3
					var side := Vector2(-dir.y, dir.x)
					var sea := false
					for d in [-3.0, -2.0, 2.0, 3.0]:
						var q: Vector2 = mid+side*d
						var h := ground(q.x, q.y)
						if not h.is_empty() and h.position.y < 0.3: sea = true
					ok = sea
				if ok: return {"at": Vector3(x, ground(x, z).position.y, z), "dir": dir}
	return {}

func walk_on(label: String, spot: Dictionary, run := false) -> void:
	if spot.is_empty():
		check(false, "found a %s spot" % label)
		return
	app.player.global_position = spot.at+Vector3(0, 0.3, 0)
	app.player.velocity = Vector3.ZERO
	for i in 20: await physics_frame
	seen.clear()
	var drawn_before: int = app.get_node("FootFx").drawn
	var dir: Vector2 = spot.dir
	if run: Input.action_press("run")
	if dir.x > 0: Input.action_press("move_right")
	elif dir.x < 0: Input.action_press("move_left")
	elif dir.y > 0: Input.action_press("move_back")
	else: Input.action_press("move_forward")
	var started := Time.get_ticks_msec()
	var shot := false
	while Time.get_ticks_msec()-started < 2400:
		await process_frame
		if not shot and Time.get_ticks_msec()-started > 1300:
			shot = true
			await shoot(label)
	release()
	var drawn: int = app.get_node("FootFx").drawn-drawn_before
	print("SURFACE %s fx=%s drawn=%d moved=%.1fm" % [label, str(seen.keys()), drawn, Vector2(app.player.global_position.x-spot.at.x, app.player.global_position.z-spot.at.z).length()])
	check(drawn >= 2, "%s: walking drew under-foot effects (%d)" % [label, drawn])

func shoot(label: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://../artifacts/foot_fx_%s.png" % label)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	print("CAPTURE ", root.get_texture().get_image().save_png(path), " ", path)

func run_test() -> void:
	app = Main.new()
	root.add_child(app)
	await process_frame
	var username := "footfx_"+str(Time.get_unix_time_from_system()).replace(".", "_")
	await app.authenticate(true, preload("res://tests/qa_server.gd").url(), username, "Qa-footfx-123", "")
	check(app.screen == "village", "village loads")
	if app.screen != "village":
		quit(1)
		return
	check(app.has_node("FootFx"), "FootFx attached to the app")
	app.world_audio.stepped.connect(func(info: Dictionary): if str(info.get("who", "")) == "hero": seen[str(info.get("fx", ""))] = true)
	app.close_village_modal()
	for i in 30: await process_frame
	await walk_on("sand", find_spot(0.95, 1.45))
	check(seen.has("dust"), "sand steps report dust")
	await walk_on("shallow", find_spot(0.5, 0.78, true))
	check(seen.has("splash"), "shallow steps report splash")
	await walk_on("grass", find_spot(2.2, 9.0), true)
	check(seen.has("grass"), "grass steps report grass")
	print("FOOT_FX_VILLAGE %s failures=%d effects=%d" % ["PASS" if failures.is_empty() else "FAIL", failures.size(), Fx.played])
	quit(0 if failures.is_empty() else 1)
