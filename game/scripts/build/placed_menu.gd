extends PanelContainer
## The small menu over a placed object (right click in the village or a room): move, turn,
## paint, put away. It floats above the object, follows it on screen and closes on Esc, on a
## click anywhere else, when the object goes away or when the walker strays far from it.
##
## Hosts (village_build.gd, room_build.gd) pass the entries and one callback; the menu only
## shows them and answers with the chosen id.
const RpgUi = preload("res://scripts/rpg_ui.gd")
## Each entry: {"id", "text", "icon" (assets/ui name) or "glyph" (a big character), "tip",
## "danger" (red look), "disabled" (reason shown as the tooltip)}.
const ENTRIES := [
	{"id":"move","text":"옮기기","icon":"craft","tip":"자리를 옮기고 방향도 바꿔요"},
	{"id":"turn","text":"돌리기","glyph":"↷","tip":"그 자리에서 90° 돌려요"},
	{"id":"paint","text":"색칠","swatch":true,"tip":"색이나 무늬를 칠해요"},
	{"id":"store","text":"넣기","icon":"bag","tip":"가방(보관함)으로 거둬들여요","danger":true},
]
const SWATCH := [Color("e86a5a"),Color("f2c14e"),Color("6cc08b"),Color("5b8fd9")]
## Close when the object is this far (metres) from the walker, when a walker is given.
const STRAY := 9.0

var camera: Camera3D
var item: Node3D
var walker: Node3D
var pick: Callable
var closing := false

static func open(host: Control, view_camera: Camera3D, target: Node3D, title: String, on_pick: Callable, opts := {}) -> Control:
	var menu = load("res://scripts/build/placed_menu.gd").new()
	menu.setup(view_camera,target,title,on_pick,opts)
	host.add_child(menu)
	menu.follow()
	RpgUi.pop_in(menu,0.2,0.86)
	RpgUi.sfx("click",-8.0)
	return menu

func setup(view_camera: Camera3D, target: Node3D, title: String, on_pick: Callable, opts: Dictionary) -> void:
	camera=view_camera;item=target;pick=on_pick
	walker=opts.get("walker")
	name="PlacedMenu"
	theme=RpgUi.night_theme()
	mouse_filter=Control.MOUSE_FILTER_STOP
	var chip := RpgUi.panel_style("pill")
	chip.content_margin_left=16;chip.content_margin_right=16;chip.content_margin_top=8;chip.content_margin_bottom=10
	add_theme_stylebox_override("panel",chip)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation",4)
	add_child(column)
	var head := RpgUi.label(column,title,13,RpgUi.GOLD)
	head.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	head.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
	head.custom_minimum_size.x=10
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation",6)
	row.alignment=BoxContainer.ALIGNMENT_CENTER
	column.add_child(row)
	var off: Dictionary=opts.get("disabled",{})
	for entry in ENTRIES:
		if entry.id in opts.get("hide",[]): continue
		row.add_child(_slot(entry,str(off.get(entry.id,""))))

## One round slot: a picture over a word. A disabled slot stays visible, greyed, with its reason.
func _slot(entry: Dictionary, reason: String) -> Control:
	var b := Button.new()
	b.name=str(entry.id).capitalize()
	b.custom_minimum_size=Vector2(64,66)
	b.focus_mode=Control.FOCUS_NONE
	b.theme_type_variation="DangerButton" if entry.get("danger",false) else "NightButton"
	b.tooltip_text=tr(reason) if not reason.is_empty() else tr(str(entry.tip))
	b.disabled=not reason.is_empty()
	var stack := VBoxContainer.new()
	stack.mouse_filter=Control.MOUSE_FILTER_IGNORE
	stack.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	stack.alignment=BoxContainer.ALIGNMENT_CENTER
	stack.add_theme_constant_override("separation",0)
	b.add_child(stack)
	var picture := CenterContainer.new()
	picture.mouse_filter=Control.MOUSE_FILTER_IGNORE
	picture.custom_minimum_size=Vector2(0,34)
	stack.add_child(picture)
	if entry.has("icon"):
		picture.add_child(RpgUi.icon("res://assets/ui/%s.svg" % entry.icon,30))
	elif entry.get("swatch",false):
		picture.add_child(_palette())
	else:
		var glyph := RpgUi.label(picture,str(entry.glyph),26,RpgUi.INK)
		glyph.mouse_filter=Control.MOUSE_FILTER_IGNORE
	var word := RpgUi.label(stack,tr(str(entry.text)),12,RpgUi.SOFT if b.disabled else RpgUi.INK)
	word.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	word.mouse_filter=Control.MOUSE_FILTER_IGNORE
	if b.disabled: stack.modulate=Color(1,1,1,0.45)
	RpgUi.hover_motion(b,1.06)
	var id: String=entry.id
	b.pressed.connect(func(): choose(id))
	return b

