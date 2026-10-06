extends Node3D
## Things to use around the five islands, beyond the props town.gd already reacts
## to: signposts that travel between islands, the home mailbox, the village notice
## board, a wishing well, a drinking fountain, a swing, a rocking chair, a hammock,
## a weather vane, a bird feeder, wind chimes, a gong by the stage, a photo spot,
## a lost-and-found box and two telescopes. Using one shows rather than tells (fx.gd
## puffs, bubbles and sounds); words stay where they inform: signpost destinations,
## the mailbox, the notice board, the lost-and-found list and telescope landmarks.
## A village module (see main.gd VILLAGE_MODULES): built under the village world
## each time the village is built. Every object is placed at runtime from SPECS:
## the spot is nudged until it is off the roads, clear of doors, villagers,
## activity spots, water, buildings, bridges and other props, then turned to face
## the nearest road so it is used from the path side.
const A := preload("res://scripts/art.gd")
const Town := preload("res://scripts/town.gd")
const Roads := preload("res://scripts/roads.gd")
const Daylight := preload("res://scripts/daylight.gd")
const Profile := preload("res://scripts/controller_profile.gd")
const Transition := preload("res://scripts/transition.gd")
const Fx := preload("res://scripts/fx.gd")
const SFX := "res://assets/sfx/field/%s.wav"
## Solid parts sit on the props layer (8) like the map's benches and trees.
const PROP_LAYER := 8
const BLOCK_MASK := 2|8|16
const ISLANDS := {"square":"물결빛 광장","fields":"풍차 들판","garden":"정원 언덕","camp":"캠프 초원","lighthouse":"등대섬"}
const SPECS := [
	{"id":"sign_square","kind":"signpost","at":Vector2(-29.0,32.0),"island":"square"},
	{"id":"sign_fields","kind":"signpost","at":Vector2(-31.5,-27.5),"alts":[Vector2(-25.0,-27.5)],"island":"fields"},
	{"id":"sign_garden","kind":"signpost","at":Vector2(29.0,-18.5),"island":"garden"},
	{"id":"sign_camp","kind":"signpost","at":Vector2(40.5,31.5),"island":"camp"},
	{"id":"sign_lighthouse","kind":"signpost","at":Vector2(5.5,74.5),"island":"lighthouse"},
	{"id":"mailbox","kind":"mailbox","at":Vector2(-51.3,22.6)},
	{"id":"notice","kind":"notice","at":Vector2(-37.0,31.5)},
	{"id":"well","kind":"well","at":Vector2(-24.5,40.5)},
	{"id":"fountain","kind":"fountain","at":Vector2(-22.5,28.5),"alts":[Vector2(-23.5,32.5)]},
	{"id":"swing","kind":"swing","at":Vector2(-38.5,56.5)},
	{"id":"vane","kind":"vane","at":Vector2(-24.0,-38.0)},
	{"id":"feeder","kind":"feeder","at":Vector2(-46.0,-40.0)},
	{"id":"rocker","kind":"rocker","at":Vector2(-56.5,-36.5)},
	{"id":"hammock","kind":"hammock","at":Vector2(41.0,-34.0)},
	{"id":"chimes","kind":"chimes","at":Vector2(64.0,-33.0)},
	{"id":"gong","kind":"gong","at":Vector2(43.5,23.0)},
	{"id":"photo","kind":"photo","at":Vector2(27.5,27.0)},
	{"id":"lost","kind":"lost","at":Vector2(60.5,36.0)},
	{"id":"scope_camp","kind":"telescope","at":Vector2(19.5,36.5),"targets":[["등대섬",Vector2(7,79)],["물결빛 광장",Vector2(-33,31)]]},
	{"id":"scope_light","kind":"telescope","at":Vector2(12.5,76.5),"alts":[Vector2(4.0,84.5),Vector2(11.0,83.5),Vector2(8.0,72.5)],"targets":[["캠프 초원 돌문",Vector2(54,38)],["유리 온실",Vector2(49,-20)]]},
]
## Footprint radius (m): placement clearance and how far the E prompt reaches.
const RADIUS := {"signpost":0.4,"mailbox":0.3,"notice":0.85,"well":0.95,"fountain":0.42,"swing":1.25,"vane":0.4,
	"feeder":0.4,"rocker":0.55,"hammock":1.55,"chimes":0.45,"gong":0.8,"photo":0.95,"lost":0.55,"telescope":0.45}
const PROMPTS := {"signpost":"이정표 보기 · 다른 섬으로 가기","mailbox":"우편함 열어 보기","notice":"마을 게시판 읽기",
	"well":"소원 우물에 동전 던지기","fountain":"식수대에서 물 마시기","swing":"그네 타기","vane":"풍향계 살펴보기",
	"feeder":"새 모이통 채우기","rocker":"흔들의자에 앉기","hammock":"해먹에 누워 쉬기","chimes":"풍경 흔들기",
	"gong":"징 치기","photo":"포토 스팟에서 사진 찍기","lost":"분실물 상자 열어 보기","telescope":"망원경 들여다보기"}
## Boards and signs turn toward the camera (south) so their faces stay readable.
const FACE_CAMERA := ["signpost","mailbox","notice","photo","lost","gong","hammock"]
## Ponds the walker cannot stand in (centre, radii); the map draws them as water.
const PONDS := [[Vector2(-48,44),Vector2(12.5,9.5)],[Vector2(51,-43),Vector2(9.5,7.5)]]
const SEAT := {"swing":0.52,"rocker":0.48,"hammock":0.6}
const LOST_ITEMS := ["하늘색 손수건 · 등대섬 부두에서 주웠어요","작은 놋쇠 열쇠 · 풍차 방앗간 앞 풀숲","밀짚모자 · 캠프 초원 모닥불 옆",
	"반쯤 읽은 그림책 · 정원 언덕 정자","빨간 털장갑 한 짝 · 물결빛 광장 분수 근처","나무 피리 · 음악 무대 뒤편",
	"조개껍데기 목걸이 · 남쪽 해변","낚시찌 세 개 · 마을 연못 잔교","별 모양 머리핀 · 별빛 천문대 계단","손그림 지도 · 씨앗 가게 앞 의자"]
const TIPS := ["Tab을 누르면 섬 지도가 열려요. 금빛 표식을 따라가 보세요.","B로 창고를, I로 보관함을 열 수 있어요.",
	"이정표에서 다른 섬으로 바로 이동할 수 있어요.","포토 스팟에서 찍은 사진은 사진첩 폴더에 저장돼요.",
	"밤이 되면 가로등과 이정표 등불이 켜져요. 산책하기 좋은 시간이에요.","O를 누르면 옷장에서 차림을 바꿀 수 있어요.",
	"망원경으로 먼 섬의 풍경을 살펴볼 수 있어요.","C를 누르면 새 물건 제작을 맡길 수 있어요."]

static var sounds: Dictionary = {}
var app: Node
var space: PhysicsDirectSpaceState3D
## One entry per placed object: {spec, kind, id, root, at (Vector2), ground, front (Vector2), radius, ...}.
var objects: Array = []
## Specs that found no valid spot (reported by the harness).
var skipped: Array = []
var lamps: Array = []
var voices: Array[AudioStreamPlayer] = []
var voice_index := 0
var clock := 0.0
var light_timer := 0.0
var seat: Dictionary = {}
var view: Dictionary = {}
var flash_layer: CanvasLayer
var last_photo: Image
var rng := RandomNumberGenerator.new()

func setup(main: Node) -> void:
	app = main
	rng.randomize()
	for i in 4:
		var voice := AudioStreamPlayer.new()
		voice.bus = &"SFX"
		add_child(voice)
		voices.append(voice)
	build()

## Places and builds every object. Safe to call once per village build.
func build() -> void:
	space = get_world_3d().direct_space_state
	for spec in SPECS:
		var spot := find_spot(spec)
		if spot.is_empty():
			skipped.append(spec.id)
			continue
		var entry := {"spec":spec,"id":spec.id,"kind":spec.kind,"at":spot.at,"ground":spot.ground,"front":spot.front,
			"radius":float(RADIUS[spec.kind])}
		var root := Node3D.new()
		root.name = "Field_"+String(spec.id)
		add_child(root)
		root.position = Vector3(spot.at.x, spot.ground, spot.at.y)
		root.rotation.y = atan2(spot.front.x, spot.front.y)
		entry.root = root
		call("make_"+String(spec.kind), entry)
		merge_static(entry)
		entry.stand = stand_point(entry)
		objects.append(entry)
	apply_night(night_level())

# ------------------------------------------------------------------ placement
func find_spot(spec: Dictionary) -> Dictionary:
	var r: float = RADIUS[spec.kind]
	# "alts" are fallback origins for crowded spots, tried in order.
	for origin: Vector2 in [spec.at]+spec.get("alts", []):
		for ring: float in [0.0,0.5,1.0,1.5,2.0,2.5,3.0,3.5]:
			var steps := 1 if ring==0.0 else 10
			for k in steps:
				var angle := TAU*float(k)/steps+ring*0.7
				var p := origin+Vector2(cos(angle),sin(angle))*ring
				var ground := spot_ground(p, r)
				if is_nan(ground) or not blocker(p, r, ground).is_empty(): continue
				return {"at":p,"ground":ground,"front":facing(p, String(spec.kind))}
	return {}

## Ground height under a footprint, or NAN on water, cliffs, rocks or slopes.
func spot_ground(p: Vector2, r: float) -> float:
	var heights: Array[float] = []
	for k in 9:
		var q := p if k==0 else p+Vector2(cos(k*TAU/8),sin(k*TAU/8))*r
		var hit := ray_down(q, 1)
		if hit.is_empty(): return NAN
		heights.append(hit.position.y)
	var low: float = heights.min()
	if low < 1.45 or float(heights.max())-low > 0.55: return NAN
	return heights[0]

