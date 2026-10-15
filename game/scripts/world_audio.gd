extends Node
## Footsteps, looping ambience beds and the random one-shots over them (ambience_spots.gd).
##
## Footsteps: baked takes res://assets/sfx/steps/<surface>_<walk|run>_<n>.wav (14 per surface and
## gait, tools/sfx/make_world_steps.py) picked through sfx_bank.gd's shuffle bag, so a take never
## plays twice in a row and every take comes round once per cycle. Left and right feet differ a
## little in pitch and level, and a cloth/gear rustle (steps/cloth_<n>) joins about every third
## step. Other walkers (remote players, shadow folk, residents) use remote_step(): their own
## positional voices and their own bag, so they never take the hero's voices or reorder its takes.
## Ambience: 60 s beds res://assets/sfx/ambience/<name>.wav (tools/sfx/make_world_ambience.py,
## seamless loops, imported with loop_mode forward), loaded on a worker thread the first time a bed
## is wanted, faded by mix_targets(); ambience_spots.gd scatters bird calls, gulls, waves, gusts,
## crickets, owls, frogs, a rooster at dawn, windmill creaks and a far bell around the listener.
## Fallback: when the baked files are missing (not imported yet) the old runtime synth is built
## (on a worker thread from prepare()) for the six original surfaces and seven original beds; new
## surfaces then fall back to the nearest synthesized one.
## Footsteps play on the SFX bus, beds and one-shots on Ambience (game_settings.gd).

const GameSettings = preload("res://scripts/game_settings.gd")
const SfxBank = preload("res://scripts/sfx_bank.gd")
const Spots = preload("res://scripts/ambience_spots.gd")
const RATE := 22050
## Every surface footstep() knows; anything else plays as grass.
const SURFACES := ["grass", "sand", "stone", "wood", "rock", "shallow", "snow", "ice", "gravel", "leaves", "ash", "dirt",
	"planks", "tile", "rug", "stairs"]
## The runtime synth's surfaces (fallback only) and the synth stand-in for every other surface.
const SYNTH_SURFACES := ["grass", "sand", "stone", "wood", "rock", "shallow"]
const SYNTH_FOR := {"snow": "sand", "ice": "stone", "gravel": "stone", "leaves": "grass", "ash": "sand", "dirt": "sand",
	"planks": "wood", "tile": "stone", "rug": "sand", "stairs": "wood"}
## Synthesized takes per surface and gait (fallback only).
const VARIATIONS := 4
## Above this speed (m/s) the harder, shorter running steps are used.
const RUN_SPEED := 3.6
const STEPS := "steps/"
const BED_DIR := "res://assets/sfx/ambience/"
const CLOTH := "steps/cloth"
## The wave slap layered over a fall into the sea (splash()).
const SLAP := "ambience/spots/wave_slap"
## Chance of the cloth/gear rustle on a hero step (walking; running adds a little).
const CLOTH_CHANCE := 0.3
## Level of the rustle under the step (dB).
const CLOTH_DB := -5.0
## Left/right foot: +-1.2 % pitch and +-0.6 dB.
const FOOT_PITCH := 0.012
const FOOT_DB := 0.6
## Other walkers: voices, and how far away they are still heard (m from the hero).
const REMOTE_VOICES := 6
const REMOTE_AUDIBLE := 26.0
const FALLOFF_START := 2.5
## Level (dB) of each baked bed when its gain is 1 (file beds sit at -20 dBFS RMS; see
## make_world_ambience.py TARGET). "_muffled" twins play indoors. The clock and room tone files are
## quieter (about -30 and -33 dBFS RMS), hence their higher trims: indoors the beds stay within
## about 10 dB of each other (hearth about -40 dBFS in game, clock -45, the bare room tone -49).
const BED_DB := {
	"birds": -17.0, "birds_far": -21.0, "insects": -20.0, "night": -19.0, "coast": -4.5, "wind": -8.0, "waterfall": -4.0,
	"room": -6.5, "forest": -10.0, "frost": -11.0, "quarry": -12.0, "ember": -6.5, "hearth": -5.0, "clock": -5.0,
	"mill": -8.0, "cafe": -13.5, "sea_muffled": -15.0, "wind_muffled": -19.0, "waterfall_muffled": -14.0,
}
## The same for the synthesized fallback beds (normalized differently) and which synth bed stands in.
const SYNTH_BED_DB := {"birds": -17.0, "birds_far": -22.0, "insects": -18.0, "coast": -10.0, "wind": -14.0,
	"waterfall": -9.0, "room": -25.0, "sea_muffled": -20.0, "wind_muffled": -24.0, "waterfall_muffled": -19.0}
