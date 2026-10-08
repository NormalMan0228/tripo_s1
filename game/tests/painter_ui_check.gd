extends SceneTree
## The painting workspace without a server: opening, shortcuts (and that typing in its text
## fields never triggers them), a brush stroke, undo/redo keys, layers, fill, gradient,
## saving through a stub API, the UV-less fallback and applying a saved paint to a model.
##   godot --headless --path game --script res://tests/painter_ui_check.gd
const Painter = preload("res://scripts/painter/painter.gd")
const PaintApply = preload("res://scripts/painter/paint_apply.gd")
const Loader = preload("res://scripts/model_loader.gd")

var failures := 0
var passes := 0

class StubApi extends Node:
	var calls: Array = []
	func request(path: String, payload: Dictionary = {}, method := HTTPClient.METHOD_GET, binary := false, timeout := 12.0) -> Dictionary:
		await get_tree().process_frame
		calls.append({"path": path, "payload": payload, "method": method, "timeout": timeout})
		if path.ends_with("/paint") and method == HTTPClient.METHOD_POST:
			return {"ok": true, "data": {"paint_version": 3 if payload.get("clear", false) == false else null, "sha256": "x"}}
		return {"ok": false, "error": "paint_not_found", "status": 404}
	func post(path: String, payload: Dictionary) -> Dictionary:
		return await request(path, payload, HTTPClient.METHOD_POST)
	func mutation(extra: Dictionary = {}) -> Dictionary:
		return extra.merged({"request_id": "00000000-0000-4000-8000-000000000000"})

func expect(value: bool, label: String) -> void:
	if value: passes += 1
	else: failures += 1
	print(("PASS " if value else "FAIL ") + label)

func _initialize() -> void:
	call_deferred("run")

func model(with_uvs := true) -> Node3D:
	var root := Node3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(1.2, 0.8, 0.9)
	box.subdivide_width = 4; box.subdivide_height = 4; box.subdivide_depth = 4
	var arrays := box.get_mesh_arrays()
	if not with_uvs: arrays[Mesh.ARRAY_TEX_UV] = null
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var instance := MeshInstance3D.new()
	instance.mesh = mesh
	instance.position = Vector3(0, 0.4, 0)
	instance.set_meta("craft_surface", true)
	root.add_child(instance)
	Loader.paint(root, Color("d9b98a"))
	return root

func key(code: Key, ctrl := false, shift := false, unicode := 0) -> void:
	for pressed in [true, false]:
		var event := InputEventKey.new()
		event.keycode = code
		event.physical_keycode = code
		event.pressed = pressed
		event.ctrl_pressed = ctrl
		event.shift_pressed = shift
		event.unicode = unicode if pressed else 0
		Input.parse_input_event(event)
		await process_frame

func mouse(painter, kind: String, at: Vector2, pressure := 1.0) -> void:
	var event: InputEvent
	if kind == "motion":
		var motion := InputEventMouseMotion.new()
		motion.position = at
		motion.pressure = pressure
		motion.button_mask = MOUSE_BUTTON_MASK_LEFT
		event = motion
	else:
		var button := InputEventMouseButton.new()
		button.button_index = MOUSE_BUTTON_LEFT
		button.pressed = kind == "down"
		button.position = at
		event = button
	painter._on_view_event(event)

