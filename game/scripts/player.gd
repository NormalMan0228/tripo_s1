extends CharacterBody3D

const Profile=preload("res://scripts/controller_profile.gd")
const SPEED := Profile.VILLAGE_WALK
var controls_enabled := true
var visual_only := false
var facing := Vector3.FORWARD
var visual: Node3D
var external_motion := Vector2.ZERO
var external_velocity := Vector2.ZERO
var locomotion_velocity := Vector2.ZERO
var locomotion_pose: SkeletonModifier3D
var stride := 0.0
var left_leg: Node3D
var right_leg: Node3D
var equipment: Node3D
var tool_node: Node3D
var equipped := ""
var animation_player: AnimationPlayer
var current_clip := ""
var hand_skeleton: Skeleton3D
var hand_index := -1
var reaction_tween: Tween
var action_pose: SkeletonModifier3D
var finger_pose: SkeletonModifier3D
var sprinting := false
var action_facing := Vector3.ZERO
var facing_until := 0.0
var avatar: Dictionary={}
var action_until := 0.0
var tool_grip := Basis.IDENTITY
var ambient_clip := "idle"
var greeting_until := 0.0
const Art = preload("res://scripts/art.gd")

func _ready() -> void:
	Profile.ensure_input()
	floor_snap_length = 0.3
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = Profile.BODY_RADIUS
	capsule.height = Profile.BODY_HEIGHT
	shape.shape = capsule
	shape.position.y = Profile.BODY_HEIGHT*.5
	add_child(shape)
	visual = Node3D.new()
	add_child(visual)
	_build_explorer()
	apply_colors()
	visual.rotation.y=PI
	return

