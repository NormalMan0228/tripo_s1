extends Control
## The full-screen painting workspace for a crafted object (village bag and room studio).
##
##   var painter = load("res://scripts/painter/painter.gd").new()
##   painter.setup(api, obj, model, {"saved": func(image, version), "flat": func(hex, part, reset),
##       "parts": [[id, label], ...], "views": [viewports to pause]})
##   host_control.add_child(painter)
##
## The model is only read (meshes, materials). Tools: brush and eraser (size, hardness,
## opacity, flow, spacing, smoothing, tablet pressure, round/flat/grainy tips, blend modes),
## fill, gradient and eyedropper; up to eight layers; undo/redo history. Saving flattens the
## layers into one 1024 px PNG, uploads it and hands it to the host, which shows it in the
## world. An object without UVs gets the whole-object colour panel instead, with a reason.
## Typing in its text fields never triggers a shortcut.
signal finished(saved: bool)

const Core = preload("res://scripts/painter/paint_core.gd")
const PaintApply = preload("res://scripts/painter/paint_apply.gd")
const PaintView = preload("res://scripts/painter/paint_view.gd")
const ColorPanel = preload("res://scripts/painter/color_picker.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const SIZE := 1024
const GROUP := &"painter_open"
const BRUSH := "brush"
const ERASER := "eraser"
const FILL := "fill"
const GRADIENT := "gradient"
const PICKER := "picker"
const MODE_NAMES := ["보통", "곱하기", "스크린", "오버레이", "더하기"]
const TIP_NAMES := ["둥근 붓", "납작 붓", "거친 붓"]
const SETTINGS_SECTION := "painter"
const STAMP_BUDGET_MS := 9

var api: Node
var obj: Dictionary = {}
var model: Node3D
var options: Dictionary = {}
var core: Core
var view: PaintView
var picker: ColorPanel
var tool := BRUSH
var primary := Color("c4553b")
var secondary := Color("f6eee0")
var settings := {
	BRUSH: {"size": 28.0, "hardness": 0.75, "opacity": 1.0, "flow": 1.0, "spacing": 0.12, "smoothing": 0.0,
		"pressure_size": true, "pressure_opacity": false, "tip": 0, "angle": 0.0, "roundness": 1.0, "mode": 0},
	ERASER: {"size": 36.0, "hardness": 0.6, "opacity": 1.0, "flow": 1.0, "spacing": 0.12, "smoothing": 0.0,
		"pressure_size": true, "pressure_opacity": false, "tip": 0, "angle": 0.0, "roundness": 1.0, "mode": 0},
	FILL: {"tolerance": 32.0, "opacity": 1.0, "mode": 0, "sample_all": true},
	GRADIENT: {"radial": false, "to_clear": false, "opacity": 1.0, "mode": 0, "part_only": false},
}
var ready_to_paint := false
var busy := false
var dirty := false
var closing := false
var stroke := {}
var gradient_start := {}
var paused_views: Array = []
# UI
var title_label: Label
var status_label: Label
var tool_buttons := {}
var option_rows := {}
var option_controls := {}
var primary_chip: Button
var secondary_chip: Button
var symmetry_choice: OptionButton
var layer_list: VBoxContainer
var layer_opacity: HSlider
var layer_opacity_label: Label
var layer_mode: OptionButton
var rename_row: HBoxContainer
var rename_field: LineEdit
var history_list: ItemList
var undo_button: Button
var redo_button: Button
var save_button: Button
var reset_button: Button
var busy_layer: Control
var busy_label: Label
var busy_bar: ProgressBar
var dialog_layer: Control
var workspace: Control
var refreshing_layers := false
var pending_task := -1
var backdrop: ColorRect

func setup(api_node: Node, object: Dictionary, model_node: Node3D, extra := {}) -> void:
	api = api_node
	obj = object.duplicate(true)
	model = model_node
	options = extra

static func is_open(tree: SceneTree) -> bool:
	return tree != null and tree.get_first_node_in_group(GROUP) != null

func _ready() -> void:
	add_to_group(GROUP)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var look := RpgUi.theme().duplicate() as Theme
	look.merge_with(RpgUi.night_theme())
	theme = look
	backdrop = ColorRect.new()
	backdrop.color = Color("15191b")
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(backdrop)
	_load_settings()
	for viewport in options.get("views", []):
		if viewport is Viewport and is_instance_valid(viewport) and not viewport.disable_3d:
			viewport.disable_3d = true
			paused_views.append(viewport)
	_build_busy()
	RpgUi.sfx("open", -8.0)
	_prepare.call_deferred()

func _exit_tree() -> void:
	# A fill, gradient or flattening still running finishes before this node goes away.
	if pending_task >= 0:
		WorkerThreadPool.wait_for_task_completion(pending_task)
		pending_task = -1
	for viewport in paused_views:
		if is_instance_valid(viewport): viewport.disable_3d = false
	paused_views.clear()

# ------------------------------------------------------------------ preparation

func _prepare() -> void:
	_show_busy(tr("작업대를 준비하고 있어요…"), true)
	await get_tree().process_frame
	if not is_instance_valid(model) or not PaintApply.has_uvs(model):
		_hide_busy()
		_build_fallback(tr("이 물건은 표면에 그림을 입힐 좌표(UV) 없이 만들어져서 붓으로 칠할 수 없어요. 대신 전체 색을 바꿀 수 있어요. 새로 만드는 물건은 붓으로 칠할 수 있어요."))
		return
	var slots := PaintApply.mesh_slots(model)
	var looks := PaintApply.slot_looks(model)
	var paint_image: Image = null
	if obj.get("paint_version") != null:
		paint_image = await PaintApply.fetch(api, obj, str(options.get("prefix", "/v1/objects/")))
		if not is_inside_tree(): return
	var engine := Core.new()
	var base_name := tr("바탕")
	var job := {}
	# The worker only touches its own data (never this node), so leaving early is safe.
	pending_task = WorkerThreadPool.add_task(func():
		engine.setup(slots, SIZE)
		if not engine.uv_ok: return
		engine.bake()
		var under := PaintApply.compose_looks(looks, SIZE)
		var base := PaintApply.image_bytes(paint_image, SIZE) if paint_image != null else under
		engine.start_layers(base, under, base_name)
		job.done = true)
	while not WorkerThreadPool.is_task_completed(pending_task):
		busy_bar.value = engine.progress * 100.0
		await get_tree().process_frame
	WorkerThreadPool.wait_for_task_completion(pending_task)
	pending_task = -1
	if not is_inside_tree(): return
	core = engine
	_hide_busy()
	if not job.get("done", false) or core.covered < SIZE * SIZE / 400:
		core = null
		_build_fallback(tr("이 물건의 표면 좌표(UV)가 비어 있어 붓으로 칠할 수 없어요. 대신 전체 색을 바꿀 수 있어요."))
		return
	_build_workspace()
	view.show_model(model, PaintApply.slots_of(model), core)
	ready_to_paint = true
	_refresh_layers()
	_refresh_history()
	_select_tool(BRUSH)
	if core.overlap_ratio() > 0.12:
		_status(tr("이 물건은 무늬 좌표가 일부 겹쳐 있어서, 한 곳을 칠하면 다른 곳에도 같이 묻을 수 있어요."))

# ------------------------------------------------------------------ workspace UI

func _build_workspace() -> void:
	workspace = VBoxContainer.new()
	workspace.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	workspace.offset_left = 10; workspace.offset_top = 8; workspace.offset_right = -10; workspace.offset_bottom = -6
	workspace.add_theme_constant_override("separation", 6)
	add_child(workspace)
	move_child(workspace, 1)
	# Top bar: title, tool options (two rows), reset / cancel / save.
	var bar := PanelContainer.new()
	var bar_style := RpgUi.panel_style("pill", 8)
	# Clear of the pill's rounded, studded ends.
	bar_style.content_margin_left = 28
	bar_style.content_margin_right = 24
	bar.add_theme_stylebox_override("panel", bar_style)
	workspace.add_child(bar)
	var bar_row := HBoxContainer.new()
	bar_row.add_theme_constant_override("separation", 14)
	bar.add_child(bar_row)
	var heading := VBoxContainer.new()
	heading.custom_minimum_size.x = 150
	bar_row.add_child(heading)
	var ribbon := RpgUi.label(heading, tr("색칠 작업대"), 20, RpgUi.GOLD)
	ribbon.add_theme_font_override("font", RpgUi.FONT_DISPLAY)
	title_label = RpgUi.label(heading, str(obj.get("name", "")), 13, RpgUi.INK)
	title_label.clip_text = true
	title_label.custom_minimum_size.x = 150
	var options_box := VBoxContainer.new()
	options_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	options_box.add_theme_constant_override("separation", 2)
	# Same height for every tool, so switching tools never resizes (and reframes) the view.
	options_box.custom_minimum_size.y = 72
	bar_row.add_child(options_box)
	_build_options(options_box)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 6)
	bar_row.add_child(actions)
	reset_button = _button(actions, tr("원래대로"), _ask_reset, "", tr("칠한 것을 모두 지우고 처음 모습으로"))
	_button(actions, tr("취소"), _ask_cancel, "", tr("저장하지 않고 닫기  ·  Esc"))
	save_button = _button(actions, tr("저장"), save, "GoldButton", tr("마을과 방에 칠한 모습으로 저장  ·  Ctrl+S"))
	save_button.custom_minimum_size.x = 84
	# Middle: tools | view | panels.
	var middle := HBoxContainer.new()
	middle.size_flags_vertical = Control.SIZE_EXPAND_FILL
	middle.add_theme_constant_override("separation", 6)
	workspace.add_child(middle)
	middle.add_child(_build_tools())
	var frame := PanelContainer.new()
	var frame_style := StyleBoxFlat.new()
	frame_style.bg_color = Color("0d1012")
	frame_style.set_border_width_all(2)
	frame_style.border_color = Color("6b5a3a")
	frame_style.set_corner_radius_all(6)
	frame_style.set_content_margin_all(2)
	frame.add_theme_stylebox_override("panel", frame_style)
	frame.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	middle.add_child(frame)
	view = PaintView.new()
	view.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	view.paint_event.connect(_on_view_event)
	frame.add_child(view)
	middle.add_child(_build_side())
	status_label = Label.new()
	status_label.add_theme_font_size_override("font_size", 12)
	status_label.add_theme_color_override("font_color", Color(1, 1, 1, 0.72))
	status_label.clip_text = true
	workspace.add_child(status_label)
	_status("")

