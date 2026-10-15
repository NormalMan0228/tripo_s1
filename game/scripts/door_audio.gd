extends RefCounted
## Door sounds for any door, anyone's: the hook for animated door leaves, visitors walking in and
## out, locked doors and knocks. Static API, no node to add:
##   const DoorAudio = preload("res://scripts/door_audio.gd")
##   DoorAudio.play(host, kind, room := "", at := Vector3.INF, db := 0.0) -> bool
## host: any node in the scene tree (the village main, the room studio); the small voice pool
##   lives under it and goes away with it.
## kind:
##   "open"   latch and hinge, the room's own takes (doors/<room>_open[_n].wav, transition.gd)
##   "close"  the leaf meeting the frame (doors/<room>_close[_n].wav)
##   "swing"  a slow hinge creak while a leaf visibly swings (doors/swing_n, 1.2-2.4 s); play it
##            with open/close when the door animates, not instead of them
##   "locked" a handle tried against a locked latch (doors/locked_n)
##   "knock"  knuckles on the door (interior/knock_n, else life/knock_n)
## room: the interior id ("home", "workshop", "01_cafe" ... "17_lighthouse"); "" or an unknown
##   room plays the generic door (transition.gd door_sound()).
## at: the door's world position. INF = the player's own door, flat like transition.play_door();
##   otherwise positional (AudioStreamPlayer3D, panned) and falling off with the distance from the
##   listener like footsteps (world_audio.gd distance_db), silent past AUDIBLE m.
## Every kind plays through sfx_bank.gd's shuffle bags (never the same take twice running) with
## +-3 % pitch and +-1 dB. The same kind at the same door within GAP_MS plays once (two peers
## arriving in one presence poll). False when nothing played.
## Sequences for an animated door: door_open(host, room, at, seconds) and door_close(...).
const Transition = preload("res://scripts/transition.gd")
const SfxBank = preload("res://scripts/sfx_bank.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const WorldAudio = preload("res://scripts/world_audio.gd")

const KINDS := ["open", "close", "swing", "locked", "knock"]
## Level of each kind before distance (open/close match transition.gd DOOR_DB).
const DB := {"open": -9.0, "close": -9.0, "swing": -11.0, "locked": -8.0, "knock": -8.0}
const VOICES := 4
const AUDIBLE := 30.0
const GAP_MS := 90
const POOL := "DoorAudioVoices"

static var _last := {}

static func play(host: Node, kind: String, room := "", at := Vector3.INF, db := 0.0) -> bool:
	if host == null or not is_instance_valid(host) or not host.is_inside_tree(): return false
	if not kind in KINDS: return false
	var falloff := 0.0
	if at != Vector3.INF:
		var ears := listener(host)
		if ears != Vector3.INF:
			var distance := ears.distance_to(at)
			if distance > AUDIBLE: return false
			falloff = WorldAudio.distance_db(distance)
	var key := "%s|%s|%s" % [kind, room, "" if at == Vector3.INF else str(at.snapped(Vector3.ONE * 0.5))]
	var now := Time.get_ticks_msec()
	if now - int(_last.get(key, -100000)) < GAP_MS: return false
	_last[key] = now
	if _last.size() > 64: _last.clear()
	var take := stream(kind, room)
	if take == null: return false
	var voice := _voice(host, at != Vector3.INF)
	if voice == null: return false
	voice.stop()
	voice.set("stream", take)
	voice.set("pitch_scale", SfxBank.pitch(0.03))
	voice.set("volume_db", float(DB[kind]) + db + falloff + SfxBank.db(1.0))
	if voice is AudioStreamPlayer3D: (voice as AudioStreamPlayer3D).global_position = at
	voice.call("play")
	return true

## A door leaf animating open over `seconds`: the latch and hinge at once, and the slow creak under
## it when the swing is long enough to hear (>= 0.8 s).
static func door_open(host: Node, room := "", at := Vector3.INF, seconds := 1.0) -> bool:
	var played := play(host, "open", room, at)
	if seconds >= 0.8: play(host, "swing", room, at, -2.0)
	return played

## A door leaf swinging shut over `seconds`: the creak while it moves, then the leaf meeting the
## frame when it lands (scheduled `seconds` later; skipped if the host has gone).
static func door_close(host: Node, room := "", at := Vector3.INF, seconds := 0.6) -> bool:
	if host == null or not is_instance_valid(host) or not host.is_inside_tree(): return false
	if seconds >= 0.8: play(host, "swing", room, at, -3.0)
	if seconds <= 0.05: return play(host, "close", room, at)
	var ref: WeakRef = weakref(host)
	host.get_tree().create_timer(seconds).timeout.connect(func():
		var node = ref.get_ref()
		if node != null and is_instance_valid(node) and node.is_inside_tree(): play(node, "close", room, at))
	return true

## The take a kind would play now (from its shuffle bag), else null.
static func stream(kind: String, room := "") -> AudioStream:
	match kind:
		"open", "close": return Transition.door_stream(kind, room)
		"swing": return SfxBank.pick("doors/swing")
		"locked":
			var take := SfxBank.pick("doors/locked")
			return take if take != null else SfxBank.pick("interior/knock")
		"knock":
			var take := SfxBank.pick("interior/knock")
			return take if take != null else SfxBank.pick("life/knock")
	return null

## Where the listener is: the host's player / hero, else the camera (INF: unknown).
static func listener(host: Node) -> Vector3:
	for member in ["player", "hero"]:
		var hero = host.get(member)
		if hero is Node3D and is_instance_valid(hero) and hero.is_inside_tree(): return hero.global_position
	var viewport := host.get_viewport()
	var camera: Camera3D = viewport.get_camera_3d() if viewport else null
	return camera.global_position if camera != null else Vector3.INF

## A free voice of the wanted kind under the host (made on first use), else the first busy one.
static func _voice(host: Node, positional: bool) -> Node:
	var pool := host.get_node_or_null(POOL)
	if pool == null:
		pool = Node.new()
		pool.name = POOL
		host.add_child(pool)
		for i in VOICES:
			var flat := AudioStreamPlayer.new()
			flat.bus = GameSettings.BUS_SFX
			pool.add_child(flat)
			var p3 := AudioStreamPlayer3D.new()
			p3.attenuation_model = AudioStreamPlayer3D.ATTENUATION_DISABLED
			p3.panning_strength = 0.6
			p3.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
			p3.bus = GameSettings.BUS_SFX
			pool.add_child(p3)
	var oldest: Node = null
	for child in pool.get_children():
		if (child is AudioStreamPlayer3D) != positional: continue
		if not child.get("playing"): return child
		if oldest == null: oldest = child
	return oldest
