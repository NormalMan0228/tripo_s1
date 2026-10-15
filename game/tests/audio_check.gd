extends SceneTree
## WorldAudio (world_audio.gd) and its one-shot scheduler (ambience_spots.gd): the baked footstep
## takes and ambience beds, how they are picked, mixed and faded. Needs the imported WAVs
## (tools/sfx/make_world_steps.py, make_world_ambience.py, then the importer).
## With --export=<dir> it also renders listenable WAV previews (beds, scene mixes, footsteps).
const WorldAudio := preload("res://scripts/world_audio.gd")
const Spots := preload("res://scripts/ambience_spots.gd")
const SfxBank := preload("res://scripts/sfx_bank.gd")
const OUT := 22050
## Scene and footstep previews are lifted by this much so they are easy to hear; their
## balance is the in-game one.
const PREVIEW_DB := 12.0
## Takes each surface and gait must have (the generator makes 14).
const MIN_TAKES := 12
var failures := 0
var decoded := {}

func check(ok: bool, what: String) -> void:
	if ok: return
	failures += 1
	print("AUDIO_FAIL ", what)

func _initialize() -> void:
	# The root joins the tree after _initialize; players can only start once it has.
	call_deferred("run")

func run() -> void:
	check(WorldAudio.baked(), "baked footsteps / beds not found (run the importer)")
	var audio: Node = WorldAudio.new()
	root.add_child(audio)
	var started := Time.get_ticks_usec()
	audio.setup()
	var build_ms := (Time.get_ticks_usec() - started) / 1000.0
	print("AUDIO_BUILD ms=%.0f cached_streams=%d synth=%s" % [build_ms, WorldAudio.cache.size(), WorldAudio.synth_built])
	check(build_ms < 1500.0, "first setup took %.0f ms" % build_ms)
	check(not WorldAudio.synth_built, "the synth fallback was built although the takes are baked")
	# A node made later (scene re-entry) is just as quick.
	var again: Node = WorldAudio.new()
	root.add_child(again)
	started = Time.get_ticks_usec()
	again.setup()
	var cached_ms := (Time.get_ticks_usec() - started) / 1000.0
	print("AUDIO_CACHED ms=%.1f" % cached_ms)
	check(cached_ms < 30.0, "cached setup took %.1f ms" % cached_ms)
	check(again.steps.size() == 4 and again.beds.size() == WorldAudio.BED_DB.size(), "second node players")
	again.free()
	check_takes()
	check_footsteps(audio)
	check_remote(audio)
	check_beds(audio)
	check_ambience(audio)
	check_spots(audio)
	check_helpers(audio)
	check_fallback(audio)
	var dir := export_dir()
	if dir != "": export_previews(audio, dir)
	audio.stop_all()
	# Give the audio thread a moment to drop stopped playbacks before the node goes.
	await create_timer(0.5).timeout
	audio.free()
	SfxBank.clear()
	WorldAudio.cache.clear()
	print("AUDIO_DONE failures=", failures)
	quit(1 if failures else 0)

func export_dir() -> String:
	for arg in OS.get_cmdline_user_args() + OS.get_cmdline_args():
		if arg.begins_with("--export="): return arg.trim_prefix("--export=")
	return ""

