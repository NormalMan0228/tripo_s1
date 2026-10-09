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
##
## Laid out like current drawing apps (paint_widgets.gd, icons in assets/ui/painter): a slim
## tool rail with the colour well on the left, a context bar on top with only the active
## tool's options (brush presets drawn as strokes, size, opacity, flow, hardness, smoothing;
## the rest behind the tune button) beside undo/redo, Procreate-style size and opacity
## sliders on the canvas edge, and a right dock with folding Colour / Layers / History.
signal finished(saved: bool)

const Core = preload("res://scripts/painter/paint_core.gd")
const PaintApply = preload("res://scripts/painter/paint_apply.gd")
const PaintView = preload("res://scripts/painter/paint_view.gd")
const ColorPanel = preload("res://scripts/painter/color_picker.gd")
const Widgets = preload("res://scripts/painter/paint_widgets.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const SIZE := 1024
const GROUP := &"painter_open"
const BRUSH := "brush"
const ERASER := "eraser"
const FILL := "fill"
const GRADIENT := "gradient"
const PICKER := "picker"
## Photoshop's Korean names ("표준" is Normal; "보통" already reads Medium in the settings).
const MODE_NAMES := ["표준", "곱하기", "스크린", "오버레이", "더하기"]
const TIP_NAMES := ["둥근 붓", "납작 붓", "거친 붓"]
## Rail order: tool, name, key, icon.
const TOOL_SPECS := [[BRUSH, "붓", "B", "brush"], [ERASER, "지우개", "E", "eraser"], [FILL, "채우기", "G", "fill"],
	[GRADIENT, "그라데이션", "G", "gradient"], [PICKER, "스포이드", "I", "picker"]]
## Brush presets (brush and eraser): choosing one sets these keys and the size.
const PRESETS := [
	{"name": "연필", "tip": 0, "size": 6.0, "hardness": 1.0, "flow": 1.0, "spacing": 0.08, "roundness": 1.0, "angle": 0.0},
	{"name": "둥근 붓", "tip": 0, "size": 28.0, "hardness": 0.75, "flow": 1.0, "spacing": 0.12, "roundness": 1.0, "angle": 0.0},
	{"name": "에어브러시", "tip": 0, "size": 72.0, "hardness": 0.0, "flow": 0.18, "spacing": 0.1, "roundness": 1.0, "angle": 0.0},
	{"name": "납작 붓", "tip": 1, "size": 34.0, "hardness": 0.85, "flow": 1.0, "spacing": 0.06, "roundness": 0.3, "angle": 35.0},
	{"name": "거친 붓", "tip": 2, "size": 40.0, "hardness": 0.6, "flow": 0.85, "spacing": 0.1, "roundness": 1.0, "angle": 0.0},
	{"name": "마커", "tip": 1, "size": 22.0, "hardness": 0.95, "flow": 0.55, "spacing": 0.05, "roundness": 0.55, "angle": 90.0},
]
const PRESET_KEYS := ["tip", "hardness", "flow", "spacing", "roundness", "angle"]
const SETTINGS_SECTION := "painter"
const STAMP_BUDGET_MS := 9
const DOCK_WIDTH := 276.0

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
## "tool:key" -> [{control, refresh}]: every control showing a setting (context bar, edge
## sliders, the tune popover); _set_option() keeps them in step.
var option_controls := {}
var primary_chip: Button
var secondary_chip: Button
var symmetry_button: Button
var symmetry_badge: Label
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
var stage: Control
var size_edge
var opacity_edge
var preset_views := {}
var preset_tiles: Array = []
var sections := {}
var dock_scroll: ScrollContainer
var popover: Control
var gradient_swatches: Array = []
var thumbs := {}
var thumb_views := {}
var thumb_queue: Array = []
var warm_previews := 0
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
	look.merge_with(Widgets.theme())
	theme = look
	backdrop = ColorRect.new()
	backdrop.color = Color("101416")
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
	# One pose for the bake and the view, even if the object's program moves it meanwhile.
	var slot_list := PaintApply.slots_of(model)
	var poses := PaintApply.poses_of(model, slot_list)
	var slots := PaintApply.mesh_slots(model, poses)
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
	if not is_instance_valid(model):
		_close(false)
		return
	core = engine
	_hide_busy()
	if not job.get("done", false) or core.covered < SIZE * SIZE / 400:
		core = null
		_build_fallback(tr("이 물건의 표면 좌표(UV)가 비어 있어 붓으로 칠할 수 없어요. 대신 전체 색을 바꿀 수 있어요."))
		return
	_build_workspace()
	view.show_model(model, slot_list, core, poses)
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
	workspace.offset_left = 8; workspace.offset_top = 8; workspace.offset_right = -8; workspace.offset_bottom = -8
	workspace.add_theme_constant_override("separation", 8)
	add_child(workspace)
	move_child(workspace, 1)
	# Top bar: title, undo/redo, the active tool's options, reset / cancel / save. One height for
	# every tool, so switching tools never resizes (and reframes) the view.
	var bar := PanelContainer.new()
	bar.add_theme_stylebox_override("panel", _panel_box(10, Vector4(12, 6, 8, 6)))
	bar.custom_minimum_size.y = 54
	workspace.add_child(bar)
	var bar_row := HBoxContainer.new()
	bar_row.add_theme_constant_override("separation", 8)
	bar.add_child(bar_row)
	var heading := VBoxContainer.new()
	heading.custom_minimum_size.x = 112
	heading.alignment = BoxContainer.ALIGNMENT_CENTER
	heading.add_theme_constant_override("separation", 0)
	bar_row.add_child(heading)
	var ribbon := Widgets.caption(heading, tr("색칠 작업대"), 15, Widgets.GOLD)
	ribbon.add_theme_font_override("font", RpgUi.FONT_DISPLAY)
	title_label = Widgets.caption(heading, str(obj.get("name", "")), 12)
	title_label.clip_text = true
	title_label.custom_minimum_size.x = 112
	var heading_rule := _rule(true)
	bar_row.add_child(heading_rule)
	# A large interface scale narrows the canvas: the title gives way before options clip.
	var fit := func():
		heading.visible = size.x >= 1150.0
		heading_rule.visible = heading.visible
	resized.connect(fit)
	fit.call()
	undo_button = Widgets.icon_button(bar_row, "undo", tr("되돌리기") + "  ·  Ctrl+Z", undo, 36, "PaintSegment")
	redo_button = Widgets.icon_button(bar_row, "redo", tr("다시 하기") + "  ·  Ctrl+Shift+Z", redo, 36, "PaintSegment")
	for b in [undo_button, redo_button]: b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	bar_row.add_child(_rule(true))
	var context_bar := HBoxContainer.new()
	context_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	context_bar.add_theme_constant_override("separation", 10)
	bar_row.add_child(context_bar)
	_build_options(context_bar)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 6)
	bar_row.add_child(actions)
	reset_button = _button(actions, tr("원래대로"), _ask_reset, "", tr("칠한 것을 모두 지우고 처음 모습으로"))
	_button(actions, tr("취소"), _ask_cancel, "", tr("저장하지 않고 닫기  ·  Esc"))
	save_button = _button(actions, tr("저장"), save, "PaintGold", tr("마을과 방에 칠한 모습으로 저장  ·  Ctrl+S"))
	save_button.custom_minimum_size.x = 76
	for b in actions.get_children(): (b as Control).size_flags_vertical = Control.SIZE_SHRINK_CENTER
	# Middle: tool rail | canvas | dock.
	var middle := HBoxContainer.new()
	middle.size_flags_vertical = Control.SIZE_EXPAND_FILL
	middle.add_theme_constant_override("separation", 8)
	workspace.add_child(middle)
	middle.add_child(_build_rail())
	var frame := PanelContainer.new()
	frame.add_theme_stylebox_override("panel", Widgets.flat(Color("0d1012"), 10, Widgets.LINE, 1, 1))
	frame.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	middle.add_child(frame)
	stage = Control.new()
	stage.clip_contents = true
	frame.add_child(stage)
	view = PaintView.new()
	view.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	view.paint_event.connect(_on_view_event)
	view.camera_moving.connect(_flush_stroke)
	stage.add_child(view)
	_build_canvas_overlay()
	middle.add_child(_build_dock())
	_status("")

