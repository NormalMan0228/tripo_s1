extends SceneTree
## Free turning and shape edits end to end: crafted pieces turned to non-quarter angles and
## reshaped (모양 바꾸기) in the village and in the home, reloaded from the server, turned
## again in place, and read by a visitor; checks the assembled models' transforms and sizes.
##   godot --path game --script res://tests/object_transform_check.gd -- --mute --qa --server=http://127.0.0.1:8812 [--capture]
const ObjectTransform = preload("res://scripts/object_transform.gd")
const Loader = preload("res://scripts/model_loader.gd")
const TownLayout = preload("res://scripts/town.gd")
var server := "http://127.0.0.1:8766"
var failures: Array[String] = []

func check(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void: call_deferred("run")

func capture(path: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	# Windows pop in over a quarter second.
	await create_timer(0.6).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../artifacts/" + path)

func key(code: Key, shift := false, alt := false, ctrl := false) -> InputEventKey:
	var event := InputEventKey.new()
	event.pressed = true; event.keycode = code; event.physical_keycode = code
	event.shift_pressed = shift; event.alt_pressed = alt; event.ctrl_pressed = ctrl
	return event

func wheel(up: bool) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.pressed = true
	event.button_index = MOUSE_BUTTON_WHEEL_UP if up else MOUSE_BUTTON_WHEEL_DOWN
	return event

func near(a: Vector3, b: Vector3, tolerance := 0.01) -> bool:
	return (a - b).abs().length() <= tolerance * maxf(1.0, b.length())

func same_angle(node: Node3D, degrees: float) -> bool:
	return absf(angle_difference(node.rotation.y, deg_to_rad(degrees))) < 0.01

## The frame, size meta and footing all follow the shape. The frame's offset is what puts the
## model's built bounds on the floor and in the middle (asset_assembly / model_loader), so it
## must scale with the frame for the piece to stay standing on the floor.
func shaped(node: Node3D, shape: Dictionary, label: String) -> void:
	check(is_instance_valid(node), label + ": model present")
	if not is_instance_valid(node): return
	var frame := ObjectTransform.frame_of(node)
	var base: Dictionary = node.get_meta("shape_base", {})
	var k := ObjectTransform.factors(shape)
	check(frame != null and not base.is_empty(), label + ": shape frame found")
	if frame == null or base.is_empty(): return
	check(near(frame.scale, base.scale * k), label + ": frame scale %s = base x %s" % [str(frame.scale), str(k)])
	check(near(node.get_meta("size"), base.size * k.abs()), label + ": size meta %s" % str(node.get_meta("size")))
	check((frame.scale.x < 0.0) == bool(shape.get("mirror", false)), label + ": mirror sign")
	check(near(frame.position, base.position * k, 0.001), label + ": stays on the floor (offset %s)" % str(frame.position))

func listed(objects: Array, id: String) -> Dictionary:
	for obj in objects:
		if str(obj.id) == id: return obj
	return {}

func craft(api: Node, prompt: String) -> String:
	var queued: Dictionary = await api.post("/v1/studio/jobs", api.mutation({"prompt": prompt, "motion": "static", "geometry": "proxy", "designer": "fixture"}))
	if not queued.ok: return ""
	for attempt in 80:
		var job: Dictionary = await api.request("/v1/studio/jobs/" + queued.data.id)
		if job.ok and job.data.state == "ready": return str(job.data.object_id)
		await create_timer(0.25).timeout
	return ""

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	var app = load("res://scripts/main.gd").new()
	root.add_child(app)
	await process_frame
	var username := "shape_" + str(Time.get_ticks_usec() % 100000000)
	# The very first request of a fresh window can miss the server; one retry covers it.
	for attempt in 2:
		await app.authenticate(true, server, username, "Shape-qa-password-1", "")
		if app.screen == "village": break
		await create_timer(1.0).timeout
	check(app.screen == "village", "village opened (%s)" % app.screen)
	if app.screen != "village": finish(); return
	var village_id := await craft(app.api, "wooden chest")
	var room_id := await craft(app.api, "wooden chest")
	check(not village_id.is_empty() and not room_id.is_empty(), "two crafted pieces")
	if village_id.is_empty() or room_id.is_empty(): finish(); return
	await app.refresh_inventory()

	# ---------------------------------------------------------------- village: shape
	for i in app.me.objects.size():
		if app.me.objects[i].id == village_id: app.objects_list.select(i); app.select_object(i)
	for attempt in 40:
		if is_instance_valid(app.inspect_model): break
		await create_timer(0.1).timeout
	if not app.right.get_parent().visible: app.toggle_drawer()
	app.open_shape_panel()
	var panel = app.shape_panel
	check(is_instance_valid(panel), "bag opens the shape window")
	if not is_instance_valid(panel): finish(); return
	check(panel.save_button.disabled, "nothing to save before a change")
	var village_shape := {"width": 150, "depth": 90, "height": 80, "scale": 120, "mirror": true}
	for axis in ObjectTransform.AXES: panel.sliders[axis].value = village_shape[axis]
	panel.mirror_button.button_pressed = true
	check(not panel.save_button.disabled, "a change can be saved")
	shaped(app.inspect_model, village_shape, "village bag preview (live)")
	check(panel.size_readout.text.ends_with(" m"), "size readout shows metres: " + panel.size_readout.text)
	await capture("object-shape-village.png")
	await panel.save()
	check(not is_instance_valid(app.shape_panel) or app.shape_panel.is_queued_for_deletion(), "saving closes the window")
	var saved: Dictionary = listed(app.me.objects, village_id).get("shape", {})
	check(ObjectTransform.same(saved, village_shape) and int(saved.get("version", 0)) == 1, "bag list holds the saved shape")
	var me: Dictionary = await app.api.request("/v1/me")
	check(ObjectTransform.same(listed(me.data.objects, village_id).get("shape"), village_shape), "server keeps the shape")

	# ---------------------------------------------------------------- village: free turning
	await app.begin_place()
	check(is_instance_valid(app.preview) and is_instance_valid(app.turn_hud), "placing shows the ghost and the turn bar")
	if not is_instance_valid(app.preview): finish(); return
	shaped(app.preview, village_shape, "village ghost")
	for event in [key(KEY_R), key(KEY_R), key(KEY_R, false, true), key(KEY_R, false, false, true), wheel(true), key(KEY_R, true), key(KEY_R)]:
		app._unhandled_input(event)
	check(app.preview_rotation == 37, "R 15°, Alt/Ctrl+R 1°, wheel 5°, Shift+R back: %d°" % app.preview_rotation)
	check(app.turn_readout.text == "37°", "turn bar reads " + app.turn_readout.text)
	await create_timer(0.6).timeout
	check(same_angle(app.preview, 37), "ghost eases to 37°")
	await capture("object-turn-village.png")
	app.preview.position = TownLayout.furniture_point(4, 3)
	await app.place_preview()
	check(not is_instance_valid(app.turn_hud), "turn bar leaves with the ghost")
	check(app.loaded.has(village_id) and same_angle(app.loaded[village_id], 37), "placed at 37°")
	shaped(app.loaded.get(village_id), village_shape, "village placed")
	await app.refresh_inventory()
	check(app.loaded.has(village_id) and same_angle(app.loaded[village_id], 37), "37° survives a reload")
	shaped(app.loaded.get(village_id), village_shape, "village reloaded")
	var collision_size := Vector3.ZERO
	for body in app.loaded[village_id].get_children():
		if body is StaticBody3D: collision_size = (body.get_child(0).shape as BoxShape3D).size
	check(near(collision_size, app.loaded[village_id].get_meta("size")), "collision box follows the shape")

	# ---------------------------------------------------------------- village: turn again in place
	for i in app.me.objects.size():
		if app.me.objects[i].id == village_id: app.select_object(i)
	var spot: Vector3 = app.loaded[village_id].position
	await app.begin_place()
	check(app.preview_moving == village_id and is_instance_valid(app.preview) and app.preview.position.distance_to(spot) < 0.01, "a placed piece is picked up where it stands")
	check(not app.loaded[village_id].visible, "its old copy hides meanwhile")
	app._unhandled_input(key(KEY_R, true))
	app._unhandled_input(key(KEY_R, true, true))
	check(app.preview_rotation == 21, "turned back to 21°: %d" % app.preview_rotation)
	check(app.placement_problem().is_empty(), "its own spot is free for it: " + app.placement_problem())
	await app.place_preview()
	me = await app.api.request("/v1/me")
	var moved: Dictionary = listed(me.data.objects, village_id)
	check(int(moved.get("rotation", -1)) == 21 and moved.get("state") == "placed", "server keeps 21° (no retrieve)")
	check(app.loaded.has(village_id) and same_angle(app.loaded[village_id], 21) and app.loaded[village_id].visible, "village shows the turned piece")

	# ---------------------------------------------------------------- visitor sees it
	var guest = load("res://scripts/api.gd").new()
	root.add_child(guest)
	guest.base_url = server
	var guest_login: Dictionary = await guest.post("/v1/auth/register", {"username": "g" + username, "password": "Shape-qa-password-1"})
	var invite: Dictionary = await app.api.post("/v1/social/invites", app.api.mutation({"username": "g" + username, "kind": "village"}))
	if guest_login.ok and invite.ok:
		guest.token = guest_login.data.token
		var accepted: Dictionary = await guest.post("/v1/social/invites/" + str(invite.data.id) + "/accept", guest.mutation())
		var space: Dictionary = await guest.post("/v1/social/presence", {"x": 1, "z": 2})
		var seen: Dictionary = listed(space.data.get("village", {}).get("objects", []), village_id) if space.ok else {}
		check(accepted.ok and int(seen.get("rotation", -1)) == 21 and ObjectTransform.same(seen.get("shape"), village_shape), "visitor list carries turn and shape")
		var host_token: String = app.api.token
		app.api.token = guest.token
		var visited: Node3D = await app.load_object(seen, "/v1/social/village/objects/")
		app.api.token = host_token
		shaped(visited, village_shape, "visitor's copy")
		if is_instance_valid(visited): visited.free()
	else: check(false, "visitor account and invite")
	var token: String = app.api.token
	app.queue_free()
	await process_frame

	# ---------------------------------------------------------------- footprint maths
	check(ObjectTransform.footprint_half(Vector3(2, 1, 1), 90).distance_to(Vector2(0.5, 1.0)) < 0.001, "a quarter turn swaps the footprint")
	check(ObjectTransform.footprint_half(Vector3(1, 1, 1), 45).distance_to(Vector2.ONE * 0.7071) < 0.001, "45° widens the footprint to the diagonal")
	check(not ObjectTransform.footprints_overlap(Vector2.ZERO, Vector2.ONE, 0, Vector2(1.2, 0), Vector2.ONE, 0), "squares side by side are apart")
	check(ObjectTransform.footprints_overlap(Vector2.ZERO, Vector2.ONE, 45, Vector2(1.2, 0), Vector2.ONE, 45), "turned 45° their corners meet")
	check(not ObjectTransform.footprints_overlap(Vector2.ZERO, Vector2(3, 0.4), 90, Vector2(1, 0), Vector2(3, 0.4), 90), "long thin pieces turned upright stand apart")

	# ---------------------------------------------------------------- home: shape and turn
	Engine.set_meta("studio_session", {"token": token, "url": server, "room": "home"})
	var home = load("res://scenes/studio.tscn").instantiate()
	root.add_child(home)
	await create_timer(2.0).timeout
	var index := -1
	for i in home.data.get("objects", []).size():
		if home.data.objects[i].id == room_id: index = i
	check(index >= 0, "home lists the second piece")
	if index < 0: finish(); return
	home.set_dock_open(true)
	var tabs: TabContainer = home.find_children("*", "TabContainer", true, false)[0]
	tabs.current_tab = 1
	await home.select_item(index)
	home.open_shape_panel()
	panel = home.shape_panel
	check(is_instance_valid(panel), "보관함 opens the shape window")
	if not is_instance_valid(panel): finish(); return
	var room_shape := {"width": 60, "depth": 140, "height": 200, "scale": 85, "mirror": false}
	for axis in ObjectTransform.AXES: panel.sliders[axis].value = room_shape[axis]
	shaped(home.inspected, room_shape, "room preview (live)")
	await capture("object-shape-room.png")
	# Closing without saving puts the made shape back.
	panel.close()
	await process_frame
	shaped(home.inspected, {}, "room preview after closing unsaved")
	home.open_shape_panel()
	panel = home.shape_panel
	for axis in ObjectTransform.AXES: panel.sliders[axis].value = room_shape[axis]
	await panel.save()
	check(ObjectTransform.same(listed(home.data.objects, room_id).get("shape"), room_shape), "room list holds the saved shape")
	await home.begin_place()
	check(is_instance_valid(home.ghost), "room ghost")
	if not is_instance_valid(home.ghost): finish(); return
	shaped(home.ghost, room_shape, "room ghost")
	for i in 13: home._unhandled_key_input(key(KEY_R))
	home.view_input(wheel(true))
	for i in 3: home._unhandled_key_input(key(KEY_R, false, true))
	check(home.placement_rotation == 203, "room turns to 203°: %d" % home.placement_rotation)
	check(home.turn_readout.text == "203°", "room readout " + home.turn_readout.text)
	home.place_at = Vector3(2, 0.08, -1); home.ghost.position = home.place_at
	await create_timer(0.6).timeout
	check(same_angle(home.ghost, 203), "room ghost eases to 203°")
	check(home.placement_problem(home.place_at).is_empty(), "free spot: " + home.placement_problem(home.place_at))
	# Right next to the back wall: the turned footprint would cross it.
	var half := ObjectTransform.footprint_half(home.ghost.get_meta("size"), 203)
	var back := -Vector2(home.room_spec.size).y * 0.5 + half.y * 0.5
	if back >= -4.0:
		check(not home.placement_problem(Vector3(2, 0.08, back)).is_empty(), "the turned footprint may not cross the wall")
	await capture("object-turn-room.png")
	await home.commit_place()
	check(home.placed.has(room_id) and same_angle(home.placed[room_id], 203), "placed in the home at 203°")
	shaped(home.placed.get(room_id), room_shape, "room placed")
	home.queue_free()
	await process_frame
	Engine.set_meta("studio_session", {"token": token, "url": server, "room": "home"})
	home = load("res://scenes/studio.tscn").instantiate()
	root.add_child(home)
	await create_timer(2.0).timeout
	check(home.placed.has(room_id) and same_angle(home.placed[room_id], 203), "203° survives re-entering the home")
	shaped(home.placed.get(room_id), room_shape, "room reloaded")
	var stored: Dictionary = listed(home.data.objects, room_id)
	check(int(stored.get("rotation", -1)) == 203, "server keeps 203°")
	home.queue_free()
	await process_frame
	finish()

func finish() -> void:
	print("OBJECT_TRANSFORM ", JSON.stringify({"ok": failures.is_empty(), "failures": failures}))
	quit(0 if failures.is_empty() else 1)
