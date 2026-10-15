extends CanvasLayer
## Screen fades and door sounds that survive scene changes (village <-> rooms).
## One instance lives under the tree root; scenes call Transition.of(tree).
## Every change of place uses the same short fade: fade_out() (OUT seconds), build
## the new place, fade_in() (IN seconds). Call loading(title) before fade_out() and
## the covered screen is a loading card instead of a black frame: the place's name and
## a slowly turning star seed among drifting motes, no other lines, over a dimmed painting
## of that kind of place when the caller names one (BACKDROPS). loading("", "start")
## is the game's first load, over the island cover art (assets/ui/loading_cover.jpg)
## with the painted logo. A plain fade_out() (stairs) stays a dark veil.
## While the veil covers the screen, builds pace themselves with LoadPace (load_pace.gd) so the
## card keeps turning, and the ring around the star seed shows how far they are.
const RpgUi = preload("res://scripts/rpg_ui.gd")
const LoadPace = preload("res://scripts/load_pace.gd")
const SfxBank = preload("res://scripts/sfx_bank.gd")
const Brand = preload("res://scripts/brand.gd")
const OUT := 0.35
const IN := 0.45
const COVER_ART := "res://assets/ui/loading_cover.jpg"
const SEED_ICON := "res://assets/starseed.svg"
## Painted backdrops for place cards (tools/build_brand_art.py), by the kind of place:
## the village and each of its islands (field_objects.ISLANDS ids), rooms, expedition regions.
const BACKDROPS := {
	"village": "res://assets/ui/loading/village.jpg",
	"square": "res://assets/ui/loading/village.jpg",
	"fields": "res://assets/ui/loading/fields.jpg",
	"garden": "res://assets/ui/loading/garden.jpg",
	"camp": "res://assets/ui/loading/camp.jpg",
	"lighthouse": "res://assets/ui/loading/lighthouse.jpg",
	"room": "res://assets/ui/loading/room.jpg",
	"tutorial": "res://assets/ui/loading/camp.jpg",
	"forest": "res://assets/ui/loading/forest.jpg",
	"quarry": "res://assets/ui/loading/quarry.jpg",
	"frost": "res://assets/ui/loading/frost.jpg",
}
## How dark a backdrop sits under the place name.
const BACKDROP_TINT := Color(0.52, 0.52, 0.56)
var veil: ColorRect
var door: AudioStreamPlayer
var tween: Tween
static var instance: CanvasLayer
## The loading card under the veil and its parts.
var card: Control
var art: TextureRect
## The place card's painting; read on a worker thread and faded in once it is there.
var backdrop: TextureRect
var backdrop_path := ""
## A soft dark pool behind the place name, so it reads over a bright painting.
var name_shade: TextureRect
## The last two backdrops shown stay loaded (village <-> room is the common walk).
static var backdrop_cache: Dictionary = {}
var glow: TextureRect
var floor_shade: TextureRect
var wordmark: VBoxContainer
var place: VBoxContainer
var heading: Label
var tip: Label
var spinner: Control
var seed: TextureRect
var halo: TextureRect
## The thin ring around the seed that fills with LoadPace's progress (hidden when none is reported).
var ring: Control
var ring_value := 0.0
var motes: CPUParticles2D
var spin: Tween
## "" (plain veil), "place" or "start".
var style := ""
## Counts fades, so a fade-in still waiting for its first frame yields to a newer fade.
var turn := 0

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
	build_card()
	door = AudioStreamPlayer.new()
	door.volume_db = DOOR_DB
	door.bus = &"SFX"
	add_child(door)

func _ready() -> void:
	get_tree().process_frame.connect(_frame_began)
	# The game's first card is dressed before this node joins the tree.
	set_process(card.visible)

func _exit_tree() -> void:
	if instance == self: instance = null
	if get_tree().process_frame.is_connected(_frame_began): get_tree().process_frame.disconnect(_frame_began)

## LoadPace measures each frame's work from here.
func _frame_began() -> void:
	LoadPace.frame_began()

## The ring eases toward the reported progress (never past it).
func _process(delta: float) -> void:
	if card.visible and not backdrop_path.is_empty() and backdrop.texture == null: _poll_backdrop()
	if not card.visible or LoadPace.shown < 0.0:
		ring.visible = false
		return
	ring.visible = true
	var target := LoadPace.shown
	if not is_equal_approx(ring_value, target):
		ring_value = move_toward(ring_value, target, maxf(target-ring_value, 0.1)*delta*5.0) if target > ring_value else target
		ring.queue_redraw()

func _draw_ring() -> void:
	var centre := ring.size*0.5
	var radius := ring.size.x*0.5
	ring.draw_arc(centre, radius, 0.0, TAU, 64, Color(1.0, 0.95, 0.82, 0.14), 2.0, true)
	if ring_value > 0.002:
		ring.draw_arc(centre, radius, -PI*0.5, -PI*0.5+TAU*ring_value, maxi(6, int(64*ring_value)), Color(RpgUi.GOLD, 0.9), 2.4, true)

