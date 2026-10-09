extends RefCounted
## The painter's look and small widgets, in the spirit of current drawing apps on the game's
## night/gold palette: flat dark panels, light line icons (assets/ui/painter, 24 px grid,
## tinted here), a thin gold accent for what is active.
##   theme()            the workspace theme (merged over RpgUi's)
##   icon(name)         an icon texture;  icon_button(...) an icon-only button with a tooltip
##   EdgeSlider         Procreate-style vertical slider at the canvas edge
##   Section            a collapsible dock section (Color / Layers / History)
##   Thumb              a layer thumbnail over a transparency checker
##   stroke_preview()   a brush stroke drawn with the painter's own dab falloff
const RpgUi = preload("res://scripts/rpg_ui.gd")
const ICONS := "res://assets/ui/painter/%s.svg"
const PANEL := Color(0.07, 0.085, 0.095, 0.97)
const RAISED := Color(0.13, 0.155, 0.17, 1.0)
const HOVER := Color(0.19, 0.22, 0.235, 1.0)
const LINE := Color(0.91, 0.82, 0.6, 0.16)
const GOLD := Color("e9c46a")
const INK := Color("f4ead2")
const MUTED := Color(0.96, 0.92, 0.82, 0.58)
const DARK_INK := Color("23170b")

static var _icons := {}
static var _theme: Theme
static var _previews := {}

static func icon(name: String) -> Texture2D:
	if not _icons.has(name): _icons[name] = load(ICONS % name)
	return _icons[name]

## An icon at a fixed small size (for places that draw icons at their own size, like the
## option button's arrow). Icons import at 2x; headless runs (nothing drawn, no pixels to read)
## get a blank one of the same size, so layouts match.
static func small_icon(name: String, side: int) -> Texture2D:
	var key := "%s@%d" % [name, side]
	if _icons.has(key): return _icons[key]
	var texture: Texture2D = icon(name)
	if DisplayServer.get_name() == "headless":
		texture = ImageTexture.create_from_image(Image.create(side, side, false, Image.FORMAT_RGBA8))
	elif texture != null:
		var image := texture.get_image()
		if image != null:
			image = image.duplicate()
			if image.is_compressed(): image.decompress()
			image.clear_mipmaps()
			image.resize(side, side, Image.INTERPOLATE_LANCZOS)
			texture = ImageTexture.create_from_image(image)
	_icons[key] = texture
	return texture

static func flat(fill: Color, radius := 8, border := Color(0, 0, 0, 0), width := 0, padding := -1.0) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = fill
	box.set_corner_radius_all(radius)
	box.anti_aliasing = true
	if width > 0:
		box.border_color = border
		box.set_border_width_all(width)
	if padding >= 0.0: box.set_content_margin_all(padding)
	return box

