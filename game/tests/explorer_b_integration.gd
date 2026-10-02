extends SceneTree
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var stage := Node3D.new();root.add_child(stage)
	var actor=load("res://scripts/player.gd").new();actor.avatar={"character":"explorer_b","coat":"#dba448","pants":"#526552","boots":"#765744","backpack":false};actor.controls_enabled=false;stage.add_child(actor);actor.set_physics_process(false);actor.visual.rotation.y=PI
	var env := WorldEnvironment.new();env.environment=Environment.new();env.environment.background_mode=Environment.BG_COLOR;env.environment.background_color=Color("365b56");env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.environment.ambient_light_color=Color.WHITE;env.environment.ambient_light_energy=.18;stage.add_child(env)
	var sun := DirectionalLight3D.new();sun.rotation_degrees=Vector3(-35,-30,0);sun.light_energy=.6;stage.add_child(sun)
	var camera := Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=2.35;camera.position=Vector3(1,1.2,4);stage.add_child(camera);camera.look_at(Vector3(0,.85,0));camera.current=true
	var ok: bool=actor.animation_player.has_animation("walk") and actor.animation_player.has_animation("run") and actor.hand_skeleton.get_bone_count()>=71
	actor.animation_player.play("idle");await create_timer(1).timeout
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png("res://../artifacts/explorer-b-game.png")
	actor.apply_avatar(actor.avatar.merged({"coat":"#6889a1","pants":"#526552","boots":"#765744"},true))
	actor.animation_player.play("walk");await create_timer(.5).timeout
	var recolored := 0
	for mesh in actor.visual.find_children("*","MeshInstance3D",true,false):
		for index in mesh.mesh.get_surface_count():
			if mesh.get_surface_override_material(index) is ShaderMaterial:recolored+=1
	ok=ok and recolored==1
	actor.equip("axe");actor.react("gather");await create_timer(.2).timeout
	ok=ok and is_instance_valid(actor.tool_node) and actor.hand_index>=0
	ok=ok and actor.finger_pose.samples.size()==30 and actor.finger_pose.grip>.4
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png("res://../artifacts/explorer-b-tool.png")
	print("EXPLORER_B_INTEGRATION ",JSON.stringify({"ok":ok,"bones":actor.hand_skeleton.get_bone_count(),"recolored_surfaces":recolored}))
	quit(0 if ok else 1)
