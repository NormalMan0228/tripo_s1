extends SceneTree
## Korean typed into every text field a player can type in, while each screen's periodic work keeps
## running (presence poll every 0.25 s, furniture proximity, bag refresh, a room's refresh): login
## (ID focused by the page, world address), the village craft window, 함께하기 (invite name; chat:
## two messages in a row with Enter, no click between), the interaction editor's describe box, the
## painter's layer name (focused by the painter) and a room's craft tab.
## Windowed on Windows with the Korean IME, the keys go through the real IME: tools/ime_type.ps1
## presses 2-beolsik keys with SendInput, only while this window is in front, and the field is
## focused with a click like a player's. Headless (or without the Korean IME) the committed syllables
## an IME delivers are sent as key events instead: no composition then, but focus and text must still
## survive the refreshes and Enter.
##   godot --path game --resolution 1280x800 [--position X,Y] --script res://tests/ime_typing.gd -- --mute --qa --server=http://127.0.0.1:8813
##   (add --headless for the committed-syllable mode; --position from tools/test_window_position.ps1)
const Main = preload("res://scripts/main.gd")
var server := "http://127.0.0.1:8766"
var failed := false
var real_ime := false
var hwnd := 0
var app: Node3D
## Runs every few moments while keys are going in: the periodic refreshes of the screen under test.
var during := Callable()

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")
	create_timer(300).timeout.connect(func(): print("IME_TYPING timeout"); quit(2))

func wait_until(condition: Callable, seconds := 20.0) -> bool:
	var deadline := Time.get_ticks_msec()+int(seconds*1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call(): return true
		await process_frame
	return condition.call()

func click(control: Control) -> void:
	var at := control.get_global_rect().get_center()
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		event.position = at
		event.global_position = at
		Input.parse_input_event(event)
		await process_frame

func key(keycode: Key, unicode: int) -> void:
	for pressed in [true, false]:
		var event := InputEventKey.new()
		event.pressed = pressed
		event.keycode = keycode
		event.physical_keycode = keycode
		event.unicode = unicode if pressed else 0
		Input.parse_input_event(event)
		await process_frame

## Focuses the field (a click, or the screen's own focus), then types. Real IME: `keys` are the
## 2-beolsik keys ("gksrmf" = 한글, '>' Enter, '.' a short pause). Otherwise `text` goes in as
## committed syllables ('\n' Enter). Returns "0 ..." when typed, "2 ..." when another window took
## the front, "3 ..." without a Korean IME.
func type_into(field: Control, keys: String, text: String, clicked := true) -> String:
	if clicked: await click(field)
	if root.gui_get_focus_owner() != field:
		print("  (focus was on %s, hovered %s; grabbing)" % [root.gui_get_focus_owner(), root.gui_get_hovered_control()])
		field.grab_focus()
	for i in 5: await process_frame
	var last := Time.get_ticks_msec()
	if not real_ime:
		for ch in text:
			if ch == "\n":
				await key(KEY_ENTER, 0)
				await create_timer(1.0).timeout  # the server takes one chat line a second
			else: await key(KEY_NONE, ch.unicode_at(0))
			await create_timer(0.08).timeout
			if Time.get_ticks_msec()-last > 300 and during.is_valid(): last = Time.get_ticks_msec(); during.call()
		for i in 10: await process_frame
		return "0 committed syllables"
	var log := ProjectSettings.globalize_path("user://ime_type.txt")
	if FileAccess.file_exists(log): DirAccess.remove_absolute(log)
	var script := ProjectSettings.globalize_path("res://../tools/ime_type.ps1")
	var pid := OS.create_process("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Hwnd", str(hwnd), "-Keys", keys, "-Log", log, "-DelayMs", "70"])
	while OS.is_process_running(pid):
		if Time.get_ticks_msec()-last > 300 and during.is_valid(): last = Time.get_ticks_msec(); during.call()
		await process_frame
	for i in 10: await process_frame
	var report := FileAccess.get_file_as_string(log).strip_edges() if FileAccess.file_exists(log) else "3 no driver log"
	if report.begins_with("3"):
		print("  no Korean IME (%s): committed syllables from here on" % report)
		real_ime = false
		return await type_into(field, keys, text, clicked)
	return "%s %s" % [report, "(real IME)"]

