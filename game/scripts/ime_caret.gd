extends Node
## Korean (and other IME) composition: Godot draws the text caret at the start of the syllable being
## composed, so it looks stuck in front of what is typed. While a composition is open the focused
## field's caret is hidden (the composing syllable keeps its underline); it comes back the moment the
## syllable is committed. Autoloaded, so it covers every LineEdit and TextEdit in every scene.
var hidden: Control

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS

func _process(_delta: float) -> void:
	var focus := get_viewport().gui_get_focus_owner()
	var field: Control = focus if focus is LineEdit or focus is TextEdit else null
	var composing := field != null and not DisplayServer.ime_get_text().is_empty()
	if composing and hidden != field:
		_restore()
		field.add_theme_constant_override("caret_width", 0)
		hidden = field
	elif not composing and hidden != null:
		_restore()

func _restore() -> void:
	if is_instance_valid(hidden): hidden.remove_theme_constant_override("caret_width")
	hidden = null
