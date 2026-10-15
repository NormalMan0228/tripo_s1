extends SceneTree
## Expedition stages in the real game, in a window, against a QA server whose first stage is short
## (demo mode, TRIPOTHON_STAGE_SECONDS, e.g. 12: stages of 12, 16, 20 s). A new account:
##  1. asks for the forest and gets the tutorial (its first expedition, /v1/me tutorial_done false);
##     the night comes and outlasts its stage (stage_remaining -1, no boss), the creatures are the
##     tutorial's species drawn with their stand-ins, and nobody falls there;
##  2. its goals (gather 6, an axe, a fire, 2 kills) are met by a bot playing through the public run
##     API while the game's own ticks are paused; the run is won and claimed, and back in the village
##     tutorial_done is true;
##  3. the forest starts (3 stages); its last night is the boss night: the treant comes as a brute
##     scaled to 5 m, the night holds (day_progress 0.82, the map stays dark) and the run goes on.
## Prints STAGE_SMOKE PASS/FAIL lines and STAGE_SMOKE_RESULT {json}; with --out=DIR captures
## tutorial_night.png and forest_boss.png there.
## Usage: Godot --path game --position X,Y --script res://tests/stage_smoke.gd -- --qa
##   --server=http://127.0.0.1:8831 [--out=D:/.../stage_smoke]
var server := preload("res://tests/qa_server.gd").url()
var out_dir := ""
var failures: Array[String] = []
var result := {}

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="): out_dir = arg.trim_prefix("--out=")
	call_deferred("run")
	create_timer(400).timeout.connect(func():
		failures.append("timed out after 400 seconds")
		finish())

func check(value: bool, description: String) -> void:
	print("STAGE_SMOKE ", "PASS " if value else "FAIL ", description)
	if not value: failures.append(description)

func finish() -> void:
	result["ok"] = failures.is_empty()
	result["failures"] = failures
	print("STAGE_SMOKE_RESULT ", JSON.stringify(result))
	quit(0 if failures.is_empty() else 1)

