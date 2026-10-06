extends Control
## Tabbed settings panel (그래픽 / 사운드 / 조작 / 게임플레이 / 접근성) used by the
## title screen and the pause menu:
##   var menu = SettingsMenu.open(parent_control, func(): ...)   # on_close is optional
## Changes go to a draft. Volume, brightness and interface size preview live; 적용
## saves the draft through GameSettings.commit(); 닫기 with unapplied changes asks
## first and otherwise restores the saved values. Keyboard and gamepad: arrows/stick
## move focus, Enter/A picks, PageUp/PageDown or LB/RB switch tabs, Esc closes.
const GameSettings = preload("res://scripts/game_settings.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")

const TABS := [["graphics","그래픽"],["audio","사운드"],["controls","조작"],["gameplay","게임플레이"],["accessibility","접근성"]]
const SELECTED := Color(0.36,0.28,0.14,.95)
const IDLE := Color(0.09,0.12,0.13,.78)
const HOVER := Color(0.24,0.2,0.12,.92)
const SOFT := Color("c9d3c6")
const WARN := Color("ffb38a")

signal closed

var on_close: Callable
var draft: Dictionary = {}
var draft_bindings: Dictionary = {}
var tab := "graphics"
var panel: PanelContainer
var tab_bar: HBoxContainer
var tab_buttons: Dictionary = {}
var scroll: ScrollContainer
var rows: VBoxContainer
var status: Label
var apply_button: Button
var capture: Dictionary = {}
var confirm: Control
var refreshing := false
## The saved values the draft started from (to tell edited rows from untouched ones).
var base: Dictionary = {}

static func open(parent: Node, callback: Callable = Callable()) -> Control:
	var menu: Control = load("res://scripts/settings_menu.gd").new()
	menu.on_close = callback
	parent.add_child(menu)
	return menu

func _ready() -> void:
	GameSettings.ensure_loaded()
	name = "SettingsMenu"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	theme = _theme()
	draft = GameSettings.snapshot()
	draft_bindings = GameSettings.bindings.duplicate(true)
	base = draft.duplicate()
	get_viewport().size_changed.connect(_fit)
	# Saved changes made elsewhere (M key, another menu) reach untouched rows.
	GameSettings.listen(_on_saved)
	_build()

func _build() -> void:
	tab_buttons.clear()
	var shade := ColorRect.new()
	shade.color = Color(0.02,0.03,0.035,.62)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	panel = PanelContainer.new()
	var frame := RpgUi.panel_style("night")
	frame.content_margin_left = 36; frame.content_margin_right = 36; frame.content_margin_top = 28; frame.content_margin_bottom = 26
	panel.add_theme_stylebox_override("panel", frame)
	panel.theme = RpgUi.night_theme()
	RpgUi.pop_in(panel)
	center.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	panel.add_child(column)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 18)
	column.add_child(head)
	RpgUi.label(head, tr("설정"), 28, RpgUi.GOLD)
	tab_bar = HBoxContainer.new()
	tab_bar.add_theme_constant_override("separation", 6)
	tab_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tab_bar.alignment = BoxContainer.ALIGNMENT_END
	head.add_child(tab_bar)
	for entry in TABS:
		var b := _button(tab_bar, tr(entry[1]), func(): show_tab(entry[0]), 17)
		b.custom_minimum_size = Vector2(112, 42)
		tab_buttons[entry[0]] = b
	column.add_child(_rule())
	scroll = ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(scroll)
	rows = VBoxContainer.new()
	rows.add_theme_constant_override("separation", 6)
	rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(rows)
	column.add_child(_rule())
	var foot := HBoxContainer.new()
	foot.add_theme_constant_override("separation", 10)
	column.add_child(foot)
	_button(foot, tr("기본값으로"), reset_tab, 16).custom_minimum_size = Vector2(150, 44)
	status = RpgUi.label(foot, "", 14, SOFT, false)
	status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	apply_button = _button(foot, tr("적용"), apply, 17)
	apply_button.custom_minimum_size = Vector2(130, 44)
	_button(foot, tr("닫기"), request_close, 17).custom_minimum_size = Vector2(130, 44)
	_fit()
	show_tab(tab)