func wait_until(condition: Callable, seconds := 20.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

func run() -> void:
	var api := StubApi.new()
	root.add_child(api)
	var stage := Node3D.new()
	root.add_child(stage)
	var subject := model()
	stage.add_child(subject)
	var bare := model(false)
	expect(PaintApply.has_uvs(subject) and not PaintApply.has_uvs(bare), "UV detection on the loaded model")
	bare.free()
	var saved := {}
	var painter := Painter.new()
	painter.setup(api, {"id": "object-1", "name": "작은 상자", "paint_version": null}, subject,
		{"saved": func(image, version): saved.image = image; saved.version = version, "views": [root], "remember": false})
	root.add_child(painter)
	expect(root.disable_3d, "the scene behind is not rendered while painting")
	var opened_at := Time.get_ticks_msec()
	expect(await wait_until(func(): return painter.ready_to_paint), "workspace prepares the surface")
	print("TIMING open_ms=%d" % (Time.get_ticks_msec() - opened_at))
	expect(painter.view.materials.size() == 1 and painter.core.layers.size() == 1, "one surface shown with the base layer")
	var base_center: Color = painter.core.sample(painter.core.nearest_texel(Vector3(0, 0.4, 0.45), Vector3(0, 0, 1)))
	expect(base_center.is_equal_approx(Color("d9b98a")) or absf(base_center.r - Color("d9b98a").r) < 0.01, "base layer starts from the object's colour")

	# Shortcuts.
	await key(KEY_E)
	expect(painter.tool == Painter.ERASER, "E selects the eraser")
	await key(KEY_G)
	expect(painter.tool == Painter.FILL, "G selects fill")
	await key(KEY_G)
	expect(painter.tool == Painter.GRADIENT, "G again selects the gradient")
	await key(KEY_I)
	expect(painter.tool == Painter.PICKER, "I selects the eyedropper")
	await key(KEY_B)
	expect(painter.tool == Painter.BRUSH, "B selects the brush")
	var size_before: float = painter.settings.brush.size
	await key(KEY_BRACKETRIGHT)
	expect(painter.settings.brush.size > size_before, "] grows the brush")
	await key(KEY_BRACKETLEFT)
	await key(KEY_BRACKETLEFT)
	expect(painter.settings.brush.size < size_before, "[ shrinks the brush")
	var front: Color = painter.primary
	await key(KEY_X)
	expect(painter.primary != front and painter.secondary == front, "X swaps the colours")
	await key(KEY_X)
	# Typing in a text field never reaches the shortcuts.
	painter._start_rename()
	await process_frame
	for letter in ["e", "g", "x"]:
		await key(OS.find_keycode_from_string(letter.to_upper()), false, false, letter.unicode_at(0))
	expect(painter.tool == Painter.BRUSH and painter.primary == front, "keys typed into the layer name are not shortcuts")
	expect(painter.rename_field.text.ends_with("egx"), "the text field received the typing")
	await key(KEY_ESCAPE)
	expect(not painter.rename_field.has_focus() and not painter.rename_row.visible and is_instance_valid(painter) and not painter.closing, "Esc leaves the text field, not the workspace")
	painter._start_rename()
	painter.rename_field.text = "밑칠"
	painter._finish_rename()
	expect(painter.core.layers[0].name == "밑칠", "layer renamed")
	painter.picker.hex_field.grab_focus()
	await key(KEY_B, false, false, "b".unicode_at(0))
	expect(painter.tool == Painter.BRUSH and painter.picker.hex_field.has_focus(), "the HEX field keeps its keys")
	painter.picker.hex_field.release_focus()

	# A brush stroke across the middle of the view.
	var view_size: Vector2 = painter.view.size
	var centre := view_size * 0.5
	expect(painter.core.pick(painter.view.ray(centre)[0], painter.view.ray(centre)[1]).hit, "the view looks at the object")
	painter.primary = Color(0.1, 0.3, 0.9)
	var steps: int = painter.core.history_index
	mouse(painter, "down", centre - Vector2(60, 0))
	for i in 25:
		mouse(painter, "motion", centre + Vector2(-60 + i * 5, 0), 0.6 + i * 0.016)
		await process_frame
	mouse(painter, "up", centre + Vector2(60, 0))
	await process_frame
	expect(painter.core.history_index == steps + 1 and painter.dirty, "the stroke is one history step")
	var hit: Dictionary = painter.core.pick(painter.view.ray(centre)[0], painter.view.ray(centre)[1])
	var painted: Color = painter.core.sample(painter.core.nearest_texel(hit.position, hit.normal))
	expect(painted.b > 0.6 and painted.r < 0.4, "the stroke painted where the cursor went (%s)" % painted)
	expect(painter.picker.recent.size() >= 1 and painter.picker.recent[0] == painter.primary.to_html(false), "the colour joins the recent colours")
	# The same through real mouse input (the view's gui_input path).
	var screen_centre: Vector2 = painter.view.get_global_rect().get_center()
	var before_real: int = painter.core.history_index
	await real_mouse("down", screen_centre + Vector2(0, 30))
	for i in 8: await real_mouse("motion", screen_centre + Vector2(i * 6, 30))
	await real_mouse("up", screen_centre + Vector2(48, 30))
	expect(painter.core.history_index == before_real + 1, "a real mouse drag in the view paints one stroke")
	await key(KEY_Z, true)
	expect(painter.core.history_index == before_real, "Ctrl+Z undoes")
	await key(KEY_Z, true, true)
	expect(painter.core.history_index == before_real + 1, "Ctrl+Shift+Z redoes")

	# Layers, fill and gradient.
	painter._add_layer()
	expect(painter.core.layers.size() == 2 and painter.core.current == 1, "a layer is added")
	painter._select_tool(Painter.FILL)
	painter.primary = Color(0.9, 0.8, 0.1)
	await painter._fill_at(centre + Vector2(0, 80))
	expect(painter.core.history_index == steps + 4, "fill is one step")
	painter._select_tool(Painter.GRADIENT)
	mouse(painter, "down", centre - Vector2(80, 40))
	mouse(painter, "motion", centre + Vector2(80, 40))
	expect(painter.view.line_visible, "the gradient line follows the drag")
	painter._on_view_event(_release(centre + Vector2(80, 40)))
	await wait_until(func(): return not painter.busy)
	expect(painter.core.history_index == steps + 5, "gradient is one step")
	painter.layer_opacity.value = 40
	expect(absf(painter.core.layers[1].opacity - 0.4) < 0.001, "layer opacity follows the slider")
	painter.layer_mode.select(1)
	painter.layer_mode.item_selected.emit(1)
	expect(painter.core.layers[1].mode == 1, "layer blend mode follows the menu")
	painter._select_tool(Painter.PICKER)
	print("VIEW size before=%s now=%s" % [view_size, painter.view.size])
	hit = painter.core.pick(painter.view.ray(centre)[0], painter.view.ray(centre)[1])
	mouse(painter, "down", centre)
	var seen: Color = painter.core.sample(painter.core.nearest_texel(hit.position, hit.normal))
	expect(painter.primary.is_equal_approx(seen), "the eyedropper takes the visible colour (%s / %s)" % [painter.primary, seen])

	await capture("painter-workspace")
	# Save: one PNG through the API, handed to the host.
	var gone: WeakRef = weakref(painter)
	await painter.save()
	await wait_until(func(): return gone.get_ref() == null)
	var upload: Dictionary = {}
	for call in api.calls:
		if call.path == "/v1/objects/object-1/paint": upload = call
	expect(not upload.is_empty() and upload.timeout > 12.0, "save uploads to the object's paint route")
	var png := Image.new()
	var decoded := Marshalls.base64_to_raw(str(upload.get("payload", {}).get("png", "")))
	expect(png.load_png_from_buffer(decoded) == OK and png.get_width() == 1024 and png.get_height() == 1024, "the upload is a 1024 px PNG")
	expect(saved.get("version") == 3 and saved.get("image") is Image, "the host gets the image and the new version")
	expect(not root.disable_3d, "closing restores the scene behind")
	expect(PaintApply.images.has("object-1:3"), "the saved image is cached by object and version")

	# The world shows it; a later whole-object colour keeps the texture.
	PaintApply.apply(subject, saved.image, "object-1:3")
	var surface: MeshInstance3D = subject.get_child(0)
	var material := surface.get_active_material(0) as StandardMaterial3D
	expect(material != null and material.albedo_texture != null and material.albedo_color == Color.WHITE, "the paint becomes the albedo texture")
	Loader.paint(subject, Color.RED)
	material = surface.get_active_material(0) as StandardMaterial3D
	expect(material.albedo_texture != null, "whole-object colour does not wipe the paint")
	PaintApply.clear(subject)
	material = surface.get_active_material(0) as StandardMaterial3D
	expect(material.albedo_texture == null and material.albedo_color == Color.RED, "clearing returns to the flat colour")

	# No UVs: the whole-object colour panel with a reason.
	var plain := model(false)
	stage.add_child(plain)
	var flat := {}
	var fallback := Painter.new()
	fallback.setup(api, {"id": "object-2", "name": "의자"}, plain, {"remember": false, "flat": func(hex: String, part: String, reset: bool): flat.hex = hex; flat.part = part; flat.reset = reset})
	root.add_child(fallback)
	expect(await wait_until(func(): return is_instance_valid(fallback.picker)), "UV-less object opens the colour panel")
	expect(fallback.core == null and not fallback.ready_to_paint, "no painting surface without UVs")
	var reason := fallback.find_children("*", "Label", true, false).any(func(l): return "UV" in (l as Label).text)
	expect(reason, "the panel explains why")
	fallback.picker.set_color(Color("336699"))
	await capture("painter-fallback")
	var apply_button: Button = null
	for b in fallback.find_children("*", "Button", true, false):
		if (b as Button).text == tr("적용"): apply_button = b
	apply_button.pressed.emit()
	expect(flat.get("hex") == "#336699" and flat.get("part") == "all" and flat.get("reset") == false, "applying sends the whole colour to the host")
	var closed: WeakRef = weakref(fallback)
	await wait_until(func(): return closed.get_ref() == null, 2.0)
	stage.queue_free()
	api.queue_free()
	await process_frame
	print("PAINTER_UI ", JSON.stringify({"passed": passes, "failed": failures}))
	quit(1 if failures else 0)

## Through the viewport's input path (window coordinates), like hud_fold_check.gd.
func real_mouse(kind: String, canvas_at: Vector2) -> void:
	var at: Vector2 = root.get_final_transform() * canvas_at
	var event: InputEvent
	if kind == "motion":
		var motion := InputEventMouseMotion.new()
		motion.position = at; motion.global_position = at; motion.pressure = 1.0
		motion.button_mask = MOUSE_BUTTON_MASK_LEFT
		event = motion
	else:
		var button := InputEventMouseButton.new()
		button.button_index = MOUSE_BUTTON_LEFT
		button.pressed = kind == "down"
		button.button_mask = MOUSE_BUTTON_MASK_LEFT if kind == "down" else 0
		button.position = at; button.global_position = at
		event = button
	root.push_input(event)
	await process_frame

## Windowed runs with --capture=<folder> save screenshots for a visual check.
func capture(label: String) -> void:
	var folder := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="): folder = arg.trim_prefix("--capture=")
	if folder.is_empty() or DisplayServer.get_name() == "headless": return
	for i in 6: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(folder.path_join(label + ".png"))

func _release(at: Vector2) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = false
	event.position = at
	return event
