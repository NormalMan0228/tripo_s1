extends Node
## Sounds for farming, fishing and foraging. Every kind is a take family
## res://assets/sfx/life/<kind>_<n>.wav (tools/sfx/gen_life.py) picked through sfx_bank.gd: a
## shuffle bag (no take repeats back to back) with a little pitch and volume jitter on every
## play, multiplied with the caller's pitch. A kind without takes (not imported yet) falls back
## to its old synthesized sound below. They play on the SFX bus (game_settings.gd), under
## Master, so the M mute silences them too.
const SfxBank = preload("res://scripts/sfx_bank.gd")
const RATE := 22050
const VOLUME := -13.0
## Baked takes sit this far under the synth they replace (gen_life.py HEADROOM_DB).
const BAKED_DB := 6.0
const PITCH_JITTER := 0.04
const DB_JITTER := 1.0
## Recorded gathering sounds (shared with the expedition harvest), used for forage pick-ups:
## take families whose _1 is the team recording.
const SAMPLES := {"dig_stone":"res://assets/sfx/combat/harvest_stone","dig_grass":"res://assets/sfx/combat/harvest_fiber",
	"chop_wood":"res://assets/sfx/combat/harvest_tree"}
## Takes that open with silence the file must keep (the team recording harvest_fiber_1 has ~98 ms
## of air before the tear): playback starts this many seconds in.
const LEAD_IN := {"harvest_fiber_1.wav":0.09}
## Kinds that only exist as take families: the old synth (kind, pitch, dB) standing in for them.
const STAND_IN := {"knock":["rock",0.55,-3.0],"bell":["catch",0.5,0.0],"thrash":["plop",0.8,0.0],"ripple":["plop",1.3,-8.0],
	"whiz":["cast",1.3,-6.0],"windup":["cast",0.8,-6.0],"strike":["cast",1.4,-2.0],"reel_back":["tick",0.8,-4.0],
	"fish_out":["plop",0.7,0.0],"rod_equip":["rock",0.8,-6.0],"pocket":["collect",1.5,-8.0],"fruit_detach":["rustle",1.4,-4.0],
	"bounce":["rock",0.5,-4.0],"fruit_water":["plop",0.6,0.0],"grab":["rustle",0.8,-6.0]}
## Pocket plips climb this pentatonic ladder (semitones) while items keep landing in the bag.
const LADDER := [0,2,4,7,9,12,14,16]
const LADDER_GAP := 0.9
var streams := {}
var voices: Array[AudioStreamPlayer]=[]
var next := 0
var ladder_step := 0
var ladder_at := -10.0

func _ready() -> void:
	for i in 8:
		var p := AudioStreamPlayer.new()
		p.volume_db=VOLUME
		p.bus=&"SFX"
		add_child(p)
		voices.append(p)

func play(kind: String, pitch := 1.0, volume := 0.0) -> void:
	_play(kind,pitch,volume,PITCH_JITTER)

## A sound at a world position heard from `listener` (the walker): -0.8 dB per metre past
## 3 m like Fx.sound, nothing once it is 30 dB down.
func play_at(kind: String, at: Vector3, listener: Vector3, pitch := 1.0, volume := 0.0) -> void:
	var fall := clampf(listener.distance_to(at)-3.0,0.0,40.0)*0.8
	if fall>=30.0: return
	_play(kind,pitch,volume-fall,PITCH_JITTER)

## An item lands in the bag: landings less than LADDER_GAP s apart climb a pentatonic ladder.
func pocket(volume := -4.0) -> void:
	var now := Time.get_ticks_msec()*0.001
	ladder_step=mini(ladder_step+1,LADDER.size()-1) if now-ladder_at<LADDER_GAP else 0
	ladder_at=now
	_play("pocket",pow(2.0,float(LADDER[ladder_step])/12.0),volume,0.008)

## The take for `kind` from its family (null when it has none): life/<kind>, or the recorded
## harvest family for the SAMPLES kinds.
func baked(kind: String) -> AudioStream:
	return SfxBank.pick(SAMPLES[kind] if SAMPLES.has(kind) else "life/"+kind)

func _play(kind: String, pitch: float, volume: float, spread: float) -> void:
	if voices.is_empty(): return
	var stream: AudioStream = baked(kind)
	if stream!=null:
		if not SAMPLES.has(kind): volume+=BAKED_DB
	else:
		var synth := kind
		if STAND_IN.has(kind):
			var stand: Array=STAND_IN[kind]
			synth=stand[0]
			pitch*=float(stand[1])
			volume+=float(stand[2])
		if not streams.has(synth): streams[synth]=make(synth)
		stream=streams[synth]
	var p := _voice()
	p.stream=stream
	p.pitch_scale=clampf(pitch*SfxBank.pitch(spread),0.25,4.0)
	p.volume_db=VOLUME+volume+SfxBank.db(DB_JITTER)
	p.play(float(LEAD_IN.get(stream.resource_path.get_file(),0.0)))

