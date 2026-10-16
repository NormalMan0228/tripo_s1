extends SceneTree
## Sitting and lying follow the piece's turn (user, 2026-10-16: "가구를 사용가능하면 이것도 방향 잘
## 맞춰야함 배치 각도에 따라서"). A chair, a bed, a bench and a rocking chair are each turned to
## 0/45/90/135/180/270 degrees, and a chair also stands on a raised platform (a piece put on top of
## another one). For every case the real Player walks up, sits or lies down, and gets up again
## through rest_seat.gd and the ISS-1 driver, and this records:
##   seated facing error  the body's facing in HOLD against the socket's own yaw (and, for seats,
##                        against the piece's front: it must face the way the piece faces)
##   exit facing error    getting up facing out of the seat
##   step / turn          the largest body move and visual turn in one tick (teleport check:
##                        <= 0.08 m and <= 0.35 rad, the motion continuity limits)
##   joints               the largest joint rotation in one tick (< 25 degrees)
##   contact              the seat contact (or the hips lying) against the socket in HOLD
##   exit clear           a fixed capsule at the exit spot meets no furniture (not stuck)
## Prints IX_ANGLES <json> and writes artifacts/ix_angles.json for the result sheet.
##   godot --headless --path game --script res://tests/ix_angles_check.gd
const Kit = preload("res://tests/ix_fixture_kit.gd")
const IxRig = preload("res://scripts/ix/ix_rig.gd")
const IxMath = preload("res://scripts/ix/ix_math.gd")
const IxSources = preload("res://scripts/ix/ix_sources.gd")
const Driver = preload("res://scripts/ix/ix_driver.gd")
const ANGLES := [0.0, 45.0, 90.0, 135.0, 180.0, 270.0]
const STEP_LIMIT := 0.08
const TURN_LIMIT := 0.35
const JOINT_LIMIT := 25.0
const FACE_LIMIT := 8.0

var failures: Array[String] = []
var rows: Array = []
var stage: Node3D
var player: CharacterBody3D
var seat: Node
var joint_step := 0.0
var last_rot := {}
var sample_contact := Vector3.ZERO
var sample_hips := Vector3.ZERO

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if not value: failures.append(label)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	stage = Node3D.new()
	root.add_child(stage)
	Kit.floor_body(stage, 60.0)
	player = load("res://scripts/player.gd").new()
	stage.add_child(player)
	seat = load("res://scripts/rest_seat.gd").new()
	stage.add_child(seat)
	seat.keep_height = true
	seat.hero = player
	for i in 4: await physics_frame
	if is_instance_valid(player.locomotion_pose): player.locomotion_pose.modification_processed.connect(_sampled)
	var arch := Kit.archetypes()
	var kinds := [["chair", Kit.box_chair(0.45), "sit", 0.45], ["bed", Kit.box_bed(), "lie", 0.45],
		["bench", arch.bench, "sit", -1.0], ["rocking_chair", arch.rocking_chair, "sit", -1.0]]
	var spot := 0
	for kind in kinds:
		for angle in ANGLES:
			var node := place(kind[1], Vector3((spot % 6) * 7.0 - 17.0, 0, int(spot / 6) * 7.0 - 10.0), angle)
			spot += 1
			await physics_frame
			await cycle("%s %d°" % [kind[0], int(angle)], kind[0], node, kind[2], angle, 0.0)
			node.queue_free()
	# Stacked: a chair standing on a 0.18 m platform (a piece put on another piece).
	for angle in [0.0, 90.0, 225.0]:
		# A flat deck turned with the chair, as a stack moves and turns together.
		var platform := Kit.build({"id": "platform", "rest": "sit", "parts": [{"id": "deck", "parent": "", "shape": "box", "size": [1.6, 0.18, 1.6], "position": [0, 0.09, 0], "rotation": [0, 0, 0], "pivot": [0, 0, 0]}]})
		stage.add_child(platform)
		var at := Vector3((spot % 6) * 7.0 - 17.0, 0, int(spot / 6) * 7.0 - 10.0)
		spot += 1
		platform.position = at
		platform.rotation_degrees.y = angle
		var node := place(Kit.box_chair(0.45), at + Vector3(0, 0.18, 0), angle)
		await physics_frame
		await cycle("stacked chair %d°" % int(angle), "stacked_chair", node, "sit", angle, 0.18)
		node.queue_free()
		platform.queue_free()
	check(Driver.claims.is_empty(), "no seat stays claimed")
	var report := {"ok": failures.is_empty(), "failures": failures, "rows": rows,
		"limits": {"step_m": STEP_LIMIT, "turn_rad": TURN_LIMIT, "joint_deg": JOINT_LIMIT, "face_deg": FACE_LIMIT}}
	var file := FileAccess.open("res://../artifacts/ix_angles.json", FileAccess.WRITE)
	if file: file.store_string(JSON.stringify(report, "  "))
	print("IX_ANGLES ", JSON.stringify({"ok": report.ok, "failures": failures, "cases": rows.size()}))
	stage.queue_free()
	await process_frame
	quit(0 if failures.is_empty() else 1)