func _build_explorer() -> void:
	if avatar.get("character")=="haeru":
		var actor := preload("res://assets/haeru_v1.glb").instantiate() as Node3D
		visual.add_child(actor)
		actor.scale=Vector3.ONE*Profile.CHARACTER_SCALE
		# Developer GLB is X-forward; Player visual expects -Z-forward.
		actor.rotation.y=PI*.5
		animation_player=actor.find_children("*","AnimationPlayer",true,false)[0]
		hand_skeleton=actor.find_children("*","Skeleton3D",true,false)[0]
		hand_index=hand_skeleton.find_bone("R_Hand")
		for clip in ["idle","walk","fishing"]:
			animation_player.get_animation(clip).loop_mode=Animation.LOOP_LINEAR
		animation_player.get_animation("greet").loop_mode=Animation.LOOP_NONE
		ambient_clip="fishing"
		animation_player.play("fishing")
		animation_player.advance(0)
		return
	if avatar.get("character","explorer_b")=="explorer_b":
		var character=preload("res://scripts/style_character.gd").new()
		character.wardrobe=true
		visual.add_child(character)
		character.scale=Vector3.ONE*Profile.CHARACTER_SCALE;character.rotation.y=PI
		animation_player=character.animator;hand_skeleton=character.body_skeleton
		hand_index=hand_skeleton.find_bone("R_Hand")
		action_pose=preload("res://scripts/action_pose.gd").new();hand_skeleton.add_child(action_pose)
		action_pose.modification_processed.connect(update_tool_pose)
		finger_pose=preload("res://scripts/finger_pose.gd").new();hand_skeleton.add_child(finger_pose);finger_pose.configure(animation_player)
		var library: AnimationLibrary=animation_player.get_animation_library("")
		for pair in [["idle","movement/B_Scout"],["walk","movement/B_TrailWalk"],["run","movement/B_Dash"]]:
			library.add_animation(pair[0],animation_player.get_animation(pair[1]).duplicate(true))
		locomotion_pose=preload("res://scripts/locomotion_pose.gd").new()
		hand_skeleton.add_child(locomotion_pose)
		locomotion_pose.configure(self)
		return
	# Authored fallback remains playable if the optional Scenario model is unavailable.
	var hero_path: String="res://assets/"+str(avatar.get("character","explorer"))+".glb"
	if ResourceLoader.exists(hero_path):
		var packed := load(hero_path) as PackedScene
		if packed:
			var hero := packed.instantiate() as Node3D
			if hero:
				var meshes: Array[MeshInstance3D]=[]
				var loader = preload("res://scripts/model_loader.gd")
				loader._collect_meshes(hero,meshes)
				var bounds := AABB()
				var first := true
				for instance in meshes:
					var b: AABB=loader._local_transform(instance,hero)*instance.get_aabb()
					bounds=b if first else bounds.merge(b)
					first=false
				if bounds.size.y>0.001:
					var pivot := Node3D.new()
					visual.add_child(pivot)
					pivot.add_child(hero)
					pivot.scale=Vector3.ONE*(Profile.CHARACTER_SCALE/bounds.size.y)
					hero.position-=Vector3(bounds.get_center().x,bounds.position.y,bounds.get_center().z)
					pivot.rotation.y=PI
					var controllers := hero.find_children("*","AnimationPlayer",true,false)
					var skeletons := hero.find_children("*","Skeleton3D",true,false)
					if not skeletons.is_empty():
						hand_skeleton=skeletons[0]
						hand_index=hand_skeleton.find_bone("R_Hand")
						action_pose=preload("res://scripts/action_pose.gd").new()
						hand_skeleton.add_child(action_pose)
						action_pose.modification_processed.connect(update_tool_pose)
					if not controllers.is_empty():
						animation_player=controllers[0]
						for clip in ["idle","walk","run"]:
							if animation_player.has_animation(clip):
								animation_player.get_animation(clip).loop_mode=Animation.LOOP_LINEAR
					return
	Art.sphere(visual,Vector3(0,1.35,0),Vector3(0.65,0.66,0.6),Color("e4b587"))
	Art.sphere(visual,Vector3(0,1.62,0.04),Vector3(0.7,0.33,0.65),Color("30595b"))
	for x in [-0.22,0.0,0.22]:
		var tuft := Art.cone(visual,Vector3(x,1.5,-0.28),0.18,0.33,Color("30595b"))
		tuft.rotation_degrees.z=180
	Art.box(visual,Vector3(0,0.9,0),Vector3(0.55,0.65,0.38),Color("dba448"))
	Art.box(visual,Vector3(0,1.15,-0.22),Vector3(0.58,0.14,0.1),Color("417f7a"))
	Art.box(visual,Vector3(0.15,0.95,-0.23),Vector3(0.12,0.4,0.08),Color("417f7a"))
	Art.box(visual,Vector3(0,0.95,0.3),Vector3(0.45,0.5,0.25),Color("a68c63"))
	for x in [-0.36,0.36]:
		Art.box(visual,Vector3(x,0.9,0),Vector3(0.17,0.47,0.19),Color("dba448"))
		Art.sphere(visual,Vector3(x,0.64,0),Vector3(0.18,0.2,0.18),Color("e4b587"))
	for x in [-0.16,0.16]:
		var leg := Node3D.new()
		visual.add_child(leg)
		leg.position=Vector3(x,0.6,0)
		Art.box(leg,Vector3(0,-0.2,0),Vector3(0.22,0.4,0.24),Color("526552"))
		Art.box(leg,Vector3(0,-0.48,-0.06),Vector3(0.24,0.18,0.35),Color("765744"))
		if x<0: left_leg=leg
		else: right_leg=leg
	for x in [-0.14,0.14]: Art.sphere(visual,Vector3(x,1.37,-0.275),Vector3(0.09,0.12,0.06),Color("263f42"))
	for y in [0.71,0.88,1.05]: Art.sphere(visual,Vector3(-0.02,y,-0.21),Vector3.ONE*0.055,Color("655442"))

