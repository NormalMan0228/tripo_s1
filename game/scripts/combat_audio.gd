extends RefCounted
## Combat and survival one-shots: swings, impacts, dodges, crits, spawn/dissolve puffs,
## the hero being hit, the low-HP heartbeat, campfire fuel and loop, the night/dawn stings and
## the survival status cues (hunger, cold, ember ground, night warning, depleted nodes, crafts).
## Static helpers only; pooled playback through creature_audio.gd (bus "SFX", else Master):
##   const CombatAudio = preload("res://scripts/combat_audio.gd")
##   CombatAudio.play(app, event: String, at := Vector3.INF, db := 0.0, pitch := 1.0) -> bool
##
## Files: res://assets/sfx/combat/<event>_<n>.wav (tools/make_creature_sfx.py takes 1-3, then
## tools/sfx/gen_combat.py: 5-14 structurally different takes per event; the team's recorded
## harvest_tree/stone/fiber_1 plus takes derived from them). Takes come from sfx_bank.gd: every
## take once per shuffle-bag cycle, never the same take twice in a row (with 6+ takes not one of
## the last two), loaded on first use; pitch jitter per event and +-1 dB.
## events (at = world position for distance falloff/panning; omit for the hero's own sounds):
##   "swing_axe" / "swing_axe_heavy"       low, weighty whoosh with an air push
##   "swing_spear" / "swing_spear_heavy"   thin fast whoosh with a faint shaft whistle
##   "swing_fist" / "swing_fist_heavy"     short "fft" with a sleeve rustle (no weapon)
##   "hit_flesh"   thump + smack (wolf, boar)          "hit_stone"  crack + chips (brute)
##   "hit_wood"    hollow thock (trees, shields)       "hit_spirit" chime-swish + motes (wisp, shroom)
##   "block"       a blow interrupts a telegraphed strike: hard knock + scrape
##   "dodge"       sprint/dodge start: cloth whoosh + ground skid
##   "whiff"       an enemy strike lands where the hero no longer is
##   "critical"    hit + bright "shing" + low boom + sparkles (the kill blow)
##   "spawn"       enemy appears: dark reverse swell into a smoky pop (a roster is staggered)
##   "dissolve"    enemy dies: falling shimmer, soft "fwoo", fading notes (staggered too)
##   "player_hit"  the hero takes damage: soft punchy thump with a cartoon "bwom"
##   "equip"       a new weapon in hand          "fuel"  logs on the campfire
##   "sputter"     the campfire spits / is about to die     "campfire_loop.wav" (campfire())
##   "night"       sun-down sting                "dawn"  morning relief
##   "night_warn"  ten seconds of daylight left
##   "buff_warm" / "buff_heal" / "buff_end"  the campfire's warmth buff: stepping into it, a heal tick, it fading
##   "cold" / "hunger" / "ember"   status cues (cue())
##   "depleted_tree" / "_stone" / "_fiber" / "_berry"   a resource node is used up
##   "craft_tool" / "craft_soup" / "craft_bandage"      survival recipes;  "bandage" = using one
##   "harvest_tree" / "harvest_stone" / "harvest_fiber" / "harvest_berry"  gathering hits
## aliases: swing->swing_fist, hit/impact->hit_flesh, parry->block, crit->critical,
##   enemy_spawn->spawn, enemy_death->dissolve, hurt/damage->player_hit, campfire->fuel,
##   night_start->night, morning->dawn, chop->harvest_tree, mine->harvest_stone, miss->whiff,
##   heal->bandage, starving->hunger, freezing->cold, burn->ember
## Helpers:
##   CombatAudio.swing(app, weapon := "", heavy := false)   weapon "axe" / "spear" / "" (fist); every
##       third swing of a quick combo is the heavy take
##   CombatAudio.impact(app, species, at, critical := false)  material from the species
##   CombatAudio.harvest(app, node_kind, at := Vector3.INF, tool := "axe")  "tree" / "stone" / "fiber" /
##       "berry"; a tree without an axe is a hollow knock (hit_wood)
##   CombatAudio.depleted(app, node_kind, at)                  the node is used up
##   CombatAudio.craft(app, recipe)                            "axe"/"spear" -> tool, "soup", "bandage"
##   CombatAudio.heartbeat(app, hp, max_hp := 100.0)  call on every HP update: loops below 30 %,
##       louder and faster as HP falls, fades out above it or at 0 HP
##   CombatAudio.campfire(app, seconds_left, at := Vector3.ZERO, night := false)  call on every run
##       update: crackling loop at the fire while it burns (louder when low, sputters below 7 s);
##       fades out when it goes out or when the calls stop (leaving the run)
##   CombatAudio.cue(app, event, on, every := 0.0) -> bool   plays when `on` turns true, then every
##       `every` s (+-15 %) while it stays true
##   CombatAudio.edge(key, on) -> bool       true once when `on` turns true (state per key)
##   CombatAudio.changed(key, value) -> bool true when value differs from the last call's (first: false)
##   CombatAudio.later(app, event, delay, at := Vector3.INF, db := 0.0)  play() after delay s
##   CombatAudio.material_for(species) -> "hit_flesh" / "hit_stone" / "hit_spirit"
const CreatureAudio = preload("res://scripts/creature_audio.gd")
const SfxBank = preload("res://scripts/sfx_bank.gd")
const DIR := "res://assets/sfx/combat/"
## event: [dB at the hero, priority, pitch jitter]
const EVENTS := {
	"swing_axe": [-13.0, 2, 0.05], "swing_axe_heavy": [-12.0, 2, 0.04], "swing_spear": [-13.0, 2, 0.05],
	"swing_spear_heavy": [-12.0, 2, 0.04], "swing_fist": [-13.0, 2, 0.06], "swing_fist_heavy": [-12.0, 2, 0.05],
	"hit_flesh": [-10.5, 4, 0.06], "hit_stone": [-10.5, 4, 0.05], "hit_wood": [-11.0, 4, 0.06], "hit_spirit": [-11.0, 4, 0.04],
	"block": [-11.0, 4, 0.04], "dodge": [-13.0, 3, 0.05], "whiff": [-12.5, 3, 0.05], "critical": [-9.5, 5, 0.02],
	"spawn": [-11.0, 3, 0.04], "dissolve": [-11.0, 4, 0.03], "player_hit": [-10.0, 5, 0.04], "equip": [-13.0, 2, 0.04],
	"fuel": [-11.0, 3, 0.03], "sputter": [-14.0, 1, 0.06], "night": [-11.0, 6, 0.0], "dawn": [-11.0, 6, 0.0],
	"night_warn": [-11.5, 6, 0.0], "cold": [-13.0, 3, 0.04], "hunger": [-12.0, 3, 0.05], "ember": [-12.0, 3, 0.05],
	"buff_warm": [-12.0, 3, 0.02], "buff_heal": [-15.0, 2, 0.03], "buff_end": [-14.0, 2, 0.02],
	"depleted_tree": [-11.5, 3, 0.04], "depleted_stone": [-11.5, 3, 0.04], "depleted_fiber": [-12.0, 3, 0.05], "depleted_berry": [-12.0, 3, 0.05],
	"craft_tool": [-11.5, 3, 0.04], "craft_soup": [-11.5, 3, 0.04], "craft_bandage": [-12.0, 3, 0.04], "bandage": [-12.0, 3, 0.04],
	"harvest_tree": [-12.0, 2, 0.06], "harvest_stone": [-12.0, 2, 0.05], "harvest_fiber": [-12.5, 2, 0.06], "harvest_berry": [-12.5, 2, 0.06],
}
const ALIASES := {"swing": "swing_fist", "punch": "swing_fist", "hit": "hit_flesh", "impact": "hit_flesh", "parry": "block",
	"crit": "critical", "enemy_spawn": "spawn", "enemy_death": "dissolve", "death": "dissolve", "hurt": "player_hit",
	"damage": "player_hit", "campfire": "fuel", "fire": "fuel", "night_start": "night", "dusk": "night", "morning": "dawn",
	"dawn_relief": "dawn", "chop": "harvest_tree", "mine": "harvest_stone", "harvest": "harvest_tree", "miss": "whiff",
	"heal": "bandage", "starving": "hunger", "freezing": "cold", "burn": "ember", "warning": "night_warn"}
