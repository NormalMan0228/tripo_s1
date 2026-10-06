extends Node
## Footsteps and looping ambience beds, synthesized in code (mono 16-bit PCM, nothing imported).
## Streams are built once per session and shared through a static cache.
## Add the node, call setup(), then footstep() on every foot plant and set_ambience()
## whenever the place or the hour changes. Footsteps play on the SFX bus and the
## beds on Ambience (game_settings.gd), so the player's volume sliders reach them.

const GameSettings = preload("res://scripts/game_settings.gd")
const RATE := 22050
const SURFACES := ["grass", "sand", "stone", "wood", "rock", "shallow"]
const VARIATIONS := 4
## Above this speed (m/s) the harder, shorter running steps are used.
const RUN_SPEED := 3.6
const NOISE_SIZE := 1 << 18
const NOISE_MASK := NOISE_SIZE - 1
## Level (dB) of each looping bed when its parameter is 1. "_muffled" copies play indoors.
const BED_DB := {
	"birds": -17.0, "birds_far": -22.0, "insects": -18.0, "coast": -10.0, "wind": -14.0,
	"waterfall": -9.0, "room": -25.0, "coast_muffled": -20.0, "wind_muffled": -24.0,
	"waterfall_muffled": -19.0,
}
## Evens out the takes (hard ground lands a little louder than grass and sand).
const SURFACE_DB := {"grass": -0.5, "sand": -1.5, "stone": -1.0, "wood": -2.5, "rock": -1.5, "shallow": 0.0}

## "step/<surface>/<walk|run>/<n>" and "bed/<name>" -> AudioStreamWAV.
static var cache: Dictionary = {}
## Shared white noise (12 s at 22050 Hz) every generator reads from at its own offset.
static var noise := PackedFloat32Array()

## Master trims, set to sit with sound.gd (effects peak near -19 dBFS, music near -42 dBFS RMS).
var footstep_db := -19.0
var ambience_db := -10.0
## Seconds for a bed to go from silent to full (and back).
var fade := 1.5
var params := {"day": 1.0, "coast": 0.0, "wind": 0.0, "waterfall": 0.0, "indoor": false}
var steps: Array[AudioStreamPlayer] = []
var step_index := 0
var last_variation := {}
var beds := {}
var gains := {}
var targets := {}
var rng := RandomNumberGenerator.new()

func _init() -> void:
	# Fades keep running under a paused tree.
	process_mode = Node.PROCESS_MODE_ALWAYS

func setup() -> void:
	if cache.is_empty(): build_streams()
	if not steps.is_empty(): return
	rng.randomize()
	for i in 4:
		var player := AudioStreamPlayer.new()
		player.bus = GameSettings.BUS_SFX
		add_child(player)
		steps.append(player)
	for key in BED_DB:
		var player := AudioStreamPlayer.new()
		player.bus = GameSettings.BUS_AMBIENCE
		player.stream = cache["bed/" + key]
		add_child(player)
		beds[key] = player
		gains[key] = 0.0
		targets[key] = 0.0
	set_process(false)

func _enter_tree() -> void:
	# Coming back after _exit_tree let go of the streams: beds fade back in.
	for key in beds: beds[key].stream = cache["bed/" + key]
	if targets.values().any(func(level: float) -> bool: return level > 0.0): set_process(true)

func _exit_tree() -> void:
	# Release looping playback before the audio server shuts down.
	for player in steps:
		player.stop()
		player.stream = null
	for key in beds:
		beds[key].stop()
		beds[key].stream = null
		gains[key] = 0.0

## One foot plant. speed in m/s: ~2.8 walking, ~4.5 running; slower is softer.
func footstep(surface: String, speed: float) -> void:
	if steps.is_empty(): setup()
	if not is_inside_tree() or speed <= 0.05: return
	var step := step_choice(surface, speed)
	var player := steps[step_index]
	step_index = (step_index + 1) % steps.size()
	player.stream = step.stream
	player.pitch_scale = step.pitch
	player.volume_db = step.volume_db
	player.play()

