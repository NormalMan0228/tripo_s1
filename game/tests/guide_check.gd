extends SceneTree
## Route guide (scripts/guide.gd) on the real village built from recorded server
## replies (tests/ui_stub_api.gd): the road graph reaches every island, routes to
## places on different islands are sane and stay on the roads, the trail lies on
## them, walking a route ends in an arrival that clears the guide, tracker rows and
## the Tab map start and stop it, the setting hides the trail but keeps the minimap
## flag, the goal survives a rebuilt village, and a frame of guiding allocates no
## objects. Headless:
##   godot --headless --path game --script res://tests/guide_check.gd -- --qa
const Main = preload("res://scripts/main.gd")
const Guide = preload("res://scripts/guide.gd")
const Town = preload("res://scripts/town.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const I18n = preload("res://scripts/i18n.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
var failed := false
var app: Node
var guide: Node

func _initialize() -> void:
	call_deferred("run")
	create_timer(300).timeout.connect(func():
		push_error("guide check exceeded 300 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func settle(seconds := 0.4) -> void:
	await create_timer(seconds).timeout

func click(c: Control) -> void:
	var at: Vector2 = root.get_final_transform() * (c.get_global_transform_with_canvas() * (c.size * 0.5))
	for down in [true, false]:
		var event := InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = down
		event.position = at
		event.global_position = at
		root.push_input(event)
		await process_frame

func put(at: Vector2) -> void:
	app.player.velocity = Vector3.ZERO
	app.player.global_position = Town.point(at, 0.1)
	await physics_frame
	await process_frame

func run() -> void:
	I18n.setup()
	GameSettings.ensure_loaded()
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	app = Main.new()
	root.add_child(app)
	await settle(1.6)
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	Guide.kept = {}
	Guide.player_stopped = false
	await app.enter_village()
	await settle(1.5)
	expect(app.screen == "village", "village built from recorded replies")
	guide = Guide.current
	expect(is_instance_valid(guide) and guide in app.modules, "guide module live in the village")
	if not is_instance_valid(guide):
		quit(1)
		return
	expect(guide.paths.points.size() > 60 and guide.paths.edges().size() > 60, "road graph built (%d nodes, %d edges)" % [guide.paths.points.size(), guide.paths.edges().size()])
	await tracker()
	await routes()
	await walk_arrive()
	await clicks()
	await tab_map()
	await setting()
	await frames()
	await survive()
	print("GUIDE_CHECK ", "FAIL" if failed else "OK")
	app.queue_free()
	await settle(0.3)
	quit(1 if failed else 0)

## Tracker lines turned into rows; the first objective guided on arrival.
func tracker() -> void:
	expect(not app.objective.visible and guide.rows_box != null and guide.rows_box.get_parent() == app.objective.get_parent(), "objective lines shown as guide rows")
	var keys := []
	for row in guide.rows:
		if row.panel.visible and not str(row.key).is_empty(): keys.append(row.key)
	expect(keys.size() >= 3 and "fish" in keys and "forage" in keys, "objective rows map to goals %s" % [keys])
	expect(guide.active() and guide.target.key == keys[0], "first objective guided when the village opens (%s)" % guide.target.get("key", ""))
	expect(guide.trail.visible and guide.beacon.visible and guide.trail.multimesh.visible_instance_count > 5, "trail (%d chevrons) and pillar shown" % guide.trail.multimesh.visible_instance_count)
	expect(app.minimap.guide_target == guide.target.at and app.minimap.guide_route.size() > 1, "minimap carries the route and the flag")

## Routes across islands: sane length, roads all the way, trail on the roads.
func routes() -> void:
	var cases := [
		["lighthouse bell", Town.SPAWN, Vector2(10.4, 79.6), Vector2(-13.5, 65.5)],
		["windmill door", Town.SPAWN, Vector2(-18.9, -41.0), Vector2(2.0, -36.0)],
		["camp gate", Town.SPAWN, Town.GATE, Vector2(3.5, 27.0)],
		["general store door", Vector2(-50.5, 27.5), Vector2(-17.9, 29.9), Vector2.INF],
		["observatory door", Vector2(4.6, 80.6), Vector2(30.0, -42.6), Vector2(57.0, 3.5)],
	]
	for entry in cases:
		var from: Vector2 = entry[1]
		var goal: Vector2 = entry[2]
		await put(from)
		guide.guide_to(Town.point(goal), entry[0], "check")
		var route: PackedVector2Array = guide.route
		var straight := from.distance_to(goal)
		expect(guide.active() and route.size() >= 3 and route[route.size()-1].distance_to(goal) < 0.05, "%s: route of %d points ends at the goal" % [entry[0], route.size()])
		expect(guide.remaining >= straight-0.5 and guide.remaining <= straight*3.2+40.0, "%s: %.0f m by road vs %.0f m straight" % [entry[0], guide.remaining, straight])
		var off := 0.0
		for i in route.size():
			if route[i].distance_to(from) < 3.0 or route[i].distance_to(goal) < 4.0: continue
			off = maxf(off, guide.paths.distance_to_network(route[i]))
		expect(off < 0.6, "%s: every bend is on a road (worst %.2f m off)" % [entry[0], off])
		if entry[3] != Vector2.INF:
			var crossed := false
			for i in route.size()-1:
				if Geometry2D.get_closest_point_to_segment(entry[3], route[i], route[i+1]).distance_to(entry[3]) < 3.0: crossed = true
			expect(crossed, "%s: crosses the bridge at (%.0f, %.0f)" % [entry[0], entry[3].x, entry[3].y])
		var multi: MultiMesh = guide.trail.multimesh
		var worst := 0.0
		var lowest := INF
		for i in multi.visible_instance_count:
			var at: Vector3 = guide.spots[i]
			var p := Vector2(at.x, at.z)
			if p.distance_to(goal) < 4.0 or p.distance_to(from) < 3.0: continue
			worst = maxf(worst, guide.paths.distance_to_network(p))
			# Ground or deck under the chevron (terrain and structures; walkers and props
			# on layer 8 come and go).
			var hit: Dictionary = guide.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x, at.y+1.0, p.y), Vector3(p.x, -20, p.y), 1|2))
			if not hit.is_empty(): lowest = minf(lowest, at.y-float(hit.position.y))
		expect(multi.visible_instance_count >= 20 and worst < 1.0, "%s: %d chevrons on the road (worst %.2f m off)" % [entry[0], multi.visible_instance_count, worst])
		expect(lowest > 0.05 and lowest < 0.5, "%s: chevrons float just above the ground (min lift %.2f m)" % [entry[0], lowest])
	guide.stop(false)