func _panel_box(radius: int, padding: Vector4) -> StyleBoxFlat:
	var box := Widgets.flat(Widgets.PANEL, radius, Widgets.LINE, 1)
	box.content_margin_left = padding.x; box.content_margin_top = padding.y
	box.content_margin_right = padding.z; box.content_margin_bottom = padding.w
	return box

## A thin divider line (vertical in rows, horizontal in columns).
func _rule(vertical: bool) -> Control:
	var line := ColorRect.new()
	line.color = Widgets.LINE
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if vertical:
		line.custom_minimum_size = Vector2(1, 30)
		line.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	else:
		line.custom_minimum_size = Vector2(0, 1)
	return line

func _button(parent: Node, text: String, callback: Callable, variation := "", tip := "") -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size.y = 34
	if not variation.is_empty(): b.theme_type_variation = variation
	b.add_theme_font_size_override("font_size", 13)
	b.pressed.connect(func(): callback.call())
	if not tip.is_empty(): b.tooltip_text = tip
	parent.add_child(b)
	return b

## Registers a control that shows settings[tool_name][key]; refresh(value) updates it silently.
func _bind(tool_name: String, key: String, control: Control, refresh: Callable) -> void:
	var id := tool_name + ":" + key
	if not option_controls.has(id): option_controls[id] = []
	option_controls[id].append({"control": control, "refresh": refresh})

## A compact labelled slider: its name and value (e.g. 크기 28px) over a thin bar.
func _slider(parent: Node, key: String, tool_name: String, title: String, low: float, high: float, step: float, unit: String, scale := 1.0, width := 92.0, tip := "") -> HSlider:
	var box := VBoxContainer.new()
	box.custom_minimum_size.x = width
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_theme_constant_override("separation", 1)
	parent.add_child(box)
	var caption := Widgets.caption(box, "", 11)
	var slider := HSlider.new()
	slider.min_value = low; slider.max_value = high; slider.step = step
	# Size moves on a curve: fine steps for small brushes, still reaching 400 px.
	slider.exp_edit = key == "size"
	slider.focus_mode = Control.FOCUS_NONE
	slider.custom_minimum_size.y = 16
	if not tip.is_empty(): slider.tooltip_text = tip
	box.add_child(slider)
	# Values are stored as they are used (0..1 for percentages); `scale` only formats them.
	var show := func(value: float):
		caption.text = "%s  %d%s" % [title, int(round(value * scale)), unit]
	slider.value = float(settings[tool_name][key])
	show.call(slider.value)
	slider.value_changed.connect(func(value: float):
		show.call(value)
		_set_option(tool_name, key, value, slider))
	_bind(tool_name, key, slider, func(value):
		slider.set_value_no_signal(float(value))
		show.call(float(value)))
	return slider

func _toggle(parent: Node, key: String, tool_name: String, text: String, tip: String, icon_name := "") -> Button:
	var b := Button.new()
	b.toggle_mode = true
	b.text = text
	b.theme_type_variation = "PaintSegment"
	if not icon_name.is_empty():
		b.icon = Widgets.icon(icon_name)
		b.add_theme_constant_override("icon_max_width", 16)
		b.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size.y = 32
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	b.add_theme_font_size_override("font_size", 12)
	b.button_pressed = bool(settings[tool_name][key])
	b.tooltip_text = tip
	b.toggled.connect(func(on: bool): _set_option(tool_name, key, on, b))
	_bind(tool_name, key, b, func(value): b.set_pressed_no_signal(bool(value)))
	parent.add_child(b)
	return b

func _choice(parent: Node, key: String, tool_name: String, names: Array, tip: String, width := 92.0) -> OptionButton:
	var choice := OptionButton.new()
	for name in names: choice.add_item(tr(name))
	choice.focus_mode = Control.FOCUS_NONE
	choice.custom_minimum_size = Vector2(width, 32)
	choice.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	choice.tooltip_text = tip
	choice.select(int(settings[tool_name][key]))
	choice.item_selected.connect(func(index: int): _set_option(tool_name, key, index, choice))
	_bind(tool_name, key, choice, func(value): choice.select(int(value)))
	parent.add_child(choice)
	return choice

