extends PanelContainer
## 모양 바꾸기: the player's own object made wider, deeper or taller, sized up or down and
## mirrored. Every copy on screen (the bag preview, the placed one) follows the sliders
## live; 저장 keeps it on the server (POST /v1/objects/{id}/shape, server/object_shape.py),
## 원래대로 goes back to the made shape, and closing without saving puts the saved shape back.
## The village bag and the room 보관함 open it; object_transform.gd draws the shape.
const RpgUi = preload("res://scripts/rpg_ui.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")
signal saved(shape: Dictionary)
signal closed

var api: Node
var object: Dictionary = {}
## Returns the nodes that show this object now (invalid entries are skipped).
var targets: Callable
var say: Callable
var draft: Dictionary = {}
var stored: Dictionary = {}
var version := 0
var sliders: Dictionary = {}
var values: Dictionary = {}
var mirror_button: Button
var save_button: Button
var reset_button: Button
var size_readout: Label
var busy := false
var syncing := false

static var _theme: Theme

## The night glass of the HUD with the shared gold sliders.
static func panel_theme() -> Theme:
	if _theme: return _theme
	var t := RpgUi.night_theme().duplicate() as Theme
	var shared := RpgUi.theme()
	for item in ["slider", "grabber_area", "grabber_area_highlight"]: t.set_stylebox(item, "HSlider", shared.get_stylebox(item, "HSlider"))
	for item in ["grabber", "grabber_highlight"]: t.set_icon(item, "HSlider", shared.get_icon(item, "HSlider"))
	t.default_font = RpgUi.FONT_BODY
	t.default_font_size = 15
	_theme = t
	return t

func setup(api_node: Node, obj: Dictionary, show_on: Callable, speak: Callable) -> void:
	api = api_node
	object = obj.duplicate(true)
	targets = show_on
	say = speak
	stored = ObjectTransform.shape_of(obj.get("shape"))
	draft = stored.duplicate()
	var listed = obj.get("shape")
	version = int(listed.get("version", 0)) if listed is Dictionary else 0
	name = "ShapePanel"
	theme = panel_theme()
	add_theme_stylebox_override("panel", RpgUi.panel_style("night"))
	custom_minimum_size.x = 324
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	add_child(box)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 8)
	box.add_child(head)
	RpgUi.label(head, tr("모양 바꾸기"), 20, RpgUi.GOLD).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var close_button := Button.new()
	close_button.text = "✕"
	close_button.name = "Close"
	close_button.focus_mode = Control.FOCUS_NONE
	close_button.custom_minimum_size = Vector2(36, 34)
	close_button.tooltip_text = tr("닫기") + " · Esc"
	close_button.pressed.connect(close)
	head.add_child(close_button)
	var title := RpgUi.label(box, str(object.get("name", "")), 13, RpgUi.SOFT, false)
	title.max_lines_visible = 1
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	title.custom_minimum_size.x = 280
	size_readout = RpgUi.numbers(RpgUi.label(box, "", 16, RpgUi.GOLD), 16)
	size_readout.name = "SizeReadout"
	for spec in [["width", tr("가로")], ["depth", tr("깊이")], ["height", tr("높이")], ["scale", tr("전체 크기")]]:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 8)
		box.add_child(row)
		var caption := RpgUi.label(row, spec[1], 14)
		caption.custom_minimum_size.x = 78
		var slider := HSlider.new()
		slider.name = str(spec[0]).capitalize()
		slider.min_value = ObjectTransform.LOWEST
		slider.max_value = ObjectTransform.HIGHEST
		slider.step = 5
		slider.value = draft[spec[0]]
		slider.focus_mode = Control.FOCUS_NONE
		slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		slider.custom_minimum_size = Vector2(140, 22)
		row.add_child(slider)
		var shown := RpgUi.numbers(RpgUi.label(row, "", 15), 15)
		shown.custom_minimum_size.x = 54
		shown.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		var key: String = spec[0]
		sliders[key] = slider
		values[key] = shown
		slider.value_changed.connect(func(value: float): changed(key, value))
		# A double click on the number puts that one slider back to 100%.
		shown.mouse_filter = Control.MOUSE_FILTER_STOP
		shown.tooltip_text = tr("두 번 누르면 100%")
		shown.gui_input.connect(func(event: InputEvent):
			if event is InputEventMouseButton and event.double_click: slider.value = 100)
	mirror_button = Button.new()
	mirror_button.name = "Mirror"
	mirror_button.toggle_mode = true
	mirror_button.focus_mode = Control.FOCUS_NONE
	mirror_button.text = tr("⇆ 좌우 반전")
	mirror_button.custom_minimum_size.y = 38
	mirror_button.button_pressed = bool(draft.mirror)
	mirror_button.toggled.connect(func(on: bool): changed("mirror", on))
	box.add_child(mirror_button)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 8)
	box.add_child(actions)
	reset_button = Button.new()
	reset_button.name = "Reset"
	reset_button.text = tr("원래대로")
	reset_button.focus_mode = Control.FOCUS_NONE
	reset_button.custom_minimum_size = Vector2(108, 42)
	reset_button.pressed.connect(func(): await reset())
	actions.add_child(reset_button)
	save_button = Button.new()
	save_button.name = "Save"
	save_button.text = tr("저장")
	save_button.theme_type_variation = "GoldButton"
	save_button.focus_mode = Control.FOCUS_NONE
	save_button.custom_minimum_size.y = 42
	save_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	save_button.pressed.connect(func(): await save())
	actions.add_child(save_button)
	for b in [close_button, mirror_button, reset_button, save_button]: RpgUi.hover_motion(b, 1.04)
	refresh()
	RpgUi.pop_in(self)
	RpgUi.sfx("open", -8.0)

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		close()

