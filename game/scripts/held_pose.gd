extends SkeletonModifier3D
## Arms for a carried thing (held_items.gd): a two-bone reach per arm that puts the palm on the
## item's handle, the elbow toward a pole, the hand turned to (dir, palm). It runs right before
## locomotion_pose, so that layer's angular limiter (20 rad/s) smooths every change, and it fades
## in and out over `fade` seconds; at weight 0 it does nothing and the clip's arm swing is back.
##
## Targets come from the holder every tick in the walker's visual frame (metres, -Z forward), so the
## render-time offset of the visual (player.render_position) never shows between hand and item.
const IxRig = preload("res://scripts/ix/ix_rig.gd")
const NODE_NAME := "HeldPose"

## The holder (held_items.gd): arm_targets(pose) -> {"r": {...}, "l": {...}} in the visual frame,
## each {at, dir, palm, pole} (palm point, hand direction, palm normal, elbow direction).
var holder: Node
## player.visual (-Z forward).
var frame: Node3D
var actor: Node
var weight := 0.0
var target := 0.0
var fade := 0.2
## Measured once per skeleton (configure()): bones, rest frames, arm length in metres.
var cfg := {}

## The layer on a walker's skeleton (created once, before locomotion_pose; reused after).
static func attach(player: Node, owner_node: Node) -> SkeletonModifier3D:
	if not is_instance_valid(player) or not "hand_skeleton" in player or not is_instance_valid(player.hand_skeleton): return null
	var skel: Skeleton3D = player.hand_skeleton
	var pose := skel.get_node_or_null(NODE_NAME) as SkeletonModifier3D
	if pose == null:
		pose = load("res://scripts/held_pose.gd").new()
		pose.name = NODE_NAME
		skel.add_child(pose)
	pose.holder = owner_node
	pose.frame = player.visual
	pose.actor = player
	if "locomotion_pose" in player and is_instance_valid(player.locomotion_pose) and player.locomotion_pose.get_parent() == skel:
		var at: int = player.locomotion_pose.get_index()
		if pose.get_index() > at: skel.move_child(pose, at)
	return pose

## Skeleton space <- visual frame (the skeleton is a child of the visual, so this ignores where
## the visual is drawn this frame).
func to_skeleton(skel: Skeleton3D) -> Transform3D:
	return (frame.global_transform.affine_inverse() * skel.global_transform).affine_inverse()

func ready_for(skel: Skeleton3D) -> bool:
	if skel == null or not is_instance_valid(frame): return false
	if int(cfg.get("skel", 0)) != skel.get_instance_id(): cfg = configure(skel, frame)
	return bool(cfg.get("ok", false))

func _process_modification_with_delta(delta: float) -> void:
	weight = move_toward(weight, target, delta / maxf(0.01, fade))
	if weight <= 0.0 or not is_instance_valid(holder): return
	var skel := get_skeleton()
	if not ready_for(skel): return
	var w := smoothstep(0.0, 1.0, weight)
	# A gesture on top (gather, eat: action_pose) takes the arm for its short swing.
	if is_instance_valid(actor) and "action_pose" in actor and is_instance_valid(actor.action_pose):
		w *= 1.0 - clampf(float(actor.action_pose.applied_amount), 0.0, 1.0)
	if w <= 0.0: return
	var targets: Dictionary = holder.arm_targets(self)
	var to_skel := to_skeleton(skel)
	for side in ["r", "l"]:
		if targets.has(side) and cfg.has(side): solve(skel, cfg[side], targets[side], to_skel, w)

## Bones and rest frames of both arms. Frames are (direction along the bone, a reference normal):
## the upper arm's normal is the way the elbow folds (the body's forward in the bind pose), the
## forearm's and hand's the palm normal, read from the knuckle line.
static func configure(skel: Skeleton3D, frame_node: Node3D) -> Dictionary:
	var out := {"skel": skel.get_instance_id(), "ok": false}
	var to_visual := frame_node.global_transform.affine_inverse() * skel.global_transform
	var forward := (to_visual.basis.inverse() * Vector3.FORWARD).normalized()
	for side in ["r", "l"]:
		var p := "Right" if side == "r" else "Left"
		var up := IxRig.bone(skel, p + "UpperArm")
		var fo := IxRig.bone(skel, p + "LowerArm")
		var ha := IxRig.bone(skel, p + "Hand")
		if mini(up, mini(fo, ha)) < 0: continue
		var s0 := skel.get_bone_global_rest(up).origin
		var e0 := skel.get_bone_global_rest(fo).origin
		var w0 := skel.get_bone_global_rest(ha).origin
		var mid := IxRig.bone(skel, p + "MiddleProximal")
		var index := IxRig.bone(skel, p + "IndexProximal")
		var little := IxRig.bone(skel, p + "LittleProximal")
		var m0 := skel.get_bone_global_rest(mid).origin if mid >= 0 else w0 + (w0 - e0).normalized() * 0.08
		var hand_dir := (m0 - w0).normalized()
		var palm := Vector3.ZERO
		if index >= 0 and little >= 0:
			var k := (skel.get_bone_global_rest(little).origin - skel.get_bone_global_rest(index).origin).normalized()
			palm = hand_dir.cross(k) if side == "r" else k.cross(hand_dir)
		if palm.length_squared() < 0.01: palm = (to_visual.basis.inverse() * Vector3.DOWN).normalized()
		palm = (palm - hand_dir * hand_dir.dot(palm)).normalized()
		var rest_ha := skel.get_bone_global_rest(ha).basis
		# The handle sits in the closed fist: most of the way to the knuckles, a little palm-side.
		var reach := (m0 - w0).length()
		var grip_point := (m0 - w0) * 0.78 + palm * reach * 0.28
		# The right hand of the Explorer B rig grips where its tools sit (IxRig.GRIP_R, which the
		# equipment socket hand_r also uses), so a carried thing and a tool share one grip point.
		var grip_local: Vector3 = IxRig.GRIP_R.origin if side == "r" and IxRig.detect(skel) == "vrs" else rest_ha.inverse() * grip_point
		out[side] = {"up": up, "fo": fo, "ha": ha, "a": s0.distance_to(e0), "b": e0.distance_to(w0),
			"up_rest": skel.get_bone_global_rest(up).basis, "fo_rest": skel.get_bone_global_rest(fo).basis, "ha_rest": rest_ha,
			"up_f0": frame_of((e0 - s0).normalized(), forward), "fo_f0": frame_of((w0 - e0).normalized(), palm),
			"ha_f0": frame_of(hand_dir, palm), "grip": grip_local, "palm0": palm}
	if out.has("r"):
		var r: Dictionary = out.r
		var s0 := skel.get_bone_global_rest(r.up).origin
		var w0 := skel.get_bone_global_rest(r.ha).origin
		out["arm"] = (to_visual * s0).distance_to(to_visual * skel.get_bone_global_rest(r.fo).origin) + (to_visual * skel.get_bone_global_rest(r.fo).origin).distance_to(to_visual * w0)
		out["ok"] = true
	return out

