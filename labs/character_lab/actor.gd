extends CharacterBody3D

var visual: Node3D
var animator: AnimationPlayer
var skeleton: Skeleton3D
var clip := "idle"
var display_motion := "idle"
var mode := "review"
var speed := 0.0
var face := PI
var original_materials: Array = []
var model_path := "res://assets/explorer_b_v5.glb"
var locomotion_velocity := Vector2.ZERO
var current_clip: String:
	get: return clip
var locomotion_pose: SkeletonModifier3D
var jump_was_down := false

func _ready() -> void:
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.height=1.55;capsule.radius=.26;shape.shape=capsule;shape.position.y=.775
	add_child(shape);floor_snap_length=.35
	visual=Node3D.new();add_child(visual)
	var model := (load(model_path) as PackedScene).instantiate() as Node3D
	visual.add_child(model);model.scale=Vector3.ONE*1.7;model.rotation.y=PI*.5
	animator=model.find_children("*","AnimationPlayer",true,false)[0]
	skeleton=model.find_children("*","Skeleton3D",true,false)[0]
	for child in model.find_children("*","MeshInstance3D",true,false):
		original_materials.append([child,child.material_override])
	for name in ["idle","walk","run","hands","reach"]:
		if animator.has_animation(name):animator.get_animation(name).loop_mode=Animation.LOOP_LINEAR
	visual.rotation.y=face
	play_motion("idle")
	locomotion_pose=preload("res://locomotion_pose.gd").new()
	skeleton.add_child(locomotion_pose)
	locomotion_pose.configure(self)

func play_motion(name: String) -> void:
	if animator.has_animation(name):
		clip=name;animator.play(name,.2)
	elif animator.has_animation("B_Scout"):
		clip=name;animator.play("B_Scout",.2)

func _physics_process(delta: float) -> void:
	var input := Vector2.ZERO
	if mode=="play":
		input=Vector2(float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)),float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W))).limit_length()
	var target := 4.5 if Input.is_physical_key_pressed(KEY_SHIFT) else 2.8
	velocity.x=input.x*target;velocity.z=input.y*target
	velocity.y=0 if is_on_floor() else velocity.y-20*delta
	var jump := Input.is_physical_key_pressed(KEY_SPACE)
	if mode=="play" and jump and not jump_was_down and is_on_floor():velocity.y=5.0
	jump_was_down=jump
	move_and_slide();speed=Vector2(get_real_velocity().x,get_real_velocity().z).length()
	locomotion_velocity=Vector2(get_real_velocity().x,get_real_velocity().z) if mode=="play" else Vector2.ZERO
	if mode=="play":
		var desired := ("run" if speed>3.4 else "walk") if speed>.1 else "idle"
		if desired!=clip:play_motion(desired)
		if speed>.1:
			face=atan2(-velocity.x,-velocity.z)
			visual.rotation.y=lerp_angle(visual.rotation.y,face,1-exp(-14*delta))
		animator.speed_scale=clampf(animator.get_animation(clip).length/locomotion_pose.cycle_seconds,.5,3.2) if speed>.1 else 1.0
	else:
		animator.speed_scale=1.0
		if clip!=display_motion:play_motion(display_motion)
	if global_position.y< -3:global_position=Vector3(0,.1,0)

func set_clay(enabled: bool) -> void:
	for pair in original_materials:
		var material := StandardMaterial3D.new()
		material.albedo_color=Color("dad2c3");material.roughness=.8
		pair[0].material_override=material if enabled else pair[1]
