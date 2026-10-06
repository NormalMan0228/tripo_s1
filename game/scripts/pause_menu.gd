extends CanvasLayer
## Esc menu for the village, survival and the rooms:
##   PauseMenu.open(app)   app is main.gd (screen "village" / "survival") or studio.gd
##   PauseMenu.close()     PauseMenu.is_open()
## 계속하기 · 설정 · 조작 안내 · (survival) 진행을 저장하고 마을로 / 탐험을 마치고 귀환
## · (village) 타이틀로 · (room) 마을로 · 게임 종료.
##
## While open it eats gameplay keys and clicks, and keeps the walker still. Solo
## survival reuses main.gd's own pause (app.paused stops tick_run, so the server
## sees no time pass); co-op survival keeps running and says so. Nothing new is
## sent to the server. The menu closes itself when the app leaves that screen.
const GameSettings = preload("res://scripts/game_settings.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const SettingsMenu = preload("res://scripts/settings_menu.gd")

static var current: CanvasLayer

var app: Node
var context := ""
var paused_run := false
var root: Control
var card: PanelContainer
var column: VBoxContainer
var sub: Control
## "main", "settings", "controls" or "ask": Esc steps back to "main", then closes.
var view := "main"

static func open(target: Node) -> CanvasLayer:
	if is_open(): return current
	if not is_instance_valid(target): return null
	var menu: CanvasLayer = load("res://scripts/pause_menu.gd").new()
	menu.app = target
	current = menu
	target.add_child(menu)
	return menu

static func close() -> void:
	if is_open(): current.dismiss()

static func is_open() -> bool:
	return is_instance_valid(current) and not current.is_queued_for_deletion()

static func theme_of(target: Node) -> Theme:
	var hud = target.get("ui")
	if hud is Control and hud.theme: return hud.theme
	if target is Control and target.theme: return target.theme
	return null

static func context_of(target: Node) -> String:
	if "screen" in target: return str(target.screen)
	if target.has_method("leave"): return "room"
	return "other"

func _ready() -> void:
	name = "PauseMenu"
	layer = 50
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_priority = 100
	context = context_of(app)
	if context == "survival" and "paused" in app and not app.paused and str(app.run.get("status","")) == "active":
		# The same switch main.gd's toggle_pause() flips: no ticks reach the server.
		app.paused = true
		app.pending_action = ""
		app.pending_target = ""
		paused_run = true
	root = Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_STOP
	# A CanvasLayer cuts theme inheritance: borrow the app's HUD theme (RpgUi kit).
	root.theme = theme_of(app)
	add_child(root)
	var shade := ColorRect.new()
	shade.color = Color(0.02,0.04,0.05,.66)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(shade)
	show_main()
	if not GameSettings.reduced_motion():
		root.modulate.a = 0.0
		root.create_tween().tween_property(root, "modulate:a", 1.0, 0.12)

func dismiss() -> void:
	if paused_run and is_instance_valid(app) and "paused" in app and str(app.get("screen")) == "survival":
		app.paused = false
	paused_run = false
	if current == self: current = null
	queue_free()

func _exit_tree() -> void:
	if current == self: current = null

func _process(_delta: float) -> void:
	if not is_instance_valid(app) or context_of(app) != context or ("results_shown" in app and app.results_shown):
		dismiss()
		return
	# Hold the walker: main.gd re-enables village controls every frame before us.
	if "player" in app and is_instance_valid(app.player) and "controls_enabled" in app.player:
		app.player.controls_enabled = false

func _input(event: InputEvent) -> void:
	if view == "settings": return
	var back: bool = (event is InputEventKey and event.pressed and not event.echo and event.physical_keycode == KEY_ESCAPE) \
		or (event is InputEventJoypadButton and event.pressed and event.button_index in [JOY_BUTTON_B, JOY_BUTTON_START])
	if back:
		get_viewport().set_input_as_handled()
		if view != "main": show_main()
		else: dismiss()

func _unhandled_input(event: InputEvent) -> void:
	# Nothing behind the menu reacts while it is open (E, I, M, wheel zoom...).
	if event is InputEventKey or event is InputEventMouseButton or event is InputEventJoypadButton:
		get_viewport().set_input_as_handled()

func _clear() -> void:
	if is_instance_valid(card): card.queue_free()
	if is_instance_valid(sub): sub.queue_free()
	card = null
	sub = null

func _card(width: float) -> VBoxContainer:
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(center)
	card = PanelContainer.new()
	var frame := RpgUi.panel_style("night")
	frame.content_margin_left = 36; frame.content_margin_right = 36; frame.content_margin_top = 30; frame.content_margin_bottom = 28
	card.add_theme_stylebox_override("panel", frame)
	card.theme = RpgUi.night_theme()
	RpgUi.pop_in(card)
	card.custom_minimum_size.x = width
	center.add_child(card)
	column = VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	card.add_child(column)
	# The card's CenterContainer goes with it.
	card.tree_exiting.connect(center.queue_free)
	return column

func show_main() -> void:
	_clear()
	view = "main"
	var list := _card(420)
	RpgUi.label(list, tr("잠깐 쉬어 가기"), 30, RpgUi.GOLD)
	RpgUi.divider(list, Color(RpgUi.GOLD, .6))
	var note := ""
	if context == "survival":
		note = tr("협동 생존은 메뉴를 열어도 계속됩니다.\n연결이 끊겨도 동료가 남아 있으면 위험에 노출됩니다.") if app.get("coop_run") else tr("일시 정지 중에는 생존 시간과 허기가 멈춥니다.")
	elif context == "village":
		note = tr("마을의 하루는 메뉴를 여는 동안에도 흘러가요.")
	if not note.is_empty():
		var l := RpgUi.label(list, note, 14, Color("c9d3c6"), false)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.custom_minimum_size.x = 360
	var gap := Control.new(); gap.custom_minimum_size.y = 6; list.add_child(gap)
	var first := _item(list, tr("계속하기"), dismiss)
	first.theme_type_variation = "GoldButton"
	first.add_theme_color_override("font_hover_color", RpgUi.PAPER_INK)
	first.add_theme_color_override("font_focus_color", RpgUi.PAPER_INK)
	_item(list, tr("설정"), show_settings)
	_item(list, tr("조작 안내"), show_controls)
	match context:
		"survival":
			if not app.get("coop_run"): _item(list, tr("진행을 저장하고 마을로"), func():
				dismiss()
				app.suspend_run())
			_item(list, tr("탐험을 마치고 귀환"), func(): app.confirm_return())
		"village":
			_item(list, tr("타이틀로"), func(): ask(tr("로그아웃하고 타이틀로 돌아갈까요?"), func():
				dismiss()
				app.logout()))
		"room":
			_item(list, tr("마을로"), func():
				dismiss()
				app.leave())
	_item(list, tr("게임 종료"), func(): ask(tr("게임을 종료할까요?") + ("\n" + tr("진행 중인 탐험은 저장되어 다음에 이어 할 수 있어요.") if context == "survival" and not app.get("coop_run") else ""), func(): get_tree().quit()))
	_focus.call_deferred(first)

func _item(parent: Node, text: String, callback: Callable) -> Button:
	var b := RpgUi.menu_button(parent, text, callback, 360.0)
	b.focus_mode = Control.FOCUS_ALL
	b.add_theme_stylebox_override("focus", RpgUi.frame("focus"))
	b.add_theme_color_override("font_focus_color", Color("ffe08a"))
	return b

func show_settings() -> void:
	_clear()
	view = "settings"
	sub = SettingsMenu.open(root, show_main)

func show_controls() -> void:
	_clear()
	view = "controls"
	var list := _card(760)
	RpgUi.label(list, tr("조작 안내"), 26)
	var columns := HBoxContainer.new()
	columns.add_theme_constant_override("separation", 36)
	list.add_child(columns)
	var groups := [
		[[tr("이동"), [["move_forward","move_back","move_left","move_right"], ["run"]]],
			[tr("마을과 방"), [["interact"],["inventory"],["map"],["storage"],["craft"],["wardrobe"],["rotate"]]]],
		[[tr("생존"), [["interact"],["attack"],["eat"],["campfire"],["heal"]]],
			[tr("기타"), [["toggle_sound"]]]],
	]
	for side in groups:
		var half := VBoxContainer.new()
		half.add_theme_constant_override("separation", 6)
		half.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		columns.add_child(half)
		for group in side:
			RpgUi.label(half, group[0], 15, RpgUi.GOLD)
			var grid := GridContainer.new()
			grid.columns = 2
			grid.add_theme_constant_override("h_separation", 14)
			grid.add_theme_constant_override("v_separation", 3)
			half.add_child(grid)
			for actions in group[1]:
				var keys := []
				for action in actions: keys.append(GameSettings.key_label(action))
				var cap := RpgUi.label(grid, " / ".join(keys), 15, Color("ffe08a"))
				cap.custom_minimum_size.x = 120
				var what: String = tr("이동") if actions.size() > 1 else tr(GameSettings.action_label(actions[0]))
				if actions[0] == "run" and str(GameSettings.get_value("run_mode")) == "toggle": what += tr(" (눌러서 전환)")
				RpgUi.label(grid, what, 15)
	var extra := RpgUi.label(list, tr("마우스 휠 · 확대/축소     Esc · 메뉴     %s · 대화 넘기기") % GameSettings.key_label("interact"), 13, Color("c9d3c6"), false)
	extra.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var back := _item(list, tr("돌아가기"), show_main)
	_focus.call_deferred(back)

func ask(question: String, yes: Callable) -> void:
	_clear()
	view = "ask"
	var list := _card(440)
	var l := RpgUi.label(list, question, 19)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size.x = 380
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	list.add_child(row)
	var confirm := _item(row, tr("확인"), yes)
	confirm.custom_minimum_size.x = 180
	var cancel := _item(row, tr("취소"), show_main)
	cancel.custom_minimum_size.x = 180
	_focus.call_deferred(cancel)

## Focus once the frame settles, if the control is still on screen.
func _focus(control) -> void:
	if is_instance_valid(control) and control.is_inside_tree() and control.is_visible_in_tree(): control.grab_focus()
