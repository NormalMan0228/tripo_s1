extends SceneTree
## Time of day on the expeditions and the tutorial's guidance in the world, in the real game
## against a QA server, in a window (captures for review). A new account:
##  1. the tutorial (its first expedition): one capture per goal with its cue in the world (gather,
##     craft, the fire from away and at the camp, the creatures, cleared), the goals played by a bot
##     on the public run API while the game's own ticks are paused (as stage_smoke.gd does);
##  2. per map (--maps, default forest,quarry,frost): the camp fire lit, the ticks paused (the run's
##     clock stands still), the camera pinned on the camp and day_progress held at 0.15 / 0.5 / 0.6 /
##     0.66 / 0.8: <map>_tod_<n>_<progress>.png, UI hidden; then the map's boss night held (0.82 with
##     the server's boss_night flag, no boss on the field): <map>_tod_6_boss.png;
##  3. the forest's boss night: ticks on (fire kept up) until it comes: forest_boss_night.png. Run the
##     QA server with short stages (TRIPOTHON_STAGE_SECONDS=24: the forest's boss night ~82 s in).
## Checks along the way: noon (0.3) is the map's tuned day grade, 0.6 is the sunset (its warm sun),
## the night is dark, the boss night red, the guide marks each goal. --skip-tutorial marks the new
## account's tutorial as cleared on the client, so its expeditions go to the maps themselves.
## Prints EXPDAY PASS/FAIL lines and EXPDAY_RESULT {json}.
## Usage: Godot --path game --position X,Y --script res://tests/expedition_daytime.gd -- --qa --mute
##   --server=http://127.0.0.1:8831 --out=D:/.../artifacts/tod [--maps=forest] [--skip-tutorial] [--skip-boss]
const PROGRESS := [0.15, 0.5, 0.6, 0.66, 0.8]
const CP = preload("res://scripts/controller_profile.gd")
var server := preload("res://tests/qa_server.gd").url()
var out_dir := ""
var maps := ["forest", "quarry", "frost"]
var failures: Array[String] = []
var result := {"tutorial":{}, "maps":{}}
var pin: Pin
# The tutorial bot's state (the public run API).
var api: Node
var route := ""
var s: Dictionary = {}

## Holds the camera on a fixed focus after main.gd's follow camera (priority 0) and before the
## survival map (priority 100), and the run's clock at `progress` (the boss night when `boss`).
class Pin extends Node:
	const CP = preload("res://scripts/controller_profile.gd")
	var app: Node
	var focus := Vector3(0.0, 0.0, 1.4)
	var progress := 0.3
	var boss := false
	var hold_time := false
	var hold_camera := false
	func _init() -> void:
		process_priority = 50
	func _process(_delta: float) -> void:
		if not is_instance_valid(app): return
		var run = app.get("run")
		if hold_time and run is Dictionary and not (run as Dictionary).is_empty():
			run["day_progress"] = progress
			run["night"] = progress >= 0.65
			run["boss_night"] = boss
		var cam: Camera3D = app.get("camera")
		if not hold_camera or not is_instance_valid(cam): return
		var f := focus+CP.CAMERA_FOCUS_OFFSET
		cam.global_position = f+CP.CAMERA_OFFSET*CP.CAMERA_PULLBACK
		cam.look_at(f, Vector3.UP)
		cam.size = CP.CAMERA_DEFAULT

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="): out_dir = arg.trim_prefix("--out=")
		if arg.begins_with("--maps="): maps = arg.trim_prefix("--maps=").split(",")
	call_deferred("run")
	create_timer(1100).timeout.connect(func():
		failures.append("timed out after 1100 seconds")
		finish())

func check(value: bool, description: String) -> void:
	print("EXPDAY ", "PASS " if value else "FAIL ", description)
	if not value: failures.append(description)

