extends Control
## The first look (31): right after 계정 만들기, over the title, the new player picks a traveller on
## 남 / 여 tabs (four cards each, the new player characters' front images, build_charsel_cards.py),
## sees them in 3D and dresses them (the wardrobe editor, wardrobe.gd: colours, hat, pack), then
## 모험 시작 saves the look (/v1/profile) and the game goes on to the first place. main.gd
## authenticate awaits `done`; only the real game shows it (test harnesses add Main directly).
## The new characters' 3D models come from the 05 session one by one: until a card's model is in,
## it stands in with an older model (STAND_IN) or the card is locked as 준비 중.
signal done(avatar: Dictionary)

const RpgUi = preload("res://scripts/rpg_ui.gd")
const Wardrobe = preload("res://scripts/wardrobe.gd")
## id (the server's character id), picture, tab, role, stand-in model (an older character the
## server already has) or "" while locked.
const CARDS := [["m1", "m1_adventurer", "m", "모험가", "explorer"], ["m2", "m2_artisan", "m", "장인", ""], ["m3", "m3_fisher", "m", "낚시꾼", ""], ["m4", "m4_smith", "m", "대장장이", ""],
	["f1", "f1_adventurer", "f", "모험가", "explorer_b"], ["f2", "f2_herbalist", "f", "약초사", ""], ["f3", "f3_inventor", "f", "발명가", ""], ["f4", "f4_sailor", "f", "선원", ""]]
## Characters whose own 3D model is in (05 session); the rest wear their stand-in or stay locked.
static var ready_models: Array = []

var avatar: Dictionary = {}
## The world takes avatar_v2 looks (main.gd): accent, straw hat and any skin in the editor.
var v2 := false
var editor: HBoxContainer
var cards: Dictionary = {}
var pages: Dictionary = {}
var chosen := ""

## The model a card wears now: its own once it is in (assets/<id>.glb), else its stand-in
## ("" = locked).
static func model_for(id: String, stand_in: String) -> String:
	return id if id in ready_models or ResourceLoader.exists("res://assets/%s.glb" % id) else stand_in

func _ready() -> void:
	name = "CharacterSelect"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var shade := ColorRect.new()
	shade.color = RpgUi.SHADE_IN
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(shade)
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", RpgUi.panel_style("night"))
	card.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	# Grows from the centre both ways, so the whole card stays on screen.
	card.grow_horizontal = Control.GROW_DIRECTION_BOTH
	card.grow_vertical = Control.GROW_DIRECTION_BOTH
	add_child(card)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	card.add_child(column)
	RpgUi.label(column, tr("나의 여행자 만들기"), 26, RpgUi.GOLD)
	RpgUi.caption(column, tr("함께 모험할 여행자를 고르고 꾸며 보세요. 나중에 옷장에서 언제든 바꿀 수 있어요."), 13)
	RpgUi.divider(column, Color(RpgUi.GOLD, .6))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 22)
	column.add_child(row)
	# 1. 남 / 여 tabs, four cards each.
	var left := VBoxContainer.new()
	left.add_theme_constant_override("separation", 8)
	row.add_child(left)
	var tabs := RpgUi.tab_strip(left, [{"id":"m", "label":tr("남")}, {"id":"f", "label":tr("여")}], func(id: String):
		for key in pages: (pages[key] as Control).visible = key == id
		if is_instance_valid(card): _fit(card), "night")
	tabs.name = "SexTabs"
	var group := ButtonGroup.new()
	for tab in ["m", "f"]:
		var grid := GridContainer.new()
		grid.name = "Cards_" + tab
		grid.columns = 2
		grid.add_theme_constant_override("h_separation", 10)
		grid.add_theme_constant_override("v_separation", 10)
		grid.visible = tab == "m"
		left.add_child(grid)
		pages[tab] = grid
	for spec in CARDS:
		var b := _card(spec, group)
		pages[spec[2]].add_child(b)
		cards[spec[0]] = b
	# 2 and 3. The 3D preview and the dressing controls (the wardrobe editor; its own traveller
	# buttons give way to the cards).
	editor = Wardrobe.new()
	editor.avatar = avatar.duplicate(true)
	editor.v2 = v2
	row.add_child(editor)
	for b in editor.find_children("*", "Button", true, false):
		if b.has_meta("character"): b.get_parent().visible = false
	# The wardrobe's part names were set for a paper card: light ink on this night glass.
	for l in editor.find_children("*", "Label", true, false):
		(l as Label).add_theme_color_override("font_color", RpgUi.INK)
	for c in editor.find_children("*", "CheckButton", true, false):
		(c as CheckButton).add_theme_color_override("font_color", RpgUi.INK)
	var start := RpgUi.button(column, tr("모험 시작"), _start, "gold", "lg", true)
	start.name = "Start"
	start.size_flags_horizontal = Control.SIZE_SHRINK_END
	start.custom_minimum_size.x = 260
	# The tab and card that match the look now (a 여 stand-in opens the 여 tab).
	var now := str(editor.avatar.get("character", "explorer_b"))
	var first := "f1" if now in ["explorer_b", "ranger"] or now.begins_with("f") else "m1"
	for spec in CARDS:
		if spec[0] == now or spec[4] == now: first = spec[0]
	RpgUi.select_tab(tabs, "f" if first.begins_with("f") else "m")
	pick(first, false)
	_fit.call_deferred(card)
	# A soft fade in (a slide would fight the centring above).
	card.modulate.a = 0.0
	card.create_tween().tween_property(card, "modulate:a", 1.0, 0.3)