const MATERIAL := {"wolf": "hit_flesh", "boar": "hit_flesh", "brute": "hit_stone", "wisp": "hit_spirit", "shroom": "hit_spirit"}
const RECIPE := {"axe": "craft_tool", "spear": "craft_tool", "soup": "craft_soup", "bandage": "craft_bandage"}
## Minimum seconds between two plays of one event (sprints restarting, double crafts).
const GAP := {"dodge": 0.35, "equip": 0.3, "whiff": 0.12, "sputter": 0.6, "block": 0.08}
## Events a whole roster fires in one frame: spread over up to STAGGER_MAX s, at most GROUP_MAX
## audible per burst (the rest would only add level, not information).
const STAGGERED := ["spawn", "dissolve"]
const STAGGER_WINDOW := 0.3
const STAGGER_MAX := 0.25
const GROUP_MAX := 4
const COMBO_GAP := 1.1
## Takes that open with silence the file must keep (a team recording): playback starts this many
## seconds in. harvest_fiber_1 has ~98 ms of air before the tear; the derived takes start at once.
const LEAD_IN := {"harvest_fiber_1.wav": 0.09}
const HEART_START := 0.3
const FIRE_LOW := 7.0
const FIRE_DB := -17.0

static var cache := {}
static var last_take := {}
static var last_time := {}
static var heart: AudioStreamPlayer
static var heart_tween: Tween
## True while heart_tween / fire_tween is the fade to silence (a fade is started once, never restarted).
static var heart_fading := false
static var fire: AudioStreamPlayer3D
static var fire_tween: Tween
static var fire_fading := false
static var fire_watch_id := 0
static var fire_seen := -10.0
static var fire_next_sputter := 0.0
static var rng := RandomNumberGenerator.new()
static var combo := 0
static var combo_at := -10.0
static var group_start := {}
static var group_count := {}
static var edges := {}
static var values := {}
static var cue_next := {}

