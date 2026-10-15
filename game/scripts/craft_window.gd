extends Control
## The one craft window ("공방 제작 의뢰"), the same in the village and in every room: C (or the 제작
## slot of the hotbar) opens the shared parchment window (RpgUi.window, action "craft": C closes it
## again, Esc always) at the same size and place, holding the craft form and the craft under way
## (craft_panel.gd). The session's CraftTracker follows the craft, so the window shows the same state
## wherever it opens and the craft goes on after it closes.
##   var window := CraftWindow.new(); window.setup(self, api); parent.add_child(window)
##   await window.open()
## The place it opens in (main.gd, studio.gd) implements:
##   craft_say(words)              a toast in this place
##   craft_place(object_id)        "여기에 놓기": put the finished object down here (closes the window)
##   craft_place_block() -> String why it cannot be put down here ("" = it can; the bag keeps it)
##   craft_bag_changed()           a craft started, ended or was cancelled (wallet and bag)
##   close_craft()                 close this window with the place's own bookkeeping
## This node is a full-screen holder that takes no clicks itself: the window (shade, card, head with
## the close key) lives under it and sits on the window stack, and the notes' lane over the card.
const RpgUi = preload("res://scripts/rpg_ui.gd")
const CraftPanel = preload("res://scripts/craft_panel.gd")
const CraftWords = preload("res://scripts/craft_words.gd")
## The card on the 1280x800 design canvas: top centre at RpgUi.WINDOW_TOP (92), the standard width.
const CARD_TOP := 92.0
const CARD_WIDTH := 760.0
## The notes' lane ends this far above the card (the pill's drawn shadow included) and shows at most
## NOTE_MAX notes at once.
const NOTE_GAP := 10.0
const NOTE_MAX := 2

var host: Node
var panel: CraftPanel
## The window's description on the stack (RpgUi.window: root, shade, card, head, title, close...).
var window: Dictionary = {}
var card: PanelContainer
var scroll: ScrollContainer
var title: Label
var close_key: Button
## Short lines over the card for what the craft says while the window is open (the place's own
## toast lane sits under the window): the shared toast lane (RpgUi.toast), growing up from just
## above the card.
var note_lane: VBoxContainer

func setup(place: Node, network: Node) -> void:
	host = place
	name = "CraftWindow"
	# The parchment look wherever it opens (a room's own theme is night glass).
	theme = RpgUi.theme()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	window = RpgUi.window(self, tr(CraftWords.TITLE), {"action":"craft", "width":CARD_WIDTH, "place":"top", "scroll":false,
		"on_close":close, "id":"craft"})
	card = window.card
	title = window.title
	close_key = window.close
	# Scrolls only when the window would be taller than the screen (style buttons, picture, quote).
	scroll = ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	(window.body as Control).add_child(scroll)
	panel = CraftPanel.new()
	panel.name = "CraftPanel"
	scroll.add_child(panel)
	panel.setup(place, network)
	panel.minimum_size_changed.connect(_fit)
	# Its foot sits NOTE_GAP above the card and it stacks upward, so notes never cover the card's
	# title row and close key; two at most (the room above the card holds two one-line pills).
	note_lane = RpgUi.toast_lane(self, CARD_TOP - NOTE_GAP, 0.0, CARD_WIDTH - 80.0, {"grow":"up", "max":NOTE_MAX})
	note_lane.name = "Notes"

func _ready() -> void:
	_fit()

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
