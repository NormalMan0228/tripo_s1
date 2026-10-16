extends SceneTree
## Frame time and memory in the real game screens (main.gd against recorded replies, as
## tests/hud_layout_check.gd): the village and a forest expedition, the walker moving in a slow
## circle, drawn in a window with no frame cap and no vsync. Per scene for SECONDS: fps, average and
## worst-1 % frame ms, CPU process / physics ms, draw calls, primitives, objects drawn, static memory,
## video memory, node count. Prints PERF_SCENE lines (JSON) and writes artifacts/perf-scenes.json.
##   godot --path game --script res://tests/perf_scenes.gd -- --qa [--seconds=10] [--label=before]
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const I18n = preload("res://scripts/i18n.gd")
const SocialHud = preload("res://scripts/social_hud.gd")
const Figure = preload("res://scripts/shadow_figure.gd")
const PlayerBody = preload("res://scripts/player.gd")
var app: Node
var results := {}

func _initialize() -> void:
	call_deferred("run")
	create_timer(300).timeout.connect(func(): quit(2))

func arg(name: String, fallback: String) -> String:
	for item in OS.get_cmdline_user_args():
		if item.begins_with("--"+name+"="): return item.trim_prefix("--"+name+"=")
	return fallback

func settle(seconds: float) -> void:
	await create_timer(seconds).timeout

func run() -> void:
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	I18n.setup()
	RpgUi.set_folds(RpgUi.FOLD_TIPS.keys()+["chat"], false, false)
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	fixture["/v1/social/presence"] = {"self_id":"me", "host_id":"me", "host_name":"haneul", "visiting":false, "party":null, "invites":[],
		"pending_rewards":[], "village":{"players":[{"id":"me", "username":"haneul", "x":0, "z":0}]}, "messages":[]}
	# --preset=low|medium|high: that graphics level (the laptop measurement).
	var preset := arg("preset", "")
	var Settings = load("res://scripts/game_settings.gd")
	var preset_before := str(Settings.get_value("preset"))
	if arg("window", "") != "":
		var size := arg("window", "").split("x")
		DisplayServer.window_set_size(Vector2i(int(size[0]), int(size[1])))
	if not preset.is_empty():
		Settings.set_value("preset", preset)
		for key in Settings.PRESETS[preset]: Settings.set_value(key, Settings.PRESETS[preset][key])
	app = Main.new()
	root.add_child(app)
	current_scene = app
	await settle(1.6)
	app.api.queue_free()
	var stub = Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = true
	await app.enter_village()
	preload("res://scripts/transition.gd").of(self).fade_in()
	await settle(3.0)
	await measure("village", float(arg("seconds", "10")))
	await app.start_run("forest", "standard")
	await settle(3.0)
	await measure("expedition", float(arg("seconds", "10")))
	var out := ProjectSettings.globalize_path("res://../artifacts")
	DirAccess.make_dir_recursive_absolute(out)
	var path := out.path_join("perf-scenes-%s.json" % arg("label", "run"))
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(results, "  "))
	f.close()
	print("PERF_SCENES_DONE ", path)
	# The QA settings file keeps the level it had.
	if not preset.is_empty() and Settings.PRESETS.has(preset_before):
		Settings.set_value("preset", preset_before)
		for key in Settings.PRESETS[preset_before]: Settings.set_value(key, Settings.PRESETS[preset_before][key])
	app.queue_free()
	await settle(0.4)
	SocialHud.end()
	quit(0)

## The end of every _process (lowest priority) and of every _physics_process: script time per frame.
class EndMark extends Node:
	var process_end := 0
	var physics_us := 0
	var physics_start := 0
	func _init() -> void:
		process_priority = 1000000
		process_physics_priority = 1000000
		process_mode = Node.PROCESS_MODE_ALWAYS
	func _process(_d: float) -> void: process_end = Time.get_ticks_usec()
	func _physics_process(_d: float) -> void: physics_us += Time.get_ticks_usec()-physics_start

class StartMark extends Node:
	var mark: Node
	func _init() -> void:
		process_physics_priority = -1000000
		process_mode = Node.PROCESS_MODE_ALWAYS
	func _physics_process(_d: float) -> void: mark.physics_start = Time.get_ticks_usec()

