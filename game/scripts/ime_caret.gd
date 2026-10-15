extends Node
## IME (Korean, Chinese...) fixes for every LineEdit and TextEdit; autoloaded so it covers every scene.
##
## Caret: Godot draws the text caret in front of the syllable being composed, so it looks stuck at the
## front while typing. While a composition is open the focused field's caret is hidden (the composing
## syllable keeps its underline); it comes back the moment the syllable is committed.
##
## Focus change: Godot does not commit an open composition when focus moves, so Windows commits the
## pending syllable into whatever has focus next and it lands in the other field. The syllable is
## remembered on the focus change; if it shows up in the new field it is moved back to the end of the
## field it was typed in, and if focus went to something that is not a text field (or nothing arrives
## within a few frames) it is committed to its own field directly.
##
## Editing: a Godot 4.7 LineEdit takes keys and IME text only while it is "editing", and it can keep
## focus without editing: after Enter (unless keep_editing_on_text_submit), after Esc, or when focus
## reached it while an arrow key or pad direction was held. It then looks ready but drops every key.
## A focused LineEdit here always edits, wherever its focus came from (a click, the page, a panel);
## Esc leaves the field instead, so the next Esc reaches the page.
##
## Lost syllables: Godot 4.7.2 on Windows drops the Korean syllables typed with the new Microsoft IME,
## each one replacing the last (engine bug godotengine/godot#123269, fixed for 4.7.3; our engine patch:
## tools/engine_patches). No script can change the order in which the engine reads window messages, so
## when composed syllables never reach their field, the player is told the Windows setting that
## avoids the bug (the previous Microsoft IME).
##
## Passwords are not handled here: a field turns the IME back on at each redraw, so the password field
## itself keeps only Latin letters (RpgUi.field).
##
## "--ime-trace" (after "--" on the command line) writes focus, editing, IME text and key events to
## user://logs/ime_trace.txt.
const SETTLE_FRAMES := 15
## Frames after the next syllable starts in which the one before must reach the field.
const COMMIT_FRAMES := 8
## Syllables lost before the hint shows.
const LOST_BEFORE_HINT := 2
const HINT_SECONDS := 14.0
const CHOSEONG := "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
## Loaded when needed, not held (an autoload holding UI scripts crashed the engine at exit, cloud_prefs.gd).
const GAME_SETTINGS := "res://scripts/game_settings.gd"
const PERF_OVERLAY := "res://scripts/perf_overlay.gd"

signal syllable_lost(field: Control)

var hidden: Control
var composing_field: Control
var composing_text := ""
var pending := {}
## Headless runs (tests, servers) have no IME; asking there logs an error every frame.
var ime_supported := false
## Tests: the composition to use instead of asking the display server (null = ask).
var ime_override = null
## The LineEdit Esc was pressed in: it stops editing, and then loses focus instead of staying deaf.
var cancelled: Control
var last_ime := ""
var last_length := 0
var last_field: Control
## {"field", "length", "frames"}: a syllable started; the one before must reach `field` in time.
var watch := {}
var lost_syllables := 0
var hint: CanvasLayer
var trace: FileAccess

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	ime_supported = DisplayServer.has_feature(DisplayServer.FEATURE_IME)
	get_viewport().gui_focus_changed.connect(_on_focus_changed)
	get_window().window_input.connect(_on_window_input)
	if "--ime-trace" in OS.get_cmdline_user_args(): start_trace("user://logs/ime_trace.txt")
	RenderingServer.frame_post_draw.connect(_keep_latin)
	# The performance overlay when the setting is on, or later when it is turned on.
	var settings = load(GAME_SETTINGS)
	settings.listen(_on_settings)
	if bool(settings.get_value("perf_overlay")): perf_overlay.call_deferred()

## The performance overlay (perf_overlay.gd: F2, or Settings > 그래픽 > 성능 표시) is made on first use
## here. It is not an autoload of its own: a new autoload changes project.binary, and a changed
## project.binary sends every player to the installer instead of a patch (tools/game_patch.py).
func perf_overlay() -> Node:
	var overlay := get_tree().root.get_node_or_null("PerfOverlay")
	if overlay == null:
		overlay = load(PERF_OVERLAY).new()
		overlay.name = "PerfOverlay"
		get_tree().root.add_child(overlay)
	return overlay

