extends SceneTree
## Treasure chest spots (treasure.gd FIELD): builds the island map (town.gd), field_objects.gd and
## treasure.gd with a stub app (no server), then checks every field chest: placed (not skipped)
## within 0.8 m of its authored spot, two per island on the island its id names, sitting on the
## ground, off the roads, clear of doors, signposts, seats and the café terrace slot, reachable from
## the nearest road with a 0.34 m sphere, E (closest()) offered where the walker stands, and the
## café chest a short walk from 모카's terrace. Run it after map changes (another session owns the
## map): a chest whose spot was built over moves at most RING_MAX metres or is reported here.
##   godot --headless --path game --script res://tests/treasure_spots.gd
##   ... -- --probe=x,z;x,z   prints why chests could or could not stand at those points
##   ... -- --grid=x0,z0,x1,z1  an ASCII map of where chests could stand (1 m cells)
## Windowed with -- --capture it writes artifacts/treasure-day.png, treasure-night.png and
## treasure-open.png contact sheets (-- --wide: a wider view around each chest).
const Town = preload("res://scripts/town.gd")
const Roads = preload("res://scripts/roads.gd")
const Fields = preload("res://scripts/field_objects.gd")
const Treasure = preload("res://scripts/treasure.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const Daylight = preload("res://scripts/daylight.gd")
const Player = preload("res://scripts/player.gd")
const Guide = preload("res://scripts/guide.gd")
const Story = preload("res://scripts/story.gd")

class Stub extends Node3D:
	const P = preload("res://scripts/controller_profile.gd")
	var player: CharacterBody3D
	var camera: Camera3D
	var town: Node3D
	var ui: Control
	var daylight: Node
	var social: Node
	var me := {"username":"tester"}
	var modules: Array = []
	var screen := "village"
	var messages: Array = []
	func message(text: String) -> void: messages.append(text)
	func open_dialogue(_speaker: String, _cast: String, _lines: Array, _choices: Array) -> void: pass
	func follow_camera(_delta: float) -> void:
		var focus := player.position+P.CAMERA_FOCUS_OFFSET
		camera.position = focus+P.CAMERA_OFFSET
		camera.look_at(focus)

class SocialStub extends Node:
	var enabled := false
	var data := {}
	func visiting() -> bool: return false

var app: Stub
var fields: Node3D
var chests: Node3D
var space: PhysicsDirectSpaceState3D
var report := PackedStringArray()
var failures := 0
var environment: Environment
var sun: DirectionalLight3D
var daylight: Node

func _initialize() -> void: call_deferred("run")

func check(ok: bool, what: String) -> void:
	report.append(("PASS " if ok else "FAIL ")+what)
	if not ok: failures += 1

func frames(n: int) -> void:
	for i in n: await process_frame

func run() -> void:
	Profile.ensure_input()
	var args := OS.get_cmdline_user_args()
	var world := WorldEnvironment.new()
	environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	world.environment = environment
	root.add_child(world)
	sun = DirectionalLight3D.new()
	sun.shadow_enabled = true
	root.add_child(sun)
	app = Stub.new()
	root.add_child(app)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = Profile.VILLAGE_CAMERA_DEFAULT
	camera.current = true
	app.add_child(camera)
	app.camera = camera
	app.ui = Control.new()
	var layer := CanvasLayer.new()
	app.add_child(layer)
	layer.add_child(app.ui)
	app.social = SocialStub.new()
	app.add_child(app.social)
	var town: Node3D = Town.new()
	town.camera = camera
	app.add_child(town)
	app.town = town
	Town.Archipelago.apply_lighting(environment, sun)
	daylight = Daylight.new()
	daylight.override_hour = 12.0
	root.add_child(daylight)
	daylight.attach(environment, sun, town.map)
	app.daylight = daylight
	var player: CharacterBody3D = Player.new()
	app.add_child(player)
	player.position = Town.point(Town.SPAWN, .3)
	player.min_ground_y = Town.SHORE_MIN_Y
	app.player = player
	await physics_frame
	await physics_frame
	fields = Fields.new()
	app.add_child(fields)
	await fields.setup(app)
	app.modules.append(fields)
	chests = Treasure.new()
	chests.always_shown = true
	chests.fields_module = fields
	app.add_child(chests)
	await chests.setup(app)
	app.modules.append(chests)
	space = chests.get_world_3d().direct_space_state
	for i in 4: await physics_frame
	for arg in args:
		if arg.begins_with("--probe="): probe(arg.substr(8))
		if arg.begins_with("--grid="): grid(arg.substr(7))
	check(chests.skipped.is_empty(), "every field chest found a spot (skipped: %s)" % str(chests.skipped))
	check(chests.chests.size() == Treasure.FIELD.size() and Treasure.FIELD.size() == 10, "ten field chests placed (%d)" % chests.chests.size())
	var per_island := {}
	for chest in chests.chests: await check_chest(chest, per_island)
	check(per_island.size() == 5 and per_island.values().all(func(n): return n == 2), "two chests on each of the five islands (%s)" % str(per_island))
	var cafe: Dictionary = chests.chest_of("fields_cafe")
	if not cafe.is_empty():
		var walk: float = Vector2(cafe.at).distance_to(Story.MOKA_AT)
		check(walk >= 3.0 and walk <= 14.0, "the café chest is a few steps from 모카's terrace (%.1f m)" % walk)
	if "--capture" in args: await captures("--wide" in args)
	report.append("RESULT %s (%d failures)" % ["PASS" if failures == 0 else "FAIL", failures])
	var text := "\n".join(report)
	print(text)
	var out := FileAccess.open(ProjectSettings.globalize_path("res://../artifacts/treasure-spots.txt"), FileAccess.WRITE)
	if out: out.store_string(text+"\n")
	quit(1 if failures > 0 else 0)

func ground(p: Vector2, mask := 1) -> float:
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x,60,p.y),Vector3(p.x,-20,p.y),mask))
	return hit.position.y if not hit.is_empty() else NAN