static func theme() -> Theme:
	if _theme: return _theme
	var t := Theme.new()
	t.set_color("font_color", "Label", INK)
	t.set_color("font_outline_color", "Label", Color(0, 0, 0, 0.6))
	t.set_constant("outline_size", "Label", 0)
	# Plain buttons: flat dark keys that light up on hover.
	_button_styles(t, "Button", flat(RAISED, 7, LINE, 1, 6), flat(HOVER, 7, Color(GOLD, 0.35), 1, 6), flat(Color(GOLD, 0.22), 7, GOLD, 1, 6))
	t.set_stylebox("disabled", "Button", flat(Color(RAISED, 0.5), 7, Color(LINE, 0.08), 1, 6))
	for item in ["font_color", "font_focus_color", "font_pressed_color"]: t.set_color(item, "Button", INK)
	t.set_color("font_hover_color", "Button", Color("ffe7a8"))
	t.set_color("font_hover_pressed_color", "Button", Color("ffe7a8"))
	t.set_color("font_disabled_color", "Button", Color(INK, 0.35))
	for item in ["icon_normal_color", "icon_focus_color"]: t.set_color(item, "Button", Color(INK, 0.92))
	t.set_color("icon_hover_color", "Button", Color("ffe7a8"))
	t.set_color("icon_pressed_color", "Button", DARK_INK)
	t.set_color("icon_hover_pressed_color", "Button", DARK_INK)
	t.set_color("icon_disabled_color", "Button", Color(INK, 0.28))
	t.set_font("font", "Button", RpgUi.FONT_STRONG)
	t.set_font_size("font_size", "Button", 13)
	# Icon keys (rail, layer actions): no frame until hovered; the active one is gold.
	t.set_type_variation("PaintIcon", "Button")
	_button_styles(t, "PaintIcon", flat(Color(0, 0, 0, 0), 8, Color(0, 0, 0, 0), 0, 4), flat(HOVER, 8, Color(0, 0, 0, 0), 0, 4), flat(GOLD, 8, Color(0, 0, 0, 0), 0, 4))
	t.set_stylebox("disabled", "PaintIcon", flat(Color(0, 0, 0, 0), 8, Color(0, 0, 0, 0), 0, 4))
	t.set_constant("icon_max_width", "PaintIcon", 22)
	# Segments (gradient shape and colours, tips): framed, gold when chosen.
	t.set_type_variation("PaintSegment", "Button")
	_button_styles(t, "PaintSegment", flat(RAISED, 7, LINE, 1, 5), flat(HOVER, 7, Color(GOLD, 0.4), 1, 5), flat(Color(GOLD, 0.26), 7, GOLD, 2, 5))
	t.set_constant("icon_max_width", "PaintSegment", 20)
	t.set_color("icon_pressed_color", "PaintSegment", Color("ffe7a8"))
	t.set_color("icon_hover_pressed_color", "PaintSegment", Color("ffe7a8"))
	t.set_color("font_pressed_color", "PaintSegment", Color("ffe7a8"))
	# The one gold call to action.
	t.set_type_variation("PaintGold", "Button")
	_button_styles(t, "PaintGold", flat(Color("e2b955"), 7, Color("f6dc93"), 1, 6), flat(Color("efc865"), 7, Color("fff0bf"), 1, 6), flat(Color("c99c3c"), 7, Color("f6dc93"), 1, 6))
	for item in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]: t.set_color(item, "PaintGold", DARK_INK)
	# Dock section headers: a full-width row.
	t.set_type_variation("PaintHeader", "Button")
	_button_styles(t, "PaintHeader", flat(Color(0, 0, 0, 0), 6, Color(0, 0, 0, 0), 0, 4), flat(Color(1, 1, 1, 0.05), 6, Color(0, 0, 0, 0), 0, 4), flat(Color(1, 1, 1, 0.05), 6, Color(0, 0, 0, 0), 0, 4))
	for item in ["font_color", "font_pressed_color", "font_focus_color"]: t.set_color(item, "PaintHeader", GOLD)
	for item in ["icon_normal_color", "icon_pressed_color", "icon_hover_pressed_color", "icon_focus_color"]: t.set_color(item, "PaintHeader", GOLD)
	t.set_constant("icon_max_width", "PaintHeader", 16)
	t.set_font_size("font_size", "PaintHeader", 13)
	# Layer rows: selected one is softly gold.
	t.set_type_variation("PaintRow", "Button")
	_button_styles(t, "PaintRow", flat(Color(1, 1, 1, 0.03), 7, Color(0, 0, 0, 0), 0, 4), flat(Color(1, 1, 1, 0.07), 7, Color(0, 0, 0, 0), 0, 4), flat(Color(GOLD, 0.16), 7, Color(GOLD, 0.7), 1, 4))
	# Fields, menus, lists, sliders and scroll bars.
	for type in ["LineEdit", "TextEdit"]:
		t.set_stylebox("normal", type, flat(Color(0, 0, 0, 0.32), 6, LINE, 1, 6))
		t.set_stylebox("focus", type, flat(Color(0, 0, 0, 0.4), 6, GOLD, 1, 6))
		t.set_stylebox("read_only", type, flat(Color(0, 0, 0, 0.2), 6, LINE, 1, 6))
		t.set_color("font_color", type, INK)
		t.set_color("caret_color", type, GOLD)
		t.set_color("selection_color", type, Color(GOLD, 0.35))
		t.set_color("font_selected_color", type, INK)
		t.set_color("font_placeholder_color", type, Color(INK, 0.4))
		t.set_font_size("font_size", type, 13)
	t.set_icon("arrow", "OptionButton", small_icon("chevron_down", 12))
	t.set_constant("arrow_margin", "OptionButton", 6)
	t.set_font_size("font_size", "OptionButton", 12)
	t.set_color("font_color", "OptionButton", INK)
	var menu := flat(Color(0.09, 0.11, 0.12, 0.99), 8, Color(GOLD, 0.3), 1, 6)
	t.set_stylebox("panel", "PopupMenu", menu)
	t.set_stylebox("hover", "PopupMenu", flat(Color(GOLD, 0.2), 5))
	for item in ["font_color", "font_accelerator_color"]: t.set_color(item, "PopupMenu", INK)
	t.set_color("font_hover_color", "PopupMenu", Color("ffe7a8"))
	t.set_constant("v_separation", "PopupMenu", 6)
	t.set_font_size("font_size", "PopupMenu", 13)
	t.set_stylebox("panel", "ItemList", flat(Color(0, 0, 0, 0.22), 7, LINE, 1, 4))
	t.set_stylebox("focus", "ItemList", StyleBoxEmpty.new())
	for item in ["selected", "selected_focus"]: t.set_stylebox(item, "ItemList", flat(Color(GOLD, 0.2), 5, Color(GOLD, 0.6), 1))
	t.set_stylebox("hovered", "ItemList", flat(Color(1, 1, 1, 0.06), 5))
	for item in ["cursor", "cursor_unfocused"]: t.set_stylebox(item, "ItemList", StyleBoxEmpty.new())
	for item in ["font_color", "font_hovered_color"]: t.set_color(item, "ItemList", INK)
	t.set_color("font_selected_color", "ItemList", Color("ffe7a8"))
	t.set_color("guide_color", "ItemList", Color(0, 0, 0, 0))
	t.set_constant("v_separation", "ItemList", 3)
	t.set_font_size("font_size", "ItemList", 12)
	for type in ["HSlider", "VSlider"]:
		var track := flat(Color(1, 1, 1, 0.12), 3)
		track.content_margin_top = 2; track.content_margin_bottom = 2
		t.set_stylebox("slider", type, track)
		t.set_stylebox("grabber_area", type, flat(Color(GOLD, 0.85), 3))
		t.set_stylebox("grabber_area_highlight", type, flat(GOLD, 3))
		t.set_icon("grabber", type, _dot(12, INK))
		t.set_icon("grabber_highlight", type, _dot(12, Color("ffe7a8")))
		t.set_constant("center_grabber", type, 0)
	for type in ["VScrollBar", "HScrollBar"]:
		t.set_stylebox("scroll", type, flat(Color(0, 0, 0, 0), 3, Color(0, 0, 0, 0), 0, 2))
		t.set_stylebox("scroll_focus", type, flat(Color(0, 0, 0, 0), 3, Color(0, 0, 0, 0), 0, 2))
		t.set_stylebox("grabber", type, flat(Color(1, 1, 1, 0.16), 3))
		t.set_stylebox("grabber_highlight", type, flat(Color(GOLD, 0.45), 3))
		t.set_stylebox("grabber_pressed", type, flat(Color(GOLD, 0.6), 3))
	t.set_stylebox("panel", "PanelContainer", StyleBoxEmpty.new())
	t.set_color("font_color", "CheckBox", INK)
	t.set_font_size("font_size", "CheckBox", 12)
	_theme = t
	return t

