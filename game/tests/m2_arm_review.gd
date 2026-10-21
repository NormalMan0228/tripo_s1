extends SceneTree
const Player=preload("res://scripts/player.gd")
const Art=preload("res://scripts/art.gd")
var out := ""
func _initialize() -> void:call_deferred("review")
func review() -> void:
	out=ProjectSettings.globalize_path("res://../artifacts")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--artifacts="):out=arg.trim_prefix("--artifacts=")
	var stage := Node3D.new();root.add_child(stage)
	var environment := WorldEnvironment.new();stage.add_child(environment);environment.environment=Environment.new()
	environment.environment.background_mode=Environment.BG_COLOR;environment.environment.background_color=Color("d2dacd")
	environment.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;environment.environment.ambient_light_energy=.65
	var sun := DirectionalLight3D.new();stage.add_child(sun);sun.rotation_degrees=Vector3(-40,-25,0)
	Art.box(stage,Vector3(0,-.06,-3),Vector3(16,.1,13),Color("b9c4b0"))
	var camera := Camera3D.new();stage.add_child(camera);camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=7.3;camera.current=true
	camera.position=Vector3(0,10,14);camera.look_at(Vector3(0,1,-3.2))
	var report: Array=[]
	var actors: Array=[]
	for row in 3:
		for col in 5:
			var id := "m1" if row==0 else "m2"
			var clip: String=["RESET","idle","walk","run","slash"][col]
			var actor := Player.new();actor.avatar={"character":id,"backpack":false};actor.controls_enabled=false;actor.visual_only=true
			stage.add_child(actor);actor.position=Vector3((col-2)*2.15,0,-row*3.3)
			actor.set_meta("review_row",row);actor.set_meta("review_clip",clip);actors.append(actor)
			actor.set_physics_process(false);actor.visual.visible=true;actor.visual.rotation.y=0 if row==2 else PI
			var animator: AnimationPlayer=actor.animation_player
			animator.callback_mode_process=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
			if animator.has_animation(clip):animator.play(clip);animator.seek([0.,.5,.35,.2,1.35][col],true)
			var label := Art.label3d(stage,id+" / "+clip+(" BACK" if row==2 else ""),actor.position+Vector3(0,2.1,0),Color("263e37"))
			label.font_size=42;label.pixel_size=.005
			var bones := {}
			for name in ["L_Upperarm","L_Forearm","L_Hand","R_Upperarm","R_Forearm","R_Hand"]:
				var index: int=actor.hand_skeleton.find_bone(name)
				if index>=0:
					var pos: Vector3=actor.global_transform.affine_inverse()*actor.hand_skeleton.global_transform*actor.hand_skeleton.get_bone_global_pose(index).origin
					bones[name]=[pos.x,pos.y,pos.z]
			report.append({"id":id,"clip":clip,"back":row==2,"bones":bones})
	await create_timer(.4).timeout;await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("m2-arm-review.png"))
	for label in stage.find_children("*","Label3D",true,false):label.visible=false
	var selected := ["idle","walk","slash"]
	for actor in actors:
		var clip: String=actor.get_meta("review_clip")
		actor.visible=int(actor.get_meta("review_row"))==1 and clip in selected
		if not actor.visible:continue
		actor.position=Vector3((selected.find(clip)-1)*1.65,0,0)
		if clip=="slash":actor.equip("axe")
		var label := Art.label3d(stage,{"idle":"대기","walk":"걷기","slash":"공격"}[clip],actor.position+Vector3(0,2.02,0),Color("263e37"))
		label.font_size=48;label.pixel_size=.004
	camera.size=3.6;camera.position=Vector3(0,2.5,8);camera.look_at(Vector3(0,1,0))
	await create_timer(.2).timeout;await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out.path_join("m2-arm-detail.png"))
	var output := FileAccess.open(out.path_join("m2-arm-review.json"),FileAccess.WRITE);output.store_string(JSON.stringify(report,"\t"));output.close()
	stage.queue_free();await process_frame;await process_frame
	print("M2_ARM_REVIEW_DONE");quit()
