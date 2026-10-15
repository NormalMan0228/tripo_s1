extends SceneTree
## ISS-1 interaction driver (S-WP4), offline on the shipped Player and rest_seat facade: box seats of
## 0.30 and 0.45 m, a bed, a rocking chair and a bench, each a real crafted assembly with collision.
## Phases run in order with no teleport (body <= 0.08 m and visual yaw <= 0.35 rad per tick, joints
## < 25 degrees per tick), the seat contact lands within 3 cm, a rocking seat carries the hips, the
## walker gets up onto a free spot facing out of the seat, movement cancels an approach at once, a
## foreign move aborts, a new look keeps sitting, and two walkers share a bench.
##   godot --headless --path game --script res://tests/ix_flow_check.gd
const Kit = preload("res://tests/ix_fixture_kit.gd")
const IxRig = preload("res://scripts/ix/ix_rig.gd")
const IxMath = preload("res://scripts/ix/ix_math.gd")
const IxSources = preload("res://scripts/ix/ix_sources.gd")
const Driver = preload("res://scripts/ix/ix_driver.gd")

var failures: Array[String] = []
var passes := 0
var report := {}
var stage: Node3D
var player: CharacterBody3D
var seat: Node
var joint_step := 0.0
var joint_bone := ""
var last_rot := {}
var sample_contact := Vector3.ZERO
var sample_hips := Vector3.ZERO

