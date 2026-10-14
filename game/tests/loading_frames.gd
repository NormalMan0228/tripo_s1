extends SceneTree
## Frame times while the loading card is up, through the real game against a QA server:
## start -> title, title -> home, home -> village, village -> a resident's house -> village,
## village -> expedition -> village. Run it in a window with vsync off (the test turns it off):
##   Godot --path game --position X,Y --script res://tests/loading_frames.gd -- --server=http://127.0.0.1:8820
## A frame counts while the veil is up (fading out, covered, fading in). Prints one LOADING line per
## change of place (worst frame, frames over 50 ms, seconds under the veil) and LOADING_FRAMES {...}.
## --max-hitch=MS fails a change whose worst frame under the card is longer than MS.
## --load-phases (passed on to the game's LoadPace) adds each change's phase times (ms): paced build
## work by kind, waiting for file reads, GPU upload + engine, render, first render after the build.
## Every change also reports video/static memory after it, and the start its black screen: from the
## engine's start until the first frame that shows the card.
var failures: Array[String] = []
var server := "http://127.0.0.1:8766"
var max_hitch := 0.0
var transition_script: Script
var pace: Script
## [usec, frame ms, veil alpha, card visible, style]
var samples: Array = []
var last_usec := 0
var results := {}

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
		if arg.begins_with("--max-hitch="): max_hitch = float(arg.trim_prefix("--max-hitch="))
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	transition_script = load("res://scripts/transition.gd")
	pace = load("res://scripts/load_pace.gd")
	call_deferred("run")
	create_timer(300).timeout.connect(func():
		failures.append("timed out after 300 seconds")
		finish())

func check(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failures.append(description)

func finish() -> void:
	print("LOADING_FRAMES ", JSON.stringify({"ok":failures.is_empty(), "failures":failures, "changes":results}))
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
	if ms > 50.0 and "--log-hitches" in OS.get_cmdline_user_args():
		print("HITCH %.1f ms at %d (process %.1f, physics %.1f)" % [ms, Time.get_ticks_msec(), Performance.get_monitor(Performance.TIME_PROCESS)*1000.0, Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)*1000.0])
	var v := veil()
	samples.append([now, ms, v.veil.modulate.a if v else 0.0, v.card.visible and v.is_inside_tree() if v else false, v.style if v else ""])

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

func settled() -> bool:
	var v := veil()
	return v != null and is_zero_approx(v.veil.modulate.a) and not v.card.visible and (v.tween == null or not v.tween.is_running())

## Frames from `from` on that began with the veil (or the card) on screen: a frame that ends a
## stall shows its length on the card. The frame that first raises the veil is not one of them (at
## the game's start the card is not drawn yet; that time is the boot's black screen).
func judge(name: String, from: int) -> void:
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
		return
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
	results[name] = {"worst_ms":snappedf(worst, 0.1), "over_50ms":over, "frames":frames.size(), "seconds":snappedf(seconds, 0.01),
		"mean_ms":snappedf(total/frames.size(), 0.1), "longest":longest,
		"video_mb":snappedf(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED)/1048576.0, 0.1),
		"texture_mb":snappedf(Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED)/1048576.0, 0.1),
		"static_mb":snappedf(Performance.get_monitor(Performance.MEMORY_STATIC)/1048576.0, 0.1)}
	if pace.phases_on:
		var phases: Dictionary = pace.take_phases()
		for key in phases: phases[key] = snappedf(phases[key], 0.1)
		results[name]["phases"] = phases
		print("LOAD_PHASES %s %s" % [name, JSON.stringify(phases)])
	print("LOADING %-28s worst=%7.1f ms  >50ms=%3d  frames=%4d  under veil=%5.2f s  longest=%s" % [name, worst, over, frames.size(), seconds, str(longest)])
	if max_hitch > 0.0: check(worst <= max_hitch, "%s: worst frame %.1f ms <= %.0f ms" % [name, worst, max_hitch])

func change(name: String, action: Callable, arrived: Callable, seconds := 90.0) -> bool:
	await wait_until(settled, 10.0)
	await create_timer(0.5).timeout
	var mark := samples.size()
	if pace.phases_on: pace.take_phases()
	action.call()
	var ok := await wait_until(func(): return arrived.call() and settled(), seconds)
	check(ok, name+": arrived")
	if ok: judge(name, mark)
	return ok

func run() -> void:
	process_frame.connect(record)
	var mark := samples.size()
	change_scene_to_file("res://scenes/main.tscn")
	var titled := await wait_until(func(): return is_instance_valid(current_scene) and current_scene.get("screen") == "login" and not current_scene.busy and settled(), 120.0)
	check(titled, "start: reached the title")
	if not titled:
		finish()
		return
	judge("start -> title", mark)
	# The boot's black screen: until the frame after the first one that drew the card.
	for i in samples.size()-1:
		if samples[i][3]:
			results["start -> title"]["black_until_card_s"] = snappedf(samples[i+1][0]/1000000.0, 0.01)
			print("LOADING black screen until the card: %.2f s after the engine started" % (samples[i+1][0]/1000000.0))
			break
	if "--stop-at-title" in OS.get_cmdline_user_args():
		finish()
		return
	var user := "load_"+str(Time.get_ticks_usec() % 100000000)
	var ok := await change("title -> home", func(): current_scene.authenticate(true, server, user, "Load-check-password-1!", ""),
		func(): return is_instance_valid(current_scene) and current_scene.get("room") == "home")
	if not ok:
		finish()
		return
	ok = await change("home -> village", func(): current_scene.leave(),
		func(): return is_instance_valid(current_scene) and current_scene.get("screen") == "village")
	if not ok:
		finish()
		return
	var house: String = load("res://scripts/npc_gifts.gd").home_of("naru")
	if await change("village -> resident's house", func(): current_scene.open_studio(house),
			func(): return is_instance_valid(current_scene) and current_scene.get("room") == house):
		await change("resident's house -> village", func(): current_scene.leave(),
			func(): return is_instance_valid(current_scene) and current_scene.get("screen") == "village")
	if await change("village -> expedition", func(): current_scene.start_run("forest"),
			func(): return current_scene.get("screen") == "survival" and not current_scene.busy):
		await change("expedition -> village", func(): current_scene.leave_run(),
			func(): return current_scene.get("screen") == "village" and not current_scene.busy)
	finish()
