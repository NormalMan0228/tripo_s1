extends SceneTree
## Sitting and lying on crafted pieces in the village, the way rooms do it (rest_seat.gd): a crafted
## rocking chair is a seat and a crafted bed a bed (their library types), placed in the village; E on
## the chair seats the walker (sitting pose, its own physics waiting, the prompt says 일어나기), E gets it
## up where it stood, walking gets it up too, and E on the bed lays it down. --capture saves a
## picture of the walker sitting in the village (artifacts/village-sit.png); run it windowed for it.
##   godot --path game --script res://tests/village_rest_check.gd -- --server=URL [--capture]
const Town = preload("res://scripts/town.gd")

var server := "http://127.0.0.1:8766"
var failures: Array[String] = []
var passes := 0

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if value: passes += 1
	else: failures.append(label)

func _initialize() -> void:
	call_deferred("run")

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
	var stood_at: Vector3 = app.player.position
	await app.village_furniture_event(app.nearest_furniture(), "click")
	await create_timer(0.3).timeout
	var seat: Node = app.seat
	var on_seat := Vector2(app.player.position.x - item.position.x, app.player.position.z - item.position.z).length()
	check(is_instance_valid(seat) and seat.mode == "sit", "E seats the walker on the chair")
	check(on_seat < 0.3 and app.player.visual_only, "it sits on the seat (%.2f m off) and its own walking waits" % on_seat)
	check(is_instance_valid(seat.pose) and seat.pose.mode == "sit", "hips and knees bend like in rooms")
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
	await process_frame
	check(seat.mode == "" and not app.player.visual_only, "E gets it up and walking again")
	check(Vector2(app.player.position.x - stood_at.x, app.player.position.z - stood_at.z).length() < 0.05, "it stands where it stood")
	# Walking off the seat.
	await app.village_furniture_event(app.nearest_furniture(), "click")
	await create_timer(0.2).timeout
	check(seat.mode == "sit", "sits again")
	Input.action_press("move_forward")
	await create_timer(0.3).timeout
	Input.action_release("move_forward")
	check(seat.mode == "", "a movement key gets it up")
	await create_timer(0.3).timeout

	# A bed: lies along it, and gets up on E.
	var bed := await craft_and_place(app, "침대", 4, 7)
	check(not bed.is_empty() and str(app.loaded[bed].rest) == "lie", "a crafted bed stands in the village as a bed (%s)" % [str(app.loaded[bed].rest) if app.loaded.has(bed) else "not placed"])
	if bed.is_empty(): finish(); return
	app.player.position = Town.furniture_point(4, 8.4)
	await create_timer(0.4).timeout
	check("눕기" in prompt_of(app), "next to it the prompt offers to lie down (%s)" % prompt_of(app))
	await app.village_furniture_event(bed, "click")
	await create_timer(0.3).timeout
	check(seat.mode == "lie" and absf(app.player.basis.y.y) < 0.2, "E lays the walker down on the bed")
	key(app, KEY_ESCAPE)
	await process_frame
	check(seat.mode == "" and app.player.basis.y.y > 0.99, "Esc gets it up again")
	finish()