## Open-air bed <-> its indoor twin: the twin starts where the other one is, so the swells line up.
const TWINS := {"coast": "sea_muffled", "sea_muffled": "coast", "wind": "wind_muffled", "wind_muffled": "wind",
	"waterfall": "waterfall_muffled", "waterfall_muffled": "waterfall"}
## Survival regions (and the ember cracks): their own bed plus how much of each village bed stays.
const ZONES := {
	"forest": {"forest": 1.0, "birds": 0.8, "birds_far": 1.0, "insects": 0.8, "night": 0.9, "wind": 0.6},
	"frost": {"frost": 1.0, "birds": 0.0, "birds_far": 0.12, "insects": 0.0, "night": 0.2, "wind": 0.7},
	"quarry": {"quarry": 1.0, "birds": 0.3, "birds_far": 0.5, "insects": 0.6, "night": 0.6, "wind": 0.8},
	"ember": {"ember": 1.0, "quarry": 0.5, "birds": 0.0, "birds_far": 0.0, "insects": 0.0, "night": 0.0, "wind": 0.5},
}
const ZONE_BEDS := ["forest", "frost", "quarry", "ember"]
## Indoor room beds (set_ambience {"room": ...}); room_ambience() picks one per interior.
const ROOM_BEDS := ["hearth", "clock", "mill", "cafe"]
const ROOM_BED_OF := {
	"home": "hearth", "lodge": "hearth", "loft": "hearth", "cottage_bedroom": "hearth", "kitchen": "hearth",
	"owner_room": "hearth", "study": "clock", "office": "clock", "reading": "clock", "archive": "clock",
	"parlour": "clock", "purple_study": "clock", "bedroom": "clock", "observatory": "clock",
	"windmill": "mill", "gear_loft": "mill", "cafe": "cafe", "cafe_kitchen": "cafe", "shop": "cafe", "seed_shop": "cafe",
}
## Rooms that hear the sea through the walls (sea_muffled at this level).
const ROOM_SEA := {"lighthouse": 1.0, "lantern": 1.0, "keeper": 0.8, "lodge": 0.35, "cafe": 0.3, "shop": 0.25}
## Interior floor (interiors.gd ROOMS "floor") -> footstep surface.
const FLOOR_SURFACE := {"planks": "planks", "wide_planks": "planks", "checker": "tile", "tiles": "tile",
	"terracotta": "tile", "flags": "stone"}
## Evens out the surfaces in game (dB, on top of each family's file level): keeps the balance of
## the earlier runtime synth (grass -15.5, sand -17.5, stone -15.8, wood -16.7 dBFS st-rms in game
## before footstep_db) and places the new floors next to their nearest old one.
const SURFACE_DB := {"grass": 1.0, "sand": -2.5, "stone": 1.2, "wood": -1.7, "rock": -1.0, "shallow": -0.5,
	"snow": -2.0, "ice": 1.0, "gravel": -0.8, "leaves": -0.6, "ash": -2.0, "dirt": -1.5, "planks": -1.0, "tile": 0.5,
	"rug": -2.0, "stairs": -0.5}
const SYNTH_SURFACE_DB := {"grass": -0.5, "sand": -1.5, "stone": -1.0, "wood": -2.5, "rock": -1.5, "shallow": 0.0}

