extends SceneTree
## Creature / combat / hero / NPC-voice sound bank check (headless).
##   godot --headless --path game --script res://tests/audio_bank_check.gd
## 1. Every WAV under assets/sfx/{creatures,combat,hero,voice} loads as an AudioStreamWAV,
##    is mono, under 150 KB, and its length, peak and loudest 120 ms RMS (>150 Hz weighted,
##    same measure as tools/make_creature_sfx.py) sit inside the group's range.
## 2. Every API event resolves: CreatureAudio species x event x region (>= 2 takes),
##    CombatAudio / HeroVoice events, every VoiceBabble voice slices into its syllable bank
##    (each slot sounds and is silent at its end), resolve() maps casts and titles.
## 3. Pooled playback: voices never exceed the pool, species and idle limits hold, far
##    sounds are skipped, low-priority sounds can't steal from high-priority ones, the
##    heartbeat loops and fades, and the babble follows a typing Label (rate-limited,
##    stops on skip, "" stays silent).
## Writes artifacts/audio-bank-check.txt. Exit code 1 on any failure.
const CreatureAudio := preload("res://scripts/creature_audio.gd")
const CombatAudio := preload("res://scripts/combat_audio.gd")
const HeroVoice := preload("res://scripts/hero_voice.gd")
const VoiceBabble := preload("res://scripts/voice_babble.gd")
const SfxBank := preload("res://scripts/sfx_bank.gd")
const MAX_BYTES := 150000
## group: [min s, max s, max peak, min st-rms dBFS, max st-rms dBFS]
const RANGES := {
	"creatures": [0.3, 2.0, 0.95, -24.0, -13.0],
	"combat": [0.15, 2.3, 0.95, -25.0, -12.0],
	"hero": [0.15, 2.3, 0.95, -27.0, -14.0],
	"voice": [3.0, 3.4, 0.95, -40.0, -8.0],
}
## Files whose name starts with a key use its range instead of the group's (monster footfalls are short).
const RANGE_PREFIX := {"step_": [0.08, 1.0, 0.95, -28.0, -14.0]}
## Loops (name contains "_loop"): longer, bigger, no fade at the ends; the wrap must be continuous.
const LOOP_RANGE := [0.5, 10.0, 0.95, -30.0, -12.0]
const LOOP_MAX_BYTES := 450000
## Minimum takes per event (tools/sfx/gen_combat.py families; most hold more, counting the older takes).
## Creature pools = region-neutral takes + the region's own takes.
const CREATURE_MIN := 8
const CREATURE_EXTRA_MIN := {"boar": 6}
const STEP_MIN := 6
const LAYER_MIN := 4
const COMBAT_MIN := {"swing_axe": 12, "swing_spear": 12, "swing_fist": 12, "swing_axe_heavy": 6, "swing_spear_heavy": 6,
	"swing_fist_heavy": 6, "hit_flesh": 10, "hit_stone": 10, "hit_wood": 10, "hit_spirit": 10, "block": 6, "dodge": 8,
	"whiff": 6, "critical": 5, "spawn": 6, "dissolve": 6, "player_hit": 8, "equip": 5, "fuel": 5, "sputter": 5, "night": 3,
	"dawn": 3, "night_warn": 3, "cold": 4, "hunger": 4, "ember": 4, "depleted_tree": 3, "depleted_stone": 3,
	"depleted_fiber": 3, "depleted_berry": 3, "craft_tool": 4, "craft_soup": 4, "craft_bandage": 4, "bandage": 4,
	"harvest_tree": 12, "harvest_stone": 12, "harvest_fiber": 12, "harvest_berry": 10}
const HERO_MIN := {"attack": 10, "attack_heavy": 5, "hurt": 8, "pickup": 6, "harvest": 8, "dodge": 5, "tired": 5, "eat": 5,
	"faint": 3, "reward": 4, "levelup": 3}

var failures := 0
var lines := PackedStringArray()

func _initialize() -> void: call_deferred("run")

func check(ok: bool, what: String) -> void:
	if ok: return
	failures += 1
	lines.append("FAIL "+what)

