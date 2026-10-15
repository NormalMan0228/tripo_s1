extends Control
## The one craft window ("공방 제작 의뢰"), the same in the village and in every room: C (or the 제작
## slot of the hotbar) opens a parchment card over a soft shade, at the same size and place, holding
## the craft form and the craft under way (craft_panel.gd). The session's CraftTracker follows the
## craft, so the window shows the same state wherever it opens and the craft goes on after it closes.
##   var window := CraftWindow.new(); window.setup(self, api); parent.add_child(window)
##   await window.open()
## The place it opens in (main.gd, studio.gd) implements:
##   craft_say(words)              a toast in this place
##   craft_place(object_id)        "여기에 놓기": put the finished object down here (closes the window)
##   craft_place_block() -> String why it cannot be put down here ("" = it can; the bag keeps it)
##   craft_bag_changed()           a craft started, ended or was cancelled (wallet and bag)
##   close_craft()                 close this window with the place's own bookkeeping
const RpgUi = preload("res://scripts/rpg_ui.gd")
const CraftPanel = preload("res://scripts/craft_panel.gd")
const CraftWords = preload("res://scripts/craft_words.gd")
## The card on the 1280x800 design canvas: centred, 92 px from the top, 760 px wide.
const CARD_TOP := 92.0
const CARD_WIDTH := 760.0

var host: Node
var panel: CraftPanel
var card: PanelContainer
var scroll: ScrollContainer
var title: Label
var close_key: Button
## Short lines over the card for what the craft says while the window is open (the place's own
## toast lane sits under the window): the shared toast lane (RpgUi.toast), just above the card.
var note_lane: VBoxContainer

func setup(place: Node, network: Node) -> void:
	host = place
	name = "CraftWindow"
	# The parchment look wherever it opens (a room's own theme is night glass).
	theme = RpgUi.theme()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var shade := TextureRect.new()
	var fall := GradientTexture2D.new()
	fall.fill = GradientTexture2D.FILL_RADIAL
	fall.fill_from = Vector2(0.5, 0.45)
	fall.fill_to = Vector2(1.1, 1.1)
	fall.gradient = Gradient.new()
	fall.gradient.colors = PackedColorArray([Color(0.03, 0.05, 0.06, .55), Color(0.02, 0.03, 0.04, .86)])
	shade.texture = fall
	shade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.name = "Shade"
	add_child(shade)
	shade.modulate.a = 0.0
	card = PanelContainer.new()
	card.name = "Card"
	card.custom_minimum_size.x = CARD_WIDTH
	card.add_theme_stylebox_override("panel", RpgUi.panel_style("paper"))
	# Pinned to the top centre (as RpgUi.pin would in the tree): it grows down with its content.
	card.anchor_left = 0.5
	card.anchor_right = 0.5
	card.offset_left = -CARD_WIDTH * 0.5
	card.offset_right = CARD_WIDTH * 0.5
	card.offset_top = CARD_TOP
	card.offset_bottom = CARD_TOP
	card.grow_horizontal = Control.GROW_DIRECTION_BOTH
	card.grow_vertical = Control.GROW_DIRECTION_END
	add_child(card)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	card.add_child(v)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	v.add_child(row)
	title = Label.new()
	title.text = tr(CraftWords.TITLE)
	title.add_theme_font_size_override("font_size", 27)
	title.add_theme_font_override("font", RpgUi.FONT_DISPLAY)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(title)
	close_key = Button.new()
	close_key.text = tr("닫기 · Esc")
	close_key.custom_minimum_size = Vector2(0, 36)
	close_key.focus_mode = Control.FOCUS_NONE
	close_key.add_theme_font_size_override("font_size", 13)
	RpgUi.hover_motion(close_key, 1.03)
	close_key.pressed.connect(close)
	row.add_child(close_key)
	RpgUi.divider(v)
	# Scrolls only when the window would be taller than the screen (style buttons, picture, quote).
	scroll = ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)
	panel = CraftPanel.new()
	panel.name = "CraftPanel"
	scroll.add_child(panel)
	panel.setup(place, network)
	panel.minimum_size_changed.connect(_fit)
	note_lane = RpgUi.toast_lane(self, CARD_TOP - 50.0, 0.0, CARD_WIDTH - 80.0)
	note_lane.name = "Notes"

func _ready() -> void:
	_fit()
	get_node("Shade").create_tween().tween_property(get_node("Shade"), "modulate:a", 1.0, 0.2)
	RpgUi.pop_in(card)
	RpgUi.sfx("open", -8.0)

## Shows what the session's craft is doing (or the form) and keeps following it.
func open() -> void:
	if panel.tracker == null: return
	panel.tracker.window = self
	panel.tracker.attach(host)
	await panel.open()

func _exit_tree() -> void:
	if panel != null and panel.tracker != null and is_instance_valid(panel.tracker) and panel.tracker.window == self:
		panel.tracker.window = null

## The place closes the window (its modal bookkeeping); a place without one just frees it.
func close() -> void:
	if is_instance_valid(host) and host.has_method("close_craft"): host.close_craft()
	else: queue_free()

## The card grows with its content up to the screen's height, then the content scrolls.
func _fit() -> void:
	if not is_instance_valid(panel) or not is_inside_tree(): return
	var room := maxf(260.0, get_viewport().get_visible_rect().size.y - 230.0)
	scroll.custom_minimum_size.y = minf(panel.get_combined_minimum_size().y, room)

## A short line over the card (the craft accepted, a refusal, the picture is ready), fading out.
## Silent: the place's own toast under the window chimes for the same line.
func note(words: String) -> void:
	if words.is_empty() or not is_instance_valid(note_lane): return
	RpgUi.toast(note_lane, words, "info", {"sound": false})
