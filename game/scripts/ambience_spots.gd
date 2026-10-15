extends Node
## Random one-shots over the ambience beds (a WorldAudio child, world_audio.gd): bird calls, gulls,
## wave crashes and slaps, wind gusts, crickets, owls, frogs, a rooster at dawn, the windmill
## creaking and a far bell (by day, and once at dusk, softer and lower). Takes:
## res://assets/sfx/ambience/spots/<kind>_<n>.wav (tools/sfx/make_world_ambience.py), picked
## through sfx_bank.gd's shuffle bag.
## WorldAudio.set_ambience() hands over its bed gains (mix_targets) and parameters; weights()
## turns them into how lively each kind is (0 = silent: daytime birds at night, gulls inland, any
## of it indoors). Each kind waits a random gap (longer when its weight is low), then plays one
## take at a random place around the hero: a panned AudioStreamPlayer3D (attenuation off,
## WorldAudio.distance_db from the reference distance) when there is a camera, else a flat
## player; sea and wind sounds are never placed (the sea's side is not known here) and get
## louder with their weight instead. Everything plays on the Ambience bus.
## Counters for tests: fired, fired_by[kind], last_path[kind] (scheduled calls); dusk_count.

const GameSettings = preload("res://scripts/game_settings.gd")
const SfxBank = preload("res://scripts/sfx_bank.gd")
const DIR := "ambience/spots/"
## gap: [min, max] s between two calls at full weight; db: level at `ref` m (with
## WorldAudio.ambience_db on top); pitch: +- jitter; dist / height: where it is placed around
## the hero (empty: not placed, flat); limit: most calls per dawn / per stretch (0 = no limit).
## Birds call often and close: they sit under the hero's walking steps, not above them.
const KINDS := {
	"bird": {"gap": [2.5, 9.0], "db": -14.5, "pitch": 0.06, "dist": [6.0, 26.0], "height": [2.0, 7.0], "ref": 10.0},
	"gull": {"gap": [8.0, 24.0], "db": -12.0, "pitch": 0.05, "dist": [14.0, 40.0], "height": [6.0, 14.0], "ref": 18.0},
	"wave_crash": {"gap": [5.0, 13.0], "db": -9.0, "pitch": 0.04, "dist": [], "height": [], "ref": 1.0},
	"wave_slap": {"gap": [4.0, 14.0], "db": -14.0, "pitch": 0.06, "dist": [], "height": [], "ref": 1.0},
	"gust": {"gap": [9.0, 26.0], "db": -13.0, "pitch": 0.05, "dist": [], "height": [], "ref": 1.0},
	"cricket": {"gap": [1.2, 5.0], "db": -17.0, "pitch": 0.03, "dist": [3.0, 12.0], "height": [0.0, 0.4], "ref": 5.0},
	"owl": {"gap": [14.0, 40.0], "db": -15.0, "pitch": 0.04, "dist": [14.0, 36.0], "height": [5.0, 11.0], "ref": 16.0},
	"frog": {"gap": [3.5, 12.0], "db": -17.0, "pitch": 0.06, "dist": [5.0, 22.0], "height": [0.0, 0.2], "ref": 8.0},
	"rooster": {"gap": [18.0, 45.0], "db": -13.0, "pitch": 0.03, "dist": [30.0, 55.0], "height": [1.0, 2.0], "ref": 35.0, "limit": 3},
	"windmill_creak": {"gap": [7.0, 18.0], "db": -16.0, "pitch": 0.05, "dist": [18.0, 40.0], "height": [4.0, 9.0], "ref": 20.0},
	"distant_bell": {"gap": [70.0, 170.0], "db": -16.0, "pitch": 0.02, "dist": [], "height": [], "ref": 1.0, "limit": 2},
}
const VOICES_3D := 6
const VOICES_FLAT := 3
## Dusk: once an evening, the far bell (DUSK_KIND takes, softer and a little lower) as the daylight
## falls through DUSK_DAY, outdoors in the village. The fall itself marks the evening (the real-time
## clock moves the daylight too slowly for day_trend); a jump of more than DUSK_STEP (a scene change,
## the survival night switch) rings nothing. Daylight above DUSK_REARM arms it for the next evening.
const DUSK_KIND := "distant_bell"
const DUSK_DAY := 0.4
const DUSK_DB := -18.0
const DUSK_PITCH := 0.89
const DUSK_STEP := 0.15
const DUSK_REARM := 0.6

## The WorldAudio this belongs to (ambience_db, listener()).
var audio: Node
var levels := {}
var params := {}
var weight := {}
var wait := {}
var dawn := 0.0
var last_day := -1.0
var day_trend := 0.0
var limited := {}
var fired := 0
var fired_by := {}
var last_path := {}
## This evening's dusk bell has rung (or its moment passed indoors); dusk bells so far (tests).
var dusk_rung := false
var dusk_count := 0
var voices3d: Array[AudioStreamPlayer3D] = []
var voices_flat: Array[AudioStreamPlayer] = []
var rng := RandomNumberGenerator.new()