func check(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ") + label)
	if value: passes += 1
	else: failures.append(label)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	stage = Node3D.new()
	root.add_child(stage)
	Kit.floor_body(stage)
	player = load("res://scripts/player.gd").new()
	stage.add_child(player)
	seat = load("res://scripts/rest_seat.gd").new()
	stage.add_child(seat)
	seat.keep_height = true
	seat.hero = player
	for i in 4: await physics_frame
	hook_signal()
	var arch := Kit.archetypes()
	var chair45 := place(Kit.box_chair(0.45), Vector3(0, 0, 0), 20.0)
	var chair30 := place(Kit.box_chair(0.30), Vector3(4, 0, 0), -35.0)
	var bed := place(Kit.box_bed(), Vector3(-4, 0, 1), 90.0)
	var rocker := place(arch.rocking_chair, Vector3(0, 0, 5), 180.0)
	var bench := place(arch.bench, Vector3(4, 0, 5), 0.0)
	await physics_frame
	await cycle("chair_045", chair45, "sit", 0.45)
	await cycle("chair_030", chair30, "sit", 0.30)
	await cycle("bed", bed, "lie", 0.45)
	await cycle("rocker", rocker, "sit", 0.49, true)
	await cancel_on_move(chair45)
	await foreign_move(chair45)
	await new_look(chair45)
	await two_on_a_bench(bench)
	check(Driver.claims.is_empty(), "no seat stays claimed (%s)" % str(Driver.claims))
	print("IX_FLOW_CHECK ", JSON.stringify({"ok": failures.is_empty(), "passed": passes, "failures": failures, "report": report}))
	stage.queue_free()
	await process_frame
	quit(0 if failures.is_empty() else 1)

func place(arch: Dictionary, at: Vector3, yaw_deg: float) -> Node3D:
	var node := Kit.build(arch)
	stage.add_child(node)
	node.position = at
	node.rotation_degrees.y = yaw_deg
	return node

## Stand the walker a metre or so away, looking somewhere else.
func stand_near(node: Node3D, distance := 1.1, side := 0.4) -> void:
	var front := IxMath.dir_of(node.rotation.y)
	var at: Vector3 = node.global_position + front * distance + front.cross(Vector3.UP) * side
	player.global_position = Vector3(at.x, 0.02, at.z)
	player.facing = -front.rotated(Vector3.UP, 0.7)
	player.velocity = Vector3.ZERO
	for i in 8: await physics_frame

func cycle(label: String, node: Node3D, hint: String, top: float, rock := false) -> void:
	await stand_near(node)
	var trace := {"step": 0.0, "yaw": 0.0, "contact": 0.0, "rock": 0.0}
	joint_step = 0.0
	last_rot.clear()
	var started := Time.get_ticks_msec()
	seat.crafted(node, hint)
	var driver: Node = seat.driver
	check(seat.resting() and is_instance_valid(driver) and driver.busy(), "%s: E starts the interaction (%s)" % [label, driver.why if is_instance_valid(driver) else "no driver"])
	if not is_instance_valid(driver) or not driver.busy(): return
	var seated_after := -1.0
	var last_pos: Vector3 = player.global_position
	var last_yaw: float = player.visual.rotation.y
	var t := 0.0
	while t < 4.0:
		await physics_frame
		t += 1.0 / 60.0
		trace.step = maxf(trace.step, player.global_position.distance_to(last_pos))
		trace.yaw = maxf(trace.yaw, absf(angle_difference(last_yaw, player.visual.rotation.y)))
		last_pos = player.global_position
		last_yaw = player.visual.rotation.y
		if driver.state == Driver.HOLD:
			seated_after = (Time.get_ticks_msec() - started) / 1000.0
			break
	check(seated_after > 0.0, "%s: seated (%s)" % [label, str(driver.phases)])
	if seated_after < 0.0:
		seat.stand()
		return
	check(seated_after <= (3.0 if hint == "lie" else 2.0), "%s: E to %s in %.2f s" % [label, "lying" if hint == "lie" else "sitting", seated_after])
	var order: Array = driver.phases.filter(func(p): return p in ["approach", "align", "enter", "hold"])
	check(order == ["approach", "align", "enter", "hold"] or order == ["align", "enter", "hold"], "%s: phases in order %s" % [label, str(driver.phases)])
	# Hold: contact on the socket (and on a rocking seat, riding it).
	var socket_entry: Dictionary = driver.entry
	for i in 40:
		if rock: node.whole_root.rotation.x = 0.12 * sin(i * 0.12)
		await physics_frame
		trace.step = maxf(trace.step, player.global_position.distance_to(last_pos))
		last_pos = player.global_position
		var point := IxSources.point_now(socket_entry)
		var measured: Vector3 = sample_hips - Vector3(0, IxRig.LIE_LIFT, 0) if hint == "lie" else sample_contact
		if i > 3: trace.contact = maxf(trace.contact, measured.distance_to(point))
	check(trace.contact <= (0.02 if rock else 0.03), "%s: contact on the socket in HOLD (%.1f cm)" % [label, trace.contact * 100.0])
	var height: float = driver.socket.height
	check(absf(height - top) < 0.03, "%s: socket on the real top (%.3f vs %.3f m)" % [label, height, top])
	if hint == "lie": check(player.global_basis.is_equal_approx(Basis.IDENTITY) and seat.mode == "lie", "%s: lying keeps the body upright" % label)
	else: check(seat.mode == "sit" and seat.pose.mode == "sit", "%s: rest_seat reports sitting" % label)
	if rock: node.whole_root.rotation.x = 0.0
	seat.stand()
	var stood := false
	t = 0.0
	while t < 3.0:
		await physics_frame
		t += 1.0 / 60.0
		trace.step = maxf(trace.step, player.global_position.distance_to(last_pos))
		trace.yaw = maxf(trace.yaw, absf(angle_difference(last_yaw, player.visual.rotation.y)))
		if player.global_position.distance_to(last_pos) > 0.08 or absf(angle_difference(last_yaw, player.visual.rotation.y)) > 0.35:
			print("JUMP %s %.3f m %.2f rad state %s/%d %.2f pos %s" % [label, player.global_position.distance_to(last_pos), angle_difference(last_yaw, player.visual.rotation.y), driver.state_name(), driver.lie_phase, driver.phase_t, str(player.global_position)])
		last_pos = player.global_position
		last_yaw = player.visual.rotation.y
		if not driver.busy():
			stood = true
			break
	check(stood and not seat.resting() and not player.visual_only, "%s: E gets it up and walking again" % label)
	var off: float = Vector2(player.global_position.x - driver.exit_point.x, player.global_position.z - driver.exit_point.z).length()
	var facing_error := absf(angle_difference(IxMath.yaw_of(player.facing), float(driver.socket.yaw)))
	check(off <= 0.05, "%s: stands at the exit point (%.3f m)" % [label, off])
	check(facing_error <= deg_to_rad(5.0), "%s: faces out of the seat (%.1f deg)" % [label, rad_to_deg(facing_error)])
	check(driver.spot_free(player.global_position), "%s: the exit spot is free" % label)
	check(trace.step <= 0.08 and driver.max_step <= 0.08, "%s: no body jump (max %.3f m per tick)" % [label, maxf(trace.step, driver.max_step)])
	check(trace.yaw <= 0.35, "%s: no visual turn jump (max %.2f rad per tick)" % [label, trace.yaw])
	check(joint_step < 25.0, "%s: joints < 25 deg per tick (%.1f, %s)" % [label, joint_step, joint_bone])
	report[label] = {"seconds": seated_after, "max_step_m": maxf(trace.step, driver.max_step), "max_yaw_rad": trace.yaw, "contact_cm": trace.contact * 100.0,
		"joint_deg": joint_step, "joint_bone": joint_bone, "exit_off_m": off, "height": height, "variant": driver.variant, "phases": driver.phases, "step_at": driver.max_step_at, "yaw_at": driver.max_yaw_at, "driver_yaw": driver.max_yaw_step}
	for i in 10: await physics_frame

func cancel_on_move(node: Node3D) -> void:
	await stand_near(node, 1.6, 0.0)
	seat.crafted(node, "sit")
	var driver: Node = seat.driver
	for i in 3: await physics_frame
	check(driver.state == Driver.APPROACH, "walking up to the chair (%s)" % driver.state_name())
	Input.action_press("move_left")
	await physics_frame
	var cancelled: bool = not driver.busy() and not seat.resting() and not player.visual_only
	await physics_frame
	Input.action_release("move_left")
	check(cancelled, "a movement key cancels the approach within one tick (%s, %s)" % [driver.state_name(), driver.why])
	for i in 20: await physics_frame

func foreign_move(node: Node3D) -> void:
	await sit_down(node)
	var driver: Node = seat.driver
	await process_frame
	player.global_position += Vector3(3, 0, 0)
	var t := 0.0
	while t < 0.25 and (driver.busy() or (is_instance_valid(driver.pose) and driver.pose.weight > 0.0)):
		await physics_frame
		t += 1.0 / 60.0
	check(not driver.busy() and driver.pose.weight == 0.0 and not seat.resting(), "a foreign move aborts and the pose is gone in %.2f s (%s)" % [t, driver.why])
	check(not player.visual_only, "and the walker has its physics back")
	player.global_position = Vector3(8, 0.02, 8)
	for i in 10: await physics_frame

func new_look(node: Node3D) -> void:
	await sit_down(node)
	var driver: Node = seat.driver
	var old_skeleton: Skeleton3D = player.hand_skeleton
	player.apply_avatar({"character": "explorer_b", "coat": "#3a6ea5", "pants": "#4a4a4a"})
	for i in 12: await physics_frame
	hook_signal()
	check(driver.state == Driver.HOLD and player.hand_skeleton != old_skeleton and is_instance_valid(driver.pose) and driver.pose.get_parent() == player.hand_skeleton,
		"a new look while seated stays seated on the new skeleton")
	seat.stand()
	for i in 60: await physics_frame
	check(not driver.busy(), "and gets up afterwards")

func two_on_a_bench(bench: Node3D) -> void:
	await sit_down(bench)
	var first: String = seat.driver.socket.id
	var other: CharacterBody3D = load("res://scripts/player.gd").new()
	stage.add_child(other)
	var other_seat: Node = load("res://scripts/rest_seat.gd").new()
	stage.add_child(other_seat)
	other_seat.keep_height = true
	other_seat.hero = other
	var front := IxMath.dir_of(bench.rotation.y)
	other.global_position = bench.global_position + front * 1.0 - front.cross(Vector3.UP) * 0.5
	for i in 6: await physics_frame
	other_seat.crafted(bench, "sit")
	var second: String = other_seat.driver.socket.id if other_seat.resting() else ""
	check(not second.is_empty() and second != first, "two walkers on a bench take different seats (%s, %s)" % [first, second])
	for i in 150:
		await physics_frame
		if other_seat.driver.state == Driver.HOLD: break
	check(other_seat.driver.state == Driver.HOLD, "the second walker sits too")
	seat.stand()
	other_seat.stand()
	for i in 90: await physics_frame
	check(not seat.driver.busy() and not other_seat.driver.busy(), "both get up")

func sit_down(node: Node3D) -> void:
	await stand_near(node)
	seat.crafted(node, "sit")
	for i in 180:
		await physics_frame
		if seat.driver.state == Driver.HOLD: return

func hook_signal() -> void:
	if is_instance_valid(player.locomotion_pose) and not player.locomotion_pose.modification_processed.is_connected(_sampled):
		player.locomotion_pose.modification_processed.connect(_sampled)
	last_rot.clear()

## The final pose, read in the last modifier's signal.
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
		if last_rot.has(i):
			var step := rad_to_deg((last_rot[i] as Quaternion).angle_to(q))
			if step > joint_step:
				joint_step = step
				joint_bone = name + " in " + seat.driver.state_name() + " " + str(snappedf(seat.driver.phase_t, 0.01))
		last_rot[i] = q
