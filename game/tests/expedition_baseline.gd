extends SceneTree
## Expedition baseline (map work, phase 1): the real game against a QA server, in a window, vsync
## off. Title -> home -> village, then --warmup (default 1) + --entries (default 3) times
## village -> expedition (--map=forest|quarry|frost) -> village. Each entry reports the frames under
## the loading card the way tests/loading_frames.gd judges them (worst frame, frames over 50 ms,
## seconds under the veil, LoadPace phases with --load-phases) and the time from start_run() to a
## settled view. After each entry the camera is pinned to the camp view (the default follow view of
## the spawn point, ortho size 14.5) and, after a 3 s settle, 5 s are sampled: fps, worst frame,
## draw calls, objects, primitives (tris) on screen, CPU/GPU render time, video/texture/buffer memory.
## After the last entry three fixed spots per map (camp, a scatter-dense spot, a rim spot) are
## sampled for 2 s each and captured with the UI hidden to --out=DIR as <map>_<spot>.png.
## The time of day is held at day_progress 0.3 (plain day grade) while measuring.
## --alternate-prefetch: entries alternate the survival map's creature prefetch (survival_map.gd
## prefetch_monsters) off and on (warmups keep it on), to compare both under the same conditions.
## Prints EXPB lines and EXPB_RESULT {json}; also writes <out>/<map>.json.
## Usage: Godot --path game --position X,Y --script res://tests/expedition_baseline.gd --
##   --server=http://127.0.0.1:8831 --map=forest --out=D:/.../baseline --load-phases --mute
const SPOTS := {
	"forest": [["camp", Vector2(0.0, 1.4)], ["dense", Vector2(6.0, 12.0)], ["rim", Vector2(14.0, -22.0)]],
	"quarry": [["camp", Vector2(0.0, 1.4)], ["dense", Vector2(-16.0, 0.0)], ["rim", Vector2(14.0, -22.0)]],
	"frost": [["camp", Vector2(0.0, 1.4)], ["dense", Vector2(-18.0, -12.0)], ["rim", Vector2(14.0, -22.0)]],
}

var server := preload("res://tests/qa_server.gd").url()
var map_id := "forest"
var entries := 3
var warmup := 1
var out_dir := ""
var settle_s := 3.0
var sample_s := 5.0
var spot_s := 2.0
var failures: Array[String] = []
var transition_script: Script
var pace: Script
## [usec, frame ms, veil alpha, card visible]
var samples: Array = []
var last_usec := 0
var result := {}
var pin: Pin

## Holds the camera on a fixed focus after main.gd's follow camera (priority 0) and before the
## survival map's per-frame work (priority 100), and the time of day at DAY_PROGRESS.
class Pin extends Node:
	const CP = preload("res://scripts/controller_profile.gd")
	var app: Node
	var focus := Vector3.ZERO
	var active := false
	func _init() -> void:
		process_priority = 50
	func _process(_delta: float) -> void:
		if not active or not is_instance_valid(app): return
		var run = app.get("run")
		if run is Dictionary and not (run as Dictionary).is_empty():
			run["day_progress"] = 0.3
			run["night"] = false
		var cam: Camera3D = app.get("camera")
		if not is_instance_valid(cam): return
		var f := focus+CP.CAMERA_FOCUS_OFFSET
		cam.global_position = f+CP.CAMERA_OFFSET*CP.CAMERA_PULLBACK
		cam.look_at(f, Vector3.UP)
		cam.size = CP.CAMERA_DEFAULT

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
		if arg.begins_with("--map="): map_id = arg.trim_prefix("--map=")
		if arg.begins_with("--entries="): entries = int(arg.trim_prefix("--entries="))
		if arg.begins_with("--warmup="): warmup = int(arg.trim_prefix("--warmup="))
		if arg.begins_with("--out="): out_dir = arg.trim_prefix("--out=")
		if arg.begins_with("--sample="): sample_s = float(arg.trim_prefix("--sample="))
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	transition_script = load("res://scripts/transition.gd")
	pace = load("res://scripts/load_pace.gd")
	result = {"map":map_id, "warmup":warmup, "warmups":[], "entries":[], "spots":{}, "renderer":RenderingServer.get_current_rendering_method(),
		"window":str(DisplayServer.window_get_size()), "gpu":RenderingServer.get_video_adapter_name()}
	call_deferred("run")
	create_timer(420).timeout.connect(func():
		failures.append("timed out after 420 seconds")
		finish())

