extends CanvasLayer
## Screen fades and door sounds that survive scene changes (village <-> rooms).
## One instance lives under the tree root; scenes call Transition.of(tree).
var veil: ColorRect
var door: AudioStreamPlayer
var tween: Tween
static var instance: CanvasLayer

static func of(tree: SceneTree) -> CanvasLayer:
	if is_instance_valid(instance): return instance
	instance = load("res://scripts/transition.gd").new()
	instance.layer = 100
	instance.name = "Transition"
	# The root may be busy adding the new scene; join it on the next idle step.
	tree.root.add_child.call_deferred(instance)
	return instance

func _init() -> void:
	veil = ColorRect.new()
	veil.color = Color(0.02,0.03,0.04,1.0)
	veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	veil.modulate.a = 0.0
	add_child(veil)
	door = AudioStreamPlayer.new()
	door.volume_db = -9
	add_child(door)

func _exit_tree() -> void:
	if instance == self: instance = null

## Fades to black. Await it before changing scenes or rebuilding the world.
func fade_out(seconds := 0.45) -> void:
	await _fade(1.0, seconds)

func fade_in(seconds := 0.6) -> void:
	await _fade(0.0, seconds)

## Starts fully black, for scenes that open with a fade-in.
func cover() -> void:
	if tween and tween.is_valid(): tween.kill()
	veil.modulate.a = 1.0
	veil.mouse_filter = Control.MOUSE_FILTER_STOP

func _fade(alpha: float, seconds: float) -> void:
	if tween and tween.is_valid(): tween.kill()
	veil.mouse_filter = Control.MOUSE_FILTER_STOP
	var tree := Engine.get_main_loop() as SceneTree
	tween = tree.create_tween()
	tween.tween_property(veil, "modulate:a", alpha, seconds).set_trans(Tween.TRANS_SINE)
	await tween.finished
	if alpha <= 0.0: veil.mouse_filter = Control.MOUSE_FILTER_IGNORE

## Each building's door has its own pair of sounds (tools/make_village_sfx.py):
## bells over the cafe, bakery and shop doors, the seed shop's bamboo chimes, the
## greenhouse's glass slider, the observatory hatch, the windmill's wind, the
## lighthouse's iron door and echo... Unknown rooms use the generic latch/thud.
const DOOR_SOUNDS := "res://assets/sfx/doors/%s_%s.wav"
## room+kind -> AudioStream, shared by every Transition instance.
static var door_cache: Dictionary = {}

## kind is "open" (entering) or "close" (stepping back outside); room is the
## interior id ("home", "workshop", "01_cafe", ... "17_lighthouse").
func play_door(kind: String, room := "") -> void:
	# The node joins the root one idle step after a scene first asks for it.
	if not door.is_inside_tree(): await ready
	door.stream = door_stream(kind, room)
	door.play()

## The stream play_door uses: the room's own sound, else the generic synthesized one.
static func door_stream(kind: String, room := "") -> AudioStream:
	if kind != "open": kind = "close"
	var key := room+"/"+kind
	if not door_cache.has(key):
		var path := DOOR_SOUNDS % [room, kind]
		var stream: AudioStream = load(path) if not room.is_empty() and ResourceLoader.exists(path) else null
		door_cache[key] = stream if stream != null else door_sound(kind)
	return door_cache[key]

static func door_sound(kind: String) -> AudioStreamWAV:
	var rate := 22050
	var length := 0.62 if kind == "open" else 0.34
	var frames := int(length*rate)
	var data := PackedByteArray()
	data.resize(frames*2)
	var rng := RandomNumberGenerator.new()
	rng.seed = kind.hash()
	var phase := 0.0
	for i in frames:
		var t := float(i)/rate
		var wave := 0.0
		if kind == "open":
			# Latch click, then a rising hinge creak with a little grain.
			var click := exp(-t*90.0)*rng.randf_range(-1,1)*0.9
			var creak_t := maxf(t-0.05,0.0)
			var frequency := 170.0+150.0*creak_t+sin(creak_t*38.0)*22.0
			phase += TAU*frequency/rate
			var creak := (sin(phase)*0.5+sin(phase*2.0)*0.22)*minf(creak_t*12.0,1.0)*pow(1.0-t/length,1.6)*0.6
			wave = click+creak+rng.randf_range(-0.05,0.05)*(1.0-t/length)
		else:
			var thud := sin(TAU*(88.0-40.0*t)*t)*exp(-t*14.0)
			wave = thud*0.95+rng.randf_range(-0.25,0.25)*exp(-t*55.0)
		data.encode_s16(i*2, int(clampf(wave,-1,1)*21000))
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = rate
	stream.data = data
	return stream
