extends SkeletonModifier3D
## Contact-aware lower-body IK over the reviewed clips; no face/hand/mesh edits.
const FINGER_PARTS := ["Thumb_","Index_","Middle_","Ring_","Little_"]
var actor: Node3D
var forward_sign := -1.0
var preserve_bend := false
var legs: Array[Dictionary]=[]
var phase := 0.0
var blend := 0.0
var cycle_seconds := .65
var speed := 0.0
var running := false
var contact_error := 0.0
var contact_vertical_error := 0.0
var previous_solved: Dictionary={}

func smooth_solved_pose(skeleton: Skeleton3D,delta: float,legs_only: bool) -> void:
	# Contact releases and clip transitions share a finite angular velocity.
	# Body 16 rad/s; legs 18 rad/s preserve reach without a one-frame pose swap.
	# Normal source poses pass through; only a discontinuous target is limited.
	for index in skeleton.get_bone_count():
		var is_leg := false
		for leg in legs:
			if index==leg.hip or index==leg.knee or index==leg.foot:
				is_leg=true
				break
		if is_leg!=legs_only:continue
		var name := skeleton.get_bone_name(index)
		if name.begins_with("Face_"):continue
		var finger := false
		for digit in FINGER_PARTS:
			if digit in name:
				finger=true
				break
		if finger:continue
		var target := skeleton.get_bone_pose_rotation(index)
		if previous_solved.has(index):
			var old: Quaternion=previous_solved[index]
			var angle := old.angle_to(target)
			var weight := minf(1.0,(18.0 if legs_only else 16.0)*delta/maxf(.00001,angle))
			target=old.slerp(target,weight)
		skeleton.set_bone_pose_rotation(index,target);previous_solved[index]=target

func body_basis() -> Basis:return actor.visual.global_basis
func motion_speed() -> float:return actor.locomotion_velocity.length()
func motion_clip() -> String:return actor.current_clip
func motion_phase() -> float:return actor.gait_phase

func leg_bone(skeleton: Skeleton3D,side: String,part: String) -> int:
	var long_side := "Left" if side=="L" else "Right"
	var mix: String={"Thigh":"UpLeg","Calf":"Leg","Foot":"Foot"}[part]
	var cast: String={"Thigh":"UpperLeg","Calf":"LowerLeg","Foot":"Foot"}[part]
	for name in [side+"_"+part,"mixamorig_"+long_side+mix,"mixamorig:"+long_side+mix,cast+"."+side,part+"."+side]:
		var index := skeleton.find_bone(name)
		if index>=0:return index
	return -1

func configure(player: Node3D) -> void:
	actor=player
	var skeleton := get_skeleton()
	for side in ["L","R"]:
		var hip := leg_bone(skeleton,side,"Thigh")
		var knee := leg_bone(skeleton,side,"Calf")
		var foot := leg_bone(skeleton,side,"Foot")
		if mini(hip,mini(knee,foot))<0:continue
		var a := skeleton.global_transform*skeleton.get_bone_global_rest(hip).origin
		var b := skeleton.global_transform*skeleton.get_bone_global_rest(knee).origin
		var c := skeleton.global_transform*skeleton.get_bone_global_rest(foot).origin
		var offset: Vector3=body_basis().inverse()*(c-actor.global_position)
		legs.append({"hip":hip,"knee":knee,"foot":foot,"offset":offset,"reach":a.distance_to(b)+b.distance_to(c),"contact":false,"target":c,"start":c,"last_phase":0.0})

func rotate_joint(skeleton: Skeleton3D,index: int,basis: Basis,weight: float) -> void:
	var parent := skeleton.get_bone_parent(index)
	var parent_basis := skeleton.get_bone_global_pose(parent).basis if parent>=0 else Basis.IDENTITY
	# Godot 4 poses already contain the local rest transform. Applying its inverse
	# again would flip imported glTF joints and fold the knees above the hip.
	var local := parent_basis.inverse()*basis
	var pose := skeleton.get_bone_pose_rotation(index)
	skeleton.set_bone_pose_rotation(index,pose.slerp(local.orthonormalized().get_rotation_quaternion(),weight))

