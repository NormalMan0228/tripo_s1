extends SceneTree
## ISS-1 rig map and pose layer (S-WP2), offline on the shipped Player: every humanoid bone maps on the
## three Explorer B GLBs, the seated seat_contact lands on seats of 0.30/0.45/0.60 m with the knees in
## front and the feet on the floor, lying keeps the body upright with the hips on the mattress, and
## fading the pose in and out never turns a joint more than 25 degrees in one tick.
##   godot --headless --path game --script res://tests/ix_pose_check.gd
const IxRig = preload("res://scripts/ix/ix_rig.gd")
const IxPose = preload("res://scripts/ix/ix_pose.gd")
const IxMath = preload("res://scripts/ix/ix_math.gd")

var failures: Array[String] = []
var passes := 0
var report := {}
var player: CharacterBody3D
var sample := {}
var last_rot := {}
var max_step := 0.0
var max_step_bone := ""
var tracking := false

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if value: passes += 1
	else: failures.append(label)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	profiles()
	var stage := Node3D.new()
	root.add_child(stage)
	var floor := StaticBody3D.new()
	stage.add_child(floor)
	var shape := CollisionShape3D.new()
	floor.add_child(shape)
	var box := BoxShape3D.new()
	box.size = Vector3(20, 0.2, 20)
	shape.shape = box
	floor.position.y = -0.1
	player = load("res://scripts/player.gd").new()
	stage.add_child(player)
	for i in 4: await physics_frame
	await process_frame
	var skel: Skeleton3D = player.hand_skeleton
	var m := IxRig.measure(skel, player.visual)
	check(IxRig.detect(skel) == "vrs" and m.ok, "the walker's rig is the Explorer B profile (%s)" % IxRig.detect(skel))
	var seat_node = load("res://scripts/rest_seat.gd").new()
	stage.add_child(seat_node)
	seat_node.hero = player
	check(absf(float(m.hip_height) - float(seat_node.hip_height())) < 0.001, "hip height matches rest_seat (%.3f / %.3f)" % [m.hip_height, seat_node.hip_height()])
	report["measure"] = {"hip_height": m.hip_height, "thigh": m.thigh, "shin": m.shin, "ankle": m.ankle, "seat_contact": str(m.seat_contact), "pelvis": str(m.pelvis)}
	var pose: SkeletonModifier3D = IxPose.attach(player)
	check(is_instance_valid(pose) and pose.get_index() < player.locomotion_pose.get_index(), "the pose layer runs before locomotion_pose's limiter")
	check(IxPose.attach(player) == pose, "attaching again reuses the one layer")
	player.locomotion_pose.modification_processed.connect(_sampled)
	pose.driven = true
	player.visual_only = true
	var yaw := 0.6
	var facing := IxMath.dir_of(yaw)
	player.facing = facing
	player.visual.rotation.y = atan2(-facing.x, -facing.z)
	# Seats: hips on the seat, knees forward, feet on the floor.
	for height in [0.30, 0.45, 0.60]:
		var variant := IxMath.sit_variant(height)
		pose.set_preset(variant)
		var drop: float = height + float(m.seat_drop) - float(m.ankle)
		pose.plant_legs(m, drop)
		var s := Vector3(1.0, height, -0.5)
		player.global_position = IxMath.hold_root(s, yaw, m.seat_contact)
		await ramp(pose, 0.0, 1.0, 0.4)
		for i in 6: await physics_frame
		var contact: Vector3 = sample.contact
		var error := contact.distance_to(s)
		var knee_ahead: float = (sample.knee - sample.hip).dot(facing)
		var feet: float = sample.foot_y - float(m.ankle)
		report["seat_%.2f" % height] = {"variant": variant, "contact_cm": error * 100.0, "knee_ahead": knee_ahead, "ankle_above_floor_cm": feet * 100.0}
		check(error <= 0.03, "seat %.2f m: seat_contact on the seat (%.1f cm)" % [height, error * 100.0])
		check(knee_ahead > 0.2, "seat %.2f m: knees bend forward (%.2f m ahead of the hips)" % [height, knee_ahead])
		check(absf(feet) <= 0.06, "seat %.2f m: feet on the floor (%.1f cm)" % [height, feet * 100.0])
		await ramp(pose, 1.0, 0.0, 0.3)
	# Lying: the body stays upright, the skeleton turns about the hips onto the mattress.
	pose.set_preset("lie")
	var mattress := Vector3(-1.0, 0.5, 0.8)
	player.global_position = IxMath.hold_root(mattress + Vector3(0, float(m.lie_lift), 0), yaw, m.pelvis)
	await ramp(pose, 0.0, 1.0, 0.5)
	for i in 6: await physics_frame
	var hip_error: float = sample.hips.distance_to(mattress + Vector3(0, float(m.lie_lift), 0))
	var flat: float = absf(sample.head.y - sample.hips.y)
	var head_back: float = (sample.head - sample.hips).dot(-facing)
	report["lie"] = {"hips_cm": hip_error * 100.0, "head_height_over_hips": sample.head.y - sample.hips.y, "head_back": head_back}
	check(player.global_basis.is_equal_approx(Basis.IDENTITY), "lying keeps the body basis identity")
	check(hip_error <= 0.03, "lying: hips at mattress +0.12 (%.1f cm)" % (hip_error * 100.0))
	check(flat < 0.2 and head_back > 0.3, "lying: the head lies back level with the hips (dy %.2f, back %.2f)" % [sample.head.y - sample.hips.y, head_back])
	await ramp(pose, 1.0, 0.0, 0.4)
	# Fades in and out: no joint turns more than 25 degrees in one tick.
	pose.set_preset("sit")
	player.global_position = Vector3.ZERO
	max_step = 0.0
	last_rot.clear()
	tracking = true
	await ramp(pose, 0.0, 1.0, 0.45)
	await ramp(pose, 1.0, 0.0, 0.35)
	pose.set_preset("lie")
	await ramp(pose, 0.0, 1.0, 0.7)
	await ramp(pose, 1.0, 0.0, 0.5)
	tracking = false
	report["max_joint_step_deg"] = max_step
	report["max_joint_step_bone"] = max_step_bone
	check(max_step < 25.0, "fading the pose never turns a joint over 25 degrees in a tick (%.1f, %s)" % [max_step, max_step_bone])
	# Weight 0: the layer leaves the walker's own pose alone.
	pose.weight = 0.0
	for i in 3: await physics_frame
	var with_layer: Quaternion = sample.thigh_rot
	pose.active = false
	await physics_frame
	var without: Quaternion = sample.thigh_rot
	pose.active = true
	check(rad_to_deg(with_layer.angle_to(without)) < 3.0, "at weight 0 the legs follow the clip (%.2f deg)" % rad_to_deg(with_layer.angle_to(without)))
	# Cost: one full pose (hips, root tilt, six leg bones, spine, arms) on the walker's skeleton.
	var cfg := IxPose.configure(skel, player.visual)
	var t0 := Time.get_ticks_usec()
	for i in 500: IxPose.pose_skeleton(skel, cfg, 1.5, -1.55, -0.1, 0.35, 0.7, 0.3, 0.0, Basis.IDENTITY, 1.0)
	var per_call := (Time.get_ticks_usec() - t0) / 500.0
	report["pose_cost_us"] = per_call
	check(per_call < 400.0, "one pose costs %.0f us (budget 400)" % per_call)
	# The fallback (no driver): mode alone eases the pose in and out.
	pose.driven = false
	pose.mode = "sit"
	for i in 30: await physics_frame
	check(absf(pose.weight - 1.0) < 1e-4 and pose.mode == "sit", "without a driver, mode 'sit' eases the pose in")
	pose.mode = ""
	for i in 30: await physics_frame
	check(pose.weight == 0.0, "and mode '' eases it out")
	print("IX_POSE_CHECK ", JSON.stringify({"ok": failures.is_empty(), "passed": passes, "failures": failures, "report": report}))
	stage.queue_free()
	await process_frame
	quit(0 if failures.is_empty() else 1)

