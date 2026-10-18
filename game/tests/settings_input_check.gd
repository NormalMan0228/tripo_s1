extends SceneTree
## Real viewport key/mouse events: closing a settings screen can replace its owner UI.
const SettingsMenu = preload("res://scripts/settings_menu.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const PauseMenu = preload("res://scripts/pause_menu.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
var failures := 0
var checks := 0
var holder: Control
var title_closes := 0
var clicked := 0

class App extends Node:
	var screen := "survival"
	var paused := false
	var run := {"status":"active"}
	var pending_action := "attack"
	var pending_target := "target"
	var coop_run := false
	var results_shown := false
	var player: Node
	var ui: Control
	func suspend_run() -> void: pass
	func confirm_return() -> void: pass
	func logout() -> void: pass

func check(ok: bool, what: String) -> void:
	checks += 1
	print(("PASS " if ok else "FAIL ") + what)
	if not ok: failures += 1

func _initialize() -> void:
	call_deferred("run_game_only" if "--only-game" in OS.get_cmdline_user_args() else "run")

func run_game_only() -> void:
	root.size = Vector2i(1280,800)
	GameSettings.apply_all(self)
	await settle()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): await check_game(arg.trim_prefix("--server="))
	print("SETTINGS_INPUT_DONE checks=%d failures=%d" % [checks,failures])
	quit(1 if failures else 0)

func settle() -> void:
	for i in 12: await process_frame
	await create_timer(.2).timeout

func key(code: int, physical := true) -> void:
	for down in [true, false]:
		var event := InputEventKey.new()
		event.keycode = code
		if physical: event.physical_keycode = code
		event.pressed = down
		root.push_input(event,true)
		await process_frame
	await settle()

func pad_back() -> void:
	for down in [true,false]:
		var event := InputEventJoypadButton.new()
		event.button_index = JOY_BUTTON_B
		event.pressed = down
		root.push_input(event,true)
		await process_frame
	await settle()

func click(button: BaseButton) -> void:
	var at := button.get_global_transform_with_canvas() * (button.size * .5)
	var motion := InputEventMouseMotion.new()
	motion.position = at
	motion.global_position = at
	root.push_input(motion,true)
	await process_frame
	var hovered := root.gui_get_hovered_control()
	if hovered != button:
		print("CLICK_TARGET ",button.get_path()," at ",at," hovered ",hovered.get_path() if is_instance_valid(hovered) else "none")
	for down in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = at
		event.global_position = at
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = down
		root.push_input(event,true)
		await process_frame
	await settle()

func button_named(node: Node, words: String) -> BaseButton:
	for child in node.get_children():
		if child is Button and child.text == words: return child
		var found := button_named(child, words)
		if found: return found
	return null

func title_closed() -> void:
	# main.login_ui() calls clear_ui(), removing SettingsMenu synchronously.
	for child in holder.get_children():
		holder.remove_child(child)
		child.queue_free()
	title_closes += 1
	var button := RpgUi.button(holder, "title probe", func(): clicked += 1)
	button.position = Vector2(30,30)
	button.size = Vector2(200,50)

func run() -> void:
	root.size = Vector2i(1280,800)
	GameSettings.apply_all(self)
	await settle()
	holder = Control.new()
	holder.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(holder)
	for physical in [true,false]:
		var menu = SettingsMenu.open(holder, title_closed)
		await settle()
		var before := title_closes
		await key(KEY_ESCAPE, physical)
		check(title_closes == before+1 and not is_instance_valid(menu), "title Esc closes settings (%s)" % ("physical" if physical else "logical"))
		if is_instance_valid(menu): menu.close()
		await settle()
		var probe := button_named(holder,"title probe")
		var count := clicked
		await click(probe)
		check(clicked == count+1, "title buttons accept clicks after closing settings")
	var pad_menu = SettingsMenu.open(holder,title_closed)
	await settle()
	pad_menu.set_draft("music",43 if int(pad_menu.draft.music)!=43 else 44)
	await key(KEY_ESCAPE)
	await pad_back()
	check(not is_instance_valid(pad_menu.confirm), "gamepad back cancels unsaved-edits question")
	pad_menu.apply()
	await pad_back()
	check(not is_instance_valid(pad_menu), "gamepad back closes title settings safely")
	for context in ["village","survival","room"]:
		var app := App.new()
		app.screen = context
		app.ui = holder
		root.add_child(app)
		var pause = PauseMenu.open(app)
		await settle()
		await click(button_named(pause.root,"설정"))
		check(pause.view == "settings", "%s pause settings opens by click" % context)
		var menu = pause.sub
		if not is_instance_valid(menu):
			PauseMenu.close(); app.queue_free(); await settle(); continue
		await click(menu.tab_buttons.audio)
		check(menu.tab == "audio", "%s settings tab accepts mouse" % context)
		menu.set_draft("music", 41 if int(menu.draft.music)!=41 else 42)
		await key(KEY_ESCAPE)
		check(is_instance_valid(menu.confirm), "%s edited settings asks before Esc close" % context)
		await click(button_named(menu.confirm,"취소"))
		check(not is_instance_valid(menu.confirm) and pause.view == "settings", "%s cancel keeps settings interactive" % context)
		await click(menu.apply_button)
		check(not menu.dirty(), "%s apply button saves after cancel" % context)
		await key(KEY_ESCAPE)
		check(pause.view == "main" and not is_instance_valid(menu), "%s Esc returns to pause menu" % context)
		await click(button_named(pause.root,"조작 안내"))
		check(pause.view == "controls", "%s buttons work after settings Esc" % context)
		await key(KEY_ESCAPE)
		check(pause.view == "main", "%s Esc leaves controls only" % context)
		await key(KEY_ESCAPE)
		check(not PauseMenu.is_open() and not app.paused, "%s second Esc resumes play" % context)
		app.queue_free()
		await settle()
	holder.queue_free()
	await settle()
	await check_large_ui()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): await check_game(arg.trim_prefix("--server="))
	print("SETTINGS_INPUT_DONE checks=%d failures=%d" % [checks,failures])
	quit(1 if failures else 0)