func _button(parent: Node, text: String, callback: Callable, variation := "", tip := "") -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size.y = 34
	if not variation.is_empty(): b.theme_type_variation = variation
	b.add_theme_font_size_override("font_size", 14)
	b.pressed.connect(func(): callback.call())
	if not tip.is_empty(): b.tooltip_text = tip
	RpgUi.hover_motion(b, 1.03)
	parent.add_child(b)
	return b

## A labelled slider: its name and value (e.g. size 28px) above the bar.
func _slider(parent: Node, key: String, tool_name: String, title: String, low: float, high: float, step: float, unit: String, scale := 1.0, width := 104.0) -> HSlider:
	var box := VBoxContainer.new()
	box.custom_minimum_size.x = width
	box.add_theme_constant_override("separation", 0)
	parent.add_child(box)
	var caption := Label.new()
	caption.add_theme_font_size_override("font_size", 12)
	box.add_child(caption)
	var slider := HSlider.new()
	slider.min_value = low; slider.max_value = high; slider.step = step
	slider.focus_mode = Control.FOCUS_NONE
	slider.custom_minimum_size.y = 18
	box.add_child(slider)
	# Values are stored as they are used (0..1 for percentages); `scale` only formats them.
	var show := func(value: float):
		caption.text = "%s  %d%s" % [title, int(round(value * scale)), unit]
	slider.value = float(settings[tool_name][key])
	show.call(slider.value)
	slider.value_changed.connect(func(value: float):
		settings[tool_name][key] = value
		show.call(value)
		_update_cursor())
	option_controls[tool_name + ":" + key] = slider
	return slider

func _toggle(parent: Node, key: String, tool_name: String, text: String, tip: String) -> Button:
	var b := Button.new()
	b.toggle_mode = true
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.theme_type_variation = "ChoiceButton"
	b.custom_minimum_size.y = 30
	b.add_theme_font_size_override("font_size", 12)
	b.button_pressed = bool(settings[tool_name][key])
	b.tooltip_text = tip
	b.toggled.connect(func(on: bool): settings[tool_name][key] = on)
	parent.add_child(b)
	option_controls[tool_name + ":" + key] = b
	return b

func _choice(parent: Node, key: String, tool_name: String, names: Array, tip: String, width := 110.0) -> OptionButton:
	var choice := OptionButton.new()
	for name in names: choice.add_item(tr(name))
	choice.focus_mode = Control.FOCUS_NONE
	choice.custom_minimum_size = Vector2(width, 30)
	choice.add_theme_font_size_override("font_size", 12)
	choice.tooltip_text = tip
	var value = settings[tool_name][key]
	choice.select(int(value) if not value is bool else int(value))
	choice.item_selected.connect(func(index: int):
		settings[tool_name][key] = index if not settings[tool_name][key] is bool else index == 1
		_on_choice_changed())
	parent.add_child(choice)
	option_controls[tool_name + ":" + key] = choice
	return choice

func _row(parent: Node) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	parent.add_child(row)
	return row

