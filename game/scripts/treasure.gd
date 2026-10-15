extends Node3D
## Treasure chests (보물상자): one in the player's own home and ten around the five islands, two per
## island, each paying a few starseeds once per account. server/treasure.py keeps which are open
## and pays them through the ledger; the ids are the same there and here (HOME, FIELD).
##
## Village: a module of main.gd (VILLAGE_MODULES): setup(app), closest(at), interact(entry),
## leave(). Each chest is placed at runtime at its authored spot, nudged at most RING_MAX metres
## by field_objects.gd's placement rules (off the roads, clear of doors, places, villagers, props,
## water, buildings and the field objects), its lock to the camera (a little toward its road) and
## tilted to the ground. Shown once /v1/me says which are open (app.me.chests); hidden while
## visiting a friend's village.
## Home: studio.gd show_story() calls enter_room(room); use_decor()/update_hint() ask use_home()/
## home_chip() first, like the story letter (story_home.gd). The chest stands against the back
## wall of the ground floor, between the stove and the wardrobe, facing the front door.
##
## Unopened: the gold trim breathes softly, a faint additive halo (brighter at night) and a few
## sparkles now and then near the walker. The trim and halo materials are shared, so the whole glow
## costs two property writes a frame; nothing else runs per frame. E: the lid rattles while the
## server answers, then swings open with a warm light, a beam, sparkles and coins; "+N" rises and
## the stars fly into the starseed counter (quests.gd reward_fly in the village; in the home a
## small counter slides in under the room's name). Opened chests stay open (lid up, no glow, no
## prompt), also after signing in again.
const Fx := preload("res://scripts/fx.gd")
const RpgUi := preload("res://scripts/rpg_ui.gd")
const Quests := preload("res://scripts/quests.gd")
const Daylight := preload("res://scripts/daylight.gd")
const Fields := preload("res://scripts/field_objects.gd")
const LoadPace := preload("res://scripts/load_pace.gd")
const SELF := "res://scripts/treasure.gd"
const STAR_ICON := "res://assets/starseed.svg"
const SFX := "res://assets/sfx/field/%s.wav"
const META := "treasure_opened"

## The home's chest: against the back wall of the ground floor (interiors.gd 10_red_house/0), x
## tried in this order (a piece the player set down may stand at the first).
const HOME := {"id":"home", "x":[-0.15, 0.95, -1.15]}
## Field chests: id (server/treasure.py STARS), the authored spot and fallback spots (x, z).
const FIELD := [
	# 물결빛 광장: out on the little north cape; between the trees behind my own house.
	{"id":"square_cape", "at":Vector2(-6.0, -6.0)},
	{"id":"square_backyard", "at":Vector2(-61.5, 9.0)},
	# 풍차 들판: past the bushes by 모카's terrace (the demo opens it while a craft runs); by the windmill.
	{"id":"fields_cafe", "at":Vector2(-53.0, -27.0)},
	{"id":"fields_windmill", "at":Vector2(-11.0, -42.5)},
	# 정원 언덕: among the reeds on the observatory pond's far bank; beside the gazebo.
	{"id":"garden_pond", "at":Vector2(50.0, -52.5)},
	{"id":"garden_gazebo", "at":Vector2(65.5, -44.0)},
	# 캠프 초원: between the tents; behind the blue cottage.
	{"id":"camp_tents", "at":Vector2(50.0, 45.5)},
	{"id":"camp_cottage", "at":Vector2(75.0, 49.0)},
	# 등대섬: on the rocks behind the lighthouse; out on the north tip where the long bridge lands.
	{"id":"lighthouse_rocks", "at":Vector2(14.0, 80.5)},
	{"id":"lighthouse_cape", "at":Vector2(5.0, 70.0)},
]
## Spots chests keep clear of beyond field_objects.gd's rules: the café terrace's gift slot and
## 모카's place on it (story.gd), centre and metres.
const KEEP_CLEAR := [[Vector2(-60.2, -27.6), 2.6], [Vector2(-59.6, -29.9), 2.4]]
## Map seats (town.gd props) keep this far, so E near a seat always sits (its reach plus the chest's).
const SEATS := ["26_bench", "25_picnic_table", "32_cafe_chair", "29_beach_lounger"]
const SEAT_CLEAR := 3.8

## Chest size (m): width (x), depth (z), body height; the lid is an arch over the depth, LID_RISE high.
const WIDTH := 0.96
const DEPTH := 0.62
const BODY := 0.46
const LID_RISE := 0.3
## Placement footprint, E reach from the centre and how far a spot may move (m).
const RADIUS := 0.5
const REACH := 1.65
const RING_MAX := 2.0
## How far the lid swings back: in the field, and in the home against the wall.
const OPEN_ANGLE := 1.95
const HOME_OPEN_ANGLE := 1.35
## Room furniture's distance from the back wall (interiors.gd back()) plus the open lid's reach behind its hinge.
const HOME_WALL_GAP := 0.07+0.24

static var meshes := {}
static var materials := {}

var app: Node
## The home (studio.gd) when this node is the home's chest; null in the village.
var room: Node
## Set by harnesses without the field module in app.modules (tests/treasure_spots.gd).
var fields_module: Node
## Set by harnesses to draw the chests without a server (every chest closed).
var always_shown := false
## One entry per placed chest: {id, root, lid, heap, halo, trims, at (Vector2), state, record}.
var chests: Array = []
## Field ids that found no spot (reported by the harness).
var skipped: Array = []
var shown := false
var poll := 0.0
var sparkle_wait := 1.2
var night := 0.0
var night_wait := 0.0
var voice: AudioStreamPlayer

