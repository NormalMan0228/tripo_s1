extends CanvasLayer
## Esc menu for the village, survival and the rooms:
##   PauseMenu.open(app)   app is main.gd (screen "village" / "survival") or studio.gd
##   PauseMenu.close()     PauseMenu.is_open()
## 계속하기 · 설정 · 조작 안내 · (survival) 진행을 저장하고 마을로 / 탐험을 마치고 귀환
## · (village) 타이틀로 · (room) 마을로 · 게임 종료.
##
## Every page is a night RpgUi.window over one shared shade: the next page (조작 안내, a question,
## 설정) borrows the shade already on screen, so the world never darkens twice.
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
## The page on screen (an RpgUi.window description); the next page takes over its shade.
var win: Dictionary = {}
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
	root.name = "Pages"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_STOP
	# A CanvasLayer cuts theme inheritance: borrow the app's HUD theme (RpgUi kit).
	root.theme = theme_of(app)
	add_child(root)
	show_main()

func dismiss() -> void:
	if paused_run and is_instance_valid(app) and "paused" in app and str(app.get("screen")) == "survival":
		app.paused = false
	paused_run = false
	if current == self: current = null
	if not win.is_empty(): RpgUi.close_window(win, false)
	win = {}
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
		# A question the app asked over this menu (the survival return) is the top window: it goes first.
		var top := RpgUi.top_window()
		var over: Control = top.get("root") if not top.is_empty() else null
		if is_instance_valid(over) and over != win.get("root") and root.is_ancestor_of(over) and RpgUi.close_top(top): return
		if view != "main": show_main()
		else: dismiss()

func _unhandled_input(event: InputEvent) -> void:
	# Nothing behind the menu reacts while it is open (E, I, M, wheel zoom...).
	if event is InputEventKey or event is InputEventMouseButton or event is InputEventJoypadButton:
		get_viewport().set_input_as_handled()

## Opens the next page as a night window in the middle of the screen. It borrows the shade of the
## page on screen, which then closes and hands the shade over, so the shade never blinks. One sound
## per page change (`sound`: the window's open going forward, a close stepping back, "" when the
## page that left was heard already), never the old page's close and the new one's open together.
func _page(title: String, width: float, on_close: Callable, sound := "open") -> VBoxContainer:
	if is_instance_valid(sub): sub.queue_free()
	sub = null
	var old := win
	win = RpgUi.window(root, title, {"kind":"night", "width":width, "place":"centre", "on_close":on_close, "id":"pause_page", "sound":false})
	if not old.is_empty(): RpgUi.close_window(old, false, false)
	if not sound.is_empty(): RpgUi.sfx(sound, -8.0 if sound == "open" else -10.0)
	var column: VBoxContainer = win.body
	column.add_theme_constant_override("separation", RpgUi.GAP)
	return column

func show_main() -> void:
	# Back from 조작 안내 or a question: that page closing; back from the settings: their own close.
	var back := view
	view = "main"
	var list := _page(tr("잠깐 쉬어 가기"), 420, dismiss, "" if back == "settings" else ("close" if back in ["controls", "ask"] else "open"))
	var note := ""
	if context == "survival":
		note = tr("협동 생존은 메뉴를 열어도 계속됩니다.\n연결이 끊겨도 동료가 남아 있으면 위험에 노출됩니다.") if app.get("coop_run") else tr("일시 정지 중에는 생존 시간과 허기가 멈춥니다.")
	elif context == "village":
		note = tr("마을의 하루는 메뉴를 여는 동안에도 흘러가요.")
	if not note.is_empty():
		var l := RpgUi.label(list, note, 14, RpgUi.SOFT, false)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.custom_minimum_size.x = 360
	var gap := Control.new(); gap.custom_minimum_size.y = 2; list.add_child(gap)
	# The UI kit 2 plates: gold for the way back into play, night glass for the rest.
	var first := _item(list, tr("계속하기"), dismiss, "MenuGoldButton")
	_item(list, tr("설정"), show_settings)
	_item(list, tr("조작 안내"), show_controls)
	match context:
		"survival":
			if not app.get("coop_run"): _item(list, tr("진행을 저장하고 마을로"), func():
				dismiss()
				app.suspend_run())
			_item(list, tr("탐험을 마치고 귀환"), func(): app.confirm_return())
		"village":
			_item(list, tr("타이틀로"), func(): ask(tr("로그아웃하고 타이틀로 돌아갈까요?"), _to_title, tr("타이틀로")))
		"room":
			_item(list, tr("마을로"), func():
				dismiss()
				app.leave())
	var saved := "\n" + tr("진행 중인 탐험은 저장되어 다음에 이어 할 수 있어요.") if context == "survival" and not app.get("coop_run") else ""
	_item(list, tr("게임 종료"), func(): ask(tr("게임을 종료할까요?") + saved, _quit_game, tr("게임 종료")))
	_focus.call_deferred(first)