## Metres walked from p to the nearest road over a 0.5 m grid (a 0.34 m sphere fits, ground under
## it, no step higher than 0.45 m), or -1 when no road is reached within 50 m.
func walk_to_road(start: Vector2) -> float:
	var cell := 0.5
	var ball := SphereShape3D.new()
	ball.radius = 0.34
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = ball
	query.collision_mask = 2|8|16
	var heights := {}
	var seen := {Vector2i.ZERO:0}
	var queue: Array[Vector2i] = [Vector2i.ZERO]
	var head := 0
	while head < queue.size():
		var c: Vector2i = queue[head]
		head += 1
		var p := start+Vector2(c)*cell
		if Roads.on_road(p): return float(seen[c])*cell
		if absi(c.x) > 100 or absi(c.y) > 100: continue
		var y: float = heights.get(c, ground(p, 1|2))
		heights[c] = y
		for step in [Vector2i(1,0), Vector2i(-1,0), Vector2i(0,1), Vector2i(0,-1)]:
			var n: Vector2i = c+step
			if seen.has(n): continue
			var q := start+Vector2(n)*cell
			var ny := ground(q, 1|2)
			heights[n] = ny
			if is_nan(ny) or ny < 1.0 or absf(ny-y) > 0.45: continue
			query.transform = Transform3D(Basis.IDENTITY, Vector3(q.x, ny+0.62, q.y))
			if not space.intersect_shape(query, 1).is_empty(): continue
			seen[n] = int(seen[c])+1
			queue.append(n)
	return -1.0

## Where the walker stands to open a chest: in front of it, on its road side.
func stand_of(chest: Dictionary) -> Vector2:
	var front := Vector2(sin(chest.root.rotation.y), cos(chest.root.rotation.y))
	return Vector2(chest.at)+front*1.0

func check_chest(chest: Dictionary, per_island: Dictionary) -> void:
	var id: String = chest.id
	var at: Vector2 = chest.at
	var spec: Dictionary = {}
	for s in Treasure.FIELD:
		if s.id == id: spec = s
	var moved: float = at.distance_to(spec.get("at", at))
	report.append("  %s at (%.1f, %.1f) moved %.2f m, yaw %.0f°" % [id, at.x, at.y, moved, rad_to_deg(chest.root.rotation.y)])
	check(moved <= 0.8, id+" within 0.8 m of its authored spot (%.2f)" % moved)
	var island := Guide.island_key(at)
	per_island[island] = int(per_island.get(island, 0))+1
	check(id.begins_with(island+"_"), id+" stands on its island (%s)" % island)
	var g := ground(at)
	check(not is_nan(g) and absf(chest.root.global_position.y-g) < 0.12, id+" sits on the ground (%.2f vs %.2f)" % [chest.root.global_position.y, g])
	check(not Roads.on_road(at) and Fields.road_gap(at) >= 0.4, id+" off the roads (%.2f m from an edge)" % Fields.road_gap(at))
	var door := INF
	for d in Town.DOORS: door = minf(door, at.distance_to(d.at))
	check(door >= 2.8, id+" clear of doors (%.1f m)" % door)
	var sign := INF
	for entry in fields.objects:
		if entry.kind == "signpost": sign = minf(sign, at.distance_to(entry.at))
	check(sign >= 3.0, id+" clear of signposts (%.1f m)" % sign)
	var seat := INF
	for prop in app.town.props:
		if str(prop.id) in Treasure.SEATS: seat = minf(seat, at.distance_to(prop.at))
	check(seat >= Treasure.SEAT_CLEAR, id+" clear of seats, so E there sits (%.1f m)" % seat)
	for keep in Treasure.KEEP_CLEAR:
		check(at.distance_to(keep[0]) >= float(keep[1]), id+" clear of the café terrace slot and 모카's place")
	var stand := stand_of(chest)
	var walk := walk_to_road(stand)
	check(walk >= 0.0, id+" reachable on foot from a road (%s)" % ("%.0f m" % walk if walk >= 0.0 else "no way found"))
	app.player.global_position = Vector3(stand.x, ground(stand, 1|2)+0.05, stand.y)
	await physics_frame
	var near: Dictionary = chests.closest(app.player.position)
	check(str(near.get("id", "")) == id and str(near.get("prompt", "")) == "보물상자 열기", id+" offers E where the walker stands")

