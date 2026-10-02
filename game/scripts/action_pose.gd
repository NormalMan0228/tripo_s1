extends SkeletonModifier3D
## Add a short action on top of the imported walk/idle pose; never move the body.
var kind := ""
var elapsed := 1.0
var duration := 0.42
var applied_amount := 0.0
var body_basis := Basis.IDENTITY

func trigger(action: String) -> void:
	kind=action
	elapsed=0
	duration=0.46 if action=="gather" else 0.38

func rotate_bone(skeleton: Skeleton3D, bone: String, angles: Vector3) -> void:
	var index := skeleton.find_bone(bone)
	if index<0: return
	# Imported bones have different local axes. Express gestures in character space.
	for component in 3:
		if absf(angles[component])<0.0001: continue
		var axis := Vector3.ZERO
		axis[component]=1
		var world_axis := body_basis*axis
		var bone_world := skeleton.global_basis*skeleton.get_bone_global_pose(index).basis
		var local_axis := (bone_world.inverse()*world_axis).normalized()
		var pose := skeleton.get_bone_pose_rotation(index)
		skeleton.set_bone_pose_rotation(index,pose*Quaternion(local_axis,angles[component]))

func _process_modification_with_delta(delta: float) -> void:
	elapsed+=delta
	applied_amount=0
	if elapsed>=duration: return
	var skeleton := get_skeleton()
	if not skeleton: return
	var progress := elapsed/duration
	var power := sin(progress*PI)
	applied_amount=power
	match kind:
		"gather":
			rotate_bone(skeleton,"Spine02",Vector3(0.12*power,0,0))
			rotate_bone(skeleton,"R_Upperarm",Vector3(1.8*power,0,-0.12*power))
			rotate_bone(skeleton,"R_Forearm",Vector3(0.6*power,0,0))
		"attack":
			rotate_bone(skeleton,"Spine02",Vector3(0,0.45*power,0))
			rotate_bone(skeleton,"R_Upperarm",Vector3(1.3*power,0,-0.12*power))
			rotate_bone(skeleton,"R_Forearm",Vector3(0.2*power,0,0))
		"hurt":
			rotate_bone(skeleton,"Spine02",Vector3(-0.3*power,0,0.12*power))
			rotate_bone(skeleton,"Head",Vector3(0.12*power,0,0))
		"eat", "craft":
			rotate_bone(skeleton,"R_Upperarm",Vector3(0.8*power,0,0))
			rotate_bone(skeleton,"R_Forearm",Vector3(1.2*power,0,0))
