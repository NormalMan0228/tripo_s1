extends SceneTree
## The craft window's size box (craft_size_box.gd), headless: step 1 drags on the floor for width and
## depth, step 2 drags up for the height, a later drag changes the height only, "다시 정하기" starts
## over, and a touch drag gives the same box as the mouse. No server.
##   godot --headless --path game --script res://tests/craft_size_box_check.gd
const CraftSizeBox = preload("res://scripts/craft_size_box.gd")
var failed := false
var changed: Array = []
var clears := 0

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func mouse(box: CraftSizeBox, at: Vector2, pressed := -1) -> void:
	var event: InputEvent
	if pressed < 0:
		var motion := InputEventMouseMotion.new()
		motion.position = at
		motion.button_mask = MOUSE_BUTTON_MASK_LEFT
		event = motion
	else:
		var button := InputEventMouseButton.new()
		button.button_index = MOUSE_BUTTON_LEFT
		button.pressed = pressed == 1
		button.position = at
		event = button
	box.canvas.gui_input.emit(event)

func touch(box: CraftSizeBox, at: Vector2, pressed := -1) -> void:
	var event: InputEvent
	if pressed < 0:
		var drag := InputEventScreenDrag.new()
		drag.position = at
		event = drag
	else:
		var tap := InputEventScreenTouch.new()
		tap.pressed = pressed == 1
		tap.position = at
		event = tap
	box.canvas.gui_input.emit(event)

func near(a: Vector3, b: Vector3) -> bool:
	return a.distance_to(b) < 0.001

func run() -> void:
	var host := Control.new()
	host.size = Vector2(420, 380)
	root.add_child(host)
	var box := CraftSizeBox.new()
	host.add_child(box)
	box.size = Vector2(400, 340)
	box.dims_changed.connect(func(d: Vector3) -> void: changed.append(d))
	box.cleared.connect(func() -> void: clears += 1)
	for i in 3: await process_frame
	box._fit()
	expect(box.canvas.size.y >= 250.0 and box._scale > 20.0, "the canvas has room for the grid (%s, %.1f px/m)" % [box.canvas.size, box._scale])
	expect(box.step == CraftSizeBox.FLOOR and not box.has_box() and box.hint.text.begins_with("1"), "starts at step 1 on the floor")

	# Step 1: press near the centre, drag to the corner (0.6, 0, 0.3) -> 1.20 wide, 0.60 deep.
	mouse(box, box._project(Vector3(0.1, 0, 0.1)), 1)
	mouse(box, box._project(Vector3(0.4, 0, 0.2)))
	mouse(box, box._project(Vector3(0.61, 0, 0.29)))
	expect(near(box.dims, Vector3(1.2, 0, 0.6)) and box.step == CraftSizeBox.FLOOR, "the floor drag sets width and depth, snapped (%s)" % box.dims)
	mouse(box, box._project(Vector3(0.61, 0, 0.29)), 0)
	expect(box.step == CraftSizeBox.HEIGHT and box.hint.text.begins_with("2") and changed.is_empty(), "releasing goes to step 2, nothing sent yet")
	expect(box.sizes.text.contains("1.20m") and box.sizes.text.contains("0.60m"), "live sizes label (%s)" % box.sizes.text)

	# Step 2: drag up 0.8 m from the 0.1 m start -> 0.90 tall.
	var start := Vector2(200, 200)
	mouse(box, start, 1)
	mouse(box, start + Vector2(0, -0.4 * box._scale))
	mouse(box, start + Vector2(30, -0.8 * box._scale))
	mouse(box, start + Vector2(30, -0.8 * box._scale), 0)
	expect(box.has_box() and near(box.dims, Vector3(1.2, 0.9, 0.6)), "the height drag finishes the box (%s)" % box.dims)
	expect(changed.size() == 1 and near(changed[0], Vector3(1.2, 0.9, 0.6)), "dims_changed once with the box")
	expect(box.value() == [1.2, 0.9, 0.6], "value() for the request (%s)" % [box.value()])
	expect(box.sizes.text.contains("0.90m"), "the label shows the height (%s)" % box.sizes.text)

	# A later drag changes only the height and clamps at 3 m.
	mouse(box, start, 1)
	mouse(box, start + Vector2(0, -10.0 * box._scale))
	mouse(box, start + Vector2(0, -10.0 * box._scale), 0)
	expect(near(box.dims, Vector3(1.2, 3.0, 0.6)) and changed.size() == 2, "a later drag sets the height only, up to 3 m (%s)" % box.dims)
	mouse(box, start, 1)
	mouse(box, start + Vector2(0, 10.0 * box._scale))
	mouse(box, start + Vector2(0, 10.0 * box._scale), 0)
	expect(near(box.dims, Vector3(1.2, 0.1, 0.6)), "and down to 0.1 m (%s)" % box.dims)

	# Far outside the grid clamps the floor to 3 m a side.
	box.reset()
	expect(clears == 1 and box.step == CraftSizeBox.FLOOR and box.dims == Vector3.ZERO and box.sizes.text.is_empty(), "다시 정하기 starts over")
	mouse(box, box._project(Vector3(5, 0, 0.02)), 1)
	mouse(box, box._project(Vector3(5, 0, 0.02)), 0)
	expect(near(box.dims, Vector3(3.0, 0.1, 0.1)), "the floor clamps to 0.1..3 m (%s)" % box.dims)

	# Touch: the same two drags with the finger.
	box.reset()
	touch(box, box._project(Vector3(0.2, 0, 0.2)), 1)
	touch(box, box._project(Vector3(1.0, 0, 0.5)))
	touch(box, box._project(Vector3(1.0, 0, 0.5)), 0)
	touch(box, start, 1)
	touch(box, start + Vector2(0, -1.4 * box._scale))
	touch(box, start + Vector2(0, -1.4 * box._scale), 0)
	expect(box.has_box() and near(box.dims, Vector3(2.0, 1.5, 1.0)), "touch drags make the same kind of box (%s)" % box.dims)

	# A remembered box opens finished, without a signal.
	var before := changed.size()
	box.reset()
	box.set_dims(Vector3(0.42, 1.77, 9.0))
	expect(box.has_box() and near(box.dims, Vector3(0.4, 1.75, 3.0)) and changed.size() == before, "set_dims snaps and clamps a remembered box (%s)" % box.dims)

	# Drawing (headless still runs the draw pass) after a few smoothing frames.
	for i in 30: await process_frame
	expect(near(box.shown, box.dims), "the drawn box catches up with the chosen one")
	host.queue_free()
	await process_frame
	print("CRAFT_SIZE_BOX ", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