## Fades to black. Await it before changing scenes or rebuilding the world.
func fade_out(seconds := OUT) -> void:
	await _fade(1.0, seconds)

func fade_in(seconds := IN) -> void:
	await _fade(0.0, seconds)

## Starts fully black, for scenes that open with a fade-in.
func cover() -> void:
	if tween and tween.is_valid(): tween.kill()
	turn += 1
	veil.modulate.a = 1.0
	LoadPace.cover(true)
	veil.mouse_filter = Control.MOUSE_FILTER_STOP

## Dresses the next covered screen as a loading card: `title` is the place being
## loaded ("" for none), kind "start" (cover art and logo), "run" (an expedition) or ""
## (village and rooms), and `place_art` a BACKDROPS key for the painting behind the name
## ("" for the plain dark card). Cleared again when the veil has faded in.
func loading(title := "", kind := "", place_art := "") -> void:
	style = "start" if kind == "start" else "place"
	var start := style == "start"
	if start and art.texture == null and ResourceLoader.exists(COVER_ART): art.texture = load(COVER_ART)
	art.visible = start
	floor_shade.visible = start
	show_backdrop("" if start else str(BACKDROPS.get(place_art, "")))
	glow.visible = not start and backdrop_path.is_empty()
	name_shade.visible = not start and not backdrop_path.is_empty()
	wordmark.visible = start
	heading.text = title
	place.visible = not start and not title.is_empty()
	# No tip line: the card shows the place and the turning star seed only.
	tip.text = ""
	tip.visible = false
	card.visible = true
	motes.emitting = true
	LoadPace.reset()
	ring_value = 0.0
	ring.visible = false
	set_process(true)
	if spin and spin.is_valid(): spin.kill()
	seed.rotation = 0.0
	halo.modulate.a = 0.6
	if not RpgUi.calm():
		# Owned by the card, so it ends whenever the card is cleared or freed.
		spin = card.create_tween().set_loops()
		spin.tween_property(seed, "rotation", TAU, 6.0).from(0.0)
		spin.parallel().tween_property(halo, "modulate:a", 1.0, 3.0).from(0.45).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)

## Puts the place's painting behind the card: at once when it is loaded already, otherwise
## read on a worker thread (the fade keeps its frames) and faded in when it arrives.
func show_backdrop(path: String) -> void:
	backdrop_path = path
	backdrop.texture = null
	backdrop.visible = not path.is_empty()
	if path.is_empty() or not ResourceLoader.exists(path):
		backdrop_path = ""
		backdrop.visible = false
		return
	if backdrop_cache.has(path):
		backdrop.texture = backdrop_cache[path]
		backdrop.modulate.a = 1.0
		return
	backdrop.modulate.a = 0.0
	if ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
		ResourceLoader.load_threaded_request(path)
	set_process(true)

func _poll_backdrop() -> void:
	var status := ResourceLoader.load_threaded_get_status(backdrop_path)
	if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS: return
	var texture: Texture2D = ResourceLoader.load_threaded_get(backdrop_path) if status == ResourceLoader.THREAD_LOAD_LOADED else null
	if texture == null:
		backdrop_path = ""
		backdrop.visible = false
		name_shade.visible = false
		glow.visible = style == "place"
		return
	for path in backdrop_cache.keys():
		if backdrop_cache.size() >= 2: backdrop_cache.erase(path)
	backdrop_cache[backdrop_path] = texture
	backdrop.texture = texture
	if RpgUi.calm() or veil.modulate.a < 0.05:
		backdrop.modulate.a = 1.0
	else:
		card.create_tween().tween_property(backdrop, "modulate:a", 1.0, 0.25).set_trans(Tween.TRANS_SINE)

func clear_card() -> void:
	style = ""
	card.visible = false
	backdrop.texture = null
	backdrop_path = ""
	motes.emitting = false
	if spin and spin.is_valid(): spin.kill()
	ring.visible = false
	set_process(false)
	LoadPace.reset()