## An orthonormal basis whose X is d and Y the part of n square to d.
static func frame_of(d: Vector3, n: Vector3) -> Basis:
	var y := n - d * d.dot(n)
	if y.length_squared() < 0.000001: y = d.cross(Vector3.RIGHT if absf(d.x) < 0.9 else Vector3.UP)
	y = y.normalized()
	return Basis(d, y, d.cross(y))

## The palm point of a side's hand at the current pose, in the visual frame.
func palm_point(skel: Skeleton3D, side: String) -> Vector3:
	if not ready_for(skel) or not cfg.has(side): return Vector3.INF
	var c: Dictionary = cfg[side]
	var hand := skel.get_bone_global_pose(c.ha)
	var to_visual := frame.global_transform.affine_inverse() * skel.global_transform
	return to_visual * (hand.origin + hand.basis * (c.grip as Vector3))

## Shoulder joint of a side at the current pose, in the visual frame.
func shoulder(skel: Skeleton3D, side: String) -> Vector3:
	if not ready_for(skel) or not cfg.has(side): return Vector3.INF
	var to_visual := frame.global_transform.affine_inverse() * skel.global_transform
	return to_visual * skel.get_bone_global_pose(int(cfg[side].up)).origin

func solve(skel: Skeleton3D, c: Dictionary, t: Dictionary, to_skel: Transform3D, w: float) -> void:
	var b3 := to_skel.basis
	var palm_at: Vector3 = to_skel * (t.at as Vector3)
	var dir := (b3 * (t.dir as Vector3)).normalized()
	var palm := (b3 * (t.palm as Vector3)).normalized()
	var pole := (b3 * (t.get("pole", Vector3(0, -1, 0.3)) as Vector3)).normalized()
	var hand_basis: Basis = frame_of(dir, palm) * (c.ha_f0 as Basis).transposed() * (c.ha_rest as Basis)
	var wrist: Vector3 = palm_at - hand_basis * (c.grip as Vector3)
	var s := skel.get_bone_global_pose(c.up).origin
	var a: float = c.a
	var b: float = c.b
	var to := wrist - s
	# Never folded flat: a hand right at the shoulder would push the elbow out along the reach.
	var dist := clampf(to.length(), maxf(absf(a - b) + 0.001, (a + b) * 0.3), a + b - 0.001)
	var dn := to.normalized()
	var bend := pole - dn * dn.dot(pole)
	if bend.length_squared() < 0.0001: bend = palm - dn * dn.dot(palm)
	bend = bend.normalized()
	var along := (a * a - b * b + dist * dist) / (2.0 * dist)
	var elbow := s + dn * along + bend * sqrt(maxf(0.0, a * a - along * along))
	var reached := s + dn * dist
	var du := (elbow - s).normalized()
	var fold := (reached - elbow) - du * du.dot(reached - elbow)
	if fold.length_squared() < 0.000001: fold = -bend
	var upper: Basis = frame_of(du, fold) * (c.up_f0 as Basis).transposed() * (c.up_rest as Basis)
	_turn(skel, c.up, upper, w)
	var fore: Basis = frame_of((reached - elbow).normalized(), palm) * (c.fo_f0 as Basis).transposed() * (c.fo_rest as Basis)
	_turn(skel, c.fo, fore, w)
	_turn(skel, c.ha, hand_basis, w)

## Turns a bone toward a skeleton-space orientation by w (its parent's current pose kept).
static func _turn(skel: Skeleton3D, index: int, target: Basis, w: float) -> void:
	var parent := skel.get_bone_parent(index)
	var parent_basis := skel.get_bone_global_pose(parent).basis.orthonormalized() if parent >= 0 else Basis.IDENTITY
	var local := (parent_basis.inverse() * target.orthonormalized()).orthonormalized().get_rotation_quaternion()
	skel.set_bone_pose_rotation(index, skel.get_bone_pose_rotation(index).slerp(local, w))
