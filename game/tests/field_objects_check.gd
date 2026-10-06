extends SceneTree
## Field objects harness: builds the island map (town.gd) and field_objects.gd with a
## stub app, then checks every object: placed, on the ground, off the roads and away
## from doors, reachable from the nearest road with a 0.34 m sphere, and that
## closest()/interact() work (dialogues, seats, telescope view, signpost travel).
##   godot --headless --path game --script res://tests/field_objects_check.gd
## Windowed with -- --capture it also writes artifacts/field-day.png,
## artifacts/field-night.png and artifacts/field-seats.png contact sheets.
const Town = preload("res://scripts/town.gd")
const Roads = preload("res://scripts/roads.gd")
const Fields = preload("res://scripts/field_objects.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const Daylight = preload("res://scripts/daylight.gd")
const Player = preload("res://scripts/player.gd")
const Minimap = preload("res://scripts/minimap.gd")
const Fx = preload("res://scripts/fx.gd")

class Stub extends Node3D:
	const P = preload("res://scripts/controller_profile.gd")
	var player: CharacterBody3D
	var camera: Camera3D
	var town: Node3D
	var ui: Control
	var daylight: Node
	var social: Node
	var me := {"username":"tester"}
	var life: Node
	var screen := "village"
	var sound: Node
	var messages: Array = []
	var dialogues: Array = []
	func message(text: String) -> void: messages.append(text)
	func open_dialogue(speaker: String, _cast: String, lines: Array, choices: Array) -> void:
		dialogues.append({"speaker":speaker,"lines":lines,"choices":choices})
	func floating_feedback(text: String, _at: Vector3, _color: Color) -> void: messages.append(text)
	func follow_camera(_delta: float) -> void:
		var focus := player.position+P.CAMERA_FOCUS_OFFSET
		camera.position = focus+P.CAMERA_OFFSET
		camera.look_at(focus)

class SocialStub extends Node:
	var enabled := false
	var data := {"invites":[{"sender":"mina","kind":"village"}],"messages":[{"username":"mina","text":"놀러 와!"}]}
	func visiting() -> bool: return false
	func open_menu() -> void: pass

class LifeStub extends Node:
	var state := {"plots":[{},{"watered":false},{"watered":true,"ready_at":0},{},{},{}]}
	func goal_text() -> String: return "▸ 텃밭에 씨앗 심기\n▸ 캠프 초원에서 탐험 떠나기"
	func now() -> float: return 100.0
	func open_map() -> void: pass

var app: Stub
var fields: Node3D
var space: PhysicsDirectSpaceState3D
var report := PackedStringArray()
var failures := 0
var environment: Environment
var sun: DirectionalLight3D
var daylight: Node

func _initialize() -> void: call_deferred("run")

func check(ok: bool, what: String) -> void:
	if not ok:
		failures += 1
		report.append("FAIL "+what)

func frames(n: int) -> void:
	for i in n: await process_frame

## Lets real time pass while the stub camera follows the walker like main.gd does.
func camera_frames(seconds: float) -> void:
	var until := Time.get_ticks_msec()+int(seconds*1000.0)
	while Time.get_ticks_msec() < until:
		app.follow_camera(0.016)
		await process_frame

func run() -> void:
	Profile.ensure_input()
	var capture := "--capture" in OS.get_cmdline_user_args()
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
	app.life = LifeStub.new()
	app.add_child(app.life)
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
	fields.setup(app)
	space = fields.get_world_3d().direct_space_state
	for i in 4: await physics_frame
	report.append("placed %d / %d objects; skipped %s" % [fields.objects.size(), Fields.SPECS.size(), str(fields.skipped)])
	check(fields.skipped.is_empty(), "objects without a valid spot: %s" % str(fields.skipped))
	for spec in Fields.SPECS:
		if not spec.id in fields.skipped: continue
		var r: float = Fields.RADIUS[spec.kind]
		for ring in [0.0, 1.5, 3.0]:
			for k in 4:
				var p: Vector2 = spec.at+Vector2(cos(k*PI*0.5),sin(k*PI*0.5))*ring
				report.append("  %s at %s: %s" % [spec.id, str(p), fields.blocker(p, r, fields.spot_ground(p, r))])
	var islands := {}
	for entry in fields.objects: await check_object(entry, islands)
	report.append("islands covered: %s" % ", ".join(PackedStringArray(islands.keys())))
	check(islands.size() == 5, "objects on %d of 5 islands" % islands.size())
	await check_travel()
	if capture: await captures()
	report.append("RESULT %s (%d failures)" % ["PASS" if failures == 0 else "FAIL", failures])
	var text := "\n".join(report)
	print(text)
	var out := FileAccess.open(ProjectSettings.globalize_path("res://../artifacts/field-objects-check.txt"), FileAccess.WRITE)
	if out: out.store_string(text+"\n")
	quit(1 if failures > 0 else 0)

func ground(p: Vector2, mask := 1) -> float:
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x,60,p.y),Vector3(p.x,-20,p.y),mask))
	return hit.position.y if not hit.is_empty() else NAN

