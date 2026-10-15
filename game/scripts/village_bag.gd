extends RefCounted
## The village bag drawer (6, docs/design/UI_0118_KO.md): a header (bag, count, tidy, close), page
## tabs (전체 / 보관 / 배치 / 판매 with counts), a 4-column grid of slots (the furniture icon with
## a dot of the object's colour, a pin when placed, a tag when listed), the chosen object's name and
## state, the colour swatches, an action board with the bag icons (tools/build_ui_kit3.py: 놓기 or
## 회수 by state, 색칠, 모양, 사용, 상호작용,
## 판매 where trading is on) and the gold 새 물건 제작 key. main.gd keeps its ItemList
## (objects_list, hidden) as the selection model: a slot selects its row there and calls
## select_object, so tests and older code that drive objects_list keep working.
const RpgUi = preload("res://scripts/rpg_ui.gd")
const COLUMNS := 4
const SLOT := Vector2(64, 64)
const PAGES := [["all", "전체"], ["inventory", "보관"], ["placed", "배치"], ["listed", "판매"]]
const ICON_FURNITURE := "res://assets/ui/icons/furniture.png"
const ICON_PIN := "res://assets/ui/icons/pin.png"
const ICON_TAG := "res://assets/ui/icons/tag.png"

var app: Node
var count_label: Label
var tabs: HBoxContainer
var grid: GridContainer
var name_label: Label
var state_label: Label
var place_key: Button
var slots: Array = []
var page := "all"
var chosen := -1

## Builds the drawer's insides into `right` (main.gd enter_village) and hands main its pieces.
static func build(main: Node, right: VBoxContainer, close: Callable) -> RefCounted:
	var bag := new()
	bag.app = main
	bag._build(right, close)
	return bag