func ramp(pose: SkeletonModifier3D, from: float, to: float, seconds: float) -> void:
	var ticks := maxi(1, int(round(seconds * 60.0)))
	for i in ticks + 1:
		pose.weight = lerpf(from, to, smoothstep(0.0, 1.0, float(i) / ticks))
		await physics_frame

## The final pose, read in the last modifier's signal (Skeleton3D restores the base pose after drawing).
func _sampled() -> void:
	var skel: Skeleton3D = player.hand_skeleton
	var g := func(name: String) -> Vector3: return skel.global_transform * skel.get_bone_global_pose(IxRig.bone(skel, name)).origin
	var lt: Vector3 = g.call("LeftUpperLeg")
	var rt: Vector3 = g.call("RightUpperLeg")
	sample.hip = (lt + rt) * 0.5
	sample.contact = sample.hip - Vector3(0, IxRig.SEAT_DROP, 0)
	sample.knee = (g.call("LeftLowerLeg") + g.call("RightLowerLeg")) * 0.5
	sample.foot_y = (g.call("LeftFoot").y + g.call("RightFoot").y) * 0.5
	sample.hips = g.call("Hips")
	sample.head = g.call("Head")
	sample.thigh_rot = skel.get_bone_pose_rotation(IxRig.bone(skel, "LeftUpperLeg"))
	if not tracking: return
	for i in skel.get_bone_count():
		var name := skel.get_bone_name(i)
		if name.begins_with("Face_"): continue
		var q := skel.get_bone_pose_rotation(i)
		if last_rot.has(i):
			var step := rad_to_deg((last_rot[i] as Quaternion).angle_to(q))
			if step > max_step:
				max_step = step
				max_step_bone = name
		last_rot[i] = q

func profiles() -> void:
	for path in ["res://assets/explorer_b_wardrobe.glb", "res://assets/explorer_b_reference.glb", "res://assets/explorer_b_motion.glb"]:
		var scene := (load(path) as PackedScene).instantiate()
		var skeletons := scene.find_children("*", "Skeleton3D", true, false)
		var missing: Array = []
		if skeletons.is_empty(): missing.append("skeleton")
		else:
			var skel: Skeleton3D = skeletons[0]
			for humanoid in IxRig.HUMANOID:
				var finger := false
				for digit in ["Thumb", "Index", "Middle", "Ring", "Little"]:
					if digit in humanoid: finger = true
				if IxRig.bone(skel, humanoid) < 0 and not finger: missing.append(humanoid)
		check(missing.is_empty(), "every body bone maps on %s %s" % [path.get_file(), str(missing)])
		scene.free()