static func _button_styles(t: Theme, type: String, normal: StyleBox, hover: StyleBox, pressed: StyleBox) -> void:
	t.set_stylebox("normal", type, normal)
	t.set_stylebox("hover", type, hover)
	t.set_stylebox("pressed", type, pressed)
	t.set_stylebox("hover_pressed", type, pressed)
	t.set_stylebox("focus", type, StyleBoxEmpty.new())

static func _dot(side: int, color: Color) -> ImageTexture:
	var image := Image.create(side, side, false, Image.FORMAT_RGBA8)
	var c := (side - 1) * 0.5
	for y in side:
		for x in side:
			var d := Vector2(x - c, y - c).length()
			var a := clampf(c - d + 0.5, 0.0, 1.0)
			var rim := clampf(d - (c - 1.6), 0.0, 1.0)
			image.set_pixel(x, y, Color(color.lerp(Color(0.1, 0.07, 0.03), rim * 0.6), a))
	return ImageTexture.create_from_image(image)

## An icon-only button (with a tooltip carrying the shortcut); "" leaves it blank for drawing.
static func icon_button(parent: Node, name: String, tip: String, callback: Callable, side := 36.0, variation := "PaintIcon") -> Button:
	var b := Button.new()
	if not name.is_empty(): b.icon = icon(name)
	b.theme_type_variation = variation
	b.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.expand_icon = false
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(side, side)
	b.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	b.tooltip_text = tip
	b.pressed.connect(func(): callback.call())
	if parent != null: parent.add_child(b)
	return b

