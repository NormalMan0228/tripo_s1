extends SceneTree
## Verify the delivered clips and transitions on imported Godot skeletons.
var report: Dictionary={"clips":{},"transitions":{},"provider_calls":0}

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var review := load("res://review.tscn").instantiate() as Control
	root.add_child(review);review.set_process(false);review.playing=false
	await process_frame
	var max_steps := 0.0
	for index in 3:
		var player: AnimationPlayer=review.players[index]
		var skeleton: Skeleton3D=review.skeletons[index]
		for suffix in ["_sequence","_loop"]:
			var clip: String=review.SOURCES[index]+suffix
			player.play(clip)
			var duration: float=player.get_animation(clip).length
			var frames := roundi(duration*60)
			var previous: Array=[];var first: Array=[];var step_max := 0.0
			var hip := skeleton.find_bone("Hip");var hip_x_min := INF;var hip_x_max := -INF
			var previous_hip := Vector3.ZERO;var hip_step_max := 0.0
			for frame in range(frames+1):
				player.seek(minf(float(frame)/60.0,duration-.00001),true);player.advance(0)
				var poses: Array=[]
				for bone in skeleton.get_bone_count():
					var q := skeleton.get_bone_pose_rotation(bone);poses.append(q)
					if not previous.is_empty():step_max=maxf(step_max,rad_to_deg(q.angle_to(previous[bone])))
				if first.is_empty():first=poses.duplicate()
				previous=poses
				var hip_position := skeleton.get_bone_global_pose(hip).origin
				if frame>0:hip_step_max=maxf(hip_step_max,hip_position.distance_to(previous_hip)*1.7)
				previous_hip=hip_position
				var x := hip_position.x
				hip_x_min=minf(hip_x_min,x);hip_x_max=maxf(hip_x_max,x)
			var endpoint := 0.0
			for bone in skeleton.get_bone_count():endpoint=maxf(endpoint,rad_to_deg(first[bone].angle_to(previous[bone])))
			report.clips[clip]={"seconds":duration,"frames":frames+1,"max_joint_step_deg_60hz":step_max,
				"horizontal_hip_range_game_m":(hip_x_max-hip_x_min)*1.7,"endpoint_rotation_gap_deg":endpoint,
				"max_hip_step_game_m_60hz":hip_step_max}
			max_steps=maxf(max_steps,step_max)
	# Use the actual comparison UI's transition code at both frame rates.
	for fps in [30,60]:
		review.loops=false;review.select_clips();review.time=2.1;review.apply_time()
		var previous: Array=[];var previous_hips: Array=[]
		for skeleton in review.skeletons:
			var row: Array=[]
			for bone in skeleton.get_bone_count():row.append(skeleton.get_bone_pose_rotation(bone))
			previous.append(row)
			previous_hips.append(skeleton.get_bone_global_pose(skeleton.find_bone("Hip")).origin)
		review.toggle_mode()
		var max_transition := 0.0;var max_hip_transition := 0.0
		for frame in 20:
			review.time+=1.0/float(fps);review.transition_alpha=minf(1.0,review.transition_alpha+1.0/float(fps)/.24);review.apply_time()
			for index in 3:
				var skeleton: Skeleton3D=review.skeletons[index]
				var hip_position := skeleton.get_bone_global_pose(skeleton.find_bone("Hip")).origin
				max_hip_transition=maxf(max_hip_transition,hip_position.distance_to(previous_hips[index])*1.7*float(fps)/60.0)
				previous_hips[index]=hip_position
				for bone in skeleton.get_bone_count():
					var q := skeleton.get_bone_pose_rotation(bone)
					max_transition=maxf(max_transition,rad_to_deg(q.angle_to(previous[index][bone]))*float(fps)/60.0)
					previous[index][bone]=q
		report.transitions[str(fps)+"fps"]={"max_joint_step_deg_60hz":max_transition,"blend_seconds":.24,
			"max_hip_step_game_m_60hz":max_hip_transition}
	var loops_closed := true
	for clip in report.clips:
		if clip.ends_with("_loop") and report.clips[clip].endpoint_rotation_gap_deg>.2:loops_closed=false
	report.pass=report.clips.size()==6 and max_steps<12 and loops_closed
	for result in report.clips.values():report.pass=report.pass and result.max_hip_step_game_m_60hz<.08
	for result in report.transitions.values():report.pass=report.pass and result.max_joint_step_deg_60hz<15 and result.max_hip_step_game_m_60hz<.08
	var output := "C:/lsm26/triphthonS1/artifacts/video-motion-20261003/godot-acceptance.json"
	var file := FileAccess.open(output,FileAccess.WRITE);file.store_string(JSON.stringify(report,"\t"));file.close()
	print("VIDEO_MOTION_ACCEPTANCE ",JSON.stringify(report))
	quit(0 if report.pass else 1)