func finish() -> void:
	result["ok"] = failures.is_empty()
	result["failures"] = failures
	print("EXPDAY_RESULT ", JSON.stringify(result))
	quit(0 if failures.is_empty() else 1)

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

func settled() -> bool:
	var node = load("res://scripts/transition.gd").get("instance")
	return is_instance_valid(node) and is_zero_approx(node.veil.modulate.a) and not node.card.visible and (node.tween == null or not node.tween.is_running())

func app() -> Node:
	return current_scene

func run_state() -> Dictionary:
	return app().get("run") if is_instance_valid(app()) else {}

func map_node() -> Node:
	var world = app().get("world") if is_instance_valid(app()) else null
	return world.get_node_or_null("SurvivalMap") if is_instance_valid(world) else null

func in_survival() -> bool:
	return is_instance_valid(app()) and app().get("screen") == "survival" and app().get("busy") != true and settled()

func in_village() -> bool:
	return is_instance_valid(app()) and app().get("screen") == "village" and app().get("busy") != true

## The frame as drawn (UI hidden unless `with_ui`).
func capture(file: String, with_ui := false) -> void:
	if out_dir.is_empty(): return
	DirAccess.make_dir_recursive_absolute(out_dir)
	var hidden: Array = []
	if not with_ui:
		for layer in root.find_children("*", "CanvasLayer", true, false):
			if layer.visible:
				layer.visible = false
				hidden.append(layer)
	for i in 3: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out_dir.path_join(file))
	for layer in hidden:
		if is_instance_valid(layer): layer.visible = true
	print("EXPDAY CAPTURE ", file)

func run() -> void:
	pin = Pin.new()
	root.add_child(pin)
	change_scene_to_file("res://scenes/main.tscn")
	if not await wait_until(func(): return is_instance_valid(app()) and app().get("screen") == "login" and app().get("busy") != true, 120.0):
		check(false, "reached the title")
		return finish()
	var user := "tod_"+str(Time.get_ticks_usec() % 100000000)
	app().authenticate(true, server, user, "Daytime-check-password-1!", "")
	if not await wait_until(func(): return is_instance_valid(app()) and app().get("room") == "home" and app().get("busy") != true, 90.0):
		check(false, "signed up and reached home")
		return finish()
	var arrived := false
	for attempt in 6:
		await wait_until(settled, 60.0)
		if is_instance_valid(app()) and app().has_method("leave") and app().get("room") == "home": app().leave()
		arrived = await wait_until(in_village, 30.0)
		if arrived: break
	if not arrived:
		check(false, "reached the village")
		return finish()
	pin.app = app()
	if not "--skip-tutorial" in OS.get_cmdline_user_args():
		await tutorial()
	for map_id in maps:
		if not failures.is_empty() and failures.size() > 6: break
		await strip(map_id)
	finish()

