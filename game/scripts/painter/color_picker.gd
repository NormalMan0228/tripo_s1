extends VBoxContainer
## The painter's colour panel: saturation/value square with a hue strip, a HEX field, R/G/B
## fields, a saved swatch palette (+ adds the current colour, right-click removes) and the
## recent colours. Text fields use plain LineEdits, so Korean IME and focus keep working.
signal color_changed(color: Color)
signal swatches_changed

const RpgUi = preload("res://scripts/rpg_ui.gd")
const SQUARE := Vector2(206, 150)
const MAX_SWATCHES := 24
const MAX_RECENT := 10

var hue := 0.0
var sat := 0.0
var val := 0.0
var color := Color.BLACK
var swatches: PackedStringArray = []
var recent: PackedStringArray = []
var square: TextureRect
var square_mark: Control
var strip: TextureRect
var strip_mark: Control
var hex_field: LineEdit
var channel_fields: Array[SpinBox] = []
var swatch_grid: GridContainer
var recent_row: HBoxContainer
var syncing := false
var dragging := ""

func _init() -> void:
	add_theme_constant_override("separation", 6)

func _ready() -> void:
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 8)
	add_child(top)
	square = TextureRect.new()
	square.custom_minimum_size = SQUARE
	square.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	square.stretch_mode = TextureRect.STRETCH_SCALE
	var white := Image.create(4, 4, false, Image.FORMAT_RGBA8); white.fill(Color.WHITE)
	square.texture = ImageTexture.create_from_image(white)
	var shader := Shader.new()
	shader.code = "shader_type canvas_item;\nuniform float hue = 0.0;\nvec3 hsv(vec3 c){vec3 p=abs(fract(c.xxx+vec3(1.0,2.0/3.0,1.0/3.0))*6.0-3.0);return c.z*mix(vec3(1.0),clamp(p-1.0,0.0,1.0),c.y);}\nvoid fragment(){COLOR=vec4(hsv(vec3(hue,UV.x,1.0-UV.y)),1.0);}"
	var material := ShaderMaterial.new()
	material.shader = shader
	square.material = material
	square.mouse_filter = Control.MOUSE_FILTER_STOP
	square.mouse_default_cursor_shape = Control.CURSOR_CROSS
	square.gui_input.connect(_square_input)
	top.add_child(square)
	square_mark = Control.new()
	square_mark.mouse_filter = Control.MOUSE_FILTER_IGNORE
	square_mark.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	square_mark.draw.connect(func():
		var at := Vector2(sat, 1.0 - val) * square_mark.size
		square_mark.draw_arc(at, 6.0, 0.0, TAU, 20, Color.BLACK, 2.5, true)
		square_mark.draw_arc(at, 6.0, 0.0, TAU, 20, Color.WHITE, 1.2, true))
	square.add_child(square_mark)
	strip = TextureRect.new()
	strip.custom_minimum_size = Vector2(18, SQUARE.y)
	strip.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	strip.stretch_mode = TextureRect.STRETCH_SCALE
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 1.0 / 6.0, 2.0 / 6.0, 0.5, 4.0 / 6.0, 5.0 / 6.0, 1.0])
	gradient.colors = PackedColorArray([Color(1, 0, 0), Color(1, 1, 0), Color(0, 1, 0), Color(0, 1, 1), Color(0, 0, 1), Color(1, 0, 1), Color(1, 0, 0)])
	var hue_texture := GradientTexture2D.new()
	hue_texture.gradient = gradient
	hue_texture.fill_from = Vector2(0, 0); hue_texture.fill_to = Vector2(0, 1)
	hue_texture.width = 8; hue_texture.height = 128
	strip.texture = hue_texture
	strip.mouse_filter = Control.MOUSE_FILTER_STOP
	strip.gui_input.connect(_strip_input)
	top.add_child(strip)
	strip_mark = Control.new()
	strip_mark.mouse_filter = Control.MOUSE_FILTER_IGNORE
	strip_mark.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	strip_mark.draw.connect(func():
		var y := hue * strip_mark.size.y
		strip_mark.draw_rect(Rect2(-2, y - 3, strip_mark.size.x + 4, 6), Color.BLACK, false, 2.5)
		strip_mark.draw_rect(Rect2(-2, y - 3, strip_mark.size.x + 4, 6), Color.WHITE, false, 1.0))
	strip.add_child(strip_mark)
	var fields := HBoxContainer.new()
	fields.add_theme_constant_override("separation", 4)
	add_child(fields)
	var hash := Label.new(); hash.text = "#"; fields.add_child(hash)
	hex_field = LineEdit.new()
	hex_field.max_length = 7
	hex_field.custom_minimum_size = Vector2(96, 30)
	hex_field.add_theme_font_size_override("font_size", 13)
	hex_field.tooltip_text = tr("HEX 색 코드 (예: e9a23b)")
	hex_field.text_submitted.connect(func(_text: String): _hex_entered())
	hex_field.focus_exited.connect(_hex_entered)
	fields.add_child(hex_field)
	var channels := HBoxContainer.new()
	channels.add_theme_constant_override("separation", 4)
	add_child(channels)
	for channel in ["R", "G", "B"]:
		var field := SpinBox.new()
		field.min_value = 0; field.max_value = 255; field.step = 1
		field.prefix = channel
		field.custom_minimum_size = Vector2(76, 30)
		field.add_theme_font_size_override("font_size", 12)
		field.get_line_edit().add_theme_font_size_override("font_size", 12)
		field.value_changed.connect(func(_value: float): _channels_changed())
		channels.add_child(field)
		channel_fields.append(field)
	var palette_head := HBoxContainer.new()
	add_child(palette_head)
	var palette_title := Label.new(); palette_title.text = tr("팔레트"); palette_title.add_theme_font_size_override("font_size", 13)
	palette_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	palette_head.add_child(palette_title)
	var add := Button.new()
	add.text = "+"
	add.focus_mode = Control.FOCUS_NONE
	add.custom_minimum_size = Vector2(30, 26)
	RpgUi.name_tip(add, tr("지금 색을 팔레트에 저장"))
	add.pressed.connect(add_swatch)
	palette_head.add_child(add)
	swatch_grid = GridContainer.new()
	swatch_grid.columns = 10
	swatch_grid.add_theme_constant_override("h_separation", 3)
	swatch_grid.add_theme_constant_override("v_separation", 3)
	add_child(swatch_grid)
	var recent_title := Label.new(); recent_title.text = tr("최근 색"); recent_title.add_theme_font_size_override("font_size", 13)
	add_child(recent_title)
	recent_row = HBoxContainer.new()
	recent_row.add_theme_constant_override("separation", 3)
	add_child(recent_row)
	_rebuild_swatches()
	_rebuild_recent()
	set_color(color, false)