func _build_options(parent: VBoxContainer) -> void:
	for tool_name in [BRUSH, ERASER]:
		var holder := VBoxContainer.new()
		holder.add_theme_constant_override("separation", 2)
		parent.add_child(holder)
		option_rows[tool_name] = holder
		var first := _row(holder)
		_slider(first, "size", tool_name, tr("크기"), 1, 400, 1, "px")
		_slider(first, "hardness", tool_name, tr("경도"), 0, 1, 0.01, "%", 100.0, 92)
		_slider(first, "opacity", tool_name, tr("불투명도"), 0.01, 1, 0.01, "%", 100.0, 100)
		_slider(first, "flow", tool_name, tr("흐름"), 0.01, 1, 0.01, "%", 100.0, 92)
		if tool_name == BRUSH: _choice(first, "mode", tool_name, MODE_NAMES, tr("붓 혼합 모드"), 100)
		var second := _row(holder)
		_choice(second, "tip", tool_name, TIP_NAMES, tr("붓 끝 모양"), 96)
		_slider(second, "angle", tool_name, tr("각도"), 0, 180, 1, "°", 1.0, 84)
		_slider(second, "roundness", tool_name, tr("둥글기"), 0.05, 1, 0.01, "%", 100.0, 84)
		_slider(second, "spacing", tool_name, tr("간격"), 0.01, 2, 0.01, "%", 100.0, 84)
		_slider(second, "smoothing", tool_name, tr("보정"), 0, 1, 0.01, "%", 100.0, 84)
		_toggle(second, "pressure_size", tool_name, tr("필압→크기"), tr("펜 압력으로 크기 조절"))
		_toggle(second, "pressure_opacity", tool_name, tr("필압→불투명"), tr("펜 압력으로 불투명도 조절"))
	var fill_row := VBoxContainer.new()
	parent.add_child(fill_row)
	option_rows[FILL] = fill_row
	var fill_first := _row(fill_row)
	_slider(fill_first, "tolerance", FILL, tr("허용치"), 0, 255, 1, "", 1.0, 120)
	_slider(fill_first, "opacity", FILL, tr("불투명도"), 0.01, 1, 0.01, "%", 100.0, 110)
	_choice(fill_first, "mode", FILL, MODE_NAMES, tr("혼합 모드"), 100)
	_toggle(fill_first, "sample_all", FILL, tr("모든 레이어 기준"), tr("보이는 색 전체를 기준으로 영역을 고릅니다"))
	RpgUi.caption(_row(fill_row), tr("클릭한 곳과 이어진 비슷한 색을 표면을 따라 채워요."), 12, Color(1, 1, 1, 0.6))
	var gradient_row := VBoxContainer.new()
	parent.add_child(gradient_row)
	option_rows[GRADIENT] = gradient_row
	var gradient_first := _row(gradient_row)
	_choice(gradient_first, "radial", GRADIENT, ["선형", "원형"], tr("그라데이션 모양"), 90)
	_choice(gradient_first, "to_clear", GRADIENT, ["앞색 → 뒷색", "앞색 → 투명"], tr("그라데이션 색"), 120)
	_slider(gradient_first, "opacity", GRADIENT, tr("불투명도"), 0.01, 1, 0.01, "%", 100.0, 110)
	_choice(gradient_first, "mode", GRADIENT, MODE_NAMES, tr("혼합 모드"), 100)
	_toggle(gradient_first, "part_only", GRADIENT, tr("시작 부품만"), tr("드래그를 시작한 부품에만 그립니다"))
	RpgUi.caption(_row(gradient_row), tr("물건 위에서 드래그해 방향과 길이를 정해요."), 12, Color(1, 1, 1, 0.6))
	var picker_row := VBoxContainer.new()
	parent.add_child(picker_row)
	option_rows[PICKER] = picker_row
	RpgUi.caption(picker_row, tr("물건을 클릭하면 보이는 색을 앞색으로 가져와요. 다른 도구에서는 Alt+클릭."), 12, Color(1, 1, 1, 0.7))

func _build_tools() -> Control:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", RpgUi.panel_style("night_plain", 8))
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	panel.add_child(column)
	for spec in [[BRUSH, tr("붓"), "B"], [ERASER, tr("지우개"), "E"], [FILL, tr("채우기"), "G"], [GRADIENT, tr("그라데이션"), "G"], [PICKER, tr("스포이드"), "I"]]:
		var b := Button.new()
		b.toggle_mode = true
		b.focus_mode = Control.FOCUS_NONE
		b.custom_minimum_size = Vector2(52, 50)
		b.theme_type_variation = "HudSlot"
		RpgUi.name_tip(b, spec[1], spec[2])
		var glyph := Control.new()
		glyph.mouse_filter = Control.MOUSE_FILTER_IGNORE
		glyph.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		var kind: String = spec[0]
		glyph.draw.connect(func(): _draw_tool_icon(glyph, kind, b.button_pressed))
		b.add_child(glyph)
		b.toggled.connect(func(_on: bool): glyph.queue_redraw())
		b.pressed.connect(func(): _select_tool(kind))
		column.add_child(b)
		tool_buttons[kind] = b
	column.add_child(HSeparator.new())
	# Foreground / background colour chips (X swaps, D resets).
	var chips := Control.new()
	chips.custom_minimum_size = Vector2(52, 52)
	column.add_child(chips)
	secondary_chip = _color_chip(chips, Vector2(18, 18), secondary)
	primary_chip = _color_chip(chips, Vector2(2, 2), primary)
	primary_chip.pressed.connect(func(): picker.set_color(primary, false))
	secondary_chip.pressed.connect(_swap_colors)
	RpgUi.name_tip(primary_chip, tr("앞색"))
	RpgUi.name_tip(secondary_chip, tr("뒷색 · 클릭하면 바꾸기"), "X")
	var swap := _button(column, "⇄", _swap_colors, "", tr("앞색과 뒷색 바꾸기  ·  X"))
	swap.custom_minimum_size = Vector2(52, 28)
	column.add_child(HSeparator.new())
	symmetry_choice = OptionButton.new()
	for name in [tr("대칭 끔"), tr("대칭 X"), tr("대칭 Z")]: symmetry_choice.add_item(name)
	symmetry_choice.focus_mode = Control.FOCUS_NONE
	symmetry_choice.custom_minimum_size = Vector2(52, 30)
	symmetry_choice.add_theme_font_size_override("font_size", 11)
	symmetry_choice.tooltip_text = tr("거울 대칭으로 양쪽을 함께 칠하기")
	symmetry_choice.item_selected.connect(func(index: int): core.symmetry = index)
	column.add_child(symmetry_choice)
	var home := _button(column, tr("시점"), func(): view.reset_view(), "", tr("시점 초기화  ·  F"))
	home.custom_minimum_size = Vector2(52, 30)
	home.add_theme_font_size_override("font_size", 12)
	return panel

func _color_chip(parent: Control, at: Vector2, value: Color) -> Button:
	var chip := Button.new()
	chip.focus_mode = Control.FOCUS_NONE
	chip.position = at
	chip.size = Vector2(32, 32)
	parent.add_child(chip)
	_paint_chip(chip, value)
	return chip