## The card shrinks to its content (containers only grow by themselves) and sits in the middle.
func _fit(card: Control) -> void:
	if not is_instance_valid(card): return
	card.reset_size()
	card.set_anchors_and_offsets_preset(Control.PRESET_CENTER, Control.PRESET_MODE_MINSIZE)

func _card(spec: Array, group: ButtonGroup) -> Button:
	var id: String = spec[0]
	var model := model_for(id, spec[4])
	var b := Button.new()
	b.name = "Card_" + id
	b.toggle_mode = true
	b.button_group = group
	b.focus_mode = Control.FOCUS_NONE
	b.theme_type_variation = "SlotButton"
	b.custom_minimum_size = Vector2(150, 186)
	b.set_meta("model", model)
	var face := TextureRect.new()
	var path := "res://assets/ui/charsel/%s_card.png" % spec[1]
	face.texture = load(path) if ResourceLoader.exists(path) else null
	face.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	face.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	face.position = Vector2(8, 8)
	face.size = Vector2(134, 144)
	face.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(face)
	var title := RpgUi.label(b, tr(spec[3]), 17, RpgUi.PAPER_INK, false)
	title.add_theme_font_override("font", RpgUi.FONT_STRONG)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.position = Vector2(0, 152)
	title.size = Vector2(150, 28)
	if model.is_empty():
		# Not drawn in 3D yet: the picture stays, dimmed, under a 준비 중 band.
		b.disabled = true
		face.modulate = Color(1, 1, 1, 0.55)
		var band := PanelContainer.new()
		var style := StyleBoxFlat.new()
		style.bg_color = Color(RpgUi.NIGHT, 0.88)
		style.set_corner_radius_all(6)
		band.add_theme_stylebox_override("panel", style)
		band.position = Vector2(22, 66)
		band.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.add_child(band)
		RpgUi.label(band, tr("준비 중"), 15, RpgUi.GOLD)
		RpgUi.name_tip(b, tr(spec[3]), tr("곧 만나요"))
	else:
		b.pressed.connect(func(): pick(id))
		RpgUi.hover_motion(b, 1.04)
		RpgUi.name_tip(b, tr(spec[3]))
	return b

## A card: dresses the editor in its model (the wardrobe's own key, so its colour presets come along).
func pick(id: String, sound := true) -> void:
	if not cards.has(id): return
	var b: Button = cards[id]
	var model := str(b.get_meta("model", ""))
	if model.is_empty(): return
	chosen = id
	b.set_pressed_no_signal(true)
	for key in editor.find_children("*", "Button", true, false):
		if key.has_meta("character") and key.get_meta("character") == model:
			if sound: key.pressed.emit()
	# A world with avatar_v2 keeps the card's own id (m1...f4; the body shows its stand-in until the
	# model is in, AvatarLook.shown); an older world keeps the stand-in's id.
	editor.avatar.character = id if v2 else model
	editor.refresh()

func _start() -> void:
	RpgUi.sfx("confirm", -6.0)
	done.emit(editor.avatar.duplicate(true))