func place(arch: Dictionary, at: Vector3, yaw_deg: float) -> Node3D:
	var node := Kit.build(arch)
	stage.add_child(node)
	node.position = at
	node.rotation_degrees.y = yaw_deg
	return node

## The walker a metre or so in front and to the side, looking somewhere else.
func stand_near(node: Node3D) -> void:
	var front := IxMath.dir_of(node.rotation.y)
	var at: Vector3 = node.global_position + front * 1.1 + front.cross(Vector3.UP) * 0.4
	player.global_position = Vector3(at.x, 0.02, at.z)
	player.facing = -front.rotated(Vector3.UP, 0.7)
	player.velocity = Vector3.ZERO
	for i in 8: await physics_frame

func cycle(label: String, kind: String, node: Node3D, hint: String, angle: float, lift: float) -> void:
	await stand_near(node)
	var row := {"case": label, "kind": kind, "angle": angle, "lift": lift, "ok": false}
	rows.append(row)
	joint_step = 0.0
	last_rot.clear()
	seat.crafted(node, hint)
	var driver: Node = seat.driver
	if not is_instance_valid(driver) or not driver.busy():
		row["why"] = driver.why if is_instance_valid(driver) else "no driver"
		check(false, "%s: starts (%s)" % [label, row.why])
		return
	var step := 0.0
	var step_where := ""
	var turn := 0.0
	var last_pos: Vector3 = player.global_position
	var last_yaw: float = player.visual.rotation.y
	var seated := -1.0
	var t := 0.0
	while t < 4.0:
		await physics_frame
		t += 1.0 / 60.0
		var moved := player.global_position.distance_to(last_pos)
		if moved > step: step_where = "%s %s dy=%.3f" % [driver.state_name(), str(driver.phase_t), player.global_position.y - last_pos.y]
		step = maxf(step, moved)
		turn = maxf(turn, absf(angle_difference(last_yaw, player.visual.rotation.y)))
		last_pos = player.global_position
		last_yaw = player.visual.rotation.y
		if driver.state == Driver.HOLD:
			seated = t
			break
	row["seated_s"] = seated
	if seated < 0.0:
		row["why"] = "never seated " + str(driver.phases)
		check(false, "%s: seated" % label)
		seat.stand()
		for i in 60: await physics_frame
		return
	# Settled in HOLD: the body faces the socket's way (and a seat faces the piece's own front).
	var contact := 0.0
	for i in 30:
		await physics_frame
		var point := IxSources.point_now(driver.entry)
		var measured: Vector3 = sample_hips - Vector3(0, IxRig.LIE_LIFT, 0) if hint == "lie" else sample_contact
		if i > 5: contact = maxf(contact, measured.distance_to(point))
	# The body's turn and the socket's turn against the piece's turn: they must stay the same at
	# every angle (the sockets turn with the piece). Compared with the same kind at 0° below.
	var body_rel := rad_to_deg(angle_difference(node.global_rotation.y, player.visual.global_rotation.y))
	var socket_rel := rad_to_deg(angle_difference(node.global_rotation.y, float(driver.socket.yaw)))
	seat.stand()
	var stood := false
	t = 0.0
	while t < 3.0:
		await physics_frame
		t += 1.0 / 60.0
		var moved := player.global_position.distance_to(last_pos)
		if moved > step: step_where = "%s %s dy=%.3f" % [driver.state_name(), str(driver.phase_t), player.global_position.y - last_pos.y]
		step = maxf(step, moved)
		turn = maxf(turn, absf(angle_difference(last_yaw, player.visual.rotation.y)))
		last_pos = player.global_position
		last_yaw = player.visual.rotation.y
		if not driver.busy():
			stood = true
			break
	var exit_err := rad_to_deg(absf(angle_difference(IxMath.yaw_of(player.facing), float(driver.socket.yaw))))
	var clear := capsule_clear(player.global_position)
	step = maxf(step, driver.max_step)
	var base := baseline(kind, body_rel, socket_rel, angle)
	var body_drift := rad_to_deg(absf(angle_difference(deg_to_rad(body_rel), deg_to_rad(base.body))))
	var socket_drift := rad_to_deg(absf(angle_difference(deg_to_rad(socket_rel), deg_to_rad(base.socket))))
	row.merge({"body_drift_deg": body_drift, "socket_drift_deg": socket_drift, "exit_face_deg": exit_err, "step_m": step, "turn_rad": turn,
		"joint_deg": joint_step, "contact_cm": contact * 100.0, "stood": stood, "exit_clear": clear, "step_where": step_where, "driver_step": driver.max_step, "driver_step_at": str(driver.max_step_at), "height": float(driver.socket.height), "phases": driver.phases})
	var ok := stood and clear and body_drift <= FACE_LIMIT and socket_drift <= FACE_LIMIT and exit_err <= FACE_LIMIT
	ok = ok and step <= STEP_LIMIT and turn <= TURN_LIMIT and joint_step < JOINT_LIMIT and contact <= 0.03
	row.ok = ok
	if not ok: print("  where: ", step_where, " driver ", driver.max_step, " at ", driver.max_step_at)
	check(ok, "%s: body drift %.1f°, socket drift %.1f°, exit %.1f°, step %.3f m, turn %.2f rad, joints %.1f°, contact %.1f cm, clear %s" % [label, body_drift, socket_drift, exit_err, step, turn, joint_step, contact * 100.0, str(clear)])
	for i in 10: await physics_frame