func _paint_chip(chip: Button, value: Color) -> void:
	for state in ["normal", "hover", "pressed", "hover_pressed", "focus"]:
		var box := StyleBoxFlat.new()
		box.bg_color = value
		box.set_border_width_all(2)
		box.border_color = Color("ffe08a") if state != "normal" else Color(0.95, 0.9, 0.78)
		box.set_corner_radius_all(4)
		box.shadow_color = Color(0, 0, 0, 0.45)
		box.shadow_size = 3
		chip.add_theme_stylebox_override(state, box)

func _draw_tool_icon(canvas: Control, kind: String, active: bool) -> void:
	var c := canvas.size * 0.5
	var ink := Color("ffe08a") if active else Color("f4ead2")
	var dark := Color(0, 0, 0, 0.55)
	match kind:
		BRUSH:
			canvas.draw_line(c + Vector2(9, -11), c + Vector2(-2, 2), dark, 6.0, true)
			canvas.draw_line(c + Vector2(9, -11), c + Vector2(-2, 2), ink, 3.5, true)
			canvas.draw_colored_polygon(PackedVector2Array([c + Vector2(-1, 1), c + Vector2(-6, 6), c + Vector2(-11, 11), c + Vector2(-4, 4)]), ink)
			canvas.draw_circle(c + Vector2(-6, 7), 3.6, Color(primary, 1.0))
		ERASER:
			var box := PackedVector2Array([c + Vector2(-11, 3), c + Vector2(1, -9), c + Vector2(10, 0), c + Vector2(-2, 12)])
			canvas.draw_colored_polygon(box, Color("e7a3a0") if not active else Color("f3b9b5"))
			canvas.draw_polyline(box + PackedVector2Array([box[0]]), ink, 1.6, true)
			canvas.draw_line(c + Vector2(-5, -3), c + Vector2(4, 6), ink, 1.6, true)
		FILL:
			var bucket := PackedVector2Array([c + Vector2(-9, -3), c + Vector2(1, -11), c + Vector2(10, -2), c + Vector2(0, 7)])
			canvas.draw_colored_polygon(bucket, Color(ink, 0.25))
			canvas.draw_polyline(bucket + PackedVector2Array([bucket[0]]), ink, 2.0, true)
			canvas.draw_circle(c + Vector2(9, 8), 3.4, Color(primary, 1.0))
		GRADIENT:
			for i in 10:
				var t := i / 9.0
				canvas.draw_rect(Rect2(c + Vector2(-11 + i * 2.2, -9), Vector2(2.4, 18)), primary.lerp(secondary, t))
			canvas.draw_rect(Rect2(c + Vector2(-11, -9), Vector2(22, 18)), ink, false, 1.6)
		PICKER:
			canvas.draw_line(c + Vector2(8, -8), c + Vector2(-7, 7), dark, 6.0, true)
			canvas.draw_line(c + Vector2(8, -8), c + Vector2(-7, 7), ink, 3.0, true)
			canvas.draw_circle(c + Vector2(8, -8), 4.2, ink)
			canvas.draw_circle(c + Vector2(-8, 8), 2.4, Color(primary, 1.0))

func _card(parent: Node, title: String) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", RpgUi.panel_style("night_plain", 10))
	parent.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 5)
	panel.add_child(column)
	RpgUi.label(column, title, 15, RpgUi.GOLD)
	return column

## Two docked columns like Photoshop's panels: colour and history | layers. Each scrolls on
## its own if the window is very short.
func _column(parent: Node) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size.x = 268
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	parent.add_child(scroll)
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.add_theme_constant_override("separation", 6)
	scroll.add_child(column)
	return column

func _build_side() -> Control:
	var docks := HBoxContainer.new()
	docks.add_theme_constant_override("separation", 6)
	var side := _column(docks)
	var layers_side := _column(docks)
	var color_card := _card(side, tr("색"))
	picker = ColorPanel.new()
	picker.swatches = PackedStringArray(_setting("swatches", "").split(",", false))
	picker.recent = PackedStringArray(_setting("recent", "").split(",", false))
	color_card.add_child(picker)
	picker.set_color(primary, false)
	picker.color_changed.connect(func(value: Color):
		primary = value
		_paint_chip(primary_chip, primary)
		_redraw_tool_icons())
	var layers_card := _card(layers_side, tr("레이어"))
	layer_list = VBoxContainer.new()
	layer_list.add_theme_constant_override("separation", 3)
	layers_card.add_child(layer_list)
	var props := HBoxContainer.new()
	props.add_theme_constant_override("separation", 6)
	layers_card.add_child(props)
	var opacity_box := VBoxContainer.new()
	opacity_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	props.add_child(opacity_box)
	layer_opacity_label = Label.new()
	layer_opacity_label.add_theme_font_size_override("font_size", 12)
	opacity_box.add_child(layer_opacity_label)
	layer_opacity = HSlider.new()
	layer_opacity.min_value = 0; layer_opacity.max_value = 100; layer_opacity.step = 1
	layer_opacity.focus_mode = Control.FOCUS_NONE
	layer_opacity.value_changed.connect(func(value: float):
		layer_opacity_label.text = tr("레이어 불투명도  %d%%") % int(value)
		if refreshing_layers or core == null: return
		core.set_layer_props(core.current, {"opacity": value / 100.0}, tr("레이어 불투명도"))
		_after_change(false))
	opacity_box.add_child(layer_opacity)
	layer_mode = OptionButton.new()
	for name in MODE_NAMES: layer_mode.add_item(tr(name))
	layer_mode.focus_mode = Control.FOCUS_NONE
	layer_mode.custom_minimum_size = Vector2(96, 30)
	layer_mode.add_theme_font_size_override("font_size", 12)
	layer_mode.tooltip_text = tr("레이어 혼합 모드")
	layer_mode.item_selected.connect(func(index: int):
		if refreshing_layers or core == null: return
		core.set_layer_props(core.current, {"mode": index}, tr("혼합 모드"))
		_after_change(false))
	props.add_child(layer_mode)
	var layer_actions := HBoxContainer.new()
	layer_actions.add_theme_constant_override("separation", 3)
	layers_card.add_child(layer_actions)
	for spec in [["+", _add_layer, tr("새 레이어  ·  Ctrl+Shift+N")], ["⧉", _duplicate_layer, tr("레이어 복제")], ["▲", func(): _move_layer(1), tr("위로")], ["▼", func(): _move_layer(-1), tr("아래로")], ["✎", _start_rename, tr("이름 바꾸기")], ["✕", _delete_layer, tr("레이어 삭제")]]:
		var b := _button(layer_actions, spec[0], spec[1], "", spec[2])
		b.custom_minimum_size = Vector2(40, 30)
	rename_row = HBoxContainer.new()
	rename_row.visible = false
	layers_card.add_child(rename_row)
	rename_field = LineEdit.new()
	rename_field.max_length = 24
	rename_field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rename_field.custom_minimum_size.y = 30
	rename_field.text_submitted.connect(func(_text: String): _finish_rename())
	# Esc cancels the rename (and never reaches the workspace's Esc = close).
	rename_field.gui_input.connect(_rename_key)
	rename_row.add_child(rename_field)
	_button(rename_row, tr("확인"), _finish_rename).custom_minimum_size = Vector2(56, 30)
	var history_card := _card(side, tr("작업 기록"))
	var history_actions := HBoxContainer.new()
	history_card.add_child(history_actions)
	undo_button = _button(history_actions, tr("되돌리기"), undo, "", "Ctrl+Z")
	redo_button = _button(history_actions, tr("다시 하기"), redo, "", "Ctrl+Shift+Z")
	history_list = ItemList.new()
	history_list.custom_minimum_size.y = 150
	history_list.focus_mode = Control.FOCUS_NONE
	history_list.add_theme_font_size_override("font_size", 12)
	history_list.item_clicked.connect(func(index: int, _at: Vector2, button: int):
		if button == MOUSE_BUTTON_LEFT and not busy and core != null and not core.stroke_active():
			core.jump(index)
			_after_change(true))
	history_card.add_child(history_list)
	return docks

