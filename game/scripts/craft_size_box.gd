extends VBoxContainer
## The box the player drags in the craft window before a craft goes off: step 1 drags on the floor
## for the width (x) and depth (z), as a rectangle around the grid's centre; step 2 drags up or down
## for the height (y). An isometric floor grid (0.5 m cells, 3 x 3 m) and a 1.7 m person give the
## scale; each side snaps to 5 cm, 0.1..3 m. Mouse and touch both drag (a touch that also arrives as
## an emulated mouse event lands on the same value). craft_panel.gd sends the box as
## StudioRequest.dims [width, height, depth]; the server words the designer and Tripo with it and
## the game scales the finished object by its longest side.
##   var box := CraftSizeBox.new(); parent.add_child(box)
##   box.dims_changed.connect(func(d: Vector3) -> void: ...)   # x width, y height, z depth (m)
##   box.set_dims(Vector3(1.2, 0.9, 0.6))   # a remembered box, shown finished
##   box.value()                            # [1.2, 0.9, 0.6] for the request
##   box.reset()                            # back to step 1 (emits cleared)
const RpgUi = preload("res://scripts/rpg_ui.gd")

## The finished box (after the height drag, and after each later height change).
signal dims_changed(dims: Vector3)
## "다시 정하기": back to step 1 with no box.
signal cleared

const MIN_M := 0.1
const MAX_M := 3.0
const STEP_M := 0.05
const GRID_M := 3.0
const CELL_M := 0.5
const PERSON_M := 1.7
## Where the person stands (outside the grid, at its right corner).
const PERSON_AT := Vector3(1.95, 0, -1.95)
## Isometric axes: x runs down-right, z down-left, y up.
const ISO := Vector2(0.866, 0.5)
## The drawing's extent in metres on screen (left, right, top, bottom) for a 3 m box.
const VIEW := Rect2(-2.65, -4.6, 6.4, 6.35)
const INK_DEEP := Color("8a5a1c")

enum { FLOOR, HEIGHT, DONE }

var step := FLOOR
## The chosen sides (snapped), x width, y height, z depth; zero until dragged.
var dims := Vector3.ZERO
## What is drawn: follows dims smoothly.
var shown := Vector3.ZERO
var canvas: Control
var hint: Label
var sizes: Label
var redo: Button
var dragging := false
var _from_y := 0.0
var _from_h := 0.0
var _scale := 40.0
var _origin := Vector2.ZERO

func _init() -> void:
	add_theme_constant_override("separation", 6)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hint = RpgUi.label(self, "", 14, INK_DEEP, false)
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	canvas = Control.new()
	canvas.custom_minimum_size = Vector2(0, 250)
	canvas.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	canvas.mouse_filter = Control.MOUSE_FILTER_STOP
	canvas.mouse_default_cursor_shape = Control.CURSOR_CROSS
	canvas.clip_contents = true
	canvas.draw.connect(_paint)
	canvas.gui_input.connect(_on_input)
	add_child(canvas)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	add_child(row)
	sizes = RpgUi.label(row, "", 14, RpgUi.PAPER_INK, false)
	sizes.add_theme_font_override("font", RpgUi.FONT_NUMBERS)
	sizes.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sizes.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	redo = RpgUi.button(row, tr("다시 정하기"), reset, "normal", "sm")
	set_process(false)
	_refresh(false)

func _notification(what: int) -> void:
	# Fades in when the size row opens it.
	if what == NOTIFICATION_VISIBILITY_CHANGED and is_visible_in_tree() and not RpgUi.calm():
		modulate.a = 0.0
		create_tween().tween_property(self, "modulate:a", 1.0, 0.18).set_trans(Tween.TRANS_SINE)

## True once both drags are done (the box can be sent).
func has_box() -> bool:
	return step == DONE

## [width, height, depth] in metres for StudioRequest.dims.
func value() -> Array:
	return [snappedf(dims.x, 0.01), snappedf(dims.y, 0.01), snappedf(dims.z, 0.01)]