func equip(item: String) -> void:
	if item==equipped: return
	equipped=item
	if is_instance_valid(finger_pose):finger_pose.holding=not item.is_empty()
	if is_instance_valid(equipment):
		if equipment.get_parent(): equipment.get_parent().remove_child(equipment)
		equipment.queue_free()
	equipment=null
	tool_node=null
	if item.is_empty(): return
	var tool: Node3D
	if is_instance_valid(hand_skeleton) and hand_index>=0:
		var attachment := BoneAttachment3D.new()
		attachment.bone_name="R_Hand"
		hand_skeleton.add_child(attachment)
		equipment=attachment
		tool=Node3D.new()
		equipment.add_child(tool)
		var hand_transform: Transform3D=hand_skeleton.global_transform*hand_skeleton.get_bone_global_pose(hand_index)
		tool.basis=hand_transform.basis.inverse()*visual.global_basis.orthonormalized()
		if item=="axe": tool.basis=tool.basis*Basis(Vector3.FORWARD,PI)
		if avatar.get("character","explorer_b")=="explorer_b":
			# Hand-local palm center and the line across the finger bases form the grip.
			tool.position=Vector3(-.015,.095,0)
			tool.basis=Basis(Vector3.LEFT,Vector3.FORWARD,Vector3.DOWN).scaled(Vector3.ONE/hand_transform.basis.get_scale().x)
		elif avatar.get("character")=="haeru":
			tool.position=Vector3(0,.045,0)
			# Establish the grip once; the original fishing/greeting wrist animates it.
			tool.basis=hand_transform.basis.inverse()*Basis(Vector3.UP,visual.global_rotation.y)*Basis(Vector3.RIGHT,-.35)
		tool_grip=tool.basis
	else:
		equipment=Node3D.new()
		visual.add_child(equipment)
		equipment.position=Vector3(0.43,0.77,-0.12)
		tool=equipment
	tool_node=tool
	if item=="rod":
		if ResourceLoader.exists("res://assets/fishing_rod.glb"):
			tool.add_child((load("res://assets/fishing_rod.glb") as PackedScene).instantiate())
			tool.set_meta("line_tip",Vector3(0,1.63,0))
			return
		Art.box(tool,Vector3(0,0.85,0),Vector3(0.045,2.9,0.045),Color("ac8758"))
		Art.sphere(tool,Vector3(0.1,0.03,0),Vector3(0.18,0.18,0.12),Color("819f9d"))
		return
	if item=="watering_can":
		Art.sphere(tool,Vector3(0,-0.05,0),Vector3(0.45,0.45,0.4),Color("76acb0"))
		Art.box(tool,Vector3(0.3,0.1,0),Vector3(0.5,0.09,0.09),Color("b1d1cd"))
		return
	if item in ["axe","spear"]:
		var source := load("res://assets/authored_"+item+"_v1.glb") as PackedScene
		if source:
			tool.add_child(source.instantiate())
			return
	Art.box(tool,Vector3.ZERO,Vector3(0.035,1.0,0.035),Color("80634b"))
	if item=="spear":
		Art.cone(tool,Vector3(0,0.73,0),0.12,0.3,Color("cad2cb"))
	else:
		Art.box(tool,Vector3(0.07,0.43,0),Vector3(0.32,0.23,0.12),Color("a8b8ae"))

func update_tool_pose() -> void:
	if not is_instance_valid(tool_node) or not is_instance_valid(hand_skeleton): return
	if avatar.get("character","explorer_b") in ["explorer_b","haeru"]:
		tool_node.basis=tool_grip
		return
	if current_clip=="slash":
		tool_node.basis=tool_grip
		return
	var hand_world: Transform3D=hand_skeleton.global_transform*hand_skeleton.get_bone_global_pose(hand_index)
	var angle := 0.0
	if is_instance_valid(action_pose) and action_pose.kind in ["attack","gather"]:
		angle=-1.6*action_pose.applied_amount
	# Keep the blade ahead of the hand while the imported wrist turns.
	tool_node.basis=hand_world.basis.inverse()*visual.global_basis.orthonormalized()*Basis(Vector3.RIGHT,angle)
	if equipped=="axe": tool_node.basis=tool_node.basis*Basis(Vector3.FORWARD,PI)