func _redraw_tool_icons() -> void:
	for b in tool_buttons.values():
		for child in b.get_children(): (child as Control).queue_redraw()

# ------------------------------------------------------------------ busy / dialogs / status

func _build_busy() -> void:
	busy_layer = Control.new()
	busy_layer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	busy_layer.mouse_filter = Control.MOUSE_FILTER_STOP
	busy_layer.visible = false
	add_child(busy_layer)
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.45)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	busy_layer.add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	busy_layer.add_child(center)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", RpgUi.panel_style("night"))
	panel.custom_minimum_size.x = 340
	center.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	panel.add_child(column)
	busy_label = RpgUi.label(column, "", 16, RpgUi.INK)
	busy_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	busy_bar = ProgressBar.new()
	busy_bar.custom_minimum_size = Vector2(280, 14)
	busy_bar.show_percentage = false
	column.add_child(busy_bar)

func _show_busy(text: String, measured := false) -> void:
	busy = true
	busy_label.text = text
	busy_bar.value = 0.0 if measured else 100.0
	busy_bar.modulate.a = 1.0 if measured else 0.55
	busy_layer.visible = true
	move_child(busy_layer, get_child_count() - 1)

func _hide_busy() -> void:
	busy = false
	busy_layer.visible = false

## Runs slow core work (fill, gradient, flattening) on a worker thread while the screen
## shows what is happening; the frame keeps going.
func _work(text: String, job: Callable) -> void:
	_show_busy(text)
	pending_task = WorkerThreadPool.add_task(job)
	var started := Time.get_ticks_msec()
	while not WorkerThreadPool.is_task_completed(pending_task):
		busy_bar.value = fmod((Time.get_ticks_msec() - started) / 12.0, 100.0)
		await get_tree().process_frame
	WorkerThreadPool.wait_for_task_completion(pending_task)
	pending_task = -1
	if is_inside_tree(): _hide_busy()

func _status(text: String) -> void:
	if not is_instance_valid(status_label): return
	var keys := tr("B 붓 · E 지우개 · G 채우기/그라데이션 · I 스포이드 · [ ] 크기 · X 색 바꾸기 · Ctrl+Z 되돌리기 · 우클릭 회전 · 휠 확대 · 가운데 버튼 이동")
	status_label.text = text if not text.is_empty() else keys

func _confirm(text: String, accept: String, callback: Callable) -> void:
	if is_instance_valid(dialog_layer): dialog_layer.queue_free()
	dialog_layer = Control.new()
	dialog_layer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dialog_layer.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(dialog_layer)
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.5)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dialog_layer.add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dialog_layer.add_child(center)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", RpgUi.panel_style("night"))
	panel.custom_minimum_size.x = 380
	center.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	panel.add_child(column)
	var message := RpgUi.label(column, text, 15, RpgUi.INK)
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	message.custom_minimum_size.x = 340
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	row.add_theme_constant_override("separation", 8)
	column.add_child(row)
	_button(row, tr("돌아가기"), func(): dialog_layer.queue_free())
	_button(row, accept, func():
		dialog_layer.queue_free()
		callback.call(), "GoldButton")
	RpgUi.pop_in(panel)

# ------------------------------------------------------------------ tools

func _select_tool(kind: String) -> void:
	if stroke_active(): return
	tool = kind
	for name in tool_buttons: tool_buttons[name].set_pressed_no_signal(name == kind)
	_redraw_tool_icons()
	for name in option_rows: option_rows[name].visible = name == kind
	if is_instance_valid(view):
		view.line_visible = false
		view.overlay.queue_redraw()
	_update_cursor()

func _on_choice_changed() -> void:
	_update_cursor()

func _update_cursor() -> void:
	if not is_instance_valid(view): return
	if tool in [BRUSH, ERASER]:
		view.cursor_kind = "brush"
		view.cursor_radius = float(settings[tool].size) * 0.5
	else:
		view.cursor_kind = "cross"
	view.overlay.queue_redraw()

func stroke_active() -> bool:
	return core != null and core.stroke_active()

func _on_view_event(event: InputEvent) -> void:
	if not ready_to_paint or busy: return
	if event is InputEventMouseButton:
		if event.pressed:
			if is_instance_valid(rename_row) and rename_row.visible: _finish_rename()
			get_viewport().gui_release_focus()
			if event.alt_pressed and tool != PICKER:
				_pick_color(event.position)
				return
			match tool:
				BRUSH, ERASER: _stroke_begin(event.position)
				FILL: _fill_at(event.position)
				GRADIENT: _gradient_begin(event.position)
				PICKER: _pick_color(event.position)
		else:
			match tool:
				BRUSH, ERASER: _stroke_end()
				GRADIENT: _gradient_end(event.position)
	elif event is InputEventMouseMotion:
		if stroke_active() and not stroke.is_empty():
			var pressure: float = event.pressure if event.pressure > 0.0 else 1.0
			stroke.queue.append([event.position, pressure])
		elif not gradient_start.is_empty():
			view.line_to = event.position
			view.overlay.queue_redraw()

func _process(_delta: float) -> void:
	var hold = options.get("hold")
	if hold is Callable and (hold as Callable).is_valid(): hold.call()
	if core == null or not ready_to_paint: return
	if stroke_active() and not stroke.is_empty(): _drain_stroke(STAMP_BUDGET_MS)
	if not busy: view.sync(core)

func _stroke_begin(at: Vector2) -> void:
	core.begin_stroke(tool == ERASER)
	stroke = {"lazy": at, "last": at, "pressure": 1.0, "carry": 0.0, "queue": [], "seed": randi() % 100000, "count": 0, "cursor": at}
	_stamp_at(at, 1.0)