## A remembered box, shown finished (no signal).
func set_dims(v: Vector3) -> void:
	dims = Vector3(_snap(v.x), _snap(v.y), _snap(v.z))
	shown = dims
	step = DONE
	dragging = false
	_refresh(false)
	canvas.queue_redraw()

func reset() -> void:
	step = FLOOR
	dims = Vector3.ZERO
	dragging = false
	RpgUi.sfx("click")
	_refresh(true)
	set_process(true)
	cleared.emit()

static func _snap(v: float) -> float:
	return clampf(snappedf(v, STEP_M), MIN_M, MAX_M)

# ------------------------------------------------------------------ input

func _on_input(event: InputEvent) -> void:
	var pressed := false
	var at := Vector2.ZERO
	if event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		if button.button_index != MOUSE_BUTTON_LEFT: return
		pressed = button.pressed
		at = button.position
	elif event is InputEventScreenTouch:
		var touch := event as InputEventScreenTouch
		if touch.index != 0: return
		pressed = touch.pressed
		at = touch.position
	elif event is InputEventMouseMotion:
		if dragging:
			_move((event as InputEventMouseMotion).position)
			canvas.accept_event()
		return
	elif event is InputEventScreenDrag:
		var drag := event as InputEventScreenDrag
		if dragging and drag.index == 0:
			_move(drag.position)
			canvas.accept_event()
		return
	else: return
	canvas.accept_event()
	if pressed: _press(at)
	else: _release()

func _press(at: Vector2) -> void:
	_fit()
	dragging = true
	if step == FLOOR:
		_floor(at)
	else:
		_from_y = at.y
		_from_h = dims.y

func _move(at: Vector2) -> void:
	if step == FLOOR: _floor(at)
	else: _apply(Vector3(dims.x, _snap(_from_h + (_from_y - at.y) / _scale), dims.z))

func _release() -> void:
	if not dragging: return
	dragging = false
	if step == FLOOR:
		if dims.x <= 0.0: return
		step = HEIGHT
		dims.y = maxf(dims.y, MIN_M)
		RpgUi.sfx("select")
		_refresh(true)
		set_process(true)
	elif step == HEIGHT:
		step = DONE
		RpgUi.sfx("confirm", -6.0)
		_refresh(true)
		dims_changed.emit(dims)
	else:
		dims_changed.emit(dims)

## The floor point under `at` sets the corner of a rectangle centred on the grid.
func _floor(at: Vector2) -> void:
	var q := (at - _origin) / _scale
	var u := q.x / ISO.x
	var v := q.y / ISO.y
	_apply(Vector3(_snap(absf(u + v)), 0.0, _snap(absf(v - u))))

func _apply(v: Vector3) -> void:
	if v.is_equal_approx(dims): return
	dims = v
	# A soft tick on every 5 cm step (the sound gate keeps fast drags from rattling).
	RpgUi.sfx("snap", -14.0)
	_refresh(false)
	set_process(true)

func _process(delta: float) -> void:
	shown = dims if RpgUi.calm() else shown.lerp(dims, 1.0 - exp(-delta * 18.0))
	if shown.distance_to(dims) < 0.002:
		shown = dims
		set_process(false)
	canvas.queue_redraw()

# ------------------------------------------------------------------ text

func _refresh(new_step: bool) -> void:
	var words: String = [tr("1 바닥을 드래그해 넓이 정하기"), tr("2 위아래로 드래그해 높이 정하기"), tr("크기를 정했어요 · 위아래로 끌면 높이만 바뀌어요")][step]
	if hint.text != words:
		hint.text = words
		if new_step and is_inside_tree() and not RpgUi.calm():
			hint.modulate.a = 0.0
			hint.create_tween().tween_property(hint, "modulate:a", 1.0, 0.22).set_trans(Tween.TRANS_SINE)
	sizes.text = tr("가로 %s · 세로 %s · 높이 %s") % [_m(dims.x), _m(dims.z), _m(dims.y if step != FLOOR else 0.0)] if dims.x > 0.0 else ""
	redo.disabled = step == FLOOR and dims.x <= 0.0

