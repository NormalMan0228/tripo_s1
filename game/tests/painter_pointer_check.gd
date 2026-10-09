extends SceneTree
## Paint lands under the pointer on a real Tripo model (tests/fixtures/tripo/tripo_pot.glb is a
## Tripo craft part with its maps scaled down), loaded like a craft (geometry "tripo": the -90°
## turn, design-box fit, size), placed under a turned parent, and painted through the real
## mouse path (window events -> the view's gui_input -> the brush):
##  - a dab paints the texel the view shows under the pointer, centred on the shown surface;
##  - a part the object's program keeps turning is baked and shown in one pose;
##  - dabs still queued when the camera zooms land where they were made;
##  - a stroke's seam padding reaches the view.
## Windowed runs repeat at 1280x800 and 1920x1080 and also compare rendered frames.
##   godot --headless --path game --script res://tests/painter_pointer_check.gd -- --mute --qa
##   godot --path game --script res://tests/painter_pointer_check.gd -- --mute --qa
const Painter = preload("res://scripts/painter/painter.gd")
const PaintApply = preload("res://scripts/painter/paint_apply.gd")
const Assembly = preload("res://scripts/asset_assembly.gd")
const FIXTURE := "res://tests/fixtures/tripo/tripo_pot.glb"
const BRUSH_PX := 16.0
const INK := Color(1, 0, 1)

var failures := 0
var passes := 0
var rendered := false

class StubApi extends Node:
	func request(_path: String, _payload: Dictionary = {}, _method := HTTPClient.METHOD_GET, _binary := false, _timeout := 12.0) -> Dictionary:
		await get_tree().process_frame
		return {"ok": false, "error": "paint_not_found", "status": 404}
	func post(path: String, payload: Dictionary) -> Dictionary:
		return await request(path, payload, HTTPClient.METHOD_POST)
	func mutation(extra: Dictionary = {}) -> Dictionary:
		return extra

func expect(value: bool, label: String) -> void:
	if value: passes += 1
	else: failures += 1
	print(("PASS " if value else "FAIL ") + label)

func _initialize() -> void:
	call_deferred("run")

