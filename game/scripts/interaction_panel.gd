extends Control
## The interaction editor (상호작용) for a crafted object its owner keeps: opened from the village
## bag and every room's 보관함 tab.
##
##   var panel := InteractionPanel.new()
##   panel.setup(api, obj, model, {"saved": func(reply: Dictionary), "closed": func()})
##   host_control.add_child(panel)
##
## Ready-made behaviours cost nothing: pick cards (spin, sway, bounce, light, glow, colour, slow
## turn, open/close a part), each with when (click/E, near, leave, always), how strong and, for a
## part, which one. "글로 설명하기" lets the server's designer write it from a sentence (starseeds,
## a daily limit). 앉기/눕기 makes it a seat or a bed in rooms. Every change plays on the object
## right here (미리보기); 저장 keeps it on the server (server/interactions.py) and every copy -
## rooms, the village, visitors - runs it from then on; 원래대로 goes back to the crafted motion.
## The host's preview model is borrowed into the editor's stage and handed back on close.
signal finished(saved: bool)

const RpgUi = preload("res://scripts/rpg_ui.gd")
const Assembly = preload("res://scripts/asset_assembly.gd")
## id, card name. Shown translated.
const KINDS := [["spin", "빙글 돌기"], ["sway", "흔들흔들"], ["bounce", "통통 튀기"], ["glow", "불 켜기·끄기"],
	["pulse", "은은하게 빛나기"], ["hue", "색 바꾸기"], ["turn", "천천히 계속 돌기"], ["hinge", "부품 열기·닫기"]]
const TRIGGERS := [["click", "클릭·E"], ["near", "다가가면"], ["leave", "멀어지면"], ["always", "항상"]]
const LEVELS := ["약하게", "보통", "세게"]
const DEFAULT_TRIGGER := {"pulse": "always", "turn": "always"}
const PART_NAMES := {"body": "본체", "lid": "뚜껑", "base": "받침", "stem": "줄기", "hour_hand": "시침", "minute_hand": "분침",
	"second_hand": "초침", "face": "앞면", "bulb": "전구", "door": "문", "center": "가운데"}
const MAX_PRESETS := 6

var api: Node
var obj: Dictionary = {}
var model: Node3D
var options: Dictionary = {}
var info: Dictionary = {}
var choice := {"mode": "presets", "presets": [], "keep": true, "rest": ""}
var focus := -1
var busy := false
var saved_once := false
var own_model := false
var home: Node
var home_transform := Transform3D.IDENTITY
var saved_program: Dictionary = {}
var saved_state: Dictionary = {}
var draft: Dictionary = {}
var preview_serial := 0

var window: PanelContainer
var stage: Node3D
var turntable: Node3D
var stage_camera: Camera3D
var title_label: Label
var status_label: Label
var cards := {}
var card_badges := {}
var options_box: VBoxContainer
var presets_page: VBoxContainer
var custom_page: VBoxContainer
var mode_buttons := {}
var rest_buttons := {}
var keep_box: CheckBox
var describe_text: TextEdit
var describe_button: Button
var describe_note: Label
var describe_result: HFlowContainer
var save_button: Button
var preview_button: Button
var reset_button: Button
var chips: HFlowContainer
var preview_timer: Timer
var dragging := false

func setup(network: Node, object: Dictionary, borrowed: Node3D, extra := {}) -> void:
	api = network
	obj = object
	model = borrowed
	options = extra
	name = "InteractionPanel"
	theme = RpgUi.theme()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_build()

func _ready() -> void:
	_open.call_deferred()

# ---------------------------------------------------------------- layout