func run() -> void:
	var started := Time.get_ticks_msec()
	check_files()
	check_events()
	await check_pool()
	await check_variety()
	await check_heartbeat()
	await check_campfire()
	await check_babble()
	lines.append("RESULT %s (%d problems, %.1f s)" % ["PASS" if failures == 0 else "FAIL", failures, (Time.get_ticks_msec()-started)*0.001])
	var text := "\n".join(lines)
	print(text)
	var out := FileAccess.open(ProjectSettings.globalize_path("res://../artifacts/audio-bank-check.txt"), FileAccess.WRITE)
	if out: out.store_string(text+"\n")
	quit(1 if failures > 0 else 0)

# ------------------------------------------------------------------ 1. files
func check_files() -> void:
	for group in RANGES:
		var dir := "res://assets/sfx/%s/" % group
		# voice/: only the syllable banks (<id>.wav, <id>_2.wav ...); the emote/greet barks and
		# quill ticks there are checked by voice_variety_check.gd.
		var names := Array(DirAccess.get_files_at(dir)).filter(func(f: String) -> bool: return f.ends_with(".wav") and not (group == "voice" and VoiceBabble.is_bark_file(f)))
		names.sort()
		check(not names.is_empty(), group+": no wav files")
		var spec: Array = RANGES[group]
		var total_kb := 0.0
		var lo_rms := 0.0
		var hi_rms := -200.0
		var longest := 0.0
		for name in names:
			var path: String = dir+name
			var stream := load(path) as AudioStreamWAV
			check(stream != null, path+" does not load as AudioStreamWAV")
			if stream == null: continue
			check(not stream.stereo, path+" is stereo")
			check(stream.get_length() > 0.05, path+" is empty")
			var bytes := FileAccess.get_file_as_bytes(ProjectSettings.globalize_path(path)).size()
			total_kb += bytes/1024.0
			var looped: bool = group != "voice" and name.contains("_loop")
			check(bytes < (LOOP_MAX_BYTES if looped else MAX_BYTES), "%s is %d bytes" % [path, bytes])
			var m := measure(path)
			if m.is_empty():
				check(false, path+" unreadable")
				continue
			var fspec: Array = LOOP_RANGE if looped else spec
			for prefix in RANGE_PREFIX:
				if group != "voice" and name.begins_with(prefix): fspec = RANGE_PREFIX[prefix]
			longest = maxf(longest, m.seconds)
			check(m.seconds >= fspec[0] and m.seconds <= fspec[1], "%s length %.2f s outside %.2f..%.2f" % [path, m.seconds, fspec[0], fspec[1]])
			check(m.peak <= fspec[2], "%s peak %.3f" % [path, m.peak])
			check(m.rms_db >= fspec[3] and m.rms_db <= fspec[4], "%s st-rms %.1f dBFS outside %.0f..%.0f" % [path, m.rms_db, fspec[3], fspec[4]])
			if looped: check(absf(m.last-m.first) < 0.15, "%s loop seam jumps %.3f -> %.3f" % [path, m.last, m.first])
			else: check(absf(m.first) < 0.02 and absf(m.last) < 0.02, "%s starts/ends with a step (%.3f / %.3f)" % [path, m.first, m.last])
			if m.rms_db > -100.0:
				lo_rms = minf(lo_rms, m.rms_db)
				hi_rms = maxf(hi_rms, m.rms_db)
			if group == "voice": check_bank_file(path, m)
		lines.append("%-10s %3d files  %7.1f KB  longest %.2f s  st-rms %.1f..%.1f dBFS" % [group, names.size(), total_kb, longest, lo_rms, hi_rms])

## Each syllable slot must sound and be silent in its last 5 ms (slices land on the gaps).
func check_bank_file(path: String, m: Dictionary) -> void:
	var samples: PackedFloat32Array = m.samples
	var rate: int = m.rate
	var slots := VoiceBabble.ONSETS.size()*VoiceBabble.VOWELS.size()
	for k in slots:
		var a := int(round(k*VoiceBabble.SLOT*rate))
		var b := mini(int(round((k+1)*VoiceBabble.SLOT*rate)), samples.size())
		var peak := 0.0
		var tail := 0.0
		for i in range(a, b):
			peak = maxf(peak, absf(samples[i]))
			if i >= b-int(0.005*rate): tail = maxf(tail, absf(samples[i]))
		check(peak > 0.05, "%s slot %d is silent" % [path, k])
		check(tail < 0.01, "%s slot %d runs into the next slot (%.3f)" % [path, k, tail])