func _fade(alpha: float, seconds: float) -> void:
	if tween and tween.is_valid(): tween.kill()
	turn += 1
	var mine := turn
	veil.mouse_filter = Control.MOUSE_FILTER_STOP
	var tree := Engine.get_main_loop() as SceneTree
	if alpha > 0.0 and is_equal_approx(veil.modulate.a, alpha):
		LoadPace.cover(true)
		return
	# The place is built once it fades in: work from now on runs unpaced, and the ring is full.
	LoadPace.cover(false)
	if alpha <= 0.0 and LoadPace.shown >= 0.0: LoadPace.shown = 1.0
	# A fade often follows a long frame (a room or the village just built, a reply
	# just handled); started now, its first step would be that whole frame and the
	# veil would jump. Two frames later the steps are even.
	for i in 2: await tree.process_frame
	if mine != turn: return
	var mine_tween := tree.create_tween()
	tween = mine_tween
	mine_tween.tween_property(veil, "modulate:a", alpha, seconds).set_trans(Tween.TRANS_SINE)
	# A later fade kills this tween and `finished` never comes: waiting on it hung the caller
	# (busy for good). Wait for the tween to end either way; a newer fade owns the veil then.
	while mine_tween.is_valid() and mine_tween.is_running(): await tree.process_frame
	if mine != turn: return
	if alpha >= 1.0: LoadPace.cover(true)
	if alpha <= 0.0:
		veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if is_zero_approx(veil.modulate.a): clear_card()

## The card's layout on the logical canvas; anchors keep it right at any size.
func build_card() -> void:
	card = Control.new()
	card.name = "LoadingCard"
	card.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.visible = false
	veil.add_child(card)
	art = TextureRect.new()
	art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	art.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(art)
	backdrop = TextureRect.new()
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	backdrop.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	backdrop.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	backdrop.self_modulate = BACKDROP_TINT
	backdrop.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	backdrop.visible = false
	card.add_child(backdrop)
	name_shade = gradient_rect(GradientTexture2D.FILL_RADIAL, Vector2(0.5, 0.5), Vector2(0.5, 0.0),
		[Color(0.02, 0.02, 0.03, 0.62), Color(0.02, 0.02, 0.03, 0.3), Color(0, 0, 0, 0)], [0.0, 0.5, 1.0])
	name_shade.set_anchors_preset(Control.PRESET_CENTER)
	name_shade.offset_left = -380
	name_shade.offset_right = 380
	name_shade.offset_top = -150
	name_shade.offset_bottom = 110
	name_shade.visible = false
	card.add_child(name_shade)
	# Rooms and areas: a warm glow in the middle of the dark, like a lantern behind a door.
	glow = gradient_rect(GradientTexture2D.FILL_RADIAL, Vector2(0.5, 0.46), Vector2(1.05, 0.46),
		[Color(0.42, 0.3, 0.16, 0.42), Color(0.12, 0.1, 0.08, 0.12), Color(0, 0, 0, 0)], [0.0, 0.45, 1.0])
	card.add_child(glow)
	# The cover art darkens toward the bottom so the words read over it.
	floor_shade = gradient_rect(GradientTexture2D.FILL_LINEAR, Vector2(0, 0), Vector2(0, 1),
		[Color(0.02, 0.03, 0.04, 0.0), Color(0.02, 0.03, 0.04, 0.12), Color(0.02, 0.03, 0.04, 0.86)], [0.0, 0.5, 1.0])
	card.add_child(floor_shade)
	var vignette := gradient_rect(GradientTexture2D.FILL_RADIAL, Vector2(0.5, 0.5), Vector2(1.1, 1.1),
		[Color(0, 0, 0, 0), Color(0.01, 0.02, 0.03, 0.5)], [0.6, 1.0])
	card.add_child(vignette)
	motes = CPUParticles2D.new()
	var dot := GradientTexture2D.new()
	dot.width = 32
	dot.height = 32
	dot.fill = GradientTexture2D.FILL_RADIAL
	dot.fill_from = Vector2(0.5, 0.5)
	dot.fill_to = Vector2(1.0, 0.5)
	dot.gradient = Gradient.new()
	dot.gradient.colors = PackedColorArray([Color(1, 0.94, 0.75, 0.9), Color(1, 0.85, 0.5, 0)])
	motes.texture = dot
	motes.amount = 26
	motes.lifetime = 8.0
	motes.preprocess = 8.0
	motes.emitting = false
	motes.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	motes.direction = Vector2(0.12, -1)
	motes.spread = 16
	motes.gravity = Vector2.ZERO
	motes.initial_velocity_min = 18
	motes.initial_velocity_max = 40
	motes.scale_amount_min = 0.16
	motes.scale_amount_max = 0.5
	var fade := Gradient.new()
	fade.colors = PackedColorArray([Color(1, 1, 1, 0), Color(1, 1, 1, 0.8), Color(1, 1, 1, 0)])
	fade.offsets = PackedFloat32Array([0, 0.3, 1])
	motes.color_ramp = fade
	card.add_child(motes)
	card.resized.connect(func():
		motes.position = Vector2(card.size.x*0.5, card.size.y+30)
		motes.emission_rect_extents = Vector2(card.size.x*0.55, 30))
	# The game's painted logo, bottom left, as on the title screen.
	wordmark = VBoxContainer.new()
	wordmark.alignment = BoxContainer.ALIGNMENT_END
	wordmark.anchor_top = 1.0
	wordmark.anchor_bottom = 1.0
	wordmark.offset_left = 48
	wordmark.offset_top = -220
	wordmark.offset_right = 420
	wordmark.offset_bottom = -40
	wordmark.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(wordmark)
	wordmark.add_child(Brand.logo(340))
	# A place being entered: its name in the middle with a gold rule under it.
	place = VBoxContainer.new()
	place.alignment = BoxContainer.ALIGNMENT_CENTER
	place.add_theme_constant_override("separation", 6)
	place.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	place.offset_left = -320
	place.offset_right = 320
	place.offset_top = -70
	place.offset_bottom = 30
	place.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(place)
	heading = RpgUi.label(place, "", 40, RpgUi.GOLD)
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_constant_override("outline_size", 7)
	RpgUi.divider(place, RpgUi.GOLD, 300).size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	# The old tip line along the bottom, kept hidden: the card shows no extra sentences.
	tip = RpgUi.label(card, "", 17, Color(1.0, 0.96, 0.86, 0.9))
	tip.anchor_top = 1.0
	tip.anchor_bottom = 1.0
	tip.anchor_right = 1.0
	tip.offset_left = 66
	tip.offset_right = -150
	tip.offset_top = -62
	tip.offset_bottom = -34
	tip.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	# The star seed turning slowly in a breathing halo, bottom right.
	spinner = Control.new()
	spinner.anchor_left = 1.0
	spinner.anchor_right = 1.0
	spinner.anchor_top = 1.0
	spinner.anchor_bottom = 1.0
	spinner.offset_left = -118
	spinner.offset_right = -54
	spinner.offset_top = -100
	spinner.offset_bottom = -36
	spinner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(spinner)
	halo = gradient_rect(GradientTexture2D.FILL_RADIAL, Vector2(0.5, 0.5), Vector2(1.0, 0.5),
		[Color(1.0, 0.86, 0.52, 0.55), Color(1.0, 0.78, 0.4, 0.0)], [0.0, 1.0])
	halo.offset_left = -22
	halo.offset_top = -22
	halo.offset_right = 22
	halo.offset_bottom = 22
	spinner.add_child(halo)
	seed = RpgUi.icon(SEED_ICON, 64)
	seed.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	seed.pivot_offset = Vector2(32, 32)
	spinner.add_child(seed)
	ring = Control.new()
	ring.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ring.offset_left = -6
	ring.offset_top = -6
	ring.offset_right = 6
	ring.offset_bottom = 6
	ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ring.visible = false
	ring.draw.connect(_draw_ring)
	spinner.add_child(ring)

