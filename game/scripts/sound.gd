extends Node
## Music and the small game effects. Music plays on the Music bus, clicks and error beeps on
## UI, everything else on SFX (GameSettings carries the volumes).
## Effects: every kind is a take family res://assets/sfx/core/<kind>_<n>.wav
## (tools/sfx/gen_life.py) picked through sfx_bank.gd (shuffle bag, small pitch/volume jitter);
## a kind without takes plays its old synthesized blip (make_effect) instead.
## Music: a mode starts its team track at a random point and crossfades over CROSSFADE s. Once a
## track has played for at least two loops and PLAY_MIN s it fades out and the ambience carries
## the scene for GAP_MIN..GAP_MAX s of silence, then the track fades back in at a random point.
## A mode change ends a silence gap at once.
const GameSettings = preload("res://scripts/game_settings.gd")
const SfxBank = preload("res://scripts/sfx_bank.gd")
const UI_EFFECTS := ["click","error"]
const EFFECT_DB := -16.0
## Baked takes sit this far under the synth they replace (gen_life.py HEADROOM_DB).
const BAKED_DB := 6.0
## Kinds that only exist as take families: the old synth that stands in for them.
const STAND_IN := {"sell":"reward","buy":"gather","errand":"reward","newday":"reward","win":"reward","lose":"error","bandage":"eat"}
const MUSIC_DB := -14.0
const SILENT_DB := -60.0
const CROSSFADE := 1.2
const PLAY_MIN := 75.0
const GAP_MIN := 20.0
const GAP_MAX := 60.0
const GAP_FADE_OUT := 5.0
const GAP_FADE_IN := 4.0

var muted := false
var effects: Dictionary = {}
var voices: Array[AudioStreamPlayer]=[]
var music: Array[AudioStreamPlayer]=[]
var voice_index := 0
var music_index := 0
var music_mode := ""
var fade: Tween
## Seconds the current track has played since it (re)started, and the play time before its gap.
var music_clock := 0.0
var music_quota := 0.0
## In a silence gap: fading out (music_gap < 0) or silent with music_gap seconds left.
var music_resting := false
var music_gap := 0.0

func _ready() -> void:
	muted=GameSettings.muted()
	for kind in ["click","gather","craft","eat","fire","hit","hurt","error","reward"]:
		effects[kind]=make_effect(kind)
	for i in 5:
		var player := AudioStreamPlayer.new()
		player.volume_db=EFFECT_DB
		player.bus=GameSettings.BUS_SFX
		add_child(player)
		voices.append(player)
	for i in 2:
		var player := AudioStreamPlayer.new()
		player.volume_db=SILENT_DB
		player.bus=GameSettings.BUS_MUSIC
		add_child(player)
		music.append(player)
	apply_mute()

func apply_mute() -> void:
	# The Master bus belongs to this game process; the system volume is unchanged.
	GameSettings.apply_audio()
	muted=GameSettings.muted()

func _exit_tree() -> void:
	if fade and fade.is_valid(): fade.kill()
	# Release looping playback before the audio server shuts down.
	for player in music+voices:
		if is_instance_valid(player):
			player.stop()
			player.stream=null
	effects.clear()

## M key / menu: flips the saved "mute all" setting.
func toggle() -> void:
	GameSettings.set_value("mute_all",not bool(GameSettings.get_value("mute_all")))
	apply_mute()

func effect(kind: String) -> void:
	# Interface clicks share RpgUi's soft click (deduped, so a button hook and an
	# older effect("click") call on the same press play it once).
	if kind=="click":
		preload("res://scripts/rpg_ui.gd").sfx("click")
		return
	var stream: AudioStream = SfxBank.pick("core/"+kind)
	var gain := BAKED_DB
	if stream==null:
		gain=0.0
		var synth: String=STAND_IN.get(kind,kind)
		if not effects.has(synth): return
		stream=effects[synth]
	var player := next_voice()
	player.stream=stream
	player.pitch_scale=SfxBank.pitch(0.04)
	player.volume_db=EFFECT_DB+gain+SfxBank.db(1.0)
	player.bus=GameSettings.BUS_UI if kind in UI_EFFECTS else GameSettings.BUS_SFX
	player.play()

## The next idle effect player (or the next in turn when all are busy); voice_index ends one
## past the player it returns.
func next_voice() -> AudioStreamPlayer:
	for k in voices.size():
		var i := (voice_index+k)%voices.size()
		if not voices[i].playing:
			voice_index=(i+1)%voices.size()
			return voices[i]
	var player := voices[voice_index]
	voice_index=(voice_index+1)%voices.size()
	return player