func solve(skeleton: Skeleton3D,leg: Dictionary,target_world: Vector3,weight: float) -> void:
	var hip: Transform3D=skeleton.get_bone_global_pose(leg.hip)
	var knee: Transform3D=skeleton.get_bone_global_pose(leg.knee)
	var foot: Transform3D=skeleton.get_bone_global_pose(leg.foot)
	var target := skeleton.global_transform.affine_inverse()*target_world
	var length_a := hip.origin.distance_to(knee.origin)
	var length_b := knee.origin.distance_to(foot.origin)
	var distance := clampf(hip.origin.distance_to(target),absf(length_a-length_b)+.001,length_a+length_b-.003)
	var direction := (target-hip.origin).normalized()
	# Knee bends along the character's facing direction, expressed in rig space.
	var forward: Vector3=skeleton.global_basis.inverse()*(body_basis().z*forward_sign)
	var bend := knee.origin-hip.origin if preserve_bend else forward
	var pole := (bend-direction*bend.dot(direction)).normalized()
	if pole.length_squared()<.01:pole=Vector3.FORWARD
	var along := (length_a*length_a-length_b*length_b+distance*distance)/(2.0*distance)
	var bent := hip.origin+direction*along+pole*sqrt(maxf(0,length_a*length_a-along*along))
	var hip_rotation := Quaternion((knee.origin-hip.origin).normalized(),(bent-hip.origin).normalized())
	rotate_joint(skeleton,leg.hip,Basis(hip_rotation)*hip.basis,weight)
	knee=skeleton.get_bone_global_pose(leg.knee)
	var current_foot := skeleton.get_bone_global_pose(leg.foot)
	var calf_rotation := Quaternion((current_foot.origin-knee.origin).normalized(),(target-knee.origin).normalized())
	rotate_joint(skeleton,leg.knee,Basis(calf_rotation)*knee.basis,weight)
	rotate_joint(skeleton,leg.foot,foot.basis,weight)
	if leg.contact and weight>.99:
		var result: Vector3=skeleton.global_transform*skeleton.get_bone_global_pose(leg.foot).origin
		contact_error=maxf(contact_error,Vector2(result.x-target_world.x,result.z-target_world.z).length())

## True when a foot point sits on (or near) the other leg's side of the body.
func crossed(leg: Dictionary,point: Vector3) -> bool:
	var side: float=float(leg.offset.x)
	var local: Vector3=body_basis().orthonormalized().inverse()*(point-actor.global_position)
	return local.x*signf(side)<absf(side)*.25

func cycle_for_speed(actual_speed: float) -> float:
	if legs.is_empty():return .65
	var fast := actual_speed>3.4
	var stance := .38 if fast else .50
	var stride_length := float(legs[0].reach)*(.90 if fast else .72)
	return clampf(stride_length/maxf(.1,actual_speed*stance),.42,1.25)

func _process_modification_with_delta(delta: float) -> void:
	if not is_instance_valid(actor) or legs.size()!=2:return
	var skeleton := get_skeleton()
	# Solve contacts against the filtered pelvis before applying leg corrections.
	smooth_solved_pose(skeleton,delta,false)
	speed=motion_speed()
	running=speed>3.4
	var active: bool=speed>.12 and (motion_clip()=="walk" or motion_clip()=="run")
	blend=lerpf(blend,1.0 if active else 0.0,1.0-exp(-16.0*delta))
	if not active:
		contact_error=0
		contact_vertical_error=0
		for leg in legs:
			if blend>.01:solve(skeleton,leg,leg.target,blend)
			else:leg.contact=false
		smooth_solved_pose(skeleton,delta,true)
		return
	var stance := .38 if running else .50
	cycle_seconds=cycle_for_speed(speed)
	phase=motion_phase()
	var forward: Vector3=body_basis().z.normalized()*forward_sign
	var footprint := speed*cycle_seconds*stance
	contact_error=0
	for i in 2:
		var leg: Dictionary=legs[i]
		var p := fposmod(phase+float(i)*.5,1.0)
		var home: Vector3=actor.global_position+body_basis()*leg.offset
		if p<stance:
			if not leg.contact:
				leg.target=home+forward*(footprint*(.5-p/stance))
				leg.contact=true
			# A sharp turn, step or teleport releases an unreachable old contact. So does a
			# quick turn on the spot: the planted foot would end up across the other leg
			# and fold the hips and knees sideways.
			if home.distance_to(leg.target)>float(leg.reach)*.78 or absf(home.y-leg.target.y)>.25 or crossed(leg,leg.target):
				leg.target=home
			leg.start=leg.target
		else:
			if leg.contact:leg.start=leg.target
			leg.contact=false
			# The body turned during the swing: lift from under the hip, not across the body.
			if crossed(leg,leg.start):leg.start=home
			var u := (p-stance)/(1.0-stance)
			var landing: Vector3=home+forward*footprint*.5
			leg.target=leg.start.lerp(landing,smoothstep(0.0,1.0,u))+Vector3.UP*sin(u*PI)*(.15 if running else .085)
		solve(skeleton,leg,leg.target,blend)
		leg.last_phase=p
	smooth_solved_pose(skeleton,delta,true)
	# Report the final pose, including transition filtering.
	contact_error=0
	contact_vertical_error=0
	for leg in legs:
		var final_foot: Vector3=skeleton.global_transform*skeleton.get_bone_global_pose(leg.foot).origin
		if leg.contact and blend>.99:
			var foot: Vector3=final_foot
			contact_error=maxf(contact_error,Vector2(foot.x-leg.target.x,foot.z-leg.target.z).length())
			contact_vertical_error=maxf(contact_vertical_error,absf(foot.y-leg.target.y))