func check(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failures.append(description)

func finish() -> void:
	result["ok"] = failures.is_empty()
	result["failures"] = failures
	var text := JSON.stringify(result)
	print("EXPB_RESULT ", text)
	if not out_dir.is_empty():
		DirAccess.make_dir_recursive_absolute(out_dir)
		var file := FileAccess.open(out_dir.path_join(map_id+".json"), FileAccess.WRITE)
		if file: file.store_string(JSON.stringify(result, "  "))
	quit(0 if failures.is_empty() else 1)

func veil() -> CanvasLayer:
	var node = transition_script.get("instance")
	return node if is_instance_valid(node) else null

func record() -> void:
	# The game applies the player's frame cap and vsync when it starts; measure uncapped.
	if Engine.max_fps != 0 or DisplayServer.window_get_vsync_mode() != DisplayServer.VSYNC_DISABLED:
		Engine.max_fps = 0
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var now := Time.get_ticks_usec()
	var ms := (now-last_usec)/1000.0 if last_usec > 0 else 0.0
	last_usec = now
	var v := veil()
	if ms > 50.0 and "--log-hitches" in OS.get_cmdline_user_args():
		print("HITCH %.1f ms at %d screen=%s veil=%.2f card=%s last_step=%s process=%.1f physics=%.1f" % [ms, Time.get_ticks_msec(),
			str(current_scene.get("screen")) if is_instance_valid(current_scene) else "-", v.veil.modulate.a if v else -1.0, str(v.card.visible) if v else "-",
			str(pace.last_what), Performance.get_monitor(Performance.TIME_PROCESS)*1000.0, Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)*1000.0])
	samples.append([now, ms, v.veil.modulate.a if v else 0.0, v.card.visible and v.is_inside_tree() if v else false])

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

func settled() -> bool:
	var v := veil()
	return v != null and is_zero_approx(v.veil.modulate.a) and not v.card.visible and (v.tween == null or not v.tween.is_running())

## Frames from `from` on that began with the veil (or the card) on screen (loading_frames.gd judge()).
func judge(name: String, from: int) -> Dictionary:
	var frames: Array = []
	var first := -1
	var last := -1
	for i in range(maxi(from, 1), samples.size()):
		var up: bool = samples[i-1][2] > 0.001 or samples[i-1][3]
		if not up: continue
		if first < 0: first = i
		last = i
		frames.append(samples[i][1])
	if frames.is_empty():
		check(false, "%s: the veil came up" % name)
		return {}
	var worst := 0.0
	var over := 0
	var total := 0.0
	for ms in frames:
		worst = maxf(worst, ms)
		total += ms
		if ms > 50.0: over += 1
	var longest: Array = frames.duplicate()
	longest.sort()
	longest.reverse()
	longest = longest.slice(0, 5).map(func(ms): return snappedf(ms, 0.1))
	var seconds: float = (samples[last][0]-samples[first][0])/1000000.0
	var out := {"worst_ms":snappedf(worst, 0.1), "over_50ms":over, "frames":frames.size(), "veil_s":snappedf(seconds, 0.001),
		"mean_ms":snappedf(total/frames.size(), 0.1), "longest":longest}
	if pace.phases_on:
		var phases: Dictionary = pace.take_phases()
		for key in phases: phases[key] = snappedf(phases[key], 0.1)
		out["phases"] = phases
	return out

func change(name: String, action: Callable, arrived: Callable, seconds := 90.0) -> Dictionary:
	await wait_until(settled, 10.0)
	await create_timer(0.5).timeout
	var mark := samples.size()
	if pace.phases_on: pace.take_phases()
	var started := Time.get_ticks_usec()
	action.call()
	var ok := await wait_until(func(): return arrived.call() and settled(), seconds)
	check(ok, name+": arrived")
	if not ok: return {}
	var out := judge(name, mark)
	out["click_to_play_ms"] = snappedf((Time.get_ticks_usec()-started)/1000.0, 0.1)
	return out