## Why a footprint cannot go at p ("" when it can).
func blocker(p: Vector2, r: float, ground: float) -> String:
	if is_nan(ground): return "water, rock or slope"
	if Roads.on_road(p) or road_gap(p) < r*0.6+0.25 or road_centre(p).distance_to(p) < 1.2: return "road"
	for door in Town.DOORS:
		if p.distance_to(door.at) < 2.5+r: return "door "+String(door.id)
	for place in Town.PLACES:
		if p.distance_to(place.at) < 2.6+r: return "place "+String(place.id)
	for role in Town.VILLAGERS:
		if p.distance_to(Town.VILLAGERS[role]) < 2.4+r: return "villager "+String(role)
	for plot in Town.PLOTS:
		if p.distance_to(plot) < 2.0+r: return "farm plot"
	if p.distance_to(Town.GATE) < 3.5+r: return "gate"
	for pond in PONDS:
		var d: Vector2 = (p-pond[0])/pond[1]
		if d.length() < 1.12: return "pond"
	for entry in objects:
		if p.distance_to(entry.at) < float(entry.radius)+r+1.2: return "object "+String(entry.id)
	# Activities with E prompts on the map (benches, lamps...) keep their own space.
	if app and "town" in app and is_instance_valid(app.town) and "props" in app.town:
		for prop in app.town.props:
			if p.distance_to(prop.at) < 1.6+r: return "prop "+String(prop.id)
	# Buildings, bridges, piers, props and furniture (anything not terrain).
	if not ray_down(p, 2).is_empty(): return "building or bridge"
	var box := BoxShape3D.new()
	box.size = Vector3(r*2.0+0.3, 1.5, r*2.0+0.3)
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = box
	query.collision_mask = BLOCK_MASK
	query.transform = Transform3D(Basis.IDENTITY, Vector3(p.x, ground+1.1, p.y))
	var hits := space.intersect_shape(query, 1)
	if not hits.is_empty():
		var body: Object = hits[0].collider
		return "collider "+(str(body.get_parent().name) if body is Node and body.get_parent() else str(body))
	return ""

func ray_down(p: Vector2, mask: int) -> Dictionary:
	return space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x,60,p.y),Vector3(p.x,-20,p.y),mask))

## Closest point on any road centre line.
static func road_centre(p: Vector2) -> Vector2:
	var best := Vector2(INF,INF)
	for road in Roads.ROADS:
		var pts: Array = road[2]
		for i in pts.size()-1:
			var q := Geometry2D.get_closest_point_to_segment(p,pts[i],pts[i+1])
			if q.distance_to(p) < best.distance_to(p): best = q
	return best

## Metres from p to the nearest road edge (negative on a road).
static func road_gap(p: Vector2) -> float:
	var gap := INF
	for road in Roads.ROADS:
		var pts: Array = road[2]
		for i in pts.size()-1:
			gap = minf(gap, Geometry2D.get_closest_point_to_segment(p,pts[i],pts[i+1]).distance_to(p)-float(road[1])*0.5)
	return gap

## Local +Z of each object faces this way: toward its road, boards toward the camera too.
static func facing(p: Vector2, kind: String) -> Vector2:
	var toward := (road_centre(p)-p).normalized()
	if toward == Vector2.ZERO: toward = Vector2(0,1)
	# Boards lean toward the camera when their road is to the south or side; with the
	# road behind them they face the road, so the walker never reaches them from the back.
	if kind in FACE_CAMERA and toward.y > -0.35:
		var yaw := clampf(atan2(toward.x, toward.y), -0.6, 0.6)
		return Vector2(sin(yaw), cos(yaw))
	return toward

## Where the walker stands to use an object: in front of it, on its road side.
func stand_point(entry: Dictionary) -> Vector3:
	var p: Vector2 = entry.at+entry.front*(float(entry.radius)+0.5)
	var hit := ray_down(p, 1|2)
	return Vector3(p.x, hit.position.y if not hit.is_empty() else float(entry.ground), p.y)

# ------------------------------------------------------------------ module contract
func closest(at: Vector3) -> Dictionary:
	if not seat.is_empty(): return {"prompt":tr("일어나기"),"distance":0.0,"id":"stand"}
	if not view.is_empty(): return {"prompt":tr("망원경에서 눈 떼기"),"distance":0.0,"id":"look_away"}
	var best := {}
	var best_gap := INF
	var p := Vector2(at.x, at.z)
	for entry in objects:
		var gap: float = p.distance_to(entry.at)
		var reach: float = float(entry.radius)+1.15
		if gap < reach and gap < best_gap:
			best_gap = gap
			best = {"prompt":tr(PROMPTS[entry.kind]),"distance":maxf(gap-float(entry.radius),0.0),"id":entry.id}
	return best

func interact(entry: Dictionary) -> void:
	var id := String(entry.get("id",""))
	if id == "stand":
		stand_up()
		return
	if id == "look_away":
		end_view()
		return
	var target := object(id)
	if target.is_empty() or not is_instance_valid(app) or not is_instance_valid(app.player): return
	app.player.face_point(target.root.global_position)
	call("use_"+String(target.kind), target)

func leave() -> void:
	stand_up(true)
	end_view(true)
	for voice in voices:
		voice.stop()
		voice.stream = null

func object(id: String) -> Dictionary:
	for entry in objects:
		if entry.id == id: return entry
	return {}

# ------------------------------------------------------------------ frame updates
func _process(delta: float) -> void:
	clock += delta
	light_timer -= delta
	if light_timer <= 0.0:
		light_timer = 1.0
		apply_night(night_level())
	for entry in objects:
		match entry.kind:
			"vane": animate_vane(entry, delta)
			"chimes": animate_chimes(entry, delta)
			"feeder": animate_birds(entry, delta)
			"lost": close_lid_when_away(entry)
	if not view.is_empty(): update_view(delta)

func _physics_process(delta: float) -> void:
	if not seat.is_empty(): update_seat(delta)

func walker_moving() -> bool:
	return Input.get_vector("move_left","move_right","move_forward","move_back").length() > 0.3

func walker_xz() -> Vector2:
	return Vector2(app.player.position.x, app.player.position.z) if app and is_instance_valid(app.player) else Vector2(INF,INF)

## 0 by day, 1 at night: follows the village's Daylight node when there is one.
func night_level() -> float:
	var current: Dictionary = {}
	if app and "daylight" in app and is_instance_valid(app.daylight) and "current" in app.daylight: current = app.daylight.current
	if current.is_empty(): current = Daylight.sample(Daylight.clock_hour())
	return clampf(float(current.get("lamp_energy",0.0))/Daylight.LAMP_NIGHT_GAIN, 0.0, 1.0)

func apply_night(level: float) -> void:
	for lamp in lamps:
		var light: OmniLight3D = lamp.light
		if is_instance_valid(light):
			light.visible = level > 0.02
			light.light_energy = float(lamp.energy)*level
		var glow: StandardMaterial3D = lamp.material
		glow.emission_energy_multiplier = 0.15+float(lamp.glow)*level

# ------------------------------------------------------------------ sound
func play(sound_name: String, at := Vector3.INF, db := -9.0) -> void:
	if not sounds.has(sound_name):
		var path := SFX % sound_name
		sounds[sound_name] = load(path) if ResourceLoader.exists(path) else null
	var stream: AudioStream = sounds[sound_name]
	if stream == null:
		if app and "sound" in app and is_instance_valid(app.sound): app.sound.effect("click")
		return
	if at != Vector3.INF and app and is_instance_valid(app.player):
		# Quieter with distance from the walker (the camera floats far above).
		db -= clampf(app.player.position.distance_to(at)-2.0, 0.0, 30.0)*0.7
		if db < -40.0: return
	var voice := voices[voice_index]
	voice_index = (voice_index+1)%voices.size()
	voice.stream = stream
	voice.volume_db = db
	voice.pitch_scale = rng.randf_range(0.97,1.03)
	voice.play()