## Picks the stream, pitch and level for one step; never the same take twice in a row.
func step_choice(surface: String, speed: float) -> Dictionary:
	if not surface in SURFACES: surface = "grass"
	var pace := clampf((speed - 1.0) / 3.5, 0.0, 1.0)
	var gait := "run" if speed > RUN_SPEED else "walk"
	var slot := surface + gait
	var take := rng.randi() % VARIATIONS
	if take == last_variation.get(slot, -1): take = (take + 1 + rng.randi() % (VARIATIONS - 1)) % VARIATIONS
	last_variation[slot] = take
	return {
		"stream": cache["step/%s/%s/%d" % [surface, gait, take]],
		"pitch": lerpf(0.94, 1.06, pace) * rng.randf_range(0.95, 1.05),
		"volume_db": footstep_db + SURFACE_DB[surface] + lerpf(-9.0, 2.0, pace) + rng.randf_range(-1.5, 1.5),
	}

## Keys (all optional, missing ones keep their last value): day 0..1 (1 = noon), coast, wind,
## waterfall 0..1, indoor (bool or 0..1), fade (seconds for this and later changes).
func set_ambience(next: Dictionary) -> void:
	if beds.is_empty(): setup()
	for key in next:
		if key == "fade": fade = maxf(float(next[key]), 0.0)
		else: params[key] = next[key]
	targets = mix_targets(params)
	set_process(true)

func stop_all() -> void:
	for player in steps: player.stop()
	for key in beds:
		beds[key].stop()
		gains[key] = 0.0
		targets[key] = 0.0
	set_process(false)

## Linear gain (0..1, before BED_DB) of every bed for a set of ambience parameters.
static func mix_targets(p: Dictionary) -> Dictionary:
	var day := clampf(float(p.get("day", 1.0)), 0.0, 1.0)
	var inside_value = p.get("indoor", false)
	var inside: float = (1.0 if inside_value else 0.0) if inside_value is bool else clampf(float(inside_value), 0.0, 1.0)
	# Birds and crickets only reach the room faintly; the low beds come through the walls muffled.
	var walls := lerpf(1.0, 0.06, inside)
	var birds := smoothstep(0.3, 0.7, day) * walls
	var out := {"birds": birds, "birds_far": birds, "insects": (1.0 - smoothstep(0.2, 0.55, day)) * walls, "room": inside}
	for key in ["coast", "wind", "waterfall"]:
		var level := clampf(float(p.get(key, 0.0)), 0.0, 1.0)
		out[key] = level * (1.0 - inside)
		out[key + "_muffled"] = level * inside
	return out

func _process(delta: float) -> void:
	var step := delta / fade if fade > 0.0 else 1.0
	var busy := false
	for key in beds:
		var target: float = targets.get(key, 0.0)
		var gain: float = move_toward(gains[key], target, step)
		gains[key] = gain
		if gain != target: busy = true
		var player: AudioStreamPlayer = beds[key]
		if gain <= 0.0005:
			if player.playing: player.stop()
			continue
		if not player.playing: _start(key)
		player.volume_db = ambience_db + BED_DB[key] + linear_to_db(gain)
	if not busy: set_process(false)

func _start(key: String) -> void:
	var player: AudioStreamPlayer = beds[key]
	var length := player.stream.get_length()
	var at := rng.randf() * length
	# An indoor copy picks up where its open-air twin is, so the swells line up.
	var twin: String = key.trim_suffix("_muffled") if key.ends_with("_muffled") else key + "_muffled"
	if beds.has(twin) and beds[twin].playing: at = fmod(beds[twin].get_playback_position(), length)
	player.play(at)

static func build_streams() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 7071
	var table := PackedFloat32Array()
	table.resize(NOISE_SIZE)
	for i in NOISE_SIZE:
		table[i] = rng.randf() * 2.0 - 1.0
	noise = table
	for surface in SURFACES:
		for take in VARIATIONS:
			cache["step/%s/walk/%d" % [surface, take]] = _wav(_step(surface, rng, rng.randf_range(0.1, 0.35)), RATE, false, 0.2)
			cache["step/%s/run/%d" % [surface, take]] = _wav(_step(surface, rng, rng.randf_range(0.75, 0.95)), RATE, false, 0.2)
	cache["bed/birds"] = _wav(_bed_birds(9.0, 11, false), RATE, true)
	cache["bed/birds_far"] = _wav(_bed_birds(7.0, 29, true), RATE, true)
	cache["bed/insects"] = _wav(_bed_insects(8.0, RATE), RATE, true)
	var coast := _bed_coast(10.0, 16000)
	cache["bed/coast"] = _wav(coast, 16000, true, 0.2)
	cache["bed/coast_muffled"] = _wav(_muffle(coast, 16000, 380.0, 2), 8000, true, 0.2)
	var wind := _bed_wind(8.0, 11025)
	cache["bed/wind"] = _wav(wind, 11025, true, 0.2)
	cache["bed/wind_muffled"] = _wav(_muffle(wind, 11025, 320.0, 1), 11025, true, 0.2)
	var fall := _bed_waterfall(6.0, 16000)
	cache["bed/waterfall"] = _wav(fall, 16000, true, 0.2)
	cache["bed/waterfall_muffled"] = _wav(_muffle(fall, 16000, 380.0, 2), 8000, true, 0.2)
	cache["bed/room"] = _wav(_bed_room(6.0, 8000), 8000, true, 0.2)