func _build(right: VBoxContainer, close: Callable) -> void:
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 6)
	right.add_child(head)
	head.add_child(RpgUi.icon("res://assets/ui/bag.svg", 30))
	var title: Label = app.text(head, tr("가방"), 24)
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	count_label = RpgUi.label(head, "", 14, RpgUi.PAPER_MUTED, false)
	count_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	count_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var tidy := Button.new()
	tidy.flat = true
	tidy.icon = load("res://assets/ui/icons/refresh.png")
	tidy.expand_icon = true
	tidy.add_theme_constant_override("icon_max_width", 26)
	tidy.custom_minimum_size = Vector2(30, 30)
	tidy.focus_mode = Control.FOCUS_NONE
	tidy.pressed.connect(app.refresh_inventory)
	RpgUi.hover_motion(tidy, 1.12)
	RpgUi.name_tip(tidy, tr("가방 정리 · 서버에서 다시 받아요"))
	head.add_child(tidy)
	app.close_button(head, close, "I")
	app.rule(right)
	tabs = RpgUi.tab_strip(right, PAGES.map(func(p): return {"id":p[0], "label":tr(p[1])}), func(id: String):
		page = id
		refresh())
	tabs.name = "BagTabs"
	var scroll := ScrollContainer.new()
	scroll.name = "BagScroll"
	scroll.custom_minimum_size = Vector2(0, (SLOT.y + 6) * 3 + 4)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	right.add_child(scroll)
	grid = GridContainer.new()
	grid.name = "BagGrid"
	grid.columns = COLUMNS
	grid.add_theme_constant_override("h_separation", 6)
	grid.add_theme_constant_override("v_separation", 6)
	scroll.add_child(grid)
	# The selection model main.gd and its tests drive (hidden).
	var list := ItemList.new()
	list.visible = false
	list.item_selected.connect(app.select_object)
	right.add_child(list)
	app.objects_list = list
	app.rule(right)
	name_label = app.text(right, tr("물건을 고르세요."), 18)
	name_label.custom_minimum_size.x = 250
	name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	state_label = RpgUi.label(right, "", 13, RpgUi.PAPER_MUTED, false)
	# main.gd writes "name\nstate" here (select_object); the two labels above show it.
	var info := Label.new()
	info.visible = false
	right.add_child(info)
	app.object_info = info
	var palette := HBoxContainer.new()
	palette.add_theme_constant_override("separation", 8)
	palette.alignment = BoxContainer.ALIGNMENT_CENTER
	right.add_child(palette)
	for color in app.COLORS: RpgUi.name_tip(app.swatch(palette, Color(color), func(): app.paint_object(color)), RpgUi.color_name(color))
	app.paint_palette = palette
	app.paint_hint = app.text(right, "", 12)
	app.paint_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	app.paint_hint.custom_minimum_size.x = 250
	app.paint_hint.visible = false
	var board := GridContainer.new()
	board.name = "BagActions"
	board.columns = 3
	board.add_theme_constant_override("h_separation", 6)
	board.add_theme_constant_override("v_separation", 6)
	right.add_child(board)
	place_key = _action(board, tr("놓기"), "pin", place_or_take, "primary")
	app.paint_button = _action(board, tr("색칠"), "paint", app.open_painter)
	app.paint_button.tooltip_text = tr("붓·채우기·그라데이션으로 표면을 직접 칠해요")
	app.shape_button = _action(board, tr("모양"), "resize", app.open_shape_panel)
	app.shape_button.tooltip_text = tr("가로 · 깊이 · 높이 · 크기 · 좌우 반전")
	_action(board, tr("사용"), "use", func(): await app.village_furniture_event(app.selected.get("id", ""), "click")).tooltip_text = tr("놓아 둔 가구를 써 봐요")
	_action(board, tr("상호작용"), "magic", app.open_interactions).tooltip_text = tr("누르거나 다가가면 움직이고 빛나게")
	if app.TRADING_UI_ENABLED:
		_action(board, tr("판매"), "tag", app.sell_object)
		var sell_row := HBoxContainer.new()
		right.add_child(sell_row)
		RpgUi.label(sell_row, tr("값"), 14, RpgUi.PAPER_MUTED, false)
		app.price = SpinBox.new()
		app.price.min_value = 1
		app.price.max_value = 10000
		app.price.value = 25
		app.price.custom_minimum_size.x = 115
		sell_row.add_child(app.price)
	var craft: Button = app.button(right, tr("새 물건 제작 의뢰"), app.open_craft, "gold")
	craft.custom_minimum_size.y = 46
	RpgUi.name_tip(craft, tr("새 물건 제작 의뢰"), RpgUi.key_text("craft"))
	app.prompt = LineEdit.new()
	app.prompt.max_length = 500
	app.prompt.visible = false # Retained for legacy integration/recovery, outside the player flow.
	right.add_child(app.prompt)
	RpgUi.select_tab(tabs, "all")

func _action(board: GridContainer, label: String, icon: String, callback: Callable, kind := "default") -> Button:
	var b: Button = app.button(board, label, callback, kind)
	b.custom_minimum_size = Vector2(88, 40)
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var path := "res://assets/ui/icons/%s.png" % icon
	if not icon.is_empty() and ResourceLoader.exists(path):
		b.icon = load(path)
		b.expand_icon = true
		b.add_theme_constant_override("icon_max_width", 22)
	return b

## 놓기 for a stored object, 회수 for a placed one (main.gd begin_place / retrieve_object).
func place_or_take() -> void:
	if app.selected.is_empty(): return
	if str(app.selected.get("state", "")) == "placed": await app.retrieve_object()
	else: app.begin_place()

