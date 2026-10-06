extends SceneTree
## Builds the synthesized world audio, checks every stream and the mixing rules.
## With --export=<dir> it also renders listenable WAV previews (beds, scene mixes, footsteps).
const WorldAudio := preload("res://scripts/world_audio.gd")
const OUT := 22050
## Scene and footstep previews are lifted by this much so they are easy to hear; their
## balance is the in-game one.
const PREVIEW_DB := 12.0
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
	var audio: Node = WorldAudio.new()
	root.add_child(audio)
	var started := Time.get_ticks_usec()
	audio.setup()
	var build_ms := (Time.get_ticks_usec() - started) / 1000.0
	print("AUDIO_BUILD ms=%.0f streams=%d" % [build_ms, WorldAudio.cache.size()])
	check(build_ms < 1500.0, "first setup took %.0f ms" % build_ms)
	# A node made later (scene re-entry) reuses the static cache.
	var again: Node = WorldAudio.new()
	root.add_child(again)
	started = Time.get_ticks_usec()
	again.setup()
	var cached_ms := (Time.get_ticks_usec() - started) / 1000.0
	print("AUDIO_CACHED ms=%.1f" % cached_ms)
	check(cached_ms < 30.0, "cached setup took %.1f ms" % cached_ms)
	check(again.beds["coast"].stream == audio.beds["coast"].stream, "second node did not share streams")
	again.free()
	check_streams()
	check_footsteps(audio)
	check_ambience(audio)
	var dir := export_dir()
	if dir != "": export_previews(audio, dir)
	audio.stop_all()
	# Give the audio thread a moment to drop stopped playbacks before the node goes.
	await create_timer(0.5).timeout
	audio.free()
	print("AUDIO_DONE failures=", failures)
	quit(1 if failures else 0)

func export_dir() -> String:
	for arg in OS.get_cmdline_user_args() + OS.get_cmdline_args():
		if arg.begins_with("--export="): return arg.trim_prefix("--export=")
	return ""

func check_streams() -> void:
	var cache: Dictionary = WorldAudio.cache
	for surface in WorldAudio.SURFACES:
		var lengths := {"walk": 0.0, "run": 0.0}
		var bright := {"walk": 0.0, "run": 0.0}
		var loud := {"walk": 0.0, "run": 0.0}
		for gait in ["walk", "run"]:
			for take in WorldAudio.VARIATIONS:
				var key := "step/%s/%s/%d" % [surface, gait, take]
				var stream: AudioStreamWAV = cache.get(key)
				check(stream != null, "missing " + key)
				if stream == null: continue
				var length := stream.get_length()
				lengths[gait] += length / WorldAudio.VARIATIONS
				check(length > 0.08 and length < 0.6, "%s length %.2f s" % [key, length])
				check(stream.loop_mode == AudioStreamWAV.LOOP_DISABLED, key + " should not loop")
				var stats := measure(stream)
				check(stats.peak > 0.3 and stats.peak <= 0.93, "%s peak %.2f" % [key, stats.peak])
				# Mean slope over mean level rises with high-frequency content.
				bright[gait] += stats.step / stats.mean / WorldAudio.VARIATIONS
				loud[gait] += stats.punch / WorldAudio.VARIATIONS
		print("AUDIO_STEP %-7s walk=%.2fs bright=%.3f punch=%.1fdB | run=%.2fs bright=%.3f punch=%.1fdB" % [surface,
			lengths.walk, bright.walk, linear_to_db(loud.walk), lengths.run, bright.run, linear_to_db(loud.run)])
		check(lengths.run < lengths.walk, surface + " running takes are not shorter")
		check(bright.run > bright.walk, surface + " running takes are not brighter")
	for key in WorldAudio.BED_DB:
		var stream: AudioStreamWAV = cache.get("bed/" + key)
		check(stream != null, "missing bed " + key)
		if stream == null: continue
		var length := stream.get_length()
		var frames := stream.data.size() / 2
		check(length >= 6.0 and length <= 10.0, "bed %s length %.2f s" % [key, length])
		check(stream.loop_mode == AudioStreamWAV.LOOP_FORWARD and stream.loop_begin == 0 and stream.loop_end == frames, "bed %s loop points" % key)
		var stats := measure(stream)
		# The jump across the loop point should look like any other step in the signal.
		check(stats.seam <= maxf(stats.local * 1.25, 0.01), "bed %s seam jump %.4f vs nearby steps up to %.4f" % [key, stats.seam, stats.local])
		check(stats.rms > 0.01, "bed %s is silent" % key)
		print("AUDIO_BED %-18s %.1fs %5dHz rms=%.3f peak=%.2f seam=%.4f nearby_max=%.4f mean_step=%.4f" % [key, length, stream.mix_rate, stats.rms, stats.peak, stats.seam, stats.local, stats.step])