## Normalizes to a target loudness (never past -0.7 dBFS) and packs 16-bit PCM.
static func _wav(buf: PackedFloat32Array, rate: int, loop: bool, rms_target := 1.0) -> AudioStreamWAV:
	var peak := 0.0001
	var energy := 0.0
	for v: float in buf:
		peak = maxf(peak, absf(v))
		energy += v * v
	var rms := sqrt(energy / maxf(buf.size(), 1.0))
	var scale := minf(0.92 / peak, rms_target / maxf(rms, 0.000001)) * 32767.0
	var data := PackedByteArray()
	data.resize(buf.size() * 2)
	for i in buf.size():
		var v := buf[i]
		if v != 0.0: data.encode_s16(i * 2, int(v * scale))
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = rate
	stream.data = data
	if loop:
		stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
		stream.loop_begin = 0
		stream.loop_end = buf.size()
	return stream

static func _pole(hz: float, rate := RATE) -> float:
	return 1.0 - exp(-TAU * hz / rate)

## The generated tail past n crossfades (equal power) into the head, so the loop has no seam.
static func _fold(buf: PackedFloat32Array, n: int, overlap: int) -> PackedFloat32Array:
	for i in overlap:
		var x := float(i) / overlap * PI * 0.5
		buf[i] = buf[i] * sin(x) + buf[n + i] * cos(x)
	buf.resize(n)
	return buf

## Two-pole low-pass run around the loop (primed with its tail), kept every `every` samples.
static func _muffle(buf: PackedFloat32Array, rate: int, cutoff: float, every: int) -> PackedFloat32Array:
	var a := _pole(cutoff, rate)
	var n := buf.size()
	var l1 := 0.0
	var l2 := 0.0
	for i in range(n - rate / 2, n):
		l1 += a * (buf[i] - l1)
		l2 += a * (l1 - l2)
	var out := PackedFloat32Array()
	out.resize(n / every)
	for i in out.size() * every:
		l1 += a * (buf[i] - l1)
		l2 += a * (l1 - l2)
		if i % every == 0: out[i / every] = l2
	return out

# --- Footsteps -------------------------------------------------------------------------------

