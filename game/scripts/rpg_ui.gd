extends RefCounted
## Player-facing HUD pieces in a cozy RPG style: a character frame, a slot hotbar
## with key caps, an interaction prompt and title-menu buttons. Text is passed
## through tr() by the callers.
const INK := Color("fff4d6")
const GOLD := Color("e9d29b")
const NIGHT := Color(0.11,0.14,0.15,0.86)

static func style(fill: Color, radius := 14, border := GOLD, width := 2) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = fill
	box.set_corner_radius_all(radius)
	box.set_border_width_all(width)
	box.border_color = border
	box.shadow_color = Color(0,0,0,.3)
	box.shadow_size = 8
	box.shadow_offset = Vector2(0,3)
	box.content_margin_left = 12
	box.content_margin_right = 12
	box.content_margin_top = 8
	box.content_margin_bottom = 8
	return box

static func label(parent: Node, value: String, size := 15, color := INK, outline := true) -> Label:
	var l := Label.new()
	l.text = value
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	if outline:
		l.add_theme_color_override("font_outline_color", Color(0.08,0.07,0.05,.9))
		l.add_theme_constant_override("outline_size", 4)
	parent.add_child(l)
	return l

static func icon(path: String, size: float) -> TextureRect:
	var image := TextureRect.new()
	image.texture = load(path)
	image.custom_minimum_size = Vector2(size,size)
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	image.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return image

## Portrait medallion, name and the two currencies. Returns the labels to update.
static func player_frame(ui: Control, portrait: String) -> Dictionary:
	var shell := PanelContainer.new()
	shell.position = Vector2(18,16)
	shell.add_theme_stylebox_override("panel", style(NIGHT, 40))
	ui.add_child(shell)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	shell.add_child(row)
	var medal := PanelContainer.new()
	var ring := style(Color("f5e6c4"), 34, GOLD, 3)
	ring.content_margin_left = 3; ring.content_margin_right = 3; ring.content_margin_top = 3; ring.content_margin_bottom = 3
	medal.add_theme_stylebox_override("panel", ring)
	medal.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	row.add_child(medal)
	medal.add_child(icon(portrait, 60))
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 3)
	row.add_child(column)
	var name := label(column, "", 19)
	var coins := HBoxContainer.new()
	coins.add_theme_constant_override("separation", 6)
	column.add_child(coins)
	coins.add_child(icon("res://assets/starseed.svg", 22))
	var stars := label(coins, "0", 16, Color("ffe08a"))
	var gap := Control.new(); gap.custom_minimum_size.x = 8; coins.add_child(gap)
	coins.add_child(icon("res://assets/ui/leaf.svg", 20))
	var leaves := label(coins, "0", 16, Color("bfe59c"))
	var status := label(column, "", 12, Color("d8e3d4"))
	status.visible = false
	return {"panel":shell, "name":name, "stars":stars, "leaves":leaves, "status":status, "column":column}

## Square slots with an icon, a key cap and a caption.
static func hotbar(ui: Control, slots: Array, y: float) -> HBoxContainer:
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", 10)
	bar.alignment = BoxContainer.ALIGNMENT_CENTER
	bar.position = Vector2(0, y)
	bar.size = Vector2(1280, 96)
	ui.add_child(bar)
	for slot in slots:
		var b := Button.new()
		b.custom_minimum_size = Vector2(78, 78)
		b.focus_mode = Control.FOCUS_NONE
		b.tooltip_text = slot.label
		for state in ["normal","hover","pressed"]:
			var fill := NIGHT if state=="normal" else (Color(0.2,0.27,0.27,.95) if state=="hover" else Color(0.35,0.3,0.2,.95))
			var box := style(fill, 14, GOLD if state!="normal" else Color(GOLD,.7), 2)
			if slot.get("primary", false): box.bg_color = Color(0.36,0.27,0.13,.94) if state=="normal" else box.bg_color
			b.add_theme_stylebox_override(state, box)
		var stack := VBoxContainer.new()
		stack.alignment = BoxContainer.ALIGNMENT_CENTER
		stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
		stack.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		stack.add_theme_constant_override("separation", 0)
		b.add_child(stack)
		var art := icon(slot.icon, 38)
		art.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		stack.add_child(art)
		var caption := label(stack, slot.label, 12)
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if not String(slot.get("key","")).is_empty():
			var cap := Label.new()
			cap.text = slot.key
			cap.add_theme_font_size_override("font_size", 11)
			cap.add_theme_color_override("font_color", Color("2b2112"))
			cap.add_theme_stylebox_override("normal", style(GOLD, 5, Color("8c6a2c"), 1))
			cap.get_theme_stylebox("normal").content_margin_left = 4
			cap.get_theme_stylebox("normal").content_margin_right = 4
			cap.get_theme_stylebox("normal").content_margin_top = 0
			cap.get_theme_stylebox("normal").content_margin_bottom = 0
			cap.position = Vector2(-6,-8)
			cap.mouse_filter = Control.MOUSE_FILTER_IGNORE
			b.add_child(cap)
		b.pressed.connect(slot.call)
		bar.add_child(b)
	return bar

## Floating "E · ..." prompt above the hotbar; hidden while empty.
static func prompt(ui: Control, y: float) -> Label:
	var pill := Label.new()
	pill.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pill.add_theme_font_size_override("font_size", 16)
	pill.add_theme_color_override("font_color", INK)
	pill.add_theme_stylebox_override("normal", style(Color(0.1,0.12,0.13,.88), 18))
	pill.position = Vector2(440, y)
	pill.size = Vector2(400, 36)
	pill.grow_horizontal = Control.GROW_DIRECTION_BOTH
	pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pill.visible = false
	ui.add_child(pill)
	return pill

## Large title-menu button: dark plate with a gold edge that warms on hover.
static func menu_button(parent: Node, value: String, callback: Callable, width := 300.0) -> Button:
	var b := Button.new()
	b.text = value
	b.custom_minimum_size = Vector2(width, 54)
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 20)
	for state in ["normal","hover","pressed","disabled"]:
		var fill := Color(0.09,0.12,0.13,.78) if state=="normal" else (Color(0.24,0.2,0.12,.92) if state=="hover" else Color(0.36,0.28,0.14,.95))
		b.add_theme_stylebox_override(state, style(fill, 10, GOLD if state=="hover" else Color(GOLD,.55), 2))
	for state in ["font_color","font_hover_color","font_pressed_color"]:
		b.add_theme_color_override(state, Color("fff2cf") if state!="font_hover_color" else Color("ffe08a"))
	b.pressed.connect(callback)
	parent.add_child(b)
	return b

## Text field matching the title card.
static func field(parent: Node, placeholder: String, secret := false, width := 320.0) -> LineEdit:
	var line := LineEdit.new()
	line.placeholder_text = placeholder
	line.auto_translate_mode = Node.AUTO_TRANSLATE_MODE_DISABLED
	line.secret = secret
	line.custom_minimum_size = Vector2(width, 44)
	line.add_theme_font_size_override("font_size", 16)
	line.add_theme_color_override("font_color", INK)
	line.add_theme_color_override("font_placeholder_color", Color("d4cbb8"))
	line.add_theme_stylebox_override("normal", style(Color(0.05,0.07,0.08,.7), 8, Color(GOLD,.45), 1))
	line.add_theme_stylebox_override("focus", style(Color(0.05,0.07,0.08,.8), 8, GOLD, 2))
	parent.add_child(line)
	return line
