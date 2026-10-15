extends SceneTree
## Sitting and lying on crafted pieces in the village, the way rooms do it (rest_seat.gd over the ISS-1
## driver): a crafted rocking chair is a seat and a crafted bed a bed (their library types), placed in
## the village; E on the chair walks the walker up, turns it and sits it down on the derived seat point
## (sitting pose, its own physics waiting, the prompt says 일어나기), E gets it up onto the exit point
## facing out, walking gets it up too, and E on the bed lays it down with the body upright. No frame
## moves the body more than 0.08 m. --capture saves a picture of the walker sitting in the village
## (artifacts/village-sit.jpg); run it windowed for it.
##   godot --path game --script res://tests/village_rest_check.gd -- --server=URL [--capture]
const Town = preload("res://scripts/town.gd")
const Driver = preload("res://scripts/ix/ix_driver.gd")
const IxRig = preload("res://scripts/ix/ix_rig.gd")
const IxMath = preload("res://scripts/ix/ix_math.gd")
const IxSources = preload("res://scripts/ix/ix_sources.gd")
const Residents = preload("res://scripts/residents.gd")

var server := preload("res://tests/qa_server.gd").url()
var failures: Array[String] = []
## The biggest body step in one physics tick while a seat had the walker.
var biggest_step := 0.0
var watch_from: Node3D
var watch_last := Vector3.INF
var biggest_at := ""
var passes := 0

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if value: passes += 1
	else: failures.append(label)

func _initialize() -> void:
	call_deferred("run")
	physics_frame.connect(_watch)

func _watch() -> void:
	if not is_instance_valid(watch_from): return
	var busy: bool = is_instance_valid(watch_from.get("ix")) and watch_from.ix.busy()
	if busy and watch_last.is_finite() and watch_from.global_position.distance_to(watch_last) > biggest_step:
		biggest_step = watch_from.global_position.distance_to(watch_last)
		biggest_at = "%s/%d %.2f fast %s on %s: %s -> %s" % [watch_from.ix.state_name(), watch_from.ix.lie_phase, watch_from.ix.phase_t, str(watch_from.ix.exit_fast), str(watch_from.ix.kind), str(watch_last), str(watch_from.global_position)]
	watch_last = watch_from.global_position if busy else Vector3.INF