func _on_settings(keys: Array[String]) -> void:
	if "perf_overlay" in keys and bool(load(GAME_SETTINGS).get_value("perf_overlay")): perf_overlay()

## A Latin field (RpgUi.field: password, id, world address) types keyboard letters even when the
## Korean IME is in Hangul mode. Godot turns the IME on again whenever the field redraws, so it is
## switched off after every frame's drawing, before the next frame reads the keyboard.
func _keep_latin() -> void:
	if not ime_supported or not get_window().has_focus(): return
	var focus := get_viewport().gui_get_focus_owner()
	if focus is LineEdit and focus.has_meta("latin") and (focus as LineEdit).is_editing():
		DisplayServer.window_set_ime_active(false)

func _process(_delta: float) -> void:
	var focus := get_viewport().gui_get_focus_owner()
	var field: Control = focus if _is_text(focus) else null
	if field is LineEdit and not field.is_editing() and field.is_visible_in_tree():
		if cancelled == field:
			cancelled = null
			field.release_focus()
			_note("esc: focus released from %s" % _name(field))
			field = null
		else:
			field.edit()
			_note("edit() on %s, focused without editing" % _name(field))
	var ime := _ime_text(field)
	if ime != last_ime: _note("ime '%s' in %s, text %d" % [ime, _name(field), _length(field)])
	if field != null: _watch_commits(field, ime)
	if field != null and not ime.is_empty():
		composing_field = field
		composing_text = ime
	elif field != null and field == composing_field:
		composing_text = ""
	var composing := field != null and not ime.is_empty()
	if composing and hidden != field:
		_restore()
		field.add_theme_constant_override("caret_width", 0)
		hidden = field
	elif not composing and hidden != null:
		_restore()
	if not pending.is_empty(): _settle()
	last_ime = ime
	last_field = field
	last_length = _length(field)

func _ime_text(field: Control) -> String:
	if field == null: return ""
	if ime_override != null: return str(ime_override)
	# Asked only while a text field is focused in a focused window: before the window has ever had
	# focus (the player clicked elsewhere while the game started) Godot 4.7.2 looks the IME up on a
	# window that does not exist yet and the engine aborts.
	return DisplayServer.ime_get_text() if ime_supported and get_window().has_focus() else ""

func _on_window_input(event: InputEvent) -> void:
	if not event is InputEventKey: return
	# F2 before the overlay exists: make it and show it (once made, it takes F2 itself).
	if event.pressed and not event.echo and event.keycode == KEY_F2 and not get_tree().root.has_node("PerfOverlay"):
		perf_overlay().show_overlay(true)
	var focus := get_viewport().gui_get_focus_owner()
	if event.pressed and event.is_action("ui_cancel") and focus is LineEdit: cancelled = focus
	if trace:
		_note("key %s kc=%s phys=%s uni=%s%s focus=%s editing=%s" % ["down" if event.pressed else "up",
			OS.get_keycode_string(event.keycode), OS.get_keycode_string(event.physical_keycode),
			("U+%04X" % event.unicode) if event.unicode else "-", " echo" if event.echo else "",
			_name(focus), str(focus.is_editing()) if focus is LineEdit else "-"])

func _on_focus_changed(control: Control) -> void:
	cancelled = null
	_note("focus %s" % _name(control))
	if composing_text.is_empty() or not is_instance_valid(composing_field) or control == composing_field: return
	var target: Control = control if _is_text(control) else null
	pending = {"from": composing_field, "to": target, "text": composing_text,
		"before": target.text if target != null else "", "frames": SETTLE_FRAMES}
	composing_field = null
	composing_text = ""
	if target == null: _commit_to_origin()

func _settle() -> void:
	var target = pending.to
	var text: String = pending.text
	var before: String = pending.before
	if is_instance_valid(target) and target.text != before and target.text.length() >= before.length() + text.length() and target.text.contains(text):
		target.text = before
		if target is LineEdit: target.caret_column = before.length()
		_commit_to_origin()
		return
	pending.frames -= 1
	if pending.frames <= 0: _commit_to_origin()

func _commit_to_origin() -> void:
	var origin = pending.get("from")
	if is_instance_valid(origin):
		origin.insert_text_at_caret(pending.text)
	pending = {}