## hard 0..1: walking takes are soft and long, running takes snap harder, brighter and shorter.
static func _step(surface: String, rng: RandomNumberGenerator, hard: float) -> PackedFloat32Array:
	var roll := rng.randf_range(0.05, 0.08) * lerpf(1.0, 0.75, hard)
	match surface:
		"grass":
			return _scuff(rng, {"length": lerpf(0.26, 0.19, hard), "attack": lerpf(0.014, 0.005, hard),
				"decay": lerpf(0.05, 0.034, hard), "roll": roll, "roll_amp": rng.randf_range(0.45, 0.7),
				"lo": rng.randf_range(800.0, 1100.0), "hi": lerpf(4500.0, 7000.0, hard), "grain": 64, "depth": 0.8,
				"crunch": 0.15, "crunch_hz": rng.randf_range(2800.0, 3600.0), "crunch_amp": 0.5,
				"thump": rng.randf_range(60.0, 80.0), "thump_amp": lerpf(0.2, 0.3, hard)})
		"sand":
			return _scuff(rng, {"length": lerpf(0.3, 0.22, hard), "attack": lerpf(0.022, 0.009, hard),
				"decay": lerpf(0.065, 0.045, hard), "roll": roll * 1.2, "roll_amp": rng.randf_range(0.7, 0.9),
				"lo": 250.0, "hi": lerpf(1500.0, 2600.0, hard), "grain": 24, "depth": 0.95,
				"thump": rng.randf_range(50.0, 62.0), "thump_amp": lerpf(0.22, 0.32, hard)})
		"stone":
			return _scuff(rng, {"length": lerpf(0.24, 0.18, hard), "attack": 0.003,
				"decay": lerpf(0.042, 0.03, hard), "roll": roll * 0.8, "roll_amp": rng.randf_range(0.5, 0.7),
				"lo": 700.0, "hi": lerpf(3000.0, 5000.0, hard), "grain": 96, "depth": 0.9,
				"crunch": 1.0, "crunch_hz": rng.randf_range(2300.0, 2900.0) + 700.0 * hard, "crunch_amp": lerpf(0.9, 1.3, hard),
				"thump": rng.randf_range(85.0, 110.0), "thump_amp": lerpf(0.5, 0.45, hard)})
		"wood":
			var plank := rng.randf_range(115.0, 160.0)
			return _knock(rng, {"length": lerpf(0.26, 0.2, hard), "click": lerpf(2500.0, 5000.0, hard),
				"roll": roll, "roll_amp": rng.randf_range(0.4, 0.6), "direct": lerpf(0.3, 0.6, hard),
				"grit": lerpf(0.08, 0.16, hard), "decay_scale": lerpf(1.0, 0.8, hard), "modes": [[plank, lerpf(0.09, 0.06, hard), lerpf(1.0, 0.6, hard)],
				[plank * rng.randf_range(2.2, 2.5), 0.06, 0.7], [rng.randf_range(560.0, 760.0), 0.035, lerpf(0.5, 0.9, hard)],
				[rng.randf_range(1500.0, 1900.0), 0.018, lerpf(0.27, 0.54, hard)]]})
		"rock":
			var ring := rng.randf_range(750.0, 1050.0)
			return _knock(rng, {"length": lerpf(0.17, 0.13, hard), "click": lerpf(4000.0, 8000.0, hard),
				"roll": roll * 0.8, "roll_amp": rng.randf_range(0.35, 0.5), "direct": lerpf(0.6, 1.1, hard),
				"grit": lerpf(0.28, 0.45, hard), "decay_scale": lerpf(1.0, 0.85, hard), "modes": [[rng.randf_range(80.0, 100.0), 0.03, lerpf(1.3, 0.9, hard)],
				[ring, 0.028, 0.5], [ring * 1.73, 0.02, lerpf(0.36, 0.56, hard)], [ring * 2.61, 0.012, lerpf(0.27, 0.42, hard)]]})
		"shallow":
			var buf := _scuff(rng, {"length": lerpf(0.42, 0.33, hard), "attack": lerpf(0.01, 0.005, hard),
				"decay": lerpf(0.11, 0.08, hard), "roll": rng.randf_range(0.1, 0.13), "roll_amp": 0.5,
				"lo": 450.0, "hi": lerpf(3200.0, 5500.0, hard), "grain": 40, "depth": 0.9,
				"thump": rng.randf_range(85.0, 100.0), "thump_amp": lerpf(0.4, 0.25, hard)})
			_bubbles(buf, rng, rng.randi_range(4, 7), lerpf(0.25, 0.18, hard))
			return buf
	return PackedFloat32Array()