func _stroke_end() -> void:
	if not stroke_active(): return
	_drain_stroke(-1)
	# The smoothing string catches up with the cursor at the end of the stroke.
	if float(settings[tool].smoothing) > 0.0: _walk_to(stroke.cursor, float(stroke.pressure))
	var erase := tool == ERASER
	if core.end_stroke(tr("지우개") if erase else tr("붓")):
		dirty = true
		if not erase: picker.use(primary)
	stroke = {}
	_after_change(false)

func _drain_stroke(budget_ms: int) -> void:
	var started := Time.get_ticks_msec()
	var queue: Array = stroke.queue
	var lazy_length: float = float(settings[tool].smoothing) * 80.0
	while not queue.is_empty():
		if budget_ms >= 0 and Time.get_ticks_msec() - started > budget_ms: break
		var item: Array = queue.pop_front()
		var target: Vector2 = item[0]
		var pressure: float = item[1]
		stroke.cursor = target
		var lazy: Vector2 = stroke.lazy
		if lazy_length > 0.0:
			var pull := target - lazy
			if pull.length() <= lazy_length:
				stroke.pressure = pressure
				continue
			lazy = target - pull.normalized() * lazy_length
		else:
			lazy = target
		stroke.lazy = lazy
		_walk_to(lazy, pressure)

## Stamps along the screen path from the last dab, every `spacing` of the brush diameter.
func _walk_to(to: Vector2, pressure: float) -> void:
	var from: Vector2 = stroke.last
	var length := from.distance_to(to)
	var start_pressure: float = stroke.pressure
	if length < 0.001:
		stroke.pressure = pressure
		return
	var direction := (to - from) / length
	var travelled := 0.0
	var carry: float = stroke.carry
	while true:
		var p := lerpf(start_pressure, pressure, clampf(travelled / length, 0.0, 1.0))
		var step := maxf(1.0, float(settings[tool].spacing) * _diameter(p))
		var need := step - carry
		if travelled + need > length: break
		travelled += need
		carry = 0.0
		_stamp_at(from + direction * travelled, lerpf(start_pressure, pressure, travelled / length))
	stroke.carry = carry + (length - travelled)
	stroke.last = to
	stroke.pressure = pressure

func _diameter(pressure: float) -> float:
	var s: Dictionary = settings[tool]
	return float(s.size) * (lerpf(0.12, 1.0, pressure) if bool(s.pressure_size) else 1.0)

func _stamp_at(at: Vector2, pressure: float) -> void:
	var r := view.ray(at)
	var hit: Dictionary = core.pick(r[0], r[1])
	if not hit.hit: return
	var s: Dictionary = settings[tool]
	var radius := _diameter(pressure) * 0.5 * view.world_per_pixel(hit.position)
	stroke.count = int(stroke.count) + 1
	core.stamp(hit.position, hit.normal, radius, {
		"color": primary, "mode": int(s.mode), "flow": float(s.flow), "hardness": float(s.hardness),
		"opacity": float(s.opacity) * (pressure if bool(s.pressure_opacity) else 1.0),
		"tip": int(s.tip), "roundness": float(s.roundness), "angle": deg_to_rad(float(s.angle)),
		"right": view.camera_right(), "up": view.camera_up(), "seed": int(stroke.seed) + int(stroke.count)})

func _hit_at(at: Vector2) -> Dictionary:
	var r := view.ray(at)
	return core.pick(r[0], r[1])

func _pick_color(at: Vector2) -> void:
	var hit := _hit_at(at)
	if not hit.hit: return
	var texel := core.nearest_texel(hit.position, hit.normal)
	if texel < 0: return
	picker.set_color(core.sample(texel))
	RpgUi.sfx("click", -10.0)

func _fill_at(at: Vector2) -> void:
	var hit := _hit_at(at)
	if not hit.hit: return
	var texel := core.nearest_texel(hit.position, hit.normal)
	if texel < 0: return
	var s: Dictionary = settings[FILL]
	var color := primary
	var result := {}
	await _work(tr("표면을 따라 채우는 중…"), func():
		result.count = core.fill(texel, color, int(s.tolerance), {"opacity": float(s.opacity), "mode": int(s.mode)}, bool(s.sample_all)))
	if int(result.get("count", 0)) > 0:
		dirty = true
		picker.use(color)
	_after_change(false)

func _gradient_begin(at: Vector2) -> void:
	var hit := _hit_at(at)
	if not hit.hit: return
	gradient_start = {"screen": at, "point": hit.position, "slot": int(hit.slot)}
	view.line_from = at
	view.line_to = at
	view.line_visible = true
	view.overlay.queue_redraw()

func _gradient_end(at: Vector2) -> void:
	if gradient_start.is_empty(): return
	var start := gradient_start
	gradient_start = {}
	view.line_visible = false
	view.overlay.queue_redraw()
	if at.distance_to(start.screen) < 4.0: return
	var hit := _hit_at(at)
	var a: Vector3 = start.point
	var b: Vector3 = hit.position if hit.hit else view.plane_point(at, a)
	var s: Dictionary = settings[GRADIENT]
	var c1 := primary
	var c2 := Color(primary, 0.0) if bool(s.to_clear) else secondary
	var slot := int(start.slot) if bool(s.part_only) else -1
	var result := {}
	await _work(tr("그라데이션을 그리는 중…"), func():
		result.count = core.gradient(a, b, bool(s.radial), c1, c2, {"opacity": float(s.opacity), "mode": int(s.mode)}, slot))
	if int(result.get("count", 0)) > 0: dirty = true
	_after_change(false)

func _swap_colors() -> void:
	var keep := primary
	primary = secondary
	secondary = keep
	picker.set_color(primary, false)
	_paint_chip(primary_chip, primary)
	_paint_chip(secondary_chip, secondary)
	_redraw_tool_icons()

func _reset_colors() -> void:
	primary = Color.BLACK
	secondary = Color.WHITE
	picker.set_color(primary, false)
	_paint_chip(primary_chip, primary)
	_paint_chip(secondary_chip, secondary)
	_redraw_tool_icons()

# ------------------------------------------------------------------ layers and history

func _after_change(structure: bool) -> void:
	if core == null: return
	view.sync(core)
	_refresh_layers()
	_refresh_history()
	if structure: dirty = true