## Reads the source PCM (imports may be QOA) and measures it like the generator does.
func measure(path: String) -> Dictionary:
	var raw := FileAccess.get_file_as_bytes(ProjectSettings.globalize_path(path))
	if raw.size() < 44 or raw.slice(0, 4).get_string_from_ascii() != "RIFF": return {}
	var pos := 12
	var rate := 0
	var data := PackedByteArray()
	while pos+8 <= raw.size():
		var id := raw.slice(pos, pos+4).get_string_from_ascii()
		var size := raw.decode_u32(pos+4)
		if id == "fmt ": rate = raw.decode_u32(pos+12)
		elif id == "data": data = raw.slice(pos+8, pos+8+size)
		pos += 8+size+(size & 1)
	var frames := data.size()/2
	if frames == 0 or rate == 0: return {}
	var samples := PackedFloat32Array()
	samples.resize(frames)
	var peak := 0.0
	# 2nd-order Butterworth high-pass at 150 Hz, then the loudest 120 ms RMS.
	var w := TAU*150.0/rate
	var alpha := sin(w)/(2.0*sqrt(0.5))
	var a0 := 1.0+alpha
	var b0 := (1.0+cos(w))*0.5/a0
	var b1 := -(1.0+cos(w))/a0
	var a1 := -2.0*cos(w)/a0
	var a2 := (1.0-alpha)/a0
	var x1 := 0.0
	var x2 := 0.0
	var y1 := 0.0
	var y2 := 0.0
	var window := int(0.12*rate)
	var squares := PackedFloat64Array()
	squares.resize(frames+1)
	var acc := 0.0
	for i in frames:
		var x := data.decode_s16(i*2)/32768.0
		samples[i] = x
		peak = maxf(peak, absf(x))
		var y := b0*x+b1*x1+b0*x2-a1*y1-a2*y2
		x2 = x1
		x1 = x
		y2 = y1
		y1 = y
		acc += y*y
		squares[i+1] = acc
	var best := 0.0
	if frames <= window: best = acc/maxf(frames, 1)
	else:
		for i in range(window, frames+1, 32): best = maxf(best, (squares[i]-squares[i-window])/window)
	return {"seconds": float(frames)/rate, "rate": rate, "peak": peak, "rms_db": linear_to_db(sqrt(maxf(best, 1e-12))),
		"first": samples[0], "last": samples[frames-1], "samples": samples}