func _on_saved(keys: Array) -> void:
	if not is_inside_tree(): return
	var saved := GameSettings.snapshot()
	for key in keys:
		if draft.has(key) and draft[key] == base.get(key): draft[key] = saved.get(key)
	base = saved
	_refresh_rows()
	_update_status()

func _exit_tree() -> void:
	GameSettings.unlisten(_on_saved)
	if get_viewport() and get_viewport().size_changed.is_connected(_fit): get_viewport().size_changed.disconnect(_fit)

func _fit() -> void:
	if not is_instance_valid(panel): return
	var view := get_viewport_rect().size
	panel.custom_minimum_size = Vector2(minf(1000.0, view.x-40.0), minf(660.0, view.y-40.0))

# ------------------------------------------------------------------ tabs
func show_tab(id: String) -> void:
	tab = id
	capture = {}
	for key in tab_buttons: _paint(tab_buttons[key], key == id)
	for child in rows.get_children():
		rows.remove_child(child)
		child.queue_free()
	match id:
		"graphics": _graphics()
		"audio": _audio()
		"controls": _controls()
		"gameplay": _gameplay()
		"accessibility": _accessibility()
	_update_status()
	scroll.scroll_vertical = 0
	# Mouse players see no focus ring; the first arrow key or stick push focuses
	# the first row (see _input), and tab switches keep keyboard focus on the page.
	var owner := get_viewport().gui_get_focus_owner() if is_inside_tree() else null
	if owner and is_ancestor_of(owner):
		var first := _first_focus(rows)
		_focus.call_deferred(first if first else tab_buttons[id])

func next_tab(step: int) -> void:
	var index := 0
	for i in TABS.size():
		if TABS[i][0] == tab: index = i
	show_tab(TABS[(index+step+TABS.size())%TABS.size()][0])

func _graphics() -> void:
	_heading(tr("화질"))
	_choice("preset", tr("그래픽 품질"), tr("높음은 그림자와 가장자리가 가장 매끈하고, 낮음은 느린 PC에서 부드럽게 움직여요."))
	_slider("render_scale", tr("3D 해상도"))
	_choice("shadows", tr("그림자"))
	_choice("msaa", tr("안티에일리어싱"))
	_choice("view_detail", tr("시야 디테일"), tr("먼 곳의 나무와 소품을 얼마나 자세히 그릴지 정해요."))
	_heading(tr("화면"))
	_choice("window_mode", tr("화면 모드"))
	_toggle("vsync", tr("수직 동기화"), tr("화면 찢어짐을 막아요. 끄면 입력이 조금 더 빨라질 수 있어요."))
	_choice("fps_cap", tr("최대 프레임"))
	_toggle("night_grade", tr("밤 색감"), tr("해가 지면 마을에 푸른 밤빛을 입혀요."))
	_slider("brightness", tr("밝기"), tr("어두운 곳이 잘 안 보이면 올려 주세요."))

func _audio() -> void:
	_heading(tr("음량"))
	_slider("master", tr("전체 음량"))
	_slider("music", tr("배경 음악"))
	_slider("sfx", tr("효과음"), tr("발소리, 문, 도구, 전투 소리예요."))
	_slider("ambience", tr("환경음"), tr("새소리, 파도, 바람 같은 배경 소리예요."))
	_slider("voice", tr("목소리"))
	_slider("ui", tr("인터페이스"))
	_heading(tr("음소거"))
	_toggle("mute_all", tr("모든 소리 끄기"), tr("게임 중에는 M 키로도 켜고 끌 수 있어요."))
	_toggle("background_mute", tr("다른 창을 볼 때 음소거"))

func _controls() -> void:
	_heading(tr("키 설정"))
	_note(tr("칸을 누른 뒤 새 키를 누르세요. Esc 취소 · Backspace 지우기"))
	for entry in GameSettings.ACTIONS: _binding_row(entry[0], tr(entry[1]))
	_heading(tr("카메라와 이동"))
	_slider("zoom_speed", tr("시점 확대 속도"))
	_toggle("zoom_invert", tr("마우스 휠 방향 반대로"))
	_choice("run_mode", tr("달리기 방식"))

