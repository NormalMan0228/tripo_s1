extends Node
## Sitting on and lying down on furniture, for rooms (studio.gd) and the village (main.gd). A facade
## over the ISS-1 interaction driver (ix/ix_driver.gd): the walker walks up to the seat, turns, sits
## down (or sits on the bed's edge and lies back) in one continuous motion, rides a rocking seat, and
## gets up again facing out of it, onto a free spot. A crafted piece its owner marked as a seat or a
## bed (상호작용 · 쉬기) works the same way in both places (crafted()).
##
## Fallback: a walker without the driver hook, a piece with no usable socket, or use_driver off keeps
## the simplified way (settle on the seat at once, the ISS-1 pose layer easing in; up again where it
## stood). It is not the pre-ISS-1 code: beds keep the body upright and tilt the skeleton through the
## pose layer, and field seats, shadow figures and story guests use ISS-1 whatever the switch says.
##
## In the village the walker is the player's own controller: walking (walk_off allows it) gets it up,
## being moved away by something else lets it go.
const IxPose = preload("res://scripts/ix/ix_pose.gd")
const IxRig = preload("res://scripts/ix/ix_rig.gd")
const Driver = preload("res://scripts/ix/ix_driver.gd")
## Off: every seat takes the fallback above (a hotfix switch; tests/village_rest_check.gd runs it).
static var use_driver := true

var hero: Node3D:
	set(value):
		# A new walker (a rebuilt world): whatever the driver had with the old one is over.
		if is_instance_valid(driver) and driver.busy() and driver.actor != value: driver.reset("gone")
		hero = value
		if is_instance_valid(driver):
			driver.actor = value
			if is_instance_valid(value) and "ix" in value: value.ix = driver
## "", "sit" or "lie": while the driver has the walker (walking up, seated, getting up), or the old way.
## A driver whose walker went away with its world never counts as resting.
var mode: String:
	get: return driver.kind if is_instance_valid(driver) and driver.locks_input() and driver.actor_ok() else legacy_mode
	set(value): legacy_mode = value
var legacy_mode := ""
var pose: SkeletonModifier3D:
	get: return driver.pose if is_instance_valid(driver) and is_instance_valid(driver.pose) else legacy_pose
	set(value): legacy_pose = value
var legacy_pose: SkeletonModifier3D
var driver: Node
## Where the walker stood before resting, and where resting put it (the old way).
var back_to := Vector3.ZERO
var settled_at := Vector3.ZERO
## The village: getting up keeps the height the walker stood at (rooms stand on their floor, y = 0).
var keep_height := false
## The village: true while movement keys may get the walker up (main.world_movement_allowed).
var walk_off := Callable()
## Rooms: how the walker walks up to a seat (studio.move_hero without doors and stairs) and which
## spots it may stand on (studio.can_stand). The village uses the walker's own physics.
var mover := Callable()
var free_check := Callable()
var was_visual_only := true
var furniture: Node3D
var on_furniture := false
## The way out of the seat (getting up faces it, not the camera).
var front := Vector3.BACK

func resting() -> bool:
	return not mode.is_empty()

## The driver for this walker (made once), or null when the walker has no hook for it.
func ensure_driver() -> Node:
	if not use_driver or not is_instance_valid(hero) or not "ix" in hero or not hero.is_inside_tree(): return null
	if not is_instance_valid(driver):
		driver = Driver.new()
		driver.name = "IxDriver"
		add_child(driver)
	driver.actor = hero
	hero.ix = driver
	driver.input_allowed = walk_off
	driver.mover = mover
	driver.free_check = free_check
	return driver

func start(opts: Dictionary) -> bool:
	var d := ensure_driver()
	if d == null: return false
	if d.busy(): return true
	return d.begin(opts)

