extends SceneTree
## Crafting is one feature in two places. The village and the home open the same craft window with C
## (same controls, words, options, size and place, the same 제작 slot), and one craft started in the
## village goes on in the home and back: the picture and the finished object are announced once each,
## by one follower for the session. Runs against the QA server (demo mode fakes the crafting).
## With --capture it saves artifacts/craft-one-side-by-side.png (the village and the home window).
const CraftPanel = preload("res://scripts/craft_panel.gd")
const CraftTracker = preload("res://scripts/craft_tracker.gd")
const CraftWords = preload("res://scripts/craft_words.gd")
const Transition = preload("res://scripts/transition.gd")
var failed := false
var url := preload("res://tests/qa_server.gd").url()
var shots: Array[Image] = []

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("Craft one-feature check exceeded 240 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func wait_for(condition: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return condition.call()

## The village after a scene change, standing and uncovered.
func village() -> Node:
	await wait_for(func() -> bool: return is_instance_valid(current_scene) and current_scene.get("screen") == "village" and Transition.instance != null and is_zero_approx(Transition.instance.veil.modulate.a), 60.0)
	return current_scene

## The home after a scene change, with its /v1/studio read.
func home() -> Node:
	await wait_for(func() -> bool: return is_instance_valid(current_scene) and current_scene.get("room") == "home" and not current_scene.data.is_empty(), 60.0)
	return current_scene

func press(key: Key) -> void:
	for down in [true, false]:
		var event := InputEventKey.new()
		event.physical_keycode = key
		event.keycode = key
		event.pressed = down
		Input.parse_input_event(event)
		await process_frame

## Everything the window shows, in order: each visible control's kind, words, choices and state,
## and the card's place on the screen.
func signature(window: Control) -> Dictionary:
	var controls := []
	for node in window.find_children("*", "Control", true, false):
		if not node.is_visible_in_tree(): continue
		var entry: String = node.get_class()
		if node is OptionButton:
			var items := []
			for i in node.item_count: items.append(node.get_item_text(i) + ("(off)" if node.is_item_disabled(i) else ""))
			entry += ":" + ",".join(items) + "@" + str(node.selected)
		elif node is Button: entry += ":" + node.text + (":off" if node.disabled else "") + (":on" if node.button_pressed else "")
		elif node is Label: entry += ":" + node.text
		elif node is TextEdit: entry += ":" + node.placeholder_text
		controls.append(entry)
	var card: Control = window.card
	return {"controls": controls, "card": Rect2(card.global_position, card.size), "theme": window.theme}

func compare(a: Dictionary, b: Dictionary, what: String) -> void:
	var same: bool = a.controls == b.controls
	if not same:
		for i in maxi(a.controls.size(), b.controls.size()):
			var left: String = a.controls[i] if i < a.controls.size() else "-"
			var right: String = b.controls[i] if i < b.controls.size() else "-"
			if left != right: print("  DIFF %d village=%s room=%s" % [i, left, right])
	expect(same and a.controls.size() > 20, what + ": the same controls, words and options (%d)" % a.controls.size())
	expect(a.card.is_equal_approx(b.card) and a.theme == b.theme, what + ": the same card size, place and look (%s / %s)" % [a.card, b.card])
	var screen := Rect2(Vector2.ZERO, root.get_visible_rect().size)
	expect(screen.encloses(a.card) and absf(a.card.get_center().x - screen.get_center().x) < 1.0, what + ": the card is whole and centred on the screen (%s in %s)" % [a.card, screen])

func slot_of(place: Node) -> Button:
	for b in place.find_children("*", "Button", true, false):
		if b.tooltip_text == tr("제작") + "  ·  C" and b.theme_type_variation == "HudSlot": return b
	return null

func capture() -> void:
	if "--capture" not in OS.get_cmdline_user_args(): return
	for i in 20: await process_frame
	await RenderingServer.frame_post_draw
	shots.append(root.get_texture().get_image())

func trackers() -> int:
	return root.get_children().filter(func(node: Node) -> bool: return str(node.name).begins_with("CraftTracker")).size()

func run() -> void:
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = url
	var login: Dictionary = await api.post("/v1/auth/register", {"username": "one_" + str(Time.get_ticks_usec()), "password": "Craft-one-password-1"})
	expect(login.ok, "a fresh account")
	if not login.ok: quit(1); return
	Engine.set_meta("studio_session", {"token": login.data.token, "url": url, "room": "home"})
	change_scene_to_file("res://scenes/main.tscn")
	var town: Node = await village()
	expect(town.screen == "village", "the village stands")
	# 1. Village: C opens the craft window; a craft is asked for, then the player walks into the home.
	await press(KEY_C)
	expect(is_instance_valid(town.craft_window) and town.craft_box is CraftPanel, "the village's C opens the craft window")
	await wait_for(func() -> bool: return not town.craft_box.style_buttons.is_empty(), 10.0)
	await create_timer(0.6).timeout
	var village_form := signature(town.craft_window)
	var village_slot := slot_of(town)
	var village_slot_size: Vector2 = village_slot.size if village_slot else Vector2.ZERO
	await capture()
	await town.request_craft("small wooden chest")
	var tracker: Node = town.craft_tracker()
	var craft: String = tracker.job_id
	expect(not craft.is_empty(), "the village's craft was accepted")
	town.close_village_modal()
	town.open_studio("home")
	# 2. Home: the same craft goes on; its picture is announced once.
	var room: Node = await home()
	expect(room.room == "home" and not is_instance_valid(town), "walked into the home (the village is gone)")
	expect(CraftTracker.of(room.api) == tracker and tracker.host == room, "the home speaks for the same craft follower")
	await wait_for(func() -> bool: return str(tracker.job.get("state", "")) == "awaiting_confirmation", 30.0)
	expect(str(tracker.job.get("id", "")) == craft and str(tracker.job.get("state", "")) == "awaiting_confirmation", "the craft reached its picture while the player was away from the village")
	await press(KEY_C)
	expect(is_instance_valid(room.craft_window) and room.craft.job_id == craft and str(room.craft.job.get("state", "")) == "awaiting_confirmation", "the home's C opens the same craft at its picture")
	var buttons: Array = room.craft.status.find_children("*", "Button", true, false).map(func(b: Button) -> String: return b.text)
	expect(buttons.any(func(text: String) -> bool: return text.begins_with(tr("이 그림으로 만들기").split(" ·")[0])) and buttons.has(tr("모습 미리보기")), "the quote offers the picture, the preview and the cancel")
	await room.confirm_job()
	await press(KEY_ESCAPE)
	expect(not is_instance_valid(room.craft_window), "Esc closes the window in the home")
	room.leave()
	# 3. Back in the village: the object is finished there; announced once.
	town = await village()
	await wait_for(func() -> bool: return not tracker.done.is_empty(), 40.0)
	expect(str(tracker.done.get("id", "")) == craft and str(tracker.done.get("state", "")) == "ready", "the craft finished after walking back out")
	var pictures: Array = tracker.told.filter(func(entry: String) -> bool: return entry.begins_with("picture:" + craft))
	var endings: Array = tracker.told.filter(func(entry: String) -> bool: return entry == "ended:" + craft)
	expect(pictures.size() == 1 and endings.size() == 1, "the picture and the finished object were announced once each (%s)" % [tracker.told])
	expect(tracker.waiting.is_empty() and trackers() == 1 and CraftTracker.trackers.size() == 1, "one follower for the session, nothing left unsaid")
	await town.refresh_inventory()
	expect(town.me.objects.any(func(o: Dictionary) -> bool: return o.id == str(tracker.done.get("object_id", ""))), "the new object is in the bag")
	await press(KEY_C)
	var finished: Array = town.craft_box.status.find_children("*", "Button", true, false).map(func(b: Button) -> String: return b.text)
	expect(finished.has(tr(CraftWords.PLACE)) and finished.has(tr("새로 만들기")), "the village window shows the finished craft with 여기에 놓기")
	town.craft_box.status.find_children("*", "Button", true, false).filter(func(b: Button) -> bool: return b.text == tr("새로 만들기"))[0].pressed.emit()
	await process_frame
	expect(town.craft_box.form.visible and tracker.done.is_empty(), "새로 만들기 clears it everywhere")
	town.close_village_modal()
	# 4. Home again: the same window, word for word, at the same size and place.
	town.open_studio("home")
	room = await home()
	await press(KEY_C)
	expect(is_instance_valid(room.craft_window) and room.craft.form.visible, "the home's C opens the form")
	await wait_for(func() -> bool: return not room.craft.style_buttons.is_empty(), 10.0)
	await create_timer(0.6).timeout
	compare(village_form, signature(room.craft_window), "village and home windows")
	var room_slot := slot_of(room)
	expect(village_slot_size != Vector2.ZERO and room_slot != null and village_slot_size == room_slot.size, "the same 제작 slot (C) in both hotbars")
	expect(room.dock_toggle.tooltip_text == tr("가방") + "  ·  I" and room.default_hint().contains(tr("I 가방   C 제작")), "the home's bag is I, as in the village, and the key line says so")
	await capture()
	if shots.size() == 2:
		var a: Image = shots[0]
		var b: Image = shots[1]
		var both := Image.create(a.get_width() + b.get_width(), maxi(a.get_height(), b.get_height()), false, a.get_format())
		both.blit_rect(a, Rect2i(Vector2i.ZERO, a.get_size()), Vector2i.ZERO)
		b.convert(a.get_format())
		both.blit_rect(b, Rect2i(Vector2i.ZERO, b.get_size()), Vector2i(a.get_width(), 0))
		expect(both.save_png(ProjectSettings.globalize_path("res://../artifacts/craft-one-side-by-side.png")) == OK, "side-by-side capture saved")
	room.close_craft()
	print("CRAFT_ONE " + ("FAILED" if failed else "OK"))
	quit(1 if failed else 0)
