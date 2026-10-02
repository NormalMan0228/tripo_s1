extends SceneTree
## Deterministic frames of the authored clips; never calls a paid API.
func _initialize() -> void:call_deferred("review")
func review() -> void:
	var stage := Node3D.new();root.add_child(stage)
	var actor=preload("res://scripts/player.gd").new();actor.avatar={"character":"haeru","backpack":false};actor.controls_enabled=false;actor.visual_only=true;stage.add_child(actor)
	actor.set_physics_process(false)
	var env := WorldEnvironment.new();env.environment=Environment.new()
	env.environment.background_mode=Environment.BG_COLOR;env.environment.background_color=Color("c3cbbb")
	env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.environment.ambient_light_energy=.45
	stage.add_child(env)
	var light := DirectionalLight3D.new();light.rotation_degrees=Vector3(-42,-35,0);light.light_energy=.65;light.shadow_enabled=true;stage.add_child(light)
	preload("res://scripts/art.gd").box(stage,Vector3(0,-.08,0),Vector3(20,.1,20),Color("b5bea9"))
	var camera := Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=2.7;stage.add_child(camera)
	camera.position=Vector3(3.2,2.2,5);camera.look_at(Vector3(0,.95,0));camera.current=true
	var layer := CanvasLayer.new();root.add_child(layer)
	var card := Label.new();card.position=Vector2(32,30);card.add_theme_font_size_override("font_size",26);card.add_theme_color_override("font_color",Color("3f4b3a"));layer.add_child(card)
	var note := Label.new();note.position=Vector2(32,76);note.text="Tripo 메시·리그 / Blender에서 직접 만든 동작";note.add_theme_color_override("font_color",Color("52634d"));layer.add_child(note)
	var folder := ProjectSettings.globalize_path("res://../artifacts/haeru-motion")
	DirAccess.make_dir_recursive_absolute(folder)
	actor.animation_player.callback_mode_process=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var counter := 0
	for entry in [["idle","해루 · 주변 살피기",2.0],["walk","해루 · 걷기",2.5],["fishing","해루 · 낚시 대기",3.0],["greet","해루 · 인사",2.5]]:
		card.text=entry[1];actor.equip("rod" if entry[0] in ["fishing","greet"] else "")
		actor.animation_player.play(entry[0]);actor.animation_player.advance(0)
		for frame in int(entry[2]*24):
			actor.animation_player.advance(1.0/24.0)
			await process_frame;await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(folder.path_join("frame-%04d.png"%counter));counter+=1
	print("HAERU_MOTION_FRAMES ",counter)
	stage.queue_free();layer.queue_free();await process_frame;await process_frame;quit()