## Grainy band-limited noise for a heel and a softer toe contact over a low thump;
## "crunch" adds sparse ringing grit clicks (gravel, dry grass).
static func _scuff(rng: RandomNumberGenerator, p: Dictionary) -> PackedFloat32Array:
	var n := int(float(p["length"]) * RATE)
	var buf := PackedFloat32Array()
	buf.resize(n)
	var nz := noise
	var o := rng.randi() & NOISE_MASK
	var ka := exp(-1.0 / (float(p["attack"]) * RATE))
	var kd := exp(-1.0 / (float(p["decay"]) * RATE))
	var roll := int(float(p["roll"]) * RATE)
	var top_a := _pole(p["hi"])
	var base_a := _pole(p["lo"])
	var grain_len: int = p["grain"]
	var depth: float = p["depth"]
	var crunch := float(p.get("crunch", 0.0)) * 0.03
	var cw := TAU * float(p.get("crunch_hz", 3000.0)) / RATE
	var cr := exp(-1.0 / (0.0022 * RATE))
	var cc1 := 2.0 * cr * cos(cw)
	var cc2 := cr * cr
	var cg := sin(cw) * float(p.get("crunch_amp", 0.0))
	var thump_w := TAU * float(p["thump"]) / RATE
	var thump: float = p["thump_amp"]
	var thump_k := exp(-1.0 / (0.025 * RATE))
	var a1 := 1.0
	var d1 := 1.0
	var a2 := 1.0
	var d2: float = p["roll_amp"]
	var top := 0.0
	var base := 0.0
	var grain := 1.0
	var grain_to := 1.0
	var y1 := 0.0
	var y2 := 0.0
	for i in n:
		a1 *= ka
		d1 *= kd
		var env := (1.0 - a1) * d1
		if i >= roll:
			a2 *= ka
			d2 *= kd
			env += (1.0 - a2) * d2
		if i % grain_len == 0:
			var g := nz[(o + i + 65537) & NOISE_MASK]
			grain_to = 1.0 - depth + depth * 2.4 * g * g
		grain += 0.25 * (grain_to - grain)
		var x := nz[(o + i) & NOISE_MASK]
		top += top_a * (x - top)
		base += base_a * (top - base)
		var u := nz[(o + 3 * i + 131071) & NOISE_MASK]
		var y := cc1 * y1 - cc2 * y2
		if absf(u) > 1.0 - crunch * env: y += cg * u
		y2 = y1
		y1 = y
		thump *= thump_k
		buf[i] = (top - base) * env * grain + y + sin(thump_w * i) * thump * (1.0 - a1)
	return buf

## A heel and toe tap ringing four resonant modes (planks, stone) plus a little grit.
static func _knock(rng: RandomNumberGenerator, p: Dictionary) -> PackedFloat32Array:
	var n := int(float(p["length"]) * RATE)
	var buf := PackedFloat32Array()
	buf.resize(n)
	var nz := noise
	var o := rng.randi() & NOISE_MASK
	var scale: float = p["decay_scale"]
	var c := PackedFloat32Array()
	for mode in p["modes"]:
		var r := exp(-1.0 / (float(mode[1]) * scale * RATE))
		var w := TAU * float(mode[0]) / RATE
		c.append(2.0 * r * cos(w))
		c.append(r * r)
		c.append(float(mode[2]) * sin(w))
	var a1 := c[0]; var b1 := c[1]; var g1 := c[2]
	var a2 := c[3]; var b2 := c[4]; var g2 := c[5]
	var a3 := c[6]; var b3 := c[7]; var g3 := c[8]
	var a4 := c[9]; var b4 := c[10]; var g4 := c[11]
	var p1 := 0.0; var q1 := 0.0; var p2 := 0.0; var q2 := 0.0
	var p3 := 0.0; var q3 := 0.0; var p4 := 0.0; var q4 := 0.0
	var click_k := exp(-1.0 / (0.0018 * RATE))
	var grit_k := exp(-1.0 / (0.03 * RATE))
	var click_a := _pole(p["click"])
	var roll := int(float(p["roll"]) * RATE)
	var direct: float = p["direct"]
	var grit: float = p["grit"]
	var e1 := 1.0
	var e2: float = p["roll_amp"]
	var eg := grit
	var xl := 0.0
	var gl := 0.0
	for i in n:
		var e := e1
		e1 *= click_k
		if i >= roll:
			e += e2
			e2 *= click_k
		var x := nz[(o + i) & NOISE_MASK] * e
		xl += click_a * (x - xl)
		var m1 := a1 * p1 - b1 * q1 + g1 * xl
		q1 = p1
		p1 = m1
		var m2 := a2 * p2 - b2 * q2 + g2 * xl
		q2 = p2
		p2 = m2
		var m3 := a3 * p3 - b3 * q3 + g3 * xl
		q3 = p3
		p3 = m3
		var m4 := a4 * p4 - b4 * q4 + g4 * xl
		q4 = p4
		p4 = m4
		var s := nz[(o + i + 123457) & NOISE_MASK]
		gl += 0.3 * (s - gl)
		eg *= grit_k
		buf[i] = m1 + m2 + m3 + m4 + xl * direct + (s - gl) * eg
	return buf

## Rising bubble blips after a splash.
static func _bubbles(buf: PackedFloat32Array, rng: RandomNumberGenerator, count: int, spread: float) -> void:
	for b in count:
		var start := int(rng.randf_range(0.01, spread) * RATE)
		var f0 := rng.randf_range(450.0, 1300.0)
		var length := int(rng.randf_range(0.02, 0.05) * RATE)
		var amp := rng.randf_range(0.15, 0.4)
		var phase := 0.0
		for j in mini(length, buf.size() - start):
			var u := float(j) / length
			phase += TAU * f0 * (1.0 + 0.9 * u) / RATE
			buf[start + j] += sin(phase) * amp * (1.0 - u) * minf(u * 20.0, 1.0)