# ------------------------------------------------------------------ shared state

static func t(text: String) -> String:
	return TranslationServer.translate(text)

## Chests this login opened (Engine metadata: it outlives rooms and village rebuilds).
static func remembered(token: String) -> Array:
	var kept = Engine.get_meta(META, {}) if Engine.has_meta(META) else {}
	return kept.get("ids", []) if kept is Dictionary and str(kept.get("token", "")) == token else []

static func remember(token: String, ids: Array) -> void:
	var known := remembered(token).duplicate()
	for id in ids:
		if not str(id) in known: known.append(str(id))
	Engine.set_meta(META, {"token":token, "ids":known})

## E on a chest: the server opens it (the same request again if the reply was lost on the way).
static func request_open(api: Node, id: String) -> Dictionary:
	var body: Dictionary = api.mutation()
	var reply: Dictionary = await api.post("/v1/chests/%s/open" % id, body)
	if not reply.get("ok", false) and str(reply.get("error", "")) == "connection_failed" and is_instance_valid(api):
		reply = await api.post("/v1/chests/%s/open" % id, body)
	return reply

## The words for a refusal (the codes are server/treasure.py's).
static func refusal(code: String) -> String:
	match code:
		"chest_already_open": return t("이미 열어 본 보물상자예요")
		"chest_own_village_only": return t("친구 마을의 보물상자는 열 수 없어요")
		"chest_too_fast": return t("잠시 뒤에 다시 열어 보세요")
	return t("보물상자가 열리지 않았어요. 잠시 뒤 다시 해 보세요.")

# ------------------------------------------------------------------ the home (studio.gd hooks)

## studio.gd show_story(): the chest in the owner's own home (nothing in other rooms or on a visit).
static func enter_room(owner_room: Node) -> void:
	if not is_instance_valid(owner_room): return
	var old := owner_room.get_node_or_null("TreasureHome")
	if old:
		old.name = "TreasureHomeOld"
		old.queue_free()
	if str(owner_room.get("room")) != "home" or bool(owner_room.get("public_room")) or bool(owner_room.get("visiting")): return
	if not str(owner_room.get("visit_host")).is_empty() or str(owner_room.api.token).is_empty(): return
	var node: Node3D = load(SELF).new()
	node.name = "TreasureHome"
	owner_room.add_child(node)
	node.setup_home(owner_room)

static func home_of(owner_room: Node) -> Node:
	return owner_room.get_node_or_null("TreasureHome") if is_instance_valid(owner_room) else null

## studio.gd use_decor(): true when E was the home chest's.
static func use_home(owner_room: Node, record: Dictionary) -> bool:
	var home := home_of(owner_room)
	return home != null and home.use(record)

## studio.gd update_hint(): the key chip's words for the home chest ("" for anything else).
static func home_chip(owner_room: Node, record: Dictionary) -> String:
	var home := home_of(owner_room)
	return home.chip(record) if home != null else ""

func setup_home(owner_room: Node) -> void:
	room = owner_room
	add_voice()
	var token := str(room.api.token)
	var known := remembered(token)
	var asked := false
	# Known this login: drawn at once (no pop after the room appears); else after the server answers.
	if not Engine.has_meta(META) or str(Engine.get_meta(META).get("token", "")) != token:
		asked = true
		await refresh_home()
		if not is_instance_valid(room) or not is_inside_tree(): return
		known = remembered(token)
	place_home("home" in known)
	if not asked: refresh_home()

## The server's word on the home chest (another device may have opened it).
func refresh_home() -> void:
	var reply: Dictionary = await room.api.request("/v1/chests")
	if not is_instance_valid(room) or not reply.get("ok", false) or not reply.data.get("chests") is Dictionary: return
	remember(str(room.api.token), reply.data.chests.get("opened", []))
	if not chests.is_empty() and chests[0].state == "closed" and "home" in reply.data.chests.get("opened", []): set_open(chests[0], false)

func place_home(open: bool) -> void:
	if room.floor_roots.is_empty() or room.decor_by_floor.is_empty(): return
	var size: Vector2 = Vector2(room.room_spec.get("size", Vector2(10, 10)))
	var z := -size.y*0.5+HOME_WALL_GAP+DEPTH*0.5
	var x: float = HOME.x[0]
	for option in HOME.x:
		if home_spot_free(Vector2(option, z)):
			x = option
			break
	var root := build_chest(room.floor_roots[0], "home")
	root.position = Vector3(x, 0.0, z)
	var chest: Dictionary = chests.back()
	chest.at = Vector2(x, z)
	chest.record = {"kind":"treasure_chest", "node":root, "center":Vector3(x, 0, z), "yaw":0.0, "mounted":false, "solid":true,
		"interactive":true, "glb":false, "size":Vector3(WIDTH, BODY+LID_RISE, DEPTH), "half":Vector2(WIDTH*0.5+0.02, DEPTH*0.5+0.02),
		"world_half":Vector2(WIDTH*0.5+0.02, DEPTH*0.5+0.02), "top":BODY+LID_RISE, "floor":0}
	room.decor_by_floor[0].append(chest.record)
	if room.floor_index == 0: room.decor = room.decor_by_floor[0]
	if open: set_open(chest, false)
	shown = true
	set_process(true)

