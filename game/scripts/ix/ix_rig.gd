extends RefCounted
## ISS-1 character rigs: which rig a skeleton is, the humanoid bone map, the body measurements the
## interaction math needs (hip height, leg lengths, where seat_contact and pelvis_lie are) and the
## character socket table. Measurements come from the skeleton's rest pose and are cached per
## skeleton, so they cost nothing after the first use.
##
## Body frame: origin on the floor under the body root, +Y up, +Z forward (player.facing), +X the
## character's left. The visual node of player.gd faces -Z, so body = visual turned 180 degrees.

## Every character in Villagen shares the Explorer B skeleton ("vrs": the wardrobe/reference/motion
## GLBs; shadow folk and day villagers use the same model). The legacy explorer/ranger/tinker GLBs and
## haeru are an A-pose Tripo rig with the same names; the NPC cast rig is Blender-style (.L/.R).
const PROFILES := {
	"vrs": {"clips": true, "pose": true, "note": "Explorer B (explorer_b_wardrobe/reference/motion.glb)"},
	"tripo41_apose": {"clips": false, "pose": true, "note": "legacy explorer/ranger/tinker, haeru_v1"},
	"npc_cast": {"clips": false, "pose": false, "note": "Blender .L/.R cast rig (map declared, deferred)"},
}

## SkeletonProfileHumanoid name -> bone, for vrs and tripo41_apose. Unmapped: Pelvis, NeckTwist02, twists.
const HUMANOID := {
	"Root": "Root", "Hips": "Hip", "Spine": "Waist", "Chest": "Spine01", "UpperChest": "Spine02", "Neck": "NeckTwist01", "Head": "Head",
	"LeftShoulder": "L_Clavicle", "LeftUpperArm": "L_Upperarm", "LeftLowerArm": "L_Forearm", "LeftHand": "L_Hand",
	"RightShoulder": "R_Clavicle", "RightUpperArm": "R_Upperarm", "RightLowerArm": "R_Forearm", "RightHand": "R_Hand",
	"LeftUpperLeg": "L_Thigh", "LeftLowerLeg": "L_Calf", "LeftFoot": "L_Foot", "LeftToes": "L_ToeBase",
	"RightUpperLeg": "R_Thigh", "RightLowerLeg": "R_Calf", "RightFoot": "R_Foot", "RightToes": "R_ToeBase",
	"LeftThumbMetacarpal": "L_Thumb_01", "LeftThumbProximal": "L_Thumb_02", "LeftThumbDistal": "L_Thumb_03",
	"LeftIndexProximal": "L_Index_01", "LeftIndexIntermediate": "L_Index_02", "LeftIndexDistal": "L_Index_03",
	"LeftMiddleProximal": "L_Middle_01", "LeftMiddleIntermediate": "L_Middle_02", "LeftMiddleDistal": "L_Middle_03",
	"LeftRingProximal": "L_Ring_01", "LeftRingIntermediate": "L_Ring_02", "LeftRingDistal": "L_Ring_03",
	"LeftLittleProximal": "L_Little_01", "LeftLittleIntermediate": "L_Little_02", "LeftLittleDistal": "L_Little_03",
	"RightThumbMetacarpal": "R_Thumb_01", "RightThumbProximal": "R_Thumb_02", "RightThumbDistal": "R_Thumb_03",
	"RightIndexProximal": "R_Index_01", "RightIndexIntermediate": "R_Index_02", "RightIndexDistal": "R_Index_03",
	"RightMiddleProximal": "R_Middle_01", "RightMiddleIntermediate": "R_Middle_02", "RightMiddleDistal": "R_Middle_03",
	"RightRingProximal": "R_Ring_01", "RightRingIntermediate": "R_Ring_02", "RightRingDistal": "R_Ring_03",
	"RightLittleProximal": "R_Little_01", "RightLittleIntermediate": "R_Little_02", "RightLittleDistal": "R_Little_03",
}
## The cast rig's names (declared for WP15; not verified in engine yet).
const NPC_CAST := {"Hips": "Hips", "Spine": "Spine", "Chest": "Chest", "Neck": "Neck", "Head": "Head",
	"LeftUpperArm": "UpperArm.L", "LeftLowerArm": "ForeArm.L", "LeftHand": "Hand.L", "RightUpperArm": "UpperArm.R",
	"RightLowerArm": "ForeArm.R", "RightHand": "Hand.R", "LeftUpperLeg": "Thigh.L", "LeftLowerLeg": "Shin.L",
	"LeftFoot": "Foot.L", "RightUpperLeg": "Thigh.R", "RightLowerLeg": "Shin.R", "RightFoot": "Foot.R"}

