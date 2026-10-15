extends RefCounted
## Village building front doors that open, made from the buildings themselves: tools/door_leaves.gd
## copied each Town.DOORS door's own faces out of its Tripo building GLB (outline, texcoords, normals
## kept) and made them a solid leaf THICKNESS deep (doors/<model>.res). The same leaf is the room's
## front door inside (interiors.gd front()): one door design, outside and in.
## On a building (children of Buildings/<id>, made by install(); nothing collides, so walkability and
## the map's points stay as they were):
##   DoorLeaf      Node3D, the hinge: its origin on the door's right-hand edge seen from outside, at
##                 the threshold. Rotates about its local +Y: rotation.y 0 closed, +OPEN_DEGREES open
##                 (outward). Child "Mesh": the leaf, drawn with the building's exterior material.
##   DoorOpening   MeshInstance3D, the dark doorway just in front of the painted door, hidden behind
##                 the closed leaf; material_override's `inner_light` (0..1) lights it from inside.
## API (static): door_ids(), door_leaf(id), door_opening(id), set_door_open(id, amount) (0 closed ..
## 1 open, at once: callers tween), door_open(id), leaf_mesh(id) / opening_mesh(id) (the resources).
## Docs for the 집·문·방문 session: docs/coordination/DOOR_HOOKS_KO.md.
const RECTS := "res://maps/archipelago/door_leaves.json"
const DOORS_DIR := "res://maps/archipelago/doors/"
const LEAF := "DoorLeaf"
const OPENING := "DoorOpening"
## How far a fully open door swings out (the room's front door opens as far: interiors.gd).
const OPEN_DEGREES := 108.0
## The closed leaf lies this far in front of the painted door, the opening between the two.
const LEAF_LIFT := 0.006
const OPENING_LIFT := 0.002
## Buildings whose door is made this way so far (a test before all of them: the rest keep their painted
## door). ALL_DOORS true applies it to every door in door_leaves.json.
const ENABLED := ["10_red_house"]
const ALL_DOORS := false
## Doors tools/door_leaves.gd cannot find by their wood paint: id -> [across from the door point, height
## above the pad, width, height, arch rise] in metres on the wall (the top `rise` a half ellipse). The
## cafe's glazed double door, the observatory's door half behind a column, the greenhouse's green
## glazed doors; the town hall (workshop) and the shop have open fronts (no painted door).
const RECT_OVERRIDES := {
	"01_cafe": [-0.62, 0.4, 1.72, 2.6, 0.55],
	"05_observatory": [0.3, 1.13, 1.3, 1.95, 0.0],
	"07_greenhouse": [-0.95, 0.6, 1.9, 2.0, 0.0],
	"09_town_hall": [-0.73, 1.13, 2.0, 2.1, 0.0],
	"13_shop": [-0.5, 0.45, 1.0, 1.9, 0.0],
}
const OPENING_SHADER := """
shader_type spatial;
render_mode unshaded, cull_back, shadows_disabled;
// 0: nobody home, a dark doorway; 1: a lit room behind it (the 집·문·방문 session drives this).
uniform float inner_light : hint_range(0.0, 1.0) = 0.0;
uniform vec3 light_color : source_color = vec3(1.0, 0.74, 0.44);
uniform vec3 dark_color : source_color = vec3(0.045, 0.036, 0.03);
void fragment() {
	float up = 1.0-UV.y;
	// Jambs and lintel in shadow: the doorway reads as a recess, not a painted shape.
	float edge = smoothstep(0.0, 0.22, min(UV.x, 1.0-UV.x))*smoothstep(0.0, 0.08, 1.0-up);
	vec3 dark = dark_color*mix(0.55, 1.0, edge)*mix(1.25, 0.8, up);
	// Room light: strongest low in the middle (light on the floor), fading up and to the jambs.
	vec3 lit = light_color*mix(0.35, 1.35, edge)*mix(1.2, 0.45, up);
	ALBEDO = mix(dark, lit, clamp(inner_light, 0.0, 1.0));
}
"""

## --no-doors: every building and room keeps the painted door / box door it had (comparisons).
static var disabled := "--no-doors" in OS.get_cmdline_user_args()
static var _table: Dictionary = {}
static var _buildings: Dictionary = {}
static var _opening_shader: Shader

## door_leaves.json: {id: {model, mesh, opening, origin, out, side, left, bottom, width, height, front, ...}}.
static func table() -> Dictionary:
	if _table.is_empty() and FileAccess.file_exists(RECTS):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(RECTS))
		if parsed is Dictionary: _table = parsed
	return _table

static func enabled(id: String) -> bool:
	return not disabled and table().has(id) and (ALL_DOORS or ENABLED.has(id))

