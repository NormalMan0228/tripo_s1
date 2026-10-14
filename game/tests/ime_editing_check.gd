extends SceneTree
## Text fields keep taking Korean however they got focus (headless: the syllables an IME commits are
## sent as key events, the open composition is set on the IME helper).
## - A Godot 4.7 LineEdit types only while "editing": focused by a click, by code, deferred, while an
##   arrow key was held, after Enter without keep_editing_on_text_submit. ImeCaret makes it edit.
## - Esc leaves the field (focus goes) instead of leaving it focused but deaf.
## - The login page: Korean in the ID stays in the ID (focus and page stay), keys the IME passes on
##   (Hangul key, letters without text) move nothing; the password keeps Latin letters and says why.
## - The composition helper: caret hidden while composing, committed syllables kept, and syllables
##   that never arrive (engine bug godotengine/godot#123269) counted, with the Windows hint shown.
##   godot --headless --path game --script res://tests/ime_editing_check.gd
const Main = preload("res://scripts/main.gd")
const Ui = preload("res://scripts/rpg_ui.gd")
var failed := false
var helper: Node

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")
	create_timer(180).timeout.connect(func(): print("IME_EDITING timeout"); quit(2))

func frames(count := 2) -> void:
	for i in count: await process_frame

func send_key(keycode: Key, physical := KEY_NONE, unicode := 0) -> void:
	for pressed in [true, false]:
		var event := InputEventKey.new()
		event.pressed = pressed
		event.keycode = keycode
		event.physical_keycode = physical if physical != KEY_NONE else keycode
		event.unicode = unicode if pressed else 0
		Input.parse_input_event(event)
		await process_frame

## What the IME delivers for each committed syllable: a key press carrying only the character.
func commit(text: String) -> void:
	for ch in text:
		var event := InputEventKey.new()
		event.pressed = true
		event.unicode = ch.unicode_at(0)
		Input.parse_input_event(event)
		await process_frame

func click(control: Control) -> void:
	# Window pixels: the stretch (headless windows are not 1280x800) scales the canvas.
	var at := root.get_final_transform() * control.get_global_rect().get_center()
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		event.position = at
		event.global_position = at
		Input.parse_input_event(event)
		await process_frame

