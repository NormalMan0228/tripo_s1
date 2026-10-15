extends SceneTree
## Performance overlay (scripts/perf_overlay.gd, autoload PerfOverlay): hidden by default, F2 shows
## and hides it, the settings key does the same, its text has every line, and its own cost is small.
## With a window it also saves artifacts/perf-overlay.png over the village.
##   Godot --path game --script res://tests/perf_overlay_check.gd [--position X,Y]   (or --headless)
const Stub = preload("res://tests/shadow_folk_stub.gd")
const Folk = preload("res://scripts/shadow_folk.gd")
const Town = preload("res://scripts/town.gd")
const PlayerBody = preload("res://scripts/player.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
var failed := false

func _initialize() -> void: call_deferred("run")

func expect(value: bool, text: String) -> void:
	print(("PASS " if value else "FAIL ")+text)
	if not value: failed = true

func press(key: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.physical_keycode = key
	event.pressed = true
	Input.parse_input_event(event)
	await process_frame
	event = event.duplicate()
	event.pressed = false
	Input.parse_input_event(event)
	await process_frame

func run() -> void:
	# Not an autoload (that would change project.binary and need the installer): ImeCaret makes it
	# on first use (F2 or the setting).
	expect(root.get_node_or_null("PerfOverlay") == null, "no overlay until it is first used")
	var overlay = root.get_node("ImeCaret").perf_overlay()
	expect(overlay != null and overlay == root.get_node_or_null("PerfOverlay"), "PerfOverlay made on first use")
	if overlay == null:
		quit(1)
		return
	expect(not overlay.visible and not overlay.is_processing(), "hidden and idle by default")
	# A village with residents to count, under the orthographic follow camera.
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = Profile.VILLAGE_CAMERA_DEFAULT
	camera.far = 400.0
	root.add_child(camera)
	var app = Stub.new()
	app.name = "Main"
	root.add_child(app)
	app.build(camera)
	current_scene = app
	for i in 8: await physics_frame
	app.spawn_villagers()
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
	for walker in folk.walkers.slice(0, 5):
		walker.set_present(true)
		walker.position = Town.point(start+Vector2(randf_range(-6, 6), randf_range(-4, 4)), 0.05)
	var focus: Vector3 = player.global_position+Profile.CAMERA_FOCUS_OFFSET
	camera.position = focus+Profile.CAMERA_OFFSET*Profile.CAMERA_PULLBACK
	camera.look_at(focus)
	camera.current = true
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	sun.light_energy = 1.2
	app.add_child(sun)
	var sky := WorldEnvironment.new()
	sky.environment = Environment.new()
	sky.environment.background_mode = Environment.BG_COLOR
	sky.environment.background_color = Color("8fb8c9")
	sky.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	sky.environment.ambient_light_color = Color("b9c7cf")
	app.add_child(sky)
	for i in 30: await process_frame
	await press(KEY_F2)
	expect(overlay.visible and overlay.is_processing(), "F2 shows it")
	await create_timer(1.2).timeout
	var text: String = overlay.label.text
	print(text)
	for word in ["FPS", "1%", "CPU", "물리", "메모리", "VRAM", "드로우콜", "삼각형", "노드", "오브젝트", "장면 Main", "서버 응답", "근처 플레이어", "주민"]:
		expect(word in text, "line has '%s'" % word)
	if DisplayServer.get_name() != "headless":
		await create_timer(0.3).timeout
		await RenderingServer.frame_post_draw
		var out := ProjectSettings.globalize_path("res://../artifacts")
		DirAccess.make_dir_recursive_absolute(out)
		root.get_texture().get_image().save_png(out.path_join("perf-overlay.png"))
		print("CAPTURE ", out.path_join("perf-overlay.png"))
	var near: Vector2i = overlay.nearby(app)
	expect(near.y >= 3, "counts the residents nearby (%d)" % near.y)
	# Its own cost: building the text and the per-frame record.
	var started := Time.get_ticks_usec()
	for i in 100: overlay.describe()
	var describe_ms := (Time.get_ticks_usec()-started)/100.0/1000.0
	started = Time.get_ticks_usec()
	for i in 1000: overlay._process(0.0001)
	var frame_us := (Time.get_ticks_usec()-started)/1000.0
	print("OVERLAY_COST describe=%.3f ms (twice a second)  per_frame=%.2f us" % [describe_ms, frame_us])
	expect(describe_ms < 1.0 and frame_us < 20.0, "overlay cost small")
	await press(KEY_F2)
	expect(not overlay.visible and not overlay.is_processing(), "F2 hides it again")
	GameSettings.values["perf_overlay"] = true
	GameSettings._notify(["perf_overlay"] as Array[String])
	expect(overlay.visible, "settings key shows it")
	GameSettings.values.erase("perf_overlay")
	GameSettings._notify(["perf_overlay"] as Array[String])
	expect(not overlay.visible, "settings key hides it")
	print("PERF_OVERLAY_CHECK ", "FAIL" if failed else "PASS")
	quit(1 if failed else 0)
