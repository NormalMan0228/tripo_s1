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
const SETTLE_FRAMES := 15

var hidden: Control
var composing_field: Control
var composing_text := ""
var pending := {}

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	get_viewport().gui_focus_changed.connect(_on_focus_changed)

func _process(_delta: float) -> void:
	var focus := get_viewport().gui_get_focus_owner()
	var field: Control = focus if _is_text(focus) else null
	var ime := DisplayServer.ime_get_text()
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

func _on_focus_changed(control: Control) -> void:
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
