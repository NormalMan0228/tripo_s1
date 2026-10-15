extends SceneTree
## Door sounds: every room's open/close sounds are a family of takes (DOOR_SOUNDS plus
## <room>_<kind>_<n>.wav, tools/sfx/gen_doors.py). For each one this measures every take
## (length, peak, loudest 120 ms RMS next to the generic fallback) and asks
## Transition.door_stream for two full rounds of the shuffle bag.
## Fails if a room has fewer than MIN_TAKES takes (missing or not imported), a take is
## empty or clips, a take's loudness strays more than 4 dB from the generic door's,
## door_stream returns something that is not one of the room's takes (e.g. the generic
## sound), leaves a take out of a round, plays one take twice in a row, or returns a
## stream that is not the cached one for its path; and if an unknown room does not fall
## back to the one cached generic stream.
##   godot --headless --path game --script res://tests/door_sounds_check.gd
const Transition = preload("res://scripts/transition.gd")
const Town = preload("res://scripts/town.gd")
const SfxBank = preload("res://scripts/sfx_bank.gd")
const MIN_TAKES := 4

func _initialize() -> void: call_deferred("run")

func run() -> void:
	var rooms: Array[String] = []
	for door in Town.DOORS:
		if not String(door.room) in rooms: rooms.append(String(door.room))
	var lines := PackedStringArray()
	var failures := 0
	var reference := {}
	SfxBank.clear()
	for kind in ["open","close"]:
		var generic: AudioStreamWAV = Transition.door_sound(kind)
		reference[kind] = measure(generic)
		lines.append("%-30s %s" % ["generic/"+kind, describe(reference[kind])])
	var total_takes := 0
	for room: String in rooms:
		for kind in ["open","close"]:
			var takes := SfxBank.paths(Transition.DOOR_SOUNDS % [room, kind])
			total_takes += takes.size()
			var problems := PackedStringArray()
			if takes.size() < MIN_TAKES: problems.append("%d takes < %d" % [takes.size(), MIN_TAKES])
			for path in takes:
				var stats := measure(SfxBank.stream(path))
				var issues := PackedStringArray()
				if stats.get("frames", 0) == 0: issues.append("empty")
				if float(stats.get("peak", 0.0)) > 0.995: issues.append("clips")
				if stats.has("rms_db") and absf(float(stats.rms_db)-float(reference[kind].rms_db)) > 4.0:
					issues.append("loudness %.1f dB off" % (float(stats.rms_db)-float(reference[kind].rms_db)))
				failures += issues.size()
				lines.append("%-30s %s%s" % [path.get_file().get_basename(), describe(stats), "" if issues.is_empty() else "  FAIL "+", ".join(issues)])
			# Two rounds of the bag: only the room's own takes, each once per round, never twice in a
			# row, and always the cached stream of that take.
			var seen := {}
			var last := ""
			for i in takes.size()*2:
				var stream := Transition.door_stream(kind, room)
				var path: String = stream.resource_path if stream != null else ""
				if not path in takes:
					problems.append("door_stream returned %s, not one of the room's takes" % ("the generic sound" if path.is_empty() else path))
					break
				if stream != SfxBank.stream(path): problems.append("%s is not the cached stream" % path.get_file())
				if path == last and takes.size() > 1: problems.append("%s twice in a row" % path.get_file())
				last = path
				seen[path] = true
				if i == takes.size()-1 and seen.size() != takes.size(): problems.append("a round left out %d take(s)" % (takes.size()-seen.size()))
			failures += problems.size()
			lines.append("%-30s %d takes%s" % [room+"/"+kind, takes.size(), "" if problems.is_empty() else "  FAIL "+", ".join(problems)])
	for kind in ["open","close"]:
		var stream := Transition.door_stream(kind, "unknown_room")
		var problems := PackedStringArray()
		if stream == null or stream.resource_path != "": problems.append("unknown room did not fall back")
		elif stream != Transition.door_stream(kind, "unknown_room"): problems.append("generic stream is not cached")
		failures += problems.size()
		lines.append("%-30s %s%s" % ["unknown_room/"+kind, describe(measure(stream)) if stream != null else "null", "" if problems.is_empty() else "  FAIL "+", ".join(problems)])
	lines.append("RESULT %s (%d problems, %d rooms, %d takes)" % ["PASS" if failures == 0 else "FAIL", failures, rooms.size(), total_takes])
	var text := "\n".join(lines)
	print(text)
	var out := FileAccess.open(ProjectSettings.globalize_path("res://../artifacts/door-sounds-check.txt"), FileAccess.WRITE)
	if out: out.store_string(text+"\n")
	quit(1 if failures > 0 else 0)

func describe(stats: Dictionary) -> String:
	if stats.has("error"): return String(stats.error)
	return "%5.2fs  %5d Hz  peak %6.1f dBFS  rms120 %6.1f dBFS  %s" % [stats.seconds, stats.rate, linear_to_db(maxf(stats.peak,1e-6)), stats.rms_db, stats.format]

## Decodes 16-bit PCM directly; imported (compressed) WAVs are measured from the
## source file next to them, which is what the importer encoded.
func measure(stream: AudioStream) -> Dictionary:
	var wav := stream as AudioStreamWAV
	if wav == null: return {"error":"not a WAV stream"}
	var data := wav.data
	var rate := wav.mix_rate
	var format := "pcm16"
	if wav.format != AudioStreamWAV.FORMAT_16_BITS:
		format = "imported (%s)" % ["8bit","16bit","ima-adpcm","qoa"][wav.format]
		var source := ProjectSettings.globalize_path(wav.resource_path)
		var raw := FileAccess.get_file_as_bytes(source)
		if raw.size() < 44: return {"error":"cannot read "+source}
		rate = raw.decode_u32(24)
		data = raw.slice(44)
	var frames := data.size()/2
	if frames == 0: return {"frames":0,"seconds":0.0,"rate":rate,"peak":0.0,"rms_db":-120.0,"format":format}
	var peak := 0.0
	var squares := PackedFloat64Array()
	squares.resize(frames+1)
	var total := 0.0
	# Same weighting as tools/make_village_sfx.py: 2nd-order Butterworth high-pass at 150 Hz.
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
	for i in frames:
		var x := data.decode_s16(i*2)/32768.0
		peak = maxf(peak, absf(x))
		var y := b0*x+b1*x1+b0*x2-a1*y1-a2*y2
		x2 = x1
		x1 = x
		y2 = y1
		y1 = y
		total += y*y
		squares[i+1] = total
	var window := mini(frames, int(0.12*rate))
	var loudest := 0.0
	for i in range(window, frames+1, 64):
		loudest = maxf(loudest, squares[i]-squares[i-window])
	return {"frames":frames,"seconds":float(frames)/rate,"rate":rate,"peak":peak,
		"rms_db":linear_to_db(sqrt(loudest/window)+1e-9),"format":format}
