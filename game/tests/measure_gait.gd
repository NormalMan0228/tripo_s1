extends SceneTree
func _initialize() -> void:call_deferred("measure")
func measure() -> void:
	var player=preload("res://scripts/player.gd").new();root.add_child(player)
	player.set_physics_process(false);player.locomotion_pose.active=false
	player.finger_pose.active=false;player.action_pose.active=false
	var sk: Skeleton3D=player.hand_skeleton
	var report: Dictionary={}
	var forward: Vector3=-player.visual.global_basis.z
	for kind in ["walk","run"]:
		var animation: Animation=player.animation_player.get_animation(kind)
		var count := 120
		var points: Array=[]
		player.animation_player.play(kind,0)
		for i in count:
			player.animation_player.seek(animation.length*i/count,true)
			sk.force_update_all_bone_transforms()
			var sample: Dictionary={}
			for side in ["L","R"]:
				var p: Vector3=sk.global_transform*sk.get_bone_global_pose(sk.find_bone(side+"_Foot")).origin-player.global_position
				sample[side]=Vector2(p.dot(forward),p.y)
			points.append(sample)
		var gait: Dictionary={}
		for side in ["L","R"]:
			var low := INF;var high := -INF
			for point in points:low=minf(low,point[side].y);high=maxf(high,point[side].y)
			var mask: Array=[]
			for point in points:mask.append(point[side].y<low+.035)
			gait[side+"_mask"]=mask;gait[side+"_height_range"]=high-low
		var candidates: Array=[];var slopes: Array=[]
		for i in count:
			if gait.L_mask[i]:candidates.append(i)
			if i<count-1 and gait.L_mask[i] and gait.L_mask[i+1] and points[i+1].L.x<points[i].L.x:
				slopes.append(-(points[i+1].L.x-points[i].L.x)*count)
		var onset: int=candidates[0]
		for i in candidates:
			if points[i].L.x>points[onset].L.x:onset=i
		slopes.sort()
		gait.phase_offset=float(onset)/count
		gait.distance=clampf(slopes[slopes.size()/2] if not slopes.is_empty() else .9,.4,2.4)
		gait.seconds=animation.length;report[kind]=gait
	var f := FileAccess.open("res://../artifacts/production-lab-20261003/source-gait-measurement.json",FileAccess.WRITE);f.store_string(JSON.stringify(report,"  "));f.close()
	print("GAIT_MEASURED ",JSON.stringify({"walk_distance":report.walk.distance,"run_distance":report.run.distance,"walk_offset":report.walk.phase_offset,"run_offset":report.run.phase_offset}))
	player.queue_free();await process_frame;quit()