## Character sockets: id -> [humanoid bone, what it is]. Positions are measured from the rest pose
## (measure()); grip_r is exactly the hand-local literal player.gd equips tools with.
const SOCKETS := {
	"root": ["Root", "floor under the feet, +Z forward"],
	"seat_contact": ["Hips", "thigh-joint height minus seat_drop; meets sit sockets"],
	"pelvis_lie": ["Hips", "hips centre; meets lie sockets"],
	"sole_l": ["LeftFoot", "foot dropped to the floor plane at rest"],
	"sole_r": ["RightFoot", "foot dropped to the floor plane at rest"],
	"grip_r": ["RightHand", "Transform3D(Basis(LEFT,FORWARD,DOWN), (-.015,.095,0)) hand-local (player.gd equip)"],
	"grip_l": ["LeftHand", "grip_r mirrored"],
	"pinch_r": ["RightIndexDistal", "small items"],
	"pinch_l": ["LeftIndexDistal", "small items"],
	"hold_front": ["UpperChest", "0.25 m in front: two-hand carry, gifts"],
	"back": ["UpperChest", "backpack"],
	"hip_r": ["Hips", "holstered tool, right"],
	"hip_l": ["Hips", "holstered tool, left"],
	"eyes": ["Head", "look-at origin; what others look at"],
	"mouth": ["Head", "eat/drink target"],
	"head_top": ["Head", "hats"],
	"overhead": ["Head", "nameplate and bubbles (2.05 m standing)"],
}
const GRIP_R := Transform3D(Basis(Vector3.LEFT, Vector3.FORWARD, Vector3.DOWN), Vector3(-0.015, 0.095, 0.0))
## The "+0.1" of the old seat formula: the thigh joint sits this far above the seat surface.
const SEAT_DROP := 0.10
## The hips centre rides this far above a mattress top when lying.
const LIE_LIFT := 0.12

static var _cache := {}

## "vrs", "tripo41_apose", "npc_cast" or "" (unknown rig).
static func detect(skel: Skeleton3D) -> String:
	if not is_instance_valid(skel): return ""
	if skel.find_bone("Hip") >= 0 and skel.find_bone("R_Hand") >= 0:
		# Explorer B binds in a T-pose (arms level); the legacy Tripo rigs bind in an A-pose.
		var arm := skel.find_bone("R_Upperarm")
		var hand := skel.find_bone("R_Hand")
		if arm >= 0 and hand >= 0:
			var a := skel.get_bone_global_rest(arm).origin
			var b := skel.get_bone_global_rest(hand).origin
			var along := (b - a)
			var up := skel.get_bone_global_rest(skel.find_bone("Head")).origin - skel.get_bone_global_rest(skel.find_bone("Hip")).origin if skel.find_bone("Head") >= 0 else Vector3.UP
			var drop := along.normalized().dot(up.normalized())
			return "vrs" if absf(drop) < 0.35 else "tripo41_apose"
		return "vrs"
	if skel.find_bone("Hips") >= 0 and skel.find_bone("Hand.R") >= 0: return "npc_cast"
	return ""

## The rig bone for a humanoid name (-1 when the rig has none).
static func bone(skel: Skeleton3D, humanoid: String) -> int:
	if not is_instance_valid(skel): return -1
	var map: Dictionary = NPC_CAST if detect(skel) == "npc_cast" else HUMANOID
	return skel.find_bone(str(map.get(humanoid, humanoid)))

