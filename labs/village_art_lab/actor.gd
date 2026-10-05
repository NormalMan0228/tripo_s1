extends CharacterBody3D
## Experiment actor: server/world motor owns travel, the skin owns only poses.
const WALK_SPEED := 2.8
const RUN_SPEED := 4.5
var visual: Node3D
var animator: AnimationPlayer
var skeleton: Skeleton3D
var motion_tree: AnimationTree
var foot_lock: SkeletonModifier3D
var manifest: Dictionary
var original_materials: Array=[]
var clip := "idle"
var display_motion := "idle"
var mode := "review"
var paused := false
var speed := 0.0
var phase := 0.0
var move_blend := 0.0
var run_blend := 0.0
var cycle_distance := 1.0
var playback_rate := 0.0
var scripted_input := Vector2.ZERO
var scripted_running := false
var scripted_control := false
var locomotion_velocity := Vector2.ZERO

func _ready() -> void:
	manifest=JSON.parse_string(FileAccess.get_file_as_string("res://assets/motion_manifest.json"))
	var shape := CollisionShape3D.new();var bounds := CapsuleShape3D.new()
	bounds.height=1.55;bounds.radius=.26;shape.shape=bounds;shape.position.y=.775
	add_child(shape);floor_snap_length=.35
	visual=Node3D.new();add_child(visual)
	var model := (load("res://assets/explorer_b.glb") as PackedScene).instantiate() as Node3D
	visual.add_child(model);model.scale=Vector3.ONE*1.7;model.rotation.y=PI*.5
	animator=model.find_children("*","AnimationPlayer",true,false)[0]
	skeleton=model.find_children("*","Skeleton3D",true,false)[0]
	skeleton.modifier_callback_mode_process=Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_PHYSICS
	for child in model.find_children("*","MeshInstance3D",true,false):original_materials.append([child,child.material_override])
	for name in ["idle","walk","run"]:animator.get_animation(name).loop_mode=Animation.LOOP_LINEAR
	var graph := AnimationNodeBlendTree.new()
	var idle := AnimationNodeAnimation.new();idle.animation="idle"
	var gait := AnimationNodeBlendSpace1D.new();gait.min_space=0;gait.max_space=1
	gait.sync_mode=AnimationNodeBlendSpace1D.SYNC_MODE_CYCLIC_CONSTANT;gait.cyclic_length=1.0
	var walk := AnimationNodeAnimation.new();walk.animation="walk"
	var run := AnimationNodeAnimation.new();run.animation="run"
	gait.add_blend_point(walk,0,-1,&"walk");gait.add_blend_point(run,1,-1,&"run")
	var pace := AnimationNodeTimeScale.new()
	var blend := AnimationNodeBlend2.new();blend.sync=true
	graph.add_node("Idle",idle);graph.add_node("Gait",gait);graph.add_node("Pace",pace);graph.add_node("Move",blend)
	graph.connect_node("Pace",0,"Gait");graph.connect_node("Move",0,"Idle")
	graph.connect_node("Move",1,"Pace");graph.connect_node("output",0,"Move")
	motion_tree=AnimationTree.new();model.add_child(motion_tree)
	motion_tree.tree_root=graph;motion_tree.anim_player=motion_tree.get_path_to(animator)
	motion_tree.root_node=motion_tree.get_path_to(animator.get_node(animator.root_node))
	motion_tree.callback_mode_process=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	motion_tree.active=false;play_motion("idle")
	foot_lock=preload("res://foot_lock.gd").new();skeleton.add_child(foot_lock);foot_lock.configure(self)

func play_motion(name: String) -> void:
	if not animator.has_animation(name):name="idle"
	clip=name;animator.play(name,.24)

func _physics_process(delta: float) -> void:
	if paused:return
	var input := scripted_input if scripted_control else Vector2(
		float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)),
		float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W))).limit_length()
	var running := scripted_running if scripted_control else Input.is_physical_key_pressed(KEY_SHIFT)
	if mode!="play":input=Vector2.ZERO
	var target: Vector2=input*(RUN_SPEED if running else WALK_SPEED)
	var planar := Vector2(velocity.x,velocity.z).move_toward(target,(16.0 if input.length()>.01 else 20.0)*delta)
	velocity.x=planar.x;velocity.z=planar.y
	velocity.y=0 if is_on_floor() else velocity.y-20*delta
	move_and_slide();locomotion_velocity=Vector2(get_real_velocity().x,get_real_velocity().z)
	speed=locomotion_velocity.length()
	if mode=="play":
		if not motion_tree.active:animator.stop();motion_tree.active=true
		if speed>.08:visual.rotation.y=lerp_angle(visual.rotation.y,atan2(-locomotion_velocity.x,-locomotion_velocity.y),1-exp(-12*delta))
		run_blend=move_toward(run_blend,clampf((speed-WALK_SPEED)/(RUN_SPEED-WALK_SPEED),0,1),delta*5)
		# Fade the pose with actual movement, including collisions and deceleration.
		move_blend=move_toward(move_blend,clampf(speed/.7,0,1),delta*6)
		var walk_distance: float=manifest.gaits.walk.cycle_distance_m
		var run_distance: float=manifest.gaits.run.cycle_distance_m
		cycle_distance=lerpf(walk_distance,run_distance,run_blend)
		playback_rate=speed/maxf(.2,cycle_distance)
		phase=fposmod(phase+delta*playback_rate,1)
		motion_tree.set("parameters/Gait/blend_position",run_blend)
		motion_tree.set("parameters/Pace/scale",playback_rate)
		motion_tree.set("parameters/Move/blend_amount",move_blend)
		motion_tree.advance(delta)
		clip="idle" if move_blend<.03 else ("run" if run_blend>.5 else "walk")
	else:
		if motion_tree.active:motion_tree.active=false;play_motion(display_motion)
		animator.speed_scale=1
		if clip!=display_motion:play_motion(display_motion)
	if global_position.y< -3:global_position=Vector3(0,.1,0)

func contact_strength(side: int) -> float:
	var key := "left_contact_mask" if side==0 else "right_contact_mask"
	var result := 0.0
	for pair in [["walk",1-run_blend],["run",run_blend]]:
		var mask: Array=manifest.gaits[pair[0]][key]
		var index := int(phase*mask.size())%mask.size()
		result+=(1.0 if mask[index] else 0.0)*pair[1]
	return result*move_blend

func set_clay(enabled: bool) -> void:
	for pair in original_materials:
		var material := StandardMaterial3D.new();material.albedo_color=Color("dad2c3");material.roughness=.8
		pair[0].material_override=material if enabled else pair[1]
