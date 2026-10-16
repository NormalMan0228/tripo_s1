extends RefCounted
## Monster voices for the survival nights, plus the pooled one-shot engine that
## combat_audio.gd and hero_voice.gd share. Static helpers only (no autoload):
##   const CreatureAudio = preload("res://scripts/creature_audio.gd")
##   CreatureAudio.play(app_or_node, species: String, event: String, at: Vector3, variant := "", kind := "", size := 0.0) -> bool
##   CreatureAudio.step(app_or_node, species: String, at: Vector3, speed := 1.0) -> bool
##
## Own voices (tools/sfx/gen_monsters.py): every staged expedition species of server/catalog.py has
## its own takes, res://assets/sfx/creatures/<species>_<event>_<n>.wav (4 per event, the species' map
## baked in, so no region layer plays under them), and the bosses also <boss>_roar_<n> and
## <boss>_intro_<n>. play() resolves the family with voice_name(species, kind, event): the species'
## own takes when it has them (for the event or its FALLBACK event), otherwise the stand-in `kind`
## exactly as before (region pools and region layer; `size`, the species' height in metres, pitches
## the stand-in a little: bigger is lower, at most SIZE_PITCH). Voice limits and throttles key on
## the resolved name.
##
## Sounds (tools/make_creature_sfx.py, then tools/sfx/gen_combat.py), one pool per
## species x event x region, picked through sfx_bank.gd shuffle bags (every take once per cycle,
## never twice in a row, with 6+ takes not one of the last two):
##   res://assets/sfx/creatures/<species>_<event>_<n>.wav           7 region-neutral takes, each a
##       different call (count, contour, length, extra layer); a region layer plays under them:
##   res://assets/sfx/creatures/layer_<region>_<accent|bed>_<n>.wav  moss/twigs, embers, ice
##   res://assets/sfx/creatures/<species>_<event>_<region>_<n>.wav  the original region takes (2)
##   res://assets/sfx/creatures/step_<gait>_<n>.wav                 monster footfalls (step())
##
## species (unknown names fall back to "wolf"):
##   "wolf"   그림자 늑대  quadruped pack hunter: sniffs, low growls, howl/bark, jaw snap, yelp
##   "boar"   가시 멧돼지  charger: grunts, snorts, hoof pawing, squeals, heavy body thud
##   "brute"  이끼 수호자  stone/moss golem: grinding, deep groans, ground slam, rubble collapse
##   "wisp"   불씨 도깨비  hovering fire imp: flame flicker, giggles, fire inhale, spit, fizzle
##   "shroom" 버섯 망령    mushroom wraith: squishy bloops, ghostly "ooh", inflating cap, spore puff
##   aliases: beast/shadow -> wolf, golem -> brute, imp/ember -> wisp, mushroom/spore -> shroom
## event:
##   "idle"    ambient breath/chitter while chasing or circling the fire (throttled: one per
##             species per IDLE_GAP s, at most MAX_IDLE at once, so a pack doesn't drone)
##   "alert"   aggro call when it appears or first targets the player   (alias "aggro", "spawn");
##             alerts of a roster appearing together are staggered 80-300 ms apart
##   "windup"  attack anticipation, timed to the server wind-up: wolf .6 s, boar .8 s,
##             brute 1.1 s, wisp .85 s, shroom .8 s; call when phase becomes "windup"
##   "strike"  the blow lands (phase windup -> recover)                 (alias "attack")
##   "hurt"    hp went down                                             (alias "hit")
##   "death"   killed / removed with hp <= 0                            (alias "die")
##   "charge"  the boar's committed dash (phase windup -> charge); other species: windup takes
##   "dazed"   the boar stunned after its dash (charge -> recover); other species: hurt takes
##   "roar"    a boss's roar (every third wind-up, and once as its health falls past half); alert
##             takes for a species without roars
##   "intro"   a boss's arrival sting, once when it appears; always flat (not positional), so the
##             whole field hears the boss arrive; alert takes for a species without intros
## variant: region colouring
##   "forest" / "moss"  leaf-and-moss rustle, twig snaps
##   "quarry" / "ember" warm crackle, ember flare on strike/death
##   "frost"  / "ice"   crystalline shimmer, ice crack on strike/hurt/death
##   ""  reads app.run.map_id when app has a run, else "forest".
## at: world position. Loudness falls off from the hero (app.player, else the camera):
##   flat inside FALLOFF_START m, about -5 dB per doubling after, silent past AUDIBLE m.
##   When the viewport has a Camera3D the sound is panned (AudioStreamPlayer3D, attenuation
##   off); otherwise a flat player is used. Vector3.INF = not positional.
## Returns true when a sound started (or was scheduled, for a staggered alert). Pitch +-5 %, +-1 dB.
## Voices: MAX_VOICES pooled 3D players + MAX_VOICES flat players under root/GameSfx,
## MAX_PER_SPECIES at once per species; a full pool steals the lowest-priority, oldest voice
## (death 5 > strike/hurt/charge 4 > alert/windup/dazed 3 > idle 1 > region layers/steps 0)
## or drops the new sound if it ranks lower. Steps: at most MAX_STEPS at once, within STEP_RANGE m,
## one per species every STEP_GAP s and about STEP_RATE per second over the whole pack.
## Bus: "SFX" when the project has it, else "Master".
##
## Shared engine (used by combat_audio.gd / hero_voice.gd):
##   CreatureAudio.emit(app_or_node, stream, at, volume_db, pitch, priority, tag, bus := "SFX") -> bool
##   CreatureAudio.after(delay, app_or_node, fn) -> bool  fn.call(app_or_node) after delay s, holding
##       the app weakly (skipped when it is freed by then; no "Lambda capture was freed" error)
##   CreatureAudio.listener(app_or_node) -> Vector3 (Vector3.INF when unknown)
##   CreatureAudio.find_app(node) -> Object (the node, the current scene or an ancestor with `player`)
##   CreatureAudio.bus(name) -> StringName, CreatureAudio.active(tag_prefix := "") -> int
##   CreatureAudio.preload_all() warms every creature stream (call at run start to avoid hitches).
##   CreatureAudio.played: int counts sounds started (tests).

