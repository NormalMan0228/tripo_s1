extends SceneTree
## U-WP-04 key routing in the village, through real key events (Viewport.push_input):
## the key that opens a window closes it (Tab map, B storage, O wardrobe, C craft), Esc closes the
## top window, a side drawer on the window stack closes on Esc before the pause menu, and E, Space
## and Enter advance a conversation. U-WP-05/06: the craft window is a shared window on the stack
## (C toggles it in the village and in a room too; its prompt takes Korean: a focusable text box
## without the Latin-only flag), the seed picker (1-5 keycaps, a digit picks, Esc closes), and in a
## room the storage chest (E or Esc) and the shape drawer. Windowed or headless:
##   godot --path game --script res://tests/window_keys_check.gd
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const PauseMenu = preload("res://scripts/pause_menu.gd")
const ShapePanel = preload("res://scripts/shape_panel.gd")
const CraftTracker = preload("res://scripts/craft_tracker.gd")
var failures: Array[String] = []
var app: Node

func expect(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("window_keys_check exceeded 240 seconds")
		quit(2))

func press(key: Key) -> void:
	for down in [true, false]:
		var event := InputEventKey.new()
		event.keycode = key
		event.physical_keycode = key
		event.pressed = down
		root.push_input(event)
		await process_frame
	await process_frame

## Committed syllables as an IME delivers them (key events with a unicode, no keycode).
func type_text(text: String) -> void:
	for ch in text:
		for down in [true, false]:
			var event := InputEventKey.new()
			event.pressed = down
			event.unicode = ch.unicode_at(0) if down else 0
			root.push_input(event)
			await process_frame

func shades_under(node: Node) -> int:
	return node.find_children("Shade", "TextureRect", true, false).size()

func close_keys(node: Node) -> Array:
	return node.find_children("*", "Button", true, false).filter(func(b): return b.get_meta("rpg_close", false))

## The craft prompt takes Korean: a visible, editable, focusable text box that is not Latin-only
## (RpgUi.field's flag); focused, committed syllables go in and it keeps the focus.
func check_prompt(prompt: TextEdit, where: String) -> void:
	expect(prompt != null and prompt.is_visible_in_tree() and prompt.editable and prompt.focus_mode == Control.FOCUS_ALL and not prompt.has_meta("latin"),
		"%s craft prompt: a visible, editable, focusable text box that allows the IME" % where)
	if prompt == null: return
	prompt.text = ""
	prompt.grab_focus()
	await process_frame
	await type_text("오르골 상자")
	expect(prompt.text == "오르골 상자" and prompt.has_focus(), "%s craft prompt: committed Korean syllables go in and it keeps the focus ('%s')" % [where, prompt.text])
	prompt.text = ""

func title_of(modal: Control) -> String:
	if not is_instance_valid(modal): return ""
	var w: Dictionary = modal.get_meta("rpg_window", {})
	return str((w.get("title") as Label).text) if w.get("title") is Label else modal.name