func _build() -> void:
	var dim := ColorRect.new()
	dim.color = Color(0.03, 0.04, 0.05, 0.55)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	window = PanelContainer.new()
	window.add_theme_stylebox_override("panel", RpgUi.panel_style("paper"))
	window.custom_minimum_size = Vector2(1040, 660)
	center.add_child(window)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	window.add_child(column)
	# Header: ribbon title, the object's name, close.
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 12)
	column.add_child(head)
	RpgUi.ribbon(head, tr("상호작용"), true, 22)
	title_label = RpgUi.heading(head, str(obj.get("name", "")), 20)
	title_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	title_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	var close := Button.new()
	close.icon = RpgUi.icon_texture("close")
	close.expand_icon = true
	close.custom_minimum_size = Vector2(40, 40)
	close.focus_mode = Control.FOCUS_NONE
	RpgUi.name_tip(close, tr("닫기"), "Esc")
	close.pressed.connect(func(): close_panel())
	head.add_child(close)
	var body := HBoxContainer.new()
	body.add_theme_constant_override("separation", 16)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(body)
	_build_stage(body)
	var right := VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.add_theme_constant_override("separation", 8)
	body.add_child(right)
	var modes := HBoxContainer.new()
	modes.add_theme_constant_override("separation", 6)
	right.add_child(modes)
	for spec in [["presets", tr("기본 동작")], ["custom", tr("글로 설명하기")]]:
		var b := _toggle(modes, spec[1], func(): _set_mode(spec[0]))
		b.custom_minimum_size.x = 150
		mode_buttons[spec[0]] = b
	var hint := RpgUi.caption(modes, tr("무료"), 12)
	hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	hint.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	hint.set_meta("free_hint", true)
	presets_page = VBoxContainer.new()
	presets_page.add_theme_constant_override("separation", 8)
	presets_page.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_child(presets_page)
	_build_presets(presets_page)
	custom_page = VBoxContainer.new()
	custom_page.add_theme_constant_override("separation", 8)
	custom_page.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_child(custom_page)
	_build_custom(custom_page)
	RpgUi.divider(right)
	var rest_row := HBoxContainer.new()
	rest_row.add_theme_constant_override("separation", 6)
	right.add_child(rest_row)
	_row_title(rest_row, tr("쉬기"))
	for spec in [["", tr("없음")], ["sit", tr("앉을 수 있음")], ["lie", tr("누울 수 있음")]]:
		rest_buttons[spec[0]] = _toggle(rest_row, spec[1], func(): _set_rest(spec[0]))
	# Footer: back to the crafted motion | what happened | preview, save.
	var foot := HBoxContainer.new()
	foot.add_theme_constant_override("separation", 10)
	column.add_child(foot)
	reset_button = _button(foot, tr("원래대로"), func(): _reset_choice())
	RpgUi.name_tip(reset_button, tr("만들 때의 움직임으로 (저장하면 적용)"))
	status_label = RpgUi.caption(foot, "", 14, RpgUi.PAPER_INK)
	status_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	status_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	status_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	preview_button = _button(foot, tr("미리보기"), func(): _preview(true))
	preview_button.custom_minimum_size.x = 130
	save_button = _button(foot, tr("저장"), func(): _save())
	save_button.theme_type_variation = "PrimaryButton"
	save_button.custom_minimum_size.x = 150
	preview_timer = Timer.new()
	preview_timer.one_shot = true
	preview_timer.wait_time = 0.3
	preview_timer.timeout.connect(func(): _preview(false))
	add_child(preview_timer)
	_set_enabled(false)
	RpgUi.pop_in(window)

func _build_stage(parent: Control) -> void:
	var left := VBoxContainer.new()
	left.custom_minimum_size.x = 340
	left.add_theme_constant_override("separation", 8)
	parent.add_child(left)
	var frame := PanelContainer.new()
	frame.add_theme_stylebox_override("panel", RpgUi.panel_style("night", 6))
	left.add_child(frame)
	var view := SubViewportContainer.new()
	view.stretch = true
	view.custom_minimum_size = Vector2(328, 300)
	frame.add_child(view)
	view.gui_input.connect(_stage_input)
	var port := SubViewport.new()
	port.size = Vector2i(328, 300)
	port.own_world_3d = true
	port.msaa_3d = Viewport.MSAA_4X
	port.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	view.add_child(port)
	stage = Node3D.new()
	port.add_child(stage)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("2c3a3b")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = 0.45
	environment.environment.glow_enabled = true
	stage.add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-42, -32, 0)
	sun.light_energy = 0.9
	stage.add_child(sun)
	var floor_disc := MeshInstance3D.new()
	var disc := CylinderMesh.new()
	disc.top_radius = 1.4
	disc.bottom_radius = 1.45
	disc.height = 0.06
	floor_disc.mesh = disc
	var floor_material := StandardMaterial3D.new()
	floor_material.albedo_color = Color("6f7f69")
	floor_material.roughness = 0.95
	floor_disc.material_override = floor_material
	floor_disc.position.y = -0.03
	stage.add_child(floor_disc)
	turntable = Node3D.new()
	stage.add_child(turntable)
	stage_camera = Camera3D.new()
	stage_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	stage_camera.size = 2.6
	stage.add_child(stage_camera)
	_frame_camera(Vector3.ONE)
	# Try the triggers on the object here; nothing is saved.
	var tests := HBoxContainer.new()
	tests.add_theme_constant_override("separation", 6)
	left.add_child(tests)
	_row_title(tests, tr("시험"))
	for spec in [["click", tr("클릭")], ["near", tr("다가가기")], ["leave", tr("멀어지기")]]:
		var b := _button(tests, spec[1], func(): _try(spec[0]))
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	chips = HFlowContainer.new()
	chips.add_theme_constant_override("h_separation", 6)
	chips.add_theme_constant_override("v_separation", 6)
	left.add_child(chips)

