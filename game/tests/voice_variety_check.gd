extends SceneTree
## NPC voice variety check (headless; needs the imported voice files of tools/sfx/gen_voice.py):
##   godot --headless --path game --script res://tests/voice_variety_check.gd
## 1. Alternate babble banks: every voice has <id>.wav + <id>_2.wav + <id>_3.wav, each a mono
##    16-bit PCM import (compress/mode=0) of 3.0-3.4 s that slices into the same 28 syllables of
##    0.10-0.13 s, and bank_set() returns all three.
## 2. Barks and ticks: emote_<register>_<kind> (4 registers x 6 kinds), greet_<register> and quill
##    have enough takes; every file loads, is mono, small, short, inside its loudness window and
##    starts/ends quietly. Every voice has a bark register and a gentle pitch toward its f0.
## 3. Babble variety: the same character spoken over and over never plays the same take twice in a
##    row, uses every bank, and its pitch varies (+-2 % on top of the per-character note).
## 4. Quill: "", "sign" and "letter" tick (ticks_played) on a ~8-11/s cadence while the text
##    reveals (not one tick per character), never closer than the throttle allows, stop with the
##    line and never babble (syllables_played). A typing Label (main.gd open_dialogue with an
##    empty cast) ticks too; a stalled reveal rests the pen and a skip silences it at once.
## 5. Greeting: greet() plays once per voice per GREET_GAP; a new dialogue Label greets and holds
##    the first syllables; the next page (same Label) does not greet again.
## 6. Emotes: bubble glyphs map to kinds, emote() plays, is throttled per voice and overall,
##    refuses unknown kinds and far positions.
## Prints RESULT PASS|FAIL; exit code 1 on failure.
const VoiceBabble = preload("res://scripts/voice_babble.gd")
const SfxBank = preload("res://scripts/sfx_bank.gd")
const DIR := "res://assets/sfx/voice/"
const KINDS := ["note", "exclaim", "dots", "heart", "mail", "sleep"]
const MAX_BYTES := 150000
## [min s, max s, min st-rms dBFS, max st-rms dBFS, min takes]
const BARK_RANGE := [0.12, 1.2, -22.0, -16.0, 4]
const GREET_RANGE := [0.2, 0.8, -22.0, -16.0, 4]
const QUILL_RANGE := [0.025, 0.15, -28.5, -21.5, 8]

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
	check_banks()
	check_barks()
	check_variety()
	await check_quill()
	await check_greet()
	await check_emotes()
	VoiceBabble.stop(true)
	lines.append("RESULT %s (%d problems, %.1f s)" % ["PASS" if failures == 0 else "FAIL", failures, (Time.get_ticks_msec()-started)*0.001])
	print("\n".join(lines))
	SfxBank.clear()
	quit(1 if failures > 0 else 0)

# ------------------------------------------------------------------ 1. banks
func check_banks() -> void:
	var slots := VoiceBabble.ONSETS.size()*VoiceBabble.VOWELS.size()
	var total := 0
	for id in VoiceBabble.VOICES:
		var paths := SfxBank.paths(DIR+id)
		check(paths.size() >= 3, "voice %s has %d banks %s" % [id, paths.size(), paths])
		for path in paths:
			var stream := load(path) as AudioStreamWAV
			check(stream != null, path+" does not load")
			if stream == null: continue
			check(stream.format == AudioStreamWAV.FORMAT_16_BITS and not stream.stereo, "%s is not a mono 16-bit PCM import (format %d)" % [path, stream.format])
			check(stream.get_length() >= 3.0 and stream.get_length() <= 3.4, "%s length %.2f" % [path, stream.get_length()])
		var sets := VoiceBabble.bank_set(id)
		check(sets.size() == paths.size(), "bank_set(%s) has %d of %d banks" % [id, sets.size(), paths.size()])
		for list in sets:
			check(list.size() == slots, "a bank of %s sliced into %d syllables" % [id, list.size()])
			for part in list:
				check(part.get_length() > 0.1 and part.get_length() < 0.13, "voice %s syllable length %.3f" % [id, part.get_length()])
		total += sets.size()
	check(VoiceBabble.bank("naru").size() == slots, "bank() no longer returns the primary bank")
	lines.append("banks      %d banks for %d voices (%d syllables each)" % [total, VoiceBabble.VOICES.size(), slots])

