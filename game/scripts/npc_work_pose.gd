extends "res://scripts/action_pose.gd"
## Small job gestures over the idle clip, in body space. Full-body greetings and
## conversation temporarily release the job's arms.
var actor: Node3D
var motion: Node
var clock := 0.0
var weight := 0.0

func bone(skeleton: Skeleton3D, game: String, cast: String, mixamo: String) -> String:
	for candidate in [game,cast,"mixamorig:"+mixamo,"mixamorig_"+mixamo,mixamo]:
		if skeleton.find_bone(candidate)>=0: return candidate
	return ""

func turn(skeleton: Skeleton3D, game: String, cast: String, mixamo: String, angles: Vector3) -> void:
	var found := bone(skeleton,game,cast,mixamo)
	if not found.is_empty(): rotate_bone(skeleton,found,angles*weight)

func _process_modification_with_delta(delta: float) -> void:
	if not is_instance_valid(actor) or not is_instance_valid(motion): return
	var skeleton := get_skeleton()
	if not skeleton: return
	clock+=delta
	var task: String=motion.activity
	var active: bool=motion.posture=="stand" and not motion.talking and motion.greeting_left<=0.0 and not motion.moving
	weight=move_toward(weight,1.0 if active and task in ["tailor","fish","write","cook","wash"] else 0.0,delta*6.0)
	if weight<.001: return
	body_basis=actor.global_basis.orthonormalized()
	var beat := sin(clock*3.2)
	var reach := .55 if task=="fish" else .35
	turn(skeleton,"R_Upperarm","UpperArm.R","RightArm",Vector3(reach+.04*beat,0,-.08))
	turn(skeleton,"L_Upperarm","UpperArm.L","LeftArm",Vector3(reach,0,.08))
	turn(skeleton,"R_Forearm","Forearm.R","RightForeArm",Vector3(.72+.12*beat,0,0))
	turn(skeleton,"L_Forearm","Forearm.L","LeftForeArm",Vector3(.8-.04*beat,0,0))
	turn(skeleton,"Head","Head","Head",Vector3(.05,0,0))
