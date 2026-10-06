extends RefCounted
## Monster voices for the survival nights, plus the pooled one-shot engine that
## combat_audio.gd and hero_voice.gd share. Static helpers only (no autoload):
##   const CreatureAudio = preload("res://scripts/creature_audio.gd")
##   CreatureAudio.play(app_or_node, species: String, event: String, at: Vector3, variant := "") -> bool
##
## Sounds are pre-rendered by tools/make_creature_sfx.py into
##   res://assets/sfx/creatures/<species>_<event>_<region>_<n>.wav   (2 takes each)
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
##   "alert"   aggro call when it appears or first targets the player   (alias "aggro", "spawn")
##   "windup"  attack anticipation, timed to the server wind-up: wolf .6 s, boar .8 s,
##             brute 1.1 s, wisp .85 s, shroom .8 s; call when phase becomes "windup"
##   "strike"  the blow lands (phase windup -> recover)                 (alias "attack")
##   "hurt"    hp went down                                             (alias "hit")
##   "death"   killed / removed with hp <= 0                            (alias "die")
## variant: region colouring layered into every take
##   "forest" / "moss"  leaf-and-moss rustle, twig snaps
##   "quarry" / "ember" warm crackle, ember flare on strike/death
##   "frost"  / "ice"   crystalline shimmer, ice crack on strike/hurt/death
##   ""  reads app.run.map_id when app has a run, else "forest".
## at: world position. Loudness falls off from the hero (app.player, else the camera):
##   flat inside FALLOFF_START m, about -5 dB per doubling after, silent past AUDIBLE m.
##   When the viewport has a Camera3D the sound is panned (AudioStreamPlayer3D, attenuation
##   off); otherwise a flat player is used. Vector3.INF = not positional.
## Returns true when a sound started. Takes never repeat back to back; pitch +-5 %.
## Voices: MAX_VOICES pooled 3D players + MAX_VOICES flat players under root/GameSfx,
## MAX_PER_SPECIES at once per species; a full pool steals the lowest-priority, oldest voice
## (death 5 > strike/hurt 4 > alert/windup 3 > idle 1) or drops the new sound if it ranks lower.
## Bus: "SFX" when the project has it, else "Master".
##
## Shared engine (used by combat_audio.gd / hero_voice.gd):
##   CreatureAudio.emit(app_or_node, stream, at, volume_db, pitch, priority, tag, bus := "SFX") -> bool
##   CreatureAudio.listener(app_or_node) -> Vector3 (Vector3.INF when unknown)
##   CreatureAudio.find_app(node) -> Object (the node, the current scene or an ancestor with `player`)
##   CreatureAudio.bus(name) -> StringName, CreatureAudio.active(tag_prefix := "") -> int
##   CreatureAudio.preload_all() warms every creature stream (call at run start to avoid hitches).
##   CreatureAudio.played: int counts sounds started (tests).

const DIR := "res://assets/sfx/creatures/"
const SPECIES := ["wolf", "boar", "brute", "wisp", "shroom"]
const EVENTS := ["idle", "alert", "windup", "strike", "hurt", "death"]
const REGIONS := ["forest", "quarry", "frost"]
const SPECIES_ALIASES := {"beast": "wolf", "shadow": "wolf", "shadow_beast": "wolf", "golem": "brute", "guardian": "brute",
	"imp": "wisp", "ember": "wisp", "fire": "wisp", "mushroom": "shroom", "spore": "shroom"}
const EVENT_ALIASES := {"aggro": "alert", "notice": "alert", "spawn": "alert", "wind_up": "windup", "charge": "windup",
	"attack": "strike", "bite": "strike", "slam": "strike", "hit": "hurt", "damage": "hurt", "die": "death", "dead": "death",
	"breath": "idle", "chase": "idle"}