func set_color(value: Color, emit := true) -> void:
	value.a = 1.0
	color = value
	# Keep the hue while the colour is grey (Photoshop does the same).
	if value.s > 0.0001 and value.v > 0.0001: hue = value.h
	if value.v > 0.0001: sat = value.s
	val = value.v
	_sync()
	if emit: color_changed.emit(color)

func _sync() -> void:
	if not is_inside_tree(): return
	syncing = true
	(square.material as ShaderMaterial).set_shader_parameter("hue", hue)
	square_mark.queue_redraw()
	strip_mark.queue_redraw()
	if not hex_field.has_focus(): hex_field.text = color.to_html(false)
	var values := [color.r8, color.g8, color.b8]
	for i in 3:
		if not channel_fields[i].get_line_edit().has_focus(): channel_fields[i].set_value_no_signal(values[i])
	syncing = false

func _from_hsv() -> void:
	color = Color.from_hsv(hue, sat, val)
	_sync()
	color_changed.emit(color)

func _square_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		dragging = "square" if event.pressed else ""
	if (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT) or (event is InputEventMouseMotion and dragging == "square"):
		var at: Vector2 = (event.position / square.size).clamp(Vector2.ZERO, Vector2.ONE)
		sat = at.x
		val = 1.0 - at.y
		_from_hsv()
		square.accept_event()