func memory() -> Dictionary:
	return {"video_mb":snappedf(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED)/1048576.0, 0.1),
		"texture_mb":snappedf(Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED)/1048576.0, 0.1),
		"buffer_mb":snappedf(Performance.get_monitor(Performance.RENDER_BUFFER_MEM_USED)/1048576.0, 0.1),
		"static_mb":snappedf(Performance.get_monitor(Performance.MEMORY_STATIC)/1048576.0, 0.1)}

## Steady-state sample: uncapped frames for `seconds`, monitors averaged per frame.
func sample(seconds: float) -> Dictionary:
	var viewport := root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(viewport, true)
	for i in 10: await process_frame
	var frames := 0
	var worst := 0.0
	var over := 0
	var started := Time.get_ticks_usec()
	var last := started
	var draws := 0.0
	var objects := 0.0
	var prims := 0.0
	var cpu := 0.0
	var gpu := 0.0
	var process := 0.0
	while Time.get_ticks_usec()-started < seconds*1000000.0:
		await process_frame
		var now := Time.get_ticks_usec()
		var ms := (now-last)/1000.0
		worst = maxf(worst, ms)
		if ms > 50.0: over += 1
		last = now
		frames += 1
		draws += Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
		objects += Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)
		prims += Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
		process += Performance.get_monitor(Performance.TIME_PROCESS)*1000.0
		cpu += RenderingServer.viewport_get_measured_render_time_cpu(viewport)+RenderingServer.get_frame_setup_time_cpu()
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(viewport)
	var ms_avg := (Time.get_ticks_usec()-started)/1000.0/frames
	var out := {"frames":frames, "avg_ms":snappedf(ms_avg, 0.01), "avg_fps":snappedf(1000.0/ms_avg, 0.1), "worst_ms":snappedf(worst, 0.1), "over_50ms":over,
		"draw_calls":int(draws/frames), "objects":int(objects/frames), "tris":int(prims/frames),
		"process_ms":snappedf(process/frames, 0.01), "render_cpu_ms":snappedf(cpu/frames, 0.01), "render_gpu_ms":snappedf(gpu/frames, 0.01)}
	out.merge(memory())
	return out

func map_node() -> Node:
	var world = current_scene.get("world") if is_instance_valid(current_scene) else null
	return world.get_node_or_null("SurvivalMap") if is_instance_valid(world) else null

func aim(at: Vector2) -> void:
	var map := map_node()
	var y: float = map.height(at.x, at.y) if map and map.has_method("height") else 0.0
	pin.app = current_scene
	pin.focus = Vector3(at.x, y, at.y)
	pin.active = true

func capture(path: String) -> Vector2i:
	var hidden: Array = []
	for layer in root.find_children("*", "CanvasLayer", true, false):
		if layer.visible:
			layer.visible = false
			hidden.append(layer)
	for i in 3: await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.save_png(path)
	for layer in hidden:
		if is_instance_valid(layer): layer.visible = true
	return image.get_size()

func line(name: String, d: Dictionary) -> void:
	print("EXPB %-24s fps=%6.1f avg=%6.2f ms worst=%6.1f >50=%d draws=%5d objects=%5d tris=%8d cpu=%5.2f gpu=%5.2f video=%7.1f MB" % [name, d.avg_fps, d.avg_ms, d.worst_ms, d.over_50ms, d.draw_calls, d.objects, d.tris, d.render_cpu_ms, d.render_gpu_ms, d.video_mb])