func wait_until(condition: Callable, seconds := 30.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return false

func part(id: String, size: Array, position: Array) -> Dictionary:
	return {"id": id, "parent": "", "prompt": "", "shape": "box", "size": size, "position": position,
		"rotation": [0, 0, 0], "pivot": [0, 0, 0], "color": "#c9a46e"}

## A Tripo craft: one static piece, or a body with a lid its program keeps turning.
func craft(turning: bool) -> Node3D:
	var bytes := FileAccess.get_file_as_bytes(FIXTURE)
	var parts := [part("whole", [1.2, 0.7, 1.2], [0, 0.35, 0])]
	var program := {"version": 1, "state": {}, "functions": {}, "events": {}}
	var blobs := {"whole": bytes}
	if turning:
		parts = [part("body", [1.0, 0.55, 1.0], [0, 0.275, 0]), part("lid", [0.7, 0.3, 0.7], [0, 0.7, 0])]
		program.events = {"tick": [["emit", "rotate_y", "lid", ["mod", ["mul", ["input", "time"], 140], 360]]]}
		blobs = {"body": bytes, "lid": bytes}
	var manifest := {"schema": 1, "plan": {"parts": parts}, "program": program,
		"provenance": {"geometry": "tripo", "size_m": 1.1}, "runtime": {}}
	var model := Assembly.new()
	if not model.build(manifest, blobs):
		model.free()
		return null
	return model

func open(api: Node, model: Node3D) -> Control:
	var painter := Painter.new()
	painter.setup(api, {"id": "pot", "name": "pot", "paint_version": null}, model, {"views": [root], "remember": false})
	root.add_child(painter)
	if not await wait_until(func(): return painter.ready_to_paint): return null
	for i in 4: await process_frame
	painter.settings.brush.merge({"size": BRUSH_PX, "hardness": 1.0, "opacity": 1.0, "flow": 1.0, "spacing": 0.12,
		"smoothing": 0.0, "pressure_size": false, "pressure_opacity": false, "tip": 0, "mode": 0}, true)
	painter.primary = INK
	return painter

func close(painter: Control) -> void:
	painter.queue_free()
	await process_frame

## Through the window's input path, like a player's mouse.
func real_mouse(kind: String, canvas_at: Vector2, wheel := MOUSE_BUTTON_NONE) -> void:
	var at: Vector2 = root.get_final_transform() * canvas_at
	var event: InputEvent
	if kind == "motion":
		var motion := InputEventMouseMotion.new()
		motion.position = at; motion.global_position = at; motion.pressure = 1.0
		motion.button_mask = MOUSE_BUTTON_MASK_LEFT
		event = motion
	else:
		var button := InputEventMouseButton.new()
		button.button_index = MOUSE_BUTTON_LEFT if wheel == MOUSE_BUTTON_NONE else wheel
		button.pressed = kind == "down"
		button.button_mask = MOUSE_BUTTON_MASK_LEFT if kind == "down" and wheel == MOUSE_BUTTON_NONE else 0
		button.position = at; button.global_position = at
		event = button
	root.push_input(event)
	await process_frame

## What the view shows under a view point: the nearest hit on the shown copies, with the slot
## and the atlas texel that the display samples there.
func shown_hit(painter: Control, at: Vector2) -> Dictionary:
	var view = painter.view
	var r: Array = view.ray(at)
	var best := {"hit": false, "distance": INF}
	var slots: Array = PaintApply.slots_of(painter.model)
	for k in slots.size():
		var source: MeshInstance3D = slots[k].mesh
		var copy: MeshInstance3D = null
		for child in view.world_root.get_children():
			if child is MeshInstance3D and child.mesh == source.mesh: copy = child
		if copy == null: continue
		var arrays := source.mesh.surface_get_arrays(slots[k].surface)
		var v: PackedVector3Array = copy.global_transform * (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array)
		var uv: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
		var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		for i in range(0, index.size() - 2, 3):
			var a := v[index[i]]; var b := v[index[i + 1]]; var c := v[index[i + 2]]
			var p = Geometry3D.ray_intersects_triangle(r[0], r[1], a, b, c)
			if p == null: continue
			var d: float = (p - r[0]).length()
			if d >= best.distance: continue
			var w := Geometry3D.get_triangle_barycentric_coords(p, a, b, c)
			var rect: Rect2i = painter.core.slot_rects[k]
			var at_uv: Vector2 = uv[index[i]] * w.x + uv[index[i + 1]] * w.y + uv[index[i + 2]] * w.z
			var texel := Vector2(rect.position) + at_uv.clamp(Vector2.ZERO, Vector2.ONE * 0.9999) * float(rect.size.x)
			var normal := (b - a).cross(c - a).normalized()
			best = {"hit": true, "distance": d, "position": p, "slot": k, "texel": int(texel.y) * painter.core.size + int(texel.x),
				"facing": absf(normal.dot(r[1]))}
	return best

func painted(core, texel: int) -> bool:
	var data: PackedByteArray = core.layers[core.current].data
	var o := texel * 4
	return data[o] > 230 and data[o + 1] < 40 and data[o + 2] > 230

## View points (view pixels) whose shown surface faces the camera, optionally on one slot.
func targets(painter: Control, slot := -1, count := 4) -> Array:
	var out := []
	for fy in [0.35, 0.5, 0.65, 0.42, 0.58]:
		for fx in [0.3, 0.45, 0.6, 0.72, 0.38, 0.52]:
			var at: Vector2 = painter.view.size * Vector2(fx, fy)
			var hit := shown_hit(painter, at)
			if hit.hit and hit.facing > 0.5 and (slot < 0 or hit.slot == slot): out.append([at, hit])
			if out.size() >= count: return out
	return out

func port_image(view) -> Image:
	for i in 3: await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = view.port.get_texture().get_image()
	image.convert(Image.FORMAT_RGBA8)
	return image

## One click at a view point; returns {texels, centroid (baked space), screen (rendered centroid
## in view pixels, windowed runs only)}.
func dab(painter: Control, at: Vector2) -> Dictionary:
	var core = painter.core
	var before: PackedByteArray = core.layers[core.current].data.duplicate()
	var before_image: Image = await port_image(painter.view) if rendered else null
	var canvas: Vector2 = painter.view.get_global_rect().position + at
	await real_mouse("down", canvas)
	await real_mouse("up", canvas)
	var data: PackedByteArray = core.layers[core.current].data
	var sum := Vector3.ZERO
	var count := 0
	for t: int in core.size * core.size:
		var o := t * 4
		if core.texel_slot[t] >= 0 and (data[o] != before[o] or data[o + 1] != before[o + 1] or data[o + 2] != before[o + 2]):
			sum += core.texel_position(t)
			count += 1
	var out := {"texels": count, "centroid": sum / maxf(count, 1)}
	if rendered:
		var after_image: Image = await port_image(painter.view)
		var spot := Vector2.ZERO
		var pixels := 0
		for y in after_image.get_height():
			for x in after_image.get_width():
				var a := after_image.get_pixel(x, y); var b := before_image.get_pixel(x, y)
				if absf(a.r - b.r) + absf(a.g - b.g) + absf(a.b - b.b) > 0.15:
					spot += Vector2(x + 0.5, y + 0.5)
					pixels += 1
		out.pixels = pixels
		out.screen = spot / maxf(pixels, 1) * painter.view.size / Vector2(painter.view.port.size)
	return out

func check_dabs(painter: Control, picks: Array, label: String) -> void:
	var view = painter.view
	var under := 0
	var centred := 0
	var on_screen := 0
	var worst := 0.0
	var worst_px := 0.0
	for item in picks:
		var at: Vector2 = item[0]
		var hit: Dictionary = item[1]
		var result := await dab(painter, at)
		var radius: float = BRUSH_PX * 0.5 * view.world_per_pixel(hit.position)
		var gap: float = (result.centroid as Vector3).distance_to(hit.position)
		worst = maxf(worst, gap / radius)
		if painted(painter.core, hit.texel): under += 1
		if result.texels > 0 and gap < radius * 0.4: centred += 1
		if rendered:
			var px: float = (result.screen as Vector2).distance_to(at) if result.pixels > 0 else 999.0
			worst_px = maxf(worst_px, px)
			if px < 3.0: on_screen += 1
		painter.undo()
		await process_frame
	expect(not picks.is_empty() and under == picks.size(), "%s: the texel shown under the pointer is painted (%d/%d)" % [label, under, picks.size()])
	expect(not picks.is_empty() and centred == picks.size(), "%s: each dab is centred on the shown surface point (worst %.2f radius)" % [label, worst])
	if rendered:
		expect(on_screen == picks.size(), "%s: the rendered dab sits under the pointer (worst %.1f px)" % [label, worst_px])

func run() -> void:
	rendered = DisplayServer.get_name() != "headless"
	var sizes: Array = [Vector2i(1280, 800), Vector2i(1920, 1080)] if rendered else [Vector2i.ZERO]
	var api := StubApi.new()
	root.add_child(api)
	for window in sizes:
		if window != Vector2i.ZERO:
			DisplayServer.window_set_size(window)
			for i in 5: await process_frame
		var tag := "%dx%d" % [window.x, window.y] if window != Vector2i.ZERO else "headless"

		# A one-piece craft placed and turned in the world.
		var spot := Node3D.new()
		spot.position = Vector3(6.0, 0.3, -4.0)
		spot.rotation.y = 0.9
		root.add_child(spot)
		var model := craft(false)
		expect(model != null and PaintApply.has_uvs(model), "%s: the Tripo craft loads with UVs" % tag)
		if model == null: break
		spot.add_child(model)
		model.rotation.y = -2.2
		var painter := await open(api, model)
		expect(painter != null, "%s: the painter opens on the Tripo craft" % tag)
		if painter == null: break
		print("NOTE %s view=%s port=%s triangles=%d covered=%d" % [tag, painter.view.size, painter.view.port.size, painter.core.tri_count, painter.core.covered])
		await check_dabs(painter, targets(painter), tag + " one piece")

		# Dabs queued during a stroke, then a zoom: they land where they were made.
		var path: Array = targets(painter, -1, 30)
		var middle: Vector2 = painter.view.size * 0.5
		path.sort_custom(func(a, b): return (a[0] as Vector2).distance_to(middle) < (b[0] as Vector2).distance_to(middle))
		var from: Vector2 = path[0][0]
		var to: Vector2 = path[path.size() - 1][0]
		var far := shown_hit(painter, to)
		var origin: Vector2 = painter.view.get_global_rect().position
		await real_mouse("down", origin + from)
		var motion := InputEventMouseMotion.new()
		motion.position = to
		motion.pressure = 1.0
		painter._on_view_event(motion)
		for i in 3: await real_mouse("down", origin + to, MOUSE_BUTTON_WHEEL_UP)
		await real_mouse("up", origin + to)
		expect(far.hit and painted(painter.core, far.texel), "%s: dabs queued before a zoom land where they were made" % tag)
		painter.undo()

		# The stroke's seam padding reaches the view (it uploads layers by revision).
		var core = painter.core
		var layer = core.layers[core.current]
		var line: Array = targets(painter, -1, 2)
		var seam := shown_hit(painter, line[0][0])
		core.begin_stroke(false)
		core.stamp(seam.position, Vector3.ZERO - painter.view.ray(line[0][0])[1], 0.12, {"color": INK, "hardness": 1.0})
		var stamped: int = layer.revision
		core.end_stroke()
		expect(layer.revision > stamped, "%s: padding a stroke marks the layer for upload" % tag)
		core.undo()
		await real_mouse("down", origin + line[0][0])
		for i in 9: await real_mouse("motion", origin + (line[0][0] as Vector2).lerp(line[1][0], i / 8.0))
		await real_mouse("up", origin + line[1][0])
		await process_frame
		if rendered:
			var shown: Image = (painter.view.textures[layer].texture as ImageTexture).get_image()
			shown.convert(Image.FORMAT_RGBA8)
			expect(shown.get_data() == layer.data, "%s: the view shows the stroke with its seam padding" % tag)
		await close(painter)
		spot.queue_free()

		# A craft whose lid its program keeps turning, inspected in its own stage like the bag.
		var stage := SubViewport.new()
		stage.own_world_3d = true
		stage.size = Vector2i(210, 185)
		root.add_child(stage)
		var turning := craft(true)
		stage.add_child(turning)
		turning.rotation.y = 1.3
		painter = await open(api, turning)
		expect(painter != null, "%s: the painter opens on the turning craft" % tag)
		if painter == null: break
		var worst := 0.0
		core = painter.core
		var slots: Array = PaintApply.slots_of(turning)
		for k in slots.size():
			var source: MeshInstance3D = slots[k].mesh
			for child in painter.view.world_root.get_children():
				if not (child is MeshInstance3D and child.mesh == source.mesh): continue
				var arrays := source.mesh.surface_get_arrays(slots[k].surface)
				var v: PackedVector3Array = (child as MeshInstance3D).transform * (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array)
				var index: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
				var t: int = core.tri_slot.find(k)
				for i in range(0, index.size() - 2, 3):
					if t < 0 or t >= core.tri_count or core.tri_slot[t] != k: break
					var face := (v[index[i + 1]] - v[index[i]]).cross(v[index[i + 2]] - v[index[i]])
					if face.length_squared() < 1e-20: continue
					worst = maxf(worst, core.tri_v[t * 3].distance_to(v[index[i]]))
					t += 1
		expect(worst < 1e-4, "%s: the turning lid is baked in the pose the view shows (%.4f m apart)" % [tag, worst])
		await check_dabs(painter, targets(painter, 1), tag + " turning lid")
		await close(painter)
		stage.queue_free()
		await process_frame
	api.queue_free()
	await process_frame
	print("PAINTER_POINTER ", JSON.stringify({"passed": passes, "failed": failures}))
	quit(1 if failures else 0)
