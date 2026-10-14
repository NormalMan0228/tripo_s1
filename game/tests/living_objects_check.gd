extends SceneTree
## Living crafted objects against a local demo server: a crafted wall clock arrives with its hands on
## the player's local time (hour and minute glide, the second hand ticks 6° a second with a small
## mechanical overshoot), it stops working while nobody can see it and is right again when seen, and a
## crafted chest of drawers slides its drawer out on E. The hands are the game's own crafted shapes
## (spade, arrow, needle with a counterweight, hub caps) in layers in front of the dial, coloured by
## the craft style. --capture saves two pictures of the ticking clock a second apart
## (artifacts/clock-tick-1.png, -2.png) and close-ups of antique and sci-fi hands
## (artifacts/clock-hands-antique.jpg, -scifi.jpg); run it windowed for those.
##   godot --path game --script res://tests/living_objects_check.gd -- --server=URL [--capture]
const Assembly = preload("res://scripts/asset_assembly.gd")
const Api = preload("res://scripts/api.gd")

var server := preload("res://tests/qa_server.gd").url()
var failures: Array[String] = []
var passes := 0

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if value: passes += 1
	else: failures.append(label)

func _initialize() -> void:
	call_deferred("run")

func finish() -> void:
	Assembly.clock_override = -1.0
	print("LIVING_OBJECTS_CHECK ", JSON.stringify({"ok": failures.is_empty(), "passed": passes, "failures": failures}))
	quit(0 if failures.is_empty() else 1)

func frames(count := 2) -> void:
	for i in count: await process_frame

## Degrees clockwise (seen from the front) a hand shows, 0..360.
func clockwise(item: Node3D, part: String) -> float:
	return fposmod(-item.pivots[part].rotation_degrees.z, 360.0)

func near(a: float, b: float, tolerance := 0.05) -> bool:
	return absf(wrapf(a - b, -180.0, 180.0)) <= tolerance

## A fixture craft (proxy shapes, no paid call) made into an object: its id, or "".
func craft(api: Node, prompt: String, extra := {}) -> String:
	var queued: Dictionary = await api.post("/v1/studio/jobs", api.mutation({"prompt": prompt, "geometry": "proxy", "designer": "fixture"}.merged(extra)))
	if not queued.ok: return ""
	var deadline := Time.get_ticks_msec() + 30000
	while Time.get_ticks_msec() < deadline:
		var job: Dictionary = await api.request("/v1/studio/jobs/" + str(queued.data.id))
		if job.ok and job.data.state == "ready": return str(job.data.object_id)
		if job.ok and job.data.state == "failed": return ""
		await create_timer(0.3).timeout
	return ""

func stage() -> Camera3D:
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("e9e2d4")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color(0.85, 0.85, 0.85)
	root.add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-35, 25, 0)
	root.add_child(sun)
	var camera := Camera3D.new()
	root.add_child(camera)
	camera.position = Vector3(0, 0.45, 1.55)
	camera.fov = 45
	camera.current = true
	return camera