## No piece the player set down (ground floor) overlaps the chest at this spot.
func home_spot_free(at: Vector2) -> bool:
	for id in room.placed:
		var item: Node3D = room.placed[id]
		if not is_instance_valid(item): continue
		var size: Vector3 = item.get_meta("size", Vector3(1.6, 1.6, 1.6))
		var half: float = maxf(size.x, size.z)*0.5
		if absf(item.position.x-at.x) < half+WIDTH*0.5 and absf(item.position.z-at.y) < half+DEPTH*0.5: return false
	return true

func use(target: Dictionary) -> bool:
	if chests.is_empty() or target.is_empty() or target != chests[0].get("record"): return false
	if chests[0].state == "closed": open_chest(chests[0])
	return true

func chip(target: Dictionary) -> String:
	if chests.is_empty() or target.is_empty() or target != chests[0].get("record") or chests[0].state != "closed": return ""
	return tr("보물상자 열기")

func _exit_tree() -> void:
	if room == null: return
	for chest in chests:
		if is_instance_valid(chest.root): chest.root.queue_free()
		if is_instance_valid(room) and not room.decor_by_floor.is_empty() and chest.has("record"): room.decor_by_floor[0].erase(chest.record)

# ------------------------------------------------------------------ the village (module contract)

func setup(main: Node) -> void:
	app = main
	name = "Treasure"
	add_voice()
	# The kept map reaches the physics space at the next physics step (field_objects.gd build()).
	await get_tree().physics_frame
	var fields := field_module()
	for spec in FIELD:
		await LoadPace.step("treasure chest")
		var spot := find_spot(spec, fields)
		if spot.is_empty():
			skipped.append(spec.id)
			continue
		var root := build_chest(self, str(spec.id))
		root.position = Vector3(spot.at.x, spot.ground, spot.at.y)
		root.rotation = Vector3(spot.pitch, atan2(spot.front.x, spot.front.y), spot.roll)
		chests.back().at = spot.at
	visible = false
	sync()

func leave() -> void:
	for chest in chests: chest.state = "gone" if chest.state == "opening" else chest.state

func closest(at: Vector3) -> Dictionary:
	if not shown: return {}
	var best := {}
	var p := Vector2(at.x, at.z)
	for chest in chests:
		if chest.state != "closed": continue
		var gap: float = p.distance_to(chest.at)
		if gap < REACH and (best.is_empty() or gap < float(best.gap)):
			best = {"prompt":tr("보물상자 열기"), "distance":maxf(gap-RADIUS, 0.0), "id":chest.id, "gap":gap}
	return best

func interact(entry: Dictionary) -> void:
	var chest := chest_of(str(entry.get("id", "")))
	if not chest.is_empty() and chest.state == "closed": open_chest(chest)

func chest_of(id: String) -> Dictionary:
	for chest in chests:
		if chest.id == id: return chest
	return {}

## The field objects module (field_objects.gd) whose placement rules chests follow.
func field_module() -> Node:
	if is_instance_valid(fields_module): return fields_module
	if is_instance_valid(app) and app.get("modules") is Array:
		for module in app.modules:
			if is_instance_valid(module) and module.has_method("blocker") and module.has_method("spot_ground"): return module
	return null

## Shown once the server said which chests are open, and not while visiting a friend's village.
func wanted() -> bool:
	if always_shown: return true
	if not is_instance_valid(app) or not app.get("api") or str(app.api.token).is_empty(): return false
	if is_instance_valid(app.get("social")) and app.social.has_method("visiting") and app.social.visiting(): return false
	return app.me is Dictionary and app.me.get("chests") is Dictionary

## Follows /v1/me (polled by main.gd) and this login's own opens, twice a second.
func sync() -> void:
	var now := wanted()
	if now != shown:
		shown = now
		visible = now
	if not shown or always_shown: return
	var token := str(app.api.token)
	var opened: Array = app.me.chests.get("opened", [])
	remember(token, opened)
	var known := remembered(token)
	for chest in chests:
		if chest.state == "closed" and chest.id in known: set_open(chest, false)

# ------------------------------------------------------------------ placement

## The authored spot, else the nearest good one within RING_MAX: flat dry ground clear of what
## field_objects.gd keeps clear, the KEEP_CLEAR spots and the other chests.
func find_spot(spec: Dictionary, fields: Node) -> Dictionary:
	for origin: Vector2 in [spec.at]+spec.get("alts", []):
		for ring: float in [0.0, 0.5, 1.0, 1.5, 2.0]:
			if ring > RING_MAX: break
			var steps := 1 if ring == 0.0 else 10
			for k in steps:
				var angle := TAU*float(k)/steps+ring*0.7
				var p := origin+Vector2(cos(angle), sin(angle))*ring
				var why := spot_problem(p, fields)
				if not why.is_empty(): continue
				var front := facing(p)
				if spec.has("face"): front = Vector2(spec.face).normalized()
				var fit := ground_fit(p, front)
				if fit.is_empty(): continue
				fit["at"] = p
				fit["front"] = front
				return fit
	return {}

## Local +Z (the lock and the lid's opening side) faces the camera (south), turned up to ~30°
## toward the chest's road so it reads from the path too.
static func facing(p: Vector2) -> Vector2:
	var toward := (Fields.road_centre(p)-p).normalized()
	return Vector2(clampf(toward.x, -0.6, 0.6), 1.0).normalized()

