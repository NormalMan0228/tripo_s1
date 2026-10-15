extends PanelContainer
## The input language a text field will type in, as a small chip at its right edge (37): "한" or
## "A". Godot cannot read the Windows 한/영 key, so the chip follows what the field receives: an open
## IME composition or a Hangul letter means 한, a Latin letter means A (one state for the whole game,
## shared by every field). Until the first letter it stays hidden rather than guess; the tooltip says
## it is read from typing. Attach with LangChip.attach(field) (RpgUi.field, the craft prompt).
const RpgUi = preload("res://scripts/rpg_ui.gd")

## "": not known yet, "ko", "en".
static var mode := ""

var field: Control
var word: Label

static func attach(target: Control) -> Control:
	if not is_instance_valid(target) or target.get_node_or_null("LangChip"): return null
	var chip := new()
	chip.field = target
	target.add_child(chip)
	return chip

## Reads a typed string: the last letter decides.
static func note(text: String) -> void:
	for i in range(text.length() - 1, -1, -1):
		var code := text.unicode_at(i)
		if (code >= 0xAC00 and code <= 0xD7A3) or (code >= 0x3131 and code <= 0x318E):
			mode = "ko"
			return
		if (code >= 0x41 and code <= 0x5A) or (code >= 0x61 and code <= 0x7A):
			mode = "en"
			return

func _ready() -> void:
	name = "LangChip"
	mouse_filter = Control.MOUSE_FILTER_PASS
	var style := StyleBoxFlat.new()
	style.bg_color = Color(RpgUi.NIGHT, 0.82)
	style.border_color = Color(RpgUi.GOLD, 0.7)
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	style.content_margin_left = 6
	style.content_margin_right = 6
	style.content_margin_top = 1
	style.content_margin_bottom = 1
	add_theme_stylebox_override("panel", style)
	word = RpgUi.label(self, "", 12, RpgUi.GOLD, false)
	word.add_theme_font_override("font", RpgUi.FONT_STRONG)
	tooltip_text = tr("입력 언어 · 입력한 글자로 알아봐요 (한/영 키로 바꿔요)")
	visible = false
	if field.has_signal("text_changed"):
		field.text_changed.connect(func(value = ""): note(str(value) if value is String else str(field.get("text"))))
	_place()
	field.resized.connect(_place)

func _place() -> void:
	if not is_instance_valid(field): return
	var want := get_combined_minimum_size()
	# A one-line field: centred at its right end; a text box: its top-right corner.
	var y := 6.0 if field is TextEdit else (field.size.y - want.y) * 0.5
	position = Vector2(field.size.x - want.x - 8.0, y)
	size = want

func _process(_delta: float) -> void:
	if not is_instance_valid(field): return
	if field.has_focus() and DisplayServer.has_feature(DisplayServer.FEATURE_IME) and not DisplayServer.ime_get_text().is_empty():
		mode = "ko"
	var show := field.has_focus() and not mode.is_empty()
	if show:
		var text := "한" if mode == "ko" else "A"
		if word.text != text:
			word.text = text
			_place()
	if visible != show: visible = show
