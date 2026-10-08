extends SceneTree
## End to end against a local demo server: the village bag opens the painter, a stroke is
## saved (PNG upload), the paint shows on the inspected copy, after a fresh load, on the
## placed village copy, for a visiting friend (guest route) and in the room studio; an object
## without UVs gets the whole-object colour; resetting clears it everywhere.
##   godot --path game --script res://tests/painter_e2e.gd -- --server=http://127.0.0.1:8796
const PaintApply = preload("res://scripts/painter/paint_apply.gd")
const Assembly = preload("res://scripts/asset_assembly.gd")
const Api = preload("res://scripts/api.gd")

var server := "http://127.0.0.1:8796"
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

func click(painter: Control, kind: String, at: Vector2) -> void:
	var event: InputEvent
	if kind == "motion":
		var motion := InputEventMouseMotion.new()
		motion.position = at
		motion.pressure = 1.0
		event = motion
	else:
		var button := InputEventMouseButton.new()
		button.button_index = MOUSE_BUTTON_LEFT
		button.pressed = kind == "down"
		button.position = at
		event = button
	painter._on_view_event(event)

func painted(node: Node3D, key: String) -> bool:
	if not is_instance_valid(node) or str(node.get_meta("paint_key", "")) != key: return false
	for slot in PaintApply.slots_of(node):
		var material := (slot.mesh as MeshInstance3D).get_active_material(slot.surface) as StandardMaterial3D
		if material == null or material.albedo_texture == null or material.albedo_color != Color.WHITE: return false
	return true

