extends RefCounted
## World-space body sizes shared by gameplay, rooms and character previews.
## Fit the body before adding hats/hand props; equipment must not shrink its wearer.
const HUMAN_HEIGHT := 1.75
const CHILD_HEIGHT := 1.30
const REGULAR_MONSTER_MAX := 1.90
const BOSS_MIN := 3.50

static func human_height(id: String) -> float:
	return CHILD_HEIGHT if id in ["kid","sol"] else HUMAN_HEIGHT

## Mesh rest bounds in the model's parent space, without requiring it to enter the tree.
static func bounds(model: Node3D) -> AABB:
	var boxes: Array[AABB] = []
	collect(model,Transform3D.IDENTITY,model.transform,boxes)
	var box := AABB()
	for i in boxes.size(): box = boxes[i] if i==0 else box.merge(boxes[i])
	return box

static func collect(node: Node, parent: Transform3D, skin_root: Transform3D, boxes: Array[AABB]) -> void:
	var xf: Transform3D = parent*node.transform if node is Node3D else parent
	var skin_xf: Transform3D = xf if node is Node3D and not node.scene_file_path.is_empty() else skin_root
	if node is MeshInstance3D and node.mesh != null:
		# Authored skinned GLBs store vertices in model space. Their armature's
		# import scale is cancelled by inverse binds; applying it again made Boni
		# and Sol's measured bodies 1.6x too tall, shrinking the displayed people.
		boxes.append((skin_xf if node.skin else xf)*node.get_aabb())
	for child in node.get_children(): collect(child,xf,skin_xf,boxes)

## Uniform scale preserves proportions and keeps the feet on y=0.
## Call on a container outside animation tracks so animation cannot reset the fit.
static func fit(model: Node3D, target: float) -> bool:
	var box := bounds(model)
	if not is_finite(box.size.y) or box.size.y<.001: return false
	var factor := target/box.size.y
	model.scale *= factor
	model.position.y = (model.position.y-box.position.y)*factor
	return true

static func monster_height(model_height: float, requested: float, is_boss: bool) -> float:
	var target := requested if is_finite(requested) and requested>0 else model_height
	return maxf(BOSS_MIN,maxf(target,model_height)) if is_boss else minf(target,REGULAR_MONSTER_MAX)