func run() -> void:
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = false
	await app.enter_village()
	await create_timer(0.8).timeout
	# Opening key toggles: the same key closes what it opened.
	for entry in [[KEY_TAB, "map"], [KEY_B, "storage"], [KEY_O, "wardrobe"]]:
		await press(entry[0])
		await create_timer(0.3).timeout
		var modal: Control = app.village_modal
		var opened: bool = is_instance_valid(modal) and str(app.modal_window(modal).get("action", "")) == entry[1]
		expect(opened, "%s opens with %s (%s)" % [entry[1], OS.get_keycode_string(entry[0]), title_of(modal)])
		await press(entry[0])
		await create_timer(0.3).timeout
		expect(not is_instance_valid(app.village_modal) and RpgUi.windows().is_empty(), "%s closes with the same key" % entry[1])
	# Esc closes the top window too.
	await press(KEY_TAB)
	await create_timer(0.3).timeout
	await press(KEY_ESCAPE)
	await create_timer(0.3).timeout
	expect(not is_instance_valid(app.village_modal), "Esc closes the map")
	expect(not is_instance_valid(PauseMenu.current), "the Esc that closed the map did not open the pause menu")
	# C: the craft window (its own window) opens and closes with C.
	await press(KEY_C)
	await create_timer(0.8).timeout
	var crafting: bool = is_instance_valid(app.craft_window) and app.village_modal == app.craft_window
	expect(crafting, "C opens the craft window")
	if crafting:
		var top := RpgUi.top_window()
		var closes := close_keys(app.craft_window)
		expect(top.get("id") == "craft" and top.get("action") == "craft" and top.get("root").get_parent() == app.craft_window and bool(top.get("modal")),
			"the craft window is a shared modal window on the stack (action craft)")
		expect(closes.size() == 1 and str(closes[0].tooltip_text).ends_with("C") and shades_under(app.ui) == 1, "the craft window: one shade, one close key named '…C' (%s)" % [closes.map(func(b): return b.tooltip_text)])
		expect(app.craft_window.note_lane.get_parent() == app.craft_window, "the craft notes keep their own lane over the card")
		await check_prompt(app.craft_box.prompt, "village")
	var field := app.get_viewport().gui_get_focus_owner()
	if field is LineEdit or field is TextEdit: field.release_focus()
	await press(KEY_C)
	await create_timer(0.4).timeout
	expect(not is_instance_valid(app.village_modal), "C closes the craft window when no field is focused")
	# A side drawer on the window stack: Esc closes it before anything else.
	var side := RpgUi.drawer(app.ui, "함께하기", {"side":"left", "action":"", "id":"probe_drawer"})
	await process_frame
	expect(RpgUi.top_window().get("id") == "probe_drawer", "a drawer is on the window stack")
	await press(KEY_ESCAPE)
	await create_timer(0.3).timeout
	expect(RpgUi.windows().is_empty(), "Esc closes the drawer")
	expect(not is_instance_valid(PauseMenu.current), "that Esc did not open the pause menu")
	# A conversation: E finishes the line, then turns the page; Enter and Space do the same.
	app.open_dialogue("하늘 · 별지기", "", ["첫 번째 줄이에요.", "두 번째 줄이에요.", "세 번째 줄이에요."], [["고마워요", Callable()]])
	await create_timer(0.2).timeout
	var body: Label = app.village_modal.find_children("*", "Label", true, false).filter(func(l): return l.text.begins_with("첫"))[0] if is_instance_valid(app.village_modal) else null
	expect(body != null and RpgUi.top_window().get("kind") == "dialogue", "the dialogue is on the window stack as a dialogue")
	await press(KEY_E)
	expect(body != null and is_equal_approx(body.visible_ratio, 1.0), "E shows the whole line")
	await press(KEY_E)
	expect(body != null and body.text.begins_with("두"), "E turns to the next page (%s)" % (body.text if body else ""))
	await press(KEY_ENTER)
	await press(KEY_ENTER)
	expect(body != null and body.text.begins_with("세"), "Enter turns the page too (%s)" % (body.text if body else ""))
	await press(KEY_ESCAPE)
	await create_timer(0.3).timeout
	expect(not is_instance_valid(app.village_modal) and RpgUi.windows().is_empty(), "Esc ends the conversation and it leaves the stack")
	await check_seed_picker()
	await check_room()
	print("WINDOW_KEYS ", "PASS" if failures.is_empty() else "FAIL %d" % failures.size())
	quit(0 if failures.is_empty() else 1)

## The seed picker: a night window just above the hotbar on the stack (no shade), the number keys
## on keycaps on the slots, a digit picks a seed, Esc closes.
func check_seed_picker() -> void:
	var free_plot := -1
	for i in app.life.state.get("plots", []).size():
		if not app.life.state.plots[i].get("crop"):
			free_plot = i
			break
	expect(free_plot >= 0, "the fixture has a free bed")
	if free_plot < 0: return
	app.life.open_plot(free_plot)
	await create_timer(0.3).timeout
	var top := RpgUi.top_window()
	var picker: Control = app.village_modal
	expect(is_instance_valid(picker) and top.get("id") == "seed_picker" and top.get("kind") == "night" and not bool(top.get("modal")) and shades_under(app.ui) == 0,
		"the seed picker is a night window on the stack without a shade")
	var caps: Array = picker.find_children("*", "Label", true, false).filter(func(l): return l.get_parent() is Button and l.text in ["1","2","3","4","5"]) if is_instance_valid(picker) else []
	var slots: Array = picker.find_children("Seed_*", "Button", true, false) if is_instance_valid(picker) else []
	expect(not slots.is_empty() and caps.size() == slots.size() and close_keys(picker).size() == 1, "every seed slot shows its number key on a keycap (%d slots, %d caps), one close key" % [slots.size(), caps.size()])
	await press(KEY_ESCAPE)
	await create_timer(0.3).timeout
	expect(not is_instance_valid(app.village_modal) and RpgUi.windows().is_empty() and not is_instance_valid(PauseMenu.current), "Esc closes the seed picker (and opens no pause menu)")
	app.life.open_plot(free_plot)
	await create_timer(0.3).timeout
	var first := str(app.life.seed_choices[0]) if not app.life.seed_choices.is_empty() else ""
	var stocked := int(app.life.state.bag.get(first + "_seed", 0)) > 0
	await press(KEY_1)
	await create_timer(0.3).timeout
	expect(stocked and not is_instance_valid(app.village_modal) and app.life.mode != "seeds", "1 picks the first seed (%s) and the picker closes" % first)