const REGION_ALIASES := {"forest": "forest", "moss": "forest", "quarry": "quarry", "ember": "quarry", "frost": "frost", "ice": "frost"}
## Level (dB) at the hero for each event; the files are levelled, these set the mix.
## Door sounds play at -22.5 dBFS (file) -9 dB; a close strike lands ~3 dB above a door.
const EVENT_DB := {"idle": -15.0, "alert": -11.0, "windup": -12.0, "strike": -10.0, "hurt": -11.5, "death": -10.5}
const PRIORITY := {"idle": 1, "alert": 3, "windup": 3, "strike": 4, "hurt": 4, "death": 5}
const MAX_VOICES := 10
const MAX_PER_SPECIES := 3
const MAX_IDLE := 2
const IDLE_GAP := 0.9
const FALLOFF_START := 2.5
const AUDIBLE := 34.0

static var played := 0
static var holder: Node3D
static var pool3d: Array = []
static var pool2d: Array = []
static var cache := {}
static var last_take := {}
static var last_idle := {}
static var last_key := {}
static var rng := RandomNumberGenerator.new()

static func play(app_or_node, species: String, event: String, at: Vector3, variant := "") -> bool:
	species = species_name(species)
	event = event_name(event)
	var region := region_name(variant, app_or_node)
	var now := Time.get_ticks_msec()*0.001
	if event == "idle":
		if now-float(last_idle.get(species, -10.0)) < IDLE_GAP: return false
		if active("creature/", "idle") >= MAX_IDLE: return false
	var list := streams(species, event, region)
	if list.is_empty(): return false
	var key := "%s_%s_%s" % [species, event, region]
	# Two of the same call within 40 ms (two wolves hit together) read as one louder call.
	if now-float(last_key.get(key, -10.0)) < 0.04: return false
	var take := rng.randi() % list.size()
	if list.size() > 1 and take == int(last_take.get(key, -1)): take = (take+1+rng.randi() % (list.size()-1)) % list.size()
	var db: float = EVENT_DB[event]+rng.randf_range(-1.0, 1.0)
	var pitch := rng.randf_range(0.93, 1.07) if event == "idle" else rng.randf_range(0.95, 1.05)
	var tag := "creature/%s/%s" % [species, event]
	var priority: int = PRIORITY[event]
	# A species may hold MAX_PER_SPECIES voices; a more important call replaces its weakest one.
	var mine := _active_entries("creature/%s/" % species)
	if mine.size() >= MAX_PER_SPECIES:
		mine.sort_custom(func(a, b): return a.priority < b.priority or (a.priority == b.priority and a.started < b.started))
		if int(mine[0].priority) > priority: return false
		mine[0].node.stop()
	if not emit(app_or_node, list[take], at, db, pitch, priority, tag): return false
	last_take[key] = take
	last_key[key] = now
	if event == "idle": last_idle[species] = now
	return true

static func species_name(species: String) -> String:
	species = species.to_lower()
	species = SPECIES_ALIASES.get(species, species)
	return species if species in SPECIES else "wolf"

static func event_name(event: String) -> String:
	event = event.to_lower()
	event = EVENT_ALIASES.get(event, event)
	return event if event in EVENTS else "idle"

static func region_name(variant: String, app_or_node = null) -> String:
	var region: String = REGION_ALIASES.get(variant.to_lower(), "")
	if region.is_empty():
		var app = find_app(app_or_node)
		if app != null and "run" in app and app.run is Dictionary:
			region = REGION_ALIASES.get(str(app.run.get("map_id", "forest")), "forest")
	return region if not region.is_empty() else "forest"

## Every take for one sound, loaded once. A missing region falls back to the forest takes.
static func streams(species: String, event: String, region: String) -> Array:
	var key := "%s_%s_%s" % [species, event, region]
	if cache.has(key): return cache[key]
	var list := []
	for n in range(1, 5):
		var path := DIR+key+"_%d.wav" % n
		if ResourceLoader.exists(path): list.append(load(path))
	if list.is_empty() and region != "forest": list = streams(species, event, "forest")
	cache[key] = list
	return list

static func preload_all() -> int:
	var count := 0
	for species in SPECIES:
		for event in EVENTS:
			for region in REGIONS: count += streams(species, event, region).size()
	return count

# ------------------------------------------------------------------ shared engine
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