func wait_until(condition: Callable, seconds := 20.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

func finish() -> void:
	Input.action_release("move_forward")
	print("VILLAGE_REST_CHECK ", JSON.stringify({"ok": failures.is_empty(), "passed": passes, "failures": failures}))
	quit(0 if failures.is_empty() else 1)

func key(app: Node, code: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.pressed = true
	app._unhandled_input(event)

## A still fixture craft (proxy shapes, no paid call), placed in the village at (x, z).
func craft_and_place(app: Node, prompt: String, x: float, z: float, motion := "static") -> String:
	var queued: Dictionary = await app.api.post("/v1/studio/jobs", app.api.mutation({"prompt": prompt, "geometry": "proxy", "designer": "fixture", "motion": motion}))
	var id := ""
	for _i in 60:
		var job: Dictionary = await app.api.request("/v1/studio/jobs/" + str(queued.get("data", {}).get("id", "")))
		if job.ok and job.data.state == "ready": id = str(job.data.object_id); break
		await create_timer(0.5).timeout
	if id.is_empty(): return ""
	await app.refresh_inventory()
	for i in app.me.objects.size():
		if app.me.objects[i].id == id: app.select_object(i)
	await app.begin_place()
	if is_instance_valid(app.preview):
		app.preview.position = Town.furniture_point(x, z)
		await app.place_preview()
	await wait_until(func(): return app.loaded.has(id) and is_instance_valid(app.loaded[id]))
	return id if app.loaded.has(id) else ""

func prompt_of(app: Node) -> String:
	return str(app.hint.get_meta("prompt", "")) if is_instance_valid(app.hint) else ""

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	# The residents follow the wall clock (residents.gd) and the pond beside these spots is one of their
	# leisure spots: a villager strolling by takes the E prompt first (main.gd puts people before
	# furniture), so the prompt checks failed at some hours. Everyone is kept out of their plan here.
	for entry in Residents.RESIDENTS: Residents.hold(str(entry.id), true)
	var app = load("res://scripts/main.gd").new()
	root.add_child(app)
	await process_frame
	await wait_until(func(): return not app.busy and app.screen == "login", 60.0)
	for _attempt in 3:
		await app.authenticate(true, server, "rst_" + str(Time.get_ticks_usec() % 100000000), "Local-rest-qa-1!", "")
		if app.screen == "village": break
		await create_timer(0.5).timeout
	check(app.screen == "village", "registered and in the village (%s)" % app.screen)
	if app.screen != "village": finish(); return

	var stool := await craft_and_place(app, "흔들의자", 4, 3, "dynamic")
	check(not stool.is_empty() and str(app.loaded[stool].rest) == "sit", "a crafted rocking chair stands in the village as a seat")
	if stool.is_empty(): finish(); return
	var item: Node3D = app.loaded[stool]
	app.player.position = Town.furniture_point(4, 4.2)
	await create_timer(0.4).timeout
	check("앉기" in prompt_of(app), "next to it the prompt offers to sit (%s)" % prompt_of(app))
	var seat: Node
	var item_size: Vector3 = item.get_meta("size", Vector3.ONE)
	watch_from = app.player
	await app.village_furniture_event(app.nearest_furniture(), "click")
	seat = app.seat
	check(is_instance_valid(seat) and seat.resting(), "E starts the walk up to the chair")
	var held := await wait_until(func(): return is_instance_valid(seat.driver) and seat.driver.state == Driver.HOLD, 4.0)
	check(held and seat.mode == "sit", "it walks up, turns and sits down on the chair (%s)" % str(seat.driver.phases if is_instance_valid(seat.driver) else []))
	if not held: finish(); return
	var driver: Node = seat.driver
	var m: Dictionary = IxRig.measure(app.player.hand_skeleton, app.player.visual)
	var hold_root: Vector3 = IxMath.hold_root(IxSources.point_now(driver.entry), float(driver.socket.yaw), m.seat_contact)
	var on_seat := Vector2(app.player.position.x - item.position.x, app.player.position.z - item.position.z).length()
	check(app.player.global_position.distance_to(hold_root) < 0.06 and on_seat < maxf(item_size.x, item_size.z) * 0.6 and app.player.visual_only,
		"it holds on the derived seat point (%.3f m) and its own walking waits" % app.player.global_position.distance_to(hold_root))
	check(float(driver.socket.height) > 0.25 and float(driver.socket.height) < 0.7 and str(driver.socket.source) != "bbox", "the seat height comes from the chair itself (%.2f m, %s)" % [float(driver.socket.height), driver.socket.source])
	check(is_instance_valid(seat.pose) and seat.pose.mode == "sit", "hips and knees bend like in rooms")
	await create_timer(0.25).timeout
	check("일어나기" in prompt_of(app), "the prompt says how to get up (%s)" % prompt_of(app))
	if "--capture" in OS.get_cmdline_user_args():
		await create_timer(1.2).timeout
		await RenderingServer.frame_post_draw
		var image := root.get_texture().get_image()
		image.resize(800, int(800.0 * image.get_height() / image.get_width()), Image.INTERPOLATE_LANCZOS)
		image.save_jpg("res://../artifacts/village-sit.jpg", 0.85)
		print("CAPTURE ", ProjectSettings.globalize_path("res://../artifacts/village-sit.jpg"))
	await create_timer(0.3).timeout
	check(seat.mode == "sit", "it stays seated while nothing is pressed")
	key(app, KEY_E)
	var up := await wait_until(func(): return not driver.busy(), 2.0)
	check(up and seat.mode == "" and not app.player.visual_only, "E gets it up and walking again")
	var off := Vector2(app.player.position.x - driver.exit_point.x, app.player.position.z - driver.exit_point.z).length()
	check(off < 0.05, "it stands at the exit point (%.3f m)" % off)
	check(absf(angle_difference(IxMath.yaw_of(app.player.facing), float(driver.socket.yaw))) < deg_to_rad(5.0), "facing out of the seat")
	# Walking off the seat.
	await app.village_furniture_event(app.nearest_furniture(), "click")
	held = await wait_until(func(): return driver.state == Driver.HOLD, 4.0)
	check(held and seat.mode == "sit", "sits again")
	Input.action_press("move_forward")
	up = await wait_until(func(): return not driver.busy(), 2.0)
	await create_timer(0.2).timeout
	Input.action_release("move_forward")
	check(up and seat.mode == "", "a movement key gets it up")
	await create_timer(0.3).timeout

	# A bed: sits on its edge and lies back along it, the body itself upright; Esc gets it up.
	# Off the south road (big pieces may not stand on a road, build_rules.gd village_problem).
	var bed := await craft_and_place(app, "침대", 8, 7)
	check(not bed.is_empty() and str(app.loaded[bed].rest) == "lie", "a crafted bed stands in the village as a bed (%s)" % [str(app.loaded[bed].rest) if app.loaded.has(bed) else "not placed"])
	if bed.is_empty(): finish(); return
	app.player.position = Town.furniture_point(8, 8.4)
	await create_timer(0.4).timeout
	check("눕기" in prompt_of(app), "next to it the prompt offers to lie down (%s)" % prompt_of(app))
	await app.village_furniture_event(bed, "click")
	held = await wait_until(func(): return driver.state == Driver.HOLD, 5.0)
	check(held and seat.mode == "lie" and app.player.global_basis.y.y > 0.99, "E lays the walker down on the bed, the body upright (%s)" % str(driver.phases))
	if held:
		var bed_root: Vector3 = IxMath.hold_root(IxSources.point_now(driver.entry) + Vector3(0, IxRig.LIE_LIFT, 0), driver.lie_yaw, m.pelvis)
		check(app.player.global_position.distance_to(bed_root) < 0.06, "the hips lie on the mattress point (%.3f m)" % app.player.global_position.distance_to(bed_root))
	key(app, KEY_ESCAPE)
	up = await wait_until(func(): return not driver.busy(), 2.5)
	check(up and seat.mode == "" and app.player.global_basis.y.y > 0.99 and not app.player.visual_only, "Esc gets it up again")
	check(biggest_step <= 0.08, "no frame jump while sitting, lying or getting up (max %.3f m, %s)" % [biggest_step, biggest_at])
	finish()
