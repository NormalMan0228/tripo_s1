extends SceneTree
## Headless checks for the world-presentation pass (no server):
##  - stairs: a room's stair climb plays the walk clip, never a gliding idle pose.
##  - gait: walking, sharp turns, reversals, stops, running and an attack keep the
##    lower body with the upper body (hips square to the chest, knees bending forward,
##    feet on their own side, planted feet on the ground up and down a slope) in
##    the final drawn pose.
##   Godot --headless --path game --script res://tests/world_polish_check.gd [-- --only=stairs]
var failures: Array[String] = []
var only := ""

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--only="): only = arg.trim_prefix("--only=")
	call_deferred("run")
	create_timer(300).timeout.connect(func():
		push_error("world_polish_check exceeded 300 seconds")
		quit(2))

func check(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failures.append(description)

func wants(name: String) -> bool:
	return only.is_empty() or only == name

func run() -> void:
	if wants("stairs"): await stairs()
	if wants("gait"): await gait()
	print("WORLD_POLISH ", JSON.stringify({"ok":failures.is_empty(), "failures":failures}))
	quit(0 if failures.is_empty() else 1)

## Climbs a straight staircase and the lighthouse's spiral: while the walker is on
## the stair (above the floor) the walk clip runs and the body reports motion.
func stairs() -> void:
	Engine.set_meta("interior_hour", 13.0)
	for room in ["home", "17_lighthouse"]:
		Engine.set_meta("studio_session", {"token":"", "url":"http://127.0.0.1:9", "room":room})
		var studio: Control = load("res://scenes/studio.tscn").instantiate()
		root.add_child(studio)
		await create_timer(0.8).timeout
		var record: Dictionary = {}
		for item in studio.decor:
			if item.has("link"):
				record = item
				break
		check(not record.is_empty(), "%s has a stair" % room)
		if record.is_empty(): continue
		var front := Vector3(0, 0, 1).rotated(Vector3.UP, float(record.yaw))
		for distance in [0.7, 0.9, 1.1, 1.4]:
			var at: Vector3 = record.center+front*(float(record.half.y)+distance)
			at.y = 0
			if studio.can_stand(at):
				studio.hero.position = at
				break
		await create_timer(0.3).timeout
		studio.travel(record)
		var climbing := 0
		var walking := 0
		for i in 120:
			await physics_frame
			if studio.floor_index != 0 or not studio.travelling: break
			if studio.hero.position.y > 0.05:
				climbing += 1
				if studio.hero.current_clip == "walk" and studio.hero.locomotion_velocity.length() > 0.5: walking += 1
		check(climbing > 20, "%s: the walker climbs the %s (%d frames)" % [room, record.kind, climbing])
		check(walking >= climbing*0.9, "%s: the walk clip runs on the %s (%d of %d frames)" % [room, record.kind, walking, climbing])
		studio.queue_free()
		await process_frame
		await process_frame
	Engine.remove_meta("interior_hour")

## ------------------------------------------------------------------ gait

var walker: CharacterBody3D
var skeleton: Skeleton3D
var bones := {}
var worst := {}
var phase_name := ""
var samples := 0
var ankle_height := 0.0

## Drives the village walker with the real input actions over a flat floor and reads
## every final pose (after the contact IK) the skeleton draws.
func gait() -> void:
	var stage := Node3D.new()
	root.add_child(stage)
	var floor_body := StaticBody3D.new()
	floor_body.collision_layer = 1
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(200, 1, 200)
	shape.shape = box
	shape.position.y = -0.5
	floor_body.add_child(shape)
	stage.add_child(floor_body)
	walker = load("res://scripts/player.gd").new()
	stage.add_child(walker)
	await physics_frame
	await physics_frame
	skeleton = walker.hand_skeleton
	for bone in ["Pelvis", "L_Thigh", "R_Thigh", "L_Calf", "R_Calf", "L_Foot", "R_Foot", "L_Upperarm", "R_Upperarm"]:
		bones[bone] = skeleton.find_bone(bone)
	check(not bones.values().has(-1), "gait: the rig has hips, legs and shoulders")
	if bones.values().has(-1): return
	ankle_height = point("L_Foot").y-walker.global_position.y
	skeleton.skeleton_updated.connect(sample)
	var steps := [["idle", [], 0.6], ["walk", ["move_forward"], 1.6], ["turn right", ["move_right"], 1.0],
		["reverse", ["move_left"], 1.0], ["diagonal", ["move_back", "move_left"], 0.8], ["stop", [], 0.8],
		["run", ["move_forward", "run"], 1.4], ["run reverse", ["move_back", "run"], 1.0], ["run stop", [], 0.8],
		["zigzag", ["move_left"], 0.25], ["zigzag", ["move_right"], 0.25], ["zigzag", ["move_left"], 0.25], ["zigzag", ["move_right"], 0.25],
		["settle", [], 0.8], ["attack", [], 0.6], ["to ramp", [], 0.1], ["uphill", ["move_forward"], 2.2], ["downhill", ["move_back"], 2.2], ["ramp stop", [], 0.6]]
	for step in steps:
		phase_name = step[0]
		if phase_name == "attack": walker.react("attack")
		if phase_name == "to ramp":
			# An 18 degree slope (the island's steeper paths) rising toward -Z.
			var ramp := StaticBody3D.new()
			var slope := CollisionShape3D.new()
			var plank := BoxShape3D.new()
			plank.size = Vector3(6, 1, 14)
			slope.shape = plank
			ramp.add_child(slope)
			stage.add_child(ramp)
			ramp.position = Vector3(40, -0.5*cos(deg_to_rad(18.0))+0.02, -2.0)
			ramp.rotation.x = deg_to_rad(18.0)
			walker.global_position = Vector3(40, 0.05, 6.5)
			walker.velocity = Vector3.ZERO
		for action in step[1]: Input.action_press(action)
		await create_timer(float(step[2])).timeout
		for action in step[1]: Input.action_release(action)
	skeleton.skeleton_updated.disconnect(sample)
	for key in worst: print("GAIT worst %s = %.3f (%s)" % [key, worst[key][0], worst[key][1]])
	check(samples > 400, "gait: sampled %d drawn poses" % samples)
	check(worst.hip_twist[0] < 40.0, "gait: hips stay square to the chest (worst %.1f deg, %s)" % worst.hip_twist)
	check(worst.knee_back[0] < 0.035, "gait: knees never fold backwards (worst %.3f m, %s)" % worst.knee_back)
	check(worst.feet_cross[0] < 0.06, "gait: feet stay on their own side (worst %.3f m, %s)" % worst.feet_cross)
	check(worst.hip_yaw[0] < 40.0, "gait: hips face where the body faces (worst %.1f deg, %s)" % worst.hip_yaw)
	check(worst.knee_flex[0] < 100.0, "gait: knees bend no deeper than a stride (worst %.1f deg, %s)" % worst.knee_flex)
	check(worst.plant_gap[0] < 0.2, "gait: planted feet stay on the ground, slopes too (worst %.3f m, %s)" % worst.plant_gap)
	stage.queue_free()
	await process_frame

func note(key: String, value: float) -> void:
	if not worst.has(key) or value > worst[key][0]: worst[key] = [value, phase_name]

func point(bone: String) -> Vector3:
	return skeleton.global_transform*skeleton.get_bone_global_pose(bones[bone]).origin

func flat(v: Vector3) -> Vector3:
	return Vector3(v.x, 0, v.z).normalized()

func sample() -> void:
	samples += 1
	var forward := flat(-walker.visual.global_basis.z)
	var right := forward.cross(Vector3.UP)
	# Right is whichever thigh / shoulder the body's right side holds.
	var hips := flat(point("R_Thigh")-point("L_Thigh"))
	var shoulders := flat(point("R_Upperarm")-point("L_Upperarm"))
	if hips.dot(right) < 0.0: hips = -hips
	if shoulders.dot(right) < 0.0: shoulders = -shoulders
	note("hip_twist", rad_to_deg(hips.angle_to(shoulders)))
	note("hip_yaw", rad_to_deg(hips.angle_to(right)))
	for side in ["L", "R"]:
		var hip := point(side+"_Thigh")
		var knee := point(side+"_Calf")
		var foot := point(side+"_Foot")
		var line := (foot-hip).normalized()
		var bend := (knee-hip)-line*(knee-hip).dot(line)
		note("knee_back", maxf(0.0, -bend.dot(forward)))
	var pose: SkeletonModifier3D = walker.locomotion_pose
	for i in pose.legs.size():
		var leg: Dictionary = pose.legs[i]
		var hip := point(["L", "R"][i]+"_Thigh")
		var knee := point(["L", "R"][i]+"_Calf")
		var foot := point(["L", "R"][i]+"_Foot")
		note("knee_flex", 180.0-rad_to_deg((hip-knee).angle_to(foot-knee)))
		if leg.contact and pose.blend > 0.9:
			var ray := PhysicsRayQueryParameters3D.create(foot+Vector3.UP*0.6, foot+Vector3.DOWN*0.8, 1)
			var hit := walker.get_world_3d().direct_space_state.intersect_ray(ray)
			if not hit.is_empty(): note("plant_gap", absf(foot.y-hit.position.y-ankle_height))
	var left_side := (point("L_Foot")-point("R_Foot")).dot(right)
	var thighs := (point("L_Thigh")-point("R_Thigh")).dot(right)
	# The feet cross when they sit on the opposite sides of the thighs' order.
	note("feet_cross", maxf(0.0, -left_side*signf(thighs)))
