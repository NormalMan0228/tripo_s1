extends RefCounted
## The protagonist's little voice: soft, cute synthesized vowel efforts (no words) and
## reward chimes. Static helpers only; bus "SFX" (else Master), not positional (the hero
## is the listener):
##   const HeroVoice = preload("res://scripts/hero_voice.gd")
##   HeroVoice.play(app, event: String, db := 0.0, force := false) -> bool
##
## Files: res://assets/sfx/hero/<event>_<n>.wav (tools/make_creature_sfx.py).
## events (chance = how often the effort is voiced, gap = minimum seconds between two):
##   "attack"        "hup!" / "hap!" / "heup!"        chance .6, gap .25
##   "attack_heavy"  "hyah!"                          chance 1,  gap .3
##   "hurt"          "ah!" / "eup!" / "ow"            chance 1,  gap .3
##   "pickup"        happy "oh!" / "ung!"             chance 1,  gap .5
##   "harvest"       effort "hn!" / "eung" / "hup"    chance .4, gap .6
##   "dodge"         quick exhale "hp!"               chance .8, gap .3
##   "tired"         "hah... hah..." (stamina empty)  chance 1,  gap 4
##   "eat"           contented "mm~!"                 chance 1,  gap .8
##   "faint"         "aww..." (run lost / 0 HP)       chance 1,  gap 2
##   "reward"        bright arpeggio + sparkle (chime, overlaps the voice)
##   "levelup"       rising run, chord and shimmer (chime, overlaps the voice)
## aliases: swing->attack, heavy->attack_heavy, damage->hurt, gather->harvest,
##   pick_up->pickup, death/down->faint, breath/exhausted->tired, level_up->levelup,
##   chime/win/day->reward
## One effort at a time: a new effort replaces the previous one unless that one ranks higher
## (faint > hurt > others) and is still in its first .25 s. force := true skips chance and gap.
const CreatureAudio = preload("res://scripts/creature_audio.gd")
const DIR := "res://assets/sfx/hero/"
## event: [dB, chance, gap s, rank]
const EVENTS := {
	"attack": [-14.0, 0.6, 0.25, 1], "attack_heavy": [-13.0, 1.0, 0.3, 1], "hurt": [-12.0, 1.0, 0.3, 3],
	"pickup": [-14.0, 1.0, 0.5, 1], "harvest": [-15.0, 0.4, 0.6, 1], "dodge": [-15.0, 0.8, 0.3, 1],
	"tired": [-15.0, 1.0, 4.0, 2], "eat": [-14.0, 1.0, 0.8, 1], "faint": [-12.0, 1.0, 2.0, 4],
	"reward": [-13.0, 1.0, 0.4, 0], "levelup": [-12.0, 1.0, 0.8, 0],
}
const CHIMES := ["reward", "levelup"]
const ALIASES := {"swing": "attack", "heavy": "attack_heavy", "damage": "hurt", "hit": "hurt", "gather": "harvest",
	"pick_up": "pickup", "pick": "pickup", "death": "faint", "down": "faint", "breath": "tired", "exhausted": "tired",
	"level": "levelup", "level_up": "levelup", "chime": "reward", "win": "reward", "day": "reward"}

static var cache := {}
static var last_take := {}
static var last_time := {}
static var effort: AudioStreamPlayer
static var effort_rank := 0
static var effort_started := -10.0
static var rng := RandomNumberGenerator.new()

static func play(app, event: String, db := 0.0, force := false) -> bool:
	event = ALIASES.get(event, event)
	if not EVENTS.has(event): return false
	var spec: Array = EVENTS[event]
	var now := Time.get_ticks_msec()*0.001
	if not force:
		if now-float(last_time.get(event, -10.0)) < float(spec[2]): return false
		if rng.randf() > float(spec[1]): return false
	var list := streams(event)
	if list.is_empty(): return false
	var take := rng.randi() % list.size()
	if list.size() > 1 and take == int(last_take.get(event, -1)): take = (take+1+rng.randi() % (list.size()-1)) % list.size()
	var pitch := rng.randf_range(0.97, 1.03)
	var ok := false
	if event in CHIMES:
		ok = CreatureAudio.emit(app, list[take], Vector3.INF, float(spec[0])+db, 1.0, 5, "hero/"+event)
	else:
		if not _effort(): return false
		var rank: int = spec[3]
		if effort.playing and effort_rank > rank and now-effort_started < 0.25: return false
		effort.stop()
		effort.stream = list[take]
		effort.volume_db = float(spec[0])+db
		effort.pitch_scale = pitch
		effort.bus = CreatureAudio.bus("SFX")
		effort.play()
		effort_rank = rank
		effort_started = now
		CreatureAudio.played += 1
		ok = true
	if ok:
		last_take[event] = take
		last_time[event] = now
	return ok

static func streams(event: String) -> Array:
	if cache.has(event): return cache[event]
	var list := []
	for n in range(1, 5):
		var path := DIR+event+"_%d.wav" % n
		if ResourceLoader.exists(path): list.append(load(path))
	cache[event] = list
	return list

static func speaking() -> bool:
	return is_instance_valid(effort) and effort.playing

static func _effort() -> bool:
	if is_instance_valid(effort) and effort.is_inside_tree(): return true
	if not CreatureAudio._ensure(): return false
	rng.randomize()
	effort = AudioStreamPlayer.new()
	effort.name = "HeroVoice"
	CreatureAudio.holder.add_child(effort)
	return effort.is_inside_tree()