## Side-by-side choices (gradient shape and colours): segment i stores values[i]. `draw`
## paints a segment that has no icon (draw.call(canvas, i)).
func _segments(parent: Node, key: String, tool_name: String, values: Array, icons: Array, tips: Array, draw := Callable()) -> Array:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 3)
	row.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	parent.add_child(row)
	var buttons: Array[Button] = []
	for i in values.size():
		var b := Widgets.icon_button(row, icons[i], tips[i], func(): _set_option(tool_name, key, values[i]), 34, "PaintSegment")
		b.toggle_mode = true
		if icons[i] == "" and draw.is_valid():
			b.custom_minimum_size.x = 46
			var canvas := Control.new()
			canvas.mouse_filter = Control.MOUSE_FILTER_IGNORE
			canvas.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
			canvas.offset_left = 8; canvas.offset_top = 10; canvas.offset_right = -8; canvas.offset_bottom = -10
			var index: int = i
			canvas.draw.connect(func(): draw.call(canvas, index))
			b.add_child(canvas)
			gradient_swatches.append(canvas)
		buttons.append(b)
	var refresh := func(value):
		for i in buttons.size(): buttons[i].set_pressed_no_signal(values[i] == value)
	refresh.call(settings[tool_name][key])
	_bind(tool_name, key, row, refresh)
	return buttons

## The context bar: one row per tool, only the active tool's row shows.
func _build_options(parent: HBoxContainer) -> void:
	for tool_name in [BRUSH, ERASER]:
		var holder := HBoxContainer.new()
		holder.add_theme_constant_override("separation", 10)
		holder.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		parent.add_child(holder)
		option_rows[tool_name] = holder
		_preset_button(holder, tool_name)
		_slider(holder, "size", tool_name, tr("크기"), 1, 400, 1, "px", 1.0, 96, tr("크기") + "  ·  [ ]")
		_slider(holder, "opacity", tool_name, tr("불투명도"), 0.01, 1, 0.01, "%", 100.0, 92, tr("불투명도") + "  ·  1…0")
		_slider(holder, "flow", tool_name, tr("흐름"), 0.01, 1, 0.01, "%", 100.0, 84)
		_slider(holder, "hardness", tool_name, tr("경도"), 0, 1, 0.01, "%", 100.0, 84, tr("경도") + "  ·  Shift+[ ]")
		_slider(holder, "smoothing", tool_name, tr("보정"), 0, 1, 0.01, "%", 100.0, 84)
		var tune: Button = Widgets.icon_button(holder, "tune", tr("붓 설정 더 보기 · 모양, 각도, 간격, 필압, 혼합"), func(): pass, 34, "PaintSegment")
		tune.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		var name: String = tool_name
		tune.pressed.connect(func(): _open_tune(name, tune))
	var fill_row := HBoxContainer.new()
	fill_row.add_theme_constant_override("separation", 10)
	fill_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(fill_row)
	option_rows[FILL] = fill_row
	_slider(fill_row, "tolerance", FILL, tr("허용치"), 0, 255, 1, "", 1.0, 110)
	_slider(fill_row, "opacity", FILL, tr("불투명도"), 0.01, 1, 0.01, "%", 100.0, 100)
	_choice(fill_row, "mode", FILL, MODE_NAMES, tr("혼합 모드"))
	_toggle(fill_row, "sample_all", FILL, tr("모든 레이어"), tr("보이는 색 전체를 기준으로 영역을 고릅니다"), "layers")
	_hint(fill_row, tr("클릭한 곳과 이어진 비슷한 색을 표면을 따라 채워요."))
	var gradient_row := HBoxContainer.new()
	gradient_row.add_theme_constant_override("separation", 10)
	gradient_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(gradient_row)
	option_rows[GRADIENT] = gradient_row
	_segments(gradient_row, "radial", GRADIENT, [false, true], ["gradient_linear", "gradient_radial"], [tr("선형"), tr("원형")])
	_segments(gradient_row, "to_clear", GRADIENT, [false, true], ["", ""], [tr("앞색 → 뒷색"), tr("앞색 → 투명")], _draw_gradient_swatch)
	_slider(gradient_row, "opacity", GRADIENT, tr("불투명도"), 0.01, 1, 0.01, "%", 100.0, 100)
	_choice(gradient_row, "mode", GRADIENT, MODE_NAMES, tr("혼합 모드"))
	_toggle(gradient_row, "part_only", GRADIENT, tr("시작 부품만"), tr("드래그를 시작한 부품에만 그립니다"), "part")
	_hint(gradient_row, tr("물건 위에서 드래그해 방향과 길이를 정해요."))
	var picker_row := HBoxContainer.new()
	picker_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(picker_row)
	option_rows[PICKER] = picker_row
	_hint(picker_row, tr("물건을 클릭하면 보이는 색을 앞색으로 가져와요. 다른 도구에서는 Alt+클릭."))

func _hint(parent: Node, text: String) -> Label:
	var label := Widgets.caption(parent, text, 12)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	label.clip_text = true
	label.tooltip_text = text
	label.mouse_filter = Control.MOUSE_FILTER_PASS
	return label

## Front colour to back colour (or to clear) as a small bar inside a gradient segment.
func _draw_gradient_swatch(canvas: Control, index: int) -> void:
	var rect := Rect2(Vector2.ZERO, canvas.size)
	if index == 1:
		var cell := rect.size.y * 0.5
		var x := 0.0
		var flip := 0
		while x < rect.size.x:
			for row in 2:
				var tint := Color(0.75, 0.75, 0.75) if (flip + row) % 2 == 0 else Color(0.45, 0.45, 0.45)
				canvas.draw_rect(Rect2(Vector2(x, row * cell), Vector2(minf(cell, rect.size.x - x), cell)), tint)
			x += cell
			flip += 1
	var steps := 12
	for i in steps:
		var t := (i + 0.5) / steps
		var c := primary.lerp(secondary, t) if index == 0 else Color(primary, 1.0 - t)
		canvas.draw_rect(Rect2(Vector2(rect.size.x * i / steps, 0), Vector2(rect.size.x / steps + 0.5, rect.size.y)), c)
	canvas.draw_rect(rect, Color(0, 0, 0, 0.5), false, 1.0)

# ------------------------------------------------------------------ presets and the tune popover

