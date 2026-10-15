extends SceneTree
## U-WP-04 key routing in the village, through real key events (Viewport.push_input):
## the key that opens a window closes it (Tab map, B storage, O wardrobe, C craft), Esc closes the
## top window, a side drawer on the window stack closes on Esc before the pause menu, and E, Space
## and Enter advance a conversation. Windowed or headless:
##   godot --path game --script res://tests/window_keys_check.gd
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const PauseMenu = preload("res://scripts/pause_menu.gd")
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
	print("WINDOW_KEYS ", "PASS" if failures.is_empty() else "FAIL %d" % failures.size())
	quit(0 if failures.is_empty() else 1)