# ------------------------------------------------------------------ 2. barks
func check_barks() -> void:
	var files := 0
	var kb := 0.0
	for id in VoiceBabble.VOICES:
		check(VoiceBabble.BARK_VOICES.has(id), "voice %s has no bark register" % id)
		check(VoiceBabble.REGISTER_F0.has(VoiceBabble.register_of(id)), "voice %s register %s" % [id, VoiceBabble.register_of(id)])
		var p := VoiceBabble.bark_pitch(id)
		check(p >= 0.86 and p <= 1.16, "voice %s bark pitch %.3f" % [id, p])
	for reg in VoiceBabble.REGISTER_F0:
		for kind in KINDS:
			var r := check_family(DIR+"emote_%s_%s" % [reg, kind], BARK_RANGE)
			files += r[0]
			kb += r[1]
		var g := check_family(DIR+"greet_"+reg, GREET_RANGE)
		files += g[0]
		kb += g[1]
	var q := check_family(DIR+"quill", QUILL_RANGE)
	files += q[0]
	kb += q[1]
	for name in ["emote_mid_note_1.wav", "greet_low_2.wav", "quill_3.wav"]:
		check(VoiceBabble.is_bark_file(name), name+" is not a bark file")
	check(not VoiceBabble.is_bark_file("naru_2.wav") and not VoiceBabble.is_bark_file("kid.wav"), "a bank counts as a bark file")
	lines.append("barks      %d files, %.1f KB (emotes 4 registers x %d kinds, greetings, quill)" % [files, kb, KINDS.size()])

func check_family(base: String, spec: Array) -> Array:
	var paths := SfxBank.paths(base)
	check(paths.size() >= int(spec[4]), "%s has %d takes" % [base, paths.size()])
	var kb := 0.0
	for path in paths:
		var stream := load(path) as AudioStreamWAV
		check(stream != null and not stream.stereo, path+" does not load as mono AudioStreamWAV")
		var raw := FileAccess.get_file_as_bytes(ProjectSettings.globalize_path(path))
		kb += raw.size()/1024.0
		check(raw.size() < MAX_BYTES, "%s is %d bytes" % [path, raw.size()])
		var m := measure(raw)
		if m.is_empty():
			check(false, path+" unreadable")
			continue
		check(m.seconds >= spec[0] and m.seconds <= spec[1], "%s length %.3f s outside %.2f..%.2f" % [path, m.seconds, spec[0], spec[1]])
		check(m.peak <= 0.95, "%s peak %.3f" % [path, m.peak])
		check(m.rms_db >= spec[2] and m.rms_db <= spec[3], "%s st-rms %.1f dBFS outside %.1f..%.1f" % [path, m.rms_db, spec[2], spec[3]])
		check(absf(m.first) < 0.02 and absf(m.last) < 0.02, "%s starts/ends with a step" % path)
	return [paths.size(), kb]

## Source PCM measure, the same as audio_bank_check.gd: 150 Hz high-pass, loudest 120 ms RMS.
func measure(raw: PackedByteArray) -> Dictionary:
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
	var peak := 0.0
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
	var first := 0.0
	var last := 0.0
	for i in frames:
		var x := data.decode_s16(i*2)/32768.0
		if i == 0: first = x
		last = x
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
	return {"seconds": float(frames)/rate, "peak": peak, "rms_db": linear_to_db(sqrt(maxf(best, 1e-12))), "first": first, "last": last}

# ------------------------------------------------------------------ 3. babble variety
func check_variety() -> void:
	var node = VoiceBabble._node()
	check(node != null, "no VoiceBabble node")
	if node == null: return
	node.voice = "naru"
	node.quill = false
	node.text = "가".repeat(64)
	node._shape()
	var code := "가".unicode_at(0)
	var banks := VoiceBabble.bank_set("naru")
	# 가 = plosive onset (ㄱ), vowel a (ㅏ)
	var k: int = VoiceBabble.INITIAL_ONSET[0]*VoiceBabble.VOWELS.size()+VoiceBabble.MEDIAL_VOWEL[0]
	var seen := {}
	var previous: AudioStream = null
	var repeats := 0
	var pitches := {}
	for n in 60:
		node._emit(n % 64, code)
		var p: AudioStreamPlayer = node.players[(node.next+node.players.size()-1) % node.players.size()]
		if p.stream == previous: repeats += 1
		previous = p.stream
		for b in banks.size():
			if banks[b].size() > k and banks[b][k] == p.stream: seen[b] = true
		pitches[snappedf(p.pitch_scale, 0.0001)] = true
	node.active = false
	VoiceBabble.stop(true)
	check(repeats == 0, "the same syllable take played twice in a row %d times" % repeats)
	check(seen.size() == banks.size(), "60 syllables used %d of %d banks" % [seen.size(), banks.size()])
	check(pitches.size() >= 20, "pitch did not vary (%d distinct values in 60 syllables)" % pitches.size())
	lines.append("variety    60 x '가' (naru): %d banks used, %d back-to-back repeats, %d distinct pitches" % [seen.size(), repeats, pitches.size()])