static func caption(parent: Node, text: String, size := 12, color := MUTED) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label

## A brush stroke (a soft S) stamped with the painter's dab falloff, white on clear, cached by
## spec. spec: {tip, size, hardness, flow, spacing, roundness, angle}.
static func stroke_preview(spec: Dictionary, width := 132, height := 34) -> ImageTexture:
	var key := "%s|%d|%d" % [JSON.stringify(spec), width, height]
	if _previews.has(key): return _previews[key]
	var alpha := PackedFloat32Array(); alpha.resize(width * height)
	var tip := int(spec.get("tip", 0))
	var hardness := float(spec.get("hardness", 0.8))
	var flow := float(spec.get("flow", 1.0))
	var roundness := clampf(float(spec.get("roundness", 1.0)), 0.05, 1.0) if tip != 0 else 1.0
	var angle := deg_to_rad(float(spec.get("angle", 0.0)))
	var ca := cos(angle); var sa := sin(angle)
	var top := height * 0.4
	var radius := lerpf(1.6, top, clampf(sqrt(float(spec.get("size", 28.0)) / 80.0), 0.0, 1.0))
	var hard := minf(hardness, clampf(1.0 - 1.5 / radius, 0.0, 1.0))
	var soft := maxf(1e-4, 1.0 - hard)
	var t := 0.0
	var seed := 0
	while t <= 1.0:
		var taper := 0.35 + 0.65 * sin(PI * t)
		var r := maxf(1.0, radius * taper)
		var at := Vector2(lerpf(radius + 3.0, width - radius - 3.0, t), height * 0.5 + sin(t * TAU) * (height * 0.5 - radius - 2.0) * 0.8)
		var x0 := maxi(0, int(at.x - r - 1)); var x1 := mini(width - 1, int(at.x + r + 1))
		var y0 := maxi(0, int(at.y - r - 1)); var y1 := mini(height - 1, int(at.y + r + 1))
		seed += 1
		for y in range(y0, y1 + 1):
			for x in range(x0, x1 + 1):
				var u := x + 0.5 - at.x; var v := y + 0.5 - at.y
				var d: float
				if tip == 0: d = sqrt(u * u + v * v) / r
				else:
					var ur := u * ca + v * sa
					var vr := (v * ca - u * sa) / roundness
					d = sqrt(ur * ur + vr * vr) / r
				if d >= 1.0: continue
				var dab := flow
				if d > hard:
					var f := (d - hard) / soft
					dab *= 1.0 - f * f * (3.0 - 2.0 * f)
				if tip == 2:
					# Grainy: a cheap stable hash stands in for the core's noise tile.
					var h := sin(float(x * 12.9898 + y * 78.233 + seed * 3.17)) * 43758.5453
					dab *= clampf((h - floor(h)) * 1.6 - 0.15, 0.0, 1.0)
				var o := y * width + x
				alpha[o] = alpha[o] + (1.0 - alpha[o]) * dab
		t += maxf(0.75, float(spec.get("spacing", 0.12)) * 2.0 * r) / float(width)
	var data := PackedByteArray(); data.resize(width * height * 4)
	for o in alpha.size():
		data[o * 4] = 255; data[o * 4 + 1] = 255; data[o * 4 + 2] = 255
		data[o * 4 + 3] = int(clampf(alpha[o], 0.0, 1.0) * 255.0)
	var texture := ImageTexture.create_from_image(Image.create_from_data(width, height, false, Image.FORMAT_RGBA8, data))
	_previews[key] = texture
	return texture