## The door leaf of a building (shared by every building with the same model), or null.
static func leaf_mesh(id: String) -> ArrayMesh:
	if not enabled(id): return null
	var path := String(table()[id].get("mesh", ""))
	return load(path) as ArrayMesh if ResourceLoader.exists(path) else null

static func opening_mesh(id: String) -> ArrayMesh:
	if not enabled(id): return null
	var path := String(table()[id].get("opening", ""))
	return load(path) as ArrayMesh if ResourceLoader.exists(path) else null

## Size of a door leaf in metres: Vector3(width, height, thickness).
static func leaf_size(id: String) -> Vector3:
	var rect: Dictionary = table().get(id, {})
	return Vector3(float(rect.get("width", 0.0)), float(rect.get("height", 0.0)), float(rect.get("thickness", 0.0)))

## The door's hinge frame in its building's space (origin: the right-hand edge at the threshold, on the
## opening plane; x across, y up, z out of the wall).
static func hinge_frame(id: String) -> Transform3D:
	var rect: Dictionary = table()[id]
	var origin := _vec(rect.origin)
	var out := _vec(rect.out)
	var side := _vec(rect.side)
	var corner := origin+side*(float(rect.left)+float(rect.width))+Vector3.UP*float(rect.bottom)+out*float(rect.front)
	return Transform3D(Basis(side, Vector3.UP, out), corner)

## Puts the doors on the map's buildings (idempotent). Call before the dressing restyles the buildings:
## the leaf then takes its building's exterior material like the rest of it.
static func install(host: Node3D) -> void:
	var buildings := host.get_node_or_null("Buildings") if host else null
	if buildings == null: return
	for id: String in table():
		var building := buildings.get_node_or_null(id) as Node3D
		if building and enabled(id): attach(building, id)

static func attach(building: Node3D, id: String) -> void:
	_buildings[id] = building
	if building.has_node(LEAF): return
	var mesh := leaf_mesh(id)
	var doorway := opening_mesh(id)
	if mesh == null or doorway == null: return
	var frame := hinge_frame(id)
	var hinge := Node3D.new()
	hinge.name = LEAF
	hinge.transform = frame.translated_local(Vector3(0, 0, LEAF_LIFT))
	building.add_child(hinge)
	var leaf := MeshInstance3D.new()
	leaf.name = "Mesh"
	leaf.mesh = mesh
	# The exterior shader shades by height in the building (contact shade, window band): the leaf's
	# own origin sits at the threshold, this far above the building's.
	leaf.set_meta("door_local_lift", frame.origin.y)
	hinge.add_child(leaf)
	var opening := MeshInstance3D.new()
	opening.name = OPENING
	opening.mesh = doorway
	opening.transform = frame.translated_local(Vector3(0, 0, OPENING_LIFT))
	opening.material_override = _opening_material()
	opening.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	building.add_child(opening)

static func _opening_material() -> ShaderMaterial:
	if _opening_shader == null:
		_opening_shader = Shader.new()
		_opening_shader.code = OPENING_SHADER
	var material := ShaderMaterial.new()
	material.shader = _opening_shader
	return material

static func _vec(value) -> Vector3:
	return Vector3(float(value[0]), float(value[1]), float(value[2]))

static func _building(id: String) -> Node3D:
	var building = _buildings.get(id)
	return building if building != null and is_instance_valid(building) else null

## The ids whose door is installed on the current map.
static func door_ids() -> PackedStringArray:
	var ids := PackedStringArray()
	for id: String in _buildings:
		if _building(id) and _building(id).has_node(LEAF): ids.append(id)
	return ids

## The hinge (Buildings/<id>/DoorLeaf: rotation.y 0 closed .. OPEN_DEGREES open), or null.
static func door_leaf(id: String) -> Node3D:
	var building := _building(id)
	return building.get_node_or_null(LEAF) as Node3D if building else null

## The doorway (Buildings/<id>/DoorOpening; material_override's `inner_light` 0..1), or null.
static func door_opening(id: String) -> MeshInstance3D:
	var building := _building(id)
	return building.get_node_or_null(OPENING) as MeshInstance3D if building else null

## Opens a door by `amount` (0 closed .. 1 open), at once: tween this for an animation.
static func set_door_open(id: String, amount: float) -> void:
	var hinge := door_leaf(id)
	if hinge: hinge.rotation.y = deg_to_rad(OPEN_DEGREES)*clampf(amount, 0.0, 1.0)

static func door_open(id: String) -> float:
	var hinge := door_leaf(id)
	return clampf(hinge.rotation.y/deg_to_rad(OPEN_DEGREES), 0.0, 1.0) if hinge else 0.0
