extends SceneTree
## Village-life and core effect sounds (tools/sfx/gen_life.py), headless, after the import:
##   godot --headless --path game --script res://tests/life_sound_check.gd
## 1. Every family gen_life.py writes is imported and found with its exact take count.
## 2. LifeSfx (life_sfx.gd): play() puts a baked take of the kind on a voice, with the caller's
##    pitch times a small jitter and the baked-take gain; the forage kinds play the recorded
##    combat/harvest_* families without that gain; pocket() climbs its ladder; play_at() is
##    quieter with distance and silent far away.
## 3. Sound.effect (sound.gd): every core kind plays one of its takes on SFX (error on UI), and
##    voice_index ends one past the player it used.
## 4. Music (sound.gd): play_music starts the track with a play quota of at least two loops and
##    75 s and an offset inside the track; once the quota is used up the track fades out and a
##    20..60 s silence keeps music_mode; the gap ends by fading the same track back in; a mode
##    change during a gap starts the new track at once.
## Prints RESULT PASS|FAIL; exit code 1 on failure.
const SfxBank = preload("res://scripts/sfx_bank.gd")
const LifeSfx = preload("res://scripts/life_sfx.gd")
const Sound = preload("res://scripts/sound.gd")
const FAMILIES := {"life/tick":16,"life/nibble":10,"life/collect":12,"life/pop":8,"life/hoe":8,"life/seed":8,
	"life/water":6,"life/rustle":8,"life/rock":6,"life/shell":6,"life/escape":6,"life/cast":6,"life/plop":6,"life/bite":6,
	"life/catch":5,"life/card":4,"life/thrash":10,"life/ripple":6,"life/whiz":6,"life/windup":4,"life/strike":5,
	"life/reel_back":4,"life/fish_out":5,"life/rod_equip":4,"life/pocket":10,"life/fruit_detach":6,"life/bounce":8,
	"life/fruit_water":4,"life/grab":6,"life/knock":5,"life/bell":3,"core/reward":6,"core/gather":6,"core/craft":8,
	"core/eat":6,"core/bandage":4,"core/fire":4,"core/error":8,"core/sell":5,"core/buy":5,"core/errand":5,"core/newday":3,
	"core/win":3,"core/lose":3}

var failures := 0
var lines := PackedStringArray()

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, what: String) -> void:
	if ok: return
	failures += 1
	lines.append("FAIL "+what)

func run() -> void:
	var started := Time.get_ticks_msec()
	SfxBank.clear()
	SfxBank.set_seed(4711)
	check_families()
	var life: Node = LifeSfx.new()
	root.add_child(life)
	check_life(life)
	life.free()
	var sound: Node = Sound.new()
	root.add_child(sound)
	check_effects(sound)
	check_music(sound)
	sound.free()
	SfxBank.clear()
	lines.append("RESULT %s (%d problems, %.1f s)" % ["PASS" if failures == 0 else "FAIL", failures, (Time.get_ticks_msec()-started)*0.001])
	print("\n".join(lines))
	quit(1 if failures > 0 else 0)

# ------------------------------------------------------------------ 1. families
func check_families() -> void:
	var takes := 0
	for base in FAMILIES:
		var n := SfxBank.count(base)
		takes += n
		check(n == int(FAMILIES[base]), "%s has %d takes, want %d" % [base, n, FAMILIES[base]])
	lines.append("families %d, takes %d" % [FAMILIES.size(), takes])

# ------------------------------------------------------------------ 2. LifeSfx
func last_voice(life: Node) -> AudioStreamPlayer:
	return life.voices[(int(life.next)+life.voices.size()-1)%life.voices.size()]