## Four paint dots in a little fan: the paint slot's picture.
func _palette() -> Control:
	var fan := Control.new()
	fan.custom_minimum_size=Vector2(32,30)
	fan.mouse_filter=Control.MOUSE_FILTER_IGNORE
	for i in SWATCH.size():
		var dot := Panel.new()
		dot.mouse_filter=Control.MOUSE_FILTER_IGNORE
		var look := StyleBoxFlat.new()
		look.bg_color=SWATCH[i];look.set_corner_radius_all(8)
		look.border_color=Color(0.1,0.07,0.04,0.9);look.set_border_width_all(2)
		dot.add_theme_stylebox_override("panel",look)
		dot.size=Vector2(15,15)
		dot.position=Vector2(2+i*5.5,13-absf(1.5-i)*4.0)
		fan.add_child(dot)
	return fan

func choose(id: String) -> void:
	if closing: return
	var callback := pick
	close()
	if callback.is_valid(): callback.call(id)

func close(sound := false) -> void:
	if closing: return
	closing=true
	if sound: RpgUi.sfx("cancel",-10.0)
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	var t := create_tween()
	t.tween_property(self,"modulate:a",0.0,0.12)
	t.tween_callback(queue_free)

## Above the object's top, kept on screen.
func follow() -> void:
	if not is_instance_valid(item) or not is_instance_valid(camera): return
	var span: Vector3=item.get_meta("size",Vector3.ONE)
	var top: Vector3=item.global_position+Vector3(0,span.y+0.25,0)
	if camera.is_position_behind(top): return
	var spot: Vector2=camera.unproject_position(top)
	# The 3D view may render at another size than the UI it sits in (rooms scale their view).
	var view := camera.get_viewport()
	var canvas: Vector2=get_parent_area_size() if get_parent() is Control else Vector2(view.get_visible_rect().size)
	var ratio: Vector2=canvas/Vector2(view.get_visible_rect().size).max(Vector2.ONE)
	var at: Vector2=spot*ratio-Vector2(size.x*0.5,size.y+6)
	position=at.clamp(Vector2(8,8),(canvas-size-Vector2(8,8)).max(Vector2(8,8)))
	pivot_offset=Vector2(size.x*0.5,size.y)

func _process(_delta: float) -> void:
	if closing: return
	if not is_instance_valid(item) or not item.is_inside_tree() or not item.visible or not is_instance_valid(camera):
		close();return
	if is_instance_valid(walker) and walker.global_position.distance_to(item.global_position)>STRAY:
		close(true);return
	follow()

## Esc closes the menu before the scene's own Esc (pause menu, leaving placement) sees it.
func _shortcut_input(event: InputEvent) -> void:
	if closing: return
	if event is InputEventKey and event.pressed and not event.echo and event.keycode==KEY_ESCAPE:
		close(true)
		get_viewport().set_input_as_handled()

## A click outside the menu closes it (rooms' 3D view is a GUI control, so this looks before the
## GUI does); the click still goes on to whatever it was meant for.
func _input(event: InputEvent) -> void:
	if closing: return
	if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_LEFT,MOUSE_BUTTON_RIGHT]:
		if not get_global_rect().has_point(event.position): close()