static func play(app, event: String, at := Vector3.INF, db := 0.0, pitch := 1.0) -> bool:
	event = ALIASES.get(event, event)
	if not EVENTS.has(event): return false
	var now := Time.get_ticks_msec()*0.001
	if GAP.has(event) and now-float(last_time.get(event, -10.0)) < float(GAP[event]): return false
	if event in STAGGERED: return _staggered(app, event, at, db, pitch, now)
	return _emit(app, event, at, db, pitch, now)

static func _emit(app, event: String, at: Vector3, db: float, pitch: float, now: float) -> bool:
	var path := SfxBank.pick_path(DIR+event)
	if path.is_empty(): return false
	var spec: Array = EVENTS[event]
	var jitter: float = spec[2]
	var stream := SfxBank.stream(path)
	if not CreatureAudio.emit(app, stream, at, float(spec[0])+db+SfxBank.db(1.0), pitch*SfxBank.pitch(jitter), int(spec[1]), "combat/"+event):
		return false
	if LEAD_IN.has(path.get_file()): _skip_lead_in(stream, float(LEAD_IN[path.get_file()]))
	last_take[event] = path
	last_time[event] = now
	return true

## Restarts the pooled voice CreatureAudio.emit() just started for `stream` (the newest one playing
## it) `seconds` in, past the take's silent lead-in.
static func _skip_lead_in(stream: AudioStream, seconds: float) -> void:
	if stream == null or seconds <= 0.0 or seconds >= stream.get_length(): return
	var newest: Node = null
	var started := -1.0
	for entry in CreatureAudio.pool3d + CreatureAudio.pool2d:
		var node = entry.get("node")
		if is_instance_valid(node) and node.stream == stream and node.playing and float(entry.get("started", 0.0)) >= started:
			newest = node
			started = float(entry.get("started", 0.0))
	if newest != null: newest.call("play", seconds)

## The first of a burst plays at once; the next ones of the same event within STAGGER_WINDOW s are
## spread 60-250 ms apart (a pack appearing reads as a ripple, not one loud stacked hit).
static func _staggered(app, event: String, at: Vector3, db: float, pitch: float, now: float) -> bool:
	if now-float(group_start.get(event, -10.0)) > STAGGER_WINDOW:
		group_start[event] = now
		group_count[event] = 0
	var index: int = group_count.get(event, 0)
	group_count[event] = index+1
	if index == 0: return _emit(app, event, at, db, pitch, now)
	if index >= GROUP_MAX: return false
	var delay := minf(STAGGER_MAX, index*rng.randf_range(0.06, 0.09)+rng.randf_range(0.0, 0.03))
	var level := db-1.5*index
	# The app is held weakly (CreatureAudio.after): a scene left mid-burst just drops the rest.
	return CreatureAudio.after(delay, app, func(target) -> void:
		_emit(target, event, at, level, pitch, Time.get_ticks_msec()*0.001))

## play() after `delay` s (skipped when `app` is gone by then; the timer holds it weakly).
static func later(app, event: String, delay: float, at := Vector3.INF, db := 0.0) -> void:
	CreatureAudio.after(delay, app, func(target) -> void: play(target, event, at, db))

## Every take of an event, loaded (tests and warm-up; play() loads lazily).
static func streams(event: String) -> Array:
	event = ALIASES.get(event, event)
	if cache.has(event): return cache[event]
	var list := []
	for path in SfxBank.paths(DIR+event):
		var stream := SfxBank.stream(path)
		if stream != null: list.append(stream)
	cache[event] = list
	return list