func ensure_pose() -> bool:
	if not is_instance_valid(hero) or not "hand_skeleton" in hero or not is_instance_valid(hero.hand_skeleton): return false
	if not is_instance_valid(legacy_pose) or legacy_pose.get_parent()!=hero.hand_skeleton:
		legacy_pose=IxPose.attach(hero)
	if is_instance_valid(legacy_pose):
		legacy_pose.driven=false
		# The layer is shared: a field seat may have left its own fade time on it.
		legacy_pose.fade_time=0.25
	return is_instance_valid(legacy_pose)

func hip_height() -> float:
	if not is_instance_valid(hero) or not "hand_skeleton" in hero or not is_instance_valid(hero.hand_skeleton): return 0.85
	var skeleton: Skeleton3D=hero.hand_skeleton
	var bone := skeleton.find_bone("L_Thigh")
	if bone<0: return 0.85
	var hip: Vector3=skeleton.global_transform*skeleton.get_bone_global_rest(bone).origin
	return clampf(hip.y-hero.global_position.y,0.5,1.1)

## Sits on or lies down on a crafted piece marked as a seat or a bed; ground: the height it stands on.
func crafted(item: Node3D, kind: String, ground := 0.0) -> void:
	if not is_instance_valid(item) or resting(): return
	if start({"node":item,"hint":kind}):
		furniture=item
		on_furniture=true
		return
	var size: Vector3=item.get_meta("size",Vector3.ONE)
	var yaw: float=item.rotation.y
	# A bed lies along its longer side.
	if kind=="lie" and size.x>size.z:
		yaw+=PI*0.5;size=Vector3(size.z,size.y,size.x)
	var record := {"kind":"chair" if kind=="sit" else "bed","size":size,"yaw":yaw,"center":Vector3(item.position.x,0,item.position.z),"node":item,"ground":ground}
	if kind=="sit":legacy_sit(record)
	else:legacy_lie(record)
	if resting():
		furniture=item
		on_furniture=true

## Sits on a chair, sofa or bench (a room piece record): the walker walks up and sits facing out.
func sit(record: Dictionary) -> void:
	if not is_instance_valid(hero) or resting(): return
	if start({"record":record,"hint":"sit"}): return
	legacy_sit(record)

## Lies down on a bed, head on the pillow.
func lie(record: Dictionary) -> void:
	if not is_instance_valid(hero) or resting(): return
	if start({"record":record,"hint":"lie"}): return
	legacy_lie(record)

## Gets up: with the driver, the walker stands up and steps off (face_away false: a door or a
## teleport takes it, so it is let go where it is).
func stand(face_away := true) -> void:
	if is_instance_valid(driver) and driver.busy() and not driver.actor_ok():
		driver.reset("gone")
		on_furniture=false
		furniture=null
		return
	if is_instance_valid(driver) and driver.busy():
		if face_away: driver.request_exit()
		else: driver.abort("away")
		on_furniture=false
		furniture=null
		return
	if not resting() or not is_instance_valid(hero): return
	release()
	hero.position=Vector3(back_to.x,back_to.y if keep_height else 0.0,back_to.z)
	# Up and facing out of the seat (it used to turn toward the camera, +Z, whatever the seat).
	if face_away: hero.facing=front

# ------------------------------------------------------------------ the old way (fallback)

func legacy_sit(record: Dictionary) -> void:
	var size: Vector3=record.size
	var yaw: float=record.yaw
	front = Vector3(0,0,1).rotated(Vector3.UP,yaw)
	var seat_x := 0.0
	if record.kind=="sofa":
		var local: Vector3=(hero.position-record.center).rotated(Vector3.UP,-yaw)
		seat_x=clampf(local.x,-size.x*0.25,size.x*0.25)
	var seat: Vector3=record.center+Vector3(seat_x,0,0.04).rotated(Vector3.UP,yaw)
	hold("sit")
	var height: float=minf(size.y*0.5,0.5) if record.kind!="bench" else 0.47
	hero.position=Vector3(seat.x,float(record.get("ground",0.0))+height-hip_height()+IxRig.SEAT_DROP,seat.z)
	hero.facing=front
	settled_at=hero.position
	if ensure_pose(): legacy_pose.mode="sit"