# ------------------------------------------------------------------ 4. quill
func check_quill() -> void:
	var line := "이정표: 서쪽 다리를 건너면 바닷가 마을이에요"
	var min_ms := int(VoiceBabble.QUILL_GAP*600.0)-20
	var rates := PackedStringArray()
	var closest := 100000
	for id in ["", "sign", "letter"]:
		var ticks := VoiceBabble.ticks_played
		var syllables := VoiceBabble.syllables_played
		var t0 := Time.get_ticks_msec()
		VoiceBabble.speak(null, id, line, 30.0)
		check(VoiceBabble.speaking(), "'%s' did not start the quill" % id)
		var seen := ticks
		var last := -1
		var at_half := -1
		while VoiceBabble.speaking() and Time.get_ticks_msec()-t0 < 3000:
			await process_frame
			var now := Time.get_ticks_msec()
			if VoiceBabble.ticks_played != seen:
				if last >= 0: closest = mini(closest, now-last)
				last = now
				seen = VoiceBabble.ticks_played
			if at_half < 0 and now-t0 >= 500: at_half = VoiceBabble.ticks_played-ticks
		var seconds := (Time.get_ticks_msec()-t0)*0.001
		var made := VoiceBabble.ticks_played-ticks
		var rate := made/maxf(seconds, 0.001)
		check(not VoiceBabble.speaking(), "'%s' quill did not end with the line" % id)
		check(at_half >= 4 and at_half <= 7, "'%s' made %d quill ticks in 0.5 s (want a ~8-11/s cadence)" % [id, at_half])
		check(rate >= 7.0 and rate <= 12.5, "'%s' quill cadence %.1f/s (%d ticks over %.2f s)" % [id, rate, made, seconds])
		await create_timer(0.3).timeout
		check(VoiceBabble.ticks_played-ticks == made, "'%s' kept ticking after the line was written (%d more)" % [id, VoiceBabble.ticks_played-ticks-made])
		check(VoiceBabble.syllables_played == syllables, "'%s' babbled" % id)
		rates.append("%.1f" % rate)
		VoiceBabble.stop(true)
	check(closest >= min_ms, "two quill ticks only %d ms apart (throttle %d ms)" % [closest, min_ms])
	# Label-driven, as main.gd open_dialogue does for signs and letters (empty cast): a stalled
	# reveal rests the pen, a skip to the full line silences it at once.
	var label := Label.new()
	root.add_child(label)
	label.text = "게시판: 내일 아침 부두에서 낚시 대회가 열립니다. 모두 오세요!"
	label.visible_ratio = 0.0
	var typing := label.create_tween()
	typing.tween_property(label, "visible_ratio", 1.0, 1.6)
	var before := VoiceBabble.ticks_played
	VoiceBabble.speak(null, "", label.text, 0.0, label)
	await create_timer(0.5).timeout
	var typed := VoiceBabble.ticks_played-before
	check(typed >= 4, "a typing sign Label made %d quill ticks in 0.5 s" % typed)
	typing.kill()
	await create_timer(VoiceBabble.QUILL_IDLE+0.1).timeout
	var rested := VoiceBabble.ticks_played
	await create_timer(0.3).timeout
	check(VoiceBabble.ticks_played == rested, "the quill kept ticking while the reveal stalled (%d)" % (VoiceBabble.ticks_played-rested))
	check(VoiceBabble.speaking(), "a stalled reveal ended the quill")
	label.visible_ratio = 1.0
	await process_frame
	await process_frame
	check(not VoiceBabble.speaking() and VoiceBabble.ticks_played == rested, "skipping to the full line did not stop the quill")
	VoiceBabble.stop(true)
	label.queue_free()
	await process_frame
	lines.append("quill      '', sign, letter: %s ticks/s, closest %d ms, label %d ticks in 0.5 s, rests on a stall, skip stops, never babble" % [" / ".join(rates), closest, typed])

