extends SceneTree
## Frame times around the first night of an expedition (run elapsed 36-46 s: the night starts at 39 s
## and the first creatures of the day's species spawn), where a species' first model used to be read
## from disk in the spawn frame. The survival map now reads every species' model on a worker thread a
## second after the card is gone (survival_map.gd _prefetch_monsters); --no-prefetch turns that off
## to compare. Uncapped frames (vsync off). Run rendered:
##   $env:TRIPOTHON_TEST_ARGS='--region=forest'; tools/test.ps1 -SkipServerTests -ClientScript survival_night_frames -Capture
## Prints NIGHT_FRAMES {worst ms and when, frames over 33 ms, first spawn time, models cached}.
const Main = preload("res://scripts/main.gd")
const Monster = preload("res://scripts/monster.gd")
var app: Node3D

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var region := "forest"
	var prefetch := true
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--region="): region = argument.trim_prefix("--region=")
		if argument == "--no-prefetch": prefetch = false
	app = Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	await app.authenticate(true, preload("res://tests/qa_server.gd").url(), "night_"+str(Time.get_ticks_msec()), "Night-probe-password-1", "")
	await app.start_run(region, "standard")
	var map: Node = app.world.get_node_or_null("SurvivalMap")
	if map and not prefetch: map.set("monster_wait", 1.0e9)
	var worst := 0.0
	var worst_at := 0.0
	var over := 0
	var frames := 0
	var first_spawn := -1.0
	var cached_at_night := -1
	var last := Time.get_ticks_usec()
	var started := Time.get_ticks_msec()
	while Time.get_ticks_msec()-started < 90000:
		await process_frame
		var now := Time.get_ticks_usec()
		var frame := (now-last)/1000.0
		last = now
		var elapsed := float(app.run.get("elapsed", 0.0))
		if cached_at_night < 0 and elapsed >= 38.0:
			cached_at_night = 0
			for species in Monster.WALK_REF:
				var path := Monster.resolved_path(species, region)
				if path != "" and ResourceLoader.has_cached(path): cached_at_night += 1
		if first_spawn < 0.0 and not app.enemy_nodes.is_empty(): first_spawn = elapsed
		if elapsed >= 36.0 and elapsed <= 46.0:
			frames += 1
			if frame > worst:
				worst = frame
				worst_at = elapsed
			if frame > 33.0: over += 1
		if elapsed > 46.0: break
	print("NIGHT_FRAMES region=%s prefetch=%s worst_ms=%.1f at=%.1f over_33ms=%d frames=%d first_spawn=%.1f models_cached_at_38s=%d" % [region, prefetch, worst, worst_at, over, frames, first_spawn, cached_at_night])
	quit(0 if frames > 0 else 1)