func play_music(mode: String) -> void:
	if mode==music_mode: return
	music_mode=mode
	var stream: AudioStream
	for extension in ["ogg","mp3","wav"]:
		var path: String = "res://assets/audio/"+mode+"."+extension
		if ResourceLoader.exists(path):
			stream=load(path).duplicate()
			break
	if not stream: return
	if stream is AudioStreamOggVorbis or stream is AudioStreamMP3: stream.loop=true
	elif stream is AudioStreamWAV:
		stream.loop_mode=AudioStreamWAV.LOOP_FORWARD
		stream.loop_end=stream.data.size()/(4 if stream.stereo else 2)
	if fade and fade.is_valid(): fade.kill()
	music_resting=false
	music_gap=0.0
	var previous := music[music_index]
	music_index=(music_index+1)%music.size()
	var next := music[music_index]
	next.stop()
	next.stream=stream
	next.volume_db=SILENT_DB
	next.play(music_offset(stream))
	start_quota(stream)
	fade=create_tween().set_parallel(true)
	fade.tween_property(previous,"volume_db",SILENT_DB,CROSSFADE)
	fade.tween_property(next,"volume_db",MUSIC_DB,CROSSFADE)
	fade.chain().tween_callback(previous.stop)

## Somewhere in the first 90 % of the track, so a mode does not always open on the same bar.
func music_offset(stream: AudioStream) -> float:
	var length := stream.get_length()
	return randf_range(0.0,length*0.9) if length>1.0 else 0.0

func start_quota(stream: AudioStream) -> void:
	music_clock=0.0
	music_quota=maxf(2.0*stream.get_length(),PLAY_MIN)+randf_range(0.0,15.0)

func _process(delta: float) -> void:
	if music_mode.is_empty() or music.is_empty(): return
	if music_resting:
		if music_gap>0.0:
			music_gap-=delta
			if music_gap<=0.0: resume_music()
		return
	if not music[music_index].playing: return
	music_clock+=delta
	if music_clock>=music_quota: rest_music()

## Fades the current track out; the silence gap starts once it is quiet.
func rest_music() -> void:
	music_resting=true
	music_gap=-1.0
	if fade and fade.is_valid(): fade.kill()
	var current := music[music_index]
	fade=create_tween()
	fade.tween_property(current,"volume_db",SILENT_DB,GAP_FADE_OUT)
	fade.tween_callback(func():
		current.stop()
		music_gap=randf_range(GAP_MIN,GAP_MAX))

## After a silence gap: the same mode's track fades back in at a random point.
func resume_music() -> void:
	music_resting=false
	music_gap=0.0
	var current := music[music_index]
	if current.stream==null: return
	if fade and fade.is_valid(): fade.kill()
	current.volume_db=SILENT_DB
	current.play(music_offset(current.stream))
	start_quota(current.stream)
	fade=create_tween()
	fade.tween_property(current,"volume_db",MUSIC_DB,GAP_FADE_IN)

## A recorded one-shot (portal, door) on the SFX bus, over the music.
func stinger(path: String, volume_db := -10.0) -> void:
	if not ResourceLoader.exists(path): return
	var player := next_voice()
	player.stream=load(path)
	player.bus=GameSettings.BUS_SFX
	player.pitch_scale=1.0
	player.volume_db=volume_db
	player.play()

func make_effect(kind: String) -> AudioStreamWAV:
	var length := 0.15
	var frequency := 550.0
	match kind:
		"click": length=0.045; frequency=620
		"gather": length=0.17; frequency=410
		"craft": length=0.38; frequency=660
		"eat": length=0.13; frequency=270
		"fire": length=0.24; frequency=170
		"hit": length=0.12; frequency=110
		"hurt": length=0.18; frequency=140
		"error": length=0.13; frequency=185
		"reward": length=0.58; frequency=780
	var sample_rate := 22050
	var frames := int(length*sample_rate)
	var data := PackedByteArray()
	data.resize(frames*2)
	var rng := RandomNumberGenerator.new()
	rng.seed=kind.hash()
	for i in frames:
		var t := float(i)/sample_rate
		var envelope := minf(t*100,1.0)*pow(1.0-float(i)/frames,2.0)
		var wave := sin(TAU*frequency*t)*0.55+sin(TAU*frequency*2*t)*0.12
		if kind in ["craft","reward"]:
			var note: float = [1.0,1.25,1.5][mini(2,int(t/length*3))]
			wave=sin(TAU*frequency*note*t)*0.55
		elif kind in ["hit","hurt","fire","eat"]:
			wave=wave*0.55+rng.randf_range(-0.3,0.3)
		data.encode_s16(i*2,int(clampf(wave*envelope,-1,1)*22000))
	var stream := AudioStreamWAV.new()
	stream.format=AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate=sample_rate
	stream.data=data
	return stream