# ------------------------------------------------------------------ 2. events
func check_events() -> void:
	var resolved := 0
	for species in CreatureAudio.SPECIES:
		for event in CreatureAudio.EVENTS:
			for region in CreatureAudio.REGIONS:
				var takes := CreatureAudio.streams(species, event, region)
				check(takes.size() >= CREATURE_MIN, "creature %s/%s/%s has %d takes (want >= %d)" % [species, event, region, takes.size(), CREATURE_MIN])
				var own := 0
				for path in CreatureAudio.pool_paths(species, event, region):
					if path.contains("_%s_" % region): own += 1
				check(own >= 2 and takes.size()-own >= 6, "creature %s/%s/%s: %d region-neutral + %d own takes" % [species, event, region, takes.size()-own, own])
				resolved += takes.size()
		for event in CreatureAudio.EXTRA:
			var extra := CreatureAudio.streams(species, event, "forest")
			check(extra.size() >= int(CREATURE_EXTRA_MIN.get(species, 1)), "creature %s/%s has %d takes" % [species, event, extra.size()])
			resolved += extra.size()
		check(SfxBank.count("creatures/step_"+CreatureAudio.GAIT[species]) >= STEP_MIN, "%s footfalls: %d takes" % [species, SfxBank.count("creatures/step_"+CreatureAudio.GAIT[species])])
	for region in CreatureAudio.REGIONS:
		for kind in ["accent", "bed"]:
			check(SfxBank.count("creatures/layer_%s_%s" % [region, kind]) >= LAYER_MIN, "region layer %s/%s: %d takes" % [region, kind, SfxBank.count("creatures/layer_%s_%s" % [region, kind])])
	check(CreatureAudio.species_name("golem") == "brute" and CreatureAudio.species_name("???") == "wolf", "species aliases")
	check(CreatureAudio.event_name("attack") == "strike" and CreatureAudio.event_name("aggro") == "alert", "event aliases")
	check(CreatureAudio.event_name("charge") == "charge" and CreatureAudio.event_name("stunned") == "dazed", "boar cue aliases")
	check(CreatureAudio.region_name("ember") == "quarry" and CreatureAudio.region_name("ice") == "frost" and CreatureAudio.region_name("") == "forest", "region aliases")
	for event in CombatAudio.EVENTS:
		var takes := CombatAudio.streams(event)
		check(takes.size() >= int(COMBAT_MIN.get(event, 2)), "combat %s has %d takes (want >= %d)" % [event, takes.size(), int(COMBAT_MIN.get(event, 2))])
		resolved += takes.size()
	check(ResourceLoader.exists(CombatAudio.DIR+"campfire_loop.wav"), "combat/campfire_loop.wav missing")
	for event in HeroVoice.EVENTS:
		var takes := HeroVoice.streams(event)
		check(takes.size() >= int(HERO_MIN.get(event, 1)), "hero %s has %d takes (want >= %d)" % [event, takes.size(), int(HERO_MIN.get(event, 1))])
		resolved += takes.size()
	for id in VoiceBabble.VOICES:
		var bank := VoiceBabble.bank(id)
		check(bank.size() == VoiceBabble.ONSETS.size()*VoiceBabble.VOWELS.size(), "voice %s sliced into %d syllables (PCM import?)" % [id, bank.size()])
		for part in bank: check(part.get_length() > 0.1 and part.get_length() < 0.13, "voice %s syllable length %.3f" % [id, part.get_length()])
	var cases := {["naru", ""]: "naru", ["res://assets/ui/shadow_postman.png", ""]: "postman", ["res://assets/portraits/haeru.png", ""]: "haeru",
		["", "이정표"]: "", ["", "수상한 그림자 · 시인"]: "shadow", ["", "소라 · 재단사"]: "sora", ["stranger", ""]: "villager"}
	for key in cases:
		var got := VoiceBabble.resolve(key[0], key[1])
		check(got == cases[key], "resolve(%s, %s) = '%s', want '%s'" % [key[0], key[1], got, cases[key]])
	check(CombatAudio.material_for("brute") == "hit_stone" and CombatAudio.material_for("wisp") == "hit_spirit", "impact materials")
	lines.append("events     %d streams resolve (creatures %d keys, combat %d, hero %d, voices %d)" % [resolved,
		CreatureAudio.SPECIES.size()*CreatureAudio.EVENTS.size()*CreatureAudio.REGIONS.size(), CombatAudio.EVENTS.size(), HeroVoice.EVENTS.size(), VoiceBabble.VOICES.size()])

# ------------------------------------------------------------------ 3. playback
func make_app() -> Node3D:
	var script := GDScript.new()
	script.source_code = "extends Node3D\nvar player: Node3D\nvar run := {\"map_id\": \"frost\"}\n"
	script.reload()
	var app: Node3D = script.new()
	root.add_child(app)
	var hero := Node3D.new()
	app.add_child(hero)
	app.player = hero
	return app

