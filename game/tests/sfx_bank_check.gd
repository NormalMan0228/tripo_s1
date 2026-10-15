extends SceneTree
## Take picker check for scripts/sfx_bank.gd (headless, existing imported sounds only):
##   godot --headless --path game --script res://tests/sfx_bank_check.gd
## Take counts are never pinned: the expected takes of every family come from the files under
## res://assets/sfx (base.wav, base_1.wav, base_2.wav ...), so adding takes keeps this test valid.
## 1. Discovery: every family on disk is found with exactly its takes, bare original first, then
##    _1.._N in number order (hit_flesh_10 after _9); the short form and a ".wav" suffix name the
##    same family; a missing family has no takes and picks null / "". Discovery loads nothing.
## 2. Shuffle bag on real families (a big one, ui/hover and a small one): 300 picks, never the
##    same take twice in a row, every take once per cycle, and with 6+ takes neither of the last
##    two across cycle boundaries. A single-take family (found on disk, else a test-only fake)
##    always picks its one take. The bag core on synthetic sizes 1..12: the same rules.
## 3. Lazy cached loading (only the chosen take loads, one cycle loads each take once, the next
##    cycle reuses the same objects), warm(), clear(), jitter ranges, set_seed() reproducibility,
##    play_on() on AudioStreamPlayer / 2D / 3D and on a player that joins the tree later,
##    refusals (no takes, not a player).
## 4. Exit: freeing a CleanExit node empties the cache (the autoload does that at quit); the run
##    then quits with streams cached again, as the game does, and the log must hold no "ERROR:"
##    line ("resources still in use at exit" included).
## Prints RESULT PASS|FAIL; exit code 1 on failure.
const SfxBank = preload("res://scripts/sfx_bank.gd")
const ROOT := "res://assets/sfx"
const FLESH := "res://assets/sfx/combat/hit_flesh"
const HOVER := "res://assets/sfx/ui/hover"
const STONE := "res://assets/sfx/combat/hit_stone"
const MISSING := "res://assets/sfx/ui/__no_such_family__"
## Only used when no single-take family exists on disk: injected into the bank's path cache.
const FAKE_SINGLE := "res://assets/sfx/__test__/single_take"

var failures := 0
var lines := PackedStringArray()
var disk := {}            # family base -> PackedStringArray of its take paths, in bank order
var single := ""          # a family with exactly one take ("" = use FAKE_SINGLE)
var small := ""           # a family with 2..5 takes (no avoid-last-2 rule)

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, what: String) -> void:
	if ok: return
	failures += 1
	lines.append("FAIL "+what)

func run() -> void:
	var started := Time.get_ticks_msec()
	SfxBank.clear()
	scan_disk()
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

# ------------------------------------------------------------------ disk truth
## Every family under ROOT from the files themselves (.wav, or its .import / .remap entry):
## "x.wav" is the bare take of family x, "x_<n>.wav" take n of family x.
func scan_disk() -> void:
	var numbered := RegEx.create_from_string("^(.*)_(\\d+)$")
	var found := {}   # base -> {"bare": bool, "idx": Array[int]}
	var dirs := [ROOT]
	while not dirs.is_empty():
		var dir: String = dirs.pop_back()
		for sub in DirAccess.get_directories_at(dir): dirs.append(dir+"/"+sub)
		var seen := {}
		for file in DirAccess.get_files_at(dir):
			var fname := file.trim_suffix(".import").trim_suffix(".remap")
			if not fname.ends_with(".wav") or seen.has(fname): continue
			seen[fname] = true
			var stem := dir+"/"+fname.trim_suffix(".wav")
			var m := numbered.search(stem)
			var base := m.get_string(1) if m else stem
			var entry: Dictionary = found.get(base, {"bare": false, "idx": []})
			if m: entry["idx"].append(int(m.get_string(2)))
			else: entry["bare"] = true
			found[base] = entry
	var single_bytes := -1
	var small_n := 99
	for base in found:
		var entry: Dictionary = found[base]
		var list := PackedStringArray()
		if entry["bare"]: list.append(base+".wav")
		var idx: Array = entry["idx"]
		idx.sort()
		for n in idx: list.append("%s_%d.wav" % [base, n])
		disk[base] = list
		# Smallest single-take file (cheap to load), and the smallest 2..5-take family.
		if list.size() == 1:
			var file := FileAccess.open(list[0], FileAccess.READ)
			var bytes := file.get_length() if file else 1 << 40
			if single.is_empty() or bytes < single_bytes or (bytes == single_bytes and base < single):
				single = base
				single_bytes = bytes
		elif list.size() <= 5 and (list.size() < small_n or (list.size() == small_n and base < small)):
			small = base
			small_n = list.size()
	lines.append("families on disk: %d, takes: %d, single-take: %s, small: %s (%d)" % [disk.size(), disk.values().reduce(func(a, l): return a+l.size(), 0), single if not single.is_empty() else "none (test fake)", small, small_n if not small.is_empty() else 0])