## The body's and the socket's turn relative to the piece, for this kind at 0° (the first case).
var baselines := {}
func baseline(kind: String, body: float, socket: float, angle: float) -> Dictionary:
	var key := kind.trim_prefix("stacked_")
	if not baselines.has(key) and is_zero_approx(angle): baselines[key] = {"body": body, "socket": socket}
	return baselines.get(key, {"body": body, "socket": socket})

func capsule_clear(point: Vector3) -> bool:
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.30
	capsule.height = 1.4
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.transform = Transform3D(Basis.IDENTITY, point + Vector3(0, 0.08 + 0.7, 0))
	query.collision_mask = 2 | 8 | 16
	query.exclude = [player.get_rid()]
	return player.get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty()

func _sampled() -> void:
	var skel: Skeleton3D = player.hand_skeleton
	if not is_instance_valid(skel): return
	sample_contact = IxRig.socket_global(skel, "seat_contact", player.visual).origin
	sample_hips = skel.global_transform * skel.get_bone_global_pose(IxRig.bone(skel, "Hips")).origin
	if not is_instance_valid(seat.driver) or not seat.driver.busy():
		last_rot.clear()
		return
	for i in skel.get_bone_count():
		var name := skel.get_bone_name(i)
		if name.begins_with("Face_"): continue
		var q := skel.get_bone_pose_rotation(i)
		if last_rot.has(i): joint_step = maxf(joint_step, rad_to_deg((last_rot[i] as Quaternion).angle_to(q)))
		last_rot[i] = q