## A 0.34 m sphere walks from the nearest road centre point to where the walker stands.
func path_clear(from: Vector2, to: Vector2) -> String:
	var steps := maxi(1, int(from.distance_to(to)/0.25))
	var ball := SphereShape3D.new()
	ball.radius = 0.34
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = ball
	query.collision_mask = 2|8|16
	for i in steps+1:
		var p := from.lerp(to, float(i)/steps)
		var y := ground(p, 1|2)
		if is_nan(y) or y < 1.0: return "water/void at %s" % str(p)
		query.transform = Transform3D(Basis.IDENTITY, Vector3(p.x, y+0.62, p.y))
		var hits := space.intersect_shape(query, 1)
		if not hits.is_empty():
			var body: Object = hits[0].collider
			var owner_name := str(body.get_parent().name) if body is Node and body.get_parent() else str(body)
			return "blocked at %s by %s" % [str(p), owner_name]
	return ""

func check_object(entry: Dictionary, islands: Dictionary) -> void:
	var id: String = entry.id
	var root: Node3D = entry.root
	check(is_instance_valid(root) and root.is_inside_tree(), id+" exists")
	var at: Vector2 = entry.at
	var g := ground(at)
	check(not is_nan(g) and absf(root.global_position.y-g) < 0.06, id+" sits on ground (%.2f vs %.2f)" % [root.global_position.y, g])
	check(not Roads.on_road(at), id+" on a road")
	var centre: Vector2 = Fields.road_centre(at)
	check(centre.distance_to(at) >= 1.2, id+" too close to a road centre line")
	var nearest_door := INF
	for door in Town.DOORS: nearest_door = minf(nearest_door, at.distance_to(door.at))
	check(nearest_door >= 2.5, id+" within 2.5 m of a door")
	var stand: Vector3 = entry.stand
	var blocked := path_clear(centre, Vector2(stand.x, stand.z))
	check(blocked.is_empty(), id+" not reachable from the road: "+blocked)
	islands[Minimap.island_name(at)] = true
	# Use it.
	var player := app.player
	player.global_position = stand+Vector3(0,0.05,0)
	await physics_frame
	var near: Dictionary = fields.closest(player.position)
	check(near.get("id","") == id, id+" closest() gave %s" % str(near.get("id","")))
	var said := app.messages.size()
	var shown := Fx.played
	var talked := app.dialogues.size()
	fields.interact(near)
	await frames(6)
	var effect := ""
	match String(entry.kind):
		"signpost","mailbox","notice","lost":
			check(app.dialogues.size() > talked, id+" opened no dialogue")
			if app.dialogues.size() > talked:
				var d: Dictionary = app.dialogues[app.dialogues.size()-1]
				effect = "dialogue '%s' %d lines, %d choices" % [d.speaker, d.lines.size(), d.choices.size()]
				if entry.kind == "signpost": check(d.choices.size() == 5, id+" offers %d choices" % d.choices.size())
		"swing","rocker","hammock":
			check(not fields.seat.is_empty() and player.visual_only, id+" did not seat the walker")
			for i in 30: await physics_frame
			var seat_y: float = (entry.pivot.global_transform*Vector3(entry.seat_local)).y
			effect = "seated, hips %.2f m over seat" % (player.global_position.y+fields.hip_height(player)-seat_y)
			var standing: Dictionary = fields.closest(player.position)
			check(standing.get("id","") == "stand", id+" offers no stand-up prompt")
			fields.interact(standing)
			await physics_frame
			check(fields.seat.is_empty() and not player.visual_only, id+" stand up failed")
		"telescope":
			check(not fields.view.is_empty(), id+" started no view")
			var before := app.camera.position
			await camera_frames(1.2)
			var moved := app.camera.position.distance_to(before)
			effect = "view moved camera %.1f m, size %.1f" % [moved, app.camera.size]
			check(moved > 10.0, id+" view barely moved the camera")
			fields.interact(fields.closest(player.position))
			await camera_frames(1.3)
			check(fields.view.is_empty() and absf(app.camera.size-Profile.VILLAGE_CAMERA_DEFAULT) < 0.01, id+" view did not end cleanly")
		_:
			if entry.kind == "photo": await frames(10)
			# Uses show instead of tell: effects started, no toast sentences.
			check(Fx.played > shown, id+" showed nothing")
			check(app.messages.size() == said, id+" still talks: %s" % str(app.messages.slice(said)))
			effect = "%d effects" % (Fx.played-shown)
	report.append("%-16s %-10s at (%6.1f, %6.1f) y %.2f  yaw %4.0f  road %.1f m  door %.1f m  %s  | %s" % [id, entry.kind,
		at.x, at.y, root.global_position.y, rad_to_deg(root.rotation.y), centre.distance_to(at), nearest_door,
		Minimap.island_name(at), effect])