## Why a chest cannot stand at p ("" when it can).
func spot_problem(p: Vector2, fields: Node) -> String:
	for keep in KEEP_CLEAR:
		if p.distance_to(keep[0]) < float(keep[1])+RADIUS: return "kept clear"
	for chest in chests:
		if p.distance_to(chest.at) < 3.0: return "chest "+str(chest.id)
	if is_instance_valid(app) and is_instance_valid(app.get("town")) and "props" in app.town:
		for prop in app.town.props:
			if str(prop.id) in SEATS and p.distance_to(prop.at) < SEAT_CLEAR: return "seat "+str(prop.id)
	if fields == null: return "" if not is_nan(ray_height(p)) else "no ground"
	return fields.blocker(p, RADIUS, fields.spot_ground(p, RADIUS))

## Ground height under the chest's four corners and centre: the chest sits on their mean, tilted
## with the ground (at most ~7°); {} where the ground is too uneven.
func ground_fit(p: Vector2, front: Vector2) -> Dictionary:
	var side := Vector2(front.y, -front.x)
	var h := {}
	for key in ["c", "f", "b", "l", "r"]:
		var q: Vector2 = p+{"c":Vector2.ZERO, "f":front*DEPTH*0.5, "b":-front*DEPTH*0.5, "l":-side*WIDTH*0.5, "r":side*WIDTH*0.5}[key]
		h[key] = ray_height(q)
		if is_nan(h[key]): return {}
	var values: Array = h.values()
	if float(values.max())-float(values.min()) > 0.16: return {}
	return {"ground":(float(h.c)+float(h.f)+float(h.b)+float(h.l)+float(h.r))/5.0,
		"pitch":clampf(-atan2(float(h.f)-float(h.b), DEPTH), -0.12, 0.12), "roll":clampf(atan2(float(h.r)-float(h.l), WIDTH), -0.12, 0.12)}

func ray_height(p: Vector2) -> float:
	var hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x, 60, p.y), Vector3(p.x, -20, p.y), 1))
	return hit.position.y if not hit.is_empty() and hit.position.y > 1.0 else NAN

# ------------------------------------------------------------------ the chest

static func material(key: String) -> StandardMaterial3D:
	if materials.has(key): return materials[key]
	var m := StandardMaterial3D.new()
	match key:
		"wood":
			m.albedo_color = Color("7c4a22")
			m.roughness = 0.85
		"lid":
			m.albedo_color = Color("935d2d")
			m.roughness = 0.8
		"dark":
			m.albedo_color = Color("4a2e17")
			m.roughness = 0.9
		"inside":
			m.albedo_color = Color("22150b")
			m.roughness = 1.0
		"gold", "gold_dull":
			# Barely metallic: it reads as gold under any sky (a metal mirrors a dark environment).
			m.albedo_color = Color("f5c445") if key == "gold" else Color("c39b48")
			m.metallic = 0.3
			m.roughness = 0.42 if key == "gold" else 0.55
			if key == "gold":
				m.emission_enabled = true
				m.emission = Color("ffc84a")
				m.emission_energy_multiplier = 0.3
		"heap":
			m.albedo_color = Color("ffd24a")
			m.metallic = 0.55
			m.roughness = 0.3
			m.emission_enabled = true
			m.emission = Color("ffbf3a")
			m.emission_energy_multiplier = 0.9
		"halo":
			m.albedo_texture = Fx.tex("soft")
			m.albedo_color = Color(1.0, 0.82, 0.45, 0.2)
			m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
			m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	materials[key] = m
	return m

## One half-pipe arch over z in [0, 2*radius], rise high, width wide (x centred), closed with its
## end caps and a flat bottom; flat-shaded so its faces read as planks.
static func arch(width: float, radius: float, rise: float, segments := 7) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var profile: Array[Vector2] = []
	for i in segments+1:
		var a := PI*float(i)/segments
		profile.append(Vector2(radius-cos(a)*radius, sin(a)*rise))
	var hx := width*0.5
	for i in segments:
		var a: Vector2 = profile[i]
		var b: Vector2 = profile[i+1]
		var d := b-a
		var n := Vector3(0, d.x, -d.y).normalized()
		quad(st, Vector3(-hx, a.y, a.x), Vector3(hx, a.y, a.x), Vector3(hx, b.y, b.x), Vector3(-hx, b.y, b.x), n)
	for sx in [-1.0, 1.0]:
		var centre := Vector3(sx*hx, 0, radius)
		for i in segments:
			tri(st, centre, Vector3(sx*hx, profile[i].y, profile[i].x), Vector3(sx*hx, profile[i+1].y, profile[i+1].x), Vector3(sx, 0, 0))
	quad(st, Vector3(-hx, 0, 0), Vector3(hx, 0, 0), Vector3(hx, 0, radius*2.0), Vector3(-hx, 0, radius*2.0), Vector3.DOWN)
	# Indexed like the primitive meshes it is merged with (SurfaceTool.append_from keeps one index list).
	st.index()
	return st.commit()

## A triangle facing n (Godot's front faces wind clockwise seen from the front).
static func tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, n: Vector3) -> void:
	if (b-a).cross(c-a).dot(n) > 0.0:
		var swap := b
		b = c
		c = swap
	for v in [a, b, c]:
		st.set_normal(n)
		st.add_vertex(v)

static func quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, n: Vector3) -> void:
	tri(st, a, b, c, n)
	tri(st, a, c, d, n)

static func box(size: Vector3) -> BoxMesh:
	var mesh := BoxMesh.new()
	mesh.size = size
	return mesh