# ------------------------------------------------------------------ the tutorial
func tutorial() -> void:
	await create_timer(1.5).timeout
	app().start_run("forest", "relaxed")
	if not await wait_until(in_survival, 90.0):
		check(false, "the tutorial started")
		return
	var map := map_node()
	var guide: Node = map.get_node_or_null("TutorialGuide") if map else null
	check(run_state().get("map_id") == "tutorial" and guide != null, "the first expedition is the tutorial, with its guide in the world")
	if guide == null: return
	await create_timer(2.0).timeout
	app().paused = true
	await wait_until(func(): return not app().ticking, 5.0)
	api = app().api
	route = "/v1/runs/"+str(app().run_id)
	var reply: Dictionary = await api.request(route)
	if not reply.ok:
		check(false, "read the tutorial's run")
		return
	s = reply.data
	await show_state(1.8)
	check(int(guide.step) == 0 and guide.goal_at != Vector3.INF and is_instance_valid(guide.goal_model), "gather: a resource is marked (step %d)" % int(guide.step))
	result.tutorial["gather"] = {"target":str(guide.goal_at), "outlined":is_instance_valid(guide.goal_model)}
	await capture("tutorial_1_gather.png", true)
	# Two stones and four wood (stage_smoke.gd's bot), then the axe's materials are in the bag.
	await walk_to(Vector2(0.7, -1.7))
	await act("harvest", "n2", func(): return int(s.inventory.stone) >= 2)
	await walk_to(Vector2(1.6, 0.0))
	await act("harvest", "n0", func(): return int(s.harvested) >= 6)
	await show_state(1.8)
	check(int(guide.step) == 1 and guide.cue_kind == "bag", "craft: the bag's icon over the walker (step %d, cue %s)" % [int(guide.step), guide.cue_kind])
	await capture("tutorial_2_craft.png", true)
	await act("craft", "axe", func(): return int((s.get("crafted", {}) as Dictionary).get("axe", 0)) >= 1)
	await walk_to(Vector2(0.0, 7.0))
	await show_state(1.8)
	check(int(guide.step) == 2 and guide.show_zone and guide.goal_at == Vector3.ZERO, "fire: the hearth's ring and gem from away (step %d)" % int(guide.step))
	await capture("tutorial_3_fire.png", true)
	await walk_to(Vector2(0.0, 1.8))
	await show_state(1.8)
	check(guide.cue_kind == "fire", "fire: the fire's icon over the walker at the camp (cue %s)" % guide.cue_kind)
	await capture("tutorial_3b_fire_here.png", true)
	await act("fire", "", func(): return int(s.get("fires", 0)) >= 1)
	# The night brings the creatures (the run's clock moves with the bot's inputs).
	await act("", "", func(): return not (s.get("enemies", []) as Array).is_empty(), 60.0)
	await act("", "", func(): return false, 2.0)
	await show_state(2.0)
	check(int(guide.step) == 3 and is_instance_valid(guide.threat_node), "creatures: the nearest one is marked (step %d)" % int(guide.step))
	await capture("tutorial_4_creatures.png", true)
	await fight(func(): return s.get("status") != "active", 150.0)
	await show_state(0.4)
	await capture("tutorial_5_cleared.png", true)
	await create_timer(1.8).timeout
	check(not guide.visible or float(guide.fade) <= 0.01, "cleared: the guide faded out (fade %.2f)" % float(guide.fade))
	result.tutorial["won"] = s.get("status")
	app().paused = false
	await create_timer(0.5).timeout
	app().leave_run(false)
	await wait_until(in_village, 90.0)
	await wait_until(func(): return app().me.get("tutorial_done") == true, 10.0)

## The bot's state into the game (paused: the walker stands where the server has it) and a moment
## for the guide to pick and glide.
func show_state(seconds: float) -> void:
	app().run = s
	app().update_run()
	await create_timer(seconds).timeout

func send(dx: float, dz: float, action: String, target: String) -> void:
	var payload := {"sequence":int(s.get("sequence", 0))+1, "dx":clampf(dx, -1, 1), "dz":clampf(dz, -1, 1), "sprint":false, "action":action, "target":target}
	var reply: Dictionary = await api.request(route+"/input", payload, HTTPClient.METHOD_POST)
	if reply.ok: s = reply.data
	elif str(reply.get("error", "")) == "stale_input":
		var fresh: Dictionary = await api.request(route)
		if fresh.ok: s = fresh.data
	await create_timer(0.1).timeout

func walk_to(goal: Vector2, seconds := 20.0) -> void:
	var deadline := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < deadline:
		var at := Vector2(float(s.x), float(s.z))
		if at.distance_to(goal) < 0.3: return
		var step := (steer(at, goal)-at)*2.0
		await send(step.x, step.y, "", "")

func act(action: String, target: String, done: Callable, seconds := 20.0) -> void:
	var deadline := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < deadline and s.get("status") == "active":
		if done.call(): return
		await send(0.0, 0.0, action, target)