## "step/<surface>/<walk|run>/<n>" and "synth/<bed>" (synthesized fallback) and "bed/<name>" (the
## stream a bed plays, baked or synthesized) -> AudioStream.
static var cache: Dictionary = {}
## Level (BED_DB or SYNTH_BED_DB) of the stream in cache["bed/<name>"].
static var bed_level: Dictionary = {}
## Beds being read on a worker thread: name -> path.
static var loading: Dictionary = {}
## Shared white noise (12 s at 22050 Hz) every synth generator reads from at its own offset.
static var noise := PackedFloat32Array()
static var synth_built := false

## Master trims, set to sit with sound.gd (effects peak near -19 dBFS, music near -42 dBFS RMS).
var footstep_db := -19.0
var ambience_db := -10.0
## Seconds for a bed to go from silent to full (and back).
var fade := 1.5
var params := {"day": 1.0, "coast": 0.0, "wind": 0.0, "waterfall": 0.0, "indoor": false, "zone": "", "room": ""}
## Where the hero is (distance falloff of remote steps and one-shots). Unset: the parent's
## `player` or `hero`, else the camera.
var focus: Node3D
var steps: Array[AudioStreamPlayer] = []
var step_index := 0
var cloth_voices: Array[AudioStreamPlayer] = []
var cloth_index := 0
var remote_voices: Array = []
var remote_index := 0
## 0 = left, 1 = right: flips on every hero step.
var foot := 0
## The last hero step (tests, diagnostics): step_choice()'s dictionary.
var last_step := {}
## Walkers tracked by stride(): key -> {"at", "distance", "seen"}.
var walkers := {}
## Remote steps played so far (tests, diagnostics).
var remote_count := 0
## false: ignore the baked takes and use the synthesized fallback (tests).
var use_baked := true
var beds := {}
var gains := {}
var targets := {}
var spots: Node
var rng := RandomNumberGenerator.new()

func _init() -> void:
	# Fades keep running under a paused tree.
	process_mode = Node.PROCESS_MODE_ALWAYS

## True when the baked takes and beds are imported (else the synth fallback is used).
static func baked() -> bool:
	return ResourceLoader.exists("res://assets/sfx/steps/grass_walk_1.wav") and ResourceLoader.exists(BED_DIR + "birds.wav")

## Called while the first loading card is up: starts reading the village beds on worker threads,
## or synthesizes the fallback streams on one when nothing is baked. setup() waits for the synth.
static var building_task := -1
static func prepare() -> void:
	if baked():
		for key in ["birds", "birds_far", "coast", "wind", "insects", "night", "waterfall"]: _request_bed(key)
	elif not synth_built and building_task < 0:
		building_task = WorkerThreadPool.add_task(build_streams, true, "world audio")

func setup() -> void:
	if building_task >= 0:
		WorkerThreadPool.wait_for_task_completion(building_task)
		building_task = -1
	if not synth_built and not baked(): build_streams()
	if not steps.is_empty(): return
	rng.randomize()
	for i in 4:
		steps.append(_player(GameSettings.BUS_SFX))
	for i in 2:
		cloth_voices.append(_player(GameSettings.BUS_SFX))
	for key in BED_DB:
		var player := _player(GameSettings.BUS_AMBIENCE)
		if cache.has("bed/" + key): player.stream = cache["bed/" + key]
		beds[key] = player
		gains[key] = 0.0
		targets[key] = 0.0
	spots = Spots.new()
	spots.name = "Spots"
	spots.audio = self
	add_child(spots)
	set_process(false)

func _player(bus: StringName) -> AudioStreamPlayer:
	var player := AudioStreamPlayer.new()
	player.bus = bus
	add_child(player)
	return player

func _enter_tree() -> void:
	# Coming back after _exit_tree let go of the streams: beds fade back in.
	for key in beds:
		if cache.has("bed/" + key): beds[key].stream = cache["bed/" + key]
	if targets.values().any(func(level: float) -> bool: return level > 0.0): set_process(true)

func _notification(what: int) -> void:
	# The loaded bed files go with the node (they are re-read when wanted again), so no file
	# stream is still cached when the engine checks for resources in use at exit.
	if what == NOTIFICATION_PREDELETE:
		for key in cache.keys():
			if str(key).begins_with("bed/"): cache.erase(key)
		bed_level.clear()

