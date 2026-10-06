extends SceneTree
## Picture-only controls name themselves on hover (RpgUi.name_tip): icon keys with no
## words, hoverable pictures and unlabelled HUD icons all resolve to a tooltip, and the
## tooltip itself is the painted night pill with outlined cream text. Builds the real
## village and field HUDs against recorded server replies (tests/ui_stub_api.gd), opens
## the bag drawers, the seed picker, the storage and the wardrobe, and hovers pictures
## through the viewport. Headless:
##   godot --headless --path game --script res://tests/tooltip_check.gd -- --qa
const Main = preload("res://scripts/main.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const I18n = preload("res://scripts/i18n.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const LifeIcon = preload("res://scripts/life_icon.gd")
var failed := false
var app

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("Tooltip check exceeded 240 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func settle(seconds := 0.4) -> void:
	await create_timer(seconds).timeout

func t(text: String) -> String:
	return TranslationServer.translate(text)

## Letters or digits a person can read, not just "●" or "×".
func has_words(text: String) -> bool:
	for i in text.length():
		var code := text.unicode_at(i)
		if text[i].to_upper() != text[i].to_lower() or (code >= 0x30 and code <= 0x39): return true
		if (code >= 0xAC00 and code <= 0xD7A3) or (code >= 0x4E00 and code <= 0x9FFF): return true
	return false

## The tooltip the viewport shows over c: its own, else its parents' through controls
## that pass the mouse on (the way Viewport looks it up).
func tip_of(c: Control) -> String:
	while c:
		var tip := c.get_tooltip(c.size * 0.5)
		if not tip.is_empty(): return tip
		if c.mouse_filter == Control.MOUSE_FILTER_STOP or c.top_level: return ""
		c = c.get_parent_control()
	return ""

func is_picture(c: Control) -> bool:
	return c is TextureRect or c.get_script() == LifeIcon

## A picture with words beside it in its own row (a sibling label, or labels inside a
## sibling column) needs no name of its own.
func labelled(c: Control) -> bool:
	for sibling in c.get_parent().get_children():
		if sibling == c or not sibling is CanvasItem or not sibling.visible: continue
		for words in [sibling] + sibling.find_children("*", "Label", true, false):
			if words is Label and words.is_visible_in_tree() and has_words(words.text): return true
	return false

func inside_button(c: Node) -> bool:
	var up := c.get_parent()
	while up:
		if up is BaseButton: return true
		up = up.get_parent()
	return false

## Moves the mouse over c's centre through the viewport; the tooltip it would show.
func hover(c: Control) -> String:
	await hover_at(centre(c))
	var over := root.gui_get_hovered_control()
	return tip_of(over) if over else ""

func centre(c: Control) -> Vector2:
	return root.get_final_transform() * (c.get_global_transform_with_canvas() * (c.size * 0.5))

func hover_at(at: Vector2) -> String:
	var motion := InputEventMouseMotion.new()
	motion.position = at
	motion.global_position = at
	root.push_input(motion)
	await process_frame
	var over := root.gui_get_hovered_control()
	return tip_of(over) if over else ""

## Something unrelated (a window's shade) lies over c, so c cannot be hovered now.
func covered(c: Control) -> bool:
	var over := root.gui_get_hovered_control()
	return over != null and over != c and not over.is_ancestor_of(c) and not c.get_parent().is_ancestor_of(over)

## Every visible picture-only control under top shows a name: buttons without words,
## icon-sized pictures that take the mouse, and unlabelled icons hovered for real.
func audit(top: Control, where: String) -> void:
	var missing := []
	var probes := []
	var seen := []
	walk(top, missing, probes, seen)
	for c in probes:
		if (await hover(c)).is_empty() and not covered(c): missing.append(c)
	for c in missing: print("  unnamed: %s <%s>" % [app.get_path_to(c), c.get_class()])
	expect(missing.is_empty(), "%s: every picture-only control names itself (%d keys/pictures, %d hovered, %d unnamed)" % [where, seen.size(), probes.size(), missing.size()])

func walk(node: Node, missing: Array, probes: Array, seen: Array) -> void:
	if node is CanvasItem and not (node as CanvasItem).visible: return
	if node is Control:
		var c := node as Control
		if c is BaseButton:
			if not has_words((c as Button).text if c is Button else ""):
				seen.append(c)
				if tip_of(c).is_empty(): missing.append(c)
		elif is_picture(c) and c.size.x > 0.0 and c.size.y > 0.0 and c.size.x <= 160.0 and c.size.y <= 160.0:
			if c.mouse_filter != Control.MOUSE_FILTER_IGNORE:
				seen.append(c)
				if tip_of(c).is_empty(): missing.append(c)
			elif not labelled(c) and not inside_button(c):
				probes.append(c)
	for child in node.get_children(): walk(child, missing, probes, seen)

## The tooltip label the viewport made (an internal child of the hovered control).
func tooltip_label(node: Node) -> Label:
	for child in node.get_children(true):
		if child is Label and String(child.theme_type_variation) == "TooltipLabel": return child
		var found := tooltip_label(child)
		if found: return found
	return null

func run() -> void:
	expect("--qa" in OS.get_cmdline_user_args() and I18n.settings_path().ends_with("settings_qa.cfg"), "QA settings file in use")
	I18n.setup()
	helpers()
	await village()
	await field()
	print("TOOLTIP_CHECK ", "FAIL" if failed else "OK")
	quit(1 if failed else 0)

## name_tip, the shared tooltip look and the hover delay.
func helpers() -> void:
	var art := RpgUi.icon("res://assets/ui/bag.svg", 32)
	var named := RpgUi.name_tip(art, "가방", "I")
	expect(named == art and art.tooltip_text == "가방  ·  I" and art.mouse_filter == Control.MOUSE_FILTER_PASS, "name_tip names a picture with its key and lets the hover reach it")
	var key := Button.new()
	RpgUi.name_tip(key, "닫기")
	expect(key.tooltip_text == "닫기" and key.mouse_filter == Control.MOUSE_FILTER_STOP, "name_tip leaves a button's mouse handling alone")
	art.free(); key.free()
	expect(RpgUi.color_name("#D98477") == t("산호색") and RpgUi.color_name("#123456") == "#123456", "swatch colours have names")
	expect(RpgUi.fold_tip("objective", false) == t("목표 접기") and RpgUi.fold_tip("hotbar", true) == t("퀵슬롯 펼치기"), "fold keys name their panel")
	for kit in [["theme", RpgUi.theme()], ["night theme", RpgUi.night_theme()]]:
		var theme: Theme = kit[1]
		var panel := theme.get_stylebox("panel", "TooltipPanel") as StyleBoxTexture
		expect(panel != null and panel.texture != null and panel.texture == RpgUi.half("tooltip"), "%s: tooltip panel is the painted pill" % kit[0])
		expect(theme.get_font("font", "TooltipLabel") == RpgUi.FONT_STRONG and theme.get_font_size("font_size", "TooltipLabel") == 14, "%s: tooltip text is the strong face at 14 px" % kit[0])
		expect(theme.get_color("font_color", "TooltipLabel") == RpgUi.INK and theme.get_constant("outline_size", "TooltipLabel") == 4 and theme.get_color("font_outline_color", "TooltipLabel") == RpgUi.OUTLINE, "%s: cream tooltip text with a dark outline" % kit[0])
	expect(is_equal_approx(float(ProjectSettings.get_setting("gui/timers/tooltip_delay_sec", 0.5)), 0.25), "tooltips appear after 0.25 s")

func village() -> void:
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	app = Main.new()
	root.add_child(app)
	await settle(1.6)
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = true
	# Every panel open, whatever an earlier run saved.
	RpgUi.set_folds(["objective", "minimap", "hotbar", "profile", "survival_objective", "toolbar"], false, false)
	await app.enter_village()
	await settle(1.0)
	expect(app.screen == "village", "village built from recorded replies")
	var ui: Control = app.ui
	await audit(ui, "village HUD")
	# Hotbar slots: name and key.
	var bar: Control = app.expedition_button.get_parent()
	var names := []
	for slot in bar.get_children(): names.append(slot.tooltip_text)
	expect(names.slice(0, 5) == [t("가방")+"  ·  I", t("제작")+"  ·  C", t("지도")+"  ·  Tab", t("창고")+"  ·  B", t("옷장")+"  ·  O"] and has_words(names[5]), "hotbar slots: %s" % [names])
	expect(await hover(bar.get_child(0)) == t("가방")+"  ·  I", "hovering the bag slot names it")
	# The tooltip itself: shown after the delay in the shared look.
	await settle(0.5)
	var label := tooltip_label(bar.get_child(0))
	expect(label != null and label.text == t("가방")+"  ·  I", "the bag slot's tooltip pops up")
	if label:
		expect(label.get_theme_font("font") == RpgUi.FONT_STRONG and label.get_theme_font_size("font_size") == 14 and label.get_theme_constant("outline_size") == 4, "tooltip uses the kit's strong 14 px outlined text")
		var pill := label.get_parent() as Window
		expect(pill != null and pill.get_theme_stylebox("panel") is StyleBoxTexture, "tooltip sits on the painted pill")
	await hover_at(Vector2(640, 300))
	# HUD pictures.
	expect(await hover(app.frame.portrait) == t("내 캐릭터"), "portrait named")
	var coins: Control = app.frame.stars.get_parent()
	expect(await hover(coins.get_child(0)) == t("별씨") and await hover(app.frame.stars) == t("별씨"), "star coins named on icon and number")
	expect(await hover(coins.get_child(3)) == t("잎전") and await hover(app.frame.leaves) == t("잎전"), "leaf coins named on icon and number")
	var map: Control = app.minimap
	var centre: Vector2 = root.get_final_transform() * (map.get_global_transform_with_canvas() * Vector2(102, 102))
	var corner: Vector2 = root.get_final_transform() * (map.get_global_transform_with_canvas() * Vector2(3, 3))
	expect(await hover_at(centre) == t("미니맵")+"  ·  Tab", "minimap named with its map key")
	expect(await hover_at(corner) == "", "minimap corners stay click-through")
	expect(await hover(map.key) == t("미니맵 접기"), "minimap fold key named")
	var card_key: Control = app.objective_card.find_child("Fold", true, false)
	expect(await hover(card_key) == t("목표 접기"), "tracker fold key named")
	var badge: Control = app.frame.panel.find_child("Fold", true, false)
	expect(await hover(badge) == t("프로필 접기"), "profile fold key named")
	var chip: Control = ui.get_node("SocialChip")
	var keys := chip.find_children("*", "Button", true, false)
	expect(keys.size() == 2 and await hover(keys[0]) == t("함께하기") and await hover(keys[1]) == t("인사"), "social chip keys named")
	RpgUi.set_folded("hotbar", true, false)
	await settle(0.1)
	expect(await hover(ui.get_node("FoldHandle")) == t("퀵슬롯 펼치기"), "folded hotbar handle named")
	RpgUi.set_folded("hotbar", false, false)
	await settle(0.1)
	# The bag drawer: close key and paint swatches.
	app.toggle_drawer()
	await settle(0.4)
	await audit(app.right.get_parent(), "village bag drawer")
	var swatches := []
	for b in app.right.find_children("*", "Button", true, false):
		if not has_words(b.text) and b.icon == null: swatches.append(b.tooltip_text)
	expect(swatches == [t("상아색"), t("꿀색"), t("산호색"), t("청록색"), t("하늘색")], "paint swatches named: %s" % [swatches])
	var close: Button = app.right.get_child(0).get_child(2)
	expect(close.tooltip_text == t("닫기")+"  ·  I", "drawer close key named with its key")
	app.toggle_drawer()
	await settle(0.3)
	# Seed picker, storage and wardrobe windows.
	app.life.open_plot(1)
	await settle(0.4)
	await audit(app.village_modal, "seed picker")
	var seed: Button = ui.find_child("Seed_turnip", true, false)
	expect(seed != null and seed.tooltip_text.begins_with(t("순무 씨앗")) and seed.tooltip_text.ends_with("·  1"), "seed buttons named with their number key")
	app.close_village_modal()
	app.life.open_storage()
	await settle(0.4)
	await audit(app.village_modal, "storage window")
	app.open_wardrobe()
	await settle(0.8)
	await audit(app.village_modal, "wardrobe")
	var coat := []
	for b in app.village_modal.find_children("*", "Button", true, false):
		if b.has_meta("part") and b.get_meta("part") == "coat": coat.append(b.tooltip_text)
	expect(coat.size() == 8 and coat[0] == t("상의")+" · "+t("짙은 청록"), "wardrobe swatches named: %s" % coat[0] if coat.size() else "wardrobe swatches named")
	app.close_village_modal()
	await settle(0.3)

func field() -> void:
	app.social.enabled = false
	await app.start_run("forest", "standard")
	await settle(1.4)
	expect(app.screen == "survival", "field run built from recorded replies")
	var ui: Control = app.ui
	await audit(ui, "field HUD")
	var chips := []
	for item in ["wood", "stone", "berry", "fiber"]:
		var count: Control = app.quick_counts[item]
		chips.append(await hover(count) == t(Main.ITEM_NAMES[item]) and await hover(count.get_parent().get_child(0)) == t(Main.ITEM_NAMES[item]))
	expect(chips.all(func(ok): return ok), "quick resource counts named on icon and number")
	expect(await hover(app.day_track) == t("일곱 밤 중 지나온 날"), "day tracker named")
	expect(await hover(app.field_map) == t("주변 지도"), "field map named")
	expect(await hover(app.hp_bar.get_parent().get_parent().get_child(0)) == t("체력"), "health meter icon named")
	app.toggle_drawer()
	await settle(0.4)
	await audit(app.right.get_parent(), "field bag")
	expect(app.inventory_slots.wood.button.tooltip_text == t("목재") and app.inventory_slots.soup.button.tooltip_text.begins_with(t("수프")), "bag slots named in the current language")
	app.toggle_drawer()
	await settle(0.3)
	app.queue_free()
	await settle(0.5)
