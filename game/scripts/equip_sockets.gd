extends RefCounted
## Equipment sockets: one set of names for every character rig, so an item knows where it goes
## without per-tool rotation fixes.
##   hand_r, hand_l  palm centre; the item's +Y runs along the grip (from the little finger to the
##                   thumb side, toward the tool head), its +Z away from the palm
##   back            between the shoulder blades, diagonal; the item's +Y along the strap
##   hip_r, hip_l    at the belt on each side, hanging; the item's +Y points down
##   head            on the crown; the item's +Y up
## Bones come from the ISS-1 humanoid map (ix/ix_rig.gd), so every rig it knows works: the player
## (style_character) and the residents (the wardrobe GLB) share Explorer B, haeru and the legacy GLBs
## are the A-pose Tripo rig. ISS-1's own names are accepted too (ALIASES: grip_r is hand_r, grip_l
## hand_l, head_top head), so interaction code and held items share these nodes. The frames are worked
## out from the rig's rest pose
## (up = hips to head, forward = foot to toe, side = left hand to right hand), so a re-export with
## other bone rolls keeps working. The right hand keeps the hand-local grip the player used before
## (player.gd equip(), checked on the explorer_b rig); the left hand is its mirror image.
## Item data (grip point, turn, scale, the socket it is stowed on) is assets/equip/equip_sockets.json;
## crafted items get theirs from estimate_grip() (long axis, thinner end = handle).
const DATA_PATH := "res://assets/equip/equip_sockets.json"
const NAMES := ["hand_r", "hand_l", "back", "hip_r", "hip_l", "head"]
const ALIASES := {"grip_r":"hand_r", "grip_l":"hand_l", "head_top":"head"}
const IxRig = preload("res://scripts/ix/ix_rig.gd")
## Socket -> ISS-1 humanoid bone (the same bones as IxRig.SOCKETS).
const BONES := {"hand_r":"RightHand", "hand_l":"LeftHand", "back":"UpperChest", "hip_r":"Hips", "hip_l":"Hips", "head":"Head"}
## The right-hand grip in the hand bone's own frame (IxRig.GRIP_R, what player.gd always used): palm
## centre and the axes the tool models were authored for.
const HAND_R_OFFSET := IxRig.GRIP_R.origin
const HAND_R_BASIS := IxRig.GRIP_R.basis
static var _data := {}

static func data() -> Dictionary:
	if _data.is_empty():
		var text := FileAccess.get_file_as_string(DATA_PATH)
		var parsed = JSON.parse_string(text) if not text.is_empty() else null
		_data = parsed if parsed is Dictionary else {"items":{}, "sockets":{}}
	return _data

## The equip record of an item ({} when it has none): hold, stow, grip, rot, stow_rot, scale.
static func item(name: String) -> Dictionary:
	var items: Dictionary = data().get("items", {})
	return items.get(name, {})

## Mixamo rigs (05's monsters, the NPCs boni and sol; ':' became '_' for Godot node paths).
const MIXAMO := {"RightHand":"mixamorig_RightHand", "LeftHand":"mixamorig_LeftHand", "UpperChest":"mixamorig_Spine2",
	"Hips":"mixamorig_Hips", "Head":"mixamorig_Head", "LeftFoot":"mixamorig_LeftFoot", "LeftToes":"mixamorig_LeftToeBase",
	"RightLowerArm":"mixamorig_RightForeArm"}

## The ISS-1 profile ("vrs", "tripo41_apose", ...) or "mixamo" when the rig has every socket bone and
## the axis bones, else "".
static func rig_of(skeleton: Skeleton3D) -> String:
	if not is_instance_valid(skeleton): return ""
	var profile := IxRig.detect(skeleton)
	if profile.is_empty() and skeleton.find_bone("mixamorig_Hips") >= 0: profile = "mixamo"
	if profile.is_empty(): return ""
	for humanoid in ["RightHand", "LeftHand", "UpperChest", "Hips", "Head", "LeftFoot", "LeftToes"]:
		if bone(skeleton, humanoid) < 0: return ""
	return profile

## The rig bone for an ISS-1 humanoid name (-1 when none).
static func bone(skeleton: Skeleton3D, humanoid: String) -> int:
	if skeleton.find_bone("mixamorig_Hips") >= 0: return skeleton.find_bone(str(MIXAMO.get(humanoid, "mixamorig_"+humanoid)))
	return IxRig.bone(skeleton, humanoid)

