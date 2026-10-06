extends RefCounted
## Combat and survival one-shots: swings, impacts, dodges, crits, spawn/dissolve puffs,
## the hero being hit, the low-HP heartbeat, campfire fuel and the night/dawn stings.
## Static helpers only; pooled playback through creature_audio.gd (bus "SFX", else Master):
##   const CombatAudio = preload("res://scripts/combat_audio.gd")
##   CombatAudio.play(app, event: String, at := Vector3.INF, db := 0.0, pitch := 1.0) -> bool
##
## Files: res://assets/sfx/combat/<event>_<n>.wav (tools/make_creature_sfx.py), 1-3 takes,
## never the same take twice in a row, small pitch jitter.
## events (at = world position for distance falloff/panning; omit for the hero's own sounds):
##   "swing_axe" / "swing_axe_heavy"       low, weighty whoosh with an air push
##   "swing_spear" / "swing_spear_heavy"   thin fast whoosh with a faint shaft whistle
##   "swing_fist" / "swing_fist_heavy"     short "fft" with a sleeve rustle (no weapon)
##   "hit_flesh"   thump + smack (wolf, boar)          "hit_stone"  crack + chips (brute)
##   "hit_wood"    hollow thock (trees, shields)       "hit_spirit" chime-swish + motes (wisp, shroom)
##   "block"       weapon catches a blow: hard knock + scrape
##   "dodge"       roll: cloth whoosh + ground skid
##   "critical"    hit + bright "shing" + low boom + sparkles
##   "spawn"       enemy appears: dark reverse swell into a smoky pop
##   "dissolve"    enemy dies: falling shimmer, soft "fwoo", two fading notes
##   "player_hit"  the hero takes damage: soft punchy thump with a cartoon "bwom"
##   "fuel"        logs on the campfire: two knocks, a flare, crackle burst
##   "night"       sun-down sting: low minor swell, cold glints, far howl (2.2 s)
##   "dawn"        morning relief: warm major arpeggio, pad, birds (2.2 s)
##   "harvest_tree" / "harvest_stone" / "harvest_fiber" / "harvest_berry"  gathering hits
## aliases: swing->swing_fist, hit/impact->hit_flesh, parry->block, crit->critical,
##   enemy_spawn->spawn, enemy_death->dissolve, hurt/damage->player_hit, campfire->fuel,
##   night_start->night, morning->dawn, chop->harvest_tree, mine->harvest_stone
## Helpers:
##   CombatAudio.swing(app, weapon := "", heavy := false)   weapon "axe" / "spear" / "" (fist)
##   CombatAudio.impact(app, species, at, critical := false)  material from the species
##   CombatAudio.harvest(app, node_kind, at := Vector3.INF)    "tree" / "stone" / "fiber" / "berry"
##   CombatAudio.heartbeat(app, hp, max_hp := 100.0)  call on every HP update: loops below 30 %,
##       louder and faster as HP falls, fades out above it or at 0 HP
##   CombatAudio.material_for(species) -> "hit_flesh" / "hit_stone" / "hit_spirit"
const CreatureAudio = preload("res://scripts/creature_audio.gd")
const DIR := "res://assets/sfx/combat/"
## event: [dB at the hero, priority, pitch jitter]
const EVENTS := {
	"swing_axe": [-13.0, 2, 0.05], "swing_axe_heavy": [-12.0, 2, 0.04], "swing_spear": [-13.0, 2, 0.05],
	"swing_spear_heavy": [-12.0, 2, 0.04], "swing_fist": [-13.0, 2, 0.06], "swing_fist_heavy": [-12.0, 2, 0.05],
	"hit_flesh": [-10.5, 4, 0.06], "hit_stone": [-10.5, 4, 0.05], "hit_wood": [-11.0, 4, 0.06], "hit_spirit": [-11.0, 4, 0.04],
	"block": [-11.0, 4, 0.04], "dodge": [-13.0, 3, 0.05], "critical": [-9.5, 5, 0.02], "spawn": [-11.0, 3, 0.04],
	"dissolve": [-11.0, 4, 0.03], "player_hit": [-10.0, 5, 0.04], "fuel": [-11.0, 3, 0.03],
	"night": [-11.0, 6, 0.0], "dawn": [-11.0, 6, 0.0],
	"harvest_tree": [-12.0, 2, 0.06], "harvest_stone": [-12.0, 2, 0.05], "harvest_fiber": [-12.5, 2, 0.06], "harvest_berry": [-12.5, 2, 0.06],
}
const ALIASES := {"swing": "swing_fist", "punch": "swing_fist", "hit": "hit_flesh", "impact": "hit_flesh", "parry": "block",
	"crit": "critical", "enemy_spawn": "spawn", "enemy_death": "dissolve", "death": "dissolve", "hurt": "player_hit",
	"damage": "player_hit", "campfire": "fuel", "fire": "fuel", "night_start": "night", "dusk": "night", "morning": "dawn",
	"dawn_relief": "dawn", "chop": "harvest_tree", "mine": "harvest_stone", "harvest": "harvest_tree"}