## The preset key in the context bar: the current preset's stroke and name.
func _preset_button(parent: Node, tool_name: String) -> Button:
	var b := Button.new()
	b.theme_type_variation = "PaintSegment"
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(124, 40)
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	b.tooltip_text = tr("붓 프리셋")
	parent.add_child(b)
	var preview := TextureRect.new()
	preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	preview.modulate = Widgets.INK
	preview.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	preview.offset_left = 6; preview.offset_top = 3; preview.offset_right = -6; preview.offset_bottom = -15
	b.add_child(preview)
	var name := Label.new()
	name.add_theme_font_size_override("font_size", 11)
	name.add_theme_color_override("font_color", Widgets.MUTED)
	name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name.mouse_filter = Control.MOUSE_FILTER_IGNORE
	name.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	name.offset_top = -16; name.offset_bottom = -1
	b.add_child(name)
	preset_views[tool_name] = {"preview": preview, "name": name}
	b.pressed.connect(func(): _open_presets(tool_name, b))
	_refresh_preset(tool_name)
	return b

## Index of the preset the tool's settings match (size aside), or -1.
func _current_preset(tool_name: String) -> int:
	var s: Dictionary = settings[tool_name]
	for i in PRESETS.size():
		var p: Dictionary = PRESETS[i]
		var same := int(s.tip) == int(p.tip)
		for key in ["hardness", "flow", "spacing"]: same = same and absf(float(s[key]) - float(p[key])) < 0.005
		if int(p.tip) != 0:
			same = same and absf(float(s.roundness) - float(p.roundness)) < 0.005 and absf(float(s.angle) - float(p.angle)) < 0.5
		if same: return i
	return -1

func _preview_spec(spec: Dictionary) -> Dictionary:
	var out := {}
	for key in PRESET_KEYS + ["size"]: out[key] = spec.get(key, 0)
	return out

func _refresh_preset(tool_name: String) -> void:
	var views: Dictionary = preset_views.get(tool_name, {})
	if views.is_empty(): return
	var index := _current_preset(tool_name)
	var s: Dictionary = settings[tool_name]
	# Custom settings show their tip's stroke (drawing one per slider step would stutter).
	var spec: Dictionary = PRESETS[index] if index >= 0 else PRESETS[[1, 3, 4][clampi(int(s.tip), 0, 2)]]
	(views.preview as TextureRect).texture = Widgets.stroke_preview(_preview_spec(spec), 112, 22)
	(views.name as Label).text = tr(PRESETS[index].name) if index >= 0 else tr("직접 설정")

func _apply_preset(tool_name: String, index: int) -> void:
	var p: Dictionary = PRESETS[index]
	for key in PRESET_KEYS + ["size"]: _set_option(tool_name, key, p[key])
	view.flash_ring()

func _open_presets(tool_name: String, anchor: Control) -> void:
	var column := _popover(anchor)
	Widgets.caption(column, tr("붓 프리셋"), 12, Widgets.GOLD)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 6)
	grid.add_theme_constant_override("v_separation", 6)
	column.add_child(grid)
	var current := _current_preset(tool_name)
	preset_tiles.clear()
	for i in PRESETS.size():
		var tile := Button.new()
		tile.theme_type_variation = "PaintSegment"
		tile.toggle_mode = true
		tile.button_pressed = i == current
		tile.focus_mode = Control.FOCUS_NONE
		tile.custom_minimum_size = Vector2(156, 62)
		tile.tooltip_text = tr(PRESETS[i].name)
		var preview := TextureRect.new()
		preview.texture = Widgets.stroke_preview(_preview_spec(PRESETS[i]), 144, 34)
		preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
		preview.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		preview.offset_left = 6; preview.offset_top = 4; preview.offset_right = -6; preview.offset_bottom = -20
		tile.add_child(preview)
		var name := Label.new()
		name.text = tr(PRESETS[i].name)
		name.add_theme_font_size_override("font_size", 12)
		name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		name.mouse_filter = Control.MOUSE_FILTER_IGNORE
		name.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
		name.offset_top = -20; name.offset_bottom = -3
		tile.add_child(name)
		var index: int = i
		tile.pressed.connect(func():
			_apply_preset(tool_name, index)
			_close_popover())
		grid.add_child(tile)
		preset_tiles.append(tile)

## Tip shape, angle, roundness, spacing, pen pressure and (brush) blend mode.
func _open_tune(tool_name: String, anchor: Control) -> void:
	var column := _popover(anchor)
	Widgets.caption(column, tr("붓 끝 모양"), 12, Widgets.GOLD)
	var tips := HBoxContainer.new()
	tips.add_theme_constant_override("separation", 6)
	column.add_child(tips)
	var tip_buttons: Array[Button] = []
	for i in TIP_NAMES.size():
		var b := Button.new()
		b.theme_type_variation = "PaintSegment"
		b.toggle_mode = true
		b.focus_mode = Control.FOCUS_NONE
		b.custom_minimum_size = Vector2(92, 54)
		b.tooltip_text = tr(TIP_NAMES[i])
		var preview := TextureRect.new()
		preview.texture = Widgets.stroke_preview(_preview_spec(PRESETS[[1, 3, 4][i]]), 112, 22)
		preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
		preview.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		preview.offset_left = 4; preview.offset_top = 4; preview.offset_right = -4; preview.offset_bottom = -20
		b.add_child(preview)
		var name := Label.new()
		name.text = tr(TIP_NAMES[i])
		name.add_theme_font_size_override("font_size", 11)
		name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		name.mouse_filter = Control.MOUSE_FILTER_IGNORE
		name.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
		name.offset_top = -19; name.offset_bottom = -3
		b.add_child(name)
		var index: int = i
		b.pressed.connect(func(): _set_option(tool_name, "tip", index))
		tips.add_child(b)
		tip_buttons.append(b)
	var show_tip := func(value):
		for i in tip_buttons.size(): tip_buttons[i].set_pressed_no_signal(i == int(value))
	show_tip.call(settings[tool_name].tip)
	_bind(tool_name, "tip", tips, show_tip)
	var shape := HBoxContainer.new()
	shape.add_theme_constant_override("separation", 12)
	column.add_child(shape)
	_slider(shape, "angle", tool_name, tr("각도"), 0, 180, 1, "°", 1.0, 88)
	_slider(shape, "roundness", tool_name, tr("둥글기"), 0.05, 1, 0.01, "%", 100.0, 88)
	_slider(shape, "spacing", tool_name, tr("간격"), 0.01, 2, 0.01, "%", 100.0, 88)
	var pens := HBoxContainer.new()
	pens.add_theme_constant_override("separation", 6)
	column.add_child(pens)
	_toggle(pens, "pressure_size", tool_name, tr("필압→크기"), tr("펜 압력으로 크기 조절"), "pressure")
	_toggle(pens, "pressure_opacity", tool_name, tr("필압→불투명"), tr("펜 압력으로 불투명도 조절"), "pressure")
	if tool_name == BRUSH:
		var blend := HBoxContainer.new()
		blend.add_theme_constant_override("separation", 8)
		column.add_child(blend)
		var label := Widgets.caption(blend, tr("붓 혼합 모드"), 12)
		label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		_choice(blend, "mode", tool_name, MODE_NAMES, tr("붓 혼합 모드"), 120)