const SfxBank = preload("res://scripts/sfx_bank.gd")
const DIR := "res://assets/sfx/creatures/"
const SPECIES := ["wolf", "boar", "brute", "wisp", "shroom"]
const EVENTS := ["idle", "alert", "windup", "strike", "hurt", "death"]
## Species-specific cues; a species without takes for one uses its FALLBACK event's takes.
const EXTRA := ["charge", "dazed", "roar", "intro"]
const FALLBACK := {"charge": "windup", "dazed": "hurt", "roar": "alert", "intro": "alert"}
## Stand-in heights (shadow_beast.gd procedural bodies): a stand-in voicing a species of another
## size is pitched by (HEIGHT/size)^0.25, clamped to 1 +- SIZE_PITCH. Own voices are not pitched.
const HEIGHT := {"wolf": 1.3, "boar": 1.1, "brute": 2.4, "wisp": 1.3, "shroom": 1.0}
const SIZE_PITCH := 0.08
const REGIONS := ["forest", "quarry", "frost"]
const SPECIES_ALIASES := {"beast": "wolf", "shadow": "wolf", "shadow_beast": "wolf", "golem": "brute", "guardian": "brute",
	"imp": "wisp", "ember": "wisp", "fire": "wisp", "mushroom": "shroom", "spore": "shroom"}
const EVENT_ALIASES := {"aggro": "alert", "notice": "alert", "spawn": "alert", "wind_up": "windup", "dash": "charge",
	"attack": "strike", "bite": "strike", "slam": "strike", "hit": "hurt", "damage": "hurt", "die": "death", "dead": "death",
	"breath": "idle", "chase": "idle", "stun": "dazed", "stunned": "dazed"}
const REGION_ALIASES := {"forest": "forest", "moss": "forest", "quarry": "quarry", "ember": "quarry", "frost": "frost", "ice": "frost"}
## Level (dB) at the hero for each event; the files are levelled, these set the mix.
## Door sounds play at -22.5 dBFS (file) -9 dB; a close strike lands ~3 dB above a door.
const EVENT_DB := {"idle": -15.0, "alert": -11.0, "windup": -12.0, "strike": -10.0, "hurt": -11.5, "death": -10.5,
	"charge": -10.5, "dazed": -12.0, "roar": -10.5, "intro": -11.0}
const PRIORITY := {"idle": 1, "alert": 3, "windup": 3, "strike": 4, "hurt": 4, "death": 5, "charge": 4, "dazed": 3,
	"roar": 4, "intro": 5}
