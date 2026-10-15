extends SceneTree
## Take picker check for scripts/sfx_bank.gd (headless, existing imported sounds only):
##   godot --headless --path game --script res://tests/sfx_bank_check.gd
## 1. Discovery: combat/hit_flesh has _1.._3, ui/hover is the bare file only, the short form and a
##    ".wav" suffix name the same family, a missing family has no takes and picks null / "".
## 2. Shuffle bag on a real family: 300 picks, never the same take twice in a row, every take
##    once per cycle. The bag core on synthetic sizes 1..12: the same, plus with 6+ takes neither
##    of the last two across cycle boundaries.
## 3. Lazy cached loading (only the chosen take loads, the same object comes back), jitter
##    ranges, set_seed() reproducibility, play_on() on AudioStreamPlayer / 2D / 3D and on a
##    player that joins the tree later, refusals (no takes, not a player).
## 4. Exit: freeing a CleanExit node empties the cache (the autoload does that at quit); the run
##    then quits with streams cached again, as the game does, and the log must hold no "ERROR:"
##    line ("resources still in use at exit" included).
## Prints RESULT PASS|FAIL; exit code 1 on failure.
const SfxBank = preload("res://scripts/sfx_bank.gd")
const FLESH := "res://assets/sfx/combat/hit_flesh"
const HOVER := "res://assets/sfx/ui/hover"
const MISSING := "res://assets/sfx/ui/__no_such_family__"

var failures := 0
var lines := PackedStringArray()

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, what: String) -> void:
	if ok: return
	failures += 1
	lines.append("FAIL "+what)

func run() -> void:
	var started := Time.get_ticks_msec()
	SfxBank.clear()
	check_discovery()
	check_bag()
	check_bag_core()
	check_loading()
	check_jitter()
	await check_play()
	check_exit_hook()
	lines.append("cached streams at quit: %d (CleanExit autoload %s)" % [SfxBank.cached_count(), "present" if root.get_node_or_null("CleanExit") else "absent"])
	lines.append("RESULT %s (%d problems, %.1f s)" % ["PASS" if failures == 0 else "FAIL", failures, (Time.get_ticks_msec()-started)*0.001])
	print("\n".join(lines))
	quit(1 if failures > 0 else 0)

# ------------------------------------------------------------------ 1. discovery
func check_discovery() -> void:
	var flesh := SfxBank.paths(FLESH)
	check(flesh == PackedStringArray([FLESH+"_1.wav", FLESH+"_2.wav", FLESH+"_3.wav"]), "hit_flesh paths %s" % [flesh])
	check(SfxBank.count(FLESH) == 3, "hit_flesh count %d" % SfxBank.count(FLESH))
	check(SfxBank.count("combat/hit_flesh") == 3, "short form count %d" % SfxBank.count("combat/hit_flesh"))
	check(SfxBank.count(FLESH+".wav") == 3, ".wav suffix count %d" % SfxBank.count(FLESH+".wav"))
	var hover := SfxBank.paths(HOVER)
	check(hover == PackedStringArray([HOVER+".wav"]), "hover paths %s" % [hover])
	check(SfxBank.has("ui/hover"), "ui/hover not found")
	check(SfxBank.count("creatures/wolf_idle_forest") == 2, "wolf idle count %d" % SfxBank.count("creatures/wolf_idle_forest"))
	check(SfxBank.count("combat/harvest_tree") == 1, "harvest_tree count %d" % SfxBank.count("combat/harvest_tree"))
	check(SfxBank.count(MISSING) == 0 and not SfxBank.has(MISSING), "missing family has takes")
	check(SfxBank.pick(MISSING) == null, "missing family picked a stream")
	check(SfxBank.pick_path(MISSING) == "", "missing family picked a path")
	check(SfxBank.cached_count() == 0, "discovery loaded %d streams" % SfxBank.cached_count())

# ------------------------------------------------------------------ 2. bags
func check_bag() -> void:
	SfxBank.clear()
	var takes := SfxBank.paths(FLESH)
	var picks: Array[String] = []
	for i in 300: picks.append(SfxBank.pick_path(FLESH))
	var repeats := 0
	for i in range(1, picks.size()):
		if picks[i] == picks[i-1]: repeats += 1
	check(repeats == 0, "hit_flesh repeated a take back to back %d times" % repeats)
	var bad_cycles := 0
	for c in picks.size()/takes.size():
		var cycle := picks.slice(c*takes.size(), (c+1)*takes.size())
		for path in takes:
			if cycle.count(path) != 1: bad_cycles += 1
	check(bad_cycles == 0, "hit_flesh cycles missing or doubling a take: %d" % bad_cycles)
	check(SfxBank.pick_path(HOVER) == HOVER+".wav" and SfxBank.pick_path(HOVER) == HOVER+".wav", "single-take family")
	check(SfxBank.cached_count() == 0, "pick_path loaded streams")

func check_bag_core() -> void:
	SfxBank.set_seed(20261015)
	for size in [1, 2, 3, 5, 6, 7, 12]:
		var key := "test/size_%d" % size
		var seq: Array[int] = []
		for i in 300: seq.append(SfxBank.bag_index(key, size))
		var problems := 0
		for i in seq.size():
			if seq[i] < 0 or seq[i] >= size: problems += 1
			if size >= 2 and i >= 1 and seq[i] == seq[i-1]: problems += 1
			if size >= 6 and i >= 2 and seq[i] == seq[i-2]: problems += 1
		for c in seq.size()/size:
			var cycle := seq.slice(c*size, (c+1)*size)
			for k in size:
				if cycle.count(k) != 1: problems += 1
		check(problems == 0, "bag of %d: %d rule breaks in 300 picks" % [size, problems])
	# a family whose size changes (takes added, cache cleared) restarts its bag cleanly
	for i in 5: SfxBank.bag_index("test/grow", 3)
	var grown := []
	for i in 8: grown.append(SfxBank.bag_index("test/grow", 8))
	grown.sort()
	check(grown == [0, 1, 2, 3, 4, 5, 6, 7], "bag after a size change %s" % [grown])