## Slots for the objects on the current page, in the bag's order; tab labels carry the counts.
func refresh() -> void:
	if not is_instance_valid(grid): return
	var objects: Array = app.me.get("objects", [])
	count_label.text = tr("%d개") % objects.size()
	var buttons: Dictionary = tabs.get_meta("buttons", {})
	for p in PAGES:
		if buttons.has(p[0]):
			var n := objects.size() if p[0] == "all" else objects.filter(func(o): return str(o.get("state", "")) == p[0]).size()
			(buttons[p[0]] as Button).text = "%s %d" % [tr(p[1]), n]
	for child in grid.get_children():
		grid.remove_child(child)
		child.queue_free()
	slots.clear()
	for index in objects.size():
		var obj: Dictionary = objects[index]
		if page != "all" and str(obj.get("state", "")) != page: continue
		slots.append(_slot(index, obj))
	# Empty slots fill the last row and at least three rows, like a real bag.
	var shown := slots.size()
	var total := maxi(COLUMNS * 3, int(ceil(shown / float(COLUMNS))) * COLUMNS)
	for i in total - shown:
		var empty := Panel.new()
		empty.custom_minimum_size = SLOT
		empty.theme_type_variation = "SlotButton"
		empty.modulate = Color(1, 1, 1, 0.55)
		empty.mouse_filter = Control.MOUSE_FILTER_IGNORE
		grid.add_child(empty)
	mark(chosen)

func _slot(index: int, obj: Dictionary) -> Button:
	var slot := Button.new()
	slot.name = "Slot_%d" % index
	slot.custom_minimum_size = SLOT
	slot.focus_mode = Control.FOCUS_NONE
	slot.theme_type_variation = "SlotButton"
	slot.toggle_mode = true
	slot.set_meta("index", index)
	RpgUi.hover_motion(slot, 1.06)
	var state := str(obj.get("state", ""))
	RpgUi.name_tip(slot, str(obj.get("name", "")), {"inventory":tr("보관 중"), "placed":tr("배치됨"), "listed":tr("판매 중")}.get(state, ""))
	slot.pressed.connect(func():
		app.objects_list.select(index)
		app.select_object(index))
	grid.add_child(slot)
	var art := TextureRect.new()
	art.texture = load(ICON_FURNITURE) if ResourceLoader.exists(ICON_FURNITURE) else RpgUi.icon_texture("chest")
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.position = Vector2(8, 8)
	art.size = SLOT - Vector2(16, 16)
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	slot.add_child(art)
	# The object's own colour as a dot in the corner.
	if Color.html_is_valid(str(obj.get("color", ""))):
		var dot := Panel.new()
		var dot_style := StyleBoxFlat.new()
		dot_style.bg_color = Color(str(obj.color))
		dot_style.set_corner_radius_all(7)
		dot_style.border_color = RpgUi.PAPER_INK
		dot_style.set_border_width_all(2)
		dot.add_theme_stylebox_override("panel", dot_style)
		dot.position = Vector2(4, SLOT.y - 18)
		dot.size = Vector2(14, 14)
		dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
		slot.add_child(dot)
	var badge_path := ICON_PIN if state == "placed" else (ICON_TAG if state == "listed" else "")
	if not badge_path.is_empty() and ResourceLoader.exists(badge_path):
		var badge := TextureRect.new()
		badge.texture = load(badge_path)
		badge.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		badge.position = Vector2(SLOT.x - 24, 2)
		badge.size = Vector2(22, 22)
		badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
		slot.add_child(badge)
	return slot

## Lights the chosen slot and fits the board to the object (main.gd select_object calls it).
func mark(index: int) -> void:
	chosen = index
	for slot in slots:
		if is_instance_valid(slot): (slot as Button).set_pressed_no_signal(int(slot.get_meta("index")) == index)
	var has: bool = index >= 0 and index < app.me.get("objects", []).size()
	var obj: Dictionary = app.me.objects[index] if has else {}
	name_label.text = str(obj.get("name", tr("물건을 고르세요.")))
	var lines: PackedStringArray = str(app.object_info.text).split("\n")
	state_label.text = lines[1] if has and lines.size() > 1 else ""
	place_key.text = tr("회수") if str(obj.get("state", "")) == "placed" else tr("놓기")
	place_key.disabled = not has or str(obj.get("state", "")) == "listed"