## Region layer under a region-neutral take: [layer kind, chance]; level LAYER_DB below the take.
const LAYER := {"idle": ["bed", 0.5], "alert": ["accent", 0.8], "windup": ["bed", 0.6], "strike": ["accent", 0.9],
	"hurt": ["accent", 0.8], "death": ["accent", 1.0], "charge": ["accent", 0.7], "dazed": ["bed", 0.6],
	"roar": ["accent", 0.8], "intro": ["accent", 0.0]}
const LAYER_DB := -5.0
## Footfalls: gait per species and its level at the hero (before distance falloff).
const GAIT := {"wolf": "paw", "boar": "hoof", "brute": "stomp", "wisp": "flutter", "shroom": "squelch"}
const STEP_DB := {"paw": -19.0, "hoof": -17.5, "stomp": -14.0, "flutter": -20.0, "squelch": -18.5}
const MAX_STEPS := 2
const STEP_RANGE := 18.0
const STEP_GAP := 0.12
## Footfalls across every species: a bucket of STEP_BURST refilled at STEP_RATE per second, so a
## running pack stays a soft patter instead of a drum roll.
const STEP_RATE := 8.0
const STEP_BURST := 3.0
const MAX_VOICES := 10
const MAX_PER_SPECIES := 3
const MAX_IDLE := 2
const IDLE_GAP := 0.9
const ALERT_WINDOW := 0.35
const ALERT_GROUP_MAX := 4
const FALLOFF_START := 2.5
const AUDIBLE := 34.0

static var played := 0
static var holder: Node3D
static var pool3d: Array = []
static var pool2d: Array = []
static var cache := {}
static var pools := {}
static var last_take := {}
static var last_idle := {}
static var last_key := {}
static var last_step := {}
static var step_tokens := STEP_BURST
static var step_refill := -10.0
static var alert_start := -10.0
static var alert_count := 0
static var own_voice := {}
static var rng := RandomNumberGenerator.new()

static func play(app_or_node, species: String, event: String, at: Vector3, variant := "", kind := "", size := 0.0) -> bool:
	event = event_name(event)
	species = voice_name(species, kind, event)
	var size_scale := size_pitch(species, size)
	var region := region_name(variant, app_or_node)
	# A boss's arrival sting is for the whole field: flat, wherever the boss stands.
	if event == "intro": at = Vector3.INF
	var now := Time.get_ticks_msec()*0.001
	if event == "idle":
		if now-float(last_idle.get(species, -10.0)) < IDLE_GAP: return false
		if active("creature/", "idle") >= MAX_IDLE: return false
	var list := pool_paths(species, event, region)
	if list.is_empty(): return false
	var key := "%s_%s_%s" % [species, event, region]
	# Two of the same call within 40 ms (two wolves hit together) read as one louder call.
	if now-float(last_key.get(key, -10.0)) < 0.04: return false
	if not _audible(app_or_node, at): return false
	last_key[key] = now
	if event == "alert":
		# A roster appearing together: the first calls at once, the next ones ripple after it.
		if now-alert_start > ALERT_WINDOW:
			alert_start = now
			alert_count = 0
		alert_count += 1
		if alert_count > 1:
			if alert_count > ALERT_GROUP_MAX: return false
			var delay := minf(0.3, (alert_count-1)*rng.randf_range(0.08, 0.12)+rng.randf_range(0.0, 0.04))
			# The creature that called may die before its turn: after() holds it weakly.
			return after(delay, app_or_node, func(target) -> void:
				_voice(target, species, event, region, key, at, Time.get_ticks_msec()*0.001, size_scale))
	return _voice(app_or_node, species, event, region, key, at, now, size_scale)

static func _voice(app_or_node, species: String, event: String, region: String, key: String, at: Vector3, now: float, size_scale := 1.0) -> bool:
	var list := pool_paths(species, event, region)
	if list.is_empty(): return false
	var path: String = list[SfxBank.bag_index("creature/"+key, list.size())]
	var db: float = EVENT_DB[event]+SfxBank.db(1.0)
	var pitch := (SfxBank.pitch(0.07) if event == "idle" else SfxBank.pitch(0.05))*size_scale
	var tag := "creature/%s/%s" % [species, event]
	var priority: int = PRIORITY[event]
	# A species may hold MAX_PER_SPECIES voices; a more important call replaces its weakest one.
	var mine := _active_entries("creature/%s/" % species)
	if mine.size() >= MAX_PER_SPECIES:
		mine.sort_custom(func(a, b): return a.priority < b.priority or (a.priority == b.priority and a.started < b.started))
		if int(mine[0].priority) > priority: return false
		mine[0].node.stop()
	if not emit(app_or_node, SfxBank.stream(path), at, db, pitch, priority, tag): return false
	last_take[key] = path
	if event == "idle": last_idle[species] = now
	# Region-neutral takes get the region's colour as a quiet layer (the old region takes and the
	# species' own voices have it baked in).
	if species in SPECIES and not path.contains("_%s_" % region): _layer(app_or_node, region, event, at, db)
	return true