func check_pool() -> void:
	var app := make_app()
	await process_frame
	check(CreatureAudio.region_name("", app) == "frost", "region from app.run.map_id")
	var before := CreatureAudio.played
	check(CreatureAudio.play(app, "wolf", "alert", Vector3(3, 0, 0)), "wolf alert did not play")
	check(not CreatureAudio.play(app, "wolf", "alert", Vector3(3, 0, 0)), "same call within 40 ms was not merged")
	check(not CreatureAudio.play(app, "boar", "alert", Vector3(60, 0, 0)), "a sound 60 m away played")
	check(CreatureAudio.play(app, "boar", "idle", Vector3(2, 0, 2)), "boar idle did not play")
	check(not CreatureAudio.play(app, "boar", "idle", Vector3(2, 0, 2)), "idle throttle let a second boar idle through")
	await process_frame
	check(CreatureAudio.active("creature/") >= 2, "pooled voices are not playing (%d)" % CreatureAudio.active("creature/"))
	# Hammer the pool: every species, every event, many positions, all at once.
	var attempts := 0
	var max_seen := 0
	for pass_index in 3:
		for species in CreatureAudio.SPECIES:
			for event in CreatureAudio.EVENTS:
				CreatureAudio.last_key.clear()
				CreatureAudio.play(app, species, event, Vector3(randf_range(-8, 8), 0, randf_range(-8, 8)))
				CombatAudio.play(app, "hit_flesh", Vector3(1, 0, 1))
				attempts += 2
				max_seen = maxi(max_seen, CreatureAudio.active())
				for s in CreatureAudio.SPECIES:
					check(CreatureAudio.active("creature/%s/" % s) <= CreatureAudio.MAX_PER_SPECIES, "species %s over its voice limit" % s)
				check(CreatureAudio.active("creature/", "/idle") <= CreatureAudio.MAX_IDLE, "too many idle voices")
	check(max_seen <= CreatureAudio.MAX_VOICES*2, "pool exceeded: %d voices" % max_seen)
	check(CreatureAudio.pool3d.size() == CreatureAudio.MAX_VOICES and CreatureAudio.pool2d.size() == CreatureAudio.MAX_VOICES, "pool size changed")
	# Fill the flat pool with top-priority sounds: an idle must not steal a voice.
	CreatureAudio.stop_all()
	for i in CreatureAudio.MAX_VOICES: CombatAudio.play(app, "critical")
	await process_frame
	check(CreatureAudio.active("combat/critical") == CreatureAudio.MAX_VOICES, "criticals did not fill the pool (%d)" % CreatureAudio.active("combat/critical"))
	CreatureAudio.last_idle.clear()
	check(not CombatAudio.play(app, "swing_fist"), "a low-priority swing stole a critical's voice")
	# With a camera the positional sounds pan through the 3D pool.
	var camera := Camera3D.new()
	app.add_child(camera)
	camera.current = true
	await process_frame
	CreatureAudio.last_key.clear()
	check(CreatureAudio.play(app, "brute", "strike", Vector3(-4, 0, 0)), "brute strike did not play with a camera")
	await process_frame
	var in3d := 0
	for entry in CreatureAudio.pool3d:
		if entry.node.playing: in3d += 1
	check(in3d >= 1, "positional sound did not use the 3D pool")
	check(HeroVoice.play(app, "hurt", 0.0, true), "hero hurt did not play")
	check(not HeroVoice.play(app, "attack", 0.0, true), "an attack effort cut the hurt cry")
	check(HeroVoice.play(app, "reward", 0.0, true), "reward chime did not play over the voice")
	var played := CreatureAudio.played-before
	lines.append("pool       %d attempts, %d started, max %d voices at once (limit %d+%d), bus %s" % [attempts, played, max_seen,
		CreatureAudio.MAX_VOICES, CreatureAudio.MAX_VOICES, CreatureAudio.bus("SFX")])
	CreatureAudio.stop_all()
	app.queue_free()
	await process_frame

