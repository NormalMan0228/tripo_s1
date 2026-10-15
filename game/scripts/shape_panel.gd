extends Control
## 모양 바꾸기: the player's own object made wider, deeper or taller, sized up or down and
## mirrored. Every copy on screen (the bag preview, the placed one) follows the sliders
## live; 저장 keeps it on the server (POST /v1/objects/{id}/shape, server/object_shape.py),
## 원래대로 goes back to the made shape, and closing without saving puts the saved shape back.
## The village bag and the room 보관함 open it; object_transform.gd draws the shape.
## It is a night-glass drawer on the window stack (RpgUi.drawer): the close key or Esc (the
## stack's routing in main.gd / studio.gd) leaves it. This node is a full-screen holder that takes
## no clicks; `place` picks the side ({"side":"left","top":128} in rooms, where the bag's own
## preview sits on the right).
const RpgUi = preload("res://scripts/rpg_ui.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")
const WIDTH := 324.0
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
## The drawer's description on the window stack (root, card, head, title, close...).
var window: Dictionary = {}
## Where the drawer goes ({"side", "top"}; setup's `place`).
var side: Dictionary = {}

func setup(api_node: Node, obj: Dictionary, show_on: Callable, speak: Callable, place := {}) -> void:
	api = api_node
	object = obj.duplicate(true)
	targets = show_on
	say = speak
	stored = ObjectTransform.shape_of(obj.get("shape"))
	draft = stored.duplicate()
	var listed = obj.get("shape")
	version = int(listed.get("version", 0)) if listed is Dictionary else 0
	name = "ShapePanel"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	side = place

## The drawer is built once this holder is on screen: it slides in from where the screen's edge
## really is (built off-screen, the slide would end at a zero-sized parent's edge).
func _ready() -> void:
	var place := side
	window = RpgUi.drawer(self, tr("모양 바꾸기"), {"side":str(place.get("side", "right")), "top":float(place.get("top", 20.0)),
		"kind":"night", "width":WIDTH, "action":"", "on_close":close, "id":"shape_panel"})
	var box: VBoxContainer = window.body
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
		# 128: the row fits the 324 px drawer.
		slider.custom_minimum_size = Vector2(128, 22)
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
	mirror_button = RpgUi.button(box, tr("⇆ 좌우 반전"), Callable(), "normal", "md")
	mirror_button.name = "Mirror"
	mirror_button.toggle_mode = true
	mirror_button.button_pressed = bool(draft.mirror)
	mirror_button.toggled.connect(func(on: bool): changed("mirror", on))
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 8)
	box.add_child(actions)
	reset_button = RpgUi.button(actions, tr("원래대로"), func(): await reset(), "normal", "lg")
	reset_button.name = "Reset"
	reset_button.custom_minimum_size.x = 108
	save_button = RpgUi.button(actions, tr("저장"), func(): await save(), "gold", "lg")
	save_button.name = "Save"
	save_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	refresh()

func changed(key: String, value) -> void:
	if syncing: return
	draft[key] = bool(value) if key == "mirror" else int(value)
	refresh()

## Sliders, numbers and every copy on screen follow the draft.
func refresh() -> void:
	for key in ObjectTransform.AXES:
		values[key].text = "%d%%" % int(draft[key])
		values[key].add_theme_color_override("font_color", RpgUi.INK if int(draft[key]) == 100 else RpgUi.HOVER)
	mirror_button.add_theme_color_override("font_color", RpgUi.HOVER if draft.mirror else RpgUi.INK)
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
	# Off the window stack at once (Esc and the next key see the window under it), then gone.
	if is_instance_valid(window.get("root")): (window.root as Node).queue_free()
	queue_free()