func _strip_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		dragging = "strip" if event.pressed else ""
	if (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT) or (event is InputEventMouseMotion and dragging == "strip"):
		hue = clampf(event.position.y / strip.size.y, 0.0, 0.9999)
		_from_hsv()
		strip.accept_event()

func _hex_entered() -> void:
	var text := hex_field.text.strip_edges().trim_prefix("#")
	if text.length() == 3: text = text[0] + text[0] + text[1] + text[1] + text[2] + text[2]
	if text.length() == 6 and text.is_valid_hex_number():
		set_color(Color.html(text))
	else:
		hex_field.text = color.to_html(false)

func _channels_changed() -> void:
	if syncing: return
	set_color(Color8(int(channel_fields[0].value), int(channel_fields[1].value), int(channel_fields[2].value)))

## Remembers a colour that was used to paint (most recent first).
func use(value: Color) -> void:
	var code := value.to_html(false)
	var index := recent.find(code)
	if index >= 0: recent.remove_at(index)
	recent.insert(0, code)
	if recent.size() > MAX_RECENT: recent.resize(MAX_RECENT)
	_rebuild_recent()
	swatches_changed.emit()

func add_swatch() -> void:
	var code := color.to_html(false)
	if swatches.has(code): return
	swatches.append(code)
	if swatches.size() > MAX_SWATCHES: swatches.remove_at(0)
	_rebuild_swatches()
	swatches_changed.emit()

func remove_swatch(code: String) -> void:
	var index := swatches.find(code)
	if index < 0: return
	swatches.remove_at(index)
	_rebuild_swatches()
	swatches_changed.emit()

func _chip(value: Color, side: float) -> Button:
	var chip := Button.new()
	chip.focus_mode = Control.FOCUS_NONE
	chip.custom_minimum_size = Vector2(side, side)
	for state in ["normal", "hover", "pressed", "hover_pressed", "focus"]:
		var box := StyleBoxFlat.new()
		box.bg_color = value
		box.set_corner_radius_all(4)
		box.set_border_width_all(2 if state in ["hover", "pressed", "hover_pressed"] else 1)
		box.border_color = Color("ffe08a") if state in ["hover", "pressed", "hover_pressed"] else Color(0, 0, 0, 0.55)
		chip.add_theme_stylebox_override(state, box)
	return chip

func _rebuild_swatches() -> void:
	if swatch_grid == null: return
	for child in swatch_grid.get_children(): child.queue_free()
	for code in swatches:
		var chip := _chip(Color.html(code), 20)
		RpgUi.name_tip(chip, "#" + code + "  ·  " + tr("우클릭 삭제"))
		chip.gui_input.connect(func(event: InputEvent):
			if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_RIGHT:
				remove_swatch(code))
		chip.pressed.connect(func(): set_color(Color.html(code)))
		swatch_grid.add_child(chip)
	if swatches.is_empty():
		var hint := Label.new()
		hint.text = tr("+로 색을 모아 두세요")
		hint.add_theme_font_size_override("font_size", 12)
		hint.modulate = Color(1, 1, 1, 0.6)
		swatch_grid.add_child(hint)

func _rebuild_recent() -> void:
	if recent_row == null: return
	for child in recent_row.get_children(): child.queue_free()
	for code in recent:
		var chip := _chip(Color.html(code), 20)
		RpgUi.name_tip(chip, "#" + code)
		chip.pressed.connect(func(): set_color(Color.html(code)))
		recent_row.add_child(chip)