func _init() -> void:
	rng.randomize()
	for kind in KINDS: wait[kind] = _gap(kind, 1.0) * rng.randf_range(0.3, 1.0)
	set_process(false)

## New bed gains (WorldAudio.mix_targets) and parameters: recomputes every kind's weight.
func update(targets: Dictionary, p: Dictionary) -> void:
	levels = targets
	params = p
	var day := clampf(float(p.get("day", 1.0)), 0.0, 1.0)
	if last_day >= 0.0: day_trend = lerpf(day_trend, signf(day - last_day), 0.5) if absf(day - last_day) > 0.0005 else day_trend
	_dusk(last_day, day, p)
	last_day = day
	if p.has("hour") and float(p.hour) >= 0.0:
		var hour := float(p.hour)
		dawn = 1.0 if hour >= 5.0 and hour <= 7.5 else 0.0
	else:
		dawn = 1.0 if day_trend > 0.2 and day > 0.25 and day < 0.65 else 0.0
	if dawn <= 0.0: limited.clear()
	weight = weights(levels, params, dawn, windmill_near())
	var any := false
	for kind in weight:
		if weight[kind] > 0.02: any = true
	set_process(any)

## The dusk bell when the daylight has just fallen through DUSK_DAY (from `before` to `day`, a small
## step), outdoors in the village; at most once until the daylight is back over DUSK_REARM.
func _dusk(before: float, day: float, p: Dictionary) -> void:
	if day > DUSK_REARM: dusk_rung = false
	if dusk_rung or before < 0.0 or before <= DUSK_DAY or day > DUSK_DAY or before - day > DUSK_STEP: return
	dusk_rung = true
	var inside_value = p.get("indoor", false)
	var inside: bool = bool(inside_value) if inside_value is bool else float(inside_value) >= 0.5
	if inside or str(p.get("zone", "")) not in ["", "village"]: return
	ring_dusk()

## Rings the dusk bell now: one far bell take on a flat voice. False when nothing played.
func ring_dusk() -> bool:
	var path := SfxBank.pick_path(DIR + DUSK_KIND)
	var stream := SfxBank.stream(path) if not path.is_empty() else null
	var flat := _free_flat()
	if stream == null or flat == null: return false
	var trim: float = audio.get("ambience_db") if audio != null else -10.0
	flat.stream = stream
	flat.pitch_scale = DUSK_PITCH * SfxBank.pitch(0.02)
	flat.volume_db = trim + DUSK_DB + SfxBank.db(1.0)
	flat.play()
	dusk_count += 1
	return true

## How lively each kind is (0..1) for bed gains `levels` (mix_targets), parameters `p`, dawn 0/1 and
## how near the windmill is (0..1, 1 when unknown).
static func weights(levels: Dictionary, p: Dictionary, dawn_now := 0.0, windmill := 1.0) -> Dictionary:
	var inside_value = p.get("indoor", false)
	var inside: float = (1.0 if inside_value else 0.0) if inside_value is bool else clampf(float(inside_value), 0.0, 1.0)
	var outside := 1.0 - inside
	var zone := str(p.get("zone", ""))
	var village := 1.0 if zone in ["", "village"] else 0.0
	var day := clampf(float(p.get("day", 1.0)), 0.0, 1.0)
	var coast := clampf(float(p.get("coast", 0.0)), 0.0, 1.0) * outside
	var night: float = levels.get("night", 0.0)
	var night_zone: float = {"forest": 1.0, "frost": 0.3, "quarry": 0.3, "ember": 0.0}.get(zone, 0.6)
	return {
		"bird": clampf(float(levels.get("birds", 0.0)), 0.0, 1.0) * outside,
		"gull": coast * smoothstep(0.3, 0.7, day) * village,
		"wave_crash": smoothstep(0.25, 0.9, coast),
		"wave_slap": smoothstep(0.45, 1.0, coast),
		"gust": clampf(float(levels.get("wind", 0.0)) * 1.3, 0.0, 1.0),
		"cricket": clampf(maxf(night, 0.6 * float(levels.get("insects", 0.0))), 0.0, 1.0) * outside,
		"owl": night * night_zone * outside,
		"frog": night * ({"forest": 0.7, "": 1.0, "village": 1.0}.get(zone, 0.0) as float) * (0.5 + 0.5 * maxf(coast, float(p.get("waterfall", 0.0)))) * outside,
		"rooster": dawn_now * village * outside,
		"windmill_creak": village * outside * (0.35 + 0.65 * clampf(float(p.get("wind", 0.0)), 0.0, 1.0)) * windmill,
		"distant_bell": village * outside * smoothstep(0.5, 0.8, day),
	}

## 0..1 from the windmill_at parameter (1 within 15 m, 0 past 60 m); 1 when it was not given.
func windmill_near() -> float:
	var at = params.get("windmill_at")
	if not at is Vector3 or audio == null: return 1.0
	var ears: Vector3 = audio.listener()
	if ears == Vector3.INF: return 1.0
	return 1.0 - smoothstep(15.0, 60.0, ears.distance_to(at))

