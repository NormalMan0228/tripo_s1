extends Node
## Fades a room's front door (interiors.gd building_door) while it stands between the camera and the
## walker: the door is the building's full-height leaf and the room's front faces the camera, so the
## closed door would hide whoever walks behind it. Every CHECK seconds a segment from the camera to the
## walker's chest is tested against the leaf's box; the leaf's GeometryInstance3D transparency eases
## to FADED while it is hit and back to solid when not. The studio's walker is its `hero`.
const CHECK := 0.1
const FADED := 0.65
const EASE := 3.0
var leaf: GeometryInstance3D
var studio: Node
var wait := 0.0
var target := 0.0

func _ready() -> void:
	leaf = get_parent().get_node_or_null("Mesh") as GeometryInstance3D
	var node := get_parent()
	while node != null and studio == null:
		if "hero" in node: studio = node
		node = node.get_parent()

func _process(delta: float) -> void:
	if leaf == null: return
	wait -= delta
	if wait <= 0.0:
		wait = CHECK
		target = FADED if occludes() else 0.0
	if not is_equal_approx(leaf.transparency, target): leaf.transparency = move_toward(leaf.transparency, target, delta*EASE)

## True when the door's box lies on the line from the camera to the walker.
func occludes() -> bool:
	var camera := get_viewport().get_camera_3d() if is_inside_tree() else null
	var hero = studio.get("hero") if studio else null
	if camera == null or not (hero is Node3D) or not is_instance_valid(hero) or not (hero as Node3D).is_visible_in_tree(): return false
	var to: Vector3 = (hero as Node3D).global_position+Vector3(0, 0.9, 0)
	var from := to+camera.global_basis.z*60.0 if camera.projection == Camera3D.PROJECTION_ORTHOGONAL else camera.global_position
	var box: AABB = leaf.global_transform*leaf.get_aabb()
	return box.intersects_segment(from, to) != null