## Every surface and gait has its takes; they load, do not loop, are short, and running takes are
## shorter and brighter than walking ones (measured on the source PCM).
func check_takes() -> void:
	var total := 0
	for surface in WorldAudio.SURFACES:
		var lengths := {"walk": 0.0, "run": 0.0}
		var bright := {"walk": 0.0, "run": 0.0}
		var loud := {"walk": 0.0, "run": 0.0}
		for gait in ["walk", "run"]:
			var base := "steps/%s_%s" % [surface, gait]
			var list := SfxBank.paths(base)
			check(list.size() >= MIN_TAKES, "%s has %d takes" % [base, list.size()])
			total += list.size()
			for path in list:
				var stream := SfxBank.stream(path) as AudioStreamWAV
				check(stream != null, "cannot load " + path)
				if stream == null: continue
				check(stream.loop_mode == AudioStreamWAV.LOOP_DISABLED, path + " should not loop")
				var length := stream.get_length()
				check(length > 0.08 and length < 0.6, "%s length %.2f s" % [path, length])
				var stats := measure(source(path))
				check(stats.peak > 0.1 and stats.peak <= 0.95, "%s peak %.2f" % [path, stats.peak])
				lengths[gait] += length / list.size()
				# Mean slope over mean level rises with high-frequency content.
				bright[gait] += stats.step / stats.mean / list.size()
				loud[gait] += stats.punch / list.size()
		print("AUDIO_STEP %-7s walk=%.2fs bright=%.3f punch=%.1fdB | run=%.2fs bright=%.3f punch=%.1fdB" % [surface,
			lengths.walk, bright.walk, linear_to_db(maxf(loud.walk, 0.00001)), lengths.run, bright.run, linear_to_db(maxf(loud.run, 0.00001))])
		check(lengths.run < lengths.walk, surface + " running takes are not shorter")
		check(bright.run > bright.walk, surface + " running takes are not brighter")
	var cloth := SfxBank.paths(WorldAudio.CLOTH)
	check(cloth.size() >= 8, "cloth layer has %d takes" % cloth.size())
	print("AUDIO_TAKES steps=%d cloth=%d" % [total, cloth.size()])

func check_footsteps(audio: Node) -> void:
	for surface in WorldAudio.SURFACES:
		for speed in [2.8, 4.5]:
			audio.footstep(surface, speed)
			var gait := "run" if speed > WorldAudio.RUN_SPEED else "walk"
			var player: AudioStreamPlayer = audio.steps[(audio.step_index + audio.steps.size() - 1) % audio.steps.size()]
			var step: Dictionary = audio.last_step
			check(player.stream == step.stream and step.source == "baked", "%s %.1f m/s stream" % [surface, speed])
			check(str(step.path).begins_with("res://assets/sfx/steps/%s_%s_" % [surface, gait]), "%s %.1f m/s took %s" % [surface, speed, step.path])
			check(player.bus == &"SFX" and player.playing, "%s %.1f m/s not playing on SFX" % [surface, speed])
	audio.footstep("lava", 2.8) # unknown surfaces fall back instead of failing
	check(audio.last_step.surface == "grass", "unknown surface did not play as grass")
	var slow := average_step(audio, "stone", 1.2)
	var walk := average_step(audio, "stone", 2.8)
	var run := average_step(audio, "stone", 4.5)
	print("AUDIO_GAIT slow=%.1fdB walk=%.1fdB/%.2fx run=%.1fdB/%.2fx cloth=%.0f%%/%.0f%%" % [slow.db, walk.db, walk.pitch,
		run.db, run.pitch, walk.cloth * 100.0, run.cloth * 100.0])
	check(run.db > walk.db + 3.0 and walk.db > slow.db + 3.0, "speed does not change step loudness enough")
	check(run.pitch > walk.pitch, "running steps are not brighter")
	check(not run.repeats and not walk.repeats and not slow.repeats, "a take repeated back to back")
	check(walk.used >= MIN_TAKES and run.used >= MIN_TAKES, "the bag did not go round every take (%d / %d)" % [walk.used, run.used])
	check(walk.alternates and run.alternates, "left and right feet do not alternate")
	check(walk.cloth > 0.18 and walk.cloth < 0.42, "cloth layer on %.0f %% of walking steps" % (walk.cloth * 100.0))
	# The cloth voice plays with the step it rides on.
	for i in 30: audio.footstep("grass", 2.8)
	check(audio.cloth_voices.any(func(p: AudioStreamPlayer) -> bool: return p.stream != null), "the cloth layer never played")

func average_step(audio: Node, surface: String, speed: float) -> Dictionary:
	var db := 0.0
	var pitch := 0.0
	var repeats := false
	var alternates := true
	var cloth := 0
	var last := ""
	var last_foot := -1
	var used := {}
	for i in 200:
		var step: Dictionary = audio.step_choice(surface, speed)
		db += step.volume_db / 200.0
		pitch += step.pitch / 200.0
		if step.path == last: repeats = true
		if step.foot == last_foot: alternates = false
		if step.cloth: cloth += 1
		last = step.path
		last_foot = step.foot
		used[step.path] = true
	return {"db": db, "pitch": pitch, "repeats": repeats, "alternates": alternates, "cloth": cloth / 200.0, "used": used.size()}

