extends SkeletonModifier3D
## ISS-1 pose layer: the one sitting / lying pose for every walker (it replaces Interiors.RestPose,
## field_objects.SeatPose and shadow_figure.bend). It runs before locomotion_pose, so the existing
## angular limiter (20 rad/s body, 24 rad/s legs) smooths whatever it does.
##
## What it does, all about the character's sideways axis (+ swings a bone's far end forward):
##   - legs: override toward the rest leg bent by thigh / calf (planted or dangling), feet kept level;
##   - hips: back to their rest height and turn, so the seat contact is where the math says;
##   - spine and arms: a small extra bend on top of the playing clip, so the idle keeps breathing;
##   - tilt: the whole skeleton turns about the hips (lying back on a bed or a lounger), and `carrier`
##     adds a moving seat's rock. The walker's body (CharacterBody3D) itself always stays upright.
## Weight: `weight` 0..1 (the driver sets it every tick, `driven`); without a driver the layer eases
## toward `mode` by itself (the fallback used by rest_seat.gd alone). At weight 0 it does nothing.
const IxRig = preload("res://scripts/ix/ix_rig.gd")
const IxMath = preload("res://scripts/ix/ix_math.gd")
const NODE_NAME := "IxPose"

## [thigh, calf, spine, arm, forearm, tilt, foot_follow] per mode (radians).
const PRESETS := {
	"": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
	"sit": [1.50, -1.55, -0.10, 0.35, 0.70, 0.0, 0.0],
	"sit_low": [1.85, -2.05, -0.16, 0.30, 0.65, 0.0, 0.0],
	"perch": [1.30, -1.05, -0.08, 0.30, 0.60, 0.0, 0.3],
	"sit_ground": [1.50, -0.15, -0.22, 0.12, 0.30, 0.0, 0.8],
	"lie": [0.10, -0.18, 0.0, 0.05, 0.20, PI * 0.5, 1.0],
	# field_objects swings/rockers and the hammock keep their old look (the SeatPose values; the
	# spine bend is spread over three bones at 0.6, so -0.10 is the old -0.06 on Spine02).
	"seat_field": [1.45, -1.45, -0.10, 0.0, 0.0, 0.0, 0.0],
	"hammock": [1.20, -1.00, -0.42, 0.0, 0.0, 0.0, 0.0],
	# shadow_figure.set_pose (the old bend() values).
	"figure_sit": [1.45, -1.45, -0.08, 0.0, 0.0, 0.0, 0.0],
	"figure_sit_ground": [1.50, -0.12, -0.08, 0.0, 0.0, 0.0, 0.8],
}

## Compatibility with rest_seat/village_rest_check: the pose being shown ("", "sit", "lie", ...).
var mode := "":
	set(value):
		mode = value
		if not driven and PRESETS.has(value) and not value.is_empty(): set_preset(value)
var driven := false
var weight := 0.0
var thigh := 0.0
var calf := 0.0
var spine := 0.0
var arm := 0.0
var forearm := 0.0
var tilt := 0.0
var foot_follow := 0.0
## A moving seat's rock (world space, about the hips), e.g. a rocking chair's pitch.
var carrier := Basis.IDENTITY
## The node whose -Z is forward (player.visual); forward_sign +1 for a +Z-facing figure.
var frame: Node3D
var forward_sign := -1.0
## Seconds for the fallback fade (no driver).
var fade_time := 0.25
var _cfg := {}
## Shadow figures pose without a modifier (pose_now): their configurations by skeleton.
static var _figures := {}

## The pose layer on a walker's skeleton (created once, before locomotion_pose; reused after).
static func attach(actor: Node) -> SkeletonModifier3D:
	if not is_instance_valid(actor) or not "hand_skeleton" in actor or not is_instance_valid(actor.hand_skeleton): return null
	var skel: Skeleton3D = actor.hand_skeleton
	var pose := skel.get_node_or_null(NODE_NAME) as SkeletonModifier3D
	if pose == null:
		pose = load("res://scripts/ix/ix_pose.gd").new()
		pose.name = NODE_NAME
		skel.add_child(pose)
	pose.frame = actor.visual if "visual" in actor else actor
	pose.forward_sign = -1.0
	# Processing order is child order: before locomotion_pose's limiter, after action/finger poses.
	if "locomotion_pose" in actor and is_instance_valid(actor.locomotion_pose) and actor.locomotion_pose.get_parent() == skel:
		var at: int = actor.locomotion_pose.get_index()
		if pose.get_index() > at: skel.move_child(pose, at)
	return pose