## The socket frame on this skeleton (made on first use, a BoneAttachment3D "Socket_<name>" with a
## "Frame" child); null when the rig has no such bone. Items are children of the returned node.
static func socket(skeleton: Skeleton3D, name: String) -> Node3D:
	name = str(ALIASES.get(name, name))
	if not is_instance_valid(skeleton) or not name in NAMES: return null
	var existing := skeleton.get_node_or_null("Socket_"+name)
	if existing: return existing.get_node("Frame")
	var rig := rig_of(skeleton)
	if rig.is_empty(): return null
	var bone_index := bone(skeleton, BONES[name])
	var attachment := BoneAttachment3D.new()
	attachment.name = "Socket_"+name
	attachment.bone_name = skeleton.get_bone_name(bone_index)
	skeleton.add_child(attachment)
	var frame := Node3D.new()
	frame.name = "Frame"
	attachment.add_child(frame)
	# Tuning is in metres; skeleton space may be scaled (the rig and the character's size).
	var unit := 1.0/maxf(0.0001, skeleton.global_transform.basis.get_scale().x) if skeleton.is_inside_tree() else 1.0
	frame.transform = local_frame(skeleton, name, unit)
	# Items are sized in metres: undo the rig's and the character's scale on the socket.
	var world_scale := (skeleton.global_transform*skeleton.get_bone_global_rest(bone_index)).basis.get_scale().x if skeleton.is_inside_tree() else 1.0
	if world_scale > 0.0001: frame.basis = frame.basis.scaled_local(Vector3.ONE/world_scale)
	return frame

## Body axes in skeleton space, from the rest pose: up, forward, right (unit vectors).
static func body_axes(skeleton: Skeleton3D) -> Dictionary:
	var at := func(humanoid: String) -> Vector3: return skeleton.get_bone_global_rest(bone(skeleton, humanoid)).origin
	var up: Vector3 = (at.call("Head")-at.call("Hips")).normalized()
	var forward: Vector3 = at.call("LeftToes")-at.call("LeftFoot")
	forward = (forward-up*forward.dot(up)).normalized()
	var right: Vector3 = at.call("RightHand")-at.call("LeftHand")
	right = (right-up*right.dot(up)-forward*right.dot(forward)).normalized()
	return {"up":up, "forward":forward, "right":right, "mid":(at.call("RightHand")+at.call("LeftHand"))*0.5}

## The socket's frame in its bone's local space (unscaled), built in skeleton space.
## unit: skeleton-space length of one metre.
static func local_frame(skeleton: Skeleton3D, name: String, unit := 1.0) -> Transform3D:
	var bone_rest := func(socket_name: String) -> Transform3D: return skeleton.get_bone_global_rest(bone(skeleton, BONES[socket_name]))
	var rest: Transform3D = bone_rest.call(name)
	var axes := body_axes(skeleton)
	var up: Vector3 = axes.up
	var forward: Vector3 = axes.forward
	var right: Vector3 = axes.right
	var tune: Dictionary = data().get("sockets", {}).get(name, {})
	var wanted := Transform3D.IDENTITY
	match name:
		"hand_r":
			if rig_of(skeleton) in ["vrs", "tripo41_apose"]: return Transform3D(HAND_R_BASIS, HAND_R_OFFSET)
			# Other rigs: from the rest pose. Palm centre a little past the wrist along the hand; the
			# grip line runs forward (a fist at the side holds a tool pointing ahead), away from the palm down.
			var hand: Vector3 = rest.origin
			var elbow_index := bone(skeleton, "RightLowerArm")
			var along := (hand-skeleton.get_bone_global_rest(elbow_index).origin).normalized() if elbow_index >= 0 else right
			var down := -up
			wanted = Transform3D(Basis(forward.cross(down), forward, down).orthonormalized(), hand+along*float(tune.get("palm", 0.07))*unit)
		"hand_l":
			# The right grip mirrored across the body's middle plane (normal = right).
			var right_grip: Transform3D = bone_rest.call("hand_r")*local_frame(skeleton, "hand_r", unit)
			# I - 2 r r^T, column by column.
			var mirror := Basis(Vector3.RIGHT-right*(2.0*right.x), Vector3.UP-right*(2.0*right.y), Vector3.BACK-right*(2.0*right.z))
			var mid: Vector3 = axes.mid
			var p: Vector3 = mid+mirror*(right_grip.origin-mid)
			wanted = Transform3D(mirror*right_grip.basis*mirror, p)
		"back":
			var spine: Vector3 = rest.origin
			var tilt := deg_to_rad(float(tune.get("tilt_deg", 28.0)))
			var along := up.rotated(forward, tilt)
			var out := -forward
			wanted = Transform3D(Basis(along.cross(out), along, out).orthonormalized(), spine+(out*float(tune.get("out", 0.13))+up*float(tune.get("up", 0.04)))*unit)
		"hip_r", "hip_l":
			var side := right if name == "hip_r" else -right
			var down := -up
			wanted = Transform3D(Basis(down.cross(side), down, side).orthonormalized(), rest.origin+(side*float(tune.get("side", 0.17))+up*float(tune.get("up", 0.0))+forward*float(tune.get("forward", 0.02)))*unit)
		"head":
			wanted = Transform3D(Basis(up.cross(forward), up, forward).orthonormalized(), rest.origin+up*float(tune.get("up", 0.16))*unit)
	return rest.affine_inverse()*wanted