func _physics_process(delta: float) -> void:
	var movement := Vector2.ZERO
	if controls_enabled:
		movement = Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var speed := Profile.VILLAGE_RUN if sprinting else SPEED
	velocity.x = movement.x * speed
	velocity.z = movement.y * speed
	if visual_only:
		velocity=Vector3.ZERO
	elif not is_on_floor():
		velocity.y -= 20.0 * delta
	else:
		velocity.y = 0.0
	if not visual_only:move_and_slide()
	locomotion_velocity=Vector2(get_real_velocity().x,get_real_velocity().z) if controls_enabled and not visual_only else external_velocity
	var look_motion := locomotion_velocity.normalized() if controls_enabled else external_motion
	if Time.get_ticks_msec()*0.001<facing_until:
		facing=action_facing
	elif look_motion.length_squared() > 0.01:
		facing = Vector3(look_motion.x, 0.0, look_motion.y)
	if facing.length_squared()>0.01:
		visual.rotation.y = lerp_angle(visual.rotation.y, atan2(-facing.x, -facing.z), Profile.damping(Profile.TURN_RESPONSE,delta))
	if is_instance_valid(action_pose): action_pose.body_basis=visual.global_basis.orthonormalized()
	var moving := minf(1.0,locomotion_velocity.length()/SPEED)
	stride+=delta*11*moving
	if is_instance_valid(animation_player) and animation_player.has_animation("walk") and animation_player.has_animation("idle"):
		var desired := ("run" if (sprinting or locomotion_velocity.length()>3.4) and animation_player.has_animation("run") else "walk") if moving>0.1 else "idle"
		if avatar.get("character")=="haeru" and moving<=.1:
			desired="greet" if Time.get_ticks_msec()*.001<greeting_until else ambient_clip
		if Time.get_ticks_msec()*0.001<action_until: desired="slash"
		if current_clip!=desired:
			current_clip=desired
			animation_player.play(desired,0.08 if desired=="slash" else 0.18)
			if desired=="slash": animation_player.seek(1.1,true)
		if is_instance_valid(locomotion_pose) and desired in ["walk","run"]:
			animation_player.speed_scale=clampf(animation_player.get_animation(desired).length/locomotion_pose.cycle_seconds,.5,3.2)
		else:
			animation_player.speed_scale=3.2 if desired=="slash" else (1.0 if desired=="run" else (1.5 if moving>0.1 else 1.0))
		visual.position.y=0
	else:
		visual.position.y=absf(sin(stride))*0.045*moving
	if is_instance_valid(left_leg):
		left_leg.rotation.x=sin(stride)*0.5*moving
		right_leg.rotation.x=-sin(stride)*0.5*moving
	if position.y < -10.0:
		position = Vector3(0, 0.2, 4)

func react(kind: String) -> void:
	# Visual response only. The collision body and server position never change.
	if kind in ["attack","gather"] and equipped=="axe" and animation_player and animation_player.has_animation("slash"):
		# Tripo's 6.6s clip has long idle handles. Use the actual wind-up, strike and recovery.
		action_until=Time.get_ticks_msec()*0.001+0.7
		current_clip=""
	elif is_instance_valid(action_pose): action_pose.trigger(kind)
	if reaction_tween and reaction_tween.is_valid(): reaction_tween.kill()
	visual.scale=Vector3.ONE
	reaction_tween=create_tween()
	reaction_tween.tween_property(visual,"scale",Vector3(1.06,0.91,1.06) if kind=="hurt" else Vector3(0.97,1.035,0.97),0.07)
	reaction_tween.tween_property(visual,"scale",Vector3.ONE,0.17).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	if not is_instance_valid(action_pose) and kind in ["attack","gather"] and is_instance_valid(equipment) and equipment.get_child_count()>0:
		var tool := equipment.get_child(0) as Node3D
		if tool and not tool.has_meta("swing"):
			tool.set_meta("swing",true)
			var rest := tool.rotation
			var swing := tool.create_tween()
			swing.tween_property(tool,"rotation",rest+Vector3(0.25,0,-0.9),0.08)
			swing.tween_property(tool,"rotation",rest,0.2)
			swing.tween_callback(func(): tool.remove_meta("swing"))

func face_point(point: Vector3) -> void:
	var direction := point-position
	direction.y=0
	if direction.length_squared()<0.001: return
	action_facing=direction.normalized()
	facing=action_facing
	facing_until=Time.get_ticks_msec()*0.001+0.4
	if avatar.get("character")=="haeru":greeting_until=Time.get_ticks_msec()*.001+2.5

func apply_avatar(value: Dictionary) -> void:
	if value==avatar: return
	avatar=value.duplicate(true)
	if not is_instance_valid(visual): return
	var old_tool := equipped
	equipped=""
	for child in visual.get_children():
		visual.remove_child(child)
		child.queue_free()
	animation_player=null
	hand_skeleton=null
	action_pose=null
	finger_pose=null
	locomotion_pose=null
	equipment=null
	tool_node=null
	current_clip=""
	left_leg=null
	right_leg=null
	_build_explorer()
	apply_colors()
	equip(old_tool)