func _build_presets(page: VBoxContainer) -> void:
	var grid := GridContainer.new()
	grid.columns = 4
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 8)
	page.add_child(grid)
	for spec in KINDS:
		var kind: String = spec[0]
		var card := Button.new()
		card.theme_type_variation = "SlotButton"
		card.custom_minimum_size = Vector2(150, 64)
		card.focus_mode = Control.FOCUS_NONE
		card.toggle_mode = true
		card.name = "Card_" + kind
		RpgUi.name_tip(card, tr(spec[1]))
		var inside := VBoxContainer.new()
		inside.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		inside.alignment = BoxContainer.ALIGNMENT_CENTER
		inside.add_theme_constant_override("separation", 0)
		inside.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(inside)
		var glyph := Control.new()
		glyph.custom_minimum_size = Vector2(36, 36)
		glyph.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		glyph.mouse_filter = Control.MOUSE_FILTER_IGNORE
		glyph.draw.connect(func(): _draw_glyph(glyph, kind))
		inside.add_child(glyph)
		var caption := RpgUi.caption(inside, tr(spec[1]), 13, RpgUi.PAPER_INK)
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.autowrap_mode = TextServer.AUTOWRAP_OFF
		caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
		# A gold check in the corner while the behaviour is in use.
		var badge := Control.new()
		badge.custom_minimum_size = Vector2(18, 18)
		badge.size = Vector2(18, 18)
		badge.position = Vector2(126, 5)
		badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
		badge.draw.connect(func():
			badge.draw_circle(Vector2(9, 9), 9, Color("c9822c"))
			badge.draw_polyline(PackedVector2Array([Vector2(4.5, 9.5), Vector2(8, 13), Vector2(13.5, 5.5)]), Color.WHITE, 2.2, true))
		badge.visible = false
		card.add_child(badge)
		card_badges[kind] = badge
		card.pressed.connect(func(): _pick_card(kind))
		RpgUi.hover_motion(card, 1.04)
		grid.add_child(card)
		cards[kind] = card
	keep_box = CheckBox.new()
	keep_box.text = tr("만들 때의 움직임도 함께")
	keep_box.button_pressed = true
	keep_box.toggled.connect(func(on: bool): choice.keep = on; _changed())
	page.add_child(keep_box)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	page.add_child(scroll)
	options_box = VBoxContainer.new()
	options_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	options_box.add_theme_constant_override("separation", 6)
	scroll.add_child(options_box)

func _build_custom(page: VBoxContainer) -> void:
	RpgUi.heading(page, tr("어떻게 움직였으면 좋겠나요?"), 18)
	describe_text = TextEdit.new()
	describe_text.custom_minimum_size.y = 92
	describe_text.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	describe_text.placeholder_text = tr("예) 다가가면 뚜껑이 천천히 열리고 은은하게 빛나요")
	describe_text.text_changed.connect(func():
		if describe_text.text.length() > _text_limit():
			describe_text.text = describe_text.text.substr(0, _text_limit())
			describe_text.set_caret_column(describe_text.text.length())
		_update_describe())
	page.add_child(describe_text)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	page.add_child(row)
	row.add_child(RpgUi.icon("res://assets/ui/starseed.svg", 24))
	describe_note = RpgUi.caption(row, "", 13, RpgUi.PAPER_INK)
	describe_note.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	describe_note.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	describe_button = _button(row, tr("만들어 보기"), func(): _describe())
	describe_button.theme_type_variation = "GoldButton"
	describe_button.custom_minimum_size.x = 140
	describe_result = HFlowContainer.new()
	describe_result.add_theme_constant_override("h_separation", 6)
	page.add_child(describe_result)
	RpgUi.caption(page, tr("지금 모양의 부품만 움직여요. 모양은 바뀌지 않아요."), 12)

# ---------------------------------------------------------------- small widgets