func _exit_tree() -> void:
	# Release playback before the audio server shuts down.
	for player in steps + cloth_voices:
		player.stop()
		player.stream = null
	for entry in remote_voices:
		entry.node.stop()
		entry.node.stream = null
	for key in beds:
		beds[key].stop()
		beds[key].stream = null
		gains[key] = 0.0

# --- Footsteps -------------------------------------------------------------------------------

## One foot plant of the hero. speed in m/s: ~2.8 walking, ~4.5 running; slower is softer.
func footstep(surface: String, speed: float) -> void:
	if steps.is_empty(): setup()
	if not is_inside_tree() or speed <= 0.05: return
	var step := step_choice(surface, speed)
	if step.stream == null: return
	var player := steps[step_index]
	step_index = (step_index + 1) % steps.size()
	player.stream = step.stream
	player.pitch_scale = step.pitch
	player.volume_db = step.volume_db
	player.play()
	if step.cloth: _cloth(step.volume_db, step.pitch)
	last_step = step

## Picks the stream, pitch and level of one hero step; never the same take twice in a row.
## Returns {stream, path, surface (asked, after the grass fallback), source ("baked"|"synth"),
## gait, foot (0 left, 1 right), pitch, volume_db, cloth (bool)}.
func step_choice(surface: String, speed: float) -> Dictionary:
	foot = 1 - foot
	var step := _pick_step(surface, speed, "")
	var side := -1.0 if foot == 0 else 1.0
	step.foot = foot
	step.pitch *= 1.0 + FOOT_PITCH * side
	step.volume_db += FOOT_DB * side
	step.cloth = rng.randf() < CLOTH_CHANCE + (0.12 if step.gait == "run" else 0.0) and SfxBank.has(CLOTH)
	return step

## The take for `surface` at `speed` from bag `bag` ("" = the hero's): baked when imported, else
## the synthesized stand-in. Pitch and level follow the pace like the earlier synth.
func _pick_step(surface: String, speed: float, bag: String) -> Dictionary:
	if not surface in SURFACES: surface = "grass"
	var pace := clampf((speed - 1.0) / 3.5, 0.0, 1.0)
	var gait := "run" if speed > RUN_SPEED else "walk"
	var base := STEPS + "%s_%s" % [surface, gait]
	var path := ""
	var stream: AudioStream = null
	var trim: float = SURFACE_DB[surface]
	var source := "baked"
	var list := SfxBank.paths(base) if use_baked else PackedStringArray()
	if not list.is_empty():
		path = SfxBank.pick_path(base) if bag.is_empty() else list[SfxBank.bag_index(bag + base, list.size())]
		stream = SfxBank.stream(path)
	if stream == null:
		var stand_in: String = surface if surface in SYNTH_SURFACES else SYNTH_FOR.get(surface, "grass")
		if not synth_built: build_streams()
		var take := SfxBank.bag_index("synth/" + bag + stand_in + gait, VARIATIONS)
		path = "step/%s/%s/%d" % [stand_in, gait, take]
		stream = cache.get(path)
		trim = SYNTH_SURFACE_DB[stand_in]
		source = "synth"
	return {
		"stream": stream, "path": path, "surface": surface, "gait": gait, "source": source, "foot": 0, "cloth": false,
		"pitch": lerpf(0.97, 1.03, pace) * rng.randf_range(0.96, 1.04),
		"volume_db": footstep_db + trim + lerpf(-9.0, 2.0, pace) + rng.randf_range(-1.5, 1.5),
	}

func _cloth(step_db: float, pitch: float) -> void:
	var take := SfxBank.pick(CLOTH)
	if take == null: return
	var player := cloth_voices[cloth_index]
	cloth_index = (cloth_index + 1) % cloth_voices.size()
	player.stream = take
	player.pitch_scale = pitch * rng.randf_range(0.95, 1.05)
	player.volume_db = step_db + CLOTH_DB + rng.randf_range(-2.0, 1.0)
	player.play()

