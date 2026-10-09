extends RefCounted
## Turning and reshaping the player's objects wherever they stand (village, rooms, visits).
##
## Turning: any whole degree 0..359 (server: ObjectEdit / Placement rotation). R turns 15°,
## Shift+R back; with Alt or Ctrl held a single degree. The mouse wheel turns 5° and the
## on-screen arrows 15°. ↶ (and R, wheel up) is counter-clockwise seen from above.
##
## Shape (server/object_shape.py): width, depth, height and overall size in whole percent
## (50..200) and a left-right mirror. apply() scales the model's frame ("ShapeFrame", the
## node that already fits and grounds the model) from the size it was built with, so the
## root keeps its spot and turn, the object stays on the floor and the size meta, collision
## and footprints follow. Painted textures follow the surface (UVs), so they stay in place.
const RpgUi = preload("res://scripts/rpg_ui.gd")
const KEY_STEP := 15
const FINE_STEP := 1
const WHEEL_STEP := 5
const BUTTON_STEP := 15
const LOWEST := 50
const HIGHEST := 200
const AXES := ["width", "depth", "height", "scale"]
const DEFAULT := {"width": 100, "depth": 100, "height": 100, "scale": 100, "mirror": false}

# ------------------------------------------------------------------ turning

static func wrap_degrees(degrees: float) -> int:
	return posmod(int(roundf(degrees)), 360)

## Degrees one R press turns: 15, a single degree with Alt or Ctrl; Shift turns back.
static func key_turn(event: InputEventKey) -> int:
	var step := FINE_STEP if event.alt_pressed or event.ctrl_pressed else KEY_STEP
	return -step if event.shift_pressed else step

## Degrees a wheel notch turns (0 for other buttons).
static func wheel_turn(event: InputEventMouseButton) -> int:
	match event.button_index:
		MOUSE_BUTTON_WHEEL_UP: return WHEEL_STEP
		MOUSE_BUTTON_WHEEL_DOWN: return -WHEEL_STEP
	return 0

## Eases a shown yaw toward the chosen angle (radians), the short way round.
static func ease_yaw(current: float, degrees: int, delta: float) -> float:
	var target := deg_to_rad(float(degrees))
	if absf(angle_difference(current, target)) < 0.002: return target
	return lerp_angle(current, target, 1.0 - exp(-delta * 22.0))

## ↶  37°  ↷ : on-screen turn arrows around the angle readout. Returns the readout.
static func turn_bar(parent: Node, turn: Callable) -> Label:
	var row := HBoxContainer.new()
	row.name = "TurnBar"
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 6)
	parent.add_child(row)
	var readout: Label
	for spec in [["↶", BUTTON_STEP, "%s · R"], ["", 0, ""], ["↷", -BUTTON_STEP, "%s · Shift+R"]]:
		if spec[0] == "":
			readout = RpgUi.numbers(RpgUi.label(row, "0°", 18, RpgUi.GOLD), 18)
			readout.name = "Angle"
			readout.custom_minimum_size.x = 58
			readout.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			continue
		var arrow := Button.new()
		arrow.text = spec[0]
		arrow.focus_mode = Control.FOCUS_NONE
		arrow.custom_minimum_size = Vector2(44, 38)
		arrow.add_theme_font_size_override("font_size", 20)
		arrow.tooltip_text = spec[2] % TranslationServer.translate("돌리기")
		var degrees: int = spec[1]
		arrow.pressed.connect(func(): turn.call(degrees))
		RpgUi.hover_motion(arrow, 1.08)
		row.add_child(arrow)
	return readout

static func show_angle(readout: Label, degrees: int) -> void:
	if is_instance_valid(readout): readout.text = "%d°" % wrap_degrees(degrees)

# ------------------------------------------------------------------ shape

## A clean copy of a listed shape (null or missing values are the made shape).
static func shape_of(value) -> Dictionary:
	var out := DEFAULT.duplicate()
	if value is Dictionary:
		for key in AXES: out[key] = clampi(int(value.get(key, 100)), LOWEST, HIGHEST)
		out.mirror = bool(value.get("mirror", false))
	return out

static func is_default(value) -> bool:
	return shape_of(value) == DEFAULT

static func same(a, b) -> bool:
	return shape_of(a) == shape_of(b)

## Per-axis multipliers (x carries the mirror's sign).
static func factors(value) -> Vector3:
	var s := shape_of(value)
	var overall := float(s.scale) / 100.0
	return Vector3(float(s.width) / 100.0 * (-1.0 if s.mirror else 1.0), float(s.height) / 100.0, float(s.depth) / 100.0) * overall

static func frame_of(root: Node3D) -> Node3D:
	if not is_instance_valid(root): return null
	# Crafted objects keep it under their whole-object motion node (asset_assembly.gd whole_root).
	var frame := root.get_node_or_null("ShapeFrame") as Node3D
	return frame if frame != null else root.get_node_or_null("Whole/ShapeFrame") as Node3D

## The size the model was built with, before any shape.
static func base_size(root: Node3D) -> Vector3:
	if root.has_meta("shape_base"): return root.get_meta("shape_base").size
	return root.get_meta("size", Vector3.ONE)

## Shows a shape on a loaded model (and its collision box); cheap enough for live sliders.
static func apply(root: Node3D, value) -> void:
	var frame := frame_of(root)
	if frame == null: return
	if not root.has_meta("shape_base"):
		root.set_meta("shape_base", {"scale": frame.scale, "position": frame.position, "size": root.get_meta("size", Vector3.ONE)})
	var base: Dictionary = root.get_meta("shape_base")
	var k := factors(value)
	frame.scale = base.scale * k
	# The frame's offset centres and grounds the model; it scales with it.
	frame.position = base.position * k
	var size: Vector3 = base.size * k.abs()
	root.set_meta("size", size)
	root.set_meta("shape", shape_of(value))
	for body in root.get_children():
		if not body is StaticBody3D: continue
		for child in body.get_children():
			if child is CollisionShape3D and child.shape is BoxShape3D:
				(child.shape as BoxShape3D).size = size
				child.position.y = size.y * 0.5

## Half the floor footprint (x, z) of a size turned by `degrees`.
static func footprint_half(size: Vector3, degrees: float) -> Vector2:
	var c := absf(cos(deg_to_rad(degrees)))
	var s := absf(sin(deg_to_rad(degrees)))
	return Vector2(size.x * c + size.z * s, size.x * s + size.z * c) * 0.5

## The floor directions (x, z) of a model's own x and z axes after a yaw.
static func floor_axes(degrees: float) -> Array:
	var r := deg_to_rad(degrees)
	return [Vector2(cos(r), -sin(r)), Vector2(sin(r), cos(r))]

## Whether two turned floor rectangles (centre, size along their own x/z, yaw) overlap;
## edges that only touch do not count.
static func footprints_overlap(a: Vector2, a_size: Vector2, a_degrees: float, b: Vector2, b_size: Vector2, b_degrees: float) -> bool:
	var ua := floor_axes(a_degrees)
	var ub := floor_axes(b_degrees)
	for axis in ua + ub:
		var ra: float = a_size.x * 0.5 * absf(ua[0].dot(axis)) + a_size.y * 0.5 * absf(ua[1].dot(axis))
		var rb: float = b_size.x * 0.5 * absf(ub[0].dot(axis)) + b_size.y * 0.5 * absf(ub[1].dot(axis))
		if absf((b - a).dot(axis)) >= ra + rb - 0.02: return false
	return true