static func _m(v: float) -> String:
	return "%.2fm" % v if v > 0.0 else "—"

# ------------------------------------------------------------------ drawing

func _project(p: Vector3) -> Vector2:
	return _origin + Vector2((p.x - p.z) * ISO.x, (p.x + p.z) * ISO.y - p.y) * _scale

## Fits the drawing (VIEW) into the canvas: metres to pixels and where the grid's centre is.
func _fit() -> void:
	var area := canvas.size
	_scale = maxf(8.0, minf((area.x - 16.0) / VIEW.size.x, (area.y - 12.0) / VIEW.size.y))
	_origin = Vector2((area.x - VIEW.size.x * _scale) * 0.5 - VIEW.position.x * _scale, (area.y - VIEW.size.y * _scale) * 0.5 - VIEW.position.y * _scale)

func _paint() -> void:
	_fit()
	var line := RpgUi.PAPER_LINE
	var half := GRID_M * 0.5
	# The floor: a soft parchment diamond with 0.5 m cells, the metre lines a little stronger.
	var floor_pts := PackedVector2Array([_project(Vector3(-half, 0, -half)), _project(Vector3(half, 0, -half)),
		_project(Vector3(half, 0, half)), _project(Vector3(-half, 0, half))])
	canvas.draw_colored_polygon(floor_pts, Color(line, 0.16))
	var cells := int(GRID_M / CELL_M)
	for i in cells + 1:
		var t := -half + i * CELL_M
		var c := Color(line, 0.85 if i % 2 == 0 else 0.45)
		canvas.draw_line(_project(Vector3(t, 0, -half)), _project(Vector3(t, 0, half)), c, 1.0, true)
		canvas.draw_line(_project(Vector3(-half, 0, t)), _project(Vector3(half, 0, t)), c, 1.0, true)
	_person()
	var w := shown.x * 0.5
	var d := shown.z * 0.5
	var h := shown.y
	if step == FLOOR:
		# Where the rectangle grows from.
		var centre := _project(Vector3.ZERO)
		canvas.draw_arc(centre, 6.0, 0.0, TAU, 20, Color(INK_DEEP, 0.75), 1.5, true)
		canvas.draw_circle(centre, 2.0, INK_DEEP)
	if w < 0.01 or d < 0.01: return
	var amber := RpgUi.AMBER
	var edge := Color(INK_DEEP, 0.95)
	# Its shadow on the floor, the hidden edges faint, then the three faces the camera sees.
	var foot := PackedVector2Array([_project(Vector3(-w, 0, -d)), _project(Vector3(w, 0, -d)), _project(Vector3(w, 0, d)), _project(Vector3(-w, 0, d))])
	canvas.draw_colored_polygon(foot, Color(RpgUi.PAPER_INK, 0.10))
	var back := _project(Vector3(-w, 0, -d))
	for corner in [Vector3(w, 0, -d), Vector3(-w, 0, d), Vector3(-w, h, -d)]:
		canvas.draw_dashed_line(back, _project(corner), Color(edge, 0.35), 1.0, 4.0)
	if h > 0.005:
		canvas.draw_colored_polygon(PackedVector2Array([_project(Vector3(-w, 0, d)), _project(Vector3(w, 0, d)), _project(Vector3(w, h, d)), _project(Vector3(-w, h, d))]), Color(amber.darkened(0.18), 0.62))
		canvas.draw_colored_polygon(PackedVector2Array([_project(Vector3(w, 0, -d)), _project(Vector3(w, 0, d)), _project(Vector3(w, h, d)), _project(Vector3(w, h, -d))]), Color(amber.darkened(0.34), 0.62))
	var top := PackedVector2Array([_project(Vector3(-w, h, -d)), _project(Vector3(w, h, -d)), _project(Vector3(w, h, d)), _project(Vector3(-w, h, d))])
	canvas.draw_colored_polygon(top, Color(amber.lightened(0.25), 0.7))
	top.append(top[0])
	canvas.draw_polyline(top, edge, 2.0, true)
	if h > 0.005:
		for p in [Vector3(-w, 0, d), Vector3(w, 0, d), Vector3(w, 0, -d)]:
			canvas.draw_line(_project(p), _project(p + Vector3(0, h, 0)), edge, 2.0, true)
		canvas.draw_polyline(PackedVector2Array([_project(Vector3(-w, 0, d)), _project(Vector3(w, 0, d)), _project(Vector3(w, 0, -d))]), edge, 2.0, true)
	# The sides on the drawing: width on the front-left edge, depth on the front-right, height on the left.
	_tag(_project(Vector3(0, 0, d)) + Vector2(-6, 14), _m(dims.x), HORIZONTAL_ALIGNMENT_RIGHT)
	_tag(_project(Vector3(w, 0, 0)) + Vector2(6, 14), _m(dims.z), HORIZONTAL_ALIGNMENT_LEFT)
	if step != FLOOR: _tag(_project(Vector3(-w, h * 0.5, d)) + Vector2(-6, 4), _m(dims.y), HORIZONTAL_ALIGNMENT_RIGHT)
	if step == HEIGHT:
		# Up / down chevrons over the lid while the height is being chosen.
		var lid := _project(Vector3(0, h, 0))
		var up := lid + Vector2(0, -16)
		var down := lid + Vector2(0, 10)
		canvas.draw_colored_polygon(PackedVector2Array([up + Vector2(-6, 4), up + Vector2(6, 4), up + Vector2(0, -4)]), INK_DEEP)
		canvas.draw_colored_polygon(PackedVector2Array([down + Vector2(-6, -4), down + Vector2(6, -4), down + Vector2(0, 4)]), INK_DEEP)