func check_life(life: Node) -> void:
	check(life.voices.size() >= 6 and life.voices[0].bus == &"SFX", "life voices on SFX")
	for base in FAMILIES:
		if not String(base).begins_with("life/"): continue
		var kind := String(base).trim_prefix("life/")
		life.play(kind, 1.5, -2.0)
		var p := last_voice(life)
		var path := p.stream.resource_path if p.stream != null else ""
		check(path.begins_with("res://assets/sfx/life/"+kind+"_"), "life %s played %s" % [kind, path])
		check(p.pitch_scale >= 1.5*0.959 and p.pitch_scale <= 1.5*1.041, "life %s pitch %.3f not 1.5 +-4 %%" % [kind, p.pitch_scale])
		var want: float = LifeSfx.VOLUME-2.0+LifeSfx.BAKED_DB
		check(absf(p.volume_db-want) <= 1.01, "life %s volume %.2f, want %.2f +-1" % [kind, p.volume_db, want])
	# Forage pick-ups: the recorded harvest families, at the plain life level.
	for kind in LifeSfx.SAMPLES:
		life.play(kind)
		var p := last_voice(life)
		var path := p.stream.resource_path if p.stream != null else ""
		check(path.begins_with(String(LifeSfx.SAMPLES[kind])+"_"), "%s played %s" % [kind, path])
		check(absf(p.volume_db-LifeSfx.VOLUME) <= 1.01, "%s volume %.2f" % [kind, p.volume_db])
	# Back-to-back plays of one kind never repeat a take.
	var last := ""
	for i in 40:
		life.play("tick")
		var path: String = last_voice(life).stream.resource_path
		check(path != last, "tick repeated %s" % path)
		last = path
	# The pocket ladder climbs while items keep landing.
	var pitches: Array[float] = []
	for i in 4:
		life.pocket()
		pitches.append(last_voice(life).pitch_scale)
	check(pitches[0] < pitches[1] and pitches[1] < pitches[2] and pitches[2] < pitches[3], "pocket ladder %s" % [pitches])
	# Distance: quieter further away, nothing far off.
	var here := Vector3.ZERO
	life.play_at("bounce", Vector3(2, 0, 0), here)
	var near: float = last_voice(life).volume_db
	life.play_at("bounce", Vector3(15, 0, 0), here)
	var mid: float = last_voice(life).volume_db
	check(mid < near-6.0, "play_at 15 m (%.1f dB) not quieter than 2 m (%.1f dB)" % [mid, near])
	var before: int = life.next
	life.play_at("bounce", Vector3(60, 0, 0), here)
	check(int(life.next) == before, "play_at 60 m still played")

# ------------------------------------------------------------------ 3. Sound.effect
func check_effects(sound: Node) -> void:
	for base in FAMILIES:
		if not String(base).begins_with("core/"): continue
		var kind := String(base).trim_prefix("core/")
		sound.effect(kind)
		var p: AudioStreamPlayer = sound.voices[(sound.voice_index+sound.voices.size()-1)%sound.voices.size()]
		var path := p.stream.resource_path if p.stream != null else ""
		check(path.begins_with("res://assets/sfx/core/"+kind+"_"), "effect %s played %s" % [kind, path])
		check(p.bus == (&"UI" if kind == "error" else &"SFX"), "effect %s on bus %s" % [kind, p.bus])
		check(p.pitch_scale >= 0.959 and p.pitch_scale <= 1.041, "effect %s pitch %.3f" % [kind, p.pitch_scale])

# ------------------------------------------------------------------ 4. music
func check_music(sound: Node) -> void:
	sound.play_music("forest")
	var player: AudioStreamPlayer = sound.music[sound.music_index]
	check(player.stream != null and player.playing and sound.music_mode == "forest", "forest music plays")
	if player.stream == null: return
	var length: float = player.stream.get_length()
	check(sound.music_quota >= maxf(2.0*length, Sound.PLAY_MIN), "quota %.1f s under two loops / %d s" % [sound.music_quota, Sound.PLAY_MIN])
	var offsets := {}
	for i in 12:
		var at: float = sound.music_offset(player.stream)
		check(at >= 0.0 and at <= length*0.9+0.001, "offset %.2f outside the track" % at)
		offsets[snappedf(at, 0.01)] = true
	check(offsets.size() > 6, "offsets barely vary (%d distinct)" % offsets.size())
	# Quota used up: fade out, then a silent gap that keeps the mode.
	sound.music_clock = sound.music_quota
	sound._process(0.02)
	check(sound.music_resting, "no rest after the quota")
	sound.fade.custom_step(Sound.GAP_FADE_OUT+0.2)
	check(not player.playing and sound.music_mode == "forest", "track still playing in the gap (mode %s)" % sound.music_mode)
	check(sound.music_gap >= Sound.GAP_MIN and sound.music_gap <= Sound.GAP_MAX, "gap %.1f s outside %d..%d" % [sound.music_gap, Sound.GAP_MIN, Sound.GAP_MAX])
	sound.play_music("forest")
	check(sound.music_resting and not player.playing, "the same mode ended the gap")
	# The gap runs out: the same track fades back in.
	sound._process(sound.music_gap+0.05)
	check(player.playing and not sound.music_resting and sound.music_clock == 0.0, "track did not come back after the gap")
	sound.fade.custom_step(Sound.GAP_FADE_IN+0.2)
	check(absf(player.volume_db-Sound.MUSIC_DB) < 0.1, "fade-in ends at %.1f dB" % player.volume_db)
	# A mode change inside a gap starts the new track at once.
	sound.music_clock = sound.music_quota
	sound._process(0.02)
	sound.fade.custom_step(Sound.GAP_FADE_OUT+0.2)
	sound.play_music("frost")
	var next: AudioStreamPlayer = sound.music[sound.music_index]
	check(not sound.music_resting and next.playing and next.stream != null and sound.music_mode == "frost", "mode change during the gap")
	sound.fade.custom_step(Sound.CROSSFADE+0.2)
	check(absf(next.volume_db-Sound.MUSIC_DB) < 0.1, "crossfade ends at %.1f dB" % next.volume_db)