## Walking the route (teleported a step per frame) ends in an arrival.
func walk_arrive() -> void:
	await put(Vector2(-33.0, 31.0))
	var goal: Dictionary = Guide.place("pond")
	var heard := []
	guide.arrived.connect(func(key): heard.append(key))
	guide.guide_to(Town.point(goal.at), "pond", "place:pond")
	var route: PackedVector2Array = guide.route.duplicate()
	expect(route.size() >= 2, "pond route from the town hall (%d points, %.0f m)" % [route.size(), guide.remaining])
	var start: float = guide.remaining
	var steps := 0
	var counted_down := false
	for i in route.size()-1:
		var a: Vector2 = route[i]
		var b: Vector2 = route[i+1]
		var n := maxi(1, int(a.distance_to(b)/0.8))
		for k in n:
			if not guide.active(): break
			await put(a.lerp(b, float(k+1)/n))
			steps += 1
			if steps == 12:
				await settle(0.35)
				counted_down = guide.remaining < start-3.0
	await settle(0.2)
	expect(counted_down, "distance counts down while walking (%.0f m -> less)" % start)
	expect(heard == ["place:pond"] and not guide.active() and Guide.kept.is_empty(), "arrival within %.0f m clears the guide (%s after %d steps)" % [Guide.ARRIVE, heard, steps])
	expect(not guide.trail.visible and app.minimap.guide_target == Vector2.INF, "trail and minimap flag cleared")

## Tracker rows: a click guides to the line's goal, a second click stops.
func clicks() -> void:
	await put(Town.SPAWN)
	Guide.player_stopped = false
	var row: Dictionary = {}
	for r in guide.rows:
		if r.panel.visible and r.key == "fish": row = r
	expect(not row.is_empty() and row.panel.mouse_filter == Control.MOUSE_FILTER_STOP, "fishing line is a clickable row")
	await click(row.panel)
	await settle(0.3)
	expect(guide.active() and guide.target.key == "fish", "clicking the line guides to the nearest fishing spot (%s)" % guide.target.get("name", ""))
	expect(row.far.visible and row.close.visible and row.far.text.ends_with(" m"), "guided row shows the distance %s and a close key" % row.far.text)
	await click(row.panel)
	await settle(0.3)
	expect(not guide.active() and Guide.player_stopped, "clicking it again stops the guide")
	await click(row.panel)
	await settle(0.3)
	expect(guide.active(), "and starts it again")
	await click(row.close)
	await settle(0.3)
	expect(not guide.active(), "the close key stops it")