func _button(parent: Node, text: String, callback: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(callback)
	parent.add_child(b)
	return b

func _toggle(parent: Node, text: String, callback: Callable) -> Button:
	var b := _button(parent, text, callback)
	b.theme_type_variation = "ChoiceButton"
	b.toggle_mode = true
	b.custom_minimum_size.y = 34
	b.add_theme_font_size_override("font_size", 14)
	return b

func _row_title(parent: Node, text: String) -> Label:
	var l := RpgUi.caption(parent, text, 13)
	l.custom_minimum_size.x = 44
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	return l

func _chip(parent: Node, text: String, gold := false) -> void:
	var pill := PanelContainer.new()
	pill.add_theme_stylebox_override("panel", RpgUi.panel_style("pill_paper" if not gold else "pill"))
	pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var l := RpgUi.caption(pill, text, 12, RpgUi.INK if gold else RpgUi.PAPER_INK)
	l.autowrap_mode = TextServer.AUTOWRAP_OFF
	parent.add_child(pill)

## A small drawn icon per behaviour (no art files; scales with the UI).
func _draw_glyph(c: Control, kind: String) -> void:
	var s := c.size
	var mid := s * 0.5
	var r := minf(s.x, s.y) * 0.36
	var ink := RpgUi.PAPER_INK
	var gold := Color("c9822c")
	match kind:
		"spin", "turn":
			c.draw_arc(mid, r, -PI * 0.2, PI * 1.45, 24, ink, 2.6, true)
			var tip := mid + Vector2(cos(PI * 1.45), sin(PI * 1.45)) * r
			c.draw_colored_polygon(PackedVector2Array([tip + Vector2(-6, -1), tip + Vector2(5, -4), tip + Vector2(1, 7)]), gold)
			if kind == "turn": c.draw_arc(mid, r * 0.45, 0, TAU, 16, Color(ink, 0.5), 1.6, true)
		"sway":
			var top := Vector2(mid.x, s.y * 0.12)
			for a in [-0.45, 0.45]:
				var end := top + Vector2(sin(a), cos(a)) * r * 1.9
				c.draw_line(top, end, Color(ink, 0.3), 1.6, true)
			c.draw_line(top, top + Vector2(0, r * 1.9), ink, 2.4, true)
			c.draw_circle(top + Vector2(0, r * 1.9), 5, gold)
		"bounce":
			c.draw_line(Vector2(4, s.y - 4), Vector2(s.x - 4, s.y - 4), ink, 2.0, true)
			c.draw_arc(Vector2(mid.x, s.y - 4), r, PI, TAU, 16, Color(ink, 0.45), 1.6, true)
			c.draw_circle(Vector2(mid.x, s.y - 4 - r), 5.5, gold)
		"glow":
			c.draw_circle(mid, r * 0.55, Color("f2c14e"))
			for i in 8:
				var a := TAU * i / 8.0
				c.draw_line(mid + Vector2(cos(a), sin(a)) * r * 0.75, mid + Vector2(cos(a), sin(a)) * r * 1.15, ink, 2.2, true)
		"pulse":
			for i in 3:
				c.draw_arc(mid, r * (0.4 + i * 0.3), 0, TAU, 24, Color(gold, 1.0 - i * 0.3), 2.0, true)
			c.draw_circle(mid, r * 0.22, Color("f2c14e"))
		"hue":
			for i in 6:
				var a := TAU * i / 6.0
				c.draw_circle(mid + Vector2(cos(a), sin(a)) * r * 0.75, r * 0.3, Color.from_hsv(i / 6.0, 0.55, 0.9))
		"hinge":
			var box := Rect2(mid.x - r, mid.y - r * 0.1, r * 2, r * 1.1)
			c.draw_rect(box, ink, false, 2.2)
			var hinge := Vector2(box.position.x, box.position.y)
			c.draw_line(hinge, hinge + Vector2(cos(-0.75), sin(-0.75)) * r * 2.0, gold, 3.0, true)

# ---------------------------------------------------------------- opening and closing

func _open() -> void:
	if not is_instance_valid(model) or not model.has_method("start_program"):
		_say(tr("물건을 불러오는 중이에요."))
		model = await Assembly.fetch(api, str(obj.id))
		own_model = model != null
	if is_instance_valid(model):
		home = model.get_parent()
		home_transform = model.transform
		if home: home.remove_child(model)
		turntable.add_child(model)
		model.transform = Transform3D.IDENTITY
		saved_program = Assembly.program_of(model.manifest)
		saved_state = model.vm.state.duplicate(true)
		_frame_camera(model.get_meta("size", Vector3.ONE))
	var reply: Dictionary = await api.request("/v1/objects/" + str(obj.id) + "/interaction")
	if not is_inside_tree(): return
	if not reply.ok:
		_say(_error(reply.error))
		return
	info = reply.data
	var spec: Dictionary = info.get("spec", {})
	choice = {"mode": "presets" if spec.get("mode", "original") == "original" else str(spec.mode),
		"presets": spec.get("presets", []).duplicate(true), "keep": bool(spec.get("keep", true)), "rest": str(spec.get("rest", ""))}
	if info.get("draft") is Dictionary:
		draft = info.draft
		describe_text.text = str(draft.get("text", ""))
	elif str(spec.get("text", "")) != "":
		describe_text.text = str(spec.text)
	focus = 0 if not choice.presets.is_empty() else -1
	keep_box.button_pressed = choice.keep
	keep_box.visible = bool(info.get("moving", false))
	_set_mode(choice.mode, false)
	_set_rest(choice.rest, false)
	_refresh()
	_set_enabled(not info.get("listed", false))
	if info.get("listed", false): _say(tr("장터에 올린 물건은 바꿀 수 없어요."))
	else: _say(tr("카드를 골라 움직임을 더해 보세요."))

func close_panel(saved := false) -> void:
	if is_queued_for_deletion(): return
	preview_timer.stop()
	preview_serial += 1
	if is_instance_valid(model):
		# Unsaved previews end here: the object runs what is saved.
		model.start_program(Assembly.program_of(model.manifest), saved_state)
		if model.get_parent() == turntable: turntable.remove_child(model)
		if own_model: model.queue_free()
		elif is_instance_valid(home):
			home.add_child(model)
			model.transform = home_transform
		else: model.queue_free()
	RpgUi.sfx("close")
	if options.get("closed") is Callable and options.closed.is_valid(): options.closed.call()
	finished.emit(saved or saved_once)
	queue_free()

func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
		var owner_focus := get_viewport().gui_get_focus_owner()
		if owner_focus is TextEdit: owner_focus.release_focus()
		else: close_panel()
		get_viewport().set_input_as_handled()

func _unhandled_key_input(event: InputEvent) -> void:
	# The world behind does not react while the editor is open.
	get_viewport().set_input_as_handled()

func _stage_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		dragging = event.pressed
	elif event is InputEventMouseMotion and dragging:
		turntable.rotation.y += event.relative.x * 0.012
	elif event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
		stage_camera.size = clampf(stage_camera.size * (0.9 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.1), 0.8, 8.0)

func _frame_camera(size: Vector3) -> void:
	var tall := maxf(size.y, maxf(size.x, size.z))
	stage_camera.size = clampf(tall * 2.3, 1.6, 8.0)
	var look := Vector3(0, size.y * 0.45, 0)
	stage_camera.look_at_from_position(look + Vector3(2.4, 1.6, 3.6).normalized() * 9.0, look)

# ---------------------------------------------------------------- choices

func _set_mode(mode: String, preview := true) -> void:
	choice.mode = mode if mode in ["presets", "custom"] else "presets"
	for key in mode_buttons: mode_buttons[key].button_pressed = key == choice.mode
	presets_page.visible = choice.mode == "presets"
	custom_page.visible = choice.mode == "custom"
	_update_describe()
	if preview: _changed()

func _set_rest(value: String, preview := true) -> void:
	choice.rest = value
	for key in rest_buttons: rest_buttons[key].button_pressed = key == value
	if preview: _changed(false)

func _pick_card(kind: String) -> void:
	cards[kind].button_pressed = _uses(kind)
	if busy: return
	for i in choice.presets.size():
		if choice.presets[i].kind == kind:
			focus = i
			_refresh()
			return
	if choice.presets.size() >= MAX_PRESETS:
		_say(tr("움직임은 %d개까지 함께 쓸 수 있어요.") % MAX_PRESETS)
		return
	var target := "whole"
	if kind == "hinge":
		var movable := _movable_parts()
		if movable.is_empty():
			_say(tr("여러 부품으로 만든 물건만 열고 닫을 수 있어요."))
			return
		target = movable[0]
	choice.presets.append({"kind": kind, "trigger": DEFAULT_TRIGGER.get(kind, "click"), "target": target, "level": 2,
		"direction": 1, "axis": "x", "angle": -90})
	focus = choice.presets.size() - 1
	RpgUi.sfx("confirm")
	_refresh()
	_changed()

func _remove(index: int) -> void:
	if index < 0 or index >= choice.presets.size(): return
	choice.presets.remove_at(index)
	focus = mini(index, choice.presets.size() - 1)
	_refresh()
	_changed()

func _duplicate(index: int) -> void:
	if choice.presets.size() >= MAX_PRESETS:
		_say(tr("움직임은 %d개까지 함께 쓸 수 있어요.") % MAX_PRESETS)
		return
	var copy: Dictionary = choice.presets[index].duplicate(true)
	var used := []
	for p in choice.presets:
		if p.kind == copy.kind: used.append(p.target)
	var targets := _movable_parts() if copy.kind == "hinge" else ["whole"] + _part_ids()
	for t in targets:
		if not used.has(t):
			copy.target = t
			choice.presets.append(copy)
			focus = choice.presets.size() - 1
			_refresh()
			_changed()
			return
	_say(tr("모든 부품에 이미 있어요."))

func _set_option(key: String, value) -> void:
	if focus < 0 or focus >= choice.presets.size(): return
	choice.presets[focus][key] = value
	_refresh()
	_changed()

func _reset_choice() -> void:
	choice = {"mode": "presets", "presets": [], "keep": true, "rest": ""}
	focus = -1
	keep_box.button_pressed = true
	_set_mode("presets", false)
	_set_rest("", false)
	_refresh()
	_changed()
	_say(tr("만들 때의 움직임이에요. 저장하면 되돌아가요."))

func _changed(replay := true) -> void:
	preview_timer.set_meta("replay", replay)
	preview_timer.start()

# ---------------------------------------------------------------- refresh

func _refresh() -> void:
	for kind in cards:
		var used := _uses(kind)
		cards[kind].button_pressed = used
		card_badges[kind].visible = used
	for child in options_box.get_children(): child.queue_free()
	if focus >= 0 and focus < choice.presets.size():
		_build_options(choice.presets[focus])
	elif choice.presets.is_empty():
		RpgUi.caption(options_box, tr("고른 움직임이 없어요. 위 카드를 눌러 더해 보세요."), 13)
	for child in chips.get_children(): child.queue_free()
	for i in choice.presets.size():
		var p: Dictionary = choice.presets[i]
		var b := Button.new()
		b.text = tr(_trigger_name(p.trigger)) + " → " + tr(_kind_name(p.kind)) + ("" if p.target == "whole" else " · " + _part_name(p.target))
		b.theme_type_variation = "ChoiceButton"
		b.toggle_mode = true
		b.button_pressed = i == focus
		b.focus_mode = Control.FOCUS_NONE
		b.add_theme_font_size_override("font_size", 12)
		var index: int = i
		b.pressed.connect(func(): focus = index; _refresh())
		chips.add_child(b)
	if choice.rest != "": _chip(chips, tr("앉기") if choice.rest == "sit" else tr("눕기"), true)

func _build_options(p: Dictionary) -> void:
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 8)
	options_box.add_child(head)
	var title := RpgUi.heading(head, tr(_kind_name(p.kind)), 18)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if p.kind == "hinge" or _part_ids().size() > 1:
		RpgUi.name_tip(_button(head, "+", func(): _duplicate(focus)), tr("다른 부위에도"))
	_button(head, tr("빼기"), func(): _remove(focus))
	var when := HBoxContainer.new()
	when.add_theme_constant_override("separation", 6)
	options_box.add_child(when)
	_row_title(when, tr("언제"))
	for spec in TRIGGERS:
		var b := _toggle(when, tr(spec[1]), func(): _set_option("trigger", spec[0]))
		b.button_pressed = p.trigger == spec[0]
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var level := HBoxContainer.new()
	level.add_theme_constant_override("separation", 6)
	options_box.add_child(level)
	_row_title(level, tr("세기"))
	for i in 3:
		var b := _toggle(level, tr(LEVELS[i]), func(): _set_option("level", i + 1))
		b.button_pressed = int(p.level) == i + 1
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if p.kind in ["spin", "turn"]:
		var turn := HBoxContainer.new()
		turn.add_theme_constant_override("separation", 6)
		options_box.add_child(turn)
		_row_title(turn, tr("방향"))
		for spec in [[1, tr("↶ 왼쪽으로")], [-1, tr("오른쪽으로 ↷")]]:
			var b := _toggle(turn, spec[1], func(): _set_option("direction", spec[0]))
			b.button_pressed = int(p.direction) == spec[0]
			b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var ids := _movable_parts() if p.kind == "hinge" else ["whole"] + _part_ids()
	if ids.size() > 1:
		var where := HBoxContainer.new()
		where.add_theme_constant_override("separation", 6)
		options_box.add_child(where)
		_row_title(where, tr("부위"))
		var pick := OptionButton.new()
		pick.focus_mode = Control.FOCUS_NONE
		pick.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		for id in ids:
			pick.add_item(_part_name(id))
			pick.set_item_metadata(pick.item_count - 1, id)
			if id == p.target: pick.select(pick.item_count - 1)
		pick.item_selected.connect(func(index: int): _set_option("target", str(pick.get_item_metadata(index))))
		where.add_child(pick)
	if p.kind == "hinge":
		var axis := HBoxContainer.new()
		axis.add_theme_constant_override("separation", 6)
		options_box.add_child(axis)
		_row_title(axis, tr("축"))
		for spec in [["x", tr("앞뒤로 열기")], ["z", tr("옆으로 열기")], ["y", tr("돌려 열기")]]:
			var b := _toggle(axis, spec[1], func(): _set_option("axis", spec[0]))
			b.button_pressed = p.axis == spec[0]
			b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var angle := HBoxContainer.new()
		angle.add_theme_constant_override("separation", 6)
		options_box.add_child(angle)
		_row_title(angle, tr("각도"))
		var slider := HSlider.new()
		slider.min_value = -180
		slider.max_value = 180
		slider.step = 15
		slider.value = int(p.angle)
		slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		angle.add_child(slider)
		var shown := RpgUi.caption(angle, "%d°" % int(p.angle), 13, RpgUi.PAPER_INK)
		shown.custom_minimum_size.x = 52
		# Kept without rebuilding the row, so a drag is never interrupted.
		slider.value_changed.connect(func(v: float):
			shown.text = "%d°" % int(v)
			if focus >= 0 and focus < choice.presets.size(): choice.presets[focus].angle = int(v)
			_changed())