func capture(path: String) -> void:
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.resize(640, int(640.0 * image.get_height() / image.get_width()), Image.INTERPOLATE_LANCZOS)
	if path.ends_with(".jpg"): image.save_jpg(path, 0.88)
	else: image.save_png(path)
	print("CAPTURE ", ProjectSettings.globalize_path(path))

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	var api := Api.new()
	root.add_child(api)
	api.base_url = server
	var login: Dictionary = await api.post("/v1/auth/register", {"username": "lvg_" + str(Time.get_ticks_usec() % 100000000), "password": "Living-check-password"})
	check(login.ok, "an account on the demo server")
	if not login.ok: finish(); return
	api.token = str(login.data.get("token", ""))
	var camera := stage()

	# A wall clock asked for as a still piece: it is built moving anyway, with separate hands turning
	# with the player's local time (the hands cost nothing; the still price is kept).
	var clock_id := await craft(api, "벽시계", {"motion": "static"})
	check(not clock_id.is_empty(), "a wall clock is crafted")
	if clock_id.is_empty(): finish(); return
	var clock: Node3D = await Assembly.fetch(api, clock_id)
	check(clock != null and clock.pivots.has("hour_hand") and clock.pivots.has("second_hand"), "the clock has its own hands")
	if clock == null: finish(); return
	check(str(clock.manifest.get("interaction", {}).get("mode", "")) == "presets", "it arrives with the clock type's behaviour")
	var hand_mesh: MeshInstance3D = clock.surfaces["hour_hand"][0]
	check(hand_mesh.mesh.surface_get_array_len(0) > 100, "the hands are crafted shapes, not bars (%d vertices)" % hand_mesh.mesh.surface_get_array_len(0))
	var layers := [clock.pose_nodes["hour_hand"].position.z, clock.pose_nodes["minute_hand"].position.z, clock.pose_nodes["second_hand"].position.z]
	check(layers[0] > 0.07 and layers[0] < layers[1] and layers[1] < layers[2], "they stand in layers in front of the dial (%s)" % str(layers))
	root.add_child(clock)
	var at := 10 * 3600 + 8 * 60 + 30.5  # 10:08:30.5
	Assembly.clock_override = at
	await frames()
	check(near(clockwise(clock, "hour_hand"), (10 + 8.0 / 60 + 30.5 / 3600) * 30), "hour hand at 10:08 (%.2f°)" % clockwise(clock, "hour_hand"))
	check(near(clockwise(clock, "minute_hand"), (8 + 30.5 / 60) * 6), "minute hand at 8 min 30 s (%.2f°)" % clockwise(clock, "minute_hand"))
	check(near(clockwise(clock, "second_hand"), 30 * 6), "second hand at 30 s (%.2f°)" % clockwise(clock, "second_hand"))
	# One second later: one step of 6°, after a quick jump that goes a little past it.
	Assembly.clock_override = at + 0.6  # 0.1 s into second 31
	await frames()
	var mid := wrapf(clockwise(clock, "second_hand") - 180.0, -180.0, 180.0)
	Assembly.clock_override = at + 1.0
	await frames()
	var settled := wrapf(clockwise(clock, "second_hand") - 180.0, -180.0, 180.0)
	check(near(settled, 6), "a second later the second hand moved one 6° step (%.2f°)" % settled)
	check(mid > 6.2 and mid < 7.2, "mid-step it overshoots a little like a mechanism (%.2f°)" % mid)
	Assembly.clock_override = at + 0.54
	await frames()
	var early := wrapf(clockwise(clock, "second_hand") - 180.0, -180.0, 180.0)
	check(early > 0.0 and early < 6.0, "the jump takes a moment (%.2f° after 0.04 s)" % early)

	# Out of sight it does no work; back in view it shows the right time at once.
	clock.position = Vector3(0, 0, 400)
	Assembly.clock_override = at + 600
	await frames()
	check(near(clockwise(clock, "minute_hand"), (8 + 30.5 / 60) * 6, 0.2), "far out of view the hands wait")
	clock.position = Vector3.ZERO
	await frames()
	check(near(clockwise(clock, "minute_hand"), (18 + 30.5 / 60) * 6), "in view again they show the time (%.2f°)" % clockwise(clock, "minute_hand"))

	if "--capture" in OS.get_cmdline_user_args():
		Assembly.clock_override = -1.0
		camera.look_at(Vector3(0, 0.45, 0))
		await create_timer(0.6).timeout
		await capture("res://../artifacts/clock-tick-1.png")
		await create_timer(1.0).timeout
		await capture("res://../artifacts/clock-tick-2.png")
	clock.queue_free()

	# Hands in two craft styles: antique dark iron and brass, sci-fi gunmetal with a glowing second hand.
	for style in ["antique", "scifi"]:
		var styled_id := await craft(api, "벽시계", {"style": style, "motion": "static"})
		var styled: Node3D = await Assembly.fetch(api, styled_id) if not styled_id.is_empty() else null
		check(styled != null, "a %s wall clock is crafted" % style)
		if styled == null: continue
		var colours := {}
		for part in styled.manifest.plan.parts: colours[part.id] = str(part.color)
		var glows := JSON.stringify(styled.vm.program).contains("emission")
		if style == "antique": check(colours.hour_hand == "#2b2622" and colours.second_hand == "#b08d57" and not glows, "antique hands: dark iron and a brass second hand")
		else: check(colours.second_hand == "#42d9ff" and glows, "sci-fi hands: a glowing cyan second hand")
		root.add_child(styled)
		Assembly.clock_override = 10 * 3600 + 9 * 60 + 36.5
		if "--capture" in OS.get_cmdline_user_args():
			camera.position = Vector3(0.32, 0.5, 1.05)
			camera.look_at(Vector3(0, 0.45, 0))
			await create_timer(0.8).timeout
			await capture("res://../artifacts/clock-hands-%s.jpg" % style)
		styled.queue_free()
		await frames()

	# A chest of drawers (a second account: a new one has starseeds for a few crafts): E slides the
	# drawer out, again pushes it back.
	Assembly.clock_override = -1.0
	var second: Dictionary = await api.post("/v1/auth/register", {"username": "lvh_" + str(Time.get_ticks_usec() % 100000000), "password": "Living-check-password"})
	if second.ok: api.token = str(second.data.get("token", ""))
	var drawers_id := await craft(api, "서랍장")
	var drawers: Node3D = await Assembly.fetch(api, drawers_id) if not drawers_id.is_empty() else null
	check(drawers != null and drawers.pivots.has("drawer"), "a chest of drawers is crafted with a drawer part")
	if drawers:
		root.add_child(drawers)
		drawers.local_event("click")
		await create_timer(1.2).timeout
		var out: float = drawers.pivots["drawer"].position.z
		check(out > 0.25 and out <= 0.31, "E slides the drawer out (%.2f m)" % out)
		drawers.local_event("click")
		await create_timer(1.2).timeout
		check(absf(drawers.pivots["drawer"].position.z) < 0.02, "E again pushes it back")
	finish()
