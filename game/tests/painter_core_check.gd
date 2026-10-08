extends SceneTree
## The painter engine without UI (scripts/painter/paint_core.gd): baking, picking, brush,
## eraser, fill tolerance, gradient, undo/redo and symmetry, plus timings.
##   godot --headless --path game --script res://tests/painter_core_check.gd
const Core = preload("res://scripts/painter/paint_core.gd")

var failures := 0
var passes := 0

func expect(value: bool, label: String) -> void:
	if value: passes += 1
	else: failures += 1
	print(("PASS " if value else "FAIL ") + label)

func _initialize() -> void:
	call_deferred("run")

func box_slot(side := 1.6, subdivide := 8) -> Dictionary:
	var box := BoxMesh.new()
	box.size = Vector3.ONE * side
	box.subdivide_width = subdivide; box.subdivide_height = subdivide; box.subdivide_depth = subdivide
	var arrays := box.get_mesh_arrays()
	return {"vertices": arrays[Mesh.ARRAY_VERTEX], "normals": arrays[Mesh.ARRAY_NORMAL],
		"uvs": arrays[Mesh.ARRAY_TEX_UV], "indices": arrays[Mesh.ARRAY_INDEX]}

func solid(core, color: Color) -> PackedByteArray:
	var image := Image.create(core.size, core.size, false, Image.FORMAT_RGBA8)
	image.fill(color)
	return image.get_data()

func snapshot(core) -> Array:
	var out := []
	for layer in core.layers: out.append([layer.name, layer.data.duplicate(), layer.opacity, layer.mode, layer.visible])
	return out

func brush(color := Color.RED, extra := {}) -> Dictionary:
	return {"color": color, "opacity": 1.0, "flow": 1.0, "hardness": 0.8, "mode": Core.NORMAL}.merged(extra, true)