func _update_describe() -> void:
	if not is_instance_valid(describe_note): return
	var d: Dictionary = info.get("describe", {})
	var left := int(d.get("left", 0))
	describe_note.text = tr("%d 별씨 · 오늘 %d번 남음") % [int(d.get("cost", 5)), left]
	describe_button.disabled = busy or describe_text.text.strip_edges().length() < 2 or left <= 0 or info.get("listed", false)
	for child in describe_result.get_children(): child.queue_free()
	if not draft.is_empty() and draft.get("program") is Dictionary:
		var s: Dictionary = draft.get("summary", {})
		_chip(describe_result, tr("✓ 준비됨"), true)
		for e in s.get("events", []):
			if e != "spawn": _chip(describe_result, tr({"click": "클릭·E", "near": "다가가면", "leave": "멀어지면", "tick": "항상"}.get(e, e)))
		for op in s.get("ops", []):
			_chip(describe_result, tr({"rotate_x": "기울기", "rotate_y": "돌기", "rotate_z": "흔들기", "offset_y": "뜨기", "emission": "빛", "hue": "색"}.get(op, op)))

# ---------------------------------------------------------------- server

func _payload() -> Dictionary:
	var presets: Array = []
	for p in choice.presets:
		presets.append({"kind": p.kind, "trigger": p.trigger, "target": p.target, "level": int(p.level),
			"direction": int(p.get("direction", 1)), "axis": str(p.get("axis", "x")), "angle": int(p.get("angle", 90))})
	var mode: String = choice.mode
	if mode == "presets" and presets.is_empty() and choice.keep: mode = "original"
	return {"mode": mode, "presets": presets if mode == "presets" else [], "keep": bool(choice.keep), "rest": str(choice.rest)}

