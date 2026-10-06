extends SceneTree
## Rendered route-guide tour (scripts/guide.gd) against the QA server: logs in, picks
## the lighthouse bell on the Tab map (across the long bridge), walks part of the way
## with the movement keys following the guided route, then on to the arrival.
## Captures artifacts/guide-objective.png (the first objective guided), guide-map.png, guide-start.png, guide-walking.png and
## guide-arrive.png (with "-night" before .png when --hour is 19 or later).
##   powershell -File tools/test.ps1 -SkipServerTests -ClientScript guide_tour -Capture -Hour 12
const Main = preload("res://scripts/main.gd")
const Guide = preload("res://scripts/guide.gd")
const I18n = preload("res://scripts/i18n.gd")
var failed := false
var app: Node3D
var suffix := ""

func _initialize() -> void:
	call_deferred("run")
	create_timer(300).timeout.connect(func():
		push_error("guide tour exceeded 300 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func capture(name: String) -> void:
	for i in 4: await process_frame
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/guide-%s%s.png" % [name, suffix]))

func release() -> void:
	for action in ["move_left","move_right","move_forward","move_back","run"]: Input.action_release(action)

## Walks the guided route with the movement keys for `metres` (or to the arrival).
func walk(guide: Node, metres: float) -> float:
	var walked := 0.0
	var last := Vector2(app.player.position.x, app.player.position.z)
	var frames := 0
	var mark := last
	var since := 0
	while guide.active() and walked < metres and frames < 60*60:
		var here := Vector2(app.player.position.x, app.player.position.z)
		walked += here.distance_to(last)
		last = here
		# A bot is no player: pressed against a post or a wall, it hops a step on.
		since += 1
		if here.distance_to(mark) > 0.4:
			mark = here
			since = 0
		elif since > 45:
			var hop := lookahead(guide.route, 1.5)
			app.player.global_position = Vector3(hop.x, guide.ground_y(hop)+0.15, hop.y)
			app.player.velocity = Vector3.ZERO
			since = 0
		var aim := lookahead(guide.route, 1.3)
		var d := (aim-here).normalized()
		release()
		Input.action_press("run")
		if d.x > 0.05: Input.action_press("move_right", d.x)
		if d.x < -0.05: Input.action_press("move_left", -d.x)
		if d.y > 0.05: Input.action_press("move_back", d.y)
		if d.y < -0.05: Input.action_press("move_forward", -d.y)
		await physics_frame
		frames += 1
	release()
	return walked

## The point `ahead` metres along the route from its start (the walker).
static func lookahead(route: PackedVector2Array, ahead: float) -> Vector2:
	var left := ahead
	for i in route.size()-1:
		var seg := route[i].distance_to(route[i+1])
		if left <= seg: return route[i].lerp(route[i+1], left/maxf(seg, 0.001))
		left -= seg
	return route[route.size()-1]

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--hour=") and float(arg.trim_prefix("--hour=")) >= 19.0: suffix = "-night"
	I18n.setup()
	app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	await app.authenticate(true, "http://127.0.0.1:8766", "guide_"+str(Time.get_ticks_msec()), "Guide-tour-password-123", "")
	await create_timer(2.0).timeout
	expect(app.screen == "village", "village after login")
	var guide: Node = Guide.current
	expect(is_instance_valid(guide) and guide.active(), "first objective guided on arrival (%s)" % (guide.target.get("name", "") if is_instance_valid(guide) else ""))
	if not is_instance_valid(guide):
		quit(1)
		return
	await capture("objective")
	# Tab map: pick the lighthouse bell from the list.
	app.life.open_map()
	await create_timer(0.4).timeout
	var list: Control = app.life.map_view.get_parent().get_child(1)
	(list.get_child(6) as Button).pressed.emit()
	await create_timer(0.9).timeout
	expect(guide.target.get("key", "") == "place:bell" and app.life.map_view.route.size() > 2, "bell picked on the map, route drawn")
	await capture("map")
	app.life.open_map()
	await create_timer(0.6).timeout
	expect(app.life.mode != "map", "Tab closed the map")
	await capture("start")
	var start: float = guide.remaining
	var walked := await walk(guide, 55.0)
	await create_timer(0.5).timeout
	expect(walked > 35.0 and guide.remaining < start-30.0, "walked %.0f m along the trail, %.0f m left" % [walked, guide.remaining])
	await capture("walking")
	var heard := []
	guide.arrived.connect(func(key): heard.append(key))
	await walk(guide, 400.0)
	await create_timer(0.25).timeout
	await capture("arrive")
	expect(heard == ["place:bell"] and not guide.active(), "arrived at the bell, guide cleared")
	app.queue_free()
	await create_timer(0.5).timeout
	print("GUIDE_TOUR ", "FAIL" if failed else "OK")
	quit(1 if failed else 0)