func measure(stream: AudioStreamWAV) -> Dictionary:
	var s := samples(stream)
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
	var window := stream.mix_rate / 20
	var punch := 0.0
	var run := 0.0
	for i in s.size():
		run += s[i] * s[i]
		if i >= window: run -= s[i - window] * s[i - window]
		punch = maxf(punch, run)
	# Largest step within 10 ms either side of the loop point.
	var near := 0.0
	var span := mini(stream.mix_rate / 100, s.size() / 4)
	for i in range(1, span):
		near = maxf(near, maxf(absf(s[i] - s[i - 1]), absf(s[s.size() - i] - s[s.size() - i - 1])))
	return {"peak": peak, "rms": sqrt(energy / s.size()), "step": step / maxf(s.size() - 1, 1),
		"mean": level / s.size(), "punch": sqrt(maxf(punch, 0.0) / window),
		"seam": absf(s[0] - s[s.size() - 1]), "local": near}

func samples(stream: AudioStreamWAV) -> PackedFloat32Array:
	if decoded.has(stream): return decoded[stream]
	var data := stream.data
	var out := PackedFloat32Array()
	out.resize(data.size() / 2)
	for i in out.size(): out[i] = data.decode_s16(i * 2) / 32768.0
	decoded[stream] = out
	return out

func check_footsteps(audio: Node) -> void:
	for surface in WorldAudio.SURFACES:
		for speed in [2.8, 4.5]:
			audio.footstep(surface, speed)
			var player: AudioStreamPlayer = audio.steps[(audio.step_index + audio.steps.size() - 1) % audio.steps.size()]
			check(player.stream == WorldAudio.cache.get("step/%s/%s/%d" % [surface, "run" if speed > 3.6 else "walk", audio.last_variation[surface + ("run" if speed > 3.6 else "walk")]]), "%s %.1f m/s stream" % [surface, speed])
			check(player.bus == &"Master" and player.playing, "%s %.1f m/s not playing on Master" % [surface, speed])
	audio.footstep("lava", 2.8) # unknown surfaces fall back instead of failing
	var slow := average_step(audio, "stone", 1.2)
	var walk := average_step(audio, "stone", 2.8)
	var run := average_step(audio, "stone", 4.5)
	print("AUDIO_GAIT slow=%.1fdB walk=%.1fdB/%.2fx run=%.1fdB/%.2fx" % [slow.db, walk.db, walk.pitch, run.db, run.pitch])
	check(run.db > walk.db + 3.0 and walk.db > slow.db + 3.0, "speed does not change step loudness enough")
	check(run.pitch > walk.pitch, "running steps are not brighter")
	check(not run.repeats and not walk.repeats, "a take repeated back to back")

func average_step(audio: Node, surface: String, speed: float) -> Dictionary:
	var db := 0.0
	var pitch := 0.0
	var repeats := false
	var last: Variant = null
	for i in 200:
		var step: Dictionary = audio.step_choice(surface, speed)
		db += step.volume_db / 200.0
		pitch += step.pitch / 200.0
		if step.stream == last: repeats = true
		last = step.stream
	return {"db": db, "pitch": pitch, "repeats": repeats}