## Take variety and the cues added with it: shuffle bags never repeat a take back to back, every
## third swing of a combo is heavy, a roster's spawn is staggered and capped, region layers sound
## under region-neutral takes, footfalls are throttled, status cues fire on their edge and period.
func check_variety() -> void:
	var app := make_app()
	await process_frame
	var seen := {}
	var repeats := 0
	var last := ""
	for i in 24:
		CreatureAudio.stop_all()
		check(CombatAudio.play(app, "hit_flesh", Vector3(1, 0, 1)), "hit_flesh play %d failed" % i)
		var take: String = CombatAudio.last_take.get("hit_flesh", "")
		if take == last: repeats += 1
		last = take
		seen[take] = true
	check(repeats == 0, "hit_flesh repeated a take back to back %d times" % repeats)
	check(seen.size() >= 10, "hit_flesh used only %d different takes in 24 plays" % seen.size())
	var hero_seen := {}
	var hero_repeats := 0
	var hero_last := ""
	for i in 16:
		check(HeroVoice.play(app, "hurt", 0.0, true), "hero hurt %d did not play" % i)
		var take: String = HeroVoice.last_take.get("hurt", "")
		if take == hero_last: hero_repeats += 1
		hero_last = take
		hero_seen[take] = true
	check(hero_repeats == 0 and hero_seen.size() >= 8, "hero hurt: %d back-to-back repeats, %d different takes" % [hero_repeats, hero_seen.size()])
	CreatureAudio.stop_all()
	CombatAudio.combo = 0
	CombatAudio.combo_at = -10.0
	CombatAudio.last_time.erase("swing_axe_heavy")
	for i in 3: CombatAudio.swing(app, "axe")
	check(CombatAudio.last_time.has("swing_axe_heavy"), "the third swing of a quick combo was not the heavy take")
	CreatureAudio.stop_all()
	await process_frame
	var before := CreatureAudio.played
	for i in 7: CombatAudio.play(app, "spawn", Vector3(i, 0, 2))
	check(CreatureAudio.played-before == 1, "a spawn burst started %d sounds at once (want 1)" % (CreatureAudio.played-before))
	await create_timer(0.45).timeout
	var spawned := CreatureAudio.active("combat/spawn")
	check(spawned >= 2 and spawned <= CombatAudio.GROUP_MAX, "a spawn burst of 7 played %d (want 2..%d)" % [spawned, CombatAudio.GROUP_MAX])
	var layered := 0
	for i in 12:
		CreatureAudio.last_key.clear()
		CreatureAudio.stop_all()
		CreatureAudio.play(app, "wolf", "death", Vector3(2, 0, 0))
		await process_frame
		if CreatureAudio.active("layer/frost") > 0: layered += 1
	check(layered >= 3, "the frost layer sounded under only %d of 12 wolf deaths" % layered)
	CreatureAudio.stop_all()
	CreatureAudio.last_step.clear()
	check(CreatureAudio.step(app, "boar", Vector3(2, 0, 0), 2.0), "boar footfall did not play")
	check(not CreatureAudio.step(app, "boar", Vector3(2, 0, 0), 2.0), "two boar footfalls within STEP_GAP")
	check(not CreatureAudio.step(app, "wolf", Vector3(40, 0, 0), 2.0), "a footfall 40 m away played")
	check(CreatureAudio.step(app, "brute", Vector3(-2, 0, 0), 1.0), "brute footfall did not play")
	await process_frame
	check(not CreatureAudio.step(app, "shroom", Vector3(0, 0, 2), 1.0), "more than MAX_STEPS footfalls at once")
	check(CreatureAudio.pool_paths("boar", "charge", "quarry").size() >= 6, "boar charge pool")
	check(CreatureAudio.pool_paths("wolf", "dazed", "forest") == CreatureAudio.pool_paths("wolf", "hurt", "forest"), "dazed falls back to hurt")
	CreatureAudio.stop_all()
	check(CombatAudio.cue(app, "hunger", true, 30.0), "hunger cue did not play when it started")
	check(not CombatAudio.cue(app, "hunger", true, 30.0), "hunger cue repeated before its period")
	CombatAudio.cue(app, "hunger", false)
	check(CombatAudio.cue(app, "hunger", true, 30.0), "hunger cue did not play again after it ended")
	lines.append("variety    hit_flesh %d takes in 24 plays, hero hurt %d in 16, no back-to-back repeat; spawn burst 7 -> %d; frost layer %d/12" % [
		seen.size(), hero_seen.size(), spawned, layered])
	CreatureAudio.stop_all()
	app.queue_free()
	await process_frame

func check_campfire() -> void:
	var app := make_app()
	var camera := Camera3D.new()
	app.add_child(camera)
	camera.current = true
	await process_frame
	CombatAudio.campfire(app, 40.0, Vector3(1, 0, 0))
	await process_frame
	check(CombatAudio.campfire_playing(), "campfire loop did not start")
	var stream: AudioStreamWAV = CombatAudio.fire.stream as AudioStreamWAV if is_instance_valid(CombatAudio.fire) else null
	check(stream != null and stream.loop_mode != AudioStreamWAV.LOOP_DISABLED, "campfire stream does not loop")
	await create_timer(0.6).timeout
	CombatAudio.campfire(app, 40.0, Vector3(1, 0, 0))
	check(CombatAudio.campfire_playing(), "campfire stopped while it was fed")
	CombatAudio.campfire(app, 0.0, Vector3(1, 0, 0))
	await create_timer(1.0).timeout
	check(not CombatAudio.campfire_playing(), "campfire did not fade out when the fire went out")
	CombatAudio.campfire(app, 30.0, Vector3(1, 0, 0))
	await process_frame
	check(CombatAudio.campfire_playing(), "campfire did not restart")
	await create_timer(3.2).timeout
	check(not CombatAudio.campfire_playing(), "campfire kept playing after the run stopped calling it")
	lines.append("campfire   loops while fed, fades when the fire goes out or the run is left")
	app.queue_free()
	await process_frame