func _to_title() -> void:
	dismiss()
	app.logout()

func _quit_game() -> void:
	# The same notice as closing the window, so friends see this player leave at once (social.gd),
	# then the screen fades out before the game closes (clean_exit.gd).
	preload("res://scripts/clean_exit.gd").request_quit(get_tree())

## A menu plate ("MenuGoldButton" or "MenuNightButton") that arrows and the pad can reach.
func _item(parent: Node, text: String, callback: Callable, variant := "MenuNightButton") -> Button:
	var b := RpgUi.menu_button(parent, text, callback, 360.0, variant)
	b.focus_mode = Control.FOCUS_ALL
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	if variant == "MenuNightButton": b.add_theme_color_override("font_focus_color", RpgUi.HOVER)
	return b

func show_settings() -> void:
	view = "settings"
	# The pause page steps aside but stays open under the settings window, which borrows its shade.
	if not win.is_empty() and is_instance_valid(win.card): win.card.visible = false
	sub = SettingsMenu.open(root, show_main)

func show_controls() -> void:
	view = "controls"
	var list := _page(tr("조작 안내"), 760, show_main)
	var columns := HBoxContainer.new()
	columns.add_theme_constant_override("separation", 36)
	list.add_child(columns)
	# [group, rows]; a row is [keys, words]: action ids show their current key (and follow a rebind),
	# literal keys pass through; empty words name the action itself.
	var groups := [
		[[tr("이동"), [[["move_forward","move_left","move_back","move_right"], tr("이동")], [["run"], ""], [[tr("휠")], tr("확대/축소")]]],
			[tr("마을과 방"), [[["interact"], ""], [["inventory"], ""], [["map"], ""], [["storage"], ""], [["craft"], ""], [["wardrobe"], ""], [["rotate"], ""]]]],
		[[tr("생존"), [[["interact"], ""], [["attack"], ""], [["eat"], ""], [["campfire"], ""], [["heal"], ""]]],
			[tr("대화와 채팅"), [[["Enter"], tr("채팅")], [["social"], tr("함께하기")], [["interact","Space","Enter"], tr("대화 넘기기")], [["1-9"], tr("선택지")]]],
			[tr("기타"), [[["toggle_hud"], tr("HUD 접기")], [["toggle_sound"], ""], [["Esc"], tr("메뉴")]]]],
	]
	for side in groups:
		var half := VBoxContainer.new()
		half.add_theme_constant_override("separation", 5)
		half.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		columns.add_child(half)
		for group in side:
			if half.get_child_count() > 0:
				var gap := Control.new(); gap.custom_minimum_size.y = 4; half.add_child(gap)
			RpgUi.label(half, group[0], 15, RpgUi.GOLD)
			for row in group[1]: _keys(half, row[0], row[1])
	var back := _item(list, tr("돌아가기"), show_main)
	_focus.call_deferred(back)

## One controls row: the key caps, then what they do. Caps built from an action id relabel
## themselves after a rebind (RpgUi.keycap); further keys join the first cap ("E Space Enter").
func _keys(parent: Node, keys: Array, words: String) -> HBoxContainer:
	if words.is_empty():
		words = tr(GameSettings.action_label(keys[0]))
		if keys[0] == "run" and str(GameSettings.get_value("run_mode")) == "toggle": words += tr(" (눌러서 전환)")
	var row := RpgUi.key_hint(parent, keys[0], words)
	var said: Control = row.get_meta("words")
	for key in keys.slice(1):
		var cap := RpgUi.keycap(row, key)
		cap.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.move_child(cap, said.get_index())
	return row

## A yes/no question on its own page; 취소 (and Esc) go back to the main page.
func ask(question: String, yes: Callable, title := "") -> void:
	view = "ask"
	var list := _page(title if not title.is_empty() else tr("잠깐 쉬어 가기"), 440, show_main)
	var l := RpgUi.label(list, question, 17)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size.x = 380
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", RpgUi.GAP)
	list.add_child(row)
	var confirm := RpgUi.button(row, tr("확인"), yes, "primary", "lg", true)
	var cancel := RpgUi.button(row, tr("취소"), show_main, "night", "lg", true)
	for b in [confirm, cancel]: b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_focus.call_deferred(cancel)

## Focus once the frame settles, if the control is still on screen.
func _focus(control) -> void:
	if is_instance_valid(control) and control.is_inside_tree() and control.is_visible_in_tree(): control.grab_focus(true)