func fight(done: Callable, seconds: float) -> void:
	var deadline := Time.get_ticks_msec()+int(seconds*1000.0)
	var report := 0
	while Time.get_ticks_msec() < deadline:
		if done.call(): return
		report += 1
		if report % 40 == 0:
			var near := []
			for enemy in s.get("enemies", []): near.append("%s(%.1f,%.1f hp%.0f)" % [enemy.get("species", "?"), float(enemy.x), float(enemy.z), float(enemy.hp)])
			print("EXPDAY BOT at (%.1f,%.1f) kills %s hp %.0f msg %s enemies %s" % [float(s.x), float(s.z), s.get("kills"), float(s.get("hp", 0)), s.get("message"), near])
		var at := Vector2(float(s.x), float(s.z))
		var nearest = null
		for enemy in s.get("enemies", []):
			if nearest == null or at.distance_to(Vector2(enemy.x, enemy.z)) < at.distance_to(Vector2(nearest.x, nearest.z)): nearest = enemy
		if nearest == null:
			await send(0.0, 0.0, "", "")
			continue
		# Closing in while swinging (stage_smoke.gd's bot): a swing an obstacle blocks lands once nearer.
		var goal := Vector2(nearest.x, nearest.z)
		var step := (steer(at, goal)-at)*2.0
		if at.distance_to(goal) < 1.0: step = Vector2.ZERO
		await send(step.x, step.y, "attack" if at.distance_to(goal) < 2.2 else "", "")

## Around the camp's fire pit (solid, 1.05 m at the centre): along a 1.9 m ring until the goal is in
## a straight line that clears it (stage_smoke.gd).
func steer(at: Vector2, goal: Vector2) -> Vector2:
	var d := goal-at
	var t := clampf(-at.dot(d)/maxf(d.length_squared(), 0.0001), 0.0, 1.0)
	if (at+d*t).length() > 1.4: return goal
	var turn := wrapf(goal.angle()-at.angle(), -PI, PI)
	return Vector2.from_angle(at.angle()+clampf(turn, -0.6, 0.6))*1.9

