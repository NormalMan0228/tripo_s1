extends Node
## Small synthesized sounds for farming, fishing and foraging. They play on the
## Master bus, so the game's M mute (sound.gd) silences them too.
const RATE := 22050
var streams := {}
var voices: Array[AudioStreamPlayer]=[]
var next := 0

func _ready() -> void:
	for i in 6:
		var p := AudioStreamPlayer.new()
		p.volume_db=-13
		add_child(p)
		voices.append(p)

func play(kind: String, pitch := 1.0, volume := 0.0) -> void:
	if not streams.has(kind): streams[kind]=make(kind)
	var p := voices[next]
	next=(next+1)%voices.size()
	p.stream=streams[kind]
	p.pitch_scale=pitch
	p.volume_db=-13+volume
	p.play()

func make(kind: String) -> AudioStreamWAV:
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
