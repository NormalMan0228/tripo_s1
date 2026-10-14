extends SceneTree
## Quitting with crafted furniture standing in the village ends cleanly (exit code 0). Every quit of
## the game used to end in an access violation (0xC0000005): settings listeners were lambdas kept in
## GameSettings' static list, which outlives the scripts owning the lambdas' code (game_settings.gd,
## listen()). This places a crafted rocking chair, checks that every settings listener is a plain
## method, and quits with the whole village still up, as a player does. The exit code is the real
## check, so run it through the runner, which fails on a non-zero exit:
##   powershell -File tools\test.ps1 -SkipServerTests -ClientScript exit_clean_check
const Town = preload("res://scripts/town.gd")
const GameSettings = preload("res://scripts/game_settings.gd")

var server := "http://127.0.0.1:8766"
var failures: Array[String] = []

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if not value: failures.append(label)

func _initialize() -> void:
	call_deferred("run")

func wait_until(condition: Callable, seconds := 20.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

func finish() -> void:
	print("EXIT_CLEAN_CHECK ", JSON.stringify({"ok": failures.is_empty(), "failures": failures}))
	quit(0 if failures.is_empty() else 1)

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	var app = load("res://scripts/main.gd").new()
	root.add_child(app)
	await process_frame
	await wait_until(func(): return not app.busy and app.screen == "login", 60.0)
	for _attempt in 3:
		await app.authenticate(true, server, "exq_" + str(Time.get_ticks_usec() % 100000000), "Local-exit-qa-1!", "")
		if app.screen == "village": break
		await create_timer(0.5).timeout
	check(app.screen == "village", "registered and in the village (%s)" % app.screen)
	if app.screen != "village": finish(); return
	# A moving fixture craft (its program, tweens and collision all live) placed in the village.
	var queued: Dictionary = await app.api.post("/v1/studio/jobs", app.api.mutation({"prompt": "흔들의자", "geometry": "proxy", "designer": "fixture", "motion": "dynamic"}))
	var id := ""
	for _i in 60:
		var job: Dictionary = await app.api.request("/v1/studio/jobs/" + str(queued.get("data", {}).get("id", "")))
		if job.ok and job.data.state == "ready": id = str(job.data.object_id); break
		await create_timer(0.5).timeout
	check(not id.is_empty(), "the fixture chair was crafted")
	if id.is_empty(): finish(); return
	await app.refresh_inventory()
	for i in app.me.objects.size():
		if app.me.objects[i].id == id: app.select_object(i)
	await app.begin_place()
	if is_instance_valid(app.preview):
		app.preview.position = Town.furniture_point(4, 3)
		await app.place_preview()
	await wait_until(func(): return app.loaded.has(id) and is_instance_valid(app.loaded[id]))
	check(app.loaded.has(id) and is_instance_valid(app.loaded[id]), "the chair stands in the village")
	var custom := GameSettings.listeners.filter(func(callback: Callable): return callback.is_custom())
	check(not GameSettings.listeners.is_empty() and custom.is_empty(), "settings listeners are plain methods (%d of %d are not)" % [custom.size(), GameSettings.listeners.size()])
	await create_timer(0.5).timeout
	finish()
