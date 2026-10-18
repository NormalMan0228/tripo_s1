extends SceneTree
## Route guide only where the walker can walk (maps/archipelago/walk_route.gd behind
## scripts/guide.gd update_route) on the real village built from recorded server replies
## (tests/ui_stub_api.gd). Headless:
##   godot --headless --path game --script res://tests/guide_walk_check.gd -- --qa
##  - a straight line through a building (the red house, front step to back garden) is
##    blocked and comes from the cache the second time;
##  - six start -> goal routes (home -> town hall, square -> lighthouse pier, square ->
##    observatory, farm -> orange cottage over the bridge, round the red house both ways):
##    every half metre of the drawn line is dry ground or a deck, outside every walled
##    building's footprint (building_placements.json, eaves trimmed), and the off-road
##    legs are clear for a walker-sized capsule; the bridge route crosses the bridge;
##  - cost: a refresh while walking takes <= 2 ms typical (median), a plan is reported.
## Prints GUIDE_WALK_CHECK {...}.
const Main = preload("res://scripts/main.gd")
const Guide = preload("res://scripts/guide.gd")
const Town = preload("res://scripts/town.gd")
const WalkRoute = preload("res://maps/archipelago/walk_route.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const I18n = preload("res://scripts/i18n.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
## Footprints (model bounding boxes) lose this much on every side: roof overhangs,
## porches and steps; the capsule checks of walk_route.gd see the real walls.
const EAVES := 1.8
var failed := false
var app: Node
var guide: Node
var report := {}
var footprints: Array = []

## The red house (10_red_house, centre (-55, 17)): its front step and its back garden.
const FRONT := Vector2(-54.0, 23.6)
const BACK := Vector2(-56.5, 10.4)
const ROUTES := [
	["home_to_town_hall", Vector2(-54.0, 22.8), Vector2(-33.2, 28.4)],
	["square_to_pier", Vector2(-33, 37), Vector2(-4, 82.6)],
	["square_to_observatory", Vector2(-33, 37), Vector2(33.6, -41.2)],
	["farm_over_bridge", Vector2(-18.4, -34.0), Vector2(24, -25.0)],
	["round_red_house", FRONT, BACK],
	["behind_house_to_town_hall", BACK, Vector2(-33.2, 28.4)],
]

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("guide walk check exceeded 240 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func settle(seconds := 0.4) -> void:
	await create_timer(seconds).timeout

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
	guide = Guide.current
	expect(is_instance_valid(guide), "guide module live in the village")
	if not is_instance_valid(guide):
		quit(1)
		return
	for i in 10: await physics_frame
	load_footprints()
	await lines()
	await routes()
	report["passed"] = not failed
	print("GUIDE_WALK_CHECK ", JSON.stringify(report))
	quit(1 if failed else 0)

## Walled buildings (the ones with a door, town.gd DOORS) as [centre, half extents, yaw].
func load_footprints() -> void:
	var walled := {}
	for door in Town.DOORS: walled[door.id] = true
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://maps/archipelago/building_placements.json"))
	for spec in manifest.buildings:
		if not walled.has(spec.id): continue
		var scale := float(spec.get("scale", 1.0))
		var half := Vector2(float(spec.dimensions_m[0]), float(spec.dimensions_m[2]))*scale*0.5-Vector2(EAVES, EAVES)
		footprints.append([str(spec.id), Vector2(float(spec.position[0]), float(spec.position[2])), half, deg_to_rad(float(spec.yaw_degrees))])
	expect(footprints.size() >= 12, "walled building footprints loaded (%d)" % footprints.size())

func inside_building(p: Vector2) -> String:
	for f in footprints:
		var d: Vector2 = p-f[1]
		var c := cos(float(f[3]))
		var s := sin(float(f[3]))
		var local := Vector2(d.x*c-d.y*s, d.x*s+d.y*c)
		if absf(local.x) < f[2].x and absf(local.y) < f[2].y: return f[0]
	return ""

func lines() -> void:
	await put(FRONT)
	guide.guide_to(Town.point(BACK, 0.0), "뒤뜰")
	await settle(0.3)
	var walk = guide.walk
	walk.cache.clear()
	var through: bool = walk.clear(guide, FRONT, BACK)
	expect(not through, "the straight line through the red house is blocked")
	var first: int = walk.queries
	walk.clear(guide, FRONT, BACK)
	expect(walk.queries == first, "the answer comes from the cache the second time")
	guide.stop(false)

func routes() -> void:
	var times: Array = []
	var plans: Array = []
	for spec in ROUTES:
		var label: String = spec[0]
		var from: Vector2 = spec[1]
		var goal: Vector2 = spec[2]
		await put(from)
		guide.guide_to(Town.point(goal, 0.0), label)
		await settle(0.2)
		plans.append(guide.walk.plan_usec)
		guide.update_route(from)
		times.append(guide.walk.route_usec)
		var route: PackedVector2Array = guide.route
		var problems := check_route(route, goal)
		report[label] = {"points": route.size(), "metres": snappedf(guide.remaining, 0.1), "plan_ms": snappedf(guide.walk.plan_usec/1000.0, 0.01), "problems": problems.slice(0, 4)}
		expect(route.size() >= 2 and route[route.size()-1].distance_to(goal) < 0.5, "%s: the line reaches the goal (%d points, %.0f m)" % [label, route.size(), guide.remaining])
		expect(problems.is_empty(), "%s: every half metre walkable %s" % [label, str(problems.slice(0, 3))])
		if label == "farm_over_bridge":
			var crossed := false
			for i in route.size()-1:
				for k in 11:
					var p := route[i].lerp(route[i+1], k/10.0)
					if absf(p.y+36.0) < 2.5 and p.x > -6.0 and p.x < 10.0: crossed = true
			expect(crossed, "farm_over_bridge: the line crosses the bridge")
		if label == "round_red_house":
			expect(route.size() > 2, "a goal behind the house is guided round (%d points)" % route.size())
		# Walking on along the line: refreshes stay cheap.
		var at := from
		for step in 5:
			if route.size() < 2: break
			at = at.move_toward(route[mini(1, route.size()-1)], 0.6)
			await put(at)
			guide.update_route(at)
			times.append(guide.walk.route_usec)
		guide.stop(false)
	times.sort()
	var median: float = times[times.size()/2]/1000.0
	report["route_ms_median"] = snappedf(median, 0.01)
	report["route_ms_max"] = snappedf(times[times.size()-1]/1000.0, 0.01)
	plans.sort()
	report["plan_ms_max"] = snappedf(plans[plans.size()-1]/1000.0, 0.01)
	expect(median <= 2.0, "a refresh takes %.2f ms typical (max %.2f)" % [median, times[times.size()-1]/1000.0])

## Problems along the line: water / no ground, inside a building, a blocked off-road leg.
func check_route(route: PackedVector2Array, goal: Vector2) -> Array:
	var problems: Array = []
	var walked := 0.0
	var total := 0.0
	for i in route.size()-1: total += route[i].distance_to(route[i+1])
	for i in route.size()-1:
		var a := route[i]
		var b := route[i+1]
		var length := a.distance_to(b)
		var steps := maxi(1, ceili(length/0.5))
		for k in range(0, steps+1):
			var d := walked+length*k/steps
			if d < WalkRoute.SKIP_START or total-d < WalkRoute.SKIP_END+0.5: continue
			var p := a.lerp(b, float(k)/steps)
			var y: float = guide.ground_y(p)
			if is_nan(y) or y < WalkRoute.DRY:
				problems.append("water %.1f,%.1f y=%s" % [p.x, p.y, str(y)])
				break
			var house := inside_building(p)
			if house != "":
				problems.append("%s %.1f,%.1f" % [house, p.x, p.y])
				break
		walked += length
	# The off-road legs: walker -> road and road -> goal.
	if route.size() >= 2:
		if not guide.walk.clear(guide, route[0], route[1]): problems.append("blocked first leg")
		if route.size() >= 3 and not guide.walk.clear(guide, route[route.size()-2], goal): problems.append("blocked last leg")
	return problems