func check_ambience(audio: Node) -> void:
	var cases := [
		[{"day": 1.0, "coast": 0.8, "wind": 0.3}, ["birds", "birds_far", "coast", "wind"]],
		[{"day": 0.0}, ["insects", "coast", "wind"]],
		[{"day": 0.45, "coast": 0.0, "wind": 0.6}, ["birds", "birds_far", "insects", "wind"]],
		[{"day": 0.85, "waterfall": 1.0, "wind": 0.2}, ["birds", "birds_far", "waterfall", "wind"]],
		[{"indoor": true}, ["birds", "birds_far", "room", "waterfall_muffled", "wind_muffled"]],
		[{"indoor": false, "waterfall": 0.0, "wind": 0.0, "day": 1.0, "fade": 0.5}, ["birds", "birds_far"]],
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
			check(player.bus == &"Master", key + " not on Master")
			check(player.playing == (audio.gains[key] > 0.0005), "%s playing=%s at gain %.3f" % [key, player.playing, audio.gains[key]])
			if player.playing: audible.append(key)
		print("AUDIO_AMBIENCE %s -> %s" % [JSON.stringify(case[0]), ", ".join(audible)])
		audible.sort()
		expected.sort()
		check(audible == expected, "expected %s, heard %s" % [expected, audible])
		check(not audio.is_processing(), "fades kept processing after settling")
	# Indoors the bright beds drop by more than 20 dB.
	var inside: Dictionary = WorldAudio.mix_targets({"day": 1.0, "indoor": true, "coast": 1.0})
	check(inside.birds < 0.1 and inside.coast == 0.0 and inside.coast_muffled == 1.0, "indoor muffling")
	# The fade ramps rather than jumping.
	audio.set_ambience({"fade": 1.5, "coast": 1.0})
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

# --- Previews ----------------------------------------------------------------------------------

func export_previews(audio: Node, dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	var cache: Dictionary = WorldAudio.cache
	var written := []
	# Each bed alone at full scale, starting 3 s before its loop point so the seam is mid-file.
	for key in WorldAudio.BED_DB:
		var stream: AudioStreamWAV = cache["bed/" + key]
		written.append(save(dir, "bed_%s.wav" % key, render(stream, 6.0, stream.get_length() - 3.0)))
	# Scenes at their in-game balance (Master at 0 dB), lifted for listening.
	var lift := db_to_linear(PREVIEW_DB)
	var scenes := {
		"day_coast": {"day": 1.0, "coast": 0.8, "wind": 0.3},
		"night_coast": {"day": 0.0, "coast": 0.8, "wind": 0.2},
		"dusk_meadow": {"day": 0.45, "wind": 0.5},
		"waterfall": {"day": 0.85, "waterfall": 1.0, "wind": 0.2},
		"indoor_day": {"day": 1.0, "coast": 0.7, "wind": 0.4, "indoor": true},
		"indoor_night": {"day": 0.0, "coast": 0.7, "wind": 0.4, "indoor": true},
	}
	for scene in scenes:
		written.append(save(dir, "scene_%s.wav" % scene, ambience(audio, scenes[scene], 8.0), lift))
	# Every surface: six walking steps, then six running steps.
	var walk := PackedFloat32Array()
	walk.resize(int(22.0 * OUT))
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
	var beach := ambience(audio, {"day": 1.0, "coast": 0.9, "wind": 0.3, "indoor": false}, 10.0)
	var at := add_steps(audio, beach, "sand", 2.8, 0.47, 8, 0.4)
	at = add_steps(audio, beach, "shallow", 2.4, 0.52, 5, at)
	add_steps(audio, beach, "wood", 4.5, 0.32, 7, at + 0.2)
	written.append(save(dir, "scene_beach_walk.wav", beach, lift))
	print("AUDIO_EXPORT %s (scenes and footsteps +%.0f dB) %s" % [dir, PREVIEW_DB, ", ".join(written)])

func ambience(audio: Node, params: Dictionary, seconds: float) -> PackedFloat32Array:
	var gains: Dictionary = WorldAudio.mix_targets(params)
	var mix := PackedFloat32Array()
	mix.resize(int(seconds * OUT))
	for key in gains:
		if gains[key] <= 0.0005: continue
		var stream: AudioStreamWAV = WorldAudio.cache["bed/" + key]
		var level: float = gains[key] * db_to_linear(audio.ambience_db + WorldAudio.BED_DB[key])
		add(mix, render(stream, seconds, randf() * stream.get_length()), 0, level)
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
func render(stream: AudioStreamWAV, seconds: float, offset := 0.0, pitch := 1.0) -> PackedFloat32Array:
	var src := samples(stream)
	var frames := src.size()
	var looped := stream.loop_mode == AudioStreamWAV.LOOP_FORWARD
	var advance := stream.mix_rate * pitch / OUT
	var pos := offset * stream.mix_rate
	var out := PackedFloat32Array()
	out.resize(int(seconds * OUT))
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