## Procreate-style vertical slider for the canvas edge: drag anywhere on it, wheel nudges;
## while hovered or dragged a bubble shows the value. `shape` > 1 gives fine control low down.
class EdgeSlider extends Control:
	signal value_changed(value: float)
	signal dragging_changed(active: bool)
	var min_value := 0.0
	var max_value := 1.0
	var value := 0.5
	var step := 0.0
	var shape := 1.0
	var format := func(v: float) -> String: return str(snappedf(v, 0.01))
	var title := ""
	var dragging := false
	var hovered := false

	func _init() -> void:
		custom_minimum_size = Vector2(28, 150)
		mouse_filter = Control.MOUSE_FILTER_STOP
		mouse_default_cursor_shape = Control.CURSOR_VSIZE
		mouse_entered.connect(func(): hovered = true; queue_redraw())
		mouse_exited.connect(func(): hovered = false; queue_redraw())

	func ratio() -> float:
		return pow(clampf((value - min_value) / maxf(max_value - min_value, 1e-6), 0.0, 1.0), 1.0 / shape)

	func set_value_no_signal(v: float) -> void:
		value = clampf(v, min_value, max_value)
		queue_redraw()

	func _set_from(y: float) -> void:
		var r := clampf(1.0 - (y - 6.0) / maxf(size.y - 12.0, 1.0), 0.0, 1.0)
		var v := min_value + pow(r, shape) * (max_value - min_value)
		if step > 0.0: v = snappedf(v, step)
		v = clampf(v, min_value, max_value)
		if not is_equal_approx(v, value):
			value = v
			value_changed.emit(value)
		queue_redraw()

	func _gui_input(event: InputEvent) -> void:
		if event is InputEventMouseButton:
			if event.button_index == MOUSE_BUTTON_LEFT:
				dragging = event.pressed
				dragging_changed.emit(dragging)
				if dragging: _set_from(event.position.y)
				queue_redraw()
				accept_event()
			elif event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
				var r := ratio() + (0.03 if event.button_index == MOUSE_BUTTON_WHEEL_UP else -0.03)
				_set_from(6.0 + (1.0 - clampf(r, 0.0, 1.0)) * (size.y - 12.0))
				accept_event()
		elif event is InputEventMouseMotion and dragging:
			_set_from(event.position.y)
			accept_event()

	func _draw() -> void:
		var rect := Rect2(Vector2(5, 0), Vector2(size.x - 10, size.y))
		draw_style_box(_box(Color(0.05, 0.06, 0.07, 0.72), 9, Color(1, 1, 1, 0.1)), rect)
		var inner := rect.grow(-3)
		var filled := inner.size.y * ratio()
		if filled > 0.5:
			draw_style_box(_box(Color(0.91, 0.77, 0.42, 0.55 if not (hovered or dragging) else 0.8), 6), Rect2(inner.position + Vector2(0, inner.size.y - filled), Vector2(inner.size.x, filled)))
		var y := inner.position.y + inner.size.y - filled
		draw_style_box(_box(Color("fff4d6") if (hovered or dragging) else Color(0.96, 0.92, 0.82, 0.9), 3), Rect2(Vector2(rect.position.x - 2, y - 3), Vector2(rect.size.x + 4, 6)))
		if hovered or dragging:
			var font := get_theme_default_font()
			var text: String = format.call(value)
			var label := (title + "  " if not title.is_empty() else "") + text
			var width := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x + 16
			var bubble := Rect2(Vector2(size.x + 6, clampf(y - 12, 0, size.y - 24)), Vector2(width, 24))
			draw_style_box(_box(Color(0.05, 0.06, 0.07, 0.9), 7, Color(0.91, 0.77, 0.42, 0.5)), bubble)
			draw_string(font, bubble.position + Vector2(8, 17), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("fff4d6"))

	func _box(fill: Color, radius: int, border := Color(0, 0, 0, 0)) -> StyleBoxFlat:
		var box := StyleBoxFlat.new()
		box.bg_color = fill
		box.set_corner_radius_all(radius)
		box.anti_aliasing = true
		if border.a > 0.0:
			box.border_color = border
			box.set_border_width_all(1)
		return box