func finish() -> void:
	PaintApply.images.clear(); PaintApply.texture_sets.clear()
	print("PAINTER_E2E ", JSON.stringify({"ok": failures.is_empty(), "passed": passes, "failures": failures}))
	quit(0 if failures.is_empty() else 1)

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	var app = load("res://scripts/main.gd").new()
	root.add_child(app)
	await process_frame
	var name := "paint_" + str(Time.get_ticks_usec() % 100000000)
	var password := "Local-paint-qa-1!"
	await app.authenticate(true, server, name, password, "")
	check(app.screen == "village", "registered and in the village")
	if app.screen != "village": finish(); return
	var token: String = app.api.token

	# The welcome chair has no UVs: the bag keeps its swatches; the painter offers the whole colour.
	app.select_object(0)
	check(await wait_until(func(): return is_instance_valid(app.inspect_model)), "welcome chair inspected")
	check(not PaintApply.has_uvs(app.inspect_model) and app.paint_palette.visible and app.paint_button.text == tr("전체 색 고르기"), "UV-less object keeps the swatches with a reason")
	app.open_painter()
	var fallback: Control = app.painter
	check(await wait_until(func(): return is_instance_valid(fallback) and is_instance_valid(fallback.picker)), "painter opens the colour panel")
	check(fallback.core == null, "no painting surface for the UV-less chair")
	fallback.picker.set_color(Color("7c9ec6"))
	for b in fallback.find_children("*", "Button", true, false):
		if (b as Button).text == tr("적용"): (b as Button).pressed.emit()
	check(await wait_until(func(): return app.selected.get("color", "") == "#7c9ec6"), "whole colour saved through the old route")
	if "--stop=1" in OS.get_cmdline_user_args(): finish(); return

	# A fixture assembly (procedural parts with UVs).
	var queued: Dictionary = await app.api.post("/v1/studio/jobs", app.api.mutation({"prompt": "wooden chest", "geometry": "proxy", "designer": "fixture", "motion": "static"}))
	check(queued.ok, "fixture craft queued")
	if not queued.ok: finish(); return
	var id := ""
	for _i in 60:
		var job: Dictionary = await app.api.request("/v1/studio/jobs/" + str(queued.data.id))
		if job.ok and job.data.state == "ready": id = job.data.object_id; break
		await create_timer(0.5).timeout
	check(not id.is_empty(), "fixture craft ready")
	if id.is_empty(): finish(); return
	await app.refresh_inventory()
	var index := -1
	for i in app.me.objects.size():
		if app.me.objects[i].id == id: index = i
	app.select_object(index)
	check(await wait_until(func(): return is_instance_valid(app.inspect_model) and app.selected.get("id") == id and app.inspect_model.get_meta("studio", false)), "crafted assembly inspected")
	check(PaintApply.has_uvs(app.inspect_model) and not app.paint_palette.visible and app.paint_button.text == tr("색칠하기"), "the bag offers the painter for a UV object")
	check(app.me.objects[index].get("paint_version") == null, "not painted yet")

	app.open_painter()
	var painter: Control = app.painter
	check(await wait_until(func(): return is_instance_valid(painter) and painter.ready_to_paint, 30.0), "painter ready on the assembly (%d slots)" % PaintApply.slots_of(app.inspect_model).size())
	check(not app.world_movement_allowed(), "the walker stays still while painting")
	var centre: Vector2 = painter.view.size * 0.5
	painter.primary = Color(0.15, 0.35, 0.85)
	click(painter, "down", centre - Vector2(40, 0))
	for i in 17: click(painter, "motion", centre + Vector2(-40 + i * 5, 0))
	click(painter, "up", centre + Vector2(40, 0))
	await process_frame
	check(painter.dirty and painter.core.history_index == 1, "stroke painted")
	var hit: Dictionary = painter.core.pick(painter.view.ray(centre)[0], painter.view.ray(centre)[1])
	var texel: int = painter.core.nearest_texel(hit.position, hit.normal)
	var expected: Color = painter.core.sample(texel)
	var saved_at := Time.get_ticks_msec()
	var gone: WeakRef = weakref(painter)
	painter.save()
	check(await wait_until(func(): return gone.get_ref() == null, 30.0), "saved and closed")
	print("TIMING save_ms=%d" % (Time.get_ticks_msec() - saved_at))
	var key := id + ":1"
	if "--stop=2" in OS.get_cmdline_user_args(): finish(); return
	check(app.me.objects[index].get("paint_version") == 1, "the bag knows the new paint version")
	check(painted(app.inspect_model, key), "the inspected copy shows the paint")
	var fetched: Dictionary = await app.api.request("/v1/objects/" + id + "/paint", {}, HTTPClient.METHOD_GET, true)
	var image := Image.new()
	check(fetched.ok and image.load_png_from_buffer(fetched.bytes) == OK and image.get_width() == 1024, "the server keeps a 1024 px PNG")
	if fetched.ok and not image.is_empty():
		var pixel := image.get_pixel(texel % 1024, texel / 1024)
		check(absf(pixel.r - expected.r) < 0.02 and absf(pixel.b - expected.b) < 0.02, "the uploaded PNG holds the painted colour (%s / %s)" % [pixel, expected])
	var me: Dictionary = await app.api.request("/v1/me")
	check(me.ok and me.data.objects.any(func(o): return o.id == id and o.paint_version == 1), "/v1/me lists paint_version")

	# A fresh load (village, rooms and visits all load through attach()).
	PaintApply.images.clear(); PaintApply.texture_sets.clear(); PaintApply.image_order.clear(); PaintApply.texture_order.clear()
	var fresh: Node3D = await app.load_object(app.me.objects[index])
	check(painted(fresh, key), "a freshly loaded copy fetches and shows the paint")
	if is_instance_valid(fresh): fresh.free()
	await app.begin_place()
	check(is_instance_valid(app.preview) and painted(app.preview, key), "the placement preview is painted")
	if is_instance_valid(app.preview):
		app.preview.position = load("res://scripts/town.gd").furniture_point(4, 3)
		await app.place_preview()
	check(await wait_until(func(): return app.loaded.has(id) and painted(app.loaded[id], key)), "the placed village copy is painted")

	# A visiting friend reads it through the guest route; a stranger cannot.
	var guest := Api.new(); root.add_child(guest); guest.base_url = server
	var guest_name := "guest_" + str(Time.get_ticks_usec() % 100000000)
	var login: Dictionary = await guest.post("/v1/auth/register", {"username": guest_name, "password": password})
	check(login.ok, "guest registered")
	guest.token = login.data.get("token", "") if login.ok else ""
	var guest_route := "/v1/social/village/objects/"
	var refused: Dictionary = await guest.request(guest_route + id + "/paint", {}, HTTPClient.METHOD_GET, true)
	check(not refused.ok and int(refused.get("status", 0)) == 404, "a stranger cannot read the paint")
	var invite: Dictionary = await app.api.post("/v1/social/invites", app.api.mutation({"username": guest_name, "kind": "village"}))
	var accepted: Dictionary = await guest.post("/v1/social/invites/" + str(invite.get("data", {}).get("id", "")) + "/accept", guest.mutation())
	check(invite.ok and accepted.ok, "guest invited into the village")
	var presence: Dictionary = await guest.post("/v1/social/presence", {"x": 1, "z": 2})
	var listed: Array = presence.get("data", {}).get("village", {}).get("objects", []) if presence.ok else []
	check(listed.any(func(o): return o.id == id and o.paint_version == 1), "the visitor's object list carries paint_version")
	PaintApply.images.clear(); PaintApply.texture_sets.clear()
	var visit_copy: Node3D = await Assembly.fetch(guest, id, guest_route)
	if visit_copy: await PaintApply.attach(guest, visit_copy, {"id": id, "paint_version": 1}, guest_route)
	check(visit_copy != null and painted(visit_copy, key), "the visitor's copy shows the paint")
	if is_instance_valid(visit_copy): visit_copy.free()

	# The room studio: move it to the workshop and open the room.
	if "--stop=3" in OS.get_cmdline_user_args(): finish(); return
	var obj: Dictionary = app.me.objects[index]
	for item in app.me.objects:
		if item.id == id: obj = item
	var moved: Dictionary = await app.api.post("/v1/objects/" + id + "/placement", app.api.mutation({"version": int(obj.version), "action": "retrieve"}))
	var placed: Dictionary = await app.api.post("/v1/objects/" + id + "/placement", app.api.mutation({"version": int(obj.version) + 1, "room": "workshop", "x": 2, "z": 0}))
	check(moved.ok and placed.ok, "moved into the workshop")
	app.queue_free()
	guest.queue_free()
	await process_frame
	PaintApply.images.clear(); PaintApply.texture_sets.clear()
	Engine.set_meta("studio_session", {"token": token, "url": server, "room": "workshop"})
	change_scene_to_file("res://scenes/studio.tscn")
	check(await wait_until(func(): return current_scene != null and "placed" in current_scene and current_scene.placed.has(id), 30.0), "the workshop loads the piece")
	var studio = current_scene
	check(studio != null and painted(studio.placed.get(id), key), "the workshop copy is painted")
	var studio_index := -1
	for i in studio.data.objects.size():
		if studio.data.objects[i].id == id: studio_index = i
	await studio.select_item(studio_index)
	check(is_instance_valid(studio.inspected) and painted(studio.inspected, key), "the studio preview is painted")
	check(studio.paint_button.text == tr("색칠하기") and not studio.paint_rows[0].visible, "the 보관함 tab offers the painter")
	studio.open_painter()
	var room_painter: Control = studio.painter
	check(await wait_until(func(): return is_instance_valid(room_painter) and room_painter.ready_to_paint, 30.0), "the studio painter starts from the saved paint")
	var base: Color = room_painter.core.sample(room_painter.core.nearest_texel(hit.position, hit.normal))
	check(base.is_equal_approx(expected) or (absf(base.r - expected.r) < 0.02 and absf(base.b - expected.b) < 0.02), "the saved pixels come back as the base layer (%s / %s)" % [base, expected])
	var closing: WeakRef = weakref(room_painter)
	room_painter._reset()
	check(await wait_until(func(): return closing.get_ref() == null, 20.0), "reset clears the paint and closes")
	check(studio.data.objects[studio_index].get("paint_version") == null and not studio.placed[id].has_meta("paint_key"), "the room copy is back to unpainted")
	var after: Dictionary = await studio.api.request("/v1/objects/" + id + "/paint", {}, HTTPClient.METHOD_GET, true)
	check(not after.ok and int(after.get("status", 0)) == 404, "the server has no paint after reset")
	finish()