static func gradient_rect(fill: int, from: Vector2, to: Vector2, colors: Array, offsets: Array) -> TextureRect:
	var texture := GradientTexture2D.new()
	texture.fill = fill
	texture.fill_from = from
	texture.fill_to = to
	texture.gradient = Gradient.new()
	texture.gradient.colors = PackedColorArray(colors)
	texture.gradient.offsets = PackedFloat32Array(offsets)
	var rect := TextureRect.new()
	rect.texture = texture
	rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return rect

## Each building's door has its own sounds (tools/make_village_sfx.py, more takes from
## tools/sfx/gen_doors.py): bells over the cafe, bakery and shop doors, the seed shop's
## bamboo chimes, the greenhouse's glass slider, the observatory hatch, the windmill's
## wind, the lighthouse's iron door and echo... Every room and kind has several takes
## (DOOR_SOUNDS plus <room>_<kind>_<n>.wav), each the same door worked another way.
## Unknown rooms use the generic latch/thud.
const DOOR_SOUNDS := "res://assets/sfx/doors/%s_%s.wav"
const DOOR_DB := -9.0
## kind -> the generic synthesized door, shared by every Transition instance (room takes
## are cached by sfx_bank.gd).
static var door_cache: Dictionary = {}

## kind is "open" (entering) or "close" (stepping back outside); room is the
## interior id ("home", "workshop", "01_cafe", ... "17_lighthouse").
func play_door(kind: String, room := "") -> void:
	# The node joins the root one idle step after a scene first asks for it.
	if not door.is_inside_tree(): await ready
	door.stream = door_stream(kind, room)
	door.pitch_scale = SfxBank.pitch(0.03)
	door.volume_db = DOOR_DB+SfxBank.db(1.0)
	door.play()

## The stream play_door uses: the next of the room's takes from sfx_bank.gd's shuffle bag
## (a door never plays the same take twice running; each take is loaded once and cached),
## else the generic synthesized one.
static func door_stream(kind: String, room := "") -> AudioStream:
	if kind != "open": kind = "close"
	if not room.is_empty():
		var take := SfxBank.pick(DOOR_SOUNDS % [room, kind])
		if take != null: return take
	if not door_cache.has(kind): door_cache[kind] = door_sound(kind)
	return door_cache[kind]

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