# --- Ambience beds ---------------------------------------------------------------------------

## Sparse bird calls written around the loop (wrapping), so the seam needs no crossfade.
## Each resident bird repeats its own call with small changes; far birds are quieter and duller.
static func _bed_birds(seconds: float, seed_value: int, far: bool) -> PackedFloat32Array:
	var buf := PackedFloat32Array()
	buf.resize(int(seconds * RATE))
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var birds := []
	for b in 3:
		birds.append({"kind": (seed_value + b * 3) % 4, "pitch": rng.randf_range(0.88, 1.12), "amp": rng.randf_range(0.6, 1.0)})
	var t := rng.randf_range(0.2, 0.8)
	while t < seconds - 0.3:
		var bird: Dictionary = birds[rng.randi() % birds.size()]
		t += _phrase(buf, rng, int(t * RATE), bird, 0.4 if far else 1.0)
		t += rng.randf_range(0.5, 1.6) if far else rng.randf_range(0.7, 2.2)
	return buf

static func _phrase(buf: PackedFloat32Array, rng: RandomNumberGenerator, start: int, bird: Dictionary, soft: float) -> float:
	var p: float = bird.pitch * rng.randf_range(0.97, 1.03)
	var amp: float = bird.amp * rng.randf_range(0.75, 1.0)
	var t := 0.0
	match int(bird.kind):
		0: # descending "tee-tee-tew-tew"
			for k in rng.randi_range(3, 6):
				var f := (4300.0 - k * 220.0) * p
				_chirp(buf, start + int(t * RATE), 0.075, f, f - 900.0 * p, 0.0, 0.0, amp * (1.0 - k * 0.08), soft)
				t += rng.randf_range(0.11, 0.14)
		1: # quick rising chips
			for k in rng.randi_range(2, 4):
				_chirp(buf, start + int(t * RATE), 0.04, 2300.0 * p, 3900.0 * p, 0.0, 0.0, amp, soft)
				t += rng.randf_range(0.07, 0.1)
		2: # fast trill
			for k in rng.randi_range(8, 14):
				_chirp(buf, start + int(t * RATE), 0.022, 5000.0 * p, 4400.0 * p, 0.0, 0.0, amp * 0.6, soft)
				t += 0.034
		_: # sweet two-note whistle with vibrato
			_chirp(buf, start, 0.22, 2500.0 * p, 2700.0 * p, 9.0, 70.0, amp * 0.75, soft)
			t += 0.3
			_chirp(buf, start + int(t * RATE), 0.28, 3100.0 * p, 2800.0 * p, 9.0, 80.0, amp * 0.75, soft)
			t += 0.3
	return t

static func _chirp(buf: PackedFloat32Array, start: int, seconds: float, f0: float, f1: float, vib_hz: float, vib: float, amp: float, soft: float) -> void:
	var n := buf.size()
	var count := int(seconds * RATE)
	var phase := 0.0
	var lp := 0.0
	var vib_w := TAU * vib_hz / RATE
	for j in count:
		var u := float(j) / count
		phase += TAU * (f0 + (f1 - f0) * u + vib * sin(vib_w * j)) / RATE
		var e := sin(PI * u)
		lp += soft * ((sin(phase) + 0.12 * sin(2.0 * phase)) * e * e * amp - lp)
		buf[(start + j) % n] += lp
	# Let a dulled (far) chirp's filter tail die out.
	if soft < 1.0:
		for j in 64:
			lp *= 1.0 - soft
			buf[(start + count + j) % n] += lp