## The chest's parts, merged once per material and shared by every chest.
static func mesh(key: String) -> Mesh:
	if meshes.has(key): return meshes[key]
	var parts: Array = []
	var hw := WIDTH*0.5
	var hd := DEPTH*0.5
	match key:
		"body":
			parts.append([box(Vector3(WIDTH, BODY-0.06, DEPTH)), Vector3(0, 0.06+(BODY-0.06)*0.5, 0)])
		"dark":
			# The plinth and two plank grooves round the body.
			parts.append([box(Vector3(WIDTH+0.06, 0.07, DEPTH+0.06)), Vector3(0, 0.035, 0)])
			for f in [0.36, 0.7]:
				parts.append([box(Vector3(WIDTH+0.004, 0.012, DEPTH+0.004)), Vector3(0, 0.06+(BODY-0.06)*f, 0)])
		"gold":
			for x in [-1.0, 1.0]:
				for z in [-1.0, 1.0]:
					parts.append([box(Vector3(0.06, BODY-0.03, 0.06)), Vector3(x*(hw-0.018), 0.04+(BODY-0.03)*0.5, z*(hd-0.018))])
			# Bands down the front and back, in line with the lid's.
			for x in [-0.3, 0.3]:
				for z in [-1.0, 1.0]:
					parts.append([box(Vector3(0.075, BODY-0.07, 0.014)), Vector3(x, 0.07+(BODY-0.07)*0.5, z*(hd+0.005))])
			for z in [-1.0, 1.0]:
				parts.append([box(Vector3(WIDTH+0.014, 0.036, 0.014)), Vector3(0, BODY-0.018, z*(hd+0.004))])
			for x in [-1.0, 1.0]:
				parts.append([box(Vector3(0.014, 0.036, DEPTH+0.014)), Vector3(x*(hw+0.004), BODY-0.018, 0)])
			parts.append([box(Vector3(0.17, 0.17, 0.024)), Vector3(0, BODY-0.1, hd+0.012)])
		"inside":
			parts.append([box(Vector3(WIDTH-0.08, 0.004, DEPTH-0.08)), Vector3(0, BODY+0.001, 0)])
			parts.append([box(Vector3(0.026, 0.05, 0.006)), Vector3(0, BODY-0.115, hd+0.026)])
			var hole := SphereMesh.new()
			hole.radius = 0.019
			hole.height = 0.014
			hole.radial_segments = 10
			hole.rings = 4
			parts.append([hole, Vector3(0, BODY-0.085, hd+0.025)])
		"heap":
			var pile := SphereMesh.new()
			pile.radius = 0.5
			pile.height = 1.0
			pile.radial_segments = 14
			pile.rings = 7
			parts.append([pile, Transform3D(Basis.from_scale(Vector3(WIDTH-0.16, 0.26, DEPTH-0.14)), Vector3(0, BODY-0.05, 0))])
			var coin := CylinderMesh.new()
			coin.top_radius = 0.04
			coin.bottom_radius = 0.04
			coin.height = 0.012
			coin.radial_segments = 10
			coin.rings = 1
			for c in [[-0.24, 0.06, 0.4], [0.07, -0.1, -0.5], [0.26, 0.07, 0.8], [-0.05, 0.12, -0.2], [0.14, -0.02, 0.3]]:
				var turn := Basis(Vector3.RIGHT, float(c[2])).rotated(Vector3.UP, float(c[0])*9.0)
				parts.append([coin, Transform3D(turn, Vector3(float(c[0]), BODY+0.075-absf(float(c[0]))*0.14, float(c[1])))])
		"lid":
			parts.append([arch(WIDTH+0.024, hd+0.012, LID_RISE), Vector3(0, 0, -0.012)])
		"lid_gold":
			for x in [-0.3, 0.3]:
				parts.append([arch(0.08, hd+0.03, LID_RISE+0.02), Vector3(x, 0, -0.03)])
			for z in [-0.02, DEPTH+0.02]:
				parts.append([box(Vector3(WIDTH+0.04, 0.04, 0.016)), Vector3(0, 0.02, z)])
			parts.append([box(Vector3(0.09, 0.12, 0.02)), Vector3(0, -0.04, DEPTH+0.036)])
	var tool := SurfaceTool.new()
	for part in parts:
		var place: Transform3D = part[1] if part[1] is Transform3D else Transform3D(Basis.IDENTITY, part[1])
		tool.append_from(part[0], 0, place)
	meshes[key] = tool.commit()
	return meshes[key]

func part(parent: Node3D, key: String, look: String, shadow := true) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.mesh = mesh(key)
	node.material_override = material(look)
	if not shadow: node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(node)
	return node

## A closed chest under parent: body, lid on its back hinge, the gold heap inside, the halo and a
## solid footprint on the props layer (field_objects.gd PROP_LAYER) so walkers go round it.
func build_chest(parent: Node3D, id: String) -> Node3D:
	var root := Node3D.new()
	root.name = "Chest_"+id
	parent.add_child(root)
	part(root, "body", "wood")
	part(root, "dark", "dark")
	var trims: Array = [part(root, "gold", "gold", false)]
	part(root, "inside", "inside", false)
	var heap := part(root, "heap", "heap", false)
	var lid := Node3D.new()
	lid.name = "Lid"
	lid.position = Vector3(0, BODY, -DEPTH*0.5)
	root.add_child(lid)
	part(lid, "lid", "lid")
	trims.append(part(lid, "lid_gold", "gold", false))
	var halo := MeshInstance3D.new()
	var quad_mesh := QuadMesh.new()
	quad_mesh.size = Vector2(1.9, 1.9)
	halo.mesh = quad_mesh
	halo.material_override = material("halo")
	halo.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	halo.position = Vector3(0, 0.55, 0)
	root.add_child(halo)
	var body := StaticBody3D.new()
	body.collision_layer = Fields.PROP_LAYER
	body.collision_mask = 0
	var shape := CollisionShape3D.new()
	var bounds := BoxShape3D.new()
	bounds.size = Vector3(WIDTH+0.06, BODY+LID_RISE, DEPTH+0.06)
	shape.shape = bounds
	shape.position = Vector3(0, (BODY+LID_RISE)*0.5, 0)
	body.add_child(shape)
	root.add_child(body)
	chests.append({"id":id, "root":root, "lid":lid, "heap":heap, "halo":halo, "trims":trims, "at":Vector2.ZERO, "state":"closed"})
	return root

