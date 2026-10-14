extends SceneTree
## Every change of place through the real game, against a QA server: title -> home
## (log in), home -> village (front door), village -> expedition, expedition ->
## village. Each must fade out and back in over several frames (never a cut), with
## the loading card (place name and a tip) up while the screen is covered.
##   Godot --headless --path game --script res://tests/world_transitions.gd -- --server=http://127.0.0.1:8812
var failures: Array[String] = []
var server := preload("res://tests/qa_server.gd").url()
var samples: Array = []
var veil: CanvasLayer

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("world_transitions exceeded 240 seconds")
		finish())

func check(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failures.append(description)

func finish() -> void:
	print("WORLD_TRANSITIONS ", JSON.stringify({"ok":failures.is_empty(), "failures":failures}))
	quit(0 if failures.is_empty() else 1)

func record() -> void:
	if not is_instance_valid(veil): return
	samples.append([Time.get_ticks_msec(), veil.veil.modulate.a, veil.card.visible, veil.heading.text, veil.style])

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

func settled() -> bool:
	return is_instance_valid(veil) and is_zero_approx(veil.veil.modulate.a) and veil.tween != null and not veil.tween.is_running()

## One change of place: the veil climbs to covered and falls back over frames.
func judge(name: String, run_from: int) -> void:
	var part := samples.slice(run_from)
	var rising := 0
	var falling := 0
	var covered := false
	var peak_index := -1
	var card_seen := false
	var heading := ""
	for i in part.size():
		var alpha: float = part[i][1]
		if alpha >= 0.999 and not covered:
			covered = true
			peak_index = i
		if covered and part[i][2]:
			card_seen = true
			heading = str(part[i][3]) if heading.is_empty() else heading
		if alpha > 0.05 and alpha < 0.95:
			if not covered: rising += 1
			else: falling += 1
	check(covered, "%s: the screen is covered" % name)
	check(rising >= 3, "%s: fades out over %d frames" % [name, rising])
	check(falling >= 3, "%s: fades in over %d frames" % [name, falling])
	check(card_seen, "%s: the loading card shows (%s)" % [name, heading])

func run() -> void:
	process_frame.connect(record)
	change_scene_to_file("res://scenes/main.tscn")
	await create_timer(0.5).timeout
	veil = load("res://scripts/transition.gd").instance
	var main: Node = current_scene
	await wait_until(func(): return is_instance_valid(current_scene) and current_scene.get("screen") == "login" and not current_scene.busy, 60.0)
	main = current_scene
	await wait_until(settled, 5.0)
	# Title -> home: log in (the session opens in the home room).
	var mark := samples.size()
	var user := "fade_"+str(Time.get_ticks_usec() % 100000000)
	main.authenticate(true, server, user, "Fade-check-password-1!", "")
	var in_room := await wait_until(func(): return is_instance_valid(current_scene) and current_scene.get("room") == "home" and settled(), 60.0)
	check(in_room, "logged in and standing in the home room")
	if not in_room:
		finish()
		return
	judge("title -> home", mark)
	await create_timer(0.6).timeout
	# Home -> village through the front door.
	mark = samples.size()
	current_scene.leave()
	var outside := await wait_until(func(): return is_instance_valid(current_scene) and current_scene.get("screen") == "village" and settled(), 90.0)
	check(outside, "walked out into the village")
	if not outside:
		finish()
		return
	judge("home -> village", mark)
	await create_timer(0.6).timeout
	# Village -> expedition and back.
	mark = samples.size()
	current_scene.start_run("forest")
	var away := await wait_until(func(): return current_scene.get("screen") == "survival" and not current_scene.busy and settled(), 90.0)
	check(away, "set out on an expedition")
	if away:
		judge("village -> expedition", mark)
		await create_timer(0.6).timeout
		mark = samples.size()
		current_scene.leave_run()
		var back := await wait_until(func(): return current_scene.get("screen") == "village" and not current_scene.busy and settled(), 90.0)
		check(back, "came back to the village")
		if back: judge("expedition -> village", mark)
	finish()