## Other walkers: their own voices and bag, distance falloff and culling, stride().
func check_remote(audio: Node) -> void:
	var hero_index: int = audio.step_index
	var hero_streams: Array = audio.steps.map(func(p: AudioStreamPlayer) -> AudioStream: return p.stream)
	check(audio.remote_step(Vector3(3, 0, 0), "stone", 2.8), "a remote step did not play")
	check(audio.remote_playing() >= 1, "no remote voice is sounding")
	for i in 20: audio.remote_step(Vector3(2, 0, i * 0.2), "gravel", 4.5, -6.0)
	check(audio.remote_playing() <= WorldAudio.REMOTE_VOICES, "remote voices went past the pool")
	check(audio.step_index == hero_index and audio.steps.map(func(p: AudioStreamPlayer) -> AudioStream: return p.stream) == hero_streams,
		"remote steps used the hero's voices")
	var hero := Node3D.new()
	root.add_child(hero)
	audio.focus = hero
	check(not audio.remote_step(Vector3(40, 0, 0), "grass", 2.8), "a remote step 40 m away played")
	check(audio.remote_step(Vector3(5, 0, 0), "grass", 2.8), "a remote step 5 m away did not play")
	check(WorldAudio.distance_db(20.0) < -12.0 and WorldAudio.distance_db(2.0) == 0.0, "distance falloff")
	# stride(): a walker crossing 3 m at 3 m/s takes about four steps; a teleport takes none.
	var before: int = audio.remote_count
	var at := Vector3.ZERO
	for i in 60:
		at.x += 0.05
		audio.stride("peer", at, 1.0 / 60.0, "sand")
	var taken: int = audio.remote_count - before
	check(taken >= 3 and taken <= 5, "stride took %d steps over 3 m" % taken)
	before = audio.remote_count
	audio.stride("peer", at + Vector3(10, 0, 0), 1.0 / 60.0, "sand")
	check(audio.remote_count == before, "a teleport played a step")
	audio.focus = null
	hero.free()

## Every bed is imported as a forward loop of about a minute and its source file wraps without a seam.
func check_beds(audio: Node) -> void:
	var started := Time.get_ticks_usec()
	var ready: int = audio.warm_beds()
	print("AUDIO_BEDS warmed=%d in %.0f ms" % [ready, (Time.get_ticks_usec() - started) / 1000.0])
	check(ready == WorldAudio.BED_DB.size(), "only %d of %d beds loaded" % [ready, WorldAudio.BED_DB.size()])
	for key in WorldAudio.BED_DB:
		var stream := WorldAudio.cache.get("bed/" + key) as AudioStreamWAV
		check(stream != null, "missing bed " + key)
		if stream == null: continue
		check(WorldAudio.bed_level.get(key) == WorldAudio.BED_DB[key], key + " is not the baked bed")
		var length := stream.get_length()
		check(length >= 55.0 and length <= 95.0, "bed %s length %.1f s" % [key, length])
		check(stream.loop_mode == AudioStreamWAV.LOOP_FORWARD, "bed %s is not imported as a forward loop" % key)
		var stats := loop_stats(WorldAudio.BED_DIR + key + ".wav")
		# The jump across the loop point should look like any other step in the signal.
		check(stats.seam <= maxf(stats.local * 1.25, 0.01), "bed %s seam jump %.4f vs nearby steps up to %.4f" % [key, stats.seam, stats.local])
		check(stats.rms > 0.01, "bed %s is silent" % key)
		print("AUDIO_BED %-18s %.1fs %5dHz rms=%.3f seam=%.4f nearby_max=%.4f" % [key, length, stream.mix_rate, stats.rms, stats.seam, stats.local])