## Open for good: lid up, no glow, no gold, no prompt.
func set_open(chest: Dictionary, _animate: bool) -> void:
	chest.state = "open"
	if is_instance_valid(chest.lid): chest.lid.rotation.x = -(HOME_OPEN_ANGLE if room != null else OPEN_ANGLE)
	if is_instance_valid(chest.halo): chest.halo.visible = false
	if is_instance_valid(chest.heap): chest.heap.visible = false
	for trim in chest.trims:
		if is_instance_valid(trim): trim.material_override = material("gold_dull")
	if chest.has("record"): chest.record.interactive = false

# ------------------------------------------------------------------ opening

func open_chest(chest: Dictionary) -> void:
	chest.state = "opening"
	var api: Node = room.api if room != null else app.api
	var hero: Node3D = room.hero if room != null else app.player
	if is_instance_valid(hero) and hero.has_method("face_point"): hero.face_point(chest.root.global_position)
	if room != null and room.has_method("update_hint"): room.update_hint()
	# The lid rattles while the server answers (at least a beat, for the anticipation).
	var shake := rattle(chest)
	play("box", -10.0)
	var started := Time.get_ticks_msec()
	var reply: Dictionary = await request_open(api, str(chest.id))
	var waited := (Time.get_ticks_msec()-started)*0.001
	if waited < 0.3 and is_inside_tree(): await get_tree().create_timer(0.3-waited).timeout
	if shake and shake.is_valid(): shake.kill()
	if not is_inside_tree() or not is_instance_valid(chest.root) or chest.state != "opening": return
	chest.lid.rotation.x = 0.0
	if reply.get("ok", false):
		var data: Dictionary = reply.data
		remember(str(api.token), data.get("chests", {}).get("opened", [chest.id]))
		if room == null and app.me is Dictionary and app.me.get("chests") is Dictionary and not chest.id in app.me.chests.get("opened", []):
			app.me.chests.opened.append(chest.id)
		moment(chest, int(data.get("stars", 0)), int(data.get("shards", 0)), data.get("chests", {}))
		return
	var code := str(reply.get("error", ""))
	if code == "chest_already_open":
		remember(str(api.token), [chest.id])
		swing(chest)
		chest.state = "open"
		finish(chest)
	else:
		chest.state = "closed"
	say(refusal(code))

func rattle(chest: Dictionary) -> Tween:
	var lid: Node3D = chest.lid
	var tw := lid.create_tween().set_loops()
	tw.tween_property(lid, "rotation:x", -0.09, 0.07).set_trans(Tween.TRANS_SINE)
	tw.tween_property(lid, "rotation:x", 0.0, 0.07).set_trans(Tween.TRANS_SINE)
	tw.tween_property(lid, "rotation:x", -0.05, 0.06).set_trans(Tween.TRANS_SINE)
	tw.tween_property(lid, "rotation:x", 0.0, 0.06).set_trans(Tween.TRANS_SINE)
	tw.tween_interval(0.08)
	return tw

func swing(chest: Dictionary) -> void:
	var angle := HOME_OPEN_ANGLE if room != null else OPEN_ANGLE
	var lid: Node3D = chest.lid
	if RpgUi.calm():
		lid.rotation.x = -angle
		return
	var tw := lid.create_tween()
	tw.tween_property(lid, "rotation:x", -angle, 0.55).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)

## The open: lid, light, beam, sparkles and coins at the chest, "+N" over it and the stars into the
## counter, then the gold inside is gone and the trim goes still.
func moment(chest: Dictionary, stars: int, total: int, summary: Dictionary) -> void:
	var root: Node3D = chest.root
	var top := root.global_position+Vector3(0, BODY+0.25, 0)
	var stage: Node3D = root.get_parent()
	swing(chest)
	chest.halo.visible = false
	play("lid", -5.0)
	warm_light(chest)
	beam(chest)
	Fx.glow(stage, top, Color("ffd27a"), 2.2, 1.3)
	Fx.burst(stage, top, "sparkle", 26, Color(0,0,0,0), 0.32)
	Fx.ring(stage, root.global_position+Vector3(0, 0.03, 0), 1.6, Color(1.0, 0.88, 0.5, 0.8), 0.9)
	if DisplayServer.get_name() != "headless": Fx.sound(room if room != null else app, "twinkle", Vector3.INF, 1.1, -2.0)
	await get_tree().create_timer(0.16).timeout
	play("coin", -7.0)
	RpgUi.sfx("confirm", -4.0)
	if stars > 0: badge(root.global_position+Vector3(0, 1.05, 0), stars)
	await get_tree().create_timer(0.45).timeout
	if not is_inside_tree(): return
	if room != null: room_stars(root.global_position+Vector3(0, 0.9, 0), stars, total)
	elif is_instance_valid(app): Quests.reward_fly(app, root.global_position+Vector3(0, -1.0, 0), stars, total)
	var words := t("보물상자 · 별씨 +%d") % stars if stars > 0 else t("보물상자를 열었어요")
	say(words)
	var opened: Array = summary.get("opened", [])
	if not opened.is_empty() and opened.size() >= int(summary.get("total", 99)):
		get_tree().create_timer(2.6).timeout.connect(func(): if is_inside_tree(): say(t("보물상자를 모두 찾았어요! %d/%d") % [opened.size(), opened.size()]))
	await get_tree().create_timer(0.25).timeout
	if not is_inside_tree() or not is_instance_valid(root): return
	var heap: Node3D = chest.heap
	if RpgUi.calm(): heap.visible = false
	else:
		var tw := heap.create_tween()
		tw.tween_property(heap, "scale", Vector3(0.6, 0.05, 0.6), 0.55).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
		tw.tween_callback(func(): heap.visible = false)
	chest.state = "open"
	finish(chest)

