extends SceneTree
## Key caps and key tooltips follow rebinding (U-WP-02). Builds the village HUD and a room HUD
## against recorded replies (tests/ui_stub_api.gd), rebinds 가방 (inventory) to J and checks the
## hotbar cap shows J and its tooltip reads "가방  ·  J" in both, then resets to I. Also checks the
## shared controls: the painted close icon, close_key, key_text, key_hint, button variants, badge
## and swatch. Headless:
##   godot --headless --path game --script res://tests/keycap_rebind_check.gd -- --qa
const Main = preload("res://scripts/main.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const I18n = preload("res://scripts/i18n.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
var failures := 0
var checks := 0

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("Keycap rebind check exceeded 240 seconds")
		quit(2))

func expect(ok: bool, what: String) -> void:
	checks += 1
	print(("PASS " if ok else "FAIL ") + what)
	if not ok: failures += 1

func settle(seconds := 0.3) -> void:
	await create_timer(seconds).timeout

func t(text: String) -> String:
	return TranslationServer.translate(text)

func run() -> void:
	expect("--qa" in OS.get_cmdline_user_args() and I18n.settings_path().ends_with("settings_qa.cfg"), "QA settings file in use")
	I18n.setup()
	GameSettings.reset_bindings()
	controls()
	await village()
	await room()
	GameSettings.reset_bindings()
	print("KEYCAP_REBIND ", JSON.stringify({"checks":checks, "failures":failures}))
	quit(1 if failures else 0)

## The cap and the tooltip of a hotbar slot.
func slot_keys(slot: Control) -> Array:
	var cap := ""
	for child in slot.get_children():
		if child is Label and child.has_meta("key_action"): cap = (child as Label).text
	return [cap, slot.tooltip_text]

func controls() -> void:
	expect(RpgUi.painted("res://assets/ui/close.svg") == "res://assets/ui/icons/close.png" and ResourceLoader.exists("res://assets/ui/icons/close.png"), "RpgUi.painted('close') resolves the painted PNG")
	expect(RpgUi.key_text("inventory") == "I" and RpgUi.key_text("map") == "Tab" and RpgUi.key_text("Esc") == "Esc" and RpgUi.key_text("1-9") == "1-9", "key_text: action ids give their key, literals pass through")
	var host := Control.new()
	root.add_child(host)
	var closed := [false]
	var close := RpgUi.close_key(host, func(): closed[0] = true)
	close.pressed.emit()
	expect(close.get_meta("rpg_close", false) and close.tooltip_text == t("닫기") + "  ·  Esc" and close.custom_minimum_size == Vector2(34, 34)
		and close.focus_mode == Control.FOCUS_NONE and close.flat and close.icon != null and close.icon.resource_path.ends_with("icons/close.png") and closed[0], "close_key: flat 34 px painted icon, '닫기 · Esc', calls back")
	var craft_close := RpgUi.close_key(host, func(): pass, "craft")
	expect(craft_close.tooltip_text == t("닫기") + "  ·  C", "close_key with an action names its key")
	var hint := RpgUi.key_hint(host, "interact", t("닫기"))
	var cap: Label = hint.get_child(0)
	expect(cap.text == "E" and (hint.get_meta("words") as Label).text == t("닫기"), "key_hint: [E] 닫기")
	var sizes := []
	for size in ["sm", "md", "lg", "menu"]: sizes.append(int(RpgUi.button(host, "x", func(): pass, "normal", size).custom_minimum_size.y))
	expect(sizes == [32, 40, 44, 52], "button sizes sm/md/lg/menu %s" % [sizes])
	var missing := []
	for variant in RpgUi.BUTTON_VARIANTS:
		var type: String = RpgUi.BUTTON_VARIANTS[variant]
		if type.is_empty(): continue
		for theme in [RpgUi.theme(), RpgUi.night_theme()]:
			if not theme.has_stylebox("normal", type) or not theme.has_color("font_color", type): missing.append(type)
	var ghost := RpgUi.button(host, "x", func(): pass, "ghost", "md", true)
	expect(missing.is_empty() and ghost.theme_type_variation == "GhostButton" and ghost.focus_mode == Control.FOCUS_ALL, "every button variant is styled in both themes %s; menus take focus" % [missing])
	var slot := Button.new()
	slot.custom_minimum_size = Vector2(70, 70)
	host.add_child(slot)
	var pill := RpgUi.badge(slot, 3)
	var shown := pill.visible and pill.text == "3"
	RpgUi.badge(slot, 0)
	expect(shown and not pill.visible and slot.get_node("Badge") == pill, "badge shows a count and hides at 0")
	var picked := [""]
	var dot := RpgUi.swatch(host, "#d98477", true, func(): picked[0] = "coral")
	dot.pressed.emit()
	expect(dot.tooltip_text == t("산호색") and (dot.get_theme_stylebox("normal") as StyleBoxFlat).border_color == RpgUi.HOVER and picked[0] == "coral", "swatch: named, gold rim when chosen, calls back")
	# Rebinding relabels caps and tooltips built from an action.
	GameSettings.rebind("craft", 0, KEY_G)
	RpgUi.relabel_keys()
	expect(craft_close.tooltip_text == t("닫기") + "  ·  G", "a rebind relabels the close key's tooltip")
	GameSettings.reset_bindings()
	host.free()

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
	app.social.enabled = false
	await app.enter_village()
	await settle(1.0)
	expect(app.screen == "village", "village built from recorded replies")
	var bar: Control = app.expedition_button.get_parent()
	var bag: Control = bar.get_child(0)
	var before := slot_keys(bag)
	var others := []
	for i in 5: others.append(slot_keys(bar.get_child(i))[0])
	expect(before == ["I", t("가방") + "  ·  I"] and others == ["I", "C", "Tab", "B", "O"], "village hotbar caps %s, bag tooltip '%s'" % [others, before[1]])
	GameSettings.rebind("inventory", 0, KEY_J)
	await process_frame
	await process_frame
	expect(root.has_node("RpgUiKeys"), "one key watcher listens for rebinding")
	var after := slot_keys(bag)
	expect(after == ["J", t("가방") + "  ·  J"], "after the rebind the bag cap shows J and the tooltip reads '%s'" % after[1])
	GameSettings.reset_bindings()
	await process_frame
	expect(slot_keys(bag) == before, "reset restores I")
	app.queue_free()
	await settle(0.5)

func room() -> void:
	Engine.set_meta("studio_session", {"token":"", "url":"http://gallery.invalid", "room":"01_cafe"})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	root.add_child(studio)
	await settle(2.5)
	var bag: Control = studio.dock_toggle
	var craft: Control = studio.craft_slot
	expect(slot_keys(bag) == ["I", t("가방") + "  ·  I"] and slot_keys(craft) == ["C", t("제작") + "  ·  C"], "room hotbar: 가방 I, 제작 C")
	GameSettings.rebind("inventory", 0, KEY_J)
	await process_frame
	expect(slot_keys(bag) == ["J", t("가방") + "  ·  J"], "the room's bag cap follows the rebind too")
	GameSettings.reset_bindings()
	await process_frame
	expect(slot_keys(bag)[0] == "I", "and comes back to I")
	studio.queue_free()
	Engine.remove_meta("studio_session")
	await settle(0.5)