static func swing(app, weapon := "", heavy := false) -> bool:
	var kind := "axe" if weapon == "axe" else ("spear" if weapon == "spear" else "fist")
	var now := Time.get_ticks_msec()*0.001
	combo = combo+1 if now-combo_at < COMBO_GAP else 1
	combo_at = now
	if combo % 3 == 0: heavy = true
	return play(app, "swing_"+kind+("_heavy" if heavy else ""))

static func material_for(species: String) -> String:
	return MATERIAL.get(CreatureAudio.species_name(species), "hit_flesh")

static func impact(app, species: String, at: Vector3, critical := false) -> bool:
	var ok := play(app, material_for(species), at)
	if critical: ok = play(app, "critical", at) or ok
	return ok

## tool: the hero's tool; a tree worked without an axe knocks hollow (hit_wood) instead of the axe chop.
static func harvest(app, node_kind: String, at := Vector3.INF, tool := "axe") -> bool:
	if node_kind == "tree" and tool != "axe": return play(app, "hit_wood", at, -1.5)
	var event: String = {"tree": "harvest_tree", "stone": "harvest_stone", "fiber": "harvest_fiber", "berry": "harvest_berry"}.get(node_kind, "harvest_fiber")
	return play(app, event, at)

static func depleted(app, node_kind: String, at := Vector3.INF) -> bool:
	var kind: String = node_kind if node_kind in ["tree", "stone", "fiber", "berry"] else "fiber"
	return play(app, "depleted_"+kind, at)

static func craft(app, recipe: String) -> bool:
	return play(app, RECIPE.get(recipe, "craft_tool"))

## True once each time `on` turns true for `key`.
static func edge(key: String, on: bool) -> bool:
	var was: bool = edges.get(key, false)
	edges[key] = on
	return on and not was

## True when `value` differs from the value of the previous call for `key` (false on the first call).
static func changed(key: String, value) -> bool:
	var had := values.has(key)
	var before = values.get(key)
	values[key] = value
	return had and before != value

## A status cue: plays when `on` turns true, then again every `every` s (+-15 %) while it stays on.
static func cue(app, event: String, on: bool, every := 0.0, at := Vector3.INF) -> bool:
	var key := "cue/"+event
	var now := Time.get_ticks_msec()*0.001
	var start := edge(key, on)
	if not on: return false
	if not start and (every <= 0.0 or now < float(cue_next.get(key, INF))): return false
	cue_next[key] = now+every*rng.randf_range(0.85, 1.15) if every > 0.0 else INF
	return play(app, event, at)

## Low-HP heartbeat loop on its own player: off at or above 30 % HP, then louder (-22 -> -9 dB)
## and faster (pitch 1.0 -> 1.4) toward 0; stops when hp <= 0.
static func heartbeat(app, hp: float, max_hp := 100.0) -> void:
	var ratio := clampf(hp/maxf(max_hp, 1.0), 0.0, 1.0)
	var on := hp > 0.0 and ratio < HEART_START
	if not on:
		_heart_fade()
		return
	if not _heart(): return
	var urgency := 1.0-ratio/HEART_START
	if heart_tween and heart_tween.is_valid(): heart_tween.kill()
	heart_fading = false
	heart.pitch_scale = lerpf(1.0, 1.4, urgency)
	var target := lerpf(-22.0, -9.0, urgency)
	if not heart.playing:
		heart.volume_db = -40.0
		heart.play()
	heart_tween = heart.create_tween()
	heart_tween.tween_property(heart, "volume_db", target, 0.4)

static func heartbeat_playing() -> bool:
	return is_instance_valid(heart) and heart.playing

## Fades the heartbeat out and stops it. Idempotent: HP updates arrive several times a second, and
## restarting the 0.6 s fade on each one would keep the stop at its end from ever running.
static func _heart_fade() -> void:
	if not is_instance_valid(heart) or not heart.playing or not heart.is_inside_tree(): return
	if heart_fading and heart_tween and heart_tween.is_valid(): return
	if heart_tween and heart_tween.is_valid(): heart_tween.kill()
	heart_fading = true
	heart_tween = heart.create_tween()
	heart_tween.tween_property(heart, "volume_db", -50.0, 0.6)
	heart_tween.tween_callback(heart.stop)

static func _heart() -> bool:
	if is_instance_valid(heart) and heart.is_inside_tree(): return true
	if not CreatureAudio._ensure(): return false
	var stream := _looped(DIR+"heartbeat_loop.wav")
	if stream == null: return false
	heart = AudioStreamPlayer.new()
	heart.name = "Heartbeat"
	heart.stream = stream
	heart.bus = CreatureAudio.bus("SFX")
	CreatureAudio.holder.add_child(heart)
	return heart.is_inside_tree()

