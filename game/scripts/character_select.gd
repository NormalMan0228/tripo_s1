extends Control
## The first look (31): right after 계정 만들기, over the title, the new player picks one of the four
## travellers on portrait cards, sees them turn in 3D and dresses them (the wardrobe editor,
## wardrobe.gd: colours, hat, pack), then 모험 시작 saves the look (/v1/profile) and the game goes on
## to the first place. main.gd authenticate awaits `done`; only the real game shows it (test
## harnesses add Main to the root directly). A later new hero (credits) is one more card.
signal done(avatar: Dictionary)

const RpgUi = preload("res://scripts/rpg_ui.gd")
const Wardrobe = preload("res://scripts/wardrobe.gd")
const CARDS := [["explorer_b", "여행자", "res://assets/ui/portrait_explorer_b.png"], ["explorer", "루", "res://assets/ui/portrait_explorer.png"],
	["ranger", "미라", "res://assets/ui/portrait_ranger.png"], ["tinker", "테오", "res://assets/ui/portrait_tinker.png"]]

var avatar: Dictionary = {}
var editor: HBoxContainer
var cards: Dictionary = {}

func _ready() -> void:
	name = "CharacterSelect"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var shade := ColorRect.new()
	shade.color = RpgUi.SHADE_IN
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(shade)
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", RpgUi.panel_style("night"))
	card.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	add_child(card)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	card.add_child(column)
	RpgUi.label(column, tr("나의 여행자 만들기"), 26, RpgUi.GOLD)
	RpgUi.caption(column, tr("함께 모험할 여행자를 고르고 꾸며 보세요. 나중에 옷장에서 언제든 바꿀 수 있어요."), 13)
	RpgUi.divider(column, Color(RpgUi.GOLD, .6))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 22)
	column.add_child(row)
	# 1. The travellers on portrait cards.
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 10)
	row.add_child(grid)
	var group := ButtonGroup.new()
	for spec in CARDS:
		var id: String = spec[0]
		var b := Button.new()
		b.name = "Card_" + id
		b.toggle_mode = true
		b.button_group = group
		b.focus_mode = Control.FOCUS_NONE
		b.theme_type_variation = "SlotButton"
		b.custom_minimum_size = Vector2(150, 186)
		var face := TextureRect.new()
		face.texture = load(spec[2]) if ResourceLoader.exists(spec[2]) else null
		face.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		face.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		face.position = Vector2(10, 8)
		face.size = Vector2(130, 140)
		face.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.add_child(face)
		var title := RpgUi.label(b, tr(spec[1]), 17, RpgUi.PAPER_INK, false)
		title.add_theme_font_override("font", RpgUi.FONT_STRONG)
		title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		title.position = Vector2(0, 150)
		title.size = Vector2(150, 28)
		b.pressed.connect(func(): pick(id))
		RpgUi.hover_motion(b, 1.04)
		grid.add_child(b)
		cards[id] = b
	# 2 and 3. The 3D preview and the dressing controls (the wardrobe editor; its own traveller
	# buttons give way to the cards).
	editor = Wardrobe.new()
	editor.avatar = avatar.duplicate(true)
	row.add_child(editor)
	for b in editor.find_children("*", "Button", true, false):
		if b.has_meta("character"): b.get_parent().visible = false
	var start := RpgUi.button(column, tr("모험 시작"), _start, "gold", "lg", true)
	start.name = "Start"
	start.size_flags_horizontal = Control.SIZE_SHRINK_END
	start.custom_minimum_size.x = 260
	var chosen: String = str(editor.avatar.get("character", "explorer_b"))
	if cards.has(chosen): (cards[chosen] as Button).set_pressed_no_signal(true)
	RpgUi.slide_in(card, Vector2(0, 16), 0.3)

## A card: the wardrobe's own traveller key (its colour presets come along).
func pick(id: String) -> void:
	for b in editor.find_children("*", "Button", true, false):
		if b.has_meta("character") and b.get_meta("character") == id: b.pressed.emit()

func _start() -> void:
	RpgUi.sfx("confirm", -6.0)
	done.emit(editor.avatar.duplicate(true))
