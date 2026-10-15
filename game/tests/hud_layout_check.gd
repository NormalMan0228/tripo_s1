extends SceneTree
## HUD layout (docs/design/UI_UNIFICATION.md 5 and 8): in the village, on an expedition and in a
## room, at UI scale 80, 100, 120 and 140 % (GameSettings ui_scale -> root.content_scale_factor),
## the visible HUD pieces do not overlap: the character frame (the field's status card), the chat
## box (SocialHud.of(api).chat), the hotbar tray, the prompt chip (with a long line), the toast lane
## (three toasts on it), the minimap / the field's map card / the room's location card, the goal
## card and the field's day counter. Against recorded replies (tests/ui_stub_api.gd, no port), with
## the social layer bound as in tests/chat_box_check.gd. Headless or windowed:
##   godot --headless --path game --script res://tests/hud_layout_check.gd -- --qa
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const I18n = preload("res://scripts/i18n.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const SocialHud = preload("res://scripts/social_hud.gd")
const SCALES := [80, 100, 120, 140]
## A long prompt line (a resident's title and the talk verb), the widest the chip usually gets.
const PROMPT_TEXT := "모루 · 야영 전문가와 이야기하기"
const TOASTS := ["물결빛 마을에 오신 것을 환영해요! 다리를 건너 다섯 섬을 둘러보세요.", "해가 졌어요. 야영지로 돌아가 불을 지키세요.", "가구를 놓았어요"]
var failures: Array[String] = []
var checks := 0
var app: Node
var stub: Node
var hub: Node

func _initialize() -> void:
	call_deferred("run")
	create_timer(300).timeout.connect(func():
		push_error("hud_layout_check exceeded 300 seconds")
		quit(2))

func expect(value: bool, message: String) -> void:
	checks += 1
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func settle(seconds := 0.3) -> void:
	await create_timer(seconds).timeout

func t(text: String) -> String:
	return TranslationServer.translate(text)

func run() -> void:
	expect("--qa" in OS.get_cmdline_user_args() and I18n.settings_path().ends_with("settings_qa.cfg"), "QA settings file in use")
	I18n.setup()
	RpgUi.set_folds(RpgUi.FOLD_TIPS.keys() + ["chat"], false, false)
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	fixture["/v1/social/presence"] = {"self_id":"me", "host_id":"me", "host_name":"haneul", "visiting":false, "party":null, "invites":[],
		"pending_rewards":[], "village":{"players":[{"id":"me", "username":"haneul", "x":0, "z":0}]}, "messages":[]}
	app = Main.new()
	root.add_child(app)
	await settle(1.6)
	app.api.queue_free()
	stub = Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = true
	await app.enter_village()
	preload("res://scripts/transition.gd").of(self).fade_in()
	await settle(1.2)
	hub = SocialHud.of(stub)
	expect(hub != null and is_instance_valid(hub.chat) and hub.chat.visible, "the village binds the chat box")
	# The village: frame, minimap, goal card, hotbar, prompt, toasts and the chat.
	app.prompt_wait = 1.0e9
	for scale in SCALES:
		await at_scale(scale)
		var pieces := {
			"frame": app.frame.get("panel"), "minimap": app.minimap, "objective": app.objective_card,
			"hotbar": hotbar_tray(app.expedition_button.get_parent()), "chat": hub.chat}
		await lane_rects(app.toast_lane, pieces, func(text): app.message(text))
		prompt_rect(app.hint, pieces)
		assert_apart("village", scale, pieces)
	await at_scale(100)
	# An expedition: status card, map card, goal card, day counter, the icon hotbar, prompt, toasts.
	await app.start_run("forest", "standard")
	await settle(1.4)
	expect(app.screen == "survival", "expedition built from recorded replies")
	expect(hub.chat.visible and hub.place == app, "the expedition keeps the chat box bound")
	for scale in SCALES:
		await at_scale(scale)
		var pieces := {
			"frame": app.left.get_parent(), "minimap": app.field_panel, "objective": app.objective_card,
			"day": app.day_track.get_parent(), "hotbar": hotbar_tray(app.toolbar_bar), "chat": hub.chat}
		await lane_rects(app.toast_lane, pieces, func(text): app.message(text))
		prompt_rect(app.hint, pieces)
		assert_apart("survival", scale, pieces)
		# The expedition's old social chip under the day counter (social.gd) is retired by U-WP-14;
		# until then it is reported, not failed.
		var chip := app.ui.get_node_or_null("SocialChip") as Control
		if chip and chip.is_visible_in_tree() and pieces.get("toasts") is Rect2 and chip.get_global_rect().intersects(pieces.toasts):
			print("NOTE survival %d%%: the SocialChip %s lies under the toast lane %s (U-WP-14 retires it)" % [scale, chip.get_global_rect(), pieces.toasts])
	await at_scale(100)
	app.queue_free()
	await settle(0.6)
	await room()
	GameSettings.set_value("ui_scale", 100)
	SocialHud.end()
	print("HUD_LAYOUT ", JSON.stringify({"checks":checks, "failures":failures.size()}))
	quit(0 if failures.is_empty() else 1)

## The player's own home (all its hotbar slots), the chat bound to it as studio.social_hub() does.
func room() -> void:
	Engine.set_meta("studio_session", {"token":"", "url":"http://gallery.invalid", "room":"home", "username":"haneul", "coins":12})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	root.add_child(studio)
	await settle(2.5)
	hub.bind(studio, "room", studio.toast_lane)
	await settle(0.2)
	expect(hub.chat.visible and hub.place == studio, "the room binds the chat box")
	expect(studio.frame.name.text == "haneul" and studio.dock_toggle.visible and studio.room_buttons[1].visible and not studio.room_buttons[0].visible,
		"the home's frame names the player; its hotbar has the bag and the way to the workshop")
	for scale in SCALES:
		await at_scale(scale)
		var pieces := {
			"frame": studio.frame.get("panel"), "location": studio.name_panel,
			"hotbar": hotbar_tray(studio.dock_toggle.get_parent()), "chat": hub.chat}
		await lane_rects(studio.toast_lane, pieces, func(text): studio.message(text))
		studio.set_chip("interact", PROMPT_TEXT)
		pieces["prompt"] = studio.hint_chip.get_global_rect() if studio.hint_chip.is_visible_in_tree() else null
		assert_apart("room", scale, pieces)
	await at_scale(100)
	hub.unbind(studio)
	studio.queue_free()
	await settle(0.5)

func at_scale(percent: int) -> void:
	GameSettings.set_value("ui_scale", percent)
	for i in 4: await process_frame
	expect(is_equal_approx(root.content_scale_factor, percent / 100.0), "ui_scale %d%% sets the root's content scale" % percent)

func hotbar_tray(bar: Node) -> Control:
	return bar.get_meta("tray") if bar and bar.has_meta("tray") else null

## Three toasts on the lane: their rects together are the lane's piece.
func lane_rects(lane: Control, pieces: Dictionary, say: Callable) -> void:
	RpgUi.clear_toasts(lane)
	await process_frame
	for text in TOASTS: say.call(t(text))
	await settle(0.4)
	var area := Rect2()
	for pill in RpgUi.toasts(lane):
		var rect: Rect2 = (pill as Control).get_global_rect()
		area = rect if area.size == Vector2.ZERO else area.merge(rect)
	expect(RpgUi.toasts(lane).size() == 3, "three toasts stand on the lane")
	pieces["toasts"] = area if area.size != Vector2.ZERO else null

## The prompt chip with a long line, measured in the same frame (the place rewrites it soon after).
func prompt_rect(chip: Label, pieces: Dictionary) -> void:
	RpgUi.set_prompt(chip, RpgUi.key_text("interact") + "  " + t(PROMPT_TEXT))
	chip.visible = true
	pieces["prompt"] = chip.get_global_rect()

## No two visible pieces overlap; every piece stays on the screen.
func assert_apart(place: String, scale: int, pieces: Dictionary) -> void:
	var screen: Rect2 = root.get_visible_rect()
	var rects := {}
	for key in pieces:
		var piece = pieces[key]
		if piece is Rect2: rects[key] = piece
		elif piece is Control and is_instance_valid(piece) and (piece as Control).is_visible_in_tree(): rects[key] = (piece as Control).get_global_rect()
	expect(rects.size() == pieces.size(), "%s %d%%: every piece is shown %s of %s" % [place, scale, rects.keys(), pieces.keys()])
	var outside := []
	for key in rects:
		if not screen.grow(1.0).encloses(rects[key]): outside.append("%s %s" % [key, rects[key]])
	expect(outside.is_empty(), "%s %d%%: every piece is on the %s screen %s" % [place, scale, screen.size, outside])
	var keys: Array = rects.keys()
	var clashes := []
	for i in keys.size():
		for j in range(i + 1, keys.size()):
			var a: Rect2 = rects[keys[i]]
			var b: Rect2 = rects[keys[j]]
			if a.intersects(b): clashes.append("%s×%s %s" % [keys[i], keys[j], a.intersection(b).size.round()])
	expect(clashes.is_empty(), "%s %d%%: no HUD pieces overlap %s" % [place, scale, clashes])
	if not clashes.is_empty():
		for key in rects: print("    %s %s" % [key, rects[key]])
