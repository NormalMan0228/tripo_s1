extends Node
## Sitting on and lying down on furniture, for rooms (studio.gd) and the village (main.gd): the walker
## settles on a seat facing out, or lies on a bed head on the pillow, while Interiors.RestPose bends
## the hips and knees; getting up puts it back where it stood. A crafted piece its owner marked as a
## seat or a bed (상호작용 · 쉬기) works the same way in both places (crafted()).
##
## In the village the walker is the player's own controller: its physics waits while it rests
## (visual_only), and walking (walk_off allows it) or being moved away by something else gets it up.
const Interiors = preload("res://scripts/interiors.gd")

var hero: Node3D
## "", "sit" or "lie".
var mode := ""
var pose: SkeletonModifier3D
## Where the walker stood before resting, and where resting put it.
var back_to := Vector3.ZERO
var settled_at := Vector3.ZERO
## The village: getting up keeps the height the walker stood at (rooms stand on their floor, y = 0).
var keep_height := false
## The village: true while movement keys may get the walker up (main.world_movement_allowed).
var walk_off := Callable()
var was_visual_only := true
var furniture: Node3D
var on_furniture := false

func resting() -> bool:
	return not mode.is_empty()

func ensure_pose() -> bool:
	if not is_instance_valid(hero) or not is_instance_valid(hero.hand_skeleton): return false
	if not is_instance_valid(pose) or pose.get_parent()!=hero.hand_skeleton:
		pose=Interiors.RestPose.new()
		hero.hand_skeleton.add_child(pose)
	pose.body=hero.visual
	return true

func hip_height() -> float:
	if not is_instance_valid(hero) or not is_instance_valid(hero.hand_skeleton): return 0.85
	var skeleton: Skeleton3D=hero.hand_skeleton
	var bone := skeleton.find_bone("L_Thigh")
	if bone<0: return 0.85
	var hip: Vector3=skeleton.global_transform*skeleton.get_bone_global_rest(bone).origin
	return clampf(hip.y-hero.global_position.y,0.5,1.1)

## Sits on or lies down on a crafted piece marked as a seat or a bed; ground: the height it stands on.
func crafted(item: Node3D, kind: String, ground := 0.0) -> void:
	var size: Vector3=item.get_meta("size",Vector3.ONE)
	var yaw: float=item.rotation.y
	# A bed lies along its longer side.
	if kind=="lie" and size.x>size.z:
		yaw+=PI*0.5;size=Vector3(size.z,size.y,size.x)
	var record := {"kind":"chair" if kind=="sit" else "bed","size":size,"yaw":yaw,"center":Vector3(item.position.x,0,item.position.z),"node":item,"ground":ground}
	if kind=="sit":sit(record)
	else:lie(record)
	if resting():
		furniture=item
		on_furniture=true

## Sits on a chair, sofa or bench: hips and knees bend and the walker settles on the seat facing out.
func sit(record: Dictionary) -> void:
	if not is_instance_valid(hero) or resting(): return
	var size: Vector3=record.size
	var yaw: float=record.yaw
	var front := Vector3(0,0,1).rotated(Vector3.UP,yaw)
	var seat_x := 0.0
	if record.kind=="sofa":
		var local: Vector3=(hero.position-record.center).rotated(Vector3.UP,-yaw)
		seat_x=clampf(local.x,-size.x*0.25,size.x*0.25)
	var seat: Vector3=record.center+Vector3(seat_x,0,0.04).rotated(Vector3.UP,yaw)
	hold("sit")
	var height: float=size.y*0.5 if record.kind!="bench" else 0.47
	hero.position=Vector3(seat.x,float(record.get("ground",0.0))+height-hip_height()+0.1,seat.z)
	hero.facing=front
	settled_at=hero.position
	if ensure_pose(): pose.mode="sit"

## Lies down on a bed, head on the pillow.
func lie(record: Dictionary) -> void:
	if not is_instance_valid(hero) or resting(): return
	var size: Vector3=record.size
	var yaw: float=record.yaw
	var head := Vector3(0,0,-1).rotated(Vector3.UP,yaw)
	hold("lie")
	var feet: Vector3=record.center-head*(size.z*0.5-0.2)
	hero.facing=Vector3(0,0,-1)
	var down := Vector3(0,-1,0)
	hero.basis=Basis(head.cross(down),head,down)
	hero.position=Vector3(feet.x,float(record.get("ground",0.0))+minf(size.y*0.5,0.62)+0.14,feet.z)
	settled_at=hero.position
	if ensure_pose(): pose.mode=""

## Stops the walker where it is: the room's walker is already still; the village's waits its physics.
func hold(kind: String) -> void:
	back_to=hero.position
	mode=kind
	was_visual_only=bool(hero.get("visual_only")) if "visual_only" in hero else true
	if "visual_only" in hero: hero.visual_only=true
	if hero is CharacterBody3D: hero.velocity=Vector3.ZERO
	hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO

func stand(face_away := true) -> void:
	if not resting() or not is_instance_valid(hero): return
	release()
	hero.position=Vector3(back_to.x,back_to.y if keep_height else 0.0,back_to.z)
	if face_away: hero.facing=Vector3.BACK

## Up without moving (the walker was taken elsewhere).
func release() -> void:
	mode=""
	on_furniture=false
	furniture=null
	if not is_instance_valid(hero): return
	hero.basis=Basis()
	if "visual_only" in hero: hero.visual_only=was_visual_only
	if is_instance_valid(pose): pose.mode=""

func _process(_delta: float) -> void:
	if not resting(): return
	if not is_instance_valid(hero) or not hero.is_inside_tree():
		mode=""
		return
	# The piece went away, or something else moved the walker (a door, a teleport): just get up.
	if (on_furniture and not is_instance_valid(furniture)) or hero.position.distance_to(settled_at)>0.05:
		release()
		return
	# A new look rebuilt the character while seated (avatar_look.gd): its new skeleton sits too.
	if mode=="sit" and is_instance_valid(hero.hand_skeleton) and (not is_instance_valid(pose) or pose.get_parent()!=hero.hand_skeleton) and ensure_pose():
		pose.mode="sit"
	if walk_off.is_valid() and walk_off.call() and Input.get_vector("move_left","move_right","move_forward","move_back").length()>0.3:
		stand()
