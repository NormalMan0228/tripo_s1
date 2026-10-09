extends SceneTree
## Walking up to and away from crafted furniture in the village must not reload the placed objects.
## Each near/leave event raises the object's runtime version on the server; the 3-second /v1/me
## check used to see that as a change and rebuild every placed object (a visible hitch).
const Town = preload("res://scripts/town.gd")
var failures: Array[String] = []

func check(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")

func craft(app: Node, prompt: String) -> String:
	var queued: Dictionary = await app.api.post("/v1/studio/jobs", app.api.mutation({"prompt": prompt, "geometry": "proxy", "designer": "fixture", "motion": "dynamic"}))
	if not queued.ok: return ""
	for _i in 40:
		var job: Dictionary = await app.api.request("/v1/studio/jobs/" + queued.data.id)
		if job.ok and job.data.state == "ready": return str(job.data.object_id)
		await create_timer(0.5).timeout
	return ""

func place(app: Node, id: String, at: Vector2) -> void:
	await app.refresh_inventory()
	for i in app.me.objects.size():
		if app.me.objects[i].id == id: app.select_object(i); break
	await create_timer(0.5).timeout
	await app.begin_place()
	app.preview.position = Town.furniture_point(at.x, at.y)
	await app.place_preview()

func run() -> void:
	var server := "http://127.0.0.1:8766"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	var app = load("res://scripts/main.gd").new()
	root.add_child(app)
	await process_frame
	await create_timer(0.4).timeout
	await app.authenticate(true, server, "hitch_" + str(Time.get_ticks_msec()), "Local-hitch-qa-password1", "")
	for _i in 20:
		if app.screen == "village": break
		await create_timer(0.25).timeout
	print("SCREEN ", app.screen)
	if app.screen != "village": quit(1); return
	var chair := await craft(app, "wooden chair")
	var stool := await craft(app, "small stool")
	check(not chair.is_empty() and not stool.is_empty(), "two crafted objects")
	if chair.is_empty() or stool.is_empty(): quit(1); return
	await place(app, chair, Vector2(4, 3))
	await place(app, stool, Vector2(9, 3))
	check(app.loaded.has(chair) and app.loaded.has(stool), "both placed in the village")
	var first_chair: Node = app.loaded[chair]
	var first_stool: Node = app.loaded[stool]
	# Walk in and out of the chair's reach for about 14 seconds while the game's own timers run
	# (proximity every 0.5 s, /v1/me every 3 s).
	var started := Time.get_ticks_msec()
	var worst := 0.0
	var last := Time.get_ticks_usec()
	var reloads := 0
	var seen: Node = first_chair
	while Time.get_ticks_msec() - started < 14000:
		var phase := fmod((Time.get_ticks_msec() - started) / 1000.0, 2.4)
		app.player.position = Town.furniture_point(4, 4.4 if phase < 1.2 else 8.5)
		await process_frame
		var now := Time.get_ticks_usec()
		var spent := (now - last) / 1000.0
		worst = maxf(worst, spent)
		last = now
		if spent > 30.0: print("SPIKE %.0fms t=%.2f phase=%s nearby=%s pending=%s refreshing=%s" % [spent, (Time.get_ticks_msec() - started) / 1000.0, "near" if phase < 1.2 else "away", app.loaded[chair].nearby, app.furniture_event_pending, app.refreshing])
		if app.loaded.get(chair) != seen:
			reloads += 1
			seen = app.loaded.get(chair)
	print("HITCH worst_frame_ms=%.1f reloads=%d version=%s" % [worst, reloads, str(app.loaded[chair].runtime_version) if app.loaded.has(chair) else "-"])
	check(reloads == 0 and app.loaded.get(chair) == first_chair and app.loaded.get(stool) == first_stool, "walking near furniture never reloads the placed objects")
	check(int(app.loaded[chair].runtime_version) > 1, "near/leave events still reached the server")
	# A refresh for another reason (starseeds changed) keeps the placed models and the bag preview.
	var preview: Node = app.inspect_model
	app.me.shards = int(app.me.shards) + 1
	await app.poll_entitlements()
	check(app.loaded.get(chair) == first_chair and app.loaded.get(stool) == first_stool and app.inspect_model == preview, "a starseed refresh keeps every loaded model")
	# A version raised elsewhere (a room, another PC) is taken without a reload.
	var event: Dictionary = await app.api.post("/v1/objects/" + chair + "/event", app.api.mutation({"version": app.loaded[chair].runtime_version, "event": "click"}))
	await app.refresh_inventory()
	check(event.ok and app.loaded.get(chair) == first_chair and int(app.loaded[chair].runtime_version) == int(event.data.version), "outside state changes sync without a reload")
	# Walk into the chair and the stool with real movement input (physics, step-up, camera), logging spikes.
	for target in [chair, stool]:
		var at: Vector3 = app.loaded[target].position
		app.player.position = at + Vector3(0, 0.2, 2.6)
		app.player.velocity = Vector3.ZERO
		await create_timer(0.5).timeout
		var spikes := []
		var frames := 0
		var slowest := 0.0
		last = Time.get_ticks_usec()
		var walk_start := Time.get_ticks_msec()
		while Time.get_ticks_msec() - walk_start < 5000:
			var toward: Vector3 = at - app.player.position
			Input.action_release("move_left"); Input.action_release("move_right"); Input.action_release("move_forward"); Input.action_release("move_back")
			# Keep pushing into the object (camera-independent: pick the key by world direction).
			if absf(toward.z) > absf(toward.x): Input.action_press("move_forward" if toward.z < 0 else "move_back")
			else: Input.action_press("move_left" if toward.x < 0 else "move_right")
			await process_frame
			var now := Time.get_ticks_usec()
			var ms := (now - last) / 1000.0
			last = now
			frames += 1
			slowest = maxf(slowest, ms)
			if ms > 24.0 and frames > 3:
				spikes.append("%.0fms(proc %.1f phys %.1f near=%s refreshing=%s y=%.2f)" % [ms, Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0, Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0, app.loaded[target].nearby, app.refreshing, app.player.position.y])
		for key in ["move_forward", "move_back", "move_left", "move_right"]: Input.action_release(key)
		print("WALK %s frames=%d slowest=%.1fms distance=%.2f spikes=%s" % [target.substr(0, 6), frames, slowest, Vector2(app.player.position.x - at.x, app.player.position.z - at.z).length(), spikes.slice(0, 12)])
	print("VILLAGE_HITCH " + ("FAILED" if failures else "OK"))
	await app.logout()
	app.queue_free()
	for _i in 10: await process_frame
	await create_timer(0.5).timeout
	quit(1 if failures else 0)