## Moss / ember / ice layer for a region-neutral take; never steals a voice from a real call.
static func _layer(app_or_node, region: String, event: String, at: Vector3, db: float) -> void:
	var spec: Array = LAYER.get(event, ["bed", 0.5])
	if rng.randf() > float(spec[1]): return
	var path := SfxBank.pick_path(DIR+"layer_%s_%s" % [region, spec[0]])
	if path.is_empty(): return
	emit(app_or_node, SfxBank.stream(path), at, db+LAYER_DB+SfxBank.db(1.5), SfxBank.pitch(0.05), 0, "layer/"+region)

## One monster footfall (call per stride from the creature's movement): paw / hoof / stomp /
## squelch / flutter by species. Dropped when far away, when MAX_STEPS are sounding, when the same
## species stepped within STEP_GAP s or when the pack used up its STEP_RATE budget; priority 0, so
## steps never cut a voice.
static func step(app_or_node, species: String, at: Vector3, speed := 1.0) -> bool:
	species = species_name(species)
	var gait: String = GAIT.get(species, "paw")
	var now := Time.get_ticks_msec()*0.001
	if now-float(last_step.get(species, -10.0)) < STEP_GAP: return false
	step_tokens = minf(STEP_BURST, step_tokens+maxf(now-step_refill, 0.0)*STEP_RATE)
	step_refill = now
	if step_tokens < 1.0: return false
	if active("step/") >= MAX_STEPS: return false
	if at != Vector3.INF:
		var ears := listener(app_or_node)
		if ears != Vector3.INF and ears.distance_to(at) > STEP_RANGE: return false
	var path := SfxBank.pick_path(DIR+"step_"+gait)
	if path.is_empty(): return false
	var pace := clampf(speed/3.0, 0.0, 1.0)
	if not emit(app_or_node, SfxBank.stream(path), at, float(STEP_DB[gait])+lerpf(-1.5, 1.0, pace)+SfxBank.db(1.5),
			lerpf(0.97, 1.04, pace)*SfxBank.pitch(0.06), 0, "step/"+species):
		return false
	last_step[species] = now
	step_tokens -= 1.0
	return true

## The family a call plays: the species' own takes when it has them for this event (or the event's
## FALLBACK), else the stand-in `kind`, else species_name(species) as before (unknown -> "wolf").
static func voice_name(species: String, kind := "", event := "idle") -> String:
	var own := species.to_lower()
	# An alias that is also a species ("imp") is that species once it has its own takes.
	if not own.is_empty() and own not in SPECIES and has_own(own, event_name(event)): return own
	return species_name(kind if not kind.is_empty() else species)

## True when `name` has its own takes for `event` (or for the event's FALLBACK). Cached.
static func has_own(name: String, event: String) -> bool:
	var key := "%s/%s" % [name, event]
	if own_voice.has(key): return own_voice[key]
	var found := SfxBank.has(DIR+"%s_%s" % [name, event]) or (FALLBACK.has(event) and has_own(name, FALLBACK[event]))
	own_voice[key] = found
	return found

## Pitch for a stand-in voicing a species `size` m tall (1.0 for own voices and unknown sizes).
static func size_pitch(name: String, size: float) -> float:
	if size <= 0.0 or not HEIGHT.has(name): return 1.0
	return clampf(pow(float(HEIGHT[name])/size, 0.25), 1.0-SIZE_PITCH, 1.0+SIZE_PITCH)

static func species_name(species: String) -> String:
	species = species.to_lower()
	species = SPECIES_ALIASES.get(species, species)
	return species if species in SPECIES else "wolf"

static func event_name(event: String) -> String:
	event = event.to_lower()
	event = EVENT_ALIASES.get(event, event)
	return event if event in EVENTS or event in EXTRA else "idle"

