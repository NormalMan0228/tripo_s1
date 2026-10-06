extends Node
## Music and the small synthesized effects. Music plays on the Music bus, clicks and
## error beeps on UI, everything else on SFX (GameSettings carries the volumes).
const GameSettings = preload("res://scripts/game_settings.gd")
const UI_EFFECTS := ["click","error"]

var muted := false
var effects: Dictionary = {}
var voices: Array[AudioStreamPlayer]=[]
var music: Array[AudioStreamPlayer]=[]
var voice_index := 0
var music_index := 0
var music_mode := ""
var fade: Tween

func _ready() -> void:
	muted=GameSettings.muted()
	for kind in ["click","gather","craft","eat","fire","hit","hurt","error","reward"]:
		effects[kind]=make_effect(kind)
	for i in 5:
		var player := AudioStreamPlayer.new()
		player.volume_db=-16
		player.bus=GameSettings.BUS_SFX
		add_child(player)
		voices.append(player)
	for i in 2:
		var player := AudioStreamPlayer.new()
		player.volume_db=-60
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
	if not effects.has(kind): return
	var player := voices[voice_index]
	voice_index=(voice_index+1)%voices.size()
	player.stream=effects[kind]
	player.bus=GameSettings.BUS_UI if kind in UI_EFFECTS else GameSettings.BUS_SFX
	player.play()

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
	var previous := music[music_index]
	music_index=(music_index+1)%music.size()
	var next := music[music_index]
	next.stop()
	next.stream=stream
	next.volume_db=-60
	next.play()
	fade=create_tween().set_parallel(true)
	fade.tween_property(previous,"volume_db",-60.0,1.2)
	fade.tween_property(next,"volume_db",-14.0,1.2)
	fade.chain().tween_callback(previous.stop)

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