## A foot plant of another walker (remote player, shadow folk, resident) at `at`: its own pool of
## positional voices and its own take bag, quieter by `db`, falling off with the distance from the
## hero (silent past REMOTE_AUDIBLE m). False when it was not played.
func remote_step(at: Vector3, surface: String, speed: float, db := -8.0) -> bool:
	if steps.is_empty(): setup()
	if not is_inside_tree() or speed <= 0.05: return false
	var ears := listener()
	var falloff := 0.0
	if ears != Vector3.INF and at != Vector3.INF:
		var distance := ears.distance_to(at)
		if distance > REMOTE_AUDIBLE: return false
		falloff = distance_db(distance)
	var step := _pick_step(surface, speed, "remote:")
	if step.stream == null: return false
	var camera: Camera3D = get_viewport().get_camera_3d() if get_viewport() else null
	var entry := _remote_voice(camera != null and at != Vector3.INF)
	var node: Node = entry.node
	node.stop()
	node.set("stream", step.stream)
	node.set("pitch_scale", step.pitch)
	node.set("volume_db", step.volume_db + db + falloff)
	if node is AudioStreamPlayer3D: (node as AudioStreamPlayer3D).global_position = at
	entry.started = Time.get_ticks_msec()
	node.call("play")
	remote_count += 1
	return true

## A free remote voice of the wanted kind (3D when there is a camera), else the oldest one.
func _remote_voice(positional: bool) -> Dictionary:
	if remote_voices.is_empty():
		for i in REMOTE_VOICES:
			var p3 := AudioStreamPlayer3D.new()
			p3.attenuation_model = AudioStreamPlayer3D.ATTENUATION_DISABLED
			p3.panning_strength = 0.6
			p3.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
			p3.bus = GameSettings.BUS_SFX
			add_child(p3)
			remote_voices.append({"node": p3, "started": 0, "positional": true})
			remote_voices.append({"node": _player(GameSettings.BUS_SFX), "started": 0, "positional": false})
	var oldest := {}
	for entry in remote_voices:
		if entry.positional != positional: continue
		if not entry.node.playing: return entry
		if oldest.is_empty() or entry.started < oldest.started: oldest = entry
	return oldest

## Remote voices sounding now (tests).
func remote_playing() -> int:
	var count := 0
	for entry in remote_voices:
		if entry.node.playing: count += 1
	return count

## Footsteps for anything that moves: call every frame with its position. Every stride (0.74 m
## walking, 0.98 m running) plays a step: the hero's own (own = true, footstep()) or a remote one.
## A jump of more than 1.5 m in one frame (teleport, room change) is not a step. surface "" =
## grass. Walkers not updated for 5 s are forgotten.
func stride(key: String, at: Vector3, delta: float, surface := "", own := false, db := -8.0) -> void:
	var now := Time.get_ticks_msec()
	var entry: Dictionary = walkers.get(key, {})
	walkers[key] = entry
	var before: Vector3 = entry.get("at", at)
	entry.at = at
	entry.seen = now
	var moved := Vector2(at.x - before.x, at.z - before.z).length()
	if moved > 1.5 or delta <= 0.0: return
	var speed := moved / delta
	if speed < 0.4:
		entry.distance = 0.0
		return
	entry.distance = float(entry.get("distance", 0.0)) + moved
	if entry.distance < (0.98 if speed > RUN_SPEED else 0.74): return
	entry.distance = 0.0
	if surface.is_empty(): surface = "grass"
	if own: footstep(surface, speed)
	else: remote_step(at, surface, speed, db)
	if walkers.size() > 24:
		for other in walkers.keys():
			if now - int(walkers[other].seen) > 5000: walkers.erase(other)

## A heavy landing (a jump or a drop): a pitched-down running take with the gear rattling.
func land(speed := 6.0, surface := "grass") -> void:
	if steps.is_empty(): setup()
	if not is_inside_tree() or speed < 2.0: return
	var step := _pick_step(surface, 5.0, "")
	if step.stream == null: return
	var player := steps[step_index]
	step_index = (step_index + 1) % steps.size()
	player.stream = step.stream
	player.pitch_scale = 0.82 * rng.randf_range(0.97, 1.03)
	player.volume_db = step.volume_db + clampf((speed - 4.0) * 0.8, 0.0, 4.0)
	player.play()
	_cloth(step.volume_db + 3.0, 0.95)