# ------------------------------------------------------------------ mesh helpers
## Each object is built from a dozen primitives, and drawing every one on its own
## cost ~200 draw calls (plus shadow passes) around the square. Fixed parts hanging
## straight off the object root are merged into one mesh per material; anything an
## animation holds (stored in the entry), lamps and transparent parts stay separate.
func merge_static(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	var keep := {}
	for value in entry.values():
		if value is Node: keep[value] = true
		elif value is Array:
			for item in value:
				if item is Node: keep[item] = true
	var groups := {}
	for child in root.get_children():
		if not child is MeshInstance3D or keep.has(child) or child.get_child_count() > 0: continue
		var material := (child as MeshInstance3D).material_override as StandardMaterial3D
		if material == null or material.emission_enabled or material.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED: continue
		var key := "%s|%.2f|%.2f" % [material.albedo_color.to_html(), material.metallic, material.roughness]
		if not groups.has(key): groups[key] = []
		groups[key].append(child)
	for key in groups:
		var parts: Array = groups[key]
		if parts.size() < 2: continue
		var tool := SurfaceTool.new()
		for part: MeshInstance3D in parts:
			tool.append_from(part.mesh, 0, part.transform)
		var merged := MeshInstance3D.new()
		merged.mesh = tool.commit()
		merged.material_override = parts[0].material_override
		root.add_child(merged)
		for part: MeshInstance3D in parts:
			root.remove_child(part)
			part.free()

func mat(color: Color, metal := 0.0, rough := 0.9) -> StandardMaterial3D:
	var m := A.material(color)
	m.metallic = metal
	m.roughness = rough
	return m

func box(parent: Node3D, at: Vector3, size: Vector3, color: Color, metal := 0.0) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	node.mesh = mesh
	node.position = at
	node.material_override = mat(color, metal, 0.45 if metal > 0.0 else 0.9)
	parent.add_child(node)
	return node

func cyl(parent: Node3D, at: Vector3, radius: float, height: float, color: Color, top := -1.0, metal := 0.0, sides := 12) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.bottom_radius = radius
	mesh.top_radius = radius if top < 0.0 else top
	mesh.height = height
	mesh.radial_segments = sides
	mesh.rings = 1
	node.mesh = mesh
	node.position = at
	node.material_override = mat(color, metal, 0.4 if metal > 0.0 else 0.9)
	parent.add_child(node)
	return node

func ball(parent: Node3D, at: Vector3, size: Vector3, color: Color) -> MeshInstance3D:
	var node := A.sphere(parent, at, size, color)
	return node

## A beam between two local points (posts, legs, ropes).
func beam(parent: Node3D, a: Vector3, b: Vector3, thick: float, color: Color) -> MeshInstance3D:
	var node := box(parent, (a+b)*0.5, Vector3(thick, a.distance_to(b), thick), color)
	var up := (b-a).normalized()
	var side := up.cross(Vector3.FORWARD if absf(up.dot(Vector3.FORWARD)) < 0.95 else Vector3.RIGHT).normalized()
	node.basis = Basis(side, up, side.cross(up)).orthonormalized()
	return node

func solid(parent: Node3D, at: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	body.collision_layer = PROP_LAYER
	body.collision_mask = 0
	var shape := CollisionShape3D.new()
	var bounds := BoxShape3D.new()
	bounds.size = size
	shape.shape = bounds
	shape.position = at
	body.add_child(shape)
	parent.add_child(body)

## A warm lamp: emissive bulb that brightens at night plus a small light.
func lamp(parent: Node3D, at: Vector3, size := 0.13, energy := 0.9, reach := 3.6, color := Color("ffd59a")) -> void:
	var bulb := ball(parent, at, Vector3.ONE*size, color)
	var glow := StandardMaterial3D.new()
	glow.albedo_color = color
	glow.emission_enabled = true
	glow.emission = color
	glow.emission_energy_multiplier = 0.15
	bulb.material_override = glow
	bulb.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var light: OmniLight3D = null
	if energy > 0.0:
		light = OmniLight3D.new()
		light.position = at
		light.light_color = color
		light.omni_range = reach
		light.omni_attenuation = 1.4
		light.shadow_enabled = false
		light.visible = false
		parent.add_child(light)
	lamps.append({"light":light,"material":glow,"energy":energy,"glow":2.6})

func nameplate(parent: Node3D, text: String, at: Vector3, color := Color("f5e5b7")) -> Label3D:
	var label := A.label3d(parent, text, at, color)
	A.style_nameplate(label, 18)
	label.no_depth_test = false
	label.add_to_group("place_nameplates")
	return label

## Flat text painted on a board (not billboarded).
func painted(parent: Node3D, text: String, at: Vector3, size := 26, color := Color("3c2f22")) -> Label3D:
	var label := Label3D.new()
	label.text = tr(text)
	label.position = at
	label.pixel_size = 0.005
	label.font_size = size
	label.modulate = color
	label.outline_size = 0
	label.double_sided = false
	label.shaded = true
	parent.add_child(label)
	return label

const WOOD := Color("8a6a48")
const WOOD_DARK := Color("6b5039")
const WOOD_LIGHT := Color("b8946a")
const STONE := Color("b5ad9c")
const STONE_DARK := Color("8d8678")
const BRASS := Color("c9a24f")
const IRON := Color("4b5056")
const PAPER := Color("f3ead2")
const ROOF := Color("b0584a")

# ------------------------------------------------------------------ builders (local +Z = front)
func make_signpost(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	cyl(root, Vector3(0,1.2,0), 0.075, 2.4, WOOD_DARK, 0.065)
	cyl(root, Vector3(0,0.08,0), 0.2, 0.16, STONE_DARK, 0.17)
	solid(root, Vector3(0,0.9,0), Vector3(0.25,1.8,0.25))
	var island: String = entry.spec.island
	var hubs := {}
	for spec in SPECS:
		if spec.kind == "signpost": hubs[spec.island] = spec.at
	var colors := [Color("d9c08a"), Color("c99a6b"), Color("a9c3a0"), Color("c7b2d0"), Color("9fbfcf")]
	var row := 0
	for key in ISLANDS:
		if key == island: continue
		var direction: Vector2 = (hubs[key]-entry.at).normalized()
		var arm := Node3D.new()
		# guide.gd lights the board pointing to the guided goal's island.
		arm.set_meta("island", key)
		root.add_child(arm)
		arm.position.y = 2.05-row*0.27
		# Boards point at the other islands in world space, whatever the post's yaw.
		arm.rotation.y = atan2(direction.x, direction.y)-root.rotation.y
		box(arm, Vector3(0,0,0.42), Vector3(0.05,0.19,0.72), colors[row])
		var tip := box(arm, Vector3(0,0,0.8), Vector3(0.05,0.135,0.135), colors[row])
		tip.rotation.x = PI*0.25
		row += 1
	# A little roof and lantern so the post reads at night.
	var cap := cyl(root, Vector3(0,2.5,0), 0.22, 0.16, ROOF, 0.02, 0.0, 6)
	cap.rotation.y = 0.3
	box(root, Vector3(0,2.12,0.16), Vector3(0.05,0.05,0.24), IRON)
	box(root, Vector3(0,2.0,0.28), Vector3(0.14,0.03,0.14), IRON)
	lamp(root, Vector3(0,1.9,0.28), 0.13, 0.8, 4.0)
	nameplate(root, tr("%s 이정표") % tr(ISLANDS[island]), Vector3(0,2.95,0))

func make_mailbox(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	box(root, Vector3(0,0.5,0), Vector3(0.1,1.0,0.1), WOOD)
	box(root, Vector3(0,1.0,0), Vector3(0.36,0.04,0.56), WOOD_DARK)
	var body := box(root, Vector3(0,1.15,0), Vector3(0.32,0.26,0.52), Color("c4553f"))
	var top := cyl(root, Vector3(0,1.28,0), 0.16, 0.52, Color("c4553f"))
	top.rotation.x = PI*0.5
	solid(root, Vector3(0,0.65,0), Vector3(0.36,1.3,0.56))
	# Front flap hinges at its bottom edge; it drops open when the box is checked.
	var flap := Node3D.new()
	flap.position = Vector3(0,1.02,0.27)
	root.add_child(flap)
	box(flap, Vector3(0,0.19,0.005), Vector3(0.3,0.38,0.03), Color("a9432f"))
	box(flap, Vector3(0,0.3,0.03), Vector3(0.1,0.03,0.04), BRASS, 0.8)
	entry.flap = flap
	# Flag on the side: raised when letters or invites are waiting.
	var flag := Node3D.new()
	flag.position = Vector3(0.18,1.12,-0.12)
	root.add_child(flag)
	box(flag, Vector3(0.01,0.0,0.16), Vector3(0.025,0.04,0.32), Color("e9c44a"))
	box(flag, Vector3(0.01,0.0,0.3), Vector3(0.025,0.16,0.1), Color("e9c44a"))
	entry.flag = flag
	painted(root, "나의 집", Vector3(0,1.15,0.262), 22, Color("fbe9cf"))
	entry.next_check = 0.0

func make_notice(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	for x in [-0.78, 0.78]:
		box(root, Vector3(x,1.0,0), Vector3(0.11,2.0,0.11), WOOD_DARK)
	box(root, Vector3(0,1.35,0), Vector3(1.66,1.06,0.07), WOOD)
	box(root, Vector3(0,1.35,0.04), Vector3(1.5,0.92,0.02), Color("c79f6e"))
	var roof := box(root, Vector3(0,2.02,0.0), Vector3(1.95,0.07,0.5), ROOF)
	roof.rotation.x = -0.12
	solid(root, Vector3(0,1.0,0), Vector3(1.75,2.0,0.2))
	var notes := [[-0.48,1.55,Color("f7f0d8"),0.05],[-0.1,1.5,Color("fbe3a6"),-0.08],[0.33,1.58,Color("e3f0f5"),0.06],
		[-0.42,1.12,Color("f3d9d4"),-0.04],[0.05,1.1,Color("f7f0d8"),0.09],[0.45,1.15,Color("dff0d3"),-0.07]]
	for n in notes:
		var note := box(root, Vector3(n[0],n[1],0.06), Vector3(0.3,0.34,0.012), n[2])
		note.rotation.z = n[3]
		box(root, Vector3(n[0],n[1]+0.14,0.07), Vector3(0.035,0.035,0.012), Color("c94d3f"))
	var header := painted(root, "마을 게시판", Vector3(0,1.93,0.27), 30, Color("fbe9cf"))
	header.rotation.x = -0.12
	box(root, Vector3(0,1.86,0.2), Vector3(0.04,0.04,0.2), IRON)
	lamp(root, Vector3(0,1.78,0.3), 0.12, 0.7, 3.2)
	entry.board = root

func make_well(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	cyl(root, Vector3(0,0.38,0), 0.9, 0.76, STONE, -1.0, 0.0, 16)
	cyl(root, Vector3(0,0.78,0), 0.95, 0.08, STONE_DARK, -1.0, 0.0, 16)
	var water := cyl(root, Vector3(0,0.66,0), 0.72, 0.04, Color("2f6170"), -1.0, 0.0, 16)
	water.material_override.roughness = 0.15
	entry.water_y = 0.69
	for x in [-0.82, 0.82]:
		box(root, Vector3(x,1.35,0), Vector3(0.12,1.2,0.12), WOOD_DARK)
	for side in [-1.0, 1.0]:
		var slope := box(root, Vector3(0,2.08,side*0.4), Vector3(2.05,0.07,0.9), ROOF)
		slope.rotation.x = side*0.42
	box(root, Vector3(0,2.27,0), Vector3(2.1,0.08,0.08), WOOD_DARK)
	box(root, Vector3(0,1.62,0), Vector3(1.64,0.07,0.07), WOOD)
	var bucket := cyl(root, Vector3(0,1.22,0), 0.13, 0.2, WOOD_LIGHT, 0.15)
	beam(root, Vector3(0,1.32,0), Vector3(0,1.6,0), 0.015, Color("d8c9a3"))
	box(root, Vector3(0.9,1.62,0.0), Vector3(0.06,0.06,0.3), IRON)
	entry.bucket = bucket
	solid(root, Vector3(0,0.5,0), Vector3(1.8,1.0,1.8))
	lamp(root, Vector3(0,1.85,0.0), 0.11, 0.7, 3.4)

func make_fountain(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	cyl(root, Vector3(0,0.06,0), 0.42, 0.12, STONE_DARK, -1.0, 0.0, 10)
	cyl(root, Vector3(0,0.5,0), 0.17, 0.8, STONE, 0.14, 0.0, 10)
	cyl(root, Vector3(0,0.95,0), 0.3, 0.12, STONE, 0.34, 0.0, 12)
	var dish := cyl(root, Vector3(0,1.005,0), 0.25, 0.02, Color("4d8494"), -1.0, 0.0, 12)
	dish.material_override.roughness = 0.2
	var spout := cyl(root, Vector3(0,1.1,-0.12), 0.025, 0.16, BRASS, -1.0, 0.8)
	spout.rotation.x = 0.5
	box(root, Vector3(0.24,0.98,0), Vector3(0.05,0.05,0.1), BRASS, 0.8)
	solid(root, Vector3(0,0.55,0), Vector3(0.6,1.1,0.6))
	var spray := CPUParticles3D.new()
	spray.position = Vector3(0,1.17,-0.08)
	spray.emitting = false
	spray.amount = 40
	spray.lifetime = 0.55
	spray.direction = Vector3(0,1,0.55)
	spray.spread = 6
	spray.initial_velocity_min = 1.3
	spray.initial_velocity_max = 1.5
	spray.gravity = Vector3(0,-6,0)
	spray.scale_amount_min = 0.025
	spray.scale_amount_max = 0.04
	var drop := SphereMesh.new()
	drop.radius = 0.5
	drop.height = 1.0
	drop.radial_segments = 6
	drop.rings = 3
	spray.mesh = drop
	var water := StandardMaterial3D.new()
	water.albedo_color = Color(0.7,0.88,0.95,0.8)
	water.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	water.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	spray.material_override = water
	root.add_child(spray)
	entry.spray = spray

func make_swing(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	for x in [-1.1, 1.1]:
		beam(root, Vector3(x,0,-0.65), Vector3(x,2.3,0), 0.1, WOOD_DARK)
		beam(root, Vector3(x,0,0.65), Vector3(x,2.3,0), 0.1, WOOD_DARK)
		solid(root, Vector3(x,1.0,0), Vector3(0.18,2.0,1.1))
	box(root, Vector3(0,2.33,0), Vector3(2.5,0.12,0.12), WOOD)
	var pivot := Node3D.new()
	pivot.position = Vector3(0,2.27,0)
	root.add_child(pivot)
	for x in [-0.36, 0.36]:
		box(pivot, Vector3(x,-0.88,0), Vector3(0.025,1.76,0.025), Color("d8c9a3"))
	box(pivot, Vector3(0,-1.77,0), Vector3(0.82,0.06,0.34), Color("c06b4f"))
	entry.pivot = pivot
	entry.seat_local = Vector3(0,-1.72,0)

func make_rocker(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	var pivot := Node3D.new()
	root.add_child(pivot)
	for x in [-0.25, 0.25]:
		var rocker := box(pivot, Vector3(x,0.05,0), Vector3(0.05,0.05,0.95), WOOD_DARK)
		rocker.rotation.x = 0.0
		box(pivot, Vector3(x,0.25,0.18), Vector3(0.05,0.42,0.05), WOOD)
		box(pivot, Vector3(x,0.25,-0.18), Vector3(0.05,0.42,0.05), WOOD)
		box(pivot, Vector3(x,0.65,0.02), Vector3(0.05,0.05,0.5), WOOD)
		box(pivot, Vector3(x,0.58,0.2), Vector3(0.04,0.18,0.04), WOOD)
	box(pivot, Vector3(0,0.46,0), Vector3(0.56,0.06,0.48), WOOD_LIGHT)
	box(pivot, Vector3(0,0.5,0.0), Vector3(0.44,0.05,0.4), Color("6f8fb0"))
	var back := box(pivot, Vector3(0,0.82,-0.27), Vector3(0.52,0.66,0.05), WOOD)
	back.rotation.x = -0.18
	for x in [-0.15, 0.0, 0.15]:
		var slat := box(pivot, Vector3(x,0.82,-0.24), Vector3(0.06,0.6,0.02), WOOD_LIGHT)
		slat.rotation.x = -0.18
	solid(root, Vector3(0,0.3,0), Vector3(0.6,0.6,0.7))
	entry.pivot = pivot
	entry.seat_local = Vector3(0,0.49,0.02)

func make_hammock(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	for x in [-1.45, 1.45]:
		cyl(root, Vector3(x,0.85,0), 0.08, 1.7, WOOD_DARK)
		solid(root, Vector3(x,0.85,0), Vector3(0.2,1.7,0.2))
		cyl(root, Vector3(x,1.72,0), 0.1, 0.05, WOOD)
	var pivot := Node3D.new()
	pivot.position = Vector3(0,1.42,0)
	root.add_child(pivot)
	# Sagging striped cloth from a small grid (catenary-ish curve along X).
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var cols := 12
	var rows := 4
	var stripes := [Color("e0a35c"), Color("f1e3c2"), Color("6f9fb1"), Color("f1e3c2")]
	for i in cols:
		for j in rows:
			var quad := []
			for c in [[i,j],[i+1,j],[i,j+1],[i+1,j+1]]:
				var u := float(c[0])/cols
				var v := float(c[1])/rows
				var x := lerpf(-1.05, 1.05, u)
				var z := lerpf(-0.42, 0.42, v)
				var y := -0.78*(1.0-pow(2.0*u-1.0, 2.0))-0.12*(1.0-pow(2.0*v-1.0, 2.0))
				quad.append(Vector3(x,y,z))
			for k in [0,1,2,2,1,3]:
				st.set_color(stripes[j%stripes.size()])
				st.add_vertex(quad[k])
	st.generate_normals()
	var cloth := MeshInstance3D.new()
	cloth.mesh = st.commit()
	var cloth_mat := StandardMaterial3D.new()
	cloth_mat.vertex_color_use_as_albedo = true
	cloth_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	cloth_mat.roughness = 1.0
	cloth.material_override = cloth_mat
	pivot.add_child(cloth)
	for x in [-1.0, 1.0]:
		for z in [-0.4, 0.4]:
			beam(pivot, Vector3(x*1.43,0.22,0), Vector3(x*1.05,0,z), 0.02, Color("d8c9a3"))
	entry.pivot = pivot
	entry.seat_local = Vector3(0,-0.84,0.0)

func make_vane(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	cyl(root, Vector3(0,0.12,0), 0.24, 0.24, STONE_DARK, 0.2)
	cyl(root, Vector3(0,1.4,0), 0.045, 2.6, IRON, 0.035, 0.6)
	solid(root, Vector3(0,1.0,0), Vector3(0.3,2.0,0.3))
	# The compass letters stay true to the world whatever the post's yaw.
	var compass := Node3D.new()
	compass.position.y = 2.3
	root.add_child(compass)
	compass.rotation.y = -root.rotation.y
	box(compass, Vector3.ZERO, Vector3(0.025,0.025,0.6), IRON, 0.6)
	box(compass, Vector3.ZERO, Vector3(0.6,0.025,0.025), IRON, 0.6)
	for k in 4:
		var letter := Label3D.new()
		letter.text = tr(["남","동","북","서"][k])
		letter.position = Vector3(sin(k*PI*0.5)*0.36,0,cos(k*PI*0.5)*0.36)
		letter.pixel_size = 0.006
		letter.font_size = 34
		letter.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		letter.modulate = Color("f1e2b8")
		letter.outline_size = 6
		compass.add_child(letter)
	var arrow := Node3D.new()
	arrow.position.y = 2.62
	root.add_child(arrow)
	box(arrow, Vector3(0,0,0), Vector3(0.04,0.04,0.95), BRASS, 0.7)
	var head := box(arrow, Vector3(0,0,0.5), Vector3(0.03,0.14,0.14), BRASS, 0.7)
	head.rotation.x = PI*0.25
	box(arrow, Vector3(0,0.06,-0.42), Vector3(0.02,0.24,0.22), BRASS, 0.7)
	# A little rooster rides on top.
	ball(arrow, Vector3(0,0.16,0.05), Vector3(0.14,0.16,0.24), Color("2f3439"))
	ball(arrow, Vector3(0,0.27,0.14), Vector3(0.09,0.1,0.09), Color("2f3439"))
	box(arrow, Vector3(0,0.33,0.14), Vector3(0.02,0.06,0.07), Color("c94d3f"))
	box(arrow, Vector3(0,0.22,-0.08), Vector3(0.02,0.16,0.1), Color("2f3439"))
	entry.arrow = arrow
	entry.wind = rng.randf_range(0, TAU)
	entry.spin = 0.0

func make_feeder(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	box(root, Vector3(0,0.7,0), Vector3(0.09,1.4,0.09), WOOD_DARK)
	box(root, Vector3(0,1.4,0), Vector3(0.62,0.05,0.62), WOOD)
	for x in [-0.29, 0.29]:
		box(root, Vector3(x,1.47,0), Vector3(0.04,0.1,0.62), WOOD)
	for side in [-1.0, 1.0]:
		var slope := box(root, Vector3(side*0.19,1.83,0), Vector3(0.48,0.04,0.7), Color("7b9a6a"))
		slope.rotation.z = -side*0.62
	for x in [-0.24, 0.24]:
		box(root, Vector3(x,1.6,0.26), Vector3(0.04,0.4,0.04), WOOD)
		box(root, Vector3(x,1.6,-0.26), Vector3(0.04,0.4,0.04), WOOD)
	solid(root, Vector3(0,0.75,0), Vector3(0.3,1.5,0.3))
	var seeds := Node3D.new()
	root.add_child(seeds)
	for i in 14:
		ball(seeds, Vector3(rng.randf_range(-0.22,0.22),1.44,rng.randf_range(-0.22,0.22)), Vector3.ONE*0.05, Color("d8b56a"))
	entry.seeds = seeds
	var perches := [Vector3(-0.15,1.43,0.12), Vector3(0.17,1.43,-0.08), Vector3(0.0,1.43,0.26), Vector3(0.55,0.02,0.35), Vector3(-0.5,0.02,0.45)]
	var colors := [Color("6c8fb5"), Color("b5714b"), Color("e0c45a"), Color("8e8a7e"), Color("6c8fb5")]
	var birds := []
	for i in perches.size():
		var bird := Node3D.new()
		root.add_child(bird)
		bird.position = perches[i]
		bird.rotation.y = rng.randf_range(-PI, PI)
		ball(bird, Vector3(0,0.07,0), Vector3(0.13,0.11,0.19), colors[i])
		ball(bird, Vector3(0,0.13,0.08), Vector3(0.09,0.09,0.09), colors[i])
		var beak := A.cone(bird, Vector3(0,0.13,0.14), 0.02, 0.06, Color("e2a447"))
		beak.rotation.x = PI*0.5
		var tail := box(bird, Vector3(0,0.09,-0.11), Vector3(0.06,0.015,0.09), colors[i].darkened(0.25))
		tail.rotation.x = -0.4
		for s in [-1.0, 1.0]:
			var wing := box(bird, Vector3(s*0.06,0.08,-0.01), Vector3(0.015,0.07,0.12), colors[i].darkened(0.15))
			wing.name = "Wing"
		birds.append({"node":bird,"home":perches[i],"phase":rng.randf_range(0,TAU)})
	entry.birds = birds
	entry.away = 0.0

func make_chimes(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	box(root, Vector3(0,1.05,0), Vector3(0.1,2.1,0.1), WOOD_DARK)
	box(root, Vector3(0,2.0,0.28), Vector3(0.07,0.07,0.6), WOOD)
	solid(root, Vector3(0,1.0,0), Vector3(0.25,2.0,0.25))
	var hanger := Node3D.new()
	hanger.position = Vector3(0,1.96,0.5)
	root.add_child(hanger)
	cyl(hanger, Vector3(0,-0.1,0), 0.16, 0.035, WOOD_LIGHT)
	beam(hanger, Vector3(0,0,0), Vector3(0,-0.1,0), 0.012, Color("d8c9a3"))
	var tubes := []
	for k in 6:
		var angle := k*TAU/6.0
		var length := 0.34+0.05*k
		var pivot := Node3D.new()
		pivot.position = Vector3(cos(angle)*0.12,-0.12,sin(angle)*0.12)
		hanger.add_child(pivot)
		beam(pivot, Vector3.ZERO, Vector3(0,-0.08,0), 0.008, Color("d8c9a3"))
		cyl(pivot, Vector3(0,-0.08-length*0.5,0), 0.022, length, Color("cfd6dc"), -1.0, 0.85, 8)
		tubes.append({"node":pivot,"phase":angle})
	ball(hanger, Vector3(0,-0.38,0), Vector3.ONE*0.07, WOOD_LIGHT)
	box(hanger, Vector3(0,-0.62,0), Vector3(0.1,0.16,0.01), Color("e8d6a8"))
	entry.tubes = tubes
	entry.ring = 0.0
	entry.next_ring = rng.randf_range(4.0, 9.0)

func make_gong(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	for x in [-0.75, 0.75]:
		box(root, Vector3(x,0.95,0), Vector3(0.12,1.9,0.12), Color("8e3b2f"))
		box(root, Vector3(x,0.06,0), Vector3(0.18,0.12,0.6), WOOD_DARK)
		solid(root, Vector3(x,0.95,0), Vector3(0.2,1.9,0.3))
	var bar := box(root, Vector3(0,1.92,0), Vector3(1.8,0.12,0.14), Color("8e3b2f"))
	bar.rotation.z = 0.0
	box(root, Vector3(0,1.99,0), Vector3(1.95,0.05,0.2), Color("2f2a26"))
	var pivot := Node3D.new()
	pivot.position = Vector3(0,1.84,0)
	root.add_child(pivot)
	for x in [-0.2, 0.2]:
		beam(pivot, Vector3(x,0,0), Vector3(x*0.6,-0.28,0), 0.015, Color("d8c9a3"))
	var disc := cyl(pivot, Vector3(0,-0.88,0), 0.6, 0.05, BRASS, -1.0, 0.8, 24)
	disc.rotation.x = PI*0.5
	var boss := ball(pivot, Vector3(0,-0.88,0.03), Vector3(0.24,0.24,0.1), Color("d8b35e"))
	boss.material_override.metallic = 0.8
	boss.material_override.roughness = 0.35
	var rim := MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.55
	torus.outer_radius = 0.61
	torus.rings = 24
	torus.ring_segments = 6
	rim.mesh = torus
	rim.rotation.x = PI*0.5
	rim.position = Vector3(0,-0.88,0.0)
	rim.material_override = mat(Color("a8833b"), 0.8, 0.4)
	pivot.add_child(rim)
	# The mallet rests against the right post.
	var mallet := beam(root, Vector3(0.95,0.0,0.15), Vector3(0.82,0.85,0.12), 0.04, WOOD_LIGHT)
	mallet.name = "Mallet"
	ball(root, Vector3(0.81,0.9,0.12), Vector3(0.16,0.16,0.16), Color("e8dcc0"))
	entry.pivot = pivot

func make_photo(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	var frame_color := Color("f0e6d0")
	for x in [-0.82, 0.82]:
		box(root, Vector3(x,1.05,0), Vector3(0.12,2.1,0.12), frame_color)
		box(root, Vector3(x,0.04,0), Vector3(0.22,0.08,0.5), WOOD)
		solid(root, Vector3(x,1.05,0), Vector3(0.18,2.1,0.2))
	box(root, Vector3(0,2.1,0), Vector3(1.86,0.14,0.14), frame_color)
	box(root, Vector3(0,0.62,0), Vector3(1.64,0.1,0.1), frame_color)
	# Garland and fairy lights along the top.
	var flower_colors := [Color("e88b9a"), Color("f2d06b"), Color("f7f2e8"), Color("9fc7e8")]
	for i in 11:
		var x := lerpf(-0.88, 0.88, i/10.0)
		ball(root, Vector3(x,2.2+sin(i*1.7)*0.02,0.05), Vector3.ONE*0.11, flower_colors[i%4])
		if i%2 == 1: ball(root, Vector3(x+0.04,2.16,0.09), Vector3(0.09,0.05,0.07), Color("7fa86a"))
	for i in 9:
		var x := lerpf(-0.78, 0.78, i/8.0)
		var sag := -0.12*(1.0-pow((i/8.0)*2.0-1.0, 2.0))
		lamp(root, Vector3(x,1.98+sag,0.09), 0.055, 0.0 if i != 4 else 0.6, 3.0, Color("ffe2a8"))
	var plate := Node3D.new()
	plate.position = Vector3(0.55,0.32,0.12)
	root.add_child(plate)
	box(plate, Vector3(0,0,0), Vector3(0.62,0.22,0.03), Color("6f8fb0"))
	box(plate, Vector3(0,-0.2,-0.02), Vector3(0.04,0.3,0.04), WOOD)
	painted(plate, "포토 스팟", Vector3(0,0,0.02), 26, Color("fbf3dc"))

func make_lost(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	box(root, Vector3(0,0.24,0), Vector3(0.9,0.44,0.56), WOOD)
	for x in [-0.46, 0.46]:
		box(root, Vector3(x,0.24,0), Vector3(0.03,0.46,0.58), WOOD_DARK)
	box(root, Vector3(0,0.24,0.285), Vector3(0.92,0.05,0.02), WOOD_DARK)
	box(root, Vector3(0,0.36,0.29), Vector3(0.1,0.1,0.02), BRASS, 0.8)
	solid(root, Vector3(0,0.25,0), Vector3(0.95,0.5,0.6))
	# Something soft peeks out when the lid lifts.
	ball(root, Vector3(-0.18,0.44,0.0), Vector3(0.32,0.12,0.26), Color("8fc0dd"))
	ball(root, Vector3(0.16,0.45,-0.05), Vector3(0.26,0.1,0.22), Color("e3c37a"))
	var lid := Node3D.new()
	lid.position = Vector3(0,0.46,-0.28)
	root.add_child(lid)
	box(lid, Vector3(0,0.03,0.28), Vector3(0.92,0.06,0.58), WOOD_LIGHT)
	box(lid, Vector3(0,0.065,0.28), Vector3(0.94,0.02,0.1), WOOD_DARK)
	entry.lid = lid
	var tag := Node3D.new()
	tag.position = Vector3(0.32,0.25,0.3)
	root.add_child(tag)
	box(tag, Vector3(0,0,0), Vector3(0.26,0.16,0.01), PAPER)
	painted(tag, "분실물", Vector3(0,0,0.008), 20, Color("5a4632"))
	entry.open = false

func make_telescope(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	for k in 3:
		var angle := k*TAU/3.0+0.3
		beam(root, Vector3(cos(angle)*0.38,0,sin(angle)*0.38), Vector3(0,1.05,0), 0.035, WOOD_DARK)
	cyl(root, Vector3(0,1.08,0), 0.07, 0.08, BRASS, -1.0, 0.8)
	solid(root, Vector3(0,0.55,0), Vector3(0.5,1.1,0.5))
	var head := Node3D.new()
	head.position = Vector3(0,1.15,0)
	root.add_child(head)
	var tilt := Node3D.new()
	head.add_child(tilt)
	tilt.rotation.x = -0.22
	var tube := cyl(tilt, Vector3(0,0,0.1), 0.065, 0.85, BRASS, 0.05, 0.8)
	tube.rotation.x = PI*0.5
	var lens := cyl(tilt, Vector3(0,0,0.52), 0.07, 0.04, Color("2b3b48"), -1.0, 0.3)
	lens.rotation.x = PI*0.5
	var eye := cyl(tilt, Vector3(0,0,-0.36), 0.035, 0.16, IRON, -1.0, 0.5)
	eye.rotation.x = PI*0.5
	for z in [-0.12, 0.3]:
		var band := cyl(tilt, Vector3(0,0,z), 0.072, 0.03, Color("8a6a2f"), -1.0, 0.8)
		band.rotation.x = PI*0.5
	entry.head = head
	entry.target = 0
	aim_telescope(entry, 0, true)

func aim_telescope(entry: Dictionary, index: int, snap := false) -> void:
	var targets: Array = entry.spec.targets
	var goal: Vector2 = targets[index%targets.size()][1]
	var direction: Vector2 = (goal-entry.at).normalized()
	var yaw: float = atan2(direction.x, direction.y)-float(entry.root.rotation.y)
	var head: Node3D = entry.head
	if snap: head.rotation.y = yaw
	else: head.create_tween().tween_property(head, "rotation:y", head.rotation.y+wrapf(yaw-head.rotation.y,-PI,PI), 0.6).set_trans(Tween.TRANS_SINE)

# ------------------------------------------------------------------ uses
func use_signpost(entry: Dictionary) -> void:
	play("paper", entry.root.global_position, -14.0)
	var here: String = entry.spec.island
	var choices := []
	for other in objects:
		if other.kind != "signpost" or other.spec.island == here: continue
		choices.append([tr("%s(으)로 가기") % tr(ISLANDS[other.spec.island]), travel.bind(other)])
	choices.append([tr("그만두기"), Callable()])
	var lines := [tr("「%s」 이정표예요. 화살표마다 다른 섬의 이름이 적혀 있어요.") % tr(ISLANDS[here]),
		tr("어느 섬으로 갈까요? 다리를 건너지 않고 바로 이동해요.")]
	if app.has_method("open_dialogue"): app.open_dialogue(tr("이정표"), "", lines, choices)

## Fades out, moves the walker to the destination signpost's road-side spot, fades in.
func travel(destination: Dictionary) -> void:
	if not is_instance_valid(app) or not is_instance_valid(app.player): return
	var arrival := arrival_point(destination)
	if arrival == Vector3.INF:
		app.message(tr("지금은 그 섬으로 가는 길이 막혀 있어요."))
		return
	var veil := Transition.of(get_tree())
	play("whoosh", Vector3.INF, -10.0)
	await veil.fade_out(0.35)
	if not is_instance_valid(app) or not is_instance_valid(app.player): return
	stand_up(true)
	end_view(true)
	app.player.velocity = Vector3.ZERO
	app.player.position = arrival
	if "safe_position" in app.player:
		app.player.safe_position = arrival
		app.player.has_safe_position = true
	app.player.face_point(destination.root.global_position)
	if app.has_method("follow_camera"): app.follow_camera(1.0)
	await veil.fade_in(0.45)
	if is_instance_valid(app) and is_instance_valid(app.player):
		Fx.title(app, app.player.global_position, tr(ISLANDS[destination.spec.island]))
		Fx.burst(self, app.player.global_position+Vector3(0,0.2,0), "dust", 6, Color(0,0,0,0), 0.3)

## A clear spot on the road beside a signpost (cached).
func arrival_point(entry: Dictionary) -> Vector3:
	if entry.has("arrival"): return entry.arrival
	var centre := road_centre(entry.at)
	var along: Vector2 = (centre-entry.at).normalized()
	var found := Vector3.INF
	for offset in [0.0, 0.8, -0.8, 1.6, -1.6, 2.4, -2.4, 3.2, -3.2]:
		var p: Vector2 = centre+along.orthogonal()*offset
		var hit := ray_down(p, 1|2)
		if hit.is_empty() or hit.position.y < 1.0: continue
		var capsule := CapsuleShape3D.new()
		capsule.radius = Profile.BODY_RADIUS
		capsule.height = Profile.BODY_HEIGHT
		var query := PhysicsShapeQueryParameters3D.new()
		query.shape = capsule
		query.collision_mask = BLOCK_MASK
		query.transform = Transform3D(Basis.IDENTITY, hit.position+Vector3(0, Profile.BODY_HEIGHT*0.5+0.12, 0))
		if not space.intersect_shape(query, 1).is_empty(): continue
		found = hit.position+Vector3(0,0.05,0)
		break
	entry.arrival = found
	return found

func use_mailbox(entry: Dictionary) -> void:
	play("lid", entry.root.global_position)
	var flap: Node3D = entry.flap
	var tween := flap.create_tween()
	tween.tween_property(flap, "rotation:x", 1.35, 0.25).set_trans(Tween.TRANS_BACK)
	tween.tween_interval(2.4)
	tween.tween_property(flap, "rotation:x", 0.0, 0.3)
	var lines := mail_lines()
	var choices := []
	if app.social and app.social.enabled: choices.append([tr("함께하기 메뉴 열기"), app.social.open_menu])
	choices.append([tr("우편함 닫기"), Callable()])
	if app.has_method("open_dialogue"): app.open_dialogue(tr("나의 우편함"), "", lines, choices)

## What the mailbox says: invites, rewards waiting and recent notes (read-only).
func mail_lines() -> Array:
	var lines := []
	var data: Dictionary = app.social.data if app.social else {}
	var invites: Array = data.get("invites", []) if data.get("invites") is Array else []
	var rewards: Array = data.get("pending_rewards", []) if data.get("pending_rewards") is Array else []
	var notes: Array = data.get("messages", []) if data.get("messages") is Array else []
	var who := str(app.me.get("username", "")) if app.me is Dictionary else ""
	if invites.is_empty() and rewards.is_empty() and notes.is_empty():
		lines.append(tr("우편함이 비어 있어요.") if who.is_empty() else tr("%s님 앞으로 온 편지는 아직 없어요.") % who)
		lines.append(tr("친구가 마을이나 파티에 초대하면 초대장이 이곳에 도착해요.") if app.social and app.social.enabled
			else tr("함께하기가 켜진 월드에서는 친구의 초대장이 이곳에 도착해요."))
		return lines
	if not invites.is_empty():
		var senders := PackedStringArray()
		for invite in invites.slice(0, 3):
			senders.append("%s (%s)" % [str(invite.get("sender","?")), tr("마을 방문") if invite.get("kind","")=="village" else tr("파티")])
		lines.append(tr("초대장이 %d통 와 있어요: %s") % [invites.size(), ", ".join(senders)])
	if not rewards.is_empty(): lines.append(tr("받지 않은 보상 꾸러미가 %d개 있어요. 함께하기 메뉴에서 받을 수 있어요.") % rewards.size())
	if not notes.is_empty():
		var last: Dictionary = notes[notes.size()-1]
		lines.append(tr("최근 쪽지 · %s: %s") % [str(last.get("username","")), str(last.get("text",""))])
	return lines

func mail_waiting() -> bool:
	if not app or not app.social or not app.social.data is Dictionary: return false
	var data: Dictionary = app.social.data
	return (data.get("invites") is Array and not data.invites.is_empty()) or (data.get("pending_rewards") is Array and not data.pending_rewards.is_empty())

func use_notice(entry: Dictionary) -> void:
	play("paper", entry.root.global_position)
	var board: Node3D = entry.root
	var wobble := board.create_tween()
	wobble.tween_property(board, "rotation:z", 0.025, 0.08)
	wobble.tween_property(board, "rotation:z", -0.015, 0.1)
	wobble.tween_property(board, "rotation:z", 0.0, 0.1)
	var choices := []
	if app.life and app.life.has_method("open_map"): choices.append([tr("섬 지도 펼치기"), app.life.open_map])
	choices.append([tr("게시판 닫기"), Callable()])
	if app.has_method("open_dialogue"): app.open_dialogue(tr("마을 게시판"), "", notice_lines(), choices)

func notice_lines() -> Array:
	var now := Time.get_datetime_dict_from_system()
	var hour := Daylight.clock_hour()
	var weekday: String = ["일","월","화","수","목","금","토"][int(now.weekday)]
	var lines := [tr("%d월 %d일 %s요일 · %s") % [now.month, now.day, tr(weekday), time_of_day(hour)]]
	var tasks := PackedStringArray()
	if app.life and app.life.has_method("goal_text"):
		for line in String(app.life.goal_text()).split("\n"):
			if not line.strip_edges().is_empty(): tasks.append(line.strip_edges())
	if not tasks.is_empty(): lines.append(tr("오늘의 할 일\n%s") % "\n".join(tasks))
	var farm := farm_line()
	if not farm.is_empty(): lines.append(farm)
	var day_index := int(Time.get_unix_time_from_system()/86400.0)
	lines.append(tr("오늘의 도움말 · %s") % tr(TIPS[day_index%TIPS.size()]))
	return lines

func farm_line() -> String:
	if not app.life or not app.life.state is Dictionary or not app.life.state.get("plots") is Array: return ""
	var now: float = app.life.now() if app.life.has_method("now") else 0.0
	var ripe := 0
	var thirsty := 0
	var empty := 0
	for plot in app.life.state.plots:
		if not plot is Dictionary or plot.is_empty(): empty += 1
		elif not plot.get("watered", false): thirsty += 1
		elif now >= float(plot.get("ready_at", 0)): ripe += 1
	return tr("햇살 텃밭 소식 · 수확 %d칸, 물 줄 곳 %d칸, 빈 밭 %d칸") % [ripe, thirsty, empty]

static func time_of_day(hour: float) -> String:
	if hour < 5.0 or hour >= 21.0: return TranslationServer.translate("별이 총총한 밤")
	if hour < 7.5: return TranslationServer.translate("물안개 낀 새벽")
	if hour < 11.0: return TranslationServer.translate("상쾌한 아침")
	if hour < 14.0: return TranslationServer.translate("햇살 좋은 한낮")
	if hour < 17.5: return TranslationServer.translate("느긋한 오후")
	return TranslationServer.translate("노을 지는 저녁")

func use_well(entry: Dictionary) -> void:
	var root: Node3D = entry.root
	var coin := cyl(self, app.player.position+Vector3(0,1.3,0), 0.06, 0.015, Color("e8c45a"), -1.0, 0.9)
	coin.rotation.x = PI*0.5
	var water := root.global_position+Vector3(0, float(entry.water_y), 0)
	var top := (coin.position+water)*0.5+Vector3(0,1.1,0)
	var tween := coin.create_tween()
	tween.tween_property(coin, "position", top, 0.3).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tween.parallel().tween_property(coin, "rotation:z", TAU*2.0, 0.65)
	tween.tween_property(coin, "position", water, 0.35).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	tween.tween_callback(ripple.bind(water, 0.65, Color(0.85,0.95,1.0,0.7)))
	tween.tween_callback(coin.queue_free)
	play("coin", root.global_position)
	Fx.burst(self, coin.position, "sparkle", 3, Color(1.0,0.9,0.5), 0.05)
	if app.player.has_method("react"): app.player.react("gather")
	var bucket: Node3D = entry.bucket
	var swing := bucket.create_tween()
	swing.tween_property(bucket, "rotation:z", 0.2, 0.3)
	swing.tween_property(bucket, "rotation:z", -0.12, 0.4)
	swing.tween_property(bucket, "rotation:z", 0.0, 0.4)
	entry.tosses = int(entry.get("tosses", 0))+1
	# The wish rises back out of the well as sparkles and a star.
	get_tree().create_timer(0.75).timeout.connect(func():
		if not is_instance_valid(root): return
		Fx.burst(self, water+Vector3(0,0.15,0), "splash", 8, Color(0,0,0,0), 0.15)
		Fx.stream(self, water+Vector3(0,0.3,0), "sparkle", 1.2, 8.0, Color(0,0,0,0), 0.35)
		Fx.bubble(self, root.global_position+Vector3(0,2.1,0), "star")
		Fx.sound(app, "twinkle", root.global_position, 1.0, -4.0))

## An expanding ring on water or ground (coin plop, gong).
func ripple(at: Vector3, radius: float, color: Color, seconds := 0.9) -> void:
	var ring := MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.92
	torus.outer_radius = 1.0
	torus.rings = 32
	torus.ring_segments = 4
	ring.mesh = torus
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	ring.material_override = m
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	ring.position = at+Vector3(0,0.02,0)
	ring.scale = Vector3(0.1,0.3,0.1)
	add_child(ring)
	var tween := ring.create_tween().set_parallel(true)
	tween.tween_property(ring, "scale", Vector3(radius,0.3,radius), seconds).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tween.tween_property(m, "albedo_color:a", 0.0, seconds)
	tween.chain().tween_callback(ring.queue_free)

func use_fountain(entry: Dictionary) -> void:
	var spray: CPUParticles3D = entry.spray
	spray.emitting = true
	play("water", entry.root.global_position)
	if app.player.has_method("react"): app.player.react("eat")
	Fx.sound(app, "drink", entry.root.global_position, 1.0, -4.0)
	Fx.burst(self, app.player.global_position+Vector3(0,1.5,0), "drop", 6, Color(0,0,0,0), 0.2)
	get_tree().create_timer(0.5).timeout.connect(func():
		if is_instance_valid(app) and is_instance_valid(app.player):
			Fx.bubble(self, app.player.global_position+Vector3(0,2.0,0), "drop")
			Fx.burst(self, app.player.global_position+Vector3(0,1.2,0), "sparkle", 5, Color(0.7,0.9,1.0), 0.4))
	await get_tree().create_timer(1.1).timeout
	if is_instance_valid(spray): spray.emitting = false

func use_vane(entry: Dictionary) -> void:
	entry.spin = 3.0
	play("vane", entry.root.global_position)
	var arrow: Node3D = entry.arrow
	# The arrow points where the wind blows from; north is -Z on the island map.
	var pointing: Vector3 = arrow.global_basis.z
	var bearing := fposmod(atan2(pointing.x, -pointing.z), TAU)
	var names := ["북","북동","동","남동","남","남서","서","북서"]
	var index := int(round(bearing/(TAU/8.0)))%8
	entry.wind_from = names[index]
	# The wind shows itself: leaves blow past the vane the way it points from.
	var downwind := Vector3(-pointing.x, 0, -pointing.z)
	Fx.gust(self, entry.root.global_position+Vector3(0,1.6,0)-downwind.normalized()*1.2, downwind, "leaf", 12, 0.5)
	Fx.sound(app, "whoosh", entry.root.global_position, 0.9, -6.0)

func animate_vane(entry: Dictionary, delta: float) -> void:
	var arrow: Node3D = entry.arrow
	entry.wind = float(entry.wind)+delta*0.05*sin(clock*0.11)
	var spin: float = entry.spin
	if spin > 0.0:
		arrow.rotation.y += delta*spin*6.0
		entry.spin = maxf(0.0, spin-delta*1.2)
	else:
		var goal: float = float(entry.wind)+sin(clock*0.7)*0.18-entry.root.rotation.y
		arrow.rotation.y = lerp_angle(arrow.rotation.y, goal, 1.0-exp(-1.5*delta))

func use_feeder(entry: Dictionary) -> void:
	var seeds: Node3D = entry.seeds
	seeds.visible = true
	if app.player.has_method("react"): app.player.react("craft")
	Fx.burst(self, seeds.global_position+Vector3(0,0.25,0), "seed", 12, Color(0,0,0,0), 0.12)
	Fx.squash(seeds, 0.2, 0.3)
	if float(entry.away) > 0.0:
		play("paper", entry.root.global_position, -16.0)
		Fx.burst(self, seeds.global_position+Vector3(0,0.3,0), "sparkle", 4, Color(0,0,0,0), 0.2)
		return
	scatter_birds(entry)
	Fx.burst(self, entry.root.global_position+Vector3(0,1.6,0), "note", 4, Color(0,0,0,0), 0.5)
	Fx.sound(app, "chirp", entry.root.global_position, 1.0, -6.0)

func scatter_birds(entry: Dictionary) -> void:
	entry.away = 9.0
	play("birds", entry.root.global_position)
	for bird in entry.birds:
		var node: Node3D = bird.node
		var out := Vector3(rng.randf_range(-1,1), 0, rng.randf_range(-1,1)).normalized()*rng.randf_range(5,8)
		node.look_at(node.global_position+out, Vector3.UP)
		node.rotate_object_local(Vector3.UP, PI)
		var tween := node.create_tween()
		tween.tween_property(node, "position", node.position+out+Vector3(0,rng.randf_range(3.5,5.5),0), 1.6).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		tween.parallel().tween_property(node, "scale", Vector3.ONE*0.6, 1.6)
		tween.tween_property(node, "visible", false, 0.0)

func animate_birds(entry: Dictionary, delta: float) -> void:
	var away: float = entry.away
	if away > 0.0:
		entry.away = away-delta
		if float(entry.away) <= 0.0:
			# They come back one by one and settle where they were.
			var i := 0
			for bird in entry.birds:
				var node: Node3D = bird.node
				node.visible = true
				node.scale = Vector3.ONE*0.6
				node.position = bird.home+Vector3(rng.randf_range(-3,3),4.0,rng.randf_range(-3,3))
				var tween := node.create_tween()
				tween.tween_interval(i*0.35)
				tween.tween_property(node, "position", bird.home, 1.2).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
				tween.parallel().tween_property(node, "scale", Vector3.ONE, 1.2)
				tween.tween_property(node, "rotation", Vector3(0,rng.randf_range(-PI,PI),0), 0.1)
				i += 1
		return
	# A walker running past startles them.
	if app and is_instance_valid(app.player) and "locomotion_velocity" in app.player:
		if walker_xz().distance_to(entry.at) < 2.2 and app.player.locomotion_velocity.length() > 3.4:
			scatter_birds(entry)
			return
	for bird in entry.birds:
		var node: Node3D = bird.node
		if node.get_tree() == null or not node.visible: continue
		var t: float = clock*2.2+float(bird.phase)
		# Peck now and then, with a little hop.
		var peck := maxf(0.0, sin(t*1.7))
		node.rotation.x = peck*peck*0.7
		node.position.y = float(bird.home.y)+maxf(0.0, sin(t*0.9+1.0)-0.93)*0.6

func use_chimes(entry: Dictionary) -> void:
	entry.ring = 1.0
	play("chimes", entry.root.global_position, -10.0)
	Fx.stream(self, entry.root.global_position+Vector3(0,1.7,0), "note", 1.6, 3.5, Color(0,0,0,0), 0.3)
	Fx.burst(self, entry.root.global_position+Vector3(0,1.8,0), "sparkle", 5, Color(0,0,0,0), 0.3)

func animate_chimes(entry: Dictionary, delta: float) -> void:
	entry.ring = maxf(0.0, float(entry.ring)-delta*0.35)
	var strength: float = 0.05+0.4*float(entry.ring)
	for tube in entry.tubes:
		var node: Node3D = tube.node
		node.rotation.x = sin(clock*2.6+float(tube.phase))*strength
		node.rotation.z = cos(clock*2.1+float(tube.phase)*1.3)*strength*0.7
	# A breeze rings them now and then while someone is near.
	entry.next_ring = float(entry.next_ring)-delta
	if float(entry.next_ring) <= 0.0:
		entry.next_ring = rng.randf_range(7.0, 15.0)
		if walker_xz().distance_to(entry.at) < 10.0:
			entry.ring = maxf(float(entry.ring), 0.45)
			play("chimes", entry.root.global_position, -19.0)

func use_gong(entry: Dictionary) -> void:
	var pivot: Node3D = entry.pivot
	var tween := pivot.create_tween()
	tween.tween_property(pivot, "rotation:x", -0.16, 0.08)
	for k in 5:
		tween.tween_property(pivot, "rotation:x", 0.1*pow(0.6,k)*(1.0 if k%2==0 else -1.0), 0.28)
	tween.tween_property(pivot, "rotation:x", 0.0, 0.3)
	play("gong", entry.root.global_position, -7.0)
	var centre: Vector3 = entry.root.global_transform*Vector3(0,0.05,0.4)
	ripple(centre, 5.0, Color(0.98,0.86,0.55,0.55), 1.4)
	if app.player.has_method("react"): app.player.react("attack")
	ripple(centre, 8.0, Color(0.98,0.86,0.55,0.35), 2.0)
	Fx.burst(self, centre+Vector3(0,1.2,0), "note", 6, Color("f7d26a"), 0.5)
	Fx.burst(self, entry.root.global_position+Vector3(0,0.1,0), "dust", 6, Color(0,0,0,0), 0.6)

func use_photo(entry: Dictionary) -> void:
	play("shutter", entry.root.global_position, -8.0)
	var path: String = await snapshot()
	flash()
	if app.player.has_method("react"): app.player.react("craft")
	Fx.burst(self, entry.root.global_position+Vector3(0,1.4,0), "sparkle", 6, Color(0,0,0,0), 0.6)
	# The picture itself pops up and slides into the corner (saved under user://photos).
	if last_photo != null: Fx.polaroid(app, last_photo)

## Saves the current view without the HUD to user://photos and returns the path.
func snapshot() -> String:
	# Headless runs (tests) draw nothing to save.
	if DisplayServer.get_name() == "headless": return ""
	var hud: CanvasItem = app.ui if "ui" in app and app.ui is CanvasItem else null
	var shown := hud.visible if hud else false
	if hud: hud.visible = false
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var texture := get_viewport().get_texture()
	var image: Image = texture.get_image() if texture else null
	if hud and is_instance_valid(hud): hud.visible = shown
	if image == null or image.is_empty(): return ""
	last_photo = image
	DirAccess.make_dir_recursive_absolute("user://photos")
	var stamp := Time.get_datetime_string_from_system().replace(":","").replace("-","").replace("T","_")
	var path := "user://photos/island_%s.png" % stamp
	return path if image.save_png(path) == OK else ""

func flash() -> void:
	# Settings: reduced motion / fewer flashes skips the white camera flash.
	if not preload("res://scripts/game_settings.gd").flashes_allowed(): return
	if not is_instance_valid(flash_layer):
		flash_layer = CanvasLayer.new()
		flash_layer.layer = 60
		add_child(flash_layer)
	var white := ColorRect.new()
	white.color = Color(1,1,1,0.85)
	white.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	white.mouse_filter = Control.MOUSE_FILTER_IGNORE
	flash_layer.add_child(white)
	var tween := white.create_tween()
	tween.tween_property(white, "color:a", 0.0, 0.45)
	tween.tween_callback(white.queue_free)

func use_lost(entry: Dictionary) -> void:
	var lid: Node3D = entry.lid
	if not entry.open:
		entry.open = true
		play("box", entry.root.global_position)
		lid.create_tween().tween_property(lid, "rotation:x", -1.25, 0.35).set_trans(Tween.TRANS_BACK)
	var day_index := int(Time.get_unix_time_from_system()/86400.0)
	var lines := [tr("분실물 상자예요. 마을에서 주운 물건을 모아 두는 곳이에요.")]
	var picks := PackedStringArray()
	for k in 3: picks.append("· "+tr(LOST_ITEMS[(day_index*3+k*7)%LOST_ITEMS.size()]))
	lines.append(tr("오늘 들어온 물건\n%s") % "\n".join(picks))
	lines.append(tr("주인을 보면 알려 주세요. 물건은 상자 안에 그대로 둘게요."))
	if app.has_method("open_dialogue"): app.open_dialogue(tr("분실물 상자"), "", lines, [[tr("뚜껑 닫기"), Callable()]])

func close_lid_when_away(entry: Dictionary) -> void:
	if not entry.open or walker_xz().distance_to(entry.at) < float(entry.radius)+2.2: return
	entry.open = false
	var lid: Node3D = entry.lid
	lid.create_tween().tween_property(lid, "rotation:x", 0.0, 0.3)
	play("box", entry.root.global_position, -14.0)

# ------------------------------------------------------------------ sitting
func use_swing(entry: Dictionary) -> void: sit(entry, "creak_soft")
func use_rocker(entry: Dictionary) -> void: sit(entry, "wood_creak")
func use_hammock(entry: Dictionary) -> void: sit(entry, "wood_creak")

## Seats the walker on a swing, rocking chair or hammock until they move or press E.
func sit(entry: Dictionary, creak: String) -> void:
	if not seat.is_empty() or not view.is_empty(): return
	var player: Node3D = app.player
	var pose: SeatPose = null
	if "hand_skeleton" in player and is_instance_valid(player.hand_skeleton):
		pose = SeatPose.new()
		pose.player = player
		pose.lying = entry.kind == "hammock"
		player.hand_skeleton.add_child(pose)
	seat = {"entry":entry,"creak":creak,"time":0.0,"pose":pose,"hip":hip_height(player),"next_creak":0.6,
		"was_visual_only":player.visual_only}
	player.visual_only = true
	player.velocity = Vector3.ZERO
	var front: Vector2 = entry.front
	player.facing = Vector3(front.x, 0, front.y)
	if "action_facing" in player: player.action_facing = player.facing
	var mood: String = {"swing":"note","rocker":"heart","hammock":"zz"}[entry.kind]
	get_tree().create_timer(0.6).timeout.connect(func():
		if not seat.is_empty() and is_instance_valid(player): Fx.bubble(self, player.global_position+Vector3(0,1.9,0), mood))
	update_seat(0.0)

## Height of the hips above the walker's feet (for lowering the body onto a seat).
func hip_height(player: Node3D) -> float:
	if "hand_skeleton" in player and is_instance_valid(player.hand_skeleton):
		var skeleton: Skeleton3D = player.hand_skeleton
		var hip := skeleton.find_bone("L_Thigh")
		if hip >= 0: return (skeleton.global_transform*skeleton.get_bone_global_rest(hip).origin).y-player.global_position.y
	return 0.85

func update_seat(delta: float) -> void:
	var entry: Dictionary = seat.entry
	var player: Node3D = app.player
	if not is_instance_valid(player) or ("screen" in app and app.screen != "village"):
		stand_up(true)
		return
	seat.time = float(seat.time)+delta
	var t: float = seat.time
	if t > 0.35 and walker_moving():
		stand_up()
		return
	var pivot: Node3D = entry.pivot
	var amount := minf(t/1.5, 1.0)
	match entry.kind:
		"swing": pivot.rotation.x = sin(t*2.2)*0.38*amount
		"rocker": pivot.rotation.x = sin(t*1.9)*0.09*amount
		"hammock": pivot.rotation.z = 0.0; pivot.rotation.x = sin(t*1.1)*0.12*amount
	var seat_world: Vector3 = pivot.global_transform*Vector3(entry.seat_local)
	var axis: Vector3 = entry.root.global_basis.x.normalized()
	var tilt := Basis(axis, pivot.rotation.x)
	# The hips rest on the seat, a little behind its centre; the body tilts with it.
	var back: Vector3 = entry.root.global_basis.z.normalized()*-0.08
	player.global_basis = tilt
	player.global_position = seat_world+back-tilt*Vector3(0, float(seat.hip)-0.04, 0)
	seat.next_creak = float(seat.next_creak)-delta
	if float(seat.next_creak) <= 0.0:
		seat.next_creak = {"swing":PI/2.2,"rocker":PI/1.9,"hammock":PI/1.1}[entry.kind]
		play(String(seat.creak), entry.root.global_position, -17.0)

func stand_up(quiet := false) -> void:
	if seat.is_empty(): return
	var entry: Dictionary = seat.entry
	var pose: SeatPose = seat.pose
	var restore: bool = seat.was_visual_only
	seat = {}
	if is_instance_valid(pose): pose.queue_free()
	if is_instance_valid(entry.get("pivot")):
		var pivot: Node3D = entry.pivot
		pivot.create_tween().tween_property(pivot, "rotation:x", 0.0, 0.8).set_trans(Tween.TRANS_SINE)
	if not is_instance_valid(app) or not is_instance_valid(app.player): return
	var player: Node3D = app.player
	player.global_basis = Basis.IDENTITY
	player.visual_only = restore
	player.velocity = Vector3.ZERO
	player.global_position = Vector3(entry.stand)+Vector3(0,0.05,0)
	if not quiet: play("paper", entry.root.global_position, -24.0)

## Bends the legs into a seated pose on top of the walker's own animation.
class SeatPose extends SkeletonModifier3D:
	var player: Node3D
	var lying := false
	var amount := 0.0

	func turn(skeleton: Skeleton3D, bone: String, angles: Vector3, body: Basis) -> void:
		var index := skeleton.find_bone(bone)
		if index < 0: return
		for component in 3:
			if absf(angles[component]) < 0.0001: continue
			var axis := Vector3.ZERO
			axis[component] = 1.0
			var world_axis := body*axis
			var bone_world := skeleton.global_basis*skeleton.get_bone_global_pose(index).basis
			var local_axis := (bone_world.inverse()*world_axis).normalized()
			skeleton.set_bone_pose_rotation(index, skeleton.get_bone_pose_rotation(index)*Quaternion(local_axis, angles[component]))

	func _process_modification_with_delta(delta: float) -> void:
		amount = minf(1.0, amount+delta*3.0)
		var skeleton := get_skeleton()
		if skeleton == null or not is_instance_valid(player): return
		var body: Basis = player.visual.global_basis.orthonormalized()
		var hip := (1.2 if lying else 1.45)*amount
		var knee := (-1.0 if lying else -1.45)*amount
		for side in ["L","R"]:
			turn(skeleton, side+"_Thigh", Vector3(hip,0,0), body)
			turn(skeleton, side+"_Calf", Vector3(knee,0,0), body)
		turn(skeleton, "Spine02", Vector3((-0.25 if lying else -0.06)*amount,0,0), body)

# ------------------------------------------------------------------ telescope view
func use_telescope(entry: Dictionary) -> void:
	if not seat.is_empty() or not view.is_empty() or not "camera" in app or not is_instance_valid(app.camera): return
	var targets: Array = entry.spec.targets
	var index: int = entry.target
	entry.target = (index+1)%targets.size()
	aim_telescope(entry, index)
	play("brass", entry.root.global_position)
	var goal: Vector2 = targets[index][1]
	var focus_ground := ray_down(goal, 1|2)
	var focus := Vector3(goal.x, focus_ground.position.y if not focus_ground.is_empty() else 2.3, goal.y)+Profile.CAMERA_FOCUS_OFFSET
	view = {"entry":entry,"focus":focus,"weight":0.0,"leaving":false,"size":app.camera.size,"time":0.0,
		"was_visual_only":app.player.visual_only}
	app.player.visual_only = true
	app.player.velocity = Vector3.ZERO
	# The landmark's name floats over it once the view arrives.
	var landmark := Vector3(focus.x, focus.y-Profile.CAMERA_FOCUS_OFFSET.y, focus.z)
	var name_of: String = tr(targets[index][0])
	get_tree().create_timer(0.8).timeout.connect(func():
		if not view.is_empty() and is_instance_valid(app): Fx.title(app, landmark, name_of, Color("f5e5b7")))

func update_view(delta: float) -> void:
	var camera: Camera3D = app.camera
	if not is_instance_valid(camera) or not is_instance_valid(app.player) or ("screen" in app and app.screen != "village"):
		end_view(true)
		return
	view.time = float(view.time)+delta
	if not view.leaving and float(view.time) > 0.4 and walker_moving(): end_view()
	var weight: float = view.weight
	weight = move_toward(weight, 0.0 if view.leaving else 1.0, delta/0.9)
	view.weight = weight
	var eased := smoothstep(0.0, 1.0, weight)
	# main.gd has already placed the camera on the walker this frame; blend from there.
	var walker_focus: Vector3 = camera.position-Profile.CAMERA_OFFSET
	var focus: Vector3 = walker_focus.lerp(view.focus, eased)
	camera.position = focus+Profile.CAMERA_OFFSET
	camera.look_at(focus)
	camera.size = lerpf(float(view.size), maxf(float(view.size), 15.0), eased)
	if view.leaving and weight <= 0.0:
		camera.size = float(view.size)
		app.player.visual_only = bool(view.was_visual_only)
		view = {}

func end_view(immediate := false) -> void:
	if view.is_empty(): return
	if immediate:
		if is_instance_valid(app) and "camera" in app and is_instance_valid(app.camera): app.camera.size = float(view.size)
		if is_instance_valid(app) and is_instance_valid(app.player): app.player.visual_only = bool(view.was_visual_only)
		view = {}
		return
	view.leaving = true