func expected(base: String) -> PackedStringArray:
	return disk.get(base, PackedStringArray())

## The single-take family to test: a real one, else FAKE_SINGLE pointing at one real take
## (re-injected after every clear(), which drops the bank's path cache).
func single_key() -> String:
	if not single.is_empty(): return single
	if not SfxBank._paths.has(FAKE_SINGLE): SfxBank._paths[FAKE_SINGLE] = PackedStringArray([expected(FLESH)[0]])
	return FAKE_SINGLE

func single_path() -> String:
	return expected(single)[0] if not single.is_empty() else expected(FLESH)[0]

# ------------------------------------------------------------------ 1. discovery
func check_discovery() -> void:
	var want := expected(FLESH)
	var flesh := SfxBank.paths(FLESH)
	check(want.size() >= 6, "hit_flesh has %d takes on disk (the bag test wants 6+)" % want.size())
	check(flesh == want, "hit_flesh paths %s, files %s" % [flesh, want])
	check(flesh.size() >= 1 and flesh[0] == FLESH+"_1.wav", "hit_flesh does not start at _1: %s" % [flesh])
	var ordered := true
	for i in range(1, flesh.size()):
		if flesh[i] != FLESH+"_%d.wav" % (i+1): ordered = false
	check(ordered, "hit_flesh takes not in number order %s" % [flesh])
	check(SfxBank.count(FLESH) == want.size(), "hit_flesh count %d (files %d)" % [SfxBank.count(FLESH), want.size()])
	check(SfxBank.count("combat/hit_flesh") == want.size(), "short form count %d" % SfxBank.count("combat/hit_flesh"))
	check(SfxBank.count(FLESH+".wav") == want.size(), ".wav suffix count %d" % SfxBank.count(FLESH+".wav"))
	check(SfxBank.count(" /combat/hit_flesh ") == want.size(), "padded short form count %d" % SfxBank.count(" /combat/hit_flesh "))
	var hover := SfxBank.paths(HOVER)
	check(hover == expected(HOVER), "hover paths %s, files %s" % [hover, expected(HOVER)])
	check(hover.size() >= 2 and hover[0] == HOVER+".wav" and hover[1] == HOVER+"_1.wav", "hover is not the bare original then _1..: %s" % [hover])
	check(SfxBank.has("ui/hover"), "ui/hover not found")
	for base in ["creatures/wolf_idle_forest", "combat/harvest_tree"]:
		var full: String = ROOT+"/"+base
		check(SfxBank.count(base) == expected(full).size() and SfxBank.count(base) >= 1, "%s count %d (files %d)" % [base, SfxBank.count(base), expected(full).size()])
	# Every family on disk: the bank sees exactly its files (a gap of 2+ numbers, a zero-padded
	# number or more than MAX_TAKES would hide takes from the game).
	var wrong := PackedStringArray()
	for base in disk:
		var got := SfxBank.paths(base)
		if got != expected(base): wrong.append("%s (bank %d, files %d)" % [base.trim_prefix(ROOT+"/"), got.size(), expected(base).size()])
	check(wrong.is_empty(), "%d families differ from their files: %s" % [wrong.size(), ", ".join(wrong.slice(0, 6))])
	check(SfxBank.count(MISSING) == 0 and not SfxBank.has(MISSING), "missing family has takes")
	check(SfxBank.pick(MISSING) == null, "missing family picked a stream")
	check(SfxBank.pick_path(MISSING) == "", "missing family picked a path")
	check(SfxBank.cached_count() == 0, "discovery loaded %d streams" % SfxBank.cached_count())