## A 1.7 m person beside the grid, for scale.
func _person() -> void:
	var feet := _project(PERSON_AT)
	var s := _scale
	var tone := Color(RpgUi.PAPER_MUTED, 0.55)
	var at := func(x: float, y: float) -> Vector2: return feet + Vector2(x * s, -y * s)
	canvas.draw_circle(at.call(0.0, 1.585), 0.115 * s, tone)
	canvas.draw_colored_polygon(PackedVector2Array([at.call(-0.21, 1.44), at.call(0.21, 1.44), at.call(0.16, 0.86), at.call(-0.16, 0.86)]), tone)
	canvas.draw_colored_polygon(PackedVector2Array([at.call(-0.16, 0.88), at.call(-0.015, 0.88), at.call(-0.04, 0.0), at.call(-0.15, 0.0)]), tone)
	canvas.draw_colored_polygon(PackedVector2Array([at.call(0.015, 0.88), at.call(0.16, 0.88), at.call(0.15, 0.0), at.call(0.04, 0.0)]), tone)
	canvas.draw_colored_polygon(PackedVector2Array([at.call(-0.21, 1.42), at.call(-0.15, 1.40), at.call(-0.24, 0.82), at.call(-0.30, 0.84)]), tone)
	canvas.draw_colored_polygon(PackedVector2Array([at.call(0.15, 1.40), at.call(0.21, 1.42), at.call(0.30, 0.84), at.call(0.24, 0.82)]), tone)
	_tag(at.call(0.0, PERSON_M) + Vector2(0, -6), "1.7m", HORIZONTAL_ALIGNMENT_CENTER, 11, RpgUi.PAPER_MUTED)

func _tag(at: Vector2, text: String, align: HorizontalAlignment, font_size := 12, color := Color(0, 0, 0, 0)) -> void:
	if color.a <= 0.0: color = RpgUi.PAPER_INK
	var font: Font = RpgUi.FONT_NUMBERS
	var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var x := at.x - (width if align == HORIZONTAL_ALIGNMENT_RIGHT else width * 0.5 if align == HORIZONTAL_ALIGNMENT_CENTER else 0.0)
	canvas.draw_string(font, Vector2(x, at.y), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)