## The Tab map: list rows and markers drop a pin, the route draws, Tab closes.
func tab_map() -> void:
	app.life.open_map()
	await settle(0.4)
	var view: Control = app.life.map_view
	expect(app.life.mode == "map" and is_instance_valid(view) and view.has_signal("picked"), "Tab map open")
	var list: Control = view.get_parent().get_child(1)
	var bell: Button = list.get_child(6)
	bell.pressed.emit()
	await settle(0.3)
	expect(guide.active() and guide.target.key == "place:bell" and bell.icon != null and TranslationServer.translate("안내 중") in bell.text, "list row starts guiding and wears the pin")
	expect(view.has_destination and view.route.size() > 2 and view.destination == Guide.place("bell").at, "map draws the route and the pin")
	var shop: Dictionary = Guide.place("shop")
	view.picked.emit(shop.at, "shop")
	await settle(0.2)
	expect(guide.target.key == "place:shop" and bell.icon == null, "map marker moves the pin")
	view.picked.emit(Vector2(-40, 0), "")
	await settle(0.2)
	expect(guide.target.key == "pin" and guide.target.at.distance_to(Vector2(-40, 0)) < 0.5, "open ground drops a free pin")
	view.picked.emit(Vector2(-5, -15), "")
	await settle(0.2)
	expect(guide.target.key == "pin" and guide.paths.distance_to_network(guide.target.at) < 0.1, "a pin in the sea snaps to the nearest road")
	app.life.open_map()
	await settle(0.3)
	expect(app.life.mode != "map" and not is_instance_valid(app.village_modal), "Tab again closes the map")

## "길 안내 표시" off hides the trail and the pillar, the minimap keeps the flag.
func setting() -> void:
	expect(guide.active(), "guide active before the setting")
	GameSettings.previewing["route_guide"] = false
	await settle(0.2)
	expect(not guide.trail.visible and not guide.beacon.visible and app.minimap.guide_target == guide.target.at, "setting off: no trail or pillar, minimap flag stays")
	GameSettings.previewing.erase("route_guide")
	await settle(0.2)
	expect(guide.trail.visible and guide.beacon.visible, "setting on: trail and pillar back")
	GameSettings.previewing["reduced_motion"] = true
	await settle(0.4)
	var y: float = guide.gem.position.y
	await settle(0.3)
	expect(absf(guide.gem.position.y-y) < 0.0001 and float(guide.trail_material.get_shader_parameter("calm")) > 0.5, "reduced motion: the gem and the shimmer hold still")
	GameSettings.previewing.erase("reduced_motion")

## A frame of guiding while walking creates no objects and stays cheap.
func frames() -> void:
	await put(Town.SPAWN)
	guide.guide_to(Town.point(Vector2(10.4, 79.6)), "bell", "place:bell")
	var route: PackedVector2Array = guide.route.duplicate()
	var length := 0.0
	for i in route.size()-1: length += route[i].distance_to(route[i+1])
	# Warm caches (heights, materials) over the first stretch, then measure.
	for i in 60: step_along(route, i*0.09)
	var objects := Performance.get_monitor(Performance.OBJECT_COUNT)
	var total := 0
	var worst := 0
	for i in range(60, 600):
		var started := Time.get_ticks_usec()
		step_along(route, minf(i*0.09, length-5.0))
		var spent := Time.get_ticks_usec()-started
		total += spent
		worst = maxi(worst, spent)
	var grown := Performance.get_monitor(Performance.OBJECT_COUNT)-objects
	expect(grown <= 0, "540 guide frames while walking add no objects (%+d)" % grown)
	expect(total/540.0 < 400.0, "guide frame %.0f us on average, worst %d us (route refresh)" % [total/540.0, worst])
	print("GUIDE_FRAME avg_us=%.1f worst_us=%d" % [total/540.0, worst])

## Moves the walker along the route without physics and runs one guide frame.
func step_along(route: PackedVector2Array, distance: float) -> void:
	var left := distance
	var at := route[route.size()-1]
	for i in route.size()-1:
		var seg := route[i].distance_to(route[i+1])
		if left <= seg:
			at = route[i].lerp(route[i+1], left/maxf(seg, 0.001))
			break
		left -= seg
	app.player.global_position = Vector3(at.x, 2.4, at.y)
	guide._process(1.0/60.0)

## The goal outlives the village world (rooms, the field) and comes back with it.
func survive() -> void:
	expect(guide.active() and not Guide.kept.is_empty(), "goal kept while guiding")
	var key: String = guide.target.key
	app.leave_modules()
	expect(Guide.current == null and app.objective.visible and not is_instance_valid(guide.rows_box), "leaving the village hands the tracker back")
	var again: Node3D = Guide.new()
	app.world.add_child(again)
	again.setup(app)
	await settle(0.3)
	expect(Guide.current == again and again.active() and again.target.key == key, "a new village resumes the guide to %s" % key)
	again.stop(true)
	again.leave()
	again.queue_free()
	Guide.player_stopped = false