## Plays the current choice on the object here (server-compiled, nothing saved).
func _preview(replay: bool) -> void:
	if info.is_empty() or not is_instance_valid(model): return
	if preview_timer.has_meta("replay") and not replay: replay = bool(preview_timer.get_meta("replay"))
	preview_timer.remove_meta("replay")
	var payload := _payload()
	if payload.mode == "custom" and draft.is_empty() and str(info.get("spec", {}).get("mode", "")) != "custom":
		_say(tr("먼저 '만들어 보기'를 눌러 주세요."))
		return
	preview_serial += 1
	var serial := preview_serial
	var reply: Dictionary = await api.post("/v1/objects/" + str(obj.id) + "/interaction/preview", payload)
	if serial != preview_serial or not is_inside_tree() or not is_instance_valid(model): return
	if not reply.ok:
		_say(_error(reply.error))
		return
	model.start_program(reply.data.program)
	if replay and focus >= 0 and focus < choice.presets.size() and payload.mode == "presets":
		var trigger: String = choice.presets[focus].trigger
		if trigger != "always": model.local_event(trigger)
	_say(tr("미리보는 중 · 저장하면 어디서나 이렇게 움직여요"))

func _try(event: String) -> void:
	if not is_instance_valid(model): return
	model.local_event(event)
	RpgUi.sfx("click")

