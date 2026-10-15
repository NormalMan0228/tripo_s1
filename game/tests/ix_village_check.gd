extends SceneTree
## ISS-1 in the island village (S-WP6, S-WP7), against a QA server: E on the map's bench, café chair,
## picnic table and beach lounger really seats (or lays) the walker on the prop's measured socket at
## its real yaw and height, E gets it up onto a free spot; no tick moves the body more than 0.08 m.
## Talking to a villager first turns both toward each other: the dialogue opens once the villager
## faces the walker within 20 degrees, or after 0.4 s at most.
##   godot --path game --script res://tests/ix_village_check.gd -- --server=URL
const Driver = preload("res://scripts/ix/ix_driver.gd")
const IxSources = preload("res://scripts/ix/ix_sources.gd")
const IxMath = preload("res://scripts/ix/ix_math.gd")
const Fx = preload("res://scripts/fx.gd")

var server := preload("res://tests/qa_server.gd").url()
var failures: Array[String] = []
var passes := 0
var report := {}
var watch: Node3D
var watch_last := Vector3.INF
var biggest := 0.0

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if value: passes += 1
	else: failures.append(label)

func _initialize() -> void:
	call_deferred("run")
	physics_frame.connect(_watch)

func _watch() -> void:
	if not is_instance_valid(watch): return
	var busy: bool = is_instance_valid(watch.get("ix")) and watch.ix.busy()
	if busy and watch_last.is_finite(): biggest = maxf(biggest, watch.global_position.distance_to(watch_last))
	watch_last = watch.global_position if busy else Vector3.INF