const MATERIAL := {"wolf": "hit_flesh", "boar": "hit_flesh", "brute": "hit_stone", "wisp": "hit_spirit", "shroom": "hit_spirit"}
const HEART_START := 0.3

static var cache := {}
static var last_take := {}
static var heart: AudioStreamPlayer
static var heart_tween: Tween
static var rng := RandomNumberGenerator.new()

static func play(app, event: String, at := Vector3.INF, db := 0.0, pitch := 1.0) -> bool:
	event = ALIASES.get(event, event)
	if not EVENTS.has(event): return false
	var list := streams(event)
	if list.is_empty(): return false
	var take := rng.randi() % list.size()
	if list.size() > 1 and take == int(last_take.get(event, -1)): take = (take+1+rng.randi() % (list.size()-1)) % list.size()
	var spec: Array = EVENTS[event]
	var jitter: float = spec[2]
	if not CreatureAudio.emit(app, list[take], at, float(spec[0])+db, pitch*rng.randf_range(1.0-jitter, 1.0+jitter), int(spec[1]), "combat/"+event):
		return false
	last_take[event] = take
	return true

static func streams(event: String) -> Array:
	if cache.has(event): return cache[event]
	var list := []
	for n in range(1, 5):
		var path := DIR+event+"_%d.wav" % n
		if ResourceLoader.exists(path): list.append(load(path))
	cache[event] = list
	return list

static func swing(app, weapon := "", heavy := false) -> bool:
	var kind := "axe" if weapon == "axe" else ("spear" if weapon == "spear" else "fist")
	return play(app, "swing_"+kind+("_heavy" if heavy else ""))

static func material_for(species: String) -> String:
	return MATERIAL.get(CreatureAudio.species_name(species), "hit_flesh")

static func impact(app, species: String, at: Vector3, critical := false) -> bool:
	var ok := play(app, material_for(species), at)
	if critical: ok = play(app, "critical", at) or ok
	return ok

static func harvest(app, node_kind: String, at := Vector3.INF) -> bool:
	var event: String = {"tree": "harvest_tree", "stone": "harvest_stone", "fiber": "harvest_fiber", "berry": "harvest_berry"}.get(node_kind, "harvest_fiber")
	return play(app, event, at)

## Low-HP heartbeat loop on its own player: off at or above 30 % HP, then louder (-22 -> -9 dB)
## and faster (pitch 1.0 -> 1.4) toward 0; stops when hp <= 0.
static func heartbeat(app, hp: float, max_hp := 100.0) -> void:
	var ratio := clampf(hp/maxf(max_hp, 1.0), 0.0, 1.0)
	var on := hp > 0.0 and ratio < HEART_START
	if not on:
		if is_instance_valid(heart) and heart.playing and heart.is_inside_tree():
			if heart_tween and heart_tween.is_valid(): heart_tween.kill()
			heart_tween = heart.create_tween()
			heart_tween.tween_property(heart, "volume_db", -50.0, 0.6)
			heart_tween.tween_callback(heart.stop)
		return
	if not _heart(): return
	var urgency := 1.0-ratio/HEART_START
	if heart_tween and heart_tween.is_valid(): heart_tween.kill()
	heart.pitch_scale = lerpf(1.0, 1.4, urgency)
	var target := lerpf(-22.0, -9.0, urgency)
	if not heart.playing:
		heart.volume_db = -40.0
		heart.play()
	heart_tween = heart.create_tween()
	heart_tween.tween_property(heart, "volume_db", target, 0.4)

static func heartbeat_playing() -> bool:
	return is_instance_valid(heart) and heart.playing

static func _heart() -> bool:
	if is_instance_valid(heart) and heart.is_inside_tree(): return true
	if not CreatureAudio._ensure(): return false
	var stream := load(DIR+"heartbeat_loop.wav") as AudioStreamWAV
	if stream == null: return false
	if stream.loop_mode == AudioStreamWAV.LOOP_DISABLED:
		stream = stream.duplicate()
		stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
		stream.loop_begin = 0
		stream.loop_end = int(round(stream.get_length()*stream.mix_rate))
	heart = AudioStreamPlayer.new()
	heart.name = "Heartbeat"
	heart.stream = stream
	heart.bus = CreatureAudio.bus("SFX")
	CreatureAudio.holder.add_child(heart)
	return heart.is_inside_tree()