func finish(chest: Dictionary) -> void:
	chest.halo.visible = false
	for trim in chest.trims:
		if is_instance_valid(trim): trim.material_override = material("gold_dull")
	if chest.has("record"):
		chest.record.interactive = false
		if room != null and room.has_method("update_hint"): room.update_hint()

## A warm light from inside the chest while it opens (one short-lived light, no shadows).
func warm_light(chest: Dictionary) -> void:
	var light := OmniLight3D.new()
	light.light_color = Color("ffc866")
	light.omni_range = 3.4
	light.omni_attenuation = 1.3
	light.shadow_enabled = false
	light.light_energy = 0.0
	light.position = Vector3(0, BODY+0.25, 0.08)
	chest.root.add_child(light)
	var tw := light.create_tween()
	tw.tween_property(light, "light_energy", 2.8, 0.18)
	tw.tween_interval(0.45)
	tw.tween_property(light, "light_energy", 0.0, 1.1).set_trans(Tween.TRANS_SINE)
	tw.tween_callback(light.queue_free)

## A soft column of light rising out of the open chest.
func beam(chest: Dictionary) -> void:
	var node := MeshInstance3D.new()
	var shape := QuadMesh.new()
	shape.size = Vector2(0.9, 1.9)
	node.mesh = shape
	var m := StandardMaterial3D.new()
	m.albedo_texture = Fx.tex("soft")
	m.albedo_color = Color(1.0, 0.86, 0.5, 0.0)
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
	node.material_override = m
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	node.position = Vector3(0, BODY+0.75, 0)
	node.scale = Vector3(1.0, 0.35, 1.0)
	chest.root.add_child(node)
	var tw := node.create_tween()
	tw.tween_property(m, "albedo_color:a", 0.65, 0.2)
	tw.parallel().tween_property(node, "scale", Vector3(1.0, 1.15, 1.0), 0.5).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(node, "position:y", BODY+1.0, 0.5)
	tw.tween_property(m, "albedo_color:a", 0.0, 0.9).set_trans(Tween.TRANS_SINE)
	tw.tween_callback(node.queue_free)

## Screen point of a world point, in the overlay's pixels.
func screen_point(at: Vector3) -> Vector2:
	if room != null:
		var ratio: Vector2 = Vector2(room.viewport.size)/room.view_container.size.max(Vector2.ONE)
		return room.view_container.global_position+room.camera.unproject_position(at)/ratio
	return app.camera.unproject_position(at)

func overlay() -> Control:
	return room if room != null else app.ui