func set_preset(name: String) -> void:
	var p: Array = PRESETS.get(name, PRESETS[""])
	thigh = p[0]; calf = p[1]; spine = p[2]; arm = p[3]; forearm = p[4]; tilt = p[5]; foot_follow = p[6]

## Writes a blend of two presets (no allocation; t 0..1).
func blend_presets(a: String, b: String, t: float) -> void:
	var p: Array = PRESETS.get(a, PRESETS[""])
	var q: Array = PRESETS.get(b, PRESETS[""])
	thigh = lerpf(p[0], q[0], t); calf = lerpf(p[1], q[1], t); spine = lerpf(p[2], q[2], t)
	arm = lerpf(p[3], q[3], t); forearm = lerpf(p[4], q[4], t); tilt = lerpf(p[5], q[5], t); foot_follow = lerpf(p[6], q[6], t)

## Legs bent so the feet rest on the floor `drop` below the hip joints (planar two-bone, knee in front).
func plant_legs(m: Dictionary, drop: float, reach := -1.0) -> void:
	var forward: float = reach if reach >= 0.0 else float(m.thigh) * 0.95
	# The rest leg is not quite straight: the ankle lands ~2.5 cm lower than the planar solve says.
	var angles := IxMath.leg_angles(float(m.thigh), float(m.shin), forward, maxf(0.05, drop - 0.025))
	thigh = angles.x
	calf = angles.y

func _process_modification_with_delta(delta: float) -> void:
	if not driven:
		weight = move_toward(weight, 0.0 if mode.is_empty() else 1.0, delta / maxf(0.01, fade_time))
	# The carrier's rock is weighted too, so weight 0 is always the idle layer that does nothing.
	if weight <= 0.0: return
	var skel := get_skeleton()
	if skel == null: return
	if int(_cfg.get("skel", 0)) != skel.get_instance_id(): _cfg = configure(skel, frame, forward_sign)
	if not _cfg.ok: return
	pose_skeleton(skel, _cfg, thigh, calf, spine, arm, forearm, tilt, foot_follow, carrier, weight)

## The bones and rest orientations the pose needs, once per skeleton.
static func configure(skel: Skeleton3D, frame_node: Node3D, sign := -1.0) -> Dictionary:
	var cfg := {"skel": skel.get_instance_id(), "ok": false}
	var m := IxRig.measure(skel, frame_node if is_instance_valid(frame_node) else skel, sign)
	cfg.lateral = m.lateral
	cfg.root = IxRig.bone(skel, "Root")
	cfg.hip = IxRig.bone(skel, "Hips")
	var legs := PackedInt32Array()
	for side in ["Left", "Right"]:
		for part in ["UpperLeg", "LowerLeg", "Foot"]: legs.append(IxRig.bone(skel, side + part))
	cfg.legs = legs
	cfg.spine = PackedInt32Array([IxRig.bone(skel, "Spine"), IxRig.bone(skel, "Chest"), IxRig.bone(skel, "UpperChest")])
	cfg.arms = PackedInt32Array([IxRig.bone(skel, "LeftUpperArm"), IxRig.bone(skel, "RightUpperArm")])
	cfg.forearms = PackedInt32Array([IxRig.bone(skel, "LeftLowerArm"), IxRig.bone(skel, "RightLowerArm")])
	var rest := {}
	for i in legs:
		if i < 0: return cfg
		rest[i] = skel.get_bone_global_rest(i).basis.orthonormalized()
	cfg.rest = rest
	cfg.hip_rest = skel.get_bone_rest(cfg.hip) if cfg.hip >= 0 else Transform3D.IDENTITY
	cfg.ok = true
	return cfg

