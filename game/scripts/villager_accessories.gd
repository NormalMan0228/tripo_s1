extends RefCounted
## Clothes follow the reviewed skeleton; all accessories are developer-owned art.
const A=preload("res://scripts/art.gd")
const L=preload("res://scripts/world_detail.gd")

static func dress(actor: Node3D, role: String) -> void:
	if not is_instance_valid(actor.hand_skeleton):return
	var bone: int=actor.hand_skeleton.find_bone("Spine02")
	if bone<0:return
	var root := Node3D.new()
	actor.visual.add_child(root)
	root.position=Vector3(0,.95,-.18)
	if role in ["farmer","wardrobe"]:
		var linen := Color("d6c59d") if role=="farmer" else Color("eee0c3")
		A.box(root,Vector3(0,-.19,-.025),Vector3(.37,.49,.035),linen)
		A.box(root,Vector3(0,.06,-.03),Vector3(.26,.25,.038),linen)
		for side in [-1,1]:A.box(root,Vector3(side*.095,.20,.015),Vector3(.035,.24,.025),Color("7c9673"))
		A.box(root,Vector3(0,-.19,-.058),Vector3(.24,.16,.025),linen.darkened(.10))
		if role=="farmer":
			for x in [-.06,.035]:
				var packet := A.box(root,Vector3(x,-.13,-.073),Vector3(.075,.10,.018),Color("efdfb5"))
				packet.rotation.z=x*1.1
				A.sphere(root,Vector3(x,-.11,-.085),Vector3(.025,.04,.012),Color("718e64"))
		else:
			for i in 7:A.box(root,Vector3(.075,.02+i*.027,-.065),Vector3(.065,.013,.015),Color("b39754"))
	elif role=="guide":
		A.box(root,Vector3(0,.11,-.075),Vector3(.29,.09,.055),Color("abbdba"))
		for side in [-1,1]:
			A.sphere(root,Vector3(side*.095,.16,-.1),Vector3(.10,.16,.1),Color("4e6567"))
			A.sphere(root,Vector3(side*.095,.21,-.12),Vector3(.071,.045,.071),Color("d1d6b7"))
	elif role=="map":
		var compass := A.sphere(root,Vector3(.16,.08,-.06),Vector3(.105,.105,.034),Color("c4a165"))
		A.box(compass,Vector3(0,0,-.02),Vector3(.013,.065,.014),Color("e6dfc7")).rotation.z=.35
	# Convert from character-space clothing to this rig's rest-bone space.
	var attachment := BoneAttachment3D.new();attachment.bone_name="Spine02"
	actor.hand_skeleton.add_child(attachment)
	var desired: Transform3D=actor.visual.global_transform*root.transform
	var rest: Transform3D=actor.hand_skeleton.global_transform*actor.hand_skeleton.get_bone_global_rest(bone)
	root.reparent(attachment,false);root.transform=rest.affine_inverse()*desired