## Types into a field and checks its whole text; with a trace of its changes and focus moves on a
## failure. Another window taking the front (another test, the player) stops the driver: typed again.
func typed(field: Control, keys: String, text: String, label: String, clicked := true) -> String:
	var trace: PackedStringArray = []
	var started := Time.get_ticks_msec()
	var on_text := func(_value = null): trace.append("%d text '%s'" % [Time.get_ticks_msec()-started, field.text])
	var on_submit := func(value): trace.append("%d submit '%s'" % [Time.get_ticks_msec()-started, value])
	var on_focus := func(c: Control): trace.append("%d focus %s" % [Time.get_ticks_msec()-started, c.name if c else "none"])
	field.text_changed.connect(on_text)
	if field is LineEdit: field.text_submitted.connect(on_submit)
	root.gui_focus_changed.connect(on_focus)
	var report := ""
	var before: String = field.text
	for attempt in 3:
		if attempt > 0 or clicked:
			field.text = "" if clicked else before
			if field is LineEdit and not clicked: field.select_all()
		trace.clear()
		report = await type_into(field, keys, text, clicked)
		if not report.begins_with("2"): break
		await create_timer(1.0).timeout
	root.gui_focus_changed.disconnect(on_focus)
	if is_instance_valid(field):
		field.text_changed.disconnect(on_text)
		if field is LineEdit: field.text_submitted.disconnect(on_submit)
	if not report.begins_with("0"):
		print("SKIP %s: %s" % [label, report])
		return ""
	var wanted := text if not text.contains("\n") else ""
	var ok: bool = is_instance_valid(field) and field.text == wanted
	expect(ok, "%s: '%s' (%s)" % [label, field.text if is_instance_valid(field) else "<freed>", report])
	if not ok or text.contains("\n"): print("  trace: ", " | ".join(trace))
	return report