func _process(delta: float) -> void:
	for kind in KINDS:
		var w: float = weight.get(kind, 0.0)
		if w <= 0.02: continue
		wait[kind] = float(wait[kind]) - delta
		if wait[kind] > 0.0: continue
		wait[kind] = _gap(kind, w)
		# A low weight also skips some turns, so a faint kind is rare, not just slow.
		if rng.randf() < clampf(w * 1.4, 0.0, 1.0): fire(kind, w)

func _gap(kind: String, w: float) -> float:
	var g: Array = KINDS[kind].gap
	return rng.randf_range(float(g[0]), float(g[1])) / clampf(w, 0.25, 1.0)

## Plays one take of `kind` now (weight w scales the flat ones). False when nothing played.
func fire(kind: String, w := 1.0) -> bool:
	var spec: Dictionary = KINDS[kind]
	var limit := int(spec.get("limit", 0))
	if limit > 0 and int(limited.get(kind, 0)) >= limit: return false
	var path := SfxBank.pick_path(DIR + kind)
	if path.is_empty(): return false
	var stream := SfxBank.stream(path)
	if stream == null: return false
	var trim: float = audio.get("ambience_db") if audio != null else -10.0
	var db: float = trim + float(spec.db) + SfxBank.db(1.5)
	var pitch := SfxBank.pitch(float(spec.pitch))
	var placed := false
	var dist: Array = spec.dist
	if not dist.is_empty() and audio != null:
		var ears: Vector3 = audio.listener()
		var camera: Camera3D = get_viewport().get_camera_3d() if is_inside_tree() and get_viewport() else null
		if ears != Vector3.INF and camera != null:
			var voice := _free3d()
			if voice == null: return false
			var d := rng.randf_range(float(dist[0]), float(dist[1]))
			var angle := rng.randf() * TAU
			var height: Array = spec.height
			voice.global_position = ears + Vector3(cos(angle) * d, rng.randf_range(float(height[0]), float(height[1])), sin(angle) * d)
			if kind == "windmill_creak" and params.get("windmill_at") is Vector3:
				voice.global_position = params.windmill_at + Vector3(0, 6.0, 0)
				d = ears.distance_to(voice.global_position)
			voice.stream = stream
			voice.pitch_scale = pitch
			voice.volume_db = db - 17.0 * log(maxf(d, 1.0) / float(spec.ref)) / log(10.0)
			voice.play()
			placed = true
	if not placed:
		var flat := _free_flat()
		if flat == null: return false
		flat.stream = stream
		flat.pitch_scale = pitch
		# Unplaced sea and wind sounds swell with their weight; placed kinds without a camera
		# sound from their reference distance.
		flat.volume_db = db + (linear_to_db(clampf(w, 0.3, 1.0)) * 0.6 if dist.is_empty() else -3.0)
		flat.play()
	fired += 1
	fired_by[kind] = int(fired_by.get(kind, 0)) + 1
	last_path[kind] = path
	if limit > 0: limited[kind] = int(limited.get(kind, 0)) + 1
	return true

## A one-shot without placement, on the Ambience bus (WorldAudio.splash plays its wave slap on SFX
## itself: a sound of the hero's own action stays with the effects).
func play_flat(kind: String, db := 0.0) -> bool:
	var path := SfxBank.pick_path(DIR + kind)
	var stream := SfxBank.stream(path) if not path.is_empty() else null
	var flat := _free_flat()
	if stream == null or flat == null: return false
	flat.stream = stream
	flat.pitch_scale = SfxBank.pitch(0.05)
	flat.volume_db = db + SfxBank.db(1.0)
	flat.play()
	return true

func _free3d() -> AudioStreamPlayer3D:
	if voices3d.is_empty():
		for i in VOICES_3D:
			var p3 := AudioStreamPlayer3D.new()
			p3.attenuation_model = AudioStreamPlayer3D.ATTENUATION_DISABLED
			p3.panning_strength = 0.8
			p3.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
			p3.bus = GameSettings.BUS_AMBIENCE
			add_child(p3)
			voices3d.append(p3)
	for voice in voices3d:
		if not voice.playing: return voice
	return null

func _free_flat() -> AudioStreamPlayer:
	if voices_flat.is_empty():
		for i in VOICES_FLAT:
			var player := AudioStreamPlayer.new()
			player.bus = GameSettings.BUS_AMBIENCE
			add_child(player)
			voices_flat.append(player)
	for voice in voices_flat:
		if not voice.playing: return voice
	return null

func stop_all() -> void:
	for voice in voices3d: voice.stop()
	for voice in voices_flat: voice.stop()
	weight.clear()
	set_process(false)

func _exit_tree() -> void:
	for voice in voices3d:
		voice.stop()
		voice.stream = null
	for voice in voices_flat:
		voice.stop()
		voice.stream = null