## Body measurements from the rest pose. frame: the node whose -Z is the character's forward and whose
## origin is on the floor (player.visual); forward_sign +1 for a +Z-facing frame (shadow figures).
## {profile, hip_height, seat_contact (body frame), pelvis (body frame), thigh, shin, ankle, arm,
##  eye_height, lateral (skeleton-space sideways axis, the character's right), seat_drop, lie_lift, ok}
static func measure(skel: Skeleton3D, frame: Node3D, forward_sign := -1.0) -> Dictionary:
	if not is_instance_valid(skel) or not is_instance_valid(frame): return fallback()
	var key := skel.get_instance_id()
	if _cache.has(key):
		var cached: Dictionary = _cache[key]
		if float(cached.get("sign", -1.0)) == forward_sign: return cached
	if _cache.size() > 48: _cache.clear()
	var out := fallback()
	out["profile"] = detect(skel)
	out["sign"] = forward_sign
	# Skeleton space -> frame space -> body frame (+Z forward, +X left).
	var to_frame := frame.global_transform.affine_inverse() * skel.global_transform
	var turn := Basis(Vector3.UP, PI) if forward_sign < 0.0 else Basis.IDENTITY
	var to_body := Transform3D(turn, Vector3.ZERO) * to_frame
	out["to_body"] = to_body
	var right_frame := Vector3.RIGHT if forward_sign < 0.0 else Vector3.LEFT
	out["lateral"] = (to_frame.basis.inverse() * right_frame).normalized()
	var at := func(name: String) -> Vector3:
		var i := bone(skel, name)
		return to_body * skel.get_bone_global_rest(i).origin if i >= 0 else Vector3.INF
	var lt: Vector3 = at.call("LeftUpperLeg")
	var rt: Vector3 = at.call("RightUpperLeg")
	var lc: Vector3 = at.call("LeftLowerLeg")
	var lf: Vector3 = at.call("LeftFoot")
	var rc: Vector3 = at.call("RightLowerLeg")
	var rf: Vector3 = at.call("RightFoot")
	var hips: Vector3 = at.call("Hips")
	var head: Vector3 = at.call("Head")
	if lt.is_finite() and rt.is_finite() and lc.is_finite() and lf.is_finite():
		out.hip_height = clampf(lt.y, 0.5, 1.1)
		var mid := (lt + rt) * 0.5
		out.seat_contact = Vector3(mid.x, out.hip_height - SEAT_DROP, mid.z)
		out.thigh = (lt.distance_to(lc) + (rt.distance_to(rc) if rc.is_finite() else lt.distance_to(lc))) * 0.5
		out.shin = (lc.distance_to(lf) + (rc.distance_to(rf) if rc.is_finite() and rf.is_finite() else lc.distance_to(lf))) * 0.5
		out.ankle = maxf(0.02, (lf.y + (rf.y if rf.is_finite() else lf.y)) * 0.5)
		out.ok = true
	if hips.is_finite(): out.pelvis = hips
	if head.is_finite(): out.eye_height = head.y + 0.08
	var ua: Vector3 = at.call("RightUpperArm")
	var fa: Vector3 = at.call("RightLowerArm")
	var hd: Vector3 = at.call("RightHand")
	if ua.is_finite() and fa.is_finite() and hd.is_finite(): out.arm = ua.distance_to(fa) + fa.distance_to(hd)
	_cache[key] = out
	return out

## Measurements for a rig nobody can read (the old 0.85 m hip height).
static func fallback() -> Dictionary:
	return {"profile": "", "hip_height": 0.85, "seat_contact": Vector3(0, 0.75, 0), "pelvis": Vector3(0, 0.85, 0), "thigh": 0.38,
		"shin": 0.43, "ankle": 0.06, "arm": 0.55, "eye_height": 1.38, "lateral": Vector3.RIGHT, "seat_drop": SEAT_DROP,
		"lie_lift": LIE_LIFT, "ok": false, "to_body": Transform3D.IDENTITY}

## A character socket's global transform at the current pose (math only, no node).
static func socket_global(skel: Skeleton3D, id: String, frame: Node3D) -> Transform3D:
	if not is_instance_valid(skel) or not SOCKETS.has(id): return Transform3D.IDENTITY
	var i := bone(skel, str(SOCKETS[id][0]))
	if i < 0: return skel.global_transform
	var pose := skel.global_transform * skel.get_bone_global_pose(i)
	match id:
		"root":
			var floor_point := pose.origin
			if is_instance_valid(frame): floor_point.y = frame.global_position.y
			var f := frame.global_basis.z if is_instance_valid(frame) else Vector3.BACK
			return Transform3D(Basis.looking_at(Vector3(-f.x, 0, -f.z).normalized() if Vector2(f.x, f.z).length() > 0.01 else Vector3.BACK, Vector3.UP, true), floor_point)
		"seat_contact":
			var m := measure(skel, frame)
			var l := bone(skel, "LeftUpperLeg")
			var r := bone(skel, "RightUpperLeg")
			if l >= 0 and r >= 0:
				var mid := (skel.global_transform * skel.get_bone_global_pose(l).origin + skel.global_transform * skel.get_bone_global_pose(r).origin) * 0.5
				return Transform3D(Basis.IDENTITY, mid - Vector3(0, float(m.seat_drop), 0))
		"grip_r":
			return pose * Transform3D(GRIP_R.basis.scaled(Vector3.ONE / maxf(0.0001, pose.basis.get_scale().x)), GRIP_R.origin)
	return Transform3D(Basis.IDENTITY, pose.origin)