# ------------------------------------------------------------------ 3. loading, jitter, playback
func check_loading() -> void:
	SfxBank.clear()
	var first := SfxBank.pick(FLESH)
	check(first is AudioStreamWAV, "pick did not return an AudioStreamWAV")
	check(SfxBank.cached_count() == 1, "first pick cached %d streams (want 1)" % SfxBank.cached_count())
	var held := 0
	for path in SfxBank.paths(FLESH):
		if ResourceLoader.has_cached(path): held += 1
	check(held == 1, "first pick loaded %d hit_flesh takes (want 1)" % held)
	SfxBank.pick(FLESH)
	SfxBank.pick(FLESH)
	check(SfxBank.cached_count() == 3, "one cycle cached %d streams (want 3)" % SfxBank.cached_count())
	var again := SfxBank.pick(HOVER)
	check(again != null and again == SfxBank.pick(HOVER), "cached stream is not reused")
	check(SfxBank.stream(SfxBank.paths(FLESH)[0]) == SfxBank.stream(SfxBank.paths(FLESH)[0]), "stream() not cached")
	check(SfxBank.warm("combat/hit_stone") == 3, "warm did not load hit_stone's 3 takes")

func check_jitter() -> void:
	SfxBank.set_seed(7)
	var lo := 9.0
	var hi := -9.0
	var dlo := 99.0
	var dhi := -99.0
	for i in 2000:
		var p := SfxBank.pitch(0.04)
		var d := SfxBank.db(1.5)
		lo = minf(lo, p)
		hi = maxf(hi, p)
		dlo = minf(dlo, d)
		dhi = maxf(dhi, d)
	check(lo >= 0.96 and hi <= 1.04 and hi-lo > 0.07, "pitch jitter range %.3f..%.3f" % [lo, hi])
	check(dlo >= -1.5 and dhi <= 1.5 and dhi-dlo > 2.8, "db jitter range %.2f..%.2f" % [dlo, dhi])
	check(SfxBank.pitch(0.0) == 1.0 and SfxBank.db(0.0) == 0.0, "zero spread is not exact")
	var runs := []
	for attempt in 2:
		SfxBank.set_seed(99)
		SfxBank.clear()
		var seq := []
		for i in 12: seq.append(SfxBank.pick_path(FLESH))
		seq.append(SfxBank.pitch())
		runs.append(seq)
	check(runs[0] == runs[1], "set_seed did not reproduce the picks and jitter")
	SfxBank.set_seed(randi())

func check_play() -> void:
	var flat := AudioStreamPlayer.new()
	var flat2d := AudioStreamPlayer2D.new()
	var spatial := AudioStreamPlayer3D.new()
	var late := AudioStreamPlayer.new()
	var plain := Node.new()
	for node in [flat, flat2d, spatial, plain]: root.add_child(node)
	await process_frame
	var previous: AudioStream = null
	for i in 6:
		check(SfxBank.play_on(flat, "combat/hit_flesh", -6.0, 1.0, 0.05, 1.0), "play_on(AudioStreamPlayer) refused")
		check(flat.stream != null and flat.stream != previous, "play_on repeated the previous take")
		previous = flat.stream
		check(flat.pitch_scale >= 0.95 and flat.pitch_scale <= 1.05, "pitch_scale %.3f" % flat.pitch_scale)
		check(flat.volume_db >= -7.0 and flat.volume_db <= -5.0, "volume_db %.2f" % flat.volume_db)
	check(flat.playing, "AudioStreamPlayer is not playing")
	check(SfxBank.play_on(flat2d, "ui/hover", -4.0, 1.2, 0.0, 0.0), "play_on(2D) refused")
	check(is_equal_approx(flat2d.pitch_scale, 1.2) and is_equal_approx(flat2d.volume_db, -4.0), "zero-spread play_on changed pitch/volume")
	check(SfxBank.play_on(spatial, FLESH), "play_on(3D) refused")
	check(not SfxBank.play_on(flat, MISSING), "play_on played a missing family")
	check(not SfxBank.play_on(plain, FLESH), "play_on accepted a plain Node")
	check(not SfxBank.play_on(null, FLESH), "play_on accepted null")
	check(SfxBank.play_on(late, "ui/hover"), "play_on refused a player outside the tree")
	root.add_child(late)
	await process_frame
	check(late.playing, "the late player did not start on entering the tree")
	await create_timer(0.3).timeout
	for node in [flat, flat2d, spatial, late]: node.stop()
	for node in [flat, flat2d, spatial, late, plain]: node.queue_free()
	await process_frame
	# Give the audio thread a moment to drop the stopped playbacks (as audio_check does).
	await create_timer(0.3).timeout

# ------------------------------------------------------------------ 4. exit
func check_exit_hook() -> void:
	SfxBank.pick(HOVER)
	check(SfxBank.cached_count() > 0, "nothing cached before the exit hook")
	var hygiene: Node = load("res://scripts/clean_exit.gd").new()
	hygiene.free()  # NOTIFICATION_PREDELETE: the path the CleanExit autoload takes at quit
	check(SfxBank.cached_count() == 0, "CleanExit left %d streams in the take cache" % SfxBank.cached_count())
	check(SfxBank.count(FLESH) == 3 and SfxBank.pick(FLESH) != null, "picking after clear()")
	SfxBank.pick(HOVER)