func wait_until(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

## No loading veil or card on screen (transition.gd).
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

func capture(file: String) -> void:
	if out_dir.is_empty(): return
	DirAccess.make_dir_recursive_absolute(out_dir)
	await process_frame
	root.get_texture().get_image().save_png(out_dir.path_join(file))

func in_survival() -> bool:
	return is_instance_valid(app()) and app().get("screen") == "survival" and app().get("busy") != true

func in_village() -> bool:
	return is_instance_valid(app()) and app().get("screen") == "village" and app().get("busy") != true

func run() -> void:
	change_scene_to_file("res://scenes/main.tscn")
	if not await wait_until(func(): return is_instance_valid(app()) and app().get("screen") == "login" and app().get("busy") != true, 120.0):
		check(false, "reached the title")
		return finish()
	var user := "stage_"+str(Time.get_ticks_usec() % 100000000)
	app().authenticate(true, server, user, "Stage-smoke-password-1!", "")
	if not await wait_until(func(): return is_instance_valid(app()) and app().get("room") == "home" and app().get("busy") != true, 90.0):
		check(false, "signed up and reached home")
		return finish()
	# Out of the front door once the home is on screen (leave() waits for no veil); again if it was early.
	var arrived := false
	for attempt in 6:
		await wait_until(settled, 60.0)
		if is_instance_valid(app()) and app().has_method("leave") and app().get("room") == "home": app().leave()
		arrived = await wait_until(in_village, 30.0)
		if arrived: break
	if not arrived:
		check(false, "reached the village (at %s, screen %s)" % [app().get_script().resource_path if is_instance_valid(app()) else "-", app().get("screen") if is_instance_valid(app()) else "-"])
		return finish()
	check(app().me.get("tutorial_done") == false, "a new account has not done the tutorial")
	await tutorial()
	if failures.is_empty(): await forest()
	finish()

func tutorial() -> void:
	await create_timer(1.5).timeout
	app().start_run("forest", "veteran")
	if not await wait_until(in_survival, 90.0):
		check(false, "the first expedition started")
		return
	var s := run_state()
	check(s.get("map_id") == "tutorial" and (s.get("tutorial") == true) and s.get("difficulty") == "relaxed" and int(s.get("stage_count", 0)) == 1,
		"asking for the forest started the tutorial (relaxed, 1 stage): %s/%s/%s" % [s.get("map_id"), s.get("difficulty"), s.get("stage_count")])
	if not await wait_until(func(): return (run_state().get("night", false) == true) and not run_state().get("enemies", []).is_empty(), 60.0):
		check(false, "the tutorial's night came with its creatures")
		return
	await create_timer(2.0).timeout
	s = run_state()
	var species := []
	for enemy in s.get("enemies", []): species.append(str(enemy.get("species", "")))
	check(species.all(func(k): return k in ["goblin", "centipede"]), "tutorial creatures: %s" % [species])
	var art := []
	for node in app().enemy_nodes.values():
		if is_instance_valid(node) and node.get("monster"): art.append(str(node.monster.species))
	check(not art.is_empty() and art.all(func(k): return k in ["wolf", "boar"]), "drawn with their stand-ins (goblin: wolf, centipede: boar): %s" % [art])
	var lowest := 100.0
	var stage_end := float(s.get("stage_seconds", 12.0))
	while float(run_state().get("elapsed", 0.0)) < stage_end+3.0:
		lowest = minf(lowest, float(run_state().get("hp", 100.0)))
		await create_timer(0.2).timeout
	s = run_state()
	var map := map_node()
	check(s.get("status") == "active" and (s.get("night") == true) and int(s.get("stage_remaining", 0)) == -1 and not (s.get("boss_night", true) == true),
		"the tutorial's night outlasts its stage (stage_remaining -1, no boss night)")
	check(map != null and float(map.get("night")) > 0.9, "the map stays dark (night %.2f)" % (float(map.get("night")) if map else -1.0))
	check(lowest >= 1.0 and float(s.get("hp", 0.0)) >= 1.0, "nobody falls (lowest hp %.1f)" % lowest)
	result["tutorial"] = {"species":species, "art":art, "lowest_hp":lowest, "elapsed":s.get("elapsed")}
	await capture("tutorial_night.png")
	# The goals, played through the public run API (the game's own ticks paused meanwhile).
	app().paused = true
	await wait_until(func(): return not app().ticking, 5.0)
	await create_timer(0.5).timeout
	var won := await play_tutorial()
	app().paused = false
	check(won.get("status") == "won" and int(won.get("reward", 0)) == 20, "the tutorial's goals won it (reward %s)" % [won.get("reward")])
	if won.get("status") != "won": return
	app().run = won
	app().update_run()
	await create_timer(1.0).timeout
	app().leave_run(false)
	if not await wait_until(in_village, 90.0):
		check(false, "back in the village after the tutorial")
		return
	await wait_until(func(): return app().me.get("tutorial_done") == true, 10.0)
	check(app().me.get("tutorial_done") == true, "tutorial_done is true after the clear")

## A bot on the run API: two stones and four wood (gather 6), an axe, a fire, then two kills.
func play_tutorial() -> Dictionary:
	var api: Node = app().api
	var route := "/v1/runs/"+str(app().run_id)
	var reply: Dictionary = await api.request(route)
	if not reply.ok: return {}
	var s: Dictionary = reply.data
	var sequence := int(s.sequence)
	var deadline := Time.get_ticks_msec()+150000
	while s.get("status") == "active" and Time.get_ticks_msec() < deadline:
		var inv: Dictionary = s.inventory
		var crafted: Dictionary = s.get("crafted", {}) if s.get("crafted") is Dictionary else {}
		var goal := Vector2(0.0, 1.4)
		var action := ""
		var target := ""
		var at := Vector2(float(s.x), float(s.z))
		var stop := 0.05
		if int(s.harvested) < 4:
			goal = Vector2(1.6, 0.0)
			if at.distance_to(goal) < 0.3:
				action = "harvest"
				target = "n0"
		elif int(inv.stone) < 2 and int(crafted.get("axe", 0)) == 0:
			goal = Vector2(0.7, -1.7)
			if at.distance_to(goal) < 0.3:
				action = "harvest"
				target = "n2"
		elif int(crafted.get("axe", 0)) == 0:
			action = "craft"
			target = "axe"
		elif int(s.get("fires", 0)) == 0:
			action = "fire"
		else:
			var nearest = null
			for enemy in s.enemies:
				if nearest == null or at.distance_to(Vector2(enemy.x, enemy.z)) < at.distance_to(Vector2(nearest.x, nearest.z)): nearest = enemy
			if nearest != null:
				goal = Vector2(nearest.x, nearest.z)
				stop = 1.0
				if at.distance_to(goal) < 2.2: action = "attack"
		var step := (steer(at, goal)-at)*2.0
		if action in ["harvest", "craft", "fire"] or at.distance_to(goal) < stop: step = Vector2.ZERO
		sequence += 1
		reply = await api.request(route+"/input", {"sequence":sequence, "dx":clampf(step.x, -1, 1), "dz":clampf(step.y, -1, 1), "sprint":false, "action":action, "target":target}, HTTPClient.METHOD_POST)
		if reply.ok: s = reply.data
		elif str(reply.get("error", "")) == "stale_input": sequence += 5
		await create_timer(0.1).timeout
	result["tutorial_bot"] = {"status":s.get("status"), "harvested":s.get("harvested"), "kills":s.get("kills"), "fires":s.get("fires"), "hp":s.get("hp")}
	return s

## Around the camp's fire pit (solid, 1.05 m at the centre): along a 1.9 m ring until the goal is in
## a straight line that clears it.
func steer(at: Vector2, goal: Vector2) -> Vector2:
	var d := goal-at
	var t := clampf(-at.dot(d)/maxf(d.length_squared(), 0.0001), 0.0, 1.0)
	if (at+d*t).length() > 1.4: return goal
	var turn := wrapf(goal.angle()-at.angle(), -PI, PI)
	return Vector2.from_angle(at.angle()+clampf(turn, -0.6, 0.6))*1.9

func forest() -> void:
	await create_timer(1.5).timeout
	app().start_run("forest", "relaxed")
	if not await wait_until(in_survival, 90.0):
		check(false, "the forest started")
		return
	var s := run_state()
	check(s.get("map_id") == "forest" and int(s.get("stage_count", 0)) == 3 and (s.get("has_boss") == true), "the forest: 3 stages and a boss")
	var stages_seen := {}
	var boss_night := false
	var deadline := Time.get_ticks_msec()+120000
	while Time.get_ticks_msec() < deadline:
		s = run_state()
		if s.get("status") != "active": break
		stages_seen[int(s.get("stage", 0))] = float(s.get("stage_seconds", 0.0))
		# Keep the camp fire up at night (the spawn is beside it).
		if (s.get("night") == true) and float(s.get("fire_remaining", 0.0)) < 4.0 and int(s.inventory.wood) >= 2: app().intent("fire")
		if (s.get("boss_night") == true) and s.get("boss") is Dictionary:
			boss_night = true
			break
		await create_timer(0.25).timeout
	check(stages_seen.size() == 3, "lived through the forest's stages: %s" % [stages_seen])
	check(boss_night and int(s.get("stage_remaining", 0)) == -1 and int(s.get("stage", 0)) == 3, "the boss night came (status %s)" % [s.get("status")])
	if not boss_night: return
	check(str(s.boss.get("name", "")) == "고목 트렌트" and float(s.boss.get("hp", 0.0)) > 0.0, "run.boss: %s" % [s.boss])
	await create_timer(2.0).timeout
	var boss_node: Node = null
	for enemy in run_state().get("enemies", []):
		if (enemy.get("boss", false) == true): boss_node = app().enemy_nodes.get(enemy.id)
	var scale := -1.0
	if is_instance_valid(boss_node) and boss_node.get("monster"): scale = float(boss_node.monster.scale.x)
	check(is_instance_valid(boss_node) and boss_node.get("monster") and str(boss_node.monster.species) == "brute" and scale > 1.5,
		"the treant is drawn as a brute scaled to 5 m (scale %.2f, art %s)" % [scale, str(boss_node.monster.species) if is_instance_valid(boss_node) and boss_node.get("monster") else "-"])
	# The night holds past the end of the last stage.
	var past := float(run_state().get("elapsed", 0.0))+6.0
	await wait_until(func(): return float(run_state().get("elapsed", 0.0)) >= past or run_state().get("status") != "active", 20.0)
	s = run_state()
	var map := map_node()
	check(s.get("status") == "active" and (s.get("boss_night") == true) and absf(float(s.get("day_progress", 0.0))-0.82) < 0.01,
		"the boss night holds (day_progress %.3f, status %s)" % [float(s.get("day_progress", 0.0)), s.get("status")])
	check(map != null and float(map.get("night")) > 0.9, "the map stays dark on the boss night (night %.2f)" % (float(map.get("night")) if map else -1.0))
	result["forest"] = {"stages":stages_seen, "boss":s.get("boss"), "boss_scale":scale, "elapsed":s.get("elapsed"), "hp":s.get("hp")}
	await capture("forest_boss.png")
	app().leave_run(false)
	await wait_until(in_village, 60.0)