func legacy_lie(record: Dictionary) -> void:
	var size: Vector3=record.size
	var yaw: float=record.yaw
	var head := Vector3(0,0,-1).rotated(Vector3.UP,yaw)
	hold("lie")
	# Getting up faces away from the bed, toward where the walker stood.
	var out: Vector3=back_to-Vector3(record.center.x,back_to.y,record.center.z)
	front=out.normalized() if out.length()>0.05 else Vector3(1,0,0).rotated(Vector3.UP,yaw)
	# The body stays upright; the pose layer lays the skeleton back about the hips (feet toward -head).
	var hips: Vector3=record.center+head*0.0-head*0.10
	hips.y=float(record.get("ground",0.0))+minf(size.y*0.5,0.62)+IxRig.LIE_LIFT
	var feet_yaw := atan2(-head.x,-head.z)
	var m: Dictionary=IxRig.measure(hero.hand_skeleton,hero.visual) if "hand_skeleton" in hero and is_instance_valid(hero.hand_skeleton) else IxRig.fallback()
	hero.position=hips-Basis(Vector3.UP,feet_yaw)*Vector3(m.pelvis)
	hero.facing=-head
	settled_at=hero.position
	if ensure_pose(): legacy_pose.mode="lie"

## Stops the walker where it is: the room's walker is already still; the village's waits its physics.
func hold(kind: String) -> void:
	back_to=hero.position
	legacy_mode=kind
	was_visual_only=bool(hero.get("visual_only")) if "visual_only" in hero else true
	if "visual_only" in hero: hero.visual_only=true
	if hero is CharacterBody3D: hero.velocity=Vector3.ZERO
	hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO

## Up without moving (the walker was taken elsewhere).
func release() -> void:
	legacy_mode=""
	on_furniture=false
	furniture=null
	if not is_instance_valid(hero): return
	hero.basis=Basis()
	if "visual_only" in hero: hero.visual_only=was_visual_only
	if is_instance_valid(legacy_pose): legacy_pose.mode=""

## Everything let go at once, without touching a walker that may be gone (the world is rebuilt).
func reset() -> void:
	if is_instance_valid(driver) and driver.busy(): driver.reset("gone")
	if not legacy_mode.is_empty(): release()
	on_furniture=false
	furniture=null

## Where other players should see this walker while it rests: the spot it stood on before (its
## body is lowered into the seat, and presence carries no pose), or null when it is not resting.
func stand_spot():
	if is_instance_valid(driver) and driver.busy() and driver.actor_ok() and driver.state >= Driver.ALIGN and driver.state <= Driver.EXIT:
		return Vector3(driver.enter_from)
	if not legacy_mode.is_empty() and is_instance_valid(hero): return Vector3(back_to.x, back_to.y if keep_height else 0.0, back_to.z)
	return null

func _process(_delta: float) -> void:
	# Nothing drives a driver whose walker went away with its world (player._physics_process does).
	if is_instance_valid(driver) and driver.busy() and not driver.actor_ok(): driver.reset("gone")
	if legacy_mode.is_empty(): return
	if not is_instance_valid(hero) or not hero.is_inside_tree():
		legacy_mode=""
		return
	# The piece went away, or something else moved the walker (a door, a teleport): just get up.
	if (on_furniture and not is_instance_valid(furniture)) or hero.position.distance_to(settled_at)>0.05:
		release()
		return
	# A new look rebuilt the character while seated (avatar_look.gd): its new skeleton sits too.
	if is_instance_valid(hero.hand_skeleton) and (not is_instance_valid(legacy_pose) or legacy_pose.get_parent()!=hero.hand_skeleton) and ensure_pose():
		legacy_pose.mode=legacy_mode
	if walk_off.is_valid() and walk_off.call() and Input.get_vector("move_left","move_right","move_forward","move_back").length()>0.3:
		stand()