func _gameplay() -> void:
	_heading(tr("언어와 대화"))
	_choice("language", tr("언어"))
	_choice("text_speed", tr("대사 속도"))
	_heading(tr("화면 표시"))
	_toggle("nameplates", tr("이름표 표시"), tr("주민과 장소 위에 이름을 띄워요."))
	_toggle("prompts", tr("상호작용 안내 표시"), tr("가까이 가면 'E · 대화하기' 같은 안내를 보여 줘요."))
	_choice_bool("minimap_rotate", tr("미니맵"), tr("북쪽 고정"), tr("바라보는 방향"))
	_choice_bool("clock_24h", tr("시계"), tr("12시간"), tr("24시간"))
	_toggle("reduce_shake", tr("화면 흔들림·번쩍임 줄이기"))

func _accessibility() -> void:
	_heading(tr("보기 편하게"))
	_slider("ui_scale", tr("인터페이스 크기"), tr("손을 떼면 적용돼요."))
	_toggle("large_text", tr("큰 글씨"), tr("메뉴와 대화의 글씨를 키워요."))
	_toggle("reduced_motion", tr("움직임 줄이기"), tr("파티클, 번쩍임, 화면 흔들림을 줄여요."))

# ------------------------------------------------------------------ rows
func _row(text: String, hint := "") -> HBoxContainer:
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 14)
	line.custom_minimum_size.y = 44
	rows.add_child(line)
	var names := VBoxContainer.new()
	names.custom_minimum_size.x = 300
	names.add_theme_constant_override("separation", 0)
	names.alignment = BoxContainer.ALIGNMENT_CENTER
	line.add_child(names)
	RpgUi.label(names, text, 17)
	if not hint.is_empty():
		var small := RpgUi.label(names, hint, 12, SOFT, false)
		small.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		small.custom_minimum_size.x = 300
	var controls := HBoxContainer.new()
	controls.add_theme_constant_override("separation", 6)
	controls.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	controls.alignment = BoxContainer.ALIGNMENT_BEGIN
	line.add_child(controls)
	return controls

func _heading(text: String) -> void:
	var gap := Control.new()
	gap.custom_minimum_size.y = 4 if rows.get_child_count() == 0 else 10
	rows.add_child(gap)
	RpgUi.label(rows, text, 15, RpgUi.GOLD)

func _note(text: String) -> void:
	var l := RpgUi.label(rows, text, 13, SOFT, false)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

func _choice(key: String, text: String, hint := "") -> void:
	var box := _row(text, hint)
	for choice in GameSettings.CHOICES[key]:
		var value = choice[0]
		var label: String = choice[1] if key == "language" else tr(choice[1])
		var b := _button(box, label, func(): set_draft(key, value), 15)
		b.custom_minimum_size = Vector2(maxf(86.0, label.length()*14.0+30.0), 40)
		if key == "preset" and value == "custom": b.disabled = true
		b.set_meta("value", value)
	box.set_meta("key", key)
	_paint_group(box)

func _choice_bool(key: String, text: String, off_label: String, on_label: String) -> void:
	var box := _row(text)
	for pair in [[false, off_label],[true, on_label]]:
		var value: bool = pair[0]
		var b := _button(box, pair[1], func(): set_draft(key, value), 15)
		b.custom_minimum_size = Vector2(140, 40)
		b.set_meta("value", value)
	box.set_meta("key", key)
	_paint_group(box)

func _toggle(key: String, text: String, hint := "") -> void:
	var box := _row(text, hint)
	for pair in [[false, tr("끄기")],[true, tr("켜기")]]:
		var value: bool = pair[0]
		var b := _button(box, pair[1], func(): set_draft(key, value), 15)
		b.custom_minimum_size = Vector2(96, 40)
		b.set_meta("value", value)
	box.set_meta("key", key)
	_paint_group(box)

func _slider(key: String, text: String, hint := "") -> void:
	var box := _row(text, hint)
	var limits: Array = GameSettings.RANGES[key]
	var slider := HSlider.new()
	slider.min_value = limits[0]; slider.max_value = limits[1]; slider.step = limits[2]
	slider.value = float(draft[key])
	slider.custom_minimum_size = Vector2(340, 40)
	slider.focus_mode = Control.FOCUS_ALL
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	slider.name = "Slider_"+key
	box.add_child(slider)
	var readout := RpgUi.label(box, "%d%%" % int(draft[key]), 17, RpgUi.INK)
	readout.custom_minimum_size.x = 64
	readout.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	var dragging := [false]
	slider.drag_started.connect(func(): dragging[0] = true)
	slider.value_changed.connect(func(v: float):
		readout.text = "%d%%" % int(v)
		if refreshing: return
		# Interface size waits for the release: rescaling under the cursor jumps the knob.
		set_draft(key, int(v), not (key == "ui_scale" and dragging[0])))
	slider.drag_ended.connect(func(_changed: bool):
		dragging[0] = false
		if key == "ui_scale": set_draft(key, int(slider.value)))