func _save() -> void:
	if busy or info.is_empty(): return
	busy = true
	_set_enabled(false)
	_say(tr("저장하는 중…"))
	var path := "/v1/objects/" + str(obj.id) + "/interaction"
	var reply: Dictionary = {}
	for attempt in 2:
		reply = await api.post(path, api.mutation(_payload().merged({"version": int(info.get("runtime_version", 1))})))
		if reply.ok or reply.get("error") != "stale_runtime_version": break
		# Someone used the object meanwhile: read its version again and try once more.
		var fresh: Dictionary = await api.request(path)
		if not fresh.ok: break
		info.runtime_version = fresh.data.runtime_version
	busy = false
	if not is_inside_tree(): return
	_set_enabled(true)
	if not reply.ok:
		_say(_error(reply.error))
		return
	info.runtime_version = reply.data.runtime.version
	info.spec = reply.data.spec
	saved_once = true
	if is_instance_valid(model):
		var value = reply.data.get("interaction")
		model.use_interaction(value if value is Dictionary else {}, reply.data.program, reply.data.runtime)
		saved_state = model.vm.state.duplicate(true)
	if options.get("saved") is Callable and options.saved.is_valid(): options.saved.call(reply.data)
	RpgUi.sfx("confirm")
	_celebrate()
	_say(tr("저장했어요! 이제 어디서나 이렇게 움직여요."))

func _describe() -> void:
	if busy or info.is_empty(): return
	var text := describe_text.text.strip_edges()
	if text.length() < 2: return
	busy = true
	_set_enabled(false)
	_say(tr("설계하는 중… 잠시만요"))
	var reply: Dictionary = await api.request("/v1/objects/" + str(obj.id) + "/interaction/describe",
		api.mutation({"text": text}), HTTPClient.METHOD_POST, false, 240.0)
	busy = false
	if not is_inside_tree(): return
	_set_enabled(true)
	if not reply.ok:
		_say(_error(reply.error))
		return
	var data: Dictionary = reply.data
	var d: Dictionary = info.get("describe", {})
	d.left = maxi(0, int(d.get("left", 1)) - 1)
	info.describe = d
	if data.get("state") != "ready":
		_say(_error(str(data.get("error", "design_rejected"))) + tr(" · 별씨는 돌려드렸어요"))
		_update_describe()
		return
	draft = {"text": data.text, "program": data.program, "summary": data.get("summary", {})}
	_update_describe()
	if is_instance_valid(model):
		model.start_program(data.program)
		model.local_event("click")
	_celebrate()
	_say(tr("완성! 시험해 보고 마음에 들면 저장하세요."))

func _set_enabled(enabled: bool) -> void:
	for b in [save_button, preview_button, reset_button]:
		if is_instance_valid(b): b.disabled = not enabled
	for kind in cards: cards[kind].disabled = not enabled
	if is_instance_valid(describe_button): _update_describe()

# ---------------------------------------------------------------- helpers

func _uses(kind: String) -> bool:
	for p in choice.presets:
		if p.kind == kind: return true
	return false