func check_heartbeat() -> void:
	var app := make_app()
	CombatAudio.heartbeat(app, 80.0)
	check(not CombatAudio.heartbeat_playing(), "heartbeat at 80 HP")
	CombatAudio.heartbeat(app, 18.0)
	await process_frame
	check(CombatAudio.heartbeat_playing(), "heartbeat did not start at 18 HP")
	var stream := CombatAudio.heart.stream as AudioStreamWAV
	check(stream != null and stream.loop_mode != AudioStreamWAV.LOOP_DISABLED, "heartbeat stream does not loop")
	var slow := CombatAudio.heart.pitch_scale
	CombatAudio.heartbeat(app, 5.0)
	check(CombatAudio.heart.pitch_scale > slow, "heartbeat does not speed up at lower HP")
	await create_timer(1.0).timeout
	check(CombatAudio.heartbeat_playing(), "heartbeat loop ended by itself")
	CombatAudio.heartbeat(app, 60.0)
	await create_timer(0.9).timeout
	check(not CombatAudio.heartbeat_playing(), "heartbeat did not fade out above 30 %")
	lines.append("heartbeat  starts below 30 %%, pitch %.2f -> %.2f, loops, fades out" % [slow, CombatAudio.heart.pitch_scale])
	app.queue_free()

func check_babble() -> void:
	var label := Label.new()
	root.add_child(label)
	var line := "안녕하세요! 오늘은 바람이 참 좋네요. 같이 걸을까요?"
	label.text = line
	label.visible_ratio = 0.0
	var seconds := clampf(line.length()*0.028, 0.25, 1.6)
	var typing := label.create_tween()
	typing.tween_property(label, "visible_ratio", 1.0, seconds)
	var before := VoiceBabble.syllables_played
	VoiceBabble.speak(null, "naru", line, 0.0, label)
	check(VoiceBabble.speaking(), "babble did not start")
	var until := Time.get_ticks_msec()+4000
	while VoiceBabble.speaking() and Time.get_ticks_msec() < until:
		await process_frame
	var count := VoiceBabble.syllables_played-before
	var voiced := 0
	for i in line.length():
		if VoiceBabble._voiced(line.unicode_at(i)): voiced += 1
	var gap: float = VoiceBabble.VOICES.naru.gap
	check(count >= 5, "only %d syllables for a %d-syllable line" % [count, voiced])
	check(count <= voiced and count <= int(seconds/(gap*0.6))+2, "too many syllables: %d in %.2f s" % [count, seconds])
	lines.append("babble     naru: %d syllables for %d voiced characters over %.2f s (gap %.3f s)" % [count, voiced, seconds, gap])
	# Skipping to the full line ends the babble at once.
	label.text = "그림자도 이야기를 좋아해요. 천천히 들어 주세요."
	label.visible_ratio = 0.0
	VoiceBabble.speak(null, "res://assets/ui/shadow_poet.png", label.text, 0.0, label)
	check(VoiceBabble.instance.voice == "poet", "portrait path did not pick the poet's voice")
	await create_timer(0.15).timeout
	label.visible_ratio = 0.3
	await create_timer(0.1).timeout
	var mid := VoiceBabble.syllables_played
	label.visible_ratio = 1.0
	await process_frame
	await process_frame
	check(not VoiceBabble.speaking(), "babble kept going after the line was skipped")
	check(VoiceBabble.syllables_played-mid <= 1, "skip caught up with %d syllables" % (VoiceBabble.syllables_played-mid))
	# Timed mode (no label), a hard stop, and a silent sign.
	VoiceBabble.speak(null, "moru", "Hello there, traveller! Fire's warm.", 20.0)
	await create_timer(0.3).timeout
	check(VoiceBabble.syllables_played > mid, "timed babble made no sound")
	VoiceBabble.stop(true)
	var stopped := VoiceBabble.syllables_played
	await create_timer(0.3).timeout
	check(VoiceBabble.syllables_played == stopped and not VoiceBabble.speaking(), "stop() did not stop")
	VoiceBabble.speak(null, "", "이정표: 서쪽 다리", 0.0)
	await create_timer(0.3).timeout
	check(VoiceBabble.syllables_played == stopped, "a sign babbled")
	label.queue_free()
	lines.append("babble     skip/stop/silent-sign checks done; bus %s" % ("Voice" if AudioServer.get_bus_index("Voice") >= 0 else "Master"))