## Why chests could or could not stand at each point (x,z;x,z).
func probe(points: String) -> void:
	for item in points.split(";", false):
		var xz := item.split(",")
		if xz.size() != 2: continue
		var p := Vector2(float(xz[0]), float(xz[1]))
		var why: String = chests.spot_problem(p, fields)
		var fit: Dictionary = chests.ground_fit(p, Treasure.facing(p))
		var door := INF
		for d in Town.DOORS: door = minf(door, p.distance_to(d.at))
		var seat := INF
		for prop in app.town.props:
			if str(prop.id) in Treasure.SEATS: seat = minf(seat, p.distance_to(prop.at))
		report.append("PROBE (%.1f, %.1f) %s: %s, ground %s, road gap %.1f, door %.1f, seat %.1f" % [p.x, p.y, Guide.island_key(p), why if not why.is_empty() else "ok",
			"flat %.2f" % float(fit.ground) if not fit.is_empty() else "uneven", Fields.road_gap(p), door, seat])

## Where a chest could stand, one character per metre: . yes, r road, w water/rock/slope, p prop,
## b building or collider, o field object, d door, l place, v villager, g gate, f farm, k kept clear,
## s near a seat, c near another chest, u uneven.
func grid(box: String) -> void:
	var v := box.split(",")
	if v.size() != 4: return
	var x0 := int(v[0])
	var z0 := int(v[1])
	var x1 := int(v[2])
	var z1 := int(v[3])
	var header := "      "
	for x in range(x0, x1+1): header += str(absi(x)%10)
	report.append("GRID x %d..%d (ones digit), z rows" % [x0, x1])
	report.append(header)
	for z in range(z0, z1+1):
		var row := "%5d " % z
		for x in range(x0, x1+1):
			var why: String = chests.spot_problem(Vector2(x, z), fields)
			var mark := "."
			if why.begins_with("road"): mark = "r"
			elif why.begins_with("water") or why.begins_with("no ground"): mark = "w"
			elif why.begins_with("prop"): mark = "p"
			elif why.begins_with("building") or why.begins_with("collider"): mark = "b"
			elif why.begins_with("object"): mark = "o"
			elif why.begins_with("door"): mark = "d"
			elif why.begins_with("place"): mark = "l"
			elif why.begins_with("villager"): mark = "v"
			elif why.begins_with("gate"): mark = "g"
			elif why.begins_with("farm") or why.begins_with("pond"): mark = "f"
			elif why.begins_with("kept"): mark = "k"
			elif why.begins_with("chest"): mark = "c"
			elif why.begins_with("seat"): mark = "s"
			elif not why.is_empty(): mark = "?"
			elif chests.ground_fit(Vector2(x, z), Treasure.facing(Vector2(x, z))).is_empty(): mark = "u"
			row += mark
		report.append(row)

func captures(wide: bool) -> void:
	for pass_name in ["day", "night", "open"]:
		daylight.override_hour = 21.5 if pass_name == "night" else 15.0
		daylight.refresh(true)
		chests.night_wait = 0.0
		if pass_name == "open":
			for chest in chests.chests: chests.set_open(chest, false)
		var tiles: Array[Image] = []
		for chest in chests.chests:
			var stand := stand_of(chest)
			app.player.global_position = Vector3(stand.x, ground(stand, 1|2)+0.05, stand.y)+Vector3(0.9, 0, 0.6)
			app.player.face_point(chest.root.global_position)
			app.camera.size = 16.0 if wide else 6.0
			var focus: Vector3 = chest.root.global_position+Profile.CAMERA_FOCUS_OFFSET
			app.camera.position = focus+Profile.CAMERA_OFFSET
			app.camera.look_at(focus)
			await frames(8)
			await RenderingServer.frame_post_draw
			tiles.append(tile(root.get_viewport().get_texture().get_image()))
		save_sheet(tiles, "treasure-%s%s.png" % [pass_name, "-wide" if wide else ""])

func tile(image: Image) -> Image:
	var w := image.get_width()
	var h := image.get_height()
	var crop := image.get_region(Rect2i(int(w*0.22), int(h*0.12), int(w*0.56), int(h*0.62)))
	crop.resize(448, 310, Image.INTERPOLATE_BILINEAR)
	return crop

func save_sheet(tiles: Array[Image], file: String) -> void:
	if tiles.is_empty(): return
	var cols := 5
	var rows := int(ceil(tiles.size()/float(cols)))
	var sheet := Image.create(cols*452, rows*314, false, tiles[0].get_format())
	sheet.fill(Color(0.1,0.1,0.12))
	for i in tiles.size():
		sheet.blit_rect(tiles[i], Rect2i(0,0,448,310), Vector2i((i%cols)*452, (i/cols)*314))
	sheet.save_png(ProjectSettings.globalize_path("res://../artifacts/"+file))
	report.append("wrote artifacts/"+file)