## Into the water: a big splash (size 1, falling in the sea) or stepping into the shallows (~0.5).
func splash(size := 1.0) -> void:
	if steps.is_empty(): setup()
	if not is_inside_tree(): return
	var step := _pick_step("shallow", 5.0, "")
	if step.stream != null:
		var player := steps[step_index]
		step_index = (step_index + 1) % steps.size()
		player.stream = step.stream
		player.pitch_scale = lerpf(1.0, 0.78, clampf(size, 0.0, 1.0)) * rng.randf_range(0.97, 1.03)
		player.volume_db = step.volume_db + 4.0 * clampf(size, 0.0, 1.5)
		player.play()
	# The sea slapping back over a fall: part of the hero's own action, so it plays on SFX (a cloth
	# voice) like the splash, not as an ambience one-shot (gone with the ambience slider, and taking
	# one of the three flat ambience voices).
	if size >= 0.75 and not cloth_voices.is_empty():
		var voice := cloth_voices[cloth_index]
		cloth_index = (cloth_index + 1) % cloth_voices.size()
		SfxBank.play_on(voice, SLAP, -8.0 + 4.0 * minf(size, 1.5), 1.0, 0.05, 1.0)

## Where the hero is: `focus`, else the parent's player / hero, else the camera (INF: unknown).
func listener() -> Vector3:
	if is_instance_valid(focus) and focus.is_inside_tree(): return focus.global_position
	var parent := get_parent()
	if parent != null:
		for member in ["player", "hero"]:
			var hero = parent.get(member)
			if hero is Node3D and is_instance_valid(hero) and hero.is_inside_tree(): return hero.global_position
	var camera: Camera3D = get_viewport().get_camera_3d() if is_inside_tree() and get_viewport() else null
	return camera.global_position if camera != null else Vector3.INF

## Flat inside FALLOFF_START m, then about -5 dB per doubling (creature_audio.gd's law).
static func distance_db(distance: float) -> float:
	if distance <= FALLOFF_START: return 0.0
	return -17.0 * log(distance / FALLOFF_START) / log(10.0)

## Footstep surface of an interior floor (interiors.gd ROOMS "floor"), rug when standing on one.
static func room_surface(floor_kind: String, decor := [], at := Vector3.INF) -> String:
	if at != Vector3.INF:
		for record in decor:
			if not record is Dictionary or str(record.get("kind", "")) != "rug" or not record.has("center"): continue
			var local: Vector3 = (at - record.center).rotated(Vector3.UP, -float(record.get("yaw", 0.0)))
			var half: Vector2 = record.get("half", Vector2.ZERO)
			if absf(local.x) <= half.x and absf(local.z) <= half.y: return "rug"
	return FLOOR_SURFACE.get(floor_kind, "planks")

## set_ambience() parameters for an interior: room tone, the room's bed and the sea through the walls.
static func room_ambience(room: String, day := 1.0) -> Dictionary:
	return {"indoor": true, "room": ROOM_BED_OF.get(room, ""), "day": day, "coast": ROOM_SEA.get(room, 0.0),
		"wind": 0.25, "waterfall": 0.0, "zone": ""}

# --- Ambience --------------------------------------------------------------------------------

## Keys (all optional, missing ones keep their last value): day 0..1 (1 = noon), coast, wind,
## waterfall 0..1, indoor (bool or 0..1), zone ("" village, forest, frost, quarry, ember), room
## ("" or hearth, clock, mill, cafe: the indoor bed), hour (0..24 for the dawn rooster, -1 = unknown:
## dawn then follows the rising daylight),
## windmill_at (Vector3), any zone bed by name 0..1 (e.g. "ember": 1.0 on the hot cracks),
## fade (seconds for this and later changes).
func set_ambience(next: Dictionary) -> void:
	if beds.is_empty(): setup()
	for key in next:
		if key == "fade": fade = maxf(float(next[key]), 0.0)
		else: params[key] = next[key]
	targets = mix_targets(params)
	if is_instance_valid(spots): spots.update(targets, params)
	set_process(true)

