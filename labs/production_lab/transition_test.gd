extends RefCounted
## Replays motor inputs and measures the resulting skin, including phase transitions.
static func run(lab: Node3D) -> Dictionary:
	var actor: CharacterBody3D=lab.actor
	var trace: Array=[]
	actor.scripted_control=true;actor.mode="play"
	# Keep the entire measured route on the ground; respawn is a separate behavior.
	actor.position=Vector3(-7,.05,2);actor.velocity=Vector3.ZERO
	var previous_position: Vector3=actor.global_position
	var previous_rotations: Array=[]
	var previous_feet: Array=[]
	var max_joint_step := 0.0
	var max_motor_excess := 0.0
	var max_foot_step := 0.0
	var max_foot_stage := ""
	var max_joint_bone := ""
	var max_contact_error := 0.0
	var previous_frame := Engine.get_physics_frames()
	var stages := [["idle",Vector2.ZERO,false,40],["start_walk",Vector2(1,0),false,100],
		["walk_to_run",Vector2(1,0),true,80],["run_to_walk",Vector2(1,0),false,65],
		["brake",Vector2.ZERO,false,55],["turn",Vector2(0,-1),false,70],
		["stop",Vector2.ZERO,false,50]]
	for stage in stages:
		actor.scripted_input=stage[1];actor.scripted_running=stage[2]
		for _i in stage[3]:
			await lab.get_tree().physics_frame
			await lab.get_tree().process_frame
			var frames_now := Engine.get_physics_frames()
			var dt := maxf(1.0/60,float(frames_now-previous_frame)/60);previous_frame=frames_now
			var displacement := actor.global_position.distance_to(previous_position)
			max_motor_excess=maxf(max_motor_excess,displacement-4.5*dt-.01)
			previous_position=actor.global_position
			var rotations: Array=[]
			for i in actor.skeleton.get_bone_count():
				var q: Quaternion=actor.foot_lock.final_rotations[i] if actor.foot_lock.final_rotations.size()==actor.skeleton.get_bone_count() else actor.skeleton.get_bone_pose_rotation(i)
				rotations.append(q)
				if not previous_rotations.is_empty():
					var step := rad_to_deg(q.angle_to(previous_rotations[i]))/maxf(1,dt*60)
					if step>max_joint_step:max_joint_step=step;max_joint_bone=actor.skeleton.get_bone_name(i)
			previous_rotations=rotations
			var feet: Array=[]
			for name in ["L_Foot","R_Foot"]:
				var side := 0 if name=="L_Foot" else 1
				var foot: Vector3=actor.foot_lock.final_feet[side] if actor.foot_lock.final_feet.size()==2 else actor.skeleton.global_transform*actor.skeleton.get_bone_global_pose(actor.skeleton.find_bone(name)).origin
				feet.append(foot)
				if not previous_feet.is_empty():
					var step := foot.distance_to(previous_feet[feet.size()-1])/maxf(1,dt*60)
					if step>max_foot_step:max_foot_step=step;max_foot_stage=stage[0]
			previous_feet=feet
			var hip: Vector3=actor.skeleton.get_bone_global_pose(actor.skeleton.find_bone("Hip")).origin
			max_contact_error=maxf(max_contact_error,actor.foot_lock.contact_error)
			trace.append({"stage":stage[0],"speed":actor.speed,"phase":actor.phase,"run_weight":actor.run_blend,
				"move_weight":actor.move_blend,"cycle_distance":actor.cycle_distance,"rate":actor.playback_rate,
				"hip":var_to_str(hip),"contact_error":actor.foot_lock.contact_error})
	var stopped: bool=actor.speed<.01 and actor.clip=="idle"
	lab.record=false
	# A colliding actor must use actual displacement, and settle into idle.
	actor.position=Vector3(-7,.1,-4);actor.velocity=Vector3.ZERO
	actor.scripted_input=Vector2(0,-1)
	await lab.get_tree().create_timer(1.3).timeout
	var wall: bool=actor.position.z> -5.7 and actor.speed<.05 and actor.move_blend<.03
	actor.position=Vector3(7,.1,.35);actor.velocity=Vector3.ZERO
	await lab.get_tree().create_timer(1.4).timeout
	var ramp: bool=actor.position.y>.6 and actor.position.y<1.5
	actor.scripted_input=Vector2.ZERO
	var result := {"samples":trace.size(),"stop_idle":stopped,"wall_stop":wall,"ramp":ramp,
		"max_motor_excess_m":max_motor_excess,"max_joint_step_deg_per_60hz":max_joint_step,
		"max_foot_step_m_per_60hz":max_foot_step,"provider_calls":0,
		"max_foot_stage":max_foot_stage,"max_joint_bone":max_joint_bone,
		"max_planted_contact_error_m":max_contact_error,
		"pass":stopped and wall and ramp and max_motor_excess<.02 and max_joint_step<25 and max_foot_step<.18 and max_contact_error<.04}
	var out: String=lab.capture_dir if not lab.capture_dir.is_empty() else ProjectSettings.globalize_path("res://")
	var file := FileAccess.open(out.path_join("transition-trace.json"),FileAccess.WRITE);file.store_string(JSON.stringify(trace));file.close()
	file=FileAccess.open(out.path_join("transition-result.json"),FileAccess.WRITE);file.store_string(JSON.stringify(result,"  "));file.close()
	return result