func _binding_row(action: String, text: String) -> void:
	var box := _row(text)
	for slot in 2:
		var key: int = draft_bindings[action][slot]
		var b := _button(box, GameSettings.key_name(key) if key != KEY_NONE else tr("비어 있음"), func(): start_capture(action, slot), 16)
		b.custom_minimum_size = Vector2(150, 40)
		b.name = "Bind_%s_%d" % [action, slot]
		if key == KEY_NONE: b.add_theme_color_override("font_color", Color(1,1,1,.4))

# ------------------------------------------------------------------ draft
func set_draft(key: String, value, live := true) -> void:
	if draft.get(key) == value: return
	draft[key] = value
	if key == "preset" and GameSettings.PRESETS.has(str(value)):
		draft.merge(GameSettings.PRESETS[str(value)], true)
	elif key in GameSettings.PRESETS.medium:
		draft.preset = GameSettings.derive_preset(draft)
	if live and key in GameSettings.LIVE_KEYS: GameSettings.preview({key: value})
	_refresh_rows()
	_update_status()

func _refresh_rows() -> void:
	refreshing = true
	for line in rows.get_children():
		if not line is HBoxContainer or line.get_child_count() < 2: continue
		var box: Node = line.get_child(1)
		if box.has_meta("key"): _paint_group(box)
		for child in box.get_children():
			if child is HSlider:
				var key := str(child.name).trim_prefix("Slider_")
				if draft.has(key) and int(child.value) != int(draft[key]): child.value = float(draft[key])
	refreshing = false

func _paint_group(box: Node) -> void:
	var key: String = box.get_meta("key")
	for b in box.get_children():
		if b is Button: _paint(b, b.get_meta("value") == draft.get(key))

func dirty() -> bool:
	var saved := GameSettings.snapshot()
	for key in draft:
		if saved.get(key) != draft[key]: return true
	return draft_bindings != GameSettings.bindings

func _update_status(text := "", warn := false) -> void:
	if not is_instance_valid(status): return
	if text.is_empty():
		var unbound := []
		for entry in GameSettings.ACTIONS:
			if int(draft_bindings[entry[0]][0]) == KEY_NONE and int(draft_bindings[entry[0]][1]) == KEY_NONE: unbound.append(tr(entry[1]))
		if not unbound.is_empty():
			text = tr("키가 없는 동작: %s") % ", ".join(unbound); warn = true
		elif dirty(): text = tr("적용하지 않은 변경 사항이 있어요.")
	status.text = text
	status.add_theme_color_override("font_color", WARN if warn else SOFT)
	if is_instance_valid(apply_button): apply_button.disabled = not dirty()

func reset_tab() -> void:
	if tab == "controls": draft_bindings = GameSettings.default_bindings()
	var defaults := GameSettings.defaults_for(tab)
	draft.merge(defaults, true)
	if tab == "graphics": draft.preset = GameSettings.derive_preset(draft)
	var live := {}
	for key in defaults:
		if key in GameSettings.LIVE_KEYS: live[key] = defaults[key]
	GameSettings.preview(live)
	show_tab(tab)
	_update_status(tr("이 탭을 기본값으로 되돌렸어요. 적용을 눌러 저장하세요."))

func apply() -> void:
	var language_changed: bool = draft.get("language") != GameSettings.get_value("language")
	GameSettings.commit(draft, draft_bindings)
	draft = GameSettings.snapshot()
	base = draft.duplicate()
	draft_bindings = GameSettings.bindings.duplicate(true)
	if language_changed:
		# Every label on the panel was built in the old language.
		for child in get_children():
			remove_child(child)
			child.queue_free()
		_build()
	else:
		show_tab(tab)
	_update_status(tr("설정을 저장했어요."))