func _restore() -> void:
	if is_instance_valid(hidden): hidden.remove_theme_constant_override("caret_width")
	hidden = null

func _is_text(control: Control) -> bool:
	return (control is LineEdit and control.editable) or (control is TextEdit and control.editable)

# ------------------------------------------------------------------ lost syllables

## A whole syllable gave way to the start of the next one; Korean commits the first as that happens.
@warning_ignore("integer_division")
static func starts_next_syllable(before: String, now: String) -> bool:
	if before.length() != 1 or now.is_empty(): return false
	var a := before.unicode_at(0)
	var b := now.unicode_at(0)
	if a < 0xAC00 or a > 0xD7A3: return false
	# Backspace takes 가 back to ㄱ, its own first consonant: nothing is committed then.
	if b >= 0x3131 and b <= 0x318E: return now.substr(0, 1) != CHOSEONG[(a - 0xAC00) / 588]
	if b >= 0xAC00 and b <= 0xD7A3: return (b - 0xAC00) / 588 != (a - 0xAC00) / 588
	return false

func _watch_commits(field: Control, ime: String) -> void:
	if not watch.is_empty():
		if watch.field != field or _length(field) > watch.length: watch = {}
		else:
			watch.frames -= 1
			if watch.frames <= 0:
				watch = {}
				_lost(field)
	if field == last_field and starts_next_syllable(last_ime, ime) and not _full(field):
		watch = {"field": field, "length": last_length, "frames": COMMIT_FRAMES}

func _lost(field: Control) -> void:
	lost_syllables += 1
	_note("syllable lost in %s, %d so far" % [_name(field), lost_syllables])
	if lost_syllables == 1: print("[IME] a Korean syllable never reached %s (engine bug godotengine/godot#123269)" % _name(field))
	syllable_lost.emit(field)
	if lost_syllables == LOST_BEFORE_HINT: show_hint()

## How to type Korean on this engine build: the previous Microsoft IME does not meet the engine bug.
func show_hint() -> void:
	if is_instance_valid(hint): return
	hint = CanvasLayer.new()
	hint.layer = 120
	add_child(hint)
	var panel := PanelContainer.new()
	var box := StyleBoxFlat.new()
	box.bg_color = Color(0.07, 0.06, 0.05, 0.92)
	box.border_color = Color("e2b45a")
	box.set_border_width_all(2)
	box.set_corner_radius_all(10)
	box.set_content_margin_all(14)
	panel.add_theme_stylebox_override("panel", box)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hint.add_child(panel)
	var label := Label.new()
	label.text = tr("한글이 한 글자씩 덮어써지면 Windows 설정 › 시간 및 언어 › 한국어 › Microsoft 입력기 › 일반에서\n'이전 버전의 Microsoft IME 사용'을 켜 주세요. 이 게임 엔진 버전의 문제예요.")
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_color_override("font_color", Color("f5ead2"))
	label.add_theme_font_size_override("font_size", 16)
	panel.add_child(label)
	panel.reset_size()
	panel.position = Vector2((panel.get_viewport_rect().size.x - panel.size.x) * 0.5, 18)
	var shown := hint
	get_tree().create_timer(HINT_SECONDS, true).timeout.connect(func(): if is_instance_valid(shown): shown.queue_free())

func _full(field: Control) -> bool:
	return field is LineEdit and field.max_length > 0 and field.text.length() >= field.max_length

func _length(field: Control) -> int:
	return field.text.length() if is_instance_valid(field) else 0

# ------------------------------------------------------------------ trace

func start_trace(path: String) -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path).get_base_dir())
	trace = FileAccess.open(path, FileAccess.WRITE)
	_note("trace %s, engine %s, display %s, IME %s" % [ProjectSettings.globalize_path(path),
		Engine.get_version_info().string, DisplayServer.get_name(), ime_supported])

func _note(line: String) -> void:
	if trace == null: return
	trace.store_line("%d %s" % [Time.get_ticks_msec(), line])
	trace.flush()

func _name(control: Control) -> String:
	if not is_instance_valid(control): return "none"
	var label := "%s:%s" % [control.get_class(), control.name]
	if control is LineEdit and control.secret: label += "(secret)"
	return label