func check_ambience(audio: Node) -> void:
	var cases := [
		[{"day": 1.0, "coast": 0.8, "wind": 0.3}, ["birds", "birds_far", "coast", "wind"]],
		[{"day": 0.0}, ["insects", "night", "coast", "wind"]],
		[{"day": 0.45, "coast": 0.0, "wind": 0.6}, ["birds", "birds_far", "insects", "wind"]],
		[{"day": 0.85, "waterfall": 1.0, "wind": 0.2}, ["birds", "birds_far", "waterfall", "wind"]],
		[{"indoor": true, "room": "hearth"}, ["birds", "birds_far", "room", "hearth", "waterfall_muffled", "wind_muffled"]],
		[{"indoor": false, "room": "", "waterfall": 0.0, "wind": 0.0, "day": 1.0, "fade": 0.5}, ["birds", "birds_far"]],
		[{"zone": "frost", "wind": 0.5}, ["frost", "wind", "birds_far"]],
		[{"zone": "quarry", "ember": 1.0, "day": 0.0, "wind": 0.3}, ["quarry", "ember", "wind", "insects", "night"]],
		[{"zone": "", "ember": 0.0, "day": 1.0, "wind": 0.0}, ["birds", "birds_far"]],
	]
	for case in cases:
		audio.set_ambience(case[0])
		var expected: Array = case[1]
		var before: Dictionary = audio.gains.duplicate()
		audio._process(0.1)
		for key in audio.beds:
			# One 0.1 s tick moves each bed toward its target by at most 0.1 / fade, never past it.
			var moved: float = absf(audio.gains[key] - before[key])
			var limit: float = 0.1 / audio.fade + 0.0001
			check(moved <= limit and absf(audio.gains[key] - audio.targets[key]) <= absf(before[key] - audio.targets[key]), "%s jumped from %.2f to %.2f" % [key, before[key], audio.gains[key]])
		for i in 40: audio._process(0.1)
		var audible := []
		for key in audio.beds:
			var player: AudioStreamPlayer = audio.beds[key]
			check(is_equal_approx(audio.gains[key], audio.targets[key]), "%s fade did not settle" % key)
			check(player.bus == &"Ambience", key + " not on Ambience")
			check(player.playing == (audio.gains[key] > 0.0005), "%s playing=%s at gain %.3f" % [key, player.playing, audio.gains[key]])
			if player.playing: audible.append(key)
		print("AUDIO_AMBIENCE %s -> %s" % [JSON.stringify(case[0]), ", ".join(audible)])
		audible.sort()
		expected.sort()
		check(audible == expected, "expected %s, heard %s" % [expected, audible])
		check(not audio.is_processing(), "fades kept processing after settling")
	# Indoors the bright beds drop by more than 20 dB and the sea comes through the walls.
	var inside: Dictionary = WorldAudio.mix_targets({"day": 1.0, "indoor": true, "coast": 1.0})
	check(inside.birds < 0.1 and inside.coast == 0.0 and inside.sea_muffled == 1.0, "indoor muffling")
	# Twins start where the other one is.
	audio.set_ambience({"fade": 0.0, "indoor": false, "coast": 1.0})
	audio._process(0.1)
	audio.set_ambience({"indoor": 0.5})
	audio._process(0.1)
	var twin_gap: float = absf(audio.beds.coast.get_playback_position() - audio.beds.sea_muffled.get_playback_position())
	check(audio.beds.sea_muffled.playing and twin_gap < 0.5, "sea_muffled started %.2f s away from coast" % twin_gap)
	# The fade ramps rather than jumping.
	audio.set_ambience({"fade": 1.5, "indoor": false, "coast": 0.0})
	for i in 30: audio._process(0.1)
	audio.set_ambience({"coast": 1.0})
	audio._process(0.1)
	check(audio.gains.coast > 0.0 and audio.gains.coast < 0.2, "coast jumped to %.2f" % audio.gains.coast)
	# Leaving the tree releases playback; coming back fades the beds in again.
	audio.set_ambience({"fade": 0.0})
	audio._process(0.1)
	root.remove_child(audio)
	check(not audio.beds.coast.playing and audio.beds.coast.stream == null, "beds kept playing out of the tree")
	root.add_child(audio)
	audio._process(0.1)
	check(audio.beds.coast.playing and audio.beds.coast.stream != null, "beds did not come back on re-entry")
	audio.set_ambience({"fade": 1.5})
	audio.stop_all()
	for key in audio.beds: check(not audio.beds[key].playing, key + " survived stop_all")