## A dock section: a header row (icon, title, chevron) that folds its body.
class Section extends VBoxContainer:
	signal toggled(open: bool)
	var header: Button
	var body: VBoxContainer
	var open := true

	func _init(title: String, icon_name: String, start_open := true) -> void:
		add_theme_constant_override("separation", 4)
		header = Button.new()
		header.theme_type_variation = "PaintHeader"
		header.text = title
		header.icon = load(ICONS % icon_name)
		header.alignment = HORIZONTAL_ALIGNMENT_LEFT
		header.focus_mode = Control.FOCUS_NONE
		header.custom_minimum_size.y = 28
		header.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		header.pressed.connect(func(): set_open(not open))
		add_child(header)
		var chevron := TextureRect.new()
		chevron.name = "Chevron"
		chevron.texture = load(ICONS % "chevron_down")
		chevron.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		chevron.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		chevron.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		chevron.modulate = Color(0.96, 0.92, 0.82, 0.6)
		chevron.mouse_filter = Control.MOUSE_FILTER_IGNORE
		chevron.set_anchors_and_offsets_preset(Control.PRESET_CENTER_RIGHT)
		chevron.offset_left = -22; chevron.offset_right = -6; chevron.offset_top = -8; chevron.offset_bottom = 8
		chevron.pivot_offset = Vector2(8, 8)
		header.add_child(chevron)
		body = VBoxContainer.new()
		body.add_theme_constant_override("separation", 6)
		add_child(body)
		set_open(start_open, false)

	func set_open(value: bool, animate := true) -> void:
		open = value
		body.visible = open
		var chevron: Control = header.get_node("Chevron")
		chevron.rotation = 0.0 if open else -PI * 0.5
		if open and animate and is_inside_tree():
			body.modulate.a = 0.0
			create_tween().tween_property(body, "modulate:a", 1.0, 0.12)
		toggled.emit(open)

## A layer thumbnail: the layer's pixels over a small transparency checker.
class Thumb extends Control:
	var texture: Texture2D

	func _init() -> void:
		custom_minimum_size = Vector2(34, 34)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var cells := 4
		var side := size / cells
		for y in cells:
			for x in cells:
				draw_rect(Rect2(Vector2(x, y) * side, side), Color(0.42, 0.44, 0.45) if (x + y) % 2 == 0 else Color(0.3, 0.32, 0.33))
		if texture != null: draw_texture_rect(texture, Rect2(Vector2.ZERO, size), false)
		draw_rect(Rect2(Vector2.ZERO, size), Color(1, 1, 1, 0.18), false, 1.0)