# ------------------------------------------------------------------ 2. bags
func check_bag() -> void:
	SfxBank.clear()
	for base in [FLESH, HOVER, small]:
		if base.is_empty(): continue
		var takes := SfxBank.paths(base)
		var n := takes.size()
		if n < 2:
			check(false, "%s has %d takes for the bag test" % [base, n])
			continue
		var picks: Array[String] = []
		for i in 300: picks.append(SfxBank.pick_path(base))
		var repeats := 0
		var near := 0
		for i in range(1, picks.size()):
			if picks[i] == picks[i-1]: repeats += 1
			if n >= 6 and i >= 2 and picks[i] == picks[i-2]: near += 1
		var label: String = base.trim_prefix(ROOT+"/")
		check(repeats == 0, "%s repeated a take back to back %d times" % [label, repeats])
		check(near == 0, "%s (%d takes) replayed one of the last two %d times" % [label, n, near])
		var bad_cycles := 0
		for c in picks.size()/n:
			var cycle := picks.slice(c*n, (c+1)*n)
			for path in takes:
				if cycle.count(path) != 1: bad_cycles += 1
		check(bad_cycles == 0, "%s cycles missing or doubling a take: %d" % [label, bad_cycles])
	var key := single_key()
	var only := single_path()
	check(SfxBank.count(key) == 1, "single-take family %s has %d takes" % [key, SfxBank.count(key)])
	check(SfxBank.pick_path(key) == only and SfxBank.pick_path(key) == only and SfxBank.pick_path(key) == only, "single-take family %s did not keep its one take" % key)
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
	var takes := SfxBank.paths(FLESH)
	var n := takes.size()
	var first := SfxBank.pick(FLESH)
	check(first is AudioStreamWAV, "pick did not return an AudioStreamWAV")
	check(SfxBank.cached_count() == 1, "first pick cached %d streams (want 1)" % SfxBank.cached_count())
	var held := 0
	for path in takes:
		if ResourceLoader.has_cached(path): held += 1
	check(held == 1, "first pick loaded %d hit_flesh takes (want 1)" % held)
	var cycle1: Array = [first]
	for i in n-1: cycle1.append(SfxBank.pick(FLESH))
	check(SfxBank.cached_count() == n, "one cycle cached %d streams (want %d)" % [SfxBank.cached_count(), n])
	var distinct := {}
	for s in cycle1: distinct[s] = true
	check(distinct.size() == n and not distinct.has(null), "one cycle gave %d different takes (want %d)" % [distinct.size(), n])
	var reused := 0
	for i in n:
		if distinct.has(SfxBank.pick(FLESH)): reused += 1
	check(reused == n and SfxBank.cached_count() == n, "second cycle reused %d of %d cached takes, cache now %d" % [reused, n, SfxBank.cached_count()])
	var before := SfxBank.cached_count()
	var key := single_key()
	var again := SfxBank.pick(key)
	check(again != null and again == SfxBank.pick(key) and again == SfxBank.stream(single_path()), "cached stream of the single-take family is not reused")
	check(SfxBank.cached_count()-before <= 1, "single-take picks cached %d streams" % (SfxBank.cached_count()-before))
	check(SfxBank.stream(takes[0]) != null and SfxBank.stream(takes[0]) == SfxBank.stream(takes[0]), "stream() not cached")
	check(SfxBank.stream("") == null and SfxBank.stream(MISSING+".wav") == null, "stream() of a missing path is not null")
	var stones := expected(STONE).size()
	check(stones >= 2 and SfxBank.warm("combat/hit_stone") == stones, "warm did not load hit_stone's %d takes" % stones)
	var stones_held := 0
	for path in expected(STONE):
		if ResourceLoader.has_cached(path): stones_held += 1
	check(stones_held == stones, "after warm %d of %d hit_stone takes are loaded" % [stones_held, stones])
	check(SfxBank.warm(MISSING) == 0, "warm loaded a missing family")
	SfxBank.clear()
	check(SfxBank.cached_count() == 0, "clear() left %d streams" % SfxBank.cached_count())
	check(SfxBank.count(FLESH) == n and SfxBank.pick(FLESH) is AudioStreamWAV and SfxBank.cached_count() == 1, "picking after clear() (count %d, cache %d)" % [SfxBank.count(FLESH), SfxBank.cached_count()])

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
	check(SfxBank.play_on(late, "ui/hover"), "play_on refused a second call before the tree")
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
	check(SfxBank.count(FLESH) == expected(FLESH).size() and SfxBank.pick(FLESH) != null, "picking after clear() (count %d, files %d)" % [SfxBank.count(FLESH), expected(FLESH).size()])
	SfxBank.pick(HOVER)