func _part_ids() -> Array:
	var ids: Array = []
	for p in info.get("parts", []):
		if str(p.id) != "whole": ids.append(str(p.id))
	return ids

## Parts that can swing open: every part of a multi-part craft, the likeliest first (a lid or a
## door, then attached parts, then the others last to first - the first is usually the body).
func _movable_parts() -> Array:
	var parts: Array = info.get("parts", [])
	if parts.size() < 2: return []
	var named: Array = []
	var children: Array = []
	var roots: Array = []
	for p in parts:
		var id := str(p.id)
		if ["lid", "door", "cover", "hatch", "flap", "drawer"].any(func(word): return word in id.to_lower()): named.append(id)
		elif str(p.parent) != "": children.append(id)
		else: roots.push_front(id)
	return named + children + roots

func _part_name(id: String) -> String:
	if id == "whole": return tr("전체")
	if PART_NAMES.has(id): return tr(PART_NAMES[id])
	if id.begins_with("petal"): return tr("꽃잎 ") + id.trim_prefix("petal").trim_prefix("_")
	var parts: Array = info.get("parts", [])
	for i in parts.size():
		if str(parts[i].id) == id: return tr("부분 %d") % (i + 1)
	return id

func _kind_name(kind: String) -> String:
	for spec in KINDS:
		if spec[0] == kind: return spec[1]
	return kind

func _trigger_name(trigger: String) -> String:
	for spec in TRIGGERS:
		if spec[0] == trigger: return spec[1]
	return trigger

func _text_limit() -> int:
	return int(info.get("describe", {}).get("text_limit", 200))

func _say(text: String) -> void:
	if not is_instance_valid(status_label): return
	status_label.text = text
	if RpgUi.calm(): return
	status_label.modulate.a = 0.0
	status_label.create_tween().tween_property(status_label, "modulate:a", 1.0, 0.18)

func _error(code: String) -> String:
	var messages := {"object_is_listed": tr("장터에 올린 물건은 바꿀 수 없어요."),
		"insufficient_shards": tr("별씨가 부족해요."),
		"interaction_daily_limit": tr("오늘은 더 설명할 수 없어요. 내일 다시 해 보세요."),
		"design_pending": tr("다른 설명을 설계하고 있어요. 잠시 뒤에 다시 해 주세요."),
		"no_custom_design": tr("먼저 '만들어 보기'를 눌러 주세요."),
		"interaction_too_complex": tr("움직임이 너무 많아요. 몇 개를 빼 주세요."),
		"interaction_rejected": tr("이 조합은 안전 검사를 통과하지 못했어요."),
		"duplicate_preset": tr("같은 부위에 같은 움직임이 두 번 있어요."),
		"hinge_needs_part": tr("열고 닫을 부품을 골라 주세요."),
		"stale_runtime_version": tr("다른 곳에서 바뀌었어요. 다시 저장해 주세요."),
		"llm_not_configured": tr("지금은 글로 설명하기를 쓸 수 없어요."),
		"llm_invalid_design": tr("설명을 움직임으로 바꾸지 못했어요. 더 짧고 분명하게 써 보세요."),
		"design_changed_parts": tr("설명을 움직임으로 바꾸지 못했어요. 더 짧고 분명하게 써 보세요."),
		"design_rejected": tr("설명을 움직임으로 바꾸지 못했어요. 더 짧고 분명하게 써 보세요."),
		"connection_failed": tr("서버에 연결하지 못했어요.")}
	return str(messages.get(code, tr("잠시 뒤에 다시 해 주세요 · ") + code))

## A short sparkle around the stage after a save or a finished design (effects over sentences).
func _celebrate() -> void:
	if not is_instance_valid(window) or RpgUi.calm(): return
	window.pivot_offset = window.size * 0.5
	var tw := window.create_tween()
	tw.tween_property(window, "scale", Vector2.ONE * 1.015, 0.1).set_trans(Tween.TRANS_SINE)
	tw.tween_property(window, "scale", Vector2.ONE, 0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	if is_instance_valid(stage):
		var burst := CPUParticles3D.new()
		burst.one_shot = true
		burst.amount = 24
		burst.lifetime = 0.9
		burst.explosiveness = 0.9
		burst.direction = Vector3.UP
		burst.spread = 70.0
		burst.initial_velocity_min = 1.2
		burst.initial_velocity_max = 2.4
		burst.gravity = Vector3(0, -2.5, 0)
		burst.scale_amount_min = 0.5
		burst.scale_amount_max = 1.0
		var dot := SphereMesh.new()
		dot.radius = 0.03
		dot.height = 0.06
		dot.radial_segments = 6
		dot.rings = 3
		var glow := StandardMaterial3D.new()
		glow.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		glow.albedo_color = Color("ffe08a")
		dot.material = glow
		burst.mesh = dot
		burst.position = Vector3(0, 0.6, 0)
		stage.add_child(burst)
		burst.emitting = true
		get_tree().create_timer(1.6).timeout.connect(burst.queue_free)