static func region_name(variant: String, app_or_node = null) -> String:
	var region: String = REGION_ALIASES.get(variant.to_lower(), "")
	if region.is_empty():
		var app = find_app(app_or_node)
		if app != null and "run" in app and app.run is Dictionary:
			region = REGION_ALIASES.get(str(app.run.get("map_id", "forest")), "forest")
	return region if not region.is_empty() else "forest"

## Every take path for one sound: the region-neutral takes plus the region's own takes (a region
## without its own falls back to the forest ones; a species without an EXTRA cue to its FALLBACK).
static func pool_paths(species: String, event: String, region: String) -> PackedStringArray:
	var key := "%s_%s_%s" % [species, event, region]
	if pools.has(key): return pools[key]
	var list := SfxBank.paths(DIR+"%s_%s" % [species, event])
	var own := SfxBank.paths(DIR+key)
	if own.is_empty() and region != "forest": own = SfxBank.paths(DIR+"%s_%s_forest" % [species, event])
	list.append_array(own)
	if list.is_empty() and FALLBACK.has(event): list = pool_paths(species, FALLBACK[event], region)
	pools[key] = list
	return list

## Every take for one sound, loaded once (tests / warm-up; play() loads lazily).
static func streams(species: String, event: String, region: String) -> Array:
	var key := "%s_%s_%s" % [species, event, region]
	if cache.has(key): return cache[key]
	var list := []
	for path in pool_paths(species, event, region):
		var stream := SfxBank.stream(path)
		if stream != null: list.append(stream)
	cache[key] = list
	return list

## Reads the takes the field can play ahead of their first use (each first play read its file from
## disk in the frame it sounded: monster cries, steps). One family a frame while the run's card covers
## the screen, then one every WARM_GAP s so play never pays for more than one family at once; only the
## run's region (map ids outside REGIONS warm them all). Started by main.start_run.
const WARM_GAP := 0.3
static var _warming := false
static func warm_spread(tree: SceneTree, region := "") -> void:
	if _warming or tree == null: return
	_warming = true
	var regions: Array = [region] if region in REGIONS else REGIONS
	var jobs: Array = []
	for species in SPECIES:
		for event in EVENTS+EXTRA:
			for r in regions: jobs.append(["c", species, event, r])
	for gait in GAIT.values(): jobs.append(["s", DIR+"step_"+gait])
	for r in regions:
		for kind in ["accent", "bed"]: jobs.append(["s", DIR+"layer_%s_%s" % [r, kind]])
	var pace = load("res://scripts/load_pace.gd")
	for job in jobs:
		if job[0] == "c": streams(job[1], job[2], job[3])
		else: SfxBank.warm(job[1])
		if bool(pace.covered): await tree.process_frame
		else: await tree.create_timer(WARM_GAP).timeout
	_warming = false

static func preload_all() -> int:
	var count := 0
	for species in SPECIES:
		for event in EVENTS+EXTRA:
			for region in REGIONS: count += streams(species, event, region).size()
	for gait in GAIT.values(): count += SfxBank.warm(DIR+"step_"+gait)
	for region in REGIONS:
		for kind in ["accent", "bed"]: count += SfxBank.warm(DIR+"layer_%s_%s" % [region, kind])
	return count

# ------------------------------------------------------------------ shared engine
## fn.call(app_or_node) after `delay` s. The timer lambda holds the app through a WeakRef: a lambda
## that captured the app itself would make Godot print "Lambda capture at index 0 was freed" when
## the app (a scene being left, a creature dying) goes first. Skipped when the app is freed by then;
## a non-object app (null) is passed through. False when nothing was scheduled.
static func after(delay: float, app_or_node, fn: Callable) -> bool:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null: return false
	var is_object := typeof(app_or_node) == TYPE_OBJECT
	if is_object and not is_instance_valid(app_or_node): return false
	var ref: WeakRef = weakref(app_or_node) if is_object else null
	var plain = null if is_object else app_or_node
	tree.create_timer(maxf(delay, 0.0)).timeout.connect(func() -> void:
		var target = plain
		if ref != null:
			target = ref.get_ref()
			if target == null: return
		fn.call(target))
	return true

static func bus(name: String) -> StringName:
	return StringName(name) if AudioServer.get_bus_index(name) >= 0 else &"Master"