## A small panel under (or beside) a control; a click outside or Esc closes it. Returns its column.
func _popover(anchor: Control) -> VBoxContainer:
	_close_popover()
	popover = Control.new()
	popover.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	popover.mouse_filter = Control.MOUSE_FILTER_STOP
	popover.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.pressed: _close_popover())
	add_child(popover)
	var panel := PanelContainer.new()
	var box := Widgets.flat(Color(0.075, 0.09, 0.1, 0.99), 10, Color(Widgets.GOLD, 0.35), 1, 12)
	box.shadow_color = Color(0, 0, 0, 0.45)
	box.shadow_size = 12
	panel.add_theme_stylebox_override("panel", box)
	panel.modulate.a = 0.0
	popover.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	panel.add_child(column)
	_place_popover.call_deferred(panel, anchor)
	return column

func _place_popover(panel: Control, anchor: Control) -> void:
	if not is_instance_valid(panel) or not is_instance_valid(anchor) or not is_instance_valid(popover): return
	panel.reset_size()
	var area := popover.get_global_rect()
	var at := anchor.get_global_rect()
	var pos := Vector2(at.position.x, at.end.y + 6)
	# Rail keys open to the right of the rail.
	if at.end.x < area.position.x + 90: pos = Vector2(at.end.x + 10, at.position.y)
	if pos.y + panel.size.y > area.end.y - 8: pos.y = area.end.y - 8 - panel.size.y
	pos.x = clampf(pos.x, area.position.x + 8, area.end.x - 8 - panel.size.x)
	panel.position = pos - area.position
	var tween := panel.create_tween().set_parallel()
	tween.tween_property(panel, "modulate:a", 1.0, 0.1)
	tween.tween_property(panel, "position:y", panel.position.y, 0.12).from(panel.position.y - 6).set_ease(Tween.EASE_OUT)

func _close_popover() -> void:
	if is_instance_valid(popover): popover.queue_free()
	popover = null
	preset_tiles.clear()

# ------------------------------------------------------------------ rail, canvas edge and dock

func _build_rail() -> Control:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _panel_box(10, Vector4(5, 8, 5, 8)))
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 4)
	panel.add_child(column)
	for spec in TOOL_SPECS:
		var kind: String = spec[0]
		var b := Widgets.icon_button(column, spec[3], "", func(): _select_tool(kind), 42)
		b.toggle_mode = true
		b.add_theme_constant_override("icon_max_width", 22)
		RpgUi.name_tip(b, tr(spec[1]), spec[2])
		tool_buttons[kind] = b
	column.add_child(_rule(false))
	_build_well(column)
	column.add_child(_rule(false))
	symmetry_button = Widgets.icon_button(column, "symmetry", "", _open_symmetry, 42)
	RpgUi.name_tip(symmetry_button, tr("거울 대칭으로 양쪽을 함께 칠하기"))
	symmetry_badge = Label.new()
	symmetry_badge.add_theme_font_size_override("font_size", 10)
	symmetry_badge.add_theme_color_override("font_color", Widgets.GOLD)
	symmetry_badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	symmetry_badge.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	symmetry_badge.offset_left = -12; symmetry_badge.offset_top = -15; symmetry_badge.offset_right = -3; symmetry_badge.offset_bottom = -1
	symmetry_button.add_child(symmetry_badge)
	var home := Widgets.icon_button(column, "view_reset", "", func(): view.reset_view(), 42)
	RpgUi.name_tip(home, tr("시점 초기화"), "F")
	return panel

## Front / back colour chips: the front one opens the colour section, the back one swaps;
## small keys swap (X) and reset to black and white (D).
func _build_well(parent: Node) -> void:
	var well := Control.new()
	well.custom_minimum_size = Vector2(42, 48)
	parent.add_child(well)
	secondary_chip = _color_chip(well, Vector2(15, 17), secondary)
	primary_chip = _color_chip(well, Vector2(3, 5), primary)
	primary_chip.pressed.connect(_open_colors)
	secondary_chip.pressed.connect(_swap_colors)
	RpgUi.name_tip(primary_chip, tr("앞색"))
	RpgUi.name_tip(secondary_chip, tr("뒷색 · 클릭하면 바꾸기"), "X")
	var swap := Widgets.icon_button(well, "swap", tr("앞색과 뒷색 바꾸기  ·  X"), _swap_colors, 15)
	swap.add_theme_constant_override("icon_max_width", 12)
	swap.position = Vector2(28, 0)
	var reset := Widgets.icon_button(well, "reset_colors", tr("기본 색 (검정 · 흰색)") + "  ·  D", _reset_colors, 15)
	reset.add_theme_constant_override("icon_max_width", 11)
	reset.position = Vector2(0, 33)

func _color_chip(parent: Control, at: Vector2, value: Color) -> Button:
	var chip := Button.new()
	chip.focus_mode = Control.FOCUS_NONE
	chip.position = at
	chip.size = Vector2(24, 24)
	parent.add_child(chip)
	_paint_chip(chip, value)
	return chip

func _paint_chip(chip: Button, value: Color) -> void:
	for state in ["normal", "hover", "pressed", "hover_pressed", "focus"]:
		var box := StyleBoxFlat.new()
		box.bg_color = value
		box.set_border_width_all(2)
		box.border_color = Color("ffe08a") if state != "normal" else Color(0.95, 0.9, 0.78)
		box.set_corner_radius_all(5)
		box.shadow_color = Color(0, 0, 0, 0.5)
		box.shadow_size = 3
		chip.add_theme_stylebox_override(state, box)