## The one-shot scheduler: who may call when, no take twice in a row, the dawn rooster's limit.
func check_spots(audio: Node) -> void:
	for kind in Spots.KINDS:
		var count := SfxBank.count(Spots.DIR + kind)
		check(count >= 3, "one-shot %s has %d takes" % [kind, count])
	var day_levels: Dictionary = WorldAudio.mix_targets({"day": 1.0, "coast": 0.9, "wind": 0.4})
	var day: Dictionary = Spots.weights(day_levels, {"day": 1.0, "coast": 0.9, "wind": 0.4})
	check(day.bird > 0.5 and day.gull > 0.2 and day.wave_crash > 0.5 and day.owl == 0.0 and day.cricket == 0.0 and day.rooster == 0.0,
		"daytime coast weights %s" % day)
	var night_p := {"day": 0.0, "coast": 0.5, "wind": 0.2}
	var night: Dictionary = Spots.weights(WorldAudio.mix_targets(night_p), night_p)
	check(night.bird == 0.0 and night.gull == 0.0 and night.cricket > 0.3 and night.owl > 0.2 and night.frog > 0.2, "night weights %s" % night)
	var frost_p := {"day": 1.0, "zone": "frost", "wind": 0.5}
	var frost: Dictionary = Spots.weights(WorldAudio.mix_targets(frost_p), frost_p)
	check(frost.bird == 0.0 and frost.gull == 0.0 and frost.gust > 0.2 and frost.windmill_creak == 0.0, "frost weights %s" % frost)
	var room_p := {"day": 1.0, "indoor": true, "coast": 1.0, "wind": 0.5}
	var room: Dictionary = Spots.weights(WorldAudio.mix_targets(room_p), room_p)
	check(room.values().all(func(w: float) -> bool: return w < 0.05), "one-shots indoors %s" % room)
	var dawn_p := {"day": 0.45}
	check(Spots.weights(WorldAudio.mix_targets(dawn_p), dawn_p, 1.0).rooster > 0.5 and Spots.weights(WorldAudio.mix_targets(dawn_p), dawn_p, 0.0).rooster == 0.0, "rooster only at dawn")
	# Two simulated minutes at the coast by day.
	var spots: Node = audio.spots
	audio.set_ambience({"day": 1.0, "coast": 0.9, "wind": 0.5, "indoor": false, "zone": "", "room": "", "hour": -1.0, "fade": 1.5})
	var previous := {}
	var repeats := 0
	var start: int = spots.fired
	for i in 480:
		spots._process(0.25)
		for kind in spots.last_path:
			if previous.get(kind, "") == spots.last_path[kind] and spots.fired_by[kind] != previous.get(kind + "#", 0): repeats += 1
			previous[kind] = spots.last_path[kind]
			previous[kind + "#"] = spots.fired_by[kind]
		# Playback does not advance here: free the voices as if the calls had ended.
		for voice in spots.voices_flat + spots.voices3d: voice.stop()
	print("AUDIO_SPOTS 120 s by day at the coast: %d calls %s" % [spots.fired - start, spots.fired_by])
	check(spots.fired - start >= 15, "only %d one-shots in two minutes" % (spots.fired - start))
	for kind in spots.fired_by:
		check(kind in ["bird", "gull", "wave_crash", "wave_slap", "gust", "windmill_creak", "distant_bell"], "%s called by day" % kind)
	check(repeats == 0, "a one-shot take repeated back to back %d times" % repeats)
	check(spots.voices_flat.all(func(p: AudioStreamPlayer) -> bool: return p.bus == &"Ambience"), "one-shots not on Ambience")
	# Dawn: the rooster crows, but not more than its limit.
	audio.set_ambience({"day": 0.45, "hour": 6.0, "coast": 0.3})
	for i in 1600:
		spots._process(0.25)
		for voice in spots.voices_flat + spots.voices3d: voice.stop()
	var crows: int = spots.fired_by.get("rooster", 0)
	check(crows >= 1 and crows <= int(Spots.KINDS.rooster.limit), "rooster crowed %d times in one dawn" % crows)
	audio.set_ambience({"day": 1.0, "hour": -1.0})
	audio.stop_all()
	check(not spots.is_processing(), "one-shots kept going after stop_all")