func request_close() -> void:
	if is_instance_valid(confirm): return
	if not dirty():
		close()
		return
	confirm = Control.new()
	confirm.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	confirm.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(confirm)
	var dim := ColorRect.new()
	dim.color = Color(0,0,0,.45)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	confirm.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	confirm.add_child(center)
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", RpgUi.panel_style("night"))
	center.add_child(card)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 14)
	card.add_child(column)
	RpgUi.label(column, tr("적용하지 않은 변경 사항이 있어요."), 19)
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 8)
	column.add_child(buttons)
	var first := _button(buttons, tr("적용하고 닫기"), func():
		apply()
		close(), 16)
	_button(buttons, tr("버리고 닫기"), close, 16)
	_button(buttons, tr("취소"), func():
		confirm.queue_free()
		confirm = null
		apply_button.grab_focus(), 16)
	for b in buttons.get_children(): b.custom_minimum_size = Vector2(150, 44)
	_focus.call_deferred(first)

func close() -> void:
	GameSettings.end_preview()
	closed.emit()
	if on_close.is_valid(): on_close.call()
	queue_free()

# ------------------------------------------------------------------ key capture
func start_capture(action: String, slot: int) -> void:
	capture = {"action":action,"slot":slot}
	var b := rows.find_child("Bind_%s_%d" % [action, slot], true, false) as Button
	if b:
		b.text = tr("키를 누르세요…")
		_paint(b, true)
	_update_status(tr("%s: 새 키를 누르세요.") % tr(GameSettings.action_label(action)))

func finish_capture(key: int) -> void:
	var action: String = capture.action
	var slot: int = capture.slot
	capture = {}
	var message := ""
	var warn := false
	if key in [KEY_BACKSPACE, KEY_DELETE]:
		draft_bindings[action][slot] = KEY_NONE
	elif key != KEY_ESCAPE:
		var result := GameSettings.rebind_in(draft_bindings, action, slot, key)
		if not result.ok:
			message = tr("이 키는 설정할 수 없어요."); warn = true
		elif not str(result.swapped).is_empty():
			message = tr("이미 쓰던 키라서 '%s'의 키와 맞바꿨어요.") % tr(GameSettings.action_label(result.swapped)); warn = true
	var focus_name := "Bind_%s_%d" % [action, slot]
	show_tab("controls")
	var b := rows.find_child(focus_name, true, false) as Button
	if b: _focus.call_deferred(b)
	if not message.is_empty(): _update_status(message, warn)

func _input(event: InputEvent) -> void:
	if not is_visible_in_tree(): return
	if not capture.is_empty():
		if event is InputEventKey and event.pressed and not event.echo:
			var key: int = event.physical_keycode if event.physical_keycode != KEY_NONE else event.keycode
			finish_capture(key)
			get_viewport().set_input_as_handled()
		elif event is InputEventMouseButton and event.pressed:
			finish_capture(KEY_ESCAPE)
		return
	if not is_instance_valid(confirm) and event.is_pressed() and not event.is_echo() and _is_navigation(event):
		var owner := get_viewport().gui_get_focus_owner()
		if owner == null or not is_ancestor_of(owner):
			var first := _first_focus(rows)
			if first:
				first.grab_focus()
				get_viewport().set_input_as_handled()
				return
	if event is InputEventKey and event.pressed and not event.echo:
		match event.physical_keycode:
			KEY_ESCAPE:
				if is_instance_valid(confirm):
					confirm.queue_free(); confirm = null
				else: request_close()
				get_viewport().set_input_as_handled()
			KEY_PAGEUP:
				next_tab(-1); get_viewport().set_input_as_handled()
			KEY_PAGEDOWN:
				next_tab(1); get_viewport().set_input_as_handled()
	elif event is InputEventJoypadButton and event.pressed:
		match event.button_index:
			JOY_BUTTON_LEFT_SHOULDER: next_tab(-1); get_viewport().set_input_as_handled()
			JOY_BUTTON_RIGHT_SHOULDER: next_tab(1); get_viewport().set_input_as_handled()
			JOY_BUTTON_B:
				request_close(); get_viewport().set_input_as_handled()

func _is_navigation(event: InputEvent) -> bool:
	for action in ["ui_up","ui_down","ui_left","ui_right","ui_focus_next","ui_focus_prev"]:
		if event.is_action(action): return true
	return false