## The campfire's crackle while it burns: positioned at `at`, distance falloff like emit(), a little
## louder in its last FIRE_LOW s with random sputters (and at night a quiet spit now and then).
## Fades out when seconds_left reaches 0 or when no call came for 1.5 s (the run was left); the fade
## runs once to its end however often the out-calls keep coming (one last sputter as it goes out).
static func campfire(app, seconds_left: float, at := Vector3.ZERO, night := false) -> void:
	var now := Time.get_ticks_msec()*0.001
	if seconds_left <= 0.0:
		if campfire_playing() and not fire_fading and fire.volume_db > -45.0: play(app, "sputter", at, 2.0)
		_fire_fade()
		return
	if not _fire(): return
	fire_seen = now
	var target := FIRE_DB+(2.5 if seconds_left < FIRE_LOW else 0.0)
	var ears := CreatureAudio.listener(app)
	if ears != Vector3.INF: target += CreatureAudio.distance_db(ears.distance_to(at))
	fire.global_position = at
	if not fire.playing:
		fire.volume_db = -45.0
		fire.play(rng.randf_range(0.0, maxf(fire.stream.get_length()-0.1, 0.0)))
	# Fed again (or back in the run): a fade under way turns back into the burning level.
	if fire_tween and fire_tween.is_valid(): fire_tween.kill()
	fire_fading = false
	fire_tween = fire.create_tween()
	fire_tween.tween_property(fire, "volume_db", target, 0.35)
	if seconds_left < FIRE_LOW or night:
		if now >= fire_next_sputter:
			if fire_next_sputter > 0.0: play(app, "sputter", at, -2.0 if seconds_left >= FIRE_LOW else 0.0)
			fire_next_sputter = now+(rng.randf_range(1.2, 3.0) if seconds_left < FIRE_LOW else rng.randf_range(6.0, 14.0))
	else:
		fire_next_sputter = 0.0

static func campfire_playing() -> bool:
	return is_instance_valid(fire) and fire.playing

static func _fire() -> bool:
	if is_instance_valid(fire) and fire.is_inside_tree(): return true
	if not CreatureAudio._ensure(): return false
	var stream := _looped(DIR+"campfire_loop.wav")
	if stream == null: return false
	fire = AudioStreamPlayer3D.new()
	fire.name = "Campfire"
	fire.stream = stream
	fire.attenuation_model = AudioStreamPlayer3D.ATTENUATION_DISABLED
	fire.panning_strength = 0.5
	fire.max_db = 6.0
	fire.bus = CreatureAudio.bus("SFX")
	CreatureAudio.holder.add_child(fire)
	fire_fading = false
	fire_watch_id += 1
	_fire_watch(fire_watch_id)
	return fire.is_inside_tree()

## Polls twice a second while the loop exists: no campfire() call for 1.5 s = the run was left.
## One poll chain per fire player (`id`); a chain whose player was replaced ends.
static func _fire_watch(id: int) -> void:
	if id != fire_watch_id or not is_instance_valid(fire) or not fire.is_inside_tree(): return
	if fire.playing and Time.get_ticks_msec()*0.001-fire_seen > 1.5: _fire_fade()
	fire.get_tree().create_timer(0.5).timeout.connect(func() -> void: _fire_watch(id))

## Fades the loop to silence and stops it. Idempotent: the watchdog (every 0.5 s) and every run
## update with the fire out call it again; a fade already under way is left to reach its stop,
## restarting it each time would hold the loop just above silence forever.
static func _fire_fade() -> void:
	fire_next_sputter = 0.0
	if not campfire_playing() or not fire.is_inside_tree(): return
	if fire_fading and fire_tween and fire_tween.is_valid(): return
	if fire_tween and fire_tween.is_valid(): fire_tween.kill()
	fire_fading = true
	fire_tween = fire.create_tween()
	fire_tween.tween_property(fire, "volume_db", -50.0, 0.8)
	fire_tween.tween_callback(fire.stop)

## A WAV made to loop: the import may already loop it; otherwise a forward loop over the file.
static func _looped(path: String) -> AudioStreamWAV:
	var stream := SfxBank.stream(path) as AudioStreamWAV
	if stream == null: return null
	if stream.loop_mode == AudioStreamWAV.LOOP_DISABLED:
		stream = stream.duplicate()
		stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
		stream.loop_begin = 0
		stream.loop_end = int(round(stream.get_length()*stream.mix_rate))
	return stream