func run() -> void:
	helper = root.get_node("ImeCaret")
	var box := VBoxContainer.new()
	box.position = Vector2(40, 40)
	box.custom_minimum_size = Vector2(500, 0)
	root.add_child(box)

	# Every way a field gets focus ends with it typing.
	for way in ["click", "grab_focus", "deferred grab_focus", "grab_focus with an arrow held"]:
		var field := LineEdit.new()
		field.custom_minimum_size = Vector2(400, 40)
		box.add_child(field)
		await frames()
		match way:
			"click": await click(field)
			"grab_focus": field.grab_focus()
			"deferred grab_focus": field.grab_focus.call_deferred()
			"grab_focus with an arrow held":
				Input.action_press("ui_right")
				field.grab_focus()
				Input.action_release("ui_right")
		await frames()
		await commit("한글")
		expect(field.has_focus() and field.is_editing() and field.text == "한글", "LineEdit focused by %s types (editing %s, '%s')" % [way, field.is_editing(), field.text])
		field.queue_free()
	var area := TextEdit.new()
	area.custom_minimum_size = Vector2(400, 80)
	box.add_child(area)
	await frames()
	await click(area)
	await commit("입력")
	area.grab_focus()
	await commit("창")
	expect(area.text == "입력창", "TextEdit focused by a click and by code types ('%s')" % area.text)
	area.queue_free()

	# Enter without keep_editing_on_text_submit, then Esc.
	var line := LineEdit.new()
	line.keep_editing_on_text_submit = false
	box.add_child(line)
	await frames()
	line.grab_focus()
	await frames()
	await commit("가")
	await send_key(KEY_ENTER)
	await frames()
	await commit("나")
	expect(line.has_focus() and line.text == "가나", "after Enter the field still types ('%s', editing %s)" % [line.text, line.is_editing()])
	await send_key(KEY_ESCAPE)
	await frames()
	expect(root.gui_get_focus_owner() != line, "Esc leaves the field (focus %s)" % root.gui_get_focus_owner())
	line.queue_free()

	# The composition helper: caret, commits, lost syllables.
	expect(helper.starts_next_syllable("한", "ㄱ") and helper.starts_next_syllable("갑", "바") and not helper.starts_next_syllable("가", "ㄱ")
		and not helper.starts_next_syllable("가", "각") and not helper.starts_next_syllable("ㄱ", "가"), "syllable boundaries (한→ㄱ, 갑→바; not 가→ㄱ backspace, 가→각, ㄱ→가)")
	var typed := LineEdit.new()
	box.add_child(typed)
	await frames()
	typed.grab_focus()
	await frames()
	var lost: int = helper.lost_syllables
	for step in [["하", ""], ["한", ""], ["ㄱ", "한"], ["그", ""], ["글", ""], ["", "글"]]:
		helper.ime_override = step[0] if not str(step[0]).is_empty() else null
		if not str(step[1]).is_empty(): await commit(step[1])
		else: await process_frame
		if step[0] == "그": expect(typed.has_theme_constant_override("caret_width"), "caret hidden while a syllable is composed")
	await frames(12)
	expect(typed.text == "한글" and not typed.has_theme_constant_override("caret_width") and helper.lost_syllables == lost, "committed syllables kept, caret back, none counted lost ('%s', lost %d)" % [typed.text, helper.lost_syllables - lost])
	# The engine bug: each syllable replaces the last, nothing is committed.
	for comp in ["하", "한", "ㄱ", "그", "글", "ㅇ", "이"]:
		helper.ime_override = comp
		await frames(10)
	helper.ime_override = null
	await frames()
	expect(helper.lost_syllables - lost == 2 and is_instance_valid(helper.hint), "syllables that never arrive are counted (%d) and the Windows hint shows" % (helper.lost_syllables - lost))
	if is_instance_valid(helper.hint): helper.hint.queue_free()
	typed.queue_free()
	box.queue_free()
	await frames()

	# The login page.
	var app: Node = Main.new()
	root.add_child(app)
	var deadline := Time.get_ticks_msec() + 60000
	while app.screen != "login" and Time.get_ticks_msec() < deadline: await process_frame
	app.login_ui("login")
	await frames(10)
	# The title's arrival veil takes clicks until it has faded.
	var transition := root.get_node_or_null("Transition")
	deadline = Time.get_ticks_msec() + 20000
	while transition and transition.veil.mouse_filter != Control.MOUSE_FILTER_IGNORE and Time.get_ticks_msec() < deadline: await process_frame
	var fields: Array = app.ui.find_children("*", "LineEdit", true, false).filter(func(c): return c.is_visible_in_tree())
	var id_field: LineEdit = fields.filter(func(c): return not c.secret).front()
	var password: LineEdit = fields.filter(func(c): return c.secret).front()
	expect(root.gui_get_focus_owner() in [id_field, password] and root.gui_get_focus_owner().is_editing(), "the login page focuses a field that types (%s)" % root.gui_get_focus_owner())
	await click(id_field)
	id_field.text = ""
	await commit("한글")
	# Keys the IME passes on without text: the Hangul key (right Alt place), letters it composed.
	await send_key(KEY_UNKNOWN, KEY_ALT)
	for physical in [KEY_W, KEY_D, KEY_E, KEY_M, KEY_I]: await send_key(KEY_UNKNOWN, physical)
	await commit("아이디")
	await frames()
	expect(id_field.text == "한글아이디" and root.gui_get_focus_owner() == id_field and id_field.is_editing() and app.screen == "login" and app.title_page == "login",
		"Korean in the login ID stays there: '%s', focus %s, page %s/%s" % [id_field.text, root.gui_get_focus_owner(), app.screen, app.title_page])
	await click(password)
	password.text = ""
	await commit("ab한c")
	await frames()
	expect(password.text == "abc" and str(app.notice.text).contains("영문"), "the password keeps Latin letters and says why ('%s', notice '%s')" % [password.text, app.notice.text])
	print("IME_EDITING_DONE")
	quit(1 if failed else 0)
