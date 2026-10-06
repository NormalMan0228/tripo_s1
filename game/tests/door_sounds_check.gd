extends SceneTree
## Door sounds: builds every room's open/close stream through Transition.door_stream
## and reports length, peak and loudest 120 ms RMS next to the generic fallback.
## Fails if a room falls back to the generic sound, a stream is empty or clips,
## or its loudness strays more than 4 dB from the generic door's.
##   godot --headless --path game --script res://tests/door_sounds_check.gd
const Transition = preload("res://scripts/transition.gd")
const Town = preload("res://scripts/town.gd")

func _initialize() -> void: call_deferred("run")

func run() -> void:
	var rooms: Array[String] = []
	for door in Town.DOORS: rooms.append(String(door.room))
	var lines := PackedStringArray()
	var failures := 0
	var reference := {}
	for kind in ["open","close"]:
		var generic: AudioStreamWAV = Transition.door_sound(kind)
		reference[kind] = measure(generic)
		lines.append("%-26s %s" % ["generic/"+kind, describe(reference[kind])])
	for room: String in rooms+["unknown_room"]:
		for kind in ["open","close"]:
			var stream := Transition.door_stream(kind, room)
			var fallback: bool = room == "unknown_room"
			var path := Transition.DOOR_SOUNDS % [room, kind]
			var own: bool = not fallback and stream.resource_path == path
			var stats := measure(stream)
			var problems := PackedStringArray()
			if fallback and stream.resource_path != "": problems.append("unknown room did not fall back")
			if not fallback and not own: problems.append("uses the generic sound")
			if stats.get("frames", 0) == 0: problems.append("empty")
			if float(stats.get("peak", 0.0)) > 0.995: problems.append("clips")
			if not fallback and stats.has("rms_db") and absf(float(stats.rms_db)-float(reference[kind].rms_db)) > 4.0:
				problems.append("loudness %.1f dB off" % (float(stats.rms_db)-float(reference[kind].rms_db)))
			failures += problems.size()
			lines.append("%-26s %s%s" % [room+"/"+kind, describe(stats), "" if problems.is_empty() else "  FAIL "+", ".join(problems)])
	# Cached: asking again returns the very same stream.
	if Transition.door_stream("open","01_cafe") != Transition.door_stream("open","01_cafe"):
		failures += 1
		lines.append("FAIL door streams are not cached")
	lines.append("RESULT %s (%d problems, %d rooms)" % ["PASS" if failures == 0 else "FAIL", failures, rooms.size()])
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