## Procreate-style size and opacity on the canvas edge, and the hint line at its foot.
func _build_canvas_overlay() -> void:
	var edge := VBoxContainer.new()
	edge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	edge.add_theme_constant_override("separation", 16)
	edge.set_anchors_and_offsets_preset(Control.PRESET_CENTER_LEFT)
	edge.offset_left = 10; edge.offset_right = 38; edge.offset_top = -158; edge.offset_bottom = 158
	stage.add_child(edge)
	size_edge = Widgets.EdgeSlider.new()
	size_edge.min_value = 1.0; size_edge.max_value = 400.0; size_edge.step = 1.0; size_edge.shape = 2.4
	size_edge.title = tr("크기")
	size_edge.format = func(v: float) -> String: return "%d px" % int(round(v))
	size_edge.tooltip_text = tr("크기") + "  ·  [ ]"
	size_edge.value_changed.connect(func(v: float):
		_set_option(tool, "size", v, size_edge)
		view.flash_ring())
	size_edge.dragging_changed.connect(func(active: bool): view.hold_ring(active))
	edge.add_child(size_edge)
	opacity_edge = Widgets.EdgeSlider.new()
	opacity_edge.min_value = 0.01; opacity_edge.max_value = 1.0; opacity_edge.step = 0.01
	opacity_edge.title = tr("불투명도")
	opacity_edge.format = func(v: float) -> String: return "%d%%" % int(round(v * 100.0))
	opacity_edge.tooltip_text = tr("불투명도") + "  ·  1…0"
	opacity_edge.value_changed.connect(func(v: float): _set_option(tool, "opacity", v, opacity_edge))
	edge.add_child(opacity_edge)
	var foot := PanelContainer.new()
	foot.add_theme_stylebox_override("panel", Widgets.flat(Color(0.03, 0.04, 0.045, 0.62), 7, Color(0, 0, 0, 0), 0, 5))
	foot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	foot.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	foot.offset_left = 10; foot.offset_right = -10; foot.offset_top = -32; foot.offset_bottom = -8
	stage.add_child(foot)
	status_label = Widgets.caption(foot, "", 12, Color(1, 1, 1, 0.72))
	status_label.clip_text = true

func _sync_edges() -> void:
	if size_edge == null: return
	var s: Dictionary = settings.get(tool, {})
	size_edge.visible = s.has("size")
	opacity_edge.visible = s.has("opacity")
	if s.has("size"): size_edge.set_value_no_signal(float(s.size))
	if s.has("opacity"): opacity_edge.set_value_no_signal(float(s.opacity))

## The right dock: Colour, Layers and History, each folding on its header (remembered).
func _build_dock() -> Control:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _panel_box(10, Vector4(8, 6, 4, 6)))
	panel.custom_minimum_size.x = DOCK_WIDTH
	dock_scroll = ScrollContainer.new()
	dock_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	panel.add_child(dock_scroll)
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.add_theme_constant_override("separation", 6)
	dock_scroll.add_child(column)
	var colors := Widgets.Section.new(tr("색"), "palette", bool(_setting("dock_color", true)))
	column.add_child(colors)
	sections.color = colors
	picker = ColorPanel.new()
	picker.swatches = PackedStringArray(_setting("swatches", "").split(",", false))
	picker.recent = PackedStringArray(_setting("recent", "").split(",", false))
	colors.body.add_child(picker)
	picker.set_color(primary, false)
	picker.color_changed.connect(func(value: Color):
		primary = value
		_refresh_colors())
	column.add_child(_rule(false))
	var layers := Widgets.Section.new(tr("레이어"), "layers", bool(_setting("dock_layers", true)))
	column.add_child(layers)
	sections.layers = layers
	layer_list = VBoxContainer.new()
	layer_list.add_theme_constant_override("separation", 3)
	layers.body.add_child(layer_list)
	var props := HBoxContainer.new()
	props.add_theme_constant_override("separation", 8)
	layers.body.add_child(props)
	var opacity_box := VBoxContainer.new()
	opacity_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	opacity_box.add_theme_constant_override("separation", 1)
	props.add_child(opacity_box)
	layer_opacity_label = Widgets.caption(opacity_box, "", 11)
	layer_opacity = HSlider.new()
	layer_opacity.min_value = 0; layer_opacity.max_value = 100; layer_opacity.step = 1
	layer_opacity.focus_mode = Control.FOCUS_NONE
	layer_opacity.custom_minimum_size.y = 16
	layer_opacity.value_changed.connect(func(value: float):
		layer_opacity_label.text = tr("레이어 불투명도  %d%%") % int(value)
		if refreshing_layers or core == null: return
		core.set_layer_props(core.current, {"opacity": value / 100.0}, tr("레이어 불투명도"))
		_after_change(false))
	opacity_box.add_child(layer_opacity)
	layer_mode = OptionButton.new()
	for name in MODE_NAMES: layer_mode.add_item(tr(name))
	layer_mode.focus_mode = Control.FOCUS_NONE
	layer_mode.custom_minimum_size = Vector2(92, 30)
	layer_mode.tooltip_text = tr("레이어 혼합 모드")
	layer_mode.item_selected.connect(func(index: int):
		if refreshing_layers or core == null: return
		core.set_layer_props(core.current, {"mode": index}, tr("혼합 모드"))
		_after_change(false))
	props.add_child(layer_mode)
	var layer_actions := HBoxContainer.new()
	layer_actions.add_theme_constant_override("separation", 2)
	layers.body.add_child(layer_actions)
	for spec in [["plus", _add_layer, tr("새 레이어  ·  Ctrl+Shift+N")], ["duplicate", _duplicate_layer, tr("레이어 복제")],
			["arrow_up", func(): _move_layer(1), tr("위로")], ["arrow_down", func(): _move_layer(-1), tr("아래로")],
			["rename", _start_rename, tr("이름 바꾸기")], ["delete", _delete_layer, tr("레이어 삭제")]]:
		var b := Widgets.icon_button(layer_actions, spec[0], spec[2], spec[1], 34)
		b.add_theme_constant_override("icon_max_width", 18)
	rename_row = HBoxContainer.new()
	rename_row.visible = false
	rename_row.add_theme_constant_override("separation", 4)
	layers.body.add_child(rename_row)
	rename_field = LineEdit.new()
	rename_field.max_length = 24
	rename_field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rename_field.custom_minimum_size.y = 30
	rename_field.text_submitted.connect(func(_text: String): _finish_rename())
	# Esc cancels the rename (and never reaches the workspace's Esc = close).
	rename_field.gui_input.connect(_rename_key)
	rename_row.add_child(rename_field)
	_button(rename_row, tr("확인"), _finish_rename).custom_minimum_size = Vector2(52, 30)
	column.add_child(_rule(false))
	var history := Widgets.Section.new(tr("작업 기록"), "history", bool(_setting("dock_history", true)))
	column.add_child(history)
	sections.history = history
	history_list = ItemList.new()
	history_list.custom_minimum_size.y = 128
	history_list.focus_mode = Control.FOCUS_NONE
	history_list.item_clicked.connect(func(index: int, _at: Vector2, button: int):
		if button == MOUSE_BUTTON_LEFT and not busy and core != null and not core.stroke_active():
			core.jump(index)
			_after_change(true))
	history.body.add_child(history_list)
	return panel