func run() -> void:
	process_frame.connect(record)
	pin = Pin.new()
	root.add_child(pin)
	change_scene_to_file("res://scenes/main.tscn")
	var titled := await wait_until(func(): return is_instance_valid(current_scene) and current_scene.get("screen") == "login" and not current_scene.busy and settled(), 120.0)
	check(titled, "start: reached the title")
	if not titled:
		finish()
		return
	var user := "expb_"+str(Time.get_ticks_usec() % 100000000)
	var home := await change("title -> home", func(): current_scene.authenticate(true, server, user, "Expb-check-password-1!", ""),
		func(): return is_instance_valid(current_scene) and current_scene.get("room") == "home")
	if home.is_empty():
		finish()
		return
	var village := await change("home -> village", func(): current_scene.leave(),
		func(): return is_instance_valid(current_scene) and current_scene.get("screen") == "village")
	if village.is_empty():
		finish()
		return
	result["village_before"] = memory()
	var alternate := "--alternate-prefetch" in OS.get_cmdline_user_args()
	var survival_map = load("res://maps/survival/survival_map.gd")
	for n in warmup+entries:
		var tag := ("warmup%d" % n) if n < warmup else ("entry%d" % (n-warmup+1))
		if alternate:
			survival_map.prefetch_monsters = n < warmup or (n-warmup) % 2 == 1
			tag += "_prefetch" if bool(survival_map.prefetch_monsters) else "_noprefetch"
		await create_timer(2.0).timeout
		var entry := await change("village -> "+map_id, func(): current_scene.start_run(map_id),
			func(): return current_scene.get("screen") == "survival" and not current_scene.busy)
		if entry.is_empty():
			finish()
			return
		entry["tag"] = tag
		print("EXPB %-24s veil=%6.3f s click_to_play=%7.1f ms worst=%6.1f ms >50ms=%d frames=%d longest=%s" % [tag+" enter", entry.veil_s, entry.click_to_play_ms, entry.worst_ms, entry.over_50ms, entry.frames, str(entry.longest)])
		if entry.has("phases"): print("EXPB_PHASES %s %s" % [tag, JSON.stringify(entry.phases)])
		aim(SPOTS[map_id][0][1])
		await create_timer(settle_s).timeout
		var map := map_node()
		if n == warmup and map:
			result["map_stats"] = map.report() if map.has_method("report") else {}
			result["nodes"] = {"meshes":current_scene.find_children("*", "MeshInstance3D", true, false).size(),
				"multimesh":current_scene.find_children("*", "MultiMeshInstance3D", true, false).size(),
				"nodes":int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))}
			print("EXPB_INFO ", JSON.stringify({"stats":result.map_stats, "nodes":result.nodes}))
		entry["settled"] = await sample(sample_s)
		line(tag+" camp 5s", entry.settled)
		if n == warmup+entries-1:
			for spot in SPOTS[map_id]:
				aim(spot[1])
				await create_timer(1.0).timeout
				var s := await sample(spot_s)
				s["focus"] = [spot[1].x, spot[1].y]
				s["day_progress"] = float(current_scene.run.get("day_progress", -1.0))
				s["night"] = snappedf(float(map.get("night")), 0.001) if map else -1.0
				s["dusk"] = snappedf(float(map.get("dusk")), 0.001) if map else -1.0
				check(s.night < 0.01 and s.dusk < 0.01, "%s %s: day grade (night %.3f, dusk %.3f)" % [map_id, spot[0], s.night, s.dusk])
				if not out_dir.is_empty():
					DirAccess.make_dir_recursive_absolute(out_dir)
					var path := out_dir.path_join("%s_%s.png" % [map_id, spot[0]])
					s["png"] = path
					s["png_size"] = str(await capture(path))
				line(map_id+" spot "+spot[0], s)
				result.spots[spot[0]] = s
		pin.active = false
		var back := await change(map_id+" -> village", func(): current_scene.leave_run(),
			func(): return current_scene.get("screen") == "village" and not current_scene.busy)
		entry["leave"] = back
		if not back.is_empty(): print("EXPB %-24s veil=%6.3f s worst=%6.1f ms >50ms=%d" % [tag+" leave", back.veil_s, back.worst_ms, back.over_50ms])
		entry["village_after"] = memory()
		(result.warmups if n < warmup else result.entries).append(entry)
		if back.is_empty():
			finish()
			return
	finish()
