extends SceneTree
## The first F2 (overlay not made yet): ImeCaret makes it and it must end up shown, not shown and
## hidden again by the same key press. A second F2 hides it.
func _initialize() -> void: call_deferred("run")

func press() -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_F2
	event.physical_keycode = KEY_F2
	event.pressed = true
	Input.parse_input_event(event)
	for i in 3: await process_frame
	var up := event.duplicate()
	up.pressed = false
	Input.parse_input_event(up)
	for i in 3: await process_frame

func run() -> void:
	for i in 5: await process_frame
	print("before: ", root.has_node("PerfOverlay"))
	await press()
	var overlay = root.get_node_or_null("PerfOverlay")
	var ok1: bool = overlay != null and overlay.visible
	print("FIRST_F2 made=", overlay != null, " visible=", overlay.visible if overlay else false)
	await press()
	var ok2: bool = overlay != null and not overlay.visible
	print("SECOND_F2 visible=", overlay.visible if overlay else false)
	print("PERF_OVERLAY_FIRST_KEY ", "PASS" if ok1 and ok2 else "FAIL")
	quit(0 if ok1 and ok2 else 1)