## Every signpost sends the walker to every other island onto clear road.
func check_travel() -> void:
	var signs: Array = fields.objects.filter(func(e): return e.kind == "signpost")
	for entry in signs:
		var arrival: Vector3 = fields.arrival_point(entry)
		check(arrival != Vector3.INF, entry.id+" has no arrival point")
		if arrival == Vector3.INF: continue
		check(Roads.on_road(Vector2(arrival.x, arrival.z)), entry.id+" arrival is off the road")
	var first: Dictionary = signs[0]
	var last: Dictionary = signs[signs.size()-1]
	app.player.global_position = first.stand
	fields.interact(fields.closest(app.player.position))
	var d: Dictionary = app.dialogues[app.dialogues.size()-1]
	var go: Callable = d.choices[d.choices.size()-2][1]
	go.call()
	for i in 90: await process_frame
	var want: Vector3 = fields.arrival_point(last)
	var got: Vector3 = app.player.global_position
	report.append("travel %s -> %s: walker at (%.1f, %.1f, %.1f), arrival (%.1f, %.1f, %.1f)" % [first.id, last.id, got.x, got.y, got.z, want.x, want.y, want.z])
	check(Vector2(got.x, got.z).distance_to(Vector2(want.x, want.z)) < 0.6, "signpost travel did not arrive")

func captures() -> void:
	for hour in [12.0, 21.0]:
		daylight.override_hour = hour
		daylight.refresh(true)
		var tiles: Array[Image] = []
		for entry in fields.objects:
			var stand: Vector3 = entry.stand
			app.player.global_position = stand+Vector3(0,0.05,0)
			app.player.face_point(entry.root.global_position)
			app.camera.size = 7.0
			var focus: Vector3 = entry.root.global_position.lerp(stand, 0.4)+Profile.CAMERA_FOCUS_OFFSET
			app.camera.position = focus+Profile.CAMERA_OFFSET
			app.camera.look_at(focus)
			await frames(8)
			await RenderingServer.frame_post_draw
			tiles.append(tile(root.get_viewport().get_texture().get_image(), entry.id))
		save_sheet(tiles, "field-%s.png" % ("day" if hour < 18.0 else "night"))
	daylight.override_hour = 16.0
	daylight.refresh(true)
	var seats: Array[Image] = []
	for entry in fields.objects:
		if not entry.kind in ["swing","rocker","hammock"]: continue
		app.player.global_position = entry.stand
		fields.interact({"id":entry.id})
		for i in 50: await physics_frame
		app.camera.size = 4.5
		var focus: Vector3 = entry.root.global_position+Vector3(0,0.6,0)
		app.camera.position = focus+Profile.CAMERA_OFFSET
		app.camera.look_at(focus)
		await frames(4)
		await RenderingServer.frame_post_draw
		seats.append(tile(root.get_viewport().get_texture().get_image(), entry.id))
		fields.interact({"id":"stand"})
		await physics_frame
	save_sheet(seats, "field-seats.png")

func tile(image: Image, _label: String) -> Image:
	var w := image.get_width()
	var h := image.get_height()
	var crop := image.get_region(Rect2i(int(w*0.22), int(h*0.12), int(w*0.56), int(h*0.62)))
	crop.resize(448, 310, Image.INTERPOLATE_BILINEAR)
	return crop

func save_sheet(tiles: Array[Image], file: String) -> void:
	if tiles.is_empty(): return
	var cols := 5 if tiles.size() > 4 else tiles.size()
	var rows := int(ceil(tiles.size()/float(cols)))
	var sheet := Image.create(cols*452, rows*314, false, tiles[0].get_format())
	sheet.fill(Color(0.1,0.1,0.12))
	for i in tiles.size():
		sheet.blit_rect(tiles[i], Rect2i(0,0,448,310), Vector2i((i%cols)*452, (i/cols)*314))
	sheet.save_png(ProjectSettings.globalize_path("res://../artifacts/"+file))
	report.append("wrote artifacts/"+file)