func wait_until(condition: Callable, seconds := 20.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

func finish() -> void:
	print("IX_VILLAGE_CHECK ", JSON.stringify({"ok": failures.is_empty(), "passed": passes, "failures": failures, "report": report}))
	quit(0 if failures.is_empty() else 1)

func key(app: Node, code: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.pressed = true
	app._unhandled_input(event)

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	var app = load("res://scripts/main.gd").new()
	root.add_child(app)
	await process_frame
	await wait_until(func(): return not app.busy and app.screen == "login", 60.0)
	for _attempt in 3:
		await app.authenticate(true, server, "ixv_" + str(Time.get_ticks_usec() % 100000000), "Local-ix-qa-1!", "")
		if app.screen == "village": break
		await create_timer(0.5).timeout
	check(app.screen == "village", "registered and in the village (%s)" % app.screen)
	if app.screen != "village":
		finish()
		return
	await wait_until(func(): return is_instance_valid(app.town) and not app.town.props.is_empty(), 30.0)
	watch = app.player
	for id in ["26_bench", "32_cafe_chair", "25_picnic_table", "29_beach_lounger"]:
		await prop_case(app, id)
	await every_picnic_seat(app)
	await rebuilt_while_seated(app)
	watch = app.player
	await talk_case(app)
	check(biggest <= 0.08, "no tick moves the walker more than 0.08 m (max %.3f m)" % biggest)
	finish()

func prop_case(app: Node, id: String) -> void:
	var entries: Array = app.town.props.filter(func(e): return e.id == id)
	check(not entries.is_empty(), "%s stands in the village" % id)
	if entries.is_empty(): return
	var entry: Dictionary = entries[0]
	var node: Node3D = entry.node
	var sockets := IxSources.resolve_all(IxSources.for_node(node))
	var valid := sockets.filter(func(s): return s.valid)
	check(not valid.is_empty(), "%s has valid sockets at its yaw and scale (%d)" % [id, valid.size()])
	if valid.is_empty(): return
	# Stand on the best approach spot's side, a step further out.
	var s: Dictionary = valid[0]
	# From beside the seat (a table may stand in front of it), as a walker coming by would.
	var a: Vector3 = s.approach[0].pos
	var start: Vector3 = Vector3(s.origin.x, a.y, s.origin.z) + (s.basis as Basis).x * 1.1 + (s.basis as Basis).z * 0.3
	app.player.global_position = Vector3(start.x, a.y + 0.3, start.z)
	app.player.velocity = Vector3.ZERO
	await create_timer(0.5).timeout
	var shown: int = Fx.played
	app.town.use_prop(app, entry)
	check(Fx.played > shown, "%s: using it plays a visible cue (%d)" % [id, Fx.played - shown])
	var seat: Node = app.seat
	var held := await wait_until(func(): return is_instance_valid(seat) and is_instance_valid(seat.driver) and seat.driver.state == Driver.HOLD, 6.0)
	var want := "lie" if id == "29_beach_lounger" else "sit"
	check(held and seat.mode == want, "E on %s %s the walker (%s)" % [id, "lays down" if want == "lie" else "seats", (str(seat.driver.phases) + " " + seat.driver.why + " from " + str(start) + " to " + str(seat.driver.approach.get("pos", "")) + " at " + str(app.player.global_position)) if is_instance_valid(seat) and is_instance_valid(seat.driver) else "no driver"])
	if not held:
		if is_instance_valid(seat): seat.stand(false)
		await create_timer(0.5).timeout
		return
	var d: Node = seat.driver
	report[id] = {"height": snappedf(float(d.socket.height), 0.001), "yaw_deg": snappedf(rad_to_deg(float(d.socket.yaw)), 0.1), "prop_yaw": snappedf(node.rotation_degrees.y, 0.1), "socket": d.socket.id}
	await create_timer(0.5).timeout
	key(app, KEY_E)
	var up := await wait_until(func(): return not d.busy(), 3.0)
	check(up and not seat.resting() and not app.player.visual_only, "E gets the walker up from %s" % id)
	check(d.spot_free(app.player.global_position), "%s: it stands on a free spot" % id)
	await create_timer(0.4).timeout

## Every seat of the picnic table, from behind its bench: the walker sits on that socket at the
## model's real (turned) bench yaw and gets up again.
func every_picnic_seat(app: Node) -> void:
	var entries: Array = app.town.props.filter(func(e): return e.id == "25_picnic_table")
	if entries.is_empty(): return
	var node: Node3D = entries[0].node
	var IxData = load("res://scripts/ix/ix_data.gd")
	var authored := {}
	for r in IxData.PROP_MODELS["25_picnic_table"].sockets: authored[r.id] = float(r.yaw)
	var sockets := IxSources.resolve_all(IxSources.for_node(node)).filter(func(s): return s.valid)
	var seated := 0
	for s in sockets:
		var a: Vector3 = s.approach[0].pos
		var away := Vector3(a.x - s.origin.x, 0, a.z - s.origin.z).normalized()
		app.player.global_position = Vector3(a.x, a.y + 0.3, a.z) + away * 0.4
		app.player.velocity = Vector3.ZERO
		await create_timer(0.4).timeout
		var started: bool = app.village_seat().start({"node": node, "hint": "sit", "socket_id": s.id})
		var d: Node = app.seat.driver
		var held := false
		if started: held = await wait_until(func(): return d.state == Driver.HOLD, 6.0)
		var want := node.global_rotation.y + deg_to_rad(float(authored.get(s.id, 0.0)))
		var error := absf(angle_difference(want, IxMath.yaw_of(app.player.facing)))
		check(held and str(d.socket.id) == str(s.id) and error < deg_to_rad(3.0), "picnic table %s: seated on it facing along the bench's real yaw (%.1f deg off, %s %s)" % [s.id, rad_to_deg(error), str(d.phases), d.why])
		if held: seated += 1
		app.seat.stand()
		await wait_until(func(): return not d.busy(), 3.0)
		await create_timer(0.3).timeout
	report["picnic_seats"] = seated
	check(seated == 4, "all four picnic seats seat the walker (%d)" % seated)

## The village world is rebuilt while the walker sits (a visit, going home, signing in again): the
## seat lets go, E and Esc work again, and the new walker sits as before.
func rebuilt_while_seated(app: Node) -> void:
	var entries: Array = app.town.props.filter(func(e): return e.id == "26_bench")
	if entries.is_empty(): return
	var node: Node3D = entries[0].node
	var s: Dictionary = IxSources.resolve_all(IxSources.for_node(node)).filter(func(x): return x.valid)[0]
	var a: Vector3 = s.approach[0].pos
	app.player.global_position = Vector3(a.x, a.y + 0.3, a.z)
	await create_timer(0.4).timeout
	app.town.use_prop(app, entries[0])
	var old_seat: Node = app.seat
	var held := await wait_until(func(): return old_seat.driver.state == Driver.HOLD, 6.0)
	check(held, "seated on the bench before the rebuild")
	await app.enter_village()
	await wait_until(func(): return app.screen == "village" and is_instance_valid(app.player) and is_instance_valid(app.town) and not app.town.props.is_empty(), 30.0)
	await create_timer(0.5).timeout
	var resting: bool = is_instance_valid(app.seat) and app.seat.resting()
	check(app.screen == "village" and not resting and not (is_instance_valid(old_seat) and old_seat.resting()), "after the rebuild nothing is seated (seat %s)" % ("kept" if is_instance_valid(app.seat) else "made fresh"))
	check(Driver.claims.is_empty(), "and no seat stays claimed (%s)" % str(Driver.claims))
	key(app, KEY_E)
	await create_timer(0.2).timeout
	check(not (is_instance_valid(app.seat) and app.seat.resting()), "E is not taken by a stale seat")
	entries = app.town.props.filter(func(e): return e.id == "26_bench")
	if entries.is_empty(): return
	node = entries[0].node
	s = IxSources.resolve_all(IxSources.for_node(node)).filter(func(x): return x.valid)[0]
	a = s.approach[0].pos
	app.player.global_position = Vector3(a.x, a.y + 0.3, a.z)
	await create_timer(0.4).timeout
	app.town.use_prop(app, entries[0])
	var again := await wait_until(func(): return is_instance_valid(app.seat) and app.seat.driver.state == Driver.HOLD, 6.0)
	check(again and app.seat.driver.actor == app.player, "the new walker sits on the bench again")
	key(app, KEY_E)
	var up := await wait_until(func(): return not app.seat.driver.busy(), 3.0)
	check(up and not app.seat.resting(), "and E gets it up")
	await create_timer(0.3).timeout

func talk_case(app: Node) -> void:
	var npc: Node3D
	for n in app.npcs:
		if is_instance_valid(n) and n.visible and "turn_target" in n:
			npc = n
			break
	check(npc != null, "a villager to talk to")
	if npc == null: return
	# Behind the villager, which looks the other way.
	var away := Vector3(sin(npc.rotation.y), 0, cos(npc.rotation.y))
	app.player.global_position = npc.global_position - away * 1.4 + Vector3(0, 0.3, 0)
	await create_timer(0.4).timeout
	npc.rotation.y = npc.rotation.y + PI
	npc.turn_target = npc.rotation.y
	await physics_frame
	var started := Time.get_ticks_msec()
	app.talk_after_turn(npc)
	var opened := await wait_until(func(): return is_instance_valid(app.village_modal), 2.0)
	var took := (Time.get_ticks_msec() - started) / 1000.0
	var to: Vector3 = app.player.global_position - npc.global_position
	var error := rad_to_deg(absf(angle_difference(npc.rotation.y, atan2(to.x, to.z))))
	report["talk"] = {"seconds": took, "facing_error_deg": error}
	check(opened and took <= 0.55, "the dialogue opens after the turn, in %.2f s" % took)
	check(error <= 20.0 or took >= 0.38, "the villager faces the walker when it opens (%.0f deg)" % error)
	app.close_village_modal()
