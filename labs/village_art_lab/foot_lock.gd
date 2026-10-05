extends SkeletonModifier3D
## Contact-aware lower-body IK over the reviewed clips; no face/hand/mesh edits.
var actor: Node3D
var legs: Array[Dictionary]=[]
var phase := 0.0
var blend := 0.0
var cycle_seconds := .65
var speed := 0.0
var running := false
var contact_error := 0.0
var final_rotations: Array=[]
var final_feet: Array=[]
var previous_solved: Dictionary={}

func configure(player: Node3D) -> void:
	actor=player
	var skeleton := get_skeleton()
	for side in ["L","R"]:
		var hip := skeleton.find_bone(side+"_Thigh")
		var knee := skeleton.find_bone(side+"_Calf")
		var foot := skeleton.find_bone(side+"_Foot")
		if mini(hip,mini(knee,foot))<0:continue
		var a := skeleton.global_transform*skeleton.get_bone_global_rest(hip).origin
		var b := skeleton.global_transform*skeleton.get_bone_global_rest(knee).origin
		var c := skeleton.global_transform*skeleton.get_bone_global_rest(foot).origin
		var offset: Vector3=actor.visual.global_basis.inverse()*(c-actor.global_position)
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
	var forward: Vector3=skeleton.global_basis.inverse()*(-actor.visual.global_basis.z)
	var pole := (forward-direction*forward.dot(direction)).normalized()
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

func _process_modification_with_delta(delta: float) -> void:
	if not is_instance_valid(actor) or legs.size()!=2:return
	var skeleton := get_skeleton()
	contact_error=0
	for index in skeleton.get_bone_count():
		var is_leg := false
		for leg in legs:
			if index in [leg.hip,leg.knee,leg.foot]:is_leg=true
		if is_leg:continue
		var q := skeleton.get_bone_pose_rotation(index)
		if previous_solved.has(index):
			var before: Quaternion=previous_solved[index]
			q=before.slerp(q,minf(1,16*delta/maxf(.00001,before.angle_to(q))))
		skeleton.set_bone_pose_rotation(index,q);previous_solved[index]=q
	for i in 2:
		var leg: Dictionary=legs[i]
		var strength: float=actor.contact_strength(i) if actor.mode=="play" and actor.is_on_floor() else 0.0
		var foot_world: Vector3=skeleton.global_transform*skeleton.get_bone_global_pose(leg.foot).origin
		if strength<.25:leg["blocked"]=false
		if strength>.6 and not leg.contact and not bool(leg.get("blocked",false)):
			leg.target=leg.get("last_world",foot_world)
			var query := PhysicsRayQueryParameters3D.create(foot_world+Vector3.UP*.35,foot_world-Vector3.UP*.5)
			query.exclude=[actor.get_rid()]
			var hit: Dictionary=actor.get_world_3d().direct_space_state.intersect_ray(query)
			if not hit.is_empty():leg.target.y=hit.position.y+.045
			leg.contact=true
		if strength<.25:leg.contact=false
		var goal := strength if leg.contact else 0.0
		leg["weight"]=move_toward(float(leg.get("weight",0.0)),goal,delta*14)
		if leg.get("weight",0.0)>.001:
			var hip_world: Vector3=skeleton.global_transform*skeleton.get_bone_global_pose(leg.hip).origin
			if hip_world.distance_to(leg.target)>float(leg.reach)*.98:
				leg.contact=false;leg["blocked"]=true;leg["weight"]=maxf(0,float(leg.weight)-delta*14)
			solve(skeleton,leg,leg.target,leg.weight)
	# Blend the evaluated correction across contact releases, including a
	# reach-limit release during a sharp turn. The collision motor is untouched.
	for leg in legs:
		for key in ["hip","knee","foot"]:
			var index: int=leg[key]
			var q := skeleton.get_bone_pose_rotation(index)
			if previous_solved.has(index):
				var before: Quaternion=previous_solved[index]
				q=before.slerp(q,minf(1,18*delta/maxf(.00001,before.angle_to(q))))
			skeleton.set_bone_pose_rotation(index,q);previous_solved[index]=q
	# Enforce a continuous world-space swing path as gait weights change.
	# The cap includes motor travel; support feet already have a fixed anchor.
	for leg in legs:
		var candidate: Vector3=skeleton.global_transform*skeleton.get_bone_global_pose(leg.foot).origin
		if leg.has("last_world"):
			var last: Vector3=leg.last_world
			if candidate.distance_to(last)>10.0*delta:
				solve(skeleton,leg,last.move_toward(candidate,10.0*delta),1.0)
		for key in ["hip","knee","foot"]:
			var index: int=leg[key]
			previous_solved[index]=skeleton.get_bone_pose_rotation(index)
	contact_error=0
	for leg in legs:
		leg["last_world"]=skeleton.global_transform*skeleton.get_bone_global_pose(leg.foot).origin
		if leg.contact and float(leg.get("weight",0.0))>.99:
			var foot: Vector3=skeleton.global_transform*skeleton.get_bone_global_pose(leg.foot).origin
			contact_error=maxf(contact_error,Vector2(foot.x-leg.target.x,foot.z-leg.target.z).length())
	# SkeletonModifier restores the source pose after submitting the skin.
	# Preserve the evaluated result for acceptance tests.
	final_rotations.clear();final_feet.clear()
	for index in skeleton.get_bone_count():final_rotations.append(skeleton.get_bone_pose_rotation(index))
	for leg in legs:final_feet.append(skeleton.global_transform*skeleton.get_bone_global_pose(leg.foot).origin)