func check_helpers(audio: Node) -> void:
	check(WorldAudio.room_surface("checker") == "tile" and WorldAudio.room_surface("flags") == "stone"
		and WorldAudio.room_surface("wide_planks") == "planks" and WorldAudio.room_surface("mystery") == "planks", "floor surfaces")
	var rug := [{"kind": "rug", "center": Vector3(1, 0, 1), "yaw": 0.0, "half": Vector2(1.5, 1.0), "solid": false}]
	check(WorldAudio.room_surface("planks", rug, Vector3(2, 0, 1.5)) == "rug" and WorldAudio.room_surface("planks", rug, Vector3(3, 0, 1)) == "planks", "rug surface")
	check(WorldAudio.room_ambience("cafe").room == "cafe" and WorldAudio.room_ambience("lighthouse").coast == 1.0
		and WorldAudio.room_ambience("workshop").room == "" and WorldAudio.room_ambience("home").indoor == true, "room ambience")
	var index: int = audio.step_index
	audio.land(7.0, "dirt")
	check(audio.step_index != index and audio.steps[index].playing, "landing did not play")
	audio.splash(1.0)
	check(audio.steps[(audio.step_index + 3) % 4].playing, "splash did not play")

## Without baked takes every surface still steps on the synthesized fallback.
func check_fallback(audio: Node) -> void:
	audio.use_baked = false
	var started := Time.get_ticks_usec()
	for surface in WorldAudio.SURFACES:
		var step: Dictionary = audio.step_choice(surface, 2.8)
		check(step.source == "synth" and step.stream is AudioStreamWAV, surface + " has no synthesized fallback")
	print("AUDIO_FALLBACK synth built in %.0f ms" % ((Time.get_ticks_usec() - started) / 1000.0))
	audio.use_baked = true

# --- Sample access -----------------------------------------------------------------------------

## The PCM of a source WAV (canonical 44-byte header, mono 16-bit), cached; empty when unreadable.
func source(path: String) -> Dictionary:
	if decoded.has(path): return decoded[path]
	var raw := FileAccess.get_file_as_bytes(path)
	var out := {"rate": OUT, "data": PackedFloat32Array()}
	if raw.size() > 44 and raw.slice(0, 4).get_string_from_ascii() == "RIFF":
		out.rate = raw.decode_u32(24)
		var data := PackedFloat32Array()
		data.resize((raw.size() - 44) / 2)
		for i in data.size(): data[i] = raw.decode_s16(44 + i * 2) / 32768.0
		out.data = data
	decoded[path] = out
	return out

## Seam and level of a long source loop without decoding all of it: the 10 ms either side of the
## wrap, and the RMS of every 37th sample.
func loop_stats(path: String) -> Dictionary:
	var raw := FileAccess.get_file_as_bytes(path)
	if raw.size() < 44 + 4000: return {"rms": 0.0, "seam": 1.0, "local": 0.0}
	var rate := raw.decode_u32(24)
	var n := (raw.size() - 44) / 2
	var at := func(i: int) -> float: return raw.decode_s16(44 + posmod(i, n) * 2) / 32768.0
	var near := 0.0
	for i in range(1, rate / 100):
		near = maxf(near, maxf(absf(at.call(i) - at.call(i - 1)), absf(at.call(n - i) - at.call(n - i - 1))))
	var energy := 0.0
	var count := 0
	for i in range(0, n, 37):
		var v: float = at.call(i)
		energy += v * v
		count += 1
	return {"rms": sqrt(energy / maxi(count, 1)), "seam": absf(at.call(0) - at.call(n - 1)), "local": near}

## Samples of a stream: its source file when it was imported, its PCM data when synthesized.
func samples_of(stream: AudioStream) -> Dictionary:
	if stream.resource_path.ends_with(".wav"): return source(stream.resource_path)
	var wav := stream as AudioStreamWAV
	var data := wav.data
	var out := PackedFloat32Array()
	out.resize(data.size() / 2)
	for i in out.size(): out[i] = data.decode_s16(i * 2) / 32768.0
	return {"rate": wav.mix_rate, "data": out}