## "+N" with the starseed icon rising over the chest (quests.gd reward_burst's badge).
func badge(at: Vector3, stars: int) -> void:
	var host := overlay()
	if not is_instance_valid(host) or (room != null and not is_instance_valid(room.camera)) or (room == null and not is_instance_valid(app.get("camera"))): return
	var row := HBoxContainer.new()
	row.name = "ChestStars"
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 3)
	row.add_child(RpgUi.icon(STAR_ICON, 38))
	RpgUi.numbers(RpgUi.label(row, "+%d" % stars, 28, RpgUi.HOVER), 28)
	host.add_child(row)
	row.size = row.get_combined_minimum_size()
	row.position = screen_point(at)-row.size*0.5
	row.pivot_offset = row.size*0.5
	row.scale = Vector2.ONE*0.3
	var pop := row.create_tween()
	pop.tween_property(row, "scale", Vector2.ONE*1.15, 0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	pop.parallel().tween_property(row, "position:y", row.position.y-46, 1.0).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	pop.tween_interval(1.0)
	pop.tween_property(row, "modulate:a", 0.0, 0.35)
	pop.tween_callback(row.queue_free)

## In the home: a starseed counter slides in under the room's name, the stars fly into it and it
## ticks up, then it slides away (rooms have no HUD counter); the bag's wallet line follows too.
func room_stars(at: Vector3, stars: int, total: int) -> void:
	if room.data is Dictionary: room.data["shards"] = total
	if is_instance_valid(room.get("wallet")): room.wallet.text = tr("별씨 %d") % total
	if stars <= 0: return
	var pill := PanelContainer.new()
	pill.name = "ChestCounter"
	pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var plate := RpgUi.panel_style("pill")
	plate.content_margin_left = 14
	plate.content_margin_right = 18
	plate.content_margin_top = 6
	plate.content_margin_bottom = 6
	pill.add_theme_stylebox_override("panel", plate)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pill.add_child(row)
	row.add_child(RpgUi.icon(STAR_ICON, 26))
	var counter := RpgUi.numbers(RpgUi.label(row, str(total-stars), 19, RpgUi.HOVER), 19)
	counter.custom_minimum_size.x = 40
	room.add_child(pill)
	var below: float = 16.0
	if is_instance_valid(room.get("name_panel")) and room.name_panel.visible: below = room.name_panel.position.y+room.name_panel.size.y
	pill.position = Vector2(18, below+8)
	pill.modulate.a = 0.0
	var slide := pill.create_tween()
	slide.tween_property(pill, "modulate:a", 1.0, 0.18)
	slide.parallel().tween_property(pill, "position:x", 18.0, 0.22).from(-40.0).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	await get_tree().process_frame
	if not is_instance_valid(pill): return
	var from := screen_point(at)
	var goal := counter.get_global_rect().get_center()
	var flying := mini(stars, 8)
	var landed := [0]
	for k in flying:
		var star := RpgUi.icon(STAR_ICON, 30)
		star.name = "ChestStar"
		star.mouse_filter = Control.MOUSE_FILTER_IGNORE
		star.pivot_offset = Vector2(15, 15)
		star.position = from-Vector2(15, 15)
		star.scale = Vector2.ZERO
		room.add_child(star)
		var rise := from-Vector2(15, 15)+Vector2(randf_range(-60, 60), -60-randf_range(0, 40))
		var tw := star.create_tween()
		tw.tween_interval(0.05+k*0.07)
		tw.tween_property(star, "scale", Vector2.ONE*1.2, 0.16).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		tw.parallel().tween_property(star, "position", rise, 0.3).set_ease(Tween.EASE_OUT)
		tw.tween_property(star, "position", goal-Vector2(15, 15), 0.55).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
		tw.parallel().tween_property(star, "scale", Vector2.ONE*0.6, 0.55)
		tw.tween_callback(func():
			star.queue_free()
			landed[0] += 1
			if not is_instance_valid(counter): return
			if landed[0] == 1: RpgUi.count_to(counter, total, 0.25+0.07*flying)
			counter.pivot_offset = counter.size*0.5
			var bump := counter.create_tween()
			bump.tween_property(counter, "scale", Vector2.ONE*1.22, 0.06)
			bump.tween_property(counter, "scale", Vector2.ONE, 0.12)
			if DisplayServer.get_name() != "headless": Fx.sound(room, "pluck", Vector3.INF, 1.5+0.06*landed[0], -10.0))
	var away := pill.create_tween()
	away.tween_interval(3.2)
	away.tween_property(pill, "modulate:a", 0.0, 0.4)
	away.tween_callback(pill.queue_free)

func say(text: String) -> void:
	if room != null and is_instance_valid(room): room.message(text)
	elif is_instance_valid(app) and app.has_method("message"): app.message(text)

# ------------------------------------------------------------------ sound and the idle glow

func add_voice() -> void:
	voice = AudioStreamPlayer.new()
	voice.bus = &"SFX"
	add_child(voice)

func play(sound_name: String, db := -8.0) -> void:
	if DisplayServer.get_name() == "headless" or not is_instance_valid(voice): return
	var path := SFX % sound_name
	if not ResourceLoader.exists(path): return
	voice.stream = load(path)
	voice.volume_db = db
	voice.pitch_scale = randf_range(0.96, 1.04)
	voice.play()

func _process(delta: float) -> void:
	poll -= delta
	if poll <= 0.0 and room == null:
		poll = 0.5
		sync()
	if not shown: return
	night_wait -= delta
	if night_wait <= 0.0:
		night_wait = 1.0
		night = night_level()
	# Shared by every chest: the trim breathes and the halo follows (brighter at night).
	var breathe := 0.5+0.5*sin(Time.get_ticks_msec()*0.0019)
	material("gold").emission_energy_multiplier = 0.22+0.3*breathe+0.6*night
	var halo := material("halo")
	halo.albedo_color = Color(halo.albedo_color, (0.12+0.4*night)*(0.7+0.3*breathe))
	sparkle_wait -= delta
	if sparkle_wait <= 0.0:
		sparkle_wait = 2.3
		sparkle()

## A few sparkles over the closed chests near the walker (two at most).
func sparkle() -> void:
	var walker: Node3D = room.hero if room != null else (app.player if is_instance_valid(app) else null)
	if not is_instance_valid(walker): return
	if room != null and room.floor_index != 0: return
	var near: Array = []
	for chest in chests:
		if chest.state != "closed" or not is_instance_valid(chest.root): continue
		var gap: float = walker.global_position.distance_to(chest.root.global_position)
		if gap < 24.0: near.append([gap, chest])
	near.sort_custom(func(a, b): return a[0] < b[0])
	for pick in near.slice(0, 2):
		var root: Node3D = pick[1].root
		Fx.burst(root.get_parent(), root.global_position+Vector3(0, 0.62, 0), "sparkle", 3, Color(0,0,0,0), 0.34)

## 0 by day, 1 at night: the village's daylight (field_objects.gd night_level); the home by its clock.
func night_level() -> float:
	if room != null:
		var hour: float = float(room.get("daylight_sample").get("hour", 12.0)) if room.get("daylight_sample") is Dictionary else 12.0
		return 0.6 if hour < 6.0 or hour >= 19.0 else 0.15
	var current: Dictionary = {}
	if is_instance_valid(app) and app.get("daylight") and "current" in app.daylight: current = app.daylight.current
	if current.is_empty(): current = Daylight.sample(Daylight.clock_hour())
	return clampf(float(current.get("lamp_energy", 0.0))/Daylight.LAMP_NIGHT_GAIN, 0.0, 1.0)