func stop_all() -> void:
	for player in steps + cloth_voices: player.stop()
	for entry in remote_voices: entry.node.stop()
	for key in beds:
		beds[key].stop()
		gains[key] = 0.0
		targets[key] = 0.0
	if is_instance_valid(spots): spots.stop_all()
	set_process(false)

## Linear gain (0..1, before BED_DB) of every bed for a set of ambience parameters.
static func mix_targets(p: Dictionary) -> Dictionary:
	var day := clampf(float(p.get("day", 1.0)), 0.0, 1.0)
	var inside_value = p.get("indoor", false)
	var inside: float = (1.0 if inside_value else 0.0) if inside_value is bool else clampf(float(inside_value), 0.0, 1.0)
	var outside := 1.0 - inside
	var zone: Dictionary = ZONES.get(str(p.get("zone", "")), {})
	# Birds and crickets only reach the room faintly; the low beds come through the walls muffled.
	var walls := lerpf(1.0, 0.06, inside)
	var birds := smoothstep(0.3, 0.7, day) * walls
	var dusk := (1.0 - smoothstep(0.25, 0.6, day)) * (0.55 + 0.45 * smoothstep(0.05, 0.3, day))
	var out := {
		"birds": birds * float(zone.get("birds", 1.0)),
		"birds_far": birds * float(zone.get("birds_far", 1.0)),
		"insects": dusk * walls * float(zone.get("insects", 1.0)),
		"night": (1.0 - smoothstep(0.1, 0.4, day)) * walls * float(zone.get("night", 1.0)),
		"room": inside,
	}
	var levels := {"coast": 1.0, "wind": float(zone.get("wind", 1.0)), "waterfall": 1.0}
	var twin := {"coast": "sea_muffled", "wind": "wind_muffled", "waterfall": "waterfall_muffled"}
	for key in levels:
		var level := clampf(float(p.get(key, 0.0)), 0.0, 1.0)
		out[key] = level * levels[key] * outside
		out[twin[key]] = level * inside
	for key in ZONE_BEDS:
		out[key] = maxf(float(zone.get(key, 0.0)), clampf(float(p.get(key, 0.0)), 0.0, 1.0)) * outside
	var room := str(p.get("room", ""))
	for key in ROOM_BEDS: out[key] = inside if key == room else 0.0
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
		if not player.playing:
			if not _bed_ready(key):
				# Still reading on a worker thread: look again next frame. A bed without any
				# sound (not imported, no synth stand-in) stays silent.
				if loading.has(key): busy = true
				continue
			_start(key)
		player.volume_db = ambience_db + float(bed_level.get(key, BED_DB[key])) + linear_to_db(gain)
	if not busy: set_process(false)

func _start(key: String) -> void:
	var player: AudioStreamPlayer = beds[key]
	player.stream = cache["bed/" + key]
	var length := player.stream.get_length()
	var at := rng.randf() * length
	# An indoor copy picks up where its open-air twin is, so the swells line up.
	var twin: String = TWINS.get(key, "")
	if beds.has(twin) and beds[twin].playing: at = fmod(beds[twin].get_playback_position(), length)
	player.play(at)

## Reads every bed now (blocking): loading screens and tests. Returns how many are ready.
func warm_beds(keys := []) -> int:
	var ready := 0
	for key in (keys if not keys.is_empty() else BED_DB.keys()):
		if _bed_ready(key, true): ready += 1
	return ready

## The bed's stream is in cache["bed/<key>"]: the baked loop (read on a worker thread; `wait`
## blocks instead), else the synthesized fallback when there is one. False while it is loading
## or when the bed has no sound at all.
static func _bed_ready(key: String, wait := false) -> bool:
	if cache.has("bed/" + key): return true
	var path := BED_DIR + key + ".wav"
	if ResourceLoader.exists(path):
		if wait and not loading.has(key):
			var stream := load(path) as AudioStream
			if stream != null: return _bed_loaded(key, stream)
		_request_bed(key)
		var status := ResourceLoader.load_threaded_get_status(path)
		if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS and not wait: return false
		loading.erase(key)
		# Every request is collected, a failed one too (`wait` blocks on one still running): one
		# that never is leaks its load token at exit (see release()).
		if status != ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
			var stream := ResourceLoader.load_threaded_get(path) as AudioStream
			if stream != null: return _bed_loaded(key, stream)
	if cache.has("synth/" + key):
		cache["bed/" + key] = cache["synth/" + key]
		bed_level[key] = SYNTH_BED_DB[key]
		return true
	return false