## The colour well's front chip: open (and point at) the colour section.
func _open_colors() -> void:
	var section = sections.get("color")
	if section == null: return
	section.set_open(true)
	dock_scroll.scroll_vertical = 0
	picker.set_color(primary, false)
	var header: Control = section.header
	header.modulate = Color(1.7, 1.5, 0.9)
	header.create_tween().tween_property(header, "modulate", Color.WHITE, 0.4)

func _open_symmetry() -> void:
	if core == null: return
	var column := _popover(symmetry_button)
	Widgets.caption(column, tr("거울 대칭으로 양쪽을 함께 칠하기"), 12, Widgets.GOLD)
	var names := [tr("대칭 끔"), tr("대칭 X"), tr("대칭 Z")]
	for i in 3:
		var b := Button.new()
		b.theme_type_variation = "PaintSegment"
		b.toggle_mode = true
		b.button_pressed = core.symmetry == i
		b.text = names[i]
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.focus_mode = Control.FOCUS_NONE
		b.custom_minimum_size = Vector2(160, 32)
		var index: int = i
		b.pressed.connect(func():
			_set_symmetry(index)
			_close_popover())
		column.add_child(b)

func _set_symmetry(index: int) -> void:
	if core == null: return
	core.symmetry = index
	symmetry_badge.text = ["", "X", "Z"][index]
	var lit := Widgets.GOLD if index != 0 else Color(Widgets.INK, 0.92)
	symmetry_button.add_theme_color_override("icon_normal_color", lit)
	symmetry_button.tooltip_text = tr("거울 대칭으로 양쪽을 함께 칠하기") + "  ·  " + [tr("대칭 끔"), tr("대칭 X"), tr("대칭 Z")][index]

func _refresh_colors() -> void:
	if is_instance_valid(primary_chip): _paint_chip(primary_chip, primary)
	if is_instance_valid(secondary_chip): _paint_chip(secondary_chip, secondary)
	for swatch in gradient_swatches:
		if is_instance_valid(swatch): (swatch as Control).queue_redraw()

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
	panel.add_theme_stylebox_override("panel", Widgets.flat(Widgets.PANEL, 12, Color(Widgets.GOLD, 0.35), 1, 20))
	panel.custom_minimum_size.x = 340
	center.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	panel.add_child(column)
	busy_label = RpgUi.label(column, "", 16, RpgUi.INK)
	busy_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	busy_bar = ProgressBar.new()
	busy_bar.custom_minimum_size = Vector2(280, 8)
	busy_bar.show_percentage = false
	busy_bar.add_theme_stylebox_override("background", Widgets.flat(Color(1, 1, 1, 0.1), 4))
	busy_bar.add_theme_stylebox_override("fill", Widgets.flat(Widgets.GOLD, 4))
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
	_close_popover()
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
	panel.add_theme_stylebox_override("panel", Widgets.flat(Widgets.PANEL, 12, Color(Widgets.GOLD, 0.35), 1, 20))
	panel.custom_minimum_size.x = 380
	center.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 14)
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
		callback.call(), "PaintGold")
	RpgUi.pop_in(panel)

# ------------------------------------------------------------------ tools

func _select_tool(kind: String) -> void:
	if stroke_active(): return
	tool = kind
	_close_popover()
	for name in tool_buttons: tool_buttons[name].set_pressed_no_signal(name == kind)
	for name in option_rows: option_rows[name].visible = name == kind
	if is_instance_valid(view):
		view.line_visible = false
		view.overlay.queue_redraw()
	_sync_edges()
	_update_cursor()

func _update_cursor() -> void:
	if not is_instance_valid(view): return
	if tool in [BRUSH, ERASER]:
		var s: Dictionary = settings[tool]
		view.cursor_kind = "brush"
		view.cursor_radius = float(s.size) * 0.5
		view.cursor_hardness = float(s.hardness)
		view.cursor_roundness = float(s.roundness) if int(s.tip) != 0 else 1.0
		view.cursor_angle = deg_to_rad(float(s.angle)) if int(s.tip) != 0 else 0.0
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
	if busy or stroke_active(): return
	# Idle frames: one layer thumbnail or one preset stroke at a time, never mid-stroke.
	if not thumb_queue.is_empty(): _update_thumb()
	elif warm_previews < PRESETS.size() * 2:
		# Up to ~12 ms each: the popover then opens without a hitch.
		var spec := _preview_spec(PRESETS[warm_previews / 2])
		if warm_previews % 2 == 0: Widgets.stroke_preview(spec, 144, 34)
		else: Widgets.stroke_preview(spec, 112, 22)
		warm_previews += 1

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

## Places every queued dab before the view's camera moves (queued points are screen points).
func _flush_stroke() -> void:
	if stroke_active() and not stroke.is_empty(): _drain_stroke(-1)

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
	var s: Dictionary = settings[GRADIENT]
	# The line previews the colours and the shape it will paint.
	view.line_colors = [primary, Color(primary, 0.0) if bool(s.to_clear) else secondary]
	view.line_radial = bool(s.radial)
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
	_refresh_colors()

func _reset_colors() -> void:
	primary = Color.BLACK
	secondary = Color.WHITE
	picker.set_color(primary, false)
	_refresh_colors()

# ------------------------------------------------------------------ layers and history

func _after_change(structure: bool) -> void:
	if core == null: return
	view.sync(core)
	_refresh_layers()
	_refresh_history()
	if structure: dirty = true