func _refresh_layers() -> void:
	if core == null or not is_instance_valid(layer_list): return
	refreshing_layers = true
	for child in layer_list.get_children(): child.queue_free()
	for index in range(core.layers.size() - 1, -1, -1):
		var layer = core.layers[index]
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 4)
		layer_list.add_child(row)
		var eye := CheckBox.new()
		eye.button_pressed = layer.visible
		eye.focus_mode = Control.FOCUS_NONE
		eye.tooltip_text = tr("보이기 / 숨기기")
		var at: int = index
		eye.toggled.connect(func(on: bool):
			core.set_layer_props(at, {"visible": on}, tr("레이어 보이기"))
			_after_change(false))
		row.add_child(eye)
		var name_button := Button.new()
		var mode_text: String = "" if layer.mode == 0 else "  ·  " + tr(MODE_NAMES[layer.mode])
		name_button.text = "%s%s%s" % [layer.name, mode_text, "" if layer.opacity >= 0.999 else "  %d%%" % int(round(layer.opacity * 100))]
		name_button.tooltip_text = name_button.text
		name_button.toggle_mode = true
		name_button.button_pressed = index == core.current
		name_button.theme_type_variation = "ChoiceButton"
		name_button.focus_mode = Control.FOCUS_NONE
		name_button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		name_button.clip_text = true
		name_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		name_button.custom_minimum_size.y = 30
		name_button.add_theme_font_size_override("font_size", 13)
		name_button.pressed.connect(func():
			if stroke_active(): return
			core.current = at
			_refresh_layers())
		name_button.gui_input.connect(func(event: InputEvent):
			if event is InputEventMouseButton and event.double_click and event.button_index == MOUSE_BUTTON_LEFT:
				core.current = at
				_start_rename())
		row.add_child(name_button)
	var current = core.layers[core.current]
	layer_opacity.value = round(current.opacity * 100.0)
	layer_opacity_label.text = tr("레이어 불투명도  %d%%") % int(layer_opacity.value)
	layer_mode.select(current.mode)
	refreshing_layers = false

func _refresh_history() -> void:
	if core == null or not is_instance_valid(history_list): return
	history_list.clear()
	history_list.add_item(tr("처음 상태"))
	for name in core.history_names(): history_list.add_item(tr(name))
	for i in history_list.item_count:
		if i > core.history_index: history_list.set_item_custom_fg_color(i, Color(0.35, 0.3, 0.25, 0.55))
	history_list.select(core.history_index)
	history_list.ensure_current_is_visible()
	undo_button.disabled = not core.can_undo()
	redo_button.disabled = not core.can_redo()

func _add_layer() -> void:
	if core == null or busy or stroke_active(): return
	if core.add_layer(tr("레이어 %d") % (core.layers.size())) < 0:
		_status(tr("레이어는 8개까지 만들 수 있어요."))
		return
	_after_change(true)

func _duplicate_layer() -> void:
	if core == null or busy or stroke_active(): return
	if core.duplicate_layer(core.current, core.layers[core.current].name + tr(" 복사")) < 0:
		_status(tr("레이어는 8개까지 만들 수 있어요."))
		return
	_after_change(true)

func _delete_layer() -> void:
	if core == null or busy or stroke_active(): return
	if not core.delete_layer(core.current):
		_status(tr("마지막 레이어는 지울 수 없어요."))
		return
	_after_change(true)

func _move_layer(direction: int) -> void:
	if core == null or busy or stroke_active(): return
	if core.move_layer(core.current, core.current + direction): _after_change(true)

func _start_rename() -> void:
	if core == null: return
	rename_row.visible = true
	rename_field.text = core.layers[core.current].name
	rename_field.grab_focus()
	rename_field.select_all()

func _rename_key(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE): return
	# While an IME syllable is being composed, Esc belongs to the IME.
	if DisplayServer.has_feature(DisplayServer.FEATURE_IME) and not DisplayServer.ime_get_text().is_empty(): return
	rename_row.visible = false
	rename_field.release_focus()
	rename_field.accept_event()

func _finish_rename() -> void:
	if not rename_row.visible: return
	rename_row.visible = false
	var name := rename_field.text.strip_edges()
	if not name.is_empty() and core != null:
		core.set_layer_props(core.current, {"name": name.substr(0, 24)}, tr("이름 바꾸기"))
		_after_change(false)
	rename_field.release_focus()

func undo() -> void:
	if core == null or busy or not core.can_undo(): return
	core.undo()
	dirty = true
	_after_change(false)

func redo() -> void:
	if core == null or busy or not core.can_redo(): return
	core.redo()
	dirty = true
	_after_change(false)

# ------------------------------------------------------------------ keys

func _unhandled_key_input(event: InputEvent) -> void:
	# Nothing behind the workspace reacts to keys while it is open.
	get_viewport().set_input_as_handled()
	var key := event as InputEventKey
	if key == null or not key.pressed: return
	var focus := get_viewport().gui_get_focus_owner()
	if focus is LineEdit or focus is TextEdit:
		if key.keycode == KEY_ESCAPE: focus.release_focus()
		return
	if busy or is_instance_valid(dialog_layer):
		if key.keycode == KEY_ESCAPE and is_instance_valid(dialog_layer): dialog_layer.queue_free()
		return
	var command := key.is_command_or_control_pressed()
	match key.keycode:
		KEY_ESCAPE: _ask_cancel()
		KEY_Z:
			if command and key.shift_pressed: redo()
			elif command: undo()
		KEY_Y:
			if command: redo()
		KEY_S:
			if command: save()
		KEY_N:
			if command and key.shift_pressed: _add_layer()
	if command or core == null or not ready_to_paint: return
	match key.keycode:
		KEY_B: _select_tool(BRUSH)
		KEY_E: _select_tool(ERASER)
		KEY_G: _select_tool(GRADIENT if tool == FILL else FILL)
		KEY_I: _select_tool(PICKER)
		KEY_X: _swap_colors()
		KEY_D: _reset_colors()
		KEY_F: view.reset_view()
		KEY_BRACKETLEFT, KEY_BRACKETRIGHT:
			if tool in [BRUSH, ERASER]:
				var grow := key.keycode == KEY_BRACKETRIGHT
				if key.shift_pressed:
					_set_option(tool, "hardness", clampf(float(settings[tool].hardness) + (0.1 if grow else -0.1), 0.0, 1.0))
				else:
					var value := float(settings[tool].size)
					var step := maxf(1.0, value * 0.15)
					_set_option(tool, "size", clampf(value + (step if grow else -step), 1.0, 400.0))
		KEY_0, KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9:
			# Photoshop: number keys set the tool opacity (1 = 10% ... 0 = 100%).
			if tool in [BRUSH, ERASER, FILL, GRADIENT]:
				var digit := key.keycode - KEY_0
				_set_option(tool, "opacity", 1.0 if digit == 0 else digit / 10.0)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey or event is InputEventMouseButton or event is InputEventJoypadButton:
		get_viewport().set_input_as_handled()

func _set_option(tool_name: String, key: String, value: float) -> void:
	var control = option_controls.get(tool_name + ":" + key)
	if control is Range: (control as Range).value = value
	else: settings[tool_name][key] = value
	_update_cursor()

# ------------------------------------------------------------------ save / cancel / reset