static func _bed_loaded(key: String, stream: AudioStream) -> bool:
	cache["bed/" + key] = stream
	bed_level[key] = BED_DB[key]
	return true

static func _request_bed(key: String) -> void:
	if loading.has(key) or cache.has("bed/" + key): return
	var path := BED_DIR + key + ".wav"
	if not ResourceLoader.exists(path): return
	if ResourceLoader.load_threaded_request(path) == OK: loading[key] = path

## At quit (clean_exit.gd): collects every bed read still pending, waiting for one still running,
## and lets go of the bed streams. The engine leaks a load_threaded_request() that nobody took with
## load_threaded_get() before exit: its load token, a plain RefCounted left at reference count 0
## ("N ObjectDB instances were leaked at exit"). prepare() reads all seven village beds ahead, and
## a bed the session never wanted (night and crickets by day, birds at night, a far waterfall) was
## otherwise never collected: one leak per such bed.
static func release() -> void:
	for key in loading.keys():
		var path: String = loading[key]
		if ResourceLoader.load_threaded_get_status(path) != ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
			ResourceLoader.load_threaded_get(path)
	loading.clear()
	for key in cache.keys():
		if str(key).begins_with("bed/"): cache.erase(key)
	bed_level.clear()

## The synthesized fallback: 4 takes per original surface and gait, and the original beds.
static func build_streams() -> void:
	if synth_built: return
	var rng := RandomNumberGenerator.new()
	rng.seed = 7071
	var table := PackedFloat32Array()
	table.resize(NOISE_SIZE)
	for i in NOISE_SIZE:
		table[i] = rng.randf() * 2.0 - 1.0
	noise = table
	for surface in SYNTH_SURFACES:
		for take in VARIATIONS:
			cache["step/%s/walk/%d" % [surface, take]] = _wav(_step(surface, rng, rng.randf_range(0.1, 0.35)), RATE, false, 0.2)
			cache["step/%s/run/%d" % [surface, take]] = _wav(_step(surface, rng, rng.randf_range(0.75, 0.95)), RATE, false, 0.2)
	cache["synth/birds"] = _wav(_bed_birds(9.0, 11, false), RATE, true)
	cache["synth/birds_far"] = _wav(_bed_birds(7.0, 29, true), RATE, true)
	cache["synth/insects"] = _wav(_bed_insects(8.0, RATE), RATE, true)
	var coast := _bed_coast(10.0, 16000)
	cache["synth/coast"] = _wav(coast, 16000, true, 0.2)
	cache["synth/sea_muffled"] = _wav(_muffle(coast, 16000, 380.0, 2), 8000, true, 0.2)
	var wind := _bed_wind(8.0, 11025)
	cache["synth/wind"] = _wav(wind, 11025, true, 0.2)
	cache["synth/wind_muffled"] = _wav(_muffle(wind, 11025, 320.0, 1), 11025, true, 0.2)
	var fall := _bed_waterfall(6.0, 16000)
	cache["synth/waterfall"] = _wav(fall, 16000, true, 0.2)
	cache["synth/waterfall_muffled"] = _wav(_muffle(fall, 16000, 380.0, 2), 8000, true, 0.2)
	cache["synth/room"] = _wav(_bed_room(6.0, 8000), 8000, true, 0.2)
	synth_built = true

const NOISE_SIZE := 1 << 18
const NOISE_MASK := NOISE_SIZE - 1

# --- Synthesized fallback (the earlier runtime synth) ------------------------------------------

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


# Footsteps (fallback)

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

# Ambience beds (fallback) ----------------------------------------------------------------

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