func fields_in(node: Node, type: String) -> Array:
	return node.find_children("*", type, true, false).filter(func(c): return c.is_visible_in_tree())

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	real_ime = OS.get_name() == "Windows" and DisplayServer.get_name() != "headless" and DisplayServer.has_feature(DisplayServer.FEATURE_IME)
	if real_ime: hwnd = DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE)
	print("IME_TYPING mode: ", "real Korean IME" if real_ime else "committed syllables")
	app = Main.new()
	root.add_child(app)
	await wait_until(func(): return not app.busy and app.screen == "login", 60.0)

	# Login page: the page focuses the ID itself and the player just types; then the world address.
	app.login_ui("login")
	for i in 10: await process_frame
	var lines := fields_in(app.ui, "LineEdit")
	if lines.size() >= 2:
		lines[0].text = ""
		await typed(lines[0], "gksrmf dkdlel ", "한글 아이디 ", "login ID (focused by the page)", false)
	var servers: Array = app.ui.find_children("*", "OptionButton", true, false)
	if not servers.is_empty():
		servers[0].select(servers[0].item_count-1)
		servers[0].item_selected.emit(servers[0].item_count-1)
		await process_frame
		var custom := fields_in(app.ui, "LineEdit").filter(func(f): return not f.secret and f != lines[0])
		if not custom.is_empty():
			await typed(custom[0], "dnjfem wnth ", "월드 주소 ", "login world address")

	var name := "ime_"+str(Time.get_ticks_msec())
	for _attempt in 3:
		await app.authenticate(true, server, name, "Ime-typing-password-1", "")
		if app.screen == "village": break
		await create_timer(0.5).timeout
	expect(app.screen == "village", "signed in (%s)" % app.screen)
	if app.screen != "village": quit(1); return
	await create_timer(1.0).timeout  # the arrival veil takes clicks while it fades

	# The village craft window (C), while the bag refreshes on top of the village's own polling.
	during = func(): app.refresh_inventory()
	await app.open_craft()
	await create_timer(0.6).timeout  # the window pops in
	if is_instance_valid(app.craft_box):
		await typed(app.craft_box.prompt, "wkrdms. qjtjt. ahdid. dmlwk ", "작은 버섯 모양 의자 ", "village craft prompt")
	app.close_village_modal()

	# 함께하기 while presence polls: the invite name, then two chat lines with Enter, no click between.
	during = func(): app.social.poll()
	await app.social.open_menu()
	await create_timer(0.6).timeout
	var social_fields := fields_in(app.village_modal, "LineEdit") if is_instance_valid(app.village_modal) else []
	expect(social_fields.size() >= 2, "함께하기 has the invite and chat fields")
	if social_fields.size() >= 2:
		await typed(social_fields[0], "cheogkf. dlfma ", "초대할 이름 ", "social invite name")
		var chat: LineEdit = social_fields[social_fields.size()-1]
		var sent := await typed(chat, "dkssudgktpdy>....qksrkdnjdy>..", "안녕하세요\n반가워요\n", "social chat field empty after two Enters")
		var said := func() -> Array: return app.social.data.get("messages", []).map(func(m): return str(m.text))
		await wait_until(func(): return said.call().has("반가워요"), 5.0)
		if not sent.is_empty():
			expect(said.call().has("안녕하세요") and said.call().has("반가워요"), "social chat: both lines sent (%s)" % [said.call()])
	app.close_village_modal()
	during = Callable()

	# The interaction editor's describe box (글로 설명하기), on a free fixture chest.
	var queued: Dictionary = await app.api.post("/v1/studio/jobs", app.api.mutation({"prompt": "wooden chest", "geometry": "proxy", "designer": "fixture"}))
	var id := ""
	for _i in 60:
		var job: Dictionary = await app.api.request("/v1/studio/jobs/"+str(queued.get("data", {}).get("id", "")))
		if job.ok and job.data.state == "ready": id = job.data.object_id; break
		await create_timer(0.5).timeout
	await app.refresh_inventory()
	for i in app.me.objects.size():
		if app.me.objects[i].id == id: app.select_object(i)
	if await wait_until(func(): return is_instance_valid(app.inspect_model) and app.selected.get("id") == id and app.inspect_model.get_meta("studio", false)):
		app.open_interactions()
		var panel: Control = app.interaction_panel
		if await wait_until(func(): return is_instance_valid(panel) and not panel.info.is_empty()):
			panel.mode_buttons.custom.pressed.emit()
			await create_timer(0.4).timeout
			await typed(panel.describe_text, "ekrkrkaus. EnRjddl. dufflrh ", "다가가면 뚜껑이 열리고 ", "interaction describe box")
			panel.close_panel()
			await process_frame
		else: expect(false, "interaction editor opened")
		# The painter's layer name: the painter focuses it and selects the old name.
		app.open_painter()
		var painter: Control = app.painter
		if await wait_until(func(): return is_instance_valid(painter) and painter.core != null, 20.0):
			painter._start_rename()
			await typed(painter.rename_field, "qnf.Rhc ", "불꽃 ", "painter layer name (focused by the painter)", false)
			painter.queue_free()
			await process_frame
		else: expect(false, "painter opened")
	else: expect(false, "fixture chest in the bag")

	# A room's craft tab (the same craft window), while the room refreshes.
	var token: String = app.api.token
	var url: String = app.api.base_url
	app.queue_free()
	await process_frame
	Engine.set_meta("studio_session", {"token": token, "url": url, "room": "home"})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	root.add_child(studio)
	if await wait_until(func(): return is_instance_valid(studio.craft) and studio.craft_opened, 30.0):
		studio.set_dock_open(true)
		var tabs := studio.craft.get_parent().get_parent().get_parent() as TabContainer
		if tabs: tabs.current_tab = studio.craft.get_parent().get_parent().get_index()
		await create_timer(0.4).timeout
		during = func(): studio.refresh()
		await typed(studio.craft.prompt, "dhfmrhf. tkdwk ", "오르골 상자 ", "room craft prompt")
		during = Callable()
	else: expect(false, "room opened")
	print("IME_TYPING_DONE")
	quit(1 if failed else 0)
