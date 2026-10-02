extends SceneTree
## Actual physical input and contact correction, recorded as a review clip.
func _initialize() -> void:call_deferred("review")
func review() -> void:
	Engine.max_fps=30
	var stage := Node3D.new();root.add_child(stage)
	var actor=preload("res://scripts/player.gd").new();stage.add_child(actor)
	var floor := StaticBody3D.new();stage.add_child(floor)
	var shape := CollisionShape3D.new();floor.add_child(shape);var box := BoxShape3D.new();box.size=Vector3(80,.2,20);shape.shape=box;floor.position.y=-.1
	preload("res://scripts/art.gd").box(stage,Vector3(0,-.06,0),Vector3(80,.1,20),Color("b3bea5"))
	for x in range(-6,50):preload("res://scripts/art.gd").box(stage,Vector3(x,.001,0),Vector3(.018,.01,10),Color("91a285"))
	var env := WorldEnvironment.new();stage.add_child(env);env.environment=Environment.new();env.environment.background_mode=Environment.BG_COLOR;env.environment.background_color=Color("d2dacb")
	env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.environment.ambient_light_energy=.7
	var sun := DirectionalLight3D.new();stage.add_child(sun);sun.rotation_degrees=Vector3(-40,-30,0);sun.light_energy=.8;sun.shadow_enabled=true
	var camera := Camera3D.new();stage.add_child(camera);camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=3.2;camera.current=true
	var layer := CanvasLayer.new();root.add_child(layer);var title := Label.new();layer.add_child(title);title.position=Vector2(25,22);title.add_theme_font_size_override("font_size",25);title.add_theme_color_override("font_color",Color("3c4937"))
	var folder := ProjectSettings.globalize_path("res://../artifacts/controller-motion")
	DirAccess.make_dir_recursive_absolute(folder)
	await create_timer(.2).timeout
	var count := 0
	for segment in [["대기 · 원본 얼굴·손가락 유지",false,false,24],["산책 · 실제 이동 + 발 접지",true,false,75],["달리기 · 실제 이동 + 발 접지",true,true,65],["정지 · 대기 복귀",false,false,30]]:
		title.text=segment[0];actor.sprinting=segment[2]
		if segment[1]:Input.action_press("move_right")
		else:Input.action_release("move_right")
		for frame in segment[3]:
			await process_frame
			camera.position=actor.position+Vector3(3.5,1.9,5);camera.look_at(actor.position+Vector3.UP*.85)
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(folder.path_join("frame-%04d.png"%count));count+=1
	Input.action_release("move_right")
	print("CONTROLLER_MOTION ",count)
	stage.queue_free();layer.queue_free();await process_frame;await process_frame;quit()