static func pose_skeleton(skel: Skeleton3D, cfg: Dictionary, p_thigh: float, p_calf: float, p_spine: float, p_arm: float,
		p_forearm: float, p_tilt: float, p_foot: float, p_carrier: Basis, w: float) -> void:
	w = clampf(w, 0.0, 1.0)
	var side_axis: Vector3 = cfg.lateral
	# The tilt about the sideways axis (lying back), then a moving seat's rock, in skeleton space.
	var tb := Basis(side_axis, p_tilt * w)
	if p_carrier != Basis.IDENTITY and w > 0.0:
		var s := skel.global_basis.orthonormalized()
		var rock := Basis(Quaternion.IDENTITY.slerp(p_carrier.orthonormalized().get_rotation_quaternion(), w))
		tb = (s.inverse() * rock * s) * tb
	var hip: int = cfg.hip
	var root: int = cfg.root
	# Hips back to their rest height and (mostly) their rest turn: the idle bobs them a few cm.
	if hip >= 0:
		var hip_rest: Transform3D = cfg.hip_rest
		skel.set_bone_pose_position(hip, skel.get_bone_pose_position(hip).lerp(hip_rest.origin, w))
		skel.set_bone_pose_rotation(hip, skel.get_bone_pose_rotation(hip).slerp(hip_rest.basis.get_rotation_quaternion(), w * 0.6))
	if root >= 0 and hip >= 0 and not tb.is_equal_approx(Basis.IDENTITY):
		var pivot := skel.get_bone_global_pose(hip).origin
		var turned := Transform3D(tb, pivot - tb * pivot) * skel.get_bone_pose(root)
		skel.set_bone_pose_rotation(root, turned.basis.get_rotation_quaternion())
		skel.set_bone_pose_position(root, turned.origin)
	var bent := (tb * side_axis).normalized()
	var legs: PackedInt32Array = cfg.legs
	var rest: Dictionary = cfg.rest
	for side in 2:
		var i_thigh := legs[side * 3]
		var i_calf := legs[side * 3 + 1]
		var i_foot := legs[side * 3 + 2]
		_override(skel, i_thigh, tb * Basis(side_axis, p_thigh) * Basis(rest[i_thigh]), w)
		_override(skel, i_calf, tb * Basis(side_axis, p_thigh + p_calf) * Basis(rest[i_calf]), w)
		_override(skel, i_foot, tb * Basis(side_axis, (p_thigh + p_calf) * p_foot) * Basis(rest[i_foot]), w)
	if absf(p_spine) > 0.0001:
		for i in cfg.spine:
			if i >= 0: _bend(skel, i, bent, p_spine * w * 0.6 / 3.0)
	if absf(p_arm) > 0.0001:
		for i in cfg.arms:
			if i >= 0: _bend(skel, i, bent, p_arm * w)
	if absf(p_forearm) > 0.0001:
		for i in cfg.forearms:
			if i >= 0: _bend(skel, i, bent, p_forearm * w)

## Turns a bone toward a skeleton-space orientation by w (its parent's current pose kept).
static func _override(skel: Skeleton3D, index: int, target: Basis, w: float) -> void:
	var parent := skel.get_bone_parent(index)
	var parent_basis := skel.get_bone_global_pose(parent).basis.orthonormalized() if parent >= 0 else Basis.IDENTITY
	var local := (parent_basis.inverse() * target).orthonormalized().get_rotation_quaternion()
	skel.set_bone_pose_rotation(index, skel.get_bone_pose_rotation(index).slerp(local, w))

## Adds a turn about a skeleton-space axis on top of the bone's current pose.
static func _bend(skel: Skeleton3D, index: int, axis: Vector3, angle: float) -> void:
	var local_axis := (skel.get_bone_global_pose(index).basis.orthonormalized().inverse() * axis).normalized()
	skel.set_bone_pose_rotation(index, skel.get_bone_pose_rotation(index) * Quaternion(local_axis, angle))

## For walkers without a modifier stack (shadow figures pose after each animation step): the same
## math on a skeleton right now. frame_node faces +Z (forward +1) for shadow figures.
static func pose_now(skel: Skeleton3D, frame_node: Node3D, preset: String, w := 1.0, forward := 1.0) -> void:
	if not is_instance_valid(skel) or not PRESETS.has(preset) or w <= 0.0: return
	var id := skel.get_instance_id()
	var cfg: Dictionary = _figures.get(id, {})
	if cfg.is_empty():
		if _figures.size() > 64: _figures.clear()
		cfg = configure(skel, frame_node, forward)
		_figures[id] = cfg
	if not cfg.ok: return
	var p: Array = PRESETS[preset]
	pose_skeleton(skel, cfg, p[0], p[1], p[2], p[3], p[4], p[5], p[6], Basis.IDENTITY, w)