func measure(pcm: Dictionary) -> Dictionary:
	var s: PackedFloat32Array = pcm.get("data", PackedFloat32Array())
	if s.size() < 16: return {"peak": 0.0, "rms": 0.0, "step": 0.0, "mean": 1.0, "punch": 0.0, "seam": 1.0, "local": 0.0}
	var peak := 0.0
	var energy := 0.0
	var step := 0.0
	var level := 0.0
	for i in s.size():
		peak = maxf(peak, absf(s[i]))
		energy += s[i] * s[i]
		level += absf(s[i])
		if i > 0: step += absf(s[i] - s[i - 1])
	# Loudest 50 ms RMS: how hard a short sound lands.
	var window: int = int(pcm.rate) / 20
	var punch := 0.0
	var run := 0.0
	for i in s.size():
		run += s[i] * s[i]
		if i >= window: run -= s[i - window] * s[i - window]
		punch = maxf(punch, run)
	# Largest step within 10 ms either side of the loop point.
	var near := 0.0
	var span := mini(int(pcm.rate) / 100, s.size() / 4)
	for i in range(1, span):
		near = maxf(near, maxf(absf(s[i] - s[i - 1]), absf(s[s.size() - i] - s[s.size() - i - 1])))
	return {"peak": peak, "rms": sqrt(energy / s.size()), "step": step / maxf(s.size() - 1, 1),
		"mean": maxf(level / s.size(), 0.000001), "punch": sqrt(maxf(punch, 0.0) / window),
		"seam": absf(s[0] - s[s.size() - 1]), "local": near}

# --- Previews ----------------------------------------------------------------------------------