# ------------------------------------------------------------------ the maps' hours
func strip(map_id: String) -> void:
	await create_timer(1.5).timeout
	# The village's /v1/me refresh brings the server's flag back each time.
	if "--skip-tutorial" in OS.get_cmdline_user_args(): app().me["tutorial_done"] = true
	app().start_run(map_id, "relaxed")
	if not await wait_until(in_survival, 90.0):
		check(false, "%s started" % map_id)
		return
	if str(run_state().get("map_id", "")) != map_id:
		check(false, "%s started (got %s: the tutorial is not cleared?)" % [map_id, run_state().get("map_id")])
		app().leave_run(false)
		await wait_until(in_village, 90.0)
		return
	await create_timer(1.0).timeout
	app().intent("fire")
	await wait_until(func(): return float(run_state().get("fire_remaining", 0.0)) > 0.0, 6.0)
	app().paused = true
	await wait_until(func(): return not app().ticking, 5.0)
	var map := map_node()
	pin.focus = Vector3(0.0, 0.0, 1.4)
	pin.hold_camera = true
	pin.hold_time = true
	pin.boss = false
	var report := {}
	# Noon: the map's tuned day grade, as before the time of day.
	pin.progress = 0.3
	await create_timer(1.0).timeout
	# Snapped to the hour (a delta of 0), then read before the next frame eases anything.
	map._process(0.0)
	var look: Dictionary = map.look
	var env: Environment = app().environment
	var sun: DirectionalLight3D = app().sun
	check(env.background_color.is_equal_approx(Color(look.background)) and sun.light_color.is_equal_approx(Color(look.sun))
		and is_equal_approx(sun.light_energy, float(look.sun_energy)) and sun.rotation_degrees.distance_to(Vector3(float(look.sun_pitch), float(look.sun_yaw), 0.0)) < 0.05,
		"%s noon is the map's day grade (sky %s, sun %s %.3f, %s)" % [map_id, env.background_color.to_html(false), sun.light_color.to_html(false), sun.light_energy, str(sun.rotation_degrees)])
	for i in PROGRESS.size():
		var p: float = PROGRESS[i]
		pin.progress = p
		await create_timer(4.5).timeout
		report[str(p)] = {"hour":snappedf(float(map.daytime.hour), 0.01), "night":snappedf(float(map.night), 0.01), "dusk":snappedf(float(map.dusk), 0.01),
			"sunset":snappedf(float(map.daytime.sunset), 0.01), "saturation":snappedf(env.adjustment_saturation, 0.01),
			"sky":env.background_color.to_html(false), "sun":sun.light_color.to_html(false), "sun_energy":snappedf(sun.light_energy, 0.01),
			"sun_rotation":[snappedf(sun.rotation_degrees.x, 0.1), snappedf(sun.rotation_degrees.y, 0.1)], "adjustment":env.adjustment_enabled}
		await capture("%s_tod_%d_%s.png" % [map_id, i+1, str(p).replace(".", "")])
		if is_equal_approx(p, 0.6):
			var c := sun.light_color
			check(float(map.daytime.sunset) > 0.9 and c.r > 0.95 and c.g < 0.75 and c.b < c.g,
				"%s 0.6 is the sunset: a deep orange sun (sunset %.2f, sun %s)" % [map_id, float(map.daytime.sunset), c.to_html(false)])
	check(float(map.night) > 0.95, "%s 0.8 is night (%.2f)" % [map_id, float(map.night)])
	# The boss night held: deep night under its red moon and sky.
	pin.progress = 0.82
	pin.boss = true
	await create_timer(4.5).timeout
	var red := sun.light_color
	report["boss"] = {"night":snappedf(float(map.night), 0.01), "boss":snappedf(float(map.daytime.boss), 0.01), "sky":env.background_color.to_html(false),
		"sun":red.to_html(false), "sun_energy":snappedf(sun.light_energy, 0.01)}
	check(float(map.daytime.boss) > 0.95 and red.r > red.g*1.6 and env.background_color.r > env.background_color.b,
		"%s boss night: a red moon and sky (moon %s, sky %s)" % [map_id, red.to_html(false), env.background_color.to_html(false)])
	await capture("%s_tod_6_boss.png" % map_id)
	pin.boss = false
	result.maps[map_id] = report
	pin.hold_time = false
	pin.hold_camera = false
	app().paused = false
	if map_id == "forest" and not "--skip-boss" in OS.get_cmdline_user_args():
		await boss_night()
	app().leave_run(false)
	await wait_until(in_village, 90.0)

func boss_night() -> void:
	var deadline := Time.get_ticks_msec()+240000
	var s2 := run_state()
	while Time.get_ticks_msec() < deadline:
		s2 = run_state()
		if s2.get("status") != "active": break
		if (s2.get("night") == true) and float(s2.get("fire_remaining", 0.0)) < 4.0 and int(s2.inventory.wood) >= 2: app().intent("fire")
		if (s2.get("boss_night") == true) and s2.get("boss") is Dictionary: break
		await create_timer(0.25).timeout
	if not ((s2.get("boss_night") == true) and s2.get("boss") is Dictionary):
		check(false, "the forest's boss night came (status %s, stage %s)" % [s2.get("status"), s2.get("stage")])
		return
	await create_timer(4.0).timeout
	var map := map_node()
	check(map != null and float(map.night) > 0.95 and float(map.daytime.boss) > 0.9, "the boss night: deep night with its tint (night %.2f, boss %.2f)" % [float(map.night), float(map.daytime.boss)])
	await capture("forest_boss_night.png")
	result["boss"] = {"sky":app().environment.background_color.to_html(false), "sun":app().sun.light_color.to_html(false), "hp":run_state().get("hp")}