func save() -> void:
	if busy or closing or core == null or stroke_active(): return
	if not dirty:
		_close(false)
		return
	var result := {}
	var flatten := core
	await _work(tr("레이어를 하나로 합치는 중…"), func():
		var image := Image.create_from_data(SIZE, SIZE, false, Image.FORMAT_RGBA8, flatten.composite())
		image.convert(Image.FORMAT_RGB8)
		result.image = image
		result.png = image.save_png_to_buffer())
	if not is_inside_tree() or not result.has("png"): return
	_show_busy(tr("마을에 저장하는 중…"))
	var reply: Dictionary = await PaintApply.upload(api, str(obj.id), result.png)
	if not is_inside_tree(): return
	_hide_busy()
	if not reply.get("ok", false):
		_status(tr("저장하지 못했어요: %s") % _error_text(str(reply.get("error", ""))))
		RpgUi.sfx("close", -6.0)
		return
	var version = reply.data.get("paint_version")
	if version == null:
		_status(tr("저장하지 못했어요: %s") % "paint_version")
		return
	var key := str(obj.id) + ":" + str(int(version))
	PaintApply.remember(key, result.image)
	obj.paint_version = int(version)
	var saved = options.get("saved")
	if saved is Callable and (saved as Callable).is_valid(): saved.call(result.image, int(version))
	RpgUi.sfx("confirm", -6.0)
	_close(true)

func _error_text(code: String) -> String:
	return {"object_is_listed": tr("장터에 올린 물건은 칠할 수 없어요."), "object_not_found": tr("이 물건을 찾을 수 없어요."),
		"paint_too_large": tr("그림이 너무 커요."), "connection_failed": tr("서버에 연결하지 못했어요."),
		"body_too_large": tr("그림이 너무 커요."), "session_expired": tr("다시 로그인해 주세요.")}.get(code, code)

func _ask_cancel() -> void:
	if busy or closing: return
	if stroke_active(): return
	if dirty: _confirm(tr("칠한 것을 저장하지 않고 닫을까요?"), tr("저장 안 함"), func(): _close(false))
	else: _close(false)

func _ask_reset() -> void:
	if busy or closing or core == null: return
	_confirm(tr("칠한 것을 모두 지우고 처음 모습으로 되돌릴까요? 저장된 칠도 지워져요."), tr("되돌리기"), _reset)

func _reset() -> void:
	if obj.get("paint_version") != null:
		_show_busy(tr("처음 모습으로 되돌리는 중…"))
		var reply: Dictionary = await PaintApply.clear_remote(api, str(obj.id))
		if not is_inside_tree(): return
		_hide_busy()
		if not reply.get("ok", false):
			_status(tr("되돌리지 못했어요: %s") % _error_text(str(reply.get("error", ""))))
			return
		obj.paint_version = null
		var saved = options.get("saved")
		if saved is Callable and (saved as Callable).is_valid(): saved.call(null, null)
		_close(true)
		return
	# Nothing saved yet: start again from the unpainted look.
	core.start_layers(core.backdrop, core.backdrop, tr("바탕"))
	dirty = false
	_after_change(false)

func _close(saved: bool) -> void:
	if closing: return
	closing = true
	if core != null and core.stroke_active(): core.end_stroke()
	_save_settings()
	RpgUi.sfx("close", -10.0)
	finished.emit(saved)
	queue_free()

# ------------------------------------------------------------------ whole-object colour (no UVs)

func _build_fallback(reason: String) -> void:
	# Only a colour window: the world stays visible (and rendered) behind it.
	for viewport in paused_views:
		if is_instance_valid(viewport): viewport.disable_3d = false
	paused_views.clear()
	backdrop.color = Color(0.02, 0.03, 0.04, 0.62)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	move_child(center, 1)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", RpgUi.panel_style("night"))
	panel.custom_minimum_size.x = 460
	center.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	panel.add_child(column)
	RpgUi.label(column, tr("전체 색 바꾸기"), 24, RpgUi.GOLD)
	var why := RpgUi.label(column, reason, 14, RpgUi.INK)
	why.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	why.custom_minimum_size.x = 420
	var parts: Array = options.get("parts", [])
	var part_choice: OptionButton = null
	if not parts.is_empty():
		part_choice = OptionButton.new()
		part_choice.add_item(tr("전체"))
		part_choice.set_item_metadata(0, "all")
		for part in parts:
			part_choice.add_item(str(part[1]))
			part_choice.set_item_metadata(part_choice.item_count - 1, str(part[0]))
		part_choice.focus_mode = Control.FOCUS_NONE
		column.add_child(part_choice)
	picker = ColorPanel.new()
	picker.swatches = PackedStringArray(_setting("swatches", "").split(",", false))
	picker.recent = PackedStringArray(_setting("recent", "").split(",", false))
	column.add_child(picker)
	picker.set_color(primary, false)
	picker.color_changed.connect(func(value: Color): primary = value)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	row.add_theme_constant_override("separation", 8)
	column.add_child(row)
	var flat = options.get("flat")
	var target := func() -> String: return "all" if part_choice == null else str(part_choice.get_item_metadata(part_choice.selected))
	_button(row, tr("원래 색"), func():
		if flat is Callable: flat.call("#ffffff", target.call(), true)
		_close(true))
	_button(row, tr("취소"), func(): _close(false))
	_button(row, tr("적용"), func():
		picker.use(primary)
		if flat is Callable: flat.call("#" + primary.to_html(false), target.call(), false)
		_close(true), "GoldButton")
	RpgUi.pop_in(panel)

# ------------------------------------------------------------------ settings (follow the account)

func _settings_path() -> String:
	return load("res://scripts/i18n.gd").settings_path()

func _setting(key: String, fallback):
	var config := ConfigFile.new()
	config.load(_settings_path())
	return config.get_value(SETTINGS_SECTION, key, fallback)

func _load_settings() -> void:
	var config := ConfigFile.new()
	if config.load(_settings_path()) != OK: return
	for tool_name in settings:
		for key in settings[tool_name]:
			if not config.has_section_key(SETTINGS_SECTION, tool_name + "_" + key): continue
			var stored = config.get_value(SETTINGS_SECTION, tool_name + "_" + key)
			if settings[tool_name][key] is bool: settings[tool_name][key] = bool(stored)
			elif settings[tool_name][key] is int: settings[tool_name][key] = int(stored)
			else: settings[tool_name][key] = float(stored)
	var front := str(config.get_value(SETTINGS_SECTION, "primary", ""))
	var back := str(config.get_value(SETTINGS_SECTION, "secondary", ""))
	if front.is_valid_html_color(): primary = Color.html(front)
	if back.is_valid_html_color(): secondary = Color.html(back)

func _save_settings() -> void:
	if not bool(options.get("remember", true)): return
	var config := ConfigFile.new()
	config.load(_settings_path())
	for tool_name in settings:
		for key in settings[tool_name]:
			var value = settings[tool_name][key]
			config.set_value(SETTINGS_SECTION, tool_name + "_" + key, snappedf(value, 0.001) if value is float else value)
	config.set_value(SETTINGS_SECTION, "primary", primary.to_html(false))
	config.set_value(SETTINGS_SECTION, "secondary", secondary.to_html(false))
	if is_instance_valid(picker):
		config.set_value(SETTINGS_SECTION, "swatches", ",".join(picker.swatches))
		config.set_value(SETTINGS_SECTION, "recent", ",".join(picker.recent))
	config.save(_settings_path())