## The object that owns `player` (main.gd / studio.gd style app), or null.
static func find_app(node) -> Object:
	if node == null or not is_instance_valid(node): return null
	if node is Object and "player" in node: return node
	if node is Node and node.is_inside_tree():
		var scene: Node = node.get_tree().current_scene
		if scene != null and "player" in scene: return scene
		var up: Node = node.get_parent()
		for i in 10:
			if up == null: break
			if "player" in up: return up
			up = up.get_parent()
	return null

## Where the ears are: the hero when the app has one, otherwise the active camera.
static func listener(app_or_node) -> Vector3:
	var app = find_app(app_or_node)
	if app != null:
		var hero = app.get("player")
		if hero is Node3D and is_instance_valid(hero) and hero.is_inside_tree(): return hero.global_position
	var camera := _camera()
	return camera.global_position if camera != null else Vector3.INF

static func distance_db(distance: float) -> float:
	if distance <= FALLOFF_START: return 0.0
	return -17.0*log(distance/FALLOFF_START)/log(10.0)

static func _audible(app_or_node, at: Vector3) -> bool:
	if at == Vector3.INF: return true
	var ears := listener(app_or_node)
	return ears == Vector3.INF or ears.distance_to(at) <= AUDIBLE

static func emit(app_or_node, stream: AudioStream, at: Vector3, volume_db: float, pitch: float, priority: int, tag: String, bus_name := "SFX") -> bool:
	if stream == null or not _ensure(): return false
	var positional := at != Vector3.INF
	if positional:
		var ears := listener(app_or_node)
		if ears != Vector3.INF:
			var distance := ears.distance_to(at)
			if distance > AUDIBLE: return false
			volume_db += distance_db(distance)
	var use3d := positional and _camera() != null
	var entry := _slot(pool3d if use3d else pool2d, priority)
	if entry.is_empty(): return false
	var node = entry.node
	node.stop()
	node.stream = stream
	node.volume_db = volume_db
	node.pitch_scale = clampf(pitch, 0.5, 2.0)
	node.bus = bus(bus_name)
	if use3d: (node as AudioStreamPlayer3D).global_position = at
	entry.priority = priority
	entry.tag = tag
	entry.started = Time.get_ticks_msec()*0.001
	node.play()
	played += 1
	return true

## Voices still sounding whose tag starts with prefix (and contains `part` when given).
static func active(prefix := "", part := "") -> int:
	var count := 0
	for entry in _active_entries(prefix):
		if part.is_empty() or String(entry.tag).contains(part): count += 1
	return count

static func stop_all() -> void:
	for entry in pool3d+pool2d:
		if is_instance_valid(entry.node): entry.node.stop()

static func _active_entries(prefix: String) -> Array:
	var out := []
	for entry in pool3d+pool2d:
		if is_instance_valid(entry.node) and entry.node.playing and String(entry.tag).begins_with(prefix): out.append(entry)
	return out

static func _camera() -> Camera3D:
	if not is_instance_valid(holder) or not holder.is_inside_tree(): return null
	return holder.get_viewport().get_camera_3d()

## A free player, else the lowest-priority oldest one if it ranks no higher than the new sound.
static func _slot(pool: Array, priority: int) -> Dictionary:
	var victim := {}
	for entry in pool:
		if not entry.node.playing: return entry
		if victim.is_empty() or entry.priority < victim.priority or (entry.priority == victim.priority and entry.started < victim.started):
			victim = entry
	if victim.is_empty() or int(victim.priority) > priority: return {}
	return victim

static func _ensure() -> bool:
	if is_instance_valid(holder) and holder.is_inside_tree() and not pool3d.is_empty(): return true
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null: return false
	holder = tree.root.get_node_or_null("GameSfx") as Node3D
	if holder == null:
		holder = Node3D.new()
		holder.name = "GameSfx"
		tree.root.add_child(holder)
	pool3d.clear()
	pool2d.clear()
	rng.randomize()
	for i in MAX_VOICES:
		var p3 := AudioStreamPlayer3D.new()
		p3.attenuation_model = AudioStreamPlayer3D.ATTENUATION_DISABLED
		p3.panning_strength = 0.55
		p3.max_db = 6.0
		p3.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
		holder.add_child(p3)
		pool3d.append({"node": p3, "priority": 0, "tag": "", "started": 0.0})
		var p2 := AudioStreamPlayer.new()
		holder.add_child(p2)
		pool2d.append({"node": p2, "priority": 0, "tag": "", "started": 0.0})
	return holder.is_inside_tree()