## A faint shimmering chorus (noise rung through two narrow resonators, pulsing) under three crickets.
static func _bed_insects(seconds: float, rate: int) -> PackedFloat32Array:
	var n := int(seconds * rate)
	var overlap := int(0.5 * rate)
	var buf := PackedFloat32Array()
	buf.resize(n + overlap)
	var nz := noise
	var rng := RandomNumberGenerator.new()
	rng.seed = 4242
	var r := exp(-PI * 120.0 / rate)
	var c1 := 2.0 * r * cos(TAU * 4800.0 / rate)
	var c2 := 2.0 * r * cos(TAU * 5650.0 / rate)
	var rr := r * r
	# Pulse and swell rates divide the loop length, so they repeat exactly.
	var pa := TAU * roundf(14.0 * seconds) / seconds / rate
	var pb := TAU * roundf(17.5 * seconds) / seconds / rate
	var sw := TAU / seconds / rate
	var y1 := 0.0; var y2 := 0.0; var z1 := 0.0; var z2 := 0.0
	for i in n + overlap:
		var x := nz[(i + 200003) & NOISE_MASK]
		var y := c1 * y1 - rr * y2 + x
		y2 = y1
		y1 = y
		var z := c2 * z1 - rr * z2 + nz[(i + 17) & NOISE_MASK]
		z2 = z1
		z1 = z
		var a := sin(pa * i)
		var b := sin(pb * i + 1.3)
		var swell := 0.7 + 0.3 * sin(sw * i)
		buf[i] = (y * a * a + z * b * b * (1.3 - swell)) * swell * 0.006
	buf = _fold(buf, n, overlap)
	for cricket in 3:
		var w := TAU * rng.randf_range(4200.0, 5000.0) / rate
		var count := maxi(1, roundi(seconds / rng.randf_range(0.38, 0.62)))
		var interval := seconds / count
		var pulses := rng.randi_range(3, 4)
		var amp: float = [1.0, 0.55, 0.3][cricket]
		var plen := int(0.017 * rate)
		var gap := int(0.03 * rate)
		var offset := rng.randf() * interval
		for k in count:
			if rng.randf() < 0.08: continue
			var start := int((offset + k * interval + rng.randf_range(-0.015, 0.015)) * rate)
			var loud := amp * rng.randf_range(0.8, 1.0)
			for pulse in pulses:
				var s0 := start + pulse * gap
				for j in plen:
					var e := sin(PI * j / plen)
					buf[posmod(s0 + j, n)] += sin(w * j) * e * loud * 0.4
	return buf

## Two swells per loop (the second smaller): a low rumble builds, breaks into fizzing hiss and
## washes back duller, over a steady distant surf.
static func _bed_coast(seconds: float, rate: int) -> PackedFloat32Array:
	var n := int(seconds * rate)
	var overlap := int(0.6 * rate)
	var buf := PackedFloat32Array()
	buf.resize(n + overlap)
	var nz := noise
	var split := seconds * 0.56
	var floor_a := _pole(900.0, rate)
	var floor_h := _pole(60.0, rate)
	var hiss_h := _pole(700.0, rate)
	var rumble_a := 0.0
	var hiss_a := 0.0
	var body := 0.0
	var crash := 0.0
	var r1 := 0.0; var r2 := 0.0; var h1 := 0.0; var h2 := 0.0; var f1 := 0.0; var f2 := 0.0
	var grain := 1.0
	var grain_to := 1.0
	for i in n + overlap:
		if (i & 31) == 0:
			var t := fmod(float(i) / rate, seconds)
			var p := t / split if t < split else (t - split) / (seconds - split)
			var size := 1.0 if t < split else 0.7
			var shape := smoothstep(0.0, 0.62, p) if p < 0.62 else 1.0 - smoothstep(0.62, 1.0, p)
			body = 0.3 + 0.7 * shape * size
			var k := maxf(p - 0.56, 0.0) / 0.44
			crash = (1.0 - exp(-k * 6.0)) * exp(-k * 1.2) * (1.0 - k) * size
			rumble_a = _pole(220.0 + 380.0 * shape * size, rate)
			hiss_a = _pole(1400.0 + 3400.0 * crash, rate)
		r1 += rumble_a * (nz[i & NOISE_MASK] - r1)
		r2 += rumble_a * (r1 - r2)
		h1 += hiss_a * (nz[(i + 90001) & NOISE_MASK] - h1)
		h2 += hiss_h * (h1 - h2)
		if i % 40 == 0:
			var g := nz[(i * 5 + 170003) & NOISE_MASK]
			grain_to = 0.45 + 1.6 * g * g
		grain += 0.2 * (grain_to - grain)
		f1 += floor_a * (nz[(i + 50021) & NOISE_MASK] - f1)
		f2 += floor_h * (f1 - f2)
		buf[i] = r2 * body * 2.6 + (h1 - h2) * crash * grain * 3.2 + (f1 - f2) * 0.4
	return _fold(buf, n, overlap)

