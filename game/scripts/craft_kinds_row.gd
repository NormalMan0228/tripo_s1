extends VBoxContainer
## The craft window's "기능" row (craft_panel.gd): "자동" (the server guesses the kind from the words)
## and one chip per kind the server lets the player pick (/v1/studio "kinds", server/craft_kinds.py):
## a type whose finished object really does something (sit, light up, open...). The chosen chip turns
## gold; its tooltip says what the object does and the size rule. Each craft starts on "자동" again.

const RpgUi = preload("res://scripts/rpg_ui.gd")
const I18n = preload("res://scripts/i18n.gd")

signal picked(id: String)

## The server's icon ids and the game's icons (assets/ui); a kind without one shows its first letter
## on a small gold seal.
const ICONS := {"chest": "chest", "clock": "clock", "lantern": "fire", "plant": "leaf", "music": "sound",
	"cabinet": "wardrobe", "drawer": "bag", "door": "home"}
const ICON_SIZE := 22

var kinds: Array = []
var chosen := ""
var buttons := {}
var flow: HFlowContainer

func _init() -> void:
	add_theme_constant_override("separation", 6)
	visible = false
	var title := RpgUi.label(self, tr("기능"), 15, RpgUi.PAPER_INK, false)
	title.tooltip_text = tr("완성된 물건이 할 일을 골라요. 자동이면 설명을 읽고 정해요.")
	title.mouse_filter = Control.MOUSE_FILTER_PASS
	flow = HFlowContainer.new()
	flow.add_theme_constant_override("h_separation", 6)
	flow.add_theme_constant_override("v_separation", 6)
	add_child(flow)

## The server's list (once; a changed list rebuilds the chips). Hidden when the server offers none.
func setup(list: Array) -> void:
	var ids := list.map(func(entry) -> String: return str(entry.get("id", "")) if entry is Dictionary else "")
	if ids == kinds.map(func(entry) -> String: return str(entry.get("id", ""))): return
	kinds = list.filter(func(entry) -> bool: return entry is Dictionary and not str(entry.get("id", "")).is_empty())
	for child in flow.get_children(): child.queue_free()
	buttons = {}
	visible = not kinds.is_empty()
	if kinds.is_empty():
		chosen = ""
		return
	var group := ButtonGroup.new()
	buttons[""] = _chip(group, "", tr("자동"), null, tr("자동").left(1))
	buttons[""].tooltip_text = tr("설명을 읽고 공방이 알맞은 기능을 정해요.")
	for entry in kinds:
		var id := str(entry.id)
		var path := "res://assets/ui/%s.svg" % ICONS.get(str(entry.get("icon", "")), "")
		var texture: Texture2D = RpgUi.icon_texture(path) if ICONS.has(str(entry.get("icon", ""))) else null
		var b := _chip(group, id, text_of(entry, "names"), texture, text_of(entry, "names").left(1))
		b.tooltip_text = "%s\n%s" % [text_of(entry, "does"), text_of(entry, "hint")]
		buttons[id] = b
	if not buttons.has(chosen): chosen = ""
	_show()

## A chip: the icon (or a seal with `glyph`) and the name, on a toggle button of the shared look.
func _chip(group: ButtonGroup, id: String, title: String, texture: Texture2D, glyph: String) -> Button:
	var b := Button.new()
	b.toggle_mode = true
	b.button_group = group
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size.y = 38
	b.set_meta("kind", id)
	var box := HBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	b.add_child(box)
	if texture != null:
		var image := TextureRect.new()
		image.texture = texture
		image.custom_minimum_size = Vector2(ICON_SIZE, ICON_SIZE)
		image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		image.mouse_filter = Control.MOUSE_FILTER_IGNORE
		box.add_child(image)
	else:
		var seal := PanelContainer.new()
		seal.mouse_filter = Control.MOUSE_FILTER_IGNORE
		seal.custom_minimum_size = Vector2(ICON_SIZE, ICON_SIZE)
		seal.add_theme_stylebox_override("panel", RpgUi.style(Color(RpgUi.GOLD, 0.85), ICON_SIZE / 2, RpgUi.PAPER_LINE, 1))
		box.add_child(seal)
		var letter := RpgUi.label(seal, glyph, 12, RpgUi.PAPER_INK, false)
		letter.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		letter.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		letter.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var label := RpgUi.label(box, title, 14, RpgUi.PAPER_INK, false)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.pressed.connect(func() -> void: pick(id))
	RpgUi.hover_motion(b, 1.03)
	flow.add_child(b)
	# The chip is as wide as its icon and name (the box is laid over the button, not inside its text).
	var fit := func() -> void:
		if not is_instance_valid(box): return
		var need := box.get_combined_minimum_size()
		b.custom_minimum_size = Vector2(need.x + 24, maxf(38.0, need.y + 10))
		box.position = Vector2(12, (b.size.y - need.y) * 0.5)
		box.size = Vector2(b.size.x - 24, need.y)
	b.resized.connect(fit)
	fit.call_deferred()
	return b

## The player picked a chip ("" = 자동).
func pick(id: String) -> void:
	if not buttons.has(id): return
	var changed := id != chosen
	chosen = id
	_show()
	RpgUi.sfx("select")
	if changed: picked.emit(id)

## Back to 자동 after a craft (no sound).
func reset() -> void:
	chosen = ""
	_show()

## Whether the server lets the player pick (the request may carry archetype).
func offered() -> bool:
	return not kinds.is_empty()

func entry(id: String) -> Dictionary:
	for e in kinds:
		if str(e.get("id", "")) == id: return e
	return {}

## What the form needs of the picked kind, shaped like POST /v1/studio/kind's answer ({} for 자동).
func kind_info() -> Dictionary:
	var e := entry(chosen)
	if e.is_empty(): return {}
	return {"archetype": chosen, "names": e.get("names", {}), "always_moving": bool(e.get("always_moving", false)),
		"moving_meshes": int(e.get("moving_meshes", 2)), "rest": str(e.get("rest", "")), "needs_moving": bool(e.get("needs_moving", false))}

## A {ko, en, zh} field in the game's language.
static func text_of(e: Dictionary, key: String) -> String:
	var words = e.get(key, {})
	if not words is Dictionary: return str(words)
	return str(words.get(I18n.language(), words.get("ko", e.get("id", ""))))

func _show() -> void:
	for key in buttons:
		var b: Button = buttons[key]
		b.set_pressed_no_signal(key == chosen)
		b.theme_type_variation = "GoldButton" if key == chosen else ""