# ------------------------------------------------------------------ 5. greeting
func check_greet() -> void:
	var before := VoiceBabble.greets_played
	check(VoiceBabble.greet(null, "moru"), "greet(moru) did not play")
	check(not VoiceBabble.greet(null, "moru"), "greet(moru) played twice within GREET_GAP")
	check(not VoiceBabble.greet(null, ""), "greet('') played")
	check(VoiceBabble.greet(null, "res://assets/ui/shadow_kid.png"), "greet(kid portrait) did not play")
	# A new dialogue Label greets and holds the first syllables; the next page does not greet.
	var label := Label.new()
	root.add_child(label)
	label.text = "안녕! 오늘 바다 바람이 정말 시원하다, 그치? 같이 걸을래?"
	label.visible_ratio = 0.0
	var typing := label.create_tween()
	typing.tween_property(label, "visible_ratio", 1.0, 1.2)
	var syllables := VoiceBabble.syllables_played
	VoiceBabble.speak(null, "sora", label.text, 0.0, label)
	check(VoiceBabble.greets_played == before+3, "a new dialogue box did not greet (greets %d)" % (VoiceBabble.greets_played-before))
	await create_timer(0.12).timeout
	check(VoiceBabble.syllables_played == syllables, "syllables started under the greeting")
	await create_timer(0.6).timeout
	check(VoiceBabble.syllables_played > syllables, "no syllables after the greeting")
	typing.kill()
	label.text = "다음 장이야."
	label.visible_ratio = 0.0
	VoiceBabble.speak(null, "sora", label.text, 0.0, label)
	check(VoiceBabble.greets_played == before+3, "the next page greeted again")
	VoiceBabble.stop(true)
	label.queue_free()
	await process_frame
	lines.append("greet      %d greetings (throttled per voice, new dialogue box only)" % (VoiceBabble.greets_played-before))

# ------------------------------------------------------------------ 6. emotes
func check_emotes() -> void:
	var kinds := {"♪": "note", "!": "exclaim", "…": "dots", "♥": "heart", "✉": "mail", "zz": "sleep",
		"~": "note", "✦": "note", "heart": "heart", "flame": "", "": ""}
	for glyph in kinds:
		check(VoiceBabble.emote_kind(glyph) == kinds[glyph], "emote_kind('%s') = '%s'" % [glyph, VoiceBabble.emote_kind(glyph)])
	var before := VoiceBabble.emotes_played
	check(VoiceBabble.emote(null, "postman", "♪"), "postman ♪ did not play")
	check(not VoiceBabble.emote(null, "kid", "!"), "a second emote within EMOTE_SPACING played")
	await create_timer(VoiceBabble.EMOTE_SPACING+0.05).timeout
	check(not VoiceBabble.emote(null, "postman", "…"), "postman emoted twice within EMOTE_GAP")
	check(not VoiceBabble.emote(null, "kid", "flame"), "an unknown kind played")
	check(VoiceBabble.emote(null, "kid", "!"), "kid ! did not play")
	await create_timer(VoiceBabble.EMOTE_SPACING+0.05).timeout
	# Distance: an app whose player stands at the origin.
	var script := GDScript.new()
	script.source_code = "extends Node3D\nvar player: Node3D\n"
	script.reload()
	var app: Node3D = script.new()
	root.add_child(app)
	var hero := Node3D.new()
	app.add_child(hero)
	app.set("player", hero)
	check(not VoiceBabble.emote(app, "miller", "zz", Vector3(80, 0, 0)), "an emote 80 m away played")
	check(VoiceBabble.emote(app, "miller", "zz", Vector3(4, 0, 0)), "an emote 4 m away did not play")
	await create_timer(VoiceBabble.EMOTE_SPACING+0.05).timeout
	# Every register and kind once (naru high, sora high, moru low, haeru mid, gentleman low, stranger -> villager).
	var ids := ["naru", "sora", "moru", "haeru", "gentleman", "stranger"]
	for i in ids.size():
		check(VoiceBabble.emote(null, ids[i], KINDS[i]), "%s %s emote did not play" % [ids[i], KINDS[i]])
		await create_timer(VoiceBabble.EMOTE_SPACING+0.05).timeout
	app.queue_free()
	await process_frame
	lines.append("emotes     %d played (throttle, unknown kind, distance and every register checked)" % (VoiceBabble.emotes_played-before))