func run() -> void:
	var core := Core.new()
	core.setup([box_slot()], 1024)
	expect(core.uv_ok and core.tri_count > 0, "box mesh with UVs is accepted (%d triangles)" % core.tri_count)
	var started := Time.get_ticks_usec()
	core.bake()
	var bake_ms := (Time.get_ticks_usec() - started) / 1000.0
	print("TIMING bake_ms=%.0f covered=%d overlap=%.4f texel_world=%.5f cell=%.4f" % [bake_ms, core.covered, core.overlap_ratio(), core.texel_world, core.cell])
	expect(core.covered > 200000 and core.overlap_ratio() < 0.01, "bake covers the atlas without overlap")
	core.start_layers(solid(core, Color(0.5, 0.5, 0.5)), solid(core, Color(0.5, 0.5, 0.5)))

	# Picking: straight at the front face.
	var hit: Dictionary = core.pick(Vector3(0.1, 0.2, 5.0), Vector3(0, 0, -1))
	expect(hit.hit and absf(hit.position.z - 0.8) < 1e-3 and hit.normal.dot(Vector3(0, 0, 1)) > 0.99, "ray pick hits the front face")
	expect(not core.pick(Vector3(5, 5, 5), Vector3(1, 0, 0)).hit, "ray pick misses empty space")
	var pick_started := Time.get_ticks_usec()
	for i in 200: core.pick(Vector3(randf_range(-0.7, 0.7), randf_range(-0.7, 0.7), 5.0), Vector3(0, 0, -1))
	print("TIMING pick_ms=%.3f" % ((Time.get_ticks_usec() - pick_started) / 200000.0))

	# Brush: only texels near the hit point change.
	var before: PackedByteArray = core.layers[0].data.duplicate()
	var radius := 0.08
	core.begin_stroke(false)
	var stamp_started := Time.get_ticks_usec()
	var changed: int = core.stamp(hit.position, hit.normal, radius, brush())
	var stamp_ms := (Time.get_ticks_usec() - stamp_started) / 1000.0
	core.end_stroke()
	print("TIMING stamp_ms=%.2f changed=%d (radius %.2f)" % [stamp_ms, changed, radius])
	var far_changed := 0
	var near_changed := 0
	var data: PackedByteArray = core.layers[0].data
	for t in core.size * core.size:
		if core.texel_slot[t] < 0: continue
		var o := t * 4
		if data[o] != before[o] or data[o + 1] != before[o + 1] or data[o + 2] != before[o + 2]:
			if core.texel_position(t).distance_to(hit.position) > radius + core.texel_world * 2.0: far_changed += 1
			else: near_changed += 1
	expect(changed > 100 and near_changed > 100 and far_changed == 0, "stamp changes only texels near the hit point (%d near, %d far)" % [near_changed, far_changed])
	var centre: int = core.nearest_texel(hit.position, hit.normal)
	expect(core.sample(centre).r > 0.95 and core.sample(centre).g < 0.05, "stamp centre takes the brush colour")

	# A stroke of 40 overlapping stamps keeps the opacity cap.
	core.begin_stroke(false)
	var many_started := Time.get_ticks_usec()
	for i in 40:
		core.stamp(hit.position + Vector3(0.004 * i - 0.08, -0.15, 0), hit.normal, 0.05, brush(Color(0, 0, 1), {"opacity": 0.5, "flow": 0.3}))
	var per_stamp := (Time.get_ticks_usec() - many_started) / 40000.0
	core.end_stroke()
	print("TIMING stroke_stamp_ms=%.2f (radius 0.05)" % per_stamp)
	var stroked: Color = core.sample(core.nearest_texel(hit.position + Vector3(0, -0.15, 0), hit.normal))
	expect(absf(stroked.b - 0.75) < 0.03 and absf(stroked.r - 0.25) < 0.03, "overlapping stamps stop at the stroke opacity (b=%.2f)" % stroked.b)
	expect(core.history.size() == 2 and core.history_index == 2, "each stroke is one history step")
	var big_started := Time.get_ticks_usec()
	core.begin_stroke(false)
	var big_changed: int = core.stamp(hit.position, hit.normal, 0.3, brush(Color.GREEN))
	core.end_stroke()
	print("TIMING big_stamp_ms=%.2f changed=%d (radius 0.3)" % [(Time.get_ticks_usec() - big_started) / 1000.0, big_changed])
	core.undo()

	# Eraser on a new layer.
	core.add_layer("칠")
	expect(core.layers.size() == 2 and core.current == 1, "new layer is added above and selected")
	var side: Dictionary = core.pick(Vector3(5.0, 0.0, 0.1), Vector3(-1, 0, 0))
	core.begin_stroke(false)
	core.stamp(side.position, side.normal, 0.1, brush(Color(0, 1, 0), {"hardness": 1.0}))
	core.end_stroke()
	var side_texel: int = core.nearest_texel(side.position, side.normal)
	expect(core.layers[1].data[side_texel * 4 + 3] == 255 and core.sample(side_texel).g > 0.95, "paint lands on the new layer")
	core.begin_stroke(true)
	core.stamp(side.position, side.normal, 0.05, brush(Color.BLACK, {"hardness": 1.0}))
	core.end_stroke()
	expect(core.layers[1].data[side_texel * 4 + 3] == 0 and absf(core.sample(side_texel).g - 0.5) < 0.02, "eraser clears the current layer at the centre")
	var ring: int = core.nearest_texel(side.position + Vector3(0, 0.075, 0), side.normal)
	expect(core.layers[1].data[ring * 4 + 3] == 255, "eraser leaves paint outside its radius")

	# Undo/redo restores exactly.
	var after_erase := snapshot(core)
	core.undo()
	expect(core.layers[1].data[side_texel * 4 + 3] == 255, "undo brings the erased paint back")
	core.redo()
	expect(snapshot(core) == after_erase, "redo restores the erased state exactly")
	core.jump(0)
	expect(core.layers.size() == 1 and core.layers[0].data == before, "undoing every step restores the starting pixels exactly")
	core.jump(core.history.size())
	expect(snapshot(core) == after_erase, "redoing every step restores the final state exactly")

	# Fill: left half red, right half blue on the base; fill the red half only.
	var fresh := Core.new()
	fresh.setup([box_slot()], 512)
	fresh.bake()
	var base := PackedByteArray(); base.resize(fresh.size * fresh.size * 4)
	for t in fresh.size * fresh.size:
		var left: bool = fresh.texel_slot[t] >= 0 and fresh.texel_position(t).x < -0.01
		var color := Color(0.9, 0.1, 0.1) if left else Color(0.1, 0.1, 0.9)
		if left and fresh.texel_position(t).y > 0.6: color = Color(0.86, 0.12, 0.1)
		base[t * 4] = int(color.r * 255); base[t * 4 + 1] = int(color.g * 255); base[t * 4 + 2] = int(color.b * 255); base[t * 4 + 3] = 255
	fresh.start_layers(base, base)
	var red_seed: int = fresh.nearest_texel(Vector3(-0.8, 0.0, 0.0), Vector3(-1, 0, 0))
	var fill_started := Time.get_ticks_usec()
	var filled: int = fresh.fill(red_seed, Color.YELLOW, 4, brush())
	print("TIMING fill_ms=%.0f filled=%d" % [(Time.get_ticks_usec() - fill_started) / 1000.0, filled])
	var wrong := 0
	var yellow := 0
	var upper_red := 0
	for t in fresh.size * fresh.size:
		if fresh.texel_slot[t] < 0: continue
		var p: Vector3 = fresh.texel_position(t)
		var c: Color = fresh.sample(t)
		if p.x > 0.01 and c.g > 0.5: wrong += 1
		if p.x < -0.02 and p.y < 0.58 and c.g > 0.9: yellow += 1
		if p.x < -0.02 and p.y > 0.62 and c.g < 0.5: upper_red += 1
	expect(wrong == 0 and yellow > 1000, "fill stays inside the matching colour (%d filled, %d outside)" % [yellow, wrong])
	expect(upper_red > 100, "fill tolerance keeps a slightly different red out")
	var top_left: int = fresh.nearest_texel(Vector3(-0.5, 0.5, 0.8), Vector3(0, 0, 1))
	expect(fresh.sample(top_left).g > 0.9 or fresh.texel_position(top_left).y > 0.6, "fill crosses UV seams onto other faces")
	fresh.undo()
	var wide: int = fresh.fill(red_seed, Color.YELLOW, 40, brush())
	expect(wide > filled, "a higher tolerance takes in the similar red too")

	# Gradient: black to white along X.
	fresh.add_layer("그라데이션")
	var graded_started := Time.get_ticks_usec()
	fresh.gradient(Vector3(-0.8, 0, 0), Vector3(0.8, 0, 0), false, Color.BLACK, Color.WHITE, brush())
	print("TIMING gradient_ms=%.0f" % ((Time.get_ticks_usec() - graded_started) / 1000.0))
	var g_left: Color = fresh.sample(fresh.nearest_texel(Vector3(-0.8, 0, 0.3), Vector3(-1, 0, 0)))
	var g_mid: Color = fresh.sample(fresh.nearest_texel(Vector3(0.0, 0.0, 0.8), Vector3(0, 0, 1)))
	var g_right: Color = fresh.sample(fresh.nearest_texel(Vector3(0.8, 0, 0.3), Vector3(1, 0, 0)))
	expect(g_left.r < 0.05 and g_right.r > 0.95 and absf(g_mid.r - 0.5) < 0.06, "linear gradient follows 3D positions (%.2f %.2f %.2f)" % [g_left.r, g_mid.r, g_right.r])
	fresh.set_layer_props(fresh.current, {"opacity": 0.5})
	var half: Color = fresh.sample(fresh.nearest_texel(Vector3(0.8, 0, 0.3), Vector3(1, 0, 0)))
	expect(half.b > 0.6 and half.r > 0.45 and half.r < 0.6, "layer opacity mixes with the layers below")
	fresh.set_layer_props(fresh.current, {"mode": Core.MULTIPLY, "opacity": 1.0})
	var multiplied: Color = fresh.sample(fresh.nearest_texel(Vector3(0.8, 0, 0.3), Vector3(1, 0, 0)))
	expect(absf(multiplied.b - 0.9) < 0.04 and multiplied.r < 0.15, "multiply layer darkens by its colour")
	fresh.add_layer("원형")
	fresh.gradient(Vector3(0, 0, 0.8), Vector3(0, 0.5, 0.8), true, Color.RED, Color(0, 0, 0, 0), brush(), 0)
	var radial_centre: Color = fresh.sample(fresh.nearest_texel(Vector3(0, 0, 0.8), Vector3(0, 0, 1)))
	expect(radial_centre.r > 0.9 and radial_centre.g < 0.1, "radial gradient starts at its centre colour")
	var composite_started := Time.get_ticks_usec()
	var flat: PackedByteArray = fresh.composite()
	print("TIMING composite_ms=%.0f layers=%d size=%d" % [(Time.get_ticks_usec() - composite_started) / 1000.0, fresh.layers.size(), fresh.size])
	var probe: int = fresh.nearest_texel(Vector3(0.8, 0, 0.3), Vector3(1, 0, 0))
	var probe_color: Color = fresh.sample(probe)
	expect(absi(flat[probe * 4] - int(probe_color.r * 255)) <= 2 and flat[probe * 4 + 3] == 255, "composite matches the per-texel sample")

	# Symmetry: a stamp on +X also paints the mirrored spot on -X.
	core.jump(0)
	core.symmetry = 1
	core.begin_stroke(false)
	var right_hit: Dictionary = core.pick(Vector3(0.4, 0.3, 5.0), Vector3(0, 0, -1))
	core.stamp(right_hit.position, right_hit.normal, 0.05, brush(Color.MAGENTA, {"hardness": 1.0}))
	core.end_stroke()
	var mirrored: int = core.nearest_texel(Vector3(-0.4, 0.3, 0.8), Vector3(0, 0, 1))
	expect(core.sample(mirrored).b > 0.95 and core.sample(mirrored).g < 0.05, "X symmetry paints the mirrored point")
	var off_axis: int = core.nearest_texel(Vector3(-0.4, -0.3, 0.8), Vector3(0, 0, 1))
	expect(absf(core.sample(off_axis).r - 0.5) < 0.02, "symmetry leaves other places alone")
	core.symmetry = 0

	# Elliptic and noisy tips stay inside the round footprint.
	core.begin_stroke(false)
	var flat_changed: int = core.stamp(hit.position, hit.normal, 0.1, brush(Color.BLACK, {"tip": Core.TIP_FLAT, "roundness": 0.25, "angle": 0.0, "right": Vector3.RIGHT, "up": Vector3.UP}))
	core.end_stroke()
	var wide_point: Color = core.sample(core.nearest_texel(hit.position + Vector3(0.07, 0, 0), hit.normal))
	var tall_point: Color = core.sample(core.nearest_texel(hit.position + Vector3(0, 0.07, 0), hit.normal))
	expect(flat_changed > 0 and wide_point.r < 0.2 and absf(tall_point.r - 0.5) < 0.02, "flat tip paints along its long axis only")
	core.begin_stroke(false)
	var noisy: int = core.stamp(hit.position + Vector3(0, -0.4, 0), hit.normal, 0.1, brush(Color.BLACK, {"tip": Core.TIP_NOISE, "hardness": 1.0, "right": Vector3.RIGHT, "up": Vector3.UP}))
	core.end_stroke()
	expect(noisy > 0, "noise tip paints")

	# No UVs: the engine reports it, so the workspace offers whole-object colour instead.
	var plain := box_slot()
	plain.erase("uvs")
	var bare := Core.new()
	bare.setup([plain], 256)
	expect(not bare.uv_ok, "a mesh without UVs is detected")
	var collapsed := box_slot()
	var zero := PackedVector2Array(); zero.resize((collapsed.vertices as PackedVector3Array).size())
	collapsed.uvs = zero
	bare.setup([collapsed], 256)
	expect(not bare.uv_ok, "UVs collapsed into one point count as missing")

	# Several parts share one atlas, one tile each.
	var parts := Core.new()
	parts.setup([box_slot(1.0, 2), box_slot(0.5, 2), box_slot(0.3, 2)], 256)
	expect(parts.slot_rects.size() == 3 and parts.slot_rects[1] == Rect2i(128, 0, 128, 128), "three parts get three atlas tiles")
	parts.bake()
	var slots_seen := {}
	for t in parts.size * parts.size:
		if parts.texel_slot[t] >= 0: slots_seen[parts.texel_slot[t]] = true
	expect(slots_seen.size() == 3, "every part is baked into its tile")
	print("PAINTER_CORE ", JSON.stringify({"passed": passes, "failed": failures}))
	quit(1 if failures else 0)