func changed(key: String, value) -> void:
	if syncing: return
	draft[key] = bool(value) if key == "mirror" else int(value)
	refresh()

## Sliders, numbers and every copy on screen follow the draft.
func refresh() -> void:
	for key in ObjectTransform.AXES:
		values[key].text = "%d%%" % int(draft[key])
		values[key].add_theme_color_override("font_color", RpgUi.INK if int(draft[key]) == 100 else Color("ffe08a"))
	mirror_button.add_theme_color_override("font_color", Color("ffe08a") if draft.mirror else RpgUi.INK)
	var size := Vector3.ZERO
	for node in shown():
		ObjectTransform.apply(node, draft)
		if size == Vector3.ZERO: size = node.get_meta("size", Vector3.ZERO)
	size_readout.text = "%.2f × %.2f × %.2f m" % [size.x, size.z, size.y] if size != Vector3.ZERO else ""
	save_button.disabled = busy or ObjectTransform.same(draft, stored)
	reset_button.disabled = busy or (ObjectTransform.is_default(stored) and ObjectTransform.is_default(draft))

func shown() -> Array:
	var out := []
	for node in targets.call():
		if node is Node3D and is_instance_valid(node) and ObjectTransform.frame_of(node) != null: out.append(node)
	return out

func sync_controls() -> void:
	syncing = true
	for key in ObjectTransform.AXES: sliders[key].value = draft[key]
	mirror_button.button_pressed = bool(draft.mirror)
	syncing = false
	refresh()

func save() -> void:
	if busy or ObjectTransform.same(draft, stored): return
	var body := {"version": version}
	for key in ObjectTransform.AXES: body[key] = int(draft[key])
	body.mirror = bool(draft.mirror)
	if await send(body):
		close()

func reset() -> void:
	if busy: return
	if ObjectTransform.is_default(stored):
		# Nothing saved to undo: only the sliders go back.
		draft = ObjectTransform.DEFAULT.duplicate()
		sync_controls()
		return
	draft = ObjectTransform.DEFAULT.duplicate()
	sync_controls()
	await send({"version": version, "reset": true})

func send(body: Dictionary) -> bool:
	busy = true
	refresh()
	var reply: Dictionary = await api.post("/v1/objects/" + str(object.id) + "/shape", api.mutation(body))
	if not is_inside_tree(): return false
	busy = false
	if not reply.ok:
		var words := {"object_is_listed": tr("장터에 올린 물건은 모양을 바꿀 수 없어요."), "stale_shape_version": tr("다른 곳에서 모양이 바뀌었어요. 다시 열어 주세요."), "object_not_found": tr("물건을 찾을 수 없어요.")}
		say.call(words.get(str(reply.error), tr("모양을 저장하지 못했어요.")))
		refresh()
		return false
	stored = ObjectTransform.shape_of(reply.data)
	version = int(reply.data.get("version", version + 1))
	object.shape = reply.data
	draft = stored.duplicate()
	sync_controls()
	celebrate()
	saved.emit(reply.data)
	return true

## A short squash-and-settle on every copy and a chime instead of a sentence.
func celebrate() -> void:
	RpgUi.sfx("confirm", -6.0)
	if RpgUi.calm(): return
	for node in shown():
		var frame := ObjectTransform.frame_of(node)
		var settled := frame.scale
		var tween := frame.create_tween()
		tween.tween_property(frame, "scale", settled * Vector3(1.08, 0.9, 1.08), 0.08).set_trans(Tween.TRANS_SINE)
		tween.tween_property(frame, "scale", settled, 0.32).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)

## Leaves without saving: every copy shows the saved shape again.
func close() -> void:
	if is_queued_for_deletion(): return
	if not ObjectTransform.same(draft, stored):
		draft = stored.duplicate()
		for node in shown(): ObjectTransform.apply(node, stored)
	RpgUi.sfx("close", -10.0)
	closed.emit()
	queue_free()
