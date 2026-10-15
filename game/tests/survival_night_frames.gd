extends SceneTree
## Frame times of an expedition in one of two windows, uncapped (vsync off):
##   --window=night (default): run elapsed 36-46 s, around the first night (it starts at 39 s and the
##     first creatures of the day's species spawn), where a species' first model used to be read from
##     disk in the spawn frame;
##   --window=entry: the first 7 s the world shows through the lifting veil (the card's fade, then
##     play), where the models' GPU uploads landed when they were read a second after the card.
## The survival map reads every species' model under the card (survival_map.gd prefetch_monsters);
## --no-prefetch turns that off to compare. Run rendered:
##   $env:TRIPOTHON_TEST_ARGS='--region=forest --window=entry'; tools/test.ps1 -SkipServerTests -ClientScript survival_night_frames -Capture
## Prints NIGHT_FRAMES {window, worst ms and when, frames over 33 ms, first spawn time, models cached}.
## The entry window fails when more than one frame is over --max-ms (default 33; 0 turns that off) or
## one is over 50 ms, and (prefetch on) when a creature model was not in before the card lifted.
const Main = preload("res://scripts/main.gd")
const Monster = preload("res://scripts/monster.gd")
const SurvivalMap = preload("res://maps/survival/survival_map.gd")
const Transition = preload("res://scripts/transition.gd")
const ENTRY_S := 7.0
var app: Node3D

func _initialize() -> void:
	call_deferred("run")

func cached(region: String) -> int:
	var count := 0
	for species in Monster.WALK_REF:
		var path := Monster.resolved_path(species, region)
		if path != "" and ResourceLoader.has_cached(path): count += 1
	return count

func run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var region := "forest"
	var prefetch := true
	var window := "night"
	var max_ms := 33.0
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--region="): region = argument.trim_prefix("--region=")
		if argument == "--no-prefetch": prefetch = false
		if argument.begins_with("--window="): window = argument.trim_prefix("--window=")
		if argument.begins_with("--max-ms="): max_ms = float(argument.trim_prefix("--max-ms="))
	SurvivalMap.prefetch_monsters = prefetch
	app = Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	await app.authenticate(true, preload("res://tests/qa_server.gd").url(), "night_"+str(Time.get_ticks_msec()), "Night-probe-password-1", "")
	if window == "entry":
		await entry_window(region, prefetch, max_ms)
		return
	await app.start_run(region, "standard")
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
		if cached_at_night < 0 and elapsed >= 38.0: cached_at_night = cached(region)
		if first_spawn < 0.0 and not app.enemy_nodes.is_empty(): first_spawn = elapsed
		if elapsed >= 36.0 and elapsed <= 46.0:
			frames += 1
			if frame > worst:
				worst = frame
				worst_at = elapsed
			if frame > 33.0: over += 1
		if elapsed > 46.0: break
	print("NIGHT_FRAMES window=night region=%s prefetch=%s worst_ms=%.1f at=%.1f over_33ms=%d frames=%d first_spawn=%.1f models_cached_at_38s=%d" % [region, prefetch, worst, worst_at, over, frames, first_spawn, cached_at_night])
	quit(0 if frames > 0 else 1)

## Frames that began with the world showing through the veil (alpha below 1), for ENTRY_S seconds
## from the first one; `at` is seconds since then.
func entry_window(region: String, prefetch: bool, max_ms: float) -> void:
	await app.start_run(region, "standard")
	var cached_at_lift := cached(region)
	var veil: CanvasLayer = Transition.instance
	var worst := 0.0
	var worst_at := 0.0
	var over := 0
	var over_max := 0
	var frames := 0
	var longest: Array = []
	var showing := false
	var from := 0
	var last := Time.get_ticks_usec()
	var deadline := Time.get_ticks_msec()+20000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		var now := Time.get_ticks_usec()
		var frame := (now-last)/1000.0
		last = now
		if showing:
			frames += 1
			var at := (now-from)/1000000.0
			if frame > worst:
				worst = frame
				worst_at = at
			if frame > 33.0: over += 1
			if max_ms > 0.0 and frame > max_ms:
				over_max += 1
				longest.append("%.1f@%.2f" % [frame, at])
			if at >= ENTRY_S: break
		elif not is_instance_valid(veil) or veil.veil.modulate.a < 0.999:
			showing = true
			from = now
	var species := 0
	for kind in Monster.WALK_REF: if Monster.resolved_path(kind, region) != "": species += 1
	print("NIGHT_FRAMES window=entry region=%s prefetch=%s worst_ms=%.1f at=%.2f over_33ms=%d frames=%d models_cached_at_lift=%d/%d models_cached_after=%d over_max=%s" % [region, prefetch, worst, worst_at, over, frames, cached_at_lift, species, cached(region), str(longest)])
	# One stray frame over max_ms is let through (a busy machine); the models' own reads made two.
	var smooth := frames > 0 and over_max <= 1 and worst <= maxf(max_ms, 50.0)
	print(("PASS" if smooth else "FAIL")+" entry window: at most one frame over %.0f ms and none over %.0f ms in the first %.0f s the world shows" % [max_ms, maxf(max_ms, 50.0), ENTRY_S])
	var ready := not prefetch or cached_at_lift == species
	print(("PASS" if ready else "FAIL")+" entry window: every creature model (%d/%d) was in before the card lifted" % [cached_at_lift, species])
	quit(0 if smooth and ready else 1)