## A room (the cafe, offline): C opens the same craft window on the stack and C closes it, Esc
## closes it while typing; a finished craft opens the window on it and 새로 만들기 puts the caret
## in the box; the storage chest is a small window that E and Esc close; the shape drawer leaves
## on Esc.
func check_room() -> void:
	app.queue_free()
	await create_timer(0.4).timeout
	Engine.set_meta("studio_session", {"token":"", "url":"http://gallery.invalid", "room":"01_cafe"})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	root.add_child(studio)
	var deadline := Time.get_ticks_msec() + 30000
	while Time.get_ticks_msec() < deadline and not studio.is_processing_unhandled_key_input(): await process_frame
	await create_timer(0.6).timeout
	studio.api.token = "gallery"
	await press(KEY_C)
	await create_timer(0.6).timeout
	var open: bool = is_instance_valid(studio.craft_window)
	expect(open and RpgUi.top_window().get("action") == "craft" and studio.craft_window.window.get("root").get_parent() == studio.craft_window, "C opens the craft window in a room, on the window stack")
	if open:
		expect(close_keys(studio.craft_window).size() == 1 and str(close_keys(studio.craft_window)[0].tooltip_text).ends_with("C"), "the room's craft window has the one close key named '…C'")
		await check_prompt(studio.craft.prompt, "room")
		studio.craft.prompt.grab_focus()
		await press(KEY_ESCAPE)
		await create_timer(0.3).timeout
		expect(not is_instance_valid(studio.craft_window) and RpgUi.windows().is_empty(), "Esc closes the room's craft window while typing")
	await press(KEY_C)
	await create_timer(0.5).timeout
	var field := studio.get_viewport().gui_get_focus_owner()
	if field is LineEdit or field is TextEdit: field.release_focus()
	await press(KEY_C)
	await create_timer(0.4).timeout
	expect(not is_instance_valid(studio.craft_window) and RpgUi.windows().is_empty() and not is_instance_valid(PauseMenu.current), "C closes the room's craft window again")
	# A finished craft: the window opens on it (the form hidden); 새로 만들기 brings the form back with
	# the caret in the box, ready for Korean.
	var tracker: Node = CraftTracker.of(studio.api)
	if tracker:
		tracker.done = {"id":"finished", "state":"ready", "object_id":"o1", "prompt":"찻잔"}
		await press(KEY_C)
		await create_timer(0.6).timeout
		var shown: bool = is_instance_valid(studio.craft) and not studio.craft.form.visible and not studio.craft.prompt.is_visible_in_tree()
		expect(shown, "a finished craft opens the window on it, the form (and its prompt) hidden")
		var again: Array = studio.craft.status.find_children("*", "Button", true, false).filter(func(b): return b.text == tr("새로 만들기")) if is_instance_valid(studio.craft) else []
		if not again.is_empty(): (again[0] as Button).pressed.emit()
		await process_frame
		expect(is_instance_valid(studio.craft) and studio.craft.form.visible and studio.craft.prompt.has_focus() and tracker.done.is_empty(), "새로 만들기 shows the form with the caret in the prompt")
		if is_instance_valid(studio.craft): await check_prompt(studio.craft.prompt, "room (after 새로 만들기)")
		await press(KEY_ESCAPE)
		await create_timer(0.3).timeout
	# The storage chest (recorded reply): a small paper window, E or Esc closes it.
	var stub := Stub.new()
	stub.data = {"/v1/social/npc-homes/probe_home": {"stored": [{"name":"찻잔 세트", "npc":"", "tags":[]}, {"name":"작은 화분", "npc":"", "tags":[]}]}}
	studio.add_child(stub)
	var network: Node = studio.api
	studio.api = stub
	studio.gift_home = "probe_home"
	for key in [KEY_E, KEY_ESCAPE]:
		await studio.open_storage({})
		await create_timer(0.3).timeout
		var chest: Control = studio.talk_box
		var top := RpgUi.top_window()
		var hints: Array = chest.find_children("KeyHint", "HBoxContainer", true, false) if is_instance_valid(chest) else []
		expect(is_instance_valid(chest) and chest.name == "StorageChest" and top.get("id") == "storage_chest" and (top.get("card") as Control).custom_minimum_size.x == RpgUi.WINDOW_W.small
			and close_keys(chest).size() == 1 and shades_under(chest) == 1 and hints.size() == 1, "the storage chest: a 560 px window on the stack, one shade, one close key, one key hint")
		await press(key)
		await create_timer(0.3).timeout
		expect(not is_instance_valid(studio.talk_box) and RpgUi.windows().is_empty(), "%s closes the storage chest" % OS.get_keycode_string(key))
	studio.api = network
	stub.queue_free()
	# The shape drawer: night glass on the stack, Esc closes it.
	var shape := ShapePanel.new()
	shape.setup(network, {"id":"probe", "name":"찻잔", "shape":{}}, func(): return [], func(_t): pass, {"side":"left", "top":128.0})
	studio.add_child(shape)
	await create_timer(0.3).timeout
	var drawn := RpgUi.top_window()
	expect(drawn.get("id") == "shape_panel" and drawn.get("kind") == "drawer" and drawn.get("surface") == "night" and close_keys(shape).size() == 1, "the shape panel is a night drawer on the stack with the close key")
	await press(KEY_ESCAPE)
	await create_timer(0.3).timeout
	expect(not is_instance_valid(shape) and RpgUi.windows().is_empty() and not is_instance_valid(PauseMenu.current), "Esc closes the shape drawer (and opens no pause menu)")
	studio.queue_free()
	await create_timer(0.4).timeout