## Walks a slow circle (the movement actions) and samples every frame.
func measure(scene: String, seconds: float) -> void:
	# The game's settings turn vsync back on: uncap again for every scene.
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
	var end_mark := EndMark.new()
	root.add_child(end_mark)
	var start_mark := StartMark.new()
	start_mark.mark = end_mark
	root.add_child(start_mark)
	Figure.profile = true
	Figure.profile_us = 0
	PlayerBody.profile = true
	PlayerBody.profile_slide_us = 0
	PlayerBody.profile_step_us = 0
	PlayerBody.profile_slides = 0
	await settle(0.5)
	var times := PackedFloat32Array()
	var spikes: Array = []
	var last_compiles := 0
	var total_compiles := 0
	for monitor in [Performance.PIPELINE_COMPILATIONS_CANVAS, Performance.PIPELINE_COMPILATIONS_MESH, Performance.PIPELINE_COMPILATIONS_SURFACE, Performance.PIPELINE_COMPILATIONS_DRAW, Performance.PIPELINE_COMPILATIONS_SPECIALIZATION]:
		last_compiles += int(Performance.get_monitor(monitor))
	var sums := {"process":0.0, "physics":0.0, "draw":0.0, "prims":0.0, "objects":0.0, "render_cpu":0.0, "gpu":0.0}
	var started := Time.get_ticks_usec()
	var n := 0
	while Time.get_ticks_usec()-started < int(seconds*1000000.0):
		var a := (Time.get_ticks_usec()-started)/1000000.0*0.6
		var d := Vector2(cos(a), sin(a))
		for action in ["move_left", "move_right", "move_forward", "move_back"]: Input.action_release(action)
		if d.x > 0.05: Input.action_press("move_right", d.x)
		if d.x < -0.05: Input.action_press("move_left", -d.x)
		if d.y > 0.05: Input.action_press("move_back", d.y)
		if d.y < -0.05: Input.action_press("move_forward", -d.y)
		var physics_before: int = end_mark.physics_us
		var ticks_before := Engine.get_physics_frames()
		var walkers_before: int = Figure.profile_us
		var slide_before: int = PlayerBody.profile_slide_us
		var step_before: int = PlayerBody.profile_step_us
		await process_frame
		var frame_start := Time.get_ticks_usec()
		times.append(root.get_process_delta_time())
		await RenderingServer.frame_pre_draw
		var script_s := (end_mark.process_end-frame_start)/1000000.0
		var compiles := 0
		for monitor in [Performance.PIPELINE_COMPILATIONS_CANVAS, Performance.PIPELINE_COMPILATIONS_MESH, Performance.PIPELINE_COMPILATIONS_SURFACE, Performance.PIPELINE_COMPILATIONS_DRAW, Performance.PIPELINE_COMPILATIONS_SPECIALIZATION]:
			compiles += int(Performance.get_monitor(monitor))
		spikes.append([times[-1], script_s, (end_mark.physics_us-physics_before)/1000000.0, RenderingServer.viewport_get_measured_render_time_cpu(root.get_viewport_rid())/1000.0, n, compiles-last_compiles, Engine.get_physics_frames()-ticks_before, (Figure.profile_us-walkers_before)/1000000.0, (PlayerBody.profile_slide_us-slide_before)/1000000.0, (PlayerBody.profile_step_us-step_before)/1000000.0, app.player.global_position.snapped(Vector3.ONE*0.1) if is_instance_valid(app.player) else Vector3.ZERO, PlayerBody.profile_slides])
		total_compiles += compiles-last_compiles
		last_compiles = compiles
		sums.process += script_s
		sums.render_cpu += RenderingServer.viewport_get_measured_render_time_cpu(root.get_viewport_rid())/1000.0+RenderingServer.get_frame_setup_time_cpu()/1000.0
		sums.gpu += RenderingServer.viewport_get_measured_render_time_gpu(root.get_viewport_rid())/1000.0
		sums.draw += Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
		sums.prims += Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
		sums.objects += Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)
		n += 1
	for action in ["move_left", "move_right", "move_forward", "move_back"]: Input.action_release(action)
	sums.physics = end_mark.physics_us/1000000.0
	var walker_ms := Figure.profile_us/1000.0/maxf(1.0, n)
	Figure.profile = false
	end_mark.queue_free()
	start_mark.queue_free()
	times.sort()
	var total := 0.0
	for t in times: total += t
	var worst := 0.0
	var k := maxi(1, times.size()/100)
	for i in k: worst += times[times.size()-1-i]
	var line := {"scene":scene, "fps":snappedf(times.size()/seconds, 0.1), "avg_ms":snappedf(total/times.size()*1000.0, 0.01),
		"worst1_ms":snappedf(worst/k*1000.0, 0.01), "script_ms":snappedf(sums.process/n*1000.0, 0.01), "physics_ms_per_frame":snappedf(sums.physics/n*1000.0, 0.01),
		"render_cpu_ms":snappedf(sums.render_cpu/n*1000.0, 0.01), "gpu_ms":snappedf(sums.gpu/n*1000.0, 0.01),
		"draw_calls":int(sums.draw/n), "primitives":int(sums.prims/n), "objects":int(sums.objects/n),
		"mem_mb":snappedf(Performance.get_monitor(Performance.MEMORY_STATIC)/1048576.0, 1), "vram_mb":snappedf(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED)/1048576.0, 1),
		"nodes":int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))}
	# The longest frames and where their time went (the previous frame's physics shows in the delta).
	spikes.sort_custom(func(a, b): return a[0] > b[0])
	var top: Array = []
	for item in spikes.slice(0, 8): top.append("frame %d: %.1f ms (script %.1f, physics %.1f in %d ticks of which walkers %.1f, player slide %.1f, step_up %.1f; render cpu %.1f, pipeline compiles %d) at %s" % [item[4], item[0]*1000.0, item[1]*1000.0, item[2]*1000.0, item[6], item[7]*1000.0, item[8]*1000.0, item[9]*1000.0, item[3]*1000.0, item[5], str(item[10])])
	line["spikes"] = top
	line["pipeline_compiles"] = total_compiles
	line["walkers_ms_per_frame"] = snappedf(walker_ms, 0.01)
	line["player_slide_ms_per_frame"] = snappedf(PlayerBody.profile_slide_us/1000.0/maxf(1.0, n), 0.01)
	line["player_step_ms_per_frame"] = snappedf(PlayerBody.profile_step_us/1000.0/maxf(1.0, n), 0.01)
	line["player_position"] = str(app.player.global_position.snapped(Vector3.ONE*0.1)) if is_instance_valid(app.player) else ""
	PlayerBody.profile = false
	results[scene] = line
	print("PERF_SCENE ", JSON.stringify(line))
