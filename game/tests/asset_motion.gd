extends SceneTree

const Player = preload("res://scripts/player.gd")
const Art = preload("res://scripts/art.gd")
var failed := false

func _initialize() -> void: call_deferred("run_test")

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed=true

func run_test() -> void:
	var world := Node3D.new()
	root.add_child(world)
	Art.box(world,Vector3(0,-0.2,0),Vector3(12,0.4,12),Color("879c78"),true)
	var environment := WorldEnvironment.new()
	environment.environment=Environment.new()
	environment.environment.background_mode=Environment.BG_COLOR
	environment.environment.background_color=Color("b7ccd1")
	environment.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color=Color.WHITE
	environment.environment.ambient_light_energy=0.5
	world.add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees=Vector3(-45,-25,0)
	sun.light_energy=0.7
	world.add_child(sun)
	var camera := Camera3D.new()
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.size=3.2
	world.add_child(camera)
	camera.position=Vector3(2,1.7,4)
	camera.look_at(Vector3(0,0.85,0))
	var player := Player.new()
	player.controls_enabled=false
	world.add_child(player)
	await create_timer(0.3).timeout
	expect(is_instance_valid(player.animation_player),"authored GLB skeleton animation controller imported")
	if not is_instance_valid(player.animation_player): quit(1); return
	expect(player.animation_player.has_animation("walk") and player.animation_player.has_animation("idle"),"walk and idle clips on one rig")
	expect(player.current_clip=="idle","stationary player selects idle")
	var skeletons := player.visual.find_children("*","Skeleton3D",true,false)
	expect(skeletons.size()==1,"exactly one skeleton for both clips")
	var skeleton: Skeleton3D=skeletons[0]
	var hip := skeleton.find_bone("Hip")
	expect(hip>=0,"hip bone exists")
	player.external_motion=Vector2(1,0)
	player.external_velocity=Vector2(preload("res://scripts/controller_profile.gd").VILLAGE_WALK,0)
	await create_timer(0.35).timeout
	expect(player.current_clip=="walk","movement selects walk animation")
	player.equip("axe")
	await create_timer(0.15).timeout
	var hand: Transform3D=player.hand_skeleton.global_transform*player.hand_skeleton.get_bone_global_pose(player.hand_index)
	expect(player.equipment.global_position.distance_to(hand.origin)<0.1,"crafted tool follows animated hand")
	var animated_joint := skeleton.find_bone("L_Thigh")
	var before := skeleton.get_bone_pose(animated_joint)
	await create_timer(0.25).timeout
	expect(not before.is_equal_approx(skeleton.get_bone_pose(animated_joint)),"walk changes the thigh pose while the root stays in place")
	# Pose playback must not move the authoritative CharacterBody.
	expect(Vector2(player.position.x,player.position.z).length()<0.001,"animation does not move collision body")
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/explorer-walk.png"))
	player.external_motion=Vector2.ZERO
	player.external_velocity=Vector2.ZERO
	await create_timer(0.4).timeout
	expect(player.current_clip=="idle","stopping returns smoothly to idle")
	var body_before := player.position
	player.react("gather")
	await create_timer(0.16).timeout
	var gather_visible: bool=player.current_clip=="slash" or (player.action_pose.kind=="gather" and player.action_pose.applied_amount>0)
	expect(gather_visible,"axe gather plays the available authored action")
	expect(player.position.distance_to(body_before)<0.01,"gather keeps authoritative collision body still")
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/explorer-gather.png"))
	await create_timer(0.5).timeout
	expect(player.action_pose.applied_amount==0,"action pose expires without accumulating bone rotation")
	player.equip("spear")
	player.react("attack")
	await create_timer(0.14).timeout
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/explorer-attack.png"))
	await create_timer(0.4).timeout
	world.queue_free()
	await process_frame
	print("ASSET_MOTION_COMPLETE")
	quit(1 if failed else 0)
