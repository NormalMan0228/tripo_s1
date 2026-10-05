extends SceneTree
## Exercises the actual shipped Player without accounts, server or paid services.
func _initialize() -> void:call_deferred("run_review")
func run_review() -> void:
	var stage := Node3D.new();root.add_child(stage)
	var floor := StaticBody3D.new();stage.add_child(floor)
	var shape := CollisionShape3D.new();floor.add_child(shape)
	var box := BoxShape3D.new();box.size=Vector3(80,.2,80);shape.shape=box;floor.position.y=-.1
	var player=preload("res://scripts/player.gd").new();stage.add_child(player)
	await process_frame
	var previous_position: Vector3=player.position
	var previous: Array=[]
	var previous_phase := 0.0
	var max_step := 0.0
	var max_step_bone := ""
	var max_step_clip := ""
	var max_excess := 0.0
	var max_phase_error := 0.0
	var transition_count := 0
	var trace: Array=[]
	var previous_clip := ""
	var previous_frame := Engine.get_physics_frames()
	for segment in [["idle",false,false,20],["walk",true,false,73],["run",true,true,81],["walk",true,false,67],["idle",false,false,25]]:
		player.sprinting=segment[2]
		if segment[1]:Input.action_press("move_right")
		else:Input.action_release("move_right")
		for frame in segment[3]:
			await physics_frame;await process_frame
			var frame_now := Engine.get_physics_frames()
			var dt := maxf(1.0/60,float(frame_now-previous_frame)/60);previous_frame=frame_now
			var speed: float=player.locomotion_velocity.length()
			max_excess=maxf(max_excess,player.position.distance_to(previous_position)-4.5*dt-.001)
			previous_position=player.position
			var rotations: Array=[]
			for i in player.hand_skeleton.get_bone_count():
				# SkeletonModifier restores the base pose after submission to the skin.
				# Sample the modifier's final rotation for corrected leg bones.
				var q: Quaternion=player.locomotion_pose.previous_solved.get(i,player.hand_skeleton.get_bone_pose_rotation(i));rotations.append(q)
				if not previous.is_empty():
					var step := rad_to_deg(q.angle_to(previous[i]))/maxf(1,dt*60)
					if step>max_step:
						max_step=step;max_step_bone=player.hand_skeleton.get_bone_name(i);max_step_clip=player.current_clip
			previous=rotations
			if player.current_clip!=previous_clip and previous_clip in ["walk","run"] and player.current_clip in ["walk","run"]:
				var expected := fposmod(previous_phase+dt/player.locomotion_pose.cycle_for_speed(speed),1)
				max_phase_error=maxf(max_phase_error,absf(wrapf(player.gait_phase-expected,-.5,.5)))
				transition_count+=1
			previous_phase=player.gait_phase;previous_clip=player.current_clip
			trace.append({"clip":player.current_clip,"speed":speed,"phase":player.gait_phase,"ik_phase":player.locomotion_pose.phase,"contact_error":player.locomotion_pose.contact_error})
	Input.action_release("move_right")
	var out := ProjectSettings.globalize_path("res://../artifacts/production-lab-20261003")
	var report := {"samples":trace.size(),"gait_transitions":transition_count,"max_transition_phase_error":max_phase_error,
		"max_joint_step_deg_per_60hz":max_step,"max_step_bone":max_step_bone,"max_step_clip":max_step_clip,"max_motor_excess_m":max_excess,"idle_after_release":player.current_clip=="idle",
		"finger_samples":player.finger_pose.samples.size(),"provider_calls":0,
		"pass":transition_count==2 and max_phase_error<.0001 and max_excess<.001 and max_step<25 and player.current_clip=="idle"}
	var f := FileAccess.open(out.path_join("game-continuity.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"  "));f.close()
	f=FileAccess.open(out.path_join("game-continuity-trace.json"),FileAccess.WRITE);f.store_string(JSON.stringify(trace));f.close()
	print("GAME_CONTINUITY ",JSON.stringify(report));stage.queue_free();await process_frame;quit(0 if report.pass else 1)
