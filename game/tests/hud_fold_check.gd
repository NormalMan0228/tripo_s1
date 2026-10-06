extends SceneTree
## HUD folding: every panel folds to its compact form and back, the state lands in
## [hud] of the settings file (user://settings_qa.cfg under --qa) and is read back,
## the HUD key (U) folds everything at once, and the bag drawer and conversations
## still hide the HUD. Builds the pieces on their own, then the real village and
## field HUDs against recorded server replies (tests/ui_stub_api.gd). Headless:
##   godot --headless --path game --script res://tests/hud_fold_check.gd -- --qa
const Main = preload("res://scripts/main.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const Minimap = preload("res://scripts/minimap.gd")
const I18n = preload("res://scripts/i18n.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const VILLAGE_IDS := ["objective", "minimap", "hotbar", "profile"]
var failed := false

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("HUD fold check exceeded 240 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func settle(seconds := 0.4) -> void:
	await create_timer(seconds).timeout

func saved(id: String) -> Variant:
	var config := ConfigFile.new()
	config.load(I18n.settings_path())
	return config.get_value("hud", id, null)

func clear_saved() -> void:
	var config := ConfigFile.new()
	config.load(I18n.settings_path())
	if config.has_section("hud"): config.erase_section("hud")
	config.save(I18n.settings_path())
	RpgUi.reload_folds()

func press(code: Key, app: Node) -> void:
	var event := InputEventKey.new()
	event.physical_keycode = code
	event.keycode = code
	event.pressed = true
	app._unhandled_input(event)

## A left click at the middle of a control, through the viewport's input path.
func click(c: Control) -> void:
	var at: Vector2 = root.get_final_transform() * (c.get_global_transform_with_canvas() * (c.size * 0.5))
	for down in [true, false]:
		var event := InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = down
		event.position = at
		event.global_position = at
		root.push_input(event)
		await process_frame

func chevron_angle(key: Control) -> float:
	return wrapf((key.get_node("Chevron") as Control).rotation, 0.0, TAU)

func run() -> void:
	expect("--qa" in OS.get_cmdline_user_args() and I18n.settings_path().ends_with("settings_qa.cfg"), "QA settings file in use")
	I18n.setup()
	clear_saved()
	await pieces()
	await village()
	clear_saved()
	print("HUD_FOLD_CHECK ", "FAIL" if failed else "OK")
	quit(1 if failed else 0)

## Each fold helper on its own canvas.
func pieces() -> void:
	var ui := Control.new()
	ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.theme = RpgUi.theme()
	root.add_child(ui)
	await process_frame
	# Objective card: folds to its header row, stays pinned right.
	var card := PanelContainer.new()
	card.position = Vector2(994, 246)
	card.custom_minimum_size.x = 272
	card.add_theme_stylebox_override("panel", RpgUi.panel_style("night"))
	ui.add_child(card)
	RpgUi.pin(card, 1.0, 0.0)
	var column := VBoxContainer.new()
	card.add_child(column)
	var head := HBoxContainer.new()
	column.add_child(head)
	head.add_child(RpgUi.icon("res://assets/ui/book.svg", 22))
	RpgUi.label(head, "목표", 15, RpgUi.GOLD)
	var body := VBoxContainer.new()
	column.add_child(body)
	RpgUi.divider(body)
	var goals := RpgUi.label(body, "▸ 첫째 목표\n▸ 둘째 목표\n▸ 셋째 목표\n\n미끼 5개", 14, RpgUi.INK, false)
	goals.custom_minimum_size.x = 240
	goals.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var key := RpgUi.fold_card(card, head, body, "objective")
	await settle(0.2)
	var clip := body.get_parent() as Control
	var open_height := card.size.y
	var right_edge := card.get_global_rect().end.x
	expect(clip.visible and clip.size.y > 60 and key.get_parent() == head, "objective card open with its key in the header")
	expect(key.tooltip_text == TranslationServer.translate("목표 접기") and absf(chevron_angle(key)) < 0.01, "key offers 목표 접기, chevron up")
	key.pressed.emit()
	await settle()
	expect(RpgUi.folded("objective") and saved("objective") == true, "objective fold saved to [hud]")
	expect(not clip.visible and card.size.y < open_height - 60, "card rolled up to its header (%d -> %d)" % [open_height, card.size.y])
	expect(absf(card.get_global_rect().end.x - right_edge) < 0.5 and card.size.y >= head.size.y, "folded card keeps its right edge and header")
	expect(key.tooltip_text == TranslationServer.translate("목표 펼치기") and absf(chevron_angle(key) - PI) < 0.01, "key offers 목표 펼치기, chevron down")
	goals.text = "▸ 새 목표\n▸ 하나 더"
	await settle(0.1)
	expect(not clip.visible and card.size.y < open_height - 60, "new goals keep a folded card folded")
	goals.text = "▸ 첫째 목표\n▸ 둘째 목표\n▸ 셋째 목표\n\n미끼 5개"
	key.pressed.emit()
	await settle()
	expect(clip.visible and absf(card.size.y - open_height) < 1.0 and saved("objective") == false, "card unfolded to full height (%d)" % card.size.y)
	goals.text = "▸ 한 줄"
	await settle(0.1)
	expect(card.size.y < open_height - 30, "open card shrinks with shorter goals")
	goals.text = "▸ 첫째 목표\n▸ 둘째 목표\n▸ 셋째 목표\n\n미끼 5개"
	# Reduced motion: instant (shown without saving, the way the menu previews).
	GameSettings.ensure_loaded()
	GameSettings.previewing["reduced_motion"] = true
	RpgUi.toggle_fold("objective")
	expect(not clip.visible and card.size.y < open_height - 60, "reduced motion folds instantly")
	RpgUi.toggle_fold("objective")
	GameSettings.previewing.erase("reduced_motion")
	await settle(0.1)
	# Minimap: only the chip stays, moved into the corner.
	var map := Minimap.new()
	map.position = Vector2(1060, 10)
	ui.add_child(map)
	await process_frame
	var map_right := map.get_global_rect().end.x
	expect(map.disc.visible and map.fold == 0.0 and map.chip_rect().position.y > 190, "minimap open: map disc over the chip")
	map.key.pressed.emit()
	await settle()
	var chip := map.chip_rect()
	expect(not map.disc.visible and map.fold == 1.0 and chip.position.y < 10, "minimap folded to the place · clock chip")
	expect(map.key.position.x + map.key.size.x <= chip.position.x and absf(map.key.position.y + map.key.size.y*0.5 - chip.get_center().y) < 1.0, "fold key sits beside the folded chip")
	expect(map.anchor_left == 1.0 and absf(map.get_global_rect().end.x - map_right) < 0.5, "minimap keeps its top-right anchoring")
	expect(saved("minimap") == true, "minimap fold saved")
	map.key.pressed.emit()
	await settle()
	expect(map.disc.visible and map.fold == 0.0 and absf(map.disc.modulate.a - 1.0) < 0.01, "minimap unfolded")
	# Hotbar: slides below the screen, a handle tab waits at the bottom centre.
	var presses := [0]
	var slots := []
	for i in 6: slots.append({"icon":"res://assets/ui/bag.svg","key":"I" if i == 0 else "","label":"가방","call":func(): presses[0] += 1})
	var bar := RpgUi.hotbar(ui, slots, 700, "hotbar")
	await process_frame
	var tray: Control = ui.get_child(bar.get_index()-1)
	var handle: Button = ui.get_node("FoldHandle")
	var dock_key: Button
	for child in ui.get_children():
		if child is Button and child.has_node("Chevron") and child != handle: dock_key = child
	var bar_top := bar.get_global_rect().position.y
	expect(bar.visible and tray.visible and not handle.visible and dock_key != null, "hotbar open with a fold key, no handle")
	expect(dock_key.get_global_rect().position.x >= tray.get_global_rect().end.x and absf(dock_key.get_global_rect().get_center().y - tray.get_global_rect().get_center().y) < 1.0, "hotbar key beside the tray's right end")
	dock_key.pressed.emit()
	await settle()
	expect(not bar.visible and not tray.visible and not dock_key.visible and handle.visible, "hotbar folded to its handle")
	var tab := handle.get_global_rect()
	expect(absf(tab.get_center().x - 640.0) < 1.0 and tab.end.y <= 800.0 and tab.end.y > 780.0, "handle centred on the bottom edge")
	expect(absf(chevron_angle(handle)) < 0.01 and handle.tooltip_text == TranslationServer.translate("퀵슬롯 펼치기"), "handle points up: 퀵슬롯 펼치기")
	(bar.get_child(0) as Button).pressed.emit()
	expect(presses[0] == 1, "slot actions still reachable while folded")
	handle.pressed.emit()
	await settle()
	expect(bar.visible and tray.visible and dock_key.visible and not handle.visible and absf(bar.get_global_rect().position.y - bar_top) < 0.5 and absf(tray.modulate.a - 0.92) < 0.01, "handle brings the hotbar back in place")
	# Character frame: folds to the medal; the social chip goes with it.
	var plate := RpgUi.player_frame(ui, "res://assets/ui/portrait_explorer.png", "profile")
	plate.name.text = "tester_long_name"
	var social := PanelContainer.new()
	social.position = Vector2(14, 108)
	social.custom_minimum_size = Vector2(200, 54)
	ui.add_child(social)
	RpgUi.fold_shift(social, "profile", Vector2(-36, 0))
	await settle(0.2)
	var shell: Control = plate.panel
	var wide := shell.size.x
	var badge: Button = null
	for child in shell.get_child(0).get_child(0).get_children():
		if child is Button: badge = child
	expect(badge != null and badge.tooltip_text == TranslationServer.translate("프로필 접기"), "medal carries the fold badge")
	badge.pressed.emit()
	await settle()
	var column_clip: Control = plate.column.get_parent()
	expect(not column_clip.visible and shell.self_modulate.a < 0.01 and shell.size.x < wide - 80, "frame folded to the medal (%d -> %d)" % [wide, shell.size.x])
	expect(not social.visible, "social chip folds away with the frame")
	badge.pressed.emit()
	await settle()
	expect(column_clip.visible and shell.self_modulate.a > 0.99 and absf(shell.size.x - wide) < 1.0, "frame unfolded")
	expect(social.visible and absf(social.position.x - 14.0) < 0.5 and absf(social.modulate.a - 1.0) < 0.01, "social chip back in place")
	# Fold all: a mixed state folds everything, then everything opens again.
	RpgUi.set_folded("minimap", true, false)
	var ids := RpgUi.fold_ids()
	expect(VILLAGE_IDS.all(func(id): return id in ids), "fold ids on screen: %s" % [ids])
	expect(RpgUi.toggle_all_folds() and VILLAGE_IDS.all(func(id): return RpgUi.folded(id) and saved(id) == true), "fold-all folds and saves every panel")
	await settle()
	expect(not clip.visible and not map.disc.visible and not bar.visible and handle.visible and not column_clip.visible, "every panel shows its folded form")
	expect(not RpgUi.toggle_all_folds() and VILLAGE_IDS.all(func(id): return not RpgUi.folded(id) and saved(id) == false), "fold-all again opens every panel")
	await settle()
	expect(clip.visible and map.disc.visible and bar.visible and not handle.visible and column_clip.visible, "every panel open again")
	# Remembered across sessions: the next HUD starts folded.
	RpgUi.set_folded("hotbar", true, false)
	RpgUi.set_folded("objective", true, false)
	ui.queue_free()
	await process_frame
	RpgUi.reload_folds()
	expect(RpgUi.folded("hotbar") and RpgUi.folded("objective") and not RpgUi.folded("minimap"), "fold states read back from the settings file")

## The real village and field HUDs (main.gd) against recorded replies.
func village() -> void:
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	var app = Main.new()
	root.add_child(app)
	await settle(1.6)
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = true
	await app.enter_village()
	await settle(1.0)
	expect(app.screen == "village", "village built from recorded replies")
	var ids := RpgUi.fold_ids()
	expect(VILLAGE_IDS.all(func(id): return id in ids), "village HUD registers %s" % [ids])
	var ui: Control = app.ui
	var handle: Control = ui.get_node_or_null("FoldHandle")
	var card: Control = app.objective_card
	var clip: Control = app.objective.get_parent().get_parent()
	var bar: Control = app.expedition_button.get_parent()
	var chip: Control = ui.get_node_or_null("SocialChip")
	expect(card is PanelContainer and clip.name == "FoldClip", "objective card wraps its goals in a fold clip")
	expect(handle != null and handle.visible and not bar.visible, "saved hotbar fold restored on entering the village")
	expect(not clip.visible and app.minimap.disc.visible, "saved objective fold restored, minimap open")
	expect(chip != null and chip.visible, "social chip under the frame")
	var card_top: float = card.position.y
	# U: the mixed state folds everything.
	press(KEY_U, app)
	await settle()
	expect(VILLAGE_IDS.all(func(id): return RpgUi.folded(id)), "U folds every village panel")
	expect(not app.minimap.disc.visible and card.position.y < card_top - 150 and card.get_global_rect().position.y > app.minimap.get_global_rect().position.y + 30, "tracker rises under the folded minimap chip")
	expect(not app.frame.column.get_parent().visible and not chip.visible and not bar.visible, "frame, social chip and hotbar folded")
	# Shortcuts still work while folded.
	press(KEY_I, app)
	await settle(0.3)
	expect(app.right.get_parent().visible and not card.visible and not app.minimap.visible, "I opens the bag while folded; tracker and minimap step aside")
	press(KEY_I, app)
	await settle(0.3)
	expect(not app.right.get_parent().visible and card.visible and app.minimap.visible, "closing the bag brings tracker and minimap back")
	# Conversations hide the folded HUD and restore it as it was.
	app.open_dialogue("나루", "naru", ["안녕하세요."], [["좋아요", Callable()]])
	await settle(0.3)
	expect(not handle.visible and not card.visible and not app.minimap.visible and not app.frame.panel.visible, "dialogue hides the folded HUD")
	app.close_village_modal()
	await settle(0.3)
	expect(handle.visible and not bar.visible and card.visible and app.minimap.visible and app.frame.panel.visible, "closing the dialogue restores the folded HUD")
	press(KEY_U, app)
	await settle()
	expect(VILLAGE_IDS.all(func(id): return not RpgUi.folded(id) and saved(id) == false), "U again opens every panel")
	expect(clip.visible and app.minimap.disc.visible and bar.visible and not handle.visible and chip.visible and app.frame.column.get_parent().visible, "village HUD open")
	expect(absf(card.position.y - card_top) < 1.0, "tracker back under the open map (y %d)" % card.position.y)
	app.open_dialogue("나루", "naru", ["안녕하세요."], [["좋아요", Callable()]])
	await settle(0.3)
	expect(not bar.visible and not card.visible and not handle.visible, "dialogue hides the open HUD")
	app.close_village_modal()
	await settle(0.3)
	expect(bar.visible and card.visible and not handle.visible, "and restores it")
	# Real mouse clicks on the keys.
	var dock_key: Button = null
	for child in ui.get_children():
		if child is Button and child.has_node("Chevron") and child != handle: dock_key = child
	await click(dock_key)
	await settle()
	expect(RpgUi.folded("hotbar") and not bar.visible and handle.visible, "clicking the hotbar key folds it")
	await click(handle)
	await settle()
	expect(not RpgUi.folded("hotbar") and bar.visible and not handle.visible, "clicking the handle tab unfolds it")
	var card_key: Button = card.find_child("Fold", true, false)
	await click(card_key)
	await settle()
	expect(RpgUi.folded("objective") and not clip.visible, "clicking the tracker key folds it")
	await click(card_key)
	await settle()
	expect(not RpgUi.folded("objective") and clip.visible, "and clicking again unfolds it")
	await click(app.minimap.key)
	await settle()
	expect(RpgUi.folded("minimap") and not app.minimap.disc.visible, "clicking the minimap key folds it")
	await click(app.minimap.key)
	await settle()
	expect(not RpgUi.folded("minimap") and app.minimap.disc.visible, "and the folded chip's key opens it")
	# Field HUD: goal card and toolbar.
	app.social.enabled = false
	await app.start_run("forest", "standard")
	await settle(1.4)
	expect(app.screen == "survival", "field run built from recorded replies")
	ids = RpgUi.fold_ids()
	expect("survival_objective" in ids and "toolbar" in ids and not ids.has("hotbar"), "field HUD registers %s" % [ids])
	var goal_card: Control = app.objective_card
	var goal_clip: Control = app.objective.get_parent().get_parent()
	var goal_height: float = goal_card.size.y
	var toolbar: Control = null
	for child in ui.get_children():
		if child is PanelContainer and child.get_global_rect().position.y > 600 and child.get_global_rect().size.x > 600: toolbar = child
	var field_handle: Control = ui.get_node_or_null("FoldHandle")
	expect(toolbar != null and toolbar.visible and field_handle != null and not field_handle.visible, "toolbar open, handle hidden")
	RpgUi.toggle_fold("survival_objective")
	await settle()
	expect(not goal_clip.visible and goal_card.size.y < goal_height - 40, "field goal card folds to its header")
	press(KEY_U, app)
	await settle()
	expect(RpgUi.folded("toolbar") and not toolbar.visible and field_handle.visible, "U folds the field toolbar to its handle")
	press(KEY_I, app)
	await settle(0.3)
	expect(app.right.get_parent().visible, "I still opens the field bag while the toolbar is folded")
	press(KEY_I, app)
	await settle(0.3)
	press(KEY_U, app)
	await settle()
	expect(not RpgUi.folded("toolbar") and toolbar.visible and not field_handle.visible and goal_clip.visible, "U opens the field HUD again")
	app.queue_free()
	await settle(0.5)