## Gusting low-passed noise with a faint whistle at the gust peaks; gusts repeat with the loop.
static func _bed_wind(seconds: float, rate: int) -> PackedFloat32Array:
	var n := int(seconds * rate)
	var overlap := int(0.8 * rate)
	var buf := PackedFloat32Array()
	buf.resize(n + overlap)
	var nz := noise
	var gust := 0.0
	var lp_a := 0.0
	var wf := 0.0
	var whistle := 0.0
	var q := 0.07
	var l1 := 0.0; var l2 := 0.0; var low := 0.0; var band := 0.0
	for i in n + overlap:
		if (i & 15) == 0:
			var t := TAU * float(i) / rate / seconds
			gust = 0.6 + 0.18 * sin(t + 0.4) + 0.12 * sin(2.0 * t + 2.2) + 0.07 * sin(3.0 * t + 4.1)
			lp_a = _pole(150.0 + 650.0 * gust, rate)
			wf = 2.0 * sin(PI * (420.0 + 380.0 * gust) / rate)
			whistle = maxf(gust - 0.6, 0.0) * 0.12
		var x := nz[(i + 31337) & NOISE_MASK]
		l1 += lp_a * (x - l1)
		l2 += lp_a * (l1 - l2)
		low += wf * band
		band += wf * (x - low - q * band)
		buf[i] = l2 * (0.15 + gust * gust) * 4.0 + band * whistle
	return _fold(buf, n, overlap)

## Dense rushing water: deep rumble, a splashy mid band and hiss, gently surging.
static func _bed_waterfall(seconds: float, rate: int) -> PackedFloat32Array:
	var n := int(seconds * rate)
	var overlap := int(0.5 * rate)
	var buf := PackedFloat32Array()
	buf.resize(n + overlap)
	var nz := noise
	var ra := _pole(170.0, rate)
	var ba := _pole(2000.0, rate)
	var bb := _pole(450.0, rate)
	var ha := _pole(3000.0, rate)
	var r1 := 0.0; var r2 := 0.0; var b1 := 0.0; var b2 := 0.0; var h1 := 0.0
	var surge := 1.0
	var grain := 1.0
	var grain_to := 1.0
	for i in n + overlap:
		if (i & 31) == 0:
			var t := TAU * float(i) / rate / seconds
			surge = 1.0 + 0.1 * sin(t + 0.7) + 0.06 * sin(3.0 * t + 2.1)
		if i % 90 == 0:
			var g := nz[(i * 3 + 60013) & NOISE_MASK]
			grain_to = 0.6 + 1.2 * g * g
		grain += 0.05 * (grain_to - grain)
		r1 += ra * (nz[(i + 7777) & NOISE_MASK] - r1)
		r2 += ra * (r1 - r2)
		var y := nz[(i + 140009) & NOISE_MASK]
		b1 += ba * (y - b1)
		b2 += bb * (y - b2)
		var z := nz[(i + 220013) & NOISE_MASK]
		h1 += ha * (z - h1)
		buf[i] = (r2 * 3.0 + (b1 - b2) * 1.6 * grain + (z - h1) * 0.45 * (1.6 - 0.5 * grain)) * surge
	return _fold(buf, n, overlap)

## Quiet room air: a soft low rumble with a touch of mid, slowly drifting.
static func _bed_room(seconds: float, rate: int) -> PackedFloat32Array:
	var n := int(seconds * rate)
	var overlap := int(0.5 * rate)
	var buf := PackedFloat32Array()
	buf.resize(n + overlap)
	var nz := noise
	var la := _pole(110.0, rate)
	var ma := _pole(700.0, rate)
	var mb := _pole(250.0, rate)
	var l1 := 0.0; var l2 := 0.0; var m1 := 0.0; var m2 := 0.0
	var sw := TAU / seconds / rate
	for i in n + overlap:
		l1 += la * (nz[(i + 99991) & NOISE_MASK] - l1)
		l2 += la * (l1 - l2)
		var y := nz[(i + 180001) & NOISE_MASK]
		m1 += ma * (y - m1)
		m2 += mb * (y - m2)
		buf[i] = (l2 * 4.0 + (m1 - m2) * 0.2) * (1.0 + 0.12 * sin(sw * i))
	return _fold(buf, n, overlap)