## The next idle player of the ring, or the next one in turn when all are busy.
func _voice() -> AudioStreamPlayer:
	for k in voices.size():
		var p := voices[(next+k)%voices.size()]
		if not p.playing:
			next=(next+k+1)%voices.size()
			return p
	var p := voices[next]
	next=(next+1)%voices.size()
	return p

func make(kind: String) -> AudioStream:
	if SAMPLES.has(kind) and ResourceLoader.exists(SAMPLES[kind]+"_1.wav"): return load(SAMPLES[kind]+"_1.wav")
	var length: float={"hoe":0.26,"seed":0.3,"water":0.75,"pop":0.22,"collect":0.42,"cast":0.4,"plop":0.22,"nibble":0.09,
		"bite":0.5,"tick":0.035,"catch":1.1,"escape":0.45,"rock":0.22,"rustle":0.32,"shell":0.2,"card":0.35}.get(kind,0.2)
	var n := int(length*RATE)
	var rng := RandomNumberGenerator.new()
	rng.seed=kind.hash()
	var low := 0.0
	var data := PackedByteArray()
	data.resize(n*2)
	for i in n:
		var t := float(i)/RATE
		var u := t/length
		var noise := rng.randf_range(-1,1)
		var v := 0.0
		match kind:
			"hoe":
				low+=(noise-low)*0.18
				v=low*2.2*exp(-u*9)+sin(TAU*(95-40*u)*t)*0.7*exp(-u*7)
			"seed":
				low+=(noise-low)*0.6
				var tick := fmod(t,0.08)
				v=(low-noise*0.5)*exp(-tick*70)*0.8*(1-u)
			"water":
				low+=(noise-low)*0.35
				v=(noise-low)*0.55*sin(PI*u)*(0.7+0.3*sin(t*55))
			"pop":
				v=sin(TAU*(320+900*u)*t)*0.8*exp(-u*5)+sin(TAU*1560*t)*0.2*exp(-u*8)
			"collect":
				var f: float=1320.0 if u<0.4 else 1760.0
				v=(sin(TAU*f*t)*0.5+sin(TAU*f*2*t)*0.12)*exp(-fmod(u,0.4)*7)
			"cast":
				low+=(noise-low)*(0.05+0.4*sin(PI*u))
				v=low*1.8*sin(PI*u)
			"plop":
				v=sin(TAU*(640-470*u)*t)*0.75*exp(-u*6)
				low+=(noise-low)*0.3
				v+=low*0.5*exp(-u*12)
			"nibble":
				v=sin(TAU*(980-300*u)*t)*0.5*exp(-u*5)
			"bite":
				low+=(noise-low)*0.4
				v=low*1.2*exp(-u*7)
				if u>0.12: v+=sin(TAU*(880.0 if u<0.3 else 1175.0)*t)*0.45*exp(-fmod(u-0.12,0.18)*12)
			"tick":
				v=noise*exp(-u*8)*0.6+sin(TAU*2400*t)*0.3*exp(-u*10)
			"catch":
				var notes := [523.25,659.25,783.99,1046.5]
				var k := mini(3,int(u*5))
				var local := fmod(u*5,1.0)
				v=(sin(TAU*notes[k]*t)*0.45+sin(TAU*notes[k]*2*t)*0.1)*exp(-local*(3.0 if k==3 else 5.0))
				if k==3: v*=1.0-clampf((u-0.6)/0.4,0,1)
			"escape":
				v=sin(TAU*(420-240*u)*t)*0.55*exp(-u*3)
			"rock":
				v=(sin(TAU*1250*t)*0.45+sin(TAU*1930*t)*0.25)*exp(-u*14)+noise*0.5*exp(-u*20)
			"rustle":
				low+=(noise-low)*0.55
				v=(noise-low)*0.7*sin(PI*u)*(0.6+0.4*sin(t*90))
			"shell":
				v=(sin(TAU*2100*t)*0.35+sin(TAU*3150*t)*0.2)*exp(-u*10)+noise*0.25*exp(-u*25)
			"card":
				v=(sin(TAU*784*t)*0.4+sin(TAU*1175*t)*0.3)*exp(-u*4)*minf(1,u*30)
		var env := minf(1.0,t*400)
		data.encode_s16(i*2,int(clampf(v*env,-1,1)*21000))
	var s := AudioStreamWAV.new()
	s.format=AudioStreamWAV.FORMAT_16_BITS
	s.mix_rate=RATE
	s.data=data
	return s