func export_previews(audio: Node, dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	var written := []
	# Each bed alone at full scale, starting 3 s before its loop point so the seam is mid-file.
	for key in WorldAudio.BED_DB:
		var stream: AudioStream = WorldAudio.cache.get("bed/" + key)
		if stream == null: continue
		written.append(save(dir, "bed_%s.wav" % key, render(stream, 6.0, stream.get_length() - 3.0)))
	# Scenes at their in-game balance (Master at 0 dB), lifted for listening.
	var lift := db_to_linear(PREVIEW_DB)
	var scenes := {
		"day_coast": {"day": 1.0, "coast": 0.8, "wind": 0.3},
		"night_coast": {"day": 0.0, "coast": 0.8, "wind": 0.2},
		"dusk_meadow": {"day": 0.45, "wind": 0.5},
		"waterfall": {"day": 0.85, "waterfall": 1.0, "wind": 0.2},
		"forest_day": {"day": 1.0, "zone": "forest", "wind": 0.3},
		"frost_day": {"day": 1.0, "zone": "frost", "wind": 0.5},
		"quarry_ember": {"day": 1.0, "zone": "quarry", "ember": 1.0, "wind": 0.3},
		"room_hearth": WorldAudio.room_ambience("home"),
		"room_cafe": WorldAudio.room_ambience("cafe"),
		"room_mill": WorldAudio.room_ambience("windmill"),
		"room_lighthouse": WorldAudio.room_ambience("lighthouse"),
	}
	for scene in scenes:
		written.append(save(dir, "scene_%s.wav" % scene, ambience(audio, scenes[scene], 12.0), lift))
	# Every surface: six walking steps, then six running steps.
	var walk := PackedFloat32Array()
	walk.resize(int(60.0 * OUT))
	var run := walk.duplicate()
	var t := 0.3
	for surface in WorldAudio.SURFACES:
		t = add_steps(audio, walk, surface, 2.8, 0.47, 6, t) + 0.6
	var t_run := 0.3
	for surface in WorldAudio.SURFACES:
		t_run = add_steps(audio, run, surface, 4.5, 0.32, 6, t_run) + 0.6
	walk.resize(int(t * OUT))
	run.resize(int(t_run * OUT))
	written.append(save(dir, "footsteps_walk.wav", walk, lift))
	written.append(save(dir, "footsteps_run.wav", run, lift))
	# A stroll down the beach into the shallows, then a jog back onto the pier.
	var beach := ambience(audio, {"day": 1.0, "coast": 0.9, "wind": 0.3, "indoor": false, "zone": ""}, 10.0)
	var at := add_steps(audio, beach, "sand", 2.8, 0.47, 8, 0.4)
	at = add_steps(audio, beach, "shallow", 2.4, 0.52, 5, at)
	add_steps(audio, beach, "wood", 4.5, 0.32, 7, at + 0.2)
	written.append(save(dir, "scene_beach_walk.wav", beach, lift))
	print("AUDIO_EXPORT %s (scenes and footsteps +%.0f dB) %s" % [dir, PREVIEW_DB, ", ".join(written)])

## Beds at their in-game levels plus a few one-shots at their in-game levels (flat, no placement).
func ambience(audio: Node, params: Dictionary, seconds: float) -> PackedFloat32Array:
	var gains: Dictionary = WorldAudio.mix_targets(params)
	var mix := PackedFloat32Array()
	mix.resize(int(seconds * OUT))
	for key in gains:
		if gains[key] <= 0.0005: continue
		var stream: AudioStream = WorldAudio.cache.get("bed/" + key)
		if stream == null: continue
		var level: float = gains[key] * db_to_linear(audio.ambience_db + float(WorldAudio.bed_level.get(key, WorldAudio.BED_DB[key])))
		add(mix, render(stream, seconds, randf() * stream.get_length()), 0, level)
	var weights: Dictionary = Spots.weights(gains, params)
	for kind in weights:
		var w: float = weights[kind]
		var spec: Dictionary = Spots.KINDS[kind]
		var gap: Array = spec.gap
		var t := randf_range(0.2, 2.0)
		while w > 0.05 and t < seconds - 0.5:
			var stream := SfxBank.stream(SfxBank.pick_path(Spots.DIR + kind))
			if stream != null:
				var db: float = audio.ambience_db + float(spec.db) - (3.0 if not (spec.dist as Array).is_empty() else 0.0)
				add(mix, render(stream, 6.0), int(t * OUT), db_to_linear(db))
			t += randf_range(float(gap[0]), float(gap[1])) / clampf(w, 0.25, 1.0)
	return mix

func add_steps(audio: Node, mix: PackedFloat32Array, surface: String, speed: float, interval: float, count: int, t: float) -> float:
	for i in count:
		var step: Dictionary = audio.step_choice(surface, speed)
		add(mix, render(step.stream, 0.6, 0.0, step.pitch), int(t * OUT), db_to_linear(step.volume_db))
		t += interval * randf_range(0.96, 1.04)
	return t

func add(mix: PackedFloat32Array, part: PackedFloat32Array, at: int, level: float) -> void:
	for i in mini(part.size(), mix.size() - at): mix[at + i] += part[i] * level

## Resamples a stream to OUT the way a player would (pitch, loop), with linear interpolation.
func render(stream: AudioStream, seconds: float, offset := 0.0, pitch := 1.0) -> PackedFloat32Array:
	var pcm := samples_of(stream)
	var src: PackedFloat32Array = pcm.data
	var frames := src.size()
	var out := PackedFloat32Array()
	out.resize(int(seconds * OUT))
	if frames < 2: return out
	var wav := stream as AudioStreamWAV
	var looped := wav != null and wav.loop_mode == AudioStreamWAV.LOOP_FORWARD
	var advance: float = float(pcm.rate) * pitch / OUT
	var pos: float = offset * float(pcm.rate)
	for i in out.size():
		if looped: pos = fmod(pos, frames)
		elif pos >= frames - 1: break
		var k := int(pos)
		var f := pos - k
		out[i] = src[k] * (1.0 - f) + src[(k + 1) % frames] * f
		pos += advance
	return out

func save(dir: String, file: String, buf: PackedFloat32Array, gain := 1.0) -> String:
	var data := PackedByteArray()
	data.resize(buf.size() * 2)
	var clipped := 0
	for i in buf.size():
		var v := buf[i] * gain
		if absf(v) > 1.0: clipped += 1
		data.encode_s16(i * 2, int(clampf(v, -1.0, 1.0) * 32767.0))
	check(clipped == 0, "%s clipped %d samples" % [file, clipped])
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = OUT
	wav.data = data
	var error := wav.save_to_wav(dir.path_join(file))
	check(error == OK, "could not write %s (%s)" % [file, error_string(error)])
	return file