# ------------------------------------------------------------------ look
func _button(parent: Node, text: String, callback: Callable, size := 16) -> Button:
	var b := RpgUi.menu_button(parent, text, callback, 0.0)
	b.focus_mode = Control.FOCUS_ALL
	b.add_theme_font_size_override("font_size", size)
	b.custom_minimum_size = Vector2(0, 40)
	_paint(b, false)
	return b

## Selected buttons glow gold; focus (keyboard/gamepad) gets a bright edge.
func _paint(b: Button, selected: bool) -> void:
	var look := "btn_gold_" if selected else "btn_night_"
	for state in ["normal","hover","pressed","disabled"]:
		b.add_theme_stylebox_override(state, RpgUi.frame(look + state if not (selected and state == "disabled") else "btn_gold_normal"))
	b.add_theme_stylebox_override("focus", RpgUi.frame("focus"))
	var ink := RpgUi.PAPER_INK if selected else Color("fff2cf")
	for item in ["font_color","font_focus_color","font_pressed_color","font_hover_pressed_color"]: b.add_theme_color_override(item, ink)
	b.add_theme_color_override("font_hover_color", RpgUi.PAPER_INK if selected else Color("ffe08a"))
	b.add_theme_color_override("font_disabled_color", ink if selected else Color(1,1,1,.35))
	b.add_theme_constant_override("outline_size", 0 if selected else 3)

func _box(fill: Color, border: Color, width: int) -> StyleBoxFlat:
	var box := RpgUi.style(fill, 9, border, width)
	box.shadow_size = 0
	box.content_margin_left = 12; box.content_margin_right = 12
	box.content_margin_top = 6; box.content_margin_bottom = 6
	return box

func _rule() -> Control:
	var holder := VBoxContainer.new()
	RpgUi.divider(holder, Color(RpgUi.GOLD, .6))
	return holder

func _first_focus(node: Node) -> Control:
	for child in node.get_children():
		if child is Control and child.focus_mode == Control.FOCUS_ALL and child.visible and not (child is Button and child.disabled): return child
		var found := _first_focus(child)
		if found: return found
	return null

func _theme() -> Theme:
	var t := Theme.new()
	var track := RpgUi.frame("bar_bg")
	track.set_content_margin_all(3)
	t.set_stylebox("slider", "HSlider", track)
	t.set_stylebox("grabber_area", "HSlider", RpgUi.frame("bar_fill", Color("e9b552")))
	t.set_stylebox("grabber_area_highlight", "HSlider", RpgUi.frame("bar_fill", Color("f3c96a")))
	t.set_icon("grabber", "HSlider", RpgUi.half("slider_grabber"))
	t.set_icon("grabber_highlight", "HSlider", RpgUi.half("slider_grabber_hover"))
	t.set_icon("grabber_disabled", "HSlider", _knob(Color(1,1,1,.3)))
	var focus := StyleBoxFlat.new()
	focus.draw_center = false
	focus.border_color = Color("fff0b8"); focus.set_border_width_all(2); focus.set_corner_radius_all(6)
	focus.expand_margin_left = 6; focus.expand_margin_right = 6; focus.expand_margin_top = 2; focus.expand_margin_bottom = 2
	t.set_stylebox("focus", "HSlider", focus)
	t.set_stylebox("scroll", "VScrollBar", RpgUi.frame("scroll_track"))
	t.set_stylebox("grabber", "VScrollBar", RpgUi.frame("scroll_grabber"))
	t.set_stylebox("grabber_highlight", "VScrollBar", RpgUi.frame("scroll_grabber_hover"))
	t.set_stylebox("grabber_pressed", "VScrollBar", RpgUi.frame("scroll_grabber_hover"))
	return t

static func _knob(color: Color) -> ImageTexture:
	var size := 22
	var image := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var c := Vector2(size, size)*0.5
	for y in size:
		for x in size:
			var d := Vector2(x+0.5, y+0.5).distance_to(c)
			var edge := clampf(size*0.5-d, 0.0, 1.0)
			var ring := clampf(size*0.5-2.5-d, 0.0, 1.0)
			image.set_pixel(x, y, Color(Color("3b2d1c").lerp(color, ring), edge))
	return ImageTexture.create_from_image(image)

## Focus once the frame settles, if the control is still on screen.
func _focus(control) -> void:
	if is_instance_valid(control) and control.is_inside_tree() and control.is_visible_in_tree(): control.grab_focus()