func check_large_ui() -> void:
	GameSettings.commit({"ui_scale":140,"large_text":true})
	var host := Control.new()
	host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(host)
	var menu = SettingsMenu.open(host)
	await settle()
	for entry in SettingsMenu.TABS:
		await click(menu.tab_buttons[entry[0]])
		check(menu.tab == entry[0], "140%% UI: %s tab clickable" % entry[0])
		var foot := button_named(menu,"닫기")
		check(root.get_visible_rect().encloses(foot.get_global_rect()), "140%% UI: %s close button stays on screen" % entry[0])
	await click(button_named(menu,"닫기"))
	check(not is_instance_valid(menu), "140% UI: close button responds")
	host.queue_free()
	await settle()
	GameSettings.commit({"ui_scale":100,"large_text":false})

func check_game(server: String) -> void:
	preload("res://scripts/i18n.gd").remember("server",server)
	var app: Node = load("res://scripts/main.gd").new()
	root.add_child(app)
	for i in 600:
		if app.title_page == "menu": break
		await create_timer(.1).timeout
	check(app.title_page == "menu", "real game reaches title")
	app.login_ui("settings")
	await settle()
	await key(KEY_ESCAPE)
	check(app.title_page == "menu" and app.ui.find_child("SettingsMenu",true,false)==null, "real title Esc returns to working main menu")
	await click(button_named(app.ui,"설정"))
	check(app.title_page == "settings", "real title settings button works again after Esc")
	await key(KEY_ESCAPE)
	await app.authenticate(true,server,"settings_"+str(Time.get_ticks_msec()),"Settings-qa-password123","")
	check(app.screen == "village", "real game authenticates to local village")
	if app.screen == "village":
		await check_game_pause(app,"village")
		await app.start_run("forest","standard")
		check(app.screen == "survival", "real expedition starts")
		if app.screen == "survival": await check_game_pause(app,"survival")
	app.queue_free()
	await settle()

func check_game_pause(app: Node, context: String) -> void:
	# Open the real game's menu by Esc, then click through the real layered UI.
	var veil = preload("res://scripts/transition.gd").of(self)
	for i in 200:
		if veil.veil.mouse_filter == Control.MOUSE_FILTER_IGNORE: break
		await create_timer(.05).timeout
	check(veil.veil.mouse_filter == Control.MOUSE_FILTER_IGNORE, "real %s loading overlay releases input" % context)
	await key(KEY_ESCAPE)
	var pause = PauseMenu.current
	check(PauseMenu.is_open(), "real %s Esc opens pause" % context)
	if not PauseMenu.is_open(): return
	await click(button_named(pause.root,"설정"))
	check(pause.view == "settings", "real %s settings button responds" % context)
	if pause.view != "settings": PauseMenu.close(); return
	var menu = pause.sub
	await click(menu.tab_buttons.audio)
	check(menu.tab == "audio", "real %s audio tab responds" % context)
	menu.set_draft("music",33 if int(menu.draft.music)!=33 else 34)
	await key(KEY_ESCAPE)
	check(is_instance_valid(menu.confirm), "real %s Esc asks about unsaved edits" % context)
	if is_instance_valid(menu.confirm):
		await click(button_named(menu.confirm,"버리고 닫기"))
	check(pause.view == "main", "real %s discard button returns to pause" % context)
	await click(button_named(pause.root,"계속하기"))
	check(not PauseMenu.is_open() and not app.paused, "real %s continue button resumes" % context)
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		var folder := ProjectSettings.globalize_path("res://../artifacts")
		for arg in OS.get_cmdline_user_args():
			if arg.begins_with("--artifacts="): folder=arg.trim_prefix("--artifacts=")
		root.get_texture().get_image().save_png(folder.path_join("settings-after-esc-"+context+".png"))