## Layer rows, top layer first: visibility, thumbnail, name with mode and opacity.
func _refresh_layers() -> void:
	if core == null or not is_instance_valid(layer_list): return
	refreshing_layers = true
	for child in layer_list.get_children(): child.queue_free()
	thumb_views.clear()
	for layer in thumbs.keys():
		if not core.layers.has(layer): thumbs.erase(layer)
	for index in range(core.layers.size() - 1, -1, -1):
		var layer = core.layers[index]
		var at: int = index
		var row := Button.new()
		row.theme_type_variation = "PaintRow"
		row.toggle_mode = true
		row.button_pressed = index == core.current
		row.focus_mode = Control.FOCUS_NONE
		row.custom_minimum_size.y = 44
		row.pressed.connect(func():
			if stroke_active(): return
			core.current = at
			_refresh_layers())
		row.gui_input.connect(func(event: InputEvent):
			if event is InputEventMouseButton and event.double_click and event.button_index == MOUSE_BUTTON_LEFT:
				core.current = at
				_start_rename())
		layer_list.add_child(row)
		var line := HBoxContainer.new()
		line.mouse_filter = Control.MOUSE_FILTER_IGNORE
		line.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		line.offset_left = 2; line.offset_right = -6; line.offset_top = 4; line.offset_bottom = -4
		line.add_theme_constant_override("separation", 6)
		row.add_child(line)
		var eye := Widgets.icon_button(line, "eye" if layer.visible else "eye_off", tr("보이기 / 숨기기"), func():
			core.set_layer_props(at, {"visible": not core.layers[at].visible}, tr("레이어 보이기"))
			_after_change(false), 30)
		eye.add_theme_constant_override("icon_max_width", 16)
		if not layer.visible: eye.modulate.a = 0.6
		var thumb := Widgets.Thumb.new()
		thumb.texture = _thumb_texture(layer)
		line.add_child(thumb)
		thumb_views[layer] = thumb
		var names := VBoxContainer.new()
		names.mouse_filter = Control.MOUSE_FILTER_IGNORE
		names.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		names.alignment = BoxContainer.ALIGNMENT_CENTER
		names.add_theme_constant_override("separation", -1)
		line.add_child(names)
		var title := Widgets.caption(names, str(layer.name), 13, Widgets.INK)
		title.clip_text = true
		var mode_text: String = tr(MODE_NAMES[layer.mode])
		Widgets.caption(names, "%s  ·  %d%%" % [mode_text, int(round(layer.opacity * 100))], 11)
		row.tooltip_text = str(layer.name)
	var current = core.layers[core.current]
	layer_opacity.value = round(current.opacity * 100.0)
	layer_opacity_label.text = tr("레이어 불투명도  %d%%") % int(layer_opacity.value)
	layer_mode.select(current.mode)
	refreshing_layers = false

## The layer's thumbnail; a stale one is redrawn on an idle frame.
func _thumb_texture(layer) -> Texture2D:
	var entry: Dictionary = thumbs.get(layer, {})
	if (entry.is_empty() or int(entry.revision) != layer.revision) and not thumb_queue.has(layer): thumb_queue.append(layer)
	return entry.get("texture")

func _update_thumb() -> void:
	while not thumb_queue.is_empty() and not core.layers.has(thumb_queue[0]): thumb_queue.pop_front()
	if thumb_queue.is_empty(): return
	var layer = thumb_queue.pop_front()
	var image := Image.create_from_data(core.size, core.size, false, Image.FORMAT_RGBA8, layer.data)
	image.resize(48, 48, Image.INTERPOLATE_TRILINEAR)
	var entry: Dictionary = thumbs.get(layer, {})
	if entry.has("texture"): (entry.texture as ImageTexture).update(image)
	else: entry.texture = ImageTexture.create_from_image(image)
	entry.revision = layer.revision
	thumbs[layer] = entry
	var thumb = thumb_views.get(layer)
	if is_instance_valid(thumb):
		thumb.texture = entry.texture
		thumb.queue_redraw()

func _refresh_history() -> void:
	if core == null or not is_instance_valid(history_list): return
	history_list.clear()
	history_list.add_item(tr("처음 상태"))
	for name in core.history_names(): history_list.add_item(tr(name))
	for i in history_list.item_count:
		if i > core.history_index: history_list.set_item_custom_fg_color(i, Color(1, 1, 1, 0.3))
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
	sections.layers.set_open(true)
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
	if key.keycode == KEY_ESCAPE and is_instance_valid(popover):
		_close_popover()
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
				view.flash_ring()
		KEY_0, KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9:
			# Photoshop: number keys set the tool opacity (1 = 10% ... 0 = 100%).
			if tool in [BRUSH, ERASER, FILL, GRADIENT]:
				var digit := key.keycode - KEY_0
				_set_option(tool, "opacity", 1.0 if digit == 0 else digit / 10.0)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey or event is InputEventMouseButton or event is InputEventJoypadButton:
		get_viewport().set_input_as_handled()

## Sets one tool setting and brings every control showing it (and the cursor) in step.
func _set_option(tool_name: String, key: String, value, source: Object = null) -> void:
	if not settings.has(tool_name) or not settings[tool_name].has(key): return
	var old = settings[tool_name][key]
	if old is bool: value = bool(value)
	elif old is int: value = int(value)
	else: value = float(value)
	settings[tool_name][key] = value
	var id := tool_name + ":" + key
	var live: Array = []
	for entry in option_controls.get(id, []):
		if not is_instance_valid(entry.control): continue
		live.append(entry)
		if entry.control != source: entry.refresh.call(value)
	option_controls[id] = live
	if tool_name == tool and key in ["size", "opacity"] and source != size_edge and source != opacity_edge: _sync_edges()
	if tool_name in [BRUSH, ERASER] and key in PRESET_KEYS: _refresh_preset(tool_name)
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
	panel.add_theme_stylebox_override("panel", Widgets.flat(Widgets.PANEL, 12, Color(Widgets.GOLD, 0.35), 1, 20))
	panel.custom_minimum_size.x = 460
	center.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	panel.add_child(column)
	RpgUi.label(column, tr("전체 색 바꾸기"), 22, RpgUi.GOLD)
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
		part_choice.custom_minimum_size.y = 32
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
		_close(true), "PaintGold")
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
	for name in sections:
		if is_instance_valid(sections[name]): config.set_value(SETTINGS_SECTION, "dock_" + name, bool(sections[name].open))
	config.save(_settings_path())