## The item's transform inside its socket frame: the grip point on the socket origin, then the
## record's turn (degrees, x/y/z) and scale. `stowed` uses stow_rot.
static func placement(record: Dictionary, stowed := false) -> Transform3D:
	var turn: Array = record.get("stow_rot" if stowed else "rot", [0, 0, 0])
	var basis := Basis.from_euler(Vector3(deg_to_rad(float(turn[0])), deg_to_rad(float(turn[1])), deg_to_rad(float(turn[2]))))
	basis = basis.scaled_local(Vector3.ONE*float(record.get("scale", 1.0)))
	var grip: Array = record.get("grip", [0, 0, 0])
	return Transform3D(basis, -(basis*Vector3(float(grip[0]), float(grip[1]), float(grip[2]))))

## Grip guess for a crafted item (any Node3D with meshes): its longest bounding-box axis is the
## handle line and the thinner end the handle; the grip sits GRIP_IN of the length in from that end.
## Returns an item record (hold hand_r, stow back) in the json's format, plus "length" and "radius".
const GRIP_IN := 0.12
static func estimate_grip(root: Node3D) -> Dictionary:
	var points := PackedVector3Array()
	for mesh_node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh := (mesh_node as MeshInstance3D).mesh
		if mesh == null: continue
		var into := root.global_transform.affine_inverse()*(mesh_node as MeshInstance3D).global_transform
		for s in mesh.get_surface_count():
			var arrays := mesh.surface_get_arrays(s)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var step := maxi(1, vertices.size()/4000)
			for i in range(0, vertices.size(), step): points.append(into*vertices[i])
	if points.is_empty(): return {}
	var box := AABB(points[0], Vector3.ZERO)
	for p in points: box = box.expand(p)
	var axis := box.get_longest_axis_index()
	var low := box.position[axis]
	var length := box.size[axis]
	if length < 0.001: return {}
	# Spread across the axis near each end: the thinner end is the handle.
	var spread := [0.0, 0.0]
	var centre := [Vector3.ZERO, Vector3.ZERO]
	var counts := [0, 0]
	for p in points:
		var t := (p[axis]-low)/length
		var end := 0 if t < 0.2 else (1 if t > 0.8 else -1)
		if end < 0: continue
		centre[end] += p
		counts[end] += 1
	for end in 2: centre[end] = centre[end]/maxf(1.0, counts[end])
	for p in points:
		var t := (p[axis]-low)/length
		var end := 0 if t < 0.2 else (1 if t > 0.8 else -1)
		if end < 0: continue
		var off: Vector3 = p-centre[end]
		off[axis] = 0.0
		spread[end] = maxf(spread[end], off.length())
	var handle := 0 if spread[0] <= spread[1] else 1
	var direction := 1.0 if handle == 0 else -1.0
	var grip: Vector3 = centre[handle]
	grip[axis] = low+length*(GRIP_IN if handle == 0 else 1.0-GRIP_IN)
	# Turn the long axis (pointing from the handle to the head) onto the socket's +Y.
	var along := Vector3.ZERO
	along[axis] = direction
	var turn := Quaternion(along, Vector3.UP).get_euler()
	var rot := [snappedf(rad_to_deg(turn.x), 0.1), snappedf(rad_to_deg(turn.y), 0.1), snappedf(rad_to_deg(turn.z), 0.1)]
	var rotated := Basis.from_euler(turn)*grip
	return {"hold":"hand_r", "stow":"back", "grip":[snappedf(grip.x, 0.001), snappedf(grip.y, 0.001), snappedf(grip.z, 0.001)],
		"rot":rot, "stow_rot":rot, "scale":1.0, "estimated":true, "length":snappedf(length, 0.001), "radius":snappedf(spread[handle], 0.001),
		"grip_turned":[snappedf(rotated.x, 0.001), snappedf(rotated.y, 0.001), snappedf(rotated.z, 0.001)]}