func apply_colors() -> void:
	# Partitioned GLBs retain original weights, UVs and textures per semantic surface.
	for mesh in visual.find_children("*","MeshInstance3D",true,false):
		for index in mesh.mesh.get_surface_count():
			var source: Material=mesh.mesh.surface_get_material(index)
			if not source is StandardMaterial3D: continue
			var fields := source.resource_name.to_lower().split("__")
			var part: String=fields[0]
			if part not in ["hair","coat","pants","boots","skin","backpack"]: continue
			if avatar.get("character")=="explorer_b" and avatar.get(part)=={"coat":"#dba448","pants":"#526552","boots":"#765744"}.get(part):continue
			var material: StandardMaterial3D=source.duplicate()
			if part=="backpack" and not avatar.get("backpack",true):
				material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
				material.albedo_color.a=0
			elif part!="backpack" and avatar.has(part) and fields.size()==2 and source.albedo_texture:
				var tint := ShaderMaterial.new()
				tint.shader=preload("res://shaders/avatar_tint.gdshader")
				tint.set_shader_parameter("albedo_texture",source.albedo_texture)
				tint.set_shader_parameter("tint",Color(avatar[part]))
				tint.set_shader_parameter("reference_color",Color("#e4b587") if part=="skin" else Color("#"+fields[1]))
				tint.set_shader_parameter("skin_part",part=="skin")
				tint.set_shader_parameter("gold_cloth_only",avatar.get("character")=="explorer_b" and part=="coat")
				mesh.set_surface_override_material(index,tint)
				continue
			mesh.set_surface_override_material(index,material)
	var headwear: String=avatar.get("headwear","none")
	if headwear!="none":
		var holder := Node3D.new()
		visual.add_child(holder)
		holder.position.y=1.63
		if avatar.get("character","explorer")!="explorer": holder.scale=Vector3.ONE*0.58
		if is_instance_valid(hand_skeleton):
			var head := hand_skeleton.find_bone("Head")
			if head>=0:
				var attachment := BoneAttachment3D.new()
				attachment.bone_name="Head"
				hand_skeleton.add_child(attachment)
				var desired: Transform3D=visual.global_transform*holder.transform
				var rest: Transform3D=hand_skeleton.global_transform*hand_skeleton.get_bone_global_rest(head)
				holder.reparent(attachment,false)
				holder.transform=rest.affine_inverse()*desired
		var hat_color := Color(avatar.get("coat","#dba448")).darkened(0.15)
		Art.sphere(holder,Vector3(0,0.03,0),Vector3(0.63,0.2,0.57),hat_color)
		if headwear=="cap": Art.box(holder,Vector3(0,-0.04,-0.27),Vector3(0.42,0.045,0.3),hat_color)
		else: Art.sphere(holder,Vector3(0.05,0.09,0),Vector3(0.52,0.16,0.5),hat_color)
	if avatar.get("backpack",true) and avatar.get("character","explorer")!="explorer":
		var bag := Node3D.new()
		visual.add_child(bag)
		bag.position=Vector3(0,0.98,0.15)
		Art.box(bag,Vector3.ZERO,Vector3(0.32,0.4,0.18),Color("aa8c64"))
		Art.box(bag,Vector3(0,-0.07,0.105),Vector3(0.26,0.17,0.06),Color("85694c"))
		if hand_skeleton and hand_skeleton.find_bone("Spine02")>=0:
			var attachment := BoneAttachment3D.new()
			attachment.bone_name="Spine02"
			hand_skeleton.add_child(attachment)
			var desired: Transform3D=visual.global_transform*bag.transform
			var rest: Transform3D=hand_skeleton.global_transform*hand_skeleton.get_bone_global_rest(hand_skeleton.find_bone("Spine02"))
			bag.reparent(attachment,false)
			bag.transform=rest.affine_inverse()*desired
	elif not avatar.get("backpack",true) and avatar.get("character","explorer")=="explorer":
		# The generated backpack shares an outer shell with the coat. Close the exposed back.
		var coat_back := Art.sphere(visual,Vector3(0,0.79,0.14),Vector3(0.43,0.42,0.19),Color(avatar.get("coat","#c28b38")).darkened(0.2))
		if hand_skeleton and hand_skeleton.find_bone("Spine02")>=0:
			var attachment := BoneAttachment3D.new()
			attachment.bone_name="Spine02"
			hand_skeleton.add_child(attachment)
			var desired: Transform3D=coat_back.global_transform
			var rest: Transform3D=hand_skeleton.global_transform*hand_skeleton.get_bone_global_rest(hand_skeleton.find_bone("Spine02"))
			coat_back.reparent(attachment,false)
			coat_back.transform=rest.affine_inverse()*desired
